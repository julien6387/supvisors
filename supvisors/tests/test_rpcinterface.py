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

from unittest.mock import call, patch, Mock
from supervisor.http import NOT_DONE_YET
from supervisor.xmlrpc import Faults, RPCError

from supvisors.tests.base import DummySupervisor, MockedSupvisors


class RpcInterfaceTest(unittest.TestCase):
    """ Test case for the rpcinterface module. """

    def setUp(self):
        """ Create a dummy Supervisor structure and start a global patch. """
        # add fault codes to Supervisor
        from supvisors.plugin import expand_faults
        expand_faults()
        # create the instance to be tested
        from supvisors.rpcinterface import RPCInterface
        self.supvisors = MockedSupvisors()
        self.rpc = RPCInterface(self.supvisors)

    def test_creation(self):
        """ Test the values set at construction. """
        self.assertIs(self.rpc.supvisors, self.supvisors)

    def test_api_version(self):
        """ Test the get_api_version self.rpc. """
        from supvisors.rpcinterface import API_VERSION
        self.assertEqual(API_VERSION, self.rpc.get_api_version())

    def test_supvisors_state(self):
        """ Test the get_supvisors_state self.rpc. """
        # prepare context
        self.supvisors.fsm.serial.return_value = 'RUNNING'
        # test call
        self.assertEqual('RUNNING', self.rpc.get_supvisors_state())

    def test_master_address(self):
        """ Test the get_master_address self.rpc. """
        # prepare context
        self.supvisors.context.master_node_name = '10.0.0.1'
        # test call
        self.assertEqual('10.0.0.1', self.rpc.get_master_address())

    def test_strategies(self):
        """ Test the get_strategies self.rpc. """
        from supvisors.ttypes import ConciliationStrategies, StartingStrategies
        # prepare context
        self.supvisors.options.auto_fence = True
        self.supvisors.options.conciliation_strategy = ConciliationStrategies.INFANTICIDE
        self.supvisors.options.starting_strategy = StartingStrategies.MOST_LOADED
        # test call
        self.assertDictEqual({'auto-fencing': True, 'starting': 'MOST_LOADED',
                              'conciliation': 'INFANTICIDE'}, self.rpc.get_strategies())

    def test_address_info(self):
        """ Test the get_address_info self.rpc. """
        # prepare context
        self.supvisors.context.addresses = {'10.0.0.1': Mock(**{'serial.return_value': 'address_info'})}
        # test with known address
        self.assertEqual('address_info', self.rpc.get_address_info('10.0.0.1'))
        # test with unknown address
        with self.assertRaises(RPCError) as exc:
            self.rpc.get_address_info('10.0.0.0')
        self.assertEqual(Faults.BAD_ADDRESS, exc.exception.code)
        self.assertEqual('BAD_ADDRESS: address 10.0.0.0 unknown to Supvisors', exc.exception.text)

    def test_all_addresses_info(self):
        """ Test the get_all_addresses_info self.rpc. """
        # prepare context
        self.supvisors.context.addresses = {'10.0.0.1': Mock(**{'serial.return_value': 'address_info_1'}),
                                            '10.0.0.2': Mock(**{'serial.return_value': 'address_info_2'})}
        # test call
        self.assertListEqual(['address_info_1', 'address_info_2'], self.rpc.get_all_addresses_info())

    @patch('supvisors.rpcinterface.RPCInterface._check_from_deployment')
    @patch('supvisors.rpcinterface.RPCInterface._get_application',
           return_value=Mock(**{'serial.return_value': {'name': 'appli'}}))
    def test_application_info(self, mocked_serial, mocked_check):
        """ Test the get_application_info self.rpc. """
        # test RPC call
        self.assertEqual({'name': 'appli'}, self.rpc.get_application_info('dummy'))
        self.assertEqual([call()], mocked_check.call_args_list)
        self.assertEqual([call('dummy')], mocked_serial.call_args_list)

    @patch('supvisors.rpcinterface.RPCInterface._check_from_deployment')
    @patch('supvisors.rpcinterface.RPCInterface.get_application_info',
           side_effect=[{'name': 'appli_1'}, {'name': 'appli_2'}])
    def test_all_applications_info(self, mocked_get, mocked_check):
        """ Test the get_all_applications_info self.rpc. """
        # prepare context
        self.supvisors.context.applications = {'dummy_1': None, 'dummy_2': None}
        # test RPC call
        self.assertListEqual([{'name': 'appli_1'}, {'name': 'appli_2'}],
                             self.rpc.get_all_applications_info())
        self.assertEqual([call()], mocked_check.call_args_list)
        self.assertListEqual([call('dummy_1'), call('dummy_2')], mocked_get.call_args_list)

    @patch('supvisors.rpcinterface.RPCInterface._check_from_deployment')
    @patch('supvisors.rpcinterface.RPCInterface._get_application_process',
           side_effect=[(None, Mock(**{'serial.return_value': {'name': 'proc'}})),
                        (Mock(**{'processes.values.return_value': [
                            Mock(**{'serial.return_value': {'name': 'proc_1'}}),
                            Mock(**{'serial.return_value': {'name': 'proc_2'}})]}), None)])
    def test_process_info(self, mocked_get, mocked_check):
        """ Test the get_process_info self.rpc. """
        # test first RPC call with process namespec
        self.assertEqual([{'name': 'proc'}], self.rpc.get_process_info('appli:proc'))
        self.assertEqual([call()], mocked_check.call_args_list)
        self.assertEqual([call('appli:proc')], mocked_get.call_args_list)
        # reset patches
        mocked_check.reset_mock()
        mocked_get.reset_mock()
        # test second RPC call with group namespec
        self.assertEqual([{'name': 'proc_1'}, {'name': 'proc_2'}], self.rpc.get_process_info('appli:*'))
        self.assertEqual([call()], mocked_check.call_args_list)
        self.assertEqual([call('appli:*')], mocked_get.call_args_list)

    @patch('supvisors.rpcinterface.RPCInterface._check_from_deployment')
    def test_all_process_info(self, mocked_check):
        """ Test the get_all_process_info self.rpc. """
        # prepare context
        self.supvisors.context.processes = {'proc_1': Mock(**{'serial.return_value': {'name': 'proc_1'}}),
                                            'proc_2': Mock(**{'serial.return_value': {'name': 'proc_2'}})}
        # test RPC call
        self.assertListEqual([{'name': 'proc_1'}, {'name': 'proc_2'}], self.rpc.get_all_process_info())
        self.assertEqual([call()], mocked_check.call_args_list)

    @patch('supvisors.rpcinterface.RPCInterface._get_local_info', return_value={'group': 'group', 'name': 'name'})
    def test_local_process_info(self, mocked_get):
        """ Test the get_local_process_info self.rpc. """
        # prepare context
        info_source = self.supvisors.info_source
        mocked_rpc = info_source.supervisor_rpc_interface.getProcessInfo
        mocked_rpc.return_value = {'group': 'dummy_group', 'name': 'dummy_name'}
        # test RPC call with process namespec
        self.assertEqual({'group': 'group', 'name': 'name'}, self.rpc.get_local_process_info('appli:proc'))
        self.assertEqual([call('appli:proc')], mocked_rpc.call_args_list)
        self.assertEqual([call({'group': 'dummy_group', 'name': 'dummy_name'})], mocked_get.call_args_list)

    @patch('supvisors.rpcinterface.RPCInterface._get_local_info', return_value={'group': 'group', 'name': 'name'})
    def test_all_local_process_info(self, mocked_get):
        """ Test the get_all_local_process_info self.rpc. """
        # prepare context
        info_source = self.supvisors.info_source
        mocked_rpc = info_source.supervisor_rpc_interface.getAllProcessInfo
        mocked_rpc.return_value = [{'group': 'dummy_group', 'name': 'dummy_name'}]
        # test RPC call with process namespec
        self.assertEqual([{'group': 'group', 'name': 'name'}], self.rpc.get_all_local_process_info())
        self.assertEqual([call()], mocked_rpc.call_args_list)
        self.assertEqual([call({'group': 'dummy_group', 'name': 'dummy_name'})], mocked_get.call_args_list)

    @patch('supvisors.rpcinterface.RPCInterface._check_from_deployment')
    @patch('supvisors.rpcinterface.RPCInterface._get_application',
           return_value=Mock(**{'rules.serial.return_value': {'start': 1, 'stop': 2, 'required': True}}))
    def test_application_rules(self, mocked_get, mocked_check):
        """ Test the get_application_rules self.rpc. """
        # test RPC call with application name
        self.assertDictEqual(self.rpc.get_application_rules('appli'),
                             {'application_name': 'appli', 'start': 1, 'stop': 2, 'required': True})
        self.assertEqual([call()], mocked_check.call_args_list)
        self.assertEqual([call('appli')], mocked_get.call_args_list)

    @patch('supvisors.rpcinterface.RPCInterface._check_from_deployment')
    @patch('supvisors.rpcinterface.RPCInterface._get_application_process',
           side_effect=[(None, '1'), (Mock(**{'processes.values.return_value': ['1', '2']}), None)])
    @patch('supvisors.rpcinterface.RPCInterface._get_internal_process_rules',
           side_effect=[{'start': 1}, {'stop': 2}, {'required': True}])
    def test_process_rules(self, mocked_rules, mocked_get, mocked_check):
        """ Test the get_process_rules self.rpc. """
        # test first RPC call with process namespec
        self.assertEqual([{'start': 1}], self.rpc.get_process_rules('appli:proc'))
        self.assertEqual([call()], mocked_check.call_args_list)
        self.assertEqual([call('appli:proc')], mocked_get.call_args_list)
        self.assertEqual([call('1')], mocked_rules.call_args_list)
        # reset patches
        mocked_check.reset_mock()
        mocked_get.reset_mock()
        mocked_rules.reset_mock()
        # test second RPC call with group namespec
        self.assertEqual([{'stop': 2}, {'required': True}], self.rpc.get_process_rules('appli:*'))
        self.assertEqual([call()], mocked_check.call_args_list)
        self.assertEqual([call('appli:*')], mocked_get.call_args_list)
        self.assertEqual([call('1'), call('2')], mocked_rules.call_args_list)

    @patch('supvisors.rpcinterface.RPCInterface._check_from_deployment')
    def test_conflicts(self, mocked_check):
        """ Test the get_conflicts self.rpc. """
        # prepare context
        self.supvisors.context.processes = {'proc_1': Mock(**{'conflicting.return_value': True,
                                                              'serial.return_value': {'name': 'proc_1'}}),
                                            'proc_2': Mock(**{'conflicting.return_value': False,
                                                              'serial.return_value': {'name': 'proc_2'}}),
                                            'proc_3': Mock(**{'conflicting.return_value': True,
                                                              'serial.return_value': {'name': 'proc_3'}})}
        # test RPC call
        self.assertListEqual([{'name': 'proc_1'}, {'name': 'proc_3'}], self.rpc.get_conflicts())
        self.assertEqual([call()], mocked_check.call_args_list)

    @patch('supvisors.rpcinterface.RPCInterface._check_operating')
    def test_start_application(self, mocked_check):
        """ Test the start_application self.rpc. """
        from supvisors.ttypes import ApplicationStates, StartingStrategies
        # prepare context
        self.supvisors.context.applications = {'appli_1': Mock()}
        # get patches
        mocked_start = self.supvisors.starter.start_application
        mocked_progress = self.supvisors.starter.in_progress
        # test RPC call with unknown strategy
        with self.assertRaises(RPCError) as exc:
            self.rpc.start_application('strategy', 'appli')
        self.assertEqual(Faults.BAD_STRATEGY, exc.exception.code)
        self.assertEqual('BAD_STRATEGY: strategy', exc.exception.text)
        self.assertEqual([call()], mocked_check.call_args_list)
        self.assertEqual(0, mocked_start.call_count)
        self.assertEqual(0, mocked_progress.call_count)
        mocked_check.reset_mock()
        # test RPC call with unknown application
        with self.assertRaises(RPCError) as exc:
            self.rpc.start_application(0, 'appli')
        self.assertEqual(Faults.BAD_NAME, exc.exception.code)
        self.assertEqual('BAD_NAME: appli', exc.exception.text)
        self.assertEqual([call()], mocked_check.call_args_list)
        self.assertEqual(0, mocked_start.call_count)
        self.assertEqual(0, mocked_progress.call_count)
        mocked_check.reset_mock()
        # test RPC call with running application
        application = self.supvisors.context.applications['appli_1']
        for appli_state in [ApplicationStates.STOPPING, ApplicationStates.RUNNING, ApplicationStates.STARTING]:
            application.state = appli_state
            with self.assertRaises(RPCError) as exc:
                self.rpc.start_application(0, 'appli_1')
            self.assertEqual(Faults.ALREADY_STARTED, exc.exception.code)
            self.assertEqual('ALREADY_STARTED: appli_1', exc.exception.text)
            self.assertEqual([call()], mocked_check.call_args_list)
            self.assertEqual(0, mocked_start.call_count)
            self.assertEqual(0, mocked_progress.call_count)
            mocked_check.reset_mock()
        # test RPC call with stopped application
        # test no wait and not done
        application.state = ApplicationStates.STOPPED
        mocked_start.return_value = False
        result = self.rpc.start_application(0, 'appli_1', False)
        self.assertTrue(result)
        self.assertEqual([call()], mocked_check.call_args_list)
        self.assertEqual([call(StartingStrategies.CONFIG, application)], mocked_start.call_args_list)
        self.assertEqual(0, mocked_progress.call_count)
        mocked_check.reset_mock()
        mocked_start.reset_mock()
        # test no wait and done
        application.state = ApplicationStates.STOPPED
        mocked_start.return_value = True
        result = self.rpc.start_application(0, 'appli_1', False)
        self.assertFalse(result)
        self.assertEqual([call()], mocked_check.call_args_list)
        self.assertEqual([call(StartingStrategies.CONFIG, application)], mocked_start.call_args_list)
        self.assertEqual(0, mocked_progress.call_count)
        mocked_check.reset_mock()
        mocked_start.reset_mock()
        # test wait and done
        mocked_start.return_value = True
        result = self.rpc.start_application(0, 'appli_1')
        self.assertFalse(result)
        self.assertEqual([call()], mocked_check.call_args_list)
        self.assertEqual([call(StartingStrategies.CONFIG, application)], mocked_start.call_args_list)
        self.assertEqual(0, mocked_progress.call_count)
        mocked_check.reset_mock()
        mocked_start.reset_mock()
        # test wait and not done
        mocked_start.return_value = False
        deferred = self.rpc.start_application(0, 'appli_1')
        # result is a function for deferred result
        self.assertTrue(callable(deferred))
        self.assertEqual([call()], mocked_check.call_args_list)
        self.assertEqual([call(StartingStrategies.CONFIG, application)], mocked_start.call_args_list)
        self.assertEqual(0, mocked_progress.call_count)
        # test returned function: return True when job in progress
        mocked_progress.return_value = True
        self.assertEqual(NOT_DONE_YET, deferred())
        self.assertEqual([call()], mocked_progress.call_args_list)
        mocked_progress.reset_mock()
        # test returned function: raise exception if job not in progress anymore
        # and application not running
        mocked_progress.return_value = False
        for _ in [ApplicationStates.STOPPING, ApplicationStates.STOPPED, ApplicationStates.STARTING]:
            with self.assertRaises(RPCError) as exc:
                deferred()
            self.assertEqual(Faults.ABNORMAL_TERMINATION, exc.exception.code)
            self.assertEqual('ABNORMAL_TERMINATION: appli_1', exc.exception.text)
            self.assertEqual([call()], mocked_progress.call_args_list)
            mocked_progress.reset_mock()
        # test returned function: return True if job not in progress anymore
        # and application running
        application.state = ApplicationStates.RUNNING
        self.assertTrue(deferred())
        self.assertEqual([call()], mocked_progress.call_args_list)

    @patch('supvisors.rpcinterface.RPCInterface._check_operating_conciliation')
    def test_stop_application(self, mocked_check):
        """ Test the stop_application self.rpc. """
        from supvisors.ttypes import ApplicationStates
        # prepare context
        self.supvisors.context.applications = {'appli_1': Mock()}
        # get patches
        mocked_stop = self.supvisors.stopper.stop_application
        mocked_progress = self.supvisors.stopper.in_progress
        # test RPC call with unknown application
        with self.assertRaises(RPCError) as exc:
            self.rpc.stop_application('appli')
        self.assertEqual(Faults.BAD_NAME, exc.exception.code)
        self.assertEqual('BAD_NAME: appli', exc.exception.text)
        self.assertEqual([call()], mocked_check.call_args_list)
        self.assertEqual(0, mocked_stop.call_count)
        self.assertEqual(0, mocked_progress.call_count)
        mocked_check.reset_mock()
        # test RPC call with stopped application
        application = self.supvisors.context.applications['appli_1']
        application.state = ApplicationStates.STOPPED
        with self.assertRaises(RPCError) as exc:
            self.rpc.stop_application('appli_1')
        self.assertEqual(Faults.NOT_RUNNING, exc.exception.code)
        self.assertEqual('NOT_RUNNING: appli_1', exc.exception.text)
        self.assertEqual([call()], mocked_check.call_args_list)
        self.assertEqual(0, mocked_stop.call_count)
        self.assertEqual(0, mocked_progress.call_count)
        mocked_check.reset_mock()
        # test RPC call with running application
        for appli_state in [ApplicationStates.STOPPING, ApplicationStates.RUNNING, ApplicationStates.STARTING]:
            application.state = appli_state
            # test no wait and done
            mocked_stop.return_value = True
            result = self.rpc.stop_application('appli_1', False)
            self.assertFalse(result)
            self.assertEqual([call()], mocked_check.call_args_list)
            self.assertEqual([call(application)], mocked_stop.call_args_list)
            self.assertEqual(0, mocked_progress.call_count)
            mocked_check.reset_mock()
            mocked_stop.reset_mock()
            # test wait and done
            mocked_stop.return_value = True
            result = self.rpc.stop_application('appli_1')
            self.assertFalse(result)
            self.assertEqual([call()], mocked_check.call_args_list)
            self.assertEqual([call(application)], mocked_stop.call_args_list)
            self.assertEqual(0, mocked_progress.call_count)
            mocked_check.reset_mock()
            mocked_stop.reset_mock()
            # test wait and not done
            mocked_stop.return_value = False
            result = self.rpc.stop_application('appli_1')
            # result is a function
            self.assertTrue(callable(result))
            self.assertEqual([call()], mocked_check.call_args_list)
            self.assertEqual([call(application)], mocked_stop.call_args_list)
            self.assertEqual(0, mocked_progress.call_count)
            # test returned function: return True when job in progress
            mocked_progress.return_value = True
            self.assertEqual(NOT_DONE_YET, result())
            self.assertEqual([call()], mocked_progress.call_args_list)
            mocked_progress.reset_mock()
            # test returned function: raise exception if job not in progress anymore
            # and application not running
            mocked_progress.return_value = False
            for _ in [ApplicationStates.STOPPING, ApplicationStates.RUNNING, ApplicationStates.STARTING]:
                with self.assertRaises(RPCError) as exc:
                    result()
                self.assertEqual(Faults.ABNORMAL_TERMINATION, exc.exception.code)
                self.assertEqual('ABNORMAL_TERMINATION: appli_1', exc.exception.text)
                self.assertEqual([call()], mocked_progress.call_args_list)
                mocked_progress.reset_mock()
            # test returned function: return True if job not in progress anymore
            # and application running
            application.state = ApplicationStates.STOPPED
            self.assertTrue(result())
            self.assertEqual([call()], mocked_progress.call_args_list)
            # reset patches for next loop
            mocked_check.reset_mock()
            mocked_stop.reset_mock()
            mocked_progress.reset_mock()

    @patch('supvisors.rpcinterface.RPCInterface.start_application')
    @patch('supvisors.rpcinterface.RPCInterface.stop_application')
    @patch('supvisors.rpcinterface.RPCInterface._check_operating')
    def test_restart_application(self, mocked_check, mocked_stop, mocked_start):
        """ Test the restart_application self.rpc. """
        from supvisors.ttypes import StartingStrategies
        # test RPC call with sub-RPC calls return a direct result
        mocked_stop.return_value = True
        mocked_start.return_value = False
        deferred = self.rpc.restart_application(0, 'appli', 'wait')
        self.assertEqual([call()], mocked_check.call_args_list)
        self.assertEqual([call('appli', True)], mocked_stop.call_args_list)
        self.assertEqual(0, mocked_start.call_count)
        mocked_stop.reset_mock()
        mocked_check.reset_mock()
        # result is a function
        self.assertTrue(callable(deferred))
        self.assertTrue(deferred.waitstop)
        # test this function
        self.assertFalse(deferred())
        self.assertFalse(deferred.waitstop)
        self.assertEqual(0, mocked_stop.call_count)
        self.assertEqual([call(0, 'appli', 'wait')], mocked_start.call_args_list)
        mocked_start.reset_mock()
        # test RPC call with sub_RPC calls returning jobs
        # test with mocking functions telling that the jobs are not completed
        mocked_stop_job = Mock(return_value=False)
        mocked_start_job = Mock(return_value=False)
        mocked_stop.return_value = mocked_stop_job
        mocked_start.return_value = mocked_start_job
        deferred = self.rpc.restart_application(0, 'appli', 'wait')
        self.assertEqual([call()], mocked_check.call_args_list)
        self.assertEqual([call('appli', True)], mocked_stop.call_args_list)
        self.assertEqual(0, mocked_start.call_count)
        mocked_stop.reset_mock()
        # result is a function for deferred result
        self.assertTrue(callable(deferred))
        self.assertTrue(deferred.waitstop)
        # first call to this function tells that job is still in progress
        self.assertEqual(0, mocked_stop_job.call_count)
        self.assertEqual(0, mocked_start_job.call_count)
        self.assertEqual(NOT_DONE_YET, deferred())
        self.assertEqual(0, mocked_stop.call_count)
        self.assertEqual(0, mocked_start.call_count)
        self.assertEqual([call()], mocked_stop_job.call_args_list)
        self.assertEqual(0, mocked_start_job.call_count)
        mocked_stop_job.reset_mock()
        # replace the stop job with a function telling that the job is completed
        mocked_stop_job.return_value = True
        self.assertEqual(NOT_DONE_YET, deferred())
        self.assertFalse(deferred.waitstop)
        self.assertEqual(0, mocked_stop.call_count)
        self.assertEqual([call(0, 'appli', 'wait')], mocked_start.call_args_list)
        self.assertEqual([call()], mocked_stop_job.call_args_list)
        self.assertEqual(0, mocked_start_job.call_count)
        mocked_stop_job.reset_mock()
        # call the deferred function again to check that the start is engaged
        self.assertFalse(deferred())
        self.assertEqual([call()], mocked_start_job.call_args_list)
        self.assertEqual(0, mocked_stop_job.call_count)

    @patch('supvisors.rpcinterface.RPCInterface._get_application_process',
           return_value=(None, Mock(**{'namespec.return_value': 'appli:proc'})))
    def test_start_args(self, mocked_proc):
        """ Test the start_args self.rpc. """
        # prepare context
        info_source = self.supvisors.info_source
        info_source.update_extra_args.side_effect = KeyError
        mocked_startProcess = info_source.supervisor_rpc_interface.startProcess
        mocked_startProcess.side_effect = [RPCError(Faults.NO_FILE, 'no file'),
                                           RPCError(Faults.NOT_EXECUTABLE),
                                           RPCError(Faults.ABNORMAL_TERMINATION),
                                           'done']
        # test RPC call with extra arguments but with a process that is
        # unknown to Supervisor
        with self.assertRaises(RPCError) as exc:
            self.rpc.start_args('appli:proc', 'dummy arguments')
        self.assertEqual(Faults.BAD_NAME, exc.exception.code)
        self.assertEqual('BAD_NAME: namespec appli:proc unknown to this Supervisor instance', exc.exception.text)
        self.assertEqual([call('appli:proc', 'dummy arguments')], info_source.update_extra_args.call_args_list)
        self.assertEqual(0, mocked_startProcess.call_count)
        # update mocking
        info_source.update_extra_args.reset_mock()
        info_source.update_extra_args.side_effect = None
        # test RPC call with start exceptions
        # NO_FILE exception triggers an update of the process state
        with self.assertRaises(RPCError) as exc:
            self.rpc.start_args('appli:proc')
        self.assertEqual(Faults.NO_FILE, exc.exception.code)
        self.assertEqual("NO_FILE: no file", exc.exception.text)
        self.assertEqual([call('appli:proc', '')], info_source.update_extra_args.call_args_list)
        self.assertEqual([call('appli:proc', True)], mocked_startProcess.call_args_list)
        self.assertEqual([call('appli:proc', 'NO_FILE: no file')], info_source.force_process_fatal.call_args_list)
        # reset patches
        info_source.update_extra_args.reset_mock()
        info_source.force_process_fatal.reset_mock()
        mocked_startProcess.reset_mock()
        # NOT_EXECUTABLE exception triggers an update of the process state
        with self.assertRaises(RPCError) as exc:
            self.rpc.start_args('appli:proc', wait=False)
        self.assertEqual(Faults.NOT_EXECUTABLE, exc.exception.code)
        self.assertEqual("NOT_EXECUTABLE", exc.exception.text)
        self.assertEqual([call('appli:proc', '')], info_source.update_extra_args.call_args_list)
        self.assertEqual([call('appli:proc', False)], mocked_startProcess.call_args_list)
        self.assertEqual([call('appli:proc', 'NOT_EXECUTABLE')], info_source.force_process_fatal.call_args_list)
        # reset patches
        info_source.update_extra_args.reset_mock()
        info_source.force_process_fatal.reset_mock()
        mocked_startProcess.reset_mock()
        # other exception doesn't trigger an update of the process state
        with self.assertRaises(RPCError) as exc:
            self.rpc.start_args('appli:proc', wait=False)
        self.assertEqual(Faults.ABNORMAL_TERMINATION, exc.exception.code)
        self.assertEqual('ABNORMAL_TERMINATION', exc.exception.text)
        self.assertEqual([call('appli:proc', '')], info_source.update_extra_args.call_args_list)
        self.assertEqual([call('appli:proc', False)], mocked_startProcess.call_args_list)
        self.assertFalse(info_source.force_process_fatal.called)
        # reset patches
        info_source.update_extra_args.reset_mock()
        mocked_startProcess.reset_mock()
        # finally, normal behaviour
        self.assertEqual('done', self.rpc.start_args('appli:proc'))
        self.assertEqual([call('appli:proc', '')], info_source.update_extra_args.call_args_list)
        self.assertEqual([call('appli:proc', True)], mocked_startProcess.call_args_list)
        self.assertFalse(info_source.force_process_fatal.called)

    @patch('supvisors.rpcinterface.RPCInterface._check_operating')
    def test_start_process(self, mocked_check):
        """ Test the start_process self.rpc. """
        from supvisors.ttypes import StartingStrategies
        # get patches
        mocked_start = self.supvisors.starter.start_process
        mocked_progress = self.supvisors.starter.in_progress
        # patch the instance
        self.rpc._get_application_process = Mock()
        # test RPC call with unknown strategy
        with self.assertRaises(RPCError) as exc:
            self.rpc.start_process('strategy', 'appli:proc')
        self.assertEqual(Faults.BAD_STRATEGY, exc.exception.code)
        self.assertEqual('BAD_STRATEGY: strategy', exc.exception.text)
        self.assertEqual([call()], mocked_check.call_args_list)
        self.assertEqual(0, mocked_start.call_count)
        self.assertEqual(0, mocked_progress.call_count)
        mocked_check.reset_mock()
        # test RPC call with running process
        self.rpc._get_application_process.return_value = (None, Mock(**{'running.return_value': True,
                                                                   'namespec.return_value': 'proc1'}))
        with self.assertRaises(RPCError) as exc:
            self.rpc.start_process(0, 'appli_1')
        self.assertEqual(Faults.ALREADY_STARTED, exc.exception.code)
        self.assertEqual('ALREADY_STARTED: proc1', exc.exception.text)
        self.assertEqual([call()], mocked_check.call_args_list)
        self.assertEqual(0, mocked_start.call_count)
        self.assertEqual(0, mocked_progress.call_count)
        mocked_check.reset_mock()
        # test RPC call with running processes
        self.rpc._get_application_process.return_value = (
            Mock(**{'processes.values.return_value': [
                Mock(**{'running.return_value': False}),
                Mock(**{'running.return_value': True,
                        'namespec.return_value': 'proc2'})]}), None)
        with self.assertRaises(RPCError) as exc:
            self.rpc.start_process(0, 'appli_1')
        self.assertEqual(Faults.ALREADY_STARTED, exc.exception.code)
        self.assertEqual('ALREADY_STARTED: proc2', exc.exception.text)
        self.assertEqual([call()], mocked_check.call_args_list)
        self.assertEqual(0, mocked_start.call_count)
        self.assertEqual(0, mocked_progress.call_count)
        mocked_check.reset_mock()
        # test RPC call with stopped processes
        proc_1 = Mock(**{'running.return_value': False,
                         'stopped.return_value': True,
                         'namespec.return_value': 'proc1'})
        proc_2 = Mock(**{'running.return_value': False,
                         'stopped.return_value': False,
                         'namespec.return_value': 'proc2'})
        self.rpc._get_application_process.return_value = (
            Mock(**{'processes.values.return_value': [proc_1, proc_2]}), None)
        # test RPC call with no wait and not done
        mocked_start.return_value = False
        result = self.rpc.start_process(1, 'appli:*', 'argument list', False)
        self.assertTrue(result)
        self.assertEqual([call()], mocked_check.call_args_list)
        self.assertEqual([call(StartingStrategies.LESS_LOADED, proc_1, 'argument list'),
                          call(StartingStrategies.LESS_LOADED, proc_2, 'argument list')],
                         mocked_start.call_args_list)
        self.assertFalse(mocked_progress.called)
        mocked_check.reset_mock()
        mocked_start.reset_mock()
        # test RPC call no wait and done
        mocked_start.return_value = True
        result = self.rpc.start_process(1, 'appli:*', 'argument list', False)
        self.assertTrue(result)
        self.assertEqual([call()], mocked_check.call_args_list)
        self.assertEqual([call(StartingStrategies.LESS_LOADED, proc_1, 'argument list'),
                          call(StartingStrategies.LESS_LOADED, proc_2, 'argument list')],
                         mocked_start.call_args_list)
        self.assertFalse(mocked_progress.called)
        mocked_check.reset_mock()
        mocked_start.reset_mock()
        # test RPC call with wait and done
        result = self.rpc.start_process(2, 'appli:*', wait=True)
        self.assertTrue(result)
        self.assertEqual([call(StartingStrategies.MOST_LOADED, proc_1, ''),
                          call(StartingStrategies.MOST_LOADED, proc_2, '')],
                         mocked_start.call_args_list)
        self.assertFalse(mocked_progress.called)
        mocked_check.reset_mock()
        mocked_start.reset_mock()
        # test RPC call with wait and not done
        mocked_start.return_value = False
        deferred = self.rpc.start_process(2, 'appli:*', wait=True)
        # result is a function for deferred result
        self.assertTrue(callable(deferred))
        self.assertEqual([call()], mocked_check.call_args_list)
        self.assertEqual([call(StartingStrategies.MOST_LOADED, proc_1, ''),
                          call(StartingStrategies.MOST_LOADED, proc_2, '')],
                         mocked_start.call_args_list)
        self.assertFalse(mocked_progress.called)
        # test returned function: return True when job in progress
        mocked_progress.return_value = True
        self.assertEqual(NOT_DONE_YET, deferred())
        self.assertEqual([call()], mocked_progress.call_args_list)
        mocked_progress.reset_mock()
        # test returned function: raise exception if job not in progress anymore
        # and process still stopped
        mocked_progress.return_value = False
        with self.assertRaises(RPCError) as exc:
            deferred()
        self.assertEqual(Faults.ABNORMAL_TERMINATION, exc.exception.code)
        self.assertEqual('ABNORMAL_TERMINATION: proc1', exc.exception.text)
        self.assertEqual([call()], mocked_progress.call_args_list)
        mocked_progress.reset_mock()
        # test returned function: return True if job not in progress anymore
        # and process running
        proc_1.stopped.return_value = False
        self.assertTrue(deferred())
        self.assertEqual([call()], mocked_progress.call_args_list)

    @patch('supvisors.rpcinterface.RPCInterface._check_operating_conciliation')
    def test_stop_process(self, mocked_check):
        """ Test the stop_process self.rpc. """
        # get patches
        mocked_stop = self.supvisors.stopper.stop_process
        mocked_progress = self.supvisors.stopper.in_progress
        # patch the instance
        self.rpc._get_application_process = Mock()
        # test RPC call with running process
        self.rpc._get_application_process.return_value = (None, Mock(**{'stopped.return_value': True,
                                                                        'namespec.return_value': 'proc1'}))
        with self.assertRaises(RPCError) as exc:
            self.rpc.stop_process('appli_1')
        self.assertEqual(Faults.NOT_RUNNING, exc.exception.code)
        self.assertEqual('NOT_RUNNING: proc1', exc.exception.text)
        self.assertEqual([call()], mocked_check.call_args_list)
        self.assertEqual(0, mocked_stop.call_count)
        self.assertEqual(0, mocked_progress.call_count)
        mocked_check.reset_mock()
        # test RPC call with running processes
        self.rpc._get_application_process.return_value = (Mock(**{'processes.values.return_value': [
            Mock(**{'stopped.return_value': False}),
            Mock(**{'stopped.return_value': True, 'namespec.return_value': 'proc2'})]}), None)
        with self.assertRaises(RPCError) as exc:
            self.rpc.stop_process('appli_1')
        self.assertEqual(Faults.NOT_RUNNING, exc.exception.code)
        self.assertEqual('NOT_RUNNING: proc2', exc.exception.text)
        self.assertEqual([call()], mocked_check.call_args_list)
        self.assertEqual(0, mocked_stop.call_count)
        self.assertEqual(0, mocked_progress.call_count)
        mocked_check.reset_mock()
        # test RPC call with stopped processes
        proc_1 = Mock(**{'running.return_value': True,
                         'stopped.return_value': False,
                         'namespec.return_value': 'proc1'})
        proc_2 = Mock(**{'running.return_value': False,
                         'stopped.return_value': False,
                         'namespec.return_value': 'proc2'})
        self.rpc._get_application_process.return_value = (
            Mock(**{'processes.values.return_value': [proc_1, proc_2]}), None)
        # test RPC call with no wait and not done
        mocked_stop.return_value = False
        result = self.rpc.stop_process('appli:*', False)
        self.assertTrue(result)
        self.assertEqual([call()], mocked_check.call_args_list)
        self.assertEqual([call(proc_1), call(proc_2)], mocked_stop.call_args_list)
        self.assertEqual(0, mocked_progress.call_count)
        mocked_check.reset_mock()
        mocked_stop.reset_mock()
        # test RPC call no wait and done
        mocked_stop.return_value = True
        result = self.rpc.stop_process('appli:*', False)
        self.assertTrue(result)
        self.assertEqual([call()], mocked_check.call_args_list)
        self.assertEqual([call(proc_1), call(proc_2)], mocked_stop.call_args_list)
        self.assertEqual(0, mocked_progress.call_count)
        mocked_check.reset_mock()
        mocked_stop.reset_mock()
        # test RPC call with wait and done
        result = self.rpc.stop_process('appli:*', wait=True)
        self.assertTrue(result)
        self.assertEqual([call(proc_1), call(proc_2)], mocked_stop.call_args_list)
        self.assertEqual(0, mocked_progress.call_count)
        mocked_check.reset_mock()
        mocked_stop.reset_mock()
        # test RPC call with wait and not done
        mocked_stop.return_value = False
        deferred = self.rpc.stop_process('appli:*', wait=True)
        # result is a function for deferred result
        self.assertTrue(callable(deferred))
        self.assertEqual([call()], mocked_check.call_args_list)
        self.assertEqual([call(proc_1), call(proc_2)], mocked_stop.call_args_list)
        self.assertEqual(0, mocked_progress.call_count)
        # test returned function: return True when job in progress
        mocked_progress.return_value = True
        self.assertEqual(NOT_DONE_YET, deferred())
        self.assertEqual([call()], mocked_progress.call_args_list)
        mocked_progress.reset_mock()
        # test returned function: raise exception if job not in progress anymore and process still running
        mocked_progress.return_value = False
        with self.assertRaises(RPCError) as exc:
            deferred()
        self.assertEqual(Faults.ABNORMAL_TERMINATION, exc.exception.code)
        self.assertEqual('ABNORMAL_TERMINATION: proc1', exc.exception.text)
        self.assertEqual([call()], mocked_progress.call_args_list)
        mocked_progress.reset_mock()
        # test returned function: return True if job not in progress anymore and process stopped
        proc_1.running.return_value = False
        self.assertTrue(deferred())
        self.assertEqual([call()], mocked_progress.call_args_list)

    @patch('supvisors.rpcinterface.RPCInterface.start_process')
    @patch('supvisors.rpcinterface.RPCInterface.stop_process')
    @patch('supvisors.rpcinterface.RPCInterface._check_operating')
    def test_restart_process(self, mocked_check, mocked_stop, mocked_start):
        """ Test the restart_process self.rpc. """
        from supvisors.ttypes import StartingStrategies
        # test RPC call with sub-RPC calls return a direct result
        mocked_stop.return_value = True
        mocked_start.return_value = False
        deferred = self.rpc.restart_process(0, 'appli:*', 'arg list', 'wait')
        self.assertEqual([call()], mocked_check.call_args_list)
        self.assertEqual([call('appli:*', True)], mocked_stop.call_args_list)
        self.assertEqual(0, mocked_start.call_count)
        mocked_stop.reset_mock()
        mocked_check.reset_mock()
        # result is a function
        self.assertTrue(callable(deferred))
        self.assertTrue(deferred.waitstop)
        # test this function
        self.assertFalse(deferred())
        self.assertFalse(deferred.waitstop)
        self.assertEqual(0, mocked_stop.call_count)
        self.assertEqual([call(0, 'appli:*', 'arg list', 'wait')], mocked_start.call_args_list)
        mocked_start.reset_mock()
        # test RPC call with sub_RPC calls returning jobs
        # test with mocking functions telling that the jobs are not completed
        mocked_stop_job = Mock(return_value=False)
        mocked_start_job = Mock(return_value=False)
        mocked_stop.return_value = mocked_stop_job
        mocked_start.return_value = mocked_start_job
        deferred = self.rpc.restart_process(0, 'appli:*', '', 'wait')
        self.assertEqual([call()], mocked_check.call_args_list)
        self.assertEqual([call('appli:*', True)], mocked_stop.call_args_list)
        self.assertEqual(0, mocked_start.call_count)
        mocked_stop.reset_mock()
        # result is a function for deferred result
        self.assertTrue(callable(deferred))
        self.assertTrue(deferred.waitstop)
        # test this function
        self.assertEqual(0, mocked_stop_job.call_count)
        self.assertEqual(0, mocked_start_job.call_count)
        self.assertEqual(NOT_DONE_YET, deferred())
        self.assertEqual(0, mocked_stop.call_count)
        self.assertEqual(0, mocked_start.call_count)
        self.assertEqual([call()], mocked_stop_job.call_args_list)
        self.assertEqual(0, mocked_start_job.call_count)
        mocked_stop_job.reset_mock()
        # replace the stop job with a function telling that the job is completed
        mocked_stop_job.return_value = True
        self.assertEqual(NOT_DONE_YET, deferred())
        self.assertFalse(deferred.waitstop)
        self.assertEqual(0, mocked_stop.call_count)
        self.assertEqual([call(0, 'appli:*', '', 'wait')], mocked_start.call_args_list)
        self.assertEqual([call()], mocked_stop_job.call_args_list)
        self.assertEqual(0, mocked_start_job.call_count)
        mocked_stop_job.reset_mock()
        # call the deferred function again to check that the start is engaged
        self.assertFalse(deferred())
        self.assertEqual([call()], mocked_start_job.call_args_list)
        self.assertEqual(0, mocked_stop_job.call_count)

    @patch('supvisors.rpcinterface.RPCInterface._check_from_deployment')
    def test_restart(self, mocked_check):
        """ Test the restart self.rpc. """
        # test RPC call
        self.assertTrue(self.rpc.restart())
        self.assertEqual([call()], mocked_check.call_args_list)
        self.assertEqual([call()], self.supvisors.fsm.on_restart.call_args_list)

    @patch('supvisors.rpcinterface.RPCInterface._check_conciliation')
    def test_conciliate(self, mocked_check):
        """ Test the conciliate self.rpc. """
        from supvisors.ttypes import ConciliationStrategies, SupvisorsStates
        # set context and patches
        self.supvisors.fsm.state = SupvisorsStates.CONCILIATION
        self.supvisors.context.conflicts.return_value = [1, 2, 4]
        with patch('supvisors.rpcinterface.conciliate_conflicts') as mocked_conciliate:
            # test RPC call with wrong strategy
            with self.assertRaises(RPCError) as exc:
                self.assertTrue(self.rpc.conciliate('a strategy'))
            self.assertEqual([call()], mocked_check.call_args_list)
            self.assertEqual(Faults.BAD_STRATEGY, exc.exception.code)
            self.assertEqual('BAD_STRATEGY: a strategy', exc.exception.text)
            mocked_check.reset_mock()
            # test RPC call with USER strategy
            self.assertFalse(self.rpc.conciliate(ConciliationStrategies.USER))
            self.assertEqual([call()], mocked_check.call_args_list)
            self.assertEqual(0, mocked_conciliate.call_count)
            mocked_check.reset_mock()
            # test RPC call with another strategy
            self.assertTrue(self.rpc.conciliate(1))
            self.assertEqual([call()], mocked_check.call_args_list)
            self.assertEqual([call(self.supvisors, ConciliationStrategies.INFANTICIDE, [1, 2, 4])],
                             mocked_conciliate.call_args_list)

    @patch('supvisors.rpcinterface.RPCInterface._check_from_deployment')
    def test_shutdown(self, mocked_check):
        """ Test the shutdown self.rpc. """
        # test RPC call
        self.assertTrue(self.rpc.shutdown())
        self.assertEqual([call()], mocked_check.call_args_list)
        self.assertEqual([call()], self.supvisors.fsm.on_shutdown.call_args_list)

    def test_check_state(self):
        """ Test the _check_state utility. """
        from supvisors.ttypes import SupvisorsStates
        # prepare context
        self.supvisors.fsm.state = SupvisorsStates.DEPLOYMENT
        # test there is no exception when internal state is in list
        self.rpc._check_state([SupvisorsStates.INITIALIZATION, SupvisorsStates.DEPLOYMENT, SupvisorsStates.OPERATION])
        # test there is an exception when internal state is not in list
        with self.assertRaises(RPCError) as exc:
            self.rpc._check_state([SupvisorsStates.INITIALIZATION, SupvisorsStates.OPERATION])
        self.assertEqual(Faults.BAD_SUPVISORS_STATE, exc.exception.code)
        self.assertEqual("BAD_SUPVISORS_STATE: Supvisors (state=DEPLOYMENT) "
                         "not in state ['INITIALIZATION', 'OPERATION'] to perform request",
                         exc.exception.text)

    def test_check_from_deployment(self):
        """ Test the _check_from_deployment utility. """
        from supvisors.ttypes import SupvisorsStates
        # test the call to _check_state
        with patch.object(self.rpc, '_check_state') as mocked_check:
            self.rpc._check_from_deployment()
            expected = [x for x in SupvisorsStates if 0 < x.value < 6]
            self.assertListEqual([call(expected)], mocked_check.call_args_list)

    def test_check_operating_conciliation(self):
        """ Test the _check_operating_conciliation utility. """
        from supvisors.ttypes import SupvisorsStates
        # test the call to _check_state
        with patch.object(self.rpc, '_check_state') as mocked_check:
            self.rpc._check_operating_conciliation()
            self.assertListEqual([call([SupvisorsStates.OPERATION, SupvisorsStates.CONCILIATION])],
                                 mocked_check.call_args_list)

    def test_check_operating(self):
        """ Test the _check_operating utility. """
        from supvisors.ttypes import SupvisorsStates
        # test the call to _check_state
        with patch.object(self.rpc, '_check_state') as mocked_check:
            self.rpc._check_operating()
            self.assertListEqual([call([SupvisorsStates.OPERATION])], mocked_check.call_args_list)

    def test_check_conciliation(self):
        """ Test the _check_conciliation utility. """
        from supvisors.ttypes import SupvisorsStates
        # test the call to _check_state
        with patch.object(self.rpc, '_check_state') as mocked_check:
            self.rpc._check_conciliation()
            self.assertListEqual([call([SupvisorsStates.CONCILIATION])], mocked_check.call_args_list)

    def test_get_application(self):
        """ Test the _get_application utility. """
        # prepare context
        self.supvisors.context.applications = {'appli_1': 'first application'}
        # test with known application
        self.assertEqual('first application', self.rpc._get_application('appli_1'))
        # test with unknown application
        with self.assertRaises(RPCError) as exc:
            self.rpc._get_application('app')
        self.assertEqual(Faults.BAD_NAME, exc.exception.code)
        self.assertEqual('BAD_NAME: application app unknown to Supvisors', exc.exception.text)

    def test_get_process(self):
        """ Test the _get_process utility. """
        # prepare context
        self.supvisors.context.processes = {'proc_1': 'first process'}
        # test with known application
        self.assertEqual('first process', self.rpc._get_process('proc_1'))
        # test with unknown application
        with self.assertRaises(RPCError) as exc:
            self.rpc._get_process('proc')
        self.assertEqual(Faults.BAD_NAME, exc.exception.code)
        self.assertEqual('BAD_NAME: process proc unknown to Supvisors', exc.exception.text)

    def test_get_application_process(self):
        """ Test the _get_application_process utility. """
        # prepare context
        self.supvisors.context.applications = {'appli_1': 'first application'}
        self.supvisors.context.processes = {'appli_1:proc_1': 'first process'}
        # test with full namespec
        self.assertTupleEqual(('first application', 'first process'),
                              self.rpc._get_application_process('appli_1:proc_1'))
        # test with applicative namespec
        self.assertTupleEqual(('first application', None),
                              self.rpc._get_application_process('appli_1:*'))

    def test_get_internal_process_rules(self):
        """ Test the _get_application_process utility. """
        # prepare context
        process = Mock(application_name='appli', process_name='proc',
                       **{'rules.serial.return_value': {'start': 0, 'stop': 1}})
        # test call
        self.assertDictEqual({'application_name': 'appli',
                              'process_name': 'proc',
                              'start': 0,
                              'stop': 1},
                             self.rpc._get_internal_process_rules(process))

    def test_get_local_info(self):
        """ Test the _get_local_info utility. """
        # prepare context
        info = {'group': 'dummy_group',
                'name': 'dummy_name',
                'key': 'value',
                'state': 'undefined',
                'start': 1234,
                'stop': 7777,
                'now': 4321,
                'pid': 4567,
                'description': 'process dead',
                'spawnerr': ''}
        info_source = self.supvisors.info_source
        info_source.get_extra_args.return_value = '-x dummy_args'
        # test call
        self.assertDictEqual({'group': 'dummy_group',
                              'name': 'dummy_name',
                              'extra_args': '-x dummy_args',
                              'state': 'undefined',
                              'start': 1234,
                              'stop': 7777,
                              'now': 4321,
                              'pid': 4567,
                              'description': 'process dead',
                              'expected': True,
                              'spawnerr': ''},
                             self.rpc._get_local_info(info))


def test_suite():
    return unittest.findTestCases(sys.modules[__name__])


if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
