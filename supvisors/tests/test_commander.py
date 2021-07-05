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
import time

from supervisor.states import ProcessStates
from unittest.mock import call, patch, Mock

from supvisors.tests.base import database_copy
from supvisors.tests.conftest import create_any_process, create_process, create_application


# ProcessCommand part
def test_command_create(supvisors):
    """ Test the values set at construction of ProcessCommand. """
    from supvisors.commander import ProcessCommand
    from supvisors.ttypes import StartingStrategies
    process = create_any_process(supvisors)
    # test default strategy
    command = ProcessCommand(process)
    assert process is command.process
    assert command.strategy is None
    assert command.request_time == 0
    assert not command.ignore_wait_exit
    assert command.extra_args == ''
    # test strategy in parameter
    command = ProcessCommand(process, StartingStrategies.MOST_LOADED)
    assert process is command.process
    assert command.strategy == StartingStrategies.MOST_LOADED
    assert command.request_time == 0
    assert not command.ignore_wait_exit
    assert command.extra_args == ''


def test_str():
    """ Test the output string of the ProcessCommand. """
    from supvisors.commander import ProcessCommand
    from supvisors.ttypes import StartingStrategies
    process = Mock(state='RUNNING', last_event_time=1234, **{'namespec.return_value': 'proc_1'})
    command = ProcessCommand(process, StartingStrategies.CONFIG)
    command.request_time = 4321
    command.ignore_wait_exit = True
    command.extra_args = '-s test args'
    assert str(command) == 'process=proc_1 state=RUNNING last_event_time=1234 strategy=0 request_time=4321'\
                           ' ignore_wait_exit=True extra_args="-s test args"'


def test_timed_out():
    """ Test the ProcessCommand.timed_out method. """
    from supvisors.commander import ProcessCommand
    command = ProcessCommand(Mock(last_event_time=100))
    command.request_time = 95
    assert not command.timed_out(102)
    command.request_time = 101
    assert not command.timed_out(108)
    assert command.timed_out(112)
    command.request_time = 99
    assert command.timed_out(111)


# Commander part
def create_process_command(info, supvisors):
    """ Create a ProcessCommand from process info. """
    from supvisors.commander import ProcessCommand
    return ProcessCommand(create_process(info, supvisors))


def get_test_command(cmd_list, process_name):
    """ Return the first process corresponding to process_name. """
    return next(command for command in cmd_list if command.process.process_name == process_name)


@pytest.fixture
def command_list(supvisors):
    """ Create a command list with all processes of the database. """
    cmd_list = []
    for info in database_copy():
        command = create_process_command(info, supvisors)
        command.process.add_info('10.0.0.1', info)
        cmd_list.append(command)
    return cmd_list


@pytest.fixture
def commander(supvisors):
    """ Create the Commander instance to test. """
    from supvisors.commander import Commander
    return Commander(supvisors)


@pytest.fixture
def command_list_1(supvisors):
    return [create_process_command({'group': 'appli_A', 'name': 'dummy_A1'}, supvisors),
            create_process_command({'group': 'appli_A', 'name': 'dummy_A2'}, supvisors),
            create_process_command({'group': 'appli_A', 'name': 'dummy_A3'}, supvisors)]


@pytest.fixture
def command_list_2(supvisors):
    return [create_process_command({'group': 'appli_B', 'name': 'dummy_B1'}, supvisors)]


def test_commander_creation(supvisors, commander):
    """ Test the values set at construction of Commander. """
    assert supvisors is commander.supvisors
    assert supvisors.logger is commander.logger
    assert commander.planned_sequence == {}
    assert commander.planned_jobs == {}
    assert commander.current_jobs == {}


def test_commander_in_progress(commander, command_list_1, command_list_2):
    """ Test the Commander.in_progress method. """
    assert not commander.in_progress()
    commander.planned_sequence = {0: {'if': {0: command_list_1}}}
    assert commander.in_progress()
    commander.planned_jobs = {'then': {1: command_list_2}}
    assert commander.in_progress()
    commander.current_jobs = {'else': []}
    assert commander.in_progress()
    commander.planned_sequence = {}
    assert commander.in_progress()
    commander.planned_jobs = {}
    assert commander.in_progress()
    commander.current_jobs = {}
    assert not commander.in_progress()


def test_commander_has_application(commander, command_list_1, command_list_2):
    """ Test the Commander.has_application method. """
    assert not commander.has_application('if')
    assert not commander.has_application('then')
    assert not commander.has_application('else')
    commander.planned_sequence = {0: {'if': {0: command_list_1}}}
    assert commander.has_application('if')
    assert not commander.has_application('then')
    commander.planned_jobs = {'then': {1: command_list_2}}
    assert commander.has_application('if')
    assert commander.has_application('then')
    assert not commander.has_application('else')
    commander.current_jobs = {'else': []}
    assert commander.has_application('if')
    assert commander.has_application('then')
    assert commander.has_application('else')
    commander.planned_sequence = {}
    assert not commander.has_application('if')
    assert commander.has_application('then')
    assert commander.has_application('else')
    commander.planned_jobs = {}
    assert not commander.has_application('if')
    assert not commander.has_application('then')
    assert commander.has_application('else')
    commander.current_jobs = {}
    assert not commander.has_application('if')
    assert not commander.has_application('then')
    assert not commander.has_application('else')


def test_commander_printable_command_list(commander, command_list_1, command_list_2):
    """ Test the Commander.printable_process_list method. """
    # test with empty list
    printable = commander.printable_command_list([])
    assert printable == []
    # test with list having a single element
    printable = commander.printable_command_list(command_list_2)
    assert printable == ['appli_B:dummy_B1']
    # test with list having multiple elements
    printable = commander.printable_command_list(command_list_1)
    assert printable == ['appli_A:dummy_A1', 'appli_A:dummy_A2', 'appli_A:dummy_A3']


def test_commander_printable_current_jobs(commander, command_list_1, command_list_2):
    """ Test the Commander.printable_current_jobs method. """
    # test with empty structure
    commander.current_jobs = {}
    printable = commander.printable_current_jobs()
    assert printable == {}
    # test with complex structure
    commander.current_jobs = {'if': [], 'then': command_list_1, 'else': command_list_2}
    printable = commander.printable_current_jobs()
    assert printable == {'if': [],
                         'then': ['appli_A:dummy_A1', 'appli_A:dummy_A2', 'appli_A:dummy_A3'],
                         'else': ['appli_B:dummy_B1']}


def test_commander_printable_planned_jobs(commander, command_list_1, command_list_2):
    """ Test the Commander.printable_planned_jobs method. """
    # test with empty structure
    commander.planned_jobs = {}
    printable = commander.printable_planned_jobs()
    assert printable == {}
    # test with complex structure
    commander.planned_jobs = {'if': {0: command_list_1, 1: []},
                              'then': {2: command_list_2},
                              'else': {}}
    printable = commander.printable_planned_jobs()
    assert printable == {'if': {0: ['appli_A:dummy_A1', 'appli_A:dummy_A2', 'appli_A:dummy_A3'], 1: []},
                         'then': {2: ['appli_B:dummy_B1']},
                         'else': {}}


def test_commander_printable_planned_sequence(commander, command_list_1, command_list_2):
    """ Test the Commander.printable_planned_sequence method. """
    # test with empty structure
    commander.planned_sequence = {}
    printable = commander.printable_planned_sequence()
    assert printable == {}
    # test with complex structure
    commander.planned_sequence = {0: {'if': {-1: [], 0: command_list_1}, 'then': {2: command_list_2}},
                                  3: {'else': {}}}
    printable = commander.printable_planned_sequence()
    assert printable == {0: {'if': {-1: [], 0: ['appli_A:dummy_A1', 'appli_A:dummy_A2', 'appli_A:dummy_A3']},
                             'then': {2: ['appli_B:dummy_B1']}},
                         3: {'else': {}}}


def test_commander_process_application_jobs(commander, command_list_1, command_list_2):
    """ Test the Commander.process_application_jobs method. """
    # fill planned_jobs
    commander.planned_jobs = {'if': {0: command_list_1, 1: []}, 'then': {2: command_list_2}, 'else': {}}

    # define patch function
    def fill_jobs(*args, **_):
        args[1].append(args[0])

    with patch.object(commander, 'process_job', side_effect=fill_jobs) as mocked_job:
        # test with unknown application
        commander.process_application_jobs('while')
        assert commander.current_jobs == {}
        assert commander.planned_jobs == {'if': {0: command_list_1, 1: []},
                                          'then': {2: command_list_2},
                                          'else': {}}
        assert not mocked_job.called
        # test with known application: sequence 0 of 'if' application is popped
        commander.process_application_jobs('if')
        assert commander.planned_jobs == {'if': {1: []},
                                          'then': {2: command_list_2},
                                          'else': {}}
        assert commander.current_jobs == {'if': command_list_1}
        assert mocked_job.call_count == 3
        # test with known application: sequence 1 of 'if' application is popped
        mocked_job.reset_mock()
        commander.process_application_jobs('if')
        assert commander.planned_jobs == {'then': {2: command_list_2}, 'else': {}}
        assert commander.current_jobs == {}
        assert not mocked_job.called
    # test that process_job method must be implemented
    with pytest.raises(NotImplementedError):
        commander.process_application_jobs('then')
    assert commander.planned_jobs == {'then': {}, 'else': {}}
    assert commander.current_jobs == {'then': []}


def test_commander_trigger_jobs(commander, command_list_1, command_list_2):
    """ Test the trigger_jobs method. """
    # test with empty structure
    commander.planned_sequence = {}
    commander.trigger_jobs()
    assert commander.planned_jobs == {}
    # test with complex structure
    commander.planned_sequence = {0: {'if': {2: [], 0: command_list_1},
                                      'then': {2: command_list_2}},
                                  3: {'else': {}}}

    # define patch function
    def fill_jobs(*args, **_):
        args[1].append(args[0])

    with patch.object(commander, 'process_job', side_effect=fill_jobs) as mocked_job:
        commander.trigger_jobs()
        # test impact on internal attributes
        assert commander.planned_sequence == {3: {'else': {}}}
        assert commander.planned_jobs == {'if': {2: []}}
        assert commander.current_jobs == {'if': command_list_1, 'then': command_list_2}
        assert mocked_job.call_count == 4


@patch('supvisors.commander.Commander.trigger_jobs')
@patch('supvisors.commander.Commander.force_process_state')
@patch('supvisors.commander.Commander.after_event')
def test_commander_check_progress(mocked_after: Mock, mocked_force: Mock, mocked_trigger: Mock,
                                  commander, command_list):
    """ Test the check_progress method. """
    # test with no sequence in progress
    assert commander.check_progress('stopped', ProcessStates.FATAL)
    # test with no current jobs but planned sequence and no planned jobs
    commander.planned_sequence = {3: {'else': {}}}
    assert not commander.check_progress('stopped', ProcessStates.FATAL)
    assert mocked_trigger.call_args_list == [call()]
    mocked_trigger.reset_mock()
    # test with no current jobs but planned sequence and planned jobs (unexpected case)
    commander.planned_jobs = {'if': {2: []}}
    assert not commander.check_progress('stopped', ProcessStates.FATAL)
    assert not mocked_trigger.called
    # set test current_jobs
    # xfontsel is RUNNING, xlogo is STOPPED, yeux_00 is EXITED, yeux_01 is RUNNING
    commander.current_jobs = {'sample_test_1': [get_test_command(command_list, 'xfontsel'),
                                                get_test_command(command_list, 'xlogo')],
                              'sample_test_2': [get_test_command(command_list, 'yeux_00'),
                                                get_test_command(command_list, 'yeux_01')]}
    # assign request_time to processes in current_jobs
    for command_list in commander.current_jobs.values():
        for command in command_list:
            command.request_time = time.time()
    # stopped processes have a recent request time: nothing done
    completed = commander.check_progress('stopped', ProcessStates.FATAL)
    assert not completed
    assert commander.printable_current_jobs() == {'sample_test_1': ['sample_test_1:xfontsel', 'sample_test_1:xlogo'],
                                                  'sample_test_2': ['sample_test_2:yeux_00', 'sample_test_2:yeux_01']}
    assert not mocked_force.called
    assert not mocked_after.called
    assert not mocked_trigger.called
    # re-assign last_event_time and request_time to processes in current_jobs
    for command_list in commander.current_jobs.values():
        for command in command_list:
            command.process.last_event_time = 0
            command.request_time = 0
    # stopped processes have an old request time: actions taken on state and sequence
    completed = commander.check_progress('stopped', ProcessStates.FATAL)
    assert not completed
    assert commander.printable_current_jobs() == {'sample_test_1': ['sample_test_1:xfontsel'],
                                                  'sample_test_2': ['sample_test_2:yeux_01']}
    reason = 'Still stopped 10 seconds after request'
    assert mocked_force.call_args_list == [call('sample_test_1:xlogo', ProcessStates.FATAL, reason),
                                           call('sample_test_2:yeux_00', ProcessStates.FATAL, reason)]
    assert not mocked_after.called
    assert not mocked_trigger.called
    # reset mocks
    mocked_force.reset_mock()
    # re-assign request_time to processes in remaining current_jobs
    for command_list in commander.current_jobs.values():
        for command in command_list:
            command.request_time = time.time()
    # stopped processes have a recent request time: nothing done
    completed = commander.check_progress('running', ProcessStates.UNKNOWN)
    assert not completed
    assert commander.printable_current_jobs() == {'sample_test_1': ['sample_test_1:xfontsel'],
                                                  'sample_test_2': ['sample_test_2:yeux_01']}
    assert not mocked_force.called
    assert not mocked_after.called
    assert not mocked_trigger.called
    # re-assign last_event_time and request_time to processes in current_jobs
    for command_list in commander.current_jobs.values():
        for command in command_list:
            command.process.last_event_time = 0
            command.request_time = 0
    # stopped processes have an old request time: actions taken on state and sequence
    completed = commander.check_progress('running', ProcessStates.UNKNOWN)
    assert not completed
    assert commander.printable_current_jobs() == {'sample_test_1': [], 'sample_test_2': []}
    reason = 'Still running 10 seconds after request'
    assert mocked_force.call_args_list == [call('sample_test_1:xfontsel', ProcessStates.UNKNOWN, reason),
                                           call('sample_test_2:yeux_01', ProcessStates.UNKNOWN, reason)]
    assert mocked_after.call_args_list == [call('sample_test_1'), call('sample_test_2')]
    assert not mocked_trigger.called


@patch('supvisors.infosource.SupervisordSource.force_process_fatal')
@patch('supvisors.listener.SupervisorListener.force_process_fatal')
def test_commander_force_process_fatal(mocked_listener: Mock, mocked_source: Mock, commander):
    """ Test the force_process_state method with a FATAL parameter. """
    # test with FATAL and no info_source KeyError
    commander.force_process_state('proc', ProcessStates.FATAL, 'any reason')
    assert mocked_source.call_args_list == [call(commander.supvisors.info_source, 'proc', 'any reason')]
    assert not mocked_listener.called
    mocked_source.reset_mock()
    # test with FATAL and info_source KeyError
    mocked_source.side_effect = KeyError
    commander.force_process_state('proc', ProcessStates.FATAL, 'any reason')
    assert mocked_source.call_args_list == [call(commander.supvisors.info_source, 'proc', 'any reason')]
    assert mocked_listener.call_args_list == [call(commander.supvisors.listener, 'proc')]


@patch('supvisors.infosource.SupervisordSource.force_process_unknown')
@patch('supvisors.listener.SupervisorListener.force_process_unknown')
def test_commander_force_process_unknown(mocked_listener: Mock, mocked_source: Mock, commander):
    """ Test the force_process_state method with an UNKNOWN parameter. """
    # test with UNKNOWN and no info_source KeyError
    commander.force_process_state('proc', ProcessStates.UNKNOWN, 'any reason')
    assert mocked_source.call_args_list == [call(commander.supvisors.info_source, 'proc', 'any reason')]
    assert not mocked_listener.called
    mocked_source.reset_mock()
    # test with UNKNOWN and info_source KeyError
    mocked_source.side_effect = KeyError
    commander.force_process_state('proc', ProcessStates.UNKNOWN, 'any reason')
    assert mocked_source.call_args_list == [call(commander.supvisors.info_source, 'proc', 'any reason')]
    assert mocked_listener.call_args_list == [call(commander.supvisors.listener, 'proc')]


@patch('supvisors.commander.Commander.process_application_jobs')
@patch('supvisors.commander.Commander.trigger_jobs')
def test_commander_after_event(mocked_trigger: Mock, mocked_process: Mock, commander):
    """ Test the after_event method. """
    # prepare some context
    commander.planned_jobs = {'if': {2: []}}
    commander.current_jobs = {'if': [], 'then': [], 'else': []}
    # test after_event when there are still planned jobs for application
    commander.after_event('if')
    assert 'if' not in commander.current_jobs
    assert mocked_process.call_args_list == [call('if')]
    assert not mocked_trigger.called
    # reset mocks
    mocked_process.reset_mock()
    # test after_event when there's no more planned jobs for this application
    commander.after_event('then')
    assert 'then' not in commander.current_jobs
    assert not mocked_process.called
    assert not mocked_trigger.called
    # test after_event when there's no more planned jobs at all
    commander.planned_jobs = {}
    commander.after_event('else')
    assert 'else' not in commander.current_jobs
    assert not mocked_process.called
    assert not mocked_process.called
    assert mocked_trigger.call_args_list == [call()]


# Starter part
@pytest.fixture
def starter(supvisors):
    """ Create the Starter instance to test. """
    from supvisors.commander import Starter
    return Starter(supvisors)


def test_starter_create(starter):
    """ Test the values set at construction of Starter. """
    from supvisors.commander import Commander
    assert isinstance(starter, Commander)


def test_starter_abort(starter):
    """ Test the Starter.abort method. """
    # prepare some context
    starter.planned_sequence = {3: {'else': {}}}
    starter.planned_jobs = {'if': {2: []}}
    starter.current_jobs = {'if': ['dummy_1', 'dummy_2'], 'then': ['dummy_3']}
    # call abort and check attributes
    starter.abort()
    assert starter.planned_sequence == {}
    assert starter.planned_jobs == {}
    assert starter.current_jobs == {}


def test_starter_store_application_start_sequence(starter, command_list):
    """ Test the Starter.store_application_start_sequence method. """
    from supvisors.ttypes import StartingStrategies
    # create 2 application start_sequences
    appli1 = create_application('sample_test_1', starter.supvisors)
    for command in command_list:
        if command.process.application_name == 'sample_test_1':
            appli1.start_sequence.setdefault(len(command.process.namespec()) % 3, []).append(command.process)
    appli2 = create_application('sample_test_2', starter.supvisors)
    for command in command_list:
        if command.process.application_name == 'sample_test_2':
            appli2.start_sequence.setdefault(len(command.process.namespec()) % 3, []).append(command.process)
    # call method and check result
    starter.store_application_start_sequence(appli1, StartingStrategies.LESS_LOADED)
    # check that application sequence 0 is not in starter planned sequence
    expected = {0: {'sample_test_1': {1: ['sample_test_1:xfontsel', 'sample_test_1:xlogo'],
                                      2: ['sample_test_1:xclock']}}}
    assert starter.printable_planned_sequence() == expected
    # check strategy applied
    for proc_list in starter.planned_sequence[0]['sample_test_1'].values():
        for proc in proc_list:
            assert proc.strategy == StartingStrategies.LESS_LOADED
    # call method a second time and check result
    starter.store_application_start_sequence(appli2, StartingStrategies.LOCAL)
    # check that application sequence 0 is not in starter planned sequence
    expected = {0: {'sample_test_1': {1: ['sample_test_1:xfontsel', 'sample_test_1:xlogo'],
                                      2: ['sample_test_1:xclock']},
                    'sample_test_2': {1: ['sample_test_2:sleep']}}}
    assert starter.printable_planned_sequence() == expected
    # check strategy applied
    for proc_list in starter.planned_sequence[0]['sample_test_1'].values():
        for proc in proc_list:
            assert proc.strategy == StartingStrategies.LESS_LOADED
    for proc_list in starter.planned_sequence[0]['sample_test_2'].values():
        for proc in proc_list:
            assert proc.strategy == StartingStrategies.LOCAL


def test_starter_process_failure_optional(starter):
    """ Test the Starter.process_failure method with an optional process. """
    # prepare context
    process = Mock()
    process.rules = Mock(required=False)
    test_planned_jobs = {'appli_1': {0: ['proc_1']}, 'appli_2': {1: ['proc_2']}}
    # get the patch for stopper / stop_application
    mocked_stopper = starter.supvisors.stopper.stop_application
    # test with a process not required
    starter.planned_jobs = test_planned_jobs.copy()
    starter.process_failure(process)
    # test planned_jobs is unchanged
    assert starter.planned_jobs == test_planned_jobs
    # test stop_application is not called
    assert not mocked_stopper.called


def test_starter_process_failure_required(starter):
    """ Test the Starter.process_failure method with a required process. """
    from supvisors.ttypes import StartingFailureStrategies
    # prepare context
    process = Mock(application_name='appli_1')
    process.rules = Mock(required=True)
    application = Mock()
    starter.supvisors.context.applications = {'appli_1': application, 'proc_2': None}
    test_planned_jobs = {'appli_1': {0: ['proc_1']}, 'appli_2': {1: ['proc_2']}}
    # get the patch for stopper / stop_application
    mocked_stopper = starter.supvisors.stopper.stop_application
    # test ABORT starting strategy
    starter.planned_jobs = test_planned_jobs.copy()
    application.rules = Mock(starting_failure_strategy=StartingFailureStrategies.ABORT)
    starter.process_failure(process)
    # check that application has been removed from planned jobs and stopper wasn't called
    assert starter.planned_jobs == {'appli_2': {1: ['proc_2']}}
    assert not mocked_stopper.called
    # test CONTINUE starting strategy
    starter.planned_jobs = test_planned_jobs.copy()
    application.rules = Mock(starting_failure_strategy=StartingFailureStrategies.CONTINUE)
    starter.process_failure(process)
    # check that application has NOT been removed from planned jobs and stopper wasn't called
    assert starter.planned_jobs == {'appli_1': {0: ['proc_1']}, 'appli_2': {1: ['proc_2']}}
    assert not mocked_stopper.called
    # test STOP starting strategy
    starter.planned_jobs = test_planned_jobs.copy()
    application.rules = Mock(starting_failure_strategy=StartingFailureStrategies.STOP)
    starter.process_failure(process)
    # check that application has been removed from planned jobs and stopper has been called
    assert starter.planned_jobs == {'appli_2': {1: ['proc_2']}}
    assert mocked_stopper.call_args_list == [call(application)]


@patch('supvisors.commander.Commander.check_progress', return_value=True)
def test_starter_check_starting(mocked_check: Mock, starter):
    """ Test the Starter.check_starting method. """
    assert starter.check_starting()
    assert mocked_check.call_args_list == [call('stopped', ProcessStates.FATAL)]


def test_starter_on_event(starter, command_list):
    """ Test the Starter.on_event method. """
    # apply patches
    with patch.object(starter, 'on_event_in_sequence') as mocked_in:
        with patch.object(starter, 'on_event_out_of_sequence') as mocked_out:
            # set test current_jobs
            for command in command_list:
                starter.current_jobs.setdefault(command.process.application_name, []).append(command)
            assert 'sample_test_1' in starter.current_jobs
            # test that on_event_out_of_sequence is called when process
            # is not in current jobs due to unknown application
            process = Mock(application_name='unknown_application')
            starter.on_event(process)
            assert not mocked_in.called
            assert mocked_out.call_args_list == [(call(process))]
            mocked_out.reset_mock()
            # test that on_event_out_of_sequence is called when process is not in current jobs because unknown
            process = Mock(application_name='sample_test_1')
            starter.on_event(process)
            assert not mocked_in.called
            assert mocked_out.call_args_list == [(call(process))]
            mocked_out.reset_mock()
            # test that on_event_in_sequence is called when process is in list
            jobs = starter.current_jobs['sample_test_1']
            command = next(iter(jobs))
            starter.on_event(command.process)
            assert not mocked_out.called
            assert mocked_in.call_args_list == [(call(command, jobs))]


@patch('supvisors.commander.Starter.process_failure')
@patch('supvisors.commander.Commander.after_event')
def test_starter_on_event_in_sequence(mocked_after: Mock, mocked_failure: Mock, starter, command_list):
    """ Test the Starter.on_event_in_sequence method. """
    from supvisors.ttypes import StartingFailureStrategies
    # set context for current_jobs
    for command in command_list:
        starter.current_jobs.setdefault(command.process.application_name, []).append(command)
    # add application context
    application = create_application('sample_test_1', starter.supvisors)
    application.rules.starting_failure_strategy = StartingFailureStrategies.CONTINUE
    starter.supvisors.context.applications['sample_test_1'] = application
    application = create_application('sample_test_2', starter.supvisors)
    application.rules.starting_failure_strategy = StartingFailureStrategies.ABORT
    starter.supvisors.context.applications['sample_test_2'] = application
    # with sample_test_1 application
    # test STOPPED process
    command = get_test_command(command_list, 'xlogo')
    jobs = starter.current_jobs['sample_test_1']
    assert command in jobs
    starter.on_event_in_sequence(command, jobs)
    assert not command.ignore_wait_exit
    assert command not in jobs
    assert mocked_failure.call_args_list == [call(command.process)]
    assert not mocked_after.called
    # reset mocks
    mocked_failure.reset_mock()
    # test STOPPING process: xclock
    command = get_test_command(command_list, 'xclock')
    assert command in jobs
    starter.on_event_in_sequence(command, jobs)
    assert not command.ignore_wait_exit
    assert command not in jobs
    assert mocked_failure.call_args_list == [call(command.process)]
    assert not mocked_after.called
    # reset mocks
    mocked_failure.reset_mock()
    # test RUNNING process: xfontsel (last process of this application)
    command = get_test_command(command_list, 'xfontsel')
    assert command in jobs
    assert not command.process.rules.wait_exit
    assert not command.ignore_wait_exit
    starter.on_event_in_sequence(command, jobs)
    assert command not in jobs
    assert not mocked_failure.called
    assert mocked_after.call_args_list == [call('sample_test_1')]
    # reset mocks
    mocked_after.reset_mock()
    # with sample_test_2 application
    # test RUNNING process: yeux_01
    command = get_test_command(command_list, 'yeux_01')
    jobs = starter.current_jobs['sample_test_2']
    command.process.rules.wait_exit = True
    command.ignore_wait_exit = True
    assert command in jobs
    starter.on_event_in_sequence(command, jobs)
    assert command not in jobs
    assert not mocked_failure.called
    assert not mocked_after.called
    # test EXITED / expected process: yeux_00
    command = get_test_command(command_list, 'yeux_00')
    command.process.rules.wait_exit = True
    command.process.expected_exit = True
    assert command in jobs
    starter.on_event_in_sequence(command, jobs)
    assert command not in jobs
    assert not mocked_failure.called
    assert not mocked_after.called
    # test FATAL process: sleep (last process of this application)
    command = get_test_command(command_list, 'sleep')
    assert command in jobs
    starter.on_event_in_sequence(command, jobs)
    assert not command.ignore_wait_exit
    assert command not in jobs
    assert mocked_failure.call_args_list == [call(command.process)]
    assert mocked_after.call_args_list == [call('sample_test_2')]
    # reset mocks
    mocked_failure.reset_mock()
    mocked_after.reset_mock()
    # with crash application
    # test STARTING process: late_segv
    command = get_test_command(command_list, 'late_segv')
    jobs = starter.current_jobs['crash']
    assert command in jobs
    starter.on_event_in_sequence(command, jobs)
    assert command in jobs
    assert not mocked_failure.called
    assert not mocked_after.called
    # test BACKOFF process: segv (last process of this application)
    command = get_test_command(command_list, 'segv')
    assert command in jobs
    starter.on_event_in_sequence(command, jobs)
    assert command in jobs
    assert not mocked_failure.called
    assert not mocked_after.called
    # with firefox application
    # test EXITED / unexpected process: firefox
    command = get_test_command(command_list, 'firefox')
    jobs = starter.current_jobs['firefox']
    command.process.rules.wait_exit = True
    command.process.expected_exit = False
    assert command in jobs
    starter.on_event_in_sequence(command, jobs)
    assert 'firefox' in starter.current_jobs
    assert mocked_failure.call_args_list == [call(command.process)]
    assert mocked_after.call_args_list == [call('firefox')]


def test_starter_on_event_out_of_sequence(starter, command_list):
    """ Test how failure are raised in Starter.on_event_out_of_sequence method. """
    # set test planned_jobs and current_jobs
    starter.planned_jobs = {'sample_test_2': {1: []}}
    for command in command_list:
        starter.current_jobs.setdefault(command.process.application_name, []).append(command)
    # apply patch
    with patch.object(starter, 'process_failure') as mocked_failure:
        # test that process_failure is not called if process is not crashed
        process = next(command.process
                       for command in command_list
                       if not command.process.crashed())
        starter.on_event_out_of_sequence(process)
        assert not mocked_failure.called
        # test that process_failure is not called if process is not in planned jobs
        process = next(command.process for command in command_list
                       if command.process.application_name == 'sample_test_1')
        starter.on_event_out_of_sequence(process)
        assert not mocked_failure.called
        # get a command related to a process crashed and in planned jobs
        command = next(command for command in command_list
                       if command.process.crashed() and command.process.application_name == 'sample_test_2')
        # test that process_failure is called if process' starting is not planned
        starter.on_event_out_of_sequence(command.process)
        assert mocked_failure.call_args_list == [(call(command.process))]
        mocked_failure.reset_mock()
        # test that process_failure is not called if process' starting is still planned
        starter.planned_jobs = {'sample_test_2': {1: [command]}}
        starter.on_event_out_of_sequence(command.process)
        assert not mocked_failure.called


@patch('supvisors.commander.Commander.force_process_state')
@patch('supvisors.commander.get_node')
def test_starter_process_job(mocked_node_getter: Mock, mocked_force: Mock, starter, command_list):
    """ Test the Starter.process_job method. """
    # get patches
    mocked_pusher = starter.supvisors.zmq.pusher.send_start_process
    # test with a possible starting address
    mocked_node_getter.return_value = '10.0.0.1'
    # 1. test with running process
    command = get_test_command(command_list, 'xfontsel')
    command.ignore_wait_exit = True
    jobs = []
    # call the process_jobs
    starter.process_job(command, jobs)
    # starting methods are not called
    assert jobs == []
    assert not mocked_node_getter.called
    assert not mocked_pusher.called
    # failure method is not called
    assert not mocked_force.called
    # 2.a test with stopped process
    command = get_test_command(command_list, 'xlogo')
    command.ignore_wait_exit = True
    jobs = []
    # call the process_jobs
    starter.process_job(command, jobs)
    # starting methods are called
    assert jobs == [command]
    assert mocked_node_getter.call_args_list == [call(starter.supvisors, None, ['10.0.0.1'], 1)]
    assert mocked_pusher.call_args_list == [call('10.0.0.1', 'sample_test_1:xlogo', '')]
    mocked_pusher.reset_mock()
    # failure method is not called
    assert not mocked_force.called
    # 3. test with no starting address
    mocked_node_getter.return_value = None
    # test with stopped process
    command = get_test_command(command_list, 'xlogo')
    command.ignore_wait_exit = True
    jobs = []
    # call the process_jobs
    starter.process_job(command, jobs)
    # starting methods are not called but job is in list though
    assert jobs == [command]
    assert not mocked_pusher.called
    # failure method is called
    assert mocked_force.call_args_list == [call('sample_test_1:xlogo', ProcessStates.FATAL, 'no resource available')]


def test_starter_start_process_failure(starter, command_list):
    """ Test the Starter.start_process method in failure case. """
    from supvisors.ttypes import StartingStrategies
    xlogo_command = get_test_command(command_list, 'xlogo')
    with patch.object(starter, 'process_job', return_value=False) as mocked_jobs:
        assert starter.start_process(StartingStrategies.CONFIG, xlogo_command.process, 'extra_args')
        assert starter.current_jobs == {}
        assert mocked_jobs.call_count == 1
        args, kwargs = mocked_jobs.call_args
        assert args[0].strategy == StartingStrategies.CONFIG
        assert args[0].extra_args == 'extra_args'
        assert args[0].ignore_wait_exit


def test_starter_start_process_success(starter, command_list):
    """ Test the Starter.start_process method in success case. """
    from supvisors.ttypes import StartingStrategies
    xlogo_command = get_test_command(command_list, 'xlogo')

    # test success
    def success_job(*args, **_):
        args[1].append(args[0])
        return True

    with patch.object(starter, 'process_job', side_effect=success_job) as mocked_jobs:
        assert not starter.start_process(StartingStrategies.CONFIG, xlogo_command.process, 'extra_args')
        assert mocked_jobs.call_count == 1
        args1, _ = mocked_jobs.call_args
        assert args1[0].strategy == StartingStrategies.CONFIG
        assert args1[0].extra_args == 'extra_args'
        assert args1[0].ignore_wait_exit
        assert starter.current_jobs == {'sample_test_1': [args1[0]]}
        mocked_jobs.reset_mock()
        # get another process
        yeux_command = get_test_command(command_list, 'yeux_00')
        # test that success complements current_jobs
        assert not starter.start_process(StartingStrategies.MOST_LOADED, yeux_command.process, '')
        assert mocked_jobs.call_count == 1
        args2, _ = mocked_jobs.call_args
        assert args2[0].strategy == StartingStrategies.MOST_LOADED
        assert args2[0].extra_args == ''
        assert args2[0].ignore_wait_exit
        assert starter.current_jobs == {'sample_test_1': [args1[0]], 'sample_test_2': [args2[0]]}


def test_starter_default_start_process(starter):
    """ Test the Starter.default_start_process method. """
    with patch.object(starter, 'start_process', return_value=True) as mocked_start:
        # test that default_start_process just calls start_process with the default strategy
        process = Mock()
        assert starter.default_start_process(process)
        assert mocked_start.call_args_list == [call(starter.supvisors.options.starting_strategy, process)]


def test_starter_start_application(starter, command_list):
    """ Test the Starter.start_application method. """
    from supvisors.ttypes import ApplicationStates, StartingStrategies
    # create application start_sequence
    appli = create_application('sample_test_1', starter.supvisors)
    for command in command_list:
        if command.process.application_name == 'sample_test_1':
            appli.start_sequence.setdefault(len(command.process.namespec()) % 3, []).append(command.process)
    # patch the starter.process_application_jobs
    with patch.object(starter, 'process_application_jobs') as mocked_jobs:
        # test start_application on a running application
        appli._state = ApplicationStates.RUNNING
        assert starter.start_application(StartingStrategies.LESS_LOADED, appli)
        assert starter.planned_sequence == {}
        assert starter.planned_jobs == {}
        assert not mocked_jobs.called
        # test start_application on a stopped application
        appli._state = ApplicationStates.STOPPED
        assert not starter.start_application(StartingStrategies.LESS_LOADED, appli)
        # only planned jobs and not current jobs because of process_application_jobs patch
        assert starter.planned_sequence == {}
        expected = {'sample_test_1': {1: ['sample_test_1:xfontsel', 'sample_test_1:xlogo'],
                                      2: ['sample_test_1:xclock']}}
        assert starter.printable_planned_jobs() == expected
        assert mocked_jobs.call_args_list == [call('sample_test_1')]
        # check strategy applied
        for proc_list in starter.planned_jobs['sample_test_1'].values():
            for proc in proc_list:
                assert proc.strategy == StartingStrategies.LESS_LOADED


def test_starter_default_start_application(starter):
    """ Test the Starter.default_start_application method. """
    with patch.object(starter, 'start_application', return_value=True) as mocked_start:
        # test that default_start_application just calls start_application with the default strategy
        application = Mock()
        assert starter.default_start_application(application)
        assert mocked_start.call_args_list == [call(starter.supvisors.options.starting_strategy, application)]


def test_starter_start_applications(starter, command_list):
    """ Test the start_applications method. """
    from supvisors.ttypes import ApplicationStates
    # create one running application
    application = create_application('sample_test_1', starter.supvisors)
    application._state = ApplicationStates.RUNNING
    starter.supvisors.context.applications['sample_test_1'] = application
    # create one stopped application with a start_sequence > 0
    application = create_application('sample_test_2', starter.supvisors)
    application.rules.start_sequence = 2
    for command in command_list:
        if command.process.application_name == 'sample_test_2':
            application.start_sequence.setdefault(len(command.process.namespec()) % 3, []).append(command.process)
    starter.supvisors.context.applications['sample_test_2'] = application
    # create one stopped application with a start_sequence == 0
    application = create_application('crash', starter.supvisors)
    application.rules.start_sequence = 0
    starter.supvisors.context.applications['crash'] = application
    # call starter start_applications and check that only sample_test_2 is triggered
    with patch.object(starter, 'process_application_jobs') as mocked_jobs:
        starter.start_applications()
        assert starter.planned_sequence == {}
        assert starter.printable_planned_jobs() == {'sample_test_2': {1: ['sample_test_2:sleep']}}
        # current jobs is empty because of process_application_jobs mocking
        assert starter.printable_current_jobs() == {}
        assert mocked_jobs.call_args_list == [call('sample_test_2')]


# Stopper part
@pytest.fixture
def stopper(supvisors):
    """ Create the Stopper instance to test. """
    from supvisors.commander import Stopper
    return Stopper(supvisors)


def test_stopper_create(stopper):
    """ Test the values set at construction of Stopper. """
    from supvisors.commander import Commander
    assert isinstance(stopper, Commander)


@patch('supvisors.commander.Commander.check_progress', return_value=True)
def test_stopper_check_stopping(mocked_check: Mock, stopper):
    """ Test the Stopper.check_stopping method. """
    assert stopper.check_stopping()
    assert mocked_check.call_args_list == [call('running', ProcessStates.UNKNOWN)]


@patch('supvisors.commander.Stopper.after_event')
def test_stopper_on_event(mocked_after: Mock, stopper, command_list):
    """ Test the Stopper.on_event method. """
    # set context in current_jobs
    for command in command_list:
        stopper.current_jobs.setdefault(command.process.application_name, []).append(command)
    # add application context
    application = create_application('sample_test_1', stopper.supvisors)
    stopper.supvisors.context.applications['sample_test_1'] = application
    application = create_application('sample_test_2', stopper.supvisors)
    stopper.supvisors.context.applications['sample_test_2'] = application
    # try with unknown application
    process = create_process({'group': 'dummy_application', 'name': 'dummy_process'}, stopper.supvisors)
    stopper.on_event(process)
    assert not mocked_after.called
    # with sample_test_1 application
    # test STOPPED process
    command = get_test_command(command_list, 'xlogo')
    assert command in stopper.current_jobs['sample_test_1']
    stopper.on_event(command.process)
    assert command.process not in stopper.current_jobs['sample_test_1']
    assert not mocked_after.called
    # test STOPPING process: xclock
    command = get_test_command(command_list, 'xclock')
    assert command in stopper.current_jobs['sample_test_1']
    stopper.on_event(command.process)
    assert command in stopper.current_jobs['sample_test_1']
    assert not mocked_after.called
    # test RUNNING process: xfontsel
    command = get_test_command(command_list, 'xfontsel')
    assert command in stopper.current_jobs['sample_test_1']
    stopper.on_event(command.process)
    assert 'sample_test_1' in stopper.current_jobs.keys()
    assert not mocked_after.called
    # with sample_test_2 application
    # test EXITED / expected process: yeux_00
    command = get_test_command(command_list, 'yeux_00')
    assert command in stopper.current_jobs['sample_test_2']
    stopper.on_event(command.process)
    assert command not in stopper.current_jobs['sample_test_2']
    assert not mocked_after.called
    # test FATAL process: sleep
    command = get_test_command(command_list, 'sleep')
    assert command in stopper.current_jobs['sample_test_2']
    stopper.on_event(command.process)
    assert 'sample_test_2' in stopper.current_jobs.keys()
    assert not mocked_after.called
    # test RUNNING process: yeux_01
    command = get_test_command(command_list, 'yeux_01')
    assert command in stopper.current_jobs['sample_test_2']
    stopper.on_event(command.process)
    assert command in stopper.current_jobs['sample_test_2']
    assert not mocked_after.called
    # force yeux_01 state and re-test
    command.process._state = ProcessStates.STOPPED
    assert command in stopper.current_jobs['sample_test_2']
    stopper.on_event(command.process)
    assert command not in stopper.current_jobs['sample_test_2']
    assert mocked_after.call_args_list == [call('sample_test_2')]
    # reset resources
    mocked_after.reset_mock()
    # with crash application
    # test STARTING process: late_segv
    command = get_test_command(command_list, 'late_segv')
    assert command in stopper.current_jobs['crash']
    stopper.on_event(command.process)
    assert command in stopper.current_jobs['crash']
    assert not mocked_after.called
    # test BACKOFF process: segv (last process of this application)
    command = get_test_command(command_list, 'segv')
    assert command in stopper.current_jobs['crash']
    stopper.on_event(command.process)
    assert command in stopper.current_jobs['crash']
    assert not mocked_after.called


def test_stopper_store_application_stop_sequence(stopper, command_list):
    """ Test the Stopper.store_application_stop_sequence method. """
    # create 2 application start_sequences
    appli1 = create_application('sample_test_1', stopper.supvisors)
    for command in command_list:
        if command.process.application_name == 'sample_test_1':
            appli1.stop_sequence.setdefault(len(command.process.namespec()) % 3, []).append(command.process)
    appli2 = create_application('sample_test_2', stopper.supvisors)
    for command in command_list:
        if command.process.application_name == 'sample_test_2':
            appli2.stop_sequence.setdefault(len(command.process.namespec()) % 3, []).append(command.process)
    # call method and check result
    stopper.store_application_stop_sequence(appli1)
    # check application sequence in stopper planned sequence
    expected = {0: {'sample_test_1': {1: ['sample_test_1:xfontsel', 'sample_test_1:xlogo'],
                                      2: ['sample_test_1:xclock']}}}
    assert stopper.printable_planned_sequence() == expected
    # call method a second time and check result
    stopper.store_application_stop_sequence(appli2)
    # check application sequence in stopper planned sequence
    expected = {0: {'sample_test_1': {1: ['sample_test_1:xfontsel', 'sample_test_1:xlogo'],
                                      2: ['sample_test_1:xclock']},
                    'sample_test_2': {0: ['sample_test_2:yeux_00', 'sample_test_2:yeux_01'],
                                      1: ['sample_test_2:sleep']}}}
    assert stopper.printable_planned_sequence() == expected


def test_stopper_process_job(stopper, command_list):
    """ Test the Stopper.process_job method. """
    # get patches
    mocked_pusher = stopper.supvisors.zmq.pusher.send_stop_process
    # test with stopped process
    process = get_test_command(command_list, 'xlogo')
    jobs = []
    stopper.process_job(process, jobs)
    assert jobs == []
    assert not mocked_pusher.called
    # test with running process
    process = get_test_command(command_list, 'xfontsel')
    jobs = []
    stopper.process_job(process, jobs)
    assert jobs == [process]
    assert mocked_pusher.call_args_list == [call('10.0.0.1', 'sample_test_1:xfontsel')]


def test_stopper_stop_process_failure(stopper, command_list):
    """ Test the Stopper.stop_process method in a failure case. """
    xlogo_command = get_test_command(command_list, 'xlogo')
    # test failure
    with patch.object(stopper, 'process_job', return_value=False) as mocked_jobs:
        assert stopper.stop_process(xlogo_command.process)
        assert stopper.current_jobs == {}
        assert mocked_jobs.call_count == 1


def test_stopper_stop_process_success(stopper, command_list):
    """ Test the Stopper.stop_process method in a success case. """
    xlogo_command = get_test_command(command_list, 'xlogo')

    # test success
    def success_job(*args, **_):
        args[1].append(args[0])
        return True

    with patch.object(stopper, 'process_job', side_effect=success_job) as mocked_jobs:
        assert not stopper.stop_process(xlogo_command.process)
        assert mocked_jobs.call_count == 1
        args1, _ = mocked_jobs.call_args
        assert stopper.current_jobs == {'sample_test_1': [args1[0]]}
        mocked_jobs.reset_mock()
        # get any other process
        yeux_command = get_test_command(command_list, 'yeux_00')
        # test that success complements current_jobs
        assert not stopper.stop_process(yeux_command.process)
        assert mocked_jobs.call_count == 1
        args2, _ = mocked_jobs.call_args
        assert stopper.current_jobs == {'sample_test_1': [args1[0]], 'sample_test_2': [args2[0]]}


def test_stopper_stop_application(stopper, command_list):
    """ Test the Stopper.stop_application method. """
    from supvisors.ttypes import ApplicationStates
    # create application start_sequence
    appli = create_application('sample_test_1', stopper.supvisors)
    for command in command_list:
        if command.process.application_name == 'sample_test_1':
            appli.stop_sequence.setdefault(len(command.process.namespec()) % 3, []).append(command.process)

    # patch the starter.process_application_jobs
    def success_job(*args, **_):
        args[1].append(args[0])

    with patch.object(stopper, 'process_job', side_effect=success_job) as mocked_jobs:
        # test start_application on a stopped application
        appli._state = ApplicationStates.STOPPED
        assert stopper.stop_application(appli)
        assert stopper.planned_sequence == {}
        assert stopper.planned_jobs == {}
        assert stopper.current_jobs == {}
        assert not mocked_jobs.called
        # test start_application on a stopped application
        appli._state = ApplicationStates.RUNNING
        assert not stopper.stop_application(appli)
        # only planned jobs and not current jobs because of process_application_jobs patch
        assert stopper.planned_sequence == {}
        assert stopper.printable_planned_jobs() == {'sample_test_1': {2: ['sample_test_1:xclock']}}
        assert stopper.printable_current_jobs() == {'sample_test_1': ['sample_test_1:xfontsel', 'sample_test_1:xlogo']}
        assert mocked_jobs.call_count == 2


def test_stopper_stop_applications(stopper, command_list):
    """ Test the Stopper.stop_applications method. """
    from supvisors.ttypes import ApplicationStates
    # create one running application with a start_sequence > 0
    appli = create_application('sample_test_1', stopper.supvisors)
    appli._state = ApplicationStates.RUNNING
    appli.rules.stop_sequence = 2
    stopper.supvisors.context.applications['sample_test_1'] = appli
    for command in command_list:
        if command.process.application_name == 'sample_test_1':
            appli.stop_sequence.setdefault(len(command.process.namespec()) % 3, []).append(command.process)
    # create one stopped application
    appli = create_application('sample_test_2', stopper.supvisors)
    stopper.supvisors.context.applications['sample_test_2'] = appli
    # create one running application with a start_sequence == 0
    appli = create_application('crash', stopper.supvisors)
    appli._state = ApplicationStates.RUNNING
    appli.rules.stop_sequence = 0
    stopper.supvisors.context.applications['crash'] = appli
    for command in command_list:
        if command.process.application_name == 'crash':
            appli.stop_sequence.setdefault(len(command.process.namespec()) % 3, []).append(command.process)
    # call starter start_applications and check that only sample_test_2 is triggered
    with patch.object(stopper, 'process_application_jobs') as mocked_jobs:
        stopper.stop_applications()
        expected = {2: {'sample_test_1': {1: ['sample_test_1:xfontsel', 'sample_test_1:xlogo'],
                                          2: ['sample_test_1:xclock']}}}
        assert stopper.printable_planned_sequence() == expected
        assert stopper.printable_planned_jobs() == {'crash': {0: ['crash:late_segv'], 1: ['crash:segv']}}
        # current jobs is empty because of process_application_jobs mocking
        assert stopper.printable_current_jobs() == {}
        assert mocked_jobs.call_args_list == [call('crash')]
