"""
Classes for constructing an OAA JSON payload for Entity Enrichment

Copyright 2026 Veza Technologies Inc.

Use of this source code is governed by the MIT
license that can be found in the LICENSE file or at
https://opensource.org/licenses/MIT.
"""

from __future__ import annotations
import logging
import re
# from enum import Enum
# from typing import List, Optional

from .common import CaseInsensitiveDict, OAAPropertyType, PROPERTY_NAME_REGEX
from .exceptions import OAATemplateException

log = logging.getLogger(__name__)

###############################################################################
# Entity Enrichment
###############################################################################
class EntityEnrichment():
    """Class for modeling Entity Enrichment using the OAA Entity Enrichment template.

    The Entity Enrichment template attaches custom properties to existing Veza entities (such as `AwsIamRole`,
    `AwsIamUser` or `OktaUser`) discovered by other integrations. Unlike other OAA templates it does not create
    new entities; it only enriches existing ones with additional searchable metadata.

    Enriched entities are tracked internally in a case insensitive dictionary keyed by the composite of entity
    type, data source id, and id so the same entity id can be enriched across multiple data sources or types.
    The index is private; use `add_entity` to add entities and `get_entity` to retrieve them.

    Args:
        name (str): Name for the Entity Enrichment instance. Used when creating the provider but not included
            in the payload itself.

    Attributes:
        name (str): Name for the Entity Enrichment instance
        property_definitions (EntityEnrichmentPropertyDefinitions): Custom property definitions grouped by
            Veza entity type
    """

    TEMPLATE = "entity_enrichment"

    def __init__(self, name: str):
        self.name = name

        self._enriched_entities = CaseInsensitiveDict()
        self.property_definitions = EntityEnrichmentPropertyDefinitions()

    def __str__(self) -> str:
        return f"EntityEnrichment {self.name}"

    def __repr__(self) -> str:
        return f"EntityEnrichment(name={self.name!r})"

    def get_payload(self) -> dict:
        """Get the OAA payload.

        Returns the complete OAA template payload for entity enrichment as serializable dictionary

        Returns:
            dict: OAA payload as dictionary
        """

        payload = {"enriched_entity_property_definitions": self.property_definitions.to_dict(),
                   "enriched_entities": [entity.to_dict() for entity in self._enriched_entities.values()]
                  }

        return payload

    def _entity_key(self, entity_type: str, id: str, data_source_id: str) -> str:
        """Build the internal index key for an entity.

        The composite key keeps entities unique by the combination of type, data source and id so the same
        entity id can be enriched across multiple data sources or types. Kept private so the key format can
        change without affecting callers.

        Args:
            entity_type (str): Veza entity type (e.g. "AwsIamRole", "OktaUser")
            id (str): Veza unique ID for the entity.
            data_source_id (str): ID of the Veza data source that owns the entity.

        Returns:
            str: Composite key `"{entity_type}:{data_source_id}:{id}"`
        """

        return f"{entity_type}:{data_source_id}:{id}"

    def add_entity(self, entity_type: str, id: str, data_source_id: str) -> EnrichedEntity:
        """Add an entity to enrich

        Creates a new EnrichedEntity for an existing Veza entity. The entity is tracked internally keyed by the
        composite of entity type, data source id, and id so each entity may appear only once within the payload.

        Args:
            entity_type (str): Veza entity type (e.g. "AwsIamRole", "OktaUser")
            id (str): Veza unique ID for the entity. For AWS entities this is the ARN.
            data_source_id (str): ID of the Veza data source that owns the entity. For AWS this is the account
                ID combined with the data source type (e.g. "339083562601:awsiam").

        Raises:
            OAATemplateException: Entity with the same type, id, and data_source_id already exists

        Returns:
            EnrichedEntity: Entity for the new enrichment record
        """

        entity = EnrichedEntity(entity_type=entity_type, id=id, data_source_id=data_source_id)
        entity_key = self._entity_key(entity.entity_type, entity.id, entity.data_source_id)

        if entity_key in self._enriched_entities:
            raise OAATemplateException(f"Entity already defined: type={entity.entity_type}, id={entity.id}, data_source_id={entity.data_source_id}")

        self._enriched_entities[entity_key] = entity
        self._enriched_entities[entity_key]._property_definitions = self.property_definitions.entity_properties

        return self._enriched_entities[entity_key]

    def get_entity(self, entity_type: str, id: str, data_source_id: str) -> EnrichedEntity:
        """Get a previously added entity to enrich.

        Looks up an entity added with `add_entity` by its type, id, and data source id.

        Args:
            entity_type (str): Veza entity type (e.g. "AwsIamRole", "OktaUser")
            id (str): Veza unique ID for the entity. For AWS entities this is the ARN.
            data_source_id (str): ID of the Veza data source that owns the entity.

        Raises:
            OAATemplateException: No entity with the given type, id, and data_source_id has been added

        Returns:
            EnrichedEntity: The matching enrichment record
        """

        entity_key = self._entity_key(entity_type, id, data_source_id)

        if entity_key not in self._enriched_entities:
            raise OAATemplateException(f"Entity not found: type={entity_type}, id={id}, data_source_id={data_source_id}")

        return self._enriched_entities[entity_key]

class EnrichedEntity():
    """Enriched Entity

    Represents a single Veza entity to enrich with custom property values. The entity is identified by the
    combination of `entity_type`, `id` and `data_source_id`. Init variables are all required and must not be
    empty such as `""`.

    Args:
        entity_type (str): Veza entity type, e.g. "AwsIamRole", "OktaUser"
        id (str): Veza unique ID for the entity. For AWS entities this is the ARN.
        data_source_id (str): ID of the Veza data source that owns the entity.

    Raises:
        ValueError: Any of the required arguments are empty.

    """

    def __init__(self, entity_type: str, id: str, data_source_id: str):

        if not entity_type:
            raise ValueError("entity_type cannot be empty")
        if not id:
            raise ValueError("id cannot be empty")
        if not data_source_id:
            raise ValueError("data_source_id cannot be empty")

        self.entity_type: str = entity_type
        self.id: str = id
        self.data_source_id: str = data_source_id

        self._property_definitions = None
        self.custom_properties: dict = {}

    def __str__(self) -> str:
        return f"EnrichedEntity - {self.entity_type} ({self.id})"

    def __repr__(self) -> str:
        return f"EnrichedEntity(entity_type={self.entity_type!r}, id={self.id!r}, data_source_id={self.data_source_id!r})"

    def set_property(self, property_name: str, property_value: any, ignore_none: bool = False) -> None:
        """Set Enriched Entity custom property value

        Property name must be defined for the entity's type before calling `set_property`

        Args:
            property_name (str): Name of property
            property_value (any): Value for property, type should match OAAPropertyType for property definition
            ignore_none (bool, optional): Do not set property if value is None. Defaults to False.

        Raises:
            OAATemplateException: If property with `property_name` is not defined for the entity type.
        """

        if self._property_definitions is not None:
            if not isinstance(self._property_definitions, dict):
                raise OAATemplateException("entity property_definitions not of expected type")

            entity_type_props = self._property_definitions.get(self.entity_type)
            if entity_type_props is None or property_name not in entity_type_props:
                raise OAATemplateException(f"unknown property name {property_name} for entity type {self.entity_type}")
        else:
            log.warning("Entity does not have property names set, cannot validate property name")

        if ignore_none and property_value is None:
            return

        self.custom_properties[property_name] = property_value

        return

    def to_dict(self) -> dict:
        """ Output enriched entity to dictionary for payload. """

        return {"type": self.entity_type,
                "id": self.id,
                "data_source_id": self.data_source_id,
                "properties": self.custom_properties
                }

class EntityEnrichmentPropertyDefinitions():
    """Model for defining custom properties for Entity Enrichment.

    Property definitions are grouped by Veza entity type. Each entity type maintains its own set of property
    names and types that may be set on enriched entities of that type.

    Attributes:
        entity_properties (dict): Property definitions keyed by entity type. Each value is a dictionary mapping
            property name to its OAAPropertyType.
    """

    def __init__(self):

        self.entity_properties = {}

    def __str__(self) -> str:
        return "EntityEnrichmentPropertyDefinitions"

    def __repr__(self) -> str:
        return "EntityEnrichmentPropertyDefinitions()"

    def to_dict(self) -> list:
        """ Return property definitions as list ready for OAA payload """

        definitions = []
        for entity_type, properties in self.entity_properties.items():
            definitions.append({"entity_type": entity_type,
                                "enriched_properties": {k: v for k, v in properties.items()}
                               })

        return definitions

    def define_property(self, entity_type: str, name: str, property_type: OAAPropertyType) -> None:
        """Define a property for an entity type.

        Args:
            entity_type (str): Veza entity type the property applies to (e.g. "AwsIamRole")
            name (str): name for property
            property_type (OAAPropertyType): type for property

        Raises:
            OAATemplateException: `entity_type` is not a non-empty string
            OAATemplateException: `name` contains invalid characters or is not a string
            OAATemplateException: `property_type` is not an OAAPropertyType enum
        """

        if not isinstance(entity_type, str) or not entity_type:
            raise OAATemplateException("entity_type must be a non-empty string")

        self.validate_name(name)
        self._validate_types(name, property_type)

        if entity_type not in self.entity_properties:
            self.entity_properties[entity_type] = {}

        self.entity_properties[entity_type][name] = property_type

    def _validate_types(self, name: str, property_type: OAAPropertyType) -> None:
        """ Helper function to validate that custom property parameters are of the correct types.

        Args:
            name (str): name or property
            property_type (OAAPropertyType): OAA type for property

        """
        if not isinstance(name, str):
            raise OAATemplateException("property name must be type string")
        if not isinstance(property_type, OAAPropertyType):
            raise OAATemplateException("property_type must be type OAAPropertyType enum")

        return

    def validate_name(self, name: str) -> None:
        """Check property name for valid characters

        Raises an exception if the name string does not match required pattern. Name must start with
        a character and can only contain letters and _ character.

        Args:
            name (str): name of property to validate

        Raises:
            OAATemplateException: Name is not a string
            OAATemplateException: Name contains invalid characters or does not start with a letter
        """

        if not isinstance(name, str):
            raise OAATemplateException(f"Property name must be a string, received {type(name)}")

        if not re.match(PROPERTY_NAME_REGEX, name.lower()):
            raise OAATemplateException(f"Lower-cased property name must match the pattern: '{PROPERTY_NAME_REGEX}'. Invalid name: {name}")

        return