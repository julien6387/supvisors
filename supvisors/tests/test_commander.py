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

from supervisor.states import RUNNING_STATES, _process_states_by_code
from unittest.mock import call, Mock

from supvisors.commander import *
from supvisors.ttypes import ApplicationStates, StartingStrategies, StartingFailureStrategies

from .base import database_copy, any_process_info_by_state, process_info_by_name
from .conftest import create_any_process, create_application, create_process


# ProcessCommand part
def test_command_create(supvisors):
    """ Test the values set at construction of ProcessCommand. """
    process = create_any_process(supvisors)
    # test default strategy
    command = ProcessCommand(process)
    assert process is command.process
    assert command.identifiers == []
    assert command.request_time == 0


def test_command_str():
    """ Test the output string of the ProcessCommand. """
    process = Mock(namespec='proc_1', state='RUNNING')
    command = ProcessCommand(process)
    command.request_time = 4321
    assert str(command) == 'process=proc_1 state=RUNNING identifiers=[] request_time=4321'


def test_command_timed_out():
    """ Test the ProcessCommand.timed_out method. """
    command = ProcessCommand(Mock())
    with pytest.raises(NotImplementedError):
        command.timed_out(102)


# ProcessStartCommand part
def test_start_command_create(supvisors):
    """ Test the values set at construction of ProcessStartCommand. """
    process = create_any_process(supvisors)
    # test strategy in parameter
    command = ProcessStartCommand(process, StartingStrategies.MOST_LOADED)
    assert process is command.process
    assert command.identifiers == []
    assert command.request_time == 0
    assert command.strategy == StartingStrategies.MOST_LOADED
    assert not command.ignore_wait_exit
    assert command.extra_args == ''


def test_start_command_str():
    """ Test the output string of the ProcessCommand. """
    process = Mock(namespec='proc_1', state='RUNNING')
    command = ProcessStartCommand(process, StartingStrategies.CONFIG)
    command.request_time = 4321
    command.ignore_wait_exit = True
    command.extra_args = '-s test args'
    assert str(command) == ('process=proc_1 state=RUNNING identifiers=[] request_time=4321'
                            ' strategy=CONFIG ignore_wait_exit=True extra_args="-s test args"')


def test_start_command_timed_out():
    """ Test the ProcessStartCommand.timed_out method. """
    process = Mock(info_map={'10.0.0.1': {'state': None, 'startsecs': 2}})
    command = ProcessStartCommand(process, StartingStrategies.CONFIG)
    command.request_time = 100
    # check call when no nodes_names
    assert not command.timed_out(1000)
    # check call with nodes_names set and process state BACKOFF or STARTING on the node
    command.identifiers = ['10.0.0.1']
    for state in [ProcessStates.BACKOFF, ProcessStates.STARTING]:
        process.info_map['10.0.0.1']['state'] = state
        assert not command.timed_out(107)
        assert command.timed_out(108)
    # check call with nodes_names set and process state RUNNING on the node
    process.info_map['10.0.0.1']['state'] = ProcessStates.RUNNING
    assert not command.timed_out(1000)
    # check call with nodes_names set and process state in STOPPED_STATES or STOPPING on the node
    for state in [ProcessStates.STOPPING] + list(STOPPED_STATES):
        process.info_map['10.0.0.1']['state'] = state
        assert not command.timed_out(105)
        assert command.timed_out(106)


# ProcessStopCommand part
def test_stop_command_create(supvisors):
    """ Test the values set at construction of ProcessStopCommand. """
    process = create_any_process(supvisors)
    # test default strategy
    command = ProcessStopCommand(process)
    assert process is command.process
    assert command.identifiers == []
    assert command.request_time == 0


def test_stop_command_str():
    """ Test the output string of the ProcessCommand. """
    process = Mock(namespec='proc_1', state='RUNNING')
    command = ProcessCommand(process)
    command.request_time = 4321
    assert str(command) == 'process=proc_1 state=RUNNING identifiers=[] request_time=4321'


def test_stop_command_timed_out():
    """ Test the ProcessStopCommand.timed_out method. """
    process = Mock(info_map={'10.0.0.1': {'state': None, 'stopwaitsecs': 10},
                             '10.0.0.2': {'state': None, 'stopwaitsecs': 20}})
    command = ProcessStopCommand(process)
    command.request_time = 100
    # check call when no nodes_names
    assert not command.timed_out(1000)
    # check call with nodes_names set and process state STOPPING on the node
    command.identifiers = ['10.0.0.1', '10.0.0.2']
    process.info_map['10.0.0.1']['state'] = ProcessStates.STOPPING
    process.info_map['10.0.0.2']['state'] = ProcessStates.STOPPING
    assert not command.timed_out(115)
    assert command.timed_out(116)
    # check call with nodes_names set and process state in any other state on the node
    for state in _process_states_by_code.keys():
        if state != ProcessStates.STOPPING:
            process.info_map['10.0.0.2']['state'] = state
            assert not command.timed_out(105)
            assert command.timed_out(106)


# ApplicationJobs part
def create_process_command(info, supvisors):
    """ Create a ProcessCommand from process info. """
    return ProcessCommand(create_process(info, supvisors))


@pytest.fixture
def sample_test_1(supvisors) -> ApplicationJobs.CommandList:
    """ Create a command list with the processes of sample_test_1 of the database. """
    cmd_list = []
    for process_name in ['xclock', 'xlogo', 'xfontsel']:
        info = process_info_by_name(process_name)
        command = create_process_command(info, supvisors)
        command.process.add_info('10.0.0.1', info)
        cmd_list.append(command)
    return cmd_list


@pytest.fixture
def sample_test_2(supvisors) -> ApplicationJobs.CommandList:
    """ Create a command list with the processes of sample_test_2 of the database. """
    cmd_list = []
    for process_name in ['sleep', 'yeux_00', 'yeux_01']:
        info = process_info_by_name(process_name)
        command = create_process_command(info, supvisors)
        command.process.add_info('10.0.0.2', info)
        cmd_list.append(command)
    return cmd_list


@pytest.fixture
def application_job_1(supvisors, sample_test_1):
    """ Create an ApplicationJob with the CommandList sample_test_1. """
    application = create_application('sample_test_1', supvisors)
    supvisors.context.applications['sample_test_1'] = application
    jobs = {0: sample_test_1[0:2], 1: sample_test_1[2:]}
    return ApplicationJobs(application, jobs, supvisors)


@pytest.fixture
def application_job_2(supvisors, sample_test_2):
    """ Create an ApplicationJob with the CommandList sample_test_2. """
    application = create_application('sample_test_2', supvisors)
    supvisors.context.applications['sample_test_2'] = application
    jobs = {0: sample_test_2[0:1], 1: sample_test_2[1:]}
    return ApplicationJobs(application, jobs, supvisors)


def test_application_job_creation(supvisors, application_job_1, sample_test_1):
    """ Test the values set at construction of ApplicationJobs. """
    assert application_job_1.supvisors is supvisors
    assert application_job_1.logger is supvisors.logger
    assert application_job_1.application is supvisors.context.applications['sample_test_1']
    assert application_job_1.application_name == 'sample_test_1'
    assert application_job_1.planned_jobs == {0: sample_test_1[0:2], 1: sample_test_1[2:]}
    assert application_job_1.current_jobs == []
    assert application_job_1.pickup_logic is None
    assert application_job_1.failure_state == ProcessStates.UNKNOWN


def test_application_job_print(application_job_1):
    """ Test the ProcessCommand __repr__ through the ApplicationJobs print. """
    assert f'{application_job_1.planned_jobs}' == ('{0: [sample_test_1:xclock, sample_test_1:xlogo],'
                                                   ' 1: [sample_test_1:xfontsel]}')
    assert f'{application_job_1.current_jobs}' == '[]'
    application_job_1.current_jobs = application_job_1.planned_jobs.pop(0)
    assert f'{application_job_1.planned_jobs}' == '{1: [sample_test_1:xfontsel]}'
    assert f'{application_job_1.current_jobs}' == '[sample_test_1:xclock, sample_test_1:xlogo]'


def test_application_job_get_command(sample_test_1):
    """ Test the ApplicationJobs.get_command method. """
    # initial ProcessCommands have no identifiers set
    # test with non existing process
    assert not ApplicationJobs.get_command(sample_test_1, 'xeyes')
    assert not ApplicationJobs.get_command(sample_test_1, 'xeyes', '10.0.0.1')
    # test with existing process
    assert ApplicationJobs.get_command(sample_test_1, 'xlogo') is sample_test_1[1]
    assert not ApplicationJobs.get_command(sample_test_1, 'xlogo', '10.0.0.1')
    # set identifiers
    for command in sample_test_1:
        command.identifiers.append('10.0.0.1')
    # test with non existing process
    assert not ApplicationJobs.get_command(sample_test_1, 'xeyes')
    assert not ApplicationJobs.get_command(sample_test_1, 'xeyes', '10.0.0.1')
    # test with existing process
    assert ApplicationJobs.get_command(sample_test_1, 'xlogo') is sample_test_1[1]
    # test with existing process and wrong identifier
    assert not ApplicationJobs.get_command(sample_test_1, 'xlogo', '10.0.0.2')
    # test with existing process and correct identifier
    assert ApplicationJobs.get_command(sample_test_1, 'xlogo', '10.0.0.1') is sample_test_1[1]


def test_application_job_get_current_command(application_job_1, sample_test_1):
    """ Test the ApplicationJobs.get_current_command method. """
    # initial current_jobs is empty
    assert not application_job_1.get_current_command('xlogo')
    assert not application_job_1.get_current_command('xlogo', '10.0.0.1')
    # fill current_jobs and retry. identifiers still not set
    application_job_1.current_jobs = application_job_1.planned_jobs.pop(0)
    assert application_job_1.get_current_command('xlogo') is sample_test_1[1]
    assert not application_job_1.get_current_command('xlogo', '10.0.0.1')
    # set identifiers
    for command in sample_test_1:
        command.identifiers.append('10.0.0.1')
    # retry
    assert application_job_1.get_current_command('xlogo') is sample_test_1[1]
    assert not application_job_1.get_current_command('xlogo', '10.0.0.2')
    assert application_job_1.get_current_command('xlogo', '10.0.0.1') is sample_test_1[1]


def test_application_job_get_planned_command(application_job_1, sample_test_1):
    """ Test the ApplicationJobs.get_planned_command method. """
    # identifiers are initially not set
    assert application_job_1.get_planned_command('xlogo') is sample_test_1[1]
    assert not application_job_1.get_planned_command('xlogo', '10.0.0.1')
    # set identifiers
    for command in sample_test_1:
        command.identifiers.append('10.0.0.1')
    # retry
    assert application_job_1.get_planned_command('xlogo') is sample_test_1[1]
    assert not application_job_1.get_planned_command('xlogo', '10.0.0.2')
    assert application_job_1.get_planned_command('xlogo', '10.0.0.1') is sample_test_1[1]


def test_application_job_add_command(application_job_1, sample_test_1):
    """ Test the ApplicationJobs.add_command method. """
    # add job corresponding to existing job in planned_jobs
    job = {5: sample_test_1[1:2]}
    application_job_1.add_command(job)
    assert 5 not in application_job_1.planned_jobs
    assert not application_job_1.current_jobs
    # remove this job from planned_jobs
    application_job_1.planned_jobs.pop(0)
    # add job corresponding to non-existing job in planned_jobs
    application_job_1.add_command(job)
    assert application_job_1.planned_jobs == {1: sample_test_1[2:], 5: sample_test_1[1:2]}
    assert not application_job_1.current_jobs
    # insert a job to current_jobs
    application_job_1.current_jobs = sample_test_1[0:1]
    # add job corresponding to existing job in current_jobs
    job = {8: sample_test_1[0:1]}
    application_job_1.add_command(job)
    assert 8 not in application_job_1.planned_jobs
    assert application_job_1.current_jobs == sample_test_1[0:1]


def test_application_job_in_progress(application_job_1):
    """ Test the ApplicationJobs.in_progress method. """
    # planned_jobs is filled, current_jobs is not
    assert application_job_1.in_progress()
    # both are filled
    application_job_1.current_jobs = application_job_1.planned_jobs.pop(0)
    assert application_job_1.in_progress()
    # current_jobs is filled, planned_jobs is not
    application_job_1.planned_jobs.pop(1)
    assert application_job_1.in_progress()
    # both are empty
    application_job_1.current_jobs = []
    assert not application_job_1.in_progress()


def test_application_job_before_after(application_job_1):
    """ Test the ApplicationJobs empty and not implemented methods. """
    # nothing to test. empty implementations
    application_job_1.before()
    application_job_1.process_failure(Mock())
    application_job_1.get_load_requests()
    # not implemented
    with pytest.raises(NotImplementedError):
        application_job_1.process_job('anything')
    with pytest.raises(NotImplementedError):
        application_job_1.on_event_in_sequence(Mock(), '', {})


def test_application_job_next(mocker, application_job_1, sample_test_1):
    mocker_process = mocker.patch.object(application_job_1, 'process_job', side_effect=[True, False])
    """ Test the ApplicationJobs.next method. """
    # pickup_logic must be set
    application_job_1.pickup_logic = min
    # initial context will trigger the job for the first call
    application_job_1.next()
    assert mocker_process.call_args_list == [call(sample_test_1[0]), call(sample_test_1[1])]
    assert application_job_1.planned_jobs == {1: sample_test_1[2:]}
    assert application_job_1.current_jobs == sample_test_1[0:1]
    # xlogo has been dismissed by process_job
    mocker_process.reset_mock()
    # second call won't do anything as current_jobs is not empty
    application_job_1.next()
    assert not mocker_process.called
    assert application_job_1.planned_jobs == {1: sample_test_1[2:]}
    assert application_job_1.current_jobs == sample_test_1[0:1]
    # empty everything
    application_job_1.planned_jobs = {}
    application_job_1.current_jobs = []
    application_job_1.next()
    assert not mocker_process.called
    assert application_job_1.planned_jobs == {}
    assert application_job_1.current_jobs == []


def test_application_job_check(mocker, application_job_1, sample_test_1):
    """ Test the ApplicationJobs.check method. """
    mocker.patch('supvisors.commander.time.time', return_value=1000)
    mocked_force = mocker.patch.object(application_job_1.supvisors.listener, 'force_process_state')
    mocked_next = mocker.patch.object(application_job_1, 'next')
    mocked_timeout = mocker.patch('supvisors.commander.ProcessCommand.timed_out', return_value=False)
    # no current_jobs initially
    application_job_1.check()
    assert not mocked_timeout.called
    assert not mocked_force.called
    assert mocked_next.called
    mocker.resetall()
    # add commands to current_lobs
    application_job_1.current_jobs = application_job_1.planned_jobs.pop(0)
    # no timeout error
    application_job_1.check()
    assert application_job_1.current_jobs == sample_test_1[0:2]
    assert mocked_timeout.call_args_list == [call(1000), call(1000)]
    assert not mocked_force.called
    assert mocked_next.called
    mocker.resetall()
    # trigger timeout on first element of current_jobs
    mocked_timeout.side_effect = [True, False]
    application_job_1.check()
    assert application_job_1.current_jobs == sample_test_1[1:2]
    assert mocked_timeout.call_args_list == [call(1000), call(1000)]
    assert mocked_force.call_args_list == [call('sample_test_1:xclock', ProcessStates.UNKNOWN,
                                                'no process event received in time')]
    assert mocked_next.called


def test_application_job_on_event(mocker, application_job_1, sample_test_1):
    """ Test the ApplicationJobs.on_event method. """
    mocked_event = mocker.patch.object(application_job_1, 'on_event_in_sequence')
    # test with non-corresponding process
    process = Mock(process_name='dummy')
    application_job_1.on_event(process, '10.0.0.1', {'any': 'event'})
    assert not mocked_event.called
    # test with process in planned_jobs (identifiers not set)
    application_job_1.on_event(sample_test_1[0].process, '10.0.0.1', {'any': 'event'})
    assert not mocked_event.called
    # test with process in planned_jobs (identifiers set)
    sample_test_1[0].identifiers = ['10.0.0.1']
    application_job_1.on_event(sample_test_1[0].process, '10.0.0.1', {'any': 'event'})
    assert not mocked_event.called
    # test with process in current_jobs (identifiers set)
    application_job_1.current_jobs = application_job_1.planned_jobs.pop(0)
    application_job_1.on_event(sample_test_1[0].process, '10.0.0.1', {'any': 'event'})
    assert mocked_event.call_args_list == [call(sample_test_1[0], '10.0.0.1', {'any': 'event'})]
    mocked_event.reset_mock()
    # test with process in current_jobs (identifiers not set)
    sample_test_1[0].identifiers = []
    application_job_1.on_event(sample_test_1[0].process, '10.0.0.1', {'any': 'event'})
    assert not mocked_event.called


def test_application_job_on_nodes_invalidation(mocker, application_job_1, sample_test_1):
    """ Test the ApplicationJobs.on_instances_invalidation method. """
    mocked_failure = mocker.patch.object(application_job_1, 'process_failure')
    mocked_next = mocker.patch.object(application_job_1, 'next')
    # initially, current_jobs is empty and xlogo command is in planned_jobs
    xlogo = sample_test_1[1]
    failed_processes = {xlogo.process}
    application_job_1.on_instances_invalidation(['10.0.0.1'], failed_processes)
    assert not mocked_failure.called
    assert not mocked_next.called
    assert failed_processes == set()
    assert application_job_1.planned_jobs == {0: sample_test_1[0:2], 1: sample_test_1[2:]}
    assert application_job_1.current_jobs == []
    # fill current_jobs and retry. identifiers is set with other node
    application_job_1.current_jobs = application_job_1.planned_jobs.pop(0)
    sample_test_1[0].identifiers = ['10.0.0.3']
    xlogo.identifiers = ['10.0.0.3']
    failed_processes = {xlogo.process}
    application_job_1.on_instances_invalidation(['10.0.0.1'], failed_processes)
    assert not mocked_failure.called
    assert not mocked_next.called
    assert failed_processes == {xlogo.process}
    assert application_job_1.planned_jobs == {1: sample_test_1[2:]}
    assert application_job_1.current_jobs == sample_test_1[0:2]
    # set xlogo identifiers with 2 instances_map
    xlogo.identifiers = ['10.0.0.1', '10.0.0.2']
    application_job_1.on_instances_invalidation(['10.0.0.1'], failed_processes)
    assert not mocked_failure.called
    assert not mocked_next.called
    assert failed_processes == {sample_test_1[1].process}
    assert application_job_1.planned_jobs == {1: sample_test_1[2:]}
    assert application_job_1.current_jobs == sample_test_1[0:2]
    assert sample_test_1[1].identifiers == ['10.0.0.2']
    # invalidate the other node
    application_job_1.on_instances_invalidation(['10.0.0.2'], failed_processes)
    assert mocked_failure.call_args_list == [call(sample_test_1[1].process)]
    assert not mocked_next.called
    assert failed_processes == set()
    assert application_job_1.planned_jobs == {1: sample_test_1[2:]}
    assert application_job_1.current_jobs == sample_test_1[0:1]
    assert xlogo.identifiers == []


# ApplicationStartJobs part
def create_process_start_command(info, supvisors):
    """ Create a ProcessStartCommand from process info. """
    return ProcessStartCommand(create_process(info, supvisors), StartingStrategies.LESS_LOADED)


@pytest.fixture
def start_sample_test_1(supvisors) -> ApplicationJobs.CommandList:
    """ Create a command list with the processes of sample_test_1 of the database. """
    cmd_list = []
    for process_name in ['xclock', 'xlogo', 'xfontsel']:
        info = process_info_by_name(process_name)
        command = create_process_start_command(info, supvisors)
        command.process.add_info('10.0.0.1', info)
        cmd_list.append(command)
    return cmd_list


@pytest.fixture
def application_start_job_1(supvisors, start_sample_test_1):
    """ Create an ApplicationStartJob with the CommandList sample_test_1. """
    application = create_application('dummy_application', supvisors)
    supvisors.context.applications['dummy_application'] = application
    jobs = {0: start_sample_test_1[0:2], 1: start_sample_test_1[2:]}
    return ApplicationStartJobs(application, jobs, StartingStrategies.LESS_LOADED, supvisors)


def test_application_start_job_creation(supvisors, application_start_job_1, start_sample_test_1):
    """ Test the values set at construction of ApplicationStartJobs. """
    assert application_start_job_1.supvisors is supvisors
    assert application_start_job_1.logger is supvisors.logger
    assert application_start_job_1.application is supvisors.context.applications['dummy_application']
    assert application_start_job_1.application_name == 'dummy_application'
    assert application_start_job_1.planned_jobs == {0: start_sample_test_1[0:2], 1: start_sample_test_1[2:]}
    assert application_start_job_1.current_jobs == []
    assert application_start_job_1.pickup_logic is min
    assert application_start_job_1.failure_state == ProcessStates.FATAL
    assert application_start_job_1.starting_strategy == StartingStrategies.LESS_LOADED
    assert application_start_job_1.distributed
    assert application_start_job_1.identifier is None
    assert not application_start_job_1.stop_request


def test_application_start_job_add_command(mocker, supvisors, application_start_job_1, start_sample_test_1):
    """ Test the ApplicationStartJobs.add_command method. """
    mocked_node = mocker.patch('supvisors.commander.get_supvisors_instance')
    xclock = start_sample_test_1[0]
    xclock.process.rules.expected_load = 7
    job = {8: start_sample_test_1[0:1]}
    # test with application distributed, application identifier unset and command identifiers unset
    application_start_job_1.add_command(job)
    assert xclock.identifiers == []
    assert not mocked_node.called
    # set application non-distributed and retry
    application_start_job_1.distributed = False
    # this case corresponds to a non-distributed application for which no node has been found
    application_start_job_1.add_command(job)
    assert xclock.identifiers == []
    assert not mocked_node.called
    # set application identifier and retry
    application_start_job_1.identifier = '10.0.0.1'
    # this case corresponds to a non-distributed application for which a node has been found and the job has been added
    # in superclass (otherwise command identifiers would be set)
    # first, consider that there's no resource available anymore
    mocked_node.return_value = None
    application_start_job_1.add_command(job)
    assert xclock.identifiers == []
    assert mocked_node.call_args_list == [call(supvisors, StartingStrategies.LESS_LOADED, ['10.0.0.1'], 7)]
    mocked_node.reset_mock()
    # then, consider that the node can accept the additional loading
    mocked_node.return_value = '10.0.0.1'
    application_start_job_1.add_command(job)
    assert xclock.identifiers == ['10.0.0.1']
    assert mocked_node.call_args_list == [call(supvisors, StartingStrategies.LESS_LOADED, ['10.0.0.1'], 7)]
    mocked_node.reset_mock()
    # retry
    # this case corresponds to a non-distributed application for which a node has been found and the job has NOT been
    # added in superclass (because command identifiers is already set)
    application_start_job_1.add_command(job)
    assert xclock.identifiers == ['10.0.0.1']
    assert not mocked_node.called


def test_application_start_job_get_load_requests(application_start_job_1, start_sample_test_1):
    """ Test the ApplicationStartJobs.get_load_requests method. """
    # test with empty current_jobs
    assert application_start_job_1.get_load_requests() == {}
    # set context
    application_start_job_1.current_jobs = application_start_job_1.planned_jobs.pop(0)
    for idx, command in enumerate(start_sample_test_1):
        command.instances_map = [f'10.0.0.{idx % 2 + 1}']
        command.process.rules.expected_load = 10
    # initially: xclock STOPPING, xlogo STOPPED, xfontsel RUNNING
    assert application_start_job_1.get_load_requests() == {'10.0.0.2': 10}
    # set all processes to STOPPED and unset xfontsel identifiers
    for command in start_sample_test_1:
        command.process._state = ProcessStates.STOPPED
    start_sample_test_1[2].identifiers = []
    assert application_start_job_1.get_load_requests() == {'10.0.0.1': 10, '10.0.0.2': 10}


def test_application_start_job_before(mocker, supvisors, application_start_job_1, start_sample_test_1):
    """ Test the ApplicationStartJobs.before method. """
    mocked_node_getter = mocker.patch('supvisors.commander.get_supvisors_instance', return_value='10.0.0.1')
    mocked_app_nodes = mocker.patch.object(application_start_job_1.application,
                                           'possible_identifiers', return_value=['10.0.0.1', '10.0.0.2'])
    mocked_app_load = mocker.patch.object(application_start_job_1.application,
                                          'get_start_sequence_expected_load', return_value=27)
    # test with application distributed
    application_start_job_1.before()
    assert not application_start_job_1.identifier
    assert not mocked_node_getter.called
    assert not mocked_app_nodes.called
    assert not mocked_app_load.called
    # commands unchanged
    assert all(not command.instances_map
               for sequence in application_start_job_1.planned_jobs.values()
               for command in sequence)
    # test application provided / application not distributed
    application_start_job_1.distributed = False
    application_start_job_1.before()
    assert application_start_job_1.identifier == '10.0.0.1'
    assert mocked_node_getter.call_args_list == [call(supvisors, StartingStrategies.LESS_LOADED,
                                                      ['10.0.0.1', '10.0.0.2'], 27)]
    # check commands
    assert all(command.instances_map == ['10.0.0.1']
               for sequence in application_start_job_1.planned_jobs.values()
               for command in sequence)


def test_application_start_job_process_job(mocker, supvisors, application_start_job_1, start_sample_test_1):
    """ Test the ApplicationStartJobs.process_job method. """
    # get patches
    mocked_node_getter = mocker.patch('supvisors.commander.get_supvisors_instance')
    mocked_force = supvisors.listener.force_process_state
    mocked_pusher = supvisors.zmq.pusher.send_start_process
    mocked_failure = mocker.patch.object(application_start_job_1, 'process_failure')
    # test with a possible starting address
    mocked_node_getter.return_value = '10.0.0.1'
    # 1. xfontsel is running
    command = start_sample_test_1[2]
    assert not application_start_job_1.process_job(command)
    assert not mocked_node_getter.called
    assert not mocked_pusher.called
    assert not mocked_force.called
    assert not mocked_failure.called
    # 2. xlogo is stopped / application is not distributed
    command = start_sample_test_1[1]
    command.strategy = StartingStrategies.MOST_LOADED
    application_start_job_1.distributed = False
    # 2.a no node has been found earlier
    command.identifiers = []
    assert not application_start_job_1.process_job(command)
    assert not mocked_node_getter.called
    assert not mocked_pusher.called
    assert mocked_force.call_args_list == [call('sample_test_1:xlogo', ProcessStates.FATAL, 'no resource available')]
    assert mocked_failure.call_args_list == [call(command.process)]
    mocked_force.reset_mock()
    mocked_failure.reset_mock()
    # 2.b node has been found earlier
    command.identifiers = ['10.0.0.1']
    assert application_start_job_1.process_job(command)
    assert not mocked_node_getter.called
    assert mocked_pusher.call_args_list == [call('10.0.0.1', 'sample_test_1:xlogo', '')]
    assert not mocked_force.called
    assert not mocked_failure.called
    mocked_pusher.reset_mock()
    # 3. xlogo is stopped / application is distributed
    application_start_job_1.distributed = True
    command.identifiers = []
    # 3.a test with node found by get_supvisors_instance
    assert application_start_job_1.process_job(command)
    assert command.identifiers == ['10.0.0.1']
    assert mocked_node_getter.call_args_list == [call(supvisors, StartingStrategies.MOST_LOADED, ['10.0.0.1'], 0)]
    assert mocked_pusher.call_args_list == [call('10.0.0.1', 'sample_test_1:xlogo', '')]
    assert not mocked_force.called
    assert not mocked_failure.called
    mocked_node_getter.reset_mock()
    mocked_pusher.reset_mock()
    # 3.b test with no node found by get_supvisors_instance
    mocked_node_getter.return_value = None
    command.identifiers = []
    # call the process_jobs
    assert not application_start_job_1.process_job(command)
    assert command.identifiers == []
    assert mocked_node_getter.call_args_list == [call(supvisors, StartingStrategies.MOST_LOADED, ['10.0.0.1'], 0)]
    assert not mocked_pusher.called
    assert mocked_force.call_args_list == [call('sample_test_1:xlogo', ProcessStates.FATAL, 'no resource available')]
    assert mocked_failure.call_args_list == [call(command.process)]


def test_application_start_job_process_failure_optional(application_start_job_1, start_sample_test_1):
    """ Test the ApplicationStartJobs.process_failure method with an optional process. """
    # check initial state
    xclock = start_sample_test_1[0]
    xclock.process.rules.required = False
    assert application_start_job_1.planned_jobs == {0: start_sample_test_1[0:2], 1: start_sample_test_1[2:]}
    assert not application_start_job_1.stop_request
    # test with a process not required
    application_start_job_1.process_failure(xclock.process)
    # test attributes are is unchanged
    assert application_start_job_1.planned_jobs == {0: start_sample_test_1[0:2], 1: start_sample_test_1[2:]}
    assert not application_start_job_1.stop_request


def test_application_start_job_process_failure_required_abort(application_start_job_1, start_sample_test_1):
    """ Test the ApplicationStartJobs.process_failure method with a required process and ABORT failure strategy. """
    # check initial state
    xclock = start_sample_test_1[0]
    xclock.process.rules.required = True
    assert application_start_job_1.planned_jobs == {0: start_sample_test_1[0:2], 1: start_sample_test_1[2:]}
    assert not application_start_job_1.stop_request
    # test ABORT starting strategy
    application_start_job_1.application.rules.starting_failure_strategy = StartingFailureStrategies.ABORT
    application_start_job_1.process_failure(xclock.process)
    assert application_start_job_1.planned_jobs == {}
    assert not application_start_job_1.stop_request


def test_application_start_job_process_failure_required_continue(application_start_job_1, start_sample_test_1):
    """ Test the ApplicationStartJobs.process_failure method with a required process and CONTINUE failure strategy. """
    # check initial state
    xclock = start_sample_test_1[0]
    xclock.process.rules.required = True
    assert application_start_job_1.planned_jobs == {0: start_sample_test_1[0:2], 1: start_sample_test_1[2:]}
    assert not application_start_job_1.stop_request
    # test CONTINUE starting strategy
    application_start_job_1.application.rules.starting_failure_strategy = StartingFailureStrategies.CONTINUE
    application_start_job_1.process_failure(xclock.process)
    assert application_start_job_1.planned_jobs == {0: start_sample_test_1[0:2], 1: start_sample_test_1[2:]}
    assert not application_start_job_1.stop_request


def test_application_start_job_process_failure_required_stop(application_start_job_1, start_sample_test_1):
    """ Test the ApplicationStartJobs.process_failure method with a required process and STOP failure strategy. """
    # check initial state
    xclock = start_sample_test_1[0]
    xclock.process.rules.required = True
    assert application_start_job_1.planned_jobs == {0: start_sample_test_1[0:2], 1: start_sample_test_1[2:]}
    assert not application_start_job_1.stop_request
    # test STOP starting strategy
    application_start_job_1.application.rules.starting_failure_strategy = StartingFailureStrategies.STOP
    application_start_job_1.process_failure(xclock.process)
    assert application_start_job_1.planned_jobs == {}
    assert application_start_job_1.stop_request


def test_application_start_job_on_event_in_sequence_stopped(mocker, application_start_job_1, start_sample_test_1):
    """ Test the ApplicationStartJobs.on_event_in_sequence method with a STOPPED event. """
    mocked_time = mocker.patch('supvisors.commander.time.time', return_value=1000)
    mocked_next = mocker.patch.object(application_start_job_1, 'next')
    mocked_failure = mocker.patch.object(application_start_job_1, 'process_failure')
    # call method for STOPPED, STOPPING and UNKNOWN states
    xclock = start_sample_test_1[0]
    xclock.request_time = 100
    for state in [ProcessStates.STOPPED, ProcessStates.STOPPING, ProcessStates.UNKNOWN]:
        application_start_job_1.current_jobs = start_sample_test_1.copy()
        event = {'state': state, 'expected': True}
        application_start_job_1.on_event_in_sequence(xclock, '10.0.0.1', event)
        assert application_start_job_1.current_jobs == start_sample_test_1[1:]
        assert xclock.request_time == 100
        assert mocked_failure.call_args_list == [call(xclock.process)]
        assert not mocked_time.called
        assert mocked_next.called
        mocked_failure.reset_mock()


def test_application_start_job_on_event_in_sequence_starting(mocker, application_start_job_1, start_sample_test_1):
    """ Test the ApplicationStartJobs.on_event_in_sequence method with a STARTING event. """
    mocked_time = mocker.patch('supvisors.commander.time.time', return_value=1000)
    mocked_next = mocker.patch.object(application_start_job_1, 'next')
    mocked_failure = mocker.patch.object(application_start_job_1, 'process_failure')
    # call method for STARTING states
    xclock = start_sample_test_1[0]
    xclock.request_time = 100
    application_start_job_1.current_jobs = start_sample_test_1.copy()
    event = {'state': ProcessStates.STARTING, 'expected': True}
    application_start_job_1.on_event_in_sequence(xclock, '10.0.0.1', event)
    assert application_start_job_1.current_jobs == start_sample_test_1
    assert xclock.request_time == 100
    assert not mocked_failure.called
    assert not mocked_time.called
    assert mocked_next.called


def test_application_start_job_on_event_in_sequence_running(mocker, application_start_job_1, start_sample_test_1):
    """ Test the ApplicationStartJobs.on_event_in_sequence method with a RUNNING event. """
    mocked_time = mocker.patch('supvisors.commander.time.time', return_value=1000)
    mocked_next = mocker.patch.object(application_start_job_1, 'next')
    mocked_failure = mocker.patch.object(application_start_job_1, 'process_failure')
    # call method for RUNNING states
    xclock = start_sample_test_1[0]
    xclock.request_time = 100
    event = {'state': ProcessStates.RUNNING, 'expected': True}
    # job is done when wait_exit is not configured
    xclock.process.rules.wait_exit = False
    for ignore_wait_exit in [True, False]:
        xclock.ignore_wait_exit = ignore_wait_exit
        application_start_job_1.current_jobs = start_sample_test_1.copy()
        application_start_job_1.on_event_in_sequence(xclock, '10.0.0.1', event)
        assert application_start_job_1.current_jobs == start_sample_test_1[1:]
        assert xclock.request_time == 100
        assert not mocked_failure.called
        assert not mocked_time.called
        assert mocked_next.called
        mocked_next.reset_mock()
    # job is done when wait_exit is configured but has to be ignored
    xclock.process.rules.wait_exit = True
    xclock.ignore_wait_exit = True
    application_start_job_1.current_jobs = start_sample_test_1.copy()
    application_start_job_1.on_event_in_sequence(xclock, '10.0.0.1', event)
    assert application_start_job_1.current_jobs == start_sample_test_1[1:]
    assert xclock.request_time == 100
    assert not mocked_failure.called
    assert not mocked_time.called
    assert mocked_next.called
    mocked_next.reset_mock()
    # job is pending when wait_exit is configured and has to be configured
    xclock.ignore_wait_exit = False
    application_start_job_1.current_jobs = start_sample_test_1.copy()
    application_start_job_1.on_event_in_sequence(xclock, '10.0.0.1', event)
    assert application_start_job_1.current_jobs == start_sample_test_1
    assert xclock.request_time == 100
    assert not mocked_failure.called
    assert not mocked_time.called
    assert mocked_next.called


def test_application_start_job_on_event_in_sequence_backoff(mocker, application_start_job_1, start_sample_test_1):
    """ Test the ApplicationStartJobs.on_event_in_sequence method with a BACKOFF event. """
    mocked_time = mocker.patch('supvisors.commander.time.time', return_value=1000)
    mocked_next = mocker.patch.object(application_start_job_1, 'next')
    mocked_failure = mocker.patch.object(application_start_job_1, 'process_failure')
    # call method for BACKOFF states
    xclock = start_sample_test_1[0]
    xclock.request_time = 100
    application_start_job_1.current_jobs = start_sample_test_1.copy()
    event = {'state': ProcessStates.BACKOFF, 'expected': True}
    application_start_job_1.on_event_in_sequence(xclock, '10.0.0.1', event)
    assert application_start_job_1.current_jobs == start_sample_test_1
    assert xclock.request_time == 1000
    assert not mocked_failure.called
    assert mocked_time.called
    assert mocked_next.called


def test_application_start_job_on_event_in_sequence_exited(mocker, application_start_job_1, start_sample_test_1):
    """ Test the ApplicationStartJobs.on_event_in_sequence method with an EXITED event. """
    mocked_time = mocker.patch('supvisors.commander.time.time', return_value=1000)
    mocked_next = mocker.patch.object(application_start_job_1, 'next')
    mocked_failure = mocker.patch.object(application_start_job_1, 'process_failure')
    # call method for EXITED states
    xclock = start_sample_test_1[0]
    xclock.request_time = 100
    event = {'state': ProcessStates.EXITED, 'expected': True}
    # job is done when wait_exit is configured and event states an expected exit
    xclock.process.rules.wait_exit = True
    application_start_job_1.current_jobs = start_sample_test_1.copy()
    application_start_job_1.on_event_in_sequence(xclock, '10.0.0.1', event)
    assert application_start_job_1.current_jobs == start_sample_test_1[1:]
    assert xclock.request_time == 100
    assert not mocked_failure.called
    assert not mocked_time.called
    assert mocked_next.called
    mocked_next.reset_mock()
    # job is failed when wait_exit is configured and event states an unexpected exit
    event = {'state': ProcessStates.EXITED, 'expected': False}
    application_start_job_1.current_jobs = start_sample_test_1.copy()
    application_start_job_1.on_event_in_sequence(xclock, '10.0.0.1', event)
    assert application_start_job_1.current_jobs == start_sample_test_1[1:]
    assert xclock.request_time == 100
    assert mocked_failure.call_args_list == [call(xclock.process)]
    assert not mocked_time.called
    assert mocked_next.called
    mocked_failure.reset_mock()
    mocked_next.reset_mock()
    # job is failed when wait_exit is not configured
    xclock.process.rules.wait_exit = False
    for expected in [True, False]:
        event = {'state': ProcessStates.EXITED, 'expected': expected}
        application_start_job_1.current_jobs = start_sample_test_1.copy()
        application_start_job_1.on_event_in_sequence(xclock, '10.0.0.1', event)
        assert application_start_job_1.current_jobs == start_sample_test_1[1:]
        assert xclock.request_time == 100
        assert mocked_failure.call_args_list == [call(xclock.process)]
        assert not mocked_time.called
        assert mocked_next.called
        mocked_failure.reset_mock()
        mocked_next.reset_mock()


def test_application_start_job_on_event_in_sequence_fatal(mocker, application_start_job_1, start_sample_test_1):
    """ Test the ApplicationStartJobs.on_event_in_sequence method with a FATAL event. """
    mocked_time = mocker.patch('supvisors.commander.time.time', return_value=1000)
    mocked_next = mocker.patch.object(application_start_job_1, 'next')
    mocked_failure = mocker.patch.object(application_start_job_1, 'process_failure')
    # call method for FATAL states
    xclock = start_sample_test_1[0]
    xclock.request_time = 100
    event = {'state': ProcessStates.FATAL, 'expected': False}
    # job is done when wait_exit is configured and event states an expected exit
    xclock.process.rules.wait_exit = True
    application_start_job_1.current_jobs = start_sample_test_1.copy()
    application_start_job_1.on_event_in_sequence(xclock, '10.0.0.1', event)
    assert application_start_job_1.current_jobs == start_sample_test_1[1:]
    assert xclock.request_time == 100
    assert mocked_failure.call_args_list == [call(xclock.process)]
    assert not mocked_time.called
    assert mocked_next.called


# ApplicationStopJobs part
def create_process_stop_command(info, supvisors):
    """ Create a ProcessStopCommand from process info. """
    return ProcessStopCommand(create_process(info, supvisors))


@pytest.fixture
def stop_sample_test_1(supvisors) -> ApplicationJobs.CommandList:
    """ Create a command list with the processes of sample_test_1 of the database. """
    cmd_list = []
    for process_name in ['xclock', 'xlogo', 'xfontsel']:
        info = process_info_by_name(process_name)
        command = create_process_stop_command(info, supvisors)
        command.process.add_info('10.0.0.1', info)
        cmd_list.append(command)
    return cmd_list


@pytest.fixture
def application_stop_job_1(supvisors, stop_sample_test_1):
    """ Create an ApplicationStopJob with the CommandList sample_test_1. """
    application = create_application('dummy_application', supvisors)
    supvisors.context.applications['dummy_application'] = application
    jobs = {0: stop_sample_test_1[0:2], 1: stop_sample_test_1[2:]}
    return ApplicationStopJobs(application, jobs, supvisors)


def test_application_stop_job_creation(supvisors, application_stop_job_1, stop_sample_test_1):
    """ Test the values set at construction of ApplicationStopJobs. """
    assert application_stop_job_1.supvisors is supvisors
    assert application_stop_job_1.logger is supvisors.logger
    assert application_stop_job_1.application is supvisors.context.applications['dummy_application']
    assert application_stop_job_1.application_name == 'dummy_application'
    assert application_stop_job_1.planned_jobs == {0: stop_sample_test_1[0:2], 1: stop_sample_test_1[2:]}
    assert application_stop_job_1.current_jobs == []
    assert application_stop_job_1.pickup_logic is max
    assert application_stop_job_1.failure_state == ProcessStates.STOPPED


def test_application_stop_job_process_job(mocker, application_stop_job_1, stop_sample_test_1):
    """ Test the ApplicationStopJobs.process_job method. """
    # get patches
    mocked_time = mocker.patch('supvisors.commander.time.time', return_value=1000)
    mocked_pusher = application_stop_job_1.supvisors.zmq.pusher.send_stop_process
    # test with stopped process
    xlogo = stop_sample_test_1[1]
    assert not application_stop_job_1.process_job(xlogo)
    assert not mocked_pusher.called
    assert xlogo.identifiers == []
    assert xlogo.request_time == 0
    # test with running process
    xfontsel = stop_sample_test_1[2]
    xfontsel.process.running_identifiers = ['10.0.0.1', '10.0.0.2']
    assert application_stop_job_1.process_job(xfontsel)
    assert mocked_pusher.call_args_list == [call('10.0.0.1', 'sample_test_1:xfontsel'),
                                            call('10.0.0.2', 'sample_test_1:xfontsel')]
    assert xfontsel.identifiers == ['10.0.0.1', '10.0.0.2']
    assert xfontsel.request_time == 1000


def test_application_stop_job_on_event_in_sequence(mocker, application_stop_job_1, stop_sample_test_1):
    """ Test the ApplicationStopJobs.on_event_in_sequence method. """
    mocked_next = mocker.patch.object(application_stop_job_1, 'next')
    # add context
    application_stop_job_1.current_jobs = application_stop_job_1.planned_jobs.pop(1)
    xfontsel = stop_sample_test_1[2]
    xfontsel.identifiers = ['10.0.0.1', '10.0.0.2', '10.0.0.3', '10.0.0.4']
    # send unexpected running or stopping event
    for state in list(RUNNING_STATES) + [ProcessStates.STOPPING]:
        event = {'state': state}
        # from unexpected node
        application_stop_job_1.on_event_in_sequence(xfontsel, '10.0.0.5', event)
        assert xfontsel.identifiers == ['10.0.0.1', '10.0.0.2', '10.0.0.3', '10.0.0.4']
        assert not mocked_next.called
        # from expected node
        for node_name in ['10.0.0.1', '10.0.0.2', '10.0.0.3', '10.0.0.4']:
            application_stop_job_1.on_event_in_sequence(xfontsel, node_name, event)
            assert xfontsel.identifiers == ['10.0.0.1', '10.0.0.2', '10.0.0.3', '10.0.0.4']
            assert not mocked_next.called
    # send expected stopped state from expected instances_map
    for state, node_name in list(zip(STOPPED_STATES, xfontsel.identifiers)):
        event = {'state': state}
        application_stop_job_1.on_event_in_sequence(xfontsel, node_name, event)
    assert xfontsel.identifiers == []
    assert mocked_next.call_count == 1


# Commander part
@pytest.fixture
def commander(supvisors, application_job_1, application_job_2):
    """ Create the Commander instance to test. """
    return Commander(supvisors)


def test_commander_creation(supvisors, commander):
    """ Test the values set at construction of Commander. """
    assert supvisors is commander.supvisors
    assert supvisors.logger is commander.logger
    assert commander.planned_jobs == {}
    assert commander.current_jobs == {}
    assert commander.pickup_logic is None
    assert commander.klass == 'Commander'


def test_commander_print(commander, application_job_1, application_job_2):
    """ Test the ProcessCommand __repr__ through the Commander print. """
    assert f'{commander.planned_jobs}' == '{}'
    assert f'{commander.current_jobs}' == '{}'
    # add planned jobs
    commander.planned_jobs = {0: {'appli_1': application_job_1}, 1: {'appli_2': application_job_2}}
    planned_jobs = ("{0: {'appli_1': (planned_jobs={0: [sample_test_1:xclock, sample_test_1:xlogo],"
                    " 1: [sample_test_1:xfontsel]} current_jobs=[])},"
                    " 1: {'appli_2': (planned_jobs={0: [sample_test_2:sleep],"
                    " 1: [sample_test_2:yeux_00, sample_test_2:yeux_01]} current_jobs=[])}}")
    assert f'{commander.planned_jobs}' == planned_jobs
    assert f'{commander.current_jobs}' == '{}'
    # move to current jobs
    commander.current_jobs = commander.planned_jobs.pop(0)
    planned_jobs = ("{1: {'appli_2': (planned_jobs={0: [sample_test_2:sleep],"
                    " 1: [sample_test_2:yeux_00, sample_test_2:yeux_01]} current_jobs=[])}}")
    current_jobs = ("{'appli_1': (planned_jobs={0: [sample_test_1:xclock, sample_test_1:xlogo],"
                    " 1: [sample_test_1:xfontsel]} current_jobs=[])}")
    assert f'{commander.planned_jobs}' == planned_jobs
    assert f'{commander.current_jobs}' == current_jobs


def test_commander_in_progress(commander, application_job_1, application_job_2):
    """ Test the Commander.in_progress method. """
    assert commander.planned_jobs == {}
    assert commander.current_jobs == {}
    assert not commander.in_progress()
    commander.planned_jobs = {0: {'appli_1': application_job_1}, 1: {'appli_2': application_job_2}}
    assert commander.in_progress()
    commander.current_jobs = commander.planned_jobs.pop(0)
    assert commander.in_progress()
    commander.current_jobs = commander.planned_jobs.pop(1)
    assert commander.planned_jobs == {}
    assert commander.in_progress()
    commander.current_jobs = {}
    assert not commander.in_progress()


def test_commander_get_application_job_names(commander, application_job_1, application_job_2):
    """ Test the Commander.get_application_job_names method. """
    assert commander.get_application_job_names() == set()
    commander.planned_jobs = {0: {'appli_1': application_job_1}, 1: {'appli_2': application_job_2}}
    assert commander.get_application_job_names() == {'appli_1', 'appli_2'}
    commander.current_jobs = commander.planned_jobs.pop(0)
    assert commander.get_application_job_names() == {'appli_1', 'appli_2'}
    commander.current_jobs = commander.planned_jobs.pop(1)
    assert commander.get_application_job_names() == {'appli_2'}
    commander.current_jobs = {}
    assert commander.get_application_job_names() == set()


def test_commander_get_application_job(commander, application_job_1, application_job_2):
    """ Test the Commander.get_application_job method. """
    # test with empty structures
    assert commander.get_application_job('appli_1') is None
    assert commander.get_application_job('appli_2') is None
    # test with filled structures
    commander.planned_jobs = {0: {'appli_1': application_job_1}, 1: {'appli_2': application_job_2}}
    assert commander.get_application_job('appli_1') is application_job_1
    assert commander.get_application_job('appli_2') is application_job_2
    commander.current_jobs = commander.planned_jobs.pop(0)
    assert commander.get_application_job('appli_1') is application_job_1
    assert commander.get_application_job('appli_2') is application_job_2


def test_commander_abort(commander, application_job_1, application_job_2):
    """ Test the Commander.abort method. """
    # prepare some context
    commander.planned_jobs = {0: {'appli_1': application_job_1}}
    commander.current_jobs = {'appli_2': application_job_2}
    # call abort and check attributes
    commander.abort()
    assert commander.planned_jobs == {}
    assert commander.current_jobs == {}


def test_commander_next(mocker, commander, application_job_1, application_job_2):
    """ Test the Commander.next method. """
    mocked_job1_before = mocker.patch.object(application_job_1, 'before')
    mocked_job1_next = mocker.patch.object(application_job_1, 'next')
    mocked_job1_progress = mocker.patch.object(application_job_1, 'in_progress', return_value=True)
    mocked_job2_before = mocker.patch.object(application_job_2, 'before')
    mocked_job2_next = mocker.patch.object(application_job_2, 'next')
    mocked_job2_progress = mocker.patch.object(application_job_2, 'in_progress', return_value=False)
    mocked_after = mocker.patch.object(commander, 'after')
    # fill planned_jobs
    commander.pickup_logic = min
    commander.planned_jobs = {0: {'appli_1': application_job_1}, 1: {'appli_2': application_job_2}}
    # first call
    commander.next()
    assert commander.planned_jobs == {1: {'appli_2': application_job_2}}
    assert commander.current_jobs == {'appli_1': application_job_1}
    assert mocked_job1_before.called
    assert mocked_job1_next.called
    assert mocked_job1_progress.called
    assert not mocked_job2_before.called
    assert not mocked_job2_next.called
    assert not mocked_job2_progress.called
    assert not mocked_after.called
    mocker.resetall()
    # set application_job_1 not in progress anymore
    # will be removed from current_jobs and application_job_2
    # recursive call + application_job_2 not in_progress will end everything
    mocked_job1_progress.return_value = False
    commander.next()
    assert commander.planned_jobs == {}
    assert commander.current_jobs == {}
    assert not mocked_job1_before.called
    assert not mocked_job1_next.called
    assert mocked_job1_progress.called
    assert mocked_job2_before.called
    assert mocked_job2_next.called
    assert mocked_job2_progress.called
    assert mocked_after.call_args_list == [call(application_job_1), call(application_job_2)]


def test_commander_check(mocker, commander, application_job_1, application_job_2):
    """ Test the Commander.check method. """
    mocked_job1_check = mocker.patch.object(application_job_1, 'check')
    mocked_job2_check = mocker.patch.object(application_job_2, 'check')
    mocked_next = mocker.patch.object(commander, 'next')
    # test with empty structure
    commander.check()
    assert not mocked_job1_check.called
    assert not mocked_job2_check.called
    assert mocked_next.called
    mocker.resetall()
    # test with filled structure
    commander.current_jobs = {'appli_1': application_job_1, 'appli_2': application_job_2}
    commander.check()
    assert mocked_job1_check.called
    assert mocked_job2_check.called
    assert mocked_next.called


def test_commander_on_event(mocker, commander, application_job_1, sample_test_1):
    """ Test the Commander.on_event method. """
    mocked_job1_event = mocker.patch.object(application_job_1, 'on_event')
    mocked_next = mocker.patch.object(commander, 'next')
    # test with empty structure
    process = sample_test_1[0].process
    event = Mock()
    commander.on_event(process, '10.0.0.1', event)
    assert not mocked_job1_event.called
    assert not mocked_next.called
    # test with filled structure
    commander.current_jobs = {'sample_test_1': application_job_1, 'sample_test_2': application_job_2}
    commander.on_event(process, '10.0.0.1', event)
    assert mocked_job1_event.call_args_list == [call(process, '10.0.0.1', event)]
    assert mocked_next.called


def test_commander_on_nodes_invalidation(mocker, commander, application_job_1, application_job_2):
    """ Test the Commander.on_instances_invalidation method. """
    mocked_next = mocker.patch.object(commander, 'next')
    mocked_job1_node = mocker.patch.object(application_job_1, 'on_instances_invalidation')
    mocked_job2_node = mocker.patch.object(application_job_2, 'on_instances_invalidation')
    # test with empty structure
    invalidated_nodes = Mock()
    failed_processes = Mock()
    commander.on_instances_invalidation(invalidated_nodes, failed_processes)
    assert not mocked_job1_node.called
    assert not mocked_job2_node.called
    assert mocked_next.called
    mocker.resetall()
    # test with filled structure
    commander.planned_jobs = {0: {'appli_1': application_job_1}, 1: {'appli_2': application_job_2}}
    commander.on_instances_invalidation(invalidated_nodes, failed_processes)
    assert mocked_job1_node.call_args_list == [call(invalidated_nodes, failed_processes)]
    assert mocked_job2_node.call_args_list == [call(invalidated_nodes, failed_processes)]
    assert mocked_next.called
    mocker.resetall()
    # test with moved structures
    commander.current_jobs = commander.planned_jobs.pop(0)
    commander.on_instances_invalidation(invalidated_nodes, failed_processes)
    assert mocked_job1_node.call_args_list == [call(invalidated_nodes, failed_processes)]
    assert mocked_job2_node.call_args_list == [call(invalidated_nodes, failed_processes)]
    assert mocked_next.called


def test_commander_after(commander, application_job_1):
    """ Test the Commander.after method. """
    # Nothing to test. empty implementation
    commander.after(application_job_1)


# Starter part
@pytest.fixture
def starter(supvisors):
    """ Create the Starter instance to test. """
    return Starter(supvisors)


def test_starter_create(starter):
    """ Test the values set at construction of Starter. """
    assert isinstance(starter, Commander)
    assert starter.pickup_logic is min


def test_starter_store_application_separate(starter, sample_test_1, sample_test_2):
    """ Test the Starter.store_application method.
    sample_test_1 and sample_test_2 applications are in a different sequence. """
    # create 2 application
    appli1 = create_application('sample_test_1', starter.supvisors)
    appli1.rules.start_sequence = 1
    appli1.rules.starting_strategy = StartingStrategies.LESS_LOADED
    appli2 = create_application('sample_test_2', starter.supvisors)
    appli2.rules.start_sequence = 2
    appli2.rules.starting_strategy = StartingStrategies.MOST_LOADED
    # call method and check result
    starter.store_application(appli1)
    starter.store_application(appli2)
    assert starter.planned_jobs == {}
    # add a start sequence in applications
    for command in sample_test_1:
        appli1.start_sequence.setdefault(len(command.process.namespec) % 3, []).append(command.process)
    for command in sample_test_2:
        appli2.start_sequence.setdefault(len(command.process.namespec) % 3, []).append(command.process)
    # call method and check result
    starter.store_application(appli1)
    starter.store_application(appli2)
    # check the planned_jobs contents
    assert list(starter.planned_jobs.keys()) == [1, 2]
    # sequence 1 of planned jobs
    app_job_1_list = starter.planned_jobs[1]
    assert list(app_job_1_list.keys()) == ['sample_test_1']
    app_job_1_1 = app_job_1_list['sample_test_1']
    assert type(app_job_1_1) is ApplicationStartJobs
    assert app_job_1_1.application_name == 'sample_test_1'
    assert set(app_job_1_1.planned_jobs.keys()) == {1, 2}
    app_job_1_1_1 = app_job_1_1.planned_jobs[1]
    app_job_1_1_2 = app_job_1_1.planned_jobs[2]
    for command in app_job_1_1_1 + app_job_1_1_2:
        assert type(command) is ProcessStartCommand
        assert command.strategy == StartingStrategies.LESS_LOADED
    assert {command.process for command in app_job_1_1_1} == {sample_test_1[1].process, sample_test_1[2].process}
    assert {command.process for command in app_job_1_1_2} == {sample_test_1[0].process}
    assert app_job_1_1.current_jobs == []
    # sequence 2 of planned jobs
    app_job_2_list = starter.planned_jobs[2]
    assert list(app_job_2_list.keys()) == ['sample_test_2']
    app_job_2_1 = app_job_2_list['sample_test_2']
    assert type(app_job_2_1) is ApplicationStartJobs
    assert app_job_2_1.application_name == 'sample_test_2'
    assert set(app_job_2_1.planned_jobs.keys()) == {1}
    app_job_2_1_1 = app_job_2_1.planned_jobs[1]
    for command in app_job_2_1_1:
        assert type(command) is ProcessStartCommand
        assert command.strategy == StartingStrategies.MOST_LOADED
    # the trick used to define a process start_sequence sets 0 for yeux_00 and yeux_01
    assert {command.process for command in app_job_2_1_1} == {sample_test_2[0].process}
    assert app_job_2_1.current_jobs == []


def test_starter_store_application_mixed(starter, sample_test_1, sample_test_2):
    """ Test the Starter.store_application method.
    sample_test_1 and sample_test_2 applications are in the same sequence. """
    # create 2 application start_sequences
    appli1 = create_application('sample_test_1', starter.supvisors)
    appli1.rules.start_sequence = 2
    appli1.rules.starting_strategy = StartingStrategies.LESS_LOADED
    for command in sample_test_1:
        appli1.start_sequence.setdefault(len(command.process.namespec) % 3, []).append(command.process)
    appli2 = create_application('sample_test_2', starter.supvisors)
    appli2.rules.start_sequence = 2
    appli2.rules.starting_strategy = StartingStrategies.MOST_LOADED
    for command in sample_test_2:
        appli2.start_sequence.setdefault(len(command.process.namespec) % 3, []).append(command.process)
    # call method and check result
    starter.store_application(appli1)
    starter.store_application(appli2)
    # check the planned_jobs contents
    assert list(starter.planned_jobs.keys()) == [2]
    # sequence 1 of planned jobs
    app_job_1_list = starter.planned_jobs[2]
    assert list(app_job_1_list.keys()) == ['sample_test_1', 'sample_test_2']
    # focus on sample_test_1 part
    app_job_1_1 = app_job_1_list['sample_test_1']
    assert type(app_job_1_1) is ApplicationStartJobs
    assert app_job_1_1.application_name == 'sample_test_1'
    assert set(app_job_1_1.planned_jobs.keys()) == {1, 2}
    app_job_1_1_1 = app_job_1_1.planned_jobs[1]
    app_job_1_1_2 = app_job_1_1.planned_jobs[2]
    for command in app_job_1_1_1 + app_job_1_1_2:
        assert type(command) is ProcessStartCommand
        assert command.strategy == StartingStrategies.LESS_LOADED
    assert {command.process for command in app_job_1_1_1} == {sample_test_1[1].process, sample_test_1[2].process}
    assert {command.process for command in app_job_1_1_2} == {sample_test_1[0].process}
    assert app_job_1_1.current_jobs == []
    # focus on sample_test_2 part
    app_job_1_2 = app_job_1_list['sample_test_2']
    assert type(app_job_1_2) is ApplicationStartJobs
    assert app_job_1_2.application_name == 'sample_test_2'
    assert set(app_job_1_2.planned_jobs.keys()) == {1}
    app_job_1_2_1 = app_job_1_2.planned_jobs[1]
    for command in app_job_1_2_1:
        assert type(command) is ProcessStartCommand
        command.strategy == StartingStrategies.MOST_LOADED
    # the trick used to define a process start_sequence sets 0 for yeux_00 and yeux_01
    assert {command.process for command in app_job_1_2_1} == {sample_test_2[0].process}
    assert app_job_1_2.current_jobs == []


def test_starter_start_process_running(mocker, starter, sample_test_1):
    """ Test the Starter.start_process method when process is not stopped. """
    mocked_job = mocker.patch.object(starter, 'get_application_job')
    mocked_next = mocker.patch.object(starter, 'next')
    xfontsel = sample_test_1[2]
    starter.start_process(StartingStrategies.CONFIG, xfontsel.process, 'extra_args')
    assert starter.planned_jobs == {}
    assert starter.current_jobs == {}
    assert not mocked_job.called
    assert not mocked_next.called


def test_starter_start_process_stopped(mocker, starter, sample_test_1):
    """ Test the Starter.start_process method when process is stopped. """
    mocked_next = mocker.patch.object(starter, 'next')
    # add application to context
    appli1 = create_application('sample_test_1', starter.supvisors)
    appli1.rules.start_sequence = 7
    starter.supvisors.context.applications['sample_test_1'] = appli1
    # Step 1. start process in a context where no corresponding application job exists
    xlogo = sample_test_1[1]
    xlogo.process.rules.start_sequence = 10
    starter.start_process(StartingStrategies.CONFIG, xlogo.process, 'extra_args')
    # check the planned_jobs contents
    assert list(starter.planned_jobs.keys()) == [7]
    # sequence 7 of planned jobs
    app_job_7_list = starter.planned_jobs[7]
    assert list(app_job_7_list.keys()) == ['sample_test_1']
    app_job_7_1 = app_job_7_list['sample_test_1']
    assert type(app_job_7_1) is ApplicationStartJobs
    assert app_job_7_1.application_name == 'sample_test_1'
    assert set(app_job_7_1.planned_jobs.keys()) == {10}
    app_job_7_1_10 = app_job_7_1.planned_jobs[10]
    for command in app_job_7_1_10:
        assert type(command) is ProcessStartCommand
        assert command.strategy == StartingStrategies.CONFIG
        assert command.extra_args == 'extra_args'
    assert {command.process for command in app_job_7_1_10} == {xlogo.process}
    assert app_job_7_1.current_jobs == []
    assert starter.current_jobs == {}
    assert mocked_next.called
    mocker.resetall()
    # Step 2. start process in a context where an application job exists in planned_jobs
    xclock = sample_test_1[0]
    xclock.process.rules.start_sequence = 5
    xclock.process._state = ProcessStates.FATAL
    starter.start_process(StartingStrategies.LOCAL, xclock.process, 'extra_args')
    # check the planned_jobs contents
    assert list(starter.planned_jobs.keys()) == [7]
    # sequence 7 of planned jobs
    app_job_7_list = starter.planned_jobs[7]
    assert list(app_job_7_list.keys()) == ['sample_test_1']
    app_job_7_1 = app_job_7_list['sample_test_1']
    assert type(app_job_7_1) is ApplicationStartJobs
    assert app_job_7_1.application_name == 'sample_test_1'
    assert set(app_job_7_1.planned_jobs.keys()) == {5, 10}
    # check sequence 5
    app_job_7_1_5 = app_job_7_1.planned_jobs[5]
    for command in app_job_7_1_5:
        assert type(command) is ProcessStartCommand
        assert command.strategy == StartingStrategies.LOCAL
        assert command.extra_args == 'extra_args'
    assert {command.process for command in app_job_7_1_5} == {xclock.process}
    assert app_job_7_1.current_jobs == []
    # check sequence 10
    app_job_7_1_10 = app_job_7_1.planned_jobs[10]
    for command in app_job_7_1_10:
        assert type(command) is ProcessStartCommand
        assert command.strategy == StartingStrategies.CONFIG
    assert {command.process for command in app_job_7_1_10} == {xlogo.process}
    assert app_job_7_1.current_jobs == []
    assert starter.current_jobs == {}
    assert mocked_next.called
    mocker.resetall()
    # Step 3. start process in a context where an application job exists in current_jobs
    starter.current_jobs = starter.planned_jobs.pop(7)
    assert starter.planned_jobs == {}
    xfontsel = sample_test_1[2]
    xfontsel.process.rules.start_sequence = 5  # same start_sequence as xclock
    xfontsel.process._state = ProcessStates.EXITED
    starter.start_process(StartingStrategies.LESS_LOADED, xfontsel.process, 'extra_args')
    # check the current_jobs contents
    assert list(starter.current_jobs.keys()) == ['sample_test_1']
    app_job_7_1 = starter.current_jobs['sample_test_1']
    assert type(app_job_7_1) is ApplicationStartJobs
    assert app_job_7_1.application_name == 'sample_test_1'
    assert set(app_job_7_1.planned_jobs.keys()) == {5, 10}
    # check sequence 5
    app_job_7_1_5 = app_job_7_1.planned_jobs[5]
    for command in app_job_7_1_5:
        assert type(command) is ProcessStartCommand
        assert command.extra_args == 'extra_args'
        if command.process is xclock.process:
            assert command.strategy == StartingStrategies.LOCAL
        elif command.process is xfontsel.process:
            assert command.strategy == StartingStrategies.LESS_LOADED
    assert {command.process for command in app_job_7_1_5} == {xclock.process, xfontsel.process}
    assert app_job_7_1.current_jobs == []
    # check sequence 10
    app_job_7_1_10 = app_job_7_1.planned_jobs[10]
    for command in app_job_7_1_10:
        assert type(command) is ProcessStartCommand
        assert command.strategy == StartingStrategies.CONFIG
        assert command.extra_args == 'extra_args'
    assert {command.process for command in app_job_7_1_10} == {xlogo.process}
    assert app_job_7_1.current_jobs == []
    assert mocked_next.called


def test_starter_default_start_process(mocker, starter):
    """ Test the Starter.default_start_process method. """
    mocked_start = mocker.patch.object(starter, 'start_process')
    # test that default_start_process just calls start_process with the default strategy
    dummy_application = create_application('dummy_application', starter.supvisors)
    dummy_application.rules.starting_strategy = StartingStrategies.LOCAL
    starter.supvisors.context.applications['dummy_application'] = dummy_application
    process = Mock(application_name='dummy_application')
    starter.default_start_process(process)
    assert mocked_start.call_args_list == [call(StartingStrategies.LOCAL, process)]


def test_starter_start_application(mocker, starter):
    """ Test the Starter.start_application method. """
    mocked_store = mocker.patch.object(starter, 'store_application')
    mocked_next = mocker.patch.object(starter, 'next')
    # create application start_sequence
    appli = create_application('sample_test_1', starter.supvisors)
    # test start_application on a running application
    for state in [ApplicationStates.RUNNING, ApplicationStates.STARTING, ApplicationStates.STOPPING]:
        appli._state = state
        starter.start_application(StartingStrategies.LESS_LOADED, appli)
        assert not mocked_store.called
        assert not mocked_next.called
    # test start_application on a stopped application
    appli._state = ApplicationStates.STOPPED
    starter.start_application(StartingStrategies.LESS_LOADED, appli)
    assert mocked_store.call_args_list == [call(appli, StartingStrategies.LESS_LOADED)]
    assert mocked_next.called


def test_starter_default_start_application(mocker, starter):
    """ Test the Starter.default_start_application method. """
    mocked_start = mocker.patch.object(starter, 'start_application')
    # test that default_start_application just calls start_application with the default strategy
    appli = create_application('sample_test_1', starter.supvisors)
    appli.rules.starting_strategy = StartingStrategies.MOST_LOADED
    starter.default_start_application(appli)
    assert mocked_start.call_args_list == [call(StartingStrategies.MOST_LOADED, appli)]


def test_starter_start_applications(mocker, starter, sample_test_2):
    """ Test the Starter.start_applications method. """
    mocked_store = mocker.patch.object(starter, 'store_application')
    mocked_next = mocker.patch.object(starter, 'next')
    # create one stopped application with a start_sequence == 0
    service = create_application('service', starter.supvisors)
    service.rules.start_sequence = 0
    starter.supvisors.context.applications['service'] = service
    # call starter start_applications and check nothing is triggered
    starter.start_applications(False)
    assert not mocked_store.called
    assert mocked_next.call_args_list == [call()]
    mocker.resetall()
    # test again with failure set
    service.major_failure = True
    starter.start_applications(False)
    assert not mocked_store.called
    assert mocked_next.call_args_list == [call()]
    mocker.resetall()
    # create one running application
    sample_test_1 = create_application('sample_test_1', starter.supvisors)
    sample_test_1.rules.start_sequence = 1
    sample_test_1._state = ApplicationStates.RUNNING
    starter.supvisors.context.applications['sample_test_1'] = sample_test_1
    info = any_process_info_by_state(ProcessStates.RUNNING)
    process = create_process(info, starter.supvisors)
    process.add_info('10.0.0.1', info)
    sample_test_1.add_process(process)
    # create one running application with major failure - add FATAL process
    sample_test_major = create_application('sample_test_major', starter.supvisors)
    sample_test_major._state = ApplicationStates.RUNNING
    sample_test_major.rules.start_sequence = 3
    sample_test_major.major_failure = True
    starter.supvisors.context.applications['sample_test_major'] = sample_test_major
    info = any_process_info_by_state(ProcessStates.FATAL)
    process = create_process(info, starter.supvisors)
    process.add_info('10.0.0.1', info)
    sample_test_major.add_process(process)
    # create one running application with minor failure - add EXITED process
    sample_test_minor = create_application('sample_test_minor', starter.supvisors)
    sample_test_minor._state = ApplicationStates.RUNNING
    sample_test_minor.rules.start_sequence = 3
    sample_test_minor.minor_failure = True
    starter.supvisors.context.applications['sample_test_minor'] = sample_test_minor
    info = any_process_info_by_state(ProcessStates.EXITED)
    process = create_process(info, starter.supvisors)
    process.add_info('10.0.0.1', info)
    sample_test_minor.add_process(process)
    # create one stopped application with a start_sequence > 0
    appli_2 = create_application('sample_test_2', starter.supvisors)
    appli_2.rules.start_sequence = 2
    for command in sample_test_2:
        if command.process.application_name == 'sample_test_2':
            appli_2.start_sequence.setdefault(len(command.process.namespec) % 3, []).append(command.process)
    starter.supvisors.context.applications['sample_test_2'] = appli_2
    # create one stopped / never started application with a start_sequence > 0
    stopped_app = create_application('stopped_app', starter.supvisors)
    stopped_app.rules.start_sequence = 3
    starter.supvisors.context.applications['stopped_app'] = stopped_app
    info = any_process_info_by_state(ProcessStates.STOPPED)
    process = create_process(info, starter.supvisors)
    process.add_info('10.0.0.1', info)
    stopped_app.add_process(process)
    # call starter start_applications and check what is triggered
    starter.start_applications(False)
    mocked_store.assert_has_calls([call(appli_2), call(sample_test_major), call(sample_test_minor)],
                                  any_order=True)
    assert call(stopped_app) not in mocked_store.call_args_list
    assert mocked_next.call_args_list == [call()]
    mocker.resetall()
    # call starter forced start_applications and check what is triggered
    starter.start_applications(True)
    mocked_store.assert_has_calls([call(appli_2), call(sample_test_major), call(sample_test_minor),
                                   call(stopped_app)], any_order=True)
    assert mocked_next.call_args_list == [call()]


def test_starter_after(mocker, starter, application_start_job_1):
    """ Test the Starter.after method. """
    mocked_stop = mocker.patch.object(starter.supvisors.stopper, 'stop_application')
    # test with application_stop_requests empty
    assert not application_start_job_1.stop_request
    starter.after(application_start_job_1)
    assert not application_start_job_1.stop_request
    assert not mocked_stop.called
    # test with application_stop_requests but call with another application
    application_start_job_1.stop_request = True
    starter.after(application_start_job_1)
    assert not application_start_job_1.stop_request
    assert mocked_stop.call_args_list == [call(application_start_job_1.application)]


def test_starter_get_load_requests(mocker, starter, application_job_1, application_job_2):
    """ Test the Starter.get_load_requests method. """
    mocker.patch.object(application_job_1, 'get_load_requests',
                        return_value={'10.0.0.1': 12, '10.0.0.2': 20})
    mocker.patch.object(application_job_2, 'get_load_requests',
                        return_value={'10.0.0.2': 10, '10.0.0.3': 15})
    # call with empty current_jobs
    assert starter.get_load_requests() == {}
    # add application_job_1 to current_jobs
    starter.current_jobs['sample_test_1'] = application_job_1
    assert starter.get_load_requests() == {'10.0.0.1': 12, '10.0.0.2': 20}
    # add application_job_2 to current_jobs
    starter.current_jobs['sample_test_2'] = application_job_2
    assert starter.get_load_requests() == {'10.0.0.1': 12, '10.0.0.2': 30, '10.0.0.3': 15}


# Stopper part
@pytest.fixture
def stopper(supvisors):
    """ Create the Stopper instance to test. """
    return Stopper(supvisors)


def test_stopper_create(stopper):
    """ Test the values set at construction of Stopper. """
    assert isinstance(stopper, Commander)
    assert stopper.pickup_logic is max
    assert stopper.application_start_requests == {}
    assert stopper.process_start_requests == {}


def test_stopper_store_application_separate(stopper, sample_test_1, sample_test_2):
    """ Test the Stopper.store_application method.
    sample_test_1 and sample_test_2 applications are in a different sequence. """
    # create 2 application stop sequences
    appli1 = create_application('sample_test_1', stopper.supvisors)
    appli1.rules.stop_sequence = 1
    for command in sample_test_1:
        appli1.stop_sequence.setdefault(len(command.process.namespec) % 3, []).append(command.process)
    appli2 = create_application('sample_test_2', stopper.supvisors)
    appli2.rules.stop_sequence = 2
    for command in sample_test_2:
        appli2.stop_sequence.setdefault(len(command.process.namespec) % 3, []).append(command.process)
    # call method twice
    stopper.store_application(appli1)
    stopper.store_application(appli2)
    # check the planned_jobs contents
    assert list(stopper.planned_jobs.keys()) == [1, 2]
    # sequence 1 of planned jobs
    app_job_1_list = stopper.planned_jobs[1]
    assert list(app_job_1_list.keys()) == ['sample_test_1']
    app_job_1_1 = app_job_1_list['sample_test_1']
    assert type(app_job_1_1) is ApplicationStopJobs
    assert app_job_1_1.application_name == 'sample_test_1'
    assert set(app_job_1_1.planned_jobs.keys()) == {1, 2}
    app_job_1_1_1 = app_job_1_1.planned_jobs[1]
    app_job_1_1_2 = app_job_1_1.planned_jobs[2]
    for command in app_job_1_1_1 + app_job_1_1_2:
        assert type(command) is ProcessStopCommand
    assert {command.process for command in app_job_1_1_1} == {sample_test_1[1].process, sample_test_1[2].process}
    assert {command.process for command in app_job_1_1_2} == {sample_test_1[0].process}
    assert app_job_1_1.current_jobs == []
    # sequence 2 of planned jobs
    app_job_2_list = stopper.planned_jobs[2]
    assert list(app_job_2_list.keys()) == ['sample_test_2']
    app_job_2_1 = app_job_2_list['sample_test_2']
    assert type(app_job_2_1) is ApplicationStopJobs
    assert app_job_2_1.application_name == 'sample_test_2'
    assert set(app_job_2_1.planned_jobs.keys()) == {0, 1}
    app_job_2_1_0 = app_job_2_1.planned_jobs[0]
    app_job_2_1_1 = app_job_2_1.planned_jobs[1]
    for command in app_job_2_1_0 + app_job_2_1_1:
        assert type(command) is ProcessStopCommand
    # stop_sequence is not excluded in Stopper
    assert {command.process for command in app_job_2_1_0} == {sample_test_2[1].process, sample_test_2[2].process}
    assert {command.process for command in app_job_2_1_1} == {sample_test_2[0].process}
    assert app_job_2_1.current_jobs == []


def test_stopper_store_application_mixed(stopper, sample_test_1, sample_test_2):
    """ Test the Stopper.store_application method.
    sample_test_1 and sample_test_2 applications are in the same sequence. """
    # create 2 application stop sequences
    appli1 = create_application('sample_test_1', stopper.supvisors)
    appli1.rules.stop_sequence = 2
    for command in sample_test_1:
        appli1.stop_sequence.setdefault(len(command.process.namespec) % 3, []).append(command.process)
    appli2 = create_application('sample_test_2', stopper.supvisors)
    appli2.rules.stop_sequence = 2
    for command in sample_test_2:
        appli2.stop_sequence.setdefault(len(command.process.namespec) % 3, []).append(command.process)
    # call method twice
    stopper.store_application(appli1)
    stopper.store_application(appli2)
    # check the planned_jobs contents
    assert list(stopper.planned_jobs.keys()) == [2]
    # sequence 1 of planned jobs
    app_job_1_list = stopper.planned_jobs[2]
    assert list(app_job_1_list.keys()) == ['sample_test_1', 'sample_test_2']
    # focus on sample_test_1 part
    app_job_1_1 = app_job_1_list['sample_test_1']
    assert type(app_job_1_1) is ApplicationStopJobs
    assert app_job_1_1.application_name == 'sample_test_1'
    assert set(app_job_1_1.planned_jobs.keys()) == {1, 2}
    app_job_1_1_1 = app_job_1_1.planned_jobs[1]
    app_job_1_1_2 = app_job_1_1.planned_jobs[2]
    for command in app_job_1_1_1 + app_job_1_1_2:
        assert type(command) is ProcessStopCommand
    assert {command.process for command in app_job_1_1_1} == {sample_test_1[1].process, sample_test_1[2].process}
    assert {command.process for command in app_job_1_1_2} == {sample_test_1[0].process}
    assert app_job_1_1.current_jobs == []
    # focus on sample_test_2 part
    app_job_1_2 = app_job_1_list['sample_test_2']
    assert type(app_job_1_2) is ApplicationStopJobs
    assert app_job_1_2.application_name == 'sample_test_2'
    assert set(app_job_1_2.planned_jobs.keys()) == {0, 1}
    app_job_1_2_0 = app_job_1_2.planned_jobs[0]
    app_job_1_2_1 = app_job_1_2.planned_jobs[1]
    for command in app_job_1_2_0 + app_job_1_2_1:
        assert type(command) is ProcessStopCommand
    # stop_sequence is not excluded in Stopper
    assert {command.process for command in app_job_1_2_0} == {sample_test_2[1].process, sample_test_2[2].process}
    assert {command.process for command in app_job_1_2_1} == {sample_test_2[0].process}
    assert app_job_1_2.current_jobs == []


def test_stopper_stop_process_stopped(mocker, stopper, sample_test_1):
    """ Test the Stopper.stop_process method when process is not running. """
    mocked_job = mocker.patch.object(stopper, 'get_application_job')
    mocked_next = mocker.patch.object(stopper, 'next')
    xlogo = sample_test_1[1]
    stopper.stop_process(xlogo.process)
    assert stopper.planned_jobs == {}
    assert stopper.current_jobs == {}
    assert not mocked_job.called
    assert not mocked_next.called


def test_stopper_stop_process_running(mocker, stopper, sample_test_1):
    """ Test the Starter.start_process method when process is running. """
    mocked_next = mocker.patch.object(stopper, 'next')
    # add application to context
    appli1 = create_application('sample_test_1', stopper.supvisors)
    appli1.rules.stop_sequence = 7
    stopper.supvisors.context.applications['sample_test_1'] = appli1
    # Step 1. start process in a context where no corresponding application job exists
    xlogo = sample_test_1[1]
    xlogo.process.rules.stop_sequence = 10
    xlogo.process._state = ProcessStates.RUNNING
    stopper.stop_process(xlogo.process)
    # check the planned_jobs contents
    assert list(stopper.planned_jobs.keys()) == [7]
    # sequence 7 of planned jobs
    app_job_7_list = stopper.planned_jobs[7]
    assert list(app_job_7_list.keys()) == ['sample_test_1']
    app_job_7_1 = app_job_7_list['sample_test_1']
    assert type(app_job_7_1) is ApplicationStopJobs
    assert app_job_7_1.application_name == 'sample_test_1'
    assert set(app_job_7_1.planned_jobs.keys()) == {10}
    app_job_7_1_10 = app_job_7_1.planned_jobs[10]
    for command in app_job_7_1_10:
        assert type(command) is ProcessStopCommand
    assert {command.process for command in app_job_7_1_10} == {xlogo.process}
    assert app_job_7_1.current_jobs == []
    assert stopper.current_jobs == {}
    assert mocked_next.called
    mocker.resetall()
    # Step 2. start process in a context where an application job exists in planned_jobs
    xclock = sample_test_1[0]
    xclock.process.rules.stop_sequence = 5
    xclock.process._state = ProcessStates.STARTING
    stopper.stop_process(xclock.process)
    # check the planned_jobs contents
    assert list(stopper.planned_jobs.keys()) == [7]
    # sequence 7 of planned jobs
    app_job_7_list = stopper.planned_jobs[7]
    assert list(app_job_7_list.keys()) == ['sample_test_1']
    app_job_7_1 = app_job_7_list['sample_test_1']
    assert type(app_job_7_1) is ApplicationStopJobs
    assert app_job_7_1.application_name == 'sample_test_1'
    assert set(app_job_7_1.planned_jobs.keys()) == {5, 10}
    # check sequence 5
    app_job_7_1_5 = app_job_7_1.planned_jobs[5]
    for command in app_job_7_1_5:
        assert type(command) is ProcessStopCommand
    assert {command.process for command in app_job_7_1_5} == {xclock.process}
    assert app_job_7_1.current_jobs == []
    # check sequence 10
    app_job_7_1_10 = app_job_7_1.planned_jobs[10]
    for command in app_job_7_1_10:
        assert type(command) is ProcessStopCommand
    assert {command.process for command in app_job_7_1_10} == {xlogo.process}
    assert app_job_7_1.current_jobs == []
    assert stopper.current_jobs == {}
    assert mocked_next.called
    mocker.resetall()
    # Step 3. start process in a context where an application job exists in current_jobs
    stopper.current_jobs = stopper.planned_jobs.pop(7)
    assert stopper.planned_jobs == {}
    xfontsel = sample_test_1[2]
    xfontsel.process.rules.stop_sequence = 5  # same start_sequence as xclock
    xfontsel.process._state = ProcessStates.BACKOFF
    stopper.stop_process(xfontsel.process)
    # check the current_jobs contents
    assert list(stopper.current_jobs.keys()) == ['sample_test_1']
    app_job_7_1 = stopper.current_jobs['sample_test_1']
    assert type(app_job_7_1) is ApplicationStopJobs
    assert app_job_7_1.application_name == 'sample_test_1'
    assert set(app_job_7_1.planned_jobs.keys()) == {5, 10}
    # check sequence 5
    app_job_7_1_5 = app_job_7_1.planned_jobs[5]
    for command in app_job_7_1_5:
        assert type(command) is ProcessStopCommand
    assert {command.process for command in app_job_7_1_5} == {xclock.process, xfontsel.process}
    assert app_job_7_1.current_jobs == []
    # check sequence 10
    app_job_7_1_10 = app_job_7_1.planned_jobs[10]
    for command in app_job_7_1_10:
        assert type(command) is ProcessStopCommand
    assert {command.process for command in app_job_7_1_10} == {xlogo.process}
    assert app_job_7_1.current_jobs == []
    assert mocked_next.called


def test_stopper_restart_process(mocker, stopper, sample_test_1):
    """ Test the Stopper.restart_process method when the process is already stopped. """
    mocked_stop = mocker.patch.object(stopper, 'stop_process')
    # check initial condition
    assert stopper.process_start_requests == {}
    # test restart call
    xlogo = sample_test_1[1]
    start_parameters = (StartingStrategies.CONFIG, xlogo.process, 'any args')
    assert not stopper.restart_process(*start_parameters)
    assert mocked_stop.call_args_list == [call(xlogo.process)]
    assert stopper.process_start_requests == {'sample_test_1': [start_parameters]}


def test_stopper_stop_application(mocker, stopper):
    """ Test the Stopper.stop_application method. """
    mocked_store = mocker.patch.object(stopper, 'store_application')
    mocked_next = mocker.patch.object(stopper, 'next')
    # create application
    appli = create_application('sample_test_1', stopper.supvisors)
    mocked_running = mocker.patch.object(appli, 'has_running_processes', return_value=False)
    # test stop_application on a stopped application
    stopper.stop_application(appli)
    assert not mocked_store.called
    assert not mocked_next.called
    # test stop_application on a running application
    mocked_running.return_value = True
    stopper.stop_application(appli)
    # first call: no job in progress
    assert mocked_store.call_args_list == [call(appli)]
    assert mocked_next.called


def test_stopper_stop_applications(mocker, stopper):
    """ Test the Stopper.stop_applications method. """
    mocked_store = mocker.patch.object(stopper, 'store_application')
    mocked_next = mocker.patch.object(stopper, 'next')
    # default: only next called
    stopper.stop_applications()
    assert not mocked_store.called
    assert mocked_next.called
    mocker.resetall()
    # create one running application
    appli1 = create_application('sample_test_1', stopper.supvisors)
    mocker.patch.object(appli1, 'has_running_processes', return_value=True)
    stopper.supvisors.context.applications['sample_test_1'] = appli1
    # create one stopped application
    appli2 = create_application('sample_test_2', stopper.supvisors)
    mocker.patch.object(appli2, 'has_running_processes', return_value=False)
    stopper.supvisors.context.applications['sample_test_2'] = appli2
    # call starter stop_applications and check that only sample_test_1 is triggered
    stopper.stop_applications()
    assert mocked_store.call_args_list == [call(appli1)]
    assert mocked_next.called


def test_stopper_restart_application(mocker, stopper):
    """ Test the Stopper.restart_application method. """
    mocked_stop = mocker.patch.object(stopper, 'stop_application')
    # check initial condition
    assert stopper.application_start_requests == {}
    # test restart call
    appli = create_application('appli_1', stopper.supvisors)
    start_parameters = (StartingStrategies.CONFIG, appli)
    stopper.restart_application(*start_parameters)
    assert mocked_stop.call_args_list == [call(appli)]
    assert stopper.application_start_requests == {'appli_1': start_parameters}


def test_stopper_after(mocker, stopper, sample_test_1):
    """ Test the Stopper.after method. """
    mocked_start_app = mocker.patch.object(stopper.supvisors.starter, 'start_application')
    mocked_start_proc = mocker.patch.object(stopper.supvisors.starter, 'start_process')
    # patch context
    appli_1 = create_application('appli_1', stopper.supvisors)
    appli_2 = create_application('appli_2', stopper.supvisors)
    appli_3 = create_application('appli_3', stopper.supvisors)
    stopper.supvisors.context.applications = {'appli_1': appli_1, 'appli_2': appli_2, 'appli_3': appli_3}
    # add pending requests
    xclock = sample_test_1[0].process
    xlogo = sample_test_1[1].process
    stopper.process_start_requests = {'appli_2': [(StartingStrategies.MOST_LOADED, xclock, ''),
                                                  (StartingStrategies.LOCAL, xlogo, 'any args')]}
    stopper.application_start_requests = {'appli_3': (StartingStrategies.LESS_LOADED, appli_3)}
    # no corresponding pending request
    application_job = Mock(application_name='appli_1')
    stopper.after(application_job)
    assert not mocked_start_app.called
    assert not mocked_start_proc.called
    # appli_2 has pending process start requests
    application_job.application_name = 'appli_2'
    stopper.after(application_job)
    assert not mocked_start_app.called
    assert mocked_start_proc.call_args_list == [call(StartingStrategies.MOST_LOADED, xclock, ''),
                                                call(StartingStrategies.LOCAL, xlogo, 'any args')]
    assert stopper.process_start_requests == {}
    mocked_start_proc.reset_mock()
    # appli_3 has pending application start requests
    application_job.application_name = 'appli_3'
    stopper.after(application_job)
    assert mocked_start_app.call_args_list == [call(StartingStrategies.LESS_LOADED, appli_3)]
    assert stopper.application_start_requests == {}
    assert not mocked_start_proc.called
