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

import random
import sys
from socket import getfqdn
from unittest.mock import call

import pytest

from supvisors.application import *
from .base import database_copy, process_info_by_name, any_stopped_process_info, any_process_info_by_state
from .conftest import create_application, create_process


# ApplicationRules part
@pytest.fixture
def rules(supvisors):
    """ Return the instance to test. """
    return ApplicationRules(supvisors)


def test_rules_create(rules):
    """ Test the values set at construction. """
    # check application default rules
    assert not rules.managed
    assert rules.distribution == DistributionRules.ALL_INSTANCES
    assert rules.identifiers == ['*']
    assert rules.hash_identifiers == []
    assert rules.start_sequence == 0
    assert rules.stop_sequence == -1
    assert rules.starting_strategy == StartingStrategies.CONFIG
    assert rules.starting_failure_strategy == StartingFailureStrategies.ABORT
    assert rules.running_failure_strategy == RunningFailureStrategies.CONTINUE
    assert rules.status_tree is None


def test_rules_check_stop_sequence(rules):
    """ Test the assignment of stop sequence to start sequence if default still set. """
    # test when default still used
    assert rules.start_sequence == 0
    assert rules.stop_sequence == -1
    rules.check_stop_sequence('crash')
    assert rules.start_sequence == 0
    assert rules.stop_sequence == 0
    # test when value has been set
    rules.start_sequence = 12
    rules.stop_sequence = 50
    rules.check_stop_sequence('crash')
    assert rules.start_sequence == 12
    assert rules.stop_sequence == 50


def test_rules_check_hash_identifiers(rules):
    """ Test the resolution of identifiers when hash_identifiers is set. """
    # set initial attributes
    rules.hash_identifiers = ['*']
    rules.identifiers = []
    rules.start_sequence = 1
    # 1. test with application without ending index
    rules.check_hash_identifiers('crash')
    # identifiers is unchanged and start_sequence is invalidated
    assert rules.hash_identifiers == ['*']
    assert rules.identifiers == []
    assert rules.start_sequence == 0
    # 2. test with application with 0-ending index
    rules.start_sequence = 1
    rules.check_hash_identifiers('sample_test_0')
    # identifiers is unchanged and start_sequence is invalidated
    assert rules.hash_identifiers == ['*']
    assert rules.identifiers == []
    assert rules.start_sequence == 0
    # 3. update rules to test '#' with all instances available
    # address '10.0.0.1' has an index of 1-1 in supvisors_mapper
    rules.start_sequence = 1
    rules.check_hash_identifiers('sample_test_1')
    assert rules.identifiers == ['10.0.0.1:25000']
    assert rules.start_sequence == 1
    # 4. update rules to test '#' with a subset of instances available
    rules.hash_identifiers = ['10.0.0.0:25000', '10.0.0.3:25000', '10.0.0.5:25000']
    rules.identifiers = []
    # here, at index 2-1 of this list, '10.0.0.5' can be found
    rules.check_hash_identifiers('sample_test_2')
    assert rules.identifiers == ['10.0.0.3:25000']
    assert rules.start_sequence == 1
    # 5. test the case where procnumber is greater than the subset list of instances available
    rules.hash_identifiers = ['10.0.0.1:25000']
    rules.identifiers = []
    rules.check_hash_identifiers('sample_test_2')
    assert rules.identifiers == ['10.0.0.1:25000']
    assert rules.start_sequence == 1


def test_rules_check_dependencies(mocker, rules):
    """ Test the dependencies in process rules. """
    mocked_stop = mocker.patch('supvisors.application.ApplicationRules.check_stop_sequence')
    mocked_hash = mocker.patch('supvisors.application.ApplicationRules.check_hash_identifiers')
    # test with no hash
    rules.hash_identifiers = []
    rules.check_dependencies('dummy')
    assert mocked_stop.call_args_list == [call('dummy')]
    assert not mocked_hash.called
    mocker.resetall()
    # test with hash
    rules.hash_identifiers = ['*']
    rules.check_dependencies('dummy')
    assert mocked_stop.call_args_list == [call('dummy')]
    assert mocked_hash.call_args_list == [call('dummy')]


def test_rules_str(rules):
    """ Test the string output. """
    assert str(rules) == ("managed=False distribution=ALL_INSTANCES identifiers=['*'] start_sequence=0 stop_sequence=-1"
                          " starting_strategy=CONFIG starting_failure_strategy=ABORT running_failure_strategy=CONTINUE"
                          " status_formula=None")


def test_rules_serial(rules):
    """ Test the serialization of the ApplicationRules object. """
    # default is not managed so result is short
    assert rules.serial() == {'managed': False}
    # check managed and distributed
    rules.managed = True
    assert rules.serial() == {'managed': True, 'distribution': 'ALL_INSTANCES', 'identifiers': ['*'],
                              'start_sequence': 0, 'stop_sequence': -1,
                              'starting_strategy': 'CONFIG', 'starting_failure_strategy': 'ABORT',
                              'running_failure_strategy': 'CONTINUE',
                              'status_formula': ''}
    # finally check managed and not distributed
    rules.distribution = DistributionRules.SINGLE_INSTANCE
    rules.status_formula = 'dumb and dumber'
    assert rules.serial() == {'managed': True, 'distribution': 'SINGLE_INSTANCE', 'identifiers': ['*'],
                              'start_sequence': 0, 'stop_sequence': -1,
                              'starting_strategy': 'CONFIG', 'starting_failure_strategy': 'ABORT',
                              'running_failure_strategy': 'CONTINUE',
                              'status_formula': 'dumb and dumber'}


# Homogeneous group part
def test_homogeneous_group_create(supvisors):
    """ Test the values set at construction. """
    group = HomogeneousGroup('yeux', supvisors)
    assert group.supvisors is supvisors
    assert group.program_name == 'yeux'
    assert group.at_identifiers is None
    assert group.hash_identifiers is None
    assert group.processes == []
    assert group.logger is supvisors.logger


def test_homogeneous_group_add_remove(supvisors):
    """ Test the HomogeneousGroup methods add_process and remove_process. """
    group = HomogeneousGroup('yeux', supvisors)
    # get 2 processes for test
    info = process_info_by_name('yeux_00')
    process_1 = create_process(info, supvisors)
    process_1.add_info('10.0.0.1', info)
    info = process_info_by_name('yeux_01')
    process_2 = create_process(info, supvisors)
    process_2.add_info('10.0.0.1', info)
    # 1. add a process with default rules to the application
    group.add_process(process_1)
    # check that process is stored
    assert process_1 in group.processes
    assert group.at_identifiers is None
    assert group.hash_identifiers is None
    # 2. test removal
    group.remove_process(process_1)
    # check that process is not stored anymore
    assert group.processes == []
    assert group.at_identifiers is None
    assert group.hash_identifiers is None
    # 3. add a process with hash rules to the application
    process_1.rules.hash_identifiers = ['10.0.0.1']
    group.add_process(process_1)
    # check that process is stored
    assert group.processes == [process_1]
    assert group.at_identifiers is None
    assert group.hash_identifiers == ['10.0.0.1']
    # 4. add a process with same program name and at rules to the application
    process_2.rules.hash_identifiers = ['10.0.0.2', '10.0.0.3']
    group.add_process(process_2)
    # check that process is stored
    assert group.processes == [process_1, process_2]
    assert group.at_identifiers is None
    assert group.hash_identifiers == ['10.0.0.2', '10.0.0.3']
    # 5. test removal
    group.remove_process(process_1)
    # check that process is not stored anymore
    assert group.processes == [process_2]
    assert group.at_identifiers is None
    assert group.hash_identifiers == ['10.0.0.2', '10.0.0.3']
    # 6. test removal
    group.remove_process(process_2)
    # check that process is not stored anymore
    assert group.processes == []
    assert group.at_identifiers is None
    assert group.hash_identifiers == ['10.0.0.2', '10.0.0.3']
    # 7. quickly test with at_identifiers (at prevail on hash)
    process_1.rules.at_identifiers = ['10.0.0.1']
    process_1.rules.hash_identifiers = []
    group.add_process(process_1)
    # check stored information
    assert group.processes == [process_1]
    assert group.at_identifiers == ['10.0.0.1']
    assert group.hash_identifiers is None
    # 8. second process with at identifier
    process_2.rules.at_identifiers = ['10.0.0.0']
    process_2.rules.hash_identifiers = []
    group.add_process(process_2)
    # check stored information
    assert group.processes == [process_1, process_2]
    assert group.at_identifiers == ['10.0.0.0']
    assert group.hash_identifiers is None


@pytest.fixture
def homogeneous_group(supvisors):
    """ Return the HomogeneousGroup instance to test. """
    group = HomogeneousGroup('yeux', supvisors)
    # add 2 processes of the same program
    info = process_info_by_name('yeux_00')
    process_1 = create_process(info, supvisors)
    process_1.add_info('10.0.0.1:25000', info)
    group.add_process(process_1)
    info = process_info_by_name('yeux_01')
    process_2 = create_process(info, supvisors)
    process_2.add_info('10.0.0.1:25000', info)
    group.add_process(process_2)
    return group


def test_homogeneous_group_resolve_at_wildcard(homogeneous_group):
    """ Test the HomogeneousGroup.assign_at_identifiers method with wildcard rules and no discovery mode. """
    # force at-* rules in processes and group
    homogeneous_group.at_identifiers = [WILDCARD]
    process_1 = homogeneous_group.processes[0]
    process_1.rules.at_identifiers = [WILDCARD]
    process_1.rules.identifiers = []
    process_2 = homogeneous_group.processes[1]
    process_2.rules.at_identifiers = [WILDCARD]
    process_2.rules.identifiers = []
    # 1. check assignment
    # the number of instance exceeds the number of processes
    homogeneous_group.resolve_rules()
    assert process_1.rules.at_identifiers == []
    assert process_1.rules.identifiers == ['10.0.0.1:25000']
    assert process_2.rules.at_identifiers == []
    assert process_2.rules.identifiers == ['10.0.0.2:25000']
    # 2. check no change with same call
    homogeneous_group.resolve_rules()
    assert process_1.rules.at_identifiers == []
    assert process_1.rules.identifiers == ['10.0.0.1:25000']
    assert process_2.rules.at_identifiers == []
    assert process_2.rules.identifiers == ['10.0.0.2:25000']
    # 3. in standard mode, the list of Supvisors instances cannot change
    #    but the number of processes in a homogeneous group can (update_numprocs XML-RPC)
    info = process_2.info_map['10.0.0.1:25000']
    info.update({'name': 'yeux_02', 'process_index': 2})
    process_3 = create_process(info, homogeneous_group.supvisors)
    process_3.add_info('10.0.0.1:25000', info)
    process_3.rules.at_identifiers = [WILDCARD]
    process_3.rules.identifiers = []
    homogeneous_group.add_process(process_3)
    # call new resolution
    homogeneous_group.resolve_rules()
    assert process_1.rules.at_identifiers == []
    assert process_1.rules.identifiers == ['10.0.0.1:25000']
    assert process_2.rules.at_identifiers == []
    assert process_2.rules.identifiers == ['10.0.0.2:25000']
    assert process_3.rules.at_identifiers == []
    assert process_3.rules.identifiers == ['10.0.0.3:25000']


def test_homogeneous_group_resolve_at_list(homogeneous_group):
    """ Test the HomogeneousGroup.assign_at_identifiers method. """
    # patch list of instances so that it is smaller than the list of processes
    mapper = homogeneous_group.supvisors.mapper
    ref_instances = mapper.instances.copy()
    mapper._instances = {'10.0.0.1:25000': ref_instances['10.0.0.1:25000']}
    # force at-* rules in processes and group
    homogeneous_group.at_identifiers = ['10.0.0.2:25000', '10.0.0.1:25000']
    process_1 = homogeneous_group.processes[0]
    process_1.rules.at_identifiers = ['10.0.0.2:25000', '10.0.0.1:25000']
    process_1.rules.identifiers = []
    process_2 = homogeneous_group.processes[1]
    process_2.rules.at_identifiers = ['10.0.0.2:25000', '10.0.0.1:25000']
    process_2.rules.identifiers = []
    # 1. check assignment
    # the number of instance exceeds the number of processes
    homogeneous_group.resolve_rules()
    assert process_1.rules.at_identifiers == []
    assert process_1.rules.identifiers == ['10.0.0.1:25000']
    assert process_2.rules.at_identifiers == ['10.0.0.2:25000', '10.0.0.1:25000']
    assert process_2.rules.identifiers == []
    # 2. check no change with same call
    homogeneous_group.resolve_rules()
    assert process_1.rules.at_identifiers == []
    assert process_1.rules.identifiers == ['10.0.0.1:25000']
    assert process_2.rules.at_identifiers == ['10.0.0.2:25000', '10.0.0.1:25000']
    assert process_2.rules.identifiers == []
    # 3. in discovery mode, the list of Supvisors instances may increase
    mapper._instances = {'10.0.0.1:25000': ref_instances['10.0.0.1:25000'],
                         '10.0.0.3:25000': ref_instances['10.0.0.3:25000'],
                         '10.0.0.2:25000': ref_instances['10.0.0.2:25000']}
    # call new resolution
    homogeneous_group.resolve_rules()
    assert process_1.rules.at_identifiers == []
    assert process_1.rules.identifiers == ['10.0.0.1:25000']
    assert process_2.rules.at_identifiers == []
    assert process_2.rules.identifiers == ['10.0.0.2:25000']


def test_homogeneous_group_resolve_hash_wildcard(homogeneous_group):
    """ Test the HomogeneousGroup.assign_at_identifiers method with wildcard rules and no discovery mode. """
    # patch list of instances so that it is smaller than the list of processes
    mapper = homogeneous_group.supvisors.mapper
    ref_instances = mapper.instances.copy()
    mapper._instances = {'10.0.0.1:25000': ref_instances['10.0.0.1:25000'],
                         '10.0.0.2:25000': ref_instances['10.0.0.2:25000']}
    # force hash-* rules in processes and group
    homogeneous_group.hash_identifiers = [WILDCARD]
    process_1 = homogeneous_group.processes[0]
    process_1.rules.hash_identifiers = [WILDCARD]
    process_1.rules.identifiers = []
    process_2 = homogeneous_group.processes[1]
    process_2.rules.hash_identifiers = [WILDCARD]
    process_2.rules.identifiers = []
    # 1. check assignment
    # the number of instance exceeds the number of processes
    homogeneous_group.resolve_rules()
    assert process_1.rules.hash_identifiers == []
    assert process_1.rules.identifiers == ['10.0.0.1:25000']
    assert process_2.rules.hash_identifiers == []
    assert process_2.rules.identifiers == ['10.0.0.2:25000']
    # 2. check no change with same call
    homogeneous_group.resolve_rules()
    assert process_1.rules.hash_identifiers == []
    assert process_1.rules.identifiers == ['10.0.0.1:25000']
    assert process_2.rules.hash_identifiers == []
    assert process_2.rules.identifiers == ['10.0.0.2:25000']
    # 3. in standard mode, the list of Supvisors instances cannot change
    #    but the number of processes in a homogeneous group can (update_numprocs XML-RPC)
    info = process_2.info_map['10.0.0.1:25000']
    info.update({'name': 'yeux_02', 'process_index': 2})
    process_3 = create_process(info, homogeneous_group.supvisors)
    process_3.add_info('10.0.0.1:25000', info)
    process_3.rules.hash_identifiers = [WILDCARD]
    process_3.rules.identifiers = []
    homogeneous_group.add_process(process_3)
    # call new resolution
    homogeneous_group.resolve_rules()
    assert process_1.rules.hash_identifiers == []
    assert process_1.rules.identifiers == ['10.0.0.1:25000']
    assert process_2.rules.hash_identifiers == []
    assert process_2.rules.identifiers == ['10.0.0.2:25000']
    assert process_3.rules.hash_identifiers == []
    assert process_3.rules.identifiers == ['10.0.0.1:25000']


def test_homogeneous_group_resolve_hash_list(homogeneous_group):
    """ Test the HomogeneousGroup.assign_at_identifiers method. """
    # patch list of instances so that it is smaller than the list of processes
    mapper = homogeneous_group.supvisors.mapper
    ref_instances = mapper.instances.copy()
    mapper._instances = {'10.0.0.1:25000': ref_instances['10.0.0.1:25000'],
                         '10.0.0.2:25000': ref_instances['10.0.0.2:25000']}
    # force at-* rules in processes and group
    homogeneous_group.hash_identifiers = ['10.0.0.3:25000', '10.0.0.2:25000', '10.0.0.1:25000']
    process_1 = homogeneous_group.processes[0]
    process_1.rules.hash_identifiers = ['10.0.0.3:25000', '10.0.0.2:25000', '10.0.0.1:25000']
    process_1.rules.identifiers = []
    process_2 = homogeneous_group.processes[1]
    process_2.rules.hash_identifiers = ['10.0.0.3:25000', '10.0.0.2:25000', '10.0.0.1:25000']
    process_2.rules.identifiers = []
    # 1. check assignment
    # the number of instance exceeds the number of processes
    homogeneous_group.resolve_rules()
    assert process_1.rules.hash_identifiers == []
    assert process_1.rules.identifiers == ['10.0.0.2:25000']
    assert process_2.rules.hash_identifiers == []
    assert process_2.rules.identifiers == ['10.0.0.1:25000']
    # 2. check no change with same call
    homogeneous_group.resolve_rules()
    assert process_1.rules.hash_identifiers == []
    assert process_1.rules.identifiers == ['10.0.0.2:25000']
    assert process_2.rules.hash_identifiers == []
    assert process_2.rules.identifiers == ['10.0.0.1:25000']
    # 3. in standard mode, the list of Supvisors instances cannot change
    #    but the number of processes in a homogeneous group can (update_numprocs XML-RPC)
    info = process_2.info_map['10.0.0.1:25000']
    info.update({'name': 'yeux_02', 'process_index': 2})
    process_3 = create_process(info, homogeneous_group.supvisors)
    process_3.add_info('10.0.0.1:25000', info)
    process_3.rules.hash_identifiers = ['10.0.0.3:25000', '10.0.0.2:25000', '10.0.0.1:25000']
    process_3.rules.identifiers = []
    homogeneous_group.add_process(process_3)
    # call new resolution
    homogeneous_group.resolve_rules()
    assert process_1.rules.hash_identifiers == []
    assert process_1.rules.identifiers == ['10.0.0.2:25000']
    assert process_2.rules.hash_identifiers == []
    assert process_2.rules.identifiers == ['10.0.0.1:25000']
    assert process_3.rules.hash_identifiers == []
    assert process_3.rules.identifiers == ['10.0.0.2:25000']


# ApplicationStatus part
def test_application_create(supvisors):
    """ Test the values set at construction. """
    application = create_application('ApplicationTest', supvisors)
    # check application default attributes
    assert application.supvisors is supvisors
    assert application.logger is supvisors.logger
    assert application.application_name == 'ApplicationTest'
    assert application.state == ApplicationStates.STOPPED
    assert not application.major_failure
    assert not application.minor_failure
    assert not application.processes
    assert not application.start_sequence
    assert not application.stop_sequence
    # check application default rules
    assert not application.rules.managed
    assert application.rules.distribution == DistributionRules.ALL_INSTANCES
    assert application.rules.start_sequence == 0
    assert application.rules.stop_sequence == -1
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
    application.update_state()
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
    application.update()
    assert application.stopped()
    assert not application.has_running_processes()
    # add a running process
    info = any_process_info_by_state(ProcessStates.RUNNING)
    process = create_process(info, supvisors)
    process.add_info('10.0.0.1', info)
    application.add_process(process)
    application.update_state()
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
    assert serialized == {'application_name': 'ApplicationTest', 'managed': False,
                          'statecode': 2, 'statename': 'RUNNING', 'major_failure': False, 'minor_failure': True}
    # test that returned structure is serializable using pickle
    dumped = pickle.dumps(serialized)
    loaded = pickle.loads(dumped)
    assert serialized == loaded


def test_application_add_remove_process(supvisors):
    """ Test the add_process and remove_process methods. """
    application = create_application('ApplicationTest', supvisors)
    # get 3 processes for test
    processes = []
    for name in ['xclock', 'yeux_00', 'yeux_01']:
        info = process_info_by_name(name)
        process = create_process(info, supvisors)
        process.add_info('10.0.0.1', info)
        processes.append(process)
    process_1 = processes[0]
    process_2 = processes[1]
    process_2.rules.at_identifiers = ['10.0.0.1']
    process_3 = processes[2]
    process_3.program_name = process_2.program_name
    process_3.rules.at_identifiers = ['10.0.0.2', '10.0.0.3']
    # 1. add a process with default rules to the application
    application.add_process(process_1)
    # check that process is stored
    assert application.processes == {process_1.process_name: process_1}
    assert list(application.process_groups.keys()) == [process_1.program_name]
    group = application.process_groups[process_1.program_name]
    assert process_1 in group.processes
    assert group.at_identifiers is None
    assert group.hash_identifiers is None
    # 2. add a process with hash rules to the application
    application.add_process(process_2)
    # check that process is stored
    assert application.processes == {process_1.process_name: process_1,
                                     process_2.process_name: process_2}
    assert sorted(application.process_groups.keys()) == sorted([process_1.program_name, process_2.program_name])
    group = application.process_groups[process_2.program_name]
    assert group.processes == [process_2]
    assert group.at_identifiers == ['10.0.0.1']
    assert group.hash_identifiers is None
    # 3. add a process with same program name and at rules to the application
    application.add_process(process_3)
    # check that process is stored
    assert application.processes == {process_1.process_name: process_1,
                                     process_2.process_name: process_2,
                                     process_3.process_name: process_3}
    assert sorted(application.process_groups.keys()) == sorted([process_1.program_name, process_2.program_name])
    group = application.process_groups[process_3.program_name]
    assert group.processes == [process_2, process_3]
    assert group.at_identifiers == ['10.0.0.2', '10.0.0.3']
    assert group.hash_identifiers is None
    # 4. test first removal
    application.remove_process(process_2.process_name)
    # check that process is not stored anymore
    assert application.processes == {process_1.process_name: process_1,
                                     process_3.process_name: process_3}
    assert sorted(application.process_groups.keys()) == sorted([process_1.program_name, process_2.program_name])
    group = application.process_groups[process_1.program_name]
    assert group.processes == [process_1]
    group = application.process_groups[process_3.program_name]
    assert group.processes == [process_3]
    # 5. test second removal
    application.remove_process(process_1.process_name)
    # check that process is not stored anymore
    assert application.processes == {process_3.process_name: process_3}
    assert list(application.process_groups.keys()) == [process_3.program_name]
    group = application.process_groups[process_3.program_name]
    assert group.processes == [process_3]
    # 5. test third removal
    application.remove_process(process_3.process_name)
    # check that process is not stored anymore
    assert application.processes == {}
    assert application.process_groups == {}
    # 6. quickly test with hash_identifiers
    process_2.rules.at_identifiers = []
    process_2.rules.hash_identifiers = ['10.0.0.1']
    process_3.rules.at_identifiers = []
    process_3.rules.hash_identifiers = ['10.0.0.2', '10.0.0.3']
    application.add_process(process_3)
    application.add_process(process_2)
    # check stored information
    assert application.processes == {process_2.process_name: process_2,
                                     process_3.process_name: process_3}
    assert list(application.process_groups.keys()) == [process_2.program_name]
    group = application.process_groups[process_3.program_name]
    assert group.processes == [process_3, process_2]
    assert group.at_identifiers is None
    assert group.hash_identifiers == ['10.0.0.1']
    # 7. finish with last "should not happen" case
    process_1.program_name = process_2.program_name
    process_1.rules.at_identifiers = ['10.0.0.0']
    application.add_process(process_1)
    # check stored information
    assert application.processes == {process_1.process_name: process_1,
                                     process_2.process_name: process_2,
                                     process_3.process_name: process_3}
    assert list(application.process_groups.keys()) == [process_2.program_name]
    group = application.process_groups[process_1.program_name]
    assert group.processes == [process_3, process_2, process_1]
    assert group.at_identifiers == ['10.0.0.0']
    assert group.hash_identifiers is None


def test_application_possible_identifiers(supvisors):
    """ Test the ApplicationStatus.possible_identifiers method. """
    application = create_application('ApplicationTest', supvisors)
    # add a process to the application
    info = any_process_info_by_state(ProcessStates.STARTING)
    process1 = create_process(info, supvisors)
    for node_name in ['10.0.0.2:25000', '10.0.0.3:25000', '10.0.0.4:25000']:
        process1.add_info(node_name, info.copy())
    application.add_process(process1)
    # add another process to the application
    info = any_stopped_process_info()
    process2 = create_process(info, supvisors)
    for node_name in ['10.0.0.1:25000', '10.0.0.4:25000']:
        process2.add_info(node_name, info.copy())
    application.add_process(process2)
    # default identifiers is '*' in process rules
    assert application.possible_identifiers() == ['10.0.0.4:25000']
    # set a subset of identifiers in process rules so that there's no intersection with received status
    application.rules.identifiers = ['10.0.0.1:25000', '10.0.0.2:25000']
    assert application.possible_identifiers() == []
    # increase received status
    process1.add_info('10.0.0.1:25000', info.copy())
    assert application.possible_identifiers() == ['10.0.0.1:25000']
    # disable program on '10.0.0.1'
    process2.update_disability('10.0.0.1:25000', True)
    assert application.possible_identifiers() == []
    # reset rules
    application.rules.identifiers = ['*']
    assert application.possible_identifiers() == ['10.0.0.4:25000']
    # test with full status and all instances in rules + re-enable on '10.0.0.1'
    process2.update_disability('10.0.0.1:25000', False)
    for node_name in supvisors.mapper.instances:
        process1.add_info(node_name, info.copy())
        process2.add_info(node_name, info.copy())
    assert sorted(application.possible_identifiers()) == sorted(supvisors.mapper.instances.keys())
    # restrict again instances in rules
    application.rules.identifiers = ['10.0.0.2:25000', '10.0.0.5:25000']
    assert application.possible_identifiers() == ['10.0.0.2:25000', '10.0.0.5:25000']


def test_application_possible_node_identifiers(supvisors):
    """ Test the ApplicationStatus.possible_node_identifiers method.
    Same test logic as above but update the node mapping before. """
    # update the node mapping
    fqdn = getfqdn()
    supvisors.mapper._nodes = {'10.0.0.1': ['10.0.0.1:25000', '10.0.0.3:25000', '10.0.0.5:25000'],
                               '10.0.0.2': ['10.0.0.2:25000', '10.0.0.4:25000'],
                               fqdn: [f'{fqdn}:25000', f'{fqdn}:15000']}
    # create the test application
    application = create_application('ApplicationTest', supvisors)
    # add a process to the application
    info = any_process_info_by_state(ProcessStates.STARTING)
    process1 = create_process(info, supvisors)
    for identifier in ['10.0.0.2:25000', '10.0.0.3:25000', '10.0.0.4:25000']:
        process1.add_info(identifier, info.copy())
    application.add_process(process1)
    # add another process to the application
    info = any_stopped_process_info()
    process2 = create_process(info, supvisors)
    for identifier in ['10.0.0.1:25000', '10.0.0.4:25000']:
        process2.add_info(identifier, info.copy())
    application.add_process(process2)
    # default identifiers is '*' in process rules
    assert application.possible_node_identifiers() == ['10.0.0.1:25000', '10.0.0.2:25000',
                                                       '10.0.0.3:25000', '10.0.0.4:25000']
    # set a subset of identifiers in process rules so that there's no intersection with received status
    application.rules.identifiers = ['10.0.0.1:25000', '10.0.0.2:25000']
    assert application.possible_node_identifiers() == []
    # increase received status
    process1.add_info('10.0.0.1:25000', info.copy())
    assert application.possible_node_identifiers() == ['10.0.0.1:25000']
    # disable program on 10.0.0.1
    process2.update_disability('10.0.0.1:25000', True)
    assert application.possible_node_identifiers() == []
    # reset rules
    application.rules.identifiers = ['*']
    assert application.possible_node_identifiers() == ['10.0.0.2:25000', '10.0.0.4:25000']
    # test with full status and all instances in rules + re-enable on '10.0.0.1'
    process2.update_disability('10.0.0.1:25000', False)
    for identifier in supvisors.mapper.instances:
        process1.add_info(identifier, info.copy())
        process2.add_info(identifier, info.copy())
    assert sorted(application.possible_node_identifiers()) == sorted(supvisors.mapper.instances.keys())
    # restrict again instances in rules
    application.rules.identifiers = ['10.0.0.2:25000', '10.0.0.5:25000']
    assert application.possible_node_identifiers() == ['10.0.0.2:25000', '10.0.0.5:25000']


def test_application_get_instance_processes(supvisors):
    """ Test the ApplicationStatus.get_instance_processes method. """
    application = create_application('ApplicationTest', supvisors)
    # add a process to the application
    info = any_process_info_by_state(ProcessStates.STARTING)
    process1 = create_process(info, supvisors)
    for node_name in ['10.0.0.2', '10.0.0.3', '10.0.0.4']:
        process1.add_info(node_name, info.copy())
    application.add_process(process1)
    # add another process to the application
    info = any_stopped_process_info()
    process2 = create_process(info, supvisors)
    for node_name in ['10.0.0.1', '10.0.0.4']:
        process2.add_info(node_name, info.copy())
    application.add_process(process2)
    # test call
    assert application.get_instance_processes('10.0.0.0') == []
    assert application.get_instance_processes('10.0.0.1') == [process2]
    assert application.get_instance_processes('10.0.0.2') == [process1]
    assert application.get_instance_processes('10.0.0.3') == [process1]
    assert application.get_instance_processes('10.0.0.4') == [process1, process2]


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


def test_update(mocker, filled_application):
    """ Test the ApplicationStatus.update method. """
    mocked_state = mocker.patch.object(filled_application, 'update_state', return_value=ApplicationStates.RUNNING)
    mocked_formula = mocker.patch.object(filled_application, 'update_status_formula')
    mocked_required = mocker.patch.object(filled_application, 'update_status_required')
    # initial state
    assert filled_application.state == ApplicationStates.STOPPED
    assert not filled_application.major_failure
    assert not filled_application.minor_failure
    # update state and status
    # test with no formula set in application rules
    assert filled_application.rules.status_formula is None
    filled_application.update()
    assert filled_application.state == ApplicationStates.RUNNING
    assert not filled_application.major_failure
    assert not filled_application.minor_failure
    assert mocked_state.call_args_list == [call()]
    assert mocked_formula.call_args_list == []
    assert mocked_required.call_args_list == [call({})]
    mocker.resetall()
    # update sequences
    filled_application.rules.managed = True
    filled_application.update_sequences()
    sequenced_processes = {process.process_name: process
                           for sub_seq in filled_application.start_sequence.values()
                           for process in sub_seq}
    # test again (check also that failures are reset)
    filled_application.major_failure = True
    filled_application.minor_failure = True
    filled_application.update()
    assert filled_application.state == ApplicationStates.RUNNING
    assert not filled_application.major_failure
    assert not filled_application.minor_failure
    assert mocked_state.call_args_list == [call()]
    assert mocked_formula.call_args_list == []
    assert mocked_required.call_args_list == [call(sequenced_processes)]
    mocker.resetall()
    # test with formula set in application rules
    filled_application.rules.status_formula = "xlogo"
    filled_application.update()
    assert filled_application.state == ApplicationStates.RUNNING
    assert not filled_application.major_failure
    assert not filled_application.minor_failure
    assert mocked_state.call_args_list == [call()]
    assert mocked_formula.call_args_list == [call(sequenced_processes)]
    assert mocked_required.call_args_list == []


def test_application_update_state(filled_application):
    """ Test the rules to update the status of the application method. """
    assert filled_application.state == ApplicationStates.STOPPED
    # there is a process in STOPPING state in the process database
    # STOPPING has the highest priority in application state evaluation
    assert filled_application.update_state() == ApplicationStates.STOPPING
    # set STOPPING process to STOPPED
    for process in filled_application.processes.values():
        if process.state == ProcessStates.STOPPING:
            process.state = ProcessStates.STOPPED
    # now STARTING is expected as it is the second priority
    assert filled_application.update_state() == ApplicationStates.STARTING
    # set STARTING process to RUNNING
    starting_process = next((process for process in filled_application.processes.values()
                             if process.state == ProcessStates.STARTING), None)
    starting_process.state = ProcessStates.RUNNING
    # update status. there is still one BACKOFF process leading to STARTING application
    assert filled_application.update_state() == ApplicationStates.STARTING
    # set BACKOFF process to EXITED unexpected
    backoff_process = next((process for process in filled_application.processes.values()
                            if process.state == ProcessStates.BACKOFF), None)
    backoff_process.state = ProcessStates.EXITED
    backoff_process.expected_exit = False
    # update status. now there is only stopped and running processes.
    assert filled_application.update_state() == ApplicationStates.RUNNING
    # set all process to RUNNING
    for process in filled_application.processes.values():
        process.state = ProcessStates.RUNNING
    assert filled_application.update_state() == ApplicationStates.RUNNING
    # set all processes to STOPPED
    for process in filled_application.processes.values():
        process.state = ProcessStates.STOPPED
    # all processes are STOPPED in a STOPPED application, so no failure
    assert filled_application.update_state() == ApplicationStates.STOPPED


def test_application_update_status_required(filled_application):
    """ Test the rules to update the status of the application method. """
    # initial status
    assert filled_application.state == ApplicationStates.STOPPED
    assert not filled_application.major_failure
    assert not filled_application.minor_failure
    # first call with no process required and no start sequence
    filled_application.update_status_required({})
    assert not filled_application.major_failure
    assert not filled_application.minor_failure
    # set application to managed, update sequences and state
    filled_application.rules.managed = True
    filled_application.update_sequences()
    filled_application.state = filled_application.update_state()
    sequenced_processes = {process.process_name: process
                           for sub_seq in filled_application.start_sequence.values()
                           for process in sub_seq}
    # there is a process in STOPPING state in the process database
    # STOPPING has the highest priority in application state evaluation
    assert filled_application.state == ApplicationStates.STOPPING
    # check the operational status
    filled_application.update_status_required(sequenced_processes)
    # multiple STOPPED processes and global state not STOPPED
    # in default rules, no process is required so this is minor
    assert not filled_application.major_failure
    assert filled_application.minor_failure
    filled_application.minor_failure = False
    # set FATAL process to major
    fatal_process = next((process for process in filled_application.processes.values()
                          if process.state == ProcessStates.FATAL))
    fatal_process.rules.required = True
    # update status. major failure is now expected
    # minor still expected
    filled_application.update_status_required(sequenced_processes)
    assert filled_application.major_failure
    assert not filled_application.minor_failure
    filled_application.major_failure = False
    # set STOPPING process to STOPPED and check no impact on failures
    for process in filled_application.processes.values():
        if process.state == ProcessStates.STOPPING:
            process.state = ProcessStates.STOPPED
    filled_application.update_status_required(sequenced_processes)
    assert filled_application.major_failure
    assert not filled_application.minor_failure
    # set STARTING process to RUNNING and check no impact on failures
    starting_process = next((process for process in filled_application.processes.values()
                             if process.state == ProcessStates.STARTING), None)
    starting_process.state = ProcessStates.RUNNING
    filled_application.update_status_required(sequenced_processes)
    assert filled_application.major_failure
    assert not filled_application.minor_failure
    filled_application.major_failure = False
    # set BACKOFF process to EXITED unexpected
    backoff_process = next((process for process in filled_application.processes.values()
                            if process.state == ProcessStates.BACKOFF), None)
    backoff_process.state = ProcessStates.EXITED
    backoff_process.expected_exit = False
    # update status. major failure is set, so not minor_failure
    filled_application.update_status_required(sequenced_processes)
    assert filled_application.major_failure
    assert not filled_application.minor_failure
    filled_application.major_failure = False
    # set all process to RUNNING
    for process in filled_application.processes.values():
        process.state = ProcessStates.RUNNING
    # no more failures
    filled_application.update_status_required(sequenced_processes)
    assert not filled_application.major_failure
    assert not filled_application.minor_failure
    # set all processes to STOPPED
    for process in filled_application.processes.values():
        process.state = ProcessStates.STOPPED
    # all processes are STOPPED in a STOPPED application, so no failure
    filled_application.state = ApplicationStates.STOPPED
    filled_application.update_status_required(sequenced_processes)
    assert not filled_application.major_failure
    assert not filled_application.minor_failure


def test_application_get_process_status(filled_application):
    """ Test the ApplicationStatus._get_process_status method. """
    assert not filled_application._get_process_status('xlogo')
    assert not filled_application._get_process_status('sleep')
    assert filled_application._get_process_status('segv')
    assert filled_application._get_process_status('xfontsel')
    # force a state to STARTING
    filled_application.processes['segv'].forced_state = ProcessStates.STARTING
    assert filled_application._get_process_status('segv')
    # force a state to EXITED / expected
    filled_application.processes['xfontsel'].forced_state = ProcessStates.EXITED
    filled_application.processes['xfontsel'].expected_exit = True
    assert filled_application._get_process_status('xfontsel')
    # force a state to EXITED / not expected
    filled_application.processes['xfontsel'].expected_exit = False
    assert not filled_application._get_process_status('xfontsel')


def test_application_get_matches(filled_application):
    """ Test the ApplicationStatus._get_matches method. """
    assert filled_application._get_matches('') == []
    assert filled_application._get_matches('dummy') == []
    assert filled_application._get_matches('xlogo') == ['xlogo']
    assert sorted(filled_application._get_matches('x.*')) == ['xclock', 'xfontsel', 'xlogo']
    assert sorted(filled_application._get_matches(r'yeux_[01]{2}')) == ['yeux_00', 'yeux_01']


class Str:
    def __init__(self, value):
        self.s = value


@pytest.mark.skipif(sys.version_info >= (3, 8), reason="ast.Str is replaced by ast.Constant from Python 3.8")
def test_application_evaluate_strings_deprecated(filled_application):
    """ Test the ApplicationStatus.evaluate method with string expression from Python 3.8.
    ast.Str is obsolete since then and replaced by ast.Constant. """
    # test string leaf error
    expr = ast.Str('a string')
    with pytest.raises(ApplicationStatusParseError):
        filled_application.evaluate(expr)
    # test string leaf with process status running (force ast.Str type because it )
    expr = ast.Str('xfontsel')
    assert filled_application.evaluate(expr) is True
    # test string leaf with process status running
    expr = ast.Str('xlogo')
    assert filled_application.evaluate(expr) is False
    # test pattern with single resolution
    expr = ast.Str('xcl.ck')
    assert filled_application.evaluate(expr) is False
    # test pattern with multiple resolution
    expr = ast.Str('(xlogo|sleep)')
    assert filled_application.evaluate(expr) == [False, False]


@pytest.mark.skipif(sys.version_info < (3, 8), reason="ast.Str is replaced by ast.Constant from Python 3.8")
def test_application_evaluate_strings_38(filled_application):
    """ Test the ApplicationStatus.evaluate method with string expression from Python 3.8.
    ast.Str is obsolete since then and replaced by ast.Constant. """
    # force ast.Str type because it is replaced by an ast.Constant at creation
    ast.Str = Str
    # test string leaf error
    expr = ast.Constant('a string')
    with pytest.raises(ApplicationStatusParseError):
        filled_application.evaluate(expr)
    # test string leaf with process status running (just to hit ast.Str)
    expr = ast.Str('xfontsel')
    assert filled_application.evaluate(expr) is True
    # test string leaf with process status running
    expr = ast.Constant('xlogo')
    assert filled_application.evaluate(expr) is False
    # test pattern with single resolution
    expr = ast.Constant('xcl.ck')
    assert filled_application.evaluate(expr) is False
    # test pattern with multiple resolution
    expr = ast.Constant('(xlogo|sleep)')
    assert filled_application.evaluate(expr) == [False, False]


def test_application_evaluate_functions(filled_application):
    """ Test the ApplicationStatus.evaluate method with functions. """
    filled_application.processes['yeux_00'].expected_exit = False
    # test all function
    tree = ast.parse('all("yeux.*")')
    assert filled_application.evaluate(tree.body[0].value) is False
    tree = ast.parse('all("yeux.*1")')
    assert filled_application.evaluate(tree.body[0].value) is True
    # test any function
    tree = ast.parse('any("yeux.*")')
    assert filled_application.evaluate(tree.body[0].value) is True
    tree = ast.parse('any("xlogo")')
    assert filled_application.evaluate(tree.body[0].value) is False
    # test other function
    tree = ast.parse('map(str, ["xlogo"])')
    with pytest.raises(ApplicationStatusParseError) as exc:
        filled_application.evaluate(tree.body[0].value)
    assert exc.value.message == 'unsupported function=map'


def test_application_evaluate_operators(filled_application):
    """ Test the ApplicationStatus.evaluate method with operators. """
    filled_application.processes['yeux_00'].expected_exit = False
    # test unresolvable bool operator
    tree = ast.parse('"xlogo" and "yeux.*"')
    with pytest.raises(ApplicationStatusParseError) as exc:
        filled_application.evaluate(tree.body[0].value)
    assert exc.value.message == 'cannot apply BoolOp on unresolved expression'
    # test and operator
    tree = ast.parse('"xlogo" and "yeux_01"')
    assert filled_application.evaluate(tree.body[0].value) is False
    tree = ast.parse('"xfontsel" and "yeux_01"')
    assert filled_application.evaluate(tree.body[0].value) is True
    # test and operator
    tree = ast.parse('"xlogo" or "yeux_01"')
    assert filled_application.evaluate(tree.body[0].value) is True
    tree = ast.parse('"xlogo" or "yeux_00"')
    assert filled_application.evaluate(tree.body[0].value) is False
    # test unresolvable unary operator
    tree = ast.parse('not "yeux.*"')
    with pytest.raises(ApplicationStatusParseError) as exc:
        filled_application.evaluate(tree.body[0].value)
    assert exc.value.message == 'cannot apply UnaryOp on unresolved expression'
    # test not operator
    tree = ast.parse('not "yeux.00"')
    assert filled_application.evaluate(tree.body[0].value) is True
    tree = ast.parse('not "yeux.01"')
    assert filled_application.evaluate(tree.body[0].value) is False
    # test error when using other unary operator type
    tree = ast.parse('- "yeux.01"')
    with pytest.raises(ApplicationStatusParseError) as exc:
        filled_application.evaluate(tree.body[0].value)
    assert exc.value.message == 'unsupported UnaryOp=USub'
    # test error when using other operator type
    tree = ast.parse('"yeux.01" + "yeux.01"')
    with pytest.raises(ApplicationStatusParseError) as exc:
        filled_application.evaluate(tree.body[0].value)
    assert exc.value.message == 'unsupported Expr=BinOp'


def test_application_update_status_formula(filled_application):
    """ Test the rules to update the status of the application method. """
    filled_application.processes['yeux_00'].expected_exit = False
    # set application to managed, update sequences and state
    filled_application.rules.managed = True
    filled_application.update_sequences()
    sequenced_processes = {process.process_name: process
                           for sub_seq in filled_application.start_sequence.values()
                           for process in sub_seq}
    # check initial state
    assert not filled_application.major_failure
    assert not filled_application.minor_failure
    # test error handling when the evaluation returns a non-boolean result
    filled_application.rules.status_formula = '"yeux.*"'
    filled_application.update_status_formula(sequenced_processes)
    assert filled_application.major_failure
    assert not filled_application.minor_failure
    filled_application.major_failure = False
    # test error handling when the evaluation raises an exception
    filled_application.rules.status_formula = 'map(str, ["xlogo"])'
    filled_application.update_status_formula(sequenced_processes)
    assert filled_application.major_failure
    assert not filled_application.minor_failure
    filled_application.major_failure = False
    # test evaluation with normal major failure
    filled_application.rules.status_formula = 'all("yeux.*")'
    filled_application.update_status_formula(sequenced_processes)
    assert filled_application.major_failure
    assert not filled_application.minor_failure
    filled_application.major_failure = False
    # test evaluation with no major failure, triggering the minor failure evaluation
    # reason: sleep is FATAL
    filled_application.rules.status_formula = 'any("yeux.*")'
    filled_application.update_status_formula(sequenced_processes)
    assert not filled_application.major_failure
    assert filled_application.minor_failure
    filled_application.minor_failure = False
    # force the FATAL state to STOPPED and the expeected exit and check that minor failure disappears
    filled_application.processes['sleep'].forced_state = ProcessStates.STOPPED
    filled_application.processes['yeux_00'].expected_exit = True
    filled_application.update_status_formula(sequenced_processes)
    assert not filled_application.major_failure
    assert not filled_application.minor_failure
