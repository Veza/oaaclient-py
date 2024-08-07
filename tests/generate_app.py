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
from oaaclient.templates import CustomApplication, Tag, OAAPermission, OAAPropertyType, LocalUserType

logging.basicConfig(format='%(asctime)s %(levelname)s: %(thread)d %(message)s', level=logging.INFO)
log = logging.getLogger(__name__)


def generate_app():
    """ generates a complete OAA custom application payload """

    app = CustomApplication(name="pytest generated app", application_type="pytest", description="This is a test")

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

    app.add_custom_permission("Manage_Thing", [OAAPermission.DataRead,
                                               OAAPermission.DataWrite,
                                              ],
                              resource_types=["thing"])

    app.add_custom_permission("Unknown Permission", [OAAPermission.Uncategorized])

    # define one property of every type
    app.property_definitions.define_local_user_property("is_guest", OAAPropertyType.BOOLEAN)
    app.property_definitions.define_local_user_property("user_id", OAAPropertyType.NUMBER)
    app.property_definitions.define_local_user_property("NAME", OAAPropertyType.STRING)
    app.property_definitions.define_local_user_property("peers", OAAPropertyType.STRING_LIST)
    app.property_definitions.define_local_user_property("birthday", OAAPropertyType.TIMESTAMP)

    username_list = ["bob", "marry", "sue", "rob"]
    for username in username_list:
        user = app.add_local_user(username)
        user.add_identity(f"{username}@example.com")
        # set all the properties to something
        user.email = f"{username}@example.com"
        user.is_active = True
        user.created_at = "2001-01-01T00:00:00.000Z"
        user.last_login_at = "2002-02-01T00:00:00.000Z"
        user.deactivated_at = "2003-03-01T00:00:00.000Z"
        user.password_last_changed_at = "2004-04-01T00:00:00.000Z"
        user.set_property("is_guest", False)
        user.set_property("user_id", username_list.index(username))
        user.set_property("NAME", username.swapcase())
        user.set_property("peers", username_list)
        user.set_property("birthday", "2000-01-01T00:00:00.000Z")

    app.local_users["marry"].is_active = False
    app.local_users["marry"].user_type = LocalUserType.Human

    bot_user = app.add_local_user("bot_user")
    bot_user.user_type = LocalUserType.ServiceAccount

    # groups
    app.property_definitions.define_local_group_property("group_id", OAAPropertyType.NUMBER)
    group1 = app.add_local_group("group1")
    group1.created_at = "2001-01-01T00:00:00.000Z"
    group1.set_property("group_id", 1)

    # mix case up to test case-insensitive dict
    app.local_users["BOB"].add_group("group1")
    app.local_users["maRRy"].add_group("group1")

    group2 = app.add_local_group("group2")
    group2.created_at = "2001-01-01T00:00:00.000Z"
    group2.set_property("group_id", 2)

    app.local_users["bob"].add_group("group2")
    app.local_users["marry"].add_group("group2")

    group3 = app.add_local_group("group3")
    group3.add_group("group1")
    group3.add_group("group2")
    app.local_users["rob"].add_group("group3")

    # idp identities
    idp_user1 = app.add_idp_identity("user01@example.com")

    # roles
    app.property_definitions.define_local_role_property("role_id", OAAPropertyType.NUMBER)
    app.property_definitions.define_local_role_property("custom", OAAPropertyType.BOOLEAN)

    app.property_definitions.define_role_assignment_property("approved", OAAPropertyType.BOOLEAN)
    app.property_definitions.define_role_assignment_property("approver", OAAPropertyType.STRING)

    role1 = app.add_local_role("role1", ["all", "Admin", "Manage_Thing"])
    role1.set_property("role_id", 1)
    role1.set_property("custom", False)

    role2 = app.add_local_role("role2")
    role2.add_permissions(["view"])
    role2.set_property("role_id", 1)
    role1.set_property("custom", True)

    role3 = app.add_local_role("role3")
    role3.add_permissions(["manage", "Unknown Permission"])
    role3.set_property("role_id", 3)
    role3.add_role("role2")

    app.add_local_role("empty_role")

    # resources
    app.property_definitions.define_resource_property("thing", "private", OAAPropertyType.BOOLEAN)
    app.property_definitions.define_resource_property("thing", "unique_id", OAAPropertyType.NUMBER)
    app.property_definitions.define_resource_property("thing", "hair_color", OAAPropertyType.STRING)
    app.property_definitions.define_resource_property("thing", "peers", OAAPropertyType.STRING_LIST)
    app.property_definitions.define_resource_property("thing", "publish_date", OAAPropertyType.TIMESTAMP)

    thing1 = app.add_resource("thing1", resource_type="thing", description="thing1")
    thing1.set_property("private", False)
    thing1.set_property("unique_id", 1)
    thing1.set_property("hair_color", "blue")
    thing1.set_property("peers", ["thing2", "thing3"])
    thing1.set_property("publish_date", "1959-03-12T00:00:00.000Z")
    thing1.add_tag("tag1", value="This is a value @,-_.")

    thing2 = app.add_resource("thing2", resource_type="thing")
    thing2.set_property("private", False)
    thing2.set_property("unique_id", 2)
    thing2.set_property("hair_color", "blue")
    thing2.set_property("peers", ["thing2", "thing3"])
    thing2.set_property("publish_date", "1959-03-12T00:00:00.000Z")

    cog1 = thing2.add_sub_resource("cog1", resource_type="cog")
    cog1.add_resource_connection("service_account@some-project.iam.gserviceaccount.com", "GoogleCloudServiceAccount")

    # authorizations
    app.local_users["bob"].add_role("role1", apply_to_application=True)
    app.local_users["sue"].add_role("role3", apply_to_application=True, assignment_properties={"approved": True, "approver": "bob"})
    app.local_groups["group2"].add_role("role2", resources=[thing1])
    app.local_users["marry"].add_permission("view", resources=[thing2, cog1])
    app.local_users["rob"].add_permission("manage", resources=[thing1], apply_to_application=True)

    app.idp_identities["user01@example.com"].add_role("role1", apply_to_application=True)

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
  app = generate_app()
  log.info("App loaded")
  try:
     log.info("Pushing")
     con.push_application(provider_name="Pytest Gen App", data_source_name="generate_app_main", application_object=app, create_provider=True)
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
GENERATED_APP_PAYLOAD = """
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
          "user_id": "NUMBER",
          "NAME": "STRING",
          "peers": "STRING_LIST",
          "birthday": "TIMESTAMP"
        },
        "local_group_properties": {
          "group_id": "NUMBER"
        },
        "local_role_properties": {
          "role_id": "NUMBER",
          "custom": "BOOLEAN"
        },
        "role_assignment_properties": {
          "approved": "BOOLEAN",
          "approver": "STRING"
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
      "name": "pytest generated app",
      "application_type": "pytest",
      "description": "This is a test",
      "local_users": [
        {
          "name": "bob",
          "email": "bob@example.com",
          "identities": [
            "bob@example.com"
          ],
          "groups": [
            "group1",
            "group2"
          ],
          "is_active": true,
          "created_at": "2001-01-01T00:00:00.000Z",
          "last_login_at": "2002-02-01T00:00:00.000Z",
          "deactivated_at": "2003-03-01T00:00:00.000Z",
          "password_last_changed_at": "2004-04-01T00:00:00.000Z",
          "custom_properties": {
            "is_guest": false,
            "user_id": 0,
            "NAME": "BOB",
            "peers": [
              "bob",
              "marry",
              "sue",
              "rob"
            ],
            "birthday": "2000-01-01T00:00:00.000Z"
          }
        },
        {
          "name": "marry",
          "email": "marry@example.com",
          "identities": [
            "marry@example.com"
          ],
          "groups": [
            "group1",
            "group2"
          ],
          "is_active": false,
          "created_at": "2001-01-01T00:00:00.000Z",
          "last_login_at": "2002-02-01T00:00:00.000Z",
          "deactivated_at": "2003-03-01T00:00:00.000Z",
          "password_last_changed_at": "2004-04-01T00:00:00.000Z",
          "user_type": "human",
          "custom_properties": {
            "is_guest": false,
            "user_id": 1,
            "NAME": "MARRY",
            "peers": [
              "bob",
              "marry",
              "sue",
              "rob"
            ],
            "birthday": "2000-01-01T00:00:00.000Z"
          }
        },
        {
          "name": "sue",
          "email": "sue@example.com",
          "identities": [
            "sue@example.com"
          ],
          "is_active": true,
          "created_at": "2001-01-01T00:00:00.000Z",
          "last_login_at": "2002-02-01T00:00:00.000Z",
          "deactivated_at": "2003-03-01T00:00:00.000Z",
          "password_last_changed_at": "2004-04-01T00:00:00.000Z",
          "custom_properties": {
            "is_guest": false,
            "user_id": 2,
            "NAME": "SUE",
            "peers": [
              "bob",
              "marry",
              "sue",
              "rob"
            ],
            "birthday": "2000-01-01T00:00:00.000Z"
          }
        },
        {
          "name": "rob",
          "email": "rob@example.com",
          "identities": [
            "rob@example.com"
          ],
          "groups": [
            "group3"
          ],
          "is_active": true,
          "created_at": "2001-01-01T00:00:00.000Z",
          "last_login_at": "2002-02-01T00:00:00.000Z",
          "deactivated_at": "2003-03-01T00:00:00.000Z",
          "password_last_changed_at": "2004-04-01T00:00:00.000Z",
          "custom_properties": {
            "is_guest": false,
            "user_id": 3,
            "NAME": "ROB",
            "peers": [
              "bob",
              "marry",
              "sue",
              "rob"
            ],
            "birthday": "2000-01-01T00:00:00.000Z"
          }
        },
        {
          "name": "bot_user",
          "user_type": "service_account"
        }
      ],
      "local_groups": [
        {
          "name": "group1",
          "created_at": "2001-01-01T00:00:00.000Z",
          "custom_properties": {
            "group_id": 1
          }
        },
        {
          "name": "group2",
          "created_at": "2001-01-01T00:00:00.000Z",
          "custom_properties": {
            "group_id": 2
          }
        },
        {
          "name": "group3",
          "groups": [
            "group1",
            "group2"
          ]
        }
      ],
      "local_roles": [
        {
          "name": "role1",
          "permissions": [
            "all",
            "Admin",
            "Manage_Thing"
          ],
          "roles": [],
          "tags": [],
          "custom_properties": {
            "role_id": 1,
            "custom": true
          }
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
          }
        },
        {
          "name": "role3",
          "permissions": [
            "manage",
            "Unknown Permission"
          ],
          "roles": [
            "role2"
          ],
          "tags": [],
          "custom_properties": {
            "role_id": 3
          }
        },
        {
          "name": "empty_role",
          "permissions": [],
          "roles": [],
          "tags": [],
          "custom_properties": {}
        }
      ],
      "local_access_creds": [],
      "tags": [],
      "custom_properties": {
        "version": "2022.2.2"
      },
      "resources": [
        {
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
          },
          "tags": [
            {
              "key": "tag1",
              "value": "This is a value @,-_."
            }
          ]
        },
        {
          "name": "thing2",
          "resource_type": "thing",
          "sub_resources": [
            {
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
    },
    {
      "name": "Manage_Thing",
      "permission_type": [
        "DataRead",
        "DataWrite"
      ],
      "apply_to_sub_resources": false,
      "resource_types": [
        "thing"
      ]
    },
    {
      "name": "Unknown Permission",
      "permission_type": [
        "Uncategorized"
      ],
      "apply_to_sub_resources": false,
      "resource_types": []
    }
  ],
  "identity_to_permissions": [
    {
      "identity": "bob",
      "identity_type": "local_user",
      "role_assignments": [
        {
          "application": "pytest generated app",
          "role": "role1",
          "apply_to_application": true
        }
      ]
    },
    {
      "identity": "marry",
      "identity_type": "local_user",
      "application_permissions": [
        {
          "application": "pytest generated app",
          "resources": [
            "thing2",
            "thing2.cog1"
          ],
          "permission": "view"
        }
      ]
    },
    {
      "identity": "sue",
      "identity_type": "local_user",
      "role_assignments": [
        {
          "application": "pytest generated app",
          "role": "role3",
          "apply_to_application": true,
          "custom_properties": {
            "approved": true,
            "approver": "bob"
          }
        }
      ]
    },
    {
      "identity": "rob",
      "identity_type": "local_user",
      "application_permissions": [
        {
          "application": "pytest generated app",
          "permission": "manage",
          "apply_to_application": true
        },
        {
          "application": "pytest generated app",
          "resources": [
            "thing1"
          ],
          "permission": "manage"
        }
      ]
    },
    {
      "identity": "group2",
      "identity_type": "local_group",
      "role_assignments": [
        {
          "application": "pytest generated app",
          "role": "role2",
          "apply_to_application": false,
          "resources": [
            "thing1"
          ]
        }
      ]
    },
    {
      "identity": "user01@example.com",
      "identity_type": "idp",
      "role_assignments": [
        {
          "application": "pytest generated app",
          "role": "role1",
          "apply_to_application": true
        }
      ]
    }
  ]
}
"""