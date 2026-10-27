"""
Copyright 2026 Veza Technologies Inc.

Use of this source code is governed by the MIT
license that can be found in the LICENSE file or at
https://opensource.org/licenses/MIT.
"""

import json

import pytest

from generate_host import GENERATED_HOST_PAYLOAD, generate_host

from oaaclient.templates import HostEnvironment, HostGranteeType, HostGroup, HostNode, HostProvider, HostResource, HostUser, OAAPermission, OAAPropertyType, OAATemplateException


def test_generate_host():
    host_provider = generate_host()
    payload = host_provider.get_payload()
    print(json.dumps(payload, indent=2))

    assert payload == json.loads(GENERATED_HOST_PAYLOAD)


def test_single_host_submission():
    """ A per-host agent submission has no environment of its own; it names its environment by ID instead. """

    host_provider = HostProvider(host_type="linux")
    host_provider.add_privilege(name="sudo", privilege_type=[OAAPermission.DataRead])
    host_provider.add_host(name="web-02", unique_id="web-02", environment_id="prod-linux-fleet")

    payload = host_provider.get_payload()

    assert "environment" not in payload
    assert payload["hosts"] == [{"id": "web-02", "name": "web-02", "environment_id": "prod-linux-fleet"}]


def test_host_grant_merges_by_principal():
    """ Calling add_grant again for the same principal merges into the existing grant rather than duplicating it. """

    host_provider = HostProvider(host_type="linux")
    host = host_provider.add_host(name="web-01", unique_id="web-01")
    resource = host.add_resource(name="nginx", unique_id="nginx", resource_type="service")

    host.add_grant(principal_id="root", grantee_type=HostGranteeType.USER, privileges=["sudo"])
    host.add_grant(principal_id="root", grantee_type=HostGranteeType.USER, privileges=["sudo"], resources=[resource])
    host.add_grant(principal_id="root", grantee_type=HostGranteeType.USER, apply_to_host=True)

    assert len(host.identity_to_privileges) == 1
    grant = host.identity_to_privileges["user:root"]
    assert grant["privileges"] == ["sudo"]
    assert grant["resources"] == ["service.nginx"]
    assert grant["apply_to_host"] is True


def test_host_grant_keeps_grantee_types_separate():
    """ The same id used for both a user and a group grant produces two separate grants. """

    host_provider = HostProvider(host_type="linux")
    host = host_provider.add_host(name="web-01", unique_id="web-01")

    host.add_grant(principal_id="ops", grantee_type=HostGranteeType.USER, privileges=["sudo"])
    host.add_grant(principal_id="ops", grantee_type=HostGranteeType.GROUP, privileges=["ssh-login"])

    assert len(host.identity_to_privileges) == 2
    user_grant = host.identity_to_privileges["user:ops"]
    group_grant = host.identity_to_privileges["group:ops"]
    assert user_grant["privileges"] == ["sudo"]
    assert group_grant["privileges"] == ["ssh-login"]


def test_host_exceptions():

    host_provider = HostProvider(host_type="linux")

    # test duplicate environment
    host_provider.add_environment(unique_id="env01", name="Env 01")
    with pytest.raises(OAATemplateException) as e:
        host_provider.add_environment(unique_id="env02", name="Env 02")
    assert e.value.message == "Environment already defined for this submission"

    with pytest.raises(ValueError):
        HostEnvironment(unique_id="", name="Env")
    with pytest.raises(ValueError):
        HostEnvironment(unique_id="env", name="")

    # test duplicate host, and missing name/unique_id
    host_provider.add_host(name="web-01", unique_id="web-01")
    with pytest.raises(OAATemplateException) as e:
        host_provider.add_host(name="web-01", unique_id="web-01")
    assert e.value.message == "Host identified by web-01 already defined"

    with pytest.raises(OAATemplateException) as e:
        host_provider.add_host(name="", unique_id="web-99")
    assert e.value.message == "Host must have a name"
    with pytest.raises(OAATemplateException) as e:
        host_provider.add_host(name="web-99", unique_id="")
    assert e.value.message == "Host must have a unique_id"

    # test duplicate privilege, and missing name
    host_provider.add_privilege(name="sudo", privilege_type=[OAAPermission.DataRead])
    with pytest.raises(OAATemplateException) as e:
        host_provider.add_privilege(name="sudo", privilege_type=[OAAPermission.DataRead])
    assert e.value.message == "Privilege sudo already defined"

    with pytest.raises(OAATemplateException) as e:
        host_provider.add_privilege(name="", privilege_type=[OAAPermission.DataRead])
    assert e.value.message == "Privilege must have a name"

    with pytest.raises(OAATemplateException) as e:
        host_provider.add_privilege(name="bad", privilege_type=["DataRead"])
    assert e.value.message == "privilege_type entries must be OAAPermission enum"

    host = host_provider.hosts["web-01"]

    # test duplicate user/group/credential/resource, and missing name/unique_id
    host.add_user(name="root", unique_id="root")
    with pytest.raises(OAATemplateException) as e:
        host.add_user(name="root", unique_id="root")
    assert e.value.message == "User identified by root already defined"
    with pytest.raises(OAATemplateException) as e:
        host.add_user(name="", unique_id="x")
    assert e.value.message == "User must have a name"
    with pytest.raises(OAATemplateException) as e:
        host.add_user(name="x", unique_id="")
    assert e.value.message == "User must have a unique_id"
    with pytest.raises(OAATemplateException) as e:
        host.add_user(name="bad", unique_id="bad_type", identity_type="human")
    assert e.value.message == "identity_type must be of type HostIdentityType enum"

    host.add_group(name="wheel", unique_id="wheel")
    with pytest.raises(OAATemplateException) as e:
        host.add_group(name="wheel", unique_id="wheel")
    assert e.value.message == "Group identified by wheel already defined"
    with pytest.raises(OAATemplateException) as e:
        host.add_group(name="", unique_id="x")
    assert e.value.message == "Group must have a name"
    with pytest.raises(OAATemplateException) as e:
        host.add_group(name="x", unique_id="")
    assert e.value.message == "Group must have a unique_id"

    host.add_credential(name="key01", unique_id="key01")
    with pytest.raises(OAATemplateException) as e:
        host.add_credential(name="key01", unique_id="key01")
    assert e.value.message == "Credential identified by key01 already defined"
    with pytest.raises(OAATemplateException) as e:
        host.add_credential(name="", unique_id="x")
    assert e.value.message == "Credential must have a name"
    with pytest.raises(OAATemplateException) as e:
        host.add_credential(name="x", unique_id="")
    assert e.value.message == "Credential must have a unique_id"

    host.add_resource(name="nginx", unique_id="nginx", resource_type="service")
    # a unique_id is unique within a resource_type, so the same id under another type is a
    # separate resource
    nginx_container = host.add_resource(name="nginx", unique_id="nginx", resource_type="container")
    assert nginx_container.resource_key == "container.nginx"
    with pytest.raises(OAATemplateException) as e:
        host.add_resource(name="nginx", unique_id="nginx", resource_type="service")
    assert e.value.message == "Resource identified by service.nginx already defined"
    with pytest.raises(OAATemplateException) as e:
        host.add_resource(name="", unique_id="x", resource_type="service")
    assert e.value.message == "Resource must have a name"
    with pytest.raises(OAATemplateException) as e:
        host.add_resource(name="x", unique_id="", resource_type="service")
    assert e.value.message == "Resource must have a unique_id"
    with pytest.raises(OAATemplateException) as e:
        host.add_resource(name="x", unique_id="x", resource_type="")
    assert e.value.message == "Resource must have a resource_type"
    with pytest.raises(OAATemplateException) as e:
        host.add_resource(name="bad", unique_id="bad", resource_type="service.sub")
    assert 'resource_type must not contain a "." or ":" character' in e.value.message
    with pytest.raises(OAATemplateException) as e:
        host.add_resource(name="bad", unique_id="bad", resource_type="service:sub")
    assert 'resource_type must not contain a "." or ":" character' in e.value.message

    # test grant validation
    with pytest.raises(OAATemplateException) as e:
        host.add_grant(principal_id="", grantee_type=HostGranteeType.USER)
    assert e.value.message == "Grant must have a principal_id"

    with pytest.raises(OAATemplateException) as e:
        host.add_grant(principal_id="root", grantee_type="user")
    assert e.value.message == "grantee_type must be of type HostGranteeType enum"

    with pytest.raises(OAATemplateException) as e:
        host.add_grant(principal_id="root", grantee_type=HostGranteeType.USER, privileges="sudo")
    assert e.value.message == "privileges must be list"

    with pytest.raises(OAATemplateException) as e:
        host.add_grant(principal_id="root", grantee_type=HostGranteeType.USER, privileges=[1])
    assert e.value.message == "privileges entries must be str or dict"

    with pytest.raises(OAATemplateException) as e:
        host.add_grant(principal_id="root", grantee_type=HostGranteeType.USER, resources="nginx")
    assert e.value.message == "resources must be list"

    with pytest.raises(OAATemplateException) as e:
        host.add_grant(principal_id="root", grantee_type=HostGranteeType.USER, resources=[1])
    assert "resources entries must be" in e.value.message

    with pytest.raises(OAATemplateException) as e:
        host.add_grant(principal_id="root", grantee_type=HostGranteeType.USER, privileges=[{"no_password": True}])
    assert e.value.message == "a privilege object must carry a non-empty name"

    with pytest.raises(OAATemplateException) as e:
        host.add_grant(principal_id="root", grantee_type=HostGranteeType.USER, privileges=[{"name": ""}])
    assert e.value.message == "a privilege object must carry a non-empty name"

    # test empty-id checks on group/member-group/holder references
    user = host.add_user(name="alice", unique_id="alice")
    with pytest.raises(OAATemplateException) as e:
        user.add_group("")
    assert e.value.message == "group_id cannot be empty"

    group = host.add_group(name="wheel2", unique_id="wheel2")
    with pytest.raises(OAATemplateException) as e:
        group.add_member_group("")
    assert e.value.message == "group_id cannot be empty"

    credential = host.add_credential(name="key02", unique_id="key02")
    with pytest.raises(OAATemplateException) as e:
        credential.add_holder("")
    assert e.value.message == "identity_id cannot be empty"


def test_resource_key():
    resource = HostResource(name="nginx", unique_id="nginx", resource_type="service")
    assert resource.resource_key == "service.nginx"


def test_host_custom_properties():

    host_provider = HostProvider(host_type="linux")
    host = host_provider.add_host(name="web-01", unique_id="web-01")

    with pytest.raises(OAATemplateException) as e:
        host.set_property("unset", "something")
    assert "host property name" in e.value.message

    user = host.add_user(name="root", unique_id="root")
    with pytest.raises(OAATemplateException) as e:
        user.set_property("unset", "something")
    assert "user property name" in e.value.message

    group = host.add_group(name="wheel", unique_id="wheel")
    with pytest.raises(OAATemplateException) as e:
        group.set_property("unset", "something")
    assert "group property name" in e.value.message

    resource = host.add_resource(name="nginx", unique_id="nginx", resource_type="service")
    with pytest.raises(OAATemplateException) as e:
        resource.set_property("unset", "something")
    assert "resource property name" in e.value.message

    host_provider.property_definitions.define_host_property("region", OAAPropertyType.STRING)
    host_provider.property_definitions.define_user_property("shell", OAAPropertyType.STRING)
    host_provider.property_definitions.define_group_property("is_admin_group", OAAPropertyType.BOOLEAN)
    host_provider.property_definitions.define_resource_property("port", OAAPropertyType.NUMBER)

    host2 = host_provider.add_host(name="web-02", unique_id="web-02")
    host2.set_property("region", "us-west-2")
    assert host2.custom_properties["region"] == "us-west-2"

    user2 = host2.add_user(name="svc", unique_id="svc")
    user2.set_property("shell", "/bin/sh")
    assert user2.custom_properties["shell"] == "/bin/sh"

    group2 = host2.add_group(name="admins", unique_id="admins")
    group2.set_property("is_admin_group", True)
    assert group2.custom_properties["is_admin_group"] is True

    resource2 = host2.add_resource(name="nginx", unique_id="nginx", resource_type="service")
    resource2.set_property("port", 443)
    assert resource2.custom_properties["port"] == 443

    # entities created outside the provider have no property definitions to validate against,
    # so set_property raises rather than silently accepting an unvalidated name
    standalone_host = HostNode(name="standalone", unique_id="standalone")
    with pytest.raises(OAATemplateException):
        standalone_host.set_property("unset", "value")

    standalone_user = HostUser(name="standalone", unique_id="standalone")
    with pytest.raises(OAATemplateException):
        standalone_user.set_property("unset", "value")

    standalone_group = HostGroup(name="standalone", unique_id="standalone")
    with pytest.raises(OAATemplateException):
        standalone_group.set_property("unset", "value")
