"""
Copyright 2026 Veza Technologies Inc.

Use of this source code is governed by the MIT
license that can be found in the LICENSE file or at
https://opensource.org/licenses/MIT.
"""
import logging

from .application import (AccessCred, Application,
                          ApplicationPropertyDefinitions, CustomApplication,
                          CustomPermission, CustomResource, Identity,
                          IdPIdentity, LocalAgent, LocalGroup, LocalModel,
                          LocalRole, LocalUser, LocalUserType,
                          OAAIdentityType, OAAPermission)
from .common import (PROPERTY_NAME_REGEX, CaseInsensitiveDict, EntityOwner,
                     IdentityMappingConfigurationSubmission,
                     IdentityMappingDestinationDatasourceSubmission,
                     IdentityMappingMode, IdentityMappingProperty,
                     IdentityMappingPropertyMatchersSubmission,
                     IdentityMappingSubmission, IdentityMappingTransformation,
                     IdPProviderType, OAAPropertyType, OAAOwnerType,
                     IdentityMappingType, Provider, Tag, append_helper, unique_strs)
from .enrichment import (EntityEnrichment, EnrichedEntity, EntityEnrichmentPropertyDefinitions)
from .exceptions import OAATemplateException
from .hris import (HRISEmployee, HRISGroup, HRISPropertyDefinitions,
                   HRISProvider, HRISSystem)
from .idp import (CustomIdPApp, CustomIdPDomain, CustomIdPGroup,
                  CustomIdPProvider, CustomIdPUser, IdPEntityType,
                  IdPPropertyDefinitions, IdPUserIdentityType)
from .principal import (
    CustomPrincipal, CustomPrincipalTenant, CustomPrincipalUser,
    CustomPrincipalGroup, PrincipalPropertyDefinitions, PrincipalEntityType)
from .secret_store import (IdentityToPermission, PermissionAssignment,
                            SecretStore, SecretStorePermission,
                            SecretStorePropertyDefinitions, SecretStoreSubmission,
                            SecretStoreVault, SecretStoreVaultEntry,
                            VaultEntryIdentity)

log = logging.getLogger(__name__)

__all__ = [

    # Base
    'OAATemplateException', 'Provider', 'Application', 'Identity', 'IdPProviderType',
    # Enums
    'OAAPermission', 'OAAIdentityType', 'OAAOwnerType', 'LocalUserType',
    'OAAPropertyType',
    'IdentityMappingType', 'IdentityMappingMode', 'IdentityMappingTransformation',
    'IdentityMappingProperty',
    # Identity Mapping
    'IdentityMappingConfigurationSubmission', 'IdentityMappingSubmission',
    'IdentityMappingPropertyMatchersSubmission',
    'IdentityMappingDestinationDatasourceSubmission',
    # Application
    'CustomApplication', 'CustomResource', 'ApplicationPropertyDefinitions',
    # Identities
    'LocalUser', 'LocalGroup', 'LocalRole', 'IdPIdentity',
    'AccessCred',
    # AI Entities
    'LocalAgent',
    'LocalModel',
    # Permissions
    'CustomPermission',
    # IdP
    'CustomIdPProvider', 'CustomIdPDomain', 'CustomIdPUser',
    'CustomIdPGroup', 'CustomIdPApp', 'IdPEntityType', 'IdPPropertyDefinitions', 'IdPUserIdentityType',
    # HRIS
    'HRISProvider', 'HRISSystem', 'HRISEmployee', 'HRISGroup',
    'HRISPropertyDefinitions',
    # Secret Store
    'SecretStoreSubmission', 'SecretStore', 'SecretStorePermission',
    'SecretStoreVault', 'SecretStoreVaultEntry', 'VaultEntryIdentity',
    'IdentityToPermission', 'PermissionAssignment', 'SecretStorePropertyDefinitions',
    # Enrichment
    'EntityEnrichment', 'EnrichedEntity', "EntityEnrichmentPropertyDefinitions",
    # Principal
    'CustomPrincipal', 'CustomPrincipalTenant', 'CustomPrincipalUser',
    'CustomPrincipalGroup', 'PrincipalPropertyDefinitions', 'PrincipalEntityType',
    # Utils
    'Tag', 'EntityOwner', 'append_helper', 'unique_strs', 'PROPERTY_NAME_REGEX',

    'CaseInsensitiveDict'
]
