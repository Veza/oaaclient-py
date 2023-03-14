"""
Copyright 2023 Veza Technologies Inc.

Use of this source code is governed by the MIT
license that can be found in the LICENSE file or at
https://opensource.org/licenses/MIT.
"""

from collections.abc import Mapping, MutableMapping

class CaseInsensitiveDict(MutableMapping):
    """Case Insensitive Key Dictionary

    Dictionary like object with case insensitive keys for types that support `.lower()` such as strings.

    Keys do not have to be strings, in the case where the key type does not support `.lower()` such as integers the
    value is used as is.

    Example:
        >>> from oaaclient.structures import CaseInsensitiveDict
        >>> x = CaseInsensitiveDict()
        >>> x["User"] = "value"
        >>> x.get("user")
        'value'
        >>> "USER" in x
        True
        >>> print(x)
        {'user': 'value'}
        >>> x
        CaseInsensitiveDict({'user': 'value'})

    """

    def __init__(self, data=None, **kwargs) -> None:
        self._entities = dict()
        if data is None:
            data = {}
        self.update(data, **kwargs)

    def __getitem__(self, key):
        try:
            key = key.lower()
        except AttributeError:
            pass

        return self._entities[key][1]

    def __setitem__(self, key, value) -> None:
        try:
            key = key.lower()
        except AttributeError:
            pass

        self._entities[key] = (key, value)

    def __delitem__(self, key) -> None:
        try:
            key = key.lower()
        except AttributeError:
            pass

        del self._entities[key]

    def __iter__(self):
        return (key for key, value in self._entities.values())

    def __len__(self) -> int:
        return len(self._entities)

    def __eq__(self, other):
        return NotImplemented

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({dict(self.items())})"

    def __str__(self) -> str:
        return f"{dict(self.items())}"