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

import errno
import socket
import sys
import unittest

from unittest.mock import call, patch, Mock

from supervisor.compat import xmlrpclib
from supervisor.supervisorctl import Controller
from supervisor.xmlrpc import Faults
import errno
import socket
import sys
import unittest

from unittest.mock import call, patch, Mock

from supervisor.compat import xmlrpclib
from supervisor.supervisorctl import Controller
from supervisor.xmlrpc import Faults


class ControllerPluginTest(unittest.TestCase):
    """ Test case for the supvisorsctl module. """

    def setUp(self):
        """ Create a mocked Supervisor Controller. """
        from supvisors.rpcinterface import RPCInterface
        self.controller = Mock(spec=Controller)
        self.controller.get_server_proxy.return_value = Mock(spec=RPCInterface)
        self.controller.options = Mock(serverurl='dummy_url')

    def test_supvisors(self):
        """ Test the access to Supvisors proxy. """
        from supvisors.supvisorsctl import ControllerPlugin
        from supvisors.rpcinterface import RPCInterface
        # create the instance
        plugin = ControllerPlugin(self.controller)
        # test the proxy
        self.assertEqual(plugin.supvisors()._spec_class, RPCInterface)
        self.assertEqual([call('supvisors')],
                         self.controller.get_server_proxy.call_args_list)

    @patch('supvisors.supvisorsctl.ControllerPlugin._upcheck',
           return_value=True)
    def test_sversion(self, mocked_check):
        """ Test the sversion request. """
        from supvisors.supvisorsctl import ControllerPlugin
        # create the instance
        plugin = ControllerPlugin(self.controller)
        # test help and request
        self._check_call(None, plugin.supvisors().get_api_version,
                         plugin.help_sversion, plugin.do_sversion, '',
                         [call()])

    @patch('supvisors.supvisorsctl.ControllerPlugin._upcheck',
           return_value=True)
    def test_master(self, mocked_check):
        """ Test the master request. """
        from supvisors.supvisorsctl import ControllerPlugin
        # create the instance
        plugin = ControllerPlugin(self.controller)
        # test help and request
        self._check_call(mocked_check, plugin.supvisors().get_master_address,
                         plugin.help_master, plugin.do_master, '',
                         [call()])

    @patch('supvisors.supvisorsctl.ControllerPlugin._upcheck',
           return_value=True)
    def test_strategies(self, mocked_check):
        """ Test the master request. """
        from supvisors.supvisorsctl import ControllerPlugin
        # create the instance
        plugin = ControllerPlugin(self.controller)
        # test help and request
        mocked_rpc = plugin.supvisors().get_strategies
        mocked_rpc.return_value = {'conciliation': 'hard', 'starting': 'easy', 'auto-fencing': True}
        self._check_call(mocked_check, plugin.supvisors().get_strategies,
                         plugin.help_strategies, plugin.do_strategies, '',
                         [call()])

    @patch('supvisors.supvisorsctl.ControllerPlugin._upcheck',
           return_value=True)
    def test_sstate(self, mocked_check):
        """ Test the sstate request. """
        from supvisors.supvisorsctl import ControllerPlugin
        # create the instance
        plugin = ControllerPlugin(self.controller)
        # test help and request
        mocked_rpc = plugin.supvisors().get_supvisors_state
        mocked_rpc.return_value = {'statecode': 10, 'statename': 'running'}
        self._check_call(mocked_check, mocked_rpc,
                         plugin.help_sstate, plugin.do_sstate, '',
                         [call()])

    @patch('supvisors.supvisorsctl.ControllerPlugin._upcheck',
           return_value=True)
    def test_address_status(self, mocked_check):
        """ Test the address_status request. """
        from supvisors.supvisorsctl import ControllerPlugin
        # create the instance
        plugin = ControllerPlugin(self.controller)
        # test help and request for all address status
        mocked_rpc = plugin.supvisors().get_all_addresses_info
        mocked_rpc.return_value = [
            {'address_name': '10.0.0.1', 'statename': 'running',
             'loading': 10, 'local_time': 1500},
            {'address_name': '10.0.0.2', 'statename': 'stopped',
             'loading': 0, 'local_time': 100}]
        self._check_call(mocked_check, mocked_rpc,
                         plugin.help_address_status, plugin.do_address_status,
                         '', [call()])
        self._check_call(mocked_check, mocked_rpc,
                         plugin.help_address_status, plugin.do_address_status,
                         'all', [call()])
        # test help and request for address status from
        # a selection of address names
        mocked_rpc = plugin.supvisors().get_address_info
        mocked_rpc.side_effect = [
            {'address_name': '10.0.0.1', 'statename': 'running',
             'loading': 10, 'local_time': 1500},
            {'address_name': '10.0.0.2', 'statename': 'stopped',
             'loading': 0, 'local_time': 100}]
        self._check_call(mocked_check, mocked_rpc,
                         plugin.help_address_status, plugin.do_address_status,
                         '10.0.0.2 10.0.0.1',
                         [call('10.0.0.2'), call('10.0.0.1')])

    @patch('supvisors.supvisorsctl.ControllerPlugin._upcheck',
           return_value=True)
    def test_application_info(self, mocked_check):
        """ Test the application_info request. """
        from supvisors.supvisorsctl import ControllerPlugin
        # create the instance
        plugin = ControllerPlugin(self.controller)
        # test help and request for all application info
        mocked_rpc = plugin.supvisors().get_all_applications_info
        mocked_rpc.return_value = [
            {'application_name': 'appli_1', 'statename': 'running',
             'major_failure': True, 'minor_failure': False},
            {'application_name': 'appli_2', 'statename': 'stopped',
             'major_failure': False, 'minor_failure': True}]
        self._check_call(mocked_check, mocked_rpc,
                         plugin.help_application_info, plugin.do_application_info,
                         '', [call()])
        self._check_call(mocked_check, mocked_rpc,
                         plugin.help_application_info, plugin.do_application_info,
                         'all', [call()])
        # test help and request for application info from
        # a selection of application names
        mocked_rpc = plugin.supvisors().get_application_info
        mocked_rpc.side_effect = [
            {'application_name': 'appli_1', 'statename': 'running',
             'major_failure': True, 'minor_failure': False},
            {'application_name': 'appli_2', 'statename': 'stopped',
             'major_failure': False, 'minor_failure': True}]
        self._check_call(mocked_check, mocked_rpc,
                         plugin.help_application_info, plugin.do_application_info,
                         'appli_2 appli_1',
                         [call('appli_2'), call('appli_1')])

    @patch('supvisors.supvisorsctl.ControllerPlugin._upcheck',
           return_value=True)
    def test_sstatus(self, mocked_check):
        """ Test the sstatus request. """
        from supvisors.supvisorsctl import ControllerPlugin
        # create the instance
        plugin = ControllerPlugin(self.controller)
        # test help and request for all process info
        mocked_rpc = plugin.supvisors().get_all_process_info
        mocked_rpc.return_value = [
            {'application_name': 'appli_1', 'process_name': 'proc_1',
             'statename': 'running', 'addresses': ['10.0.1', '10.0.2']},
            {'application_name': 'appli_2', 'process_name': 'proc_3',
             'statename': 'stopped', 'addresses': []}]
        self._check_call(mocked_check, mocked_rpc,
                         plugin.help_sstatus, plugin.do_sstatus, '',
                         [call()])
        self._check_call(mocked_check, mocked_rpc,
                         plugin.help_sstatus, plugin.do_sstatus, 'all',
                         [call()])
        # test help and request for process info from a selection of namespecs
        mocked_rpc = plugin.supvisors().get_process_info
        mocked_rpc.side_effect = [
            [{'application_name': 'appli_1', 'process_name': 'proc_1',
              'statename': 'running', 'addresses': ['10.0.1', '10.0.2']}],
            [{'application_name': 'appli_2', 'process_name': 'proc_3',
              'statename': 'stopped', 'addresses': []}]]
        self._check_call(mocked_check, mocked_rpc,
                         plugin.help_sstatus, plugin.do_sstatus,
                         'appli_2:proc_3 appli_1:proc_1',
                         [call('appli_2:proc_3'), call('appli_1:proc_1')])

    @patch('supvisors.supvisorsctl.ControllerPlugin._upcheck',
           return_value=True)
    def test_local_status(self, mocked_check):
        """ Test the local_status request. """
        from supvisors.supvisorsctl import ControllerPlugin
        # create the instance
        plugin = ControllerPlugin(self.controller)
        # test help and request for all local process info
        mocked_rpc = plugin.supvisors().get_all_local_process_info
        mocked_rpc.return_value = [
            {'group': 'appli_1', 'name': 'proc_1',
             'state': 20, 'start': 1234, 'now': 4321, 'pid': 14725,
             'extra_args': '-x dummy'},
            {'group': 'appli_2', 'name': 'proc_3',
             'state': 0, 'start': 0, 'now': 0, 'pid': 0,
             'extra_args': ''}]
        self._check_call(mocked_check, mocked_rpc,
                         plugin.help_local_status, plugin.do_local_status, '',
                         [call()])
        self._check_call(mocked_check, mocked_rpc,
                         plugin.help_local_status, plugin.do_local_status, 'all',
                         [call()])
        # test help and request for process info from a selection of namespecs
        self._check_call(mocked_check, mocked_rpc,
                         plugin.help_local_status, plugin.do_local_status,
                         'appli_2:proc_3 appli_1:proc_1',
                         [call()])

    @patch('supvisors.supvisorsctl.ControllerPlugin._upcheck',
           return_value=True)
    def test_application_rules(self, mocked_check):
        """ Test the application_rules request. """
        from supvisors.supvisorsctl import ControllerPlugin
        # create the instance
        plugin = ControllerPlugin(self.controller)
        # test help and request for all rules
        mocked_appli = plugin.supvisors().get_all_applications_info
        mocked_appli.return_value = [{'application_name': 'appli_1'},
                                     {'application_name': 'appli_2'}]
        mocked_rpc = plugin.supvisors().get_application_rules
        returned_rules = [
            {'application_name': 'appli_1',
             'start_sequence': 2, 'stop_sequence': 3,
             'starting_failure_strategy': 2,
             'running_failure_strategy': 1},
            {'application_name': 'appli_2',
             'start_sequence': 1, 'stop_sequence': 0,
             'starting_failure_strategy': 0,
             'running_failure_strategy': 2}]
        # first possiblity: no argument
        mocked_rpc.side_effect = returned_rules
        self._check_call(mocked_check, mocked_rpc,
                         plugin.help_application_rules, plugin.do_application_rules, '',
                         [call('appli_1'), call('appli_2')])
        self.assertEqual([call(), call()], mocked_appli.call_args_list)
        mocked_appli.reset_mock()
        # second possiblity: use 'all'
        mocked_rpc.side_effect = returned_rules
        self._check_call(mocked_check, mocked_rpc,
                         plugin.help_application_rules, plugin.do_application_rules, 'all',
                         [call('appli_1'), call('appli_2')])
        self.assertEqual([call(), call()], mocked_appli.call_args_list)
        mocked_appli.reset_mock()
        # test help and request for rules from a selection of application names
        mocked_rpc.side_effect = returned_rules
        self._check_call(mocked_check, mocked_rpc,
                         plugin.help_application_rules, plugin.do_application_rules,
                         'appli_2 appli_1',
                         [call('appli_2'), call('appli_1')])
        self.assertEqual(0, mocked_appli.call_count)
        # test help and request with get_all_applications_info error
        mocked_appli.reset_mock()
        mocked_appli.side_effect = xmlrpclib.Fault('0', 'error')
        plugin.do_application_rules('')
        self.assertEqual([call()], mocked_appli.call_args_list)
        self.assertEqual(0, mocked_rpc.call_count)
        self.check_output_error(True)

    @patch('supvisors.supvisorsctl.ControllerPlugin._upcheck',
           return_value=True)
    def test_process_rules(self, mocked_check):
        """ Test the process_rules request. """
        from supvisors.supvisorsctl import ControllerPlugin
        # create the instance
        plugin = ControllerPlugin(self.controller)
        # test help and request for all rules
        mocked_appli = plugin.supvisors().get_all_applications_info
        mocked_appli.return_value = [{'application_name': 'appli_1'},
                                     {'application_name': 'appli_2'}]
        mocked_rpc = plugin.supvisors().get_process_rules
        returned_rules = [
            [{'application_name': 'appli_1', 'process_name': 'proc_1',
              'addresses': ['10.0.0.1', '10.0.0.2'],
              'start_sequence': 2, 'stop_sequence': 3,
              'required': True, 'wait_exit': False,
              'expected_loading': 50,
              'running_failure_strategy': 1}],
            [{'application_name': 'appli_2', 'process_name': 'proc_3',
              'addresses': ['*'],
              'start_sequence': 1, 'stop_sequence': 0,
              'required': False, 'wait_exit': True,
              'expected_loading': 15,
              'running_failure_strategy': 2}]]
        # first possiblity: no argument
        mocked_rpc.side_effect = returned_rules
        self._check_call(mocked_check, mocked_rpc,
                         plugin.help_process_rules, plugin.do_process_rules, '',
                         [call('appli_1:*'), call('appli_2:*')])
        self.assertEqual([call(), call()], mocked_appli.call_args_list)
        mocked_appli.reset_mock()
        # second possiblity: use 'all'
        mocked_rpc.side_effect = returned_rules
        self._check_call(mocked_check, mocked_rpc,
                         plugin.help_process_rules, plugin.do_process_rules, 'all',
                         [call('appli_1:*'), call('appli_2:*')])
        self.assertEqual([call(), call()], mocked_appli.call_args_list)
        mocked_appli.reset_mock()
        # test help and request for rules from a selection of namespecs
        mocked_rpc.side_effect = returned_rules
        self._check_call(mocked_check, mocked_rpc,
                         plugin.help_process_rules, plugin.do_process_rules,
                         'appli_2:proc_3 appli_1:proc_1',
                         [call('appli_2:proc_3'), call('appli_1:proc_1')])
        self.assertEqual(0, mocked_appli.call_count)
        # test help and request with get_all_applications_info error
        mocked_appli.reset_mock()
        mocked_appli.side_effect = xmlrpclib.Fault('0', 'error')
        plugin.do_process_rules('')
        self.assertEqual([call()], mocked_appli.call_args_list)
        self.assertEqual(0, mocked_rpc.call_count)
        self.check_output_error(True)

    @patch('supvisors.supvisorsctl.ControllerPlugin._upcheck',
           return_value=True)
    def test_conflicts(self, mocked_check):
        """ Test the conflicts request. """
        from supvisors.supvisorsctl import ControllerPlugin
        # create the instance
        plugin = ControllerPlugin(self.controller)
        # test help and request
        mocked_rpc = plugin.supvisors().get_conflicts
        mocked_rpc.return_value = [
            {'application_name': 'appli_1', 'process_name': 'proc_1',
             'statename': 'running', 'addresses': ['10.0.0.1', '10.0.0.2']},
            {'application_name': 'appli_2', 'process_name': 'proc_3',
             'statename': 'stopped', 'addresses': ['10.0.0.2', '10.0.0.3']}]
        self._check_call(mocked_check, mocked_rpc,
                         plugin.help_conflicts, plugin.do_conflicts, '',
                         [call()])

    @patch('supvisors.supvisorsctl.ControllerPlugin._upcheck',
           return_value=True)
    def test_start_application(self, mocked_check):
        """ Test the start_application request. """
        from supvisors.supvisorsctl import ControllerPlugin
        # create the instance
        plugin = ControllerPlugin(self.controller)
        # call the common starting test
        mocked_appli = plugin.supvisors().get_all_applications_info
        mocked_rpc = plugin.supvisors().start_application
        self._check_start_command(mocked_check, mocked_appli, mocked_rpc,
                                  plugin.help_start_application, plugin.do_start_application,
                                  ('appli_1', 'appli_2'),
                                  'appli_2 appli_1', ('appli_2', 'appli_1'))

    @patch('supvisors.supvisorsctl.ControllerPlugin._upcheck',
           return_value=True)
    def test_restart_application(self, mocked_check):
        """ Test the restart_application request. """
        from supvisors.supvisorsctl import ControllerPlugin
        # create the instance
        plugin = ControllerPlugin(self.controller)
        # call the common starting test
        mocked_appli = plugin.supvisors().get_all_applications_info
        mocked_rpc = plugin.supvisors().restart_application
        self._check_start_command(mocked_check, mocked_appli, mocked_rpc,
                                  plugin.help_restart_application, plugin.do_restart_application,
                                  ('appli_1', 'appli_2'),
                                  'appli_2 appli_1', ('appli_2', 'appli_1'))

    @patch('supvisors.supvisorsctl.ControllerPlugin._upcheck',
           return_value=True)
    def test_stop_application(self, mocked_check):
        """ Test the stop_application request. """
        from supvisors.supvisorsctl import ControllerPlugin
        # create the instance
        plugin = ControllerPlugin(self.controller)
        # call the common starting test
        mocked_appli = plugin.supvisors().get_all_applications_info
        mocked_rpc = plugin.supvisors().stop_application
        self._check_stop_command(mocked_check, mocked_appli, mocked_rpc,
                                 plugin.help_stop_application, plugin.do_stop_application,
                                 ('appli_1', 'appli_2'),
                                 'appli_2 appli_1', ('appli_2', 'appli_1'))

    @patch('supvisors.supvisorsctl.ControllerPlugin._upcheck',
           return_value=True)
    def test_start_args(self, mocked_check):
        """ Test the start_args request. """
        from supvisors.supvisorsctl import ControllerPlugin
        # create the instance
        plugin = ControllerPlugin(self.controller)
        # test the request using few arguments
        plugin.do_start_args('')
        self.check_output_error(True)
        self.assertEqual([call()], mocked_check.call_args_list)
        mocked_check.reset_mock()
        # test request to start process without extra arguments
        mocked_rpc = plugin.supvisors().start_args
        self._check_call(mocked_check, mocked_rpc,
                         plugin.help_start_args, plugin.do_start_args,
                         'proc MOST_LOADED all',
                         [call('proc', 'MOST_LOADED all')])

    @patch('supvisors.supvisorsctl.ControllerPlugin._upcheck',
           return_value=True)
    def test_start_process(self, mocked_check):
        """ Test the start_process request. """
        from supvisors.supvisorsctl import ControllerPlugin
        # create the instance
        plugin = ControllerPlugin(self.controller)
        # call the common starting test
        mocked_appli = plugin.supvisors().get_all_applications_info
        mocked_rpc = plugin.supvisors().start_process
        self._check_start_command(mocked_check, mocked_appli, mocked_rpc,
                                  plugin.help_start_process, plugin.do_start_process,
                                  ('appli_1:*', 'appli_2:*'),
                                  'appli_2:proc_3 appli_1:proc_1', ('appli_2:proc_3', 'appli_1:proc_1'))

    @patch('supvisors.supvisorsctl.ControllerPlugin._upcheck',
           return_value=True)
    def test_restart_process(self, mocked_check):
        """ Test the restart_process request. """
        from supvisors.supvisorsctl import ControllerPlugin
        # create the instance
        plugin = ControllerPlugin(self.controller)
        # call the common starting test
        mocked_appli = plugin.supvisors().get_all_applications_info
        mocked_rpc = plugin.supvisors().restart_process
        self._check_start_command(mocked_check, mocked_appli, mocked_rpc,
                                  plugin.help_restart_process, plugin.do_restart_process,
                                  ('appli_1:*', 'appli_2:*'),
                                  'appli_2:proc_3 appli_1:proc_1', ('appli_2:proc_3', 'appli_1:proc_1'))

    @patch('supvisors.supvisorsctl.ControllerPlugin._upcheck',
           return_value=True)
    def test_start_process_args(self, mocked_check):
        """ Test the start_process_args request. """
        from supvisors.supvisorsctl import ControllerPlugin
        # create the instance
        plugin = ControllerPlugin(self.controller)
        # test the request using few arguments
        plugin.do_start_process_args('')
        self.check_output_error(True)
        self.assertEqual([call()], mocked_check.call_args_list)
        mocked_check.reset_mock()
        plugin.do_start_process_args('CONFIG')
        self.check_output_error(True)
        self.assertEqual([call()], mocked_check.call_args_list)
        mocked_check.reset_mock()
        plugin.do_start_process_args('CONFIG proc')
        self.check_output_error(True)
        self.assertEqual([call()], mocked_check.call_args_list)
        mocked_check.reset_mock()
        # test the request using unknown strategy
        plugin.do_start_process_args('strategy program list of arguments')
        self.check_output_error(True)
        self.assertEqual([call()], mocked_check.call_args_list)
        mocked_check.reset_mock()
        # test request to start the process
        mocked_rpc = plugin.supvisors().start_process
        self._check_call(mocked_check, mocked_rpc,
                         plugin.help_start_process_args, plugin.do_start_process_args,
                         'LESS_LOADED appli_2:proc_3 a list of arguments',
                         [call(1, 'appli_2:proc_3', 'a list of arguments')])

    @patch('supvisors.supvisorsctl.ControllerPlugin._upcheck',
           return_value=True)
    def test_stop_process(self, mocked_check):
        """ Test the stop_process request. """
        from supvisors.supvisorsctl import ControllerPlugin
        # create the instance
        plugin = ControllerPlugin(self.controller)
        # call the common starting test
        mocked_appli = plugin.supvisors().get_all_applications_info
        mocked_rpc = plugin.supvisors().stop_process
        self._check_stop_command(mocked_check, mocked_appli, mocked_rpc,
                                 plugin.help_stop_process, plugin.do_stop_process,
                                 ('appli_1:*', 'appli_2:*'),
                                 'appli_2:proc_3 appli_1:proc_1', ('appli_2:proc_3', 'appli_1:proc_1'))

    @patch('supvisors.supvisorsctl.ControllerPlugin._upcheck',
           return_value=True)
    def test_conciliate(self, mocked_check):
        """ Test the conciliate request. """
        from supvisors.supvisorsctl import ControllerPlugin
        # create the instance
        plugin = ControllerPlugin(self.controller)
        # test the request using no strategy
        plugin.do_conciliate('')
        self.check_output_error(True)
        self.assertEqual([call()], mocked_check.call_args_list)
        mocked_check.reset_mock()
        # test the request using unknown strategy
        plugin.do_conciliate('strategy')
        self.check_output_error(True)
        self.assertEqual([call()], mocked_check.call_args_list)
        mocked_check.reset_mock()
        # test help and request
        mocked_rpc = plugin.supvisors().conciliate
        self._check_call(mocked_check, mocked_rpc,
                         plugin.help_conciliate, plugin.do_conciliate,
                         'SENICIDE', [call(0)])

    @patch('supvisors.supvisorsctl.ControllerPlugin._upcheck',
           return_value=True)
    def test_sreload(self, mocked_check):
        """ Test the sreload request. """
        from supvisors.supvisorsctl import ControllerPlugin
        # create the instance
        plugin = ControllerPlugin(self.controller)
        # test help and request
        mocked_rpc = plugin.supvisors().restart
        self._check_call(mocked_check, mocked_rpc,
                         plugin.help_sreload, plugin.do_sreload, '',
                         [call()])

    @patch('supvisors.supvisorsctl.ControllerPlugin._upcheck',
           return_value=True)
    def test_sshutdown(self, mocked_check):
        """ Test the sshutdown request. """
        from supvisors.supvisorsctl import ControllerPlugin
        # create the instance
        plugin = ControllerPlugin(self.controller)
        # test help and request
        mocked_rpc = plugin.supvisors().shutdown
        self._check_call(mocked_check, mocked_rpc,
                         plugin.help_sshutdown, plugin.do_sshutdown, '',
                         [call()])

    def test_upcheck(self):
        """ Test the _upcheck method. """
        from supvisors.rpcinterface import API_VERSION
        from supvisors.supvisorsctl import ControllerPlugin
        # create the instance
        plugin = ControllerPlugin(self.controller)
        # test different API versions
        mocked_rpc = plugin.supvisors().get_api_version
        mocked_rpc.return_value = 'dummy_version'
        self.assertFalse(plugin._upcheck())
        self.check_output_error(True)
        self.assertEqual([call()], mocked_rpc.call_args_list)
        mocked_rpc.reset_mock()
        # test handled RPC error
        mocked_rpc.side_effect = xmlrpclib.Fault(Faults.UNKNOWN_METHOD, '')
        self.assertFalse(plugin._upcheck())
        self.check_output_error(True)
        self.assertEqual([call()], mocked_rpc.call_args_list)
        mocked_rpc.reset_mock()
        # test not handled RPC error
        mocked_rpc.side_effect = xmlrpclib.Fault('0', 'error')
        with self.assertRaises(xmlrpclib.Fault):
            plugin._upcheck()
        self.assertEqual([call()], mocked_rpc.call_args_list)
        mocked_rpc.reset_mock()
        # test handled socket errors
        mocked_rpc.side_effect = socket.error(errno.ECONNREFUSED)
        self.assertFalse(plugin._upcheck())
        self.check_output_error(True)
        self.assertEqual([call()], mocked_rpc.call_args_list)
        mocked_rpc.reset_mock()
        mocked_rpc.side_effect = socket.error(errno.ENOENT)
        self.assertFalse(plugin._upcheck())
        self.check_output_error(True)
        self.assertEqual([call()], mocked_rpc.call_args_list)
        mocked_rpc.reset_mock()
        # test not handled socket error
        mocked_rpc.side_effect = socket.error(errno.EWOULDBLOCK)
        with self.assertRaises(socket.error):
            plugin._upcheck()
        self.assertEqual([call()], mocked_rpc.call_args_list)
        mocked_rpc.reset_mock()
        # test normal behaviour
        mocked_rpc.side_effect = None
        mocked_rpc.return_value = API_VERSION
        self.assertTrue(plugin._upcheck())
        self.assertEqual([call()], mocked_rpc.call_args_list)

    @patch('supvisors.supvisorsctl.ControllerPlugin')
    def test_make_plugin(self, mocked_plugin):
        """ Test the plugin factory. """
        from supvisors.supvisorsctl import make_supvisors_controller_plugin
        make_supvisors_controller_plugin(self.controller)
        self.assertEqual([call(self.controller)], mocked_plugin.call_args_list)

    def _check_start_command(self, mocked_check, mocked_appli, mocked_rpc,
                             help_cmd, do_cmd, all_result, sel_args, sel_result):
        """ Common test of a starting command. """
        # test the request using few arguments
        do_cmd('')
        self.check_output_error(True)
        self.assertEqual([call()], mocked_check.call_args_list)
        mocked_check.reset_mock()
        # test the request using unknown strategy
        do_cmd('strategy')
        self.check_output_error(True)
        self.assertEqual([call()], mocked_check.call_args_list)
        mocked_check.reset_mock()
        # test request to start all
        mocked_appli.return_value = [{'application_name': 'appli_1'},
                                     {'application_name': 'appli_2'}]
        # first possibility: use no name
        self._check_call(mocked_check, mocked_rpc,
                         help_cmd, do_cmd, 'LESS_LOADED',
                         [call(1, all_result[0]), call(1, all_result[1])])
        self.assertEqual([call(), call()], mocked_appli.call_args_list)
        mocked_appli.reset_mock()
        # second possiblity: use 'all'
        self._check_call(mocked_check, mocked_rpc,
                         help_cmd, do_cmd, 'MOST_LOADED all',
                         [call(2, all_result[0]), call(2, all_result[1])])
        self.assertEqual([call(), call()], mocked_appli.call_args_list)
        mocked_appli.reset_mock()
        # test help and request for starting a selection
        self._check_call(mocked_check, mocked_rpc,
                         help_cmd, do_cmd, 'CONFIG ' + sel_args,
                         [call(0, sel_result[0]), call(0, sel_result[1])])
        # test help and request with get_all_applications_info error
        mocked_appli.reset_mock()
        mocked_appli.side_effect = xmlrpclib.Fault('0', 'error')
        do_cmd('LESS_LOADED')
        self.assertEqual([call()], mocked_appli.call_args_list)
        self.assertEqual(0, mocked_rpc.call_count)
        self.check_output_error(True)

    def _check_stop_command(self, mocked_check, mocked_appli, mocked_rpc,
                            help_cmd, do_cmd, all_result, sel_args, sel_result):
        """ Common test of a stopping command. """
        # test request to stop all
        mocked_appli.return_value = [{'application_name': 'appli_1'},
                                     {'application_name': 'appli_2'}]
        # first possibility: use no name
        self._check_call(mocked_check, mocked_rpc,
                         help_cmd, do_cmd, '',
                         [call(all_result[0]), call(all_result[1])])
        self.assertEqual([call(), call()], mocked_appli.call_args_list)
        mocked_appli.reset_mock()
        # second possiblity: use 'all'
        self._check_call(mocked_check, mocked_rpc,
                         help_cmd, do_cmd, 'all',
                         [call(all_result[0]), call(all_result[1])])
        self.assertEqual([call(), call()], mocked_appli.call_args_list)
        mocked_appli.reset_mock()
        # test help and request for starting a selection of applications
        self._check_call(mocked_check, mocked_rpc,
                         help_cmd, do_cmd, sel_args,
                         [call(sel_result[0]), call(sel_result[1])])
        # test help and request with get_all_applications_info error
        mocked_appli.reset_mock()
        mocked_appli.side_effect = xmlrpclib.Fault('0', 'error')
        do_cmd('')
        self.assertEqual([call()], mocked_appli.call_args_list)
        self.assertEqual(0, mocked_rpc.call_count)
        self.check_output_error(True)

    def _check_call(self, mocked_check, mocked_rpc,
                    help_fct, do_fct, arg, rpc_result):
        """ Generic test of help and request. """
        # test that help uses output
        help_fct()
        self.assertTrue(self.controller.output.called)
        self.controller.output.reset_mock()
        # test request
        do_fct(arg)
        # test upcheck call if any
        if mocked_check:
            self.assertEqual([call()], mocked_check.call_args_list)
            mocked_check.reset_mock()
        # test RPC if any
        if mocked_rpc:
            self.assertEqual(rpc_result, mocked_rpc.call_args_list)
            mocked_rpc.reset_mock()
        # test ouput (with no error)
        self.check_output_error(False)
        # test request error
        mocked_rpc.side_effect = xmlrpclib.Fault('0', 'error')
        do_fct(arg)
        mocked_rpc.side_effect = None
        # test upcheck call if any
        if mocked_check:
            self.assertEqual([call()], mocked_check.call_args_list)
            mocked_check.reset_mock()
        # test RPC if any
        if mocked_rpc:
            self.assertEqual(rpc_result, mocked_rpc.call_args_list)
            mocked_rpc.reset_mock()
        # test ouput (with error)
        self.check_output_error(True)

    def check_output_error(self, error):
        """ Test ouput error of controller. """
        self.assertTrue(self.controller.output.called)
        self.assertEqual(error, any('ERROR' in str(ocall)
                                    for ocall in self.controller.output.call_args_list))
        self.controller.output.reset_mock()


def test_suite():
    return unittest.findTestCases(sys.modules[__name__])


if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
