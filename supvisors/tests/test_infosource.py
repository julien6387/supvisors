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

from unittest.mock import patch, Mock

from supervisor.http import supervisor_auth_handler
from supervisor.medusa import default_handler

from supvisors.tests.base import DummySupervisor


class InfoSourceTest(unittest.TestCase):
    """ Test case for the infosource module. """

    def setUp(self):
        """ Create a logger that stores log traces. """
        self.supervisor = DummySupervisor()

    def test_unix_server(self):
        """ Test the values set at construction. """
        from supvisors.infosource import SupervisordSource
        with patch.dict(self.supervisor.options.server_configs[0],
                        {'section': 'unix_http_server'}):
            with self.assertRaises(ValueError):
                SupervisordSource(self.supervisor)

    def test_creation(self):
        """ Test the values set at construction. """
        from supvisors.infosource import SupervisordSource
        source = SupervisordSource(self.supervisor)
        self.assertIs(self.supervisor, source.supervisord)
        self.assertIs(source.supervisord.options.server_configs[0],
                      source.server_config)
        self.assertIsNone(source._supervisor_rpc_interface)
        self.assertIsNone(source._supvisors_rpc_interface)

    def test_accessors(self):
        """ Test the accessors. """
        from supvisors.infosource import SupervisordSource
        source = SupervisordSource(self.supervisor)
        # test consistence with DummySupervisor configuration
        self.assertIs(self.supervisor.options.httpserver, source.httpserver)
        self.assertEqual('supervisor_RPC', source.supervisor_rpc_interface)
        self.assertEqual('supvisors_RPC', source.supvisors_rpc_interface)
        self.assertEqual('url', source.serverurl)
        self.assertEqual(1234, source.serverport)
        self.assertEqual('user', source.username)
        self.assertEqual('p@$$w0rd', source.password)
        self.assertEqual('mood', source.supervisor_state)

    def test_env(self):
        """ Test the environment build. """
        from supvisors.infosource import SupervisordSource
        source = SupervisordSource(self.supervisor)
        self.assertDictEqual({'SUPERVISOR_SERVER_URL': 'url',
                              'SUPERVISOR_USERNAME': 'user',
                              'SUPERVISOR_PASSWORD': 'p@$$w0rd'},
                             source.get_env())

    def test_close_server(self):
        """ Test the closing of supervisord HTTP servers. """
        from supvisors.infosource import SupervisordSource
        source = SupervisordSource(self.supervisor)
        # keep reference to http servers
        http_servers = self.supervisor.options.httpservers
        self.assertIsNone(self.supervisor.options.storage)
        # call the method
        source.close_httpservers()
        # test the result
        self.assertIsNotNone(self.supervisor.options.storage)
        self.assertIs(http_servers, self.supervisor.options.storage)
        self.assertTupleEqual((), self.supervisor.options.httpservers)
        # restore old value for tests
        self.supervisor.options.httpservers = http_servers

    def test_group_config(self):
        """ Test the access of a group configuration. """
        from supvisors.infosource import SupervisordSource
        source = SupervisordSource(self.supervisor)
        # test unknown application
        with self.assertRaises(KeyError):
            source.get_group_config('unknown_application')
        # test normal behaviour
        self.assertEqual('dummy_application_config',
                         source.get_group_config('dummy_application'))

    def test_process(self):
        """ Test the access of a supervisord process. """
        from supvisors.infosource import SupervisordSource
        source = SupervisordSource(self.supervisor)
        # test unknown application and process
        with self.assertRaises(KeyError):
            source.get_process('unknown_application:unknown_process')
        with self.assertRaises(KeyError):
            source.get_process('dummy_application:unknown_process')
        # test normal behaviour
        app_config = self.supervisor.process_groups['dummy_application']
        self.assertIs(app_config.processes['dummy_process_1'],
                      source.get_process('dummy_application:dummy_process_1'))
        self.assertIs(app_config.processes['dummy_process_2'],
                      source.get_process('dummy_application:dummy_process_2'))

    def test_process_config(self):
        """ Test the access of a group configuration. """
        from supvisors.infosource import SupervisordSource
        source = SupervisordSource(self.supervisor)
        # test unknown application and process
        with self.assertRaises(KeyError):
            source.get_process_config('unknown_application:unknown_process')
        with self.assertRaises(KeyError):
            source.get_process_config('dummy_application:unknown_process')
        # test normal behaviour
        config = source.get_process_config('dummy_application:dummy_process_1')
        self.assertTrue(config.autorestart)
        self.assertEqual('ls', config.command)
        config = source.get_process_config('dummy_application:dummy_process_2')
        self.assertFalse(config.autorestart)
        self.assertEqual('cat', config.command)

    def test_autorestart(self):
        """ Test the autostart value of a process configuration. """
        from supvisors.infosource import SupervisordSource
        source = SupervisordSource(self.supervisor)
        # test unknown application and process
        with self.assertRaises(KeyError):
            source.autorestart('unknown_application:unknown_process')
        with self.assertRaises(KeyError):
            source.autorestart('dummy_application:unknown_process')
        # test normal behaviour
        self.assertTrue(source.autorestart('dummy_application:dummy_process_1'))
        self.assertFalse(source.autorestart('dummy_application:dummy_process_2'))

    def test_disable_autorestart(self):
        """ Test the disable of the autostart of a process configuration. """
        from supvisors.infosource import SupervisordSource
        source = SupervisordSource(self.supervisor)
        # test unknown application and process
        with self.assertRaises(KeyError):
            source.disable_autorestart('unknown_application:unknown_process')
        with self.assertRaises(KeyError):
            source.disable_autorestart('dummy_application:unknown_process')
        # test normal behaviour
        self.assertTrue(source.autorestart('dummy_application:dummy_process_1'))
        source.disable_autorestart('dummy_application:dummy_process_1')
        self.assertFalse(source.autorestart('dummy_application:dummy_process_1'))

    def test_extra_args(self):
        """ Test the extra arguments functionality. """
        from supvisors.infosource import SupervisordSource
        source = SupervisordSource(self.supervisor)
        # test initial status
        self.assertFalse(any(hasattr(process.config, 'command_ref') or
                             hasattr(process.config, 'extra_args')
                             for appli in self.supervisor.process_groups.values()
                             for process in appli.processes.values()))
        # add context to internal data
        source.prepare_extra_args()
        # test internal data: all should have additional attributes
        self.assertTrue(all(hasattr(process.config, 'command_ref') or
                            hasattr(process.config, 'extra_args')
                            for appli in self.supervisor.process_groups.values()
                            for process in appli.processes.values()))
        # test unknown application and process
        with self.assertRaises(KeyError):
            source.update_extra_args('unknown_application:unknown_process', '-la')
        with self.assertRaises(KeyError):
            source.update_extra_args('dummy_application:unknown_process', '-la')
        # test normal behaviour
        namespec = 'dummy_application:dummy_process_1'
        config = source.get_process_config(namespec)
        # add extra arguments
        source.update_extra_args(namespec, '-la')
        # test access
        self.assertEqual('-la', source.get_extra_args(namespec))
        # test internal data
        self.assertEqual('ls -la', config.command)
        self.assertEqual('ls', config.command_ref)
        self.assertEqual('-la', config.extra_args)
        # remove them
        source.update_extra_args(namespec, '')
        # test access
        self.assertEqual('', source.get_extra_args(namespec))
        # test internal data
        self.assertEqual('ls', config.command)
        self.assertEqual('ls', config.command_ref)
        self.assertEqual('', config.extra_args)

    def test_force_fatal(self):
        """ Test the way to force a process in FATAL state. """
        from supvisors.infosource import SupervisordSource
        source = SupervisordSource(self.supervisor)
        # test unknown application and process
        with self.assertRaises(KeyError):
            source.force_process_fatal('unknown_application:unknown_process', 'crash')
        with self.assertRaises(KeyError):
            source.force_process_fatal('dummy_application:unknown_process', 'crash')
        # test normal behaviour
        process_1 = source.get_process('dummy_application:dummy_process_1')
        self.assertEqual('STOPPED', process_1.state)
        self.assertEqual('', process_1.spawnerr)
        source.force_process_fatal('dummy_application:dummy_process_1', 'crash')
        self.assertEqual('FATAL', process_1.state)
        self.assertEqual('crash', process_1.spawnerr)
        # restore configuration
        process_1.state = 'STOPPED'
        process_1.spawnerr = ''

    def test_force_unknown(self):
        """ Test the way to force a process in UNKNOWN state. """
        from supvisors.infosource import SupervisordSource
        source = SupervisordSource(self.supervisor)
        # test unknown application and process
        with self.assertRaises(KeyError):
            source.force_process_unknown('unknown_application:unknown_process', 'mystery')
        with self.assertRaises(KeyError):
            source.force_process_unknown('dummy_application:unknown_process', 'mystery')
        # test normal behaviour
        process_1 = source.get_process('dummy_application:dummy_process_1')
        self.assertEqual('STOPPED', process_1.state)
        self.assertEqual('', process_1.spawnerr)
        source.force_process_unknown('dummy_application:dummy_process_1', 'mystery')
        self.assertEqual(1000, process_1.state)
        self.assertEqual('mystery', process_1.spawnerr)
        # restore configuration
        process_1.state = 'STOPPED'
        process_1.spawnerr = ''

    def test_replace_handler(self):
        """ Test the autostart value of a process configuration. """
        from supvisors.infosource import SupervisordSource
        source = SupervisordSource(self.supervisor)
        # keep reference to handler
        self.assertIsInstance(self.supervisor.options.httpserver.handlers[1], Mock)
        # check method behaviour with authentication server
        source.replace_default_handler()
        # keep reference to handler
        self.assertIsInstance(self.supervisor.options.httpserver.handlers[1], supervisor_auth_handler)
        # check method behaviour with authentication server
        with patch.dict(source.server_config, {'username': None}):
            source.replace_default_handler()
        # keep reference to handler
        self.assertIsInstance(self.supervisor.options.httpserver.handlers[1], default_handler.default_handler)


def test_suite():
    return unittest.findTestCases(sys.modules[__name__])


if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
