"""
Copyright 2022 Veza Technologies Inc.

Use of this source code is governed by the MIT
license that can be found in the LICENSE file or at
https://opensource.org/licenses/MIT.
"""

import json
import pytest

from generate_hris import GENERATED_HRIS_PAYLOAD, generate_hris

from oaaclient.templates import HRISEmployee, HRISGroup, HRISProvider, OAAPropertyType, OAATemplateException

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