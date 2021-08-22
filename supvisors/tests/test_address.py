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
import random
import time

from .base import database_copy
from .conftest import create_any_process, create_process


@pytest.fixture
def filled_node(supvisors):
    """ Create an AddressStatus and add all processes of the database. """
    from supvisors.address import AddressStatus
    status = AddressStatus('10.0.0.1', supvisors.logger)
    for info in database_copy():
        process = create_process(info, supvisors)
        process.add_info('10.0.0.1', info)
        status.add_process(process)
    return status


def test_create(supvisors):
    """ Test the values set at construction. """
    from supvisors.address import AddressStatus
    from supvisors.ttypes import AddressStates
    status = AddressStatus('10.0.0.1', supvisors.logger)
    # test all AddressStatus values
    assert status.logger == supvisors.logger
    assert status.node_name == '10.0.0.1'
    assert status.state == AddressStates.UNKNOWN
    assert status.remote_time == 0
    assert status.local_time == 0
    assert status.processes == {}


def test_isolation(supvisors):
    """ Test the in_isolation method. """
    from supvisors.address import AddressStatus
    from supvisors.ttypes import AddressStates
    status = AddressStatus('10.0.0.1', supvisors.logger)
    for state in AddressStates:
        status._state = state
        assert (status.in_isolation() and state in [AddressStates.ISOLATING, AddressStates.ISOLATED] or
                not status.in_isolation() and state not in [AddressStates.ISOLATING, AddressStates.ISOLATED])


def test_serialization(supvisors):
    """ Test the serial method used to get a serializable form of AddressStatus. """
    import pickle
    from supvisors.address import AddressStatus
    from supvisors.ttypes import AddressStates
    # create address status instance
    status = AddressStatus('10.0.0.1', supvisors.logger)
    status._state = AddressStates.RUNNING
    status.checked = True
    status.remote_time = 50
    status.local_time = 60
    # test to_json method
    serialized = status.serial()
    assert serialized == {'address_name': '10.0.0.1', 'loading': 0, 'statecode': 2, 'statename': 'RUNNING',
                          'remote_time': 50, 'local_time': 60, 'sequence_counter': 0}
    # test that returned structure is serializable using pickle
    dumped = pickle.dumps(serialized)
    loaded = pickle.loads(dumped)
    assert serialized == loaded


def test_transitions(supvisors):
    """ Test the state transitions of AddressStatus. """
    from supvisors.address import AddressStatus
    from supvisors.ttypes import AddressStates, InvalidTransition
    status = AddressStatus('10.0.0.1', supvisors.logger)
    for state1 in AddressStates:
        for state2 in AddressStates:
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


def test_add_process(supvisors):
    """ Test the add_process method. """
    from supvisors.address import AddressStatus
    status = AddressStatus('10.0.0.1', supvisors.logger)
    process = create_any_process(supvisors)
    status.add_process(process)
    # check that process is stored
    assert process.namespec in status.processes.keys()
    assert process is status.processes[process.namespec]


def test_times(filled_node):
    """ Test the update_times method. """
    from supervisor.states import ProcessStates
    # get current process times
    ref_data = {process.namespec: (process.state, info['now'], info['uptime'])
                for process in filled_node.processes.values()
                for info in [process.info_map['10.0.0.1']]}
    # update times and check
    now = int(time.time())
    filled_node.update_times(28, now + 10, now)
    assert filled_node.sequence_counter == 28
    assert filled_node.remote_time == now + 10
    assert filled_node.local_time == now
    # test process times: only RUNNING and STOPPING have a positive uptime
    new_data = {process.namespec: (process.state, info['now'], info['uptime'])
                for process in filled_node.processes.values()
                for info in [process.info_map['10.0.0.1']]}
    for namespec, new_info in new_data.items():
        ref_info = ref_data[namespec]
        assert new_info[0] == ref_info[0]
        assert new_info[1] > ref_info[1]
        if new_info[0] in [ProcessStates.RUNNING, ProcessStates.STOPPING]:
            assert new_info[2] > ref_info[2]
        else:
            assert new_info[2] == ref_info[2]


def test_running_process(filled_node):
    """ Test the running_process method. """
    # check the name of the running processes
    assert {'late_segv', 'segv', 'xfontsel', 'yeux_01'} == {proc.process_name
                                                            for proc in filled_node.running_processes()}


def test_pid_process(filled_node):
    """ Test the pid_process method. """
    # check the namespec and pid of the running processes
    assert {('sample_test_1:xfontsel', 80879), ('sample_test_2:yeux_01', 80882)} == set(filled_node.pid_processes())


def test_get_loading(filled_node):
    """ Test the get_loading method. """
    # check the loading of the address: gives 0 by default because no rule has been loaded
    assert filled_node.get_loading() == 0
    # change expected_loading of any stopped process
    process = random.choice([proc for proc in filled_node.processes.values() if proc.stopped()])
    process.rules.expected_load = 50
    assert filled_node.get_loading() == 0
    # change expected_loading of any running process
    process = random.choice([proc for proc in filled_node.processes.values() if proc.running()])
    process.rules.expected_load = 50
    assert filled_node.get_loading() == 50
