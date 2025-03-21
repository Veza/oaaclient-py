"""

Classes for constructing an OAA JSON payload (Custom "Application" or "IdP").

Copyright 2022 Veza Technologies Inc.

Use of this source code is governed by the MIT
license that can be found in the LICENSE file or at
https://opensource.org/licenses/MIT.
"""

from __future__ import annotations

import json
import logging
import re
from enum import Enum
from typing import List, Optional

from .structures import CaseInsensitiveDict

PROPERTY_NAME_REGEX=r"^[a-z][a-z_]*$"

log = logging.getLogger(__name__)


class OAATemplateException(Exception):
    """ General exception used for violations of the template schema. """

    def __init__(self, message):
        self.message = message
        super().__init__(self.message)


class OAAPermission(str, Enum):
    """ Canonical permissions used by Veza Authorization Framework.

    Used to describe the raw data or metadata permissions granted by `CustomPermission`
    """
    DataRead = "DataRead"
    DataWrite = "DataWrite"
    DataCreate = "DataCreate"
    DataDelete = "DataDelete"
    MetadataRead = "MetadataRead"
    MetadataWrite = "MetadataWrite"
    MetadataCreate = "MetadataCreate"
    MetadataDelete = "MetadataDelete"
    NonData = "NonData"
    Uncategorized = "Uncategorized"

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}.{self.name}'

class OAAIdentityType(str, Enum):
    """ Types of identities for permission mapping. """
    LocalUser = "local_user"
    LocalGroup = "local_group"
    LocalRole = "local_role"
    IdP = "idp"
    AccessCred = "local_access_creds"

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}.{self.name}'

class Provider():
    """Base class for CustomProvider. """
    def __init__(self, name, custom_template):
        self.name = name
        self.custom_template = custom_template

    def serialize(self):
        return json.dumps({"name": self.name, "custom_template": self.custom_template})


class Application():
    """Base class for CustomApplication. """

    def __init__(self, name, application_type, description=None):
        self.name = name
        self.application_type = application_type
        self.description = description
        self.properties = []


class CustomApplication(Application):
    """Class for modeling application authorization using the OAA Application template.

    CustomApplication class consists of identities, resources and permissions and produces the OAA JSON payload for the
    custom application template.

    Class uses dictionaries to track most entities that can be referenced after creation. Dictionaries keys are case insensitive
    of the entity identifier (name or id). This applies to `local_users`, `local_groups`, `local_roles`, `idp_identities`,
    `resources` and `custom_permissions`.

    Args:
        name (str): Name of custom application
        application_type (str): Searchable property, can be unique or shared across multiple applications
        description (str, optional): Description for application. Defaults to None.

    Attributes:
        application_type (str): Searchable application type
        custom_permissions (dict[OAAPermission]): Dictionary of class instances
        description (str): Description for application
        identity_to_permissions (dict): Mapping of authorizations for identities to resources
        idp_identities (dict[IdPIdentity]): Contains federated identities without a corresponding local account
        local_groups (dict[LocalGroup]): Contains application groups (collections of users)
        local_roles (dict[LocalRole]): Contains application roles (collections of permissions)
        local_users (dict[LocalUser]): Contains users local to the application and their properties
        name (str): Name of custom application
        properties (dict): key value pairs of property values, property keys must be defined as part of the property_definitions
        property_definitions (ApplicationPropertyDefinitions): Custom property names and types for the application
        resources (dict[CustomResource]): Contains data resources and subresources within the application

    """

    TEMPLATE = "application"

    def __init__(self, name: str, application_type: str, description: str = None) -> None:
        super().__init__(name, application_type, description)
        self.local_users = CaseInsensitiveDict()
        self.local_groups = CaseInsensitiveDict()
        self.local_roles = CaseInsensitiveDict()
        self.idp_identities = CaseInsensitiveDict()
        self.access_creds = CaseInsensitiveDict()
        self.resources = CaseInsensitiveDict()
        self.tags = []
        self.property_definitions = ApplicationPropertyDefinitions(application_type)
        self.properties = {}

        self.custom_permissions = CaseInsensitiveDict()

        self.identity_to_permissions = {}

    def __str__(self) -> str:
        return f"Custom Application {self.name} - {self.application_type}"

    def __repr__(self) -> str:
        return f"CustomApplication(name={self.name!r}, application_type={self.application_type!r}, description={self.description!r})"

    def get_payload(self) -> dict:
        """Get the OAA payload.

        Returns the complete OAA template payload for application as serializable dictionary

        Returns:
            dict: OAA payload as dictionary
        """

        payload = {}
        payload['custom_property_definition'] = {"applications": [self.property_definitions.to_dict()]}
        payload['applications'] = [self.app_dict()]  # OAA format expects list
        payload['permissions'] = self.permissions_dict()
        payload['identity_to_permissions'] = self.get_identity_to_permissions()
        return payload

    def app_dict(self) -> dict:
        """ Return the 'applications' section of the payload as serializable dictionary. """
        # self.property_definitions.validate_properties(self.properties, "application")

        repr = {"name": self.name,
                "application_type": self.application_type,
                "description": self.description,
                "local_users": [user.to_dict() for user in self.local_users.values()],
                "local_groups": [group.to_dict() for group in self.local_groups.values()],
                "local_roles": [role.to_dict() for role in self.local_roles.values()],
                "local_access_creds": [cred.to_dict() for cred in self.access_creds.values()],
                "tags": [tag.__dict__ for tag in self.tags],
                "custom_properties": self.properties
                }

        repr['resources'] = [resource.to_dict() for resource in self.resources.values()]
        return repr

    def permissions_dict(self) -> dict:
        """ Return the 'permissions' section of the payload as serializable dictionary. """

        return [permission.to_dict() for permission in self.custom_permissions.values()]

    def define_custom_permission(self, custom_permission: CustomPermission) -> CustomPermission:
        """Add a custom permission to the application.

        .. deprecated::
            See `CustomApplication.add_custom_permission()`

        Args:
          custom_permission (CustomPermission): CustomPermission class

        Raises:
          Exception: Duplicate Keys

        Returns:
            CustomPermission: The defined custom Permission
        """

        if not isinstance(custom_permission, CustomPermission):
            raise TypeError("custom_permission must be of type CustomPermission")

        if custom_permission.name in self.custom_permissions:
            raise OAATemplateException(f"Custom permission {custom_permission.name} already defined")

        self.custom_permissions[custom_permission.name] = custom_permission

        return self.custom_permissions[custom_permission.name]

    def add_custom_permission(self, name: str, permissions: List[OAAPermission], apply_to_sub_resources: bool = False, resource_types: List[str] = None) -> CustomPermission:
        """Create a new custom permission.

        Creates a new `CustomPermission` object for the application that can be used to authorize identities to the application, resources/sub-resource or as part of a role.

        Args:
            name (str): Name of the permission
            permissions (list[OAAPermission]): Canonical permissions the custom permission represents
            apply_to_sub_resources (bool, optional): If true, when permission is applied to the application or resource, identity also has permission to all children of application/resource. Defaults to False.
            resource_types  (list, optional): List of resource types as strings that the permission relates to. Defaults to empty list.

        Returns:
            CustomPermission
        """

        if name in self.custom_permissions:
            raise OAATemplateException(f"Custom permission {name} already exists")

        if not isinstance(permissions, list):
            raise OAATemplateException("permissions must be list")

        elif not all(isinstance(p, OAAPermission) for p in permissions):
            raise OAATemplateException("permission must be of type OAAPermission")

        self.custom_permissions[name] = CustomPermission(name, permissions, apply_to_sub_resources, resource_types)

        return self.custom_permissions[name]

    def add_resource(self, name: str, resource_type: str, description: str = None, unique_id: str = None) -> CustomResource:
        """ Create a new resource under the application.

        Resource type is used to group and filter application resources. It should be consistent for all common resources of an application.

        Returns new resource object.

        Resource is identified by `name` by default unless `unique_id` is provided. `name` must be unique if not using `unique_id`.

        Resources can be referenced after creation using the `.resources` dictionary attribute. Dictionary is keyed by unique_id or name if not using
        unique_id. Use `unique_id` when name is not guaranteed to be unique.

        Args:
            name (str): Name of resources
            resource_type (str): Type for resource
            description (str, optional): Description of resources. Defaults to None.
            unique_id (str, optional): Unique identifier for resource. defaults to None.

        Returns:
            CustomResource
        """

        if unique_id:
            identifier = unique_id
        else:
            identifier = name

        if identifier in self.resources:
            raise OAATemplateException(f"Resource identified by {identifier} already defined")

        self.resources[identifier] = CustomResource(name=name,
                                                    unique_id=unique_id,
                                                    resource_type=resource_type,
                                                    description=description,
                                                    application_name=self.name,
                                                    property_definitions=self.property_definitions
                                                   )

        return self.resources[identifier]

    def add_local_user(self, name: str, identities: List[str] = None, groups: List[str] = None, unique_id: str = None) -> LocalUser:
        """ Create a new local user for application.

        Local users can be assigned to groups and associated with resources via permissions or roles.
        Groups and identities can be provided at creation or added later. See `Identity` and `LocalUser` class for operations.

        Local users will be identified by `name` by default, if `unique_id` is provided it will be used as the identifier instead.

        Local users can be referenced after creation using the `.local_users` dictionary attribute. Dictionary is case insensitivekeyed by unique_id or name if not using unique_id.

        Use `unique_id` when name is not guaranteed to be unique. All permission, group and role assignments will be referenced by unique_id.

        Args:
            name (str): Display name for user
            identities (list): List of identities as strings (usually email) for local user. Used to map local user to discovered IdP identities.
            groups (list[LocalGroup]): List of group names (as string) to add user to
            unique_id (str, optional): Unique identifier for user for reference by ID

        Returns:
            LocalUser
        """

        if unique_id:
            identifier = unique_id
        else:
            identifier = name
        if identifier in self.local_users:
            raise OAATemplateException(f"Local user identified by {identifier} already defined")

        self.local_users[identifier] = LocalUser(name, identities, groups, unique_id=unique_id, property_definitions=self.property_definitions)

        return self.local_users[identifier]

    def add_local_group(self, name: str, identities: List[str] = None, unique_id: str = None) -> LocalGroup:
        """ Create a new local group.

        Groups can be associated to resources via permissions or roles. All users in the local group are granted the group's authorization.

        Local groups will be identified by `name` by default, if `unique_id` is provided it will be used as the identifier instead

        Local groups can be referenced after creation using `.local_groups` dictionary attribute. Dictionary is case insensitive keyed by unique_id or name if not using unique_id.

        Args:
            name (str): Display name for group
            identities (list): List of IdP identities to associate group with.
            unique_id (str, optional): Unique identifier for group for reference by ID

        Returns:
            LocalGroup
        """
        if unique_id:
            identifier = unique_id
        else:
            identifier = name

        if identifier in self.local_groups:
            raise OAATemplateException(f"Local group identified by {identifier} already defined")
        self.local_groups[identifier] = LocalGroup(name, identities, unique_id=unique_id, property_definitions=self.property_definitions)

        return self.local_groups[identifier]

    def add_local_role(self, name: str, permissions: List[str] = None, unique_id: str = None) -> LocalRole:
        """ Create a new local role.

        - A local role represents a collection of permissions.
        - Identities (local user, group, idp user) can be assigned a role to the application or resource, granting the role's permissions.
        - Local roles will be identified by `name` by default, if `unique_id` is provided it will be used as the identifier instead.
        - Local roles can be referenced after creation if needed through `.local_roles` case insensitive dictionary attribute.
        - When a permission that has `resource_types` is added to a role, it will only apply to resources with a matching `resource_type`

        Args:
            name (str): Display name for role
            permissions (list): List of Custom Permission names to include in role. `CustomPermission` must be created separately.
            unique_id (str, optional): Unique identifier for role for reference by ID

        Returns:
            LocalRole
        """
        if unique_id:
            identifier = unique_id
        else:
            identifier = name

        if identifier in self.local_roles:
            raise Exception(f"Local role identified by {identifier} already defined")
        self.local_roles[identifier] = LocalRole(name, permissions, unique_id=unique_id, property_definitions=self.property_definitions)

        return self.local_roles[identifier]

    def add_idp_identity(self, name: str) -> IdPIdentity:
        """ Create an IdP principal identity.

        IdP users and groups can be authorized directly to applications and resources
        by associating custom application permissions and roles with an IdP identity's
        name or email.

        Args:
            name (str): IdP unique identifier for user or group.

        Returns:
            IdPIdentity
        """

        if name in self.idp_identities:
            raise OAATemplateException(f"IdP Identity {name} already defined")
        self.idp_identities[name] = IdPIdentity(name)

        return self.idp_identities[name]

    def add_access_cred(self, unique_id: str, name: str) -> AccessCred:
        """Create an Access Credential

        Access creds can be used to represent alternative access methods such as API keys or application integrations.

        Access creds can be assigned roles and permissions similar to local users. Access credentials can exist independently for use cases
        such as administratively created integrations or can be assigned to a local user for use cases like personal access tokens.

        Args:
            unique_id (str): unique identifier for access cred
            name (str): name for access cred

        Raises:
            OAATemplateException: Access credential with unique ID already exists

        Returns:
            AccessCred: New access cred
        """

        if unique_id in self.access_creds:
            raise OAATemplateException(f"Access credential identified by {unique_id} already exists")
        self.access_creds[unique_id] = AccessCred(unique_id=unique_id, name=name, property_definitions=self.property_definitions)

        return self.access_creds[unique_id]

    def add_tag(self, key: str, value: str = "") -> None:
        """ Add a tag to the Application

        Args:
            key (str): Key for tag, aka name. Must be present and must be letters, numbers or _ (underscore) only.
            value (str, optional): Value for Tag, will appear in Veza as `key:value`. Must be letters, numbers, whitespace and the special characters @,._- only. Defaults to "".
        """

        tag = Tag(key=key, value=value)
        if tag not in self.tags:
            self.tags.append(tag)

    def set_property(self, property_name: str, property_value: any, ignore_none: bool = False) -> None:
        """ Set a custom property value for the application.

        Property name must be defined for `CustomApplication` before calling set_property. See example below and
        `ApplicationPropertyDefinitions.define_application_property` for more information on defining properties.

        Args:
            property_name (str): Name of property to set value for, property names must be defined as part of the application property_definitions
            property_value (Any): Value for property, type should match OAAPropertyType for property definition
            ignore_none (bool, optional): Do not set property if value is None. Defaults to False.

        Raises:
            OAATemplateException: If property name is not defined

        Example:
            >>> app = CustomApplication("App", application_type="example")
            >>> app.property_definitions.define_application_property(name="my_property", property_type=OAAPropertyType.STRING)
            >>> app.set_property("my_property", "property value")
        """

        # validate property name is defined, validate_property_name will raise exception if not
        if not self.property_definitions:
            raise OAATemplateException(f"No custom properties defined, cannot set value for property {property_name}")

        if ignore_none and property_value is None:
            return

        self.property_definitions.validate_property_name(property_name, "application")
        self.properties[property_name] = property_value

        return

    def add_access(self, identity, identity_type, permission, resource=None):
        """ Legacy method for backwards compatibility.

        .. deprecated::
            Access should be added through identity (local_role, local_group, idp) """

        if resource:
            apply_to_application = True
        else:
            apply_to_application = False

        resource_list = []
        if resource:
            if isinstance(resource, str):
                resource = self.resources[resource]
            elif not isinstance(resource, CustomResource):
                raise OAATemplateException("resource must be CustomResource or string of existing resource")

            resource_list.append(resource)

        if identity_type == OAAIdentityType.LocalUser:
            if identity not in self.local_users:
                raise OAATemplateException(f"User {identity} not found in local_users")
            self.local_users[identity].add_permission(permission, resources=resource_list, apply_to_application=apply_to_application)
        elif identity_type == OAAIdentityType.LocalGroup:
            if identity not in self.local_groups:
                raise OAATemplateException(f"Group {identity} not found in local_groups")
            self.local_groups[identity].add_permission(permission, resources=resource_list, apply_to_application=apply_to_application)
        elif identity_type == OAAIdentityType.IdP:
            # legacy add_access did not require IdP user to exist first, create user to backwards compatibility
            if identity not in self.idp_identities:
                self.add_idp_identity(identity)
            self.idp_identities[identity].add_permission(permission, resource=resource_list, apply_to_application=apply_to_application)

        return

    def get_identity_to_permissions(self) -> list:
        """ Collect authorizations for all identities into a single list. """

        identity_to_permissions = []
        identities = []
        identities.extend(self.local_users.values())
        identities.extend(self.local_groups.values())
        identities.extend(self.idp_identities.values())
        identities.extend(self.access_creds.values())
        for identity in identities:
            entry = identity.get_identity_to_permissions(application_name=self.name)
            if "application_permissions" in entry or "role_assignments" in entry:
                identity_to_permissions.append(entry)
            else:
                # identity has no permissions or roles, pass
                pass

        return identity_to_permissions


class CustomResource():
    """
    Class for resources and sub-resources.

    Should be used for representing components of the application to which authorization
    is granted. Each resource has a name and a type. The type can be used for grouping and filtering.

    Arguments:
        name (str): display name for resource, must be unique to parent application or resource unless using unique_id
        resource_type (str): type for resource
        description (str): description for resource
        application_name (str): name of parent application
        resource_key (str, optional): for sub-resources the full unique identifier required for `identity_to_permissions` section. Defaults to name or unique_id if not provided.
        property_definitions (ApplicationPropertyDefinitions, optional): Property definitions structure for the resource
        unique_id (str, optional): Optional unique identifier for the resource. Defaults to None.

    Attributes:
        name (str): display name for resource, must be unique to parent application or resource
        unique_id (str): resource's unique identifier if provided.
        resource_type (str): type for resource
        application_name (str): name of parent application
        resource_key (str): for sub-resources represents the sub-resource's parent path
        sub_resources (dict): dictionary of sub-resources keyed by name
        properties (dict): dictionary of properties set for resource
        tags (list[Tag]): list of tags
    """

    def __init__(self, name: str, resource_type: str, description: str, application_name: str, resource_key: str = None, property_definitions: ApplicationPropertyDefinitions = None, unique_id: str = None) -> None:
        self.name = name
        if unique_id:
            self.unique_id = str(unique_id)
        else:
            self.unique_id = None

        self.resource_type = resource_type
        self.description = description
        self.application_name = application_name

        # the resource_key is used to identify the resource in the hierarchy
        if resource_key:
            self.resource_key = str(resource_key)
        elif unique_id:
            self.resource_key = str(unique_id)
        else:
            self.resource_key = str(name)

        self.sub_resources = CaseInsensitiveDict()
        self.connections = []
        self.property_definitions = property_definitions
        self.properties = {}
        self.tags = []

        self.resource_permissions = {}

    def __str__(self) -> str:
        return f"Resource: {self.name} ({self.unique_id}) - {self.resource_type}"

    def __repr__(self) -> str:
        return f"CustomResource(name={self.name!r}, resource_type={self.resource_type!r}, unique_id={self.unique_id!r}, application_name={self.application_name!r}, resource_key={self.resource_key!r})"

    def to_dict(self) -> dict:
        """ Return the dictionary representation of resource."""

        repr = {
            "id": self.unique_id,
            "name": self.name,
            "resource_type": self.resource_type,
            "description": self.description,
            "connections": self.connections
        }

        repr["sub_resources"] = [sub_resource.to_dict() for sub_resource in self.sub_resources.values()]
        repr['custom_properties'] = self.properties
        repr["tags"] = [tag.__dict__ for tag in self.tags]

        # filter out None/empty values before return
        return {k: v for k, v in repr.items() if v}

    def add_sub_resource(self, name: str, resource_type: str, description: str = None, unique_id: str = None) -> CustomResource:
        """ Create a new sub-resource under current resource

        Args:
            name (str): display name for resource
            resource_type (str): type for resource
            description (str, optional): String description. Defaults to None.
            unique_id (str, optional): Unique identifier for new subresource, Defaults to `name`.

        Returns:
            CustomResource
        """

        if unique_id:
            identifier = unique_id
        else:
            identifier = name

        sub_resource_key = f"{self.resource_key}.{identifier}"

        if identifier in self.sub_resources:
            raise Exception(f"Sub-resource identified by {identifier} already defined")

        self.sub_resources[identifier] = CustomResource(name=name,
                                                  unique_id=unique_id,
                                                  resource_type=resource_type,
                                                  description=description,
                                                  application_name=self.application_name,
                                                  resource_key=sub_resource_key,
                                                  property_definitions=self.property_definitions
                                                  )


        return self.sub_resources[identifier]

    def add_resource_connection(self, id: str, node_type: str) -> None:
        """ Add an external connection to the resource.

        Used to add a relationship to another entity discovered by Veza such as a service account or AWS IAM role.

        Args:
            id (str): Unique identifier for connection entity
            node_type (str): Veza type for connecting node

        """
        if not id:
            raise OAATemplateException("resource connection id cannot be None")
        if not node_type:
            raise OAATemplateException("resource connection node_type cannot be None")

        connection = {"id": str(id), "node_type": str(node_type)}

        if connection not in self.connections:
            self.connections.append(connection)

        return

    def add_access(self, identity, identity_type, permission):
        """ No longer supported, access should be added through identity (local_user, local_group, idp) """
        raise Exception("No longer supported: Add access via identity")

    def add_tag(self, key: str, value: str = "") -> None:
        """ Add a new tag to resource.

        Args:
            key (str): Key for tag, aka name. Must be present and must be letters, numbers or _ (underscore) only.
            value (str, optional): Value for Tag, will appear in Veza as `key:value`. Must be letters, numbers, whitespace and the special characters @,._- only. Defaults to "".
        """
        tag = Tag(key=key, value=value)
        if tag not in self.tags:
            self.tags.append(tag)

    def set_property(self, property_name: str, property_value: any, ignore_none: bool = False) -> None:
        """ Set the value for a custom property on a resource or sub-resource.

        Property name must be defined for resource type before calling `set_property()`. See example below and
        `ApplicationPropertyDefinitions.define_resource_property` for more information on defining properties.

        Args:
            property_name (str): Name of property to set value for
            property_value (Any): Value for property, type should match OAAPropertyType for property definition
            ignore_none (bool, optional): Do not set property if value is None. Defaults to False.

        Raises:
            OAATemplateException: If `property_name` is not defined

        Example:
            >>> app = CustomApplication("App", application_type="example")
            >>> app.property_definitions.define_resource_property(resource_type="cog", name="my_property", property_type=OAAPropertyType.STRING)
            >>> cog1 = app.add_resource(name="cog1", resource_type="cog")
            >>> cog1.set_property("my_property", "this value")
        """

        # validate property name is defined, validate_property_name will raise exception if not
        if not self.property_definitions:
            raise OAATemplateException(f"No custom properties defined, cannot set value for property {property_name}")

        if ignore_none and property_value is None:
            return

        self.property_definitions.validate_property_name(property_name, "resource", self.resource_type)
        self.properties[property_name] = property_value


class Identity():
    """Base class for deriving all identity types (should not be used directly).

    Args:
        name (str): name of identity
        identity_type (OAAIdentityType): Veza Identity Type (local_user, local_group, idp)
        unique_id (str, optional): ID of entity for reference by ID

    Attributes:
        name (str): name of identity
        identity_type (OAAIdentityType): Veza Identity Type (local_user, local_group, idp)
        application_permissions (list[CustomPermission]): List of permissions identity has directly to custom application
        resource_permissions (dict): Dictionary of custom permissions associated with resources and sub-resources. Key is permission, value is list of resource keys
        application_roles (LocalRole): List of roles identity has directly to custom application
        resource_roles (dict): Dictionary of local_roles for resources and sub-resources. Key is roles, value is list of resource keys
        properties (dict): Dictionary of properties for identity, allowed values will vary by identity type
        tags (list[Tag]): List of tags
    """

    def __init__(self, name: str, identity_type: OAAIdentityType, unique_id: str = None, property_definitions: ApplicationPropertyDefinitions = None) -> None:
        self.name = name
        if unique_id:
            self.unique_id = str(unique_id)
        else:
            self.unique_id = None
        self.identity_type = identity_type
        self.application_permissions = []
        self.resource_permissions = {}
        self.role_assignments = {}
        self.property_definitions = property_definitions
        self.properties = {}
        self.tags = []

    def add_permission(self, permission: str, resources: List[CustomResource] = None, apply_to_application: bool = False) -> None:
        """
        Add a permission to an identity.

        Permission can apply to either the application or application resource/sub-resources

        Args:
            permissions ([str]): List of strings representing the permission names
            resource (CustomResource, optional): Custom resource, if None permission is applied to application. Defaults to None.
            apply_to_application (bool): Apply permission to application when True, defaults to False
        """
        if not resources:
            resources = []
        elif not isinstance(resources, list):
            raise OAATemplateException("resources must be list")

        if resources and not all(isinstance(r, CustomResource) for r in resources):
            raise OAATemplateException("resources must be of a type CustomResource")

        if not (apply_to_application or resources):
            raise OAATemplateException("Must add permission to resource or application. resources cannot be empty and apply_to_application be False")

        if apply_to_application and permission not in self.application_permissions:
            self.application_permissions.append(permission)

        if resources:
            if permission in self.resource_permissions:
                for r in resources:
                    if r.resource_key not in self.resource_permissions[permission]:
                        self.resource_permissions[permission].append(r.resource_key)
                    else:
                        # permission to resource already associated
                        pass
            else:
                self.resource_permissions[permission] = [r.resource_key for r in resources]

    def add_role(self, role: str, resources: List[CustomResource] = None, apply_to_application: Optional[bool] = None, assignment_properties: Optional[dict] = None) -> None:
        """ Add a role to an identity.

        Role to authorize identity to either the application or application resource/sub-resource based on role's permissions.

        Role assignment properties can be set with the `assignment_properties` dictionary parameter with property names as the keys. Role assignment properties
        types must be defined on the application prior to setting.

        Args:
            role (str): Name of role as string
            resources (List[CustomResource], optional): Custom resource, if None role is applied to application. Defaults to None.
            apply_to_application (bool, optional): Apply permission to application when True, False will replace existing value, None will leave previous setting if any
            assignment_properties (dict, optional): Custom properties for the role assignment. Defaults to no properties.
        """
        if not resources:
            resources = []
        elif not isinstance(resources, list):
            raise OAATemplateException("resources must be list")

        if resources and not all(isinstance(r, CustomResource) for r in resources):
            raise OAATemplateException("resources must be of a type CustomResource")

        if not assignment_properties:
            assignment_properties = {}

        for property_name in assignment_properties:
            self.property_definitions.validate_property_name(property_name, entity_type="role_assignment")

        if role not in self.role_assignments:
            self.role_assignments[role] = {"apply_to_application": apply_to_application, "resources": [r.resource_key for r in resources], "custom_properties": assignment_properties}
        else:
            if apply_to_application is not None:
                self.role_assignments[role]["apply_to_application"] = apply_to_application
            for resource in resources:
                if resource.resource_key not in self.role_assignments[role]["resources"]:
                    self.role_assignments[role]["resources"].append(resource.resource_key)
            self.role_assignments[role].get("custom_properties", {}).update(assignment_properties)

        return

    def get_identity_to_permissions(self, application_name: str) -> dict:
        """Get a JSON serializable dictionary of all the identity's permissions and roles.

        Formats the identity's permissions and roles for the Custom Application template payload

        Returns:
            dict: JSON serializable dictionary of all the identity's permissions and roles
        """
        response = {}
        if self.unique_id:
            response['identity'] = self.unique_id
        else:
            response['identity'] = self.name

        response['identity_type'] = self.identity_type
        application_permissions = []
        role_assignments = []

        for p in self.application_permissions:
            application_permissions.append({"application": application_name, "permission": p, "apply_to_application": True})

        for permission in self.resource_permissions:
            application_permissions.append({"application": application_name,
                                                "resources": self.resource_permissions[permission],
                                                "permission": permission
                                                })

        for role in self.role_assignments:
            if not (self.role_assignments[role]["apply_to_application"] or self.role_assignments[role]["resources"]):
                # role is not assigned to application or any resources, skip including in payload
                continue

            assignment = {"application": application_name,
                            "role": role,
                            "apply_to_application": self.role_assignments[role]["apply_to_application"] or False
                            }

            if self.role_assignments[role]["resources"]:
                assignment["resources"] = self.role_assignments[role]["resources"]
            if self.role_assignments[role]["custom_properties"]:
                assignment["custom_properties"] = self.role_assignments[role]["custom_properties"]

            role_assignments.append(assignment)

        if application_permissions:
            response['application_permissions'] = application_permissions
        if role_assignments:
            response['role_assignments'] = role_assignments

        return response

    def add_tag(self, key: str, value: str = "") -> None:
        """ Add a new tag to identity.

        Args:
            key (str): Key for tag, aka name. Must be present and must be letters, numbers or _ (underscore) only.
            value (str, optional): Value for Tag, will appear in Veza as `key:value`. Must be letters, numbers, whitespace and the special characters @,._- only. Defaults to "".
        """

        tag = Tag(key=key, value=value)
        if tag not in self.tags:
            self.tags.append(tag)

    def set_property(self, property_name: str, property_value: any, ignore_none: bool = False) -> None:
        """ Set a custom defined property to a specific value on an identity.

        Property name must be defined for identity type before calling `set_property()`. See example below for `LocalUser`
        and `ApplicationPropertyDefinitions.define_local_user_property` for more information on defining properties.
        Property must be defined for the correct `Identity` type (`LocalUser` or `LocalGroup`, `IdPIdentity` does not support
        custom properties).

        Args:
            property_name (str): Name of property to set value for
            property_value (Any): Value for property, type should match `OAAPropertyType` for property definition
            ignore_none (bool, optional): Do not set property if value is None. Defaults to False.

        Raises:
            OAATemplateException: If property with `property_name` is not defined.

        Example:

            >>> app = CustomApplication("App", application_type="example")
            >>> app.property_definitions.define_local_user_property(name="my_property", property_type=OAAPropertyType.STRING)
            >>> user1 = app.add_local_user(name="user1")
            >>> user1.set_property("my_property", "value for user1")
        """

        if not self.property_definitions:
            raise OAATemplateException("No custom property definitions found for entity")

        if ignore_none and property_value is None:
            return

        self.property_definitions.validate_property_name(property_name, entity_type=self.identity_type)
        self.properties[property_name] = property_value

class LocalUserType(str, Enum):
    """ Enum for """
    Human = "human"
    ServiceAccount = "service_account"

class LocalUser(Identity):
    """ LocalUser identity, derived from Identity base class.

    Used to model an application user. Can be associated with an external IdP user, or represent a local account.

    Args:
        name (str): name of identity
        identities (list): list of strings for IdP identity association
        groups (list[LocalGroup]): list of group names as strings to add user too
        unique_id (string, optional): For reference by ID

    Attributes:
        name (str): name of identity
        id (str): ID of entity for ID based reference
        email (string): Users email address
        identities (list): list of strings for IdP identity association
        groups (list[LocalGroup]): list of group names as strings to add user too
        identity_type (OAAIdentityType): Veza Identity Type (local_user)
        application_permissions (list[CustomPermission]): Permissions identity has directly to custom application
        resource_permissions (dict): Dictionary of custom permissions associated with resources and sub-resources. Key is permission, value is list of resource keys
        application_roles (list[LocalRole]): Custom application roles assigned directly to the identity
        resource_roles (dict): Dictionary of local_roles for resources and sub-resources. Key is roles, value is list of resource keys
        properties (dict): Dictionary of properties for identity, allowed values will vary by identity type
        tags (list[Tag]): List of tags
        is_active (bool): Defaults to None for unset
        created_at (str): RFC3339 time stamp for user creation
        last_login_at (str): RFC3339 time stamp for last login
        deactivated_at (str): RFC3339 for user deactivate time
        password_last_changed_at (str): RFC3339 time stamp for last password change
        user_type (LocalUserType): Set the local user account type
    """

    def __init__(self, name: str, identities: List[str] = None, groups: List[str] = None, unique_id: str = None, property_definitions: ApplicationPropertyDefinitions = None) -> None:
        super().__init__(name, identity_type=OAAIdentityType.LocalUser, unique_id=unique_id, property_definitions=property_definitions)
        self.identities = append_helper(None, identities)
        self.groups = append_helper(None, groups)

        self.access_creds = []

        # properties available for local users
        self.is_active = None
        self.created_at = None
        self.last_login_at = None
        self.deactivated_at = None
        self.password_last_changed_at = None
        self.user_type = None
        self.email = None

    def __str__(self) -> str:
        return f"Local User - {self.name} ({self.unique_id})"

    def __repr__(self) -> str:
        return f"LocalUser(name={self.name!r}, unique_id={self.unique_id!r}, identities={self.identities})"

    def add_identity(self, identity: str) -> None:
        """ Add an identity to user.

        Identity should match the email address or another principal identifier for an IdP user (Okta, Azure, ect). Veza
        will create a connection from the application local user to IdP identity.

        Args:
            identity (str): email or identifier for IdP user
        """
        self.identities = append_helper(self.identities, identity)

    def add_identities(self, identities: List[str]) -> None:
        """ Add multiple identities to a local user from a list.

        Args:
            identities (list[str]): list of identities to add to user
        """
        if not isinstance(identities, list):
            raise OAATemplateException("identities must be of type list")

        if self.identities is None:
            self.identities = []

        for identity in identities:
            try:
                self.identities.append(str(identity))
            except ValueError as e:
                raise OAATemplateException(f"identity could not be converted to string {identity}")

        return

    def add_group(self, group: str) -> None:
        """ Add user to local group (group must be created separately).

        Args:
            group (str): identifier of local group
        """

        group = str(group)
        if self.groups and group in self.groups:
            return
        else:
            self.groups = append_helper(self.groups, group)

        return

    def add_access_cred(self, access_cred: str) -> None:
        """Add access cred to user (access cred must be created separately)

        Args:
            access_cred (str): unique identifier of access cred
        """

        access_cred = str(access_cred)
        if access_cred in self.access_creds:
            return

        self.access_creds.append(access_cred)
        return

    def to_dict(self) -> dict:
        """ Output user to dictionary for payload. """

        user = {"name": self.name,
                "email": self.email,
                "identities": self.identities,
                "groups": self.groups,
                "access_creds": self.access_creds,
                "is_active": self.is_active,
                "created_at": self.created_at,
                "last_login_at": self.last_login_at,
                "deactivated_at": self.deactivated_at,
                "password_last_changed_at":  self.password_last_changed_at,
                "user_type": self.user_type,
                "tags": [tag.__dict__ for tag in self.tags],
                "custom_properties": self.properties
                }

        if self.unique_id:
            user['id'] = self.unique_id

        # filter out None/empty values before return
        return {k: v for k, v in user.items() if v not in [None, [], {}]}


class LocalGroup(Identity):
    """ LocalGroup identity.

    Derived from Identity base class. Used to represent groups of local users for application.

    Args:
        name (str): name of group
        identities (list): list of strings for IdP identity association
        unique_id (string, optional): Unique identifier for group

    Attributes:
        name (str): name of identity
        identities (list): list of strings for IdP identity association
        groups (list[LocalGroup]): list of group names as strings that group is member of for nested groups
        identity_type (OAAIdentityType): Veza Identity Type, local_group
        application_permissions (list[CustomPermission]): permissions identity has directly to custom application
        resource_permissions (dict): Dictionary of custom permissions associated with resources and sub-resources. Key is permission, value is list of resource keys
        application_roles (list[LocalRole]): list of roles identity has directly to custom application
        resource_roles (dict): Dictionary of local_roles for resources and sub-resources. Key is roles, value is list of resource keys
        properties (dict): Dictionary of properties for identity, allowed values will vary by identity type
        tags (list[Tag]): List of tags
        created_at (str): RFC3339 time stamp for group creation time
    """

    def __init__(self, name, identities=None, unique_id: str = None, property_definitions: ApplicationPropertyDefinitions = None):
        super().__init__(name, identity_type=OAAIdentityType.LocalGroup, unique_id=unique_id, property_definitions=property_definitions)
        self.identities = append_helper(None, identities)
        self.groups = []
        self.created_at = None

    def __str__(self) -> str:
        return f"Local Group - {self.name} ({self.unique_id})"

    def __repr__(self) -> str:
        return f"LocalGroup(name={self.name!r}, unique_id={self.unique_id!r}, identities={self.identities})"

    def add_group(self, group: str) -> None:
        """ Add a nested group to local group (group must be created separately).

        Args:
            group (str): identifier of local group
        """
        group = str(group)

        if (self.unique_id and self.unique_id == group) or (self.unique_id is None and self.name == group):
            raise OAATemplateException("Cannot add group to self")

        self.groups = append_helper(self.groups, group)

    def add_identity(self, identity: str) -> None:
        """ Add an identity to group.

        The email address or another valid identifier should match that of an IdP principal (Okta, Azure, ect).
        Veza will create a connection from the application local group to IdP identity.

        Args:
            identity (str): primary IdP identifier for group to associate
        """
        self.identities = append_helper(self.identities, identity)

    def to_dict(self) -> dict:
        """ Output group to dictionary for payload. """
        group = {"name": self.name,
                "identities": self.identities,
                "created_at": self.created_at,
                "groups": self.groups,
                "tags": [tag.__dict__ for tag in self.tags],
                "custom_properties": self.properties
                }
        if self.unique_id:
            group["id"] = self.unique_id

        # filter out None/empty values before return
        return {k: v for k, v in group.items() if v}

class IdPIdentity(Identity):
    """ IdP identity derived from Identity base class.

    Used to associate IdP identities (users or groups) directly to resource where concept of local users/groups doesn't apply to application.

    Args:
        name (str): Primary IdP identifier for identity (email, group name, etc)

    Attributes:
        name (str): name of identity
        identity_type (OAAIdentityType): Veza Identity Type, (idp)
        application_permissions (list[CustomPermission]): permissions identity has directly to custom application
        resource_permissions (dict): Dictionary of custom permissions associated with resources and sub-resources. Key is permission, value is list of resource keys
        application_roles (list[LocalRole]): roles identity has directly to custom application
        resource_roles (dict): Dictionary of local_roles for resources and sub-resources. Key is roles, value is list of resource keys
        properties (dict): Dictionary of properties for identity, allowed values will vary by identity type
        tags (list[Tag]): List of tags
    """

    def __init__(self, name: str) -> None:
        super().__init__(name, identity_type=OAAIdentityType.IdP)

    def __str__(self) -> str:
        return f"IdP Identity {self.name}"

    def __repr__(self) -> str:
        return f"IdPIdentity(name={self.name!r})"

    def set_property(self, property_name: str, property_value: any, ignore_none: bool = False) -> None:
        """ Set custom IdP property (no functionality).

        IdP identities do not support custom properties since the identity is discovered through the provider (Okta, Azure, etc)
        """
        raise OAATemplateException("IdP identities do not support custom properties")

class AccessCred(Identity):
    """Access Credential derived from Identity base class.

    Access Creds can be used to represent non-user based methods that grant access such as API keys or integrations.

    AccessCreds can be assigned roles or permissions to an application or resource. An AccessCred can stand-alone or be associated
    to a local user.

    Args:
        unique_id (str): Unique identifier for access cred
        name (str): Name for access cred, does not need to be unique

    Attributes:
        unique_id (str): Unique identifier for access cred
        name (str): Name for access cred, does not need to be unique
        is_active (bool): Indicate if credential is active, defaults to True
        created_at (str): Time access cred was created at as RFC3339 timestampe, defaults to empty
        expires_at (str): Time access cred was created at as RFC3339 timestampe, defaults to empty
        last_used_at (str): Time access cred was created at as RFC3339 timestampe, defaults to empty
        can_expire (bool): Boolean to indicate if credential type can exipre, defaults to unset

    """

    def __init__(self, unique_id: str, name: str, property_definitions: ApplicationPropertyDefinitions = None) -> None:
        if not unique_id:
            raise ValueError("Unique ID cannot be empty")
        if not name:
            raise ValueError("Name cannot be empty")

        super().__init__(name, identity_type=OAAIdentityType.AccessCred, unique_id=unique_id, property_definitions=property_definitions)

        self.is_active = True
        self.created_at = ""
        self.expires_at = ""
        self.last_used_at = ""
        self.can_expire: bool|None = None

        return

    def to_dict(self) -> dict:
        """ Output Access credential dictionary for payload """

        cred = {"id": self.unique_id,
                "name": self.name,
                "is_active": self.is_active,
                "created_at": self.created_at,
                "expires_at": self.expires_at,
                "last_used_at": self.last_used_at,
                "can_expire": self.can_expire,
                "tags": [tag.__dict__ for tag in self.tags],
                "custom_properties": self.properties
                }

        return {k: v for k, v in cred.items() if v not in [None, [], {}, ""]}

    def set_property(self, property_name: str, property_value: any, ignore_none: bool = False) -> None:
        """ Set a custom defined property to a specific value on an access credential.

        Property name must be defined for access credentials before calling `set_property()`. See example below
        and `ApplicationPropertyDefinitions.define_access_cred_property` for more information on defining properties.

        Args:
            property_name (str): Name of property to set value for
            property_value (Any): Value for property, type should match `OAAPropertyType` for property definition
            ignore_none (bool, optional): Do not set property if value is None. Defaults to False.

        Raises:
            OAATemplateException: If property with `property_name` is not defined.

        Example:

            >>> app = CustomApplication("App", application_type="example")
            >>> app.property_definitions.define_access_cred_property(name="my_property", property_type=OAAPropertyType.STRING)
            >>> cred1 = app.add_access_cred(unique_id="cred001", name="Cred 001")
            >>> cred1.set_property("my_property", "value for cred001")
        """

        if not self.property_definitions:
            raise OAATemplateException("No custom property definitions found for entity")

        if ignore_none and property_value is None:
            return

        self.property_definitions.validate_property_name(property_name, entity_type="access_cred")
        self.properties[property_name] = property_value


class LocalRole():
    """Represent a Custom Application Local Role.

    Local Roles are a collection of permissions (as `CustomPermission`).
    Roles can be used to associate a local user, group or IdP identity to an application, resource or sub-resource.

    Permissions can either be assigned at creation and/or added later.

    If the `CustomPermission` definition includes resource types in the `resource_types` list, the permission will
    only be assigned to resources/sub-resources that match that type as part of an assignment.

    Args:
        name (str): name of local role
        permissions (list[CustomPermission], optional): List of custom permission names (strings) to associate with the role. Defaults to empty list.
        unique_id (string, optional): Unique identifier for role for identification by ID
    Attributes:
        name (str): name of local role
        unique_id (str): Unique identifier for role for identification by ID
        permissions (list[CustomPermission]): list of custom permission names (strings) to associate with the role
        roles (list[LocalRole]): list of roles nested inside the role
        tags (list[Tag]): list of Tags instances
    """

    def __init__(self, name: str, permissions: List[str] = None, unique_id: str = None, property_definitions: ApplicationPropertyDefinitions = None) -> None:
        self.name = name
        if unique_id:
            self.unique_id = str(unique_id)
        else:
            self.unique_id = None

        if not permissions:
            self.permissions = []
        else:
            if not isinstance(permissions, list):
                raise OAATemplateException("permissions must be list")
            self.permissions = permissions


        self.property_definitions = property_definitions
        self.properties = {}
        self.roles = []
        self.tags = []

    def __str__(self) -> str:
        return f"Local Role - {self.name} ({self.unique_id})"

    def __repr__(self) -> str:
        return f"LocalRole(name={self.name!r}, permissions={self.permissions}, unique_id={self.unique_id!r})"

    def add_permissions(self, permissions: List[str]) -> None:
        """ Add a permission to the role.

        Args:
            permissions (list): List of permission names (strings) to add to role

        """
        if not isinstance(permissions, list):
            raise OAATemplateException("permissions must be list")

        if not all(isinstance(r, str) for r in permissions):
            raise OAATemplateException("permissions must be names of permissions as strings")

        self.permissions.extend(permissions)

    def add_role(self, role: str) -> None:
        """ Add a nested sub-role to the role (nested role must be created separately)

        Args:
            role (str): identifier of the local role to nest inside this role

        """
        role = str(role)

        if (self.unique_id and self.unique_id == role) or (self.unique_id is None and self.name == role):
            raise OAATemplateException("Cannot add role to self")

        self.roles = append_helper(self.roles, role)

    def add_tag(self, key: str, value: str = "") -> None:
        """ Add a new tag to role.

        Args:
            key (str): Key for tag, aka name. Must be present and must be letters, numbers or _ (underscore) only.
            value (str, optional): Value for Tag, will appear in Veza as `key:value`. Must be letters, numbers, whitespace and the special characters @,._- only. Defaults to "".
        """

        tag = Tag(key=key, value=value)
        if tag not in self.tags:
            self.tags.append(tag)

    def set_property(self, property_name: str, property_value: any, ignore_none: bool = False) -> None:
        """ Set the value for custom property on a local role.

        Property name must be defined for local roles before calling `set_property()`. See example below and
        `ApplicationPropertyDefinitions.define_local_role_property` for more information on defining properties.

        Args:
            property_name (str): Name of property to set value for
            property_value (Any): Value for property, type should match OAAPropertyType for property definition
            ignore_none (bool, optional): Do not set property if value is None. Defaults to False.

        Raises:
            OAATemplateException: If property name is not defined.

        Example:
            >>> app = CustomApplication("App", application_type="example")
            >>> app.property_definitions.define_local_role_property(name="my_property", property_type=OAAPropertyType.STRING)
            >>> role1 = app.add_local_role(name="role1")
            >>> role1.set_property(property_name="my_property", property_value="role1s value")

        """
        # validate property name is defined, validate_property_name will raise exception if not
        if not self.property_definitions:
            raise OAATemplateException(f"No custom properties defined, cannot set value for property {property_name}")

        if ignore_none and property_value is None:
            return

        self.property_definitions.validate_property_name(property_name, "local_role")
        self.properties[property_name] = property_value

        return

    def to_dict(self) -> dict:
        """ Convert role to dictionary for inclusion in JSON payload.

        Returns:
            dict: serializable dictionary of role

        """
        response = {}
        response['name'] = self.name
        response['permissions'] = unique_strs(self.permissions)
        response['roles'] = self.roles
        response['tags'] = [tag.__dict__ for tag in self.tags]
        response['custom_properties'] = self.properties
        if self.unique_id:
            response["id"] = self.unique_id

        return response


class CustomPermission():
    """CustomPermission class for defining `CustomApplication` permissions.

    - Custom permissions represent the named permissions for the application in its terms (e.g. "Admin" or "PUSH") and define the Veza canonical mapping (e.g. DataRead, MetadataRead, DataWrite).
    - A permission can either be applied directly to an application or resource or assigned as part of a role.
    - Optionally, when permissions are used as part of a role, if the `resource_types` list is populated the permission will only be applied to resources who's type is in the `resource_types` list when the role is applied to a resource.

    Args:
        name (str): Display name for permission
        permissions (list): List of OAAPermission enums that represent the canonical permissions
        apply_to_sub_resources (bool, optional): If true, when permission is applied to the application or resource, identity also has permission to all children of application/resource. Defaults to `False`.
        resource_types(list, optional): List of resource types as strings that the permission relates to. Defaults to empty list.

    Attributes:
        name (str): Display name for permission
        permissions (list[OAAPermission]): List of OAAPermission enums that represent the canonical permissions
        apply_to_sub_resources (bool): If true, when permission is applied to the application or resource, identity also has permission to all children of application/resource.
        resource_types (list): List of resource types as strings that the permission relates to.
    """

    def __init__(self, name: str, permissions: List[OAAPermission], apply_to_sub_resources: bool = False, resource_types: list = None) -> None:
        self.name = name
        self.permission_type = []
        self.apply_to_sub_resources = apply_to_sub_resources
        if resource_types:
            self.resource_types = resource_types
        else:
            self.resource_types = []
        self.__validate_permissions(permissions)

    def __str__(self) -> str:
        return f"Custom Permission {self.name} - {self.permission_type}"

    def __repr__(self) -> str:
        return f"CustomPermissions(name={self.name!r}, permissions={self.permission_type}, apply_to_sub_resources={self.apply_to_sub_resources})"

    def to_dict(self) -> dict:
        """ Returns dictionary representation for payload. """
        return {"name": self.name,
                "permission_type": self.permission_type,
                "apply_to_sub_resources": self.apply_to_sub_resources,
                "resource_types": self.resource_types
                }

    def add_resource_type(self, resource_type: str) -> None:
        """Add a resource type to the resource_types list.

        Extends the list of resource types permission applies to when used in role assignment.

        Args:
            resource_type (str): The resource type string value
        """

        if resource_type not in self.resource_types:
            self.resource_types.append(resource_type)

    def __validate_permissions(self, permissions: List[OAAPermission]) -> None:
        """Validate permissions are OAAPermission type.

        Args:
            permissions (list): List of entities to validate are of type OAAPermission

        Raises:
            OAATemplateException
        """
        if permissions is None:
            return True

        validated_permissions = []
        if isinstance(permissions, list):
            for p in permissions:
                if isinstance(p, OAAPermission):
                    validated_permissions.append(p)
                    continue
                else:
                    raise OAATemplateException("Custom permissions must be OAAPermission enum")
        elif isinstance(permissions, OAAPermission):
            validated_permissions.append(permissions)
        else:
            raise OAATemplateException("Custom permissions must be OAAPermission enum")

        self.permission_type = validated_permissions


###############################################################################
# Custom properties related classes
###############################################################################
class OAAPropertyType(str, Enum):
    """ Supported types for custom properties on OAA entities such as application, resource, and identity.  """

    BOOLEAN = "BOOLEAN"                 # True/False boolean
    NUMBER = "NUMBER"                   # integer number
    STRING = "STRING"                   # string
    STRING_LIST = "STRING_LIST"         # list of strings
    TIMESTAMP = "TIMESTAMP"             # RFC3339 formatted time stamp 2022-02-08T13:10:50.25Z


class ApplicationPropertyDefinitions():
    """
    Model for defining custom properties for application and its entities (users, groups, roles, resources).

    Property definitions define the names for additional entity properties and the expected type.

    Args:
        application_type (str): type of custom application property definitions apply to

    Attributes:
        application_properties (dict): property definitions for application
        local_user_properties (dict): property definitions for local users
        local_group_properties (dict): property definitions for local groups
        local_role_properties (dict): property definitions for local roles
        resources (dict): property definitions for resources keyed by resource type
    """

    def __init__(self, application_type: str) -> None:
        self.application_type = application_type
        self.application_properties = {}
        self.local_user_properties = {}
        self.local_group_properties = {}
        self.local_role_properties = {}
        self.role_assignment_properties = {}
        self.access_cred_properties = {}
        self.resource_properties = {}

    def __str__(self) -> str:
        return f"ApplicationPropertyDefinitions for {self.application_type}"

    def __repr__(self) -> str:
        return f"ApplicationPropertyDefinitions(application_type={self.application_type!r})"

    def to_dict(self) -> dict:
        """ Return property definitions as dictionary ready for OAA payload """
        definitions = {
            "application_type": self.application_type,
            "application_properties": self.application_properties,
            "local_user_properties": self.local_user_properties,
            "local_group_properties": self.local_group_properties,
            "local_role_properties": self.local_role_properties,
            "role_assignment_properties": self.role_assignment_properties,
            "local_access_creds_properties": self.access_cred_properties,
            "resources": list(self.resource_properties.values())
        }

        definitions["resources"] = []
        for resource_type in self.resource_properties:
            if self.resource_properties[resource_type]:
                definitions["resources"].append({"resource_type": resource_type, "properties": self.resource_properties[resource_type]})

        return {k: v for k, v in definitions.items() if v}

    def define_application_property(self, name: str, property_type: OAAPropertyType) -> None:
        """ Define an application property.

        Args:
            name (str): name for property
            property_type (OAAPropertyType): type for property

        """
        self.validate_name(name)
        self._validate_types(name, property_type)
        self.application_properties[name] = property_type

    def define_local_user_property(self, name: str, property_type: OAAPropertyType) -> None:
        """ Define a local user property.

        Args:
            name (str): name for property
            property_type (OAAPropertyType): type for property

        """
        self.validate_name(name)
        self._validate_types(name, property_type)
        self.local_user_properties[name] = property_type

    def define_local_group_property(self, name: str, property_type: OAAPropertyType) -> None:
        """ Define a local group property.

        Args:
            name (str): name for property
            property_type (OAAPropertyType): type for property

        """
        self.validate_name(name)
        self._validate_types(name, property_type)
        self.local_group_properties[name] = property_type

    def define_local_role_property(self, name: str, property_type: OAAPropertyType) -> None:
        """ Define a local role property.

        Args:
            name (str): name for property
            property_type (OAAPropertyType): type for property

        """
        self.validate_name(name)
        self._validate_types(name, property_type)
        self.local_role_properties[name] = property_type

    def define_role_assignment_property(self, name: str, property_type: OAAPropertyType) -> None:

        if name in self.local_role_properties:
            raise OAATemplateException(f"Role assignment property names must be unique to role properties, name {name}")

        self.validate_name(name)
        self._validate_types(name, property_type)
        self.role_assignment_properties[name] = property_type

    def define_access_cred_property(self, name: str, property_type: OAAPropertyType) -> None:
        """ Define an access cred property.

        Args:
            name (str): name for property
            property_type (OAAPropertyType): type for property

        """
        self.validate_name(name)
        self._validate_types(name, property_type)
        self.access_cred_properties[name] = property_type

    def define_resource_property(self, resource_type: str, name: str, property_type: OAAPropertyType) -> None:
        """ Define a property for a resource by type of resource.

        Args:
            resource_type (str): type of resource property definition is for
            name (str): property name
            property_type (OAAPropertyType): type for property

        """
        self.validate_name(name)
        self._validate_types(name, property_type)
        if resource_type not in self.resource_properties:
            self.resource_properties[resource_type] = {name: property_type}
        else:
            self.resource_properties[resource_type][name] = property_type

    def validate_property_name(self, property_name: str, entity_type: str, resource_type: str = None) -> bool:
        """ Validate that a property name has been defined for given resource type.

        Args:
            property_name (str): name of property to validate
            entity_type (str): type of entity custom property is for (application, local_user, local_group, local_role, resource)
            resource_type (str): (optional) type for validating resource property names, only applicable to entity_type resource

        Raises:
            OAATemplateException: If property name has not been previously defined for entity

        """
        valid_property_names = []
        if entity_type == "application":
            valid_property_names = self.application_properties.keys()
        elif entity_type == "local_user":
            valid_property_names = self.local_user_properties.keys()
        elif entity_type == "local_group":
            valid_property_names = self.local_group_properties.keys()
        elif entity_type == "local_role":
            valid_property_names = self.local_role_properties.keys()
        elif entity_type == "role_assignment":
            valid_property_names = self.role_assignment_properties.keys()
        elif entity_type == "access_cred":
            valid_property_names = self.access_cred_properties.keys()
        elif entity_type == "resource":
            try:
                valid_property_names = self.resource_properties[resource_type].keys()
            except KeyError:
                raise OAATemplateException(f"No custom properties defined for resource type {resource_type}")
        else:
            raise OAATemplateException(f"Unknown entity type '{entity_type}', cannot validate property names")

        # validate against names as all lowercase
        valid_property_names = [i.lower() for i in valid_property_names]

        if property_name.lower() in valid_property_names:
            return True
        else:
            raise OAATemplateException(f"unknown property name {property_name}")

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
            raise OAATemplateException("Property name must be a string")

        if not re.match(PROPERTY_NAME_REGEX, name.lower()):
            raise OAATemplateException(f"Lower-cased property name must match the pattern: '{PROPERTY_NAME_REGEX}': {name}")

        return


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


class IdPProviderType(str, Enum):
    """ Veza supported IdP provider types. """

    ACTIVE_DIRECTORY = "active_directory"
    ANY = "any"
    AZURE_AD = "azure_ad"
    CUSTOM = "custom"
    GOOGLE_WORKSPACE = "google_workspace"
    OKTA = "okta"
    ONE_LOGIN = "one_login"


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

        group['tags'] = [tag.__dict__ for tag in self._tags]
        group['custom_properties'] = self._properties
        group['app_assignments'] = [r for r in self._app_assignments.values()]

        return {k: v for k, v in group.items() if v not in [None, [], {}]}

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


###############################################################################
# Human Resource Information Systems (HRIS)
###############################################################################

class HRISProvider():
    """Class for modeling Human Resource Information Systems (HRIS) Template

    HRIS template consists of base information about the HRIS instance, Employees and Groups.

    Employees and Groups are tracked in case insensitive dictionaries that can be used to reference entities after creation.

    Args:
        name (str): Name for HRIS Instance
        hris_type (str): Type for HRIS. Typically the vendor or product name.
        url (str): Instance URL for HRIS.

    Attributes:
        employees (dict[string]): Dictionary of HRISEmployee instances keyed by Employee ID
        groups (dict[string]): Dictionary of HRISGroup instances keyed by Group ID
    """

    TEMPLATE = "hris"

    def __init__(self, name: str, hris_type: str, url: str):
        self.name = name

        # TODO: validate HRIS type against supported characters
        self.hris_type = hris_type

        self.system = HRISSystem(name, url=url)

        self.employees = CaseInsensitiveDict()
        self.groups = CaseInsensitiveDict()

        self.property_definitions = HRISPropertyDefinitions()

    def __str__(self) -> str:
        return f"HRISProvider {self.name} - {self.hris_type}"

    def __repr__(self) -> str:
        return f"HRISProvider(name={self.name!r}, hris_type={self.hris_type!r}, url={self.system.url!r})"

    def get_payload(self) -> dict:
        """Get the OAA payload.

        Returns the complete OAA template payload for HRIS as serializable dictionary

        Returns:
            dict: OAA payload as dictionary
        """

        payload = {"name": self.name,
                    "hris_type": self.hris_type,
                    "custom_property_definition": self.property_definitions.to_dict(),
                    "system": self.system.to_dict(),
                    "employees": [employee.to_dict() for employee in self.employees.values()],
                    "groups": [group.to_dict() for group in self.groups.values()]
                  }

        return payload

    def add_employee(self, unique_id: str, name: str, employee_number: str, first_name: str, last_name: str, is_active: bool, employment_status: str) -> HRISEmployee:
        """Add a new Employee

        Function creates a new HRISEmployee instance and adds it to the `HRISProvider.employees` keyed by the `unique_id`

        Args:
            unique_id (str): Unique Identifier for Employee
            name (str): Display name for employee
            employee_number (str): The employee's number that appears in the third-party integration.
            first_name (str): Employee first name
            last_name (str): Employee last name (family name)
            is_active (bool): Boolean for employee active status
            employment_status (str): String representation of employee status, e.g. "ACTIVE", "TERMINATE", "PENDING"

        Raises:
            OAATemplateException: Employee with ID already exists

        Returns:
            HRISEmployee: Entity for new employee
        """

        if unique_id in self.employees:
            raise OAATemplateException(f"Employee with unique ID already exists, {unique_id}")

        self.employees[unique_id] = HRISEmployee(unique_id=unique_id,
                                                    name=name,
                                                    employee_number=employee_number,
                                                    first_name=first_name,
                                                    last_name=last_name,
                                                    is_active=is_active,
                                                    employment_status=employment_status
                                                )

        self.employees[unique_id]._property_definitions = self.property_definitions.employee_properties

        return self.employees[unique_id]

    def add_group(self, unique_id: str, name: str, group_type: str) -> HRISGroup:
        """Add a new Group

        Used to represent any subset of employees, such as PayGroup or Team. Employees can be in multiple Groups. Groups can also
        be members of other groups to create hierarchy.

        Some properties of HRISEmployee such as `department` must reference an existing HRISGroup by its ID.

        Args:
            unique_id (str): Unique ID for group
            name (str): Display name
            group_type (str): Type for group such as "Team", "Department", "Cost Center"

        Returns:
            HRISGroup: Entity for new group
        """
        if unique_id in self.groups:
            raise OAATemplateException(f"Group with unique ID already exists, {unique_id}")

        self.groups[unique_id] = HRISGroup(unique_id=unique_id, name=name, group_type=group_type)
        self.groups[unique_id]._property_definitions = self.property_definitions.group_properties

        return self.groups[unique_id]


class HRISSystem():
    """HRISSystem information

    Representation for HRISSystem information. The system information is used to represent additional details
    for the HRIS Instance.

    Args:
        name (str): Name for system Instance
        url (str, optional): URL for instance . Defaults to "". TODO: Is this right?
    """

    def __init__(self, name: str, url: str = ""):


        self.name = name
        self.unique_id = name
        self.url = url
        self.idp_providers = []


    def __str__(self) -> str:
        return f"HRISSystem - {self.name}"

    def __repr__(self) -> str:
        return f"HRISSystem(name={self.name!r}, url={self.url!r})"

    def to_dict(self) -> dict:
        payload = {"id": self.unique_id,
                   "name": self.name,
                   "url": self.url,
                   "idp_providers": self.idp_providers
                  }

        return payload

    def add_idp_type(self, provider_type: IdPProviderType) -> list[IdPProviderType]:
        """Link HRIS to External IdP of given type

        Sets the IdP types (Okta, AzureAD, ect) for Veza to link employee identities too.

        Args:
            provider_type (IdPProviderType): Type of IdP for source identities

        Raises:
            ValueError: provider_type must be IdPProviderType enum

        Returns:
            list[IdPProviderType]: List of configured IdP types
        """

        if not isinstance(provider_type, IdPProviderType):
            raise ValueError(f"provider_type must be of type IdPProviderType enum, received {type(provider_type)}")

        if provider_type not in self.idp_providers:
            self.idp_providers.append(provider_type)

        return self.idp_providers

class HRISEmployee():
    """HRIS Employee Entity

    Represents an employee record in the HRIS system. Each employee must have a unique ID to identify it in the payload. This ID
    is also used to reference one employee to the other for manager hierarchy.

    Init variables are all required and must not be empty such as `""`

    Args:
        unique_id (str): Unique Identifier for Employee
        name (str): Name for employee record.
        employee_number (str): The employee's number that appears in the third-party integration.
        first_name (str): Employee first name
        last_name (str): Employee last name (family name)
        is_active (bool): Boolean for employee active status
        employment_status (str): String representation of employee status, e.g. "ACTIVE", "TERMINATE", "PENDING"

    Parameters:
        company (str): The company (or subsidiary) the employee works for.
        preferred_name (str): The employee's preferred first name.
        display_full_name (str): The employee's full name, to use for display purposes.
        canonical_name (str): The employee's canonical name.
        username (str): The employee's username that appears in the integration UI.
        email (str): The employee's work email.
        idpid (str): The ID for this employee on the destination IDP provider used to automatically connect to it, if not supplied email is used.
        personal_email (str): The employee's personal email.
        home_location (str): The employee's home location.
        work_location (str): The employee's work location.
        cost_center (str): The cost center ID (Group ID) that the employee is in.
        department (str): The department ID (Group ID) that the employee is in.
        managers (str): The employee IDs of the employee's managers.
        groups (str): The IDs of groups this user is in
        start_date (str): The date that the employee started working. RFC3339 timestamp.
        termination_date (str): The employee's termination date. RFC3339 timestamp.
        job_title (str): The title of the employee.
        employment_typ (str): The employee's type of employment. For example: FULL_TIME, PART_TIME, INTERN, CONTRACTOR, FREELANCE.
        primary_time_zone (str): The time zone which the employee primarily lives.

    Raises:
        ValueError: Any of the required arguments are empty.

    """
    def __init__(self, unique_id: str, name: str, employee_number: str, first_name: str, last_name: str, is_active: bool, employment_status: str):


        # required values
        if not unique_id:
            raise ValueError("unique_id cannot be empty")
        if not name:
            raise ValueError("name cannot be empty")
        if not employee_number:
            raise ValueError("employee_number cannot be empty")
        if not first_name:
            raise ValueError("first_name cannot be empty")
        if not last_name:
            raise ValueError("last_name cannot be empty")
        if not employment_status:
            raise ValueError("employment_status cannot be empty")
        if not isinstance(is_active, bool):
            raise ValueError("is_active must be boolean type")

        self.unique_id: str = unique_id
        self.name: str = name
        self.employee_number: str = employee_number
        self.first_name: str = first_name
        self.last_name: str = last_name
        self.employment_status: str = employment_status
        self.is_active: bool = is_active

        # optional parameters
        self.company: str = ""
        self.preferred_name: str = ""
        self.display_full_name: str = ""
        self.canonical_name: str = ""
        self.username: str = ""
        self.email: str = ""
        self.idp_id: str = ""
        self.personal_email: str = ""
        self.home_location: str = ""
        self.work_location: str = ""
        self.cost_center: str = ""
        self.department: str = ""
        self.managers = []
        self.groups = []
        self.start_date: str = ""
        self.termination_date: str = ""
        self.job_title: str = ""
        self.employment_types = []
        self.primary_time_zone: str = ""

        self._property_definitions = None
        self.custom_properties: dict = {}

    def __str__(self) -> str:
        return f"HRISEmployee - {self.name} ({self.unique_id})"

    def __repr__(self) -> str:
        return f"HRISEmployee(unique_id: {self.unique_id!r}, name: {self.name!r}, employee_number: {self.employee_number!r}, first_name: {self.first_name!r}, last_name: {self.last_name!r}, is_active: {self.is_active!r}, employment_status: {self.employment_status!r})"

    def add_group(self, group_id: str) -> None:
        """Add employee to group

        Adds employee to a group by the group ID. Group must also be defined for HRISInstance with `HRISProvider.add_group()`

        Args:
            group_id (str): Unique ID of HRISGroup to add employee too
        """

        if group_id not in self.groups:
            self.groups.append(group_id)

        return

    def add_manager(self, manager_id: str) -> None:
        """Add manager to Employee

        Adds a manager to the employee by the manager's HRISEmployee instance unique ID. Manger employee record must also exist.

        Args:
            manager_id (str): Unique ID for manager HRISEmployee instance
        """

        if manager_id not in self.managers:
            self.managers.append(manager_id)

        return

    def set_property(self, property_name: str, property_value: any, ignore_none: bool = False) -> None:
        """Set Employee custom property value

        Property name must be defined for employee before calling `set_property`

        Args:
            property_name (str): Name of property
            property_value (any): Value for property, type should match OAAPropertyType for property definition
            ignore_none (bool, optional): Do not set property if value is None. Defaults to False.. Defaults to False.

        Raises:
            OAATemplateException: If property with `property_name` is not defined.
        """

        if self._property_definitions is not None:
            if not isinstance(self._property_definitions, CaseInsensitiveDict):
                raise OAATemplateException("employee property_definitions not of expected type")

            if property_name not in self._property_definitions:
                raise OAATemplateException(f"unknown employee property name {property_name}")
        else:
            log.warning("Employee does not have property names set, cannot validate property name")

        if ignore_none and property_value is None:
            return

        self.custom_properties[property_name] = property_value

        return

    def to_dict(self) -> dict:
        """ Output employee to dictionary for payload. """

        user = {"id": self.unique_id,
                "name": self.name,
                "employee_number": self.employee_number,
                "company": self.company,
                "first_name": self.first_name,
                "last_name": self.last_name,
                "preferred_name": self.preferred_name,
                "display_full_name": self.display_full_name,
                "canonical_name": self.canonical_name,
                "username": self.username,
                "email": self.email,
                "idp_id": self.idp_id,
                "personal_email": self.personal_email,
                "home_location": self.home_location,
                "work_location": self.work_location,
                "employment_status": self.employment_status,
                "start_date": self.start_date,
                "termination_date": self.termination_date,
                "job_title": self.job_title,
                "employment_types": self.employment_types,
                "primary_time_zone": self.primary_time_zone,
                "custom_properties": self.custom_properties
                }

        if isinstance(self.is_active, bool):
            user["is_active"] = self.is_active

        # entities that need reference by ID
        user["groups"] = [{"id": group_id} for group_id in self.groups]
        user["managers"] = [{"id": manager_id} for manager_id in self.managers]
        if self.department:
            user["department"] = {"id": self.department}
        if self.cost_center:
            user["cost_center"] = {"id": self.cost_center}

        # filter out None/empty values before return
        return {k: v for k, v in user.items() if v not in [None, [], {}, ""]}


class HRISGroup():
    """HRIS Group

    Represents any group of employees in the HRIS system. HRISGroups can be used to represent teams, departments, cost centers
    or any organizational unit. Each group has a type to make searching and grouping easier.

    Group's Unique ID must be unique across all group types.

    Args:
        unique_id (str): Unique ID for group
        name (str): Display name
        group_type (str): Type for group such as "Team", "Department", "Cost Center"
    """

    def __init__(self, unique_id: str, name: str, group_type: str):


        self.unique_id = unique_id
        self.name = name
        self.group_type = group_type

        self._property_definitions = None
        self.custom_properties = {}

    def __str__(self) -> str:
        return f"HRISGroup - {self.name} ({self.unique_id}) - {self.group_type}"

    def __repr__(self) -> str:
        return f"HRISGroup(unique_id={self.unique_id!r}, name={self.name!r}, group_type={self.group_type!r})"

    def set_property(self, property_name: str, property_value: any, ignore_none: bool = False) -> None:
        """Set HRIS Group custom property value

        Property name must be defined for group before calling `set_property`

        Args:
            property_name (str): Name of property
            property_value (any): Value for property, type should match OAAPropertyType for property definition
            ignore_none (bool, optional): Do not set property if value is None. Defaults to False.. Defaults to False.

        Raises:
            OAATemplateException: If property with `property_name` is not defined.
        """

        if self._property_definitions is not None:
            if not isinstance(self._property_definitions, CaseInsensitiveDict):
                raise OAATemplateException("group property_definitions not of expected type")

            if property_name not in self._property_definitions:
                raise OAATemplateException(f"unknown group property name {property_name}")
        else:
            log.warning("Group does not have property names set, cannot validate property name")

        if ignore_none and property_value is None:
            return

        self.custom_properties[property_name] = property_value

        return

    def to_dict(self) -> dict:
        """Dictionary output for inclusion in payload"""

        group = {"id": self.unique_id,
                 "name": self.name,
                 "group_type": self.group_type,
                 "custom_properties": self.custom_properties
                }
        return {k: v for k, v in group.items() if v not in [None, [], {}]}

class HRISPropertyDefinitions():

    def __init__(self):

        self.system_properties = CaseInsensitiveDict()
        self.employee_properties = CaseInsensitiveDict()
        self.group_properties = CaseInsensitiveDict()

    def to_dict(self) -> dict:

        definitions = {
            "system_properties": {k:v for k,v in self.system_properties.items()},
            "employee_properties": {k:v for k,v in self.employee_properties.items()},
            "group_properties": {k:v for k,v in self.group_properties.items()}
        }

        return definitions

    def define_system_property(self, name: str, property_type: OAAPropertyType) -> None:
        self.validate_name(name)
        self._validate_types(name, property_type)
        self.system_properties[name] = property_type

    def define_employee_property(self, name: str, property_type: OAAPropertyType) -> None:
        self.validate_name(name)
        self._validate_types(name, property_type)
        self.employee_properties[name] = property_type

    def define_group_property(self, name: str, property_type: OAAPropertyType) -> None:
        self.validate_name(name)
        self._validate_types(name, property_type)
        self.group_properties[name] = property_type

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