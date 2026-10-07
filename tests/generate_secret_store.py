#!/usr/bin/env python3
"""
Copyright 2026 Veza Technologies Inc.

Use of this source code is governed by the MIT
license that can be found in the LICENSE file or at
https://opensource.org/licenses/MIT.
"""

import json
import logging
import sys

from oaaclient.client import OAAClient, OAAClientError
from oaaclient.templates import (
    IdentityMappingMode,
    IdentityMappingProperty,
    IdentityMappingType,
    OAAPermission,
    OAAPropertyType,
    SecretStoreSubmission,
)

logging.basicConfig(format='%(asctime)s %(levelname)s: %(thread)d %(message)s', level=logging.INFO)
log = logging.getLogger(__name__)


def generate_secret_store() -> SecretStoreSubmission:
    """Generates a complete Secret Store provider"""

    provider = SecretStoreSubmission(
        name="Pytest Secret Store",
        secret_store_type="hashicorp_vault",
        unique_id="test-vault-001"
    )

    # Define custom properties
    provider.property_definitions.define_secret_store_property("environment", OAAPropertyType.STRING)
    provider.property_definitions.define_vault_property("encryption_type", OAAPropertyType.STRING)
    provider.property_definitions.define_entry_property("rotation_enabled", OAAPropertyType.BOOLEAN)

    secret_store = provider.secret_store
    secret_store.description = "Test secret storage"

    # Set properties
    secret_store.set_property("environment", "test")
    secret_store.add_tag("department", "engineering")

    # Add permissions
    read_permission = secret_store.add_permission(
        name="Read",
        unique_id="perm-read",
        allow_identity_assume=False,
        permission_type=[OAAPermission.DataRead]
    )

    write_permission = secret_store.add_permission(
        name="Write",
        unique_id="perm-write",
        allow_identity_assume=False,
        permission_type=[OAAPermission.DataWrite]
    )

    admin_permission = secret_store.add_permission(
        name="Admin",
        unique_id="perm-admin",
        allow_identity_assume=False,
        permission_type=[OAAPermission.DataRead, OAAPermission.DataWrite, OAAPermission.DataDelete]
    )
    admin_permission.add_tag("level", "admin")

    decrypt_permission = secret_store.add_permission(
        name="Decrypt",
        unique_id="perm-decrypt",
        allow_identity_assume=True
    )
    decrypt_permission.add_permission_type(OAAPermission.DataRead)

    # Add vaults
    for i in range(1, 4):
        vault = secret_store.add_vault(
            name=f"Vault {i:02d}",
            vault_type="general",
            unique_id=f"vault-{i:02d}",
            description=f"Test vault {i}"
        )
        vault.set_property("encryption_type", "AES-256")
        vault.add_tag("vault_number", str(i))

        # Add entries to each vault
        for j in range(1, 3):
            entry = vault.add_entry(
                name=f"Entry {i}-{j}",
                unique_id=f"entry-{i:02d}-{j:02d}",
                description=f"Test entry {j} in vault {i}"
            )
            entry.set_property("rotation_enabled", j % 2 == 0)

            if i == 1 and j == 1:
                # Add identity to first entry
                entry.add_identity("OktaUser", "user@example.com")

    # Add identity to permission mappings
    admin_identity = secret_store.add_identity_to_permission(
        identity="admin-user",
        identity_type="CustomPrincipalUser"
    )
    admin_identity.add_permission_assignment(
        vault=["vault-01", "vault-02", "vault-03"],
        permissions=["perm-read", "perm-admin"]
    )

    developer_identity = secret_store.add_identity_to_permission(
        identity="dev-user",
        identity_type="CustomPrincipalUser"
    )
    developer_identity.add_permission_assignment(
        vault=["vault-01"],
        permissions=["perm-read", "perm-decrypt"]
    )

    # Configure identity mapping
    identity_mapping = provider.set_identity_mapping_configuration()
    mapping = identity_mapping.add_mapping(
        destination_datasource_type="OKTA",
        destination_datasource_oaa_type="",
        mapping_type=IdentityMappingType.EQUAL,
        mapping_mode=IdentityMappingMode.USERS,
    )
    mapping.add_property_matcher(
        source_property=IdentityMappingProperty.EMAIL,
        destination_property=IdentityMappingProperty.EMAIL,
    )

    return provider


GENERATED_SECRET_STORE_PAYLOAD = """
{
  "secret_store_type": "hashicorp_vault",
  "custom_property_definition": {
    "secret_store_properties": {
      "environment": "STRING"
    },
    "permission_properties": {},
    "vault_properties": {
      "encryption_type": "STRING"
    },
    "entry_properties": {
      "rotation_enabled": "BOOLEAN"
    }
  },
  "secret_store": {
    "name": "Pytest Secret Store",
    "id": "test-vault-001",
    "description": "Test secret storage",
    "tags": [
      {
        "key": "department",
        "value": "engineering"
      }
    ],
    "custom_properties": {
      "environment": "test"
    },
    "permissions": [
      {
        "name": "Read",
        "id": "perm-read",
        "allow_identity_assume": false,
        "permission_type": [
          "DataRead"
        ]
      },
      {
        "name": "Write",
        "id": "perm-write",
        "allow_identity_assume": false,
        "permission_type": [
          "DataWrite"
        ]
      },
      {
        "name": "Admin",
        "id": "perm-admin",
        "allow_identity_assume": false,
        "permission_type": [
          "DataRead",
          "DataWrite",
          "DataDelete"
        ],
        "tags": [
          {
            "key": "level",
            "value": "admin"
          }
        ]
      },
      {
        "name": "Decrypt",
        "id": "perm-decrypt",
        "allow_identity_assume": true,
        "permission_type": [
          "DataRead"
        ]
      }
    ],
    "secret_store_vaults": [
      {
        "name": "Vault 01",
        "id": "vault-01",
        "vault_type": "general",
        "description": "Test vault 1",
        "tags": [
          {
            "key": "vault_number",
            "value": "1"
          }
        ],
        "custom_properties": {
          "encryption_type": "AES-256"
        },
        "entries": [
          {
            "name": "Entry 1-1",
            "id": "entry-01-01",
            "description": "Test entry 1 in vault 1",
            "custom_properties": {
              "rotation_enabled": false
            },
            "identities": [
              {
                "type": "OktaUser",
                "external_id": "user@example.com"
              }
            ]
          },
          {
            "name": "Entry 1-2",
            "id": "entry-01-02",
            "description": "Test entry 2 in vault 1",
            "custom_properties": {
              "rotation_enabled": true
            }
          }
        ]
      },
      {
        "name": "Vault 02",
        "id": "vault-02",
        "vault_type": "general",
        "description": "Test vault 2",
        "tags": [
          {
            "key": "vault_number",
            "value": "2"
          }
        ],
        "custom_properties": {
          "encryption_type": "AES-256"
        },
        "entries": [
          {
            "name": "Entry 2-1",
            "id": "entry-02-01",
            "description": "Test entry 1 in vault 2",
            "custom_properties": {
              "rotation_enabled": false
            }
          },
          {
            "name": "Entry 2-2",
            "id": "entry-02-02",
            "description": "Test entry 2 in vault 2",
            "custom_properties": {
              "rotation_enabled": true
            }
          }
        ]
      },
      {
        "name": "Vault 03",
        "id": "vault-03",
        "vault_type": "general",
        "description": "Test vault 3",
        "tags": [
          {
            "key": "vault_number",
            "value": "3"
          }
        ],
        "custom_properties": {
          "encryption_type": "AES-256"
        },
        "entries": [
          {
            "name": "Entry 3-1",
            "id": "entry-03-01",
            "description": "Test entry 1 in vault 3",
            "custom_properties": {
              "rotation_enabled": false
            }
          },
          {
            "name": "Entry 3-2",
            "id": "entry-03-02",
            "description": "Test entry 2 in vault 3",
            "custom_properties": {
              "rotation_enabled": true
            }
          }
        ]
      }
    ],
    "identity_to_permissions": [
      {
        "identity": "admin-user",
        "identity_type": "CustomPrincipalUser",
        "permission_assignments": [
          {
            "vault": [
              "vault-01",
              "vault-02",
              "vault-03"
            ],
            "permissions": [
              "perm-read",
              "perm-admin"
            ]
          }
        ]
      },
      {
        "identity": "dev-user",
        "identity_type": "CustomPrincipalUser",
        "permission_assignments": [
          {
            "vault": [
              "vault-01"
            ],
            "permissions": [
              "perm-read",
              "perm-decrypt"
            ]
          }
        ]
      }
    ]
  },
  "identity_mapping_configuration": {
    "use_email": false,
    "mappings": [
      {
        "destination_datasource_type": "OKTA",
        "type": "EQUAL",
        "mode": "USERS",
        "property_matchers": [
          {
            "source_property": "EMAIL",
            "destination_property": "EMAIL"
          }
        ]
      }
    ]
  }
}
"""


def main() -> None:
    log.info("Generate Secret Store Main")
    # assumes VEZA_URL and VEZA_API_KEY are set in env
    try:
        con = OAAClient()
    except (OAAClientError, ValueError) as e:
        log.error(e)
        log.error("exiting")
        sys.exit(1)

    log.info("Connected to tenant")
    secret_vault = generate_secret_store()
    log.info("Secret Store loaded")

    provider_name = "SecretStore_test_push"
    data_source_name = "SecretStore_test_push"

    try:
        log.info("Pushing")
        response = con.push_application(provider_name=provider_name,
                                        data_source_name=data_source_name,
                                        application_object=secret_vault,
                                        create_provider=True)

        if response.get("warnings"):
            log.warning("Push succeeded with warnings:")
            for w in response.get("warnings", []):
                log.warning(w)
                print(w)
    except OAAClientError as e:
        log.error(f"{e.error}: {e.message} - {e.details}")

    log.info("Complete")


if __name__ == "__main__":
    main()
