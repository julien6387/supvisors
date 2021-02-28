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

from socket import gethostname

from unittest.mock import patch
from supervisor.options import ServerOptions

from supvisors.tests.configurations import *


class SupvisorsOptionsTest(unittest.TestCase):
    """ Test case for the SupvisorsOptions class of the options module. """

    def test_creation(self):
        """ Test the values set at construction. """
        from supvisors.options import SupvisorsOptions
        opt = SupvisorsOptions()
        # all attributes are None
        self.assertIsNone(opt.address_list)
        self.assertIsNone(opt.rules_file)
        self.assertIsNone(opt.internal_port)
        self.assertIsNone(opt.event_port)
        self.assertIsNone(opt.auto_fence)
        self.assertIsNone(opt.synchro_timeout)
        self.assertIsNone(opt.force_synchro_if)
        self.assertIsNone(opt.conciliation_strategy)
        self.assertIsNone(opt.starting_strategy)
        self.assertIsNone(opt.stats_periods)
        self.assertIsNone(opt.stats_histo)
        self.assertIsNone(opt.stats_irix_mode)
        self.assertIsNone(opt.logfile)
        self.assertIsNone(opt.logfile_maxbytes)
        self.assertIsNone(opt.logfile_backups)
        self.assertIsNone(opt.loglevel)

    def test_str(self):
        """ Test the string output. """
        from supvisors.options import SupvisorsOptions
        opt = SupvisorsOptions()
        self.assertEqual('address_list=None rules_file=None '
                         'internal_port=None event_port=None auto_fence=None '
                         'synchro_timeout=None force_synchro_if=None conciliation_strategy=None '
                         'starting_strategy=None stats_periods=None stats_histo=None '
                         'stats_irix_mode=None logfile=None logfile_maxbytes=None '
                         'logfile_backups=None loglevel=None', str(opt))


class SupvisorsServerOptionsTest(unittest.TestCase):
    """ Test case for the SupvisorsServerOptionsTest class of the options module. """

    common_error_message = 'invalid value for {}'

    def test_port_num(self):
        """ Test the conversion into to a port number. """
        from supvisors.options import SupvisorsServerOptions
        error_message = self.common_error_message.format('port')
        # test invalid values
        with self.assertRaisesRegex(ValueError, error_message):
            SupvisorsServerOptions.to_port_num('-1')
        with self.assertRaisesRegex(ValueError, error_message):
            SupvisorsServerOptions.to_port_num('0')
        with self.assertRaisesRegex(ValueError, error_message):
            SupvisorsServerOptions.to_port_num('65536')
        # test valid values
        self.assertEqual(1, SupvisorsServerOptions.to_port_num('1'))
        self.assertEqual(65535, SupvisorsServerOptions.to_port_num('65535'))

    def test_timeout(self):
        """ Test the conversion of a string to a timeout value. """
        from supvisors.options import SupvisorsServerOptions
        error_message = self.common_error_message.format('synchro_timeout')
        # test invalid values
        with self.assertRaisesRegex(ValueError, error_message):
            SupvisorsServerOptions.to_timeout('-1')
        with self.assertRaisesRegex(ValueError, error_message):
            SupvisorsServerOptions.to_timeout('0')
        with self.assertRaisesRegex(ValueError, error_message):
            SupvisorsServerOptions.to_timeout('14')
        with self.assertRaisesRegex(ValueError, error_message):
            SupvisorsServerOptions.to_timeout('1201')
        # test valid values
        self.assertEqual(15, SupvisorsServerOptions.to_timeout('15'))
        self.assertEqual(1200, SupvisorsServerOptions.to_timeout('1200'))

    def test_conciliation_strategy(self):
        """ Test the conversion of a string to a conciliation strategy. """
        from supvisors.options import SupvisorsServerOptions
        from supvisors.ttypes import ConciliationStrategies
        error_message = self.common_error_message.format('conciliation_strategy')
        # test invalid values
        with self.assertRaisesRegex(ValueError, error_message):
            SupvisorsServerOptions.to_conciliation_strategy('123456')
        with self.assertRaisesRegex(ValueError, error_message):
            SupvisorsServerOptions.to_conciliation_strategy('dummy')
        with self.assertRaisesRegex(ValueError, error_message):
            SupvisorsServerOptions.to_conciliation_strategy('user')
        # test valid values
        self.assertEqual(ConciliationStrategies.SENICIDE,
                         SupvisorsServerOptions.to_conciliation_strategy('SENICIDE'))
        self.assertEqual(ConciliationStrategies.INFANTICIDE,
                         SupvisorsServerOptions.to_conciliation_strategy('INFANTICIDE'))
        self.assertEqual(ConciliationStrategies.USER,
                         SupvisorsServerOptions.to_conciliation_strategy('USER'))
        self.assertEqual(ConciliationStrategies.STOP,
                         SupvisorsServerOptions.to_conciliation_strategy('STOP'))
        self.assertEqual(ConciliationStrategies.RESTART,
                         SupvisorsServerOptions.to_conciliation_strategy('RESTART'))

    def test_starting_strategy(self):
        """ Test the conversion of a string to a starting strategy. """
        from supvisors.options import SupvisorsServerOptions
        from supvisors.ttypes import StartingStrategies
        error_message = self.common_error_message.format('starting_strategy')
        # test invalid values
        with self.assertRaisesRegex(ValueError, error_message):
            SupvisorsServerOptions.to_starting_strategy('123456')
        with self.assertRaisesRegex(ValueError, error_message):
            SupvisorsServerOptions.to_starting_strategy('dummy')
        with self.assertRaisesRegex(ValueError, error_message):
            SupvisorsServerOptions.to_starting_strategy('config')
        # test valid values
        self.assertEqual(StartingStrategies.CONFIG,
                         SupvisorsServerOptions.to_starting_strategy('CONFIG'))
        self.assertEqual(StartingStrategies.LESS_LOADED,
                         SupvisorsServerOptions.to_starting_strategy('LESS_LOADED'))
        self.assertEqual(StartingStrategies.MOST_LOADED,
                         SupvisorsServerOptions.to_starting_strategy('MOST_LOADED'))

    def test_periods(self):
        """ Test the conversion of a string to a list of periods. """
        from supvisors.options import SupvisorsServerOptions
        error_message = self.common_error_message.format('stats_periods')
        # test invalid values
        with self.assertRaisesRegex(ValueError, 'unexpected number of stats_periods'):
            SupvisorsServerOptions.to_periods([])
        with self.assertRaisesRegex(ValueError, 'unexpected number of stats_periods'):
            SupvisorsServerOptions.to_periods(['1', '2', '3', '4'])
        with self.assertRaisesRegex(ValueError, error_message):
            SupvisorsServerOptions.to_periods(['4', '3600'])
        with self.assertRaisesRegex(ValueError, error_message):
            SupvisorsServerOptions.to_periods(['5', '3601'])
        with self.assertRaisesRegex(ValueError, error_message):
            SupvisorsServerOptions.to_periods(['6', '3599'])
        # test valid values
        self.assertEqual([5], SupvisorsServerOptions.to_periods(['5']))
        self.assertEqual([60, 3600], SupvisorsServerOptions.to_periods(['60', '3600']))
        self.assertEqual([120, 720, 1800], SupvisorsServerOptions.to_periods(['120', '720', '1800']))

    def test_histo(self):
        """ Test the conversion of a string to a history depth. """
        from supvisors.options import SupvisorsServerOptions
        error_message = self.common_error_message.format('stats_histo')
        # test invalid values
        with self.assertRaisesRegex(ValueError, error_message):
            SupvisorsServerOptions.to_histo('-1')
        with self.assertRaisesRegex(ValueError, error_message):
            SupvisorsServerOptions.to_histo('9')
        with self.assertRaisesRegex(ValueError, error_message):
            SupvisorsServerOptions.to_histo('1501')
        # test valid values
        self.assertEqual(10, SupvisorsServerOptions.to_histo('10'))
        self.assertEqual(1500, SupvisorsServerOptions.to_histo('1500'))

    def test_incorrect_supvisors(self):
        """ Test that exception is raised when the supvisors section is missing. """
        with self.assertRaises(ValueError):
            self.create_server(NoSupvisors)

    def test_program_numbers(self):
        """ Test that the internal numbers of homogeneous programs are stored. """
        server = self.create_server(ProgramConfiguration)
        self.assertDictEqual({'dummy': 0, 'dummy_0': 0, 'dummy_1': 1, 'dummy_2': 2, 'dumber_10': 0, 'dumber_11': 1},
                             server.supvisors_options.procnumbers)

    def test_default_options(self):
        """ Test the default values of options with empty Supvisors configuration. """
        from supervisor.datatypes import Automatic
        from supvisors.ttypes import ConciliationStrategies, StartingStrategies
        server = self.create_server(DefaultOptionConfiguration)
        opt = server.supvisors_options
        self.assertListEqual([gethostname()], opt.address_list)
        self.assertIsNone(opt.rules_file)
        self.assertEqual(65001, opt.internal_port)
        self.assertEqual(65002, opt.event_port)
        self.assertFalse(opt.auto_fence)
        self.assertEqual(15, opt.synchro_timeout)
        self.assertEqual([], opt.force_synchro_if)
        self.assertEqual(ConciliationStrategies.USER, opt.conciliation_strategy)
        self.assertEqual(StartingStrategies.CONFIG, opt.starting_strategy)
        self.assertListEqual([10], opt.stats_periods)
        self.assertEqual(200, opt.stats_histo)
        self.assertFalse(opt.stats_irix_mode)
        self.assertEqual(Automatic, opt.logfile)
        self.assertEqual(50 * 1024 * 1024, opt.logfile_maxbytes)
        self.assertEqual(10, opt.logfile_backups)
        self.assertEqual(20, opt.loglevel)

    def test_defined_options(self):
        """ Test the values of options with defined Supvisors configuration. """
        from supvisors.ttypes import ConciliationStrategies, StartingStrategies
        server = self.create_server(DefinedOptionConfiguration)
        opt = server.supvisors_options
        self.assertEqual(['cliche01', 'cliche03', 'cliche02'], opt.address_list)
        self.assertEqual('my_movies.xml', opt.rules_file)
        self.assertEqual(60001, opt.internal_port)
        self.assertEqual(60002, opt.event_port)
        self.assertTrue(opt.auto_fence)
        self.assertEqual(20, opt.synchro_timeout)
        self.assertEqual(['cliche01', 'cliche03'], opt.force_synchro_if)
        self.assertEqual(ConciliationStrategies.SENICIDE, opt.conciliation_strategy)
        self.assertEqual(StartingStrategies.MOST_LOADED, opt.starting_strategy)
        self.assertListEqual([5, 60, 600], opt.stats_periods)
        self.assertEqual(100, opt.stats_histo)
        self.assertTrue(opt.stats_irix_mode)
        self.assertEqual('/tmp/supvisors.log', opt.logfile)
        self.assertEqual(50 * 1024, opt.logfile_maxbytes)
        self.assertEqual(5, opt.logfile_backups)
        self.assertEqual(40, opt.loglevel)

    @patch.object(ServerOptions, 'default_configfile', return_value='supervisord.conf')
    @patch.object(ServerOptions, 'exists', return_value=True)
    @patch.object(ServerOptions, 'usage', side_effect=ValueError)
    def create_server(self, *args, **keywargs):
        """ Create a SupvisorsServerOptions instance using patches on Supervisor source code.
        This is required because the unit test does not include existing files. """
        from supvisors.options import SupvisorsServerOptions
        server = SupvisorsServerOptions()
        # this flag is required for supervisor to cope with unittest arguments
        server.positional_args_allowed = 1
        # remove pytest cov options
        with patch.object(sys, 'argv', [sys.argv[0]]):
            with patch.object(ServerOptions, 'open', return_value=args[0]):
                server.realize()
        return server


def test_suite():
    return unittest.findTestCases(sys.modules[__name__])


if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
