#!/usr/bin/env python3
"""
Copyright 2026 Veza Technologies Inc.

Use of this source code is governed by the MIT
license that can be found in the LICENSE file or at
https://opensource.org/licenses/MIT.
"""

import logging
import sys

from oaaclient.client import OAAClient, OAAClientError
from oaaclient.templates import CustomPrincipal, OAAPropertyType

logging.basicConfig(format='%(asctime)s %(levelname)s: %(thread)d %(message)s', level=logging.INFO)
log = logging.getLogger(__name__)


def generate_principal() -> CustomPrincipal:
    """ Generates a complete Principal provider """

    principal = CustomPrincipal("Pytest Principal", principal_type="PyPrincipal", tenant_id="tenant01")

    # Tag tenant
    principal.tenant.add_tag("environment", "test")

    # Define custom properties
    principal.property_definitions.define_tenant_property("tenant_region", OAAPropertyType.STRING)
    principal.property_definitions.define_user_property("nickname", OAAPropertyType.STRING)
    principal.property_definitions.define_user_property("has_keys", OAAPropertyType.BOOLEAN)
    principal.property_definitions.define_group_property("is_security_group", OAAPropertyType.BOOLEAN)

    # Set tenant property
    principal.tenant.set_property("tenant_region", "us-west-2")

    # Create users
    for i in range(1, 5):
        user = principal.add_user(
            name=f"user{i:03d}",
            unique_id=f"{i:03d}",
            email=f"user{i:03d}@example.com",
            user_unique_id=f"user{i:03d}@example.com"
        )
        user.display_name = f"User {i:03d}"
        user.is_active = True
        user.add_identity(f"user{i:03d}@example.com")
        user.add_tag("department", "Engineering")
        user.set_property("nickname", f"u{i}")
        user.set_property("has_keys", i % 2 == 0)

    # Create a detailed user
    max_user = principal.add_user(
        name="maxuser",
        unique_id="max001",
        email="max@example.com",
        user_unique_id="max@example.com"
    )
    max_user.display_name = "Max User"
    max_user.is_active = True
    max_user.created_at = "2020-04-12T23:20:50.52Z"
    max_user.last_login_at = "2024-01-15T10:30:00.00Z"
    max_user.add_identity("max@example.com")
    max_user.add_identity("max@external.com")
    max_user.add_tag("role", "admin")

    # Create groups
    for i in range(1, 4):
        group = principal.add_group(
            name=f"group{i:03d}",
            unique_id=f"g{i:03d}",
            group_unique_id=f"g{i:03d}"
        )
        group.group_type = "Security"
        group.add_identity(f"group{i:03d}@example.com")
        group.add_tag("team", "Platform")
        group.set_property("is_security_group", True)

    # Add users to groups
    principal.users["001"].add_group("g001")
    principal.users["002"].add_group("g002")
    principal.users["003"].add_group("g001")
    principal.users["003"].add_group("g002")

    # Create hierarchical group
    parent_group = principal.add_group(
        name="parent_group",
        unique_id="parent01",
        group_unique_id="parent01"
    )
    parent_group.group_type = "Distribution"

    child_group = principal.groups["g003"]
    child_group.set_parent_group("parent01")

    return principal


def main() -> None:
    log.info("Generate Principal Main")
    # assumes VEZA_URL and VEZA_API_KEY are set in env
    try:
        con = OAAClient()
    except (OAAClientError, ValueError) as e:
        log.error(e)
        log.error("exiting")
        sys.exit(1)

    log.info("Connected to tenant")
    principal = generate_principal()
    log.info("Principal loaded")
    try:
        log.info("Pushing")
        con.push_application(provider_name="Pytest Gen Principal", data_source_name="generate_principal_main", application_object=principal, create_provider=True)
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


GENERATED_PRINCIPAL_PAYLOAD = """
{
  "custom_property_definition": {
    "tenant_properties": {
      "tenant_region": "STRING"
    },
    "user_properties": {
      "nickname": "STRING",
      "has_keys": "BOOLEAN"
    },
    "group_properties": {
      "is_security_group": "BOOLEAN"
    }
  },
  "name": "Pytest Principal",
  "principal_type": "PyPrincipal",
  "tenant": {
    "name": "Pytest Principal",
    "id": "tenant01",
    "tenant_unique_id": "tenant01",
    "tags": [
      {
        "key": "environment",
        "value": "test"
      }
    ],
    "custom_properties": {
      "tenant_region": "us-west-2"
    }
  },
  "users": [
    {
      "name": "user001",
      "id": "001",
      "email": "user001@example.com",
      "user_unique_id": "user001@example.com",
      "display_name": "User 001",
      "is_active": true,
      "identities": [
        "user001@example.com"
      ],
      "groups": [
        {
          "id": "g001"
        }
      ],
      "tags": [
        {
          "key": "department",
          "value": "Engineering"
        }
      ],
      "custom_properties": {
        "nickname": "u1",
        "has_keys": false
      }
    },
    {
      "name": "user002",
      "id": "002",
      "email": "user002@example.com",
      "user_unique_id": "user002@example.com",
      "display_name": "User 002",
      "is_active": true,
      "identities": [
        "user002@example.com"
      ],
      "groups": [
        {
          "id": "g002"
        }
      ],
      "tags": [
        {
          "key": "department",
          "value": "Engineering"
        }
      ],
      "custom_properties": {
        "nickname": "u2",
        "has_keys": true
      }
    },
    {
      "name": "user003",
      "id": "003",
      "email": "user003@example.com",
      "user_unique_id": "user003@example.com",
      "display_name": "User 003",
      "is_active": true,
      "identities": [
        "user003@example.com"
      ],
      "groups": [
        {
          "id": "g001"
        },
        {
          "id": "g002"
        }
      ],
      "tags": [
        {
          "key": "department",
          "value": "Engineering"
        }
      ],
      "custom_properties": {
        "nickname": "u3",
        "has_keys": false
      }
    },
    {
      "name": "user004",
      "id": "004",
      "email": "user004@example.com",
      "user_unique_id": "user004@example.com",
      "display_name": "User 004",
      "is_active": true,
      "identities": [
        "user004@example.com"
      ],
      "tags": [
        {
          "key": "department",
          "value": "Engineering"
        }
      ],
      "custom_properties": {
        "nickname": "u4",
        "has_keys": true
      }
    },
    {
      "name": "maxuser",
      "id": "max001",
      "email": "max@example.com",
      "user_unique_id": "max@example.com",
      "display_name": "Max User",
      "is_active": true,
      "created_date": "2020-04-12T23:20:50.52Z",
      "last_login": "2024-01-15T10:30:00.00Z",
      "identities": [
        "max@example.com",
        "max@external.com"
      ],
      "tags": [
        {
          "key": "role",
          "value": "admin"
        }
      ]
    }
  ],
  "groups": [
    {
      "name": "group001",
      "id": "g001",
      "group_unique_id": "g001",
      "group_type": "Security",
      "identities": [
        "group001@example.com"
      ],
      "tags": [
        {
          "key": "team",
          "value": "Platform"
        }
      ],
      "custom_properties": {
        "is_security_group": true
      }
    },
    {
      "name": "group002",
      "id": "g002",
      "group_unique_id": "g002",
      "group_type": "Security",
      "identities": [
        "group002@example.com"
      ],
      "tags": [
        {
          "key": "team",
          "value": "Platform"
        }
      ],
      "custom_properties": {
        "is_security_group": true
      }
    },
    {
      "name": "group003",
      "id": "g003",
      "group_unique_id": "g003",
      "group_type": "Security",
      "parent_group": {
        "id": "parent01"
      },
      "identities": [
        "group003@example.com"
      ],
      "tags": [
        {
          "key": "team",
          "value": "Platform"
        }
      ],
      "custom_properties": {
        "is_security_group": true
      }
    },
    {
      "name": "parent_group",
      "id": "parent01",
      "group_unique_id": "parent01",
      "group_type": "Distribution"
    }
  ]
}
"""
