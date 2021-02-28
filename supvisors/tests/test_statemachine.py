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
import time
import unittest

from unittest.mock import call, patch, Mock

from supvisors.tests.base import MockedSupvisors, database_copy


class StateMachinesTest(unittest.TestCase):
    """ Test case for the state classes of the statemachine module. """

    def setUp(self):
        """ Create a Supvisors-like structure. """
        from supvisors.address import AddressStatus
        from supvisors.ttypes import AddressStates
        self.supvisors = MockedSupvisors()
        # assign addresses in context
        addresses = self.supvisors.context.addresses
        for address_name in self.supvisors.address_mapper.addresses:
            addresses[address_name] = AddressStatus(address_name, self.supvisors.logger)
        addresses['127.0.0.1']._state = AddressStates.RUNNING
        addresses['10.0.0.1']._state = AddressStates.SILENT
        addresses['10.0.0.2']._state = AddressStates.RUNNING
        addresses['10.0.0.3']._state = AddressStates.ISOLATING
        addresses['10.0.0.4']._state = AddressStates.RUNNING
        addresses['10.0.0.5']._state = AddressStates.ISOLATED

    def test_abstract_state(self):
        """ Test the Abstract state of the self.fsm. """
        from supvisors.statemachine import AbstractState
        state = AbstractState(self.supvisors)
        # check attributes at creation
        self.assertIs(self.supvisors, state.supvisors)
        self.assertEqual('127.0.0.1', state.address_name)
        # call empty methods
        state.enter()
        state.next()
        state.exit()
        # test apply_addresses_func method
        mock_function = Mock()
        mock_function.__name__ = 'dummy_name'
        state.apply_addresses_func(mock_function)
        self.assertListEqual([call('10.0.0.2'), call('10.0.0.4'), call('127.0.0.1')],
                             mock_function.call_args_list)

    def test_initialization_state(self):
        """ Test the Initialization state of the fsm. """
        from supvisors.statemachine import AbstractState, InitializationState
        from supvisors.ttypes import AddressStates, SupvisorsStates
        state = InitializationState(self.supvisors)
        self.assertIsInstance(state, AbstractState)
        # 1. test enter method: master and start_date are reset
        # test that all addresses that are not in an isolation state are reset to UNKNOWN
        state.enter()
        self.assertEqual('', state.context.master_address)
        self.assertGreaterEqual(int(time.time()), state.start_date)
        self.assertEqual(AddressStates.UNKNOWN, self.supvisors.context.addresses['127.0.0.1'].state)
        self.assertEqual(AddressStates.UNKNOWN, self.supvisors.context.addresses['10.0.0.1'].state)
        self.assertEqual(AddressStates.UNKNOWN, self.supvisors.context.addresses['10.0.0.2'].state)
        self.assertEqual(AddressStates.ISOLATING, self.supvisors.context.addresses['10.0.0.3'].state)
        self.assertEqual(AddressStates.UNKNOWN, self.supvisors.context.addresses['10.0.0.4'].state)
        self.assertEqual(AddressStates.ISOLATED, self.supvisors.context.addresses['10.0.0.5'].state)
        # 2. test next method
        # test that Supvisors wait for all addresses to be running or a given timeout is reached
        self.supvisors.context.forced_addresses = []
        self.supvisors.context.running_addresses.return_value = []
        # test case no address is running, especially local address
        result = state.next()
        self.assertEqual(SupvisorsStates.INITIALIZATION, result)
        # test case where addresses are still unknown and timeout is not reached
        self.supvisors.context.running_addresses.return_value = ['127.0.0.1', '10.0.0.2']
        self.supvisors.context.unknown_addresses.return_value = ['10.0.0.1', '10.0.0.3']
        self.supvisors.context.unknown_forced_addresses.return_value = []
        result = state.next()
        self.assertEqual(SupvisorsStates.INITIALIZATION, result)
        # test case where no addresses are still unknown
        self.supvisors.context.running_addresses.return_value = ['127.0.0.1', '10.0.0.2']
        self.supvisors.context.unknown_addresses.return_value = []
        self.supvisors.context.unknown_forced_addresses.return_value = []
        result = state.next()
        self.assertEqual(SupvisorsStates.DEPLOYMENT, result)
        # test case where end of synchro is forced based on a subset of addresses
        self.supvisors.context.forced_addresses = ['10.0.0.2', '10.0.0.4']
        self.supvisors.context.running_addresses.return_value = ['127.0.0.1', '10.0.0.2']
        self.supvisors.context.unknown_addresses.return_value = ['10.0.0.1', '10.0.0.3']
        self.supvisors.context.unknown_forced_addresses.return_value = []
        result = state.next()
        self.assertEqual(SupvisorsStates.DEPLOYMENT, result)
        # test case where addresses are still unknown and timeout is reached
        self.supvisors.context.forced_addresses = []
        state.start_date = time.time() - 11
        result = state.next()
        self.assertEqual(SupvisorsStates.DEPLOYMENT, result)
        self.supvisors.context.unknown_addresses.return_value = []
        result = state.next()
        self.assertEqual(SupvisorsStates.DEPLOYMENT, result)
        # 3. test exit method
        # test that context end_synchro is called and master is the lowest string among address names
        self.supvisors.context.running_addresses.return_value = ['127.0.0.1', '10.0.0.2', '10.0.0.4']
        self.supvisors.context.end_synchro.return_value = ['127.0.0.1', '10.0.0.2', '10.0.0.4']
        mocked_synchro = self.supvisors.context.end_synchro
        state.exit()
        self.assertEqual(1, mocked_synchro.call_count)
        self.assertEqual('10.0.0.2', self.supvisors.context.master_address)

    def test_deployment_state(self):
        """ Test the Deployment state of the fsm. """
        from supvisors.application import ApplicationStatus
        from supvisors.process import ProcessStatus
        from supvisors.statemachine import AbstractState, DeploymentState
        from supvisors.ttypes import ApplicationStates, SupvisorsStates
        state = DeploymentState(self.supvisors)
        self.assertIsInstance(state, AbstractState)
        # test enter method
        # test that start_applications is  called only when local address is the master address
        with patch.object(self.supvisors.starter, 'start_applications') as mocked_starter:
            self.supvisors.context.master = False
            state.enter()
            self.assertEqual(0, mocked_starter.call_count)
            # now master address is local
            self.supvisors.context.master = True
            state.enter()
            self.assertEqual(1, mocked_starter.call_count)
        # create application context
        application = ApplicationStatus('sample_test_2', self.supvisors.logger)
        self.supvisors.context.applications['sample_test_2'] = application
        for info in database_copy():
            if info['group'] == 'sample_test_2':
                process = ProcessStatus(info['group'], info['name'], self.supvisors)
                process.rules.start_sequence = len(process.namespec()) % 3
                process.rules.stop_sequence = len(process.namespec()) % 3 + 1
                process.add_info('10.0.0.1', info)
                application.add_process(process)
        # test application updates
        self.supvisors.context.master = False
        self.assertEqual(ApplicationStates.STOPPED, application.state)
        self.assertFalse(application.minor_failure)
        self.assertFalse(application.major_failure)
        self.assertDictEqual({}, application.start_sequence)
        self.assertDictEqual({}, application.stop_sequence)
        state.enter()
        application = self.supvisors.context.applications['sample_test_2']
        self.assertEqual(ApplicationStates.RUNNING, application.state)
        self.assertTrue(application.minor_failure)
        self.assertFalse(application.major_failure)
        # list order may differ, so break down
        self.assertListEqual(sorted(application.start_sequence.keys()), [0, 1])
        self.assertEqual(len(application.start_sequence[0]), 2)
        self.assertTrue(all(item in [application.processes['yeux_01'], application.processes['yeux_00']]
                            for item in application.start_sequence[0]))
        self.assertListEqual([application.processes['sleep']],
                             application.start_sequence[1])
        self.assertListEqual(sorted(application.stop_sequence.keys()), [1, 2])
        self.assertEqual(len(application.stop_sequence[1]), 2)
        self.assertTrue(all(item in [application.processes['yeux_01'], application.processes['yeux_00']]
                            for item in application.stop_sequence[1]))
        self.assertListEqual([application.processes['sleep']],
                             application.stop_sequence[2])
        # test next method
        # stay in DEPLOYMENT if local is master and a starting is in progress, whatever the conflict status
        with patch.object(self.supvisors.starter, 'check_starting', return_value=False):
            for conflict in [True, False]:
                with patch.object(self.supvisors.context, 'conflicting', return_value=conflict):
                    self.supvisors.context.master = True
                    result = state.next()
                    self.assertEqual(SupvisorsStates.DEPLOYMENT, result)
        # return OPERATION if local is not master and no conflict, whatever the starting status
        self.supvisors.context.master = False
        with patch.object(self.supvisors.context, 'conflicting', return_value=False):
            for starting in [True, False]:
                with patch.object(self.supvisors.starter, 'check_starting', return_value=starting):
                    result = state.next()
                    self.assertEqual(SupvisorsStates.OPERATION, result)
        # return OPERATION if a starting is in progress and no conflict, whatever the master status
        with patch.object(self.supvisors.starter, 'check_starting', return_value=True):
            with patch.object(self.supvisors.context, 'conflicting', return_value=False):
                for master in [True, False]:
                    self.supvisors.context.master = master
                    result = state.next()
                    self.assertEqual(SupvisorsStates.OPERATION, result)
        # return CONCILIATION if local is not master and conflict detected, whatever the starting status
        self.supvisors.context.master = False
        with patch.object(self.supvisors.context, 'conflicting', return_value=True):
            for starting in [True, False]:
                with patch.object(self.supvisors.starter, 'check_starting', return_value=starting):
                    result = state.next()
                    self.assertEqual(SupvisorsStates.CONCILIATION, result)
        # return CONCILIATION if a starting is in progress and conflict detected, whatever the master status
        with patch.object(self.supvisors.starter, 'check_starting', return_value=True):
            with patch.object(self.supvisors.context, 'conflicting', return_value=True):
                for master in [True, False]:
                    self.supvisors.context.master = master
                    result = state.next()
                    self.assertEqual(SupvisorsStates.CONCILIATION, result)
        # no exit implementation. just call it without test
        state.exit()

    def test_operation_state(self):
        """ Test the Operation state of the fsm. """
        from supvisors.address import AddressStatus
        from supvisors.statemachine import AbstractState, OperationState
        from supvisors.ttypes import AddressStates, SupvisorsStates
        state = OperationState(self.supvisors)
        self.assertIsInstance(state, AbstractState)
        # no enter implementation. just call it without test
        state.enter()
        # test next method
        # do not leave OPERATION state if a starting or a stopping is in progress
        with patch.object(self.supvisors.starter, 'check_starting', return_value=False):
            result = state.next()
            self.assertEqual(SupvisorsStates.OPERATION, result)
        with patch.object(self.supvisors.stopper, 'check_stopping', return_value=False):
            result = state.next()
            self.assertEqual(SupvisorsStates.OPERATION, result)
        # create address context
        for address_name in self.supvisors.address_mapper.addresses:
            address = AddressStatus(address_name, self.supvisors.logger)
            self.supvisors.context.addresses[address_name] = address
        # declare local and master address running
        self.supvisors.context.master_address = '10.0.0.3'
        self.supvisors.context.addresses['127.0.0.1']._state = AddressStates.RUNNING
        self.supvisors.context.addresses['10.0.0.3']._state = AddressStates.RUNNING
        # consider that no starting or stopping is in progress
        with patch.object(self.supvisors.starter, 'check_starting', return_value=True):
            with patch.object(self.supvisors.stopper, 'check_stopping', return_value=True):
                # stay in OPERATION if local address and master address are RUNNING and no conflict
                with patch.object(self.supvisors.context, 'conflicting', return_value=False):
                    result = state.next()
                    self.assertEqual(SupvisorsStates.OPERATION, result)
                # transit to CONCILIATION if local address and master address are RUNNING and conflict detected
                with patch.object(self.supvisors.context, 'conflicting', return_value=True):
                    result = state.next()
                    self.assertEqual(SupvisorsStates.CONCILIATION, result)
                # transit to INITIALIZATION state if the local address or master address is not RUNNING
                self.supvisors.context.addresses['127.0.0.1']._state = AddressStates.SILENT
                result = state.next()
                self.assertEqual(SupvisorsStates.INITIALIZATION, result)
                self.supvisors.context.addresses['127.0.0.1']._state = AddressStates.RUNNING
                self.supvisors.context.addresses['10.0.0.3']._state = AddressStates.SILENT
                result = state.next()
                self.assertEqual(SupvisorsStates.INITIALIZATION, result)
        # no exit implementation. just call it without test
        state.exit()

    def test_conciliation_state(self):
        """ Test the Conciliation state of the fsm. """
        from supvisors.address import AddressStatus
        from supvisors.statemachine import AbstractState, ConciliationState
        from supvisors.ttypes import AddressStates, SupvisorsStates
        state = ConciliationState(self.supvisors)
        self.assertIsInstance(state, AbstractState)
        # test enter method
        with patch.object(self.supvisors.context, 'conflicts', return_value=[1, 2, 3]):
            with patch('supvisors.statemachine.conciliate_conflicts') as mocked_conciliate:
                # nothing done if local is not master
                self.supvisors.context.master = False
                state.enter()
                self.assertEqual(0, mocked_conciliate.call_count)
                # conciliation called if local is master
                self.supvisors.context.master = True
                state.enter()
                self.assertEqual(1, mocked_conciliate.call_count)
                self.assertEqual(call(self.supvisors, 0, [1, 2, 3]),
                                 mocked_conciliate.call_args)
        # test next method (quite similar to OPERATION state)
        # do not leave CONCILIATION state if a starting or a stopping is in progress
        with patch.object(self.supvisors.starter, 'check_starting', return_value=False):
            result = state.next()
            self.assertEqual(SupvisorsStates.CONCILIATION, result)
        with patch.object(self.supvisors.stopper, 'check_stopping', return_value=False):
            result = state.next()
            self.assertEqual(SupvisorsStates.CONCILIATION, result)
        # create address context
        addresses = self.supvisors.context.addresses
        for address_name in self.supvisors.address_mapper.addresses:
            address = AddressStatus(address_name, self.supvisors.logger)
            addresses[address_name] = address
        # declare local and master address running
        self.supvisors.context.master_address = '10.0.0.3'
        addresses['127.0.0.1']._state = AddressStates.RUNNING
        addresses['10.0.0.3']._state = AddressStates.RUNNING
        # consider that no starting or stopping is in progress
        with patch.object(self.supvisors.starter, 'check_starting', return_value=True):
            with patch.object(self.supvisors.stopper, 'check_stopping', return_value=True):
                # if local address and master address are RUNNING and
                # conflict still detected, re-enter CONCILIATION
                with patch.object(self.supvisors.context, 'conflicting', return_value=True):
                    with patch.object(state, 'enter') as mocked_enter:
                        result = state.next()
                        self.assertEqual(1, mocked_enter.call_count)
                        self.assertEqual(SupvisorsStates.CONCILIATION, result)
                # transit to OPERATION if local address and master address
                # are RUNNING and no conflict detected
                with patch.object(self.supvisors.context, 'conflicting', return_value=False):
                    result = state.next()
                    self.assertEqual(SupvisorsStates.OPERATION, result)
                # transit to INITIALIZATION state if the local address
                # or master address is not RUNNING
                addresses['127.0.0.1']._state = AddressStates.SILENT
                result = state.next()
                self.assertEqual(SupvisorsStates.INITIALIZATION, result)
                addresses['127.0.0.1']._state = AddressStates.RUNNING
                addresses['10.0.0.3']._state = AddressStates.SILENT
                result = state.next()
                self.assertEqual(SupvisorsStates.INITIALIZATION, result)
        # no exit implementation. just call it without test
        state.exit()

    def test_restarting_state(self):
        """ Test the Restarting state of the fsm. """
        from supvisors.statemachine import AbstractState, RestartingState
        from supvisors.ttypes import SupvisorsStates
        state = RestartingState(self.supvisors)
        self.assertIsInstance(state, AbstractState)
        # test enter method: starting ang stopping in progress are aborted
        with patch.object(self.supvisors.starter, 'abort') as mocked_starter:
            with patch.object(self.supvisors.stopper, 'stop_applications') as mocked_stopper:
                state.enter()
                self.assertEqual(1, mocked_starter.call_count)
                self.assertEqual(1, mocked_stopper.call_count)
        # test next method: all processes are stopped
        with patch.object(self.supvisors.stopper, 'check_stopping', return_value=True):
            result = state.next()
            self.assertEqual(SupvisorsStates.SHUTDOWN, result)
        with patch.object(self.supvisors.stopper, 'check_stopping', return_value=False):
            result = state.next()
            self.assertEqual(SupvisorsStates.RESTARTING, result)
        # test exit method: call to pusher send_restart for all addresses
        with patch.object(state, 'apply_addresses_func') as mocked_apply:
            state.exit()
            self.assertEqual(1, mocked_apply.call_count)
            self.assertEqual(call(self.supvisors.zmq.pusher.send_restart), mocked_apply.call_args)

    def test_shutting_down_state(self):
        """ Test the ShuttingDown state of the fsm. """
        from supvisors.statemachine import AbstractState, ShuttingDownState
        from supvisors.ttypes import SupvisorsStates
        state = ShuttingDownState(self.supvisors)
        self.assertIsInstance(state, AbstractState)
        # test enter method: starting ang stopping in progress are aborted
        with patch.object(self.supvisors.starter, 'abort') as mocked_starter:
            with patch.object(self.supvisors.stopper, 'stop_applications') as mocked_stopper:
                state.enter()
                self.assertEqual(1, mocked_starter.call_count)
                self.assertEqual(1, mocked_stopper.call_count)
        # test next method: all processes are stopped
        with patch.object(self.supvisors.stopper, 'check_stopping', return_value=True):
            result = state.next()
            self.assertEqual(SupvisorsStates.SHUTDOWN, result)
        with patch.object(self.supvisors.stopper, 'check_stopping', return_value=False):
            result = state.next()
            self.assertEqual(SupvisorsStates.SHUTTING_DOWN, result)
        # test exit method: call to pusher send_shutdown for all addresses
        with patch.object(state, 'apply_addresses_func') as mocked_apply:
            state.exit()
            self.assertEqual(1, mocked_apply.call_count)
            self.assertEqual(call(self.supvisors.zmq.pusher.send_shutdown), mocked_apply.call_args)

    def test_shutdown_state(self):
        """ Test the ShutDown state of the fsm. """
        from supvisors.statemachine import AbstractState, ShutdownState
        state = ShutdownState(self.supvisors)
        self.assertIsInstance(state, AbstractState)
        # no enter / next / exit implementation. just call it without test
        state.enter()
        state.next()
        state.exit()


class FiniteStateMachineTest(unittest.TestCase):
    """ Test case for the FiniteStateMachine class of the statemachine module. """

    def setUp(self):
        """ Create a Supvisors-like structure. """
        from supvisors.statemachine import FiniteStateMachine
        # create state machine instance to be tested
        self.supvisors = MockedSupvisors()
        self.fsm = FiniteStateMachine(self.supvisors)

    @patch('supvisors.statemachine.FiniteStateMachine.update_instance')
    def test_creation(self, mocked_update):
        """ Test the values set at construction. """
        from supvisors.statemachine import InitializationState
        from supvisors.ttypes import SupvisorsStates
        # test that the INITIALIZATION state is triggered at creation
        mocked_publisher = self.supvisors.zmq.publisher.send_supvisors_status
        self.assertIs(self.supvisors, self.fsm.supvisors)
        self.assertEqual(SupvisorsStates.INITIALIZATION, self.fsm.state)
        self.assertIsInstance(self.fsm.instance, InitializationState)

    def test_state_string(self):
        """ Test the string conversion of state machine. """
        from supvisors.ttypes import SupvisorsStates
        # test string conversion for all states
        for state in SupvisorsStates.values():
            self.fsm.state = state
            self.assertEqual(SupvisorsStates.to_string(state), self.fsm.state_string())

    def test_serial(self):
        """ Test the serialization of state machine. """
        from supvisors.ttypes import SupvisorsStates
        # test serialization for all states
        for state in SupvisorsStates.values():
            self.fsm.state = state
            self.assertDictEqual({'statecode': state, 'statename': SupvisorsStates.to_string(state)}, self.fsm.serial())

    @patch('supvisors.statemachine.DeploymentState.exit')
    @patch('supvisors.statemachine.DeploymentState.next')
    @patch('supvisors.statemachine.DeploymentState.enter')
    @patch('supvisors.statemachine.InitializationState.exit')
    @patch('supvisors.statemachine.InitializationState.next')
    @patch('supvisors.statemachine.InitializationState.enter')
    def test_simple_set_state(self, *args, **kwargs):
        """ Test single transitions of the state machine using set_state method. """
        from supvisors.ttypes import SupvisorsStates

        # function to compare call counts of mocked methods
        def compare_calls(call_counts):
            for call_count, mocked in zip(call_counts, args):
                self.assertEqual(call_count, mocked.call_count)
                mocked.reset_mock()

        # create state machine instance
        instance_ref = self.fsm.instance
        # test set_state with identical state parameter
        self.fsm.set_state(SupvisorsStates.INITIALIZATION)
        compare_calls([0, 0, 0, 0, 0, 0])
        self.assertIs(instance_ref, self.fsm.instance)
        self.assertEqual(SupvisorsStates.INITIALIZATION, self.fsm.state)
        # test set_state with not authorized transition
        self.fsm.set_state(SupvisorsStates.OPERATION)
        compare_calls([0, 0, 0, 0, 0, 0])
        self.assertIs(instance_ref, self.fsm.instance)
        self.assertEqual(SupvisorsStates.INITIALIZATION, self.fsm.state)
        # test set_state with authorized transition
        self.fsm.set_state(SupvisorsStates.DEPLOYMENT)
        compare_calls([0, 0, 1, 1, 1, 0])
        self.assertIsNot(instance_ref, self.fsm.instance)
        self.assertEqual(SupvisorsStates.DEPLOYMENT, self.fsm.state)

    @patch('supvisors.statemachine.OperationState.exit')
    @patch('supvisors.statemachine.OperationState.next')
    @patch('supvisors.statemachine.OperationState.enter')
    @patch('supvisors.statemachine.DeploymentState.exit')
    @patch('supvisors.statemachine.DeploymentState.next', return_value=2)
    @patch('supvisors.statemachine.DeploymentState.enter')
    @patch('supvisors.statemachine.InitializationState.exit')
    @patch('supvisors.statemachine.InitializationState.next')
    @patch('supvisors.statemachine.InitializationState.enter')
    def test_complex_set_state(self, *args, **kwargs):
        """ Test multiple transitions of the state machine using set_state method. """
        from supvisors.ttypes import SupvisorsStates

        # function to compare call counts of mocked methods
        def compare_calls(call_counts):
            for call_count, mocked in zip(call_counts, args):
                self.assertEqual(call_count, mocked.call_count)
                mocked.reset_mock()

        instance_ref = self.fsm.instance
        # test set_state with authorized transition
        self.fsm.set_state(SupvisorsStates.DEPLOYMENT)
        compare_calls([0, 0, 1, 1, 1, 1, 1, 1, 0])
        self.assertIsNot(instance_ref, self.fsm.instance)
        self.assertEqual(SupvisorsStates.OPERATION, self.fsm.state)

    @patch('supvisors.statemachine.InitializationState.exit')
    @patch('supvisors.statemachine.InitializationState.next', return_value=0)
    @patch('supvisors.statemachine.InitializationState.enter')
    def test_no_next(self, *args, **kwargs):
        """ Test no transition of the state machine using next_method. """
        from supvisors.ttypes import SupvisorsStates

        # function to compare call counts of mocked methods
        def compare_calls(call_counts):
            for call_count, mocked in zip(call_counts, args):
                self.assertEqual(call_count, mocked.call_count)
                mocked.reset_mock()

        instance_ref = self.fsm.instance
        # test set_state with authorized transition
        self.fsm.next()
        compare_calls([0, 1, 0])
        self.assertIs(instance_ref, self.fsm.instance)
        self.assertEqual(SupvisorsStates.INITIALIZATION, self.fsm.state)

    @patch('supvisors.statemachine.DeploymentState.exit')
    @patch('supvisors.statemachine.DeploymentState.next', return_value=1)
    @patch('supvisors.statemachine.DeploymentState.enter')
    @patch('supvisors.statemachine.InitializationState.exit')
    @patch('supvisors.statemachine.InitializationState.next', return_value=1)
    @patch('supvisors.statemachine.InitializationState.enter')
    def test_simple_next(self, *args, **kwargs):
        """ Test single transition of the state machine using next_method. """
        from supvisors.ttypes import SupvisorsStates

        # function to compare call counts of mocked methods
        def compare_calls(call_counts):
            for call_count, mocked in zip(call_counts, args):
                self.assertEqual(call_count, mocked.call_count)
                mocked.reset_mock()

        instance_ref = self.fsm.instance
        # test set_state with authorized transition
        self.fsm.next()
        compare_calls([0, 1, 1, 1, 1, 0])
        self.assertIsNot(instance_ref, self.fsm.instance)
        self.assertEqual(SupvisorsStates.DEPLOYMENT, self.fsm.state)

    @patch('supvisors.statemachine.ConciliationState.exit')
    @patch('supvisors.statemachine.ConciliationState.next')
    @patch('supvisors.statemachine.ConciliationState.enter')
    @patch('supvisors.statemachine.DeploymentState.exit')
    @patch('supvisors.statemachine.DeploymentState.next', return_value=3)
    @patch('supvisors.statemachine.DeploymentState.enter')
    @patch('supvisors.statemachine.InitializationState.exit')
    @patch('supvisors.statemachine.InitializationState.next', return_value=1)
    @patch('supvisors.statemachine.InitializationState.enter')
    def test_complex_next(self, *args, **kwargs):
        """ Test multiple transitions of the state machine using next_method. """
        from supvisors.ttypes import SupvisorsStates

        # function to compare call counts of mocked methods
        def compare_calls(call_counts):
            for call_count, mocked in zip(call_counts, args):
                self.assertEqual(call_count, mocked.call_count)
                mocked.reset_mock()

        instance_ref = self.fsm.instance
        # test set_state with authorized transition
        self.fsm.next()
        compare_calls([0, 1, 1, 1, 1, 1, 1, 1, 0])
        self.assertIsNot(instance_ref, self.fsm.instance)
        self.assertEqual(SupvisorsStates.CONCILIATION, self.fsm.state)

    @patch('supvisors.statemachine.ShutdownState.exit')
    @patch('supvisors.statemachine.ShutdownState.next')
    @patch('supvisors.statemachine.ShutdownState.enter')
    @patch('supvisors.statemachine.RestartingState.exit')
    @patch('supvisors.statemachine.RestartingState.next', return_value=6)
    @patch('supvisors.statemachine.RestartingState.enter')
    @patch('supvisors.statemachine.ConciliationState.exit')
    @patch('supvisors.statemachine.ConciliationState.next', side_effect=[2, 2])
    @patch('supvisors.statemachine.ConciliationState.enter')
    @patch('supvisors.statemachine.OperationState.exit')
    @patch('supvisors.statemachine.OperationState.next', side_effect=[3, 0, 4])
    @patch('supvisors.statemachine.OperationState.enter')
    @patch('supvisors.statemachine.DeploymentState.exit')
    @patch('supvisors.statemachine.DeploymentState.next', side_effect=[2, 3])
    @patch('supvisors.statemachine.DeploymentState.enter')
    @patch('supvisors.statemachine.InitializationState.exit')
    @patch('supvisors.statemachine.InitializationState.next', side_effect=[1, 1])
    @patch('supvisors.statemachine.InitializationState.enter')
    def test_very_complex_next(self, *args, **kwargs):
        """ Test multiple transitions of the state machine using next_method. """
        from supvisors.ttypes import SupvisorsStates

        # function to compare call counts of mocked methods
        def compare_calls(call_counts):
            for call_count, mocked in zip(call_counts, args):
                self.assertEqual(call_count, mocked.call_count)
                mocked.reset_mock()

        instance_ref = self.fsm.instance
        # test set_state with authorized transition
        self.fsm.next()
        compare_calls([1, 2, 2, 2, 2, 2, 3, 3, 3, 2, 2, 2, 1, 1, 1, 1, 1, 0])
        self.assertIsNot(instance_ref, self.fsm.instance)
        self.assertEqual(SupvisorsStates.SHUTDOWN, self.fsm.state)

    def test_update_instance(self):
        """ Test the recreation of the state instance, depending on the state. """
        from supvisors.statemachine import (InitializationState, DeploymentState, OperationState,
                                            ConciliationState, RestartingState, ShuttingDownState, ShutdownState)
        from supvisors.ttypes import SupvisorsStates
        # patch context
        mocked_publisher = self.supvisors.zmq.publisher.send_supvisors_status = Mock()
        self.supvisors.context.master = False

        # create function for test comparison
        def compare_state(state, klass):
            self.fsm.update_instance(state)
            # test the type of internal instance
            self.assertIsInstance(self.fsm.instance, klass)
            # test that internal instance is always recreated
            self.assertIsNot(compare_state.instance_ref, self.fsm.instance)
            compare_state.instance_ref = self.fsm.instance
            # test that the state is reassigned
            self.assertEqual(state, self.fsm.state)
            # test that the state machine object is published
            compare_state.cpt = compare_state.cpt + 1
            self.assertEqual(compare_state.cpt, mocked_publisher.call_count)

        # add internal persistent variables to function
        compare_state.instance_ref = self.fsm.instance
        compare_state.cpt = 0
        # test all states
        compare_state(SupvisorsStates.INITIALIZATION, InitializationState)
        compare_state(SupvisorsStates.DEPLOYMENT, DeploymentState)
        compare_state(SupvisorsStates.OPERATION, OperationState)
        compare_state(SupvisorsStates.CONCILIATION, ConciliationState)
        compare_state(SupvisorsStates.RESTARTING, RestartingState)
        compare_state(SupvisorsStates.SHUTTING_DOWN, ShuttingDownState)
        compare_state(SupvisorsStates.SHUTDOWN, ShutdownState)

    def test_timer_event(self):
        """ Test the actions triggered in state machine upon reception of a timer event. """
        # apply patches
        mocked_isolation = self.supvisors.context.handle_isolation
        mocked_isolation.return_value = [2, 3]
        mocked_event = self.supvisors.context.on_timer_event
        mocked_failure = self.supvisors.failure_handler.trigger_jobs
        # test that context on_timer_event is always called
        # test that fsm next is always called
        # test that result of context handle_isolation is always returned
        with patch.object(self.fsm, 'next') as mocked_next:
            result = self.fsm.on_timer_event()
            # check result: marked processes are started
            self.assertEqual([2, 3], result)
            self.assertEqual(1, mocked_next.call_count)
            self.assertEqual(1, mocked_event.call_count)
            self.assertEqual(1, mocked_failure.call_count)
            self.assertEqual(1, mocked_isolation.call_count)

    def test_tick_event(self):
        """ Test the actions triggered in state machine upon reception of a tick event. """
        # inject tick event and test call to context on_tick_event
        with patch.object(self.supvisors.context, 'on_tick_event') as mocked_evt:
            self.fsm.on_tick_event('10.0.0.1', 1234)
            self.assertEqual(1, mocked_evt.call_count)
            self.assertEqual(call('10.0.0.1', 1234), mocked_evt.call_args)

    # FIXME: test calls to failure_handler + master + crashed
    def test_process_event(self):
        """ Test the actions triggered in state machine upon reception of a process event. """
        # prepare context
        process = Mock(application_name='appli')
        # get patches
        mocked_start_evt = self.supvisors.starter.on_event
        mocked_stop_evt = self.supvisors.stopper.on_event
        mocked_ctx = self.supvisors.context.on_process_event
        mocked_start_has = self.supvisors.starter.has_application
        mocked_stop_has = self.supvisors.stopper.has_application
        # inject process event
        mocked_ctx.return_value = None
        mocked_start_has.return_value = False
        mocked_stop_has.return_value = False
        # test that context on_process_event is always called
        # test that starter and stopper are not involved when corresponding process is not found
        self.fsm.on_process_event('10.0.0.1', ['dummy_event'])
        self.assertEqual([call('10.0.0.1', ['dummy_event'])], mocked_ctx.call_args_list)
        self.assertEqual(0, mocked_start_has.call_count)
        self.assertEqual(0, mocked_stop_has.call_count)
        self.assertEqual(0, mocked_start_evt.call_count)
        self.assertEqual(0, mocked_stop_evt.call_count)
        # inject process event
        mocked_ctx.return_value = process
        mocked_ctx.reset_mock()
        # test that context on_process_event is always called
        # test that event is not pushed to starter and stopper
        # when a starting or stopping is not in progress
        self.fsm.on_process_event('10.0.0.1', ['dummy_event'])
        self.assertEqual([call('10.0.0.1', ['dummy_event'])], mocked_ctx.call_args_list)
        self.assertEqual([call('appli')], mocked_start_has.call_args_list)
        self.assertEqual([call('appli')], mocked_stop_has.call_args_list)
        self.assertEqual([call(process)], mocked_start_evt.call_args_list)
        self.assertEqual([call(process)], mocked_stop_evt.call_args_list)
        # inject process event
        mocked_start_has.reset_mock()
        mocked_start_has.return_value = True
        mocked_stop_has.reset_mock()
        mocked_stop_has.return_value = True
        mocked_ctx.reset_mock()
        mocked_start_evt.reset_mock()
        mocked_stop_evt.reset_mock()
        # test that context on_process_event is always called
        # test that event is pushed to starter and stopper
        # when a starting or stopping is in progress
        self.fsm.on_process_event('10.0.0.1', ['dummy_event'])
        self.assertEqual([call('10.0.0.1', ['dummy_event'])], mocked_ctx.call_args_list)
        self.assertEqual([call('appli')], mocked_start_has.call_args_list)
        self.assertEqual([call('appli')], mocked_stop_has.call_args_list)
        self.assertEqual([call(process)], mocked_start_evt.call_args_list)
        self.assertEqual([call(process)], mocked_stop_evt.call_args_list)

    def test_process_info(self):
        """ Test the actions triggered in state machine upon reception of a process information. """
        # inject process info and test call to context load_processes
        with patch.object(self.supvisors.context, 'load_processes') as mocked_load:
            self.fsm.on_process_info('10.0.0.1', {'info': 'dummy_info'})
            self.assertEqual(1, mocked_load.call_count)
            self.assertEqual(call('10.0.0.1', {'info': 'dummy_info'}), mocked_load.call_args)

    def test_on_authorization(self):
        """ Test the actions triggered in state machine upon reception of an authorization event. """
        from supvisors.ttypes import SupvisorsStates
        self.fsm.set_state(SupvisorsStates.OPERATION)
        # prepare context
        self.supvisors.context.master_address = ''
        mocked_auth = self.fsm.context.on_authorization
        mocked_auth.return_value = False
        # test rejected authorization
        self.fsm.on_authorization('10.0.0.1', False, '10.0.0.5')
        self.assertEqual([call('10.0.0.1', False)], mocked_auth.call_args_list)
        self.assertEqual('', self.supvisors.context.master_address)
        # reset mocks
        mocked_auth.reset_mock()
        mocked_auth.return_value = True
        # test authorization when to master address provided
        self.fsm.on_authorization('10.0.0.1', True, '')
        self.assertEqual(call('10.0.0.1', True), mocked_auth.call_args)
        self.assertEqual('', self.supvisors.context.master_address)
        # reset mocks
        mocked_auth.reset_mock()
        # test authorization and master address assignment
        self.fsm.on_authorization('10.0.0.1', True, '10.0.0.5')
        self.assertEqual(call('10.0.0.1', True), mocked_auth.call_args)
        self.assertEqual('10.0.0.5', self.supvisors.context.master_address)
        # reset mocks
        mocked_auth.reset_mock()
        # test authorization and master address assignment
        self.fsm.on_authorization('10.0.0.1', True, '10.0.0.4')
        self.assertEqual(call('10.0.0.1', True), mocked_auth.call_args)
        self.assertEqual('10.0.0.5', self.supvisors.context.master_address)
        self.assertEqual(SupvisorsStates.INITIALIZATION, self.fsm.state)

    def test_restart_event(self):
        """ Test the actions triggered in state machine upon reception
        of a restart event. """
        from supvisors.ttypes import SupvisorsStates
        # inject restart event and test call to fsm set_state RESTARTING
        with patch.object(self.fsm, 'set_state') as mocked_fsm:
            self.fsm.on_restart()
            self.assertEqual(1, mocked_fsm.call_count)
            self.assertEqual(call(SupvisorsStates.RESTARTING), mocked_fsm.call_args)

    def test_shutdown_event(self):
        """ Test the actions triggered in state machine upon reception
        of a shutdown event. """
        from supvisors.ttypes import SupvisorsStates
        # inject shutdown event and test call to fsm set_state SHUTTING_DOWN
        with patch.object(self.fsm, 'set_state') as mocked_fsm:
            self.fsm.on_shutdown()
            self.assertEqual(1, mocked_fsm.call_count)
            self.assertEqual(call(SupvisorsStates.SHUTTING_DOWN), mocked_fsm.call_args)


def test_suite():
    return unittest.findTestCases(sys.modules[__name__])


if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
