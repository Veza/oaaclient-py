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
from oaaclient.templates import EntityEnrichment, OAAPropertyType

logging.basicConfig(format='%(asctime)s %(levelname)s: %(thread)d %(message)s', level=logging.INFO)
log = logging.getLogger(__name__)


def generate_entity_enrichment() -> EntityEnrichment:
    """ Generates a complete Entity Enrichment instance """

    enrichment = EntityEnrichment("Pytest Entity Enrichment")

    enrichment.property_definitions.define_property("AwsIamRole", "my_company_id", OAAPropertyType.STRING)
    enrichment.property_definitions.define_property("AwsIamRole", "company_purpose", OAAPropertyType.STRING)
    enrichment.property_definitions.define_property("AwsIamRole", "is_compliance_validated", OAAPropertyType.BOOLEAN)
    enrichment.property_definitions.define_property("AwsIamUser", "company_purpose", OAAPropertyType.STRING)

    admin_role = enrichment.add_entity(entity_type="AwsIamRole",
                                       id="arn:aws:iam::339083562601:role/Administrator",
                                       data_source_id="339083562601:awsiam")
    admin_role.set_property("my_company_id", "DCFB16CD-A044-4787-9165-1C926221F887")
    admin_role.set_property("company_purpose", "Built in Admin role")
    admin_role.set_property("is_compliance_validated", True)

    andrew_role = enrichment.add_entity(entity_type="AwsIamRole",
                                        id="arn:aws:iam::650251689811:role/andrew_s3_all",
                                        data_source_id="339083562601:awsiam")
    andrew_role.set_property("my_company_id", "A3F40BAC-1871-4EFC-A0EE-CD77E3F513C27")
    andrew_role.set_property("company_purpose", "Some role for Andrew")
    andrew_role.set_property("is_compliance_validated", False)

    andrew_user = enrichment.add_entity(entity_type="AwsIamUser",
                                        id="arn:aws:iam::339083562601:user/andrew",
                                        data_source_id="339083562601:awsiam")
    andrew_user.set_property("company_purpose", "Engineering service account")

    return enrichment


def main() -> None:
  log.info("Generate Entity Enrichment Main")
  # assumes VEZA_URL and VEZA_API_KEY are set in env
  try:
    con = OAAClient()
  except (OAAClientError, ValueError) as e:
     log.error(e)
     log.error("exiting")
     sys.exit(1)

  log.info("Connected to tenant")
  enrichment = generate_entity_enrichment()
  log.info("Entity Enrichment loaded")
  try:
     log.info("Pushing")
     con.push_application(provider_name="Pytest Gen Entity Enrichment", data_source_name="generate_entity_enrichment_main", application_object=enrichment, create_provider=True)
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


GENERATED_ENTITY_ENRICHMENT_PAYLOAD = """
{
  "enriched_entity_property_definitions": [
    {
      "entity_type": "AwsIamRole",
      "enriched_properties": {
        "my_company_id": "STRING",
        "company_purpose": "STRING",
        "is_compliance_validated": "BOOLEAN"
      }
    },
    {
      "entity_type": "AwsIamUser",
      "enriched_properties": {
        "company_purpose": "STRING"
      }
    }
  ],
  "enriched_entities": [
    {
      "type": "AwsIamRole",
      "id": "arn:aws:iam::339083562601:role/Administrator",
      "data_source_id": "339083562601:awsiam",
      "properties": {
        "my_company_id": "DCFB16CD-A044-4787-9165-1C926221F887",
        "company_purpose": "Built in Admin role",
        "is_compliance_validated": true
      }
    },
    {
      "type": "AwsIamRole",
      "id": "arn:aws:iam::650251689811:role/andrew_s3_all",
      "data_source_id": "339083562601:awsiam",
      "properties": {
        "my_company_id": "A3F40BAC-1871-4EFC-A0EE-CD77E3F513C27",
        "company_purpose": "Some role for Andrew",
        "is_compliance_validated": false
      }
    },
    {
      "type": "AwsIamUser",
      "id": "arn:aws:iam::339083562601:user/andrew",
      "data_source_id": "339083562601:awsiam",
      "properties": {
        "company_purpose": "Engineering service account"
      }
    }
  ]
}
"""
