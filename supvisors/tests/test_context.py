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

import random
import sys
import time
import unittest

from unittest.mock import call, patch, Mock

from supvisors.tests.base import (DummyAddressMapper,
                                  MockedSupvisors,
                                  database_copy,
                                  any_process_info,
                                  CompatTestCase)


class ContextTest(CompatTestCase):
    """ Test case for the context module. """

    def setUp(self):
        """ Create a logger that stores log traces. """
        self.supvisors = MockedSupvisors()

    def test_creation(self):
        """ Test the values set at construction. """
        from supvisors.address import AddressStatus
        from supvisors.context import Context
        context = Context(self.supvisors)
        self.assertIs(self.supvisors, context.supvisors)
        self.assertIs(self.supvisors.address_mapper, context.address_mapper)
        self.assertIs(self.supvisors.logger, context.logger)
        self.assertItemsEqual(DummyAddressMapper().addresses, context.addresses.keys())
        for address_name, address in context.addresses.items():
            self.assertEqual(address_name, address.address_name)
            self.assertIsInstance(address, AddressStatus)
        self.assertDictEqual({}, context.applications)
        self.assertDictEqual({}, context.processes)
        self.assertEqual('', context._master_address)
        self.assertFalse(context.master)

    def test_master_address(self):
        """ Test the access to master address. """
        from supvisors.context import Context
        context = Context(self.supvisors)
        self.assertEqual('', context.master_address)
        self.assertFalse(context.master)
        context.master_address = '10.0.0.1'
        self.assertEqual('10.0.0.1', context.master_address)
        self.assertEqual('10.0.0.1', context._master_address)
        self.assertFalse(context.master)
        context.master_address = '127.0.0.1'
        self.assertEqual('127.0.0.1', context.master_address)
        self.assertEqual('127.0.0.1', context._master_address)
        self.assertTrue(context.master)

    def test_addresses_by_state(self):
        """ Test the access to addresses in unknown state. """
        from supvisors.context import Context
        from supvisors.ttypes import AddressStates
        context = Context(self.supvisors)
        # test initial states
        self.assertEqual(DummyAddressMapper().addresses, context.unknown_addresses())
        self.assertEqual([], context.unknown_forced_addresses())
        self.assertEqual([], context.running_addresses())
        self.assertEqual([], context.isolating_addresses())
        self.assertEqual([], context.isolation_addresses())
        self.assertEqual([], context.addresses_by_states([AddressStates.RUNNING, AddressStates.ISOLATED]))
        self.assertEqual([], context.addresses_by_states([AddressStates.SILENT]))
        self.assertEqual(DummyAddressMapper().addresses, context.addresses_by_states([AddressStates.UNKNOWN]))
        # change states
        context.addresses['127.0.0.1']._state = AddressStates.RUNNING
        context.addresses['10.0.0.1']._state = AddressStates.SILENT
        context.addresses['10.0.0.2']._state = AddressStates.ISOLATING
        context.addresses['10.0.0.3']._state = AddressStates.ISOLATED
        context.addresses['10.0.0.4']._state = AddressStates.RUNNING
        # test new states
        self.assertEqual(['10.0.0.5'], context.unknown_addresses())
        self.assertEqual([], context.unknown_forced_addresses())
        self.assertEqual(['127.0.0.1', '10.0.0.4'], context.running_addresses())
        self.assertEqual(['10.0.0.2'], context.isolating_addresses())
        self.assertEqual(['10.0.0.2', '10.0.0.3'], context.isolation_addresses())
        self.assertEqual(['127.0.0.1', '10.0.0.3', '10.0.0.4'],
                         context.addresses_by_states([AddressStates.RUNNING, AddressStates.ISOLATED]))
        self.assertEqual(['10.0.0.1'], context.addresses_by_states([AddressStates.SILENT]))
        self.assertEqual(['10.0.0.5'], context.addresses_by_states([AddressStates.UNKNOWN]))

    def test_unknown_forced_addresses(self):
        """ Test the access to addresses in unknown state. """
        from supvisors.context import Context
        from supvisors.ttypes import AddressStates
        self.supvisors.options.force_synchro_if = ['10.0.0.1', '10.0.0.4']
        context = Context(self.supvisors)
        # test initial states
        self.assertEqual(DummyAddressMapper().addresses, context.unknown_addresses())
        self.assertEqual(['10.0.0.1', '10.0.0.4'], context.unknown_forced_addresses())
        # change states
        context.addresses['127.0.0.1']._state = AddressStates.RUNNING
        context.addresses['10.0.0.2']._state = AddressStates.ISOLATING
        context.addresses['10.0.0.3']._state = AddressStates.ISOLATED
        context.addresses['10.0.0.4']._state = AddressStates.RUNNING
        # test new states
        self.assertEqual(['10.0.0.1', '10.0.0.5'], context.unknown_addresses())
        self.assertEqual(['10.0.0.1'], context.unknown_forced_addresses())
        # change states
        context.addresses['10.0.0.1']._state = AddressStates.SILENT
        # test new states
        self.assertEqual(['10.0.0.5'], context.unknown_addresses())
        self.assertEqual([], context.unknown_forced_addresses())

    @staticmethod
    def random_fill_processes( context):
        """ Pushes ProcessInfoDatabase process info in AddressStatus. """
        for info in database_copy():
            process = context.setdefault_process(info)
            address_name = random.choice(list(context.addresses.keys()))
            process.add_info(address_name, info)
            context.addresses[address_name].add_process(process)

    def test_invalid(self):
        """ Test the invalidation of an address. """
        from supvisors.context import Context
        from supvisors.ttypes import AddressStates
        context = Context(self.supvisors)

        def check_address_status(address_name, new_state):
            # get address status
            address_status = context.addresses[address_name]
            # check initial state
            self.assertEqual(AddressStates.UNKNOWN, address_status.state)
            # invalidate address
            proc_1 = Mock(**{'invalidate_address.return_value': None})
            proc_2 = Mock(**{'invalidate_address.return_value': None})
            with patch.object(address_status, 'running_processes',
                              return_value=[proc_1, proc_2]) as mocked_running:
                context.invalid(address_status)
            # check new state
            self.assertEqual(new_state, address_status.state)
            # test calls to process methods
            self.assertEqual([call()], mocked_running.call_args_list)
            self.assertEqual([call(address_name, False)],
                             proc_1.invalidate_address.call_args_list)
            self.assertEqual([call(address_name, False)],
                             proc_2.invalidate_address.call_args_list)
            # restore address state
            address_status._state = AddressStates.UNKNOWN

        # test address state with auto_fence and local_address
        check_address_status('127.0.0.1', AddressStates.SILENT)
        # test address state with auto_fence and other than local_address
        check_address_status('10.0.0.1', AddressStates.ISOLATING)
        # test address state without auto_fence
        with patch.object(self.supvisors.options, 'auto_fence', False):
            # test address state without auto_fence and local_address
            check_address_status('127.0.0.1', AddressStates.SILENT)
            # test address state without auto_fence and other than local_address
            check_address_status('10.0.0.2', AddressStates.SILENT)

    def test_end_synchro(self):
        """ Test the end of synchronization phase. """
        from supvisors.context import Context
        from supvisors.ttypes import AddressStates
        context = Context(self.supvisors)
        # choose two addresses and change their state
        for address_status in context.addresses.values():
            self.assertEqual(AddressStates.UNKNOWN, address_status.state)
        context.addresses['10.0.0.2']._state = AddressStates.RUNNING
        context.addresses['10.0.0.4']._state = AddressStates.ISOLATED
        # call end of synchro with auto_fence activated
        context.end_synchro()
        # check that UNKNOWN addresses became ISOLATING, but local address
        self.assertEqual(AddressStates.SILENT,
                         context.addresses['127.0.0.1'].state)
        self.assertEqual(AddressStates.ISOLATING,
                         context.addresses['10.0.0.1'].state)
        self.assertEqual(AddressStates.ISOLATING,
                         context.addresses['10.0.0.3'].state)
        self.assertEqual(AddressStates.ISOLATING,
                         context.addresses['10.0.0.5'].state)
        # reset states and set (local excepted)
        context.addresses['10.0.0.1']._state = AddressStates.UNKNOWN
        context.addresses['10.0.0.3']._state = AddressStates.UNKNOWN
        context.addresses['10.0.0.5']._state = AddressStates.UNKNOWN
        with patch.object(self.supvisors.options, 'auto_fence', False):
            # call end of synchro with auto_fencing deactivated
            context.end_synchro()
        # check that UNKNOWN addresses became SILENT
        self.assertEqual(AddressStates.SILENT,
                         context.addresses['10.0.0.1'].state)
        self.assertEqual(AddressStates.SILENT,
                         context.addresses['10.0.0.3'].state)
        self.assertEqual(AddressStates.SILENT,
                         context.addresses['10.0.0.5'].state)

    def test_conflicts(self):
        """ Test the detection of conflicting processes. """
        from supvisors.context import Context
        context = Context(self.supvisors)
        # add processes to context
        self.random_fill_processes(context)
        # test no conflict
        self.assertFalse(context.conflicting())
        self.assertListEqual([], context.conflicts())
        # add addresses to one process
        process1 = next(process
                        for process in context.processes.values()
                        if process.running())
        process1.addresses.update(context.addresses.keys())
        # test conflict is detected
        self.assertTrue(context.conflicting())
        self.assertListEqual([process1], context.conflicts())
        # add addresses to one other process
        process2 = next(process
                        for process in context.processes.values()
                        if process.stopped())
        process2.addresses.update(context.addresses.keys())
        # test conflict is detected
        self.assertTrue(context.conflicting())
        self.assertListEqual([process1, process2], context.conflicts())
        # empty addresses of first process list
        process1.addresses.clear()
        # test conflict is still detected
        self.assertTrue(context.conflicting())
        self.assertListEqual([process2], context.conflicts())
        # empty addresses of second process list
        process2.addresses.clear()
        # test no conflict
        self.assertFalse(context.conflicting())
        self.assertListEqual([], context.conflicts())

    def test_setdefault_application(self):
        """ Test the access / creation of an application status. """
        from supvisors.context import Context
        context = Context(self.supvisors)
        # check application list
        self.assertDictEqual({}, context.applications)
        # get application
        application1 = context.setdefault_application('dummy_1')
        # check application list
        self.assertDictEqual({'dummy_1': application1}, context.applications)
        # get application
        application2 = context.setdefault_application('dummy_2')
        # check application list
        self.assertDictEqual({'dummy_1': application1, 'dummy_2': application2},
                             context.applications)
        # get application
        application3 = context.setdefault_application('dummy_1')
        self.assertIs(application1, application3)
        # check application list
        self.assertDictEqual({'dummy_1': application1, 'dummy_2': application2},
                             context.applications)

    def test_setdefault_process(self):
        """ Test the access / creation of a process status. """
        from supvisors.context import Context
        context = Context(self.supvisors)
        # check application list
        self.assertDictEqual({}, context.applications)
        self.assertDictEqual({}, context.processes)
        # get process
        dummy_info1 = {'group': 'dummy_application_1', 'name': 'dummy_process_1'}
        process1 = context.setdefault_process(dummy_info1)
        # check application and process list
        self.assertItemsEqual(['dummy_application_1'], context.applications.keys())
        self.assertDictEqual({'dummy_application_1:dummy_process_1': process1}, context.processes)
        # get application
        dummy_info2 = {'group': 'dummy_application_2', 'name': 'dummy_process_2'}
        process2 = context.setdefault_process(dummy_info2)
        # check application and process list
        self.assertItemsEqual(['dummy_application_1', 'dummy_application_2'], context.applications.keys())
        self.assertDictEqual({'dummy_application_1:dummy_process_1': process1,
                              'dummy_application_2:dummy_process_2': process2},
                             context.processes)
        # get application
        dummy_info3 = {'group': process1.application_name,
                       'name': process1.process_name}
        process3 = context.setdefault_process(dummy_info3)
        self.assertIs(process1, process3)
        # check application and process list
        self.assertItemsEqual(['dummy_application_1', 'dummy_application_2'], context.applications.keys())
        self.assertDictEqual({'dummy_application_1:dummy_process_1': process1,
                              'dummy_application_2:dummy_process_2': process2},
                             context.processes)

    def test_load_processes(self):
        """ Test the storage of processes handled by Supervisor on a given
        address. """
        from supvisors.context import Context
        context = Context(self.supvisors)
        # check application list
        self.assertDictEqual({}, context.applications)
        self.assertDictEqual({}, context.processes)
        for address in context.addresses.values():
            self.assertDictEqual({}, address.processes)
        # load ProcessInfoDatabase in unknown address
        with self.assertRaises(KeyError):
            context.load_processes('10.0.0.0', database_copy())
        # load ProcessInfoDatabase in known address
        context.load_processes('10.0.0.1', database_copy())
        # check context contents
        self.assertItemsEqual(['sample_test_1', 'sample_test_2', 'firefox', 'crash'],
                              context.applications.keys())
        self.assertItemsEqual(['sample_test_1:xclock', 'sample_test_1:xfontsel',
                               'sample_test_1:xlogo', 'sample_test_2:sleep',
                               'sample_test_2:yeux_00', 'sample_test_2:yeux_01',
                               'crash:late_segv', 'crash:segv', 'firefox'],
                              context.processes.keys())
        self.assertDictEqual(context.addresses['10.0.0.1'].processes,
                             context.processes)
        # load ProcessInfoDatabase in other known address
        context.load_processes('10.0.0.2', database_copy())
        # check context contents
        self.assertItemsEqual(['sample_test_1', 'sample_test_2', 'firefox', 'crash'],
                              context.applications.keys())
        self.assertItemsEqual(['sample_test_1:xclock', 'sample_test_1:xfontsel',
                               'sample_test_1:xlogo', 'sample_test_2:sleep',
                               'sample_test_2:yeux_00', 'sample_test_2:yeux_01',
                               'crash:late_segv', 'crash:segv', 'firefox'],
                              context.processes.keys())
        self.assertDictEqual(context.addresses['10.0.0.2'].processes,
                             context.processes)
        # load different database in other known address
        info = any_process_info()
        info.update({'group': 'dummy_application', 'name': 'dummy_process'})
        database = [info]
        context.load_processes('10.0.0.4', database)
        # check context contents
        self.assertItemsEqual(['sample_test_1', 'sample_test_2', 'firefox',
                               'crash', 'dummy_application'],
                              context.applications.keys())
        self.assertItemsEqual(['sample_test_1:xclock', 'sample_test_1:xfontsel',
                               'sample_test_1:xlogo', 'sample_test_2:sleep',
                               'sample_test_2:yeux_00', 'sample_test_2:yeux_01',
                               'crash:late_segv', 'crash:segv', 'firefox',
                               'dummy_application:dummy_process'],
                              context.processes.keys())
        self.assertItemsEqual(['dummy_application:dummy_process'],
                              context.addresses['10.0.0.4'].processes.keys())
        # equality lost between processes in addresses and processes in context
        self.assertNotIn(list(context.processes.keys()),
                         list(context.addresses['10.0.0.1'].processes.keys()))
        self.assertNotIn(list(context.processes.keys()),
                         list(context.addresses['10.0.0.2'].processes.keys()))
        self.assertNotIn(list(context.processes.keys()),
                         list(context.addresses['10.0.0.4'].processes.keys()))
        self.assertDictContainsSubset(context.addresses['10.0.0.1'].processes,
                                      context.processes)
        self.assertDictContainsSubset(context.addresses['10.0.0.1'].processes,
                                      context.processes)
        self.assertDictContainsSubset(context.addresses['10.0.0.2'].processes,
                                      context.processes)
        self.assertDictContainsSubset(context.addresses['10.0.0.4'].processes,
                                      context.processes)

    def test_authorization(self):
        """ Test the handling of an authorization event. """
        from supvisors.context import Context
        from supvisors.ttypes import AddressStates, InvalidTransition
        context = Context(self.supvisors)
        # check no exception with unknown address
        context.on_authorization('10.0.0.0', True)
        # check no change with known address in isolation
        for state in [AddressStates.ISOLATING, AddressStates.ISOLATED]:
            for authorization in [True, False]:
                context.addresses['10.0.0.1']._state = state
                context.on_authorization('10.0.0.1', authorization)
                self.assertEqual(state, context.addresses['10.0.0.1'].state)
        # check exception if authorized and current state not CHECKING
        for state in [AddressStates.UNKNOWN, AddressStates.SILENT]:
            context.addresses['10.0.0.2']._state = state
            with self.assertRaises(InvalidTransition):
                context.on_authorization('10.0.0.2', True)
            self.assertEqual(state, context.addresses['10.0.0.2'].state)
        # check state becomes RUNNING if authorized and current state in CHECKING
        for state in [AddressStates.CHECKING, AddressStates.RUNNING]:
            context.addresses['10.0.0.2']._state = state
            context.on_authorization('10.0.0.2', True)
            self.assertEqual(AddressStates.RUNNING,
                             context.addresses['10.0.0.2'].state)
        # check state becomes ISOLATING if not authorized and auto fencing
        # activated
        for state in [AddressStates.UNKNOWN, AddressStates.CHECKING,
                      AddressStates.RUNNING]:
            context.addresses['10.0.0.4']._state = state
            context.on_authorization('10.0.0.4', False)
            self.assertEqual(AddressStates.ISOLATING,
                             context.addresses['10.0.0.4'].state)
        # check exception if not authorized and auto fencing activated and
        # current is SILENT
        context.addresses['10.0.0.4']._state = AddressStates.SILENT
        with self.assertRaises(InvalidTransition):
            context.on_authorization('10.0.0.4', True)
        self.assertEqual(AddressStates.SILENT,
                         context.addresses['10.0.0.4'].state)
        # check state becomes SILENT if not authorized and auto fencing
        # deactivated
        with patch.object(self.supvisors.options, 'auto_fence', False):
            for state in [AddressStates.UNKNOWN, AddressStates.CHECKING,
                          AddressStates.SILENT, AddressStates.RUNNING]:
                context.addresses['10.0.0.5']._state = state
                context.on_authorization('10.0.0.5', False)
                self.assertEqual(AddressStates.SILENT,
                                 context.addresses['10.0.0.5'].state)

    @patch('supvisors.context.time', return_value=3600)
    def test_tick_event(self, _):
        """ Test the handling of a timer event. """
        from supvisors.context import Context
        from supvisors.ttypes import AddressStates
        context = Context(self.supvisors)
        mocked_check = self.supvisors.zmq.pusher.send_check_address
        mocked_send = self.supvisors.zmq.publisher.send_address_status
        # check no exception with unknown address
        context.on_tick_event('10.0.0.0', {})
        self.assertEqual(0, mocked_check.call_count)
        self.assertEqual(0, mocked_send.call_count)
        # get address status used for tests
        address = context.addresses['10.0.0.1']
        # check no change with known address in isolation
        for state in [AddressStates.ISOLATING, AddressStates.ISOLATED]:
            address._state = state
            context.on_tick_event('10.0.0.1', {})
            self.assertEqual(state, address.state)
            self.assertEqual(0, mocked_check.call_count)
            self.assertEqual(0, mocked_send.call_count)
        # check that address is CHECKING and check_address is called
        # before address time is updated and address status is sent
        for state in [AddressStates.UNKNOWN, AddressStates.SILENT]:
            address._state = state
            context.on_tick_event('10.0.0.1', {'when': 1234})
            self.assertEqual(AddressStates.CHECKING, address.state)
            self.assertEqual(1234, address.remote_time)
            self.assertEqual(call('10.0.0.1'), mocked_check.call_args)
            self.assertEqual(call({'address_name': '10.0.0.1', 'statecode': 1, 'statename': 'CHECKING',
                                   'remote_time': 1234, 'local_time': 3600, 'loading': 0}),
                             mocked_send.call_args)
        # check that address time is updated and address status is sent
        mocked_check.reset_mock()
        mocked_send.reset_mock()
        for state in [AddressStates.CHECKING, AddressStates.RUNNING]:
            address._state = state
            context.on_tick_event('10.0.0.1', {'when': 5678})
            self.assertEqual(state, address.state)
            self.assertEqual(5678, address.remote_time)
            self.assertEqual(0, mocked_check.call_count)
            self.assertEqual(call({'address_name': '10.0.0.1', 'statecode': state,
                                   'statename': AddressStates.to_string(state),
                                   'remote_time': 5678, 'local_time': 3600, 'loading': 0}),
                             mocked_send.call_args)

    @patch('supvisors.process.time', return_value=1234)
    def test_process_event(self, _):
        """ Test the handling of a process event. """
        from supvisors.context import Context
        from supvisors.ttypes import AddressStates, ApplicationStates
        context = Context(self.supvisors)
        mocked_publisher = self.supvisors.zmq.publisher
        # check no exception with unknown address
        result = context.on_process_event('10.0.0.0', {})
        self.assertIsNone(result)
        self.assertEqual(0, mocked_publisher.send_application_status.call_count)
        self.assertEqual(0, mocked_publisher.send_process_status.call_count)
        # get address status used for tests
        address = context.addresses['10.0.0.1']
        # check no change with known address in isolation
        for state in [AddressStates.ISOLATING, AddressStates.ISOLATED]:
            address._state = state
            result = context.on_process_event('10.0.0.1', {})
            self.assertIsNone(result)
            self.assertEqual(0, mocked_publisher.send_application_status.call_count)
            self.assertEqual(0, mocked_publisher.send_process_status.call_count)
        # check no exception with unknown process
        for state in [AddressStates.UNKNOWN, AddressStates.SILENT,
                      AddressStates.CHECKING, AddressStates.RUNNING]:
            address._state = state
            result = context.on_process_event('10.0.0.1', {'groupname': 'dummy_application',
                                                           'processname': 'dummy_process'})
            self.assertIsNone(result)
            self.assertEqual(0, mocked_publisher.send_application_status.call_count)
            self.assertEqual(0, mocked_publisher.send_process_status.call_count)
        # fill context with one process
        dummy_info = {'group': 'dummy_application',
                      'name': 'dummy_process',
                      'expected': True, 'now': 1234, 'state': 0}
        process = context.setdefault_process(dummy_info)
        process.add_info('10.0.0.1', dummy_info)
        application = context.applications['dummy_application']
        self.assertEqual(ApplicationStates.STOPPED, application.state)
        # check normal behaviour with known process
        dummy_event = {'group': 'dummy_application',
                       'name': 'dummy_process',
                       'state': 10,
                       'now': 2345,
                       'extra_args': ''}
        for state in [AddressStates.UNKNOWN, AddressStates.SILENT, AddressStates.CHECKING, AddressStates.RUNNING]:
            address._state = state
            result = context.on_process_event('10.0.0.1', dummy_event)
            self.assertIs(process, result)
            self.assertEqual(10, process.state)
            self.assertEqual(ApplicationStates.STARTING, application.state)
            self.assertEqual(call({'application_name': 'dummy_application',
                                   'statecode': 1, 'statename': 'STARTING',
                                   'major_failure': False, 'minor_failure': False}),
                             mocked_publisher.send_application_status.call_args)
            self.assertEqual(call({'application_name': 'dummy_application', 'process_name': 'dummy_process',
                                   'statecode': 10, 'statename': 'STARTING', 'expected_exit': True,
                                   'last_event_time': 1234, 'addresses': ['10.0.0.1'],
                                   'extra_args': ''}),
                             mocked_publisher.send_process_status.call_args)

    @patch('supvisors.context.time', return_value=3600)
    def test_timer_event(self, mocked_time):
        """ Test the handling of a timer event. """
        from supvisors.context import Context
        from supvisors.ttypes import AddressStates
        context = Context(self.supvisors)
        mocked_send = self.supvisors.zmq.publisher.send_address_status
        # test address states excepting RUNNING: nothing happens
        for _ in [x for x in AddressStates.values() if x != AddressStates.RUNNING]:
            context.on_timer_event()
            for address in context.addresses.values():
                self.assertEqual(AddressStates.UNKNOWN, address.state)
            self.assertEqual(0, mocked_send.call_count)
        # test RUNNING address state with recent local_time
        test_addresses = ['10.0.0.1', '10.0.0.3', '10.0.0.5']
        for address_name in test_addresses:
            address = context.addresses[address_name]
            address._state = AddressStates.RUNNING
            address.local_time = time.time()
        context.on_timer_event()
        for address_name in test_addresses:
            self.assertEqual(AddressStates.RUNNING, context.addresses[address_name].state)
        for address_name in [x for x in context.addresses.keys()
                             if x not in test_addresses]:
            self.assertEqual(AddressStates.UNKNOWN, context.addresses[address_name].state)
        self.assertEqual(0, mocked_send.call_count)
        # test RUNNING address state with one recent local_time and with auto_fence activated
        address1 = context.addresses['10.0.0.3']
        address1.local_time = mocked_time.return_value - 100
        context.on_timer_event()
        self.assertEqual(AddressStates.ISOLATING, address1.state)
        for address_name in [x for x in test_addresses if x != '10.0.0.3']:
            self.assertEqual(AddressStates.RUNNING, context.addresses[address_name].state)
        for address_name in [x for x in context.addresses.keys()
                             if x not in test_addresses]:
            self.assertEqual(AddressStates.UNKNOWN, context.addresses[address_name].state)
        self.assertEqual(call({'address_name': '10.0.0.3', 'statecode': 4, 'statename': 'ISOLATING',
                               'remote_time': 0, 'local_time': address1.local_time, 'loading': 0}),
                         mocked_send.call_args)
        # test with one other recent local_time and with auto_fence deactivated
        self.supvisors.options.auto_fence = False
        mocked_send.reset_mock()
        address2 = context.addresses['10.0.0.5']
        address2.local_time = mocked_time.return_value - 100
        address3 = context.addresses['10.0.0.1']
        address3.local_time = mocked_time.return_value - 100
        context.on_timer_event()
        self.assertEqual(AddressStates.SILENT, address2.state)
        self.assertEqual(AddressStates.SILENT, address3.state)
        self.assertEqual(AddressStates.ISOLATING, address1.state)
        for address_name in [x for x in context.addresses.keys()
                             if x not in test_addresses]:
            self.assertEqual(AddressStates.UNKNOWN, context.addresses[address_name].state)
        send_calls = mocked_send.call_args_list
        payload2 = {'address_name': '10.0.0.5', 'statecode': 3, 'statename': 'SILENT',
                    'remote_time': 0, 'local_time': address2.local_time, 'loading': 0}
        payload3 = {'address_name': '10.0.0.1', 'statecode': 3, 'statename': 'SILENT',
                    'remote_time': 0, 'local_time': address3.local_time, 'loading': 0}
        self.assertTrue([call(payload2), call(payload3)] == send_calls or
                        [call(payload3), call(payload2)] == send_calls)

    def test_handle_isolation(self):
        """ Test the isolation of addresses. """
        from supvisors.context import Context
        from supvisors.ttypes import AddressStates
        context = Context(self.supvisors)
        with patch.object(self.supvisors.zmq.publisher, 'send_address_status') as mocked_send:
            # update address states
            context.addresses['127.0.0.1']._state = AddressStates.CHECKING
            context.addresses['10.0.0.1']._state = AddressStates.RUNNING
            context.addresses['10.0.0.2']._state = AddressStates.SILENT
            context.addresses['10.0.0.3']._state = AddressStates.ISOLATED
            context.addresses['10.0.0.4']._state = AddressStates.ISOLATING
            context.addresses['10.0.0.5']._state = AddressStates.ISOLATING
            # call method and check result
            result = context.handle_isolation()
            self.assertEqual(AddressStates.CHECKING, context.addresses['127.0.0.1'].state)
            self.assertEqual(AddressStates.RUNNING, context.addresses['10.0.0.1'].state)
            self.assertEqual(AddressStates.SILENT, context.addresses['10.0.0.2'].state)
            self.assertEqual(AddressStates.ISOLATED, context.addresses['10.0.0.3'].state)
            self.assertEqual(AddressStates.ISOLATED, context.addresses['10.0.0.4'].state)
            self.assertEqual(AddressStates.ISOLATED, context.addresses['10.0.0.5'].state)
            self.assertListEqual(['10.0.0.4', '10.0.0.5'], result)
            # check calls to publisher.send_address_status
            self.assertListEqual([call({'address_name': '10.0.0.4', 'statecode': 5, 'statename': 'ISOLATED',
                                        'remote_time': 0, 'local_time': 0, 'loading': 0}),
                                  call({'address_name': '10.0.0.5', 'statecode': 5, 'statename': 'ISOLATED',
                                        'remote_time': 0, 'local_time': 0, 'loading': 0})],
                                 mocked_send.call_args_list)


def test_suite():
    return unittest.findTestCases(sys.modules[__name__])


if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
