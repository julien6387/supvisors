#!/usr/bin/python
# -*- coding: utf-8 -*-

# ======================================================================
# Copyright 2016 Julien LE CLEACH
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

import pickle
import pytest

from supervisor.states import _process_states_by_code
from unittest.mock import call

from supvisors.process import *
from supvisors.ttypes import RunningFailureStrategies

from .base import any_process_info, any_stopped_process_info, process_info_by_name, any_process_info_by_state
from .conftest import create_process


# ProcessRules part
@pytest.fixture
def rules(supvisors):
    """ Return the instance to test. """
    return ProcessRules(supvisors)


def test_rules_create(supvisors, rules):
    """ Test the values set at construction. """
    assert rules.supvisors is supvisors
    assert rules.identifiers == ['*']
    assert rules.hash_identifiers == []
    assert rules.start_sequence == 0
    assert rules.stop_sequence == -1
    assert not rules.required
    assert not rules.wait_exit
    assert rules.expected_load == 0
    assert rules.starting_failure_strategy == StartingFailureStrategies.ABORT
    assert rules.running_failure_strategy == RunningFailureStrategies.CONTINUE


def test_rules_str(rules):
    """ Test the string output. """
    assert str(rules) == ("identifiers=['*'] hash_identifiers=[] start_sequence=0 stop_sequence=-1 required=False"
                          " wait_exit=False expected_load=0 starting_failure_strategy=ABORT"
                          " running_failure_strategy=CONTINUE")


def test_rules_serial(rules):
    """ Test the serialization of the ProcessRules object. """
    assert rules.serial() == {'identifiers': ['*'], 'start_sequence': 0, 'stop_sequence': -1,
                              'required': False, 'wait_exit': False, 'expected_loading': 0,
                              'starting_failure_strategy': 'ABORT', 'running_failure_strategy': 'CONTINUE'}


def test_rules_check_start_sequence(rules):
    """ Test the dependencies in process rules. """
    # 1. test with not required and no start sequence
    rules.start_sequence = 0
    rules.required = False
    # call check dependencies
    rules.check_dependencies('dummy')
    # check rules unchanged
    assert rules.start_sequence == 0
    assert not rules.required
    # 2. test with required and no start sequence
    rules.start_sequence = 0
    rules.required = True
    # check dependencies
    rules.check_dependencies('dummy')
    # check required has been changed
    assert rules.start_sequence == 0
    assert not rules.required
    # 3. test with not required and start sequence
    rules.start_sequence = 1
    rules.required = False
    # check dependencies
    rules.check_dependencies('dummy')
    # check rules unchanged
    assert rules.start_sequence == 1
    assert not rules.required
    # 4. test with required and start sequence
    rules.start_sequence = 1
    rules.required = True
    # check dependencies
    rules.check_dependencies('dummy')
    # check rules unchanged
    assert rules.start_sequence == 1
    assert rules.required


def test_rules_check_stop_sequence(rules):
    """ Test the assignment of stop sequence to start sequence if default still set. """
    # test when default still used
    assert rules.start_sequence == 0
    assert rules.stop_sequence == -1
    rules.check_stop_sequence('crash')
    assert rules.start_sequence == 0
    assert rules.stop_sequence == 0
    # test when value has been set
    rules.start_sequence = 12
    rules.stop_sequence = 50
    rules.check_stop_sequence('crash')
    assert rules.start_sequence == 12
    assert rules.stop_sequence == 50


def test_rules_check_autorestart(mocker, rules):
    """ Test the dependency related to running failure strategy in process rules.
    Done in a separate test as it impacts the supervisor internal model. """
    # test based on programs unknown to Supervisor
    mocked_disable = mocker.patch.object(rules.supvisors.supervisor_data, 'disable_autorestart')
    mocked_autorestart = mocker.patch.object(rules.supvisors.supervisor_data, 'autorestart')
    mocked_autorestart.side_effect = KeyError
    for strategy in RunningFailureStrategies:
        rules.running_failure_strategy = strategy
        rules.check_autorestart('dummy_process_1')
        if strategy in [RunningFailureStrategies.STOP_APPLICATION, RunningFailureStrategies.RESTART_APPLICATION]:
            assert mocked_autorestart.call_args_list == [call('dummy_process_1')]
            mocked_autorestart.reset_mock()
        else:
            assert not mocked_disable.called
        assert not mocked_disable.called
    # test based on programs known to Supervisor but with autostart not activated
    mocked_autorestart.side_effect = None
    mocked_autorestart.return_value = False
    for strategy in RunningFailureStrategies:
        rules.running_failure_strategy = strategy
        rules.check_autorestart('dummy_process_1')
        if strategy in [RunningFailureStrategies.STOP_APPLICATION, RunningFailureStrategies.RESTART_APPLICATION]:
            assert mocked_autorestart.call_args_list == [call('dummy_process_1')]
            mocked_autorestart.reset_mock()
        else:
            assert not mocked_disable.called
        assert not mocked_disable.called
    # test based on programs known to Supervisor but with autostart activated
    # test that only the CONTINUE and RESTART_PROCESS strategies keep the autorestart
    mocked_autorestart.return_value = True
    for strategy in RunningFailureStrategies:
        rules.running_failure_strategy = strategy
        rules.check_autorestart('dummy_process_1')
        if strategy in [RunningFailureStrategies.STOP_APPLICATION, RunningFailureStrategies.RESTART_APPLICATION]:
            assert mocked_disable.call_args_list == [call('dummy_process_1')]
            mocked_disable.reset_mock()
        else:
            assert not mocked_disable.called


def test_rules_check_hash_identifiers(rules):
    """ Test the resolution of instances when hash_identifiers is set. """
    # set initial attributes
    rules.hash_identifiers = ['*']
    rules.identifiers = []
    # in mocked supvisors, xclock has a procnumber of 2
    # 1. test with unknown namespec
    rules.check_hash_identifiers('sample_test_1:xfontsel')
    # identifiers is unchanged
    assert rules.hash_identifiers == ['*']
    assert rules.identifiers == []
    # 2. update rules to test '#' with all instances available
    # address '10.0.0.3' has an index of 2 in address_mapper
    rules.check_hash_identifiers('sample_test_1:xclock')
    assert rules.identifiers == ['10.0.0.3']
    # 3. update rules to test '#' with a subset of instances available
    rules.hash_identifiers = ['10.0.0.0', '10.0.0.3', '10.0.0.5']
    rules.identifiers = []
    # here, at index 2 of this list, '10.0.0.5' can be found
    rules.check_hash_identifiers('sample_test_1:xclock')
    assert rules.identifiers == ['10.0.0.5']
    # 4. test the case where procnumber is greater than the subset list of instances available
    rules.hash_identifiers = ['10.0.0.1']
    rules.identifiers = []
    rules.check_hash_identifiers('sample_test_1:xclock')
    assert rules.identifiers == []


def test_rules_check_dependencies(mocker, rules):
    """ Test the dependencies in process rules. """
    mocked_hash = mocker.patch('supvisors.process.ProcessRules.check_hash_identifiers')
    mocked_auto = mocker.patch('supvisors.process.ProcessRules.check_autorestart')
    mocked_start = mocker.patch('supvisors.process.ProcessRules.check_start_sequence')
    mocked_stop = mocker.patch('supvisors.process.ProcessRules.check_stop_sequence')
    # test with no hash
    rules.hash_identifiers = []
    # check dependencies
    rules.check_dependencies('dummy')
    # test calls
    assert mocked_start.call_args_list == [call('dummy')]
    assert mocked_stop.call_args_list == [call('dummy')]
    assert mocked_auto.call_args_list == [call('dummy')]
    assert not mocked_hash.called
    # reset mocks
    mocker.resetall()
    # test with hash
    rules.hash_identifiers = ['*']
    # check dependencies
    rules.check_dependencies('dummy')
    # test calls
    assert mocked_start.call_args_list == [call('dummy')]
    assert mocked_stop.call_args_list == [call('dummy')]
    assert mocked_auto.call_args_list == [call('dummy')]
    assert mocked_hash.call_args_list == [call('dummy')]


# ProcessStatus part
def test_process_create(supvisors):
    """ Test the values set at ProcessStatus construction. """
    info = any_stopped_process_info()
    process = create_process(info, supvisors)
    # check application default attributes
    assert process.supvisors is supvisors
    assert process.application_name == info['group']
    assert process.process_name == info['name']
    assert process.namespec == make_namespec(info['group'], info['name'])
    assert process.state == ProcessStates.UNKNOWN
    assert process.forced_state is None
    assert process.forced_reason == ''
    assert process.expected_exit
    assert process.last_event_time == 0
    assert process.extra_args == ''
    assert process.running_identifiers == set()
    assert process.info_map == {}
    # rules part identical to construction
    assert process.rules.__dict__ == ProcessRules(supvisors).__dict__


def test_process_possible_identifiers(supvisors):
    """ Test the ProcessStatus.possible_identifiers method. """
    info = any_process_info()
    process = create_process(info, supvisors)
    process.add_info('10.0.0.2', info)
    process.add_info('10.0.0.4', info)
    # default identifiers is '*' in process rules
    assert process.possible_identifiers() == ['10.0.0.2', '10.0.0.4']
    # set a subset of identifiers in process rules so that there's no intersection with received status
    process.rules.identifiers = ['10.0.0.1', '10.0.0.3']
    assert process.possible_identifiers() == []
    # increase received status
    process.add_info('10.0.0.3', info)
    assert process.possible_identifiers() == ['10.0.0.3']
    # reset rules
    process.rules.identifiers = ['*']
    assert process.possible_identifiers() == ['10.0.0.2', '10.0.0.3', '10.0.0.4']
    # test with full status and all instances in rules
    for node_name in supvisors.supvisors_mapper.instances:
        process.add_info(node_name, info)
    assert process.possible_identifiers() == list(supvisors.supvisors_mapper.instances.keys())
    # restrict again instances in rules
    process.rules.identifiers = ['10.0.0.5']
    assert process.possible_identifiers() == ['10.0.0.5']


def test_status_stopped_process(supvisors):
    """ Test the stopped / running / crashed status with a STOPPED process. """
    info = any_process_info_by_state(ProcessStates.STOPPED)
    process = create_process(info, supvisors)
    process.add_info('10.0.0.1', info)
    assert process.stopped()
    assert not process.running()
    assert not process.crashed()
    assert not process.running_on('10.0.0.1')
    assert not process.running_on('10.0.0.2')
    assert not process.pid_running_on('10.0.0.1')
    assert not process.pid_running_on('10.0.0.2')
    # test again with forced state
    event = {'state': ProcessStates.STARTING, 'identifier': '10.0.0.2',
             'forced_state': ProcessStates.FATAL, 'spawnerr': ''}
    process.force_state(event)
    assert process._state == ProcessStates.STOPPED
    assert process.stopped()
    assert not process.running()
    assert process.crashed()
    assert not process.running_on('10.0.0.1')
    assert not process.running_on('10.0.0.2')
    assert not process.pid_running_on('10.0.0.1')
    assert not process.pid_running_on('10.0.0.2')
    # STOPPED does not reset the forced state
    process.reset_forced_state(ProcessStates.STOPPED)
    assert process._state == ProcessStates.STOPPED
    assert process.stopped()
    assert not process.running()
    assert process.crashed()
    # use empty param to reset the forced state
    process.reset_forced_state()
    assert process._state == ProcessStates.STOPPED
    assert process.stopped()
    assert not process.running()
    assert not process.crashed()


def test_status_backoff_process(supvisors):
    """ Test the stopped / running / crashed status with a BACKOFF process. """
    info = any_process_info_by_state(ProcessStates.BACKOFF)
    process = create_process(info, supvisors)
    process.add_info('10.0.0.1', info)
    assert not process.stopped()
    assert process.running()
    assert not process.crashed()
    assert process.running_on('10.0.0.1')
    assert not process.running_on('10.0.0.2')
    assert not process.pid_running_on('10.0.0.1')
    assert not process.pid_running_on('10.0.0.2')
    # test again with forced state
    event = {'state': ProcessStates.RUNNING, 'identifier': '10.0.0.1',
             'forced_state': ProcessStates.STOPPED, 'spawnerr': ''}
    process.force_state(event)
    assert process._state == ProcessStates.BACKOFF
    assert process.stopped()
    assert not process.running()
    assert not process.crashed()
    assert not process.running_on('10.0.0.1')
    assert not process.running_on('10.0.0.2')
    assert not process.pid_running_on('10.0.0.1')
    assert not process.pid_running_on('10.0.0.2')
    # BACKOFF resets the forced state
    process.reset_forced_state(ProcessStates.BACKOFF)
    assert process._state == ProcessStates.BACKOFF
    assert not process.stopped()
    assert process.running()
    assert not process.crashed()


def test_status_running_process(supvisors):
    """ Test the stopped / running / crashed status with a RUNNING process. """
    info = any_process_info_by_state(ProcessStates.RUNNING)
    process = create_process(info, supvisors)
    process.add_info('10.0.0.1', info)
    assert not process.stopped()
    assert process.running()
    assert not process.crashed()
    assert process.running_on('10.0.0.1')
    assert not process.running_on('10.0.0.2')
    assert process.pid_running_on('10.0.0.1')
    assert not process.pid_running_on('10.0.0.2')
    # test again with forced state
    # here, the expected state has been reached so the forced state is ignored
    event = {'state': ProcessStates.RUNNING, 'identifier': '10.0.0.1',
             'forced_state': ProcessStates.FATAL, 'spawnerr': ''}
    process.force_state(event)
    assert process._state == ProcessStates.RUNNING
    assert not process.stopped()
    assert process.running()
    assert not process.crashed()
    assert process.running_on('10.0.0.1')
    assert not process.running_on('10.0.0.2')
    assert process.pid_running_on('10.0.0.1')
    assert not process.pid_running_on('10.0.0.2')


def test_status_stopping_process(supvisors):
    """ Test the stopped / running / crashed status with a STOPPING process. """
    info = any_process_info_by_state(ProcessStates.STOPPING)
    process = create_process(info, supvisors)
    process.add_info('10.0.0.1', info)
    assert not process.stopped()
    assert not process.running()
    assert not process.crashed()
    assert not process.running_on('10.0.0.1')
    assert not process.running_on('10.0.0.2')
    assert not process.pid_running_on('10.0.0.1')
    assert not process.pid_running_on('10.0.0.2')
    # test again with forced state
    event = {'state': ProcessStates.STOPPED, 'identifier': '10.0.0.1',
             'forced_state': ProcessStates.STOPPED, 'spawnerr': ''}
    process.force_state(event)
    assert process._state == ProcessStates.STOPPING
    assert process.stopped()
    assert not process.running()
    assert not process.crashed()
    assert not process.running_on('10.0.0.1')
    assert not process.running_on('10.0.0.2')
    assert not process.pid_running_on('10.0.0.1')
    assert not process.pid_running_on('10.0.0.2')
    # STOPPING resets the forced state
    process.reset_forced_state(ProcessStates.STOPPING)
    assert process._state == ProcessStates.STOPPING
    assert not process.stopped()
    assert not process.running()
    assert not process.crashed()


def test_status_fatal_process(supvisors):
    """ Test the stopped / running / crashed status with a FATAL process. """
    info = any_process_info_by_state(ProcessStates.FATAL)
    process = create_process(info, supvisors)
    process.add_info('10.0.0.1', info)
    assert process.stopped()
    assert not process.running()
    assert process.crashed()
    assert not process.running_on('10.0.0.1')
    assert not process.running_on('10.0.0.2')
    assert not process.pid_running_on('10.0.0.1')
    assert not process.pid_running_on('10.0.0.2')
    # test again with forced state
    event = {'state': ProcessStates.RUNNING, 'identifier': '10.0.0.1',
             'forced_state': ProcessStates.STOPPED, 'spawnerr': ''}
    process.force_state(event)
    assert process._state == ProcessStates.FATAL
    assert process.stopped()
    assert not process.running()
    assert not process.crashed()
    assert not process.running_on('10.0.0.1')
    assert not process.running_on('10.0.0.2')
    assert not process.pid_running_on('10.0.0.1')
    assert not process.pid_running_on('10.0.0.2')
    # FATAL resets the forced state
    process.reset_forced_state(ProcessStates.FATAL)
    assert process._state == ProcessStates.FATAL
    assert process.stopped()
    assert not process.running()
    assert process.crashed()


def test_status_exited_process(supvisors):
    """ Test the stopped / running / crashed status with an EXITED process. """
    # test with expected_exit
    info = any_process_info_by_state(ProcessStates.EXITED)
    process = create_process(info, supvisors)
    process.add_info('10.0.0.1', info)
    process.expected_exit = True
    assert process.stopped()
    assert not process.running()
    assert not process.crashed()
    assert not process.running_on('10.0.0.1')
    assert not process.running_on('10.0.0.2')
    assert not process.pid_running_on('10.0.0.1')
    assert not process.pid_running_on('10.0.0.2')
    # test with unexpected_exit
    process.expected_exit = False
    assert process.stopped()
    assert not process.running()
    assert process.crashed()
    assert not process.running_on('10.0.0.1')
    assert not process.running_on('10.0.0.2')
    assert not process.pid_running_on('10.0.0.1')
    assert not process.pid_running_on('10.0.0.2')
    # test again with forced state
    event = {'state': ProcessStates.STOPPED, 'identifier': '10.0.0.1',
             'forced_state': ProcessStates.FATAL, 'spawnerr': ''}
    process.force_state(event)
    assert process._state == ProcessStates.EXITED
    assert process.stopped()
    assert not process.running()
    assert process.crashed()
    assert not process.running_on('10.0.0.1')
    assert not process.running_on('10.0.0.2')
    assert not process.pid_running_on('10.0.0.1')
    assert not process.pid_running_on('10.0.0.2')
    # EXITED resets the forced state
    process.reset_forced_state(ProcessStates.EXITED)
    assert process._state == ProcessStates.EXITED
    assert process.stopped()
    assert not process.running()
    assert process.crashed()


def test_process_conflicting(supvisors):
    """ Test the is ProcessStatus.conflicting method. """
    # when there is only one STOPPED process info, there is no conflict
    info = any_process_info_by_state(ProcessStates.STOPPED)
    process = create_process(info, supvisors)
    process.add_info('10.0.0.1', info)
    assert not process.conflicting()
    # the addition of a running address, still no conflict
    process.running_identifiers.add('10.0.0.2')
    assert not process.conflicting()
    # the addition of a new running address raises a conflict
    process.running_identifiers.add('10.0.0.4')
    assert process.conflicting()
    # remove the first running address to solve the conflict
    process.running_identifiers.remove('10.0.0.2')
    assert not process.conflicting()


def test_extra_args(mocker, supvisors):
    """ Test the accessors of the ProcessStatus extra_args. """
    info = any_process_info()
    process = create_process(info, supvisors)
    assert process._extra_args == ''
    assert process.extra_args == ''
    # test assignment
    process.extra_args = 'new args'
    assert process._extra_args == 'new args'
    assert process.extra_args == 'new args'
    # test internal exception when process unknown to the local Supervisor
    mocker.patch.object(supvisors.supervisor_data, 'update_extra_args', side_effect=KeyError)
    process.extra_args = 'another args'
    assert process._extra_args == 'another args'
    assert process.extra_args == 'another args'


def test_serialization(supvisors):
    """ Test the serialization of the ProcessStatus. """
    # test with a STOPPED process
    info = any_process_info_by_state(ProcessStates.STOPPED)
    process = create_process(info, supvisors)
    process.add_info('10.0.0.1', info)
    serialized = process.serial()
    assert serialized == {'application_name': info['group'], 'process_name': info['name'],
                          'statecode': 0, 'statename': 'STOPPED', 'expected_exit': info['expected'],
                          'last_event_time': process.last_event_time, 'identifiers': [], 'extra_args': ''}
    # test that returned structure is serializable using pickle
    dumped = pickle.dumps(serialized)
    loaded = pickle.loads(dumped)
    assert loaded == serialized
    # test again with forced state
    event = {'state': ProcessStates.STARTING, 'identifier': '10.0.0.1',
             'forced_state': ProcessStates.FATAL, 'spawnerr': 'anything'}
    process.force_state(event)
    assert process._state == ProcessStates.STOPPED
    serialized = process.serial()
    assert serialized == {'application_name': info['group'], 'process_name': info['name'],
                          'statecode': 200, 'statename': 'FATAL', 'expected_exit': info['expected'],
                          'last_event_time': process.last_event_time, 'identifiers': [], 'extra_args': ''}


def test_get_last_description(supvisors):
    """ Test the ViewContext.get_process_last_desc method. """
    # create ProcessStatus instance
    process = create_process({'group': 'dummy_application', 'name': 'dummy_proc'}, supvisors)
    process.info_map = {'10.0.0.1': {'local_time': 10, 'stop': 32, 'description': 'desc1', 'state': 0},
                        '10.0.0.2': {'local_time': 30, 'stop': 12, 'description': 'Not started'},
                        '10.0.0.3': {'local_time': 20, 'stop': 22, 'description': 'desc3'}}
    # state is not forced by default
    # test method return on non-running process
    assert process.get_last_description() == ('10.0.0.1', 'desc1 on 10.0.0.1')
    # test method return on running process
    process.running_identifiers.add('10.0.0.3')
    assert process.get_last_description() == ('10.0.0.3', 'desc3 on 10.0.0.3')
    # test method return on multiple running processes
    process.running_identifiers.add('10.0.0.2')
    assert process.get_last_description() == ('10.0.0.2', 'Not started')
    # test again with forced state
    event = {'state': ProcessStates.STARTING, 'identifier': '10.0.0.1',
             'forced_state': ProcessStates.FATAL, 'spawnerr': 'global crash'}
    process.force_state(event)
    assert process.get_last_description() == (None, 'global crash')
    process.running_identifiers = set()
    assert process.get_last_description() == (None, 'global crash')


def test_add_info(supvisors):
    """ Test the addition of a process info into the ProcessStatus. """
    # get a process info and complement extra_args
    info = process_info_by_name('xclock')
    info['extra_args'] = '-x dummy'
    assert 'uptime' not in info
    # 1. create ProcessStatus instance
    process = create_process(info, supvisors)
    process.extra_args = 'something else'
    process.add_info('10.0.0.1', info)
    # check last event info
    assert process.last_event_time > 0
    last_event_time = process.last_event_time
    assert last_event_time == info['local_time']
    # check contents
    assert len(process.info_map) == 1
    assert process.info_map['10.0.0.1'] is info
    assert info['uptime'] == info['now'] - info['start']
    assert not process.running_identifiers
    assert process.state == ProcessStates.STOPPING
    assert process.expected_exit
    assert not info['has_crashed']
    assert not process.has_crashed()
    # extra_args are reset when using add_info
    assert process.extra_args == ''
    assert info['extra_args'] == ''
    # check forced_state
    assert process.forced_state is None
    assert process.forced_reason == ''
    event = {'state': ProcessStates.STARTING, 'identifier': '10.0.0.1',
             'forced_state': ProcessStates.FATAL, 'spawnerr': 'failure'}
    process.force_state(event)
    assert process.forced_state == ProcessStates.FATAL
    assert process.forced_reason == 'failure'
    assert process.state == ProcessStates.FATAL
    # 2. replace with an EXITED process info
    info = any_process_info_by_state(ProcessStates.EXITED)
    info['expected'] = False
    process.add_info('10.0.0.1', info)
    # check last event info
    assert process.last_event_time >= last_event_time
    last_event_time = process.last_event_time
    assert last_event_time == info['local_time']
    # check contents
    assert len(process.info_map) == 1
    assert process.info_map['10.0.0.1'] is info
    assert info['uptime'] == 0
    assert not process.running_identifiers
    assert process.state == ProcessStates.EXITED
    assert not process.expected_exit
    assert process.has_crashed
    # check forced_state
    assert process.forced_state is None
    assert process.forced_reason == ''
    # update rules to test '#'
    process.rules.hash_addresses = ['*']
    # 3. add a RUNNING process info
    info = any_process_info_by_state(ProcessStates.RUNNING)
    process.add_info('10.0.0.2', info)
    # check last event info
    assert process.last_event_time >= last_event_time
    assert last_event_time == info['local_time']
    # check contents
    assert len(process.info_map) == 2
    assert process.info_map['10.0.0.2'] is info
    assert info['uptime'] == info['now'] - info['start']
    assert process.running_identifiers == {'10.0.0.2'}
    assert process.state == ProcessStates.RUNNING
    assert process.expected_exit
    assert process.has_crashed


def test_update_info(supvisors):
    """ Test the update of the ProcessStatus upon reception of a process event. """
    # 1. add a STOPPED process infos into a process status
    info = any_process_info_by_state(ProcessStates.STOPPED)
    process = create_process(info, supvisors)
    process.add_info('10.0.0.1', info)
    # test last event info stored
    assert process.last_event_time > 0
    last_event_time = process.last_event_time
    assert last_event_time == info['local_time']
    # check changes on status
    assert process.info_map['10.0.0.1']['state'] == ProcessStates.STOPPED
    assert process.state == ProcessStates.STOPPED
    assert process.extra_args == ''
    assert not info['has_crashed']
    assert not process.has_crashed()
    assert not process.running_identifiers
    # 3. update with a STARTING event
    process.update_info('10.0.0.1', {'state': ProcessStates.STARTING, 'now': 10, 'extra_args': '-x dummy'})
    # test last event info stored
    assert process.last_event_time >= last_event_time
    last_event_time = process.last_event_time
    assert last_event_time == info['local_time']
    # check changes on status
    info = process.info_map['10.0.0.1']
    assert info['state'] == ProcessStates.STARTING
    assert process.state == ProcessStates.STARTING
    assert process.extra_args == '-x dummy'
    assert not info['has_crashed']
    assert not process.has_crashed()
    assert process.running_identifiers == {'10.0.0.1'}
    assert info['now'] == 10
    assert info['start'] == 10
    assert info['uptime'] == 0
    # 4. update with a RUNNING event
    process.update_info('10.0.0.1', {'state': ProcessStates.RUNNING, 'now': 15, 'pid': 1234,
                                     'extra_args': '-z another'})
    # test last event info stored
    assert process.last_event_time >= last_event_time
    last_event_time = process.last_event_time
    assert last_event_time == info['local_time']
    # check changes
    assert info['state'] == ProcessStates.RUNNING
    assert process.state == ProcessStates.RUNNING
    assert process.running_identifiers == {'10.0.0.1'}
    assert process.extra_args == '-z another'
    assert not info['has_crashed']
    assert not process.has_crashed()
    assert info['pid'] == 1234
    assert info['now'] == 15
    assert info['start'] == 10
    assert info['uptime'] == 5
    # check forced_state
    assert process.forced_state is None
    assert process.forced_reason == ''
    event = {'state': ProcessStates.STARTING, 'identifier': '10.0.0.1',
             'forced_state': ProcessStates.FATAL, 'spawnerr': 'failure'}
    process.force_state(event)
    assert process.forced_state == ProcessStates.FATAL
    assert process.forced_reason == 'failure'
    assert process.state == ProcessStates.FATAL
    # 5.a add a new STOPPED process info
    process.add_info('10.0.0.2', any_process_info_by_state(ProcessStates.STOPPED))
    # test last event info stored
    assert process.last_event_time >= last_event_time
    last_event_time = process.last_event_time
    assert last_event_time == info['local_time']
    assert process.state == ProcessStates.FATAL
    # extra_args has been reset
    assert process.extra_args == ''
    assert not info['has_crashed']
    assert not process.has_crashed()
    # 5.b update with STARTING / RUNNING events
    process.update_info('10.0.0.2', {'state': ProcessStates.STARTING, 'now': 20, 'extra_args': '-x dummy'})
    process.update_info('10.0.0.2', {'state': ProcessStates.RUNNING, 'now': 25, 'pid': 4321, 'extra_args': ''})
    # test last event info stored
    assert process.last_event_time >= last_event_time
    last_event_time = process.last_event_time
    assert last_event_time == info['local_time']
    # check state and addresses
    assert process.state == ProcessStates.RUNNING
    assert process.extra_args == ''
    assert not info['has_crashed']
    assert not process.has_crashed()
    assert process.running_identifiers == {'10.0.0.1', '10.0.0.2'}
    # 6. update with an EXITED event
    process.update_info('10.0.0.1', {'state': ProcessStates.EXITED, 'now': 30, 'expected': False, 'extra_args': ''})
    # test last event info stored
    assert process.last_event_time >= last_event_time
    last_event_time = process.last_event_time
    assert last_event_time == info['local_time']
    # check changes
    assert info['state'] == ProcessStates.EXITED
    assert process.state == ProcessStates.RUNNING
    assert process.extra_args == ''
    assert info['has_crashed']
    assert process.has_crashed()
    assert process.running_identifiers == {'10.0.0.2'}
    assert info['pid'] == 1234
    assert info['now'] == 30
    assert info['start'] == 10
    assert info['uptime'] == 0
    assert not info['expected']
    # 7. update with an STOPPING event
    info = process.info_map['10.0.0.2']
    process.update_info('10.0.0.2', {'state': ProcessStates.STOPPING, 'now': 35, 'extra_args': ''})
    # test last event info stored
    assert process.last_event_time >= last_event_time
    last_event_time = process.last_event_time
    assert last_event_time == info['local_time']
    # check changes
    assert info['state'] == ProcessStates.STOPPING
    assert process.state == ProcessStates.STOPPING
    assert process.extra_args == ''
    assert not info['has_crashed']
    assert process.has_crashed()
    assert process.running_identifiers == {'10.0.0.2'}
    assert info['pid'] == 4321
    assert info['now'] == 35
    assert info['start'] == 20
    assert info['uptime'] == 15
    assert info['expected']
    # 8. update with an STOPPED event
    process.update_info('10.0.0.2', {'state': ProcessStates.STOPPED, 'now': 40, 'extra_args': ''})
    # test last event info stored
    assert process.last_event_time >= last_event_time
    last_event_time = process.last_event_time
    assert last_event_time == info['local_time']
    # check changes
    assert info['state'] == ProcessStates.STOPPED
    assert process.state == ProcessStates.STOPPED
    assert process.extra_args == ''
    assert not info['has_crashed']
    assert process.has_crashed()
    assert not process.running_identifiers
    assert info['pid'] == 4321
    assert info['now'] == 40
    assert info['start'] == 20
    assert info['uptime'] == 0
    assert info['expected']


def test_update_times(supvisors):
    """ Test the update of the time entries for a process info belonging to a ProcessStatus. """
    # add 2 process infos into a process status
    info = any_process_info_by_state(ProcessStates.STOPPING)
    process = create_process(info, supvisors)
    process.add_info('10.0.0.1', info)
    process.add_info('10.0.0.2', any_process_info_by_state(ProcessStates.STOPPED))
    # get their time values
    now_1 = process.info_map['10.0.0.1']['now']
    uptime_1 = process.info_map['10.0.0.1']['uptime']
    now_2 = process.info_map['10.0.0.2']['now']
    # update times on address 2
    process.update_times('10.0.0.2', now_2 + 10)
    # check that nothing changed for address 1
    assert process.info_map['10.0.0.1']['now'] == now_1
    assert process.info_map['10.0.0.1']['uptime'] == uptime_1
    # check that times changed for address 2 (uptime excepted)
    assert process.info_map['10.0.0.2']['now'] == now_2 + 10
    assert process.info_map['10.0.0.2']['uptime'] == 0
    # update times on address 1
    process.update_times('10.0.0.1', now_1 + 20)
    # check that times changed for address 1 (including uptime)
    assert process.info_map['10.0.0.1']['now'] == now_1 + 20
    assert process.info_map['10.0.0.1']['uptime'] == uptime_1 + 20
    # check that nothing changed for address 2
    assert process.info_map['10.0.0.2']['now'] == now_2 + 10
    assert process.info_map['10.0.0.2']['uptime'] == 0


def test_update_uptime():
    """ Test the update of uptime entry in a Process info dictionary. """
    # check times on a RUNNING process info
    info = {'start': 50, 'now': 75}
    for state in _process_states_by_code:
        info['state'] = state
        ProcessStatus.update_uptime(info)
        if state in [ProcessStates.RUNNING, ProcessStates.STOPPING]:
            assert info['uptime'] == 25
        else:
            assert info['uptime'] == 0


def test_invalidate_nodes(supvisors):
    """ Test the invalidation of instances. """
    # create conflict directly with 3 process info
    info = any_process_info_by_state(ProcessStates.BACKOFF)
    process = create_process(info, supvisors)
    process.add_info('10.0.0.1', info)
    process.add_info('10.0.0.2', any_process_info_by_state(ProcessStates.RUNNING))
    process.add_info('10.0.0.3', any_process_info_by_state(ProcessStates.STARTING))
    # check the conflict
    assert process.conflicting()
    assert process.state == ProcessStates.RUNNING
    # invalidate RUNNING one
    assert not process.invalidate_identifier('10.0.0.2')
    # check state became FATAL on invalidated address
    assert process.info_map['10.0.0.2']['state'] == ProcessStates.FATAL
    # check the conflict
    assert process.conflicting()
    assert process.state == ProcessStates.BACKOFF
    # invalidate BACKOFF one
    assert not process.invalidate_identifier('10.0.0.1')
    # check state became FATAL on invalidated address
    assert process.info_map['10.0.0.1']['state'] == ProcessStates.FATAL
    # check 1 address: no conflict
    assert not process.conflicting()
    assert process.state == ProcessStates.STARTING
    # invalidate STARTING one
    process.invalidate_identifier('10.0.0.3')
    # check state became FATAL on invalidated address
    assert process.info_map['10.0.0.3']['state'] == ProcessStates.FATAL
    # check 0 address: no conflict
    assert not process.conflicting()
    # check that synthetic state became FATAL
    assert process.state == ProcessStates.FATAL


def test_remove_node(supvisors):
    """ Test the removal of instances. """
    # create conflict directly with 2 process info
    info = any_process_info()
    process = create_process(info, supvisors)
    process.add_info('10.0.0.1', info)
    process.add_info('10.0.0.2', any_process_info())
    # check process info_map
    assert sorted(process.info_map.keys()) == ['10.0.0.1', '10.0.0.2']
    assert not process.remove_identifier('10.0.0.2')
    assert sorted(process.info_map.keys()) == ['10.0.0.1']
    assert process.remove_identifier('10.0.0.1')
    assert sorted(process.info_map.keys()) == []


def test_update_status(supvisors):
    """ Test the update of state and running Supvisors instances. """
    # increase logger level to hit special log traces
    supvisors.logger.level = LevelsByName.BLAT
    # update_status is called in the construction
    info = any_process_info_by_state(ProcessStates.FATAL)
    process = create_process(info, supvisors)
    process.add_info('10.0.0.3', info)
    assert process.running_identifiers == set()
    assert process.state == ProcessStates.FATAL
    assert not process.expected_exit
    # add a STOPPED process info
    process.info_map['10.0.0.1'] = any_process_info_by_state(ProcessStates.STOPPED)
    process.update_status('10.0.0.1', ProcessStates.STOPPED)
    assert process.running_identifiers == set()
    assert process.state == ProcessStates.STOPPED
    assert process.expected_exit
    # replace with an EXITED process info
    process.info_map['10.0.0.1'] = any_process_info_by_state(ProcessStates.EXITED)
    process.update_status('10.0.0.1', ProcessStates.EXITED)
    assert process.running_identifiers == set()
    assert process.state == ProcessStates.EXITED
    assert process.expected_exit
    # add a STARTING process info
    process.info_map['10.0.0.2'] = any_process_info_by_state(ProcessStates.STARTING)
    process.update_status('10.0.0.2', ProcessStates.STARTING)
    assert process.running_identifiers == {'10.0.0.2'}
    assert process.state == ProcessStates.STARTING
    assert process.expected_exit
    # add a BACKOFF process info
    process.info_map['10.0.0.3'] = any_process_info_by_state(ProcessStates.BACKOFF)
    process.update_status('10.0.0.3', ProcessStates.STARTING)
    assert process.running_identifiers == {'10.0.0.3', '10.0.0.2'}
    assert process.state == ProcessStates.BACKOFF
    assert process.expected_exit
    # replace STARTING process info with RUNNING
    process.info_map['10.0.0.2'] = any_process_info_by_state(ProcessStates.RUNNING)
    process.update_status('10.0.0.2', ProcessStates.RUNNING)
    assert process.running_identifiers == {'10.0.0.3', '10.0.0.2'}
    assert process.state == ProcessStates.RUNNING
    assert process.expected_exit
    # replace BACKOFF process info with FATAL
    process.info_map['10.0.0.3'] = any_process_info_by_state(ProcessStates.FATAL)
    process.update_status('10.0.0.3', ProcessStates.FATAL)
    assert process.running_identifiers == {'10.0.0.2'}
    assert process.state == ProcessStates.RUNNING
    assert process.expected_exit
    # replace RUNNING process info with STOPPED
    # in ProcessInfoDatabase, EXITED processes have a stop date later than STOPPED processes
    process.info_map['10.0.0.2'] = any_process_info_by_state(ProcessStates.STOPPED)
    process.update_status('10.0.0.2', ProcessStates.STOPPED)
    assert not process.running_identifiers
    assert process.state == ProcessStates.EXITED
    assert process.expected_exit


def test_process_evaluate_conflict(supvisors):
    """ Test the determination of a synthetic state in case of conflict. """
    # when there is only one STOPPED process info, there is no conflict
    # this method is expected to be called aonly when a conflict (multiple running processes) is detected
    # the state is evaluated against running states. STOPPED leads to UNKNOWN
    info = any_process_info_by_state(ProcessStates.STOPPED)
    process = create_process(info, supvisors)
    process.add_info('10.0.0.1', info)
    process._evaluate_conflict()
    assert process.state == ProcessStates.UNKNOWN
    # the addition of one RUNNING process info does not raise any conflict
    process.info_map['10.0.0.2'] = any_process_info_by_state(ProcessStates.RUNNING)
    process.running_identifiers = {'10.0.0.2'}
    process._evaluate_conflict()
    # the addition of one STARTING process raises a conflict
    process.info_map['10.0.0.3'] = any_process_info_by_state(ProcessStates.STARTING)
    process.running_identifiers.add('10.0.0.3')
    process._evaluate_conflict()
    assert process.state == ProcessStates.RUNNING
    # replace the RUNNING process info with a BACKOFF process info
    process.info_map['10.0.0.2'] = any_process_info_by_state(ProcessStates.BACKOFF)
    process._evaluate_conflict()
    assert process.state == ProcessStates.BACKOFF
    # replace the BACKOFF process info with a STARTING process info
    process.info_map['10.0.0.2'] = any_process_info_by_state(ProcessStates.STARTING)
    process._evaluate_conflict()
    assert process.state == ProcessStates.STARTING
    # replace the STARTING process info with an EXITED process info
    process.info_map['10.0.0.2'] = any_process_info_by_state(ProcessStates.EXITED)
    process.running_identifiers.remove('10.0.0.2')
    process._evaluate_conflict()
    assert process.state == ProcessStates.STARTING


def test_process_running_state():
    """ Test the choice of a single state among a list of states. """
    # check running states with several combinations
    assert ProcessStatus.running_state(STOPPED_STATES) == ProcessStates.UNKNOWN
    states = {ProcessStates.STOPPING}
    assert ProcessStatus.running_state(states) == ProcessStates.STOPPING
    states = {ProcessStates.STOPPING, ProcessStates.RUNNING}
    assert ProcessStatus.running_state(states) == ProcessStates.RUNNING
    assert ProcessStatus.running_state(RUNNING_STATES) == ProcessStates.RUNNING
    states = {ProcessStates.STARTING, ProcessStates.BACKOFF}
    assert ProcessStatus.running_state(states) == ProcessStates.BACKOFF
    states = {ProcessStates.STARTING}
    assert ProcessStatus.running_state(states) == ProcessStates.STARTING
    states = {ProcessStates.STOPPING, *RUNNING_STATES, *STOPPED_STATES}
    assert ProcessStatus.running_state(states) == ProcessStates.RUNNING
