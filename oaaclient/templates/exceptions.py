"""
Copyright 2026 Veza Technologies Inc.

Use of this source code is governed by the MIT
license that can be found in the LICENSE file or at
https://opensource.org/licenses/MIT.
"""

class OAATemplateException(Exception):
    """ General exception used for violations of the template schema. """

    def __init__(self, message):
        self.message = message
        super().__init__(self.message)
