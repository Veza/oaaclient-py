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
from oaaclient.templates import HostGranteeType, HostIdentityType, HostProvider, OAAPermission, OAAPropertyType

logging.basicConfig(format='%(asctime)s %(levelname)s: %(thread)d %(message)s', level=logging.INFO)
log = logging.getLogger(__name__)


def generate_host() -> HostProvider:
    """ Generates a complete Host provider using the centralized collection model """

    host_provider = HostProvider(host_type="linux")
    host_provider.add_environment(unique_id="prod-linux-fleet", name="Production Linux Fleet", description="Pytest fleet", identity_provider_types=["okta"])

    host_provider.property_definitions.define_host_property("region", OAAPropertyType.STRING)
    host_provider.property_definitions.define_user_property("shell", OAAPropertyType.STRING)
    host_provider.property_definitions.define_group_property("is_admin_group", OAAPropertyType.BOOLEAN)
    host_provider.property_definitions.define_resource_property("port", OAAPropertyType.NUMBER)

    host_provider.add_privilege(name="sudo_all", privilege_type=[OAAPermission.DataRead, OAAPermission.DataWrite], description="Full sudo access")
    host_provider.add_privilege(name="service_restart", privilege_type=[OAAPermission.MetadataWrite])

    host = host_provider.add_host(unique_id="web-01", name="web-01.prod.example.com")
    host.platform = "linux"
    host.version = "Ubuntu 22.04.4 LTS"
    host.ip_address = "10.0.1.11"
    host.set_property("region", "us-east-1")

    root = host.add_user(unique_id="root", name="root", is_local=True, is_active=True, identity_type=HostIdentityType.NONHUMAN, last_login_at="2026-09-01T00:00:00Z")
    root.set_property("shell", "/bin/bash")

    host.add_user(unique_id="svc_deploy", name="svc_deploy", is_local=True, is_active=True, identity_type=HostIdentityType.NONHUMAN)

    jsmith = host.add_user(unique_id="jsmith", name="J Smith", is_local=False, identities=["jsmith@example.com"], is_active=True, identity_type=HostIdentityType.HUMAN)

    wheel = host.add_group(unique_id="wheel", name="wheel", group_type="local", is_local=True)
    wheel.set_property("is_admin_group", True)
    root.add_group("wheel")
    jsmith.add_group("wheel")

    admins = host.add_group(unique_id="admins", name="admins", group_type="directory", is_local=False, identities=["admins@example.com"])
    admins.add_member_group("wheel", is_local=True)

    ssh_key = host.add_credential(unique_id="root_ssh_key", name="root SSH key", credential_type="ssh_key", assumes_user="root", created_at="2026-01-01T00:00:00Z", last_used_at="2026-09-01T00:00:00Z", is_active=True, can_expire=False)
    ssh_key.add_holder("jsmith@example.com", is_local=False)
    ssh_key.add_holder("dcooper@example.com", is_local=False)

    nginx = host.add_resource(unique_id="nginx", name="nginx", resource_type="service")
    nginx.set_property("port", 443)

    host.add_grant(principal_id="root", grantee_type=HostGranteeType.USER, is_local=True, privileges=["sudo_all"], apply_to_host=True)
    host.add_grant(principal_id="svc_deploy", grantee_type=HostGranteeType.USER, is_local=True, privileges=[{"name": "service_restart", "no_password": True}], resources=[nginx])
    # second call for the same principal merges into the existing grant instead of creating a new one
    host.add_grant(principal_id="svc_deploy", grantee_type=HostGranteeType.USER, is_local=True, resources=["service.nginx"])
    host.add_grant(principal_id="admins", grantee_type=HostGranteeType.GROUP, is_local=False, privileges=["sudo_all"], apply_to_host=True)

    return host_provider


def main() -> None:
    log.info("Generate Host Main")
    # assumes VEZA_URL and VEZA_API_KEY are set in env
    try:
        con = OAAClient()
    except (OAAClientError, ValueError) as e:
        log.error(e)
        log.error("exiting")
        sys.exit(1)

    log.info("Connected to tenant")
    host_provider = generate_host()
    log.info("Host fleet loaded")
    try:
        log.info("Pushing")
        con.push_application(provider_name="Pytest Gen Host", data_source_name="generate_host_main", application_object=host_provider, create_provider=True)
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


GENERATED_HOST_PAYLOAD = """
{
  "host_type": "linux",
  "custom_property_definition": {
    "host_properties": {
      "region": "STRING"
    },
    "user_properties": {
      "shell": "STRING"
    },
    "group_properties": {
      "is_admin_group": "BOOLEAN"
    },
    "resource_properties": {
      "port": "NUMBER"
    }
  },
  "privileges": [
    {
      "name": "sudo_all",
      "description": "Full sudo access",
      "privilege_type": [
        "DataRead",
        "DataWrite"
      ]
    },
    {
      "name": "service_restart",
      "privilege_type": [
        "MetadataWrite"
      ]
    }
  ],
  "hosts": [
    {
      "id": "web-01",
      "name": "web-01.prod.example.com",
      "platform": "linux",
      "version": "Ubuntu 22.04.4 LTS",
      "ip_address": "10.0.1.11",
      "custom_properties": {
        "region": "us-east-1"
      },
      "users": [
        {
          "id": "root",
          "name": "root",
          "is_local": true,
          "identity_type": "nonhuman",
          "is_active": true,
          "last_login_at": "2026-09-01T00:00:00Z",
          "custom_properties": {
            "shell": "/bin/bash"
          },
          "groups": [
            {
              "id": "wheel"
            }
          ]
        },
        {
          "id": "svc_deploy",
          "name": "svc_deploy",
          "is_local": true,
          "identity_type": "nonhuman",
          "is_active": true
        },
        {
          "id": "jsmith",
          "name": "J Smith",
          "identities": [
            "jsmith@example.com"
          ],
          "is_local": false,
          "identity_type": "human",
          "is_active": true,
          "groups": [
            {
              "id": "wheel"
            }
          ]
        }
      ],
      "groups": [
        {
          "id": "wheel",
          "name": "wheel",
          "group_type": "local",
          "is_local": true,
          "custom_properties": {
            "is_admin_group": true
          }
        },
        {
          "id": "admins",
          "name": "admins",
          "group_type": "directory",
          "is_local": false,
          "identities": [
            "admins@example.com"
          ],
          "member_groups": [
            {
              "id": "wheel",
              "is_local": true
            }
          ]
        }
      ],
      "credentials": [
        {
          "id": "root_ssh_key",
          "name": "root SSH key",
          "credential_type": "ssh_key",
          "holders": [
            {
              "id": "jsmith@example.com",
              "is_local": false
            },
            {
              "id": "dcooper@example.com",
              "is_local": false
            }
          ],
          "created_at": "2026-01-01T00:00:00Z",
          "last_used_at": "2026-09-01T00:00:00Z",
          "is_active": true,
          "can_expire": false,
          "assumes_user": {
            "id": "root"
          }
        }
      ],
      "resources": [
        {
          "id": "nginx",
          "name": "nginx",
          "resource_type": "service",
          "custom_properties": {
            "port": 443
          }
        }
      ],
      "identity_to_privileges": [
        {
          "id": "root",
          "grantee_type": "user",
          "is_local": true,
          "privileges": [
            "sudo_all"
          ],
          "apply_to_host": true
        },
        {
          "id": "svc_deploy",
          "grantee_type": "user",
          "is_local": true,
          "privileges": [
            {
              "name": "service_restart",
              "no_password": true
            }
          ],
          "resources": [
            "service.nginx"
          ]
        },
        {
          "id": "admins",
          "grantee_type": "group",
          "is_local": false,
          "privileges": [
            "sudo_all"
          ],
          "apply_to_host": true
        }
      ]
    }
  ],
  "environment": {
    "id": "prod-linux-fleet",
    "name": "Production Linux Fleet",
    "description": "Pytest fleet",
    "identity_provider_types": [
      "okta"
    ]
  }
}
"""
