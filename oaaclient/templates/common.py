"""
Copyright 2026 Veza Technologies Inc.

Use of this source code is governed by the MIT
license that can be found in the LICENSE file or at
https://opensource.org/licenses/MIT.
"""

from __future__ import annotations

import json
import re
from enum import Enum
from typing import List, Optional

from oaaclient.structures import CaseInsensitiveDict  # noqa: F401
from .exceptions import OAATemplateException

PROPERTY_NAME_REGEX=r"^[a-z][a-z_]*$"

class IdPProviderType(str, Enum):
    """ Veza supported IdP provider types. """

    ACTIVE_DIRECTORY = "active_directory"
    ANY = "any"
    AZURE_AD = "azure_ad"
    CUSTOM = "custom"
    GOOGLE_WORKSPACE = "google_workspace"
    OKTA = "okta"
    ONE_LOGIN = "one_login"


class OAAOwnerType(str, Enum):
    """ Node types for entity owners """
    ActiveDirectoryUser = "activedirectoryuser"
    AzureADUser = "azureaduser"
    GoogleWorkspaceUser = "googleworkspaceuser"
    OktaUser = "oktauser"

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}.{self.name}'

class OAAPropertyType(str, Enum):
    """ Supported types for custom properties on OAA entities such as application, resource, and identity.  """

    BOOLEAN = "BOOLEAN"                 # True/False boolean
    NUMBER = "NUMBER"                   # integer number
    STRING = "STRING"                   # string
    STRING_LIST = "STRING_LIST"         # list of strings
    TIMESTAMP = "TIMESTAMP"             # RFC3339 formatted time stamp 2022-02-08T13:10:50.25Z


class IdentityMappingType(str, Enum):
    """Identity mapping match type.

    Corresponds to ``IdentityMapping.Type`` in identitymapping.proto.
    """

    EQUAL = "EQUAL"           # Match identities by direct equality
    CUSTOM = "CUSTOM"         # Custom matching (only via experimental feature)


class IdentityMappingMode(str, Enum):
    """Identity mapping mode.

    Corresponds to ``IdentityMapping.Mode`` in identitymapping.proto.
    """

    USERS = "USERS"               # Default. Connects users to users.
    GROUPS = "GROUPS"             # Connect groups to groups.
    ROLE_TO_USER = "ROLE_TO_USER" # Connect roles to users (e.g., AWS IAM roles to application users).


class IdentityMappingTransformation(str, Enum):
    """Identity mapping transformation applied to identity values before matching.

    Corresponds to ``IdentityMapping.Transformations`` in identitymapping.proto.
    """

    IGNORE_SPECIAL = "IGNORE_SPECIAL"   # Strip special characters before comparing
    IGNORE_DOMAIN = "IGNORE_DOMAIN"     # Strip domain suffix before comparing


class IdentityMappingProperty(str, Enum):
    """Identity property used as source or destination in a property matcher.

    Corresponds to ``IdentityMapping.Property`` in identitymapping.proto.
    """

    UNIQUE_ID = "UNIQUE_ID"               # Unique identifier of the identity
    EMAIL = "EMAIL"                       # Email address of the identity
    CUSTOM_PROPERTY = "CUSTOM_PROPERTY"   # A named custom property on the identity
    PROPERTY = "PROPERTY"                 # A standard property on the identity
    TEMPLATE = "TEMPLATE"                 # A template-rendered value


class Provider():
    """Base class for CustomProvider. """
    def __init__(self, name, custom_template):
        self.name = name
        self.custom_template = custom_template

    def serialize(self):
        return json.dumps({"name": self.name, "custom_template": self.custom_template})



###############################################################################
# Shared models
###############################################################################
class Tag():
    """ Veza Tag data model.

    Args:
        key (str): key for tag, aka name. Must be present and must be letters, numbers or _ (underscore) only.
        value (str, optional): Value for tag, will appear in Veza as `key:value`. Must be letters, numbers, whitespace and the special characters @,._- only.

    Attributes:
        key (str): key for tag, aka name. Must be present and must be letters, numbers or _ (underscore) only.
        value (str): Value for tag, will appear in Veza as `key:value`. Must be letters, numbers and the special characters @,._ only.
    """

    def __init__(self, key: str, value: str = "") -> None:
        self.key = str(key)
        self.value = str(value)

        if not re.match(r"^[\w\d_]+$", self.key):
            raise OAATemplateException(f"Invalid characters in tag key. Key '{self.key}'. Key may only contain letters, numbers, and _ (underscore)")
        if self.value != "" and not re.match(r"^[\w\d\s_,@\.-]+$", self.value):
            raise OAATemplateException(f"Invalid characters in tag value. Value '{self.value}'. Value may only contain letters, numbers, whitespace and the special characters @,._-")

    def __str__(self) -> str:
        if self.value:
            return f"Tag {self.key}:{self.value}"
        else:
            return f"Tag {self.key}"

    def __repr__(self) -> str:
        return f"Tag(key={self.key!r}, value={self.value!r})"

    def __eq__(self, o):
        if self.key == o.key and self.value == o.value:
            return True
        else:
            return False

class EntityOwner():

    def __init__(self, external_id: str, owner_type: str, is_primary: bool = False) -> None:
        self.external_id = external_id
        self.owner_type = owner_type
        self.primary = is_primary

    def __str__(self) -> str:
        return f"EntityOwner {self.owner_type}:{self.external_id}"

    def __repr__(self) -> str:
        return f"EntityOwner(external_id={self.external_id!r}, owner_type={self.owner_type!r}, is_primary={self.is_primary!r})"

    def __eq__(self, o):
        if self.external_id == o.external_id and self.owner_type == o.owner_type:
            return True
        else:
            return False


class IdentityMappingConfigurationSubmission():
    """Identity mapping configuration submission.

    Top-level container for identity mapping configuration in an OAA payload.

    Args:
        use_email (bool): Whether to use email for identity mapping. Defaults to False.
        operation (str, optional): Operation type for this configuration.

    Attributes:
        use_email (bool): Whether to use email for identity mapping. Default False.
        mappings (list[IdentityMappingSubmission]): List of identity mappings.
        operation (str): Operation type. Default None.
    """

    def __init__(self) -> None:
        self.mappings: List[IdentityMappingSubmission] = []
        self.use_email = False
        self.operation = None

    def __str__(self) -> str:
        return f"IdentityMappingConfigurationSubmission"

    def __repr__(self) -> str:
        return f"IdentityMappingConfigurationSubmission()"

    def add_mapping(self, destination_datasource_type: str, destination_datasource_oaa_type: str, mapping_type: str, mapping_mode: str = "", transformations: List[str] = None, custom_value: str = "") -> IdentityMappingSubmission:
        """Add an identity mapping.

        Args:
            destination_datasource_type (str): Destination datasource type.
            destination_datasource_oaa_type (str): Destination datasource OAA app type.
            mapping_type (str): Mapping type. Use :class:`IdentityMappingType` for valid values.
            mapping_mode (str, optional): Mapping mode. Use :class:`IdentityMappingMode` for valid values. Defaults to "".
            transformations (list[str], optional): List of transformations. Use :class:`IdentityMappingTransformation` for valid values. Defaults to None.
            custom_value (str, optional): Custom value. Defaults to "".

        Returns:
            IdentityMappingSubmission: The new mapping.
        """

        mapping = IdentityMappingSubmission(
            destination_datasource_type=destination_datasource_type,
            destination_datasource_oaa_type=destination_datasource_oaa_type,
            mapping_type=mapping_type,
            mapping_mode=mapping_mode,
            transformations=transformations or [],
            custom_value=custom_value,
        )
        self.mappings.append(mapping)
        return mapping

    def to_dict(self) -> dict:
        """Return the dictionary representation."""

        repr = {
            "use_email": self.use_email,
            "mappings": [mapping.to_dict() for mapping in self.mappings],
            "operation": self.operation,
        }

        return {k: v for k, v in repr.items() if v not in [None, [], ""]}


class IdentityMappingSubmission():
    """Identity mapping submission.

    Represents a single identity mapping configuration entry.

    Args:
        destination_datasource_type (str): Destination datasource type.
        destination_datasource_oaa_type (str): Destination datasource OAA app type.
        mapping_type (str): Mapping type (serialized as ``type``). Use :class:`IdentityMappingType` for valid values.
        mapping_mode (str, optional): Mapping mode (serialized as ``mode``). Use :class:`IdentityMappingMode` for valid values. Defaults to "".
        transformations (list[str], optional): List of transformations. Use :class:`IdentityMappingTransformation` for valid values. Defaults to None.
        custom_value (str, optional): Custom value. Defaults to "".

    Attributes:
        destination_datasource_type (str): Destination datasource type.
        destination_datasource_oaa_type (str): Destination datasource OAA app type.
        mapping_type (IdentityMappingType): Mapping type.
        mapping_mode (IdentityMappingMode): Mapping mode.
        transformations (list[IdentityMappingTransformation]): List of transformations.
        custom_value (str): Custom value.
        property_matchers (list[IdentityMappingPropertyMatchersSubmission]): Property matchers.
        destination_datasources (list[IdentityMappingDestinationDatasourceSubmission]): Destination datasources.
    """

    def __init__(self, destination_datasource_type: str, destination_datasource_oaa_type: str, mapping_type: str, mapping_mode: str = "", transformations: List[str] = None, custom_value: str = "") -> None:
        if not destination_datasource_type:
            raise ValueError("destination_datasource_type cannot be empty")
        if not mapping_type:
            raise ValueError("mapping_type cannot be empty")
        self.destination_datasource_type = destination_datasource_type
        self.destination_datasource_oaa_type = destination_datasource_oaa_type
        self.mapping_type = mapping_type
        self.mapping_mode = mapping_mode
        self.transformations: List[str] = transformations or []
        self.custom_value = custom_value
        self.property_matchers: List[IdentityMappingPropertyMatchersSubmission] = []
        self.destination_datasources: List[IdentityMappingDestinationDatasourceSubmission] = []

    def __str__(self) -> str:
        return f"IdentityMappingSubmission {self.destination_datasource_type} - {self.mapping_type}"

    def __repr__(self) -> str:
        return f"IdentityMappingSubmission(destination_datasource_type={self.destination_datasource_type!r}, mapping_type={self.mapping_type!r})"

    def add_property_matcher(self, source_property: str, destination_property: str, custom_source_property: str = "", custom_destination_property: str = "") -> IdentityMappingPropertyMatchersSubmission:
        """Add a property matcher.

        Args:
            source_property (str): Source property to match on. Use :class:`IdentityMappingProperty` for valid values.
            destination_property (str): Destination property to match against. Use :class:`IdentityMappingProperty` for valid values.
            custom_source_property (str, optional): Custom source property name, used when ``source_property`` is :attr:`IdentityMappingProperty.CUSTOM_PROPERTY`. Defaults to "".
            custom_destination_property (str, optional): Custom destination property name, used when ``destination_property`` is :attr:`IdentityMappingProperty.CUSTOM_PROPERTY`. Defaults to "".

        Returns:
            IdentityMappingPropertyMatchersSubmission: The new property matcher.
        """

        matcher = IdentityMappingPropertyMatchersSubmission(
            source_property=source_property,
            destination_property=destination_property,
            custom_source_property=custom_source_property,
            custom_destination_property=custom_destination_property,
        )
        self.property_matchers.append(matcher)
        return matcher

    def add_destination_datasource(self, datasource_type: str, oaa_type: str) -> IdentityMappingDestinationDatasourceSubmission:
        """Add a destination datasource.

        Args:
            datasource_type (str): Datasource type.
            oaa_type (str): OAA app type.

        Returns:
            IdentityMappingDestinationDatasourceSubmission: The new destination datasource.
        """

        datasource = IdentityMappingDestinationDatasourceSubmission(
            datasource_type=datasource_type,
            oaa_type=oaa_type,
        )
        self.destination_datasources.append(datasource)
        return datasource

    def to_dict(self) -> dict:
        """Return the dictionary representation."""

        repr = {
            "destination_datasource_type": self.destination_datasource_type,
            "destination_datasource_oaa_app_type": self.destination_datasource_oaa_type,
            "type": self.mapping_type,
            "mode": self.mapping_mode,
            "transformations": self.transformations,
            "custom_value": self.custom_value,
            "property_matchers": [pm.to_dict() for pm in self.property_matchers],
            "destination_datasources": [ds.to_dict() for ds in self.destination_datasources],
        }

        return {k: v for k, v in repr.items() if v not in [None, [], ""]}


class IdentityMappingPropertyMatchersSubmission():
    """Identity mapping property matcher.

    Defines how source and destination properties are matched.

    Args:
        source_property (str): Source property to match on. Use :class:`IdentityMappingProperty` for valid values.
        destination_property (str): Destination property to match against. Use :class:`IdentityMappingProperty` for valid values.
        custom_source_property (str, optional): Custom source property name, used when ``source_property`` is :attr:`IdentityMappingProperty.CUSTOM_PROPERTY`. Defaults to "".
        custom_destination_property (str, optional): Custom destination property name, used when ``destination_property`` is :attr:`IdentityMappingProperty.CUSTOM_PROPERTY`. Defaults to "".
    """

    def __init__(self, source_property: str, destination_property: str, custom_source_property: str = "", custom_destination_property: str = "") -> None:
        self.source_property = source_property
        self.destination_property = destination_property
        self.custom_source_property = custom_source_property
        self.custom_destination_property = custom_destination_property

    def __str__(self) -> str:
        return f"IdentityMappingPropertyMatchersSubmission {self.source_property} -> {self.destination_property}"

    def __repr__(self) -> str:
        return f"IdentityMappingPropertyMatchersSubmission(source_property={self.source_property!r}, destination_property={self.destination_property!r})"

    def to_dict(self) -> dict:
        """Return the dictionary representation."""

        repr = {
            "source_property": self.source_property,
            "destination_property": self.destination_property,
            "custom_source_property": self.custom_source_property,
            "custom_destination_property": self.custom_destination_property,
        }

        return {k: v for k, v in repr.items() if v not in [None, ""]}


class IdentityMappingDestinationDatasourceSubmission():
    """Identity mapping destination datasource.

    Specifies a destination datasource for an identity mapping.

    Args:
        datasource_type (str): Datasource type (serialized as ``type``).
        oaa_type (str): OAA app type (serialized as ``oaa_app_type``).
    """

    def __init__(self, datasource_type: str, oaa_type: str) -> None:
        self.datasource_type = datasource_type
        self.oaa_type = oaa_type

    def __str__(self) -> str:
        return f"IdentityMappingDestinationDatasourceSubmission {self.datasource_type}"

    def __repr__(self) -> str:
        return f"IdentityMappingDestinationDatasourceSubmission(datasource_type={self.datasource_type!r}, oaa_type={self.oaa_type!r})"

    def to_dict(self) -> dict:
        """Return the dictionary representation."""

        return {
            "type": self.datasource_type,
            "oaa_app_type": self.oaa_type,
        }


###############################################################################
# Helper functions
###############################################################################

def append_helper(base, addition):
    """ Helper function to simplify appending.

    Handles multiple cases:

    - base is None: starts a list
    - addition is list: extends base with list
    - addition is anything else: append element to list

    Args:
        base (List or None): base list to append to, can be None
        addition (*): What to append to the list

    Returns:
        list: will always return a list
    """
    if addition is None:
        return base

    if base is None:
        base = []

    if isinstance(addition, list):
        base.extend(addition)
    else:
        base.append(addition)

    return base

def unique_strs(input: list) -> list:
    """Returns a list of unique strings from input list case insensitive

    Returns the unique list of strings from input list in a case insensitive manner.
    For duplicate strings with different cast (e.g. "STRING" and "string") the case of
    the first occurrence is returned.

    Args:
        input (list): list of strings

    Returns:
        list: list of unique strings
    """

    if not isinstance(input, list):
        raise ValueError("input must be list")

    unique = []
    seen = []
    for e in input:
        if not isinstance(e, str):
            raise ValueError("input elements must be string")
        if e.lower() not in seen:
            seen.append(e.lower())
            unique.append(e)

    return unique