#!env python3
"""

Classes for calling Veza APIs and managing OAA providers and data sources.

Copyright 2022 Veza Technologies Inc.

Use of this source code is governed by the MIT
license that can be found in the LICENSE file or at
https://opensource.org/licenses/MIT.
"""

from __future__ import annotations

import argparse
import base64
import gzip
import json
import logging
import os
import platform
import re
import socket
import sys
import urllib.parse
from datetime import datetime
from enum import Enum

import requests
from requests.adapters import HTTPAdapter
from requests.exceptions import JSONDecodeError as RequestsJSONDecodeError
from urllib3.util.retry import Retry

from oaaclient import __version__ as OAACLIENT_VERSION
import oaaclient.utils as oaautils
from oaaclient.templates import CustomApplication, CustomIdPProvider

PROVIDER_ICON_MAX_SIZE = 64_000

log = logging.getLogger(__name__)

class OAAClientError(Exception):
    """Error raised by OAAClient.

    Raised for issues connecting to the OAA API and when the API returns an error.

    Args:
        error (str): short string for error message
        message (str): detailed error message
        status_code (int, optional): status code for HTTP related errors. Defaults to None.
        details (list, optional): list of additional details for error. Defaults to None.
    """

    def __init__(self, error: str, message:str , status_code: int = None, details: list = None) -> None:
        self.error = error
        self.message = message
        self.status_code = status_code
        if not details:
            self.details = []
        else:
            self.details = details

        super().__init__(self, f"{error}: {message}")

class OAAResponseError(OAAClientError):
    """ Error returned from API Call"""

    def __init__(self, *args, **kwargs):

        self.request_id = kwargs.pop("request_id", None)
        self.timestamp = kwargs.pop("timestamp", None)
        super().__init__(*args, **kwargs)
        return

class OAAConnectionError(OAAClientError):
    """ Error with API Connection"""

class OAAClient():
    """Class for OAA API Connection and Management.

    Utilities for OAA-related operations with Veza API calls. Manages custom providers and data sources, and can push OAA
    payloads from JSON or template objects.

    Connection url and API key can be automatically loaded from OS environment values if set. To utilize environment variables
    initialize OAAClient without providing a URL or API key value and set the `VEZA_URL` and `VEZA_API_KEY` OS environment variables.

    Args:
        url (str, optional): URL for Veza instance.
        api_key (str, optional): Veza API key.
        username (str, optional): Not used (legacy). Defaults to None.
        token (str, optional): Legacy parameter name for API key. Defaults to None.

    Attributes:
        url (str): URL of the Veza instance to connect to
        api_key (str): Veza API key
        enable_compression (bool): Enable or disable compression of the OAA payload during push, defaults to enabled (True)

    Raises:
        OAAClientError: For errors connecting to API and if API returns errors
    """
    # maximum number of times to retry a API calls, can be set with environment variable OAA_API_RETRIES
    DEFAULT_RETRY_COUNT = 10
    # Backoff multiplier factor for time between API retries in seconds
    # Back time exponential formula: {backoff factor} * (2 ^ ({retry number} - 1))
    DEFAULT_RETRY_BACKOFF_FACTOR = 0.6
    # maximum amount of time to backoff for between calls
    DEFAULT_RETRY_MAX_BACKOFF = 30

    # platform defined allowed characters for use unless otherwise allowed defined
    ALLOWED_CHARACTERS = r"^[ @#$%&*:()!,a-zA-Z0-9_'\"=.-]*$"

    # default number of entities to get when requesting a page size.
    # Must be passed with params for API call when calling paging APIs `params={"page_size": self.DEFAULT_PAGE_LENGTH}`
    DEFAULT_PAGE_SIZE = 250

    def __init__(self, url:str = None, api_key: str = None, username: str = None, token: str = None):

        if not url and "VEZA_URL" in os.environ:
            url = os.getenv("VEZA_URL", "")
        elif not url:
            raise ValueError("Must provide Veza URL")

        if not re.match(r"^https:\/\/.*", url):
            self.url = f"https://{url}"
        else:
            self.url = url
        self.url = self.url.rstrip("/")

        # for development purposes only sometimes system is run without signed certificates,
        # disable certificate verification only if VEZA_UNSAFE_HTTPS OS env variable is set to true
        self.verify_ssl = True
        unsafe_https = os.getenv("VEZA_UNSAFE_HTTPS", "")
        if unsafe_https.lower() == "true":
            self.verify_ssl = False

        self.username = username

        if api_key:
            self.api_key = api_key
        elif token:
            self.api_key = token
        elif "VEZA_API_KEY" in os.environ:
            self.api_key = os.getenv("VEZA_API_KEY", "")
        else:
            raise ValueError("Must provide Veza API key")

        if not self.url:
            raise OAAClientError("MISSING_URL", "URL cannot be None")
        if not self.api_key:
            raise OAAClientError("MISSING_AUTH", "API key cannot be None")

        # enable payload compression by default, connection object property can be set to False to disable
        self.enable_compression = True

        # setup retry strategy for API calls

        try:
            retry_count = int(os.getenv("OAA_API_RETRIES", self.DEFAULT_RETRY_COUNT))
        except ValueError:
            log.error(f"OAA_API_RETRIES variable must be integer, ignoring and setting to default {self.DEFAULT_RETRY_COUNT}")
            retry_count = self.DEFAULT_RETRY_COUNT

        retry_policy = OAARetry(backoff_max=self.DEFAULT_RETRY_MAX_BACKOFF, total=retry_count, backoff_factor=self.DEFAULT_RETRY_BACKOFF_FACTOR, status_forcelist=[429, 500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retry_policy)
        self._http_adapter = requests.Session()
        self._http_adapter.mount("https://", adapter)
        self._http_adapter.mount("http://", adapter)

        self.update_user_agent()

        # test connection
        self._test_connection()

    def get_provider_list(self) -> list[dict]:
        """Return list of Providers.

        Returns:
            list[dict]: Returns a list of existing Providers as dictionaries
        """

        return self.api_get("/api/v1/providers/custom", params={"page_size": self.DEFAULT_PAGE_SIZE})

    def get_provider(self, name: str) -> dict:
        """Get Provider by name.

        Args:
            name (str): name of Provider

        Returns:
            dict: dictionary representing Provider or None
        """
        filter = {"filter": f"name eq \"{name}\""}
        response = self.api_get(f"/api/v1/providers/custom", params=filter)

        # expect a list of one or empty
        if not response:
            # no provider with that name found
            provider = None
        elif len(response) == 1:
            provider = response[0]
        else:
            # this shouldn't happen
            raise OAAClientError(error="Unexpected Results", message = "Unexpected results in response, returned more than one result")

        # return the provider detail
        return provider

    def get_provider_by_id(self, provider_id: str) -> dict:
        """Get Provider by UUID identifier.

        Args:
            provider_id (str): Unique global identifier for provider

        Returns:
            dict: dictionary representation of Provider or None
        """
        try:
            response = self.api_get(f"/api/v1/providers/custom/{provider_id}")
        except OAAResponseError as e:
            if e.status_code == 404:
                # Provider not found, return None
                return None
            else:
                raise e

        return response

    def create_provider(self, name: str, custom_template: str, base64_icon: str = None) -> dict:
        """Create a new Provider.

        Creates a new Provider with the given name. An error will be raised for naming conflicts.

        Args:
            name (str): new Provider name
            custom_template (str): the OAA template to use for the Provider ("application" or "identity_provider")
            base64_icon (str, optional): Base64 encoded string of icon to set for Provider. Defaults to None.

        Raises:
            ValueError: Provider name contains invalid characters

        Returns:
            dict: dictionary representing the created Provider
        """

        if not re.match(self.ALLOWED_CHARACTERS, name):
            raise ValueError(f"Provider name contains invalid characters, must match {self.ALLOWED_CHARACTERS}")

        provider = self.api_post("/api/v1/providers/custom", {"name": name, "custom_template": custom_template})
        if base64_icon:
            self.update_provider_icon(provider['id'], base64_icon)

        return provider

    def update_provider_icon(self, provider_id: str, base64_icon: str) -> None:
        """ Update an existing custom provider icon from base64 encoded string.

        To load an icon from file,  use `utils.encode_icon_file` to get the base64 encoding of the file first

        Args:
            provider_id (str): unique ID of existing provider
            base64_icon (str): base64 encoded string of new icon

        Raises:
            ValueError: If icon size exceeds maximum allowed size

        """
        if sys.getsizeof(base64_icon) > PROVIDER_ICON_MAX_SIZE:
            raise ValueError("Max icon size of 64KB exceeded")

        if isinstance(base64_icon, bytes):
            base64_icon = base64_icon.decode()

        icon_payload = {"icon_base64": base64_icon}
        self.api_post(f"/api/v1/providers/custom/{provider_id}:icon", data=icon_payload)

        return None

    def delete_provider(self, provider_id: str) -> dict:
        """Delete an existing provider by ID.

        Deleting a provider removes all datasources and historical data.
        Fully deleting the provider is a background operation that will complete after API response is returned.

        Args:
            provider_id (str): ID of provider to delete

        Returns:
            dict: API response
        """
        response = self.api_delete(f"/api/v1/providers/custom/{provider_id}")
        return response


    def get_data_sources(self, provider_id: str) -> list[dict]:
        """Get Data Sources for Provider by ID.

        Get the list of existing Data Sources, filtered by Provider UUID.

        Args:
            provider_id (str): ID of Provider

        Returns:
            list[dict]: List of Data Sources as dictionaries
        """

        return self.api_get(f"/api/v1/providers/custom/{provider_id}/datasources", params={"page_size": self.DEFAULT_PAGE_SIZE})


    def get_data_source(self, name:str, provider_id:str) -> dict:
        """Get Provider's Data Source by name.

        Find a Data Source from a specific provider based on the name of the Data Source

        Args:
            name (str): Data Source name
            provider_id (str): Provider unique ID

        Returns:
            dict: Data Source as dict or None
        """

        filter = {"filter": f"name eq \"{name}\""}
        response = self.api_get(f"/api/v1/providers/custom/{provider_id}/datasources", params=filter)

        # expect a list of one or empty
        if not response:
            # no data_source with that name found, return None
            data_source = None
        elif len(response) == 1:
            data_source = response[0]
        else:
            # this shouldn't happen
            raise OAAClientError(error="Unexpected Results", message = "Unexpected results in response, returned more than one result")

        return data_source

    def create_data_source(self, name: str, provider_id: str) -> dict:
        """Create a new Data Source for the given Provider ID.

        Args:
            name (str): Name for new Data Source
            provider_id (str): Unique identifier for the Provider

        Raises:
            ValueError: Data source name contains invalid characters

        Returns:
            dict: dictionary of new Data Source
        """

        if not re.match(self.ALLOWED_CHARACTERS, name):
            raise ValueError(f"Data source name contains invalid characters, must match {self.ALLOWED_CHARACTERS}")

        data_source = {"name": name, "id": provider_id}
        return self.api_post(f"/api/v1/providers/custom/{provider_id}/datasources", data=data_source)

    def create_datasource(self, name, provider_id):
        """
        **Deprecated** Legacy function for backward-compatibility.
        """
        return self.create_data_source(name, provider_id)

    def delete_data_source(self, data_source_id: str, provider_id: str) -> dict:
        """Delete an existing Data Source by ID.

        Removes a Data Source and all entity data.

        Args:
            data_source_id (str): ID of Data Source to delete
            provider_id (str): ID of Data Source Provider

        Returns:
            dict: API response
        """
        response = self.api_delete(f"/api/v1/providers/custom/{provider_id}/datasources/{data_source_id}")
        return response

    def push_metadata(self, provider_name: str, data_source_name: str, metadata: dict, save_json: bool = False) -> dict:
        """Push an OAA payload dictionary to Veza.

        Publishes the supplied `metadata` dictionary representing an OAA payload to the specified provider and
        data source. The function will create a new data source if it does not already exist, but requires the Provider be
        created ahead of time.

        Args:
            provider_name (str): Name of existing Provider
            data_source_name (str): Name for Data Source, will be created if doesn't exist.
            metadata (dict): Dictionary of OAA payload to push.
            save_json (bool, optional): Save the OAA JSON payload to a local file before push. Defaults to False.

        Raises:
            OAAClientError: If any API call returns an error including errors processing the OAA payload.

        Returns:
            dict: API response to the push request (including any warnings).
        """

        provider = self.get_provider(provider_name)
        if not provider:
            raise OAAClientError("NO_PROVIDER", f"Unable to locate provider {provider_name}, cannot push without existing provider")
        data_source = self.get_data_source(data_source_name, provider["id"])
        if not data_source:
            self.create_datasource(data_source_name, provider["id"])
            data_source = self.get_data_source(data_source_name, provider["id"])

        if save_json:
            ts = datetime.now().strftime("%Y%m%d-%H%M%S")
            out_name = f"{data_source_name}-{ts}.json"
            with open(out_name, "w") as f:
                f.write(json.dumps(metadata, indent=2))

        if self.enable_compression:
            log.debug("Compressing payload")
            metadata_bytes = json.dumps(metadata).encode()
            metadata_size = sys.getsizeof(metadata_bytes)
            compressed_bytes = gzip.compress(metadata_bytes)
            del metadata_bytes

            encoded = base64.b64encode(compressed_bytes).decode()
            encoded_size = sys.getsizeof(encoded)
            del compressed_bytes
            log.debug(f"Compression complete, payload size in bytes: {metadata_size:,}, encoded compressed: {encoded_size:,}")
            payload = {"id": provider["id"], "data_source_id": data_source["id"], "json_data": encoded, "compression_type": "GZIP"}
        else:
            payload = {"id": provider["id"], "data_source_id": data_source["id"], "json_data": json.dumps(metadata)}

        payload_size = sys.getsizeof(payload["json_data"])
        if payload_size > 100_000_000:
            raise OAAClientError("OVERSIZE", message=f"Payload size exceeds maximum size of 100MB: {payload_size:,} bytes, compression enabled: {self.enable_compression}")

        log.debug(f"Final payload size: {payload_size:,} bytes")
        result = self.api_post(f"/api/v1/providers/custom/{provider['id']}/datasources/{data_source['id']}:push", payload)

        return result

    def push_application(self, provider_name: str, data_source_name: str, application_object: CustomApplication|CustomIdPProvider, save_json: bool = False, create_provider: bool = False) -> dict:
        """Push an OAA Application Object (such as CustomApplication).

        Extracts the OAA JSON payload from the supplied OAA class (e.g. CustomApplication, CustomIdPProvider, etc) and push to
        the supplied Data Source.

        The Provider with `provider_name` must be a valid existing Provider or `create_provider` must be set to `True`.  A new data source
        will be created automatically by default if it does not already exist.

        For logging, and debugging, the optional `save_json` flag writes the payload to a local file (before push). Output file name
        is formatted with a timestamp: `{data source name}-{%Y%m%d-%H%M%S}.json`

        Args:
            provider_name (str): Name of an existing Provider.
            data_source_name (str): Name for Data Source (will be created if it doesn't exist).
            application_object (Class): OAA object to extract the payload from
            save_json (bool, optional): Save the JSON payload to a local file before push. Defaults to False.
            create_provider (bool, optional): Create a new Provider if Provider does not already exists. Defaults to False.

        Raises:
            OAAClientError: If any API call returns an error (including errors processing the OAA payload).

        Returns:
            dict: API response from push, including any warnings that are returned.
        """

        if create_provider:
            if not hasattr(application_object, "TEMPLATE"):
                raise OAAClientError(error="INVALID_APP", message="Cannot create provider for application object without TEMPLATE")

            provider = self.get_provider(provider_name)
            if not provider:
                self.create_provider(provider_name, custom_template=application_object.TEMPLATE)

        metadata = application_object.get_payload()

        return self.push_metadata(provider_name, data_source_name, metadata, save_json=save_json)

    def get_queries(self, include_inactive_queries:bool = True) -> list[dict]:
        """Get all saved Assessment Queries

        Veza can filter out queries that include inactive entity types (e.g. Okta Users on a system without Okta configured).
        To only retrieve queries that include active entity types set `include_inactive_queries` to False.

        Args:
            include_inactive_queries (bool): Set False to exclude inactive queries from result. Defaults to True.

        Returns:
            list: List of assessment Queries as dictionaries
        """

        params = {}
        params["include_inactive_queries"] = include_inactive_queries
        params["page_size"] = self.DEFAULT_PAGE_SIZE

        return self.api_get("/api/v1/assessments/queries", params=params)

    def get_query_by_id(self, id: str) -> dict:
        """Get Assessment Query by ID

        Args:
            id (str): UUID identifier for Query

        Returns:
            dict: Query definition
        """

        return self.api_get(f"/api/v1/assessments/queries/{id}")

    def create_query(self, query: dict) -> dict:
        """Create a new Assessment Query

        For details on how to define an Assessment Query see the Veza docs.

        Args:
            query (dict): Query definition

        Returns:
            dict: API response including ID of created Query
        """

        return self.api_post("/api/v1/assessments/queries", data=query)

    def delete_query(self, id: str, force: bool = False) -> dict:
        """Delete an Assessment Query by ID

        Args:
            id (str): UUID of Query to delete
            force (bool): Force deletion of query that may be part of a report. Defaults to False

        Returns:
            dict: API response from delete
        """

        params = {"force": force}
        return self.api_delete(f"/api/v1/assessments/queries/{id}", params)

    def get_reports(self, include_inactive_reports: bool = True, include_inactive_queries: bool = True) -> list[dict]:
        """Get all Reports

        Gets Reports created on the system. To get all reports `include_inactive_reports` and `include_inactive_queries` must be set
        to True.

        Args:
            include_inactive_reports (bool, Optional): Set to True to include reports that contain no active providers, defaults to True.
            include_inactive_queries (bool, Optional): Set to True to include reports that contain only inactive queries, defaults to True.

        Returns:
            list[dict]: List of Reports as dictionary objects
        """

        params = {}
        params["include_inactive_reports"] = include_inactive_reports
        params["include_inactive_queries"] = include_inactive_queries
        params["page_size"] = self.DEFAULT_PAGE_SIZE

        return self.api_get("/api/preview/assessments/reports", params=params)

    def get_report_by_id(self, id: str, include_inactive_queries: bool = True) -> dict:
        """Get Report by ID

        Veza can filter out queries from reports that only contain entity types that are not configured (e.g. Okta
        Users on a system without Okta configured). To only return queries configured on the report that match entity
        types configured on the system set `include_inactive_queries` to `False`

        Args:
            id (str): UUID of Report to get
            include_inactive_queries (bool): Set True to include inactive queries. Default True.
        Returns:
            dict: Report definition
        """

        params = {"include_inactive_queries": include_inactive_queries}
        return self.api_get(f"/api/preview/assessments/reports/{id}", params=params)

    def create_report(self, report: dict) -> dict:
        """Create a new Report

        For details on how to define a new Report see the Veza docs.

        Args:
            report (dict): Report definition

        Returns:
            dict: API response including ID of created Report
        """

        return self.api_post("/api/preview/assessments/reports", data=report)

    def update_report(self, report_id: str, report: dict) -> dict:
        """Update an existing report

        Args:
            report_id (str): UUID of Report to updated
            report (dict): Updated Report definition

        Returns:
            dict: API response
        """

        return self.api_put(f"/api/preview/assessments/reports/{report_id}", data=report)

    def add_query_report(self, report_id: str, query_id: str) -> dict:
        """Add a Query to a Report

        Adds a Query to an existing Report by ID

        Args:
            report_id (str): Report UUID to add Query to
            query_id (str): Query UUID to add

        Returns:
            dict: API Response
        """

        return self.api_put(f"/api/preview/assessments/reports/{report_id}/queries/{query_id}", data=None)

    def delete_report(self, id: str) -> dict:
        """Delete Report by ID

        Args:
            id (str): UUID of Report to delete

        Returns:
            dict: API response
        """

        return self.api_delete(f"/api/preview/assessments/reports/{id}")

    def api_get(self, api_path: str, params: dict = None) -> list|dict:
        """Perform a Veza API GET operation.

        Makes the GET API call to the given path and processes the API response. Returns the `value` or `values` result
        returned from the API.

        - For API endpoints that return a list like `/api/v1/providers/custom` function will return a list of entities or an
        empty list if the API returns no results.
        - For API endpoints that are a specific ID such as `/api/v1/providers/custom/<uuid>` function will return the
        dictionary result of the JSON returned by the API.

        Args:
            api_path (str): API path relative to Veza URL (example `/api/v1/providers`).

        Raises:
            OAAResponseError: API returned an error
            OAAConnectionError: Connection error during HTTP operation

        Returns:
            list|dict: Returns list or dict based on API destination
        """

        result = []

        if not params:
            params = {}

        while True:
            response = self._perform_request(method="GET", api_path=api_path, params=params)


            if "values" in response:
                # paginated response,
                result.extend(response.get("values", []))
                if response.get("has_more"):
                    params["page_token"] = response.get("next_page_token")
                else:
                    # no more pages
                    break
            elif "value" in response:
                # singular API response, set return value to response value
                result = response["value"]
                break
            else:
                # unexpected API response, just return the result
                return response

        return result

    def api_post(self, api_path: str, data: dict, params: dict = None) -> list|dict:
        """Perform a Veza API POST operation.

        Call POST on the supplied Veza instance API path, submitting a data payload.

        Returns `value` or `values` response from API result. Paginated responses are automatically processed to
        collect all responses a single list.

        Args:
            api_path (str): API path relative to Veza URL example `/api/v1/providers`
            data (dict): dictionary object included as JSON in body of POST operation
            params (dict, optional): Optional HTTP query parameters. Defaults to empty dictionary.

        Raises:
            OAAResponseError: API returned an error
            OAAConnectionError: Connection error during HTTP operation

        Returns:
            dict: API response as dictionary
        """

        if not params:
            params = {}

        result = []
        while True:
            response = self._perform_request(method="POST", api_path=api_path, data=data, params=params)


            if "values" in response:
                # paginated response,
                result.extend(response.get("values", []))
                if response.get("has_more"):
                    params["page_token"] = response.get("next_page_token")
                else:
                    # no more pages
                    break
            elif "value" in response:
                # singular API response, set return value to response value
                result = response["value"]
                break
            else:
                # unexpected API response, just return the result
                return response

        return result

    def api_put(self, api_path: str, data: dict, params: dict = None) -> list|dict:
        """Perform Veza API PUT operation.

        Call PUT on the supplied Veza instance API path, including the data payload.

        Returns `value` or `values` response from API result. Paginated responses are automatically processed to
        collect all responses a single list.

        Args:
            api_path (str): API path relative to Veza URL example `/api/v1/providers`
            data (dict): dictionary object included as JSON in body of PUT operation
            params (dict, optional): Optional HTTP query parameters. Defaults to empty dictionary.

        Raises:
            OAAResponseError: API returned an error
            OAAConnectionError: Connection error during HTTP operation

        Returns:
            dict: API response as dictionary
        """

        if not params:
            params = {}

        result = []
        while True:
            response = self._perform_request(method="PUT", api_path=api_path, data=data, params=params)

            if "values" in response:
                # paginated response,
                result.extend(response.get("values", []))
                if response.get("has_more"):
                    params["page_token"] = response.get("next_page_token")
                else:
                    # no more pages
                    break
            elif "value" in response:
                # singular API response, set return value to response value
                result = response["value"]
                break
            else:
                # unexpected API response, just return the result
                return response

        return result

    def api_patch(self, api_path:str, data: dict, params: dict = None) -> dict:
        """Perform REST API PATCH operation.

        Args:
            api_path (str): API Path API path relative to Veza URL

        Raises:
            OAAResponseError: API returned an error
            OAAConnectionError: Connection error during HTTP operation

        Returns:
            dict: API response from call
        """
        return self._perform_request(method="PATCH", api_path=api_path, data=data, params=params)

    def api_delete(self, api_path:str, params: dict = None) -> dict:
        """Perform REST API DELETE operation.

        Args:
            api_path (str): API Path API path relative to Veza URL

        Raises:
            OAAResponseError: API returned an error
            OAAConnectionError: Connection error during HTTP operation

        Returns:
            dict: API response from call
        """
        return self._perform_request(method="DELETE", api_path=api_path, params=params)

    def _perform_request(self, method: str, api_path: str, data: dict = None, params: dict = None) -> dict:
        """Perform HTTP request

        Performs an HTTP request of the specified method to the Veza tenant

        Args:
            method (str): HTTP method, GET, POST, DELETE
            api_path (str): API path relative to Veza host URL, e.g. `/api/v1/providers`
            data (dict, optional): For POST operation data to send. Defaults to None.

        Raises:
            OAAClientError: For errors connecting to or returned by the Veza tenant

        Returns:
            dict: Veza API JSON response as dictionary
        """

        response = None

        headers = {}
        headers["authorization"] = f"Bearer {self.api_key}"
        headers["user-agent"] = self._user_agent
        api_timeout = 300
        api_path = api_path.lstrip("/")

        if params:
            params_str = urllib.parse.urlencode(params)
        else:
            params_str = None

        try:
            response = self._http_adapter.request(method, f"{self.url}/{api_path}", headers=headers, timeout=api_timeout, params=params_str, json=data, verify=self.verify_ssl)
            response.raise_for_status()
            # load API response
            result = response.json()
        except requests.exceptions.HTTPError as e:
            # HTTP request completed but returned an error
            # decode expected error message parts
            details = []
            timestamp = None
            request_id = None
            try:
                result = response.json()
                message = result.get("message", f"Unknown error during {method.upper()}")
                code = result.get("code", "UNKNOWN")
                timestamp = result.get("timestamp", None)
                request_id = result.get("request_id", None)
                details = result.get("details", [])
            except requests.exceptions.JSONDecodeError:
                # response is not a valid JSON, unexpected
                result = {}
                code = "ERROR"
                if response.reason:
                    message = f"Error reason: {response.reason}"
                else:
                    message = "Unknown error, response is not JSON"

            log.debug(f"Error returned by Veza API: {e.response.status_code} {message} {e.response.url} request_id: {request_id} timestamp {timestamp}")
            for d in details:
                log.debug(d)

            raise OAAResponseError(code, message, status_code=e.response.status_code, details=details, timestamp=timestamp, request_id=request_id)
        except requests.exceptions.JSONDecodeError as e:
            # HTTP response reports success but response does not decode to JSON
            if response:
                status_code = response.status_code
            else:
                status_code = None
            raise OAAClientError("ERROR", "Response not JSON", status_code=status_code)
        except requests.exceptions.RequestException as e:
            if not e.response:
                raise OAAConnectionError("ERROR", message=str(e))
            else:
                raise OAAConnectionError("ERROR", message=str(e), status_code=e.response.status_code)

        return result

    def _test_connection(self) -> None:
        """Test the OAAClient connection

        Validates the Veza URL and API key with a test call. Raises an exception
        when unable to connect to the Veza host.

        Raises:
            OAAResponseError: For errors returned by Veza including 401 for bad credentials
            OAAConnectionError: When unable to connect to Veza API.
        """


        # do separate DNS lookup to quickly fail if the hostname isn't resolving
        veza_url = urllib.parse.urlsplit(self.url)
        try:
            x = socket.getaddrinfo(veza_url.hostname, 0)
        except socket.gaierror as e:
            log.debug("DNS lookup failure during connection test")
            raise OAAConnectionError("Unknown host", message=f"Unable to lookup DNS for {veza_url.hostname}")

        # test connection to validate host and credentials
        try:
            self.api_get("/api/v1/providers/custom/templates")
        except OAAResponseError as e:
            log.debug("API returned error during API connection test")
            raise e
        except OAAConnectionError as e:
            log.debug("Unable to connect during API connection test")
            raise e

    def update_user_agent(self, extra: str = "") -> None:
        """Updates the User-Agent string passed with all API calls

        Generates a User-Agent with the oaaclient version, Python version and platform information.

        The optional `extra` string will be appended if provided.

        Args:
            extra (str, optional): Additional information to append to User-Agent string. Defaults to "".
        """

        python_version = platform.python_version()
        os_name = platform.system()
        os_version = platform.release()

        self._user_agent = f"oaaclient/{OAACLIENT_VERSION} python/{python_version} {os_name}/{os_version};"
        if extra:
            self._user_agent += f" {extra}"

        log.debug(f"User-Agent {self._user_agent}")

        return

class OAARetry(Retry):
    """Super class for urllib3.util.retry

    Super class to allow modifying the default max backoff time from 120 seconds
    to our own value

    Args:
        Retry (_type_): _description_
    """
    def __init__(self, backoff_max=30, **kwargs) -> None:
        super(OAARetry, self).__init__(**kwargs)
        #urllib3 1.x and 2.x have slightly different behavior for BACKOFF_MAX, setting both values covers both
        self.DEFAULT_BACKOFF_MAX = backoff_max
        self.backoff_max = backoff_max


def report_builder_entrypoint() -> None:
    """Entry point for `oaaclient-report-builder` command

    Reads a JSON file and passes it to the `oaaclient.utils.build_report` method
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=os.getenv("VEZA_URL"), help="URL endpoint for Veza Deployment")
    parser.add_argument("report_file", help="Path to source report file")
    args = parser.parse_args()

    # setup a log handler
    log = logging.getLogger()
    logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.INFO)

    report_file = args.report_file
    if not os.path.isfile(report_file):
        log.error(f"Unable to locate source file at path {report_file}")
        sys.exit(1)
    try:
        report_definition = oaautils.load_json_from_file(report_file)
    except Exception as e:
        log.error(e)
        sys.exit(1)

    veza_url = args.host
    veza_api_key = os.getenv("VEZA_API_KEY", "")
    if not veza_url:
        oaautils.log_arg_error(log, "--host", "VEZA_URL")
    if not veza_api_key:
        oaautils.log_arg_error(log, None, "VEZA_API_KEY")
    if not veza_url and veza_api_key:
        sys.exit(1)

    vezacon = OAAClient(veza_url, api_key=veza_api_key)

    log.info(f"Loading report from {report_file}")
    try:
        oaautils.build_report(vezacon, report_definition=report_definition)
    except OAAResponseError as e:
        log.error("Veza API error encounter building report")
        log.error(f"OAAResponseError {e.message} {e.status_code}")
        log.error(e.details)
        sys.exit(1)
    except OAAConnectionError as e:
        log.error("Error connecting to Veza")
        log.error(f"OAAConnectionError {e.message} {e.status_code}")
        sys.exit(1)
    except Exception as e:
        log.error("Error building report")
        log.error(e)
        sys.exit(1)

    log.info("Finished")
    return


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--auth-file", help="Config file with authentication information")
    parser.add_argument("--host", help="URL endpoint for Veza Deployment")
    parser.add_argument("--user", help="Username to connect as")
    parser.add_argument("--provider", required=True, help="Provider definition json file, will create if doesn't exist")
    parser.add_argument("metadata", help="Metadata json file to push, uses name of file as datasource name")
    args = parser.parse_args()

    host = None
    user = None
    password = None
    token = None

    if args.auth_file:
        if not os.path.isfile(args.auth_file):
            print(f"Error: Unable to locate auth file {args.auth_file}", file=sys.stderr)
            sys.exit(1)
        auth_config = oaautils.load_json_from_file(args.auth_file)

        host = auth_config['host']
        user = auth_config['user']
        if "token" in auth_config:
            token = auth_config['token']
        elif "password" in auth_config:
            password = auth_config['password']
    else:
        host = args.host
        user = args.user

    provider_metadata = oaautils.load_json_from_file(args.provider)

    try:
        provider_name = provider_metadata["name"]
        custom_template = provider_metadata['custom_template']
    except KeyError as e:
        raise Exception(f"Missing value in app template: {e}")

    try:
        con = OAAClient(host, api_key=token)
        provider = con.get_provider(provider_name)
        if provider:
            print("-- Found existing provider")
        else:
            print(f"++ Creating Provider {provider_name} of type {custom_template}")
            provider = con.create_provider(provider_name, custom_template)
        print(f"-- Provider: {provider['name']} ({provider['id']})")
        # utilize the file name as the datasource name
        data_source_name = os.path.splitext(os.path.basename(args.metadata))[0]

        print("-- Pushing metadata")
        metadata = oaautils.load_json_from_file(args.metadata)
        response = con.push_metadata(provider_name, data_source_name, metadata)
        if response.get("warnings", None):
            print("-- Push succeeded with warnings:")
            for e in response["warnings"]:
                print(f"  - {e}")
    except OAAClientError as e:
        print(f"-- Error: {e.error}: {e.message} ({e.status_code})", file=sys.stderr)
        if hasattr(e, "details"):
            for d in e.details:
                print(f"  -- {json.dumps(d, indent=2)}")
    return


if __name__ == "__main__":
    main()
