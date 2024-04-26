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
import socket
from unittest.mock import call, Mock

import pytest
from supervisor.compat import xmlrpclib
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
def supvisors_times(supvisors):
    """ Create a SupvisorsTimes. """
    return SupvisorsTimes('10.0.0.1', supvisors.logger)


def test_times(mocker, supvisors, supvisors_times):
    """ Test the SupvisorsTimes. """
    mocker.patch('time.time', return_value=1250.3)
    mocker.patch('time.monotonic', return_value=125.9)
    # test creation
    assert supvisors_times.identifier == '10.0.0.1'
    assert supvisors_times.logger is supvisors.logger
    assert supvisors_times.remote_sequence_counter == 0
    assert supvisors_times.remote_mtime == 0.0
    assert supvisors_times.remote_time == 0.0
    assert supvisors_times.local_sequence_counter == 0
    assert supvisors_times.local_mtime == 0.0
    assert supvisors_times.local_time == 0.0
    assert supvisors_times.start_local_mtime == -1.0
    # test normal local update
    supvisors_times.update(2, 100, 1000, -1)
    assert supvisors_times.remote_sequence_counter == 2
    assert supvisors_times.remote_mtime == 100
    assert supvisors_times.remote_time == 1000
    assert supvisors_times.local_sequence_counter == 2
    assert supvisors_times.local_mtime == 100
    assert supvisors_times.local_time == 1000
    assert supvisors_times.start_local_mtime == 90
    # test normal remote update
    supvisors_times.update(3, 200, 1100, 2)
    assert supvisors_times.remote_sequence_counter == 3
    assert supvisors_times.remote_mtime == 200
    assert supvisors_times.remote_time == 1100
    assert supvisors_times.local_sequence_counter == 2
    assert supvisors_times.local_mtime == 125.9
    assert supvisors_times.local_time == 1250.3
    assert supvisors_times.start_local_mtime == 90
    # test stealth update
    supvisors_times.update(1, 300.1, 1200.1, 1)
    assert supvisors_times.remote_sequence_counter == 1
    assert supvisors_times.remote_mtime == 300.1
    assert supvisors_times.remote_time == 1200.1
    assert supvisors_times.local_sequence_counter == 0
    assert supvisors_times.local_mtime == 125.9
    assert supvisors_times.local_time == 1250.3
    assert supvisors_times.start_local_mtime == 120.9
    # test getters
    assert supvisors_times.capped_remote_time == 1200
    assert supvisors_times.capped_local_time == 1250
    assert supvisors_times.get_current_uptime() == 5.0  # 125.9 - 120.9
    assert supvisors_times.get_current_remote_time(132.9) == 1207.1  # 1200.1 + (132.9 - 125.9)
    # test capped values
    supvisors_times.remote_time = xmlrpclib.MAXINT + 100
    supvisors_times.local_time = xmlrpclib.MAXINT + 1000
    assert supvisors_times.capped_remote_time == xmlrpclib.MAXINT
    assert supvisors_times.capped_local_time == xmlrpclib.MAXINT
    supvisors_times.remote_time = 1200.1
    # test serial
    expected = {'local_sequence_counter': 0, 'local_mtime': 125.9, 'local_time': xmlrpclib.MAXINT,
                'remote_sequence_counter': 1, 'remote_mtime': 300.1, 'remote_time': 1200}
    assert supvisors_times.serial() == expected


@pytest.fixture
def supvisors_id(supvisors):
    """ Create a SupvisorsInstanceId. """
    return SupvisorsInstanceId('<supvisors>10.0.0.1:25000', supvisors)


@pytest.fixture
def local_supvisors_id(supvisors):
    """ Create a SupvisorsInstanceId. """
    item = f'<supvisors>{socket.getfqdn()}:25000'
    return SupvisorsInstanceId(item, supvisors)


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
    assert status.identifier == '10.0.0.1:25000'
    assert status.usage_identifier == '<supvisors>10.0.0.1:25000'
    assert status.state == SupvisorsInstanceStates.UNKNOWN
    assert not status.isolated
    assert status.sequence_counter == 0
    assert status.times.identifier == '10.0.0.1:25000'
    assert status.times.logger is supvisors.logger
    assert status.times.remote_sequence_counter == 0
    assert status.times.remote_mtime == 0.0
    assert status.times.remote_time == 0.0
    assert status.times.local_sequence_counter == 0
    assert status.times.local_mtime == 0.0
    assert status.times.local_time == 0.0
    assert status.times.start_local_mtime == -1.0
    assert status.processes == {}
    assert status.state_modes == StateModes()
    # process_collector is None because local_identifier is different in supvisors_mapper and in SupvisorsInstanceId
    assert status.stats_collector is None


def test_create_collector(supvisors, local_supvisors_id, local_status):
    """ Test the values set at SupvisorsInstanceStatus construction. """
    assert local_status.supvisors is supvisors
    assert local_status.logger is supvisors.logger
    assert local_status.supvisors_id is local_supvisors_id
    assert local_status.identifier == supvisors.mapper.local_identifier
    assert local_status.state == SupvisorsInstanceStates.UNKNOWN
    assert local_status.times.identifier == supvisors.mapper.local_identifier
    assert local_status.times.logger is supvisors.logger
    assert local_status.times.remote_sequence_counter == 0
    assert local_status.times.remote_mtime == 0.0
    assert local_status.times.remote_time == 0.0
    assert local_status.times.local_sequence_counter == 0
    assert local_status.times.local_mtime == 0.0
    assert local_status.times.local_time == 0.0
    assert local_status.times.start_local_mtime == -1.0
    assert local_status.processes == {}
    assert local_status.state_modes == StateModes()
    # process_collector is set as SupvisorsInstanceId and supvisors_mapper's local_identifier are identical
    #  and the option process_stats_enabled is True
    assert local_status.stats_collector is not None
    assert local_status.stats_collector is supvisors.stats_collector


def test_reset(status):
    """ Test the SupvisorsInstanceStatus.reset method. """
    for state in SupvisorsInstanceStates:
        status._state = state
        status.times.remote_sequence_counter = 10
        status.times.remote_mtime = 11.1
        status.times.remote_time = 28.452
        status.times.local_sequence_counter = 10
        status.times.local_mtime = 100.7
        status.times.local_time = 27.456
        status.times.start_local_mtime = 0.7
        status.reset()
        if state in [SupvisorsInstanceStates.CHECKING, SupvisorsInstanceStates.CHECKED,
                     SupvisorsInstanceStates.RUNNING]:
            assert status.state == SupvisorsInstanceStates.UNKNOWN
        else:
            assert status.state == state
        assert status.times.remote_sequence_counter == 0
        assert status.times.remote_mtime == 0.0
        assert status.times.remote_time == 0.0
        assert status.times.local_sequence_counter == 0
        assert status.times.local_mtime == 0.0
        assert status.times.local_time == 0.0
        assert status.times.start_local_mtime == -1.0


def test_serialization(mocker, status):
    """ Test the serial method used to get a serializable form of SupvisorsInstanceStatus. """
    mocker.patch('time.time', return_value=19413.5)
    mocker.patch('time.monotonic', return_value=13.5)
    status._state = SupvisorsInstanceStates.RUNNING
    status.rpc_failure = True
    status.times.update(28, 10.5, 50.2, 17)
    # test to_json method
    serialized = status.serial()
    assert serialized == {'identifier': '10.0.0.1:25000', 'nick_identifier': 'supvisors',
                          'node_name': '10.0.0.1', 'port': 25000, 'loading': 0,
                          'statecode': 3, 'statename': 'RUNNING', 'discovery_mode': False,
                          'remote_sequence_counter': 28, 'remote_mtime': 10.5, 'remote_time': 50,
                          'local_sequence_counter': 17, 'local_mtime': 13.5, 'local_time': 19413,
                          'process_failure': False,
                          'fsm_statecode': 0, 'fsm_statename': 'OFF',
                          'master_identifier': '',
                          'starting_jobs': False, 'stopping_jobs': False}
    # test that returned structure is serializable using pickle
    dumped = pickle.dumps(serialized)
    loaded = pickle.loads(dumped)
    assert serialized == loaded


def test_transitions(status):
    """ Test the state transitions of SupvisorsInstanceStatus. """
    silent_states = [SupvisorsInstanceStates.SILENT, SupvisorsInstanceStates.ISOLATED]
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
    status.times.local_sequence_counter = 8
    for state in SupvisorsInstanceStates:
        status._state = state
        assert not status.is_inactive(10)
    # test not active
    status.times.local_sequence_counter = 7
    for state in SupvisorsInstanceStates:
        status._state = state
        if state in [SupvisorsInstanceStates.CHECKING, SupvisorsInstanceStates.CHECKED,
                     SupvisorsInstanceStates.RUNNING]:
            assert status.is_inactive(10)
        else:
            assert not status.is_inactive(10)


def test_isolation(status):
    """ Test the SupvisorsInstanceStatus.isolated property. """
    for state in SupvisorsInstanceStates:
        status._state = state
        assert (status.isolated and state == SupvisorsInstanceStates.ISOLATED or
                not status.isolated and state != SupvisorsInstanceStates.ISOLATED)


def test_process_no_collector(supvisors, status):
    """ Test the SupvisorsInstanceStatus.xxx_process methods when no process collector is available. """
    info = any_process_info_by_state(ProcessStates.RUNNING)
    process = create_process(info, supvisors)
    status.add_process(process)
    status.update_process(process)
    # check no process_collector
    assert status.stats_collector is None
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
    assert local_status.stats_collector is not None
    local_status.stats_collector = Mock()
    # add a process to the InstanceStatus but do not add the info to the ProcessStatus instance
    info = any_process_info_by_state(ProcessStates.RUNNING)
    process = create_process(info, supvisors)
    local_status.add_process(process)
    assert process.get_pid(local_status.identifier) == 0
    assert not local_status.stats_collector.send_pid.called
    # check that process is stored
    assert process.namespec in local_status.processes.keys()
    assert process is local_status.processes[process.namespec]
    # on process update, send the pid again or 0 if not found
    local_status.update_process(process)
    assert local_status.stats_collector.send_pid.call_args_list == [call(process.namespec, 0)]
    local_status.stats_collector.send_pid.reset_mock()
    # test remove process
    local_status.remove_process(process)
    # check that process is stored anymore
    assert process.namespec not in local_status.processes.keys()
    # on process removal, pid 0 is sent to the collector
    assert local_status.stats_collector.send_pid.call_args_list == [call(process.namespec, 0)]


def test_add_process_running_collector(supvisors, local_status):
    """ Test the SupvisorsInstanceStatus.add_process method when the process is running on the identifier. """
    # patch process_collector
    assert local_status.stats_collector is not None
    local_status.stats_collector = Mock()
    # add a running process to the InstanceStatus and add the info to the ProcessStatus instance
    info = any_process_info_by_state(ProcessStates.RUNNING)
    process = create_process(info, supvisors)
    process.add_info(local_status.identifier, info)
    local_status.add_process(process)
    # check that process is stored
    assert process.namespec in local_status.processes.keys()
    assert process is local_status.processes[process.namespec]
    # check data in process_collector queue
    assert local_status.stats_collector.send_pid.call_args_list == [call(process.namespec, info['pid'])]
    local_status.stats_collector.send_pid.reset_mock()
    # on process update, send the pid again
    local_status.update_process(process)
    assert local_status.stats_collector.send_pid.call_args_list == [call(process.namespec, info['pid'])]
    local_status.stats_collector.send_pid.reset_mock()
    # test remove process
    local_status.remove_process(process)
    # check that process is stored anymore
    assert process.namespec not in local_status.processes.keys()
    # on process removal, pid 0 is sent to the collector
    assert local_status.stats_collector.send_pid.call_args_list == [call(process.namespec, 0)]


def test_add_process_stopped_collector(supvisors, local_status):
    """ Test the SupvisorsInstanceStatus.add_process method when the process is stopped on the identifier. """
    # patch process_collector
    assert local_status.stats_collector is not None
    local_status.stats_collector = Mock()
    # add a stopped process to the InstanceStatus and add the info to the ProcessStatus instance
    info = any_process_info_by_state(ProcessStates.STOPPED)
    process = create_process(info, supvisors)
    process.add_info(local_status.identifier, info)
    local_status.add_process(process)
    # check that process is stored
    assert process.namespec in local_status.processes.keys()
    assert process is local_status.processes[process.namespec]
    # check data in process_collector queue
    assert not local_status.stats_collector.send_pid.called
    # on process update, send the pid again
    local_status.update_process(process)
    assert local_status.stats_collector.send_pid.call_args_list == [call(process.namespec, info['pid'])]
    local_status.stats_collector.send_pid.reset_mock()
    # test remove process
    local_status.remove_process(process)
    # check that process is stored anymore
    assert process.namespec not in local_status.processes.keys()
    # on process removal, pid 0 is sent to the collector
    assert local_status.stats_collector.send_pid.call_args_list == [call(process.namespec, info['pid'])]


def test_update_tick(mocker, filled_status):
    """ Test the SupvisorsInstanceStatus.update_tick method. """
    mocked_proc_times = [mocker.patch.object(process, 'update_times')
                         for process in filled_status.processes.values()]
    # check calls for local tick
    now, now_mono = time.time(), time.monotonic()
    filled_status.update_tick(25, now_mono, now)
    assert filled_status.times.remote_sequence_counter == 25
    assert filled_status.times.remote_mtime == now_mono
    assert filled_status.times.remote_time == now
    assert filled_status.times.local_sequence_counter == 25
    assert filled_status.times.local_mtime == now_mono
    assert filled_status.times.local_time == now
    for mocked in mocked_proc_times:
        assert mocked.call_args_list == [call(filled_status.identifier, filled_status.times.remote_mtime,
                                              filled_status.times.remote_time)]
    mocker.resetall()
    # check calls for remote tick
    now, now_mono = time.time(), time.monotonic()
    filled_status.update_tick(27, now_mono, now, 25)
    assert filled_status.times.remote_sequence_counter == 27
    assert filled_status.times.remote_mtime == now_mono
    assert filled_status.times.remote_time == now
    assert filled_status.times.local_sequence_counter == 25
    assert filled_status.times.local_mtime >= now_mono
    assert filled_status.times.local_time >= now
    for mocked in mocked_proc_times:
        assert mocked.call_args_list == [call(filled_status.identifier, filled_status.times.remote_mtime,
                                              filled_status.times.remote_time)]


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
