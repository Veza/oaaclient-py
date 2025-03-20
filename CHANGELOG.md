# OAA Client Change Log

## v1.1.12
*  Add support for setting IDP user `identity_type` for identifying non-human identity (NHI) accounts. IDP User's attribute `identity_type` can be set using the `IdPUserIdentityType` enum. Accounts default to `HUMAN`.
   ```
    svc_account = idp.add_user("svc_01", "Service Account", "helpdesk@example.com", "svc_01")
    svc_account.identity_type = IdPUserIdentityType.NonHuman
    ```
* Add `update_provisioning_status` method to `OAAClient` class. Allows enabling provisioning source on providers that support is such as HRIS template providers.

## v1.1.11
* Add support for Custom IDP Apps functionality. Ability to define new `CustomIdPApp` as part of a `CustomIdPProvider` and assign `CustomIdPUser` and  `CustomIdPGroup` to the app.
* API timeout time in seconds can be set with environment variable `OAA_API_TIMEOUT`. If unset the default 300 seconds is used.
  ```
  export OAA_API_TIMEOUT=500
  ```

## v1.1.10
* Added support for Access Credentials entity type. Access Credentials can be used to represent non-user based access such as API keys or Application Integrations that have their own roles and permissions in the application. Access Credentials can be stand-alone or assigned to a local user.
  ```python
  access_cred_1 = app.add_access_cred("cred001", "Access Cred 001")
  access_cred_1.is_active = True
  access_cred_1.last_used_at = "2024-03-12T00:00:00.000Z"
  access_cred_1.add_role("some_role_id", apply_to_application=True)
  app.local_users["user001"].add_access_cred("cred001")
  ```
* Adds support for built in `email` property for Application Local Users. The `email` property can be set on a Local User after creating it.
  ```
  user = my_app.add_local_user(unique_id="123", name="My User")
  user.email = "my_email@example.com"
  ```

## v1.1.9
* Added ability to pass additional argument using `options` dictionary parameter to more methods in the `OAAClient`. Arguments will be passed to Veza during provider create API call and must be supported by Veza or an API error will be returned.
  * `OAAClient.push_application`
  * `OAAClient.push_medatadata`
  * `OAAClient.create_data_source`
* Support for automatic paging of Veza API calls that return `path_values` lists such as the query spec API


## v1.1.8
* Support for setting linked IdP types for HRIS submissions. Veza will automatically link employees to IdP users of the given type(s) when set. Set using `HRISSystem.add_idp_type()` and `IdPProviderType` enums.
  ```
  hris = HRISProvider("HRIS", hris_type="MyHRIS", url="example.com")
  hris.system.add_idp_type(IdPProviderType.OKTA)
  ```
* Added ability to pass additional arguments during Provider Creation API Call. Additional arguments can be passed as a dictionary to `Client.create_provider` using optional `options` parameter. Arguments will be passed to Veza during provider create API call and must be supported by Veza or an API error will be returned.

## v1.1.7
* Added support for creating OAA Provider as part of `OAAClient.push_application` by passing `create_provider=True` parameter. Will automatically create a new Provider with the `provider_name` if it does not exist
* Role Assignments now support setting custom properties. These properties must be defined using the `ApplicationPropertyDefinitions.define_role_assignment_property()` method. Properties can be set when adding a role to an identity with the `add_role` method.
* Changes to `utils.build_report` function to resolve issues from duplicate queries when updating existing reports.
* Preview - Support for HRIS template with `templates.HRISProvider`. Preview release and interfaces may change before final version.

## v1.1.6
* Tagging support for CustomIdP entities. IdP Users, Groups and Domains now support `.add_tag(key: str, value: str = "")` method to set the tag key and optional value.

## v1.1.5
* Added new canonical permission `Uncategorized` for Custom Applications to use when customer permission's canonical effect is not known.
* Added `OAAClient.api_patch(api_path:str, data: dict, params: dict = None)` call to support calling API PATCH operations.
* Added `OAACLient.utils.truncate_string` to truncate strings to specific character length matching Veza template validation. Specifically required when strings contain non-UTF-8 characters.
* `set_property` methods for entities now support optional `ignore_none` which will skip setting the property if the property value is `None`

## v1.1.4
* Added support for setting LocalUser "User Type" property. Property can be set by `LocalUser.user_type` property. The enum `LocalUserType` has been added for supported types of `Human` and `ServiceAccount`

## v1.1.3
* Minor fix for API retry to support latest Python requests version
* Removes validation that permissions and assignments are present before push to support identity only submissions

## v1.1.2
* Update to allowed characters for Tag keys. Tag keys can only contain numbers, letters and the _ character. `OAATemplateException` is raised for invalid characters in Tag key or value.
* `client.OAAClient` connection class now can automatically load OS environment values for `VEZA_URL` and `VEZA_API_KEY`
* Added debug logging to `client.OAAClient` API function to log detailed error response information if logging level is set to `DEBUG`.
* OAAClient version and calling platform details are included in API call headers as the User-Agent.

## v1.1.1
* `CustomApplication` and `CustomIdPProvider` have been updated to use a case insensitive dictionary from `dict` structure to store entity lists to be
  consistent with template behavior with unique identifiers. The following attributes have been updated:
    - `CustomApplication.local_users`
    - `CustomApplication.local_groups`
    - `CustomApplication.local_roles`
    - `CustomApplication.resources`
    - `CustomApplication.custom_permissions`
    - `CustomResource.sub_resources`
    - `CustomIdPProvider.users`
    - `CustomIdPProvider.groups`
* Property names are now validated when defined against allowed character pattern `^[a-z][a-z_]*$`
* Fix for `OAAClient.get_reports` to support filtering for inactive reports
* Add support for nested roles. Child roles can be added to the parent by their identifier using the `LocalRole.add_role` function.
* `OAAResponseError` exception now contains additional properties `request_id` and `timestamp` to aid in troubleshooting
* `OAAClient.api_post` and `OAAClient.api_put` functions will automatically paginate response if necessary to return all results.
* Fix for API HTTP methods for parameter encoding for safe characters

## v1.1.0
* New functions in `OAAClient` for managing Veza Queries and Reports. See function doc strings for usage.
  * `get_queries`
  * `get_query_by_id`
  * `create_query`
  * `delete_query`
  * `get_reports`
  * `get_report_by_id`
  * `create_report`
  * `update_report`
  * `add_query_report`
  * `delete_report`
* New `utils` method `build_report` to populate a Veza Report and Quires from a dictionary containing the report and query definitions. See function docstring for more details.
* Package provides new CLI command `oaaclient-report-builder` to load a report file directory from JSON file from the command line.

## v1.0.4
* Added `__str__` and `__repr__` functions to the template classes to help with debugging and simplify printing log/status messages as needed.
* IdP now supports nested groups. A group can be added to a parent group by using the `CustomIdPGroup.add_groups()` function.

## v1.0.3
* Automatic API retries for connection errors
* New exceptions `OAAResponseError`, `OAAConnectionError` that extend the base exception `OAAClientError`
  * `OAAResponseError` raised for API calls that result in an error being returned from Veza
  * `OAAConnectionError` raised for API calls that can't complete (for network and other connection errors)
* Use new paging and filtering in Veza APIs to improve performance
  * `api_get` automatically processes paginated responses to get all entities. Will return a list of entities or a single value based on API response
  * `api_post` will automatically unwrap API response and result `result` or `results` value from API response.
* Provider and Data Source names are now checked for invalid characters in create functions before API call.

## v1.0.2
* `CustomIdPProvider.users` and `CustomerIdPProvider.groups` dictionaries are now keyed by user/group identity (if provided) to prevent duplicate name collisions. To reference a user or group from the map after creation, use the "identity" value. If an identity is not provided, "name" is used for both identity and key.

## v1.0.1
* Added support for resource unique identifier separate from `name`.
  * `add_resource` and `add_sub_resource` functions allow new optional property `unique_id`
  * `name` remains required but does not need to be unique for the entity type when using `unique_id`
  * When `unique_id` is provided it will serve as the key for the resource in the `.resources` and `.sub_resources` dictionaries
  * To use `unique_id` all resources must use `unique_id`
  * When using `unique_id` name does not need to be unique for a resource
* Duplicate LocalRole permissions are removed before payload generation
* Optimization to payload size for unset entities
* Fix for boolean local user properties in payload

## v1.0
* Release and package publication

## v0.9.11
* Documentation updates including README and docstrings for client and template functions.
* New sample `idp-import-csv.py` example for importing Custom IdP users from a CSV

## v0.9.10
* Payload compression is now enabled by default. Added more detailed logging and exception when prepared payload size will exceed 100MB.
* Added support for setting resource type list on `CustomPermission`. When permission is part of a role the permission will only be used when the role is applied if resource type is in this list. The resource type list can be specified when the permissions is created:
  ```
  CustomApplication.add_custom_permission(self, name: str, permissions: list[OAAPermission], apply_to_sub_resources: bool = False, resource_types: list = None)
  ```
* Update the tag and tag validation regex

## v0.9.9
* `custom_app.add_idp_idententiy` is now `custom_app.add_idp_identity`
* Docstring and README improvements
* Improvements to OAAClientError exceptions raised when API returns errors and additional test cases
* Changes to reduce OAA payload size during transfer.
  * Removed unset/default values from payload
  * Option to enable GZIP compression of payload
  * Structure for identity to resource permissions
* Automatically trim trailing slashes from Veza URL for `Client` connection

## v0.9.8
* Initial release of oaaclient as Python Package

## 2022/07/14
* Users, groups and roles can now be created and referenced by a unique identifier separte from `name`.
  * `add_local_user`, `add_local_group` and `add_local_role` functions all have new optional property `unique_id`
  * When `unique_id` is passed the entity will be created with the unique identifier in addition to name
  * When using unique identifiers the `unique_id` value will be used as the key in the `local_users`, `local_groups` and `local_roles` dictionaries
  * Must use unique identifier for references between entities such as `add_group` and `add_role`
  * To use `unique_id` all local users, local groups and local roles must have a unique identifier in addition to name

## 2022/07/01
* Added support for setting OAA Provider Icons via `Client.update_provider_icon` function.
* Added `utils.encode_icon_file()` function to assist with base64 encoding icon files

## 2022/06/23
* Added `client.delete_provider()` and `client.delete_data_source()` functions

## 2022/05/25
* Added support to CustomApplication template for nested groups, local groups can be added to another local group with `.add_group(group: str)` operation
* Added support to CustomIdP for groups to have a list of AWS roles that members can assume. Role can be added to a group with `.add_assumed_role_arns([arns])`
* Added support to CustomApplication resources and sub-resources for connections to outside entities in the graph.
* Extended supported characters for Tag values to include letters, numbers and specials characters `.,_@`
* Updated client `get_provier()` and `get_data_source()` operations to perform case insensitive search of existing entities

## 2022/05/03
* Moved `OAAPermission` and `OAAIdentityType` enums to `templates`, any import statements will need to be updated

## 2022/04/26
*   Added `CustomIdPUser.set_source_identity` for setting the source identity of a user. Also added new enum
    `IdPProviderType` for supported IdP providers.

## 2022/4/18
* `CookiePermission` has been renamed to `OAAPermission`, any references will need to be updated.
* `CookieIdentityType` has been renamed to `OAAIdentityType`, any references will need to be updated.
* `OAAClient.__init__` now takes in `api_key` as authorization parameter, `token` remains as an optional parameter for backwards compatibility. Raises `OAAClientError` if neither `api_key` or `token` are set.

## 2022/4/6
* Added `templates.CustomIdPProvider` to support OAA Custom Identity Provider template. See Samples directory for example.

## 2022/3/22
* The `CustomApplication` class now supports [custom entity properties](https://docs.veza.com/api/oaa/custom-properties) introduced in Veza `2022.2.2`.
  - Any applications that utilized `dynamic_properties` (`One`, `Two`, `Three` etc.) will need to be updated to use the latest SDK

  Old method:
  ```python
  app_instance.local_users['username'].property["One"] = "id:123"
  ```

  Updated method:
  ```python
  # first define custom property
  app_instance.property_definitions.define_local_user_property("id", OAAPropertyType.NUMBER)
  # set property on user
  app_instance.local_users['username'].set_property("id", 123)
  ```

  Available property types:
  * BOOLEAN
  * NUMBER
  * STRING
  * STRING_LIST
  * TIMESTAMP (RFC3339 formatted string)
