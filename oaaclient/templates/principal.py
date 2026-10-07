"""
Classes for constructing an OAA JSON payload for Custom Principal Submission

Copyright 2026 Veza Technologies Inc.

Use of this source code is governed by the MIT
license that can be found in the LICENSE file or at
https://opensource.org/licenses/MIT.
"""

from __future__ import annotations
from enum import Enum

from .common import CaseInsensitiveDict, OAAPropertyType, Tag
from .exceptions import OAATemplateException


class PrincipalEntityType(Enum):
    """ Principal entity types. """

    TENANT = "TENANT"
    USER = "USER"
    GROUP = "GROUP"


class CustomPrincipal():
    """
    CustomPrincipal class for modeling Principal services using OAA Custom Principal Template.

    Principals represent a source of identities (users and groups) to other OAA template types on the same provider.

    Class uses dictionaries to track most components, dictionaries are all keyed by case insensitive string of the entity name

    Args:
        name (str): Name of Principal Provider
        principal_type (str): Type descriptor for Principal Provider
        tenant_id (str): Unique identifier for the tenant

    Attributes:
        name (str): Name of custom Principal Provider
        principal_type (str): Type for Principal Provider
        property_definitions (PrincipalPropertyDefinitions): Custom Property definitions for Principal instance
        tenant (CustomPrincipalTenant): Tenant model
        users (dict[CustomPrincipalUser]): Dictionary of CustomPrincipalUser class instances
        groups (dict[CustomPrincipalGroup]): Dictionary of CustomPrincipalGroup class instances
    """

    TEMPLATE = "principal"

    def __init__(self, name: str, principal_type: str, tenant_id: str) -> None:
        self.name = name
        self.principal_type = principal_type

        self.property_definitions = PrincipalPropertyDefinitions()
        self.tenant = CustomPrincipalTenant(name=name, unique_id=tenant_id, property_definitions=self.property_definitions)
        self.users = CaseInsensitiveDict()
        self.groups = CaseInsensitiveDict()

    def __str__(self) -> str:
        return f"Custom Principal {self.name} - {self.principal_type}"

    def __repr__(self) -> str:
        return f"CustomPrincipal(name={self.name!r}, principal_type={self.principal_type!r}, tenant_id={self.tenant.id!r})"

    def get_payload(self) -> dict:
        """ Return formatted payload as dictionary for JSON conversion and upload """
        payload = {}
        payload['custom_property_definition'] = self.property_definitions.to_dict()
        payload['name'] = self.name
        payload['principal_type'] = self.principal_type

        if self.tenant:
            payload['tenant'] = self.tenant.to_dict()

        payload['users'] = [user.to_dict() for user in self.users.values()]
        payload['groups'] = [group.to_dict() for group in self.groups.values()]

        return payload

    def add_user(self, name: str, unique_id: str = None, email: str = None, user_unique_id: str = None) -> CustomPrincipalUser:
        """ Add user to Principal submission

        Arguments:
            name (str): name for user
            unique_id (str, optional): unique ID for user
            email (str, optional): email address for user
            user_unique_id (str, optional): unique identifier for user if different than email

        Returns:
            CustomPrincipalUser
        """

        identifier = unique_id if unique_id else name

        if identifier in self.users:
            raise OAATemplateException(f"Principal user identified by {identifier} already defined")

        user = CustomPrincipalUser(name=name, unique_id=identifier, email=email,
                                   property_definitions=self.property_definitions)
        user.user_unique_id = user_unique_id
        self.users[identifier] = user

        return self.users[identifier]

    def add_group(self, name: str, unique_id: str = None, group_unique_id: str = None) -> CustomPrincipalGroup:
        """ Add group to Principal submission

        Arguments:
            name (str): name for group
            unique_id (str, optional): unique ID for group
            group_unique_id (str, optional): unique identifier for group. Used in identity correlation. 

        Returns:
            CustomPrincipalGroup
        """

        identifier = unique_id if unique_id else name

        if identifier in self.groups:
            raise OAATemplateException(f"Principal group {identifier} already defined")

        group = CustomPrincipalGroup(name=name, unique_id=identifier,
                                     property_definitions=self.property_definitions)
        group.group_unique_id = group_unique_id
        self.groups[identifier] = group

        return self.groups[identifier]


class CustomPrincipalTenant():
    """ Tenant model for Custom Principal submission.

    Args:
        name (str): tenant name
        unique_id (str): unique ID for tenant
        tenant_unique_id (str, optional): unique identifier for tenant, usually a URL
        property_definitions (PrincipalPropertyDefinitions, optional): Property definitions for custom properties

    Attributes:
        name (str): tenant name
        id (str): unique ID for tenant
        tenant_unique_id (str): unique identifier for tenant
    """

    def __init__(self, name: str, unique_id: str, tenant_unique_id: str = None,
                 property_definitions: PrincipalPropertyDefinitions = None) -> None:
        self.name = name
        self.id = unique_id
        if not tenant_unique_id:
            self.tenant_unique_id = unique_id
        else:
            self.tenant_unique_id = tenant_unique_id
        self._tags = []
        self._properties = {}
        self._property_definitions = property_definitions

    def __str__(self) -> str:
        return f"Custom Principal Tenant {self.name}"

    def __repr__(self) -> str:
        return f"CustomPrincipalTenant(name={self.name!r}, unique_id={self.id!r}, tenant_unique_id={self.tenant_unique_id!r})"

    def to_dict(self) -> dict:
        """ Output function for payload. """
        tenant = {}
        tenant['name'] = self.name
        if self.id:
            tenant['id'] = self.id
        if self.tenant_unique_id:
            tenant['tenant_unique_id'] = self.tenant_unique_id
        tenant['tags'] = [tag.__dict__ for tag in self._tags]
        tenant['custom_properties'] = self._properties

        return {k: v for k, v in tenant.items() if v not in [None, [], {}]}

    def set_property(self, property_name: str, property_value: any, ignore_none: bool = False) -> None:
        """ Set custom property value for tenant.

        Property name must be defined for tenant before calling `set_property()`.

        Args:
            property_name (str): Name of property
            property_value (Any): Value for property, type should match OAAPropertyType for property definition
            ignore_none (bool, optional): Do not set property if value is None. Defaults to False.

        Raises:
            OAATemplateException: If property with `property_name` is not defined.
        """

        if not self._property_definitions:
            raise OAATemplateException("No custom property definitions found for tenant")

        if ignore_none and property_value is None:
            return

        self._property_definitions.validate_property_name(property_name, entity_type=PrincipalEntityType.TENANT)
        self._properties[property_name] = property_value

    def add_tag(self, key: str, value: str = "") -> None:
        """ Add a new tag to Principal Tenant.

        Args:
            key (str): Key for tag, aka name. Must be present and must be letters, numbers or _ (underscore) only.
            value (str, optional): Value for Tag, will appear in Veza as `key:value`. Must be letters, numbers, whitespace and the special characters @,._- only. Defaults to "".
        """

        tag = Tag(key=key, value=value)
        if tag not in self._tags:
            self._tags.append(tag)


class CustomPrincipalUser():
    """ User model for CustomPrincipal

    Args:
        name (str): name for user
        unique_id (str): unique ID for user
        email (str, optional): email address for user
        property_definitions (PrincipalPropertyDefinitions, optional): Property definitions for custom properties

    Attributes:
        name (str): name for user
        unique_id (str): unique ID for user
        email (str): email address for user
        user_unique_id (str): Optional unique identifier for user. Used for identity_unique_id if set.
        display_name (str): display name for user
        is_active (bool): whether user is active
        created_at (str): date user was created (RFC3339 format)
        deactivated_at (str): date user was deactivated (RFC3339 format)
        last_login_at (str): date user last logged in (RFC3339 format)
    """

    def __init__(self, name: str, unique_id: str, email: str = None, property_definitions: PrincipalPropertyDefinitions = None) -> None:
        if not name:
            raise OAATemplateException("name cannot be empty")
        if not unique_id:
            raise OAATemplateException("unique_id cannot be empty")

        self.name = name
        self.unique_id = unique_id
        self.email = email
        self.user_unique_id = None
        self.display_name = None
        self.is_active = None
        self.created_at = None
        self.deactivated_at = None
        self.last_login_at = None

        self._identities = []
        self._groups = []
        self._tags = []
        self._properties = {}
        self._property_definitions = property_definitions

    def __str__(self) -> str:
        return f"Principal User - {self.name} ({self.unique_id})"

    def __repr__(self) -> str:
        return f"CustomPrincipalUser(name={self.name!r}, unique_id={self.unique_id!r}, email={self.email!r})"

    def to_dict(self) -> dict:
        """ Function to prepare user entity for payload """
        user = {}
        user['name'] = self.name
        if self.unique_id:
            user['id'] = self.unique_id
        if self.email:
            user['email'] = self.email
        if self.user_unique_id:
            user['user_unique_id'] = self.user_unique_id
        if self.display_name:
            user['display_name'] = self.display_name
        if self.is_active is not None:
            user['is_active'] = self.is_active
        if self.created_at:
            user['created_date'] = self.created_at
        if self.deactivated_at:
            user['deactivated_date'] = self.deactivated_at
        if self.last_login_at:
            user['last_login'] = self.last_login_at

        user['identities'] = self._identities
        user['groups'] = self._groups
        user['tags'] = [tag.__dict__ for tag in self._tags]
        user['custom_properties'] = self._properties

        return {k: v for k, v in user.items() if v not in [None, [], {}]}

    def add_identity(self, identity: str) -> None:
        """ Add an identity to user.

        Args:
            identity (str): Identity string for user
        """
        if identity not in self._identities:
            self._identities.append(identity)

    def add_group(self, group_id: str) -> None:
        """ Add user to group by group ID.

        Args:
            group_id (str): ID of group to add user to
        """
        # Check if group_id already exists in the list
        existing_group_ids = [g["id"] for g in self._groups]
        if group_id not in existing_group_ids:
            self._groups.append({"id": group_id})

    def set_property(self, property_name: str, property_value: any, ignore_none: bool = False) -> None:
        """ Set custom property value for user.

        Property name must be defined for users before calling `set_property()`.

        Args:
            property_name (str): Name of property
            property_value (Any): Value for property, type should match OAAPropertyType for property definition
            ignore_none (bool, optional): Do not set property if value is None. Defaults to False.

        Raises:
            OAATemplateException: If property with `property_name` is not defined.
        """

        if not self._property_definitions:
            raise OAATemplateException("No custom property definitions found for user")

        if ignore_none and property_value is None:
            return

        self._property_definitions.validate_property_name(property_name, entity_type=PrincipalEntityType.USER)
        self._properties[property_name] = property_value

    def add_tag(self, key: str, value: str = "") -> None:
        """ Add a new tag to Principal User.

        Args:
            key (str): Key for tag, aka name. Must be present and must be letters, numbers or _ (underscore) only.
            value (str, optional): Value for Tag, will appear in Veza as `key:value`. Must be letters, numbers, whitespace and the special characters @,._- only. Defaults to "".
        """

        tag = Tag(key=key, value=value)
        if tag not in self._tags:
            self._tags.append(tag)


class CustomPrincipalGroup():
    """ Group model for CustomPrincipal.

    Args:
        name (str): name of group
        unique_id (str): unique ID for group
        property_definitions (PrincipalPropertyDefinitions, optional): Property definitions for custom properties

    Attributes:
        name (str): name of group
        id (str): unique ID for group
        group_unique_id (str): Optional unique identifier for group. Used for identity_unique_id
        group_type (str): type of group
        parent_group_id (str): ID of parent group for hierarchical groups
    """

    def __init__(self, name: str, unique_id: str, property_definitions: PrincipalPropertyDefinitions = None) -> None:
        if not name:
            raise OAATemplateException("name cannot be empty")
        if not unique_id:
            raise OAATemplateException("unique_id cannot be empty")
            
        self.name = name
        self.id = unique_id
        self.group_unique_id = None
        self.group_type = None
        self.parent_group_id = None

        self._identities = []
        self._tags = []
        self._properties = {}
        self._property_definitions = property_definitions

    def __str__(self) -> str:
        return f"Principal Group {self.name} ({self.id})"

    def __repr__(self) -> str:
        return f"CustomPrincipalGroup(name={self.name!r}, unique_id={self.id!r})"

    def to_dict(self) -> dict:
        """ Function to prepare group entity for payload. """

        group = {}
        group['name'] = self.name
        if self.id:
            group['id'] = self.id
        if self.group_unique_id:
            group['group_unique_id'] = self.group_unique_id
        if self.group_type:
            group['group_type'] = self.group_type
        if self.parent_group_id:
            group['parent_group'] = {"id": self.parent_group_id}

        group['identities'] = self._identities
        group['tags'] = [tag.__dict__ for tag in self._tags]
        group['custom_properties'] = self._properties

        return {k: v for k, v in group.items() if v not in [None, [], {}]}

    def add_identity(self, identity: str) -> None:
        """ Add an identity to group.

        Args:
            identity (str): Identity string for group
        """
        if identity not in self._identities:
            self._identities.append(identity)

    def set_parent_group(self, parent_group_id: str) -> None:
        """ Set parent group for hierarchical group structure.

        Args:
            parent_group_id (str): ID of parent group

        Raises:
            OAATemplateException: If `parent_group_id` matches the group's own id
        """

        if parent_group_id == self.id:
            raise OAATemplateException("Group cannot be its own parent")

        self.parent_group_id = parent_group_id

    def set_property(self, property_name: str, property_value: any, ignore_none: bool = False) -> None:
        """ Set custom property value for group.

        Property name must be defined for groups before calling `set_property()`.

        Args:
            property_name (str): Name of property
            property_value (Any): Value for property, type should match OAAPropertyType for property definition
            ignore_none (bool, optional): Do not set property if value is None. Defaults to False.

        Raises:
            OAATemplateException: If property with `property_name` is not defined.
        """

        if not self._property_definitions:
            raise OAATemplateException("No custom property definitions found for group")

        if ignore_none and property_value is None:
            return

        self._property_definitions.validate_property_name(property_name, entity_type=PrincipalEntityType.GROUP)
        self._properties[property_name] = property_value

    def add_tag(self, key: str, value: str = "") -> None:
        """ Add a new tag to Principal Group.

        Args:
            key (str): Key for tag, aka name. Must be present and must be letters, numbers or _ (underscore) only.
            value (str, optional): Value for Tag, will appear in Veza as `key:value`. Must be letters, numbers, whitespace and the special characters @,._- only. Defaults to "".
        """

        tag = Tag(key=key, value=value)
        if tag not in self._tags:
            self._tags.append(tag)


class PrincipalPropertyDefinitions():
    """
    Model for defining custom properties for CustomPrincipal and its entities (tenant, users, groups).

    Property definitions define the names for additional entity properties and the expected type.

    Attributes:
        tenant_properties (dict): property definitions for Principal Tenant
        user_properties (dict): property definitions for Principal users
        group_properties (dict): property definitions for Principal groups
    """

    def __init__(self) -> None:
        super().__init__()
        self.tenant_properties = {}
        self.user_properties = {}
        self.group_properties = {}

    def __str__(self) -> str:
        return "Principal Property Definitions"

    def __repr__(self) -> str:
        return "PrincipalPropertyDefinitions()"

    def to_dict(self) -> dict:
        """ Returns custom Principal property definitions. """

        return {
            "tenant_properties": self.tenant_properties,
            "user_properties": self.user_properties,
            "group_properties": self.group_properties
        }

    def define_tenant_property(self, name: str, property_type: OAAPropertyType) -> None:
        """ Define a tenant custom property.

        Args:
            name (str): name of property
            property_type (OAAPropertyType): type for property
        """
        self._validate_types(name, property_type)
        self.tenant_properties[name] = property_type

    def define_user_property(self, name: str, property_type: OAAPropertyType) -> None:
        """ Define a user custom property.

        Args:
            name (str): name of property
            property_type (OAAPropertyType): type for property
        """
        self._validate_types(name, property_type)
        self.user_properties[name] = property_type

    def define_group_property(self, name: str, property_type: OAAPropertyType) -> None:
        """ Define a group custom property.

        Args:
            name (str): name of property
            property_type (OAAPropertyType): type for property
        """
        self._validate_types(name, property_type)
        self.group_properties[name] = property_type

    def validate_property_name(self, property_name: str, entity_type: PrincipalEntityType) -> None:
        """ Validate that a property name has been defined for a given Principal entity.

        Raises exception if property name has not been previously defined for entity

        Args:
            property_name (str): name of property to validate
            entity_type (PrincipalEntityType): type of entity custom property is for (TENANT, USER, or GROUP)

        Raises:
            OAATemplateException: If property name is not defined
        """
        valid_property_names = []
        if entity_type == PrincipalEntityType.TENANT:
            valid_property_names = self.tenant_properties.keys()
        elif entity_type == PrincipalEntityType.USER:
            valid_property_names = self.user_properties.keys()
        elif entity_type == PrincipalEntityType.GROUP:
            valid_property_names = self.group_properties.keys()
        else:
            raise OAATemplateException(f"Unknown entity type '{entity_type}', cannot validate property names")

        # validate against names as all lowercase
        valid_property_names = [i.lower() for i in valid_property_names]

        if property_name.lower() in valid_property_names:
            return True
        else:
            raise OAATemplateException(f"unknown property name {property_name}")

    def _validate_types(self, name: str, property_type: OAAPropertyType) -> None:
        """ Validate that custom property parameters are of the correct types (helper function).

        Args:
            name (str): name of property
            property_type (OAAPropertyType): OAA type for property
        """
        if not isinstance(name, str):
            raise OAATemplateException("property name must be type string")
        if not isinstance(property_type, OAAPropertyType):
            raise OAATemplateException("property_type must be type OAAPropertyType enum")
