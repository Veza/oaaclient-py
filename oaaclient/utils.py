"""

`oaaclient` utility functions.

Copyright 2022 Veza Technologies Inc.

Use of this source code is governed by the MIT
license that can be found in the LICENSE file or at
https://opensource.org/licenses/MIT.

helper functions commonly used by OAA integrations
"""
import base64
import json
import os
import logging

log = logging.getLogger(__name__)

def log_arg_error(log: object, arg: str = None, env: str = None) -> None:
    """Helper function for logging errors when loading parameters

    Helper function used to create consistent messages in connectors when required parameters can be set at command
    line or as environment variables.

    Message can include information on parameter and/or environment variable but must provide one.

    Args:
        log (object): logging facility object to log to
        arg (str, optional): Command line option for parameter such as `--veza-url`. Defaults to None.
        env (str, optional): OS Environment variable for parameter such as `VEZA_URL`. Defaults to None.

    Raises:
        Exception: if neither `arg` or `env` are supplied
    """

    if arg and env:
        log.error(f"Unable to load required parameter, must supply {arg} or set OS environment variable {env}")
    elif arg and not env:
        log.error(f"Unable to load required parameter, must supply {arg}")
    elif env:
        log.error(f"Unable to load required parameter, must set OS environment variable {env}")
    else:
        raise Exception("Must provide arg or env to include in error message")
    return


def load_json_from_file(json_path: str) -> dict:
    """Load JSON from file

    Args:
        json_path (str): path to JSON file on disk

    Raises:
        Exception: Unable to process JSON
        Exception: Error reading JSON file

    Returns:
        dict: JSON decoded to dictionary
    """
    try:
        with open(json_path) as f:
            data = json.load(f)
    except json.decoder.JSONDecodeError as e:
        raise Exception(f"Unable to process JSON from {json_path}: {e}")
    except OSError as e:
        raise Exception(f"Error reading file {json_path}: {e}")

    return data

def encode_icon_file(icon_path: str) -> str:
    """ read an icon file to a base64 encoded string

    Args:
        icon_path (str): Path to icon file on disk

    Returns:
        str: base64 encoding of file
    """

    with open(icon_path, "rb") as f:
        b64_icon = base64.b64encode(f.read())

    return b64_icon.decode()

def exists_in_query_array(value_to_find, input_array) -> bool:
    for query in input_array:
        if query["name"] == value_to_find:
            return True

    return False


def build_report(veza_con, report_definition: dict) -> dict:
    """Creates or updates a Veza report from a dictionary

    Creates a report and containing queries from a dictionary definition. Function will create any queries it does not
    find based on name. If a query with the same name already exists the existing query will be added to the report.

    If a report already exists with the same name any missing queries will be added to the report.

    `report_definition` must be a dictionary with `name` for the report and `queries` list of Veza query
    definitions:

        {"name": "My Report", "queries": [{..},{...}]}

    Args:
        veza_con (OAAClient): OAAClient connection to make Veza API calls
        report_definition (dict): Report definition

    Raises:
        ValueError: Missing name or queries key

    Returns:
        dict: API response from Report creation or update
    """

    report_name = report_definition.get("name")
    if not report_name:
        raise ValueError("Report source file must contain 'name'")

    if not report_definition.get("queries"):
        raise ValueError("Report source file must contain 'queries' list")

    report_queries = report_definition.get("queries", [])

    # get all quires to know which queries need to be created and which don't
    all_queries = veza_con.get_queries()
    query_names = {}
    for q in all_queries:
        if q.get("query_type") == "SYSTEM_CREATED":
            continue
        query_names[q["name"]] = q["id"]

    # create queries that don't already exists
    query_ids = []
    query_in_report_name = []
    for query in report_definition.get("queries", []):
        if query["name"] in query_names:
            log.debug(f"Found existing query with same name, using for report, {query['name']}")
            query_ids.append(query_names[query["name"]])
            query_in_report_name.append(query["name"])
        else:
            log.debug(f"Creating query {query['name']}")
            response = veza_con.create_query(query=query)
            query_ids.append(response["id"])
            query_in_report_name.append(query["name"])

    # get all reports to know if report already exists
    existing_reports = {}
    for e in veza_con.get_reports():
        id = e.get("id")
        name = e.get("name")
        existing_reports[name] = id

    response = {}
    if report_name not in existing_reports:
        # create a new report
        log.debug("Creating new report")
        report_definition = { "name": report_name, "description": report_name, "queries": []}
        for id in query_ids:
            report_definition["queries"].append({"query": id})
        response = veza_con.create_report(report=report_definition)
    else:
        # update existing report
        report_id = existing_reports[report_name]
        log.debug(f"Updating report {report_id}")
        # Loop over query ID's
        for query_name in query_in_report_name:
            # if report exists, only add new queries
            if exists_in_query_array(query_name, report_queries):
                continue
            response = veza_con.add_query_report(report_id=report_id, query_id=query_names[query_name])

    # if the report is the exact same, it existed before so get report
    if response == {}:
        return veza_con.get_report_by_id(id=existing_reports[report_name])

    return response


def truncate_string(source_str: str, length: int = 256) -> str:
    """Helper function to truncate strings

    Helper function to truncate strings to conform to maximum length requirements for templates.

    Returns a string that is the first N bytes of the source string

    Args:
        source_str (str): Source string to truncate
        length (int, optional): Length to shorten to. Defaults to 256.

    Returns:
        str: truncated string
    """

    encoded = source_str.encode(encoding="utf-8", errors="replace")
    truncated = encoded[:length]

    result = truncated.decode(encoding="utf-8", errors="ignore")

    return result
