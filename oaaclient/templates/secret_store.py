"""
Classes for constructing an OAA JSON payload for Secret Store

Copyright 2026 Veza Technologies Inc.

Use of this source code is governed by the MIT
license that can be found in the LICENSE file or at
https://opensource.org/licenses/MIT.
"""

from __future__ import annotations

import logging
import re
from typing import List, Optional

from .application import OAAPermission
from .common import PROPERTY_NAME_REGEX, CaseInsensitiveDict, IdentityMappingConfigurationSubmission, OAAPropertyType, Tag
from .exceptions import OAATemplateException

log = logging.getLogger(__name__)

###############################################################################
# Secret Store Template
###############################################################################

class SecretStoreSubmission():
    """Class for modeling Secret Store Template

    SecretStore template consists of base information about the secret store instance,
    permissions, vaults, entries, and identity mappings.

    Args:
        name (str): Name for Secret Store Instance
        secret_store_type (str): Type for Secret Store. Typically the vendor or product name.
        unique_id (str): Unique identify for secret store instance. Optional, defaults to name.
        skip_local_users_creation (bool, optional): Skip creation of local user identities for this secret store. Defaults to None.

    Attributes:
        secret_store (SecretStore): The secret store entity
        property_definitions (SecretStorePropertyDefinitions): Custom property definitions
        identity_mapping_configuration (IdentityMappingConfigurationSubmission): Identity mapping configuration, set via :meth:`set_identity_mapping_configuration`.
        skip_local_users_creation (bool, optional): Skip creation of local user identities for this secret store.
    """

    TEMPLATE = "secret_store"

    def __init__(self, name: str, secret_store_type: str, unique_id: str = None, skip_local_users_creation: Optional[bool] = None):
        self.name = name
        self.secret_store_type = secret_store_type

        self.property_definitions = SecretStorePropertyDefinitions()
        self.identity_mapping_configuration: Optional[IdentityMappingConfigurationSubmission] = None
        self.secret_store = self._set_secret_store(name=name, unique_id=unique_id)
        self.incremental_change: bool = False
        self.skip_local_users_creation: Optional[bool] = skip_local_users_creation

    def __str__(self) -> str:
        return f"SecretStoreSubmission {self.name} - {self.secret_store_type}"

    def __repr__(self) -> str:
        return f"SecretStoreSubmission(name={self.name!r}, secret_store_type={self.secret_store_type!r})"

    def get_payload(self) -> dict:
        """Get the OAA payload.

        Returns the complete OAA template payload for Secret Store as serializable dictionary

        Returns:
            dict: OAA payload as dictionary

        Raises:
            OAATemplateException: If secret_store is not set
        """

        if self.secret_store is None:
            raise OAATemplateException("secret_store must be set before generating payload")

        payload = {
            "secret_store_type": self.secret_store_type,
            "custom_property_definition": self.property_definitions.to_dict(),
            "secret_store": self.secret_store.to_dict()
        }

        if self.incremental_change:
            payload["incremental_change"] = self.incremental_change

        if self.skip_local_users_creation is not None:
            payload["skip_local_users_creation"] = self.skip_local_users_creation

        if self.identity_mapping_configuration is not None:
            payload["identity_mapping_configuration"] = self.identity_mapping_configuration.to_dict()

        return payload

    def set_identity_mapping_configuration(self) -> IdentityMappingConfigurationSubmission:
        """Create and set the identity mapping configuration.

        Initializes the :attr:`identity_mapping_configuration` attribute with a new
        :class:`IdentityMappingConfigurationSubmission` instance and returns it for further
        configuration.

        Returns:
            IdentityMappingConfigurationSubmission: The identity mapping configuration.
        """

        self.identity_mapping_configuration = IdentityMappingConfigurationSubmission()
        return self.identity_mapping_configuration

    def _set_secret_store(self, name: str, unique_id: str = None, description: str = None) -> SecretStore:
        """Create and set the secret store entity

        Args:
            name (str): Display name for secret store
            unique_id (str, optional): Unique identifier for secret store. Defaults to name if not provided.
            description (str, optional): Description of the secret store

        Returns:
            SecretStore: The secret store entity
        """

        self.secret_store = SecretStore(name=name, unique_id=unique_id, description=description)
        self.secret_store._property_definitions = self.property_definitions.secret_store_properties
        self.secret_store._all_property_definitions = self.property_definitions

        return self.secret_store

class SecretStore():
    """Secret Store Entity

    Represents a secret store application with permissions, vaults, and identity mappings.

    Args:
        name (str): Display name for secret store
        unique_id (str, optional): Unique identifier for secret store
        description (str, optional): Description of the secret store
    """

    def __init__(self, name: str, unique_id: str = None, description: str = None):
        if not name:
            raise ValueError("name cannot be empty")

        self.name = name
        self.id = unique_id if unique_id else name
        self.description = description

        self.tags: List[Tag] = []
        self.custom_properties: dict = {}
        self.operation: Optional[str] = None

        self.permissions = CaseInsensitiveDict()
        self.vaults = CaseInsensitiveDict()
        self.identity_to_permissions = CaseInsensitiveDict()

        self._property_definitions = None
        self._all_property_definitions = None

    def __str__(self) -> str:
        return f"SecretStore - {self.name} ({self.id})"

    def __repr__(self) -> str:
        return f"SecretStore(name={self.name!r}, unique_id={self.id!r})"

    def to_dict(self) -> dict:
        """Return the dictionary representation of secret store."""

        repr = {
            "name": self.name,
            "id": self.id,
            "description": self.description,
            "tags": [tag.__dict__ for tag in self.tags],
            "custom_properties": self.custom_properties,
            "operation": self.operation,
            "permissions": [permission.to_dict() for permission in self.permissions.values()],
            "secret_store_vaults": [vault.to_dict() for vault in self.vaults.values()],
            "identity_to_permissions": [itp.to_dict() for itp in self.identity_to_permissions.values()]
        }

        # filter out None/empty values before return
        return {k: v for k, v in repr.items() if v not in [None, [], {}, ""]}

    def add_permission(self, name: str, unique_id: str = None, resource: str = None, allow_identity_assume: bool = None, permission_type: List[OAAPermission] = None) -> SecretStorePermission:
        """Add a new Permission

        Args:
            name (str): Display name for permission
            unique_id (str, optional): Unique identifier for permission. Defaults to name if not provided.
            resource (str, optional): Resource this permission applies to
            allow_identity_assume (bool, optional): Whether this permission allows identity assumption
            permission_type (list[OAAPermission], optional): List of OAAPermission enums that represent the canonical permissions

        Returns:
            SecretStorePermission: Entity for new permission

        Raises:
            OAATemplateException: Permission with ID already exists
        """

        identifier = unique_id if unique_id else name

        if identifier in self.permissions:
            raise OAATemplateException(f"Permission with identifier already exists: {identifier}")

        self.permissions[identifier] = SecretStorePermission(
            name=name,
            unique_id=unique_id,
            resource=resource,
            allow_identity_assume=allow_identity_assume,
            permission_type=permission_type
        )

        if self._all_property_definitions:
            self.permissions[identifier]._property_definitions = self._all_property_definitions.permission_properties

        return self.permissions[identifier]

    def add_vault(self, name: str, vault_type: str, unique_id: str = None, description: str = None) -> SecretStoreVault:
        """Add a new Vault

        Args:
            name (str): Display name for vault
            vault_type (str): Type of vault (user-defined)
            unique_id (str, optional): Unique identifier for vault. Defaults to name if not provided.
            description (str, optional): Description of the vault

        Returns:
            SecretStoreVault: Entity for new vault

        Raises:
            OAATemplateException: Vault with ID already exists
        """

        identifier = unique_id if unique_id else name

        if identifier in self.vaults:
            raise OAATemplateException(f"Vault with identifier already exists: {identifier}")

        self.vaults[identifier] = SecretStoreVault(
            name=name,
            vault_type=vault_type,
            unique_id=unique_id,
            description=description
        )

        if self._all_property_definitions:
            self.vaults[identifier]._property_definitions = self._all_property_definitions.vault_properties
            self.vaults[identifier]._all_property_definitions = self._all_property_definitions

        return self.vaults[identifier]

    def add_identity_to_permission(self, identity: str, identity_type: str, permission_assignments: List[PermissionAssignment] = None) -> IdentityToPermission:
        """Add identity to permission mapping

        Args:
            identity (str): The identity ID
            identity_type (str): The type of identity (e.g., "local_user")
            permission_assignments (list[PermissionAssignment], optional): Permission assignments for this identity

        Returns:
            IdentityToPermission: The identity to permission mapping

        Raises:
            OAATemplateException: Identity to permission mapping for identity and identity_type already exists
        """

        identifier = f"{identity_type}:{identity}"

        if identifier in self.identity_to_permissions:
            raise OAATemplateException(f"Identity to permission mapping already exists for identity {identity} identity_type {identity_type}")

        self.identity_to_permissions[identifier] = IdentityToPermission(
            identity=identity,
            identity_type=identity_type,
            permission_assignments=list(permission_assignments or [])
        )

        return self.identity_to_permissions[identifier]

    def add_tag(self, key: str, value: str = "") -> None:
        """Add a new tag to secret store.

        Args:
            key (str): Tag key/name
            value (str, optional): Tag value. Defaults to "".
        """

        tag = Tag(key=key, value=value)

        if tag not in self.tags:
            self.tags.append(tag)

        return

    def set_property(self, property_name: str, property_value: any, ignore_none: bool = False) -> None:
        """Set secret store custom property value

        Property name must be defined before calling `set_property`

        Args:
            property_name (str): Name of property
            property_value (any): Value for property, type should match OAAPropertyType for property definition
            ignore_none (bool, optional): Do not set property if value is None. Defaults to False.

        Raises:
            OAATemplateException: If property with `property_name` is not defined.
        """

        if self._property_definitions is not None:
            if not isinstance(self._property_definitions, CaseInsensitiveDict):
                raise OAATemplateException("secret_store property_definitions not of expected type")

            if property_name not in self._property_definitions:
                raise OAATemplateException(f"unknown secret_store property name {property_name}")
        else:
            log.warning("SecretStore does not have property names set, cannot validate property name")

        if ignore_none and property_value is None:
            return

        self.custom_properties[property_name] = property_value

        return


class SecretStorePermission():
    """Secret Store Permission Entity

    Represents a permission in a secret store.

    Args:
        name (str): Display name for permission
        unique_id (str, optional): Unique identifier for permission
        resource (str, optional): Resource this permission applies to
        allow_identity_assume (bool, optional): Whether this permission allows identity assumption
        permission_type (list[OAAPermission], optional): List of OAAPermission enums that represent the canonical permissions

    Attributes:
        permission_type (list[OAAPermission]): List of OAAPermission enums that represent the canonical permissions
    """

    def __init__(self, name: str, unique_id: str = None, resource: str = None, allow_identity_assume: bool = None, permission_type: List[OAAPermission] = None):
        if not name:
            raise ValueError("name cannot be empty")

        self.name = name
        self.id = unique_id if unique_id else name
        self.resource = resource
        self.allow_identity_assume = allow_identity_assume
        self.permission_type = []

        self.tags: List[Tag] = []
        self.custom_properties: dict = {}
        self.operation: Optional[str] = None

        self._property_definitions = None

        self.__validate_permission_type(permission_type)

    def __str__(self) -> str:
        return f"SecretStorePermission - {self.name} ({self.id})"

    def __repr__(self) -> str:
        return f"SecretStorePermission(name={self.name!r}, unique_id={self.id!r})"

    def to_dict(self) -> dict:
        """Return the dictionary representation of permission."""

        repr = {
            "name": self.name,
            "id": self.id,
            "resource": self.resource,
            "allow_identity_assume": self.allow_identity_assume,
            "permission_type": self.permission_type,
            "tags": [tag.__dict__ for tag in self.tags],
            "custom_properties": self.custom_properties,
            "operation": self.operation
        }

        # filter out None/empty values before return
        return {k: v for k, v in repr.items() if v not in [None, [], {}, ""]}

    def add_permission_type(self, permission_type: OAAPermission) -> None:
        """Add a permission type to the permission_type list.

        Extends the list of canonical OAAPermission types this permission grants.

        Args:
            permission_type (OAAPermission): The OAAPermission enum value to add

        Raises:
            OAATemplateException: If permission_type is not an OAAPermission enum
        """

        if not isinstance(permission_type, OAAPermission):
            raise OAATemplateException("permission_type must be OAAPermission enum")

        if permission_type not in self.permission_type:
            self.permission_type.append(permission_type)

        return

    def __validate_permission_type(self, permission_type: List[OAAPermission]) -> None:
        """Validate permission_type values are OAAPermission type.

        Args:
            permission_type (list): List of entities to validate are of type OAAPermission

        Raises:
            OAATemplateException
        """

        if permission_type is None:
            return

        validated_permission_type = []
        if isinstance(permission_type, list):
            for p in permission_type:
                if isinstance(p, OAAPermission):
                    validated_permission_type.append(p)
                    continue
                else:
                    raise OAATemplateException("permission_type must be OAAPermission enum")
        elif isinstance(permission_type, OAAPermission):
            validated_permission_type.append(permission_type)
        else:
            raise OAATemplateException("permission_type must be OAAPermission enum")

        self.permission_type = validated_permission_type

    def add_tag(self, key: str, value: str = "") -> None:
        """Add a new tag to permission.

        Args:
            key (str): Tag key/name
            value (str, optional): Tag value. Defaults to "".
        """

        tag = Tag(key=key, value=value)

        if tag not in self.tags:
            self.tags.append(tag)

        return

    def set_property(self, property_name: str, property_value: any, ignore_none: bool = False) -> None:
        """Set permission custom property value

        Property name must be defined before calling `set_property`

        Args:
            property_name (str): Name of property
            property_value (any): Value for property, type should match OAAPropertyType for property definition
            ignore_none (bool, optional): Do not set property if value is None. Defaults to False.

        Raises:
            OAATemplateException: If property with `property_name` is not defined.
        """

        if self._property_definitions is not None:
            if not isinstance(self._property_definitions, CaseInsensitiveDict):
                raise OAATemplateException("permission property_definitions not of expected type")

            if property_name not in self._property_definitions:
                raise OAATemplateException(f"unknown permission property name {property_name}")
        else:
            log.warning("Permission does not have property names set, cannot validate property name")

        if ignore_none and property_value is None:
            return

        self.custom_properties[property_name] = property_value

        return


class SecretStoreVault():
    """Secret Store Vault Entity

    Represents a vault in a secret store.

    Args:
        name (str): Display name for vault
        vault_type (str): Type of vault (user-defined)
        unique_id (str, optional): Unique identifier for vault
        description (str, optional): Description of the vault
    """

    def __init__(self, name: str, vault_type: str, unique_id: str = None, description: str = None):
        if not name:
            raise ValueError("name cannot be empty")
        if not vault_type:
            raise ValueError("vault_type cannot be empty")

        self.name = name
        self.vault_type = vault_type
        self.id = unique_id if unique_id else name
        self.description = description

        self.tags: List[Tag] = []
        self.custom_properties: dict = {}
        self.operation: Optional[str] = None

        self.entries = CaseInsensitiveDict()

        self._property_definitions = None
        self._all_property_definitions = None

    def __str__(self) -> str:
        return f"SecretStoreVault - {self.name} ({self.id}) - {self.vault_type}"

    def __repr__(self) -> str:
        return f"SecretStoreVault(name={self.name!r}, vault_type={self.vault_type!r}, unique_id={self.id!r})"

    def to_dict(self) -> dict:
        """Return the dictionary representation of vault."""

        repr = {
            "name": self.name,
            "id": self.id,
            "vault_type": self.vault_type,
            "description": self.description,
            "tags": [tag.__dict__ for tag in self.tags],
            "custom_properties": self.custom_properties,
            "operation": self.operation,
            "entries": [entry.to_dict() for entry in self.entries.values()]
        }

        # filter out None/empty values before return
        return {k: v for k, v in repr.items() if v not in [None, [], {}, ""]}

    def add_entry(self, name: str, unique_id: str = None, description: str = None) -> SecretStoreVaultEntry:
        """Add a new Entry to vault

        Args:
            name (str): Display name for entry
            unique_id (str, optional): Unique identifier for entry. Defaults to name if not provided.
            description (str, optional): Description of the entry

        Returns:
            SecretStoreVaultEntry: Entity for new entry

        Raises:
            OAATemplateException: Entry with ID already exists
        """

        identifier = unique_id if unique_id else name

        if identifier in self.entries:
            raise OAATemplateException(f"Entry with identifier already exists: {identifier}")

        self.entries[identifier] = SecretStoreVaultEntry(
            name=name,
            unique_id=unique_id,
            description=description
        )

        if self._all_property_definitions:
            self.entries[identifier]._property_definitions = self._all_property_definitions.entry_properties

        return self.entries[identifier]

    def add_tag(self, key: str, value: str = "") -> None:
        """Add a new tag to vault.

        Args:
            key (str): Tag key/name
            value (str, optional): Tag value. Defaults to "".
        """

        tag = Tag(key=key, value=value)

        if tag not in self.tags:
            self.tags.append(tag)

        return

    def set_property(self, property_name: str, property_value: any, ignore_none: bool = False) -> None:
        """Set vault custom property value

        Property name must be defined before calling `set_property`

        Args:
            property_name (str): Name of property
            property_value (any): Value for property, type should match OAAPropertyType for property definition
            ignore_none (bool, optional): Do not set property if value is None. Defaults to False.

        Raises:
            OAATemplateException: If property with `property_name` is not defined.
        """

        if self._property_definitions is not None:
            if not isinstance(self._property_definitions, CaseInsensitiveDict):
                raise OAATemplateException("vault property_definitions not of expected type")

            if property_name not in self._property_definitions:
                raise OAATemplateException(f"unknown vault property name {property_name}")
        else:
            log.warning("Vault does not have property names set, cannot validate property name")

        if ignore_none and property_value is None:
            return

        self.custom_properties[property_name] = property_value

        return


class SecretStoreVaultEntry():
    """Secret Store Vault Entry Entity

    Represents an entry (credential) in a vault.

    Args:
        name (str): Display name for entry
        unique_id (str, optional): Unique identifier for entry
        description (str, optional): Description of the entry
    """

    def __init__(self, name: str, unique_id: str = None, description: str = None):
        if not name:
            raise ValueError("name cannot be empty")

        self.name = name
        self.id = unique_id if unique_id else name
        self.description = description

        self.tags: List[Tag] = []
        self.custom_properties: dict = {}
        self.operation: Optional[str] = None

        self.identities: List[VaultEntryIdentity] = []

        self._property_definitions = None

    def __str__(self) -> str:
        return f"SecretStoreVaultEntry - {self.name} ({self.id})"

    def __repr__(self) -> str:
        return f"SecretStoreVaultEntry(name={self.name!r}, unique_id={self.id!r})"

    def to_dict(self) -> dict:
        """Return the dictionary representation of entry."""

        repr = {
            "name": self.name,
            "id": self.id,
            "description": self.description,
            "tags": [tag.__dict__ for tag in self.tags],
            "custom_properties": self.custom_properties,
            "operation": self.operation,
            "identities": [identity.to_dict() for identity in self.identities]
        }

        # filter out None/empty values before return
        return {k: v for k, v in repr.items() if v not in [None, [], {}, ""]}

    def add_identity(self, identity_type: str, external_id: str) -> VaultEntryIdentity:
        """Add an identity to this vault entry

        Args:
            identity_type (str): The type of identity (e.g., "OktaUser", "AzureADUser")
            external_id (str): The external ID of the identity

        Returns:
            VaultEntryIdentity: The identity entity
        """

        identity = VaultEntryIdentity(identity_type=identity_type, external_id=external_id)

        self.identities.append(identity)

        return identity

    def add_tag(self, key: str, value: str = "") -> None:
        """Add a new tag to entry.

        Args:
            key (str): Tag key/name
            value (str, optional): Tag value. Defaults to "".
        """

        tag = Tag(key=key, value=value)

        if tag not in self.tags:
            self.tags.append(tag)

        return

    def set_property(self, property_name: str, property_value: any, ignore_none: bool = False) -> None:
        """Set entry custom property value

        Property name must be defined before calling `set_property`

        Args:
            property_name (str): Name of property
            property_value (any): Value for property, type should match OAAPropertyType for property definition
            ignore_none (bool, optional): Do not set property if value is None. Defaults to False.

        Raises:
            OAATemplateException: If property with `property_name` is not defined.
        """

        if self._property_definitions is not None:
            if not isinstance(self._property_definitions, CaseInsensitiveDict):
                raise OAATemplateException("entry property_definitions not of expected type")

            if property_name not in self._property_definitions:
                raise OAATemplateException(f"unknown entry property name {property_name}")
        else:
            log.warning("Entry does not have property names set, cannot validate property name")

        if ignore_none and property_value is None:
            return

        self.custom_properties[property_name] = property_value

        return


class VaultEntryIdentity():
    """Vault Entry Identity

    Represents identity information for a vault entry.

    Args:
        identity_type (str): The type of identity (e.g., "OktaUser", "AzureADUser")
        external_id (str): The external ID of the identity
    """

    def __init__(self, identity_type: str, external_id: str):
        if not identity_type:
            raise ValueError("identity_type cannot be empty")
        if not external_id:
            raise ValueError("external_id cannot be empty")

        self.type = identity_type
        self.external_id = external_id

    def __str__(self) -> str:
        return f"VaultEntryIdentity - {self.type}:{self.external_id}"

    def __repr__(self) -> str:
        return f"VaultEntryIdentity(identity_type={self.type!r}, external_id={self.external_id!r})"

    def to_dict(self) -> dict:
        """Return the dictionary representation of identity."""

        return {
            "type": self.type,
            "external_id": self.external_id
        }


class IdentityToPermission():
    """Identity to Permission Mapping

    Maps an identity to permissions on vaults.

    Args:
        identity (str): The identity ID
        identity_type (str): The type of identity (e.g., "local_user")
        permission_assignments (list[PermissionAssignment], optional): Permission assignments for this identity
    """

    def __init__(self, identity: str, identity_type: str, permission_assignments: List[PermissionAssignment] = None):
        if not identity:
            raise ValueError("identity cannot be empty")
        if not identity_type:
            raise ValueError("identity_type cannot be empty")

        self.identity = identity
        self.identity_type = identity_type
        self.permission_assignments = list(permission_assignments or [])

    def __str__(self) -> str:
        return f"IdentityToPermission - {self.identity_type}:{self.identity}"

    def __repr__(self) -> str:
        return f"IdentityToPermission(identity={self.identity!r}, identity_type={self.identity_type!r})"

    def to_dict(self) -> dict:
        """Return the dictionary representation of identity to permission."""

        return {
            "identity": self.identity,
            "identity_type": self.identity_type,
            "permission_assignments": [pa.to_dict() for pa in self.permission_assignments]
        }

    def add_permission_assignment(self, vault: List[str], permissions: List[str]) -> PermissionAssignment:
        """Add a permission assignment

        Args:
            vault (list[str]): List of vault IDs or names
            permissions (list[str]): List of permission names

        Returns:
            PermissionAssignment: The permission assignment
        """

        assignment = PermissionAssignment(vault=vault, permissions=permissions)

        self.permission_assignments.append(assignment)

        return assignment


class PermissionAssignment():
    """Permission Assignment

    Assigns permissions to vaults.

    Args:
        vault (list[str]): List of vault IDs or names
        permissions (list[str]): List of permission names
    """

    def __init__(self, vault: List[str], permissions: List[str]):
        if not vault:
            raise ValueError("vault cannot be empty")
        if not permissions:
            raise ValueError("permissions cannot be empty")

        if not isinstance(vault, list):
            raise OAATemplateException("vault must be list")

        if not isinstance(permissions, list):
            raise OAATemplateException("permissions must be list")
        self.vault = vault
        self.permissions = permissions

    def __str__(self) -> str:
        return f"PermissionAssignment - vaults:{len(self.vault)}, permissions:{len(self.permissions)}"

    def __repr__(self) -> str:
        return f"PermissionAssignment(vault={self.vault!r}, permissions={self.permissions!r})"

    def to_dict(self) -> dict:
        """Return the dictionary representation of permission assignment."""

        return {
            "vault": self.vault,
            "permissions": self.permissions
        }


class SecretStorePropertyDefinitions():
    """Property Definitions for Secret Store entities"""

    def __init__(self):
        self.secret_store_properties = CaseInsensitiveDict()
        self.permission_properties = CaseInsensitiveDict()
        self.vault_properties = CaseInsensitiveDict()
        self.entry_properties = CaseInsensitiveDict()

    def __str__(self) -> str:
        return "SecretStorePropertyDefinitions"

    def __repr__(self) -> str:
        return "SecretStorePropertyDefinitions()"

    def to_dict(self) -> dict:
        """Convert property definitions to dictionary"""

        definitions = {
            "secret_store_properties": {k: v for k, v in self.secret_store_properties.items()},
            "permission_properties": {k: v for k, v in self.permission_properties.items()},
            "vault_properties": {k: v for k, v in self.vault_properties.items()},
            "entry_properties": {k: v for k, v in self.entry_properties.items()}
        }

        return definitions

    def define_secret_store_property(self, name: str, property_type: OAAPropertyType) -> None:
        """Define a custom property for secret store

        Args:
            name (str): Property name
            property_type (OAAPropertyType): Property type
        """
        self.validate_name(name)
        self._validate_types(name, property_type)
        self.secret_store_properties[name] = property_type

    def define_permission_property(self, name: str, property_type: OAAPropertyType) -> None:
        """Define a custom property for permissions

        Args:
            name (str): Property name
            property_type (OAAPropertyType): Property type
        """
        self.validate_name(name)
        self._validate_types(name, property_type)
        self.permission_properties[name] = property_type

    def define_vault_property(self, name: str, property_type: OAAPropertyType) -> None:
        """Define a custom property for vaults

        Args:
            name (str): Property name
            property_type (OAAPropertyType): Property type
        """
        self.validate_name(name)
        self._validate_types(name, property_type)
        self.vault_properties[name] = property_type

    def define_entry_property(self, name: str, property_type: OAAPropertyType) -> None:
        """Define a custom property for entries

        Args:
            name (str): Property name
            property_type (OAAPropertyType): Property type
        """
        self.validate_name(name)
        self._validate_types(name, property_type)
        self.entry_properties[name] = property_type

    def _validate_types(self, name: str, property_type: OAAPropertyType) -> None:
        """Helper function to validate that custom property parameters are of the correct types.

        Args:
            name (str): name of property
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
