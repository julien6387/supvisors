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
import random
import time

from supervisor.states import ProcessStates

from supvisors.instancestatus import *
from supvisors.ttypes import SupvisorsInstanceStates, InvalidTransition

from .base import database_copy
from .conftest import create_any_process, create_process


def test_state_modes():
    """ Test the values set at StateModes construction. """
    sm_1 = StateModes()
    assert sm_1.state == SupvisorsStates.OFF
    assert not sm_1.starting_jobs
    assert not sm_1.stopping_jobs
    assert sm_1.serial() == {'fsm_statecode': 0, 'fsm_statename': 'OFF',
                             'starting_jobs': False, 'stopping_jobs': False}
    sm_1.apply(fsm_state=SupvisorsStates.OPERATION)
    assert sm_1.serial() == {'fsm_statecode': 3, 'fsm_statename': 'OPERATION',
                             'starting_jobs': False, 'stopping_jobs': False}
    sm_1.apply(starter=True)
    assert sm_1.serial() == {'fsm_statecode': 3, 'fsm_statename': 'OPERATION',
                             'starting_jobs': True, 'stopping_jobs': False}
    sm_1.apply(stopper=True)
    assert sm_1.serial() == {'fsm_statecode': 3, 'fsm_statename': 'OPERATION',
                             'starting_jobs': True, 'stopping_jobs': True}
    with pytest.raises(TypeError):
        sm_1.apply(Starter=True)
    assert sm_1.serial() == {'fsm_statecode': 3, 'fsm_statename': 'OPERATION',
                             'starting_jobs': True, 'stopping_jobs': True}
    sm_2 = copy(sm_1)
    assert sm_1.state == SupvisorsStates.OPERATION
    assert sm_1.starting_jobs
    assert sm_1.stopping_jobs
    assert sm_1 == sm_2
    sm_2.update({'fsm_statecode': SupvisorsStates.SHUTTING_DOWN, 'starting_jobs': False, 'stopping_jobs': True})
    assert sm_1 != sm_2
    assert sm_2.serial() == {'fsm_statecode': 7, 'fsm_statename': 'SHUTTING_DOWN',
                             'starting_jobs': False, 'stopping_jobs': True}


@pytest.fixture
def supvisors_id(supvisors):
    """ Create a SupvisorsInstanceId. """
    return SupvisorsInstanceId('<supvisors>10.0.0.1:65000:65001', supvisors)


@pytest.fixture
def status(supvisors, supvisors_id):
    """ Create an empty SupvisorsInstanceStatus. """
    return SupvisorsInstanceStatus(supvisors_id, supvisors)


@pytest.fixture
def filled_status(supvisors, status):
    """ Create a SupvisorsInstanceStatus and add all processes of the database. """
    for info in database_copy():
        process = create_process(info, supvisors)
        process.add_info('supvisors', info)
        status.add_process(process)
    return status


def test_create(supvisors, supvisors_id, status):
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


def test_reset(status):
    """ Test the SupvisorsInstanceStatus.reset method. """
    for state in SupvisorsInstanceStates:
        status._state = state
        status.local_sequence_counter = 10
        status.remote_time = 28.452
        status.local_time = 27.456
        status.reset()
        if state in [SupvisorsInstanceStates.CHECKING, SupvisorsInstanceStates.RUNNING]:
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
                          'statecode': 2, 'statename': 'RUNNING', 'remote_time': 50, 'local_time': 60,
                          'sequence_counter': 28, 'fsm_statecode': 0, 'fsm_statename': 'OFF',
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
                               'starting_jobs': False, 'stopping_jobs': True})
    assert status.state_modes.serial() == {'fsm_statecode': 7, 'fsm_statename': 'SHUTTING_DOWN',
                                           'starting_jobs': False, 'stopping_jobs': True}


def test_apply_state_modes(status):
    """ Test the SupvisorsInstanceStatus.apply_state_modes method. """
    assert status.state_modes == StateModes()
    assert status.apply_state_modes({}) == (False, StateModes())
    event = {'starter': True}
    assert status.apply_state_modes(event) == (True, StateModes(starting_jobs=True))
    event = {'stopper': False}
    assert status.apply_state_modes(event) == (False, StateModes(starting_jobs=True))
    event = {'fsm_state': SupvisorsStates.RESTARTING}
    assert status.apply_state_modes(event) == (True, StateModes(SupvisorsStates.RESTARTING, True))
    event = {'fsm_state': SupvisorsStates.INITIALIZATION, 'stopper': True}
    assert status.apply_state_modes(event) == (True, StateModes(SupvisorsStates.INITIALIZATION, True, True))
    assert status.apply_state_modes(event) == (False, StateModes(SupvisorsStates.INITIALIZATION, True, True))


def test_inactive(status):
    """ Test the SupvisorsInstanceStatus.inactive method. """
    # test active
    status.local_sequence_counter = 8
    for state in SupvisorsInstanceStates:
        status._state = state
        assert not status.inactive(10)
    # test not active
    status.local_sequence_counter = 7
    for state in SupvisorsInstanceStates:
        status._state = state
        if state in [SupvisorsInstanceStates.CHECKING, SupvisorsInstanceStates.RUNNING]:
            assert status.inactive(10)
        else:
            assert not status.inactive(10)


def test_isolation(status):
    """ Test the SupvisorsInstanceStatus.in_isolation method. """
    for state in SupvisorsInstanceStates:
        status._state = state
        assert (status.in_isolation() and
                state in [SupvisorsInstanceStates.ISOLATING, SupvisorsInstanceStates.ISOLATED] or
                not status.in_isolation() and state not in [SupvisorsInstanceStates.ISOLATING,
                                                            SupvisorsInstanceStates.ISOLATED])


def test_add_process(supvisors, status):
    """ Test the SupvisorsInstanceStatus.add_process method. """
    process = create_any_process(supvisors)
    status.add_process(process)
    # check that process is stored
    assert process.namespec in status.processes.keys()
    assert process is status.processes[process.namespec]


def test_update_times(filled_status):
    """ Test the SupvisorsInstanceStatus.update_times method. """
    # get current process times
    ref_data = {process.namespec: (process.state, info['now'], info['uptime'])
                for process in filled_status.processes.values()
                for info in [process.info_map['supvisors']]}
    # update times and check
    now = time.time()
    filled_status.update_times(28, now + 10, 27, now)
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
    filled_status.update_times(29, now + 15, 28, now + 5)
    assert filled_status.sequence_counter == 29
    assert filled_status.local_sequence_counter == 28
    assert filled_status.start_time == ref_start_time
    assert filled_status.remote_time == now + 15
    assert filled_status.local_time == now + 5


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


def test_pid_process(filled_status):
    """ Test the SupvisorsInstanceStatus.pid_process method. """
    # check the namespec and pid of the running processes
    assert {('sample_test_1:xfontsel', 80879), ('sample_test_2:yeux_01', 80882)} == set(filled_status.pid_processes())


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
