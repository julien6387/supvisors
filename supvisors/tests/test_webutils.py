#!/usr/bin/python
# -*- coding: utf-8 -*-

# ======================================================================
# Copyright 2016 Julien LE CLEACH
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ======================================================================

import sys
import unittest

from time import ctime
from types import FunctionType

from unittest.mock import Mock

from supvisors.tests.base import CompatTestCase


class WebUtilsTest(CompatTestCase):
    """ Test case for the webutils module. """

    def test_format_gravity_message(self):
        """ Test the formatting of web messages. """
        from supvisors.webutils import format_gravity_message
        # test Supervisor information message
        msg = format_gravity_message('an information message')
        self.assertIs(tuple, type(msg))
        self.assertTupleEqual(('info', 'an information message'), msg)
        # test Supervisor error message
        msg = format_gravity_message('ERROR: an error message')
        self.assertIs(tuple, type(msg))
        self.assertTupleEqual(('erro', 'an error message'), msg)
        # test Supervisor warning message
        msg = format_gravity_message('unexpected rpc fault')
        self.assertIs(tuple, type(msg))
        self.assertTupleEqual(('warn', 'unexpected rpc fault'), msg)
        # test Supvisors information message
        msg = format_gravity_message(('warn', 'a warning message'))
        self.assertIs(tuple, type(msg))
        msg = format_gravity_message(('warn', 'a warning message'))
        self.assertIs(tuple, type(msg))

    def test_print_message(self):
        """ Test the meld formatting of a message. """
        from supvisors.webutils import print_message

        # create simple classes replacing meld behaviour
        class DummyElement:
            def __init__(self):
                self.attrib = {}

            def content(self, cnt):
                self.attrib['content'] = cnt

        class DummyRoot:
            def __init__(self):
                self.elt = DummyElement()

            def findmeld(self, _):
                return self.elt

        # test with empty message
        root = DummyRoot()
        print_message(root, 'gravity', None)
        self.assertDictContainsSubset({'class': 'empty'}, root.elt.attrib)
        self.assertDictContainsSubset({'content': ''}, root.elt.attrib)
        # test with filled message
        root = DummyRoot()
        print_message(root, 'gravity', 'a simple message')
        self.assertDictContainsSubset({'class': 'gravity'}, root.elt.attrib)
        self.assertDictContainsSubset({'content': 'a simple message'}, root.elt.attrib)

    def test_info_message(self):
        """ Test the formatting of an information message. """
        from supvisors.webutils import info_message
        self.check_message(info_message, 'info')

    def test_warn_message(self):
        """ Test the formatting of a warning message. """
        from supvisors.webutils import warn_message
        self.check_message(warn_message, 'warn')

    def test_error_message(self):
        """ Test the formatting of an error message. """
        from supvisors.webutils import error_message
        self.check_message(error_message, 'erro')

    def test_delayed_info(self):
        """ Test the callable returned for a delayed information message. """
        from supvisors.webutils import delayed_info
        self.check_delayed_message(delayed_info, 'info')

    def test_delayed_warn(self):
        """ Test the callable returned for a delayed warning message. """
        from supvisors.webutils import delayed_warn
        self.check_delayed_message(delayed_warn, 'warn')

    def test_delayed_error(self):
        """ Test the callable returned for a delayed error message. """
        from supvisors.webutils import delayed_error
        self.check_delayed_message(delayed_error, 'erro')

    def check_message(self, func, gravity):
        """ Test the formatting of any message. """
        # test without address
        msg = func('a simple message')
        self.assertIs(tuple, type(msg))
        self.assertEqual(2, len(msg))
        self.assertEqual(gravity, msg[0])
        self.assertEqual(msg[1], 'a simple message at ' + ctime())
        # test with address
        msg = func('another simple message', '10.0.0.1')
        self.assertIs(tuple, type(msg))
        self.assertEqual(2, len(msg))
        self.assertEqual(gravity, msg[0])
        self.assertEqual(msg[1], 'another simple message at ' + ctime() + ' on 10.0.0.1')

    def check_delayed_message(self, func, gravity):
        """ Test the callable returned for any delayed message. """
        # test without address
        msg_cb = func('a simple message')
        self.assertIs(FunctionType, type(msg_cb))
        self.assertEqual(0.05, msg_cb.delay)
        msg = msg_cb()
        self.assertIs(tuple, type(msg))
        self.assertEqual(2, len(msg))
        self.assertEqual(gravity, msg[0])
        self.assertEqual(msg[1], 'a simple message at ' + ctime())
        # test with address
        msg_cb = func('another simple message', '10.0.0.1')
        self.assertIs(FunctionType, type(msg_cb))
        self.assertEqual(0.05, msg_cb.delay)
        msg = msg_cb()
        self.assertIs(tuple, type(msg))
        self.assertEqual(2, len(msg))
        self.assertEqual(gravity, msg[0])
        self.assertEqual(msg[1], 'another simple message at ' + ctime() + ' on 10.0.0.1')

    def test_apply_shade(self):
        """ Test the formatting of shaded / non-shaded elements. """
        from supvisors.webutils import apply_shade
        elt = Mock(attrib={})
        # test shaded
        apply_shade(elt, True)
        self.assertEqual('shaded', elt.attrib['class'])
        # test non-shaded
        apply_shade(elt, False)
        self.assertEqual('brightened', elt.attrib['class'])


def test_suite():
    return unittest.findTestCases(sys.modules[__name__])


if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
