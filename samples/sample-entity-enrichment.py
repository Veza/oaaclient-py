#!env python3
"""Uses the `EntityEnrichment` class to enrich existing Veza entities with custom properties.

Defines a set of custom properties per Veza entity type (such as `AwsIamRole` or `AwsIamUser`) and assigns
values to specific entities by their Veza unique ID and data source ID.

To run the code, you will need to export environment variables for the Veza URL,
user and API keys.

Example:
    ```
    export OAA_TOKEN="xxxxxxx"
    export VEZA_URL="https://myveza.vezacloud.com"
    ./sample-entity-enrichment.py
    ```

Copyright 2026 Veza Technologies Inc.

Use of this source code is governed by the MIT
license that can be found in the LICENSE file or at
https://opensource.org/licenses/MIT.

"""

from oaaclient.client import OAAClient, OAAClientError
from oaaclient.templates import EntityEnrichment, OAAPropertyType
import os
import sys


def main():

    # OAA requires an API token, which you can generate from your Veza user profile
    # Export the API token, and Veza URL as environment variables
    # Making them available to your connector in this way keeps credentials out of the source code
    veza_api_key = os.getenv('VEZA_API_KEY')
    veza_url = os.getenv('VEZA_URL')
    if None in (veza_url, veza_api_key):
        print("Unable to local all environment variables")
        sys.exit(1)

    # Instantiates a client connection. The client will confirm the credentials and Veza URL are valid
    # Checking this early helps prevents connection failures in the final stage
    veza_con = OAAClient(url=veza_url, api_key=veza_api_key)

    # Create an instance of the OAA EntityEnrichment class. The Entity Enrichment template attaches custom
    # properties to entities that already exist in the Veza graph (discovered by other integrations) rather
    # than creating new entities.
    # `name` is used to identify the provider and is not part of the payload itself.
    enrichment = EntityEnrichment(name="Sample Entity Enrichment")

    # Define the custom properties per Veza entity type before assigning values.
    # Each entity type maintains its own set of property definitions.
    enrichment.property_definitions.define_property("AwsIamRole", "my_company_id", OAAPropertyType.STRING)
    enrichment.property_definitions.define_property("AwsIamRole", "company_purpose", OAAPropertyType.STRING)
    enrichment.property_definitions.define_property("AwsIamRole", "is_compliance_validated", OAAPropertyType.BOOLEAN)
    enrichment.property_definitions.define_property("AwsIamUser", "company_purpose", OAAPropertyType.STRING)

    # Add entities to enrich. Each entity is identified by its Veza entity type, unique ID and the ID of the
    # data source that owns it. For AWS entities the unique ID is the ARN and the data source ID combines the
    # account ID with the data source type (e.g. "339083562601:awsiam").
    admin_role = enrichment.add_entity(entity_type="AwsIamRole",
                                       id="arn:aws:iam::339083562601:role/Administrator",
                                       data_source_id="339083562601:awsiam")
    admin_role.set_property("my_company_id", "DCFB16CD-A044-4787-9165-1C926221F887")
    admin_role.set_property("company_purpose", "Built in Admin role")
    admin_role.set_property("is_compliance_validated", True)

    andrew_user = enrichment.add_entity(entity_type="AwsIamUser",
                                        id="arn:aws:iam::339083562601:user/andrew",
                                        data_source_id="339083562601:awsiam")
    andrew_user.set_property("company_purpose", "Engineering service account")

    # Once all enrichments have been modeled, the final step is to publish to Veza
    # Connect to the API to push, define the provider and create if necessary:

    provider_name = "Sample Entity Enrichment"
    provider = veza_con.get_provider(provider_name)
    if provider:
        print("-- Found existing provider")
    else:
        print(f"++ Creating Provider {provider_name}")
        provider = veza_con.create_provider(provider_name, "entity_enrichment")
    print(f"-- Provider: {provider['name']} ({provider['id']})")

    # Push the metadata payload:

    try:
        response = veza_con.push_application(provider_name,
                                               data_source_name=f"{enrichment.name}",
                                               application_object=enrichment,
                                               save_json=False
                                               )
        if response.get("warnings", None):
            # Veza may return warnings on a successful uploads. These are informational warnings that did not stop the processing
            # of the OAA data but may be important.
            print("-- Push succeeded with warnings:")
            for e in response["warnings"]:
                print(f"  - {e}")
    except OAAClientError as e:
        # If there are any errors connecting to the Veza API or processing the payload the client will raise an `OAAClientError`
        print(f"-- Error: {e.error}: {e.message} ({e.status_code})", file=sys.stderr)
        if hasattr(e, "details"):
            # Error details will have specifics on any issues encountered processing the payload
            for d in e.details:
                print(f"  -- {d}", file=sys.stderr)
    return


if __name__ == '__main__':
    main()
