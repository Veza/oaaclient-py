#!/usr/bin/env python3
"""
Copyright 2022 Veza Technologies Inc.

Use of this source code is governed by the MIT
license that can be found in the LICENSE file or at
https://opensource.org/licenses/MIT.
"""

import logging
import sys
from enum import unique

from oaaclient.client import OAAClient, OAAClientError
from oaaclient.templates import CustomApplication, OAAPermission, OAAPropertyType

logging.basicConfig(format='%(asctime)s %(levelname)s: %(thread)d %(message)s', level=logging.INFO)
log = logging.getLogger(__name__)


def generate_app_id_mapping():
    """ generates a complete OAA custom application payload where local users, groups and roles are mapped by a unique identifier"""

    app = CustomApplication(name="pytest unique id app", application_type="pytest", description="This is a test")

    app.property_definitions.define_application_property("version", OAAPropertyType.STRING)
    app.set_property("version", "2022.2.2")

    app.add_custom_permission("all", [OAAPermission.DataRead,
                                      OAAPermission.DataWrite,
                                      OAAPermission.DataCreate,
                                      OAAPermission.DataDelete,
                                      OAAPermission.MetadataRead,
                                      OAAPermission.MetadataWrite,
                                      OAAPermission.MetadataCreate,
                                      OAAPermission.MetadataDelete,
                                      OAAPermission.NonData
                                      ]
                              )
    app.add_custom_permission("Admin", [OAAPermission.DataRead,
                                        OAAPermission.DataWrite,
                                        OAAPermission.MetadataRead,
                                        OAAPermission.MetadataWrite,
                                        OAAPermission.NonData
                                        ],
                              apply_to_sub_resources=True
                              )
    app.add_custom_permission("Manage", [OAAPermission.DataRead,
                                         OAAPermission.DataWrite,
                                         OAAPermission.MetadataRead,
                                         OAAPermission.MetadataWrite,
                                         OAAPermission.NonData
                                         ]
                              )
    app.add_custom_permission("View", [OAAPermission.DataRead,
                                       OAAPermission.MetadataRead,
                                       ]
                              )

    # define one property of every type
    app.property_definitions.define_local_user_property("is_guest", OAAPropertyType.BOOLEAN)
    app.property_definitions.define_local_user_property("birthday", OAAPropertyType.TIMESTAMP)

    user_list = [{"name": "Megan", "id": 1234},
                 {"name": "Scott", "id": 1235},
                 {"name": "Amanda", "id": 1236},
                 {"name": "Paul", "id": 1237}
                 ]

    for user_info in user_list:
        user_name = user_info["name"]
        user_id = user_info["id"]
        user = app.add_local_user(name=user_name, unique_id=user_id)
        user.add_identity(f"{user_name}@example.com")
        # set all the properties to something
        user.is_active = True
        user.created_at = "2001-01-01T00:00:00.000Z"
        user.last_login_at = "2002-02-01T00:00:00.000Z"
        user.deactivated_at = "2003-03-01T00:00:00.000Z"
        user.password_last_changed_at = "2004-04-01T00:00:00.000Z"
        user.set_property("is_guest", False)
        user.set_property("birthday", "2000-01-01T00:00:00.000Z")

    # groups
    app.property_definitions.define_local_group_property("group_id", OAAPropertyType.NUMBER)
    group1 = app.add_local_group("group1", unique_id="g1")
    group1.created_at = "2001-01-01T00:00:00.000Z"
    group1.set_property("group_id", 1)

    app.local_users[1234].add_group("g1")
    app.local_users[1235].add_group("g1")

    group2 = app.add_local_group("group2", unique_id="g2")
    group2.created_at = "2001-01-01T00:00:00.000Z"
    group2.set_property("group_id", 2)

    app.local_users[1235].add_group("g2")
    app.local_users[1237].add_group("g2")

    group3 = app.add_local_group("group3", unique_id="g3")
    group3.add_group("g1")
    group3.add_group("g2")
    app.local_users[1236].add_group("g3")

    # roles
    app.property_definitions.define_local_role_property("role_id", OAAPropertyType.NUMBER)
    app.property_definitions.define_local_role_property("custom", OAAPropertyType.BOOLEAN)

    role1 = app.add_local_role("role1", unique_id="r1",  permissions=["all", "Admin"])
    role1.set_property("role_id", 1)
    role1.set_property("custom", False)

    role2 = app.add_local_role("role2", unique_id="r2", permissions=["view"])
    role2.set_property("role_id", 1)
    role1.set_property("custom", True)

    # resources
    app.property_definitions.define_resource_property("thing", "private", OAAPropertyType.BOOLEAN)
    app.property_definitions.define_resource_property("thing", "unique_id", OAAPropertyType.NUMBER)
    app.property_definitions.define_resource_property("thing", "hair_color", OAAPropertyType.STRING)
    app.property_definitions.define_resource_property("thing", "peers", OAAPropertyType.STRING_LIST)
    app.property_definitions.define_resource_property("thing", "publish_date", OAAPropertyType.TIMESTAMP)

    thing1 = app.add_resource("thing1", unique_id="t1", resource_type="thing", description="thing1")
    thing1.set_property("private", False)
    thing1.set_property("unique_id", 1)
    thing1.set_property("hair_color", "blue")
    thing1.set_property("peers", ["thing2", "thing3"])
    thing1.set_property("publish_date", "1959-03-12T00:00:00.000Z")

    thing2 = app.add_resource("thing2", unique_id="t2", resource_type="thing")
    thing2.set_property("private", False)
    thing2.set_property("unique_id", 2)
    thing2.set_property("hair_color", "blue")
    thing2.set_property("peers", ["thing2", "thing3"])
    thing2.set_property("publish_date", "1959-03-12T00:00:00.000Z")

    cog1 = thing2.add_sub_resource("cog1", unique_id="c1", resource_type="cog")
    cog1.add_resource_connection("service_account@some-project.iam.gserviceaccount.com", "GoogleCloudServiceAccount")

    # authorizations
    app.local_users[1235].add_role("r1", apply_to_application=True)
    app.local_groups["g2"].add_role("r2", resources=[thing1])
    app.local_users[1236].add_permission("view", resources=[thing2, cog1])
    app.local_users[1237].add_permission("manage", resources=[thing1], apply_to_application=True)


    app.property_definitions.define_access_cred_property("is_oauth", OAAPropertyType.BOOLEAN)
    app.property_definitions.define_access_cred_property("generation", OAAPropertyType.STRING)

    access_cred_1 = app.add_access_cred("cred001", "Access Cred 001")
    access_cred_1.is_active = True
    access_cred_1.can_expire = True
    access_cred_1.last_used_at = "2024-03-12T00:00:00.000Z"
    access_cred_1.created_at = "2023-01-03T00:00:00.000Z"
    access_cred_1.expires_at = "2040-04-15T00:00:00.000Z"
    access_cred_1.set_property("is_oauth", False)
    access_cred_1.set_property("generation", "v2")
    access_cred_1.add_role("r1", apply_to_application=True)

    access_cred_2 = app.add_access_cred("cred002", "Access Cred 002")
    access_cred_2.is_active = False
    access_cred_2.can_expire = True
    access_cred_2.last_used_at = "2024-03-12T00:00:00.000Z"
    access_cred_2.created_at = "2023-01-03T00:00:00.000Z"
    access_cred_2.expires_at = "2040-04-15T00:00:00.000Z"
    access_cred_2.set_property("is_oauth", True)
    access_cred_2.set_property("generation", "v3")
    access_cred_2.add_role("r2", resources=[cog1])

    app.local_users[1234].add_access_cred("cred002")

    access_cred_3 = app.add_access_cred("cred003", "Access Cred 003")
    access_cred_3.add_permission("Admin", apply_to_application=True)

    return app

def main():
  log.info("Generate App Main")
  # assumes VEZA_URL and VEZA_API_KEY are set in env
  try:
    con = OAAClient()
  except (OAAClientError, ValueError) as e:
     log.error(e)
     log.error("exiting")
     sys.exit(1)

  log.info("Connected to tenant")
  app = generate_app_id_mapping()
  log.info("App loaded")
  try:
     log.info("Pushing")
     con.push_application(provider_name="App ID Mapping", data_source_name="generate_app_id_mapping", application_object=app, create_provider=True)
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


# Full App payload as string
GENERATED_APP_ID_MAPPINGS_PAYLOAD = """
{
  "custom_property_definition": {
    "applications": [
      {
        "application_type": "pytest",
        "application_properties": {
          "version": "STRING"
        },
        "local_user_properties": {
          "is_guest": "BOOLEAN",
          "birthday": "TIMESTAMP"
        },
        "local_group_properties": {
          "group_id": "NUMBER"
        },
        "local_role_properties": {
          "role_id": "NUMBER",
          "custom": "BOOLEAN"
        },
        "local_access_creds_properties": {
          "is_oauth": "BOOLEAN",
          "generation": "STRING"
        },
        "resources": [
          {
            "resource_type": "thing",
            "properties": {
              "private": "BOOLEAN",
              "unique_id": "NUMBER",
              "hair_color": "STRING",
              "peers": "STRING_LIST",
              "publish_date": "TIMESTAMP"
            }
          }
        ]
      }
    ]
  },
  "applications": [
    {
      "name": "pytest unique id app",
      "application_type": "pytest",
      "description": "This is a test",
      "local_users": [
        {
          "name": "Megan",
          "identities": [
            "Megan@example.com"
          ],
          "groups": [
            "g1"
          ],
          "access_creds": [
            "cred002"
          ],
          "is_active": true,
          "created_at": "2001-01-01T00:00:00.000Z",
          "last_login_at": "2002-02-01T00:00:00.000Z",
          "deactivated_at": "2003-03-01T00:00:00.000Z",
          "password_last_changed_at": "2004-04-01T00:00:00.000Z",
          "custom_properties": {
            "is_guest": false,
            "birthday": "2000-01-01T00:00:00.000Z"
          },
          "id": "1234"
        },
        {
          "name": "Scott",
          "identities": [
            "Scott@example.com"
          ],
          "groups": [
            "g1",
            "g2"
          ],
          "is_active": true,
          "created_at": "2001-01-01T00:00:00.000Z",
          "last_login_at": "2002-02-01T00:00:00.000Z",
          "deactivated_at": "2003-03-01T00:00:00.000Z",
          "password_last_changed_at": "2004-04-01T00:00:00.000Z",
          "custom_properties": {
            "is_guest": false,
            "birthday": "2000-01-01T00:00:00.000Z"
          },
          "id": "1235"
        },
        {
          "name": "Amanda",
          "identities": [
            "Amanda@example.com"
          ],
          "groups": [
            "g3"
          ],
          "is_active": true,
          "created_at": "2001-01-01T00:00:00.000Z",
          "last_login_at": "2002-02-01T00:00:00.000Z",
          "deactivated_at": "2003-03-01T00:00:00.000Z",
          "password_last_changed_at": "2004-04-01T00:00:00.000Z",
          "custom_properties": {
            "is_guest": false,
            "birthday": "2000-01-01T00:00:00.000Z"
          },
          "id": "1236"
        },
        {
          "name": "Paul",
          "identities": [
            "Paul@example.com"
          ],
          "groups": [
            "g2"
          ],
          "is_active": true,
          "created_at": "2001-01-01T00:00:00.000Z",
          "last_login_at": "2002-02-01T00:00:00.000Z",
          "deactivated_at": "2003-03-01T00:00:00.000Z",
          "password_last_changed_at": "2004-04-01T00:00:00.000Z",
          "custom_properties": {
            "is_guest": false,
            "birthday": "2000-01-01T00:00:00.000Z"
          },
          "id": "1237"
        }
      ],
      "local_groups": [
        {
          "name": "group1",
          "created_at": "2001-01-01T00:00:00.000Z",
          "custom_properties": {
            "group_id": 1
          },
          "id": "g1"
        },
        {
          "name": "group2",
          "created_at": "2001-01-01T00:00:00.000Z",
          "custom_properties": {
            "group_id": 2
          },
          "id": "g2"
        },
        {
          "name": "group3",
          "groups": [
            "g1",
            "g2"
          ],
          "id": "g3"
        }
      ],
      "local_roles": [
        {
          "name": "role1",
          "permissions": [
            "all",
            "Admin"
          ],
          "roles": [],
          "tags": [],
          "custom_properties": {
            "role_id": 1,
            "custom": true
          },
          "id": "r1"
        },
        {
          "name": "role2",
          "permissions": [
            "view"
          ],
          "roles": [],
          "tags": [],
          "custom_properties": {
            "role_id": 1
          },
          "id": "r2"
        }
      ],
      "local_access_creds": [
        {
          "id": "cred001",
          "name": "Access Cred 001",
          "is_active": true,
          "created_at": "2023-01-03T00:00:00.000Z",
          "expires_at": "2040-04-15T00:00:00.000Z",
          "last_used_at": "2024-03-12T00:00:00.000Z",
          "can_expire": true,
          "custom_properties": {
            "is_oauth": false,
            "generation": "v2"
          }
        },
        {
          "id": "cred002",
          "name": "Access Cred 002",
          "is_active": false,
          "created_at": "2023-01-03T00:00:00.000Z",
          "expires_at": "2040-04-15T00:00:00.000Z",
          "last_used_at": "2024-03-12T00:00:00.000Z",
          "can_expire": true,
          "custom_properties": {
            "is_oauth": true,
            "generation": "v3"
          }
        },
        {
          "id": "cred003",
          "name": "Access Cred 003",
          "is_active": true
        }
      ],
      "tags": [],
      "custom_properties": {
        "version": "2022.2.2"
      },
      "resources": [
        {
          "id": "t1",
          "name": "thing1",
          "resource_type": "thing",
          "description": "thing1",
          "custom_properties": {
            "private": false,
            "unique_id": 1,
            "hair_color": "blue",
            "peers": [
              "thing2",
              "thing3"
            ],
            "publish_date": "1959-03-12T00:00:00.000Z"
          }
        },
        {
          "id": "t2",
          "name": "thing2",
          "resource_type": "thing",
          "sub_resources": [
            {
              "id": "c1",
              "name": "cog1",
              "resource_type": "cog",
              "connections": [
                {
                  "id": "service_account@some-project.iam.gserviceaccount.com",
                  "node_type": "GoogleCloudServiceAccount"
                }
              ]
            }
          ],
          "custom_properties": {
            "private": false,
            "unique_id": 2,
            "hair_color": "blue",
            "peers": [
              "thing2",
              "thing3"
            ],
            "publish_date": "1959-03-12T00:00:00.000Z"
          }
        }
      ]
    }
  ],
  "permissions": [
    {
      "name": "all",
      "permission_type": [
        "DataRead",
        "DataWrite",
        "DataCreate",
        "DataDelete",
        "MetadataRead",
        "MetadataWrite",
        "MetadataCreate",
        "MetadataDelete",
        "NonData"
      ],
      "apply_to_sub_resources": false,
      "resource_types": []
    },
    {
      "name": "Admin",
      "permission_type": [
        "DataRead",
        "DataWrite",
        "MetadataRead",
        "MetadataWrite",
        "NonData"
      ],
      "apply_to_sub_resources": true,
      "resource_types": []
    },
    {
      "name": "Manage",
      "permission_type": [
        "DataRead",
        "DataWrite",
        "MetadataRead",
        "MetadataWrite",
        "NonData"
      ],
      "apply_to_sub_resources": false,
      "resource_types": []
    },
    {
      "name": "View",
      "permission_type": [
        "DataRead",
        "MetadataRead"
      ],
      "apply_to_sub_resources": false,
      "resource_types": []
    }
  ],
  "identity_to_permissions": [
    {
      "identity": "1235",
      "identity_type": "local_user",
      "role_assignments": [
        {
          "application": "pytest unique id app",
          "role": "r1",
          "apply_to_application": true
        }
      ]
    },
    {
      "identity": "1236",
      "identity_type": "local_user",
      "application_permissions": [
        {
          "application": "pytest unique id app",
          "resources": [
            "t2",
            "t2.c1"
          ],
          "permission": "view"
        }
      ]
    },
    {
      "identity": "1237",
      "identity_type": "local_user",
      "application_permissions": [
        {
          "application": "pytest unique id app",
          "permission": "manage",
          "apply_to_application": true
        },
        {
          "application": "pytest unique id app",
          "resources": [
            "t1"
          ],
          "permission": "manage"
        }
      ]
    },
    {
      "identity": "g2",
      "identity_type": "local_group",
      "role_assignments": [
        {
          "application": "pytest unique id app",
          "role": "r2",
          "apply_to_application": false,
          "resources": [
            "t1"
          ]
        }
      ]
    },
    {
      "identity": "cred001",
      "identity_type": "local_access_creds",
      "role_assignments": [
        {
          "application": "pytest unique id app",
          "role": "r1",
          "apply_to_application": true
        }
      ]
    },
    {
      "identity": "cred002",
      "identity_type": "local_access_creds",
      "role_assignments": [
        {
          "application": "pytest unique id app",
          "role": "r2",
          "apply_to_application": false,
          "resources": [
            "t2.c1"
          ]
        }
      ]
    },
    {
      "identity": "cred003",
      "identity_type": "local_access_creds",
      "application_permissions": [
        {
          "application": "pytest unique id app",
          "permission": "Admin",
          "apply_to_application": true
        }
      ]
    }
  ]
}
"""
