#!/usr/bin/env python3
"""
Copyright 2022 Veza Technologies Inc.

Use of this source code is governed by the MIT
license that can be found in the LICENSE file or at
https://opensource.org/licenses/MIT.
"""

import logging
import sys

from oaaclient.client import OAAClient, OAAClientError
from oaaclient.templates import HRISProvider, OAAPropertyType

logging.basicConfig(format='%(asctime)s %(levelname)s: %(thread)d %(message)s', level=logging.INFO)
log = logging.getLogger(__name__)


def generate_hris() -> HRISProvider:
    """ Generates a complete HRIS provider """

    hris = HRISProvider("Pytest HRIS", hris_type="PyHRIS", url="example.com")

    hris.property_definitions.define_employee_property("nickname", OAAPropertyType.STRING)
    hris.property_definitions.define_employee_property("has_keys", OAAPropertyType.BOOLEAN)
    hris.property_definitions.define_group_property("is_social", OAAPropertyType.BOOLEAN)

    for i in range(1, 10):
        employee = hris.add_employee(unique_id=f"{i:03d}",
                                             name=f"employee{i:03d}",
                                             employee_number=f"{i:03d}",
                                             first_name="Employee",
                                             last_name="Fake",
                                             is_active=True,
                                             employment_status="EMPLOYED",
                                             )
        employee.set_property("nickname", f"e{i}")
        employee.set_property("has_keys", i%2 == 0)


    max_employee = hris.add_employee(unique_id="max",
                                     name="max",
                                     employee_number="1010101",
                                     first_name="max",
                                     last_name="employee",
                                     is_active=True,
                                     employment_status="hired")
    max_employee.company = "Veza"
    max_employee.preferred_name = "maxamilian"
    max_employee.display_full_name = "Max Display Name Employee"
    max_employee.canonical_name = "Max Canonical Name Employee"
    max_employee.username = "maxm"
    max_employee.email = "max@cookiestg.com"
    max_employee.idp_id = "max@veza.local"
    max_employee.personal_email = "max_no_real@gmail.com"
    max_employee.home_location = "St Paul, MN"
    max_employee.work_location = "Minneapolis, MN"

    hris.add_group(unique_id="cc01", name="Cost Center 01", group_type="cost_center")
    max_employee.cost_center = "cc01"

    hris.add_group(unique_id="eng", name="Engineering", group_type="Department")
    max_employee.department = "eng"
    max_employee.managers = ["001"]
    max_employee.add_manager("002")

    max_employee.start_date = "2020-04-12T23:20:50.52Z"
    max_employee.termination_date = "2023-10-01T23:20:50.52Z"
    max_employee.job_title = "Test Engineer"
    max_employee.employment_types = ["FULL_TIME"]
    max_employee.primary_time_zone = "CST"


    for i in range(1,5):
        group = hris.add_group(unique_id=f"g{i:03d}", name=f"Group {i:03d}", group_type="Team")
        hris.employees[f"{i:03d}"].add_group(f"g{i:03d}")

    hris.groups["g001"].set_property("is_social", True)

    return hris


def main() -> None:
  log.info("Generate HRIS Main")
  # assumes VEZA_URL and VEZA_API_KEY are set in env
  try:
    con = OAAClient()
  except (OAAClientError, ValueError) as e:
     log.error(e)
     log.error("exiting")
     sys.exit(1)

  log.info("Connected to tenant")
  hris = generate_hris()
  log.info("HRIS loaded")
  try:
     log.info("Pushing")
     con.push_application(provider_name="Pytest Gen HRIS", data_source_name="generate_hris_main", application_object=hris, create_provider=True)
  except OAAClientError as error:
      log.error(f"{error.error}: {error.message} ({error.status_code})")
      if hasattr(error, "details"):
          for detail in error.details:
              log.error(f"  {detail}")

  log.info("Complete")

  return


if __name__ == "__main__":
  log = logging.getLogger()
  main()


GENERATED_HRIS_PAYLOAD = """
{
  "name": "Pytest HRIS",
  "hris_type": "PyHRIS",
  "custom_property_definition": {
    "system_properties": {},
    "employee_properties": {
      "nickname": "STRING",
      "has_keys": "BOOLEAN"
    },
    "group_properties": {
      "is_social": "BOOLEAN"
    }
  },
  "system": {
    "id": "Pytest HRIS",
    "name": "Pytest HRIS",
    "url": "example.com"
  },
  "employees": [
    {
      "id": "001",
      "name": "employee001",
      "employee_number": "001",
      "first_name": "Employee",
      "last_name": "Fake",
      "employment_status": "EMPLOYED",
      "custom_properties": {
        "nickname": "e1",
        "has_keys": false
      },
      "is_active": true,
      "groups": [
        {
          "id": "g001"
        }
      ]
    },
    {
      "id": "002",
      "name": "employee002",
      "employee_number": "002",
      "first_name": "Employee",
      "last_name": "Fake",
      "employment_status": "EMPLOYED",
      "custom_properties": {
        "nickname": "e2",
        "has_keys": true
      },
      "is_active": true,
      "groups": [
        {
          "id": "g002"
        }
      ]
    },
    {
      "id": "003",
      "name": "employee003",
      "employee_number": "003",
      "first_name": "Employee",
      "last_name": "Fake",
      "employment_status": "EMPLOYED",
      "custom_properties": {
        "nickname": "e3",
        "has_keys": false
      },
      "is_active": true,
      "groups": [
        {
          "id": "g003"
        }
      ]
    },
    {
      "id": "004",
      "name": "employee004",
      "employee_number": "004",
      "first_name": "Employee",
      "last_name": "Fake",
      "employment_status": "EMPLOYED",
      "custom_properties": {
        "nickname": "e4",
        "has_keys": true
      },
      "is_active": true,
      "groups": [
        {
          "id": "g004"
        }
      ]
    },
    {
      "id": "005",
      "name": "employee005",
      "employee_number": "005",
      "first_name": "Employee",
      "last_name": "Fake",
      "employment_status": "EMPLOYED",
      "custom_properties": {
        "nickname": "e5",
        "has_keys": false
      },
      "is_active": true
    },
    {
      "id": "006",
      "name": "employee006",
      "employee_number": "006",
      "first_name": "Employee",
      "last_name": "Fake",
      "employment_status": "EMPLOYED",
      "custom_properties": {
        "nickname": "e6",
        "has_keys": true
      },
      "is_active": true
    },
    {
      "id": "007",
      "name": "employee007",
      "employee_number": "007",
      "first_name": "Employee",
      "last_name": "Fake",
      "employment_status": "EMPLOYED",
      "custom_properties": {
        "nickname": "e7",
        "has_keys": false
      },
      "is_active": true
    },
    {
      "id": "008",
      "name": "employee008",
      "employee_number": "008",
      "first_name": "Employee",
      "last_name": "Fake",
      "employment_status": "EMPLOYED",
      "custom_properties": {
        "nickname": "e8",
        "has_keys": true
      },
      "is_active": true
    },
    {
      "id": "009",
      "name": "employee009",
      "employee_number": "009",
      "first_name": "Employee",
      "last_name": "Fake",
      "employment_status": "EMPLOYED",
      "custom_properties": {
        "nickname": "e9",
        "has_keys": false
      },
      "is_active": true
    },
    {
      "id": "max",
      "name": "max",
      "employee_number": "1010101",
      "company": "Veza",
      "first_name": "max",
      "last_name": "employee",
      "preferred_name": "maxamilian",
      "display_full_name": "Max Display Name Employee",
      "canonical_name": "Max Canonical Name Employee",
      "username": "maxm",
      "email": "max@cookiestg.com",
      "idp_id": "max@veza.local",
      "personal_email": "max_no_real@gmail.com",
      "home_location": "St Paul, MN",
      "work_location": "Minneapolis, MN",
      "employment_status": "hired",
      "start_date": "2020-04-12T23:20:50.52Z",
      "termination_date": "2023-10-01T23:20:50.52Z",
      "job_title": "Test Engineer",
      "employment_types": [
        "FULL_TIME"
      ],
      "primary_time_zone": "CST",
      "is_active": true,
      "managers": [
        {
          "id": "001"
        },
        {
          "id": "002"
        }
      ],
      "department": {
        "id": "eng"
      },
      "cost_center": {
        "id": "cc01"
      }
    }
  ],
  "groups": [
    {
      "id": "cc01",
      "name": "Cost Center 01",
      "group_type": "cost_center"
    },
    {
      "id": "eng",
      "name": "Engineering",
      "group_type": "Department"
    },
    {
      "id": "g001",
      "name": "Group 001",
      "group_type": "Team",
      "custom_properties": {
        "is_social": true
      }
    },
    {
      "id": "g002",
      "name": "Group 002",
      "group_type": "Team"
    },
    {
      "id": "g003",
      "name": "Group 003",
      "group_type": "Team"
    },
    {
      "id": "g004",
      "name": "Group 004",
      "group_type": "Team"
    }
  ]
}
"""