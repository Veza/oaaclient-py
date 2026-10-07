"""
Copyright 2026 Veza Technologies Inc.

Use of this source code is governed by the MIT
license that can be found in the LICENSE file or at
https://opensource.org/licenses/MIT.
"""

import json

import pytest
from generate_principal import GENERATED_PRINCIPAL_PAYLOAD, generate_principal

from oaaclient.templates import (
    CustomPrincipal,
    CustomPrincipalUser,
    CustomPrincipalGroup,
    CustomPrincipalTenant,
    PrincipalPropertyDefinitions,
    PrincipalEntityType,
    OAAPropertyType,
    OAATemplateException
)


def test_generate_principal():
    principal = generate_principal()
    payload = principal.get_payload()
    print(json.dumps(payload, indent=2))

    assert payload == json.loads(GENERATED_PRINCIPAL_PAYLOAD)


def test_principal_provider_init():
    """Test CustomPrincipalProvider initialization."""
    principal = CustomPrincipal(name="Test Provider", principal_type="TestType", tenant_id="example.test")

    assert principal.name == "Test Provider"
    assert principal.principal_type == "TestType"
    assert principal.tenant.id == "example.test"
    assert isinstance(principal.property_definitions, PrincipalPropertyDefinitions)
    assert principal.tenant is not None
    assert len(principal.users) == 0
    assert len(principal.groups) == 0


def test_principal_tenant():
    """Test tenant creation and properties."""
    principal = CustomPrincipal(name="Test Provider", principal_type="TestType", tenant_id="example.test")

    tenant = principal.tenant
    assert isinstance(tenant, CustomPrincipalTenant)
    assert tenant.name == "Test Provider"
    assert tenant.id == "example.test"

    # Test tenant tags
    tenant.add_tag("environment", "production")
    tenant_dict = tenant.to_dict()
    assert len(tenant_dict["tags"]) == 1
    assert tenant_dict["tags"][0]["key"] == "environment"
    assert tenant_dict["tags"][0]["value"] == "production"


def test_principal_user_creation():
    """Test user creation and properties."""
    principal = CustomPrincipal(name="Test Provider", principal_type="TestType", tenant_id="example.test")

    # Test basic user creation
    user1 = principal.add_user("user001", unique_id="u001", email="user001@example.com")

    assert isinstance(user1, CustomPrincipalUser)
    assert user1.name == "user001"
    assert user1.unique_id == "u001"
    assert user1.email == "user001@example.com"
    assert user1.user_unique_id is None

    # Test user without email - user_unique_id should default to id
    user2 = principal.add_user("user002", unique_id="u002")
    assert user2.user_unique_id is None

    # Test user with explicit user_unique_id
    user3 = principal.add_user("user003", unique_id="u003", user_unique_id="custom_id")
    assert user3.user_unique_id == "custom_id"


def test_principal_user_properties():
    """Test user properties and methods."""
    principal = CustomPrincipal(name="Test Provider", principal_type="TestType", tenant_id="example.test")
    user = principal.add_user("testuser", unique_id="u001", email="test@example.com")

    # Test optional properties
    user.display_name = "Test User"
    user.is_active = True
    user.created_at = "2020-01-01T00:00:00.00Z"
    user.deactivated_at = "2024-01-01T00:00:00.00Z"
    user.last_login_at = "2024-01-15T10:30:00.00Z"

    user_dict = user.to_dict()
    assert user_dict["display_name"] == "Test User"
    assert user_dict["is_active"] is True
    assert user_dict["created_date"] == "2020-01-01T00:00:00.00Z"
    assert user_dict["deactivated_date"] == "2024-01-01T00:00:00.00Z"
    assert user_dict["last_login"] == "2024-01-15T10:30:00.00Z"


def test_principal_user_identities():
    """Test user identity management."""
    principal = CustomPrincipal(name="Test Provider", principal_type="TestType", tenant_id="example.test")
    user = principal.add_user("testuser", unique_id="u001")

    user.add_identity("identity1@example.com")
    user.add_identity("identity2@example.com")
    user.add_identity("identity1@example.com")  # Duplicate - should not add

    user_dict = user.to_dict()
    assert len(user_dict["identities"]) == 2
    assert "identity1@example.com" in user_dict["identities"]
    assert "identity2@example.com" in user_dict["identities"]


def test_principal_user_groups():
    """Test user group membership."""
    principal = CustomPrincipal(name="Test Provider", principal_type="TestType", tenant_id="example.test")
    user = principal.add_user("testuser", unique_id="u001")
    principal.add_group("group1", unique_id="g001")
    principal.add_group("group2", unique_id="g002")

    user.add_group("g001")
    user.add_group("g002")
    user.add_group("g001")  # Duplicate - should not add

    user_dict = user.to_dict()
    assert len(user_dict["groups"]) == 2


def test_principal_user_tags():
    """Test user tag management."""
    principal = CustomPrincipal(name="Test Provider", principal_type="TestType", tenant_id="example.test")
    user = principal.add_user("testuser", unique_id="u001")

    user.add_tag("department", "Engineering")
    user.add_tag("role", "admin")

    user_dict = user.to_dict()
    assert len(user_dict["tags"]) == 2


def test_principal_group_creation():
    """Test group creation and properties."""
    principal = CustomPrincipal(name="Test Provider", principal_type="TestType", tenant_id="example.test")

    # Test basic group creation
    group1 = principal.add_group("group001", unique_id="g001")

    assert isinstance(group1, CustomPrincipalGroup)
    assert group1.name == "group001"
    assert group1.id == "g001"
    assert group1.group_unique_id is None

    # Test group with explicit group_unique_id
    group2 = principal.add_group("group002", unique_id="g002", group_unique_id="custom_group_id")
    assert group2.group_unique_id == "custom_group_id"


def test_principal_group_properties():
    """Test group properties and methods."""
    principal = CustomPrincipal(name="Test Provider", principal_type="TestType", tenant_id="example.test")
    group = principal.add_group("testgroup", unique_id="g001")

    # Test optional properties
    group.group_type = "Security"

    group_dict = group.to_dict()
    assert group_dict["group_type"] == "Security"


def test_principal_group_identities():
    """Test group identity management."""
    principal = CustomPrincipal(name="Test Provider", principal_type="TestType", tenant_id="example.test")
    group = principal.add_group("testgroup", unique_id="g001")

    group.add_identity("group@example.com")
    group.add_identity("group-alias@example.com")
    group.add_identity("group@example.com")  # Duplicate - should not add

    group_dict = group.to_dict()
    assert len(group_dict["identities"]) == 2


def test_principal_group_hierarchy():
    """Test hierarchical group structure."""
    principal = CustomPrincipal(name="Test Provider", principal_type="TestType", tenant_id="example.test")
    parent_group = principal.add_group("parent", unique_id="parent01")
    child_group = principal.add_group("child", unique_id="child01")

    child_group.set_parent_group("parent01")

    child_dict = child_group.to_dict()
    assert "parent_group" in child_dict
    assert child_dict["parent_group"]["id"] == "parent01"


def test_principal_group_tags():
    """Test group tag management."""
    principal = CustomPrincipal(name="Test Provider", principal_type="TestType", tenant_id="example.test")
    group = principal.add_group("testgroup", unique_id="g001")

    group.add_tag("team", "Platform")
    group.add_tag("environment", "production")

    group_dict = group.to_dict()
    assert len(group_dict["tags"]) == 2


def test_principal_exceptions():
    """Test exception handling."""
    principal = CustomPrincipal(name="Test Provider", principal_type="TestType", tenant_id="example.test")

    # Test duplicate user
    user_details = {
        "name": "Test User",
        "unique_id": "u001",
        "email": "test@example.com"
    }

    principal.add_user(**user_details)

    with pytest.raises(OAATemplateException) as e:
        principal.add_user(**user_details)

    assert "u001" in str(e.value)
    assert "already defined" in str(e.value)

    # Test duplicate group
    group_details = {
        "name": "test group",
        "unique_id": "g001"
    }

    principal.add_group(**group_details)

    with pytest.raises(OAATemplateException) as e:
        principal.add_group(**group_details)

    assert "g001" in str(e.value)
    assert "already defined" in str(e.value)


def test_principal_custom_properties():
    """Test custom property functionality."""
    principal = CustomPrincipal(name="Test Provider", principal_type="TestType", tenant_id="example.test")

    # Define custom properties
    principal.property_definitions.define_tenant_property("region", OAAPropertyType.STRING)
    principal.property_definitions.define_user_property("nickname", OAAPropertyType.STRING)
    principal.property_definitions.define_user_property("has_keys", OAAPropertyType.BOOLEAN)
    principal.property_definitions.define_group_property("is_security", OAAPropertyType.BOOLEAN)

    # Set tenant and test property
    principal.tenant.set_property("region", "us-west-2")
    assert principal.tenant._properties["region"] == "us-west-2"

    # Test user property
    user1 = principal.add_user("user001", unique_id="u001")
    user1.set_property("nickname", "u1")
    user1.set_property("has_keys", True)
    assert user1._properties["nickname"] == "u1"
    assert user1._properties["has_keys"] is True

    # Test group property
    group1 = principal.add_group("group001", unique_id="g001")
    group1.set_property("is_security", True)
    assert group1._properties["is_security"] is True


def test_principal_custom_property_validation():
    """Test custom property validation."""
    principal = CustomPrincipal(name="Test Provider", principal_type="TestType", tenant_id="example.test")

    user1 = principal.add_user("user001", unique_id="u001")

    # Test setting undefined property on user
    with pytest.raises(OAATemplateException) as e:
        user1.set_property("undefined_prop", "value")

    assert "unknown property name" in str(e.value).lower()

    group1 = principal.add_group("group001", unique_id="g001")

    # Test setting undefined property on group
    with pytest.raises(OAATemplateException) as e:
        group1.set_property("undefined_prop", "value")

    assert "unknown property name" in str(e.value).lower()

    # Test setting undefined property on tenant
    with pytest.raises(OAATemplateException) as e:
        principal.tenant.set_property("undefined_prop", "value")

    assert "unknown property name" in str(e.value).lower()


def test_principal_custom_property_ignore_none():
    """Test ignore_none parameter for custom properties."""
    principal = CustomPrincipal(name="Test Provider", principal_type="TestType", tenant_id="example.test")

    principal.property_definitions.define_user_property("optional_prop", OAAPropertyType.STRING)

    user = principal.add_user("user001", unique_id="u001")

    # Test that None value is not set when ignore_none=True
    user.set_property("optional_prop", None, ignore_none=True)
    assert "optional_prop" not in user._properties

    # Test that None value is set when ignore_none=False
    user.set_property("optional_prop", None, ignore_none=False)
    assert "optional_prop" in user._properties
    assert user._properties["optional_prop"] is None


def test_principal_property_definitions():
    """Test property definitions model."""
    prop_defs = PrincipalPropertyDefinitions()

    # Test defining properties
    prop_defs.define_tenant_property("prop1", OAAPropertyType.STRING)
    prop_defs.define_user_property("prop2", OAAPropertyType.BOOLEAN)
    prop_defs.define_group_property("prop3", OAAPropertyType.NUMBER)

    assert "prop1" in prop_defs.tenant_properties
    assert "prop2" in prop_defs.user_properties
    assert "prop3" in prop_defs.group_properties

    # Test to_dict
    prop_dict = prop_defs.to_dict()
    assert "tenant_properties" in prop_dict
    assert "user_properties" in prop_dict
    assert "group_properties" in prop_dict


def test_principal_property_definitions_validation():
    """Test property definition validation."""
    prop_defs = PrincipalPropertyDefinitions()

    # Test invalid property name type
    with pytest.raises(OAATemplateException) as e:
        prop_defs.define_user_property(123, OAAPropertyType.STRING)

    assert "property name must be type string" in str(e.value).lower()

    # Test invalid property type
    with pytest.raises(OAATemplateException) as e:
        prop_defs.define_user_property("prop", "STRING")

    assert "property_type must be type oaapropertytype enum" in str(e.value).lower()


def test_principal_property_name_validation():
    """Test property name validation for different entity types."""
    prop_defs = PrincipalPropertyDefinitions()

    prop_defs.define_tenant_property("tenant_prop", OAAPropertyType.STRING)
    prop_defs.define_user_property("user_prop", OAAPropertyType.STRING)
    prop_defs.define_group_property("group_prop", OAAPropertyType.STRING)

    # Test valid property names
    assert prop_defs.validate_property_name("tenant_prop", PrincipalEntityType.TENANT) is True
    assert prop_defs.validate_property_name("user_prop", PrincipalEntityType.USER) is True
    assert prop_defs.validate_property_name("group_prop", PrincipalEntityType.GROUP) is True

    # Test case insensitivity
    assert prop_defs.validate_property_name("TENANT_PROP", PrincipalEntityType.TENANT) is True
    assert prop_defs.validate_property_name("User_Prop", PrincipalEntityType.USER) is True

    # Test invalid property names
    with pytest.raises(OAATemplateException) as e:
        prop_defs.validate_property_name("invalid_prop", PrincipalEntityType.TENANT)

    assert "unknown property name" in str(e.value).lower()

    # Test invalid entity type
    with pytest.raises(OAATemplateException) as e:
        prop_defs.validate_property_name("prop", "INVALID_TYPE")

    assert "unknown entity type" in str(e.value).lower()


def test_principal_payload_structure():
    """Test the complete payload structure."""
    principal = CustomPrincipal(name="Test Provider", principal_type="TestType", tenant_id="example.test")

    principal.property_definitions.define_user_property("test_prop", OAAPropertyType.STRING)

    user1 = principal.add_user("user001", unique_id="u001")
    user1.set_property("test_prop", "value1")

    group1 = principal.add_group("group001", unique_id="g001")

    payload = principal.get_payload()

    # Verify payload structure
    assert "custom_property_definition" in payload
    assert "name" in payload
    assert "principal_type" in payload
    assert "tenant" in payload
    assert "users" in payload
    assert "groups" in payload

    assert payload["name"] == "Test Provider"
    assert payload["principal_type"] == "TestType"
    assert len(payload["users"]) == 1
    assert len(payload["groups"]) == 1


def test_principal_case_insensitive_dict():
    """Test case-insensitive dictionary for users and groups."""
    principal = CustomPrincipal(name="Test Provider", principal_type="TestType", tenant_id="example.test")

    # Add user with lowercase id
    principal.add_user("testuser", unique_id="user001")

    # Verify case-insensitive access
    assert "user001" in principal.users
    assert "USER001" in principal.users
    assert "User001" in principal.users

    # Add group with lowercase id
    principal.add_group("testgroup", unique_id="group001")

    # Verify case-insensitive access
    assert "group001" in principal.groups
    assert "GROUP001" in principal.groups
    assert "Group001" in principal.groups


def test_principal_to_dict_excludes_empty():
    """Test that to_dict methods exclude None, empty lists, and empty dicts."""
    principal = CustomPrincipal(name="Test Provider", principal_type="TestType", tenant_id="example.test")

    # Create user with minimal properties
    user = principal.add_user("testuser", unique_id="u001")
    user_dict = user.to_dict()

    # Verify empty values are excluded
    assert "identities" not in user_dict
    assert "groups" not in user_dict
    assert "tags" not in user_dict
    assert "custom_properties" not in user_dict

    # Create group with minimal properties
    group = principal.add_group("testgroup", unique_id="g001")
    group_dict = group.to_dict()

    # Verify empty values are excluded
    assert "identities" not in group_dict
    assert "tags" not in group_dict
    assert "custom_properties" not in group_dict


def test_principal_without_property_definitions():
    """Test behavior when entities are created without property definitions."""
    # Create entities directly without going through provider
    # Should raise exception when trying to set properties without property definitions
    user = CustomPrincipalUser("testuser", unique_id="u001")
    with pytest.raises(OAATemplateException) as e:
        user.set_property("any_prop", "value")
    assert "no custom property definitions found for user" in str(e.value).lower()

    group = CustomPrincipalGroup("testgroup", unique_id="g001")
    with pytest.raises(OAATemplateException) as e:
        group.set_property("any_prop", "value")
    assert "no custom property definitions found for group" in str(e.value).lower()

    tenant = CustomPrincipalTenant("testtenant", unique_id="t001")
    with pytest.raises(OAATemplateException) as e:
        tenant.set_property("any_prop", "value")
    assert "no custom property definitions found for tenant" in str(e.value).lower()
