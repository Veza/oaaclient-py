"""
Copyright 2022 Veza Technologies Inc.

Use of this source code is governed by the MIT
license that can be found in the LICENSE file or at
https://opensource.org/licenses/MIT.
"""

import logging

import oaaclient.templates
from oaaclient.templates import log, unique_strs

def test_unique_strs():
    input = ["str1", "str2", "str3"]
    assert unique_strs(input) == input

    input = ["STR1", "STR1", "STR2", "str3", "str1"]
    assert unique_strs(input) == ["STR1", "STR2", "str3"]

    assert unique_strs([]) == []

def test_log_is_module_logger():
    """`log` must remain importable from oaaclient.templates as the module's logger."""
    assert isinstance(log, logging.Logger)
    assert log.name == "oaaclient.templates"

def test_all_exports_are_present():
    """Every name listed in __all__ must resolve to an actual attribute of the package.

    Guards against the class of regression where a package split (e.g. templates.py ->
    templates/) drops a re-export that was previously reachable with no __all__ restricting it.
    """
    missing = [name for name in oaaclient.templates.__all__ if not hasattr(oaaclient.templates, name)]
    assert not missing