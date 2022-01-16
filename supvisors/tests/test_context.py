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
from supvisors.ttypes import SupvisorsInstanceStates, ApplicationStates, InvalidTransition

from .base import database_copy, any_process_info
from .conftest import create_application


@pytest.fixture
def context(supvisors):
    """ Return the instance to test. """
    return Context(supvisors)


def load_application_rules(_, rules):
    """ Simple Parser.load_application_rules behaviour to avoid setdefault_process to always return None. """
    rules.managed = True
    rules.starting_failure_strategy = StartingFailureStrategies.STOP
    rules.running_failure_strategy = RunningFailureStrategies.RESTART_APPLICATION


@pytest.fixture
def filled_context(context):
    """ Push ProcessInfoDatabase process info in SupvisorsInstanceStatus. """
    context.supvisors.parser.load_application_rules = load_application_rules
    for info in database_copy():
        process = context.setdefault_process(info)
        node_name = random.choice(list(context.instances.keys()))
        process.add_info(node_name, info)
        context.instances[node_name].add_process(process)
    return context


def test_create(supvisors, context):
    """ Test the values set at construction of Context. """
    assert supvisors is context.supvisors
    assert supvisors.logger is context.logger
    assert set(supvisors.supvisors_mapper.instances.keys()), set(context.instances.keys())
    for identifier, instance_status in context.instances.items():
        assert instance_status.identifier == identifier
        assert isinstance(instance_status, SupvisorsInstanceStatus)
    assert context.applications == {}
    assert context._master_identifier == ''
    assert not context._is_master
    assert context.start_date == 0


def test_reset(mocker, context):
    """ Test the reset of Context values. """
    mocker.patch('supvisors.context.time', return_value=3600)
    # change master definition
    context.master_identifier = '127.0.0.1'
    assert context.is_master
    # change node states
    context.instances['127.0.0.1']._state = SupvisorsInstanceStates.RUNNING
    context.instances['10.0.0.1']._state = SupvisorsInstanceStates.SILENT
    context.instances['10.0.0.2']._state = SupvisorsInstanceStates.ISOLATING
    context.instances['10.0.0.3']._state = SupvisorsInstanceStates.ISOLATED
    context.instances['10.0.0.4']._state = SupvisorsInstanceStates.RUNNING
    # add an application
    application = create_application('dummy_appli', context.supvisors)
    context.applications['dummy_appli'] = application
    # call reset and check result
    context.reset()
    assert set(context.supvisors.supvisors_mapper.instances), set(context.instances.keys())
    context.instances['127.0.0.1']._state = SupvisorsInstanceStates.UNKNOWN
    context.instances['10.0.0.1']._state = SupvisorsInstanceStates.SILENT
    context.instances['10.0.0.2']._state = SupvisorsInstanceStates.ISOLATING
    context.instances['10.0.0.3']._state = SupvisorsInstanceStates.ISOLATED
    context.instances['10.0.0.4']._state = SupvisorsInstanceStates.UNKNOWN
    assert context.applications == {'dummy_appli': application}
    assert context._master_identifier == ''
    assert not context._is_master
    assert context.start_date == 3600


def test_master_node_name(context):
    """ Test the access to master node. """
    assert context.supvisors.supvisors_mapper.local_identifier == '127.0.0.1'
    assert context.master_identifier == ''
    assert not context.is_master
    assert not context._is_master
    context.master_identifier = '10.0.0.1'
    assert context.master_identifier == '10.0.0.1'
    assert context._master_identifier == '10.0.0.1'
    assert not context.is_master
    assert not context._is_master
    context.master_identifier = '127.0.0.1'
    assert context.master_identifier == '127.0.0.1'
    assert context._master_identifier == '127.0.0.1'
    assert context.is_master
    assert context._is_master


def test_instances_by_states(context):
    """ Test the access to instances in unknown state. """
    # test initial states
    assert sorted(context.unknown_identifiers()) == sorted(context.supvisors.supvisors_mapper.instances.keys())
    assert context.running_core_identifiers() is None
    assert context.running_identifiers() == []
    assert context.isolating_instances() == []
    assert context.isolation_instances() == []
    assert context.instances_by_states([SupvisorsInstanceStates.RUNNING, SupvisorsInstanceStates.ISOLATED]) == []
    assert context.instances_by_states([SupvisorsInstanceStates.SILENT]) == []
    assert sorted(context.instances_by_states([SupvisorsInstanceStates.UNKNOWN])) == \
           sorted(context.supvisors.supvisors_mapper.instances.keys())
    # change states
    context.instances['127.0.0.1']._state = SupvisorsInstanceStates.RUNNING
    context.instances['10.0.0.1']._state = SupvisorsInstanceStates.SILENT
    context.instances['10.0.0.2']._state = SupvisorsInstanceStates.ISOLATING
    context.instances['10.0.0.3']._state = SupvisorsInstanceStates.ISOLATED
    context.instances['10.0.0.4']._state = SupvisorsInstanceStates.RUNNING
    # test new states
    assert context.unknown_identifiers() == ['10.0.0.2', '10.0.0.5']
    assert context.running_core_identifiers() is None
    assert context.running_identifiers() == ['127.0.0.1', '10.0.0.4']
    assert context.isolating_instances() == ['10.0.0.2']
    assert context.isolation_instances() == ['10.0.0.2', '10.0.0.3']
    assert context.instances_by_states([SupvisorsInstanceStates.RUNNING, SupvisorsInstanceStates.ISOLATED]) == \
           ['127.0.0.1', '10.0.0.3', '10.0.0.4']
    assert context.instances_by_states([SupvisorsInstanceStates.SILENT]) == ['10.0.0.1']
    assert context.instances_by_states([SupvisorsInstanceStates.UNKNOWN]) == ['10.0.0.5']


def test_running_core_identifiers(supvisors):
    """ Test if the core instances are in a RUNNING state. """
    supvisors.supvisors_mapper._core_identifiers = ['10.0.0.1', '10.0.0.4']
    context = Context(supvisors)
    # test initial states
    assert sorted(context.unknown_identifiers()) == sorted(context.supvisors.supvisors_mapper.instances.keys())
    assert not context.running_core_identifiers()
    # change states
    context.instances['127.0.0.1']._state = SupvisorsInstanceStates.RUNNING
    context.instances['10.0.0.2']._state = SupvisorsInstanceStates.ISOLATING
    context.instances['10.0.0.3']._state = SupvisorsInstanceStates.ISOLATED
    context.instances['10.0.0.4']._state = SupvisorsInstanceStates.RUNNING
    # test new states
    assert context.unknown_identifiers() == ['10.0.0.1', '10.0.0.2', '10.0.0.5']
    assert not context.running_core_identifiers()
    # change states
    context.instances['10.0.0.1']._state = SupvisorsInstanceStates.SILENT
    # test new states
    assert context.unknown_identifiers() == ['10.0.0.2', '10.0.0.5']
    assert not context.running_core_identifiers()
    # change states
    context.instances['10.0.0.1']._state = SupvisorsInstanceStates.RUNNING
    # test new states
    assert context.unknown_identifiers() == ['10.0.0.2', '10.0.0.5']
    assert context.running_core_identifiers()


def check_invalid_node_status(context, node_name, new_state, fence=None):
    # get node status
    node = context.instances[node_name]
    # check initial state
    assert node.state == SupvisorsInstanceStates.UNKNOWN
    # invalidate node
    context.invalid(node, fence)
    # check new state
    assert node.state == new_state
    # restore node state
    node._state = SupvisorsInstanceStates.UNKNOWN


def test_invalid(mocker, context):
    """ Test the invalidation of a node. """
    # test node state with auto_fence
    mocker.patch.object(context.supvisors.options, 'auto_fence', True)
    # test node state with auto_fence and local_identifier
    check_invalid_node_status(context, '127.0.0.1', SupvisorsInstanceStates.SILENT)
    check_invalid_node_status(context, '127.0.0.1', SupvisorsInstanceStates.SILENT, True)
    # test node state with auto_fence and other than local_identifier
    check_invalid_node_status(context, '10.0.0.1', SupvisorsInstanceStates.ISOLATING)
    check_invalid_node_status(context, '10.0.0.1', SupvisorsInstanceStates.ISOLATING, True)
    # test node state without auto_fence
    mocker.patch.object(context.supvisors.options, 'auto_fence', False)
    # test node state without auto_fence and local_identifier
    check_invalid_node_status(context, '127.0.0.1', SupvisorsInstanceStates.SILENT)
    check_invalid_node_status(context, '127.0.0.1', SupvisorsInstanceStates.SILENT, True)
    # test node state without auto_fence and other than local_identifier
    check_invalid_node_status(context, '10.0.0.2', SupvisorsInstanceStates.SILENT)
    check_invalid_node_status(context, '10.0.0.2', SupvisorsInstanceStates.ISOLATING, True)


def test_get_managed_applications(filled_context):
    """ Test getting all managed applications. """
    # in this test, all applications are managed by default
    expected = ['crash', 'firefox', 'sample_test_1', 'sample_test_2']
    assert sorted(filled_context.get_managed_applications().keys()) == expected
    # unmanage a few ones
    filled_context.applications['firefox'].rules.managed = False
    filled_context.applications['sample_test_1'].rules.managed = False
    # re-test
    assert sorted(filled_context.get_managed_applications().keys()) == ['crash', 'sample_test_2']


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
    # add instances to one process
    process1 = next(process for application in filled_context.applications.values()
                    for process in application.processes.values()
                    if process.running())
    process1.running_identifiers.update(filled_context.instances.keys())
    # test conflict is detected
    assert filled_context.conflicting()
    assert filled_context.conflicts() == [process1]
    # add instances to one other process
    process2 = next(process for application in filled_context.applications.values()
                    for process in application.processes.values()
                    if process.stopped())
    process2.running_identifiers.update(filled_context.instances.keys())
    # test conflict is detected
    assert filled_context.conflicting()
    assert filled_context.conflicts() == [process1, process2]
    # empty instances of first process list
    process1.running_identifiers.clear()
    # test conflict is still detected
    assert filled_context.conflicting()
    assert filled_context.conflicts() == [process2]
    # empty instances of second process list
    process2.running_identifiers.clear()
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
    assert application1.rules.starting_failure_strategy == StartingFailureStrategies.ABORT
    assert application1.rules.running_failure_strategy == RunningFailureStrategies.CONTINUE
    # so patch load_application_rules to avoid that
    context.supvisors.parser.load_application_rules = load_application_rules
    # get application
    application1 = context.setdefault_application('dummy_1')
    # check application list. rules are not re-evaluated so application still not managed
    assert context.applications == {'dummy_1': application1}
    assert not application1.rules.managed
    assert application1.rules.starting_failure_strategy == StartingFailureStrategies.ABORT
    assert application1.rules.running_failure_strategy == RunningFailureStrategies.CONTINUE
    # get application
    application2 = context.setdefault_application('dummy_2')
    # check application list
    assert context.applications == {'dummy_1': application1, 'dummy_2': application2}
    assert application2.rules.managed
    assert application2.rules.starting_failure_strategy == StartingFailureStrategies.STOP
    assert application2.rules.running_failure_strategy == RunningFailureStrategies.RESTART_APPLICATION


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
    assert application1.rules.starting_failure_strategy == StartingFailureStrategies.ABORT
    assert application1.rules.running_failure_strategy == RunningFailureStrategies.CONTINUE
    assert process1.rules.starting_failure_strategy == StartingFailureStrategies.ABORT
    assert process1.rules.running_failure_strategy == RunningFailureStrategies.CONTINUE
    # so patch load_application_rules to avoid that
    context.supvisors.parser.load_application_rules = load_application_rules
    # get process
    process1 = context.setdefault_process(dummy_info1)
    # check application still unmanaged
    application1 = context.applications['dummy_application_1']
    assert not application1.rules.managed
    # no change on rules because application already exists
    assert application1.rules.starting_failure_strategy == StartingFailureStrategies.ABORT
    assert application1.rules.running_failure_strategy == RunningFailureStrategies.CONTINUE
    assert process1.rules.starting_failure_strategy == StartingFailureStrategies.ABORT
    assert process1.rules.running_failure_strategy == RunningFailureStrategies.CONTINUE
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
    assert application2.rules.starting_failure_strategy == StartingFailureStrategies.STOP
    assert application2.rules.running_failure_strategy == RunningFailureStrategies.RESTART_APPLICATION
    assert process2.rules.starting_failure_strategy == StartingFailureStrategies.STOP
    assert process2.rules.running_failure_strategy == RunningFailureStrategies.RESTART_APPLICATION


def test_load_processes(mocker, context):
    """ Test the storage of processes handled by Supervisor on a given node. """
    mocker.patch('supvisors.application.ApplicationStatus.update_sequences')
    mocker.patch('supvisors.application.ApplicationStatus.update_status')
    # check application list
    assert context.applications == {}
    for node in context.instances.values():
        assert node.processes == {}
    # load ProcessInfoDatabase in unknown node
    with pytest.raises(KeyError):
        context.load_processes('10.0.0.0', database_copy())
    assert context.applications == {}
    for node in context.instances.values():
        assert node.processes == {}
    # load ProcessInfoDatabase with known node
    context.load_processes('10.0.0.1', database_copy())
    # check context contents
    assert sorted(context.applications.keys()) == ['crash', 'firefox', 'sample_test_1', 'sample_test_2']
    assert sorted(context.applications['crash'].processes.keys()) == ['late_segv', 'segv']
    assert sorted(context.applications['firefox'].processes.keys()) == ['firefox']
    assert sorted(context.applications['sample_test_1'].processes.keys()) == ['xclock', 'xfontsel', 'xlogo']
    assert sorted(context.applications['sample_test_2'].processes.keys()) == ['sleep', 'yeux_00', 'yeux_01']
    assert sorted(context.instances['10.0.0.1'].processes.keys()) == ['crash:late_segv', 'crash:segv', 'firefox',
                                                                  'sample_test_1:xclock', 'sample_test_1:xfontsel',
                                                                  'sample_test_1:xlogo', 'sample_test_2:sleep',
                                                                  'sample_test_2:yeux_00', 'sample_test_2:yeux_01']
    assert context.instances['10.0.0.2'].processes == {}
    # check application calls
    assert all(application.update_sequences.called and application.update_status.called
               for application in context.applications.values())
    mocker.resetall()
    # load ProcessInfoDatabase in other known node
    context.load_processes('10.0.0.2', database_copy())
    # check context contents
    assert sorted(context.applications.keys()) == ['crash', 'firefox', 'sample_test_1', 'sample_test_2']
    assert sorted(context.applications['crash'].processes.keys()) == ['late_segv', 'segv']
    assert sorted(context.applications['firefox'].processes.keys()) == ['firefox']
    assert sorted(context.applications['sample_test_1'].processes.keys()) == ['xclock', 'xfontsel', 'xlogo']
    assert sorted(context.applications['sample_test_2'].processes.keys()) == ['sleep', 'yeux_00', 'yeux_01']
    assert sorted(context.instances['10.0.0.2'].processes.keys()) == ['crash:late_segv', 'crash:segv', 'firefox',
                                                                  'sample_test_1:xclock', 'sample_test_1:xfontsel',
                                                                  'sample_test_1:xlogo', 'sample_test_2:sleep',
                                                                  'sample_test_2:yeux_00', 'sample_test_2:yeux_01']
    assert context.instances['10.0.0.1'].processes == context.instances['10.0.0.2'].processes
    # check application calls
    assert all(application.update_sequences.called and application.update_status.called
               for application in context.applications.values())
    mocker.resetall()
    # load different database in other known node
    info = any_process_info()
    info.update({'group': 'dummy_application', 'name': 'dummy_process'})
    database = [info]
    context.load_processes('10.0.0.4', database)
    # check context contents
    assert sorted(context.applications.keys()) == ['crash', 'dummy_application', 'firefox',
                                                   'sample_test_1', 'sample_test_2']
    assert list(context.instances['10.0.0.4'].processes.keys()) == ['dummy_application:dummy_process']
    assert sorted(context.applications['crash'].processes.keys()) == ['late_segv', 'segv']
    assert sorted(context.applications['dummy_application'].processes.keys()) == ['dummy_process']
    assert sorted(context.applications['firefox'].processes.keys()) == ['firefox']
    assert sorted(context.applications['sample_test_1'].processes.keys()) == ['xclock', 'xfontsel', 'xlogo']
    assert sorted(context.applications['sample_test_2'].processes.keys()) == ['sleep', 'yeux_00', 'yeux_01']
    # check application calls
    assert all(application.update_sequences.called and application.update_status.called
               for application in context.applications.values())


def test_authorization(mocker, context):
    """ Test the handling of an authorization event. """
    # check no exception with unknown node
    context.on_authorization('10.0.0.0', True)
    # check no change with known node not in CHECKING state
    for fencing in [True, False]:
        context.supvisors.options.auto_fence = fencing
        for authorization in [True, False]:
            for state in SupvisorsInstanceStates:
                if state != SupvisorsInstanceStates.CHECKING:
                    context.instances['10.0.0.1']._state = state
                    context.on_authorization('10.0.0.1', authorization)
                    assert context.instances['10.0.0.1'].state == state
    # check state becomes RUNNING if authorized and current state is CHECKING
    for fencing in [True, False]:
        context.supvisors.options.auto_fence = fencing
        context.instances['10.0.0.2']._state = SupvisorsInstanceStates.CHECKING
        context.on_authorization('10.0.0.2', True)
        assert context.instances['10.0.0.2'].state == SupvisorsInstanceStates.RUNNING
    # check state becomes ISOLATING if not authorized and auto fencing activated
    context.supvisors.options.auto_fence = True
    context.instances['10.0.0.4']._state = SupvisorsInstanceStates.CHECKING
    context.on_authorization('10.0.0.4', False)
    assert context.instances['10.0.0.4'].state == SupvisorsInstanceStates.ISOLATING
    # check state becomes reciprocally ISOLATING if not authorized and auto fencing deactivated
    context.supvisors.options.auto_fence = False
    context.instances['10.0.0.4']._state = SupvisorsInstanceStates.CHECKING
    context.on_authorization('10.0.0.4', False)
    assert context.instances['10.0.0.4'].state == SupvisorsInstanceStates.ISOLATING


def test_on_tick_event(mocker, context):
    """ Test the handling of a timer event. """
    mocker.patch('supvisors.context.time', return_value=3600)
    mocked_check = context.supvisors.zmq.pusher.send_check_instance
    mocked_send = context.supvisors.zmq.publisher.send_instance_status
    # check no exception with unknown node
    context.on_tick_event('10.0.0.0', {})
    assert not mocked_check.called
    assert not mocked_send.called
    # check no processing as long as local node is not RUNNING
    assert context.supvisors.supvisors_mapper.local_identifier == '127.0.0.1'
    assert context.instances['127.0.0.1'].state == SupvisorsInstanceStates.UNKNOWN
    context.on_tick_event('10.0.0.1', {})
    assert not mocked_check.called
    assert not mocked_send.called
    # set local node state to RUNNING
    context.instances['127.0.0.1']._state = SupvisorsInstanceStates.RUNNING
    # get node status used for tests
    status = context.instances['10.0.0.1']
    assert status.sequence_counter == 0
    # check no change with known node in isolation
    for state in [SupvisorsInstanceStates.ISOLATING, SupvisorsInstanceStates.ISOLATED]:
        status._state = state
        context.on_tick_event('10.0.0.1', {})
        assert status.state == state
        assert not mocked_check.called
        assert not mocked_send.called
    # check that node is CHECKING and send_check_instance is called before node time is updated and node status is sent
    for state in [SupvisorsInstanceStates.UNKNOWN, SupvisorsInstanceStates.SILENT]:
        status._state = state
        context.on_tick_event('10.0.0.1', {'sequence_counter': 31, 'when': 1234})
        assert status.state == SupvisorsInstanceStates.CHECKING
        assert status.remote_time == 1234
        assert mocked_check.call_args_list == [call('10.0.0.1')]
        assert mocked_send.call_args_list == [call({'identifier': '10.0.0.1', 'node_name': '10.0.0.1', 'port': 65000,
                                                    'sequence_counter': 31, 'statecode': 1, 'statename': 'CHECKING',
                                                    'remote_time': 1234, 'local_time': 3600, 'loading': 0})]
        mocked_check.reset_mock()
        mocked_send.reset_mock()
    # check that node time is updated and node status is sent
    for state in [SupvisorsInstanceStates.CHECKING, SupvisorsInstanceStates.RUNNING]:
        status._state = state
        context.on_tick_event('10.0.0.1', {'sequence_counter': 57, 'when': 5678})
        assert status.state == state
        assert status.remote_time == 5678
        assert not mocked_check.called
        assert mocked_send.call_args_list == [call({'identifier': '10.0.0.1', 'node_name': '10.0.0.1', 'port': 65000,
                                                    'sequence_counter': 57,
                                                    'statecode': state.value, 'statename': state.name,
                                                    'remote_time': 5678, 'local_time': 3600, 'loading': 0})]
        mocked_send.reset_mock()
    # check that the node local_sequence_counter is forced to 0 when its sequence_counter is lower than expected
    status.sequence_counter = 102
    status._state = SupvisorsInstanceStates.RUNNING
    context.on_tick_event('10.0.0.1', {'sequence_counter': 2, 'when': 6789})
    assert status.state == SupvisorsInstanceStates.RUNNING
    assert status.local_sequence_counter == 0
    assert not mocked_check.called
    assert not mocked_send.called


def test_process_removed_event_unknown_node(context):
    """ Test the handling of a process removed event coming from an unknown node. """
    mocked_publisher = context.supvisors.zmq.publisher
    context.on_process_removed_event('10.0.0.0', {})
    assert not mocked_publisher.send_process_event.called
    assert not mocked_publisher.send_process_status.called
    assert not mocked_publisher.send_application_status.called


def test_process_removed_event_isolated_node(context):
    """ Test the handling of a process removed event coming from an isolated node. """
    mocked_publisher = context.supvisors.zmq.publisher
    # get node status used for tests
    node_status = context.instances['10.0.0.1']
    # check no change with known node in isolation
    for state in [SupvisorsInstanceStates.ISOLATING, SupvisorsInstanceStates.ISOLATED]:
        node_status._state = state
        context.on_process_removed_event('10.0.0.1', {})
        assert not mocked_publisher.send_process_state_event.called
        assert not mocked_publisher.send_process_status.called
        assert not mocked_publisher.send_application_status.called


def test_process_removed_event(mocker, context):
    """ Test the handling of a process removed event. """
    mocker.patch('supvisors.process.time', return_value=1234)
    mocked_publisher = context.supvisors.zmq.publisher
    # get node status used for tests
    node1 = context.instances['10.0.0.1']
    node2 = context.instances['10.0.0.2']
    # patch load_application_rules
    context.supvisors.parser.load_application_rules = load_application_rules
    # fill context with one process
    dummy_info = {'group': 'dummy_application', 'name': 'dummy_process', 'expected': True, 'state': 0,
                  'now': 1234, 'stop': 0, 'extra_args': '-h'}
    process = context.setdefault_process(dummy_info)
    process.add_info('10.0.0.1', dummy_info)
    process.add_info('10.0.0.2', dummy_info)
    application = context.applications['dummy_application']
    assert application.state == ApplicationStates.STOPPED
    # update sequences for the test
    application.rules.managed = True
    application.update_sequences()
    # payload for parameter
    dummy_event = {'group': 'dummy_application', 'name': 'dummy_process'}
    # check behaviour when not in RUNNING state
    for state in SupvisorsInstanceStates:
        if state != SupvisorsInstanceStates.RUNNING:
            node1._state = state
            context.on_process_removed_event('10.0.0.1', dummy_event)
            assert sorted(process.info_map.keys()) == ['10.0.0.1', '10.0.0.2']
            assert application.state == ApplicationStates.STOPPED
            assert not mocked_publisher.send_process_event.called
            assert not mocked_publisher.send_process_status.called
            assert not mocked_publisher.send_application_status.called
    # check normal behaviour in RUNNING state
    # as process will still include a definition on '10.0.0.2', no impact expected on process and application
    node1._state = SupvisorsInstanceStates.RUNNING
    node2._state = SupvisorsInstanceStates.RUNNING
    context.on_process_removed_event('10.0.0.1', dummy_event)
    assert process.state == ProcessStates.STOPPED
    assert sorted(process.info_map.keys()) == ['10.0.0.2']
    assert application.state == ApplicationStates.STOPPED
    assert mocked_publisher.send_process_event.call_args_list == \
           [call('10.0.0.1', {'group': 'dummy_application', 'name': 'dummy_process', 'state': -1})]
    assert not mocked_publisher.send_process_status.called
    assert not mocked_publisher.send_application_status.called
    mocked_publisher.send_process_event.reset_mock()
    # check normal behaviour in RUNNING state
    context.on_process_removed_event('10.0.0.2', dummy_event)
    assert process.state == ProcessStates.STOPPED
    assert list(process.info_map.keys()) == []
    assert application.state == ApplicationStates.STOPPED
    assert mocked_publisher.send_process_event.call_args_list == \
           [call('10.0.0.2', {'group': 'dummy_application', 'name': 'dummy_process', 'state': -1})]
    assert mocked_publisher.send_process_status.call_args_list == \
           [call({'application_name': 'dummy_application', 'process_name': 'dummy_process',
                  'statecode': -1, 'statename': 'DELETED', 'expected_exit': True,
                  'last_event_time': 1234, 'identifiers': [], 'extra_args': ''})]
    assert mocked_publisher.send_application_status.call_args_list == \
           [call({'application_name': 'dummy_application', 'managed': True, 'statecode': 0, 'statename': 'STOPPED',
                  'major_failure': False, 'minor_failure': False})]


def test_process_event_unknown_identifier(mocker, context):
    """ Test the handling of a process event coming from an unknown node. """
    mocker.patch('supvisors.process.time', return_value=1234)
    mocked_publisher = context.supvisors.zmq.publisher
    mocked_update_args = mocker.patch.object(context.supvisors.supervisor_data, 'update_extra_args')
    result = context.on_process_state_event('10.0.0.0', {})
    assert result is None
    assert not mocked_update_args.called
    assert not mocked_publisher.send_process_event.called
    assert not mocked_publisher.send_process_status.called
    assert not mocked_publisher.send_application_status.called


def test_process_event_isolated_instance(mocker, context):
    """ Test the handling of a process state event coming from an isolated node. """
    mocker.patch('supvisors.process.time', return_value=1234)
    mocked_publisher = context.supvisors.zmq.publisher
    mocked_update_args = mocker.patch.object(context.supvisors.supervisor_data, 'update_extra_args')
    # get node status used for tests
    node_status = context.instances['10.0.0.1']
    # check no change with known node in isolation
    for state in [SupvisorsInstanceStates.ISOLATING, SupvisorsInstanceStates.ISOLATED]:
        node_status._state = state
        result = context.on_process_state_event('10.0.0.1', {})
        assert result is None
        assert not mocked_update_args.called
        assert not mocked_publisher.send_process_state_event.called
        assert not mocked_publisher.send_process_status.called
        assert not mocked_publisher.send_application_status.called


def test_on_process_state_event(mocker, context):
    """ Test the handling of a process event. """
    mocker.patch('supvisors.process.time', return_value=1234)
    mocked_publisher = context.supvisors.zmq.publisher
    mocked_update_args = mocker.patch.object(context.supvisors.supervisor_data, 'update_extra_args')
    # get node status used for tests
    node = context.instances['10.0.0.1']
    # patch load_application_rules
    context.supvisors.parser.load_application_rules = load_application_rules
    # fill context with one process
    dummy_info = {'group': 'dummy_application', 'name': 'dummy_process', 'expected': True, 'state': 0,
                  'now': 1234, 'stop': 0, 'extra_args': '-h'}
    process = context.setdefault_process(dummy_info)
    process.add_info('10.0.0.1', dummy_info)
    application = context.applications['dummy_application']
    assert application.state == ApplicationStates.STOPPED
    # update sequences for the test
    application.rules.managed = True
    application.update_sequences()
    # payload for parameter
    dummy_event = {'group': 'dummy_application', 'name': 'dummy_process', 'state': 10, 'extra_args': '',
                   'now': 2345, 'stop': 0}
    # check behaviour when not in RUNNING state
    for state in SupvisorsInstanceStates:
        if state != SupvisorsInstanceStates.RUNNING:
            node._state = state
            assert context.on_process_state_event('10.0.0.1', dummy_event) is None
            assert not mocked_update_args.called
            assert not mocked_publisher.send_process_event.called
            assert not mocked_publisher.send_process_status.called
            assert not mocked_publisher.send_application_status.called
    # check normal behaviour in RUNNING state
    node._state = SupvisorsInstanceStates.RUNNING
    result = context.on_process_state_event('10.0.0.1', dummy_event)
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
                  'last_event_time': 1234, 'identifiers': ['10.0.0.1'], 'extra_args': ''})]
    assert mocked_publisher.send_application_status.call_args_list == \
           [call({'application_name': 'dummy_application', 'managed': True, 'statecode': 1, 'statename': 'STARTING',
                  'major_failure': False, 'minor_failure': False})]
    # reset mocks
    mocked_update_args.reset_mock()
    mocked_publisher.send_process_event.reset_mock()
    mocked_publisher.send_process_status.reset_mock()
    mocked_publisher.send_application_status.reset_mock()
    # check degraded behaviour with process to Supvisors but unknown to Supervisor (remote program)
    # basically same check as previous, just being confident that no exception is raised by the method
    mocked_update_args.side_effect = KeyError
    result = context.on_process_state_event('10.0.0.1', dummy_event)
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
                  'last_event_time': 1234, 'identifiers': ['10.0.0.1'], 'extra_args': ''})]
    assert mocked_publisher.send_application_status.call_args_list == \
           [call({'application_name': 'dummy_application', 'managed': True, 'statecode': 1, 'statename': 'STARTING',
                  'major_failure': False, 'minor_failure': False})]
    # reset mocks
    mocked_update_args.reset_mock()
    mocked_publisher.send_process_event.reset_mock()
    mocked_publisher.send_process_status.reset_mock()
    mocked_publisher.send_application_status.reset_mock()
    # check normal behaviour with known process and forced state event
    dummy_forced_event = {'group': 'dummy_application', 'name': 'dummy_process', 'state': ProcessStates.RUNNING,
                          'forced_state': ProcessStates.FATAL, 'identifier': '10.0.0.1',
                          'extra_args': '-h', 'now': 2345, 'pid': 0, 'expected': False, 'spawnerr': 'ouch'}
    result = context.on_process_state_event('10.0.0.1', dummy_forced_event)
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
                  'last_event_time': 1234, 'identifiers': ['10.0.0.1'], 'extra_args': ''})]
    assert mocked_publisher.send_application_status.call_args_list == \
           [call({'application_name': 'dummy_application', 'managed': True, 'statecode': 0, 'statename': 'STOPPED',
                  'major_failure': False, 'minor_failure': True})]


def test_on_timer_event(mocker, context):
    """ Test the handling of a timer event. """
    mocked_send = context.supvisors.zmq.publisher.send_instance_status
    # update context instances
    context.instances['127.0.0.1'].__dict__.update({'_state': SupvisorsInstanceStates.RUNNING,
                                                    'local_sequence_counter': 31})
    context.instances['10.0.0.1'].__dict__.update({'_state': SupvisorsInstanceStates.RUNNING,
                                                   'local_sequence_counter': 30})
    context.instances['10.0.0.2'].__dict__.update({'_state': SupvisorsInstanceStates.RUNNING,
                                                   'local_sequence_counter': 29})
    context.instances['10.0.0.3'].__dict__.update({'_state': SupvisorsInstanceStates.SILENT,
                                                   'local_sequence_counter': 10})
    context.instances['10.0.0.4'].__dict__.update({'_state': SupvisorsInstanceStates.ISOLATING,
                                                   'local_sequence_counter': 0})
    context.instances['10.0.0.5'].__dict__.update({'_state': SupvisorsInstanceStates.UNKNOWN,
                                                   'local_sequence_counter': 0})
    # update context applications
    application_1 = Mock()
    context.applications['dummy_application'] = application_1
    # patch the expected future invalidated node
    proc_1 = Mock(rules=Mock(expected_load=3), **{'invalidate_identifier.return_value': False})
    proc_2 = Mock(application_name='dummy_application', rules=Mock(expected_load=12),
                  **{'invalidate_identifier.return_value': True})
    mocker.patch.object(context.instances['10.0.0.2'], 'running_processes', return_value=[proc_1, proc_2])
    # test when start_date is recent
    context.start_date = 3590
    assert context.on_timer_event({'sequence_counter': 31, 'when': 3600}) == ([], set())
    assert context.local_sequence_counter == 31
    assert not mocked_send.called
    assert not proc_1.invalidate_node.called
    assert not proc_2.invalidate_node.called
    assert context.instances['10.0.0.5'].state == SupvisorsInstanceStates.UNKNOWN
    # test when synchro_timeout has passed
    context.start_date = 3589
    assert context.on_timer_event({'sequence_counter': 32, 'when': 3600}) == (['10.0.0.2'], {proc_2})
    assert context.local_sequence_counter == 32
    assert context.instances['10.0.0.5'].state == SupvisorsInstanceStates.ISOLATING
    assert mocked_send.call_args_list == [call({'identifier': '10.0.0.2', 'node_name': '10.0.0.2', 'port': 65000,
                                                'statecode': 4, 'statename': 'ISOLATING',
                                                'remote_time': 0, 'local_time': 0, 'loading': 15,
                                                'sequence_counter': 0}),
                                          call({'identifier': '10.0.0.5', 'node_name': '10.0.0.5', 'port': 65000,
                                                'statecode': 4, 'statename': 'ISOLATING',
                                                'remote_time': 0, 'local_time': 0, 'loading': 0,
                                                'sequence_counter': 0})]
    assert proc_2.invalidate_identifier.call_args_list == [call('10.0.0.2')]
    assert application_1.update_status.call_args_list == [call()]
    # only '10.0.0.2' and '10.0.0.5' instances changed state
    for identifier, state in [('127.0.0.1', SupvisorsInstanceStates.RUNNING),
                              ('10.0.0.1', SupvisorsInstanceStates.RUNNING),
                              ('10.0.0.2', SupvisorsInstanceStates.ISOLATING),
                              ('10.0.0.3', SupvisorsInstanceStates.SILENT),
                              ('10.0.0.4', SupvisorsInstanceStates.ISOLATING),
                              ('10.0.0.5', SupvisorsInstanceStates.ISOLATING)]:
        assert context.instances[identifier].state == state


def test_handle_isolation(mocker, context):
    """ Test the isolation of instances. """
    mocked_send = mocker.patch.object(context.supvisors.zmq.publisher, 'send_instance_status')
    # update node states
    context.instances['127.0.0.1']._state = SupvisorsInstanceStates.CHECKING
    context.instances['10.0.0.1']._state = SupvisorsInstanceStates.RUNNING
    context.instances['10.0.0.2']._state = SupvisorsInstanceStates.SILENT
    context.instances['10.0.0.3']._state = SupvisorsInstanceStates.ISOLATED
    context.instances['10.0.0.4']._state = SupvisorsInstanceStates.ISOLATING
    context.instances['10.0.0.5']._state = SupvisorsInstanceStates.ISOLATING
    # call method and check result
    assert context.handle_isolation() == ['10.0.0.4', '10.0.0.5']
    assert context.instances['127.0.0.1'].state == SupvisorsInstanceStates.CHECKING
    assert context.instances['10.0.0.1'].state == SupvisorsInstanceStates.RUNNING
    assert context.instances['10.0.0.2'].state == SupvisorsInstanceStates.SILENT
    assert context.instances['10.0.0.3'].state == SupvisorsInstanceStates.ISOLATED
    assert context.instances['10.0.0.4'].state == SupvisorsInstanceStates.ISOLATED
    assert context.instances['10.0.0.5'].state == SupvisorsInstanceStates.ISOLATED
    # check calls to publisher.send_instance_status
    assert mocked_send.call_args_list == [call({'identifier': '10.0.0.4', 'node_name': '10.0.0.4', 'port': 65000,
                                                'statecode': 5, 'statename': 'ISOLATED',
                                                'remote_time': 0, 'local_time': 0, 'loading': 0,
                                                'sequence_counter': 0}),
                                          call({'identifier': '10.0.0.5', 'node_name': '10.0.0.5', 'port': 65000,
                                                'statecode': 5, 'statename': 'ISOLATED',
                                                'remote_time': 0, 'local_time': 0, 'loading': 0,
                                                'sequence_counter': 0})]
