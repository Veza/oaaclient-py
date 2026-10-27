"""
Copyright 2022 Veza Technologies Inc.

Use of this source code is governed by the MIT
license that can be found in the LICENSE file or at
https://opensource.org/licenses/MIT.
"""

import pytest
import json

from oaaclient.templates import (CustomIdPProvider,
                                  IdentityMappingConfigurationSubmission,
                                  IdentityMappingMode, IdentityMappingProperty,
                                  IdentityMappingType, OAATemplateException)
from generate_idp import generate_idp, GENERATED_IDP_PAYLOAD


def test_custom_idp():
    idp_name = "test"
    idp_type = "test_idp"
    idp = CustomIdPProvider(idp_name, idp_type, "pytest test IdP")

    # create some users
    user001 = idp.add_user("user001")
    user001.department = "Quality Assurance"
    user001.department = "Quality Assurance"
    user001.manager_id = "user003_identity"
    user002 = idp.add_user("user002")
    user003 = idp.add_user("user003", identity="user003_identity")
    user004 = idp.add_user("user004")

    user003.is_guest = False
    user004.is_guest = True

    # create groups
    idp.add_group("group001")
    idp.add_group("group002")
    idp.add_group("group003", identity="group003_identity")

    # add users to groups
    user001.add_groups(["group001"])
    user002.add_groups(["group002"])
    idp.users["user003_identity"].add_groups(["group001", "group002"])

    user001.add_assumed_role_arns(["arn:aws:iam::123456789012:role/role001", "arn:aws:iam::123456789012:role/role002"])
    # test adding a role multiple times is deduplicated property
    user001.add_assumed_role_arns(["arn:aws:iam::123456789012:role/role001"])
    user002.add_assumed_role_arns(["arn:aws:iam::123456789012:role/role001"])

    payload = idp.get_payload()

    print(json.dumps(payload, indent=2))
    expected_result = json.loads(TEST_CUSTOM_IDP_RESULT)

    assert payload == expected_result


def test_generate_idp():
    idp = generate_idp()
    payload = idp.get_payload()
    print(json.dumps(payload, indent=2))

    assert payload == json.loads(GENERATED_IDP_PAYLOAD)


def test_custom_idp_exceptions():
    idp_name = "test"
    idp_type = "test_idp"
    idp = CustomIdPProvider(idp_name, idp_type, "pytest test IdP")

    # assert duplicate user raises exception
    user_name = "duplicate001"
    idp.add_user(user_name)
    with pytest.raises(OAATemplateException) as e:
        idp.add_user(user_name)
    assert user_name in e.value.message

    # asert duplicate group raises exception
    group_name = "dupgroup"
    idp.add_group(group_name)
    with pytest.raises(OAATemplateException) as e:
        idp.add_group(group_name)
    assert group_name in e.value.message

    # assert add_assumed_role_arns enforces list
    test_user = idp.add_user("test001")
    with pytest.raises(OAATemplateException) as e:
        test_user.add_assumed_role_arns("arn:aws:iam::123456789012:role/role001")
    assert e.value.message == "arns must be of type list"

    with pytest.raises(OAATemplateException) as e:
        test_user.add_groups("group01")
    assert e.value.message == "group_identities must be list"

    with pytest.raises(OAATemplateException) as e:
        test_user.set_source_identity("bob", "somestring")
    assert e.value.message == "provider_type must be IdPProviderType enum"

    test_group = idp.add_group(name="test")
    with pytest.raises(OAATemplateException) as e:
      test_group.add_groups(["test"])

    assert e.value.message == "Cannot add a group to itself 'test'"

    test_group2 = idp.add_group(name="test", identity="test2")
    with pytest.raises(OAATemplateException) as e:
      test_group2.add_groups(["test2"])

    assert e.value.message == "Cannot add a group to itself 'test2'"

# expected paylods
TEST_CUSTOM_IDP_RESULT = """
{
  "custom_property_definition": {
    "domain_properties": {},
    "user_properties": {},
    "group_properties": {},
    "app_properties": {},
    "app_assignment_properties": {}
  },
  "name": "test",
  "idp_type": "test_idp",
  "domains": [
    {
      "name": "pytest test IdP",
      "tags": [],
      "custom_properties": {}
    }
  ],
  "users": [
    {
      "name": "user001",
      "identity": "user001",
      "department": "Quality Assurance",
      "manager_id": "user003_identity",
      "groups": [
        {
          "identity": "group001"
        }
      ],
      "assumed_role_arns": [
        {
          "identity": "arn:aws:iam::123456789012:role/role001"
        },
        {
          "identity": "arn:aws:iam::123456789012:role/role002"
        }
      ]
    },
    {
      "name": "user002",
      "identity": "user002",
      "groups": [
        {
          "identity": "group002"
        }
      ],
      "assumed_role_arns": [
        {
          "identity": "arn:aws:iam::123456789012:role/role001"
        }
      ]
    },
    {
      "name": "user003",
      "identity": "user003_identity",
      "is_guest": false,
      "groups": [
        {
          "identity": "group001"
        },
        {
          "identity": "group002"
        }
      ]
    },
    {
      "name": "user004",
      "identity": "user004",
      "is_guest": true
    }
  ],
  "groups": [
    {
      "name": "group001",
      "identity": "group001"
    },
    {
      "name": "group002",
      "identity": "group002"
    },
    {
      "name": "group003",
      "identity": "group003_identity"
    }
  ],
  "apps": []
}
"""


def test_set_identity_mapping_configuration():
    """Test that set_identity_mapping_configuration creates and returns the configuration object"""
    idp = CustomIdPProvider("mappingTest", "pytest", "example.com")

    assert idp.identity_mapping_configuration is None

    config = idp.set_identity_mapping_configuration()

    assert isinstance(config, IdentityMappingConfigurationSubmission)
    assert idp.identity_mapping_configuration is config


def test_set_identity_mapping_configuration_replaces_existing():
    """Test that calling set_identity_mapping_configuration again replaces the previous one"""
    idp = CustomIdPProvider("mappingTest", "pytest", "example.com")

    config1 = idp.set_identity_mapping_configuration()
    config1.use_email = True

    config2 = idp.set_identity_mapping_configuration()

    assert idp.identity_mapping_configuration is config2
    assert config2.use_email is False


def test_identity_mapping_in_payload():
    """Test that identity mapping configuration is included in get_payload output"""
    idp = CustomIdPProvider("mappingTest", "pytest", "example.com")

    config = idp.set_identity_mapping_configuration()
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

    payload = idp.get_payload()

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
    idp = CustomIdPProvider("noMappingTest", "pytest", "example.com")

    assert "identity_mapping_configuration" not in idp.get_payload()
