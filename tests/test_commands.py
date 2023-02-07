import logging
import os
import sys


import pytest
from unittest.mock import MagicMock, patch

import oaaclient.client
import oaaclient.utils

# enable debug logging
logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger()
log.setLevel(logging.DEBUG)

@patch.object(oaaclient.client.OAAClient, "_test_connection", return_value=None)
@patch.object(os, "getenv", return_value="abc123")  # patch the getenv call that will be made for the Veza API key
@patch.object(sys, "argv", ["oaaclient-report-builder", "--host", "https://noreal.vezacloud.com", "tests/report_test.json"])
def test_report_builder_entrypoint(test_connection_mock, mock_getenv) -> None:

    with patch("oaaclient.utils.build_report") as mock_build_report:
        oaaclient.client.report_builder_entrypoint()

    assert mock_build_report.called
    mock_build_report.assert_called()
