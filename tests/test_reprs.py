"""
Copyright 2022 Veza Technologies Inc.

Use of this source code is governed by the MIT
license that can be found in the LICENSE file or at
https://opensource.org/licenses/MIT.
"""

import pytest

from generate_app import generate_app
from generate_idp import generate_idp
from generate_hris import generate_hris
from oaaclient.templates import Tag

def test_custom_app_reprs() -> None:
    # quick test to ensure that all the str and repr functions are free of bugs

    app = generate_app()

    # app
    assert app.__str__() == "Custom Application pytest generated app - pytest"
    assert app.__repr__() == "CustomApplication(name='pytest generated app', application_type='pytest', description='This is a test')"

    # test local user
    bob = app.local_users["bob"]
    assert bob.__str__() == "Local User - bob (None)"
    assert bob.__repr__() == "LocalUser(name='bob', unique_id=None, identities=['bob@example.com'])"

    group1 = app.local_groups["group1"]
    assert group1.__str__() == "Local Group - group1 (None)"
    assert group1.__repr__() == "LocalGroup(name='group1', unique_id=None, identities=None)"

    role1 = app.local_roles["role1"]
    assert role1.__str__() == "Local Role - role1 (None)"
    assert role1.__repr__() == "LocalRole(name='role1', permissions=['all', 'Admin', 'Manage_Thing'], unique_id=None)"

    all_permission = app.custom_permissions["all"]
    assert all_permission.__str__() == "Custom Permission all - [OAAPermission.DataRead, OAAPermission.DataWrite, OAAPermission.DataCreate, OAAPermission.DataDelete, OAAPermission.MetadataRead, OAAPermission.MetadataWrite, OAAPermission.MetadataCreate, OAAPermission.MetadataDelete, OAAPermission.NonData]"
    assert all_permission.__repr__() == "CustomPermissions(name='all', permissions=[OAAPermission.DataRead, OAAPermission.DataWrite, OAAPermission.DataCreate, OAAPermission.DataDelete, OAAPermission.MetadataRead, OAAPermission.MetadataWrite, OAAPermission.MetadataCreate, OAAPermission.MetadataDelete, OAAPermission.NonData], apply_to_sub_resources=False)"

    thing1 = app.resources["thing1"]
    assert thing1.__str__() == "Resource: thing1 (None) - thing"
    assert thing1.__repr__() == "CustomResource(name='thing1', resource_type='thing', unique_id=None, application_name='pytest generated app', resource_key='thing1')"

    idp_user = app.idp_identities["user01@example.com"]
    assert idp_user.__str__() == "IdP Identity user01@example.com"
    assert idp_user.__repr__() == "IdPIdentity(name='user01@example.com')"

    assert app.property_definitions.__str__() == "ApplicationPropertyDefinitions for pytest"
    assert app.property_definitions.__repr__() == "ApplicationPropertyDefinitions(application_type='pytest')"

def test_custom_idp_reprs() -> None:

    idp = generate_idp()

    assert idp.__str__() == "Custom IdP Provider Pytest IdP - pytest"
    assert idp.__repr__() == "CustomIdPProvider(name='Pytest IdP', idp_type='pytest', domain=CustomIdPDomain(name='example.com'), description='Pytest Test IdP')"

    assert idp.domain.__str__() == "Custom IdP Domain example.com"
    assert idp.domain.__repr__() == "CustomIdPDomain(name='example.com')"

    user1 = idp.users["0001"]
    assert user1.__str__() == "IdP User - user0001 (0001)"
    assert user1.__repr__() == "CustomIdPUser(name='user0001', email='user001@example.com', full_name='User 0001', identity='0001')"

    group1 = idp.groups["g001"]
    assert group1.__str__() == "IdP Group group001 (g001)"
    assert group1.__repr__() == "CustomIdPGroup(name='group001', full_name='Group 001', identity='g001')"

    assert idp.property_definitions.__str__() == "IdP Property Definitions"
    assert idp.property_definitions.__repr__() == "IdPPropertyDefinitions()"

def test_tag_repr() -> None:

    test_tag = Tag("test", "value")
    assert test_tag.__str__() == "Tag test:value"
    assert test_tag.__repr__() == "Tag(key='test', value='value')"

    test_tag = Tag("Test")
    assert test_tag.__str__() == "Tag Test"
    assert test_tag.__repr__() == "Tag(key='Test', value='')"

def test_hris_repr() -> None:
    hris = generate_hris()

    assert hris.__str__() == "HRISProvider Pytest HRIS - PyHRIS"
    assert hris.__repr__() == "HRISProvider(name='Pytest HRIS', hris_type='PyHRIS', url='example.com')"

    assert hris.system.__str__() == "HRISSystem - Pytest HRIS"
    assert hris.system.__repr__() == "HRISSystem(name='Pytest HRIS', url='example.com')"

    employee = hris.employees["001"]
    assert employee.__str__() == "HRISEmployee - employee001 (001)"
    assert employee.__repr__() == "HRISEmployee(unique_id: '001', name: 'employee001', employee_number: '001', first_name: 'Employee', last_name: 'Fake', is_active: True, employment_status: 'EMPLOYED')"

    group = hris.groups["g001"]
    assert group.__str__() == "HRISGroup - Group 001 (g001) - Team"
    assert group.__repr__() == "HRISGroup(unique_id='g001', name='Group 001', group_type='Team')"
