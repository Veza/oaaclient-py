"""
Copyright 2026 Veza Technologies Inc.

Use of this source code is governed by the MIT
license that can be found in the LICENSE file or at
https://opensource.org/licenses/MIT.
"""

import json
import pytest

from generate_secret_store import GENERATED_SECRET_STORE_PAYLOAD, generate_secret_store

from oaaclient.templates import (
    IdentityMappingConfigurationSubmission,
    IdentityMappingMode,
    IdentityMappingProperty,
    IdentityMappingType,
    IdentityToPermission,
    OAAPermission,
    OAAPropertyType,
    OAATemplateException,
    PermissionAssignment,
    SecretStore,
    SecretStorePermission,
    SecretStoreSubmission,
    SecretStoreVault,
    SecretStoreVaultEntry,
    VaultEntryIdentity,
)


def test_generate_secret_store():
    """Test that the generate_secret_store function creates the expected payload"""
    provider = generate_secret_store()
    payload = provider.get_payload()
    print(json.dumps(payload, indent=2))

    assert payload == json.loads(GENERATED_SECRET_STORE_PAYLOAD)


def test_secret_store_exceptions():
    """Test that exceptions are raised for duplicate entities and invalid inputs"""
    provider = generate_secret_store()

    # Test duplicate permission
    with pytest.raises(OAATemplateException) as e:
        provider.secret_store.add_permission(
            name="Read",
            unique_id="perm-read"
        )

    assert "Permission with identifier already exists" in e.value.message

    # Test duplicate vault
    with pytest.raises(OAATemplateException) as e:
        provider.secret_store.add_vault(
            name="Vault 01",
            vault_type="general",
            unique_id="vault-01"
        )

    assert "Vault with identifier already exists" in e.value.message

    # Test duplicate entry
    vault = provider.secret_store.vaults["vault-01"]
    with pytest.raises(OAATemplateException) as e:
        vault.add_entry(
            name="Entry 1-1",
            unique_id="entry-01-01"
        )

    assert "Entry with identifier already exists" in e.value.message

    # Test invalid property name (not a string)
    with pytest.raises(OAATemplateException) as e:
        provider.property_definitions.define_secret_store_property(1, OAAPropertyType.BOOLEAN)

    assert "property name must be" in e.value.message.lower() and "string" in e.value.message

    # Test invalid property name (invalid characters)
    with pytest.raises(OAATemplateException) as e:
        provider.property_definitions.define_vault_property("@property", OAAPropertyType.BOOLEAN)

    assert e.value.message == "Lower-cased property name must match the pattern: '^[a-z][a-z_]*$'. Invalid name: @property"


@pytest.mark.parametrize("details", [
    {"name": "", "vault_type": "test"},
    {"name": "Vault", "vault_type": ""},
])
def test_vault_init_validation(details):
    """Test that vault initialization validates required fields"""
    with pytest.raises(ValueError) as e:
        vault = SecretStoreVault(**details)

    assert e.value.args is not None


@pytest.mark.parametrize("details", [
    {"name": ""},
    {"name": "Entry", "unique_id": ""},
])
def test_entry_init_validation(details):
    """Test that entry initialization validates required fields"""
    if "unique_id" in details and details["unique_id"] == "":
        # unique_id defaults to name if not provided, so this should be valid
        entry = SecretStoreVaultEntry(**details)
        assert entry.name == "Entry"
    else:
        with pytest.raises(ValueError) as e:
            entry = SecretStoreVaultEntry(**details)

        assert e.value.args is not None


@pytest.mark.parametrize("details", [
    {"identity_type": "", "external_id": "user@example.com"},
    {"identity_type": "OktaUser", "external_id": ""},
])
def test_vault_entry_identity_init_validation(details):
    """Test that VaultEntryIdentity initialization validates required fields"""
    with pytest.raises(ValueError) as e:
        identity = VaultEntryIdentity(**details)

    assert e.value.args is not None


@pytest.mark.parametrize("details", [
    {"identity": "", "identity_type": "local_user"},
    {"identity": "user", "identity_type": ""},
])
def test_identity_to_permission_init_validation(details):
    """Test that IdentityToPermission initialization validates required fields"""
    with pytest.raises(ValueError) as e:
        itp = IdentityToPermission(**details)

    assert e.value.args is not None


@pytest.mark.parametrize("details", [
    {"vault": [], "permissions": ["Read"]},
    {"vault": ["vault-01"], "permissions": []},
])
def test_permission_assignment_init_validation(details):
    """Test that PermissionAssignment initialization validates required fields"""
    with pytest.raises(ValueError) as e:
        assignment = PermissionAssignment(**details)

    assert e.value.args is not None


def test_secret_store_custom_properties():
    """Test custom property setting and validation"""
    provider = SecretStoreSubmission("propertyTest", "pytest", "test-store-001")

    # Test setting property that is not defined
    with pytest.raises(OAATemplateException) as e:
        provider.secret_store.set_property("unset", "something")

    assert "secret_store" in e.value.message or "unknown" in e.value.message
    assert "unset" in e.value.message

    # Define property and set it
    provider.property_definitions.define_secret_store_property("test_prop", OAAPropertyType.STRING)
    provider.secret_store.set_property("test_prop", "test_value")

    assert provider.secret_store.custom_properties["test_prop"] == "test_value"


def test_vault_custom_properties():
    """Test vault custom property setting"""
    provider = SecretStoreSubmission("propertyTest", "pytest")
    provider.property_definitions.define_vault_property("test_vault_prop", OAAPropertyType.STRING)

    vault = provider.secret_store.add_vault("Test Vault", "general", "vault-001")

    # Test setting property that is not defined
    with pytest.raises(OAATemplateException) as e:
        vault.set_property("unset", "something")

    assert "vault" in e.value.message or "unknown" in e.value.message
    assert "unset" in e.value.message

    # Set defined property
    vault.set_property("test_vault_prop", "vault_value")
    assert vault.custom_properties["test_vault_prop"] == "vault_value"


def test_entry_custom_properties():
    """Test entry custom property setting"""
    provider = SecretStoreSubmission("propertyTest", "pytest")
    provider.property_definitions.define_entry_property("test_entry_prop", OAAPropertyType.BOOLEAN)

    vault = provider.secret_store.add_vault("Test Vault", "general", "vault-001")
    entry = vault.add_entry("Test Entry", "entry-001")

    # Test setting property that is not defined
    with pytest.raises(OAATemplateException) as e:
        entry.set_property("unset", "something")

    assert "entry" in e.value.message or "unknown" in e.value.message
    assert "unset" in e.value.message

    # Set defined property
    entry.set_property("test_entry_prop", True)
    assert entry.custom_properties["test_entry_prop"] == True


def test_permission_custom_properties():
    """Test permission custom property setting"""
    provider = SecretStoreSubmission("propertyTest", "pytest", "test-store-001")
    provider.property_definitions.define_permission_property("test_perm_prop", OAAPropertyType.STRING)

    permission = provider.secret_store.add_permission("Test Permission", "perm-001")

    # Test setting property that is not defined
    with pytest.raises(OAATemplateException) as e:
        permission.set_property("unset", "something")

    assert "permission" in e.value.message or "unknown" in e.value.message
    assert "unset" in e.value.message

    # Set defined property
    permission.set_property("test_perm_prop", "permission_value")
    assert permission.custom_properties["test_perm_prop"] == "permission_value"


def test_permission_type():
    """Test permission_type assignment, validation, and serialization"""
    provider = SecretStoreSubmission("permissionTypeTest", "pytest")

    # Default is an empty list
    permission = provider.secret_store.add_permission("Read", "perm-read")
    assert permission.permission_type == []
    assert "permission_type" not in permission.to_dict()

    # Set via add_permission with a list
    permission = provider.secret_store.add_permission(
        "Write", "perm-write", permission_type=[OAAPermission.DataWrite]
    )
    assert permission.permission_type == [OAAPermission.DataWrite]
    assert permission.to_dict()["permission_type"] == ["DataWrite"]

    # Set via add_permission with a bare enum (not wrapped in a list)
    permission = provider.secret_store.add_permission(
        "Admin", "perm-admin", permission_type=OAAPermission.DataDelete
    )
    assert permission.permission_type == [OAAPermission.DataDelete]

    # Invalid permission_type raises OAATemplateException
    with pytest.raises(OAATemplateException) as e:
        provider.secret_store.add_permission("Bad", "perm-bad", permission_type=["not-an-enum"])

    assert "permission_type must be OAAPermission enum" in e.value.message


def test_add_permission_type():
    """Test the add_permission_type mutator"""
    provider = SecretStoreSubmission("addPermissionTypeTest", "pytest")
    permission = provider.secret_store.add_permission("Decrypt", "perm-decrypt")

    permission.add_permission_type(OAAPermission.DataRead)
    assert permission.permission_type == [OAAPermission.DataRead]

    # Adding the same permission type again does not duplicate it
    permission.add_permission_type(OAAPermission.DataRead)
    assert permission.permission_type == [OAAPermission.DataRead]

    permission.add_permission_type(OAAPermission.MetadataRead)
    assert permission.permission_type == [OAAPermission.DataRead, OAAPermission.MetadataRead]

    with pytest.raises(OAATemplateException) as e:
        permission.add_permission_type("not-an-enum")

    assert "permission_type must be OAAPermission enum" in e.value.message


def test_secret_store_tags():
    """Test tag functionality"""
    provider = SecretStoreSubmission("tagTest", "pytest")

    # Test adding tags
    provider.secret_store.add_tag("env", "production")
    provider.secret_store.add_tag("team", "security")

    assert len(provider.secret_store.tags) == 2
    assert any(tag.key == "env" and tag.value == "production" for tag in provider.secret_store.tags)


def test_vault_entry_identity():
    """Test adding identities to vault entries"""
    provider = SecretStoreSubmission("identityTest", "pytest")
    vault = provider.secret_store.add_vault("Test Vault", "general", "vault-001")
    entry = vault.add_entry("Test Entry", "entry-001")

    # Add identity
    identity = entry.add_identity("OktaUser", "user@example.com")

    assert len(entry.identities) == 1
    assert entry.identities[0].type == "OktaUser"
    assert entry.identities[0].external_id == "user@example.com"


def test_identity_to_permission_mapping():
    """Test identity to permission mapping functionality"""
    provider = SecretStoreSubmission("mappingTest", "pytest")

    # Add identity mapping
    itp = provider.secret_store.add_identity_to_permission("user1", "local_user")

    assert len(provider.secret_store.identity_to_permissions) == 1
    assert itp.identity == "user1"
    assert itp.identity_type == "local_user"

    # Add permission assignment
    assignment = itp.add_permission_assignment(["vault-01", "vault-02"], ["Read", "Write"])

    assert len(itp.permission_assignments) == 1
    assert assignment.vault == ["vault-01", "vault-02"]
    assert assignment.permissions == ["Read", "Write"]

def test_repr_methods():
    """Test __repr__ methods for all classes"""
    provider = SecretStoreSubmission("reprTest", "pytest")
    assert "SecretStoreSubmission" in repr(provider)

    assert "SecretStore" in repr(provider.secret_store)

    permission = provider.secret_store.add_permission("Test Permission", "perm-001")
    assert "SecretStorePermission" in repr(permission)

    vault = provider.secret_store.add_vault("Test Vault", "general", "vault-001")
    assert "SecretStoreVault" in repr(vault)

    entry = vault.add_entry("Test Entry", "entry-001")
    assert "SecretStoreVaultEntry" in repr(entry)

    identity = entry.add_identity("OktaUser", "user@example.com")
    assert "VaultEntryIdentity" in repr(identity)

    itp = provider.secret_store.add_identity_to_permission("user1", "local_user")
    assert "IdentityToPermission" in repr(itp)

    assignment = itp.add_permission_assignment(["vault-01"], ["Read"])
    assert "PermissionAssignment" in repr(assignment)


def test_set_identity_mapping_configuration():
    """Test that set_identity_mapping_configuration creates and returns the configuration object"""
    provider = SecretStoreSubmission("mappingTest", "pytest")

    assert provider.identity_mapping_configuration is None

    config = provider.set_identity_mapping_configuration()

    assert isinstance(config, IdentityMappingConfigurationSubmission)
    assert provider.identity_mapping_configuration is config


def test_set_identity_mapping_configuration_replaces_existing():
    """Test that calling set_identity_mapping_configuration again replaces the previous one"""
    provider = SecretStoreSubmission("mappingTest", "pytest")

    config1 = provider.set_identity_mapping_configuration()
    config1.use_email = True

    config2 = provider.set_identity_mapping_configuration()

    assert provider.identity_mapping_configuration is config2
    assert config2.use_email is False


def test_identity_mapping_in_payload():
    """Test that identity mapping configuration is included in get_payload output"""
    provider = SecretStoreSubmission("mappingTest", "pytest")

    config = provider.set_identity_mapping_configuration()
    config.use_email = True
    mapping = config.add_mapping(
        destination_datasource_type="okta",
        destination_datasource_oaa_type="",
        mapping_type=IdentityMappingType.EQUAL,
        mapping_mode=IdentityMappingMode.USERS,
    )
    mapping.add_property_matcher(
        source_property=IdentityMappingProperty.EMAIL,
        destination_property=IdentityMappingProperty.EMAIL,
    )

    payload = provider.get_payload()

    assert "identity_mapping_configuration" in payload
    imc = payload["identity_mapping_configuration"]
    assert imc["use_email"] is True
    assert len(imc["mappings"]) == 1
    m = imc["mappings"][0]
    assert m["destination_datasource_type"] == "okta"
    assert m["type"] == "EQUAL"
    assert m["mode"] == "USERS"
    assert m["property_matchers"] == [{"source_property": "EMAIL", "destination_property": "EMAIL"}]


def test_no_identity_mapping_omitted_from_payload():
    """Test that identity_mapping_configuration is absent from payload when not set"""
    provider = SecretStoreSubmission("noMappingTest", "pytest")

    payload = provider.get_payload()

    assert "identity_mapping_configuration" not in payload
