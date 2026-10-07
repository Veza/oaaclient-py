"""
Copyright 2022 Veza Technologies Inc.

Use of this source code is governed by the MIT
license that can be found in the LICENSE file or at
https://opensource.org/licenses/MIT.
"""

import json
import pytest

from generate_entity_enrichment import GENERATED_ENTITY_ENRICHMENT_PAYLOAD, generate_entity_enrichment

from oaaclient.templates import EnrichedEntity, EntityEnrichment, OAAPropertyType, OAATemplateException

def test_generate_entity_enrichment():
    enrichment = generate_entity_enrichment()
    payload = enrichment.get_payload()
    print(json.dumps(payload, indent=2))

    assert payload == json.loads(GENERATED_ENTITY_ENRICHMENT_PAYLOAD)

def test_entity_enrichment_exceptions():

    enrichment = generate_entity_enrichment()

    # test duplicate entity
    entity_details = {"entity_type": "AwsIamRole",
                      "id": "arn:aws:iam::339083562601:role/Administrator",
                      "data_source_id": "339083562601:awsiam"
                     }

    with pytest.raises(OAATemplateException) as e:
        enrichment.add_entity(**entity_details)

    assert e.value.message == "Entity already defined: type=AwsIamRole, id=arn:aws:iam::339083562601:role/Administrator, data_source_id=339083562601:awsiam"

    with pytest.raises(OAATemplateException) as e:
        enrichment.property_definitions.define_property("AwsIamRole", 1, OAAPropertyType.BOOLEAN)

    assert e.value.message == "Property name must be a string, received <class 'int'>"

    with pytest.raises(OAATemplateException) as e:
        enrichment.property_definitions.define_property("AwsIamRole", "@property", OAAPropertyType.BOOLEAN)

    assert e.value.message == "Lower-cased property name must match the pattern: '^[a-z][a-z_]*$'. Invalid name: @property"

    with pytest.raises(OAATemplateException) as e:
        enrichment.property_definitions.define_property("", "valid_name", OAAPropertyType.STRING)

    assert e.value.message == "entity_type must be a non-empty string"

    with pytest.raises(OAATemplateException) as e:
        enrichment.property_definitions.define_property("AwsIamRole", "valid_name", "STRING")

    assert e.value.message == "property_type must be type OAAPropertyType enum"


# Test for empty input validation on entity creation
@pytest.mark.parametrize("details",
                         [
                             {"entity_type": "", "id": "arn:aws:iam::1:role/r", "data_source_id": "1:awsiam"},
                             {"entity_type": "AwsIamRole", "id": "", "data_source_id": "1:awsiam"},
                             {"entity_type": "AwsIamRole", "id": "arn:aws:iam::1:role/r", "data_source_id": ""},
                             {"entity_type": None, "id": "arn:aws:iam::1:role/r", "data_source_id": "1:awsiam"},
                             {"entity_type": "AwsIamRole", "id": None, "data_source_id": "1:awsiam"},
                             {"entity_type": "AwsIamRole", "id": "arn:aws:iam::1:role/r", "data_source_id": None}
                        ])
def test_entity_init(details):

    with pytest.raises(ValueError) as e:
        entity = EnrichedEntity(**details)

    assert e.value.args is not None


def test_entity_custom_properties():

    enrichment = EntityEnrichment("propertyTest")

    entity1 = enrichment.add_entity(entity_type="AwsIamRole",
                                    id="arn:aws:iam::1:role/r1",
                                    data_source_id="1:awsiam")

    with pytest.raises(OAATemplateException) as e:
        entity1.set_property("unset", "something")

    assert "AwsIamRole" in e.value.message
    assert "unset" in e.value.message

    enrichment.property_definitions.define_property("AwsIamRole", "test_prop", OAAPropertyType.STRING)
    entity2 = enrichment.add_entity(entity_type="AwsIamRole",
                                    id="arn:aws:iam::1:role/r2",
                                    data_source_id="1:awsiam")

    entity2.set_property("test_prop", "value1")
    assert entity2.custom_properties["test_prop"] == "value1"

    # properties for one entity type should not be valid for another
    enrichment.property_definitions.define_property("AwsIamUser", "user_only", OAAPropertyType.STRING)
    role_entity = enrichment.add_entity(entity_type="AwsIamRole",
                                        id="arn:aws:iam::1:role/r3",
                                        data_source_id="1:awsiam")

    with pytest.raises(OAATemplateException) as e:
        role_entity.set_property("user_only", "value")

    assert "AwsIamRole" in e.value.message
    assert "user_only" in e.value.message

    # test behavior when EnrichedEntity is created outside the Provider
    # since there is no property definitions no validation can be performed, unset property shouldn't cause error
    entity_obj = EnrichedEntity(entity_type="AwsIamRole",
                                id="arn:aws:iam::1:role/r4",
                                data_source_id="1:awsiam")
    entity_obj.set_property("unset", "value2")
