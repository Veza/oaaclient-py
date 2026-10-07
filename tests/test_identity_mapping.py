"""
Copyright 2026 Veza Technologies Inc.

Use of this source code is governed by the MIT
license that can be found in the LICENSE file or at
https://opensource.org/licenses/MIT.
"""

import pytest

from oaaclient.templates import (
    IdentityMappingConfigurationSubmission,
    IdentityMappingDestinationDatasourceSubmission,
    IdentityMappingMode,
    IdentityMappingProperty,
    IdentityMappingPropertyMatchersSubmission,
    IdentityMappingSubmission,
    IdentityMappingTransformation,
    IdentityMappingType,
)


###############################################################################
# Enum tests
###############################################################################

def test_identity_mapping_type_values():
    assert IdentityMappingType.EQUAL == "EQUAL"
    assert IdentityMappingType.CUSTOM == "CUSTOM"


def test_identity_mapping_mode_values():
    assert IdentityMappingMode.USERS == "USERS"
    assert IdentityMappingMode.GROUPS == "GROUPS"
    assert IdentityMappingMode.ROLE_TO_USER == "ROLE_TO_USER"


def test_identity_mapping_transformation_values():
    assert IdentityMappingTransformation.IGNORE_SPECIAL == "IGNORE_SPECIAL"
    assert IdentityMappingTransformation.IGNORE_DOMAIN == "IGNORE_DOMAIN"


def test_identity_mapping_property_values():
    assert IdentityMappingProperty.UNIQUE_ID == "UNIQUE_ID"
    assert IdentityMappingProperty.EMAIL == "EMAIL"
    assert IdentityMappingProperty.CUSTOM_PROPERTY == "CUSTOM_PROPERTY"
    assert IdentityMappingProperty.PROPERTY == "PROPERTY"
    assert IdentityMappingProperty.TEMPLATE == "TEMPLATE"


###############################################################################
# IdentityMappingConfigurationSubmission tests
###############################################################################

def test_configuration_init_defaults():
    config = IdentityMappingConfigurationSubmission()
    assert config.use_email is False
    assert config.operation is None
    assert config.mappings == []


def test_configuration_str_repr():
    config = IdentityMappingConfigurationSubmission()
    assert "IdentityMappingConfigurationSubmission" in str(config)
    assert "IdentityMappingConfigurationSubmission" in repr(config)


def test_configuration_to_dict_defaults():
    config = IdentityMappingConfigurationSubmission()
    result = config.to_dict()
    # use_email=False must be present (bool field, not filtered)
    assert "use_email" in result
    assert result["use_email"] is False
    # operation and mappings are None/"" so should be omitted
    assert "operation" not in result
    assert "mappings" not in result


def test_configuration_to_dict_use_email_true():
    config = IdentityMappingConfigurationSubmission()
    config.use_email = True
    result = config.to_dict()
    assert result["use_email"] is True


def test_configuration_to_dict_with_operation():
    config = IdentityMappingConfigurationSubmission()
    config.operation = "upsert"
    result = config.to_dict()
    assert result["operation"] == "upsert"


def test_configuration_add_mapping_returns_submission():
    config = IdentityMappingConfigurationSubmission()
    mapping = config.add_mapping(
        destination_datasource_type="okta",
        destination_datasource_oaa_type="",
        mapping_type=IdentityMappingType.EQUAL,
    )
    assert isinstance(mapping, IdentityMappingSubmission)
    assert len(config.mappings) == 1
    assert config.mappings[0] is mapping


def test_configuration_add_multiple_mappings():
    config = IdentityMappingConfigurationSubmission()
    config.add_mapping("okta", "", IdentityMappingType.EQUAL)
    config.add_mapping("azure_ad", "", IdentityMappingType.EQUAL)
    assert len(config.mappings) == 2


def test_configuration_to_dict_includes_mappings():
    config = IdentityMappingConfigurationSubmission()
    config.add_mapping(
        destination_datasource_type="okta",
        destination_datasource_oaa_type="",
        mapping_type=IdentityMappingType.EQUAL,
        mapping_mode=IdentityMappingMode.USERS,
    )
    result = config.to_dict()
    assert "mappings" in result
    assert len(result["mappings"]) == 1


###############################################################################
# IdentityMappingSubmission tests
###############################################################################

def test_submission_init():
    mapping = IdentityMappingSubmission(
        destination_datasource_type="okta",
        destination_datasource_oaa_type="",
        mapping_type=IdentityMappingType.EQUAL,
    )
    assert mapping.destination_datasource_type == "okta"
    assert mapping.mapping_type == IdentityMappingType.EQUAL
    assert mapping.mapping_mode == ""
    assert mapping.transformations == []
    assert mapping.custom_value == ""
    assert mapping.property_matchers == []
    assert mapping.destination_datasources == []


def test_submission_str_repr():
    mapping = IdentityMappingSubmission("okta", "", IdentityMappingType.EQUAL)
    assert "IdentityMappingSubmission" in str(mapping)
    assert "IdentityMappingSubmission" in repr(mapping)
    assert "okta" in str(mapping)


def test_submission_to_dict_json_keys():
    """Verify Python attribute names serialize to the correct JSON field names."""
    mapping = IdentityMappingSubmission(
        destination_datasource_type="okta",
        destination_datasource_oaa_type="my_app_type",
        mapping_type=IdentityMappingType.EQUAL,
        mapping_mode=IdentityMappingMode.USERS,
    )
    result = mapping.to_dict()
    # Remapped keys
    assert "destination_datasource_oaa_app_type" in result
    assert result["destination_datasource_oaa_app_type"] == "my_app_type"
    assert "type" in result
    assert result["type"] == "EQUAL"
    assert "mode" in result
    assert result["mode"] == "USERS"


def test_submission_to_dict_omits_empty_fields():
    mapping = IdentityMappingSubmission(
        destination_datasource_type="okta",
        destination_datasource_oaa_type="",
        mapping_type=IdentityMappingType.EQUAL,
    )
    result = mapping.to_dict()
    assert "destination_datasource_oaa_app_type" not in result
    assert "mode" not in result
    assert "custom_value" not in result
    assert "transformations" not in result
    assert "property_matchers" not in result
    assert "destination_datasources" not in result


def test_submission_transformations_serialized():
    mapping = IdentityMappingSubmission(
        destination_datasource_type="okta",
        destination_datasource_oaa_type="",
        mapping_type=IdentityMappingType.EQUAL,
        transformations=[IdentityMappingTransformation.IGNORE_DOMAIN],
    )
    result = mapping.to_dict()
    assert result["transformations"] == ["IGNORE_DOMAIN"]


def test_submission_add_property_matcher():
    mapping = IdentityMappingSubmission("okta", "", IdentityMappingType.EQUAL)
    matcher = mapping.add_property_matcher(
        source_property=IdentityMappingProperty.EMAIL,
        destination_property=IdentityMappingProperty.EMAIL,
    )
    assert isinstance(matcher, IdentityMappingPropertyMatchersSubmission)
    assert len(mapping.property_matchers) == 1
    assert mapping.property_matchers[0] is matcher


def test_submission_add_destination_datasource():
    mapping = IdentityMappingSubmission("okta", "", IdentityMappingType.EQUAL)
    ds = mapping.add_destination_datasource(datasource_type="github", oaa_type="github_app")
    assert isinstance(ds, IdentityMappingDestinationDatasourceSubmission)
    assert len(mapping.destination_datasources) == 1
    assert mapping.destination_datasources[0] is ds


def test_submission_to_dict_includes_nested():
    mapping = IdentityMappingSubmission("okta", "", IdentityMappingType.EQUAL)
    mapping.add_property_matcher(
        IdentityMappingProperty.EMAIL, IdentityMappingProperty.EMAIL
    )
    mapping.add_destination_datasource("github", "github_app")
    result = mapping.to_dict()
    assert len(result["property_matchers"]) == 1
    assert len(result["destination_datasources"]) == 1


###############################################################################
# IdentityMappingPropertyMatchersSubmission tests
###############################################################################

def test_property_matcher_init():
    matcher = IdentityMappingPropertyMatchersSubmission(
        source_property=IdentityMappingProperty.EMAIL,
        destination_property=IdentityMappingProperty.UNIQUE_ID,
    )
    assert matcher.source_property == "EMAIL"
    assert matcher.destination_property == "UNIQUE_ID"
    assert matcher.custom_source_property == ""
    assert matcher.custom_destination_property == ""


def test_property_matcher_str_repr():
    matcher = IdentityMappingPropertyMatchersSubmission(
        source_property=IdentityMappingProperty.EMAIL,
        destination_property=IdentityMappingProperty.EMAIL,
    )
    assert "IdentityMappingPropertyMatchersSubmission" in str(matcher)
    assert "IdentityMappingPropertyMatchersSubmission" in repr(matcher)


def test_property_matcher_to_dict_required_only():
    matcher = IdentityMappingPropertyMatchersSubmission(
        source_property=IdentityMappingProperty.EMAIL,
        destination_property=IdentityMappingProperty.UNIQUE_ID,
    )
    result = matcher.to_dict()
    assert result["source_property"] == "EMAIL"
    assert result["destination_property"] == "UNIQUE_ID"
    # Empty custom fields should be omitted
    assert "custom_source_property" not in result
    assert "custom_destination_property" not in result


def test_property_matcher_to_dict_with_custom_properties():
    matcher = IdentityMappingPropertyMatchersSubmission(
        source_property=IdentityMappingProperty.CUSTOM_PROPERTY,
        destination_property=IdentityMappingProperty.CUSTOM_PROPERTY,
        custom_source_property="my_src_prop",
        custom_destination_property="my_dst_prop",
    )
    result = matcher.to_dict()
    assert result["custom_source_property"] == "my_src_prop"
    assert result["custom_destination_property"] == "my_dst_prop"


###############################################################################
# IdentityMappingDestinationDatasourceSubmission tests
###############################################################################

def test_destination_datasource_init():
    ds = IdentityMappingDestinationDatasourceSubmission(
        datasource_type="github",
        oaa_type="github_app",
    )
    assert ds.datasource_type == "github"
    assert ds.oaa_type == "github_app"


def test_destination_datasource_str_repr():
    ds = IdentityMappingDestinationDatasourceSubmission("github", "github_app")
    assert "IdentityMappingDestinationDatasourceSubmission" in str(ds)
    assert "IdentityMappingDestinationDatasourceSubmission" in repr(ds)
    assert "github" in str(ds)


def test_destination_datasource_to_dict_json_keys():
    """Verify Python attribute names serialize to the correct JSON field names."""
    ds = IdentityMappingDestinationDatasourceSubmission(
        datasource_type="github",
        oaa_type="github_app",
    )
    result = ds.to_dict()
    assert "type" in result
    assert result["type"] == "github"
    assert "oaa_app_type" in result
    assert result["oaa_app_type"] == "github_app"
    # Python attribute names must not leak through
    assert "datasource_type" not in result
    assert "oaa_type" not in result


###############################################################################
# Full payload round-trip test
###############################################################################

def test_full_payload_round_trip():
    """Build a complete configuration and verify the serialized structure."""
    config = IdentityMappingConfigurationSubmission()
    config.use_email = True
    config.operation = "upsert"

    mapping = config.add_mapping(
        destination_datasource_type="okta",
        destination_datasource_oaa_type="okta_app",
        mapping_type=IdentityMappingType.EQUAL,
        mapping_mode=IdentityMappingMode.USERS,
        transformations=[
            IdentityMappingTransformation.IGNORE_DOMAIN,
            IdentityMappingTransformation.IGNORE_SPECIAL,
        ],
    )
    mapping.add_property_matcher(
        source_property=IdentityMappingProperty.EMAIL,
        destination_property=IdentityMappingProperty.EMAIL,
    )
    mapping.add_property_matcher(
        source_property=IdentityMappingProperty.CUSTOM_PROPERTY,
        destination_property=IdentityMappingProperty.CUSTOM_PROPERTY,
        custom_source_property="upn",
        custom_destination_property="login",
    )
    mapping.add_destination_datasource(datasource_type="github", oaa_type="github_app")

    result = config.to_dict()

    assert result["use_email"] is True
    assert result["operation"] == "upsert"
    assert len(result["mappings"]) == 1

    m = result["mappings"][0]
    assert m["destination_datasource_type"] == "okta"
    assert m["destination_datasource_oaa_app_type"] == "okta_app"
    assert m["type"] == "EQUAL"
    assert m["mode"] == "USERS"
    assert m["transformations"] == ["IGNORE_DOMAIN", "IGNORE_SPECIAL"]

    assert len(m["property_matchers"]) == 2
    assert m["property_matchers"][0] == {
        "source_property": "EMAIL",
        "destination_property": "EMAIL",
    }
    assert m["property_matchers"][1] == {
        "source_property": "CUSTOM_PROPERTY",
        "destination_property": "CUSTOM_PROPERTY",
        "custom_source_property": "upn",
        "custom_destination_property": "login",
    }

    assert len(m["destination_datasources"]) == 1
    assert m["destination_datasources"][0] == {
        "type": "github",
        "oaa_app_type": "github_app",
    }


@pytest.mark.parametrize("mapping_type", list(IdentityMappingType))
def test_all_mapping_types_serialize(mapping_type):
    mapping = IdentityMappingSubmission("okta", "", mapping_type)
    result = mapping.to_dict()
    assert result["type"] == mapping_type.value


@pytest.mark.parametrize("mode", list(IdentityMappingMode))
def test_all_mapping_modes_serialize(mode):
    mapping = IdentityMappingSubmission("okta", "", IdentityMappingType.EQUAL, mapping_mode=mode)
    result = mapping.to_dict()
    assert result["mode"] == mode.value


@pytest.mark.parametrize("transformation", list(IdentityMappingTransformation))
def test_all_transformations_serialize(transformation):
    mapping = IdentityMappingSubmission(
        "okta", "", IdentityMappingType.EQUAL,
        transformations=[transformation],
    )
    result = mapping.to_dict()
    assert transformation.value in result["transformations"]


@pytest.mark.parametrize("prop", list(IdentityMappingProperty))
def test_all_properties_serialize(prop):
    matcher = IdentityMappingPropertyMatchersSubmission(
        source_property=prop,
        destination_property=prop,
    )
    result = matcher.to_dict()
    assert result["source_property"] == prop.value
    assert result["destination_property"] == prop.value
