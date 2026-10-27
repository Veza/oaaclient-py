"""
Copyright 2022 Veza Technologies Inc.

Use of this source code is governed by the MIT
license that can be found in the LICENSE file or at
https://opensource.org/licenses/MIT.
"""

import json
import pytest

from generate_hris import GENERATED_HRIS_PAYLOAD, generate_hris

from oaaclient.templates import (HRISEmployee, HRISGroup, HRISProvider,
                                  IdentityMappingConfigurationSubmission,
                                  IdentityMappingMode,
                                  IdentityMappingProperty,
                                  IdentityMappingType, OAAPropertyType,
                                  OAATemplateException)

def test_generate_hris():
    hris = generate_hris()
    payload = hris.get_payload()
    print(json.dumps(payload, indent=2))

    assert payload == json.loads(GENERATED_HRIS_PAYLOAD)

def test_hris_exceptions():

    hris = generate_hris()

    # test duplicate user
    user_details = {"unique_id": "12345",
                    "name": "Test User",
                    "employee_number": "12345",
                    "first_name": "first",
                    "last_name": "last",
                    "is_active": True,
                    "employment_status": "hired"
                }

    hris.add_employee(**user_details)

    with pytest.raises(OAATemplateException) as e:
        hris.add_employee(**user_details)

    assert e.value.message == "Employee with unique ID already exists, 12345"

    # test duplicate group
    group_details = {"unique_id": "g12345",
                     "name": "test group",
                     "group_type": "Team"
                    }

    hris.add_group(**group_details)

    with pytest.raises(OAATemplateException) as e:
        hris.add_group(**group_details)

    assert e.value.message == "Group with unique ID already exists, g12345"

    with pytest.raises(OAATemplateException) as e:
        hris.property_definitions.define_employee_property(1, OAAPropertyType.BOOLEAN)

    assert e.value.message == "Property name must be a string, received <class 'int'>"

    with pytest.raises(OAATemplateException) as e:
        hris.property_definitions.define_employee_property("@property", OAAPropertyType.BOOLEAN)

    assert e.value.message == "Lower-cased property name must match the pattern: '^[a-z][a-z_]*$'. Invalid name: @property"

    with pytest.raises(ValueError, match=r"provider_type must be of type IdPProviderType enum, received <class 'str'>") as e:
        hris.system.add_idp_type("okta")


# Test for empty input validation on user creation
@pytest.mark.parametrize("details",
                         [
                             {"unique_id": "", "name": "Test User", "employee_number": "12345", "first_name": "first", "last_name": "last", "is_active": True, "employment_status": "hired"},
                             {"unique_id": "12345", "name": "", "employee_number": "12345", "first_name": "first", "last_name": "last", "is_active": True, "employment_status": "hired"},
                             {"unique_id": "12345", "name": "Test User", "employee_number": "", "first_name": "first", "last_name": "last", "is_active": True, "employment_status": "hired"},
                             {"unique_id": "12345", "name": "Test User", "employee_number": "12345", "first_name": "", "last_name": "last", "is_active": True, "employment_status": "hired"},
                             {"unique_id": "12345", "name": "Test User", "employee_number": "12345", "first_name": "first", "last_name": "", "is_active": True, "employment_status": "hired"},
                             {"unique_id": "12345", "name": "Test User", "employee_number": "12345", "first_name": "first", "last_name": "last", "is_active": None, "employment_status": "hired"},
                             {"unique_id": "12345", "name": "Test User", "employee_number": "12345", "first_name": "first", "last_name": "last", "is_active": True, "employment_status": ""}
                        ])
def test_employee_init(details):

    with pytest.raises(ValueError) as e:
        employee = HRISEmployee(**details)

    assert e.value.args is not None


def test_hris_custom_properties():

    hris = HRISProvider("propertyTest", "pytest", "https://hris.example.com")

    employee1 = hris.add_employee("001", "user001", "001", "user", "test", True, "HIRED")

    with pytest.raises(OAATemplateException) as e:
        employee1.set_property("unset", "something")

    assert "employee" in e.value.message
    assert "unset" in e.value.message

    group1 = hris.add_group("g01", "group01", "testGroup")

    with pytest.raises(OAATemplateException) as e:
        group1.set_property("unset", "hello")

    assert "group" in e.value.message
    assert "unset" in e.value.message


    hris.property_definitions.define_employee_property("testProp", OAAPropertyType.STRING)
    employee2 = hris.add_employee("002", "user002", "002", "user", "test", True, "HIRED")

    employee2.set_property("testprop", "value1")
    assert employee2.custom_properties["testprop"] == "value1"

    # test behavior when Employee or Group are created outside the Provider
    # since there is no property definitions no validation can be performed, unset property shouldn't cause error
    employee_obj = HRISEmployee("001", "user001", "001", "user", "test", True, "HIRED")
    employee_obj.set_property("unset", "value2")

    group_obj = HRISGroup("g01", "group01", "testGroup")
    group_obj.set_property("unset", "value2")


def test_set_identity_mapping_configuration():
    """Test that set_identity_mapping_configuration creates and returns the configuration object"""
    hris = HRISProvider("mappingTest", "pytest", "https://hris.example.com")

    assert hris.system.identity_mapping_configuration is None

    config = hris.system.set_identity_mapping_configuration()

    assert isinstance(config, IdentityMappingConfigurationSubmission)
    assert hris.system.identity_mapping_configuration is config


def test_set_identity_mapping_configuration_replaces_existing():
    """Test that calling set_identity_mapping_configuration again replaces the previous one"""
    hris = HRISProvider("mappingTest", "pytest", "https://hris.example.com")

    config1 = hris.system.set_identity_mapping_configuration()
    config1.use_email = True

    config2 = hris.system.set_identity_mapping_configuration()

    assert hris.system.identity_mapping_configuration is config2
    assert config2.use_email is False


def test_identity_mapping_in_payload():
    """Test that identity mapping configuration is included in get_payload output under system"""
    hris = HRISProvider("mappingTest", "pytest", "https://hris.example.com")

    config = hris.system.set_identity_mapping_configuration()
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

    payload = hris.get_payload()

    assert "identity_mapping_configuration" in payload["system"]
    imc = payload["system"]["identity_mapping_configuration"]
    assert imc["use_email"] is True
    assert len(imc["mappings"]) == 1
    m = imc["mappings"][0]
    assert m["destination_datasource_type"] == "okta"
    assert m["type"] == "EQUAL"
    assert m["mode"] == "USERS"
    assert m["property_matchers"] == [{"source_property": "EMAIL", "destination_property": "EMAIL"}]


def test_no_identity_mapping_omitted_from_payload():
    """Test that identity_mapping_configuration is absent from system payload when not set"""
    hris = HRISProvider("noMappingTest", "pytest", "https://hris.example.com")

    payload = hris.get_payload()

    assert "identity_mapping_configuration" not in payload["system"]