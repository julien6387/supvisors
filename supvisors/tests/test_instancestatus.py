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
import random
import time
from unittest.mock import call, Mock

import pytest
from supervisor.states import ProcessStates

from supvisors.instancestatus import *
from supvisors.ttypes import SupvisorsInstanceStates, InvalidTransition
from .base import database_copy, any_process_info_by_state
from .conftest import create_process


def test_state_modes():
    """ Test the values set at StateModes construction. """
    sm_1 = StateModes()
    assert sm_1.state == SupvisorsStates.OFF
    assert not sm_1.discovery_mode
    assert sm_1.master_identifier == ''
    assert not sm_1.starting_jobs
    assert not sm_1.stopping_jobs
    assert sm_1.serial() == {'fsm_statecode': 0, 'fsm_statename': 'OFF',
                             'discovery_mode': False,
                             'master_identifier': '',
                             'starting_jobs': False, 'stopping_jobs': False}
    sm_1.apply(fsm_state=SupvisorsStates.OPERATION)
    assert sm_1.serial() == {'fsm_statecode': 3, 'fsm_statename': 'OPERATION',
                             'discovery_mode': False,
                             'master_identifier': '',
                             'starting_jobs': False, 'stopping_jobs': False}
    sm_1.apply(master_identifier='10.0.0.1')
    assert sm_1.serial() == {'fsm_statecode': 3, 'fsm_statename': 'OPERATION',
                             'discovery_mode': False,
                             'master_identifier': '10.0.0.1',
                             'starting_jobs': False, 'stopping_jobs': False}
    sm_1.apply(starter=True)
    assert sm_1.serial() == {'fsm_statecode': 3, 'fsm_statename': 'OPERATION',
                             'discovery_mode': False,
                             'master_identifier': '10.0.0.1',
                             'starting_jobs': True, 'stopping_jobs': False}
    sm_1.apply(stopper=True)
    assert sm_1.serial() == {'fsm_statecode': 3, 'fsm_statename': 'OPERATION',
                             'discovery_mode': False,
                             'master_identifier': '10.0.0.1',
                             'starting_jobs': True, 'stopping_jobs': True}
    with pytest.raises(TypeError):
        sm_1.apply(Starter=True)
    assert sm_1.serial() == {'fsm_statecode': 3, 'fsm_statename': 'OPERATION',
                             'discovery_mode': False,
                             'master_identifier': '10.0.0.1',
                             'starting_jobs': True, 'stopping_jobs': True}
    sm_2 = copy(sm_1)
    assert sm_2.state == SupvisorsStates.OPERATION
    assert not sm_2.discovery_mode
    assert sm_2.master_identifier == '10.0.0.1'
    assert sm_2.starting_jobs
    assert sm_2.stopping_jobs
    assert sm_1 == sm_2
    sm_2.update({'fsm_statecode': SupvisorsStates.SHUTTING_DOWN,
                 'discovery_mode': True,
                 'master_identifier': '',
                 'starting_jobs': False, 'stopping_jobs': True})
    assert sm_1 != sm_2
    assert sm_2.serial() == {'fsm_statecode': 6, 'fsm_statename': 'SHUTTING_DOWN',
                             'discovery_mode': True,
                             'master_identifier': '',
                             'starting_jobs': False, 'stopping_jobs': True}
    # test comparison with wrong type
    assert sm_1 != 4


@pytest.fixture
def supvisors_id(supvisors):
    """ Create a SupvisorsInstanceId. """
    return SupvisorsInstanceId('<supvisors>10.0.0.1:65000:65001', supvisors)


@pytest.fixture
def local_supvisors_id(supvisors):
    """ Create a SupvisorsInstanceId. """
    return SupvisorsInstanceId(f'<{supvisors.mapper.local_identifier}>10.0.0.1:65000:65001', supvisors)


@pytest.fixture
def status(supvisors, supvisors_id):
    """ Create an empty SupvisorsInstanceStatus. """
    return SupvisorsInstanceStatus(supvisors_id, supvisors)


@pytest.fixture
def local_status(supvisors, local_supvisors_id):
    """ Create an empty SupvisorsInstanceStatus. """
    return SupvisorsInstanceStatus(local_supvisors_id, supvisors)


@pytest.fixture
def filled_status(supvisors, status):
    """ Create a SupvisorsInstanceStatus and add all processes of the database. """
    for info in database_copy():
        process = create_process(info, supvisors)
        process.add_info(status.supvisors_id.identifier, info)
        status.add_process(process)
    return status


def test_create_no_collector(supvisors, supvisors_id, status):
    """ Test the values set at SupvisorsInstanceStatus construction. """
    assert status.supvisors is supvisors
    assert status.logger is supvisors.logger
    assert status.supvisors_id is supvisors_id
    assert status.identifier == 'supvisors'
    assert status.state == SupvisorsInstanceStates.UNKNOWN
    assert status.sequence_counter == 0
    assert status.local_sequence_counter == 0
    assert status.start_time == 0.0
    assert status.remote_time == 0.0
    assert status.local_time == 0.0
    assert status.processes == {}
    assert status.state_modes == StateModes()
    # process_collector is None because local_identifier is different in supvisors_mapper and in SupvisorsInstanceId
    assert status.process_collector is None


def test_create_collector(supvisors, local_supvisors_id, local_status):
    """ Test the values set at SupvisorsInstanceStatus construction. """
    assert local_status.supvisors is supvisors
    assert local_status.logger is supvisors.logger
    assert local_status.supvisors_id is local_supvisors_id
    assert local_status.identifier == supvisors.mapper.local_identifier
    assert local_status.state == SupvisorsInstanceStates.UNKNOWN
    assert local_status.sequence_counter == 0
    assert local_status.local_sequence_counter == 0
    assert local_status.start_time == 0.0
    assert local_status.remote_time == 0.0
    assert local_status.local_time == 0.0
    assert local_status.processes == {}
    assert local_status.state_modes == StateModes()
    # process_collector is set as SupvisorsInstanceId and supvisors_mapper's local_identifier are identical
    #  and the option process_stats_enabled is True
    assert local_status.process_collector is not None
    assert local_status.process_collector is supvisors.process_collector


def test_reset(status):
    """ Test the SupvisorsInstanceStatus.reset method. """
    for state in SupvisorsInstanceStates:
        status._state = state
        status.local_sequence_counter = 10
        status.remote_time = 28.452
        status.local_time = 27.456
        status.reset()
        if state in [SupvisorsInstanceStates.CHECKING, SupvisorsInstanceStates.CHECKED,
                     SupvisorsInstanceStates.RUNNING]:
            assert status.state == SupvisorsInstanceStates.UNKNOWN
        else:
            assert status.state == state
        assert status.local_sequence_counter == 0
        assert status.remote_time == 0.0
        assert status.local_time == 0.0


def test_serialization(status):
    """ Test the serial method used to get a serializable form of SupvisorsInstanceStatus. """
    status._state = SupvisorsInstanceStates.RUNNING
    status.checked = True
    status.sequence_counter = 28
    status.remote_time = 50
    status.local_time = 60
    # test to_json method
    serialized = status.serial()
    assert serialized == {'identifier': 'supvisors', 'node_name': '10.0.0.1', 'port': 65000, 'loading': 0,
                          'statecode': 3, 'statename': 'RUNNING', 'discovery_mode': False,
                          'remote_time': 50, 'local_time': 60,
                          'sequence_counter': 28, 'process_failure': False,
                          'fsm_statecode': 0, 'fsm_statename': 'OFF',
                          'master_identifier': '',
                          'starting_jobs': False, 'stopping_jobs': False}
    # test that returned structure is serializable using pickle
    dumped = pickle.dumps(serialized)
    loaded = pickle.loads(dumped)
    assert serialized == loaded


def test_transitions(status):
    """ Test the state transitions of SupvisorsInstanceStatus. """
    silent_states = [SupvisorsInstanceStates.SILENT, SupvisorsInstanceStates.ISOLATING,
                     SupvisorsInstanceStates.ISOLATED]
    for state1 in SupvisorsInstanceStates:
        for state2 in SupvisorsInstanceStates:
            # check all possible transitions from each state
            status._state = state1
            status.state_modes.state = SupvisorsStates.OPERATION
            if state2 in status._Transitions[state1]:
                status.state = state2
                assert status.state == state2
                assert status.state.name == state2.name
                if state2 in silent_states:
                    assert status.state_modes.state == SupvisorsStates.OFF
                else:
                    assert status.state_modes.state == SupvisorsStates.OPERATION
            elif state1 == state2:
                assert status.state == state1
                assert status.state_modes.state == SupvisorsStates.OPERATION
            else:
                with pytest.raises(InvalidTransition):
                    status.state = state2
                assert status.state_modes.state == SupvisorsStates.OPERATION


def test_update_state_modes(status):
    """ Test the SupvisorsInstanceStatus.update_state_modes method. """
    assert status.state_modes == StateModes()
    status.update_state_modes({'fsm_statecode': SupvisorsStates.SHUTTING_DOWN,
                               'discovery_mode': True,
                               'master_identifier': '10.0.0.1',
                               'starting_jobs': False, 'stopping_jobs': True})
    assert status.state_modes.serial() == {'fsm_statecode': 6, 'fsm_statename': 'SHUTTING_DOWN',
                                           'discovery_mode': True,
                                           'master_identifier': '10.0.0.1',
                                           'starting_jobs': False, 'stopping_jobs': True}


def test_apply_state_modes(status):
    """ Test the SupvisorsInstanceStatus.apply_state_modes method. """
    assert status.state_modes == StateModes()
    assert status.apply_state_modes({}) == (False, StateModes())
    event = {'master_identifier': '10.0.0.1'}
    assert status.apply_state_modes(event) == (True, StateModes(master_identifier='10.0.0.1'))
    event = {'starter': True}
    assert status.apply_state_modes(event) == (True, StateModes(starting_jobs=True, master_identifier='10.0.0.1'))
    event = {'stopper': False}
    assert status.apply_state_modes(event) == (False, StateModes(master_identifier='10.0.0.1', starting_jobs=True))
    event = {'fsm_state': SupvisorsStates.RESTARTING}
    assert status.apply_state_modes(event) == (True, StateModes(SupvisorsStates.RESTARTING,
                                                                False, '10.0.0.1', True))
    event = {'fsm_state': SupvisorsStates.INITIALIZATION, 'stopper': True}
    assert status.apply_state_modes(event) == (True, StateModes(SupvisorsStates.INITIALIZATION,
                                                                False, '10.0.0.1', True, True))
    assert status.apply_state_modes(event) == (False, StateModes(SupvisorsStates.INITIALIZATION,
                                                                 False, '10.0.0.1', True, True))


def test_has_active_state(status):
    """ Test the SupvisorsInstanceStatus.has_active_state method. """
    for state in SupvisorsInstanceStates:
        status._state = state
        if state in [SupvisorsInstanceStates.CHECKING, SupvisorsInstanceStates.CHECKED,
                     SupvisorsInstanceStates.RUNNING]:
            assert status.has_active_state()
        else:
            assert not status.has_active_state()


def test_inactive(status):
    """ Test the SupvisorsInstanceStatus.is_inactive method. """
    # test active
    status.local_sequence_counter = 8
    for state in SupvisorsInstanceStates:
        status._state = state
        assert not status.is_inactive(10)
    # test not active
    status.local_sequence_counter = 7
    for state in SupvisorsInstanceStates:
        status._state = state
        if state in [SupvisorsInstanceStates.CHECKING, SupvisorsInstanceStates.CHECKED,
                     SupvisorsInstanceStates.RUNNING]:
            assert status.is_inactive(10)
        else:
            assert not status.is_inactive(10)


def test_isolation(status):
    """ Test the SupvisorsInstanceStatus.in_isolation method. """
    for state in SupvisorsInstanceStates:
        status._state = state
        assert (status.in_isolation() and
                state in [SupvisorsInstanceStates.ISOLATING, SupvisorsInstanceStates.ISOLATED] or
                not status.in_isolation() and state not in [SupvisorsInstanceStates.ISOLATING,
                                                            SupvisorsInstanceStates.ISOLATED])


def test_process_no_collector(supvisors, status):
    """ Test the SupvisorsInstanceStatus.xxx_process methods when no process collector is available. """
    info = any_process_info_by_state(ProcessStates.RUNNING)
    process = create_process(info, supvisors)
    status.add_process(process)
    status.update_process(process)
    # check no process_collector
    assert status.process_collector is None
    # check that process is stored
    assert process.namespec in status.processes.keys()
    assert process is status.processes[process.namespec]
    # test remove process
    status.remove_process(process)
    # check that process is stored anymore
    assert process.namespec not in status.processes.keys()


def test_process_running_unknown_collector(supvisors, local_status):
    """ Test the SupvisorsInstanceStatus.xxx_process methods when no pid running on the identifier. """
    # patch process_collector
    assert local_status.process_collector is not None
    local_status.process_collector = Mock()
    # add a process to the InstanceStatus but do not add the info to the ProcessStatus instance
    info = any_process_info_by_state(ProcessStates.RUNNING)
    process = create_process(info, supvisors)
    local_status.add_process(process)
    assert process.get_pid(local_status.identifier) == 0
    assert not local_status.process_collector.send_pid.called
    # check that process is stored
    assert process.namespec in local_status.processes.keys()
    assert process is local_status.processes[process.namespec]
    # on process update, send the pid again or 0 if not found
    local_status.update_process(process)
    assert local_status.process_collector.send_pid.call_args_list == [call(process.namespec, 0)]
    local_status.process_collector.send_pid.reset_mock()
    # test remove process
    local_status.remove_process(process)
    # check that process is stored anymore
    assert process.namespec not in local_status.processes.keys()
    # on process removal, pid 0 is sent to the collector
    assert local_status.process_collector.send_pid.call_args_list == [call(process.namespec, 0)]


def test_add_process_running_collector(supvisors, local_status):
    """ Test the SupvisorsInstanceStatus.add_process method when the process is running on the identifier. """
    # patch process_collector
    assert local_status.process_collector is not None
    local_status.process_collector = Mock()
    # add a running process to the InstanceStatus and add the info to the ProcessStatus instance
    info = any_process_info_by_state(ProcessStates.RUNNING)
    process = create_process(info, supvisors)
    process.add_info(local_status.identifier, info)
    local_status.add_process(process)
    # check that process is stored
    assert process.namespec in local_status.processes.keys()
    assert process is local_status.processes[process.namespec]
    # check data in process_collector queue
    assert local_status.process_collector.send_pid.call_args_list == [call(process.namespec, info['pid'])]
    local_status.process_collector.send_pid.reset_mock()
    # on process update, send the pid again
    local_status.update_process(process)
    assert local_status.process_collector.send_pid.call_args_list == [call(process.namespec, info['pid'])]
    local_status.process_collector.send_pid.reset_mock()
    # test remove process
    local_status.remove_process(process)
    # check that process is stored anymore
    assert process.namespec not in local_status.processes.keys()
    # on process removal, pid 0 is sent to the collector
    assert local_status.process_collector.send_pid.call_args_list == [call(process.namespec, 0)]


def test_add_process_stopped_collector(supvisors, local_status):
    """ Test the SupvisorsInstanceStatus.add_process method when the process is stopped on the identifier. """
    # patch process_collector
    assert local_status.process_collector is not None
    local_status.process_collector = Mock()
    # add a stopped process to the InstanceStatus and add the info to the ProcessStatus instance
    info = any_process_info_by_state(ProcessStates.STOPPED)
    process = create_process(info, supvisors)
    process.add_info(local_status.identifier, info)
    local_status.add_process(process)
    # check that process is stored
    assert process.namespec in local_status.processes.keys()
    assert process is local_status.processes[process.namespec]
    # check data in process_collector queue
    assert not local_status.process_collector.send_pid.called
    # on process update, send the pid again
    local_status.update_process(process)
    assert local_status.process_collector.send_pid.call_args_list == [call(process.namespec, info['pid'])]
    local_status.process_collector.send_pid.reset_mock()
    # test remove process
    local_status.remove_process(process)
    # check that process is stored anymore
    assert process.namespec not in local_status.processes.keys()
    # on process removal, pid 0 is sent to the collector
    assert local_status.process_collector.send_pid.call_args_list == [call(process.namespec, info['pid'])]


def test_update_tick(filled_status):
    """ Test the SupvisorsInstanceStatus.update_tick method. """
    now = time.time()
    # get current process times
    ref_data = {process.namespec: (process.state, info['now'], info['uptime'])
                for process in filled_status.processes.values()
                for info in [process.info_map['supvisors']]}
    # update times and check with normal counter
    filled_status.sequence_counter = 25
    filled_status.update_tick(28, now + 10, 27, now)
    ref_start_time = now - 28 * TICK_PERIOD
    assert filled_status.sequence_counter == 28
    assert filled_status.local_sequence_counter == 27
    assert filled_status.start_time == ref_start_time
    assert filled_status.remote_time == now + 10
    assert filled_status.local_time == now
    # test process times: only RUNNING and STOPPING have a positive uptime
    new_data = {process.namespec: (process.state, info['now'], info['uptime'])
                for process in filled_status.processes.values()
                for info in [process.info_map['supvisors']]}
    for namespec, new_info in new_data.items():
        ref_info = ref_data[namespec]
        assert new_info[0] == ref_info[0]
        assert new_info[1] > ref_info[1]
        if new_info[0] in [ProcessStates.RUNNING, ProcessStates.STOPPING]:
            assert new_info[2] > ref_info[2]
        else:
            assert new_info[2] == ref_info[2]
    # update times aa second time to check that start_time hasn't changed
    filled_status.update_tick(29, now + 15, 28, now + 5)
    assert filled_status.sequence_counter == 29
    assert filled_status.local_sequence_counter == 28
    assert filled_status.start_time == ref_start_time
    assert filled_status.remote_time == now + 15
    assert filled_status.local_time == now + 5
    # test counter issue (going backwards)
    filled_status.update_tick(28, now + 10, 27, now)
    assert filled_status.sequence_counter == 28
    assert filled_status.local_sequence_counter == 0
    assert filled_status.start_time == ref_start_time
    assert filled_status.remote_time == now + 10
    assert filled_status.local_time == now


def test_get_remote_time(filled_status):
    """ Test the SupvisorsInstanceStatus.get_remote_time method. """
    # update times and check
    filled_status.remote_time = 10
    filled_status.local_time = 5
    assert filled_status.get_remote_time(15) == 20


def test_running_process(filled_status):
    """ Test the SupvisorsInstanceStatus.running_process method. """
    # check the name of the running processes
    expected = {'late_segv', 'segv', 'xfontsel', 'yeux_01'}
    assert {proc.process_name for proc in filled_status.running_processes()} == expected


def test_get_load(filled_status):
    """ Test the SupvisorsInstanceStatus.get_load method. """
    # check the loading of the address: gives 0 by default because no rule has been loaded
    assert filled_status.get_load() == 0
    # change expected_loading of any stopped process
    process = random.choice([proc for proc in filled_status.processes.values() if proc.stopped()])
    process.rules.expected_load = 50
    assert filled_status.get_load() == 0
    # change expected_loading of any running process
    process = random.choice([proc for proc in filled_status.processes.values() if proc.running()])
    process.rules.expected_load = 50
    assert filled_status.get_load() == 50


def test_has_no_error(status):
    """ Test the SupvisorsInstanceStatus.has_error method. """
    # test that has_error is not raised when there is no error
    for state in SupvisorsInstanceStates:
        status._state = state
        assert not status.has_error()


def test_has_error(filled_status):
    """ Test the SupvisorsInstanceStatus.has_error method. """
    # test that has_error is raised only in RUNNING state when there is an error
    for state in SupvisorsInstanceStates:
        filled_status._state = state
        assert not filled_status.has_error() or state == SupvisorsInstanceStates.RUNNING
    # replace any FATAL process by unexpected EXITED
    filled_status._state = SupvisorsInstanceStates.RUNNING
    for process in filled_status.processes.values():
        info = process.info_map[filled_status.supvisors_id.identifier]
        if info['state'] == ProcessStates.FATAL:
            info['state'] = ProcessStates.EXITED
            info['expected'] = False
    # error still raised
    assert filled_status.has_error()
    # replace any EXITED process by STOPPED
    filled_status._state = SupvisorsInstanceStates.RUNNING
    for process in filled_status.processes.values():
        info = process.info_map[filled_status.supvisors_id.identifier]
        if info['state'] == ProcessStates.EXITED:
            info['state'] = ProcessStates.STOPPED
    # error still raised
    assert not filled_status.has_error()
