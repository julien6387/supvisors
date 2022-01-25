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
    assert status.remote_time == 0.0
    assert status.local_time == 0.0
    assert status.processes == {}


def test_isolation(status):
    """ Test the SupvisorsInstanceStatus.in_isolation method. """
    for state in SupvisorsInstanceStates:
        status._state = state
        assert (status.in_isolation() and
                state in [SupvisorsInstanceStates.ISOLATING, SupvisorsInstanceStates.ISOLATED] or
                not status.in_isolation() and state not in [SupvisorsInstanceStates.ISOLATING,
                                                            SupvisorsInstanceStates.ISOLATED])


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
                          'sequence_counter': 28}
    # test that returned structure is serializable using pickle
    dumped = pickle.dumps(serialized)
    loaded = pickle.loads(dumped)
    assert serialized == loaded


def test_transitions(status):
    """ Test the state transitions of SupvisorsInstanceStatus. """
    for state1 in SupvisorsInstanceStates:
        for state2 in SupvisorsInstanceStates:
            # check all possible transitions from each state
            status._state = state1
            if state2 in status._Transitions[state1]:
                status.state = state2
                assert status.state == state2
                assert status.state.name == state2.name
            elif state1 == state2:
                assert status.state == state1
            else:
                with pytest.raises(InvalidTransition):
                    status.state = state2


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
    assert filled_status.sequence_counter == 28
    assert filled_status.local_sequence_counter == 27
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
