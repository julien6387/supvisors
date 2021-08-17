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

from .base import database_copy, any_process_info, any_stopped_process_info, any_process_info_by_state
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
    assert rules.distributed
    assert rules.node_names == ['*']
    assert rules.start_sequence == 0
    assert rules.stop_sequence == 0
    assert rules.starting_strategy == StartingStrategies.CONFIG
    assert rules.starting_failure_strategy == StartingFailureStrategies.ABORT
    assert rules.running_failure_strategy == RunningFailureStrategies.CONTINUE


def test_rules_str(rules):
    """ Test the string output. """
    assert str(rules) == "managed=False distributed=True node_names=['*'] start_sequence=0 stop_sequence=0"\
                         " starting_strategy=CONFIG starting_failure_strategy=ABORT running_failure_strategy=CONTINUE"


def test_rules_serial(rules):
    """ Test the serialization of the ApplicationRules object. """
    # default is not managed so result is short
    assert rules.serial() == {'managed': False}
    # check managed and distributed
    rules.managed = True
    assert rules.serial() == {'managed': True, 'distributed': True,
                              'start_sequence': 0, 'stop_sequence': 0,
                              'starting_strategy': 'CONFIG', 'starting_failure_strategy': 'ABORT',
                              'running_failure_strategy': 'CONTINUE'}
    # finally check managed and not distributed
    rules.distributed = False
    assert rules.serial() == {'managed': True, 'distributed': False, 'addresses': ['*'],
                              'start_sequence': 0, 'stop_sequence': 0,
                              'starting_strategy': 'CONFIG', 'starting_failure_strategy': 'ABORT',
                              'running_failure_strategy': 'CONTINUE'}


# ApplicationStatus part
def test_application_create(supvisors):
    """ Test the values set at construction. """
    application = create_application('ApplicationTest', supvisors)
    # check application default attributes
    assert application.application_name == 'ApplicationTest'
    assert application.state == ApplicationStates.STOPPED
    assert not application.major_failure
    assert not application.minor_failure
    assert not application.processes
    assert not application.start_sequence
    assert not application.stop_sequence
    # check application default rules
    assert not application.rules.managed
    assert application.rules.distributed
    assert application.rules.start_sequence == 0
    assert application.rules.stop_sequence == 0
    assert application.rules.starting_failure_strategy == StartingFailureStrategies.ABORT
    assert application.rules.running_failure_strategy == RunningFailureStrategies.CONTINUE


def test_application_running(supvisors):
    """ Test the running method. """
    application = create_application('ApplicationTest', supvisors)
    assert not application.running()
    # loop on all states
    for state in ApplicationStates:
        application._state = state
        assert application.running() == (state in [ApplicationStates.STARTING, ApplicationStates.RUNNING])


def test_application_stopped(supvisors):
    """ Test the ApplicationStatus.stopped method. """
    application = create_application('ApplicationTest', supvisors)
    assert application.stopped()
    # loop on all states
    for state in ApplicationStates:
        application._state = state
        assert application.stopped() == (state == ApplicationStates.STOPPED)


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


def test_application_has_running_processes(supvisors):
    """ Test the ApplicationStatus.has_running_processes method used to know if at least one process is RUNNING. """
    application = create_application('ApplicationTest', supvisors)
    assert not application.has_running_processes()
    # add a stopped process
    info = any_stopped_process_info()
    process = create_process(info, supvisors)
    process.add_info('10.0.0.1', info)
    application.add_process(process)
    application.update_status()
    assert application.stopped()
    assert not application.has_running_processes()
    # add a running process
    info = any_process_info_by_state(ProcessStates.RUNNING)
    process = create_process(info, supvisors)
    process.add_info('10.0.0.1', info)
    application.add_process(process)
    application.update_status()
    assert application.stopped()
    assert application.has_running_processes()


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


def test_application_possible_nodes(supvisors):
    """ Test the ApplicationStatus.possible_nodes method. """
    application = create_application('ApplicationTest', supvisors)
    # add a process to the application
    info = any_process_info_by_state(ProcessStates.STARTING)
    process1 = create_process(info, supvisors)
    for node_name in ['10.0.0.2', '10.0.0.3', '10.0.0.4']:
        process1.add_info(node_name, info)
    application.add_process(process1)
    # add another process to the application
    info = any_stopped_process_info()
    process2 = create_process(info, supvisors)
    for node_name in ['10.0.0.1', '10.0.0.4']:
        process2.add_info(node_name, info)
    application.add_process(process2)
    # default node_names is '*' in process rules
    assert application.possible_nodes() == ['10.0.0.4']
    # set a subset of node_names in process rules so that there's no intersection with received status
    application.rules.node_names = ['10.0.0.1', '10.0.0.2']
    assert application.possible_nodes() == []
    # increase received status
    process1.add_info('10.0.0.1', info)
    assert application.possible_nodes() == ['10.0.0.1']
    # reset rules
    application.rules.node_names = ['*']
    assert application.possible_nodes() == ['10.0.0.1', '10.0.0.4']
    # test with full status and all nodes in rules
    for node_name in supvisors.address_mapper.node_names:
        process1.add_info(node_name, info)
        process2.add_info(node_name, info)
    assert application.possible_nodes() == supvisors.address_mapper.node_names
    # restrict again nodes in rules
    application.rules.node_names = ['10.0.0.5']
    assert application.possible_nodes() == ['10.0.0.5']


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
    # by default, applications are unmanaged so start sequence is empty
    assert not filled_application.start_sequence
    assert filled_application.stop_sequence
    # stop sequence contents is tested afterwards
    # force application to managed and call sequencer again
    filled_application.rules.managed = True
    filled_application.update_sequences()
    # as key is an integer, the sequence dictionary should be sorted but doesn't work in Travis-CI
    assert filled_application.start_sequence
    assert filled_application.stop_sequence
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


def test_application_get_start_sequence_expected_load(filled_application):
    """ Test the ApplicationStatus.get_start_sequence_expected_load method. """
    # as sequences are empty, total is 0
    assert filled_application.get_start_sequence_expected_load() == 0
    # set application to managed, update sequences and status
    filled_application.rules.managed = True
    filled_application.update_sequences()
    # process rules still have a expected_load set to 0
    assert filled_application.get_start_sequence_expected_load() == 0
    print(ApplicationStatus.printable_sequence(filled_application.start_sequence))
    # update all process loads to 10
    for proc_list in filled_application.start_sequence.values():
        for process in proc_list:
            process.rules.expected_load = 10
    seq_0_size = len(filled_application.start_sequence.get(0, []))
    seq_1_2_size = len(filled_application.processes) - seq_0_size
    assert filled_application.get_start_sequence_expected_load() == 10 * seq_1_2_size


def test_application_update_status(filled_application):
    """ Test the rules to update the status of the application method. """
    # as application is not managed, application is STOPPED there are no failures
    filled_application.update_status()
    assert filled_application.state == ApplicationStates.STOPPED
    assert not filled_application.major_failure
    assert not filled_application.minor_failure
    # set application to managed, update sequences and status
    filled_application.rules.managed = True
    filled_application.update_sequences()
    filled_application.update_status()
    # there is a process in STOPPING state in the process database
    # STOPPING has the highest priority in application state evaluation
    assert filled_application.state == ApplicationStates.STOPPING
    # multiple STOPPED processes and global state not STOPPED
    # in default rules, no process is required so this is minor
    assert not filled_application.major_failure
    assert filled_application.minor_failure
    # set FATAL process to major
    fatal_process = next((process for process in filled_application.processes.values()
                          if process.state == ProcessStates.FATAL))
    fatal_process.rules.required = True
    # update status. major failure is now expected
    # minor still expected
    filled_application.update_status()
    assert filled_application.state == ApplicationStates.STOPPING
    assert filled_application.major_failure
    assert not filled_application.minor_failure
    # set STOPPING process to STOPPED
    for process in filled_application.processes.values():
        if process.state == ProcessStates.STOPPING:
            process.state = ProcessStates.STOPPED
    # now STARTING is expected as it is the second priority
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
    # set BACKOFF process to EXITED unexpected
    backoff_process = next((process for process in filled_application.processes.values()
                            if process.state == ProcessStates.BACKOFF), None)
    backoff_process.state = ProcessStates.EXITED
    backoff_process.expected_exit = False
    # update status. now there is only stopped and running processes.
    filled_application.update_status()
    assert filled_application.state == ApplicationStates.RUNNING
    assert filled_application.major_failure
    assert filled_application.minor_failure
    # set all process to RUNNING
    for process in filled_application.processes.values():
        process.state = ProcessStates.RUNNING
    # no more failures
    filled_application.update_status()
    assert filled_application.state == ApplicationStates.RUNNING
    assert not filled_application.major_failure
    assert not filled_application.minor_failure
    # set all processes to STOPPED
    for process in filled_application.processes.values():
        process.state = ProcessStates.STOPPED
    # all processes are STOPPED in a STOPPED application, so no failure
    filled_application.update_status()
    assert filled_application.state == ApplicationStates.STOPPED
    assert not filled_application.major_failure
    assert not filled_application.minor_failure
