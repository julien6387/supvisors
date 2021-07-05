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

import pytest
import random
import time

from supvisors.tests.base import DummyAddressMapper, database_copy, any_process_info
from unittest.mock import call, patch, Mock

from supvisors.ttypes import AddressStates, ApplicationStates, InvalidTransition


@pytest.fixture
def context(supvisors):
    """ Return the instance to test. """
    from supvisors.context import Context
    return Context(supvisors)


def load_application_rules(_, rules):
    """ Simple Parser.load_application_rules behaviour to avoid setdefault_process to always return None. """
    rules.default = False


@pytest.fixture
def filled_context(context):
    """ Push ProcessInfoDatabase process info in AddressStatus. """
    context.supvisors.parser.load_application_rules = load_application_rules
    for info in database_copy():
        process = context.setdefault_process(info)
        node_name = random.choice(list(context.nodes.keys()))
        process.add_info(node_name, info)
        context.nodes[node_name].add_process(process)
    return context


def test_create(supvisors, context):
    """ Test the values set at construction of Context. """
    from supvisors.address import AddressStatus
    assert supvisors is context.supvisors
    assert supvisors.logger is context.logger
    assert set(DummyAddressMapper().node_names), set(context.nodes.keys())
    for address_name, address in context.nodes.items():
        assert address.address_name == address_name
        assert isinstance(address, AddressStatus)
    assert context.applications == {}
    assert context.processes == {}
    assert context._master_node_name == ''
    assert not context._is_master
    assert not context.master_operational


def test_master_node_name(context):
    """ Test the access to master address. """
    assert context.supvisors.address_mapper.local_node_name == '127.0.0.1'
    assert context.master_node_name == ''
    assert not context.is_master
    assert not context._is_master
    assert not context.master_operational
    context.master_operational = True
    context.master_node_name = '10.0.0.1'
    assert context.master_node_name == '10.0.0.1'
    assert context._master_node_name == '10.0.0.1'
    assert not context.is_master
    assert not context._is_master
    assert not context.master_operational
    context.master_operational = True
    context.master_node_name = '127.0.0.1'
    assert context.master_node_name == '127.0.0.1'
    assert context._master_node_name == '127.0.0.1'
    assert context.is_master
    assert context._is_master
    assert not context.master_operational


def test_nodes_by_states(context):
    """ Test the access to addresses in unknown state. """
    # test initial states
    assert context.unknown_nodes() == DummyAddressMapper().node_names
    assert context.unknown_forced_nodes() == []
    assert context.running_nodes() == []
    assert context.isolating_nodes() == []
    assert context.isolation_nodes() == []
    assert context.nodes_by_states([AddressStates.RUNNING, AddressStates.ISOLATED]) == []
    assert context.nodes_by_states([AddressStates.SILENT]) == []
    assert context.nodes_by_states([AddressStates.UNKNOWN]) == DummyAddressMapper().node_names
    # change states
    context.nodes['127.0.0.1']._state = AddressStates.RUNNING
    context.nodes['10.0.0.1']._state = AddressStates.SILENT
    context.nodes['10.0.0.2']._state = AddressStates.ISOLATING
    context.nodes['10.0.0.3']._state = AddressStates.ISOLATED
    context.nodes['10.0.0.4']._state = AddressStates.RUNNING
    # test new states
    assert context.unknown_nodes() == ['10.0.0.2', '10.0.0.5']
    assert context.unknown_forced_nodes() == []
    assert context.running_nodes() == ['127.0.0.1', '10.0.0.4']
    assert context.isolating_nodes() == ['10.0.0.2']
    assert context.isolation_nodes() == ['10.0.0.2', '10.0.0.3']
    assert context.nodes_by_states([AddressStates.RUNNING, AddressStates.ISOLATED]) == \
           ['127.0.0.1', '10.0.0.3', '10.0.0.4']
    assert context.nodes_by_states([AddressStates.SILENT]) == ['10.0.0.1']
    assert context.nodes_by_states([AddressStates.UNKNOWN]) == ['10.0.0.5']


def test_unknown_forced_nodes(supvisors):
    """ Test the access to addresses in unknown state. """
    from supvisors.context import Context
    supvisors.options.force_synchro_if = ['10.0.0.1', '10.0.0.4']
    context = Context(supvisors)
    # test initial states
    assert context.unknown_nodes() == DummyAddressMapper().node_names
    assert context.unknown_forced_nodes() == ['10.0.0.1', '10.0.0.4']
    # change states
    context.nodes['127.0.0.1']._state = AddressStates.RUNNING
    context.nodes['10.0.0.2']._state = AddressStates.ISOLATING
    context.nodes['10.0.0.3']._state = AddressStates.ISOLATED
    context.nodes['10.0.0.4']._state = AddressStates.RUNNING
    # test new states
    assert context.unknown_nodes() == ['10.0.0.1', '10.0.0.2', '10.0.0.5']
    assert context.unknown_forced_nodes() == ['10.0.0.1']
    # change states
    context.nodes['10.0.0.1']._state = AddressStates.SILENT
    # test new states
    assert context.unknown_nodes() == ['10.0.0.2', '10.0.0.5']
    assert context.unknown_forced_nodes() == []


def check_address_status(context, address_name, new_state):
    # get address status
    address_status = context.nodes[address_name]
    # check initial state
    assert address_status.state == AddressStates.UNKNOWN
    # invalidate address
    proc_1 = Mock(**{'invalidate_node.return_value': None})
    proc_2 = Mock(**{'invalidate_node.return_value': None})
    with patch.object(address_status, 'running_processes', return_value=[proc_1, proc_2]) as mocked_running:
        context.invalid(address_status)
    # check new state
    assert address_status.state == new_state
    # test calls to process methods
    assert mocked_running.call_args_list == [call()]
    assert proc_1.invalidate_node.call_args_list == [call(address_name, False)]
    assert proc_2.invalidate_node.call_args_list == [call(address_name, False)]
    # restore address state
    address_status._state = AddressStates.UNKNOWN


def test_invalid(context):
    """ Test the invalidation of an address. """
    # test address state with auto_fence and local_address
    check_address_status(context, '127.0.0.1', AddressStates.SILENT)
    # test address state with auto_fence and other than local_address
    check_address_status(context, '10.0.0.1', AddressStates.ISOLATING)
    # test address state without auto_fence
    with patch.object(context.supvisors.options, 'auto_fence', False):
        # test address state without auto_fence and local_address
        check_address_status(context, '127.0.0.1', AddressStates.SILENT)
        # test address state without auto_fence and other than local_address
        check_address_status(context, '10.0.0.2', AddressStates.SILENT)


def test_end_synchro(context):
    """ Test the end of synchronization phase. """
    # choose two addresses and change their state
    for address_status in context.nodes.values():
        assert address_status.state == AddressStates.UNKNOWN
    context.nodes['10.0.0.2']._state = AddressStates.RUNNING
    context.nodes['10.0.0.4']._state = AddressStates.ISOLATED
    # call end of synchro with auto_fence activated
    context.end_synchro()
    # check that UNKNOWN addresses became ISOLATING, but local address
    assert context.nodes['127.0.0.1'].state == AddressStates.SILENT
    assert context.nodes['10.0.0.1'].state == AddressStates.ISOLATING
    assert context.nodes['10.0.0.3'].state == AddressStates.ISOLATING
    assert context.nodes['10.0.0.5'].state == AddressStates.ISOLATING
    # reset states and set (local excepted)
    context.nodes['10.0.0.1']._state = AddressStates.UNKNOWN
    context.nodes['10.0.0.3']._state = AddressStates.UNKNOWN
    context.nodes['10.0.0.5']._state = AddressStates.UNKNOWN
    with patch.object(context.supvisors.options, 'auto_fence', False):
        # call end of synchro with auto_fencing deactivated
        context.end_synchro()
    # check that UNKNOWN addresses became SILENT
    assert context.nodes['10.0.0.1'].state == AddressStates.SILENT
    assert context.nodes['10.0.0.3'].state == AddressStates.SILENT
    assert context.nodes['10.0.0.5'].state == AddressStates.SILENT


def test_conflicts(filled_context):
    """ Test the detection of conflicting processes. """
    # test no conflict
    assert not filled_context.conflicting()
    assert filled_context.conflicts() == []
    # add addresses to one process
    process1 = next(process for process in filled_context.processes.values()
                    if process.running())
    process1.running_nodes.update(filled_context.nodes.keys())
    # test conflict is detected
    assert filled_context.conflicting()
    assert filled_context.conflicts() == [process1]
    # add addresses to one other process
    process2 = next(process for process in filled_context.processes.values()
                    if process.stopped())
    process2.running_nodes.update(filled_context.nodes.keys())
    # test conflict is detected
    assert filled_context.conflicting()
    assert filled_context.conflicts() == [process1, process2]
    # empty addresses of first process list
    process1.running_nodes.clear()
    # test conflict is still detected
    assert filled_context.conflicting()
    assert filled_context.conflicts() == [process2]
    # empty addresses of second process list
    process2.running_nodes.clear()
    # test no conflict
    assert not filled_context.conflicting()
    assert filled_context.conflicts() == []


def test_setdefault_application(context):
    """ Test the access / creation of an application status. """
    # check application list
    assert context.applications == {}
    # in this test, there is no rules file so application rules default won't be changed by load_application_rules
    assert context.setdefault_application('dummy_1') is None
    assert context.applications == {}
    # so patch load_application_rules to avoid that
    context.supvisors.parser.load_application_rules = load_application_rules
    # get application
    application1 = context.setdefault_application('dummy_1')
    # check application list
    assert context.applications == {'dummy_1': application1}
    # get application
    application2 = context.setdefault_application('dummy_2')
    # check application list
    assert context.applications == {'dummy_1': application1, 'dummy_2': application2}
    # get application
    application3 = context.setdefault_application('dummy_1')
    assert application3 is application1
    # check application list
    assert context.applications == {'dummy_1': application1, 'dummy_2': application2}


def test_setdefault_process(context):
    """ Test the access / creation of a process status. """
    # check application list
    assert context.applications == {}
    assert context.processes == {}
    # test data
    dummy_info1 = {'group': 'dummy_application_1', 'name': 'dummy_process_1'}
    dummy_info2 = {'group': 'dummy_application_2', 'name': 'dummy_process_2'}
    # in this test, there is no rules file so application rules default won't be changed by load_application_rules
    assert context.setdefault_process(dummy_info1) is None
    assert context.setdefault_process(dummy_info2) is None
    assert context.applications == {}
    assert context.processes == {}
    # so patch load_application_rules to avoid that
    context.supvisors.parser.load_application_rules = load_application_rules
    # get process
    process1 = context.setdefault_process(dummy_info1)
    # check application and process list
    assert list(context.applications.keys()) == ['dummy_application_1']
    assert context.processes == {'dummy_application_1:dummy_process_1': process1}
    # get application
    process2 = context.setdefault_process(dummy_info2)
    # check application and process list
    assert sorted(context.applications.keys()) == ['dummy_application_1', 'dummy_application_2']
    assert context.processes == {'dummy_application_1:dummy_process_1': process1,
                                 'dummy_application_2:dummy_process_2': process2}
    # get application
    dummy_info3 = {'group': process1.application_name, 'name': process1.process_name}
    process3 = context.setdefault_process(dummy_info3)
    assert process3 is process1
    # check application and process list
    assert sorted(context.applications.keys()) == ['dummy_application_1', 'dummy_application_2']
    assert context.processes == {'dummy_application_1:dummy_process_1': process1,
                                 'dummy_application_2:dummy_process_2': process2}


def test_load_processes(context):
    """ Test the storage of processes handled by Supervisor on a given address. """
    # check application list
    assert context.applications == {}
    assert context.processes == {}
    for address in context.nodes.values():
        assert address.processes == {}
    # load ProcessInfoDatabase in unknown address
    with pytest.raises(KeyError):
        context.load_processes('10.0.0.0', database_copy())
    assert context.applications == {}
    assert context.processes == {}
    for address in context.nodes.values():
        assert address.processes == {}
    # load ProcessInfoDatabase in known address
    # in this test, there is no rules file so application rules default won't be changed by load_application_rules
    context.load_processes('10.0.0.1', database_copy())
    assert context.applications == {}
    assert context.processes == {}
    for address in context.nodes.values():
        assert address.processes == {}
    # so patch load_application_rules to avoid that
    context.supvisors.parser.load_application_rules = load_application_rules
    context.load_processes('10.0.0.1', database_copy())
    # check context contents
    assert sorted(context.applications.keys()) == ['crash', 'firefox', 'sample_test_1', 'sample_test_2']
    assert sorted(context.processes.keys()) == ['crash:late_segv', 'crash:segv', 'firefox',
                                                'sample_test_1:xclock', 'sample_test_1:xfontsel',
                                                'sample_test_1:xlogo', 'sample_test_2:sleep',
                                                'sample_test_2:yeux_00', 'sample_test_2:yeux_01']
    assert context.processes == context.nodes['10.0.0.1'].processes
    # load ProcessInfoDatabase in other known address
    context.load_processes('10.0.0.2', database_copy())
    # check context contents
    assert sorted(context.applications.keys()) == ['crash', 'firefox', 'sample_test_1', 'sample_test_2']
    assert sorted(context.processes.keys()) == ['crash:late_segv', 'crash:segv', 'firefox',
                                                'sample_test_1:xclock', 'sample_test_1:xfontsel',
                                                'sample_test_1:xlogo', 'sample_test_2:sleep',
                                                'sample_test_2:yeux_00', 'sample_test_2:yeux_01']
    assert context.processes == context.nodes['10.0.0.2'].processes
    # load different database in other known address
    info = any_process_info()
    info.update({'group': 'dummy_application', 'name': 'dummy_process'})
    database = [info]
    context.load_processes('10.0.0.4', database)
    # check context contents
    assert sorted(context.applications.keys()) == ['crash', 'dummy_application', 'firefox',
                                                   'sample_test_1', 'sample_test_2']
    assert sorted(context.processes.keys()) == ['crash:late_segv', 'crash:segv', 'dummy_application:dummy_process',
                                                'firefox', 'sample_test_1:xclock', 'sample_test_1:xfontsel',
                                                'sample_test_1:xlogo', 'sample_test_2:sleep',
                                                'sample_test_2:yeux_00', 'sample_test_2:yeux_01']
    assert list(context.nodes['10.0.0.4'].processes.keys()) == ['dummy_application:dummy_process']
    # equality lost between processes in addresses and processes in context
    assert list(context.nodes['10.0.0.1'].processes.keys()) not in list(context.processes.keys())
    assert list(context.nodes['10.0.0.2'].processes.keys()) not in list(context.processes.keys())
    assert list(context.nodes['10.0.0.4'].processes.keys()) not in list(context.processes.keys())
    assert all(process in context.processes for process in context.nodes['10.0.0.1'].processes)
    assert all(process in context.processes for process in context.nodes['10.0.0.2'].processes)
    assert all(process in context.processes for process in context.nodes['10.0.0.4'].processes)


def test_authorization(context):
    """ Test the handling of an authorization event. """
    # check no exception with unknown address
    context.on_authorization('10.0.0.0', True)
    # check no change with known address in isolation
    for state in [AddressStates.ISOLATING, AddressStates.ISOLATED]:
        for authorization in [True, False]:
            context.nodes['10.0.0.1']._state = state
            context.on_authorization('10.0.0.1', authorization)
            assert context.nodes['10.0.0.1'].state == state
    # check exception if authorized and current state not CHECKING
    for state in [AddressStates.UNKNOWN, AddressStates.SILENT]:
        context.nodes['10.0.0.2']._state = state
        with pytest.raises(InvalidTransition):
            context.on_authorization('10.0.0.2', True)
        assert context.nodes['10.0.0.2'].state == state
    # check state becomes RUNNING if authorized and current state in CHECKING
    for state in [AddressStates.CHECKING, AddressStates.RUNNING]:
        context.nodes['10.0.0.2']._state = state
        context.on_authorization('10.0.0.2', True)
        assert context.nodes['10.0.0.2'].state == AddressStates.RUNNING
    # check state becomes ISOLATING if not authorized and auto fencing activated
    for state in [AddressStates.UNKNOWN, AddressStates.CHECKING, AddressStates.RUNNING]:
        context.nodes['10.0.0.4']._state = state
        context.on_authorization('10.0.0.4', False)
        assert context.nodes['10.0.0.4'].state == AddressStates.ISOLATING
    # check exception if not authorized and auto fencing activated and current is SILENT
    context.nodes['10.0.0.4']._state = AddressStates.SILENT
    with pytest.raises(InvalidTransition):
        context.on_authorization('10.0.0.4', True)
    assert context.nodes['10.0.0.4'].state == AddressStates.SILENT
    # check state becomes SILENT if not authorized and auto fencing deactivated
    with patch.object(context.supvisors.options, 'auto_fence', False):
        for state in [AddressStates.UNKNOWN, AddressStates.CHECKING, AddressStates.SILENT, AddressStates.RUNNING]:
            context.nodes['10.0.0.5']._state = state
            context.on_authorization('10.0.0.5', False)
            assert context.nodes['10.0.0.5'].state == AddressStates.SILENT


def test_tick_event(mocker, context):
    """ Test the handling of a timer event. """
    mocker.patch('supvisors.context.time', return_value=3600)
    mocked_check = context.supvisors.zmq.pusher.send_check_node
    mocked_send = context.supvisors.zmq.publisher.send_address_status
    # check no exception with unknown address
    context.on_tick_event('10.0.0.0', {})
    assert not mocked_check.called
    assert not mocked_send.called
    # get address status used for tests
    address = context.nodes['10.0.0.1']
    # check no change with known address in isolation
    for state in [AddressStates.ISOLATING, AddressStates.ISOLATED]:
        address._state = state
        context.on_tick_event('10.0.0.1', {})
        assert address.state == state
        assert not mocked_check.called
        assert not mocked_send.called
    # check that address is CHECKING and check_address is called
    # before address time is updated and address status is sent
    for state in [AddressStates.UNKNOWN, AddressStates.SILENT]:
        address._state = state
        context.on_tick_event('10.0.0.1', {'when': 1234})
        assert address.state == AddressStates.CHECKING
        assert address.remote_time == 1234
        assert mocked_check.call_args_list == [call('10.0.0.1')]
        assert mocked_send.call_args_list == [call({'address_name': '10.0.0.1',
                                                    'statecode': 1, 'statename': 'CHECKING',
                                                    'remote_time': 1234, 'local_time': 3600, 'loading': 0})]
        mocked_check.reset_mock()
        mocked_send.reset_mock()
    # check that address time is updated and address status is sent
    mocked_check.reset_mock()
    mocked_send.reset_mock()
    for state in [AddressStates.CHECKING, AddressStates.RUNNING]:
        address._state = state
        context.on_tick_event('10.0.0.1', {'when': 5678})
        assert address.state == state
        assert address.remote_time == 5678
        assert not mocked_check.called
        assert mocked_send.call_args_list == [call({'address_name': '10.0.0.1',
                                                    'statecode': state.value, 'statename': state.name,
                                                    'remote_time': 5678, 'local_time': 3600, 'loading': 0})]
        mocked_send.reset_mock()


def test_process_event(mocker, context):
    """ Test the handling of a process event. """
    mocker.patch('supvisors.process.time', return_value=1234)
    mocked_publisher = context.supvisors.zmq.publisher
    mocked_update_args = context.supvisors.info_source.update_extra_args
    # check no exception with unknown address
    result = context.on_process_event('10.0.0.0', {})
    assert result is None
    assert not mocked_update_args.called
    assert not mocked_publisher.send_process_event.called
    assert not mocked_publisher.send_process_status.called
    assert not mocked_publisher.send_application_status.called
    # get address status used for tests
    address = context.nodes['10.0.0.1']
    # check no change with known address in isolation
    for state in [AddressStates.ISOLATING, AddressStates.ISOLATED]:
        address._state = state
        result = context.on_process_event('10.0.0.1', {})
        assert result is None
        assert not mocked_update_args.called
        assert not mocked_publisher.send_process_event.called
        assert not mocked_publisher.send_process_status.called
        assert not mocked_publisher.send_application_status.called
    # check no exception with unknown process
    for state in [AddressStates.UNKNOWN, AddressStates.SILENT, AddressStates.CHECKING, AddressStates.RUNNING]:
        address._state = state
        result = context.on_process_event('10.0.0.1', {'groupname': 'dummy_application',
                                                       'processname': 'dummy_process'})
        assert result is None
        assert not mocked_update_args.called
        assert not mocked_publisher.send_process_event.called
        assert not mocked_publisher.send_process_status.called
        assert not mocked_publisher.send_application_status.called
    # patch load_application_rules
    context.supvisors.parser.load_application_rules = load_application_rules
    # fill context with one process
    dummy_info = {'group': 'dummy_application', 'name': 'dummy_process', 'expected': True, 'now': 1234, 'state': 0}
    process = context.setdefault_process(dummy_info)
    process.add_info('10.0.0.1', dummy_info)
    application = context.applications['dummy_application']
    assert application.state == ApplicationStates.STOPPED
    # check normal behaviour with known process
    dummy_event = {'group': 'dummy_application', 'name': 'dummy_process', 'state': 10, 'now': 2345, 'extra_args': ''}
    for state in [AddressStates.UNKNOWN, AddressStates.SILENT, AddressStates.CHECKING, AddressStates.RUNNING]:
        address._state = state
        result = context.on_process_event('10.0.0.1', dummy_event)
        assert result is process
        assert process.state == 10
        assert application.state == ApplicationStates.STARTING
        assert mocked_update_args.call_args_list == [call('dummy_application:dummy_process', '')]
        assert mocked_publisher.send_process_event.call_args_list == \
               [call('10.0.0.1', {'group': 'dummy_application', 'name': 'dummy_process',
                                  'state': 10, 'now': 2345, 'extra_args': ''})]
        assert mocked_publisher.send_process_status.call_args_list == \
               [call({'application_name': 'dummy_application', 'process_name': 'dummy_process',
                      'statecode': 10, 'statename': 'STARTING', 'expected_exit': True,
                      'last_event_time': 1234, 'addresses': ['10.0.0.1'], 'extra_args': ''})]
        assert mocked_publisher.send_application_status.call_args_list == \
               [call({'application_name': 'dummy_application', 'statecode': 1, 'statename': 'STARTING',
                      'major_failure': False, 'minor_failure': False})]
        # reset mocks
        mocked_update_args.reset_mock()
        mocked_publisher.send_process_event.reset_mock()
        mocked_publisher.send_process_status.reset_mock()
        mocked_publisher.send_application_status.reset_mock()
    # check degraded behaviour with process to Supvisors but unknown to Supervisor (remote program)
    # basically same check as previous, just being confident that no exception is raise dby the method
    mocked_update_args.side_effect = KeyError
    result = context.on_process_event('10.0.0.1', dummy_event)
    assert result is process
    assert process.state == 10
    assert application.state == ApplicationStates.STARTING
    assert mocked_update_args.call_args_list == [call('dummy_application:dummy_process', '')]
    assert mocked_publisher.send_process_event.call_args_list == \
           [call('10.0.0.1', {'group': 'dummy_application', 'name': 'dummy_process',
                              'state': 10, 'now': 2345, 'extra_args': ''})]
    assert mocked_publisher.send_process_status.call_args_list == \
           [call({'application_name': 'dummy_application', 'process_name': 'dummy_process',
                  'statecode': 10, 'statename': 'STARTING', 'expected_exit': True,
                  'last_event_time': 1234, 'addresses': ['10.0.0.1'], 'extra_args': ''})]
    assert mocked_publisher.send_application_status.call_args_list == \
           [call({'application_name': 'dummy_application', 'statecode': 1, 'statename': 'STARTING',
                  'major_failure': False, 'minor_failure': False})]


def test_timer_event(mocker, context):
    """ Test the handling of a timer event. """
    mocked_time = mocker.patch('supvisors.context.time', return_value=3600)
    mocked_send = context.supvisors.zmq.publisher.send_address_status
    # test address states excepting RUNNING: nothing happens
    for _ in [x for x in AddressStates if x != AddressStates.RUNNING]:
        context.on_timer_event()
        for address in context.nodes.values():
            assert address.state == AddressStates.UNKNOWN
        assert not mocked_send.called
    # test RUNNING address state with recent local_time
    test_addresses = ['10.0.0.1', '10.0.0.3', '10.0.0.5']
    for address_name in test_addresses:
        address = context.nodes[address_name]
        address._state = AddressStates.RUNNING
        address.local_time = time.time()
    context.on_timer_event()
    for address_name in test_addresses:
        assert context.nodes[address_name].state == AddressStates.RUNNING
    for address_name in [x for x in context.nodes.keys()
                         if x not in test_addresses]:
        assert context.nodes[address_name].state == AddressStates.UNKNOWN
    assert not mocked_send.called
    # test RUNNING address state with one recent local_time and with auto_fence activated
    address1 = context.nodes['10.0.0.3']
    address1.local_time = mocked_time.return_value - 100
    context.on_timer_event()
    assert address1.state == AddressStates.ISOLATING
    for address_name in [x for x in test_addresses if x != '10.0.0.3']:
        assert context.nodes[address_name].state == AddressStates.RUNNING
    for address_name in [x for x in context.nodes.keys()
                         if x not in test_addresses]:
        assert context.nodes[address_name].state == AddressStates.UNKNOWN
    assert mocked_send.call_args_list == [call({'address_name': '10.0.0.3', 'statecode': 4, 'statename': 'ISOLATING',
                                                'remote_time': 0, 'local_time': address1.local_time, 'loading': 0})]
    # test with one other recent local_time and with auto_fence deactivated
    context.supvisors.options.auto_fence = False
    mocked_send.reset_mock()
    address2 = context.nodes['10.0.0.5']
    address2.local_time = mocked_time.return_value - 100
    address3 = context.nodes['10.0.0.1']
    address3.local_time = mocked_time.return_value - 100
    context.on_timer_event()
    assert address2.state == AddressStates.SILENT
    assert address3.state == AddressStates.SILENT
    assert address1.state == AddressStates.ISOLATING
    for address_name in [x for x in context.nodes.keys()
                         if x not in test_addresses]:
        assert context.nodes[address_name].state == AddressStates.UNKNOWN
    send_calls = mocked_send.call_args_list
    payload2 = {'address_name': '10.0.0.5', 'statecode': 3, 'statename': 'SILENT',
                'remote_time': 0, 'local_time': address2.local_time, 'loading': 0}
    payload3 = {'address_name': '10.0.0.1', 'statecode': 3, 'statename': 'SILENT',
                'remote_time': 0, 'local_time': address3.local_time, 'loading': 0}
    assert send_calls == [call(payload2), call(payload3)] or send_calls == [call(payload3), call(payload2)]


def test_handle_isolation(context):
    """ Test the isolation of addresses. """
    with patch.object(context.supvisors.zmq.publisher, 'send_address_status') as mocked_send:
        # update address states
        context.nodes['127.0.0.1']._state = AddressStates.CHECKING
        context.nodes['10.0.0.1']._state = AddressStates.RUNNING
        context.nodes['10.0.0.2']._state = AddressStates.SILENT
        context.nodes['10.0.0.3']._state = AddressStates.ISOLATED
        context.nodes['10.0.0.4']._state = AddressStates.ISOLATING
        context.nodes['10.0.0.5']._state = AddressStates.ISOLATING
        # call method and check result
        assert context.handle_isolation() == ['10.0.0.4', '10.0.0.5']
        assert context.nodes['127.0.0.1'].state == AddressStates.CHECKING
        assert context.nodes['10.0.0.1'].state == AddressStates.RUNNING
        assert context.nodes['10.0.0.2'].state == AddressStates.SILENT
        assert context.nodes['10.0.0.3'].state == AddressStates.ISOLATED
        assert context.nodes['10.0.0.4'].state == AddressStates.ISOLATED
        assert context.nodes['10.0.0.5'].state == AddressStates.ISOLATED
        # check calls to publisher.send_address_status
        assert mocked_send.call_args_list == [call({'address_name': '10.0.0.4', 'statecode': 5, 'statename': 'ISOLATED',
                                                    'remote_time': 0, 'local_time': 0, 'loading': 0}),
                                              call({'address_name': '10.0.0.5', 'statecode': 5, 'statename': 'ISOLATED',
                                                    'remote_time': 0, 'local_time': 0, 'loading': 0})]
