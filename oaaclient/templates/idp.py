"""
Classes for constructing an OAA JSON payload for Custom IDP

Copyright 2026 Veza Technologies Inc.

Use of this source code is governed by the MIT
license that can be found in the LICENSE file or at
https://opensource.org/licenses/MIT.
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from .common import CaseInsensitiveDict, OAAPropertyType, IdPProviderType, PROPERTY_NAME_REGEX, Tag
from .exceptions import OAATemplateException
###############################################################################
# Custom IdP Provider
###############################################################################
class IdPEntityType(Enum):
    """ IdP entity types.  """

    USER = "USER"
    GROUP = "GROUP"
    DOMAIN = "DOMAIN"
    APP = "APP"
    APPASSIGNMENT = "APPASSIGNMENT"




class CustomIdPProvider():
    """
    CustomIdPProvider class for modeling Identity Providers (IdP) using OAA Custom Identity Provider Template.

    CustomIdPProvider class consists of IdP domain information, user, group and external associations for identities like AWS Roles.

    Classes uses dictionaries to track most components, dictionaries are all keyed by string of the entity name

    Args:
        name (str): Name of IdP
        idp_type (str): Type descriptor for IdP, can be unique or share across multiple IdP e.g. ldap, IPA
        domain (str): IdP domain name
        description (str, optional): Description for IdP. Defaults to None.

    Attributes:
        name (str): Name of custom IdP
        idp_type (str): Type for IdP
        description (str): Description for IdP
        domain (CustomIdPDomain): Domain model, created with domain name at init
        users (dict[CustomIdPUser]): Dictionary of CustomIdPUser class instances
        groups (dict[CustomIdPGroup]): Dictionary of CustomIdPGroup class instances
        property_definitions (IdPPropertyDefinitions): Custom Property definitions for IdP instance
    """

    TEMPLATE="identity_provider"

    def __init__(self, name: str, idp_type: str, domain: str, description: str = None) -> None:
        self.name = name
        self.idp_type = idp_type
        self.description = description

        self.property_definitions = IdPPropertyDefinitions()
        self.domain = CustomIdPDomain(domain, property_definitions=self.property_definitions)
        self.users = CaseInsensitiveDict()
        self.groups = CaseInsensitiveDict()
        self.apps = CaseInsensitiveDict()

    def __str__(self) -> str:
        return f"Custom IdP Provider {self.name} - {self.idp_type}"

    def __repr__(self) -> str:
        return f"CustomIdPProvider(name={self.name!r}, idp_type={self.idp_type!r}, domain={self.domain!r}, description={self.description!r})"

    def get_payload(self) -> dict:
        """ Return formatted payload as dictionary for JSON conversion and upload """
        payload = {}
        payload['custom_property_definition'] = self.property_definitions.to_dict()
        payload['name'] = self.name
        payload['idp_type'] = self.idp_type
        payload['domains'] = [self.domain.to_dict()]
        payload['users'] = [user.to_dict() for user in self.users.values()]
        payload['groups'] = [group.to_dict() for group in self.groups.values()]
        payload['apps'] = [app.to_dict() for app in self.apps.values()]
        return payload

    def add_user(self, name: str, full_name: str = None, email: str = None, identity: str = None) -> CustomIdPUser:
        """ Add user to IdP

        if no identity is set name will be used as identity

        Arguments:
            name (str): primary ID for user
            full_name (str): optional full name for display
            email (str): optional email for user
            identity (str): optional unique identifier for user, if None name is used as identity

        Returns:
            CustomIdPUser

        """

        if identity:
            identifier = identity
        else:
            identifier = name

        if identifier in self.users:
            raise OAATemplateException(f"IdP user identified by {identifier} already defined")

        self.users[identifier] = CustomIdPUser(name, email, full_name, identity, property_definitions=self.property_definitions)

        return self.users[identifier]

    def add_group(self, name: str, full_name: str = None, identity: str = None) -> CustomIdPGroup:
        """ Add group to IdP.

        Arguments:
            name (str): primary ID for group
            full_name (str): optional display name for group
            identity (str): optional unique identifier for group, if None name is used as identity

        """

        if identity:
            identifier = identity
        else:
            identifier = name

        if identifier in self.groups:
            raise OAATemplateException(f"IdP group {identifier} already defined")
        self.groups[identifier] = CustomIdPGroup(name=name, full_name=full_name, identity=identity, property_definitions=self.property_definitions)

        return self.groups[identifier]

    def add_app(self, id: str, name: str) -> CustomIdPApp:
        """_summary_

        Args:
            id (str): _description_
            name (str): _description_

        Raises:

        Returns:
            CustomIdPApp: _description_
        """

        if id in self.apps:
            raise OAATemplateException(f"IdP App with ID {id} already defined")
        self.apps[id] = CustomIdPApp(id=id, name=name, property_definitions=self.property_definitions)

        return self.apps[id]


class CustomIdPDomain():
    """ Domain model for Custom IdP provider.

    Args:
        name (str): domain name

    Attributes:
        name (str): domain name

    """

    def __init__(self, name: str, property_definitions: IdPPropertyDefinitions = None) -> None:
        self.name = name
        self._tags = []
        self._properties = {}
        self._property_definitions = property_definitions

    def __str__(self) -> str:
        return f"Custom IdP Domain {self.name}"

    def __repr__(self) -> str:
        return f"CustomIdPDomain(name={self.name!r})"

    def to_dict(self) -> dict:
        """ Output function for payload. """
        domain = {}
        domain['name'] = self.name
        domain['tags'] = [tag.__dict__ for tag in self._tags]
        domain['custom_properties'] = self._properties

        return domain

    def set_property(self, property_name: str, property_value: any, ignore_none: bool = False) -> None:
        """ Set custom property value for domain.

        Property name must be defined for domain before calling `set_property()`. See example below and
        `IdPPropertyDefinitions.define_domain_property` for more information.

        Args:
            property_name (str): Name of property
            property_value (Any): Value for property, type should match OAAPropertyType for property definition
            ignore_none (bool, optional): Do not set property if value is None. Defaults to False.

        Raises:
            OAATemplateException: If property with `property_name` is not defined.

        Example:
            >>> idp = CustomIdPProvider(name="Example IdP", idp_type="example", domain="example.com")
            >>> idp.property_definitions.define_domain_property(name="my_property", property_type=OAAPropertyType.STRING)
            >>> idp.domain.set_property(property_name="my_property", property_value="domain property value")
        """

        if not self._property_definitions:
            raise OAATemplateException("No custom property definitions found for domain")

        if ignore_none and property_value is None:
            return

        self._property_definitions.validate_property_name(property_name, entity_type=IdPEntityType.DOMAIN)
        self._properties[property_name] = property_value

    def add_tag(self, key: str, value: str = "") -> None:
        """ Add a new tag to IdP Domain.

        Args:
            key (str): Key for tag, aka name. Must be present and must be letters, numbers or _ (underscore) only.
            value (str, optional): Value for Tag, will appear in Veza as `key:value`. Must be letters, numbers, whitespace and the special characters @,._- only. Defaults to "".
        """

        tag = Tag(key=key, value=value)
        if tag not in self._tags:
            self._tags.append(tag)

class IdPUserIdentityType(str, Enum):
    """ Types of identities for permission mapping. """
    Human = "HUMAN"
    NonHuman = "NONHUMAN"

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}.{self.name}'

class CustomIdPUser():
    """ User model for CustomIdPProvider.

    Args:
        name (str): username for identity
        email (str): primary email for user
        full_name (str): Display name for user
        identity (str): unique identifier for user (may be same as username or email, or another unique ID like employee number)

    Attributes:
        name (str): username for identity
        email (str): primary email for user
        full_name (str): display name for user
        identity (str): unique identifier for user (may be same as username or email, or another unique ID like employee number)
        department (str): department name for user
        is_active (bool): if user is active, defaults to None
        is_guest (bool): if user is a guest type user, defaults to None
        manager_id (str, optional): CustomIdPUser.identity of manager, defaults to None
        identity_type (IdPUserIdentityType, optional): Identity type for user (HUMAN, NONHUMAN), defaults to HUMAN if not set.

    """

    def __init__(self, name: str, email: str = None, full_name: str = None, identity: str = None, property_definitions: IdPPropertyDefinitions = None) -> None:
        self.name = name
        self.email = email
        self.full_name = full_name
        self.identity = identity

        self.department = None
        self.is_active = None
        self.is_guest = None
        self.manager_id = None
        self.identity_type = None

        self._source_identity = None
        self._groups = {}
        self._assumed_roles = {}
        self._tags = []
        self._properties = {}
        self._property_definitions = property_definitions
        self._app_assignments = {}

    def __str__(self) -> str:
        return f"IdP User - {self.name} ({self.identity})"

    def __repr__(self) -> str:
        return f"CustomIdPUser(name={self.name!r}, email={self.email!r}, full_name={self.full_name!r}, identity={self.identity!r})"

    def to_dict(self) -> dict:
        """ Function to prepare user entity for payload """
        user = {}
        user['name'] = self.name
        user['email'] = self.email
        if self.identity:
            user['identity'] = self.identity
        else:
            user['identity'] = self.name

        user['full_name'] = self.full_name
        user['department'] = self.department
        user['is_active'] = self.is_active
        user['is_guest'] = self.is_guest
        user['manager_id'] = self.manager_id
        user['groups'] = [g for g in self._groups.values()]
        user['assumed_role_arns'] = [r for r in self._assumed_roles.values()]

        user['source_identity'] = self._source_identity
        user['tags'] = [tag.__dict__ for tag in self._tags]
        user['custom_properties'] = self._properties
        user['app_assignments'] = [r for r in self._app_assignments.values()]
        user['identity_type'] = self.identity_type

        return {k: v for k, v in user.items() if v not in [None, [], {}]}

    def set_source_identity(self, identity: str, provider_type: IdPProviderType) -> None:
        """ Set an source external identity for user.

        - `source_identity` will connect CustomIdP user to a Veza graph IdP user.
        - `provider_type` limits scope for finding matching IdP identities
        - search all providers with `IdPProviderType.ANY`.

        Args:
            identity (str): Unique Identity of the source identity
            provider_type (IdPProviderType): Type for provider to match source identity from

        """
        if not isinstance(provider_type, IdPProviderType):
            raise OAATemplateException("provider_type must be IdPProviderType enum")

        self._source_identity = {"identity": identity, "provider_type": provider_type}
        return None

    def add_assumed_role_arns(self, arns: List[str]) -> None:
        """ Add AWS Roles to list of roles user can assume by ARN.

        Args:
            arns (list): list of role ARNs as strings that the user is allowed to assume

        """

        if not isinstance(arns, list):
            raise OAATemplateException("arns must be of type list")

        for arn in arns:
            if arn not in self._assumed_roles:
                self._assumed_roles[arn] = {"identity": arn}

        return

    def add_groups(self, group_identities: List[str]) -> None:
        """ Add user to group(s) by group name

        Args:
            group_identities (list): list of strings for group identities to add user to

        """

        if not isinstance(group_identities, list):
            raise OAATemplateException("group_identities must be list")

        for group in group_identities:
            if group not in self._groups:
                self._groups[group] = {"identity": group}

        return

    def add_app_assignment(self, id: str, name: str, app_id: str, assignment_properties: Optional[dict] = None) -> None:
        """Create App assignment for user

        Args:
            id (str): ID of App assignment, must be unique for user
            name (str): Name of assignment
            app_id (str): App ID, must exist in list of Apps for IDP
            assignment_properties (Optional[dict], optional): Optional custom properties to set. Property names must be defined first. Defaults to None.

        Raises:
            OAATemplateException: Duplicate assignment ID
            OAATemplateException: Unknown assignment property name
        """
        if assignment_properties is not None and not self._property_definitions:
            raise OAATemplateException("No custom property definitions found for app assignemnt")

        if assignment_properties is None:
            assignment_properties = {}

        if id in self._app_assignments:
            raise OAATemplateException(f"App assignment with ID {id} already exists for user")

        for property_name in assignment_properties.keys():
            self._property_definitions.validate_property_name(property_name, entity_type=IdPEntityType.APPASSIGNMENT)

        self._app_assignments[id] = {"id": id, "name": name, "app_id": app_id, "custom_properties": assignment_properties}

        return

    def set_property(self, property_name: str, property_value: any, ignore_none: bool = False) -> None:
        """ Set custom property value for user.

        Property name must be defined for users before calling `set_property()`. See example below and
        `IdPPropertyDefinitions.define_user_property` for more information.

        Args:
            property_name (str): Name of property
            property_value (Any): Value for property, type should match OAAPropertyType for property definition
            ignore_none (bool, optional): Do not set property if value is None. Defaults to False.

        Raises:
            OAATemplateException: If property with `property_name` is not defined.

        Example:
            >>> idp = CustomIdPProvider(name="Example IdP", idp_type="example", domain="example.com")
            >>> idp.property_definitions.define_user_property(name="my_property", property_type=OAAPropertyType.STRING)
            >>> user1 = idp.add_user(name="User 1")
            >>> user1.set_property("my_property", "user1 value")
        """

        if not self._property_definitions:
            raise OAATemplateException("No custom property definitions found for user")

        if ignore_none and property_value is None:
            return

        self._property_definitions.validate_property_name(property_name, entity_type=IdPEntityType.USER)
        self._properties[property_name] = property_value

    def add_tag(self, key: str, value: str = "") -> None:
        """ Add a new tag to IdP User.

        Args:
            key (str): Key for tag, aka name. Must be present and must be letters, numbers or _ (underscore) only.
            value (str, optional): Value for Tag, will appear in Veza as `key:value`. Must be letters, numbers, whitespace and the special characters @,._- only. Defaults to "".
        """

        tag = Tag(key=key, value=value)
        if tag not in self._tags:
            self._tags.append(tag)

class CustomIdPGroup():
    """ Group model for CustomIdPProvider.

    Args:
        name (str): name of group
        full_name (str): optional full name for group
        identity (str): optional identifier for group if name is not reference identifier

    Parameters:
        name (str): name of group
        full_name (str): optional full name for group
        identity (str): optional identifier for group, if None name is used as identity
        is_security_group (bool): Property for group, defaults to None (unset)

    """

    def __init__(self, name: str, full_name: str = None, identity: str = None, property_definitions: IdPPropertyDefinitions = None) -> None:
        self.name = name
        self.full_name = full_name
        self.identity = identity

        self.is_security_group = None

        self._source_identity = None
        self._groups = {}
        self._assumed_roles = {}
        self._tags = []
        self._properties = {}
        self._property_definitions = property_definitions
        self._app_assignments = {}

    def __str__(self) -> str:
        return f"IdP Group {self.name} ({self.identity})"

    def __repr__(self) -> str:
        return f"CustomIdPGroup(name={self.name!r}, full_name={self.full_name!r}, identity={self.identity!r})"

    def to_dict(self) -> None:
        """ Function to prepare user entity for payload. """

        group = {}
        group['name'] = self.name
        if self.identity:
            group['identity'] = self.identity
        else:
            group['identity'] = self.name

        group['full_name'] = self.full_name
        group['is_security_group'] = self.is_security_group
        group['assumed_role_arns'] = [r for r in self._assumed_roles.values()]
        group['groups'] = [g for g in self._groups.values()]
        group['source_identity'] = self._source_identity
        group['tags'] = [tag.__dict__ for tag in self._tags]
        group['custom_properties'] = self._properties
        group['app_assignments'] = [r for r in self._app_assignments.values()]

        return {k: v for k, v in group.items() if v not in [None, [], {}]}

    def set_source_identity(self, identity: str, provider_type: IdPProviderType) -> None:
        """ Set an source external identity for group.

        - `source_identity` will connect CustomIDP group to a Veza graph IdP group.
        - `provider_type` limits scope for finding matching IdP group identities
        - search all providers with `IdPProviderType.ANY`.

        Args:
            identity (str): Unique Identity of the source group
            provider_type (IdPProviderType): Type for provider to match source identity from

        """
        if not isinstance(provider_type, IdPProviderType):
            raise OAATemplateException("provider_type must be IdPProviderType enum")

        self._source_identity = {"identity": identity, "provider_type": provider_type}
        return None

    def add_app_assignment(self, id: str, name: str, app_id: str, assignment_properties: Optional[dict] = None) -> None:
        """Create App assignment for group

        Args:
            id (str): ID of App assignment, must be unique for group
            name (str): Name of assignment
            app_id (str): App ID, must exist in list of Apps for IDP
            assignment_properties (Optional[dict], optional): Optional custom properties to set. Property names must be defined first. Defaults to None.

        Raises:
            OAATemplateException: Duplicate assignment ID
            OAATemplateException: Unknown assignment property name
        """
        if assignment_properties is not None and not self._property_definitions:
            raise OAATemplateException("No custom property definitions found for app assignemnt")

        if assignment_properties is None:
            assignment_properties = {}

        if id in self._app_assignments:
            raise OAATemplateException("App assignment with ID {id} already exists for group")

        for property_name in assignment_properties.keys():
            self._property_definitions.validate_property_name(property_name, entity_type=IdPEntityType.APPASSIGNMENT)

        self._app_assignments[id] = {"id": id, "name": name, "app_id": app_id, "custom_properties": assignment_properties}

        return

    def add_assumed_role_arns(self, arns: List[str]) -> None:
        """ Add AWS Roles to list of roles group members can assume by ARN.

        Args:
            arns (list): list of role ARNs as strings that the group members are allowed to assume

        """

        if not isinstance(arns, list):
            raise OAATemplateException("arns must be of type list")

        for arn in arns:
            if arn not in self._assumed_roles:
                self._assumed_roles[arn] = {"identity": arn}

        return

    def add_groups(self, group_identities: List[str]) -> None:
        """ Add group to group(s) by group name

        Adds current group to another parent group by the group identifier

        Args:
            group_identities (list): list of strings for group identities to add group to

        """

        if not isinstance(group_identities, list):
            raise OAATemplateException("group_identities must be list")

        for group_identity in group_identities:
            if (self.identity and group_identity == self.identity) or (not self.identity and group_identity == self.name):
                raise OAATemplateException(f"Cannot add a group to itself '{group_identity}'")
            if group_identity not in self._groups:
                self._groups[group_identity] = {"identity": group_identity}

        return

    def set_property(self, property_name: str, property_value: any, ignore_none: bool = False) -> None:
        """ Set custom property value for group.

        Property name must be defined for groups before calling `set_property()`. See example below and
        `IdPPropertyDefinitions.define_group_property` for more information.

        Args:
            property_name (str): Name of property
            property_value (Any): Value for property, type should match OAAPropertyType for property definition
            ignore_none (bool, optional): Do not set property if value is None. Defaults to False.

        Raises:
            OAATemplateException: If property with `property_name` is not defined.

        Example:
            >>> idp = CustomIdPProvider(name="Example IdP", idp_type="example", domain="example.com")
            >>> idp.property_definitions.define_group_property(name="my_property", property_type=OAAPropertyType.STRING)
            >>> group1 = idp.add_group(name="Group 1")
            >>> group1.set_property("my_property", "group1 value")
        """

        if not self._property_definitions:
            raise OAATemplateException("No custom property definitions found for group")

        if ignore_none and property_value is None:
            return

        self._property_definitions.validate_property_name(property_name, entity_type=IdPEntityType.GROUP)
        self._properties[property_name] = property_value

    def add_tag(self, key: str, value: str = "") -> None:
        """ Add a new tag to IdP Group.

        Args:
            key (str): Key for tag, aka name. Must be present and must be letters, numbers or _ (underscore) only.
            value (str, optional): Value for Tag, will appear in Veza as `key:value`. Must be letters, numbers, whitespace and the special characters @,._- only. Defaults to "".
        """

        tag = Tag(key=key, value=value)
        if tag not in self._tags:
            self._tags.append(tag)

class CustomIdPApp:
    """App model for CustomIdPProvider

    Args:
        id (str): ID for App, must be unique
        name (str): Name for App
        property_definitions (IdPPropertyDefinitions, optional): Custom property definitions, required to set custom properties. Defaults to None.

    Attributes:
        id (str): ID for App, must be unique
        name (str): Name for App
        description (str): Description property for App
    """

    def __init__(self, id: str, name: str, property_definitions: IdPPropertyDefinitions = None) -> None:

        self.id = id
        self.name = name
        self.description = ""

        self._assumed_roles = {}
        self._tags = []
        self._properties = {}
        self._property_definitions = property_definitions

    def __str__(self) -> str:
        return f"IdP App - {self.name} ({self.id})"

    def __repr__(self) -> str:
        return f"CustomIdPApp(id={self.id!r}, name={self.name!r})"

    def to_dict(self) -> dict:
        app = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "assumed_role_arns": [r for r in self._assumed_roles.values()],
            "custom_properties": self._properties,
            "tags": [tag.__dict__ for tag in self._tags]
        }
        return app

    def add_assumed_role_arns(self, arns: List[str]) -> None:
        """ Add AWS Roles to list of roles App can assume by ARN. Any Users or Groups assigned to the App are represented as being able to assume the roles.

        Args:
            arns (list): list of role ARNs as strings that the user is allowed to assume

        """

        if not isinstance(arns, list):
            raise OAATemplateException("arns must be of type list")

        for arn in arns:
            if arn not in self._assumed_roles:
                self._assumed_roles[arn] = {"identity": arn}

        return

    def set_property(self, property_name: str, property_value: any, ignore_none: bool = False) -> None:
        """ Set custom property value for app.

        Property name must be defined for app before calling `set_property()`. See example below and
        `IdPPropertyDefinitions.define_app_property` for more information.

        Args:
            property_name (str): Name of property
            property_value (Any): Value for property, type should match OAAPropertyType for property definition
            ignore_none (bool, optional): Do not set property if value is None. Defaults to False.

        Raises:
            OAATemplateException: If property with `property_name` is not defined.

        Example:
            >>> idp = CustomIdPProvider(name="Example IdP", idp_type="example", domain="example.com")
            >>> idp.property_definitions.define_app_property(name="my_property", property_type=OAAPropertyType.STRING)
            >>> app1 = idp.add_app(id="app1", ="App 1")
            >>> app1.set_property("my_property", "app1 value")
        """

        if not self._property_definitions:
            raise OAATemplateException("No custom property definitions found for app")

        if ignore_none and property_value is None:
            return

        self._property_definitions.validate_property_name(property_name, entity_type=IdPEntityType.APP)
        self._properties[property_name] = property_value

    def add_tag(self, key: str, value: str = "") -> None:
        """ Add a new tag to IdP User.

        Args:
            key (str): Key for tag, aka name. Must be present and must be letters, numbers or _ (underscore) only.
            value (str, optional): Value for Tag, will appear in Veza as `key:value`. Must be letters, numbers, whitespace and the special characters @,._- only. Defaults to "".
        """

        tag = Tag(key=key, value=value)
        if tag not in self._tags:
            self._tags.append(tag)


class IdPPropertyDefinitions():
    """
    Model for defining custom properties for CustomIdPProvider and its entities (users, groups, domain).

    Property definitions define the names for additional entity properties and the expected type.

    Attributes:
        domain_properties (dict): property definitions for IdP Domain
        user_properties (dict): property definitions for IdP users
        group_properties (dict): property definitions for IdP groups

    """

    def __init__(self) -> None:
        super().__init__()
        self.domain_properties = {}
        self.user_properties = {}
        self.group_properties = {}
        self.app_properties = {}
        self.app_assignment_properties = {}

    def __str__(self) -> str:
        return f"IdP Property Definitions"

    def __repr__(self) -> str:
        return f"IdPPropertyDefinitions()"

    def to_dict(self) -> dict:
        """ Returns custom IdP property definitions. """

        return {"domain_properties": self.domain_properties,
                "user_properties": self.user_properties,
                "group_properties": self.group_properties,
                "app_properties": self.app_properties,
                "app_assignment_properties": self.app_assignment_properties
                }

    def define_domain_property(self, name: str, property_type: OAAPropertyType) -> None:
        """ Define a domain custom property.

        Args:
            name (str): name of property
            property_type (OAAPropertyType): type for property
        """
        self._validate_types(name, property_type)
        self.domain_properties[name] = property_type

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

    def define_app_property(self, name: str, property_type: OAAPropertyType) -> None:
        """Define an app custom property

        Args:
            name (str): name of property
            property_type (OAAPropertyType): type for property
        """
        self._validate_types(name, property_type)
        self.app_properties[name] = property_type

    def define_app_assignment_property(self, name: str, property_type: OAAPropertyType) -> None:
        """Define an app assignment custom property

        Args:
            name (str): name of property
            property_type (OAAPropertyType): type for property
        """
        self._validate_types(name, property_type)
        self.app_assignment_properties[name] = property_type

    def validate_property_name(self, property_name: str, entity_type: str) -> None:
        """ Validate that a property name has been defined for a given IdP entity.

        Raises exception if property name has not been previously defined for entity

        Args:
            property_name (str): name of property to validate
            entity_type (str): type of entity custom property is for (domain, users, groups)

        Raises:
            OAATemplateException: If property name is not defined

        """
        valid_property_names = []
        if entity_type == IdPEntityType.DOMAIN:
            valid_property_names = self.domain_properties.keys()
        elif entity_type == IdPEntityType.USER:
            valid_property_names = self.user_properties.keys()
        elif entity_type == IdPEntityType.GROUP:
            valid_property_names = self.group_properties.keys()
        elif entity_type == IdPEntityType.APP:
            valid_property_names = self.app_properties.keys()
        elif entity_type == IdPEntityType.APPASSIGNMENT:
            valid_property_names = self.app_assignment_properties.keys()
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
            name (str): name or property
            property_type (OAAPropertyType): OAA type for property

        """
        if not isinstance(name, str):
            raise OAATemplateException("property name must be type string")
        if not isinstance(property_type, OAAPropertyType):
            raise OAATemplateException("property_type must be type OAAPropertyType enum")

