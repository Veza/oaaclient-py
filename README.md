# Veza OAA Python SDK

The Veza oaaclient Python SDK simplifies the process of integrating wiht the Open Authorization API (OAA).

## Getting Started
```
# pip install oaaclient
```

## Developing Using the SDK

The `oaaclient` SDK consists of two main components:
  * `oaaclient.client` - handles Veza API communication. Uses API key for authentication.
  * `oaaclient.templates` - Contains the classes for modeling and generating OAA payload.

### Sample Workflow
```python
from oaaclient.client import OAAClient
from oaaclient.templates import CustomApplication, OAAPermission

# creates a connection class to communicate with Veza
veza_con = OAAClient(url=veza_url, token=veza_api_key)

# creates a new Custom Application model
custom_app = CustomApplication(name="Sample App", application_type="sample")
```

Once the `CustomApplication` class is instantiated you can access the public methods to add local users, groups and resources and the authorization between identities and resources.

```python
custom_app.add_custom_permission("owner", [OAAPermission.DataRead, OAAPermission.DataWrite])
jane = custom_app.add_local_user("jane", identities="jane@example.com")
resource1 = custom_app.add_resource(name="Resource 1", resource_type="thing")
jane.add_permission(permission="owner", resources=[resource1])
```

After all identities, permissions and resources have been modeled the client connection handles the final push to Veza

```python
veza_con.push_application(provider, data_source_name, application_object=custom_app)
```

For complete examples of how to use the `oaaclient` SDK see the [samples](https://github.com/veza/oaaclient-py/samples)
directory.

## Command Line Use

The oaaclient can also be used as a command line tool for pushing completed OAA payloads to Veza for testing and debugging.

To use as a command line tool create the follwing JSON files:
1. Provider - Name the provider and select a support OAA template. For list of supported templates see Veza documentation on Gitbook.

   ```json
   {
     "name": "ProviderName",
     "custom_template": "application"
   }
   ```

2. Authorization - Define the Veza host API key to use

     ```json
     {
       "host": "https://demo.vezacloud.com",
       "token": "ZXlKaGJHY2lPaUpJ....."
     }
     ```

3. OAA Payload - The completed OAA JSON body to submit. For complete reference see the Veza documentation. This format must match the template selected with the provider.


Once the necessary files have been created, they can be pushed to Veza with the following command:

```shell
# oaaclient  --provider <provider-file>.json --auth <auth-file>.json <OAA Payload>.json
```

The client will read the files and push the payload to Veza. The client will automatically create any Provider or Data Sources needed.
