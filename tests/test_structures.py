"""
Copyright 2022 Veza Technologies Inc.

Use of this source code is governed by the MIT
license that can be found in the LICENSE file or at
https://opensource.org/licenses/MIT.
"""

import pytest

from oaaclient.structures import CaseInsensitiveDict

def test_caseinsensitivedict():

    x = CaseInsensitiveDict()

    x["User"] = "value"
    assert x["User"] == "value"
    assert x["user"] == "value"
    assert x.get("USER") == "value"

    assert "user" in x
    assert "user" in x.keys()

    x = CaseInsensitiveDict()
    x["User1"] = "value1"
    x["User2"] = "value2"
    x["user3"] = "value3"

    assert len(x) == 3
    x["user1"] = "value1_updated"
    assert len(x) == 3
    assert x["User1"] == "value1_updated"
    assert x["user1"] == "value1_updated"

    assert x.__str__() == "{'user1': 'value1_updated', 'user2': 'value2', 'user3': 'value3'}"
    assert x.__repr__() == "CaseInsensitiveDict({'user1': 'value1_updated', 'user2': 'value2', 'user3': 'value3'})"
    assert f"{x}" == "{'user1': 'value1_updated', 'user2': 'value2', 'user3': 'value3'}"

    # test iterators
    expected_keys = ["user1", "user2", "user3"]
    expected_values = ["value1_updated", "value2", "value3"]

    # test basic iter
    received_keys = []
    for k in x:
        received_keys.append(k)

    # keys will all come back lowercased
    assert received_keys == expected_keys

    # test .keys() iter
    received_keys = []
    for k in x.keys():
        received_keys.append(k)

    # keys will all come back lowercased
    assert received_keys == expected_keys

    # test .values iter
    received_values = []
    for v in x.values():
        received_values.append(v)

    assert received_values == expected_values

    # test .items iter
    received_keys = []
    received_values = []
    for k, v in x.items():
        received_keys.append(k)
        received_values.append(v)

    assert received_keys == expected_keys
    assert received_values == expected_values

    # test for mixed types
    mixed = CaseInsensitiveDict()

    mixed["string"] = "I am a string"
    mixed[1] = "I am an int"
    mixed[2.0] = "I am a float"

    assert mixed.get("STRING") == "I am a string"
    assert mixed.get(1) == "I am an int"
    assert mixed.get(2.0) == "I am a float"

    assert mixed.pop("STRING") == "I am a string"
    assert mixed.pop(2.0) == "I am a float"

    assert len(mixed) == 1

    assert not mixed == x
    assert mixed == mixed

    return