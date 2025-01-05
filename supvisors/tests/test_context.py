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
from unittest.mock import call, Mock

import pytest
from supervisor.process import ProcessStates

from supvisors.context import *
from supvisors.external_com import EventPublisherInterface
from supvisors.instancestatus import SupvisorsInstanceId
from supvisors.ttypes import (SupvisorsInstanceStates, ApplicationStates, SupvisorsStates,
                              StartingFailureStrategies, RunningFailureStrategies)
from .base import database_copy, any_process_info
from .conftest import create_application, create_process


@pytest.fixture
def context(supvisors_instance):
    """ Return the instance to test. """
    return Context(supvisors_instance)


def load_application_rules(_, rules):
    """ Simple Parser.load_application_rules behaviour to avoid setdefault_process to always return None. """
    rules.managed = True
    rules.starting_failure_strategy = StartingFailureStrategies.STOP
    rules.running_failure_strategy = RunningFailureStrategies.RESTART_APPLICATION


@pytest.fixture
def filled_context(supvisors_instance, context):
    """ Push ProcessInfoDatabase process info in SupvisorsInstanceStatus. """
    supvisors_instance.parser.load_application_rules = load_application_rules
    for info in database_copy():
        identifier = random.choice(list(context.instances.keys()))
        process = context.setdefault_process(identifier, info)
        context.instances[identifier].add_process(process)
    return context


def test_create(supvisors_instance, context):
    """ Test the values set at construction of Context. """
    assert supvisors_instance is context.supvisors
    assert supvisors_instance.logger is context.logger
    assert set(supvisors_instance.mapper.instances.keys()), set(context.instances.keys())
    for identifier, instance_status in context.instances.items():
        assert instance_status.identifier == identifier
        assert isinstance(instance_status, SupvisorsInstanceStatus)
    assert context.local_identifier == '10.0.0.1:25000'
    assert context.local_status == context.instances['10.0.0.1:25000']
    assert context.applications == {}
    assert context.master_identifier == ''
    assert not context.is_master
    assert context.master_instance is None
    assert context.start_date == 0.0
    assert context.uptime > 0.0


def test_master_identifier(supvisors_instance, context):
    """ Test the access to master identifier. """
    local_identifier = supvisors_instance.mapper.local_identifier
    assert context.master_identifier == ''
    assert not context.is_master
    assert context.master_instance is None
    # set remote instance as Master
    supvisors_instance.state_modes.master_identifier = '10.0.0.2:25000'
    assert context.master_identifier == '10.0.0.2:25000'
    assert not context.is_master
    assert context.master_instance is context.instances['10.0.0.2:25000']
    # set local instance as Master
    supvisors_instance.state_modes.master_identifier = local_identifier
    assert context.master_identifier == local_identifier
    assert context.is_master
    assert context.master_instance is context.local_status


def test_is_valid(context):
    """ Test the Context.is_valid method. """
    # change states
    context.instances['10.0.0.1:25000']._state = SupvisorsInstanceStates.STOPPED
    context.instances['10.0.0.2:25000']._state = SupvisorsInstanceStates.CHECKING
    context.instances['10.0.0.3:25000']._state = SupvisorsInstanceStates.ISOLATED
    context.instances['10.0.0.4:25000']._state = SupvisorsInstanceStates.RUNNING
    # test unknown identifier
    assert not context.is_valid('rocky52', 'rocky52:6000', ('192.168.1.2', 1234))
    # test known identifier but isolated
    assert not context.is_valid('10.0.0.3:25000', '10.0.0.3', ('10.0.0.3', 1234))
    # test known identifier, not isolated but with wrong IP address
    assert not context.is_valid('10.0.0.1:25000', '10.0.0.1', ('192.168.1.2', 1234))
    assert not context.is_valid('10.0.0.4:25000', '10.0.0.4', ('192.168.1.2', 1234))
    # test known identifier not isolated, with correct IP address and incorrect HTTP port
    assert not context.is_valid('10.0.0.1:25000', '10.0.0.1', ('10.0.0.1', 1234))
    assert not context.is_valid('10.0.0.4:25000', '10.0.0.4', ('10.0.0.4', 1234))
    # test known identifier not isolated, with correct IP address and HTTP port
    assert context.is_valid('10.0.0.1:25000', '10.0.0.1', ('10.0.0.1', 25000))
    assert context.is_valid('10.0.0.4:25000', '10.0.0.4', ('10.0.0.4', 25000))


def test_get_nodes_load(mocker, context):
    """ Test the Context.get_nodes_load method. """
    # empty test
    assert context.get_nodes_load() == {'01:23:45:67:89:ab': 0, 'ab:cd:ef:01:23:45': 0}
    # update context for some values
    mocker.patch.object(context.instances['10.0.0.2:25000'], 'get_load', return_value=8)
    mocker.patch.object(context.instances['10.0.0.1:25000'], 'get_load', return_value=5)
    mocker.patch.object(context.instances['10.0.0.3:25000'], 'get_load', return_value=5)
    assert context.get_nodes_load() == {'01:23:45:67:89:ab': 10, 'ab:cd:ef:01:23:45': 8}


def test_initial_running(supvisors_instance, context):
    """ Test the check of initial Supvisors instances running. """
    # update mapper
    supvisors_instance.mapper.initial_identifiers = ['10.0.0.1:25000', '10.0.0.2:25000', '10.0.0.3:25000']
    assert not context.initial_running()
    # add some RUNNING
    context.local_status._state = SupvisorsInstanceStates.RUNNING
    context.instances['10.0.0.1:25000']._state = SupvisorsInstanceStates.RUNNING
    context.instances['10.0.0.2:25000']._state = SupvisorsInstanceStates.RUNNING
    context.instances['10.0.0.4:25000']._state = SupvisorsInstanceStates.RUNNING
    assert not context.initial_running()
    # add some RUNNING so that all initial instances are RUNNING
    context.instances['10.0.0.3:25000']._state = SupvisorsInstanceStates.RUNNING
    assert context.initial_running()
    # set all RUNNING
    for instance in context.instances.values():
        instance._state = SupvisorsInstanceStates.RUNNING
    assert context.initial_running()


def test_all_running(context):
    """ Test the check of all Supvisors instances running. """
    assert not context.all_running()
    # add some RUNNING
    context.local_status._state = SupvisorsInstanceStates.RUNNING
    context.instances['10.0.0.1:25000']._state = SupvisorsInstanceStates.RUNNING
    context.instances['10.0.0.2:25000']._state = SupvisorsInstanceStates.RUNNING
    context.instances['10.0.0.4:25000']._state = SupvisorsInstanceStates.RUNNING
    assert not context.all_running()
    # set all RUNNING
    for instance in context.instances.values():
        instance._state = SupvisorsInstanceStates.RUNNING
    assert context.all_running()


def test_instances_by_states(supvisors_instance, context):
    """ Test the access to instances in unknown state. """
    # test initial states
    all_instances = sorted(supvisors_instance.mapper.instances.keys())
    assert not context.all_running()
    assert context.running_identifiers() == []
    assert context.isolated_identifiers() == []
    assert sorted(context.valid_identifiers()) == all_instances
    assert sorted(context.isolated_identifiers() + context.valid_identifiers()) == all_instances
    assert context.identifiers_by_states([SupvisorsInstanceStates.RUNNING, SupvisorsInstanceStates.ISOLATED]) == []
    assert sorted(context.identifiers_by_states([SupvisorsInstanceStates.STOPPED])) == all_instances
    # change states
    context.instances['10.0.0.1:25000']._state = SupvisorsInstanceStates.RUNNING
    context.instances['10.0.0.2:25000']._state = SupvisorsInstanceStates.CHECKING
    context.instances['10.0.0.3:25000']._state = SupvisorsInstanceStates.ISOLATED
    context.instances['10.0.0.4:25000']._state = SupvisorsInstanceStates.STOPPED
    context.instances['10.0.0.5:25000']._state = SupvisorsInstanceStates.FAILED
    context.instances['10.0.0.6:25000']._state = SupvisorsInstanceStates.CHECKED
    # test new states
    assert not context.all_running()
    assert context.running_identifiers() == ['10.0.0.1:25000']
    assert context.isolated_identifiers() == ['10.0.0.3:25000']
    assert sorted(context.valid_identifiers()) == sorted(['10.0.0.1:25000', '10.0.0.2:25000', '10.0.0.4:25000',
                                                          '10.0.0.5:25000', '10.0.0.6:25000'])
    assert sorted(context.isolated_identifiers() + context.valid_identifiers()) == all_instances
    assert context.identifiers_by_states([SupvisorsInstanceStates.RUNNING,
                                          SupvisorsInstanceStates.ISOLATED]) == ['10.0.0.1:25000', '10.0.0.3:25000']
    assert context.identifiers_by_states([SupvisorsInstanceStates.STOPPED]) == ['10.0.0.4:25000']

def test_activate_checked(context):
    """ Test the activation of checked Supvisors instances. """
    # change node states
    context.instances['10.0.0.1:25000']._state = SupvisorsInstanceStates.STOPPED
    context.instances['10.0.0.2:25000']._state = SupvisorsInstanceStates.FAILED
    context.instances['10.0.0.3:25000']._state = SupvisorsInstanceStates.ISOLATED
    context.instances['10.0.0.4:25000']._state = SupvisorsInstanceStates.CHECKED
    context.instances['10.0.0.5:25000']._state = SupvisorsInstanceStates.CHECKING
    # check status after call to activate_checked
    context.activate_checked()
    assert context.instances['10.0.0.1:25000'].state == SupvisorsInstanceStates.STOPPED
    assert context.instances['10.0.0.2:25000'].state == SupvisorsInstanceStates.FAILED
    assert context.instances['10.0.0.3:25000'].state == SupvisorsInstanceStates.ISOLATED
    assert context.instances['10.0.0.4:25000'].state == SupvisorsInstanceStates.RUNNING
    assert context.instances['10.0.0.5:25000'].state == SupvisorsInstanceStates.CHECKING


def test_invalidate_local(mocker, supvisors_instance, context):
    """ Test the invalidation of the local Supvisors instance. """
    mocked_export = mocker.patch.object(context, 'export_status')
    # get context
    status = context.local_status
    # set Master
    supvisors_instance.state_modes.master_identifier = '10.0.0.2:25000'
    # same result whatever the fence parameter, auto_fence option, Supvisors state and self FSM state
    for fence in [True, False]:
        for auto_fence in [True, False]:
            for supvisors_state in SupvisorsStates:
                # invalidate may be called from CHECKING or FAILED only or there will be an InvalidTransition exception
                for state in [SupvisorsInstanceStates.CHECKING, SupvisorsInstanceStates.FAILED]:
                    # set context
                    supvisors_instance.options.auto_fence = auto_fence
                    supvisors_instance.state_modes.master_state_modes.state = supvisors_state
                    status._state = state
                    # call for invalidation
                    context.invalidate(status, fence)
                    assert status.state == SupvisorsInstanceStates.STOPPED
                    # check publication
                    assert mocked_export.call_args_list == [call(status)]
                    mocked_export.reset_mock()


def test_invalidate_remote(supvisors_instance, context):
    """ Test the invalidation of a remote Supvisors instance.
    Publication is not tested here as already done in test_invalid_local. """
    assert supvisors_instance.external_publisher is None
    # check default context
    status = context.instances['10.0.0.2:25000']
    sm = supvisors_instance.state_modes.instance_state_modes['10.0.0.2:25000']
    assert supvisors_instance.state_modes.state == SupvisorsStates.OFF
    assert sm.state == SupvisorsStates.OFF
    # with this context, only the fence parameter makes a difference
    for fence in [True, False]:
        for auto_fence in [True, False]:
            # invalidate may be called from CHECKING or FAILED only or there will be an InvalidTransition exception
            for state in [SupvisorsInstanceStates.CHECKING, SupvisorsInstanceStates.FAILED]:
                # set context
                supvisors_instance.options.auto_fence = auto_fence
                status._state = state
                # call for invalidation
                context.invalidate(status, fence)
                assert status.state == (SupvisorsInstanceStates.ISOLATED if fence else SupvisorsInstanceStates.STOPPED)
    # set Master
    supvisors_instance.state_modes.master_identifier = '10.0.0.2:25000'
    # fence impact has been checked
    # test auto_fence option not set / no isolation
    supvisors_instance.options.auto_fence = False
    for supvisors_state in SupvisorsStates:
        for state in [SupvisorsInstanceStates.CHECKING, SupvisorsInstanceStates.FAILED]:
            # set context
            supvisors_instance.state_modes.master_state_modes.state = supvisors_state
            status._state = state
            # call for invalidation
            context.invalidate(status, fence)
            assert status.state == SupvisorsInstanceStates.STOPPED
            # reset the Master because it is cancelled when not RUNNING anymore
            supvisors_instance.state_modes.master_identifier = '10.0.0.2:25000'
    # test auto_fence option set / isolation made if Supvisors is in a working state
    supvisors_instance.options.auto_fence = True
    for supvisors_state in SupvisorsStates:
        working_state = supvisors_state in WORKING_STATES
        for state in [SupvisorsInstanceStates.CHECKING, SupvisorsInstanceStates.FAILED]:
            # set context
            supvisors_instance.state_modes.master_state_modes.state = supvisors_state
            status._state = state
            # call for invalidation
            context.invalidate(status, fence)
            assert status.state == (SupvisorsInstanceStates.ISOLATED if working_state
                                    else SupvisorsInstanceStates.STOPPED)
            # reset the Master because it is cancelled when not RUNNING anymore
            supvisors_instance.state_modes.master_identifier = '10.0.0.2:25000'




def test_invalidate_failed(mocker, supvisors_instance, context):
    """ Test the handling of FAILED instances. """
    mocked_publish = mocker.patch.object(context, 'publish_process_failures')
    supvisors_instance.external_publisher = Mock()
    # update context instances
    context.instances['10.0.0.1:25000']._state = SupvisorsInstanceStates.RUNNING
    context.instances['10.0.0.2:25000']._state = SupvisorsInstanceStates.CHECKED
    context.instances['10.0.0.3:25000']._state = SupvisorsInstanceStates.STOPPED
    context.instances['10.0.0.4:25000']._state = SupvisorsInstanceStates.CHECKING
    context.instances['10.0.0.5:25000']._state = SupvisorsInstanceStates.FAILED
    context.instances['10.0.0.6:25000']._state = SupvisorsInstanceStates.ISOLATED
    # patch the expected future invalidated node
    proc_1 = Mock(rules=Mock(expected_load=3), **{'invalidate_identifier.return_value': False})
    proc_2 = Mock(rules=Mock(expected_load=12), **{'invalidate_identifier.return_value': True})
    mocker.patch.object(context.instances['10.0.0.5:25000'], 'running_processes', return_value=[proc_1, proc_2])
    # test when synchro_timeout has passed
    assert context.invalidate_failed() == (['10.0.0.5:25000'], {proc_2})
    expected_1 = {'identifier': '10.0.0.5:25000', 'nick_identifier': '10.0.0.5',
                  'node_name': '10.0.0.5', 'port': 25000,
                  'statecode': 0, 'statename': 'STOPPED',
                  'remote_sequence_counter': 0, 'remote_mtime': 0.0, 'remote_time': 0,
                  'local_sequence_counter': 0, 'local_mtime': 0.0, 'local_time': 0,
                  'loading': 15, 'process_failure': False}
    assert supvisors_instance.external_publisher.send_instance_status.call_args_list == [call(expected_1)]
    assert proc_1.invalidate_identifier.call_args_list == [call('10.0.0.5:25000')]
    assert proc_2.invalidate_identifier.call_args_list == [call('10.0.0.5:25000')]
    assert mocked_publish.call_args_list == [call({proc_2})]


def test_export_status(supvisors_instance, context):
    """ Test the Context.export_status method. """
    # test with no external publisher
    supvisors_instance.external_publisher = None
    context.export_status(context.local_status)
    # test with external publisher
    supvisors_instance.external_publisher = Mock()
    context.export_status(context.local_status)
    expected = {'identifier': context.local_identifier,
                'nick_identifier': context.local_status.supvisors_id.nick_identifier,
                'node_name': context.local_status.supvisors_id.host_id,
                'port': 25000, 'statecode': 0, 'statename': 'STOPPED',
                'remote_sequence_counter': 0, 'remote_mtime': 0, 'remote_time': 0,
                'local_sequence_counter': 0, 'local_mtime': 0.0, 'local_time': 0,
                'loading': 0, 'process_failure': False}
    assert context.external_publisher.send_instance_status.call_args_list == [call(expected)]


def test_get_managed_applications(filled_context):
    """ Test getting all managed applications. """
    # in this test, all applications are managed by default
    expected = ['crash', 'firefox', 'sample_test_1', 'sample_test_2']
    assert sorted(filled_context.get_managed_applications().keys()) == expected
    # de-manage a few ones
    filled_context.applications['firefox'].rules.managed = False
    filled_context.applications['sample_test_1'].rules.managed = False
    # re-test
    assert sorted(filled_context.get_managed_applications().keys()) == ['crash', 'sample_test_2']


def test_is_namespec(filled_context):
    """ Test checking if namespec is known across all supvisors instances. """
    assert filled_context.is_namespec('crash:late_segv')
    assert filled_context.is_namespec('firefox')
    assert filled_context.is_namespec('firefox:firefox')
    assert filled_context.is_namespec('sample_test_1:*')
    assert filled_context.is_namespec('sample_test_2:')
    assert not filled_context.is_namespec('sample_test_2:yeux')
    assert not filled_context.is_namespec('sample_test_2:yeux_03')
    assert not filled_context.is_namespec('sleep')


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


def test_find_runnable_processes(filled_context):
    """ Test getting all processes that are not running and whose namespec matches a regex. """
    all_stopped_namespecs = ['firefox', 'sample_test_1:xclock', 'sample_test_1:xlogo',
                             'sample_test_2:sleep', 'sample_test_2:yeux_00']
    # use regex that returns everything
    processes = filled_context.find_runnable_processes('')
    assert sorted([process.namespec for process in processes]) == all_stopped_namespecs
    processes = filled_context.find_runnable_processes('^.*$')
    assert sorted([process.namespec for process in processes]) == all_stopped_namespecs
    # use regex that returns a selection
    processes = filled_context.find_runnable_processes(':x')
    assert sorted([process.namespec for process in processes]) == ['sample_test_1:xclock', 'sample_test_1:xlogo']
    processes = filled_context.find_runnable_processes('[ox]$')
    assert sorted([process.namespec for process in processes]) == ['firefox', 'sample_test_1:xlogo']


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


def test_setdefault_application(supvisors_instance, context):
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
    supvisors_instance.parser.load_application_rules = load_application_rules
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


def test_setdefault_process(supvisors_instance, context):
    """ Test the access / creation of a process status. """
    # check application list
    assert context.applications == {}
    # test data
    dummy_info1 = any_process_info()
    dummy_info1.update({'group': 'dummy_application_1', 'name': 'dummy_process_1'})
    dummy_info2 = any_process_info()
    dummy_info2.update({'group': 'dummy_application_2', 'name': 'dummy_process_2'})
    # in this test, there is no rules file so application rules managed won't be changed by load_application_rules
    process1 = context.setdefault_process('10.0.0.1:25000', dummy_info1)
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
    supvisors_instance.parser.load_application_rules = load_application_rules
    # get process
    process1 = context.setdefault_process('10.0.0.1:25000', dummy_info1)
    # check application still unmanaged
    application1 = context.applications['dummy_application_1']
    assert not application1.rules.managed
    # no change on rules because application already exists
    assert application1.rules.starting_failure_strategy == StartingFailureStrategies.ABORT
    assert application1.rules.running_failure_strategy == RunningFailureStrategies.CONTINUE
    assert process1.rules.starting_failure_strategy == StartingFailureStrategies.ABORT
    assert process1.rules.running_failure_strategy == RunningFailureStrategies.CONTINUE
    # get application
    process2 = context.setdefault_process('10.0.0.1:25000', dummy_info2)
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


def test_load_processes(mocker, supvisors_instance, context):
    """ Test the storage of processes handled by Supervisor on a given node. """
    mocker.patch('supvisors.application.ApplicationStatus.update_sequences')
    mocker.patch('supvisors.application.ApplicationStatus.update')
    status_10001 = context.instances['10.0.0.1:25000']
    status_10002 = context.instances['10.0.0.2:25000']
    status_10004 = context.instances['10.0.0.4:25000']
    # check application list
    assert context.applications == {}
    for node in context.instances.values():
        assert node.processes == {}
    # force local_identifier
    supvisors_instance.mapper.local_identifier = '10.0.0.2:25000'
    status_10001._state = SupvisorsInstanceStates.CHECKING
    # known node but empty database due to a failure in CHECKING state
    context.load_processes(status_10001, None)
    assert status_10001.state == SupvisorsInstanceStates.STOPPED
    assert context.applications == {}
    for node in context.instances.values():
        assert node.processes == {}
    # load ProcessInfoDatabase with known node
    context.load_processes(status_10001, database_copy())
    # check context contents
    assert sorted(context.applications.keys()) == ['crash', 'firefox', 'sample_test_1', 'sample_test_2']
    assert sorted(context.applications['crash'].processes.keys()) == ['late_segv', 'segv']
    assert sorted(context.applications['firefox'].processes.keys()) == ['firefox']
    assert sorted(context.applications['sample_test_1'].processes.keys()) == ['xclock', 'xfontsel', 'xlogo']
    assert sorted(context.applications['sample_test_2'].processes.keys()) == ['sleep', 'yeux_00', 'yeux_01']
    assert sorted(status_10001.processes.keys()) == ['crash:late_segv', 'crash:segv', 'firefox',
                                                     'sample_test_1:xclock', 'sample_test_1:xfontsel',
                                                     'sample_test_1:xlogo', 'sample_test_2:sleep',
                                                     'sample_test_2:yeux_00', 'sample_test_2:yeux_01']
    assert status_10002.processes == {}
    # check application calls
    assert all(application.update_sequences.called and application.update.called
               for application in context.applications.values())
    mocker.resetall()
    # load ProcessInfoDatabase in other known node
    context.load_processes(status_10002, database_copy())
    # check context contents
    assert sorted(context.applications.keys()) == ['crash', 'firefox', 'sample_test_1', 'sample_test_2']
    assert sorted(context.applications['crash'].processes.keys()) == ['late_segv', 'segv']
    assert sorted(context.applications['firefox'].processes.keys()) == ['firefox']
    assert sorted(context.applications['sample_test_1'].processes.keys()) == ['xclock', 'xfontsel', 'xlogo']
    assert sorted(context.applications['sample_test_2'].processes.keys()) == ['sleep', 'yeux_00', 'yeux_01']
    expected = ['crash:late_segv', 'crash:segv', 'firefox', 'sample_test_1:xclock', 'sample_test_1:xfontsel',
                'sample_test_1:xlogo', 'sample_test_2:sleep', 'sample_test_2:yeux_00', 'sample_test_2:yeux_01']
    assert sorted(status_10002.processes.keys()) == expected
    assert status_10001.processes == status_10002.processes
    # check application calls
    assert all(application.update_sequences.called and application.update.called
               for application in context.applications.values())
    mocker.resetall()
    # load different database in other known node
    info = any_process_info()
    info.update({'group': 'dummy_application', 'name': 'dummy_process'})
    database = [info]
    context.load_processes(status_10004, database)
    # check context contents
    assert sorted(context.applications.keys()) == ['crash', 'dummy_application', 'firefox',
                                                   'sample_test_1', 'sample_test_2']
    assert list(status_10004.processes.keys()) == ['dummy_application:dummy_process']
    assert sorted(context.applications['crash'].processes.keys()) == ['late_segv', 'segv']
    assert sorted(context.applications['dummy_application'].processes.keys()) == ['dummy_process']
    assert sorted(context.applications['firefox'].processes.keys()) == ['firefox']
    assert sorted(context.applications['sample_test_1'].processes.keys()) == ['xclock', 'xfontsel', 'xlogo']
    assert sorted(context.applications['sample_test_2'].processes.keys()) == ['sleep', 'yeux_00', 'yeux_01']
    # check application calls
    assert all(application.update_sequences.called and application.update.called
               for application in context.applications.values())


def test_publish_process_failures(supvisors_instance, context):
    """ Test the publication of processes in failure. """
    # update context applications
    application_1_serial = {'application_name': 'dummy_application_1',
                            'statename': 'RUNNING'}
    application_2_serial = {'application_name': 'dummy_application_2',
                            'statename': 'STOPPED'}
    application_3_serial = {'application_name': 'dummy_application_3',
                            'statename': 'STOPPING'}
    application_1 = Mock(application_name='dummy_application_1', **{'serial.return_value': application_1_serial})
    application_2 = Mock(application_name='dummy_application_2', **{'serial.return_value': application_2_serial})
    application_3 = Mock(application_name='dummy_application_3', **{'serial.return_value': application_3_serial})
    context.applications = {'dummy_application_1': application_1,
                            'dummy_application_2': application_2,
                            'dummy_application_3': application_3}
    # patch the expected future invalidated node
    proc_1_serial = {'application_name': 'dummy_application_1',
                     'process_name': 'proc_1'}
    proc_2_serial = {'application_name': 'dummy_application_3',
                     'process_name': 'proc_2'}
    proc_1 = Mock(application_name='dummy_application_1', **{'serial.return_value': proc_1_serial})
    proc_2 = Mock(application_name='dummy_application_3', **{'serial.return_value': proc_2_serial})
    # test with no external publisher set
    assert supvisors_instance.external_publisher is None
    context.publish_process_failures({proc_2, proc_1})
    assert application_1.update.call_args_list == [call()]
    assert not application_2.update.called
    assert application_3.update.call_args_list == [call()]
    application_1.update.reset_mock()
    application_3.update.reset_mock()
    # test with external publisher set
    supvisors_instance.external_publisher = Mock(spec=EventPublisherInterface)
    context.publish_process_failures([proc_2, proc_1])
    assert application_1.update.call_args_list == [call()]
    assert not application_2.update.called
    assert application_3.update.call_args_list == [call()]
    assert supvisors_instance.external_publisher.send_process_status.call_args_list == [call(proc_2_serial),
                                                                                        call(proc_1_serial)]
    supvisors_instance.external_publisher.send_application_status.assert_has_calls([call(application_3_serial),
                                                                                    call(application_1_serial)],
                                                                                   any_order=True)


def test_check_process(mocker, supvisors_instance, context):
    """ Test the Context.check_process method with expected context. """
    event = {'group': 'dummy_appli', 'name': 'dummy_process'}
    # test with unknown application
    assert context.check_process(context.instances['10.0.0.1:25000'], event) is None
    mocker.resetall()
    # test with unknown process
    application = context.applications['dummy_appli'] = create_application('dummy_appli', supvisors_instance)
    assert context.check_process(context.instances['10.0.0.1:25000'], event) is None
    mocker.resetall()
    # test with no information in process for identifier
    application.processes['dummy_process'] = create_process(event, supvisors_instance)
    assert context.check_process(context.instances['10.0.0.1:25000'], event) is None
    mocker.resetall()
    # test with process information related to identifier
    application = context.applications['dummy_appli'] = create_application('dummy_appli', supvisors_instance)
    process = application.processes['dummy_process'] = create_process(event, supvisors_instance)
    process.info_map['10.0.0.1:25000'] = {}
    group_event = {'group': 'dummy_appli', 'name': '*'}
    process_event = {'group': 'dummy_appli', 'name': 'dummy_process'}
    # test with group and process information
    assert context.check_process(context.instances['10.0.0.1:25000'], process_event) == (application, process)
    # test with group information only
    assert context.check_process(context.instances['10.0.0.1:25000'], group_event) == (application, None)


def test_on_discovery_event(supvisors_instance, context):
    """ Test the Context.on_discovery_event method. """
    # store reference
    nb_mapper_entries = len(supvisors_instance.mapper.instances)
    sup_id: SupvisorsInstanceId = context.instances['10.0.0.1:25000'].supvisors_id
    ref_ip_address, ref_port = sup_id.ip_address, sup_id.http_port
    # test discovery mode and identifier known and identical
    context.on_discovery_event('10.0.0.1:25000', '10.0.0.1')
    assert sup_id.ip_address == ref_ip_address
    assert sup_id.http_port == ref_port
    assert nb_mapper_entries == len(supvisors_instance.mapper.instances)
    # test discovery mode and nick identifier known and identifier different
    context.on_discovery_event('10.0.0.2:6000', '10.0.0.1')
    assert sup_id.ip_address == ref_ip_address
    assert sup_id.http_port == ref_port
    assert nb_mapper_entries == len(supvisors_instance.mapper.instances)
    # test discovery mode and identifier known and nick identifier different
    assert not context.on_discovery_event('10.0.0.1:25000', 'supvisors')
    assert sup_id.ip_address == ref_ip_address
    assert sup_id.http_port == ref_port
    assert nb_mapper_entries == len(supvisors_instance.mapper.instances)
    # test discovery mode and identifier unknown
    context.on_discovery_event('192.168.1.2:5000', 'rocky52')
    assert sup_id.ip_address == ref_ip_address
    assert sup_id.http_port == ref_port
    assert nb_mapper_entries < len(supvisors_instance.mapper.instances)
    assert '192.168.1.2:5000' in context.instances
    assert '192.168.1.2:5000' in supvisors_instance.mapper.instances
    assert '192.168.1.2:5000' in supvisors_instance.state_modes.instance_state_modes
    assert '192.168.1.2:5000' in supvisors_instance.state_modes.local_state_modes.instance_states
    assert 'rocky52' in supvisors_instance.mapper._nick_identifiers
    sup_id: SupvisorsInstanceId = context.instances['192.168.1.2:5000'].supvisors_id
    assert sup_id.ip_address == '192.168.1.2'
    assert sup_id.http_port == 5000


def test_on_identification_event(mocker, supvisors_instance, context):
    """ Test the Context.on_identification_event method. """
    mocked_identify = mocker.patch.object(supvisors_instance.mapper, 'identify')
    context.on_identification_event({'event': 'data'})
    assert mocked_identify.call_args_list == [(call({'event': 'data'}))]


def test_authorization_not_checking(supvisors_instance, context):
    """ Test the Context.on_authorization method with non-CHECKING identifier. """
    status = context.instances['10.0.0.1:25000']
    # check no change
    for fencing in [True, False]:
        supvisors_instance.options.auto_fence = fencing
        for authorization in [True, False]:
            for state in SupvisorsInstanceStates:
                if state != SupvisorsInstanceStates.CHECKING:
                    status._state = state
                    context.on_authorization(status, authorization)
                    assert status.state == state


def test_authorization_checking_normal(mocker, context):
    """ Test the handling of an authorization event. """
    mocked_invalid = mocker.patch.object(context, 'invalidate')
    # test current state not CHECKING
    status = context.instances['10.0.0.1:25000']
    status._state = SupvisorsInstanceStates.RUNNING
    context.on_authorization(status, True)
    assert not mocked_invalid.called
    # test authorization None (error in handshake)
    status._state = SupvisorsInstanceStates.CHECKING
    context.on_authorization(status, None)
    assert not mocked_invalid.called
    assert status.state == SupvisorsInstanceStates.STOPPED
    # test not authorized
    status._state = SupvisorsInstanceStates.CHECKING
    context.on_authorization(status, False)
    assert mocked_invalid.call_args_list == [call(status, True)]
    mocked_invalid.reset_mock()
    # test authorized
    context.on_authorization(status, True)
    assert not mocked_invalid.called


def test_on_local_tick_event(mocker, supvisors_instance, context):
    """ Test the handling of a TICK event on the local Supvisors instance. """
    mocker.patch('supvisors.context.time.time', return_value=3600)
    mocked_check = supvisors_instance.rpc_handler.send_check_instance
    supvisors_instance.external_publisher = Mock(spec=EventPublisherInterface)
    mocked_send = supvisors_instance.external_publisher.send_instance_status
    # check the current context
    status = context.local_status
    assert status.state == SupvisorsInstanceStates.STOPPED
    status.times.remote_sequence_counter = 7
    status.times.local_sequence_counter = 7
    assert status.times.remote_mtime == 0.0
    assert status.times.remote_time == 0
    assert status.times.local_mtime == 0.0
    assert status.times.local_time == 0
    # when a TICK is received from a STOPPED state, check that:
    #   * Supvisors instance is CHECKING
    #   * time is updated using local time
    #   * send_check_instance is called
    #   * Supvisors instance status is sent
    context.on_local_tick_event({'sequence_counter': 31, 'when': 1234, 'when_monotonic': 234.56})
    assert status.state == SupvisorsInstanceStates.CHECKING
    assert status.sequence_counter == 31
    assert status.times.local_sequence_counter == 31  # same as sequence_counter
    assert status.times.remote_mtime == 234.56
    assert status.times.remote_time == 1234
    assert status.times.local_mtime == 234.56  # same as remote_mtime
    assert status.times.local_time == 1234  # same as remote_time
    assert mocked_check.call_args_list == [call(context.local_identifier)]
    expected = {'identifier': context.local_identifier,
                'nick_identifier': context.local_status.supvisors_id.nick_identifier,
                'node_name': context.local_status.supvisors_id.host_id,
                'port': 25000,
                'statecode': 1, 'statename': 'CHECKING',
                'remote_sequence_counter': 31, 'remote_mtime': 234.56, 'remote_time': 1234,
                'local_sequence_counter': 31, 'local_mtime': 234.56, 'local_time': 1234,
                'loading': 0, 'process_failure': False}
    assert mocked_send.call_args_list == [call(expected)]
    mocked_check.reset_mock()
    mocked_send.reset_mock()
    # when a TICK is received from a CHECKING / CHECKED / RUNNING / FAILED state, check that:
    #   * Supvisors instance state is unchanged
    #   * time is updated using local time
    #   * send_check_instance is NOT called
    #   * Supvisors instance status is sent
    for state in [SupvisorsInstanceStates.CHECKING, SupvisorsInstanceStates.CHECKED,
                  SupvisorsInstanceStates.RUNNING, SupvisorsInstanceStates.FAILED]:
        status._state = state
        context.on_local_tick_event({'sequence_counter': 57, 'when': 5678, 'when_monotonic': 678.9})
        assert status.state == state
        assert status.sequence_counter == 57
        assert status.times.remote_mtime == 678.9
        assert status.times.remote_time == 5678
        assert status.times.local_sequence_counter == 57  # same as sequence_counter
        assert status.times.local_mtime == 678.9  # same as remote_mtime
        assert status.times.local_time == 5678  # same as remote_time
        assert not mocked_check.called
        expected = {'identifier': context.local_identifier,
                    'nick_identifier': context.local_status.supvisors_id.nick_identifier,
                    'node_name': context.local_status.supvisors_id.host_id,
                    'port': 25000,
                    'statecode': state.value, 'statename': state.name,
                    'remote_sequence_counter': 57, 'remote_mtime': 678.9, 'remote_time': 5678,
                    'local_sequence_counter': 57, 'local_mtime': 678.9, 'local_time': 5678,
                    'loading': 0, 'process_failure': False}
        assert mocked_send.call_args_list == [call(expected)]
        mocked_send.reset_mock()


def test_on_tick_event(mocker, supvisors_instance, context):
    """ Test the handling of a tick event from a remote Supvisors instance.
    No test with known Supvisors instance in isolation (event filtered before).
    """
    mocker.patch('time.time', return_value=7200)
    mocker.patch('time.monotonic', return_value=3600)
    mocked_check = supvisors_instance.rpc_handler.send_check_instance
    supvisors_instance.external_publisher = Mock(spec=EventPublisherInterface)
    mocked_send = supvisors_instance.external_publisher.send_instance_status
    # check the current context
    assert context.local_identifier != '10.0.0.2:25000'
    context.instances[context.local_identifier].times.remote_sequence_counter = 7
    # get reference Supvisors instance (not the local one)
    status = context.instances['10.0.0.2:25000']
    assert status.state == SupvisorsInstanceStates.STOPPED
    assert status.sequence_counter == 0
    assert status.times.local_sequence_counter == 0
    assert status.times.remote_mtime == 0.0
    assert status.times.remote_time == 0
    assert status.times.local_mtime == 0.0
    assert status.times.local_time == 0
    # check no processing as long as local Supvisors instance is not RUNNING
    assert context.local_status.state == SupvisorsInstanceStates.STOPPED
    event = {'sequence_counter': 31, 'when': 1234, 'when_monotonic': 234.56, 'stereotypes': {'test'}}
    context.on_tick_event(status, event)
    assert not mocked_check.called
    assert not mocked_send.called
    assert status.state == SupvisorsInstanceStates.STOPPED
    assert status.sequence_counter == 0
    assert status.times.local_sequence_counter == 0
    assert status.times.remote_mtime == 0.0
    assert status.times.remote_time == 0
    assert status.times.local_mtime == 0.0
    assert status.times.local_time == 0
    # set local Supvisors instance state to RUNNING
    context.local_status._state = SupvisorsInstanceStates.RUNNING
    # when a TICK is received from a STOPPED state on a remote Supvisors instance, check that:
    #   * Supvisors instance is CHECKING
    #   * time is updated using local time
    #   * send_check_instance is called
    #   * Supvisors instance status is sent
    status._state = SupvisorsInstanceStates.STOPPED
    context.on_tick_event(status, event)
    assert status.state == SupvisorsInstanceStates.CHECKING
    assert status.sequence_counter == 31
    assert status.times.local_sequence_counter == 7
    assert status.times.remote_mtime == 234.56
    assert status.times.remote_time == 1234
    assert status.times.local_mtime == 3600
    assert status.times.local_time == 7200
    assert mocked_check.call_args_list == [call('10.0.0.2:25000')]
    expected = {'identifier': '10.0.0.2:25000', 'nick_identifier': '10.0.0.2',
                'node_name': '10.0.0.2',
                'port': 25000, 'statecode': 1, 'statename': 'CHECKING',
                'remote_sequence_counter': 31, 'remote_mtime': 234.56, 'remote_time': 1234,
                'local_sequence_counter': 7, 'local_mtime': 3600, 'local_time': 7200,
                'loading': 0, 'process_failure': False}
    assert mocked_send.call_args_list == [call(expected)]
    mocked_check.reset_mock()
    mocked_send.reset_mock()
    # check that node time is updated and node status is sent
    event = {'sequence_counter': 57, 'when': 5678, 'when_monotonic': 678.9, 'stereotypes': {'test'}}
    for state in [SupvisorsInstanceStates.CHECKING, SupvisorsInstanceStates.RUNNING]:
        status._state = state
        context.on_tick_event(status, event)
        assert status.state == state
        assert status.sequence_counter == 57
        assert status.times.local_sequence_counter == 7
        assert status.times.remote_mtime == 678.9
        assert status.times.remote_time == 5678
        assert status.times.local_mtime == 3600
        assert status.times.local_time == 7200
        assert not mocked_check.called
        expected = {'identifier': '10.0.0.2:25000', 'nick_identifier': '10.0.0.2',
                    'node_name': '10.0.0.2', 'port': 25000,
                    'statecode': state.value, 'statename': state.name,
                    'remote_sequence_counter': 57, 'remote_mtime': 678.9, 'remote_time': 5678,
                    'local_sequence_counter': 7, 'local_mtime': 3600, 'local_time': 7200,
                    'loading': 0, 'process_failure': False}
        assert mocked_send.call_args_list == [call(expected)]
        mocked_send.reset_mock()
    # check that the Supvisors instance local_sequence_counter is forced to 0 when its sequence_counter
    #   is lower than expected (stealth restart)
    status._state = SupvisorsInstanceStates.RUNNING
    event = {'sequence_counter': 2, 'when': 6789, 'when_monotonic': 789.01, 'stereotypes': set()}
    context.on_tick_event(status, event)
    assert status.state == SupvisorsInstanceStates.RUNNING
    assert status.sequence_counter == 2
    assert status.times.local_sequence_counter == 0  # invalidated
    assert status.times.remote_mtime == 789.01
    assert status.times.remote_time == 6789
    assert status.times.local_mtime == 3600
    assert status.times.local_time == 7200
    assert not mocked_check.called
    expected = {'identifier': '10.0.0.2:25000', 'nick_identifier': '10.0.0.2',
                'node_name': '10.0.0.2', 'port': 25000,
                'statecode': state.value, 'statename': state.name,
                'remote_sequence_counter': 2, 'remote_mtime': 789.01, 'remote_time': 6789,
                'local_sequence_counter': 0, 'local_mtime': 3600, 'local_time': 7200,
                'loading': 0, 'process_failure': False}
    assert mocked_send.call_args_list == [call(expected)]


def test_on_timer_event(supvisors_instance, context):
    """ Test the handling of a timer event in the local Supvisors instance.
    No test with known Supvisors instance in isolation (event filtered before).
    """
    supvisors_instance.external_publisher = Mock()
    # update context instances
    context.instances['10.0.0.1:25000']._state = SupvisorsInstanceStates.RUNNING
    context.instances['10.0.0.1:25000'].times.remote_sequence_counter = 31
    context.instances['10.0.0.1:25000'].times.local_sequence_counter = 31
    context.instances['10.0.0.2:25000']._state = SupvisorsInstanceStates.RUNNING
    context.instances['10.0.0.2:25000'].times.local_sequence_counter = 29
    context.instances['10.0.0.3:25000']._state = SupvisorsInstanceStates.STOPPED
    context.instances['10.0.0.3:25000'].times.local_sequence_counter = 10
    context.instances['10.0.0.4:25000']._state = SupvisorsInstanceStates.CHECKING
    context.instances['10.0.0.4:25000'].times.local_sequence_counter = 0
    context.instances['10.0.0.5:25000']._state = SupvisorsInstanceStates.STOPPED
    context.instances['10.0.0.5:25000'].times.local_sequence_counter = 0
    context.instances['10.0.0.6:25000']._state = SupvisorsInstanceStates.ISOLATED
    context.instances['10.0.0.6:25000'].times.local_sequence_counter = 0
    # test when synchro_timeout has passed
    context.on_timer_event({'sequence_counter': 32, 'when': 3600})
    expected_1 = {'identifier': '10.0.0.2:25000', 'nick_identifier': '10.0.0.2',
                  'node_name': '10.0.0.2', 'port': 25000,
                  'statecode': 4, 'statename': 'FAILED',
                  'remote_sequence_counter': 0, 'remote_mtime': 0.0, 'remote_time': 0,
                  'local_sequence_counter': 29, 'local_mtime': 0.0, 'local_time': 0,
                  'loading': 0, 'process_failure': False}
    expected_2 = {'identifier': '10.0.0.4:25000', 'nick_identifier': '10.0.0.4',
                  'node_name': '10.0.0.4', 'port': 25000,
                  'statecode': 4, 'statename': 'FAILED',
                  'remote_sequence_counter': 0, 'remote_mtime': 0.0, 'remote_time': 0,
                  'local_sequence_counter': 0, 'local_mtime': 0.0, 'local_time': 0,
                  'loading': 0, 'process_failure': False}
    assert supvisors_instance.external_publisher.send_instance_status.call_args_list == [call(expected_1),
                                                                                         call(expected_2)]
    # '10.0.0.2', '10.0.0.4' and '10.0.0.5' instances changed state
    local_identifier = context.supvisors.mapper.local_identifier
    for identifier, state in [(local_identifier, SupvisorsInstanceStates.RUNNING),
                              ('10.0.0.1:25000', SupvisorsInstanceStates.RUNNING),
                              ('10.0.0.2:25000', SupvisorsInstanceStates.FAILED),
                              ('10.0.0.3:25000', SupvisorsInstanceStates.STOPPED),
                              ('10.0.0.4:25000', SupvisorsInstanceStates.FAILED),
                              ('10.0.0.5:25000', SupvisorsInstanceStates.STOPPED),
                              ('10.0.0.6:25000', SupvisorsInstanceStates.ISOLATED)]:
        assert context.instances[identifier].state == state


def test_on_instance_failure(mocker, context):
    """ Test the handling of an XML-RPC failure on the Supvisors instance. """
    mocked_export = mocker.patch.object(context, 'export_status')
    # update context instances
    context.local_status._state = SupvisorsInstanceStates.RUNNING
    context.instances['10.0.0.1:25000']._state = SupvisorsInstanceStates.RUNNING
    context.instances['10.0.0.2:25000']._state = SupvisorsInstanceStates.RUNNING
    context.instances['10.0.0.3:25000']._state = SupvisorsInstanceStates.STOPPED
    context.instances['10.0.0.4:25000']._state = SupvisorsInstanceStates.CHECKING
    context.instances['10.0.0.5:25000']._state = SupvisorsInstanceStates.STOPPED
    context.instances['10.0.0.6:25000']._state = SupvisorsInstanceStates.ISOLATED
    # test when synchro_timeout has passed
    context.on_instance_failure(context.instances['10.0.0.2:25000'])
    assert mocked_export.call_args_list == [call(context.instances['10.0.0.2:25000'])]
    # '10.0.0.2' instance changed state
    local_identifier = context.supvisors.mapper.local_identifier
    for identifier, state in [(local_identifier, SupvisorsInstanceStates.RUNNING),
                              ('10.0.0.1:25000', SupvisorsInstanceStates.RUNNING),
                              ('10.0.0.2:25000', SupvisorsInstanceStates.FAILED),
                              ('10.0.0.3:25000', SupvisorsInstanceStates.STOPPED),
                              ('10.0.0.4:25000', SupvisorsInstanceStates.CHECKING),
                              ('10.0.0.5:25000', SupvisorsInstanceStates.STOPPED),
                              ('10.0.0.6:25000', SupvisorsInstanceStates.ISOLATED)]:
        assert context.instances[identifier].state == state


def test_process_removed_event_not_running(supvisors_instance, context):
    """ Test the Context.on_process_removed_event with a non-RUNNING Supvisors instance. """
    supvisors_instance.external_publisher = Mock(spec=EventPublisherInterface)
    mocked_publisher = supvisors_instance.external_publisher
    # get instance status used for tests
    instance_status = context.instances['10.0.0.1:25000']
    # check no change with known instance not RUNNING
    for state in SupvisorsInstanceStates:
        if state not in [SupvisorsInstanceStates.CHECKED, SupvisorsInstanceStates.RUNNING]:
            instance_status._state = state
            context.on_process_removed_event(instance_status, {})
            assert not mocked_publisher.send_process_event.called
            assert not mocked_publisher.send_process_status.called
            assert not mocked_publisher.send_application_status.called


def test_process_removed_event_running_process_unknown(mocker, supvisors_instance, context):
    """ Test the Context.on_process_removed_event with a RUNNING Supvisors instance and an unknown process. """
    mocker.patch.object(context, 'check_process', return_value=None)
    supvisors_instance.external_publisher = Mock(spec=EventPublisherInterface)
    mocked_publisher = supvisors_instance.external_publisher
    assert supvisors_instance.options.auto_fence
    event = {'group': 'dummy_appli', 'name': 'dummy_process'}
    # get instance status used for tests
    instance_status = context.instances['10.0.0.1:25000']
    instance_status._state = SupvisorsInstanceStates.RUNNING
    # check no change with unknown process
    context.on_process_removed_event(instance_status, event)
    assert not mocked_publisher.send_process_event.called
    assert not mocked_publisher.send_process_status.called
    assert not mocked_publisher.send_application_status.called


def test_on_process_removed_event_running_process(mocker, supvisors_instance, context):
    """ Test the handling of a known process removed event coming from a RUNNING Supvisors instance. """
    mocker.patch('time.monotonic', return_value=1234)
    supvisors_instance.external_publisher = Mock(spec=EventPublisherInterface)
    mocked_publisher = supvisors_instance.external_publisher
    # add context. processes removed are expected to be STOPPED
    application = context.applications['dummy_application'] = create_application('dummy_application',
                                                                                 supvisors_instance)
    dummy_info_1 = {'group': 'dummy_application', 'name': 'dummy_process_1', 'expected': True, 'state': 0,
                    'now': 1234, 'now_monotonic': 234, 'stop': 1230, 'stop_monotonic': 230, 'extra_args': '-h',
                    'program_name': 'dummy_process', 'process_index': 0}
    dummy_info_2 = {'group': 'dummy_application', 'name': 'dummy_process_2', 'expected': True, 'state': 0,
                    'now': 4321, 'now_monotonic': 321, 'stop': 4300, 'stop_monotonic': 300, 'extra_args': '',
                    'program_name': 'dummy_process', 'process_index': 1}
    process_1 = create_process(dummy_info_1, supvisors_instance)
    process_2 = create_process(dummy_info_2, supvisors_instance)
    application.add_process(process_2)
    process_1.add_info('10.0.0.1:25000', dummy_info_1)
    process_1.add_info('10.0.0.2:25000', dummy_info_1)
    process_2.add_info('10.0.0.2:25000', dummy_info_2)
    application.add_process(process_1)
    application.add_process(process_2)
    status_10001 = context.instances['10.0.0.1:25000']
    status_10002 = context.instances['10.0.0.2:25000']
    status_10001.processes[process_1.namespec] = process_1
    status_10002.processes[process_1.namespec] = process_1
    status_10002.processes[process_2.namespec] = process_2
    # get instances status used for tests
    status_10001._state = SupvisorsInstanceStates.RUNNING
    status_10002._state = SupvisorsInstanceStates.RUNNING
    # update sequences for the test
    application.rules.managed = True
    application.update_sequences()
    application.update()
    assert application.state == ApplicationStates.STOPPED
    # payload for parameter
    dummy_event = {'group': 'dummy_application', 'name': 'dummy_process_1'}
    mocker.patch.object(context, 'check_process', return_value=(application, process_1))
    # check normal behaviour in RUNNING state when process_1 is removed from 10.0.0.1
    # as process will still include a definition on 10.0.0.2, no impact expected on process and application
    context.on_process_removed_event(status_10001, dummy_event)
    assert sorted(process_1.info_map.keys()) == ['10.0.0.2:25000']
    assert sorted(process_2.info_map.keys()) == ['10.0.0.2:25000']
    assert application.state == ApplicationStates.STOPPED
    assert sorted(status_10001.processes.keys()) == []
    assert sorted(status_10002.processes.keys()) == ['dummy_application:dummy_process_1',
                                                     'dummy_application:dummy_process_2']
    expected = {'group': 'dummy_application', 'name': 'dummy_process_1', 'state': -1}
    assert mocked_publisher.send_process_event.call_args_list == [call(expected)]
    assert not mocked_publisher.send_process_status.called
    assert not mocked_publisher.send_application_status.called
    mocked_publisher.send_process_event.reset_mock()
    # check normal behaviour in RUNNING state when process_1 is removed from 10.0.0.2
    # process_1 is removed from application and instance status but application is still STARTING due to process_2
    context.on_process_removed_event(status_10002, dummy_event)
    assert list(process_1.info_map.keys()) == []
    assert sorted(process_2.info_map.keys()) == ['10.0.0.2:25000']
    assert application.state == ApplicationStates.STOPPED
    assert sorted(status_10001.processes.keys()) == []
    assert sorted(status_10002.processes.keys()) == ['dummy_application:dummy_process_2']
    expected = {'group': 'dummy_application', 'name': 'dummy_process_1', 'state': -1}
    assert mocked_publisher.send_process_event.call_args_list == [call(expected)]
    expected = {'application_name': 'dummy_application', 'process_name': 'dummy_process_1',
                'statecode': -1, 'statename': 'DELETED', 'expected_exit': True,
                'last_event_mtime': 1234, 'now_monotonic': 1234,
                'identifiers': [], 'extra_args': ''}
    assert mocked_publisher.send_process_status.call_args_list == [call(expected)]
    expected = {'application_name': 'dummy_application', 'managed': True,
                'statecode': 0, 'statename': 'STOPPED',
                'now_monotonic': 1234, 'major_failure': False, 'minor_failure': False}
    assert mocked_publisher.send_application_status.call_args_list == [call(expected)]
    mocked_publisher.send_process_event.reset_mock()
    mocked_publisher.send_process_status.reset_mock()
    mocked_publisher.send_application_status.reset_mock()
    # check normal behaviour in RUNNING state when process_2 is removed from 10.0.0.2
    # no more process in application and instance status so application is removed
    dummy_event = {'group': 'dummy_application', 'name': 'dummy_process_2'}
    mocker.patch.object(context, 'check_process', return_value=(application, process_2))
    context.on_process_removed_event(status_10002, dummy_event)
    assert list(process_1.info_map.keys()) == []
    assert list(process_2.info_map.keys()) == []
    assert application.state == ApplicationStates.DELETED
    expected = {'group': 'dummy_application', 'name': 'dummy_process_2', 'state': -1}
    assert mocked_publisher.send_process_event.call_args_list == [call(expected)]
    expected = {'application_name': 'dummy_application', 'process_name': 'dummy_process_2',
                'statecode': -1, 'statename': 'DELETED', 'expected_exit': True,
                'last_event_mtime': 1234, 'now_monotonic': 1234,
                'identifiers': [], 'extra_args': ''}
    assert mocked_publisher.send_process_status.call_args_list == [call(expected)]
    expected = {'application_name': 'dummy_application', 'managed': True,
                'statecode': 4, 'statename': 'DELETED',
                'now_monotonic': 1234, 'major_failure': False, 'minor_failure': False}
    assert mocked_publisher.send_application_status.call_args_list == [call(expected)]


def test_on_process_removed_event_running_group(mocker, supvisors_instance, context):
    """ Test the handling of a known group removed event coming from a RUNNING Supvisors instance. """
    mocker.patch('time.monotonic', return_value=1234)
    supvisors_instance.external_publisher = Mock(spec=EventPublisherInterface)
    mocked_publisher = supvisors_instance.external_publisher
    # add context. processes removed are expected to be STOPPED
    application = create_application('dummy_application', supvisors_instance)
    context.applications['dummy_application'] = application
    dummy_info_1 = {'group': 'dummy_application', 'name': 'dummy_process_1', 'expected': True, 'state': 0,
                    'now': 1234, 'now_monotonic': 234, 'stop': 1230, 'stop_monotonic': 230, 'extra_args': '-h',
                    'program_name': 'dummy_process', 'process_index': 0}
    dummy_info_2 = {'group': 'dummy_application', 'name': 'dummy_process_2', 'expected': True, 'state': 0,
                    'now': 4321, 'now_monotonic': 321, 'stop': 4300, 'stop_monotonic': 300, 'extra_args': '',
                    'program_name': 'dummy_process', 'process_index': 1}
    process_1 = create_process(dummy_info_1, supvisors_instance)
    process_2 = create_process(dummy_info_2, supvisors_instance)
    process_1.add_info('10.0.0.1:25000', dummy_info_1)
    process_1.add_info('10.0.0.2:25000', dummy_info_1)
    process_2.add_info('10.0.0.2:25000', dummy_info_2)
    application.add_process(process_1)
    application.add_process(process_2)
    status_10001 = context.instances['10.0.0.1:25000']
    status_10002 = context.instances['10.0.0.2:25000']
    status_10001.processes[process_1.namespec] = process_1
    status_10002.processes[process_1.namespec] = process_1
    status_10002.processes[process_2.namespec] = process_2
    # get instances status used for tests
    status_10001._state = SupvisorsInstanceStates.RUNNING
    status_10002._state = SupvisorsInstanceStates.RUNNING
    # update sequences for the test
    application.rules.managed = True
    application.update_sequences()
    application.update()
    assert application.state == ApplicationStates.STOPPED
    # payload for parameter
    dummy_event = {'group': 'dummy_application', 'name': '*'}
    mocker.patch.object(context, 'check_process', return_value=(application, None))
    # check normal behaviour in RUNNING state when dummy_application is removed from 10.0.0.1
    # as processes still includes a definition on 10.0.0.2, no impact expected on process and application
    context.on_process_removed_event(status_10001, dummy_event)
    assert sorted(process_1.info_map.keys()) == ['10.0.0.2:25000']
    assert sorted(process_2.info_map.keys()) == ['10.0.0.2:25000']
    assert application.state == ApplicationStates.STOPPED
    assert sorted(status_10001.processes.keys()) == []
    assert sorted(status_10002.processes.keys()) == ['dummy_application:dummy_process_1',
                                                     'dummy_application:dummy_process_2']
    expected = {'group': 'dummy_application', 'name': 'dummy_process_1', 'state': -1}
    assert mocked_publisher.send_process_event.call_args_list == [call(expected)]
    assert not mocked_publisher.send_process_status.called
    assert not mocked_publisher.send_application_status.called
    mocked_publisher.send_process_event.reset_mock()
    # check normal behaviour in RUNNING state when dummy_application is removed from 10.0.0.2
    # no more process in application and instance status so application is removed
    context.on_process_removed_event(status_10002, dummy_event)
    assert list(process_1.info_map.keys()) == []
    assert list(process_2.info_map.keys()) == []
    assert application.state == ApplicationStates.DELETED
    expected_1 = {'group': 'dummy_application', 'name': 'dummy_process_1', 'state': -1}
    expected_2 = {'group': 'dummy_application', 'name': 'dummy_process_2', 'state': -1}
    assert mocked_publisher.send_process_event.call_args_list == [call(expected_1), call(expected_2)]
    expected_1 = {'application_name': 'dummy_application', 'process_name': 'dummy_process_1',
                  'statecode': -1, 'statename': 'DELETED', 'expected_exit': True,
                  'last_event_mtime': 1234, 'now_monotonic': 1234,
                  'identifiers': [], 'extra_args': ''}
    expected_2 = {'application_name': 'dummy_application', 'process_name': 'dummy_process_2',
                  'statecode': -1, 'statename': 'DELETED', 'expected_exit': True,
                  'last_event_mtime': 1234, 'now_monotonic': 1234,
                  'identifiers': [], 'extra_args': ''}
    assert mocked_publisher.send_process_status.call_args_list == [call(expected_1), call(expected_2)]
    expected = {'application_name': 'dummy_application', 'managed': True,
                'statecode': 4, 'statename': 'DELETED',
                'now_monotonic': 1234, 'major_failure': False, 'minor_failure': False}
    assert mocked_publisher.send_application_status.call_args_list == [call(expected)]


def test_on_process_disability_event_not_running_instance(supvisors_instance, context):
    """ Test the handling of a process disability event coming from a non-running Supvisors instance. """
    supvisors_instance.external_publisher = Mock(spec=EventPublisherInterface)
    mocked_publisher = supvisors_instance.external_publisher
    # get instance status used for tests
    instance_status = context.instances['10.0.0.1:25000']
    # check no change with known node not RUNNING
    for state in SupvisorsInstanceStates:
        if state not in [SupvisorsInstanceStates.CHECKED, SupvisorsInstanceStates.RUNNING]:
            instance_status._state = state
            context.on_process_disability_event(instance_status, {})
            assert not mocked_publisher.send_process_event.called


def test_on_process_disability_event_running_process_unknown(mocker, supvisors_instance, context):
    """ Test the Context.on_process_disability_event with a RUNNING Supvisors instance and an unknown process. """
    mocker.patch.object(context, 'check_process', return_value=None)
    supvisors_instance.external_publisher = Mock(spec=EventPublisherInterface)
    mocked_publisher = supvisors_instance.external_publisher
    assert supvisors_instance.options.auto_fence
    event = {'group': 'dummy_appli', 'name': 'dummy_process'}
    # get instance status used for tests
    instance_status = context.instances['10.0.0.1:25000']
    instance_status._state = SupvisorsInstanceStates.RUNNING
    # check no change with unknown process
    context.on_process_disability_event(instance_status, event)
    assert not mocked_publisher.send_process_event.called


def test_on_process_disability_event(mocker, supvisors_instance, context):
    """ Test the Context.on_process_disability_event with a RUNNING Supvisors instance and a known process. """
    supvisors_instance.external_publisher = Mock(spec=EventPublisherInterface)
    mocked_publisher = supvisors_instance.external_publisher
    event = {'group': 'dummy_appli', 'name': 'dummy_process', 'disabled': True}
    # get instance status used for tests
    instance_status = context.instances['10.0.0.1:25000']
    instance_status._state = SupvisorsInstanceStates.RUNNING
    # patch load_application_rules
    supvisors_instance.parser.load_application_rules = load_application_rules
    # fill context with one process
    dummy_info = {'group': 'dummy_application', 'name': 'dummy_process', 'expected': True, 'state': 0,
                  'now': 1234, 'now_monotonic': 234, 'stop': 0, 'stop_monotonic': 0, 'extra_args': '-h',
                  'disabled': False, 'program_name': 'dummy_process', 'process_index': 0}
    process = context.setdefault_process('10.0.0.2:25000', dummy_info)
    process.add_info('10.0.0.2', dummy_info)
    mocker.patch.object(context, 'check_process', return_value=(None, process))
    # check that process disabled status is not updated if the process has no information from the Supvisors instance
    context.on_process_disability_event(instance_status, event)
    assert '10.0.0.1:25000' not in process.info_map
    assert not process.info_map['10.0.0.2:25000']['disabled']
    assert mocked_publisher.send_process_event.call_args_list == [call(event)]
    mocked_publisher.send_process_event.reset_mock()
    # check that process disabled status is updated if the process has information from the Supvisors instance
    process.add_info('10.0.0.1:25000', dummy_info)
    context.on_process_disability_event(instance_status, event)
    assert process.info_map['10.0.0.1:25000']['disabled']
    assert mocked_publisher.send_process_event.call_args_list == [call(event)]


def test_on_process_state_event_not_running_instance(mocker, supvisors_instance, context):
    """ Test the handling of a process state event coming from a non-running Supvisors instance. """
    supvisors_instance.external_publisher = Mock(spec=EventPublisherInterface)
    mocked_publisher = supvisors_instance.external_publisher
    mocked_update_args = mocker.patch.object(supvisors_instance.supervisor_data, 'update_extra_args')
    # get instance status used for tests
    instance_status = context.instances['10.0.0.1:25000']
    # check no change with known node not RUNNING
    for state in SupvisorsInstanceStates:
        if state not in [SupvisorsInstanceStates.CHECKED, SupvisorsInstanceStates.RUNNING]:
            instance_status._state = state
            assert context.on_process_state_event(instance_status, {}) is None
            assert not mocked_update_args.called
            assert not mocked_publisher.send_process_event.called
            assert not mocked_publisher.send_process_status.called
            assert not mocked_publisher.send_application_status.called


def test_on_process_state_event_running_process_unknown(mocker, supvisors_instance, context):
    """ Test the Context.on_process_state_event with a RUNNING Supvisors instance and an unknown process. """
    mocker.patch.object(context, 'check_process', return_value=None)
    supvisors_instance.external_publisher = Mock(spec=EventPublisherInterface)
    mocked_publisher = supvisors_instance.external_publisher
    assert supvisors_instance.options.auto_fence
    event = {'group': 'dummy_appli', 'name': 'dummy_process'}
    # get instance status used for tests
    instance_status = context.instances['10.0.0.1:25000']
    instance_status._state = SupvisorsInstanceStates.RUNNING
    # check no change with unknown application
    assert context.on_process_state_event(instance_status, event) is None
    assert not mocked_publisher.send_process_event.called
    assert not mocked_publisher.send_process_status.called
    assert not mocked_publisher.send_application_status.called


def test_on_process_state_event_locally_unknown_forced(mocker, supvisors_instance, context):
    """ Test the Context.on_process_state_event with a RUNNING Supvisors instance and a process known by the local
    Supvisors instance but not configured on the instance that raised the event.
    This is a forced event that will be accepted in the ProcessStatus. """
    mocker.patch('time.monotonic', return_value=1234)
    supvisors_instance.external_publisher = Mock(spec=EventPublisherInterface)
    mocked_publisher = supvisors_instance.external_publisher
    # get instance status used for tests
    instance_status = context.instances['10.0.0.2:25000']
    instance_status._state = SupvisorsInstanceStates.RUNNING
    # patch load_application_rules
    supvisors_instance.parser.load_application_rules = load_application_rules
    # fill context with one process
    dummy_info = {'group': 'dummy_application', 'name': 'dummy_process', 'state': ProcessStates.RUNNING,
                  'now': 1234, 'now_monotonic': 234, 'start': 1230, 'start_monotonic': 230,
                  'expected': True, 'extra_args': '-h',
                  'program_name': 'dummy_process', 'process_index': 0}
    process = context.setdefault_process('10.0.0.2:25000', dummy_info)
    assert 'dummy_application' in context.applications
    application = context.applications['dummy_application']
    assert 'dummy_process' in application.processes
    # update sequences for the test
    application.rules.managed = True
    application.update_sequences()
    application.update()
    assert application.state == ApplicationStates.RUNNING
    # check there is no issue when a forced event is raised using an identifier not used in the process configuration
    # check the forced event will be accepted because the stored event has the same date as the forced event
    event = {'group': 'dummy_application', 'name': 'dummy_process', 'state': ProcessStates.FATAL,
             'identifier': '10.0.0.3', 'forced': True,
             'now': 1234, 'now_monotonic': 234, 'pid': 0,
             'expected': False, 'spawnerr': 'bad luck', 'extra_args': '-h'}
    assert context.on_process_state_event(instance_status, event) is process
    assert instance_status.state == SupvisorsInstanceStates.RUNNING
    assert application.state == ApplicationStates.STOPPED
    expected = {'group': 'dummy_application', 'name': 'dummy_process', 'pid': 0, 'expected': False,
                'identifier': '10.0.0.3', 'state': ProcessStates.FATAL, 'extra_args': '-h',
                'now': 1234, 'now_monotonic': 234, 'event_mtime': 1234,
                'spawnerr': 'bad luck'}
    assert mocked_publisher.send_process_event.call_args_list == [call(expected)]
    expected = {'application_name': 'dummy_application', 'process_name': 'dummy_process',
                'statecode': ProcessStates.FATAL, 'statename': 'FATAL', 'expected_exit': True,
                'last_event_mtime': 1234, 'now_monotonic': 1234,
                'identifiers': ['10.0.0.2:25000'], 'extra_args': ''}
    assert mocked_publisher.send_process_status.call_args_list == [call(expected)]
    expected = {'application_name': 'dummy_application', 'managed': True,
                'statecode': ApplicationStates.STOPPED.value, 'statename': ApplicationStates.STOPPED.name,
                'now_monotonic': 1234, 'major_failure': False, 'minor_failure': True}
    assert mocked_publisher.send_application_status.call_args_list == [call(expected)]


def test_on_process_state_event_locally_known_forced_dismissed(supvisors_instance, context):
    """ Test the Context.on_process_state_event with a RUNNING Supvisors instance and a process known by the local
    Supvisors instance and configured on the instance that raised the event.
    This is a forced event that will be dismissed in the ProcessStatus. """
    supvisors_instance.external_publisher = Mock(spec=EventPublisherInterface)
    mocked_publisher = supvisors_instance.external_publisher
    assert supvisors_instance.options.auto_fence
    # get instance status used for tests
    instance_status = context.instances['10.0.0.1:25000']
    instance_status._state = SupvisorsInstanceStates.RUNNING
    # patch load_application_rules
    supvisors_instance.parser.load_application_rules = load_application_rules
    # fill context with one process
    dummy_info = {'group': 'dummy_application', 'name': 'dummy_process', 'state': ProcessStates.RUNNING,
                  'now': 1234, 'now_monotonic': 234, 'start': 1230, 'start_monotonic': 230,
                  'expected': True, 'extra_args': '-h',
                  'program_name': 'dummy_process', 'process_index': 0}
    context.setdefault_process('10.0.0.1:25000', dummy_info)
    application = context.applications['dummy_application']
    # update sequences for the test
    application.rules.managed = True
    application.update_sequences()
    application.update()
    assert application.state == ApplicationStates.RUNNING
    # check there is no issue when a forced event is raised using an identifier not used in the process configuration
    # check the forced event will be dismissed because the stored event is more recent
    context.logger.trace = context.logger.debug = context.logger.info = print
    event = {'group': 'dummy_application', 'name': 'dummy_process', 'state': ProcessStates.FATAL,
             'identifier': '10.0.0.1:25000', 'forced': True, 'now': 1230, 'now_monotonic': 230, 'pid': 0,
             'expected': False, 'spawnerr': 'bad luck', 'extra_args': '-h'}
    assert context.on_process_state_event(instance_status, event) is None
    assert instance_status.state == SupvisorsInstanceStates.RUNNING
    assert application.state == ApplicationStates.RUNNING
    assert not mocked_publisher.send_process_event.called
    assert not mocked_publisher.send_process_status.called
    assert not mocked_publisher.send_application_status.called


def test_on_process_state_event(mocker, supvisors_instance, context):
    """ Test the handling of a process event. """
    mocker.patch('time.monotonic', return_value=1234)
    supvisors_instance.external_publisher = Mock(spec=EventPublisherInterface)
    mocked_publisher = supvisors_instance.external_publisher
    mocked_update_args = mocker.patch.object(supvisors_instance.supervisor_data, 'update_extra_args')
    # get node status used for tests
    instance_status = context.instances['10.0.0.1:25000']
    # patch load_application_rules
    supvisors_instance.parser.load_application_rules = load_application_rules
    # fill context with one process
    dummy_info = {'group': 'dummy_application', 'name': 'dummy_process', 'expected': True, 'state': 0,
                  'now': 1234, 'now_monotonic': 234, 'stop': 0, 'stop_monotonic': 0, 'extra_args': '-h',
                  'program_name': 'dummy_process', 'process_index': 0}
    process = context.setdefault_process('10.0.0.1:25000', dummy_info)
    application = context.applications['dummy_application']
    assert application.state == ApplicationStates.STOPPED
    # update sequences for the test
    application.rules.managed = True
    application.update_sequences()
    # payload for parameter
    dummy_event = {'group': 'dummy_application', 'name': 'dummy_process', 'state': 10, 'extra_args': '',
                   'now': 2345, 'stop': 0}
    # check normal behaviour in RUNNING state
    instance_status._state = SupvisorsInstanceStates.RUNNING
    result = context.on_process_state_event(instance_status, dummy_event)
    assert result is process
    assert process.state == 10
    assert application.state == ApplicationStates.STARTING
    assert mocked_update_args.call_args_list == [call('dummy_application:dummy_process', '')]
    expected = {'group': 'dummy_application', 'name': 'dummy_process',
                'state': 10, 'extra_args': '', 'now': 2345, 'stop': 0,
                'event_mtime': 1234}
    assert mocked_publisher.send_process_event.call_args_list == [call(expected)]
    expected = {'application_name': 'dummy_application', 'process_name': 'dummy_process',
                'statecode': 10, 'statename': 'STARTING', 'expected_exit': True,
                'now_monotonic': 1234, 'last_event_mtime': 1234,
                'identifiers': ['10.0.0.1:25000'], 'extra_args': ''}
    assert mocked_publisher.send_process_status.call_args_list == [call(expected)]
    expected = {'application_name': 'dummy_application', 'managed': True, 'statecode': 1, 'statename': 'STARTING',
                'now_monotonic': 1234, 'major_failure': False, 'minor_failure': False}
    assert mocked_publisher.send_application_status.call_args_list == [call(expected)]
    # reset mocks
    mocked_update_args.reset_mock()
    mocked_publisher.send_process_event.reset_mock()
    mocked_publisher.send_process_status.reset_mock()
    mocked_publisher.send_application_status.reset_mock()
    # check degraded behaviour with process to Supvisors but unknown to Supervisor (remote program)
    # basically same check as previous, just being confident that no exception is raised by the method
    mocked_update_args.side_effect = KeyError
    result = context.on_process_state_event(instance_status, dummy_event)
    assert result is process
    assert process.state == 10
    assert application.state == ApplicationStates.STARTING
    assert mocked_update_args.call_args_list == [call('dummy_application:dummy_process', '')]
    expected = {'group': 'dummy_application', 'name': 'dummy_process',
                'state': 10, 'extra_args': '', 'now': 2345, 'stop': 0,
                'event_mtime': 1234}
    assert mocked_publisher.send_process_event.call_args_list == [call(expected)]
    expected = {'application_name': 'dummy_application', 'process_name': 'dummy_process',
                'statecode': 10, 'statename': 'STARTING', 'expected_exit': True,
                'now_monotonic': 1234, 'last_event_mtime': 1234,
                'identifiers': ['10.0.0.1:25000'], 'extra_args': ''}
    assert mocked_publisher.send_process_status.call_args_list == [call(expected)]
    expected = {'application_name': 'dummy_application', 'managed': True, 'statecode': 1, 'statename': 'STARTING',
                'now_monotonic': 1234, 'major_failure': False, 'minor_failure': False}
    assert mocked_publisher.send_application_status.call_args_list == [call(expected)]
