"""
Classes for constructing an OAA JSON payload for the Host template

Copyright 2026 Veza Technologies Inc.

Use of this source code is governed by the MIT
license that can be found in the LICENSE file or at
https://opensource.org/licenses/MIT.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import List, Optional

from .application import OAAPermission
from .common import PROPERTY_NAME_REGEX, CaseInsensitiveDict, IdPProviderType, OAAPropertyType
from .exceptions import OAATemplateException

###############################################################################
# Host
###############################################################################

class HostGranteeType(str, Enum):
    """ Whether a HostGrant's principal is a user or a group. """
    USER = "user"
    GROUP = "group"

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}.{self.name}'


class HostIdentityType(str, Enum):
    """ Whether a HostUser stands for a person or not. """
    HUMAN = "human"
    NONHUMAN = "nonhuman"

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}.{self.name}'


class HostProvider():
    """Class for modeling host machine authorization using the OAA Host template.

    A Host provider supports two collection models, distinguished by shape rather than a mode
    flag. A central collector with visibility of the whole fleet calls `add_environment()` once
    and `add_host()` for every host in the fleet. An agent running on one host has no view of the
    fleet, so it calls `add_host(environment_id=...)` for its own host alone and does not call
    `add_environment()`.

    What distinguishes the two is where the environment comes from, not how many hosts are
    submitted. A submission that carries an environment of its own and also sets `environment_id`
    on a host, or that does neither, is rejected by the server as ambiguous.

    Args:
        host_type (str): Type descriptor for the fleet, typically the platform or vendor name

    Attributes:
        host_type (str): Type for the fleet
        environment (HostEnvironment): The fleet's environment, set by `add_environment()`. None for a per-host agent submission.
        hosts (dict[HostNode]): Dictionary of HostNode instances
        privileges (dict[HostPrivilegeDefinition]): Dictionary of privilege definitions, referenced by name from grants
        property_definitions (HostPropertyDefinitions): Custom property names and types for the fleet
    """

    TEMPLATE = "host"

    def __init__(self, host_type: str) -> None:
        self.host_type = host_type

        self.environment: Optional[HostEnvironment] = None
        self.hosts = CaseInsensitiveDict()
        self.privileges = CaseInsensitiveDict()

        self.property_definitions = HostPropertyDefinitions()

    def __str__(self) -> str:
        return f"Host Provider - {self.host_type}"

    def __repr__(self) -> str:
        return f"HostProvider(host_type={self.host_type!r})"

    def get_payload(self) -> dict:
        """Get the OAA payload.

        Returns the complete OAA template payload for the host fleet as serializable dictionary

        Returns:
            dict: OAA payload as dictionary
        """

        payload = {"host_type": self.host_type,
                   "custom_property_definition": self.property_definitions.to_dict(),
                   "privileges": [privilege.to_dict() for privilege in self.privileges.values()],
                   "hosts": [host.to_dict() for host in self.hosts.values()]
                  }

        if self.environment is not None:
            payload["environment"] = self.environment.to_dict()

        return payload

    def add_environment(self, unique_id: str, name: str, description: str = None, identity_provider_types: List[str] = None) -> HostEnvironment:
        """Add the fleet's environment.

        Only used by a central collector that has visibility of the whole fleet. A per-host agent
        submission names its environment with `add_host(environment_id=...)` instead and must not
        call this method.

        Args:
            unique_id (str): Unique ID for the environment. Required.
            name (str): Display name for the environment. Required.
            description (str, optional): Description for the environment. Defaults to None.
            identity_provider_types (list[str], optional): Which kinds of identity provider may be searched when resolving the identities this submission refers to. Values must be one of `IdPProviderType`. Absent or empty means all of them. Defaults to None.

        Raises:
            OAATemplateException: If an environment has already been added to this submission.

        Returns:
            HostEnvironment
        """

        if self.environment is not None:
            raise OAATemplateException("Environment already defined for this submission")

        self.environment = HostEnvironment(unique_id=unique_id, name=name, description=description, identity_provider_types=identity_provider_types)

        return self.environment

    def add_host(self, name: str, unique_id: str, environment_id: str = None) -> HostNode:
        """Add a new Host.

        Hosts can be referenced after creation using the `.hosts` dictionary attribute, keyed case
        insensitively by `unique_id`.

        Args:
            name (str): Display name for host. Required.
            unique_id (str): Unique identifier for host for reference by ID. Required.
            environment_id (str, optional): ID of the Environment this host belongs to. Required when this submission carries no environment of its own (a per-host agent submission); must be absent when `add_environment()` has been called on this provider. Defaults to None.

        Raises:
            OAATemplateException: name or unique_id is empty, or host is already defined.

        Returns:
            HostNode
        """

        if not name:
            raise OAATemplateException("Host must have a name")
        if not unique_id:
            raise OAATemplateException("Host must have a unique_id")

        if unique_id in self.hosts:
            raise OAATemplateException(f"Host identified by {unique_id} already defined")

        self.hosts[unique_id] = HostNode(name=name, unique_id=unique_id, environment_id=environment_id, property_definitions=self.property_definitions)

        return self.hosts[unique_id]

    def add_privilege(self, name: str, privilege_type: List[OAAPermission], description: str = None) -> HostPrivilegeDefinition:
        """Add a new privilege definition.

        Privileges are defined once on the fleet and referenced by name wherever they are granted
        via `HostNode.add_grant()`.

        Args:
            name (str): Name grants refer to
            privilege_type (list[OAAPermission]): Canonical access types this privilege confers
            description (str, optional): Description for privilege. Defaults to None.

        Raises:
            OAATemplateException: name is empty, or privilege with name already exists.

        Returns:
            HostPrivilegeDefinition
        """

        if not name:
            raise OAATemplateException("Privilege must have a name")

        if name in self.privileges:
            raise OAATemplateException(f"Privilege {name} already defined")

        self.privileges[name] = HostPrivilegeDefinition(name=name, privilege_type=privilege_type, description=description)

        return self.privileges[name]


class HostEnvironment():
    """Environment for a Host fleet.

    Represents the fleet-wide information for a Host submission. Created by `HostProvider.add_environment()`.

    Args:
        unique_id (str): Unique ID for the environment. Required.
        name (str): Display name for the environment. Required.
        description (str, optional): Description for the environment. Defaults to None.
        identity_provider_types (list[str], optional): Which kinds of identity provider may be searched when resolving identities this submission refers to. Values must be one of `IdPProviderType`. Defaults to None.

    Raises:
        ValueError: unique_id or name is empty.
        OAATemplateException: An identity_provider_types value is not a known IdP kind.
    """

    def __init__(self, unique_id: str, name: str, description: str = None, identity_provider_types: List[str] = None) -> None:
        if not unique_id:
            raise ValueError("unique_id cannot be empty")
        if not name:
            raise ValueError("name cannot be empty")

        self.unique_id = unique_id
        self.name = name
        self.description = description

        if identity_provider_types:
            known_types = {t.value for t in IdPProviderType}
            for idp_type in identity_provider_types:
                if idp_type not in known_types:
                    raise OAATemplateException(f"Unknown identity provider type {idp_type}, must be one of {known_types}")
            self.identity_provider_types = list(identity_provider_types)
        else:
            self.identity_provider_types = []

    def __str__(self) -> str:
        return f"Host Environment - {self.name} ({self.unique_id})"

    def __repr__(self) -> str:
        return f"HostEnvironment(unique_id={self.unique_id!r}, name={self.name!r})"

    def to_dict(self) -> dict:
        """ Output function for payload. """

        environment = {"id": self.unique_id,
                       "name": self.name,
                       "description": self.description,
                       "identity_provider_types": self.identity_provider_types
                      }

        return {k: v for k, v in environment.items() if v not in [None, [], {}, ""]}


class HostNode():
    """A single host machine.

    Contains the host's own users, groups, credentials, resources and grants. Created by
    `HostProvider.add_host()`.

    Args:
        name (str): Display name for host. Required.
        unique_id (str): Unique identifier for host. Required.
        environment_id (str, optional): ID of the Environment this host belongs to. Required for a per-host agent submission, which carries no environment of its own; must be absent when the submission carries an environment. Defaults to None.
        property_definitions (HostPropertyDefinitions, optional): Property definitions structure for the fleet. Defaults to None.

    Attributes:
        platform (str): Host platform, e.g. "linux". None until set.
        version (str): Host platform version, e.g. "Ubuntu 22.04.4 LTS". None until set.
        ip_address (str): Host IP address. None until set.
        users (dict[HostUser]): Dictionary of HostUser instances
        groups (dict[HostGroup]): Dictionary of HostGroup instances
        credentials (dict[HostCredential]): Dictionary of HostCredential instances
        resources (dict[HostResource]): Dictionary of HostResource instances, keyed by `resource_type.id`
        identity_to_privileges (dict): Dictionary of grants, keyed by principal ID

    Raises:
        ValueError: name or unique_id is empty.
    """

    def __init__(self, name: str, unique_id: str, environment_id: str = None, property_definitions: HostPropertyDefinitions = None) -> None:
        if not name:
            raise ValueError("name cannot be empty")
        if not unique_id:
            raise ValueError("unique_id cannot be empty")

        self.name = name
        self.unique_id = unique_id

        self.platform = None
        self.version = None
        self.ip_address = None
        self.environment_id = environment_id

        self.users = CaseInsensitiveDict()
        self.groups = CaseInsensitiveDict()
        self.credentials = CaseInsensitiveDict()
        self.resources = CaseInsensitiveDict()
        self.identity_to_privileges = CaseInsensitiveDict()

        self._property_definitions = property_definitions
        self.custom_properties = {}

    def __str__(self) -> str:
        return f"Host - {self.name} ({self.unique_id})"

    def __repr__(self) -> str:
        return f"HostNode(name={self.name!r}, unique_id={self.unique_id!r}, environment_id={self.environment_id!r})"

    def to_dict(self) -> dict:
        """ Output function for payload. """

        host = {"id": self.unique_id,
                "name": self.name,
                "platform": self.platform,
                "version": self.version,
                "ip_address": self.ip_address,
                "environment_id": self.environment_id,
                "custom_properties": self.custom_properties,
                "users": [user.to_dict() for user in self.users.values()],
                "groups": [group.to_dict() for group in self.groups.values()],
                "credentials": [credential.to_dict() for credential in self.credentials.values()],
                "resources": [resource.to_dict() for resource in self.resources.values()],
                "identity_to_privileges": [{k: v for k, v in grant.items() if v not in [None, [], {}, ""]} for grant in self.identity_to_privileges.values()]
               }

        return {k: v for k, v in host.items() if v not in [None, [], {}, ""]}

    def set_property(self, property_name: str, property_value: any, ignore_none: bool = False) -> None:
        """Set a custom property value for the host.

        Property name must be defined for the fleet before calling `set_property`. See
        `HostPropertyDefinitions.define_host_property` for more information.

        Args:
            property_name (str): Name of property to set value for
            property_value (Any): Value for property, type should match OAAPropertyType for property definition
            ignore_none (bool, optional): Do not set property if value is None. Defaults to False.

        Raises:
            OAATemplateException: If property name is not defined.
        """

        if not self._property_definitions:
            raise OAATemplateException(f"No custom properties defined, cannot set value for property {property_name}")

        if ignore_none and property_value is None:
            return

        if property_name not in self._property_definitions.host_properties:
            raise OAATemplateException(f"unknown host property name {property_name}")

        self.custom_properties[property_name] = property_value

    def add_user(self, name: str, unique_id: str, identities: List[str] = None, is_local: bool = True, identity_type: HostIdentityType = None, is_active: bool = None, last_login_at: str = None) -> HostUser:
        """Add a new user account to this host.

        A user belongs to exactly one host: root on two hosts is two accounts, each added
        separately.

        Args:
            name (str): Display name for user. Required.
            unique_id (str): Unique identifier for user. Required.
            identities (list[str], optional): The identities in an identity provider this account belongs to. Required when `is_local` is False. Defaults to None.
            is_local (bool, optional): True for an account configured on the host itself. False for a network user granted access without a local account. Defaults to True.
            identity_type (HostIdentityType, optional): Whether this account stands for a person. Absent means human. Defaults to None.
            is_active (bool, optional): Defaults to None.
            last_login_at (str, optional): RFC3339 timestamp of the account's last login to this host. Defaults to None.

        Raises:
            OAATemplateException: name or unique_id is empty, user already defined, or identity_type is not a HostIdentityType.

        Returns:
            HostUser
        """

        if not name:
            raise OAATemplateException("User must have a name")
        if not unique_id:
            raise OAATemplateException("User must have a unique_id")

        if unique_id in self.users:
            raise OAATemplateException(f"User identified by {unique_id} already defined")

        property_definitions = self._property_definitions.user_properties if self._property_definitions else None
        self.users[unique_id] = HostUser(name=name, unique_id=unique_id, identities=identities, is_local=is_local, identity_type=identity_type, is_active=is_active, last_login_at=last_login_at, property_definitions=property_definitions)

        return self.users[unique_id]

    def add_group(self, name: str, unique_id: str, group_type: str = None, is_local: bool = True, identities: List[str] = None) -> HostGroup:
        """Add a new group to this host.

        Args:
            name (str): Display name for group. Required.
            unique_id (str): Unique identifier for group. Required.
            group_type (str, optional): Type for group. Defaults to None.
            is_local (bool, optional): True for a group defined on the host itself. False for a directory group granted access without a local definition. Defaults to True.
            identities (list[str], optional): The identities in an identity provider this group corresponds to. Required when `is_local` is False. Defaults to None.

        Raises:
            OAATemplateException: name or unique_id is empty, or group already defined.

        Returns:
            HostGroup
        """

        if not name:
            raise OAATemplateException("Group must have a name")
        if not unique_id:
            raise OAATemplateException("Group must have a unique_id")

        if unique_id in self.groups:
            raise OAATemplateException(f"Group identified by {unique_id} already defined")

        property_definitions = self._property_definitions.group_properties if self._property_definitions else None
        self.groups[unique_id] = HostGroup(name=name, unique_id=unique_id, group_type=group_type, is_local=is_local, identities=identities, property_definitions=property_definitions)

        return self.groups[unique_id]

    def add_credential(self, name: str, unique_id: str, credential_type: str = None, assumes_user: str = None, created_at: str = None, last_used_at: str = None, is_active: bool = None, can_expire: bool = None, expires_at: str = None) -> HostCredential:
        """Add a new credential to this host.

        A credential is a way of authenticating as an account, such as an SSH key. It carries no
        privileges of its own; it identifies which account its holder becomes.

        Args:
            name (str): Display name for credential. Required.
            unique_id (str): Unique identifier for credential. Required.
            credential_type (str, optional): Type for credential. Defaults to None.
            assumes_user (str, optional): ID of the account on this host this credential authenticates as. Defaults to None.
            created_at (str, optional): RFC3339 timestamp. Defaults to None.
            last_used_at (str, optional): RFC3339 timestamp. Defaults to None.
            is_active (bool, optional): Defaults to None.
            can_expire (bool, optional): Defaults to None.
            expires_at (str, optional): RFC3339 timestamp. Defaults to None.

        Raises:
            OAATemplateException: name or unique_id is empty, or credential already defined.

        Returns:
            HostCredential
        """

        if not name:
            raise OAATemplateException("Credential must have a name")
        if not unique_id:
            raise OAATemplateException("Credential must have a unique_id")

        if unique_id in self.credentials:
            raise OAATemplateException(f"Credential identified by {unique_id} already defined")

        self.credentials[unique_id] = HostCredential(name=name, unique_id=unique_id, credential_type=credential_type, assumes_user=assumes_user, created_at=created_at, last_used_at=last_used_at, is_active=is_active, can_expire=can_expire, expires_at=expires_at)

        return self.credentials[unique_id]

    def add_resource(self, name: str, unique_id: str, resource_type: str) -> HostResource:
        """Add a new resource to this host.

        A resource is something inside the host that a privilege can apply to, such as a service
        or a command, rather than the host as a whole.

        A `unique_id` is unique within a `resource_type` rather than across the host, so a service
        and a container may both be called `postgres`.

        Args:
            name (str): Display name for resource. Required.
            unique_id (str): Unique identifier for resource within the resource_type. Required.
            resource_type (str): The kind of thing this is, e.g. "service" or "command". Must not contain a "." or ":" character. Required.

        Raises:
            OAATemplateException: name, unique_id or resource_type is empty, a resource of the same type and unique_id is already defined, or resource_type contains a "." or ":" character.

        Returns:
            HostResource
        """

        if not name:
            raise OAATemplateException("Resource must have a name")
        if not unique_id:
            raise OAATemplateException("Resource must have a unique_id")
        if not resource_type:
            raise OAATemplateException("Resource must have a resource_type")

        property_definitions = self._property_definitions.resource_properties if self._property_definitions else None
        resource = HostResource(name=name, unique_id=unique_id, resource_type=resource_type, property_definitions=property_definitions)

        if resource.resource_key in self.resources:
            raise OAATemplateException(f"Resource identified by {resource.resource_key} already defined")

        self.resources[resource.resource_key] = resource

        return resource

    def add_grant(self, principal_id: str, grantee_type: HostGranteeType, is_local: bool = True, privileges: list = None, apply_to_host: bool = None, resources: list = None) -> None:
        """Grant privileges to a principal on this host.

        Records which privileges a user or group holds, on the host itself, on resources inside
        it, or both. Calling this again for the same `principal_id` and `grantee_type` adds to the
        existing grant rather than creating a second one; the same id used for both a user and a
        group grant produces two separate grants.

        Args:
            principal_id (str): ID of the user or group holding the privileges. Must be declared among this host's users or groups when `is_local` is True.
            grantee_type (HostGranteeType): Whether `principal_id` names a user or a group.
            is_local (bool, optional): Whether the principal is declared on this host. False for a directory-backed principal, whose identity provider's connector draws the edge from it. Defaults to True.
            privileges (list, optional): Privilege names granted, each of which must have been defined on the provider with `HostProvider.add_privilege()`. An entry may be a bare name (str), or a dict carrying a `name` key where something needs to be said about how the privilege is held, such as `{"name": "sudo", "no_password": True}`. Defaults to None.
            apply_to_host (bool, optional): Whether these privileges apply to the host itself. Defaults to None.
            resources (list, optional): Resources inside the host these privileges also apply to. Accepts `HostResource` instances or "resource_type.id" strings. Defaults to None.

        Raises:
            OAATemplateException: principal_id is empty, grantee_type is not a HostGranteeType, a privileges entry is not a name or an object carrying one, or a resources entry is not the expected type.
        """

        if not principal_id:
            raise OAATemplateException("Grant must have a principal_id")

        if not isinstance(grantee_type, HostGranteeType):
            raise OAATemplateException("grantee_type must be of type HostGranteeType enum")

        if privileges is None:
            privileges = []
        elif not isinstance(privileges, list):
            raise OAATemplateException("privileges must be list")

        for privilege in privileges:
            if isinstance(privilege, str):
                continue
            elif isinstance(privilege, dict):
                if not privilege.get("name"):
                    raise OAATemplateException("a privilege object must carry a non-empty name")
            else:
                raise OAATemplateException("privileges entries must be str or dict")

        if resources is None:
            resources = []
        elif not isinstance(resources, list):
            raise OAATemplateException("resources must be list")

        resource_keys = []
        for resource in resources:
            if isinstance(resource, HostResource):
                resource_keys.append(resource.resource_key)
            elif isinstance(resource, str):
                resource_keys.append(resource)
            else:
                raise OAATemplateException("resources entries must be HostResource instances or str of 'resource_type.id'")

        grant_key = f"{grantee_type.value}:{principal_id}"
        if grant_key in self.identity_to_privileges:
            grant = self.identity_to_privileges[grant_key]
            for privilege in privileges:
                if privilege not in grant["privileges"]:
                    grant["privileges"].append(privilege)
            for resource_key in resource_keys:
                if resource_key not in grant["resources"]:
                    grant["resources"].append(resource_key)
            if apply_to_host is not None:
                grant["apply_to_host"] = apply_to_host
        else:
            self.identity_to_privileges[grant_key] = {"id": principal_id,
                                                       "grantee_type": grantee_type,
                                                       "is_local": is_local,
                                                       "privileges": list(privileges),
                                                       "apply_to_host": apply_to_host,
                                                       "resources": resource_keys
                                                      }


class HostUser():
    """A user account on a Host.

    A user belongs to exactly one host: root on two hosts is two accounts, each with its own
    `last_login_at` and `is_active`. Created by `HostNode.add_user()`.

    Args:
        name (str): Display name for user. Required.
        unique_id (str): Unique identifier for user. Required.
        identities (list[str], optional): The identities in an identity provider this account belongs to. Defaults to None.
        is_local (bool, optional): Defaults to True.
        identity_type (HostIdentityType, optional): Defaults to None.
        is_active (bool, optional): Defaults to None.
        last_login_at (str, optional): RFC3339 timestamp. Defaults to None.
        property_definitions (CaseInsensitiveDict, optional): Property definitions for the host's users. Defaults to None.

    Raises:
        ValueError: name or unique_id is empty.
        OAATemplateException: identity_type is not a HostIdentityType.
    """

    def __init__(self, name: str, unique_id: str, identities: List[str] = None, is_local: bool = True, identity_type: HostIdentityType = None, is_active: bool = None, last_login_at: str = None, property_definitions=None) -> None:
        if not name:
            raise ValueError("name cannot be empty")
        if not unique_id:
            raise ValueError("unique_id cannot be empty")

        self.name = name
        self.unique_id = unique_id

        self.identities = identities or []
        self.is_local = is_local

        if identity_type is not None and not isinstance(identity_type, HostIdentityType):
            raise OAATemplateException("identity_type must be of type HostIdentityType enum")
        self.identity_type = identity_type

        self.is_active = is_active
        self.last_login_at = last_login_at
        self.groups = []

        self._property_definitions = property_definitions
        self.custom_properties = {}

    def __str__(self) -> str:
        return f"Host User - {self.name} ({self.unique_id})"

    def __repr__(self) -> str:
        return f"HostUser(name={self.name!r}, unique_id={self.unique_id!r})"

    def add_group(self, group_id: str) -> None:
        """Add this user to a group.

        Group must also be defined on the host with `HostNode.add_group()`.

        Args:
            group_id (str): ID of the group to add user to.

        Raises:
            OAATemplateException: group_id is empty.
        """

        if not group_id:
            raise OAATemplateException("group_id cannot be empty")

        if group_id not in self.groups:
            self.groups.append(group_id)

    def set_property(self, property_name: str, property_value: any, ignore_none: bool = False) -> None:
        """Set a custom property value for the user.

        Property name must be defined for the fleet's users before calling `set_property`.

        Args:
            property_name (str): Name of property to set value for
            property_value (Any): Value for property, type should match OAAPropertyType for property definition
            ignore_none (bool, optional): Do not set property if value is None. Defaults to False.

        Raises:
            OAATemplateException: If property name is not defined.
        """

        if self._property_definitions is None:
            raise OAATemplateException(f"No custom properties defined, cannot set value for property {property_name}")

        if ignore_none and property_value is None:
            return

        if property_name not in self._property_definitions:
            raise OAATemplateException(f"unknown user property name {property_name}")

        self.custom_properties[property_name] = property_value

    def to_dict(self) -> dict:
        """ Output function for payload. """

        user = {"id": self.unique_id,
                "name": self.name,
                "identities": self.identities,
                "is_local": self.is_local,
                "identity_type": self.identity_type,
                "is_active": self.is_active,
                "last_login_at": self.last_login_at,
                "custom_properties": self.custom_properties,
                "groups": [{"id": group_id} for group_id in self.groups]
               }

        return {k: v for k, v in user.items() if v not in [None, [], {}, ""]}


class HostGroup():
    """A group on a Host.

    Created by `HostNode.add_group()`.

    Args:
        name (str): Display name for group. Required.
        unique_id (str): Unique identifier for group. Required.
        group_type (str, optional): Type for group. Defaults to None.
        is_local (bool, optional): Defaults to True.
        identities (list[str], optional): The identities in an identity provider this group corresponds to. Defaults to None.
        property_definitions (CaseInsensitiveDict, optional): Property definitions for the host's groups. Defaults to None.

    Raises:
        ValueError: name or unique_id is empty.
    """

    def __init__(self, name: str, unique_id: str, group_type: str = None, is_local: bool = True, identities: List[str] = None, property_definitions=None) -> None:
        if not name:
            raise ValueError("name cannot be empty")
        if not unique_id:
            raise ValueError("unique_id cannot be empty")

        self.name = name
        self.unique_id = unique_id

        self.group_type = group_type
        self.is_local = is_local
        self.identities = identities or []
        self.member_groups = []

        self._property_definitions = property_definitions
        self.custom_properties = {}

    def __str__(self) -> str:
        return f"Host Group - {self.name} ({self.unique_id}) - {self.group_type}"

    def __repr__(self) -> str:
        return f"HostGroup(name={self.name!r}, unique_id={self.unique_id!r}, group_type={self.group_type!r})"

    def add_member_group(self, group_id: str, is_local: bool = True) -> None:
        """Add a member group.

        A member may be another group on the same host, or a directory-backed group with no
        local definition.

        Args:
            group_id (str): ID of the member group.
            is_local (bool, optional): Whether the member group is declared on this host. Defaults to True.

        Raises:
            OAATemplateException: group_id is empty.
        """

        if not group_id:
            raise OAATemplateException("group_id cannot be empty")

        for member in self.member_groups:
            if member["id"] == group_id:
                return

        self.member_groups.append({"id": group_id, "is_local": is_local})

    def set_property(self, property_name: str, property_value: any, ignore_none: bool = False) -> None:
        """Set a custom property value for the group.

        Property name must be defined for the fleet's groups before calling `set_property`.

        Args:
            property_name (str): Name of property to set value for
            property_value (Any): Value for property, type should match OAAPropertyType for property definition
            ignore_none (bool, optional): Do not set property if value is None. Defaults to False.

        Raises:
            OAATemplateException: If property name is not defined.
        """

        if self._property_definitions is None:
            raise OAATemplateException(f"No custom properties defined, cannot set value for property {property_name}")

        if ignore_none and property_value is None:
            return

        if property_name not in self._property_definitions:
            raise OAATemplateException(f"unknown group property name {property_name}")

        self.custom_properties[property_name] = property_value

    def to_dict(self) -> dict:
        """ Output function for payload. """

        group = {"id": self.unique_id,
                 "name": self.name,
                 "group_type": self.group_type,
                 "is_local": self.is_local,
                 "identities": self.identities,
                 "custom_properties": self.custom_properties,
                 "member_groups": self.member_groups
                }

        return {k: v for k, v in group.items() if v not in [None, [], {}, ""]}


class HostCredential():
    """A credential that authenticates as an account on a Host.

    A credential is a way of authenticating as an account, such as an SSH key. It carries no
    privileges of its own; it identifies which account its holder becomes. Created by
    `HostNode.add_credential()`.

    Credentials have no custom properties.

    Args:
        name (str): Display name for credential. Required.
        unique_id (str): Unique identifier for credential. Required.
        credential_type (str, optional): Type for credential. Defaults to None.
        assumes_user (str, optional): ID of the account on this host this credential authenticates as. Defaults to None.
        created_at (str, optional): RFC3339 timestamp. Defaults to None.
        last_used_at (str, optional): RFC3339 timestamp. Defaults to None.
        is_active (bool, optional): Defaults to None.
        can_expire (bool, optional): Defaults to None.
        expires_at (str, optional): RFC3339 timestamp. Defaults to None.

    Raises:
        ValueError: name or unique_id is empty.
    """

    def __init__(self, name: str, unique_id: str, credential_type: str = None, assumes_user: str = None, created_at: str = None, last_used_at: str = None, is_active: bool = None, can_expire: bool = None, expires_at: str = None) -> None:
        if not name:
            raise ValueError("name cannot be empty")
        if not unique_id:
            raise ValueError("unique_id cannot be empty")

        self.name = name
        self.unique_id = unique_id

        self.credential_type = credential_type
        self.assumes_user = assumes_user
        self.created_at = created_at
        self.last_used_at = last_used_at
        self.is_active = is_active
        self.can_expire = can_expire
        self.expires_at = expires_at

        self.holders = []

    def __str__(self) -> str:
        return f"Host Credential - {self.name} ({self.unique_id}) - {self.credential_type}"

    def __repr__(self) -> str:
        return f"HostCredential(name={self.name!r}, unique_id={self.unique_id!r}, credential_type={self.credential_type!r})"

    def add_holder(self, identity_id: str, is_local: bool = True) -> None:
        """Add a holder to this credential.

        Holders are the identities known to hold the credential, so several people holding keys
        to one shared account can be distinguished. A holder is often not an account on this host
        at all.

        Args:
            identity_id (str): ID of the identity that holds the credential.
            is_local (bool, optional): Whether the holder is an account declared on this host. Defaults to True.

        Raises:
            OAATemplateException: identity_id is empty.
        """

        if not identity_id:
            raise OAATemplateException("identity_id cannot be empty")

        for holder in self.holders:
            if holder["id"] == identity_id:
                return

        self.holders.append({"id": identity_id, "is_local": is_local})

    def to_dict(self) -> dict:
        """ Output function for payload. """

        credential = {"id": self.unique_id,
                      "name": self.name,
                      "credential_type": self.credential_type,
                      "holders": self.holders,
                      "created_at": self.created_at,
                      "last_used_at": self.last_used_at,
                      "is_active": self.is_active,
                      "can_expire": self.can_expire,
                      "expires_at": self.expires_at
                     }

        if self.assumes_user:
            credential["assumes_user"] = {"id": self.assumes_user}

        return {k: v for k, v in credential.items() if v not in [None, [], {}, ""]}


class HostResource():
    """Something inside a host that a privilege can apply to.

    A resource is something inside a host that a privilege can apply to, such as a service or a
    command, rather than the host as a whole. Referred to from a grant as `resource_type.id` via
    `resource_key`. Created by `HostNode.add_resource()`.

    Args:
        name (str): Display name for resource. Required.
        unique_id (str): Unique identifier for resource within the resource_type. Required.
        resource_type (str): The kind of thing this is, e.g. "service" or "command". Must not contain a "." or ":" character. Required.
        property_definitions (CaseInsensitiveDict, optional): Property definitions for the host's resources. Defaults to None.

    Attributes:
        resource_key (str): The `resource_type.id` identifier a grant uses to refer to this resource.

    Raises:
        ValueError: name, unique_id or resource_type is empty.
        OAATemplateException: resource_type contains a "." or ":" character.
    """

    def __init__(self, name: str, unique_id: str, resource_type: str, property_definitions=None) -> None:
        if not name:
            raise ValueError("name cannot be empty")
        if not unique_id:
            raise ValueError("unique_id cannot be empty")
        if not resource_type:
            raise ValueError("resource_type cannot be empty")

        self.name = name
        self.unique_id = unique_id

        if "." in resource_type or ":" in resource_type:
            raise OAATemplateException(f'resource_type must not contain a "." or ":" character, received {resource_type!r}')
        self.resource_type = resource_type

        self._property_definitions = property_definitions
        self.custom_properties = {}

    def __str__(self) -> str:
        return f"Host Resource - {self.name} ({self.unique_id}) - {self.resource_type}"

    def __repr__(self) -> str:
        return f"HostResource(name={self.name!r}, unique_id={self.unique_id!r}, resource_type={self.resource_type!r})"

    @property
    def resource_key(self) -> str:
        """ The `resource_type.id` identifier a grant uses to refer to this resource. """
        return f"{self.resource_type}.{self.unique_id}"

    def set_property(self, property_name: str, property_value: any, ignore_none: bool = False) -> None:
        """Set a custom property value for the resource.

        Property name must be defined for the fleet's resources before calling `set_property`.

        Args:
            property_name (str): Name of property to set value for
            property_value (Any): Value for property, type should match OAAPropertyType for property definition
            ignore_none (bool, optional): Do not set property if value is None. Defaults to False.

        Raises:
            OAATemplateException: If property name is not defined.
        """

        if self._property_definitions is None:
            raise OAATemplateException(f"No custom properties defined, cannot set value for property {property_name}")

        if ignore_none and property_value is None:
            return

        if property_name not in self._property_definitions:
            raise OAATemplateException(f"unknown resource property name {property_name}")

        self.custom_properties[property_name] = property_value

    def to_dict(self) -> dict:
        """ Output function for payload. """

        resource = {"id": self.unique_id,
                    "name": self.name,
                    "resource_type": self.resource_type,
                    "custom_properties": self.custom_properties
                   }

        return {k: v for k, v in resource.items() if v not in [None, [], {}, ""]}


class HostPrivilegeDefinition():
    """A privilege defined once on the fleet and referenced by name wherever it is granted.

    Names are supplied by the connector rather than fixed by Veza. Created by
    `HostProvider.add_privilege()`.

    Args:
        name (str): Name grants refer to
        privilege_type (list[OAAPermission]): Canonical access types this privilege confers
        description (str, optional): Description for privilege. Defaults to None.

    Raises:
        ValueError: name is empty.
        OAATemplateException: A privilege_type entry is not an OAAPermission.
    """

    def __init__(self, name: str, privilege_type: List[OAAPermission], description: str = None) -> None:
        if not name:
            raise ValueError("name cannot be empty")

        self.name = name
        self.description = description

        if privilege_type is None:
            privilege_type = []
        elif not isinstance(privilege_type, list):
            raise OAATemplateException("privilege_type must be list")

        for p in privilege_type:
            if not isinstance(p, OAAPermission):
                raise OAATemplateException("privilege_type entries must be OAAPermission enum")

        self.privilege_type = privilege_type

    def __str__(self) -> str:
        return f"Host Privilege - {self.name}"

    def __repr__(self) -> str:
        return f"HostPrivilegeDefinition(name={self.name!r}, privilege_type={self.privilege_type})"

    def to_dict(self) -> dict:
        """ Output function for payload. """

        privilege = {"name": self.name,
                     "description": self.description,
                     "privilege_type": self.privilege_type
                    }

        return {k: v for k, v in privilege.items() if v not in [None, [], {}, ""]}


class HostPropertyDefinitions():
    """Model for defining custom properties for a Host fleet's hosts, users, groups and resources.

    Property definitions define the names for additional entity properties and the expected type.
    Credentials have no custom properties.

    Attributes:
        host_properties (dict): property definitions for hosts
        user_properties (dict): property definitions for users
        group_properties (dict): property definitions for groups
        resource_properties (dict): property definitions for resources
    """

    def __init__(self) -> None:
        self.host_properties = CaseInsensitiveDict()
        self.user_properties = CaseInsensitiveDict()
        self.group_properties = CaseInsensitiveDict()
        self.resource_properties = CaseInsensitiveDict()

    def to_dict(self) -> dict:

        definitions = {
            "host_properties": {k: v for k, v in self.host_properties.items()},
            "user_properties": {k: v for k, v in self.user_properties.items()},
            "group_properties": {k: v for k, v in self.group_properties.items()},
            "resource_properties": {k: v for k, v in self.resource_properties.items()}
        }

        return definitions

    def define_host_property(self, name: str, property_type: OAAPropertyType) -> None:
        self.validate_name(name)
        self._validate_types(name, property_type)
        self.host_properties[name] = property_type

    def define_user_property(self, name: str, property_type: OAAPropertyType) -> None:
        self.validate_name(name)
        self._validate_types(name, property_type)
        self.user_properties[name] = property_type

    def define_group_property(self, name: str, property_type: OAAPropertyType) -> None:
        self.validate_name(name)
        self._validate_types(name, property_type)
        self.group_properties[name] = property_type

    def define_resource_property(self, name: str, property_type: OAAPropertyType) -> None:
        self.validate_name(name)
        self._validate_types(name, property_type)
        self.resource_properties[name] = property_type

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

