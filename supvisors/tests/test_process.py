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
from unittest.mock import call

import pytest
from supervisor.states import _process_states_by_code

from supvisors.process import *
from supvisors.ttypes import RunningFailureStrategies
from .base import any_process_info, any_stopped_process_info, process_info_by_name, any_process_info_by_state
from .conftest import create_process


# ProcessRules part
@pytest.fixture
def rules_instance(supvisors_instance):
    """ Return the instance to test. """
    return ProcessRules(supvisors_instance)


def test_rules_create(supvisors_instance, rules_instance):
    """ Test the values set at construction. """
    assert rules_instance.supvisors is supvisors_instance
    assert rules_instance.identifiers == ['*']
    assert rules_instance.hash_identifiers == []
    assert rules_instance.start_sequence == 0
    assert rules_instance.stop_sequence == -1
    assert not rules_instance.required
    assert not rules_instance.wait_exit
    assert rules_instance.expected_load == 0
    assert rules_instance.starting_failure_strategy == StartingFailureStrategies.ABORT
    assert rules_instance.running_failure_strategy == RunningFailureStrategies.CONTINUE


def test_rules_str(rules_instance):
    """ Test the string output. """
    assert str(rules_instance) == ("identifiers=['*'] at_identifiers=[] hash_identifiers=[]"
                                   " start_sequence=0 stop_sequence=-1 required=False"
                                   " wait_exit=False expected_load=0 starting_failure_strategy=ABORT"
                                   " running_failure_strategy=CONTINUE")


def test_rules_serial(rules_instance):
    """ Test the serialization of the ProcessRules object. """
    assert rules_instance.serial() == {'identifiers': ['*'], 'start_sequence': 0, 'stop_sequence': -1,
                                       'required': False, 'wait_exit': False, 'expected_loading': 0,
                                       'starting_failure_strategy': 'ABORT', 'running_failure_strategy': 'CONTINUE'}


def test_rules_check_start_sequence(rules_instance):
    """ Test the dependencies in process rules. """
    # 1. test with not required and no start sequence
    rules_instance.start_sequence = 0
    rules_instance.required = False
    # call check dependencies
    rules_instance.check_dependencies('dummy', False)
    # check rules unchanged
    assert rules_instance.start_sequence == 0
    assert not rules_instance.required
    # 2. test with required and no start sequence
    rules_instance.start_sequence = 0
    rules_instance.required = True
    # check dependencies
    rules_instance.check_dependencies('dummy', False)
    # check required has been changed
    assert rules_instance.start_sequence == 0
    assert not rules_instance.required
    # 3. test with not required and start sequence
    rules_instance.start_sequence = 1
    rules_instance.required = False
    # check dependencies
    rules_instance.check_dependencies('dummy', False)
    # check rules unchanged
    assert rules_instance.start_sequence == 1
    assert not rules_instance.required
    # 4. test with required and start sequence
    rules_instance.start_sequence = 1
    rules_instance.required = True
    # check dependencies
    rules_instance.check_dependencies('dummy', False)
    # check rules unchanged
    assert rules_instance.start_sequence == 1
    assert rules_instance.required


def test_rules_check_stop_sequence(rules_instance):
    """ Test the assignment of stop sequence to start sequence if default still set. """
    # test when default still used
    assert rules_instance.start_sequence == 0
    assert rules_instance.stop_sequence == -1
    rules_instance.check_stop_sequence('crash')
    assert rules_instance.start_sequence == 0
    assert rules_instance.stop_sequence == 0
    # test when value has been set
    rules_instance.start_sequence = 12
    rules_instance.stop_sequence = 50
    rules_instance.check_stop_sequence('crash')
    assert rules_instance.start_sequence == 12
    assert rules_instance.stop_sequence == 50


def test_rules_check_autorestart(mocker, rules_instance):
    """ Test the dependency related to running failure strategy in process rules.
    Done in a separate test as it impacts the supervisor internal model. """
    # test based on programs unknown to Supervisor
    mocked_disable = mocker.patch.object(rules_instance.supvisors.supervisor_data, 'disable_autorestart')
    mocked_autorestart = mocker.patch.object(rules_instance.supvisors.supervisor_data, 'autorestart')
    mocked_autorestart.side_effect = KeyError
    for strategy in RunningFailureStrategies:
        rules_instance.running_failure_strategy = strategy
        rules_instance.check_autorestart('dummy_process_1')
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
        rules_instance.running_failure_strategy = strategy
        rules_instance.check_autorestart('dummy_process_1')
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
        rules_instance.running_failure_strategy = strategy
        rules_instance.check_autorestart('dummy_process_1')
        if strategy in [RunningFailureStrategies.STOP_APPLICATION, RunningFailureStrategies.RESTART_APPLICATION]:
            assert mocked_disable.call_args_list == [call('dummy_process_1')]
            mocked_disable.reset_mock()
        else:
            assert not mocked_disable.called


def test_rules_check_at_identifiers(rules_instance):
    """ Test the rules consistence when at_identifiers is set. """
    assert rules_instance.at_identifiers == []
    assert rules_instance.identifiers == ['*']
    # test with no at_identifiers
    for is_pattern in [True, False]:
        rules_instance.check_at_identifiers('dummy_process', is_pattern)
        assert rules_instance.at_identifiers == []
        assert rules_instance.identifiers == ['*']
    # test with pattern: no change
    rules_instance.at_identifiers = ['10.0.0.1', '10.0.0.2']
    assert rules_instance.identifiers == ['*']
    rules_instance.check_at_identifiers('dummy_process', True)
    assert rules_instance.at_identifiers == ['10.0.0.1', '10.0.0.2']
    assert rules_instance.identifiers == ['*']
    # test without pattern: reset
    rules_instance.check_at_identifiers('dummy_process', False)
    assert rules_instance.at_identifiers == []
    assert rules_instance.identifiers == ['*']


def test_rules_check_hash_identifiers(rules_instance):
    """ Test the rules consistence when hash_identifiers is set. """
    assert rules_instance.hash_identifiers == []
    assert rules_instance.identifiers == ['*']
    # test with no at_identifiers
    for is_pattern in [True, False]:
        rules_instance.check_hash_identifiers('dummy_process', is_pattern)
        assert rules_instance.hash_identifiers == []
        assert rules_instance.identifiers == ['*']
    # test with pattern: no change
    rules_instance.hash_identifiers = ['10.0.0.1', '10.0.0.2']
    assert rules_instance.identifiers == ['*']
    rules_instance.check_hash_identifiers('dummy_process', True)
    assert rules_instance.hash_identifiers == ['10.0.0.1', '10.0.0.2']
    assert rules_instance.identifiers == ['*']
    # test without pattern: reset
    rules_instance.check_hash_identifiers('dummy_process', False)
    assert rules_instance.hash_identifiers == []
    assert rules_instance.identifiers == ['*']


def test_rules_check_sign_identifiers(rules_instance):
    """ Test the rules consistence when at_identifiers and hash_identifiers is set. """
    assert rules_instance.at_identifiers == []
    assert rules_instance.hash_identifiers == []
    assert rules_instance.identifiers == ['*']
    # test no change with no hash or at identifiers
    rules_instance.check_sign_identifiers('dummy_process')
    assert rules_instance.at_identifiers == []
    assert rules_instance.hash_identifiers == []
    assert rules_instance.identifiers == ['*']
    # test no change with only at identifiers
    rules_instance.at_identifiers = ['10.0.0.1', '10.0.0.2']
    rules_instance.check_sign_identifiers('dummy_process')
    assert rules_instance.at_identifiers == ['10.0.0.1', '10.0.0.2']
    assert rules_instance.hash_identifiers == []
    assert rules_instance.identifiers == ['*']
    # test no change with only hash identifiers
    rules_instance.at_identifiers, rules_instance.hash_identifiers = rules_instance.hash_identifiers, rules_instance.at_identifiers
    rules_instance.check_sign_identifiers('dummy_process')
    assert rules_instance.at_identifiers == []
    assert rules_instance.hash_identifiers == ['10.0.0.1', '10.0.0.2']
    assert rules_instance.identifiers == ['*']
    # test change with both at and hash identifiers
    rules_instance.at_identifiers = ['10.0.0.1', '10.0.0.2']
    rules_instance.check_sign_identifiers('dummy_process')
    assert rules_instance.at_identifiers == ['10.0.0.1', '10.0.0.2']
    assert rules_instance.hash_identifiers == []
    assert rules_instance.identifiers == ['*']


def test_rules_check_dependencies(mocker, rules_instance):
    """ Test the dependencies in process rules. """
    mocked_at = mocker.patch('supvisors.process.ProcessRules.check_at_identifiers')
    mocked_hash = mocker.patch('supvisors.process.ProcessRules.check_hash_identifiers')
    mocked_sign = mocker.patch('supvisors.process.ProcessRules.check_sign_identifiers')
    mocked_start = mocker.patch('supvisors.process.ProcessRules.check_start_sequence')
    mocked_stop = mocker.patch('supvisors.process.ProcessRules.check_stop_sequence')
    mocked_auto = mocker.patch('supvisors.process.ProcessRules.check_autorestart')
    # check dependencies
    rules_instance.check_dependencies('dummy', False)
    # test calls
    assert mocked_at.call_args_list == [call('dummy', False)]
    assert mocked_hash.call_args_list == [call('dummy', False)]
    assert mocked_sign.call_args_list == [call('dummy')]
    assert mocked_start.call_args_list == [call('dummy')]
    assert mocked_stop.call_args_list == [call('dummy')]
    assert mocked_auto.call_args_list == [call('dummy')]


# ProcessStatus part
def test_process_create(supvisors_instance):
    """ Test the values set at ProcessStatus construction. """
    info = any_stopped_process_info()
    process = create_process(info, supvisors_instance)
    # check application default attributes
    assert process.supvisors is supvisors_instance
    assert process.application_name == info['group']
    assert process.process_name == info['name']
    assert process.namespec == make_namespec(info['group'], info['name'])
    assert process.state == ProcessStates.UNKNOWN
    assert process.forced_state is None
    assert process.forced_reason == ''
    assert process.expected_exit
    assert process.last_event_mtime == 0
    assert process.extra_args == ''
    assert process.running_identifiers == set()
    assert process.info_map == {}
    # rules part identical to construction
    assert process.rules.__dict__ == ProcessRules(supvisors_instance).__dict__


def test_process_program_name_process_index(supvisors_instance):
    """ Test the ProcessStatus program_name and process_index properties. """
    # create process
    info = any_process_info()
    info['program_name'] = 'dummy_process'
    info['process_index'] = 5
    process = create_process(info, supvisors_instance)
    assert process.program_name == ''
    assert process.process_index == 0
    # add info payload to identifier 10.0.0.1
    process.info_map['10.0.0.1'] = info
    # test program_name / process_index set for the first time
    process.program_name = info['program_name']
    process.process_index = info['process_index']
    assert process.program_name == 'dummy_process'
    assert process.process_index == 5
    # add info payload to identifier 10.0.0.2
    process.info_map['10.0.0.1'] = info
    # test set consistent program_name
    process.program_name = info['program_name']
    process.process_index = info['process_index']
    assert process.program_name == 'dummy_process'
    assert process.process_index == 5
    # test set inconsistent program_name (accepted but this triggers error logs)
    process.program_name = 'dummy_proc'
    process.process_index = 4
    assert process.program_name == 'dummy_proc'
    assert process.process_index == 4


def test_process_disabled(supvisors_instance):
    """ Test the ProcessStatus.disabled method. """
    info = any_process_info()
    process = create_process(info, supvisors_instance)
    # test enabled when no possible identifiers
    assert not process.disabled()
    process.add_info('10.0.0.1', info)
    process.add_info('10.0.0.2', info.copy())
    # test enabled
    assert not process.disabled()
    # test with one disabled among two
    process.info_map['10.0.0.1']['disabled'] = True
    assert not process.disabled()
    # test with all disabled
    process.info_map['10.0.0.2']['disabled'] = True
    assert process.disabled()


def test_process_disabled_on(supvisors_instance):
    """ Test the ProcessStatus.disabled_on method. """
    info = any_process_info()
    process = create_process(info, supvisors_instance)
    process.add_info('10.0.0.2', info)
    # test with identifier not found in process info_map
    assert not process.disabled_on('10.0.0.1')
    # test with identifier found in process info_map and enabled
    assert not process.disabled_on('10.0.0.2')
    # test with identifier found in process info_map and disabled
    info['disabled'] = True
    assert process.disabled_on('10.0.0.2')


def test_process_possible_identifiers(supvisors_instance):
    """ Test the ProcessStatus.possible_identifiers method. """
    info = any_process_info()
    process = create_process(info, supvisors_instance)
    process.add_info('10.0.0.2:25000', info)
    process.add_info('10.0.0.4:25000', info.copy())
    # default identifiers is '*' in process rules and all are enabled
    assert process.possible_identifiers() == ['10.0.0.2:25000', '10.0.0.4:25000']
    # set a subset of identifiers in process rules so that there's no intersection with received status
    process.rules.identifiers = ['10.0.0.1:25000', '10.0.0.3:25000']
    assert process.possible_identifiers() == []
    # increase received status
    process.add_info('10.0.0.3:25000', info.copy())
    assert process.possible_identifiers() == ['10.0.0.3:25000']
    # disable program on '10.0.0.3'
    process.update_disability('10.0.0.3:25000', True)
    assert process.possible_identifiers() == []
    # reset rules
    process.rules.identifiers = ['*']
    assert process.possible_identifiers() == ['10.0.0.2:25000', '10.0.0.4:25000']
    # test with full status and all instances in rules + re-enable on '10.0.0.3'
    process.update_disability('10.0.0.3:25000', False)
    for identifier in supvisors_instance.mapper.instances:
        process.add_info(identifier, info.copy())
    assert process.possible_identifiers() == list(supvisors_instance.mapper.instances.keys())
    # restrict again instances in rules
    process.rules.identifiers = ['10.0.0.5:25000']
    assert process.possible_identifiers() == ['10.0.0.5:25000']


def test_status_stopped_process(supvisors_instance):
    """ Test the stopped / running / crashed status with a STOPPED process. """
    info = any_process_info_by_state(ProcessStates.STOPPED)
    process = create_process(info, supvisors_instance)
    process.add_info('10.0.0.1', info)
    assert process.state == ProcessStates.STOPPED
    assert process.state_string() == 'STOPPED'
    assert process.displayed_state == ProcessStates.STOPPED
    assert process.displayed_state_string() == 'STOPPED'
    assert process.stopped()
    assert not process.running()
    assert not process.crashed()
    assert not process.crashed('10.0.0.1')
    assert not process.crashed('10.0.0.2')
    assert not process.running_on('10.0.0.1')
    assert not process.running_on('10.0.0.2')
    # test again with forced state
    event = {'state': ProcessStates.FATAL, 'identifier': '10.0.0.2', 'spawnerr': '',
             'now': time.time(), 'now_monotonic': time.monotonic()}
    assert process.force_state(event)
    assert process.state == ProcessStates.STOPPED
    assert process.state_string() == 'STOPPED'
    assert process.displayed_state == ProcessStates.FATAL
    assert process.displayed_state_string() == 'FATAL'
    assert process.stopped()
    assert not process.running()
    assert not process.crashed()
    assert not process.crashed('10.0.0.1')
    assert not process.crashed('10.0.0.2')
    assert not process.running_on('10.0.0.1')
    assert not process.running_on('10.0.0.2')
    # STOPPED does not reset the forced state
    process.reset_forced_state(ProcessStates.STOPPED)
    assert process.state == ProcessStates.STOPPED
    assert process.state_string() == 'STOPPED'
    assert process.displayed_state == ProcessStates.FATAL
    assert process.displayed_state_string() == 'FATAL'
    assert process.stopped()
    assert not process.running()
    assert not process.crashed()
    assert not process.crashed('10.0.0.1')
    assert not process.crashed('10.0.0.2')
    # use empty param to reset the forced state
    process.reset_forced_state()
    assert process.state == ProcessStates.STOPPED
    assert process.state_string() == 'STOPPED'
    assert process.displayed_state == ProcessStates.STOPPED
    assert process.displayed_state_string() == 'STOPPED'
    assert process.stopped()
    assert not process.running()
    assert not process.crashed()
    assert not process.crashed('10.0.0.1')
    assert not process.crashed('10.0.0.2')


def test_status_backoff_process(supvisors_instance):
    """ Test the stopped / running / crashed status with a BACKOFF process. """
    info = any_process_info_by_state(ProcessStates.BACKOFF)
    process = create_process(info, supvisors_instance)
    process.add_info('10.0.0.1', info)
    assert process.state == ProcessStates.BACKOFF
    assert process.state_string() == 'BACKOFF'
    assert process.displayed_state == ProcessStates.BACKOFF
    assert process.displayed_state_string() == 'BACKOFF'
    assert not process.stopped()
    assert process.running()
    assert not process.crashed()
    assert not process.crashed('10.0.0.1')
    assert not process.crashed('10.0.0.2')
    assert process.running_on('10.0.0.1')
    assert not process.running_on('10.0.0.2')
    # test again with forced state
    event = {'state': ProcessStates.STOPPED, 'identifier': '10.0.0.1', 'spawnerr': '',
             'now': time.time(), 'now_monotonic': time.time() - 1e6}
    assert process.force_state(event)
    assert process.state == ProcessStates.BACKOFF
    assert process.state_string() == 'BACKOFF'
    assert process.displayed_state == ProcessStates.STOPPED
    assert process.displayed_state_string() == 'STOPPED'
    assert not process.stopped()
    assert process.running()
    assert not process.crashed()
    assert not process.crashed('10.0.0.1')
    assert not process.crashed('10.0.0.2')
    assert process.running_on('10.0.0.1')
    assert not process.running_on('10.0.0.2')
    # BACKOFF resets the forced state
    process.reset_forced_state(ProcessStates.BACKOFF)
    assert process.state == ProcessStates.BACKOFF
    assert process.state_string() == 'BACKOFF'
    assert process.displayed_state == ProcessStates.BACKOFF
    assert process.displayed_state_string() == 'BACKOFF'
    assert not process.stopped()
    assert process.running()
    assert not process.crashed()
    assert not process.crashed('10.0.0.1')
    assert not process.crashed('10.0.0.2')


def test_status_running_process(supvisors_instance):
    """ Test the stopped / running / crashed status with a RUNNING process. """
    info = any_process_info_by_state(ProcessStates.RUNNING)
    process = create_process(info, supvisors_instance)
    process.add_info('10.0.0.1', info)
    assert process.state == ProcessStates.RUNNING
    assert process.state_string() == 'RUNNING'
    assert process.displayed_state == ProcessStates.RUNNING
    assert process.displayed_state_string() == 'RUNNING'
    assert not process.stopped()
    assert process.running()
    assert not process.crashed()
    assert not process.crashed('10.0.0.1')
    assert not process.crashed('10.0.0.2')
    assert process.running_on('10.0.0.1')
    assert not process.running_on('10.0.0.2')
    # test again with forced state
    # here, the stored event is more recent so the forced state is ignored
    event = {'state': ProcessStates.FATAL, 'identifier': '10.0.0.1', 'spawnerr': '',
             'now': time.time(), 'now_monotonic': 0}
    assert not process.force_state(event)
    assert process.state == ProcessStates.RUNNING
    assert process.state_string() == 'RUNNING'
    assert process.displayed_state == ProcessStates.RUNNING
    assert process.displayed_state_string() == 'RUNNING'
    assert process._state == ProcessStates.RUNNING
    assert not process.stopped()
    assert process.running()
    assert not process.crashed()
    assert not process.crashed('10.0.0.1')
    assert not process.crashed('10.0.0.2')
    assert process.running_on('10.0.0.1')
    assert not process.running_on('10.0.0.2')


def test_status_stopping_process(supvisors_instance):
    """ Test the stopped / running / crashed status with a STOPPING process. """
    info = any_process_info_by_state(ProcessStates.STOPPING)
    process = create_process(info, supvisors_instance)
    process.add_info('10.0.0.1', info)
    assert process.state == ProcessStates.STOPPING
    assert process.state_string() == 'STOPPING'
    assert process.displayed_state == ProcessStates.STOPPING
    assert process.displayed_state_string() == 'STOPPING'
    assert not process.stopped()
    assert not process.running()
    assert not process.crashed()
    assert not process.crashed('10.0.0.1')
    assert not process.crashed('10.0.0.2')
    assert not process.running_on('10.0.0.1')
    assert not process.running_on('10.0.0.2')
    # test again with forced state
    event = {'state': ProcessStates.STOPPED, 'identifier': '10.0.0.1', 'spawnerr': '',
             'now': time.time(), 'now_monotonic': time.time() - 1e6}
    assert process.force_state(event)
    assert process.state == ProcessStates.STOPPING
    assert process.state_string() == 'STOPPING'
    assert process.displayed_state == ProcessStates.STOPPED
    assert process.displayed_state_string() == 'STOPPED'
    assert not process.stopped()
    assert not process.running()
    assert not process.crashed()
    assert not process.crashed('10.0.0.1')
    assert not process.crashed('10.0.0.2')
    assert not process.running_on('10.0.0.1')
    assert not process.running_on('10.0.0.2')
    # STOPPING resets the forced state
    process.reset_forced_state(ProcessStates.STOPPING)
    assert process.state == ProcessStates.STOPPING
    assert process.state_string() == 'STOPPING'
    assert process.displayed_state == ProcessStates.STOPPING
    assert process.displayed_state_string() == 'STOPPING'
    assert not process.stopped()
    assert not process.running()
    assert not process.crashed()
    assert not process.crashed('10.0.0.1')
    assert not process.crashed('10.0.0.2')


def test_status_fatal_process(supvisors_instance):
    """ Test the stopped / running / crashed status with a FATAL process. """
    info = any_process_info_by_state(ProcessStates.FATAL)
    process = create_process(info, supvisors_instance)
    process.add_info('10.0.0.1', info)
    assert process.state == ProcessStates.FATAL
    assert process.state_string() == 'FATAL'
    assert process.displayed_state == ProcessStates.FATAL
    assert process.displayed_state_string() == 'FATAL'
    assert process.stopped()
    assert not process.running()
    assert process.crashed()
    assert process.crashed('10.0.0.1')
    assert not process.crashed('10.0.0.2')
    assert not process.running_on('10.0.0.1')
    assert not process.running_on('10.0.0.2')
    # test again with forced state
    event = {'state': ProcessStates.STOPPED, 'identifier': '10.0.0.1', 'spawnerr': '',
             'now': time.time(), 'now_monotonic': time.time() - 1e6}
    assert process.force_state(event)
    assert process.state == ProcessStates.FATAL
    assert process.state_string() == 'FATAL'
    assert process.displayed_state == ProcessStates.STOPPED
    assert process.displayed_state_string() == 'STOPPED'
    assert process.stopped()
    assert not process.running()
    assert process.crashed()
    assert process.crashed('10.0.0.1')
    assert not process.crashed('10.0.0.2')
    assert not process.running_on('10.0.0.1')
    assert not process.running_on('10.0.0.2')
    # FATAL resets the forced state
    process.reset_forced_state(ProcessStates.FATAL)
    assert process.state == ProcessStates.FATAL
    assert process.state_string() == 'FATAL'
    assert process.displayed_state == ProcessStates.FATAL
    assert process.displayed_state_string() == 'FATAL'
    assert process.stopped()
    assert not process.running()
    assert process.crashed()
    assert process.crashed('10.0.0.1')
    assert not process.crashed('10.0.0.2')


def test_status_exited_process(supvisors_instance):
    """ Test the stopped / running / crashed status with an EXITED process. """
    # test with expected_exit
    info = any_process_info_by_state(ProcessStates.EXITED)
    process = create_process(info, supvisors_instance)
    process.add_info('10.0.0.1', info)
    process.expected_exit = True
    assert process.state == ProcessStates.EXITED
    assert process.state_string() == 'EXITED'
    assert process.displayed_state == ProcessStates.EXITED
    assert process.displayed_state_string() == 'EXITED'
    assert process.stopped()
    assert not process.running()
    assert not process.crashed()
    assert not process.crashed('10.0.0.1')
    assert not process.crashed('10.0.0.2')
    assert not process.running_on('10.0.0.1')
    assert not process.running_on('10.0.0.2')
    # test with unexpected_exit
    process.expected_exit = False
    assert process.state == ProcessStates.EXITED
    assert process.state_string() == 'EXITED'
    assert process.displayed_state == ProcessStates.EXITED
    assert process.displayed_state_string() == 'EXITED'
    assert process.stopped()
    assert not process.running()
    assert process.crashed()
    assert not process.crashed('10.0.0.1')
    assert not process.crashed('10.0.0.2')
    assert not process.running_on('10.0.0.1')
    assert not process.running_on('10.0.0.2')
    # test again with forced state
    event = {'state': ProcessStates.FATAL, 'identifier': '10.0.0.1', 'spawnerr': '',
             'now': time.time(), 'now_monotonic': time.time() - 1e6}
    assert process.force_state(event)
    assert process.state == ProcessStates.EXITED
    assert process.state_string() == 'EXITED'
    assert process.displayed_state == ProcessStates.FATAL
    assert process.displayed_state_string() == 'FATAL'
    assert process.stopped()
    assert not process.running()
    assert process.crashed()
    assert not process.crashed('10.0.0.1')
    assert not process.crashed('10.0.0.2')
    assert not process.running_on('10.0.0.1')
    assert not process.running_on('10.0.0.2')
    # EXITED resets the forced state
    process.reset_forced_state(ProcessStates.EXITED)
    assert process.state == ProcessStates.EXITED
    assert process.state_string() == 'EXITED'
    assert process.displayed_state == ProcessStates.EXITED
    assert process.displayed_state_string() == 'EXITED'
    assert process.stopped()
    assert not process.running()
    assert process.crashed()
    assert not process.crashed('10.0.0.1')
    assert not process.crashed('10.0.0.2')


def test_process_conflicting(supvisors_instance):
    """ Test the is ProcessStatus.conflicting method. """
    # when there is only one STOPPED process info, there is no conflict
    info = any_process_info_by_state(ProcessStates.STOPPED)
    process = create_process(info, supvisors_instance)
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


def test_extra_args(mocker, supvisors_instance):
    """ Test the accessors of the ProcessStatus extra_args. """
    info = any_process_info()
    process = create_process(info, supvisors_instance)
    assert process._extra_args == ''
    assert process.extra_args == ''
    # test assignment
    process.extra_args = 'new args'
    assert process._extra_args == 'new args'
    assert process.extra_args == 'new args'
    # test internal exception when process unknown to the local Supervisor
    mocker.patch.object(supvisors_instance.supervisor_data, 'update_extra_args', side_effect=KeyError)
    process.extra_args = 'another args'
    assert process._extra_args == 'another args'
    assert process.extra_args == 'another args'


def test_serialization(mocker, supvisors_instance):
    """ Test the serialization of the ProcessStatus. """
    mocker.patch('time.monotonic', return_value=1234.56)
    # test with a STOPPED process
    info = any_process_info_by_state(ProcessStates.STOPPED)
    process = create_process(info, supvisors_instance)
    process.add_info('10.0.0.1', info)
    serialized = process.serial()
    assert serialized == {'application_name': info['group'], 'process_name': info['name'],
                          'now_monotonic': 1234.56, 'last_event_mtime': process.last_event_mtime,
                          'statecode': 0, 'statename': 'STOPPED', 'expected_exit': info['expected'],
                          'identifiers': [], 'extra_args': ''}
    # test that returned structure is serializable using pickle
    dumped = pickle.dumps(serialized)
    loaded = pickle.loads(dumped)
    assert loaded == serialized
    # test again with forced state
    event = {'state': ProcessStates.FATAL, 'identifier': '10.0.0.1', 'spawnerr': 'anything',
             'now': time.time(), 'now_monotonic': time.time() - 1e6}
    assert process.force_state(event)
    assert process._state == ProcessStates.STOPPED
    serialized = process.serial()
    assert serialized == {'application_name': info['group'], 'process_name': info['name'],
                          'now_monotonic': 1234.56, 'last_event_mtime': process.last_event_mtime,
                          'statecode': 200, 'statename': 'FATAL', 'expected_exit': info['expected'],
                          'identifiers': [], 'extra_args': ''}


def test_get_applicable_details(supvisors_instance):
    """ Test the ViewContext.get_applicable_details method. """
    # create ProcessStatus instance
    process = create_process({'group': 'dummy_application', 'name': 'dummy_proc'}, supvisors_instance)
    process.info_map = {'10.0.0.1:25000': {'local_time': 10, 'start': 25, 'stop': 32, 'description': 'desc1', 'state': 0,
                                           'now': 50, 'event_time': 50, 'has_stdout': True, 'has_stderr': False},
                        '10.0.0.2:25000': {'local_time': 30, 'start': 0, 'stop': 0, 'description': 'Not started',
                                           'now': 55, 'event_time': 50, 'has_stdout': False, 'has_stderr': False},
                        '10.0.0.3:25000': {'local_time': 20, 'start': 5, 'stop': 22, 'description': 'desc3',
                                           'now': 53, 'event_time': 50, 'has_stdout': True, 'has_stderr': True}}
    # state is not forced by default
    # test method return on non-running process
    assert process.get_applicable_details() == ('10.0.0.1:25000', 'desc1 on 10.0.0.1',  True, False)
    # test method return on running process
    process.running_identifiers.add('10.0.0.3:25000')
    assert process.get_applicable_details() == ('10.0.0.3:25000', 'desc3 on 10.0.0.3', True, True)
    # test method return on multiple running processes
    process.running_identifiers.add('10.0.0.2:25000')
    possible_results = [(None, 'conflict on 10.0.0.3, 10.0.0.2', False, False),
                        (None, 'conflict on 10.0.0.2, 10.0.0.3', False, False)]
    assert process.get_applicable_details() in possible_results
    # test again with forced state
    event = {'state': ProcessStates.FATAL, 'identifier': '10.0.0.1:25000',
             'now_monotonic': 50, 'spawnerr': 'global crash'}
    assert process.force_state(event)
    assert process.get_applicable_details() == (None, 'global crash', False, False)
    process.running_identifiers = set()
    assert process.get_applicable_details() == (None, 'global crash', False, False)


def test_has_stdout_stderr(supvisors_instance):
    """ Test the ViewContext.has_stdout and has_stderrmethods. """
    # create ProcessStatus instance
    process = create_process({'group': 'dummy_application', 'name': 'dummy_proc'}, supvisors_instance)
    process.info_map = {'10.0.0.1:25000': {'start': 25, 'has_stdout': True, 'has_stderr': False},
                        '10.0.0.2:25000': {'start': 0, 'has_stdout': False, 'has_stderr': False},
                        '10.0.0.3:25000': {'start': 5, 'has_stdout': False, 'has_stderr': True},
                        '10.0.0.4:25000': {'start': 0, 'has_stdout': True, 'has_stderr': True}}
    # test calls
    assert process.has_stdout('10.0.0.1:25000')
    assert not process.has_stderr('10.0.0.1:25000')
    assert not process.has_stdout('10.0.0.2:25000')
    assert not process.has_stderr('10.0.0.2:25000')
    assert not process.has_stdout('10.0.0.3:25000')
    assert process.has_stderr('10.0.0.3:25000')
    assert not process.has_stdout('10.0.0.4:25000')
    assert not process.has_stderr('10.0.0.4:25000')


def test_add_info(supvisors_instance):
    """ Test the addition of a process info into the ProcessStatus. """
    # get a process info and complement extra_args
    info = process_info_by_name('xclock')
    info['extra_args'] = '-x dummy'
    assert 'uptime' not in info
    # 1. create ProcessStatus instance
    process = create_process(info, supvisors_instance)
    process.extra_args = 'something else'
    process.add_info('10.0.0.1', info)
    # check last event info
    assert process.last_event_mtime > 0.0
    last_event_time = process.last_event_mtime
    assert last_event_time == info['local_mtime']
    assert info['event_time'] == info['now_monotonic']
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
    event = {'state': ProcessStates.FATAL, 'identifier': '10.0.0.1', 'spawnerr': 'failure',
             'now': time.time(), 'now_monotonic': time.time() - 1e6}
    assert process.force_state(event)
    assert process.forced_state == ProcessStates.FATAL
    assert process.forced_reason == 'failure'
    assert process.state == ProcessStates.STOPPING
    assert process.displayed_state == ProcessStates.FATAL
    # 2. replace with an EXITED process info
    info = any_process_info_by_state(ProcessStates.EXITED)
    info['expected'] = False
    process.add_info('10.0.0.1', info)
    # check last event info
    assert process.last_event_mtime >= last_event_time
    last_event_time = process.last_event_mtime
    assert last_event_time == info['local_mtime']
    assert info['event_time'] == info['now_monotonic']
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
    assert process.last_event_mtime >= last_event_time
    last_event_time = process.last_event_mtime
    assert last_event_time == info['local_mtime']
    assert info['event_time'] == info['now_monotonic']
    # check contents
    assert len(process.info_map) == 2
    assert process.info_map['10.0.0.2'] is info
    assert info['uptime'] == info['now'] - info['start']
    assert process.running_identifiers == {'10.0.0.2'}
    assert process.state == ProcessStates.RUNNING
    assert process.expected_exit
    assert process.has_crashed


def test_update_info(supvisors_instance):
    """ Test the update of the ProcessStatus upon reception of a process event. """
    # 1. add a STOPPED process info into a process status
    info = any_process_info_by_state(ProcessStates.STOPPED)
    process = create_process(info, supvisors_instance)
    process.add_info('10.0.0.1', info)
    # test last event info stored
    assert process.last_event_mtime > 0
    last_event_time = process.last_event_mtime
    assert last_event_time == info['local_mtime']
    assert info['event_time'] == info['now_monotonic']
    # check changes on status
    assert process.info_map['10.0.0.1']['state'] == ProcessStates.STOPPED
    assert process.state == ProcessStates.STOPPED
    assert process.extra_args == ''
    assert not info['has_crashed']
    assert not process.has_crashed()
    assert not process.running_identifiers
    # 3. update with a STARTING event
    process.update_info('10.0.0.1', {'state': ProcessStates.STARTING, 'extra_args': '-x dummy',
                                     'now': 10, 'now_monotonic': 5})
    # test last event info stored
    assert process.last_event_mtime >= last_event_time
    last_event_time = process.last_event_mtime
    assert last_event_time == info['local_mtime']
    assert info['event_time'] == info['now_monotonic']
    # check changes on status
    info = process.info_map['10.0.0.1']
    assert info['state'] == ProcessStates.STARTING
    assert process.state == ProcessStates.STARTING
    assert process.extra_args == '-x dummy'
    assert not info['has_crashed']
    assert not process.has_crashed()
    assert process.running_identifiers == {'10.0.0.1'}
    assert info['now'] == 10
    assert info['now_monotonic'] == 5
    assert info['start'] == 10
    assert info['start_monotonic'] == 5
    assert info['uptime'] == 0
    # 4. update with a RUNNING event
    process.update_info('10.0.0.1', {'state': ProcessStates.RUNNING, 'now': 15, 'now_monotonic': 10,
                                     'pid': 1234, 'extra_args': '-z another'})
    # test last event info stored
    assert process.last_event_mtime >= last_event_time
    last_event_time = process.last_event_mtime
    assert last_event_time == info['local_mtime']
    assert info['event_time'] == info['now_monotonic']
    # check changes
    assert info['state'] == ProcessStates.RUNNING
    assert process.state == ProcessStates.RUNNING
    assert process.running_identifiers == {'10.0.0.1'}
    assert process.extra_args == '-z another'
    assert not info['has_crashed']
    assert not process.has_crashed()
    assert info['pid'] == 1234
    assert info['now'] == 15
    assert info['now_monotonic'] == 10
    assert info['start'] == 10
    assert info['start_monotonic'] == 5
    assert info['uptime'] == 5
    # check forced_state
    assert process.forced_state is None
    assert process.forced_reason == ''
    event = {'state': ProcessStates.FATAL, 'identifier': '10.0.0.1', 'spawnerr': 'failure',
             'now': time.time(), 'now_monotonic': time.time() - 1e6}
    assert process.force_state(event)
    assert process.forced_state == ProcessStates.FATAL
    assert process.forced_reason == 'failure'
    assert process.state == ProcessStates.RUNNING
    assert process.displayed_state == ProcessStates.FATAL
    # 5.a add a new STOPPED process info
    info = any_process_info_by_state(ProcessStates.STOPPED)
    process.add_info('10.0.0.2', info)
    # test last event info stored
    assert process.last_event_mtime >= last_event_time
    last_event_time = process.last_event_mtime
    assert last_event_time == info['local_mtime']
    assert info['event_time'] == info['now_monotonic']
    assert process.state == ProcessStates.RUNNING
    assert process.displayed_state == ProcessStates.FATAL
    # extra_args has been reset
    assert process.extra_args == ''
    assert not info['has_crashed']
    assert not process.has_crashed()
    # 5.b update with STARTING / RUNNING events
    process.update_info('10.0.0.2', {'state': ProcessStates.STARTING, 'now': 20, 'now_monotonic': 15,
                                     'extra_args': '-x dummy'})
    process.update_info('10.0.0.2', {'state': ProcessStates.RUNNING, 'now': 25, 'now_monotonic': 20,
                                     'pid': 4321, 'extra_args': ''})
    # test last event info stored
    assert process.last_event_mtime >= last_event_time
    last_event_time = process.last_event_mtime
    assert last_event_time == info['local_mtime']
    assert info['event_time'] == info['now_monotonic']
    # check state and addresses
    assert process.state == ProcessStates.RUNNING
    assert process.extra_args == ''
    assert not info['has_crashed']
    assert not process.has_crashed()
    assert process.running_identifiers == {'10.0.0.1', '10.0.0.2'}
    # 6. update with an EXITED event
    info = process.info_map['10.0.0.1']
    process.update_info('10.0.0.1', {'state': ProcessStates.EXITED, 'now': 30, 'now_monotonic': 25,
                                     'expected': False, 'extra_args': ''})
    # test last event info stored
    assert process.last_event_mtime >= last_event_time
    last_event_time = process.last_event_mtime
    assert last_event_time == info['local_mtime']
    assert info['event_time'] == info['now_monotonic']
    # check changes
    assert info['state'] == ProcessStates.EXITED
    assert process.state == ProcessStates.RUNNING
    assert process.extra_args == ''
    assert info['has_crashed']
    assert process.has_crashed()
    assert process.running_identifiers == {'10.0.0.2'}
    assert info['pid'] == 1234
    assert info['now'] == 30
    assert info['now_monotonic'] == 25
    assert info['stop'] == 30
    assert info['stop_monotonic'] == 25
    assert info['uptime'] == 0
    assert not info['expected']
    # 7. update with an STOPPING event
    info = process.info_map['10.0.0.2']
    process.update_info('10.0.0.2', {'state': ProcessStates.STOPPING, 'now': 25, 'now_monotonic': 30,
                                     'extra_args': ''})
    # test last event info stored
    assert process.last_event_mtime >= last_event_time
    last_event_time = process.last_event_mtime
    assert last_event_time == info['local_mtime']
    assert info['event_time'] == info['now_monotonic']
    # check changes
    assert info['state'] == ProcessStates.STOPPING
    assert process.state == ProcessStates.STOPPING
    assert process.extra_args == ''
    assert not info['has_crashed']
    assert process.has_crashed()
    assert process.running_identifiers == {'10.0.0.2'}
    assert info['pid'] == 4321
    assert info['now'] == 25
    assert info['now_monotonic'] == 30
    assert info['start'] == 20
    assert info['start_monotonic'] == 15
    assert info['uptime'] == 15
    assert info['expected']
    # 8. update with an STOPPED event
    process.update_info('10.0.0.2', {'state': ProcessStates.STOPPED, 'now': 26, 'now_monotonic': 35,
                                     'extra_args': ''})
    # test last event info stored
    assert process.last_event_mtime >= last_event_time
    last_event_time = process.last_event_mtime
    assert last_event_time == info['local_mtime']
    assert info['event_time'] == info['now_monotonic']
    # check changes
    assert info['state'] == ProcessStates.STOPPED
    assert process.state == ProcessStates.STOPPED
    assert process.extra_args == ''
    assert not info['has_crashed']
    assert process.has_crashed()
    assert not process.running_identifiers
    assert info['pid'] == 4321
    assert info['now'] == 26
    assert info['now_monotonic'] == 35
    assert info['stop'] == 26
    assert info['stop_monotonic'] == 35
    assert info['uptime'] == 0
    assert info['expected']


def test_update_disability(supvisors_instance):
    """ Test the update of the disabled entry for a process info belonging to a ProcessStatus. """
    # add 2 process infos into a process status
    info = any_process_info_by_state(ProcessStates.STOPPING)
    process = create_process(info, supvisors_instance)
    process.add_info('10.0.0.1', info)
    process.add_info('10.0.0.2', any_process_info_by_state(ProcessStates.STOPPED))
    # check initial state
    assert not process.info_map['10.0.0.1']['disabled']
    assert not process.info_map['10.0.0.2']['disabled']
    # disable on identifier 2
    process.update_disability('10.0.0.2', True)
    # check that only identifier 2 is updated
    assert not process.info_map['10.0.0.1']['disabled']
    assert process.info_map['10.0.0.2']['disabled']
    # disable on identifier 1
    process.update_disability('10.0.0.1', True)
    # check that identifier 1 is updated too
    assert process.info_map['10.0.0.1']['disabled']
    assert process.info_map['10.0.0.2']['disabled']
    # reset all
    process.update_disability('10.0.0.1', False)
    process.update_disability('10.0.0.2', False)
    assert not process.info_map['10.0.0.1']['disabled']
    assert not process.info_map['10.0.0.2']['disabled']


def test_update_times(supvisors_instance):
    """ Test the update of the time entries for a process info belonging to a ProcessStatus. """
    # add 2 process infos into a process status
    info = any_process_info_by_state(ProcessStates.STOPPING)
    process = create_process(info, supvisors_instance)
    process.add_info('10.0.0.1', info)
    process.add_info('10.0.0.2', any_process_info_by_state(ProcessStates.STOPPED))
    # get their time values
    now_1 = process.info_map['10.0.0.1']['now']
    mono_1 = process.info_map['10.0.0.1']['now_monotonic']
    uptime_1 = process.info_map['10.0.0.1']['uptime']
    now_2 = process.info_map['10.0.0.2']['now']
    mono_2 = process.info_map['10.0.0.2']['now_monotonic']
    # update times on identifier 2
    process.update_times('10.0.0.2', mono_2 + 10, now_2 + 10)
    # check that nothing changed for identifier 1
    assert process.info_map['10.0.0.1']['now'] == now_1
    assert process.info_map['10.0.0.1']['now_monotonic'] == mono_1
    assert process.info_map['10.0.0.1']['uptime'] == uptime_1
    # check that times changed for address 2 (uptime excepted)
    assert process.info_map['10.0.0.2']['now'] == now_2 + 10
    assert process.info_map['10.0.0.2']['now_monotonic'] == mono_2 + 10
    assert process.info_map['10.0.0.2']['uptime'] == 0
    # update times on identifier 1
    process.update_times('10.0.0.1', mono_1 + 10, now_1 + 20)
    # check that times changed for identifier 1 (including uptime)
    assert process.info_map['10.0.0.1']['now'] == now_1 + 20
    assert process.info_map['10.0.0.1']['now_monotonic'] == mono_1 + 10
    assert process.info_map['10.0.0.1']['uptime'] == uptime_1 + 10
    # check that nothing changed for identifier 2
    assert process.info_map['10.0.0.2']['now'] == now_2 + 10
    assert process.info_map['10.0.0.2']['now_monotonic'] == mono_2 + 10
    assert process.info_map['10.0.0.2']['uptime'] == 0


def test_update_uptime():
    """ Test the update of uptime entry in a Process info dictionary. """
    # check times on a RUNNING process info
    info = {'start_monotonic': 50, 'now_monotonic': 75}
    for state in _process_states_by_code:
        info['state'] = state
        ProcessStatus.update_uptime(info)
        if state in [ProcessStates.RUNNING, ProcessStates.STOPPING]:
            assert info['uptime'] == 25
        else:
            assert info['uptime'] == 0


def test_invalidate_nodes(supvisors_instance):
    """ Test the invalidation of instances. """
    # create conflict directly with 3 process info
    info = any_process_info_by_state(ProcessStates.BACKOFF)
    process = create_process(info, supvisors_instance)
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


def test_remove_node(supvisors_instance):
    """ Test the removal of instances. """
    # create conflict directly with 2 process info
    info = any_process_info()
    process = create_process(info, supvisors_instance)
    process.add_info('10.0.0.1', info)
    process.add_info('10.0.0.2', any_process_info())
    # check process info_map
    assert sorted(process.info_map.keys()) == ['10.0.0.1', '10.0.0.2']
    assert not process.remove_identifier('10.0.0.2')
    assert sorted(process.info_map.keys()) == ['10.0.0.1']
    assert process.remove_identifier('10.0.0.1')
    assert sorted(process.info_map.keys()) == []


def test_update_status(supvisors_instance):
    """ Test the update of state and running Supvisors instances. """
    # force local monotonic time to same value as the proces info
    # increase logger level to hit special log traces
    supvisors_instance.logger.level = LevelsByName.BLAT
    # update_status is called in the construction
    info = any_process_info_by_state(ProcessStates.FATAL)
    process = create_process(info, supvisors_instance)
    process.add_info('10.0.0.3', info)
    process.info_map['10.0.0.3']['local_mtime'] = 10
    assert process.running_identifiers == set()
    assert process.state == ProcessStates.FATAL
    assert not process.expected_exit
    # add a STOPPED process info
    info = any_process_info_by_state(ProcessStates.STOPPED)
    process.add_info('10.0.0.1', info)
    process.info_map['10.0.0.1']['local_mtime'] = 5
    process.update_status('10.0.0.1', ProcessStates.STOPPED)
    assert process.running_identifiers == set()
    assert process.state == ProcessStates.FATAL  # FATAL info above is more recent
    assert not process.expected_exit
    # replace with an EXITED process info
    info = any_process_info_by_state(ProcessStates.EXITED)
    process.update_info('10.0.0.3', info)
    process.info_map['10.0.0.3']['local_mtime'] = 15
    process.update_status('10.0.0.3', ProcessStates.EXITED)
    assert process.running_identifiers == set()
    assert process.state == ProcessStates.EXITED
    assert process.expected_exit
    # add a STARTING process info
    info = any_process_info_by_state(ProcessStates.STARTING)
    process.add_info('10.0.0.2', info)
    process.info_map['10.0.0.2']['local_mtime'] = 20
    process.update_status('10.0.0.2', ProcessStates.STARTING)
    assert process.running_identifiers == {'10.0.0.2'}
    assert process.state == ProcessStates.STARTING
    assert process.expected_exit
    # replace a BACKOFF process info
    info = any_process_info_by_state(ProcessStates.BACKOFF)
    process.update_info('10.0.0.3', info)
    process.info_map['10.0.0.3']['local_mtime'] = 20
    process.update_status('10.0.0.3', ProcessStates.BACKOFF)
    assert process.running_identifiers == {'10.0.0.3', '10.0.0.2'}
    assert process.state == ProcessStates.BACKOFF
    assert process.expected_exit
    # replace STARTING process info with RUNNING
    info = any_process_info_by_state(ProcessStates.RUNNING)
    process.update_info('10.0.0.2', info)
    process.info_map['10.0.0.2']['local_mtime'] = 25
    process.update_status('10.0.0.2', ProcessStates.RUNNING)
    assert process.running_identifiers == {'10.0.0.3', '10.0.0.2'}
    assert process.state == ProcessStates.RUNNING
    assert process.expected_exit
    # replace BACKOFF process info with FATAL
    info = any_process_info_by_state(ProcessStates.FATAL)
    process.update_info('10.0.0.3', info)
    process.info_map['10.0.0.3']['local_mtime'] = 25
    process.update_status('10.0.0.3', ProcessStates.FATAL)
    assert process.running_identifiers == {'10.0.0.2'}
    assert process.state == ProcessStates.RUNNING
    assert process.expected_exit
    # replace RUNNING process info with STOPPED
    # in ProcessInfoDatabase, EXITED processes have a stop date later than STOPPED processes
    info = any_process_info_by_state(ProcessStates.STOPPED)
    process.update_info('10.0.0.2', info)
    process.info_map['10.0.0.2']['local_mtime'] = 30
    process.update_status('10.0.0.2', ProcessStates.STOPPED)
    assert not process.running_identifiers
    assert process.state == ProcessStates.STOPPED
    assert process.expected_exit


def test_process_evaluate_conflict(supvisors_instance):
    """ Test the determination of a synthetic state in case of conflict. """
    # when there is only one STOPPED process info, there is no conflict
    # this method is expected to be called only when a conflict (multiple running processes) is detected
    # the state is evaluated against running states. STOPPED leads to UNKNOWN
    info = any_process_info_by_state(ProcessStates.STOPPED)
    process = create_process(info, supvisors_instance)
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
