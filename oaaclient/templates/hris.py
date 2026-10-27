"""
Classes for constructing an OAA JSON payload for custom HRIS

Copyright 2026 Veza Technologies Inc.

Use of this source code is governed by the MIT
license that can be found in the LICENSE file or at
https://opensource.org/licenses/MIT.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from .common import PROPERTY_NAME_REGEX, CaseInsensitiveDict, IdentityMappingConfigurationSubmission, IdPProviderType, OAAPropertyType
from .exceptions import OAATemplateException

log = logging.getLogger(__name__)

###############################################################################
# Human Resource Information Systems (HRIS)
###############################################################################

class HRISProvider():
    """Class for modeling Human Resource Information Systems (HRIS) Template

    HRIS template consists of base information about the HRIS instance, Employees and Groups.

    Employees and Groups are tracked in case insensitive dictionaries that can be used to reference entities after creation.

    Args:
        name (str): Name for HRIS Instance
        hris_type (str): Type for HRIS. Typically the vendor or product name.
        url (str): Instance URL for HRIS.

    Attributes:
        employees (dict[string]): Dictionary of HRISEmployee instances keyed by Employee ID
        groups (dict[string]): Dictionary of HRISGroup instances keyed by Group ID
    """

    TEMPLATE = "hris"

    def __init__(self, name: str, hris_type: str, url: str):
        self.name = name

        # TODO: validate HRIS type against supported characters
        self.hris_type = hris_type

        self.system = HRISSystem(name, url=url)

        self.employees = CaseInsensitiveDict()
        self.groups = CaseInsensitiveDict()

        self.property_definitions = HRISPropertyDefinitions()

    def __str__(self) -> str:
        return f"HRISProvider {self.name} - {self.hris_type}"

    def __repr__(self) -> str:
        return f"HRISProvider(name={self.name!r}, hris_type={self.hris_type!r}, url={self.system.url!r})"

    def get_payload(self) -> dict:
        """Get the OAA payload.

        Returns the complete OAA template payload for HRIS as serializable dictionary

        Returns:
            dict: OAA payload as dictionary
        """

        payload = {"name": self.name,
                    "hris_type": self.hris_type,
                    "custom_property_definition": self.property_definitions.to_dict(),
                    "system": self.system.to_dict(),
                    "employees": [employee.to_dict() for employee in self.employees.values()],
                    "groups": [group.to_dict() for group in self.groups.values()]
                  }

        return payload

    def add_employee(self, unique_id: str, name: str, employee_number: str, first_name: str, last_name: str, is_active: bool, employment_status: str) -> HRISEmployee:
        """Add a new Employee

        Function creates a new HRISEmployee instance and adds it to the `HRISProvider.employees` keyed by the `unique_id`

        Args:
            unique_id (str): Unique Identifier for Employee
            name (str): Display name for employee
            employee_number (str): The employee's number that appears in the third-party integration.
            first_name (str): Employee first name
            last_name (str): Employee last name (family name)
            is_active (bool): Boolean for employee active status
            employment_status (str): String representation of employee status, e.g. "ACTIVE", "TERMINATE", "PENDING"

        Raises:
            OAATemplateException: Employee with ID already exists

        Returns:
            HRISEmployee: Entity for new employee
        """

        if unique_id in self.employees:
            raise OAATemplateException(f"Employee with unique ID already exists, {unique_id}")

        self.employees[unique_id] = HRISEmployee(unique_id=unique_id,
                                                    name=name,
                                                    employee_number=employee_number,
                                                    first_name=first_name,
                                                    last_name=last_name,
                                                    is_active=is_active,
                                                    employment_status=employment_status
                                                )

        self.employees[unique_id]._property_definitions = self.property_definitions.employee_properties

        return self.employees[unique_id]

    def add_group(self, unique_id: str, name: str, group_type: str) -> HRISGroup:
        """Add a new Group

        Used to represent any subset of employees, such as PayGroup or Team. Employees can be in multiple Groups. Groups can also
        be members of other groups to create hierarchy.

        Some properties of HRISEmployee such as `department` must reference an existing HRISGroup by its ID.

        Args:
            unique_id (str): Unique ID for group
            name (str): Display name
            group_type (str): Type for group such as "Team", "Department", "Cost Center"

        Returns:
            HRISGroup: Entity for new group
        """
        if unique_id in self.groups:
            raise OAATemplateException(f"Group with unique ID already exists, {unique_id}")

        self.groups[unique_id] = HRISGroup(unique_id=unique_id, name=name, group_type=group_type)
        self.groups[unique_id]._property_definitions = self.property_definitions.group_properties

        return self.groups[unique_id]


class HRISSystem():
    """HRISSystem information

    Representation for HRISSystem information. The system information is used to represent additional details
    for the HRIS Instance.

    Args:
        name (str): Name for system Instance
        url (str, optional): URL for instance . Defaults to "". TODO: Is this right?

    Attributes:
        identity_mapping_configuration (IdentityMappingConfigurationSubmission): Identity mapping configuration, set via :meth:`set_identity_mapping_configuration`.
    """

    def __init__(self, name: str, url: str = ""):


        self.name = name
        self.unique_id = name
        self.url = url
        self.idp_providers = []
        self.identity_mapping_configuration: Optional[IdentityMappingConfigurationSubmission] = None


    def __str__(self) -> str:
        return f"HRISSystem - {self.name}"

    def __repr__(self) -> str:
        return f"HRISSystem(name={self.name!r}, url={self.url!r})"

    def to_dict(self) -> dict:
        payload = {"id": self.unique_id,
                   "name": self.name,
                   "url": self.url,
                   "idp_providers": self.idp_providers
                  }

        if self.identity_mapping_configuration is not None:
            payload["identity_mapping_configuration"] = self.identity_mapping_configuration.to_dict()

        return payload

    def set_identity_mapping_configuration(self) -> IdentityMappingConfigurationSubmission:
        """Create and set the identity mapping configuration.

        Initializes the :attr:`identity_mapping_configuration` attribute with a new
        :class:`IdentityMappingConfigurationSubmission` instance and returns it for further
        configuration.

        Returns:
            IdentityMappingConfigurationSubmission: The identity mapping configuration.
        """

        self.identity_mapping_configuration = IdentityMappingConfigurationSubmission()
        return self.identity_mapping_configuration

    def add_idp_type(self, provider_type: IdPProviderType) -> list[IdPProviderType]:
        """Link HRIS to External IdP of given type

        Sets the IdP types (Okta, AzureAD, ect) for Veza to link employee identities too.

        Args:
            provider_type (IdPProviderType): Type of IdP for source identities

        Raises:
            ValueError: provider_type must be IdPProviderType enum

        Returns:
            list[IdPProviderType]: List of configured IdP types
        """

        if not isinstance(provider_type, IdPProviderType):
            raise ValueError(f"provider_type must be of type IdPProviderType enum, received {type(provider_type)}")

        if provider_type not in self.idp_providers:
            self.idp_providers.append(provider_type)

        return self.idp_providers

class HRISEmployee():
    """HRIS Employee Entity

    Represents an employee record in the HRIS system. Each employee must have a unique ID to identify it in the payload. This ID
    is also used to reference one employee to the other for manager hierarchy.

    Init variables are all required and must not be empty such as `""`

    Args:
        unique_id (str): Unique Identifier for Employee
        name (str): Name for employee record.
        employee_number (str): The employee's number that appears in the third-party integration.
        first_name (str): Employee first name
        last_name (str): Employee last name (family name)
        is_active (bool): Boolean for employee active status
        employment_status (str): String representation of employee status, e.g. "ACTIVE", "TERMINATE", "PENDING"

    Parameters:
        company (str): The company (or subsidiary) the employee works for.
        preferred_name (str): The employee's preferred first name.
        display_full_name (str): The employee's full name, to use for display purposes.
        canonical_name (str): The employee's canonical name.
        username (str): The employee's username that appears in the integration UI.
        email (str): The employee's work email.
        idpid (str): The ID for this employee on the destination IDP provider used to automatically connect to it, if not supplied email is used.
        personal_email (str): The employee's personal email.
        home_location (str): The employee's home location.
        work_location (str): The employee's work location.
        cost_center (str): The cost center ID (Group ID) that the employee is in.
        department (str): The department ID (Group ID) that the employee is in.
        managers (str): The employee IDs of the employee's managers.
        groups (str): The IDs of groups this user is in
        start_date (str): The date that the employee started working. RFC3339 timestamp.
        termination_date (str): The employee's termination date. RFC3339 timestamp.
        job_title (str): The title of the employee.
        employment_typ (str): The employee's type of employment. For example: FULL_TIME, PART_TIME, INTERN, CONTRACTOR, FREELANCE.
        primary_time_zone (str): The time zone which the employee primarily lives.

    Raises:
        ValueError: Any of the required arguments are empty.

    """
    def __init__(self, unique_id: str, name: str, employee_number: str, first_name: str, last_name: str, is_active: bool, employment_status: str):


        # required values
        if not unique_id:
            raise ValueError("unique_id cannot be empty")
        if not name:
            raise ValueError("name cannot be empty")
        if not employee_number:
            raise ValueError("employee_number cannot be empty")
        if not first_name:
            raise ValueError("first_name cannot be empty")
        if not last_name:
            raise ValueError("last_name cannot be empty")
        if not employment_status:
            raise ValueError("employment_status cannot be empty")
        if not isinstance(is_active, bool):
            raise ValueError("is_active must be boolean type")

        self.unique_id: str = unique_id
        self.name: str = name
        self.employee_number: str = employee_number
        self.first_name: str = first_name
        self.last_name: str = last_name
        self.employment_status: str = employment_status
        self.is_active: bool = is_active

        # optional parameters
        self.company: str = ""
        self.preferred_name: str = ""
        self.display_full_name: str = ""
        self.canonical_name: str = ""
        self.username: str = ""
        self.email: str = ""
        self.idp_id: str = ""
        self.personal_email: str = ""
        self.home_location: str = ""
        self.work_location: str = ""
        self.cost_center: str = ""
        self.department: str = ""
        self.managers = []
        self.groups = []
        self.start_date: str = ""
        self.termination_date: str = ""
        self.job_title: str = ""
        self.employment_types = []
        self.primary_time_zone: str = ""

        self._property_definitions = None
        self.custom_properties: dict = {}

    def __str__(self) -> str:
        return f"HRISEmployee - {self.name} ({self.unique_id})"

    def __repr__(self) -> str:
        return f"HRISEmployee(unique_id: {self.unique_id!r}, name: {self.name!r}, employee_number: {self.employee_number!r}, first_name: {self.first_name!r}, last_name: {self.last_name!r}, is_active: {self.is_active!r}, employment_status: {self.employment_status!r})"

    def add_group(self, group_id: str) -> None:
        """Add employee to group

        Adds employee to a group by the group ID. Group must also be defined for HRISInstance with `HRISProvider.add_group()`

        Args:
            group_id (str): Unique ID of HRISGroup to add employee too
        """

        if group_id not in self.groups:
            self.groups.append(group_id)

        return

    def add_manager(self, manager_id: str) -> None:
        """Add manager to Employee

        Adds a manager to the employee by the manager's HRISEmployee instance unique ID. Manger employee record must also exist.

        Args:
            manager_id (str): Unique ID for manager HRISEmployee instance
        """

        if manager_id not in self.managers:
            self.managers.append(manager_id)

        return

    def set_property(self, property_name: str, property_value: any, ignore_none: bool = False) -> None:
        """Set Employee custom property value

        Property name must be defined for employee before calling `set_property`

        Args:
            property_name (str): Name of property
            property_value (any): Value for property, type should match OAAPropertyType for property definition
            ignore_none (bool, optional): Do not set property if value is None. Defaults to False.. Defaults to False.

        Raises:
            OAATemplateException: If property with `property_name` is not defined.
        """

        if self._property_definitions is not None:
            if not isinstance(self._property_definitions, CaseInsensitiveDict):
                raise OAATemplateException("employee property_definitions not of expected type")

            if property_name not in self._property_definitions:
                raise OAATemplateException(f"unknown employee property name {property_name}")
        else:
            log.warning("Employee does not have property names set, cannot validate property name")

        if ignore_none and property_value is None:
            return

        self.custom_properties[property_name] = property_value

        return

    def to_dict(self) -> dict:
        """ Output employee to dictionary for payload. """

        user = {"id": self.unique_id,
                "name": self.name,
                "employee_number": self.employee_number,
                "company": self.company,
                "first_name": self.first_name,
                "last_name": self.last_name,
                "preferred_name": self.preferred_name,
                "display_full_name": self.display_full_name,
                "canonical_name": self.canonical_name,
                "username": self.username,
                "email": self.email,
                "idp_id": self.idp_id,
                "personal_email": self.personal_email,
                "home_location": self.home_location,
                "work_location": self.work_location,
                "employment_status": self.employment_status,
                "start_date": self.start_date,
                "termination_date": self.termination_date,
                "job_title": self.job_title,
                "employment_types": self.employment_types,
                "primary_time_zone": self.primary_time_zone,
                "custom_properties": self.custom_properties
                }

        if isinstance(self.is_active, bool):
            user["is_active"] = self.is_active

        # entities that need reference by ID
        user["groups"] = [{"id": group_id} for group_id in self.groups]
        user["managers"] = [{"id": manager_id} for manager_id in self.managers]
        if self.department:
            user["department"] = {"id": self.department}
        if self.cost_center:
            user["cost_center"] = {"id": self.cost_center}

        # filter out None/empty values before return
        return {k: v for k, v in user.items() if v not in [None, [], {}, ""]}


class HRISGroup():
    """HRIS Group

    Represents any group of employees in the HRIS system. HRISGroups can be used to represent teams, departments, cost centers
    or any organizational unit. Each group has a type to make searching and grouping easier.

    Group's Unique ID must be unique across all group types.

    Args:
        unique_id (str): Unique ID for group
        name (str): Display name
        group_type (str): Type for group such as "Team", "Department", "Cost Center"
    """

    def __init__(self, unique_id: str, name: str, group_type: str):


        self.unique_id = unique_id
        self.name = name
        self.group_type = group_type

        self._property_definitions = None
        self.custom_properties = {}

    def __str__(self) -> str:
        return f"HRISGroup - {self.name} ({self.unique_id}) - {self.group_type}"

    def __repr__(self) -> str:
        return f"HRISGroup(unique_id={self.unique_id!r}, name={self.name!r}, group_type={self.group_type!r})"

    def set_property(self, property_name: str, property_value: any, ignore_none: bool = False) -> None:
        """Set HRIS Group custom property value

        Property name must be defined for group before calling `set_property`

        Args:
            property_name (str): Name of property
            property_value (any): Value for property, type should match OAAPropertyType for property definition
            ignore_none (bool, optional): Do not set property if value is None. Defaults to False.. Defaults to False.

        Raises:
            OAATemplateException: If property with `property_name` is not defined.
        """

        if self._property_definitions is not None:
            if not isinstance(self._property_definitions, CaseInsensitiveDict):
                raise OAATemplateException("group property_definitions not of expected type")

            if property_name not in self._property_definitions:
                raise OAATemplateException(f"unknown group property name {property_name}")
        else:
            log.warning("Group does not have property names set, cannot validate property name")

        if ignore_none and property_value is None:
            return

        self.custom_properties[property_name] = property_value

        return

    def to_dict(self) -> dict:
        """Dictionary output for inclusion in payload"""

        group = {"id": self.unique_id,
                 "name": self.name,
                 "group_type": self.group_type,
                 "custom_properties": self.custom_properties
                }
        return {k: v for k, v in group.items() if v not in [None, [], {}]}

class HRISPropertyDefinitions():

    def __init__(self):

        self.system_properties = CaseInsensitiveDict()
        self.employee_properties = CaseInsensitiveDict()
        self.group_properties = CaseInsensitiveDict()

    def to_dict(self) -> dict:

        definitions = {
            "system_properties": {k:v for k,v in self.system_properties.items()},
            "employee_properties": {k:v for k,v in self.employee_properties.items()},
            "group_properties": {k:v for k,v in self.group_properties.items()}
        }

        return definitions

    def define_system_property(self, name: str, property_type: OAAPropertyType) -> None:
        self.validate_name(name)
        self._validate_types(name, property_type)
        self.system_properties[name] = property_type

    def define_employee_property(self, name: str, property_type: OAAPropertyType) -> None:
        self.validate_name(name)
        self._validate_types(name, property_type)
        self.employee_properties[name] = property_type

    def define_group_property(self, name: str, property_type: OAAPropertyType) -> None:
        self.validate_name(name)
        self._validate_types(name, property_type)
        self.group_properties[name] = property_type

    def _validate_types(self, name: str, property_type: OAAPropertyType) -> None:
        """ Helper function to validate that custom property parameters are of the correct types.

        Args:
            name (str): name or property
            property_type (OAAPropertyType): OAA type for property

        """
        if not isinstance(name, str):
            raise OAATemplateException("property name must be type string")
        if not isinstance(property_type, OAAPropertyType):
            raise OAATemplateException("property_type must be type OAAPropertyType enum")

        return

    def validate_name(self, name: str) -> None:
        """Check property name for valid characters

        Raises an exception if the name string does not match required pattern. Name must start with
        a character and can only contain letters and _ character.

        Args:
            name (str): name of property to validate

        Raises:
            OAATemplateException: Name is not a string
            OAATemplateException: Name contains invalid characters or does not start with a letter
        """

        if not isinstance(name, str):
            raise OAATemplateException(f"Property name must be a string, received {type(name)}")

        if not re.match(PROPERTY_NAME_REGEX, name.lower()):
            raise OAATemplateException(f"Lower-cased property name must match the pattern: '{PROPERTY_NAME_REGEX}'. Invalid name: {name}")

        return

