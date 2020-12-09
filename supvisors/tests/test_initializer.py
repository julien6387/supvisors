#!/usr/bin/python
# -*- coding: utf-8 -*-

# ======================================================================
# Copyright 2017 Julien LE CLEACH
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

from unittest.mock import patch
from supervisor.xmlrpc import Faults, RPCError

from supvisors.tests.base import DummySupervisor


class InitializerTest(unittest.TestCase):
    """ Test case for the initializer module. """

    @patch('supvisors.initializer.Parser')
    @patch('supvisors.initializer.AddressMapper')
    @patch('supvisors.initializer.loggers')
    @patch('supvisors.initializer.SupvisorsServerOptions')
    def test_creation(self, *args, **kwargs):
        """ Test the values set at construction. """
        from supvisors.initializer import Supvisors
        # create Supvisors instance
        supervisord = DummySupervisor()
        supvisors = Supvisors(supervisord)
        # test inclusion of Supvisors into Supervisor
        self.assertIs(supvisors, supervisord.supvisors)
        # test calls
        self.assertTrue(args[0].called)
        self.assertTrue(args[1].getLogger.called)
        self.assertTrue(args[1].handle_stdout.called)
        self.assertTrue(args[1].handle_file.called)
        self.assertTrue(args[2].called)
        self.assertTrue(args[3].called)
        # test instances
        self.assertIsNotNone(supvisors.options)
        self.assertIsNotNone(supvisors.logger)
        self.assertIsNotNone(supvisors.info_source)
        self.assertIsNotNone(supvisors.address_mapper)
        self.assertIsNotNone(supvisors.context)
        self.assertIsNotNone(supvisors.starter)
        self.assertIsNotNone(supvisors.stopper)
        self.assertIsNotNone(supvisors.statistician)
        self.assertIsNotNone(supvisors.fsm)
        self.assertIsNotNone(supvisors.parser)
        self.assertIsNotNone(supvisors.listener)

    @patch('supvisors.initializer.loggers')
    @patch('supvisors.initializer.SupvisorsServerOptions')
    def test_address_exception(self, *args, **kwargs):
        """ Test the values set at construction. """
        from supvisors.initializer import Supvisors
        # create Supvisors instance
        supervisord = DummySupervisor()
        # patches Faults codes
        setattr(Faults, 'SUPVISORS_CONF_ERROR', 777)
        # test that local address exception raises a failure to Supervisor
        with self.assertRaises(RPCError):
            Supvisors(supervisord)

    @patch('supvisors.initializer.Parser', side_effect=Exception)
    @patch('supvisors.initializer.AddressMapper', local_address='127.0.0.1')
    @patch('supvisors.initializer.loggers')
    @patch('supvisors.initializer.SupvisorsServerOptions')
    def test_parser_exception(self, *args, **kwargs):
        """ Test the values set at construction. """
        from supvisors.initializer import Supvisors
        # create Supvisors instance
        supervisord = DummySupervisor()
        supvisors = Supvisors(supervisord)
        # test that parser exception is accepted
        self.assertIsNone(supvisors.parser)


def test_suite():
    return unittest.findTestCases(sys.modules[__name__])


if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
