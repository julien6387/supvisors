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

from supvisors.application import *

from .base import (database_copy, any_process_info, any_stopped_process_info,
                   any_running_process_info, any_process_info_by_state)
from .conftest import create_application, create_process


# ApplicationRules part
@pytest.fixture
def rules():
    """ Return the instance to test. """
    return ApplicationRules()


def test_rules_create(rules):
    """ Test the values set at construction. """
    # check application default rules
    assert not rules.managed
    assert rules.start_sequence == 0
    assert rules.stop_sequence == 0
    assert rules.starting_failure_strategy == StartingFailureStrategies.ABORT
    assert rules.running_failure_strategy == RunningFailureStrategies.CONTINUE


def test_rules_str(rules):
    """ Test the string output. """
    assert str(rules) == 'managed=False start_sequence=0 stop_sequence=0'\
                         ' starting_failure_strategy=ABORT running_failure_strategy=CONTINUE'


def test_rules_serial(rules):
    """ Test the serialization of the ApplicationRules object. """
    assert rules.serial() == {'managed': False, 'start_sequence': 0, 'stop_sequence': 0,
                              'starting_failure_strategy': 'ABORT', 'running_failure_strategy': 'CONTINUE'}


# ApplicationStatus part
def test_application_create(supvisors):
    """ Test the values set at construction. """
    application = create_application('ApplicationTest', supvisors)
    # check application default attributes
    assert application.application_name == 'ApplicationTest'
    assert application.state == ApplicationStates.STOPPED
    assert not application.major_failure
    assert not application.minor_failure
    assert not application.start_failure
    assert not application.processes
    assert not application.start_sequence
    assert not application.stop_sequence
    # check application default rules
    assert not application.rules.managed
    assert application.rules.start_sequence == 0
    assert application.rules.stop_sequence == 0
    assert application.rules.starting_failure_strategy == StartingFailureStrategies.ABORT
    assert application.rules.running_failure_strategy == RunningFailureStrategies.CONTINUE


def test_application_running(supvisors):
    """ Test the running method. """
    application = create_application('ApplicationTest', supvisors)
    assert not application.running()
    # add a stopped process
    info = any_stopped_process_info()
    process = create_process(info, supvisors)
    process.add_info('10.0.0.1', info)
    application.add_process(process)
    application.update_status()
    assert not application.running()
    # add a running process
    info = any_running_process_info()
    process = create_process(info, supvisors)
    process.add_info('10.0.0.1', info)
    application.add_process(process)
    application.update_status()
    assert application.running()


def test_application_stopped(supvisors):
    """ Test the ApplicationStatus.stopped method. """
    application = create_application('ApplicationTest', supvisors)
    assert application.stopped()
    # add a stopped process
    info = any_stopped_process_info()
    process = create_process(info, supvisors)
    process.add_info('10.0.0.1', info)
    application.add_process(process)
    application.update_status()
    assert application.stopped()
    # add a running process
    info = any_running_process_info()
    process = create_process(info, supvisors)
    process.add_info('10.0.0.1', info)
    application.add_process(process)
    application.update_status()
    assert not application.stopped()


def test_application_never_started(supvisors):
    """ Test the ApplicationStatus.never_started method. """
    application = create_application('ApplicationTest', supvisors)
    assert application.never_started()
    # add a stopped process that has already been started
    info = any_stopped_process_info()
    process = create_process(info, supvisors)
    process.add_info('10.0.0.1', info)
    application.add_process(process)
    application.update_status()
    assert not application.never_started()


def test_application_get_operational_status(supvisors):
    """ Test the ApplicationStatus.get_operational_status method used to get a descriptive operational status. """
    # create address status instance
    application = create_application('ApplicationTest', supvisors)
    # test with non RUNNING application
    for state in [ApplicationStates.STOPPED, ApplicationStates.STARTING, ApplicationStates.STOPPING]:
        for minor_failure in [True, False]:
            for major_failure in [True, False]:
                application._state = state
                application.major_failure = major_failure
                application.minor_failure = minor_failure
                application.start_failure = False
                assert application.get_operational_status() == ''
    # test with RUNNING application
    application._state = ApplicationStates.RUNNING
    # no failure
    application.major_failure = False
    application.minor_failure = False
    application.start_failure = False
    assert application.get_operational_status() == 'Operational'
    # minor failure, no major failure
    application.major_failure = False
    application.minor_failure = True
    application.start_failure = False
    assert application.get_operational_status() == 'Degraded'
    # major failure set
    application.major_failure = True
    application.start_failure = False
    for minor_failure in [True, False]:
        application.minor_failure = minor_failure
        assert application.get_operational_status() == 'Not Operational'


def test_application_serial(supvisors):
    """ Test the serial method used to get a serializable form of Application. """
    import pickle
    # create address status instance
    application = create_application('ApplicationTest', supvisors)
    application._state = ApplicationStates.RUNNING
    application.major_failure = False
    application.minor_failure = True
    application.start_failure = False
    # test to_json method
    serialized = application.serial()
    assert serialized == {'application_name': 'ApplicationTest', 'statecode': 2, 'statename': 'RUNNING',
                          'major_failure': False, 'minor_failure': True}
    # test that returned structure is serializable using pickle
    dumped = pickle.dumps(serialized)
    loaded = pickle.loads(dumped)
    assert serialized == loaded


def test_application_add_process(supvisors):
    """ Test the add_process method. """
    application = create_application('ApplicationTest', supvisors)
    # add a process to the application
    info = any_process_info()
    process = create_process(info, supvisors)
    process.add_info('10.0.0.1', info)
    application.add_process(process)
    # check that process is stored
    assert process.process_name in application.processes
    assert process is application.processes[process.process_name]


@pytest.fixture
def filled_application(supvisors):
    """ Create an ApplicationStatus and add all processes of the database. """
    application = create_application('ApplicationTest', supvisors)
    for info in database_copy():
        process = create_process(info, supvisors)
        process.add_info('10.0.0.1', info)
        # set random sequence to process
        process.rules.start_sequence = random.randint(0, 2)
        process.rules.stop_sequence = random.randint(0, 2)
        application.add_process(process)
    return application


def test_application_update_sequences(filled_application):
    """ Test the sequencing of the update_sequences method. """
    # call the sequencer
    filled_application.update_sequences()
    # check the sequencing of the starting
    sequences = sorted({process.rules.start_sequence for process in filled_application.processes.values()})
    # as key is an integer, the sequence dictionary should be sorted but doesn't work in Travis-CI
    for sequence, processes in sorted(filled_application.start_sequence.items()):
        assert sequence == sequences.pop(0)
        assert sorted(processes, key=lambda x: x.process_name) == \
               sorted([proc for proc in filled_application.processes.values()
                       if sequence == proc.rules.start_sequence], key=lambda x: x.process_name)
    # check the sequencing of the stopping
    sequences = sorted({process.rules.stop_sequence for process in filled_application.processes.values()})
    # as key is an integer, the sequence dictionary should be sorted but doesn't work in Travis-CI
    for sequence, processes in sorted(filled_application.stop_sequence.items()):
        assert sequence == sequences.pop(0)
        assert sorted(processes, key=lambda x: x.process_name) == \
               sorted([proc for proc in filled_application.processes.values()
                       if sequence == proc.rules.stop_sequence], key=lambda x: x.process_name)


def test_check_start_sequence(supvisors):
    """ Test the result of the check_start_sequence method. """
    application = create_application('ApplicationTest', supvisors)
    assert not application.start_failure
    # add processes from test database so that there is no crash
    for info in [any_running_process_info(), any_process_info_by_state(ProcessStates.STOPPED)]:
        process = create_process(info, supvisors)
        process.add_info('10.0.0.1', info)
        process.rules.start_sequence = random.randint(1, 5)
        application.add_process(process)
    # call the sequencer and checker
    application.update_sequences()
    application.check_start_sequence()
    # test method
    assert not application.start_failure
    # add processes from test database so that there is a crash
    info = any_process_info_by_state(ProcessStates.FATAL)
    process = create_process(info, supvisors)
    process.add_info('10.0.0.1', info)
    process.rules.start_sequence = 2
    application.add_process(process)
    # call the sequencer
    application.update_sequences()
    application.check_start_sequence()
    # test method
    assert application.start_failure


def test_application_update_status(filled_application):
    """ Test the rules to update the status of the application method. """
    # init status
    # there are lots of states but the 'strongest' is STARTING
    # STARTING is a 'running' state so major/minor failures are applicable
    filled_application.update_status()
    assert filled_application.state == ApplicationStates.STARTING
    # there is a FATAL state in the process database
    # no rule is set for processes, so there are only minor failures
    assert not filled_application.major_failure
    assert filled_application.minor_failure
    # set FATAL process to major
    fatal_process = next((process for process in filled_application.processes.values()
                          if process.state == ProcessStates.FATAL), None)
    fatal_process.rules.required = True
    # update status. major failure is now expected
    filled_application.update_status()
    assert filled_application.state == ApplicationStates.STARTING
    assert filled_application.major_failure
    assert not filled_application.minor_failure
    # set STARTING process to RUNNING
    starting_process = next((process for process in filled_application.processes.values()
                             if process.state == ProcessStates.STARTING), None)
    starting_process.state = ProcessStates.RUNNING
    # update status. there is still one BACKOFF process leading to STARTING application
    filled_application.update_status()
    assert filled_application.state == ApplicationStates.STARTING
    assert filled_application.major_failure
    assert not filled_application.minor_failure
    # set BACKOFF process to EXITED
    backoff_process = next((process for process in filled_application.processes.values()
                            if process.state == ProcessStates.BACKOFF), None)
    backoff_process.state = ProcessStates.EXITED
    # update status. the 'strongest' state is now STOPPING
    # as STOPPING is not a 'running' state, failures are not applicable
    filled_application.update_status()
    assert filled_application.state == ApplicationStates.STOPPING
    assert not filled_application.major_failure
    assert not filled_application.minor_failure
    # set STOPPING process to STOPPED
    stopping_process = next((process for process in filled_application.processes.values()
                             if process.state == ProcessStates.STOPPING), None)
    stopping_process.state = ProcessStates.STOPPED
    # update status. the 'strongest' state is now RUNNING
    # failures are applicable again
    filled_application.update_status()
    assert filled_application.state == ApplicationStates.RUNNING
    assert filled_application.major_failure
    assert not filled_application.minor_failure
    # set RUNNING processes to STOPPED
    for process in filled_application.processes.values():
        if process.state == ProcessStates.RUNNING:
            process.state = ProcessStates.STOPPED
    # update status. the 'strongest' state is now RUNNING
    # failures are not applicable anymore
    filled_application.update_status()
    assert filled_application.state == ApplicationStates.STOPPED
    assert not filled_application.major_failure
    assert not filled_application.minor_failure
