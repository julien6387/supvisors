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

import pytest

from supervisor.states import ProcessStates, _process_states_by_code
from unittest.mock import call, patch

from .base import any_process_info, any_stopped_process_info, process_info_by_name, any_process_info_by_state
from .conftest import create_process


# ProcessRules part
@pytest.fixture
def rules(supvisors):
    """ Return the instance to test. """
    from supvisors.process import ProcessRules
    return ProcessRules(supvisors)


def test_rules_create(supvisors, rules):
    """ Test the values set at construction. """
    from supvisors.ttypes import RunningFailureStrategies
    assert rules.supvisors is supvisors
    assert rules.node_names == ['*']
    assert rules.start_sequence == 0
    assert rules.stop_sequence == 0
    assert not rules.required
    assert not rules.wait_exit
    assert rules.expected_load == 0
    assert rules.running_failure_strategy == RunningFailureStrategies.CONTINUE


def test_rules_str(rules):
    """ Test the string output. """
    assert str(rules) == "node_names=['*'] hash_node_names=None start_sequence=0 stop_sequence=0 required=False"\
        " wait_exit=False expected_load=0 running_failure_strategy=CONTINUE"


def test_rules_serial(rules):
    """ Test the serialization of the ProcessRules object. """
    assert rules.serial() == {'addresses': ['*'], 'start_sequence': 0, 'stop_sequence': 0,
                              'required': False, 'wait_exit': False, 'expected_loading': 0,
                              'running_failure_strategy': 'CONTINUE'}


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


def test_rules_check_autorestart(rules):
    """ Test the dependency related to running failure strategy in process rules.
    Done in a separate test as it impacts the supervisor internal model. """
    from supvisors.ttypes import RunningFailureStrategies
    # test that only the CONTINUE strategy keeps the autorestart
    mocked_disable = rules.supvisors.info_source.disable_autorestart
    for strategy in RunningFailureStrategies:
        rules.running_failure_strategy = strategy
        rules.check_autorestart('dummy_process_1')
        if strategy == RunningFailureStrategies.CONTINUE:
            assert not mocked_disable.called
        else:
            assert mocked_disable.call_args_list == [call('dummy_process_1')]
            mocked_disable.reset_mock()


def test_rules_check_hash_nodes(rules):
    """ Test the resolution of addresses when hash_address is set. """
    # check initial attributes
    assert rules.node_names == ['*']
    assert rules.hash_node_names is None
    # in mocked supvisors, xclock has a procnumber of 2
    # 1. test with unknown namespec
    rules.check_hash_nodes('sample_test_1:xfontsel')
    # node_names is unchanged
    assert rules.node_names == ['*']
    # 2. update rules to test '#' with all nodes available
    rules.hash_node_names = ['*']
    rules.node_names = []
    # address '10.0.0.2' has an index of 2 in address_mapper
    rules.check_hash_nodes('sample_test_1:xclock')
    assert rules.node_names == ['10.0.0.2']
    # 3. update rules to test '#' with a subset of nodes available
    rules.hash_node_names = ['10.0.0.0', '10.0.0.3', '10.0.0.5']
    rules.node_names = []
    # here, at index 2 of this list, '10.0.0.5' can be found
    rules.check_hash_nodes('sample_test_1:xclock')
    assert rules.node_names == ['10.0.0.5']
    # 4. test the case where procnumber is greater than the subset list of nodes available
    rules.hash_node_names = ['10.0.0.1']
    rules.node_names = []
    rules.check_hash_nodes('sample_test_1:xclock')
    assert rules.node_names == []


@patch('supvisors.process.ProcessRules.check_hash_nodes')
@patch('supvisors.process.ProcessRules.check_autorestart')
@patch('supvisors.process.ProcessRules.check_start_sequence')
def test_rules_check_dependencies(mocked_start, mocked_auto, mocked_hash, rules):
    """ Test the dependencies in process rules. """
    # test with no hash
    rules.hash_node_names = []
    # check dependencies
    rules.check_dependencies('dummy')
    # test calls
    assert mocked_start.call_args_list == [call('dummy')]
    assert mocked_auto.call_args_list == [call('dummy')]
    assert not mocked_hash.called
    # reset mocks
    mocked_start.reset_mock()
    mocked_auto.reset_mock()
    # test with hash
    rules.hash_node_names = ['*']
    # check dependencies
    rules.check_dependencies('dummy')
    # test calls
    assert mocked_start.call_args_list == [call('dummy')]
    assert mocked_auto.call_args_list == [call('dummy')]
    assert mocked_hash.call_args_list == [call('dummy')]


# ProcessStatus part
def test_process_create(supvisors):
    """ Test the values set at construction. """
    from supervisor.states import ProcessStates
    from supvisors.process import ProcessRules
    info = any_stopped_process_info()
    process = create_process(info, supvisors)
    # check application default attributes
    assert process.supvisors is supvisors
    assert process.application_name == info['group']
    assert process.process_name == info['name']
    assert process.state == ProcessStates.UNKNOWN
    assert process.expected_exit
    assert process.last_event_time == 0
    assert process.extra_args == ''
    assert process.running_nodes == set()
    assert process.info_map == {}
    # rules part identical to construction
    assert process.rules.__dict__ == ProcessRules(supvisors).__dict__


def test_namespec(supvisors):
    """ Test of the process namspec. """
    # test namespec when group and name are different
    info = process_info_by_name('segv')
    process = create_process(info, supvisors)
    assert process.namespec() == 'crash:segv'
    # test namespec when group and name are identical
    info = process_info_by_name('firefox')
    process = create_process(info, supvisors)
    assert process.namespec() == 'firefox'


def test_possible_nodes(supvisors):
    """ Test the possible_nodes method. """
    info = any_process_info()
    process = create_process(info, supvisors)
    process.add_info('10.0.0.2', info)
    process.add_info('10.0.0.4', info)
    # default node_names is '*' in process rules
    assert process.possible_nodes() == ['10.0.0.2', '10.0.0.4']
    # set a subset of node_names in process rules so that there's no intersection with received status
    process.rules.node_names = ['10.0.0.1', '10.0.0.3']
    assert process.possible_nodes() == []
    # increase received status
    process.add_info('10.0.0.3', info)
    assert process.possible_nodes() == ['10.0.0.3']
    # reset rules
    process.rules.node_names = ['*']
    assert process.possible_nodes() == ['10.0.0.2', '10.0.0.3', '10.0.0.4']
    # test with full status and all nodes in rules
    for node_name in supvisors.address_mapper.node_names:
        process.add_info(node_name, info)
    assert process.possible_nodes() == supvisors.address_mapper.node_names
    # restrict again nodes in rules
    process.rules.node_names = ['10.0.0.5']
    assert process.possible_nodes() == ['10.0.0.5']


def test_status_stopped_process(supvisors):
    """ Test the stopped / running / crashed status with a STOPPED process. """
    from supervisor.states import ProcessStates
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


def test_conflicting(supvisors):
    """ Test the process conflicting rules. """
    from supervisor.states import ProcessStates
    # when there is only one STOPPED process info, there is no conflict
    info = any_process_info_by_state(ProcessStates.STOPPED)
    process = create_process(info, supvisors)
    process.add_info('10.0.0.1', info)
    assert not process.conflicting()
    # the addition of a running address, still no conflict
    process.running_nodes.add('10.0.0.2')
    assert not process.conflicting()
    # the addition of a new running address raises a conflict
    process.running_nodes.add('10.0.0.4')
    assert process.conflicting()
    # remove the first running address to solve the conflict
    process.running_nodes.remove('10.0.0.2')
    assert not process.conflicting()


def test_serialization(supvisors):
    """ Test the serialization of the ProcessStatus. """
    import pickle
    from supervisor.states import ProcessStates
    # test with a STOPPED process
    info = any_process_info_by_state(ProcessStates.STOPPED)
    process = create_process(info, supvisors)
    process.add_info('10.0.0.1', info)
    serialized = process.serial()
    assert serialized == {'application_name': info['group'],
                          'process_name': info['name'],
                          'statecode': 0,
                          'statename': 'STOPPED',
                          'expected_exit': info['expected'],
                          'last_event_time': process.last_event_time,
                          'addresses': [],
                          'extra_args': ''}
    # test that returned structure is serializable using pickle
    dumped = pickle.dumps(serialized)
    loaded = pickle.loads(dumped)
    assert loaded == serialized


def test_add_info(supvisors):
    """ Test the addition of a process info into the ProcessStatus. """
    from supervisor.states import ProcessStates
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
    assert not process.running_nodes
    assert process.state == ProcessStates.STOPPING
    assert process.expected_exit
    # extra_args are reset when using add_info
    assert process.extra_args == ''
    assert info['extra_args'] == ''
    # 2. replace with an EXITED process info
    info = any_process_info_by_state(ProcessStates.EXITED)
    process.add_info('10.0.0.1', info)
    # check last event info
    assert process.last_event_time >= last_event_time
    last_event_time = process.last_event_time
    assert last_event_time == info['local_time']
    # check contents
    assert len(process.info_map) == 1
    assert process.info_map['10.0.0.1'] is info
    assert info['uptime'] == 0
    assert not process.running_nodes
    assert process.state == ProcessStates.EXITED
    assert process.expected_exit
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
    assert process.running_nodes == {'10.0.0.2'}
    assert process.state == ProcessStates.RUNNING
    assert process.expected_exit


def test_update_info(supvisors):
    """ Test the update of the ProcessStatus upon reception of a process event. """
    from supervisor.states import ProcessStates
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
    assert not process.running_nodes
    # 2. update with a STARTING event on an unknown address
    process.update_info('10.0.0.2', {'state': ProcessStates.STARTING, 'now': 10})
    # test last event info stored
    assert process.last_event_time >= last_event_time
    last_event_time = process.last_event_time
    assert last_event_time == info['local_time']
    # check no change on other status
    info = process.info_map['10.0.0.1']
    assert info['state'] == ProcessStates.STOPPED
    assert process.state == ProcessStates.STOPPED
    assert process.extra_args == ''
    assert not process.running_nodes
    # 3. update with a STARTING event
    process.update_info('10.0.0.1', {'state': ProcessStates.STARTING,
                                     'now': 10,
                                     'extra_args': '-x dummy'})
    # test last event info stored
    assert process.last_event_time >= last_event_time
    last_event_time = process.last_event_time
    assert last_event_time == info['local_time']
    # check changes on status
    info = process.info_map['10.0.0.1']
    assert info['state'] == ProcessStates.STARTING
    assert process.state == ProcessStates.STARTING
    assert process.extra_args == '-x dummy'
    assert process.running_nodes == {'10.0.0.1'}
    assert info['now'] == 10
    assert info['start'] == 10
    assert info['uptime'] == 0
    # 4. update with a RUNNING event
    process.update_info('10.0.0.1', {'state': ProcessStates.RUNNING,
                                     'now': 15,
                                     'pid': 1234,
                                     'extra_args': '-z another'})
    # test last event info stored
    assert process.last_event_time >= last_event_time
    last_event_time = process.last_event_time
    assert last_event_time == info['local_time']
    # check changes
    assert info['state'] == ProcessStates.RUNNING
    assert process.state == ProcessStates.RUNNING
    assert process.running_nodes == {'10.0.0.1'}
    assert process.extra_args == '-z another'
    assert info['pid'] == 1234
    assert info['now'] == 15
    assert info['start'] == 10
    assert info['uptime'] == 5
    # 5.a add a new STOPPED process info
    process.add_info('10.0.0.2', any_process_info_by_state(ProcessStates.STOPPED))
    # test last event info stored
    assert process.last_event_time >= last_event_time
    last_event_time = process.last_event_time
    assert last_event_time == info['local_time']
    # extra_args has been reset
    assert process.extra_args == ''
    # 5.b update with STARTING / RUNNING events
    process.update_info('10.0.0.2', {'state': ProcessStates.STARTING,
                                     'now': 20,
                                     'extra_args': '-x dummy'})
    process.update_info('10.0.0.2', {'state': ProcessStates.RUNNING,
                                     'now': 25,
                                     'pid': 4321,
                                     'extra_args': ''})
    # test last event info stored
    assert process.last_event_time >= last_event_time
    last_event_time = process.last_event_time
    assert last_event_time == info['local_time']
    # check state and addresses
    assert process.state == ProcessStates.RUNNING
    assert process.extra_args == ''
    assert process.running_nodes == {'10.0.0.1', '10.0.0.2'}
    # 6. update with an EXITED event
    process.update_info('10.0.0.1', {'state': ProcessStates.EXITED,
                                     'now': 30,
                                     'expected': False,
                                     'extra_args': ''})
    # test last event info stored
    assert process.last_event_time >= last_event_time
    last_event_time = process.last_event_time
    assert last_event_time == info['local_time']
    # check changes
    assert info['state'] == ProcessStates.EXITED
    assert process.state == ProcessStates.RUNNING
    assert process.extra_args == ''
    assert process.running_nodes == {'10.0.0.2'}
    assert info['pid'] == 1234
    assert info['now'] == 30
    assert info['start'] == 10
    assert info['uptime'] == 0
    assert not info['expected']
    # 7. update with an STOPPING event
    info = process.info_map['10.0.0.2']
    process.update_info('10.0.0.2', {'state': ProcessStates.STOPPING,
                                     'now': 35,
                                     'extra_args': ''})
    # test last event info stored
    assert process.last_event_time >= last_event_time
    last_event_time = process.last_event_time
    assert last_event_time == info['local_time']
    # check changes
    assert info['state'] == ProcessStates.STOPPING
    assert process.state == ProcessStates.STOPPING
    assert process.extra_args == ''
    assert process.running_nodes == {'10.0.0.2'}
    assert info['pid'] == 4321
    assert info['now'] == 35
    assert info['start'] == 20
    assert info['uptime'] == 15
    assert info['expected']
    # 8. update with an STOPPED event
    process.update_info('10.0.0.2', {'state': ProcessStates.STOPPED,
                                     'now': 40,
                                     'extra_args': ''})
    # test last event info stored
    assert process.last_event_time >= last_event_time
    last_event_time = process.last_event_time
    assert last_event_time == info['local_time']
    # check changes
    assert info['state'] == ProcessStates.STOPPED
    assert process.state == ProcessStates.STOPPED
    assert process.extra_args == ''
    assert not process.running_nodes
    assert info['pid'] == 4321
    assert info['now'] == 40
    assert info['start'] == 20
    assert info['uptime'] == 0
    assert info['expected']


def test_update_times(supvisors):
    """ Test the update of the time entries for a process info belonging to a ProcessStatus. """
    from supervisor.states import ProcessStates
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
    from supvisors.process import ProcessStatus
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
    """ Test the invalidation of nodes. """
    from supervisor.states import ProcessStates
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
    process.invalidate_node('10.0.0.2', False)
    # check state became UNKNOWN on invalidated address
    assert process.info_map['10.0.0.2']['state'] == ProcessStates.UNKNOWN
    # check the conflict
    assert process.conflicting()
    # check new synthetic state
    assert process.state == ProcessStates.BACKOFF
    # invalidate BACKOFF one
    process.invalidate_node('10.0.0.1', False)
    # check state became UNKNOWN on invalidated address
    assert process.info_map['10.0.0.1']['state'] == ProcessStates.UNKNOWN
    # check 1 address: no conflict
    assert not process.conflicting()
    # check synthetic state (running process)
    assert process.state == ProcessStates.STARTING
    # invalidate STARTING one
    process.invalidate_node('10.0.0.3', True)
    # check state became UNKNOWN on invalidated address
    assert process.info_map['10.0.0.3']['state'] == ProcessStates.UNKNOWN
    # check 0 address: no conflict
    assert not process.conflicting()
    # check that synthetic state became FATAL
    assert process.state == ProcessStates.FATAL
    # check that failure_handler is notified
    assert supvisors.failure_handler.add_default_job.call_args_list == [call(process)]
    # add one STOPPING
    process.add_info('10.0.0.4', any_process_info_by_state(ProcessStates.STOPPING))
    # check state STOPPING
    assert process.state == ProcessStates.STOPPING
    # invalidate STOPPING one
    process.invalidate_node('10.0.0.4', False)
    # check state became UNKNOWN on invalidated address
    assert process.info_map['10.0.0.4']['state'] == ProcessStates.UNKNOWN
    # check that synthetic state became STOPPED
    assert process.state == ProcessStates.STOPPED


def test_update_status(supvisors):
    """ Test the update of state and running addresses. """
    from supervisor.states import ProcessStates
    # update_status is called in the construction
    info = any_process_info_by_state(ProcessStates.STOPPED)
    process = create_process(info, supvisors)
    process.add_info('10.0.0.1', info)
    assert not process.running_nodes
    assert process.state == ProcessStates.STOPPED
    assert process.expected_exit
    # replace with an EXITED process info
    process.info_map['10.0.0.1'] = any_process_info_by_state(ProcessStates.EXITED)
    process.update_status('10.0.0.1', ProcessStates.EXITED, False)
    assert not process.running_nodes
    assert process.state == ProcessStates.EXITED
    assert not process.expected_exit
    # add a STARTING process info
    process.info_map['10.0.0.2'] = any_process_info_by_state(ProcessStates.STARTING)
    process.update_status('10.0.0.2', ProcessStates.STARTING, True)
    assert process.running_nodes == {'10.0.0.2'}
    assert process.state == ProcessStates.STARTING
    assert process.expected_exit
    # add a BACKOFF process info
    process.info_map['10.0.0.3'] = any_process_info_by_state(ProcessStates.BACKOFF)
    process.update_status('10.0.0.3', ProcessStates.STARTING, True)
    assert process.running_nodes == {'10.0.0.3', '10.0.0.2'}
    assert process.state == ProcessStates.BACKOFF
    assert process.expected_exit
    # replace STARTING process info with RUNNING
    process.info_map['10.0.0.2'] = any_process_info_by_state(ProcessStates.RUNNING)
    process.update_status('10.0.0.2', ProcessStates.RUNNING, True)
    assert process.running_nodes == {'10.0.0.3', '10.0.0.2'}
    assert process.state == ProcessStates.RUNNING
    assert process.expected_exit
    # replace BACKOFF process info with FATAL
    process.info_map['10.0.0.3'] = any_process_info_by_state(ProcessStates.FATAL)
    process.update_status('10.0.0.3', ProcessStates.FATAL, False)
    assert process.running_nodes == {'10.0.0.2'}
    assert process.state == ProcessStates.RUNNING
    assert process.expected_exit
    # replace RUNNING process info with STOPPED
    process.info_map['10.0.0.2'] = any_process_info_by_state(ProcessStates.STOPPED)
    process.update_status('10.0.0.2', ProcessStates.STOPPED, False)
    assert not process.running_nodes
    assert process.state == ProcessStates.STOPPED
    assert not process.expected_exit


def test_process_evaluate_conflict(supvisors):
    """ Test the determination of a synthetic state in case of conflict. """
    from supervisor.states import ProcessStates
    # when there is only one STOPPED process info, there is no conflict
    info = any_process_info_by_state(ProcessStates.STOPPED)
    process = create_process(info, supvisors)
    process.add_info('10.0.0.1', info)
    assert not process.evaluate_conflict()
    assert process.state == ProcessStates.STOPPED
    # the addition of one RUNNING process info does not raise any conflict
    process.info_map['10.0.0.2'] = any_process_info_by_state(ProcessStates.RUNNING)
    process.running_nodes = {'10.0.0.2'}
    assert not process.evaluate_conflict()
    # the addition of one STARTING process raises a conflict
    process.info_map['10.0.0.3'] = any_process_info_by_state(ProcessStates.STARTING)
    process.running_nodes.add('10.0.0.3')
    assert process.evaluate_conflict()
    assert process.state == ProcessStates.RUNNING
    # replace the RUNNING process info with a BACKOFF process info
    process.info_map['10.0.0.2'] = any_process_info_by_state(ProcessStates.BACKOFF)
    assert process.evaluate_conflict()
    assert process.state == ProcessStates.BACKOFF
    # replace the BACKOFF process info with a STARTING process info
    process.info_map['10.0.0.2'] = any_process_info_by_state(ProcessStates.STARTING)
    assert process.evaluate_conflict()
    assert process.state == ProcessStates.STARTING
    # replace the STARTING process info with an EXITED process info
    process.info_map['10.0.0.2'] = any_process_info_by_state(ProcessStates.EXITED)
    process.running_nodes.remove('10.0.0.2')
    assert not process.evaluate_conflict()
    assert process.state == ProcessStates.STARTING


def test_process_running_state():
    """ Test the choice of a single state among a list of states. """
    from supervisor.states import ProcessStates, STOPPED_STATES, RUNNING_STATES
    from supvisors.process import ProcessStatus
    # check running states with several combinations
    assert ProcessStatus.running_state(STOPPED_STATES) == ProcessStates.UNKNOWN
    states = {ProcessStates.STOPPING}
    assert ProcessStatus.running_state(states) == ProcessStates.UNKNOWN
    assert ProcessStatus.running_state(RUNNING_STATES) == ProcessStates.RUNNING
    states = {ProcessStates.STARTING, ProcessStates.BACKOFF}
    assert ProcessStatus.running_state(states) == ProcessStates.BACKOFF
    states = {ProcessStates.STARTING}
    assert ProcessStatus.running_state(states) == ProcessStates.STARTING
    states = {ProcessStates.STOPPING, *RUNNING_STATES, *STOPPED_STATES}
    assert ProcessStatus.running_state(states) == ProcessStates.RUNNING
