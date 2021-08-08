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

from unittest.mock import call, Mock

from supvisors.context import *
from supvisors.ttypes import AddressStates, ApplicationStates, InvalidTransition

from .base import DummyAddressMapper, database_copy, any_process_info


@pytest.fixture
def context(supvisors):
    """ Return the instance to test. """
    return Context(supvisors)


def load_application_rules(_, rules):
    """ Simple Parser.load_application_rules behaviour to avoid setdefault_process to always return None. """
    rules.managed = True


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
    assert supvisors is context.supvisors
    assert supvisors.logger is context.logger
    assert set(DummyAddressMapper().node_names), set(context.nodes.keys())
    for address_name, address in context.nodes.items():
        assert address.address_name == address_name
        assert isinstance(address, AddressStatus)
    assert context.applications == {}
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


def check_invalid_node_status(context, node_name, new_state, fence=None):
    # get address status
    node = context.nodes[node_name]
    # check initial state
    assert node.state == AddressStates.UNKNOWN
    # invalidate address
    context.invalid(node, fence)
    # check new state
    assert node.state == new_state
    # restore address state
    node._state = AddressStates.UNKNOWN


def test_invalid(mocker, context):
    """ Test the invalidation of a node. """
    # test address state with auto_fence
    mocker.patch.object(context.supvisors.options, 'auto_fence', True)
    # test address state with auto_fence and local_address
    check_invalid_node_status(context, '127.0.0.1', AddressStates.SILENT)
    check_invalid_node_status(context, '127.0.0.1', AddressStates.SILENT, True)
    # test address state with auto_fence and other than local_address
    check_invalid_node_status(context, '10.0.0.1', AddressStates.ISOLATING)
    check_invalid_node_status(context, '10.0.0.1', AddressStates.ISOLATING, True)
    # test address state without auto_fence
    mocker.patch.object(context.supvisors.options, 'auto_fence', False)
    # test address state without auto_fence and local_address
    check_invalid_node_status(context, '127.0.0.1', AddressStates.SILENT)
    check_invalid_node_status(context, '127.0.0.1', AddressStates.SILENT, True)
    # test address state without auto_fence and other than local_address
    check_invalid_node_status(context, '10.0.0.2', AddressStates.SILENT)
    check_invalid_node_status(context, '10.0.0.2', AddressStates.ISOLATING, True)


def test_end_synchro(mocker, context):
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
    # call end of synchro with auto_fencing deactivated
    mocker.patch.object(context.supvisors.options, 'auto_fence', False)
    context.end_synchro()
    # check that UNKNOWN addresses became SILENT
    assert context.nodes['10.0.0.1'].state == AddressStates.SILENT
    assert context.nodes['10.0.0.3'].state == AddressStates.SILENT
    assert context.nodes['10.0.0.5'].state == AddressStates.SILENT


def test_get_managed_applications(filled_context):
    """ Test getting all managed applications. """
    # in this test, all applications are managed by default
    managed_applications = list(filled_context.get_managed_applications())
    managed_names = {application.application_name for application in managed_applications}
    assert sorted(managed_names) == ['crash', 'firefox', 'sample_test_1', 'sample_test_2']
    # unmanage a few ones
    filled_context.applications['firefox'].rules.managed = False
    filled_context.applications['sample_test_1'].rules.managed = False
    # re-test
    managed_applications = list(filled_context.get_managed_applications())
    managed_names = {application.application_name for application in managed_applications}
    assert sorted(managed_names) == ['crash', 'sample_test_2']


def test_get_all_namespecs(filled_context):
    """ Test getting all known namespecs across all supvisors instances. """
    assert sorted(filled_context.get_all_namespecs()) == ['crash:late_segv', 'crash:segv', 'firefox',
                                                          'sample_test_1:xclock', 'sample_test_1:xfontsel',
                                                          'sample_test_1:xlogo', 'sample_test_2:sleep',
                                                          'sample_test_2:yeux_00', 'sample_test_2:yeux_01']


def test_get_process(filled_context):
    """ Test getting a ProcessStatus based on its namespec. """
    # test with existing namespec
    process = filled_context.get_process('sample_test_1:xclock')
    assert process.application_name == 'sample_test_1'
    assert process.process_name == 'xclock'
    # test with existing namespec (no group)
    process = filled_context.get_process('firefox')
    assert process.application_name == 'firefox'
    assert process.process_name == 'firefox'
    # test with unknown application or process
    with pytest.raises(KeyError):
        filled_context.get_process('unknown:xclock')
    with pytest.raises(KeyError):
        filled_context.get_process('sample_test_2:xclock')


def test_conflicts(filled_context):
    """ Test the detection of conflicting processes. """
    # test no conflict
    assert not filled_context.conflicting()
    assert filled_context.conflicts() == []
    # add addresses to one process
    process1 = next(process for application in filled_context.applications.values()
                    for process in application.processes.values()
                    if process.running())
    process1.running_nodes.update(filled_context.nodes.keys())
    # test conflict is detected
    assert filled_context.conflicting()
    assert filled_context.conflicts() == [process1]
    # add addresses to one other process
    process2 = next(process for application in filled_context.applications.values()
                    for process in application.processes.values()
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
    # in this test, there is no rules file so application rules managed won't be changed by load_application_rules
    application1 = context.setdefault_application('dummy_1')
    assert context.applications == {'dummy_1': application1}
    assert not application1.rules.managed
    # so patch load_application_rules to avoid that
    context.supvisors.parser.load_application_rules = load_application_rules
    # get application
    application1 = context.setdefault_application('dummy_1')
    # check application list. rules are not re-evaluated so application still not managed
    assert context.applications == {'dummy_1': application1}
    assert not application1.rules.managed
    # get application
    application2 = context.setdefault_application('dummy_2')
    # check application list
    assert context.applications == {'dummy_1': application1, 'dummy_2': application2}
    assert application2.rules.managed


def test_setdefault_process(context):
    """ Test the access / creation of a process status. """
    # check application list
    assert context.applications == {}
    # test data
    dummy_info1 = {'group': 'dummy_application_1', 'name': 'dummy_process_1'}
    dummy_info2 = {'group': 'dummy_application_2', 'name': 'dummy_process_2'}
    # in this test, there is no rules file so application rules managed won't be changed by load_application_rules
    process1 = context.setdefault_process(dummy_info1)
    assert process1.application_name == 'dummy_application_1'
    assert process1.process_name == 'dummy_process_1'
    assert list(context.applications.keys()) == ['dummy_application_1']
    application1 = context.applications['dummy_application_1']
    assert application1.processes == {'dummy_process_1': process1}
    assert not application1.rules.managed
    # so patch load_application_rules to avoid that
    context.supvisors.parser.load_application_rules = load_application_rules
    # get process
    process1 = context.setdefault_process(dummy_info1)
    # check application still unmanaged
    application1 = context.applications['dummy_application_1']
    assert not application1.rules.managed
    # get application
    process2 = context.setdefault_process(dummy_info2)
    # check application and process list
    assert sorted(context.applications.keys()) == ['dummy_application_1', 'dummy_application_2']
    application1 = context.applications['dummy_application_1']
    application2 = context.applications['dummy_application_2']
    assert application1.processes == {'dummy_process_1': process1}
    assert application2.processes == {'dummy_process_2': process2}
    assert not application1.rules.managed
    assert application2.rules.managed


def test_load_processes(context):
    """ Test the storage of processes handled by Supervisor on a given address. """
    # check application list
    assert context.applications == {}
    for node in context.nodes.values():
        assert node.processes == {}
    # load ProcessInfoDatabase in unknown address
    with pytest.raises(KeyError):
        context.load_processes('10.0.0.0', database_copy())
    assert context.applications == {}
    for node in context.nodes.values():
        assert node.processes == {}
    # load ProcessInfoDatabase with known address
    context.load_processes('10.0.0.1', database_copy())
    # check context contents
    assert sorted(context.applications.keys()) == ['crash', 'firefox', 'sample_test_1', 'sample_test_2']
    assert sorted(context.applications['crash'].processes.keys()) == ['late_segv', 'segv']
    assert sorted(context.applications['firefox'].processes.keys()) == ['firefox']
    assert sorted(context.applications['sample_test_1'].processes.keys()) == ['xclock', 'xfontsel', 'xlogo']
    assert sorted(context.applications['sample_test_2'].processes.keys()) == ['sleep', 'yeux_00', 'yeux_01']
    assert sorted(context.nodes['10.0.0.1'].processes.keys()) == ['crash:late_segv', 'crash:segv', 'firefox',
                                                                  'sample_test_1:xclock', 'sample_test_1:xfontsel',
                                                                  'sample_test_1:xlogo', 'sample_test_2:sleep',
                                                                  'sample_test_2:yeux_00', 'sample_test_2:yeux_01']
    assert context.nodes['10.0.0.2'].processes == {}
    # load ProcessInfoDatabase in other known address
    context.load_processes('10.0.0.2', database_copy())
    # check context contents
    assert sorted(context.applications.keys()) == ['crash', 'firefox', 'sample_test_1', 'sample_test_2']
    assert sorted(context.applications['crash'].processes.keys()) == ['late_segv', 'segv']
    assert sorted(context.applications['firefox'].processes.keys()) == ['firefox']
    assert sorted(context.applications['sample_test_1'].processes.keys()) == ['xclock', 'xfontsel', 'xlogo']
    assert sorted(context.applications['sample_test_2'].processes.keys()) == ['sleep', 'yeux_00', 'yeux_01']
    assert sorted(context.nodes['10.0.0.2'].processes.keys()) == ['crash:late_segv', 'crash:segv', 'firefox',
                                                                  'sample_test_1:xclock', 'sample_test_1:xfontsel',
                                                                  'sample_test_1:xlogo', 'sample_test_2:sleep',
                                                                  'sample_test_2:yeux_00', 'sample_test_2:yeux_01']
    assert context.nodes['10.0.0.1'].processes == context.nodes['10.0.0.2'].processes
    # load different database in other known address
    info = any_process_info()
    info.update({'group': 'dummy_application', 'name': 'dummy_process'})
    database = [info]
    context.load_processes('10.0.0.4', database)
    # check context contents
    assert sorted(context.applications.keys()) == ['crash', 'dummy_application', 'firefox',
                                                   'sample_test_1', 'sample_test_2']
    assert list(context.nodes['10.0.0.4'].processes.keys()) == ['dummy_application:dummy_process']
    assert sorted(context.applications['crash'].processes.keys()) == ['late_segv', 'segv']
    assert sorted(context.applications['dummy_application'].processes.keys()) == ['dummy_process']
    assert sorted(context.applications['firefox'].processes.keys()) == ['firefox']
    assert sorted(context.applications['sample_test_1'].processes.keys()) == ['xclock', 'xfontsel', 'xlogo']
    assert sorted(context.applications['sample_test_2'].processes.keys()) == ['sleep', 'yeux_00', 'yeux_01']


def test_authorization(mocker, context):
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
    # check state becomes ISOLATED reciprocally if not authorized and even if auto fencing deactivated
    mocker.patch.object(context.supvisors.options, 'auto_fence', False)
    for state in [AddressStates.UNKNOWN, AddressStates.CHECKING, AddressStates.SILENT, AddressStates.RUNNING]:
        context.nodes['10.0.0.5']._state = state
        context.on_authorization('10.0.0.5', False)
        assert context.nodes['10.0.0.5'].state == AddressStates.ISOLATING


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


def test_process_event_unknown_node(mocker, context):
    """ Test the handling of a process event coming from an unknown node. """
    mocker.patch('supvisors.process.time', return_value=1234)
    mocked_publisher = context.supvisors.zmq.publisher
    mocked_update_args = context.supvisors.info_source.update_extra_args
    result = context.on_process_event('10.0.0.0', {})
    assert result is None
    assert not mocked_update_args.called
    assert not mocked_publisher.send_process_event.called
    assert not mocked_publisher.send_process_status.called
    assert not mocked_publisher.send_application_status.called


def test_process_event_isolated_node(mocker, context):
    """ Test the handling of a process event coming from an isolated node. """
    mocker.patch('supvisors.process.time', return_value=1234)
    mocked_publisher = context.supvisors.zmq.publisher
    mocked_update_args = context.supvisors.info_source.update_extra_args
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


def test_process_event_unknown_process(mocker, context):
    """ Test the handling of a process event corresponding to an unknown process. """
    mocker.patch('supvisors.process.time', return_value=1234)
    mocked_publisher = context.supvisors.zmq.publisher
    mocked_update_args = context.supvisors.info_source.update_extra_args
    # get address status used for tests
    node = context.nodes['10.0.0.1']
    # check no exception with unknown process
    for state in [AddressStates.UNKNOWN, AddressStates.SILENT, AddressStates.CHECKING, AddressStates.RUNNING]:
        node._state = state
        result = context.on_process_event('10.0.0.1', {'groupname': 'dummy_application',
                                                       'processname': 'dummy_process'})
        assert result is None
        assert not mocked_update_args.called
        assert not mocked_publisher.send_process_event.called
        assert not mocked_publisher.send_process_status.called
        assert not mocked_publisher.send_application_status.called


def test_process_event(mocker, context):
    """ Test the handling of a process event. """
    mocker.patch('supvisors.process.time', return_value=1234)
    mocked_publisher = context.supvisors.zmq.publisher
    mocked_update_args = context.supvisors.info_source.update_extra_args
    # get address status used for tests
    node = context.nodes['10.0.0.1']
    # patch load_application_rules
    context.supvisors.parser.load_application_rules = load_application_rules
    # fill context with one process
    dummy_info = {'group': 'dummy_application', 'name': 'dummy_process', 'expected': True, 'state': 0,
                  'now': 1234, 'stop': 0}
    process = context.setdefault_process(dummy_info)
    process.add_info('10.0.0.1', dummy_info)
    application = context.applications['dummy_application']
    assert application.state == ApplicationStates.STOPPED
    # update sequences for the test
    application.rules.managed = True
    application.update_sequences()
    # check normal behaviour with known process
    dummy_event = {'group': 'dummy_application', 'name': 'dummy_process', 'state': 10, 'extra_args': '',
                   'now': 2345, 'stop': 0}
    for state in [AddressStates.UNKNOWN, AddressStates.SILENT, AddressStates.CHECKING, AddressStates.RUNNING]:
        node._state = state
        result = context.on_process_event('10.0.0.1', dummy_event)
        assert result is process
        assert process.state == 10
        assert application.state == ApplicationStates.STARTING
        assert mocked_update_args.call_args_list == [call('dummy_application:dummy_process', '')]
        assert mocked_publisher.send_process_event.call_args_list == \
               [call('10.0.0.1', {'group': 'dummy_application', 'name': 'dummy_process',
                                  'state': 10, 'extra_args': '', 'now': 2345, 'stop': 0})]
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
    # basically same check as previous, just being confident that no exception is raised by the method
    mocked_update_args.side_effect = KeyError
    result = context.on_process_event('10.0.0.1', dummy_event)
    assert result is process
    assert process.state == 10
    assert application.state == ApplicationStates.STARTING
    assert mocked_update_args.call_args_list == [call('dummy_application:dummy_process', '')]
    assert mocked_publisher.send_process_event.call_args_list == \
           [call('10.0.0.1', {'group': 'dummy_application', 'name': 'dummy_process',
                              'state': 10, 'extra_args': '', 'now': 2345, 'stop': 0})]
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
    # check normal behaviour with known process and forced state event
    dummy_forced_event = {'group': 'dummy_application', 'name': 'dummy_process', 'state': 200, 'forced': True,
                          'extra_args': '-h', 'now': 2345, 'pid': 0, 'expected': False, 'spawnerr': 'ouch'}
    result = context.on_process_event('10.0.0.1', dummy_forced_event)
    assert result is process
    assert process.state == 200
    assert application.state == ApplicationStates.STOPPED
    assert not mocked_update_args.called
    assert mocked_publisher.send_process_event.call_args_list == \
           [call('10.0.0.1', {'group': 'dummy_application', 'name': 'dummy_process', 'state': 200,
                              'extra_args': '-h', 'now': 2345, 'pid': 0, 'expected': False, 'spawnerr': 'ouch'})]
    assert mocked_publisher.send_process_status.call_args_list == \
           [call({'application_name': 'dummy_application', 'process_name': 'dummy_process',
                  'statecode': 200, 'statename': 'FATAL', 'expected_exit': True,
                  'last_event_time': 1234, 'addresses': ['10.0.0.1'], 'extra_args': ''})]
    assert mocked_publisher.send_application_status.call_args_list == \
           [call({'application_name': 'dummy_application', 'statecode': 0, 'statename': 'STOPPED',
                  'major_failure': False, 'minor_failure': True})]


def test_timer_event(mocker, context):
    """ Test the handling of a timer event. """
    mocker.patch('supvisors.context.time', return_value=3600)
    mocked_send = context.supvisors.zmq.publisher.send_address_status
    # update node context
    context.nodes['127.0.0.1'].__dict__.update({'_state': AddressStates.RUNNING, 'local_time': 3598})
    context.nodes['10.0.0.1'].__dict__.update({'_state': AddressStates.RUNNING, 'local_time': 3593})
    context.nodes['10.0.0.2'].__dict__.update({'_state': AddressStates.RUNNING, 'local_time': 3588})
    context.nodes['10.0.0.3'].__dict__.update({'_state': AddressStates.SILENT, 'local_time': 1800})
    context.nodes['10.0.0.4'].__dict__.update({'_state': AddressStates.ISOLATING, 'local_time': 0})
    context.nodes['10.0.0.5'].__dict__.update({'_state': AddressStates.ISOLATED, 'local_time': 0})
    # patch the expected future invalidated node
    proc_1 = Mock(rules=Mock(expected_load=3), **{'invalidate_node.return_value': False})
    proc_2 = Mock(rules=Mock(expected_load=12), **{'invalidate_node.return_value': True})
    mocker.patch.object(context.nodes['10.0.0.2'], 'running_processes', return_value=[proc_1, proc_2])
    # test call and check results
    assert context.on_timer_event() == {proc_2}
    assert mocked_send.call_args_list == [call({'address_name': '10.0.0.2', 'statecode': 4, 'statename': 'ISOLATING',
                                                'remote_time': 0, 'local_time': 3588, 'loading': 15})]
    assert proc_2.invalidate_node.call_args_list == [(call('10.0.0.2'))]
    # only '10.0.0.2' node changed state
    for node_name, state in [('127.0.0.1', AddressStates.RUNNING), ('10.0.0.1', AddressStates.RUNNING),
                             ('10.0.0.2', AddressStates.ISOLATING), ('10.0.0.3', AddressStates.SILENT),
                             ('10.0.0.4', AddressStates.ISOLATING), ('10.0.0.5', AddressStates.ISOLATED)]:
        assert context.nodes[node_name].state == state


def test_handle_isolation(mocker, context):
    """ Test the isolation of addresses. """
    mocked_send = mocker.patch.object(context.supvisors.zmq.publisher, 'send_address_status')
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
