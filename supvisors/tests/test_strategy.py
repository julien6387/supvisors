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

from unittest.mock import Mock, call

from supvisors.address import AddressStatus
from supvisors.strategy import *
from supvisors.ttypes import AddressStates, ConciliationStrategies, RunningFailureStrategies, StartingStrategies


def mock_node(mocker, status: AddressStatus, node_state: AddressStates, load: int):
    """ Mock the AddressStatus. """
    status._state = node_state
    mocker.patch.object(status, 'get_loading', return_value=load)


@pytest.fixture
def filled_nodes(mocker, supvisors):
    nodes = supvisors.context.nodes
    mock_node(mocker, nodes['127.0.0.1'], AddressStates.RUNNING, 50)
    mock_node(mocker, nodes['10.0.0.1'], AddressStates.SILENT, 0)
    mock_node(mocker, nodes['10.0.0.2'], AddressStates.ISOLATED, 0)
    mock_node(mocker, nodes['10.0.0.3'], AddressStates.RUNNING, 20)
    mock_node(mocker, nodes['10.0.0.4'], AddressStates.UNKNOWN, 0)
    mock_node(mocker, nodes['10.0.0.5'], AddressStates.RUNNING, 80)
    return supvisors


@pytest.fixture
def load_request_map():
    return {'127.0.0.1': 0, '10.0.0.3': 10, '10.0.0.5': 20}


@pytest.fixture
def starting_strategy(filled_nodes):
    """ Create the AbstractStartingStrategy instance to test. """
    return AbstractStartingStrategy(filled_nodes)


def test_is_loading_valid(starting_strategy, load_request_map):
    """ Test the validity of an address with an additional loading. """
    # test unknown address
    assert starting_strategy.is_loading_valid('10.0.0.0', 1, load_request_map) == (False, 0)
    # test not RUNNING address
    assert starting_strategy.is_loading_valid('10.0.0.1', 1, load_request_map) == (False, 0)
    assert starting_strategy.is_loading_valid('10.0.0.2', 1, load_request_map) == (False, 0)
    assert starting_strategy.is_loading_valid('10.0.0.4', 1, load_request_map) == (False, 0)
    # test loaded RUNNING address
    assert starting_strategy.is_loading_valid('127.0.0.1', 55, load_request_map) == (False, 50)
    assert starting_strategy.is_loading_valid('10.0.0.3', 85, load_request_map) == (False, 30)
    assert starting_strategy.is_loading_valid('10.0.0.5', 25, load_request_map) == (False, 100)
    # test not loaded RUNNING address
    assert starting_strategy.is_loading_valid('127.0.0.1', 45, load_request_map) == (True, 50)
    assert starting_strategy.is_loading_valid('10.0.0.3', 65, load_request_map) == (True, 30)
    assert starting_strategy.is_loading_valid('10.0.0.5', 0, load_request_map) == (True, 100)


def test_get_loading_and_validity(starting_strategy, load_request_map):
    """ Test the determination of the valid addresses with an additional loading. """
    # test valid addresses with different additional loadings
    node_names = starting_strategy.supvisors.address_mapper.node_names
    # first test
    expected = {'127.0.0.1': (True, 50), '10.0.0.1': (False, 0), '10.0.0.2': (False, 0),
                '10.0.0.3': (True, 30), '10.0.0.4': (False, 0), '10.0.0.5': (False, 100)}
    assert starting_strategy.get_loading_and_validity(node_names, 15, load_request_map) == expected
    # second test
    expected = {'127.0.0.1': (True, 50), '10.0.0.1': (False, 0), '10.0.0.2': (False, 0),
                '10.0.0.3': (True, 30), '10.0.0.4': (False, 0), '10.0.0.5': (False, 100)}
    assert starting_strategy.get_loading_and_validity(starting_strategy.supvisors.context.nodes.keys(), 45,
                                                      load_request_map) == expected
    # third test
    expected = {'127.0.0.1': (False, 50), '10.0.0.3': (True, 30), '10.0.0.5': (False, 100)}
    assert starting_strategy.get_loading_and_validity(['127.0.0.1', '10.0.0.3', '10.0.0.5'], 65,
                                                      load_request_map) == expected
    # fourth test
    expected = {'127.0.0.1': (False, 50), '10.0.0.3': (False, 30), '10.0.0.5': (False, 100)}
    assert starting_strategy.get_loading_and_validity(['127.0.0.1', '10.0.0.3', '10.0.0.5'], 85,
                                                      load_request_map) == expected


def test_sort_valid_by_loading(starting_strategy):
    """ Test the sorting of the validity of the addresses. """
    # first test
    parameters = {'10.0.0.0': (False, 0), '10.0.0.1': (True, 50), '10.0.0.2': (False, 0),
                  '10.0.0.3': (True, 20), '10.0.0.4': (False, 0), '10.0.0.5': (True, 80)}
    expected = [('10.0.0.3', 20), ('10.0.0.1', 50), ('10.0.0.5', 80)]
    assert starting_strategy.sort_valid_by_loading(parameters) == expected
    # second test
    parameters = {'10.0.0.1': (False, 50), '10.0.0.3': (True, 20), '10.0.0.5': (False, 80)}
    assert starting_strategy.sort_valid_by_loading(parameters) == [('10.0.0.3', 20)]
    # third test
    parameters = {'10.0.0.1': (False, 50), '10.0.0.3': (False, 20), '10.0.0.5': (False, 80)}
    assert starting_strategy.sort_valid_by_loading(parameters) == []


def test_abstract_get_node(starting_strategy):
    """ Test that the AbstractStartingStrategy.get_node method is not implemented. """
    node_names = starting_strategy.supvisors.address_mapper.node_names
    with pytest.raises(NotImplementedError):
        starting_strategy.get_node(node_names, 0, {})


def test_config_strategy(filled_nodes, load_request_map):
    """ Test the choice of an address according to the CONFIG strategy. """
    strategy = ConfigStrategy(filled_nodes)
    # test CONFIG strategy with different values
    node_names = filled_nodes.address_mapper.node_names
    assert strategy.get_node(node_names, 0, load_request_map) == '127.0.0.1'
    assert strategy.get_node(node_names, 15, load_request_map) == '127.0.0.1'
    assert strategy.get_node(node_names, 45, load_request_map) == '127.0.0.1'
    assert strategy.get_node(node_names, 65, load_request_map) == '10.0.0.3'
    assert strategy.get_node(node_names, 85, load_request_map) is None


def test_less_loaded_strategy(filled_nodes, load_request_map):
    """ Test the choice of an address according to the LESS_LOADED strategy. """
    strategy = LessLoadedStrategy(filled_nodes)
    # test LESS_LOADED strategy with different values
    node_names = filled_nodes.address_mapper.node_names
    assert strategy.get_node(node_names, 0, load_request_map) == '10.0.0.3'
    assert strategy.get_node(node_names, 15, load_request_map) == '10.0.0.3'
    assert strategy.get_node(node_names, 45, load_request_map) == '10.0.0.3'
    assert strategy.get_node(node_names, 65, load_request_map) == '10.0.0.3'
    assert strategy.get_node(node_names, 85, load_request_map) is None


def test_most_loaded_strategy(filled_nodes, load_request_map):
    """ Test the choice of an address according to the MOST_LOADED strategy. """
    strategy = MostLoadedStrategy(filled_nodes)
    # test MOST_LOADED strategy with different values
    node_names = filled_nodes.address_mapper.node_names
    assert strategy.get_node(node_names, 0, load_request_map) == '10.0.0.5'
    assert strategy.get_node(node_names, 15, load_request_map) == '127.0.0.1'
    assert strategy.get_node(node_names, 45, load_request_map) == '127.0.0.1'
    assert strategy.get_node(node_names, 65, load_request_map) == '10.0.0.3'
    assert strategy.get_node(node_names, 85, load_request_map) is None


def test_local_strategy(filled_nodes, load_request_map):
    """ Test the choice of an address according to the LOCAL strategy. """
    strategy = LocalStrategy(filled_nodes)
    # test LOCAL strategy with different values
    node_names = filled_nodes.address_mapper.node_names
    assert strategy.supvisors.address_mapper.local_node_name == '127.0.0.1'
    assert strategy.get_node(node_names, 0, load_request_map) == '127.0.0.1'
    assert strategy.get_node(node_names, 15, load_request_map) == '127.0.0.1'
    assert strategy.get_node(node_names, 45, load_request_map) == '127.0.0.1'
    assert strategy.get_node(node_names, 65, load_request_map) is None


def test_get_node(filled_nodes, load_request_map):
    """ Test the choice of a node according to a strategy. """
    # test CONFIG strategy
    node_names = filled_nodes.address_mapper.node_names
    assert get_node(filled_nodes, StartingStrategies.CONFIG, node_names, 0, load_request_map) == '127.0.0.1'
    assert get_node(filled_nodes, StartingStrategies.CONFIG, node_names, 15, load_request_map) == '127.0.0.1'
    assert get_node(filled_nodes, StartingStrategies.CONFIG, node_names, 65, load_request_map) == '10.0.0.3'
    assert get_node(filled_nodes, StartingStrategies.CONFIG, node_names, 85, load_request_map) is None
    # test LESS_LOADED strategy
    assert get_node(filled_nodes, StartingStrategies.LESS_LOADED, node_names, 0, load_request_map) == '10.0.0.3'
    assert get_node(filled_nodes, StartingStrategies.LESS_LOADED, node_names, 15, load_request_map) == '10.0.0.3'
    assert get_node(filled_nodes, StartingStrategies.LESS_LOADED, node_names, 65, load_request_map) == '10.0.0.3'
    assert get_node(filled_nodes, StartingStrategies.LESS_LOADED, node_names, 85, load_request_map) is None
    # test MOST_LOADED strategy
    assert get_node(filled_nodes, StartingStrategies.MOST_LOADED, node_names, 0, load_request_map) == '10.0.0.5'
    assert get_node(filled_nodes, StartingStrategies.MOST_LOADED, node_names, 15, load_request_map) == '127.0.0.1'
    assert get_node(filled_nodes, StartingStrategies.MOST_LOADED, node_names, 65, load_request_map) == '10.0.0.3'
    assert get_node(filled_nodes, StartingStrategies.MOST_LOADED, node_names, 85, load_request_map) is None
    # test LOCAL strategy
    assert get_node(filled_nodes, StartingStrategies.LOCAL, node_names, 0, load_request_map) == '127.0.0.1'
    assert get_node(filled_nodes, StartingStrategies.LOCAL, node_names, 15, load_request_map) == '127.0.0.1'
    assert get_node(filled_nodes, StartingStrategies.LOCAL, node_names, 65, load_request_map) is None


def create_process_status(name, timed_nodes):
    process_status = Mock(spec=ProcessStatus, process_name=name, namespec=name,
                          running_nodes=set(timed_nodes.keys()),
                          info_map={address_name: {'uptime': time} for address_name, time in timed_nodes.items()})
    return process_status


@pytest.fixture
def conflicts(supvisors):
    # create conflicting processes
    return [create_process_status('conflict_1', {'10.0.0.1': 5, '10.0.0.2': 10, '10.0.0.3': 15}),
            create_process_status('conflict_2', {'10.0.0.4': 6, '10.0.0.2': 5, '10.0.0.0': 4})]


def test_senicide_strategy(supvisors, conflicts):
    """ Test the strategy that consists in stopping the oldest processes. """
    strategy = SenicideStrategy(supvisors)
    strategy.conciliate(conflicts)
    # check that the oldest processes are requested to stop on the relevant addresses
    expected = [call('10.0.0.2', 'conflict_1'), call('10.0.0.3', 'conflict_1'),
                call('10.0.0.4', 'conflict_2'), call('10.0.0.2', 'conflict_2')]
    supvisors.zmq.pusher.send_stop_process.assert_has_calls(expected, any_order=True)


def test_infanticide_strategy(supvisors, conflicts):
    """ Test the strategy that consists in stopping the youngest processes. """
    strategy = InfanticideStrategy(supvisors)
    strategy.conciliate(conflicts)
    # check that the youngest processes are requested to stop on the relevant addresses
    expected = [call('10.0.0.1', 'conflict_1'), call('10.0.0.2', 'conflict_1'),
                call('10.0.0.2', 'conflict_2'), call('10.0.0.0', 'conflict_2')]
    supvisors.zmq.pusher.send_stop_process.assert_has_calls(expected, any_order=True)


def test_user_strategy(supvisors, conflicts):
    """ Test the strategy that consists in doing nothing (trivial). """
    strategy = UserStrategy(supvisors)
    strategy.conciliate(conflicts)
    # check that processes are NOT requested to stop
    assert not supvisors.stopper.stop_process.called
    assert not supvisors.zmq.pusher.send_stop_process.called


def test_stop_strategy(supvisors, conflicts):
    """ Test the strategy that consists in stopping all processes. """
    strategy = StopStrategy(supvisors)
    strategy.conciliate(conflicts)
    # check that all processes are requested to stop through the Stopper
    assert not supvisors.zmq.pusher.send_stop_process.called
    expected = [call(conflicts[0]), call(conflicts[1])]
    supvisors.stopper.stop_process.assert_has_calls(expected, any_order=True)


def test_restart_strategy(supvisors, conflicts):
    """ Test the strategy that consists in stopping all processes and restart a single one. """
    # get patches
    mocked_add = supvisors.failure_handler.add_job
    mocked_trigger = supvisors.failure_handler.trigger_jobs
    # call the conciliation
    strategy = RestartStrategy(supvisors)
    strategy.conciliate(conflicts)
    # check that all processes are NOT requested to stop directly
    assert not supvisors.stopper.stop_process.called
    assert not supvisors.zmq.pusher.send_stop_process.called
    # test failure_handler call
    assert mocked_add.call_args_list == [call(RunningFailureStrategies.RESTART_PROCESS, conflicts[0]),
                                         call(RunningFailureStrategies.RESTART_PROCESS, conflicts[1])]
    assert mocked_trigger.call_count == 1


def test_failure_strategy(supvisors, conflicts):
    """ Test the strategy that consists in stopping all processes and restart a single one. """
    # get patches
    mocked_add = supvisors.failure_handler.add_default_job
    mocked_trigger = supvisors.failure_handler.trigger_jobs
    # call the conciliation
    strategy = FailureStrategy(supvisors)
    strategy.conciliate(conflicts)
    # check that all processes are requested to stop through the Stopper
    assert not supvisors.zmq.pusher.send_stop_process.called
    assert supvisors.stopper.stop_process.call_args_list == [call(conflicts[0]), call(conflicts[1])]
    # test failure_handler call
    assert mocked_add.call_args_list == [call(conflicts[0]), call(conflicts[1])]
    assert mocked_trigger.call_count == 1


def test_conciliate_conflicts(mocker, supvisors, conflicts):
    """ Test the actions on process according to a strategy. """
    mocked_senicide = mocker.patch('supvisors.strategy.SenicideStrategy.conciliate')
    mocked_infanticide = mocker.patch('supvisors.strategy.InfanticideStrategy.conciliate')
    mocked_user = mocker.patch('supvisors.strategy.UserStrategy.conciliate')
    mocked_stop = mocker.patch('supvisors.strategy.StopStrategy.conciliate')
    mocked_restart = mocker.patch('supvisors.strategy.RestartStrategy.conciliate')
    mocked_failure = mocker.patch('supvisors.strategy.FailureStrategy.conciliate')
    # test senicide conciliation
    conciliate_conflicts(supvisors, ConciliationStrategies.SENICIDE, conflicts)
    for mock in [mocked_infanticide, mocked_user, mocked_stop, mocked_restart, mocked_failure]:
        assert not mock.called
    assert mocked_senicide.call_args_list == [call(conflicts)]
    mocked_senicide.reset_mock()
    # test infanticide conciliation
    conciliate_conflicts(supvisors, ConciliationStrategies.INFANTICIDE, conflicts)
    for mock in [mocked_senicide, mocked_user, mocked_stop, mocked_restart, mocked_failure]:
        assert not mock.called
    assert mocked_infanticide.call_args_list == [call(conflicts)]
    mocked_infanticide.reset_mock()
    # test user conciliation
    conciliate_conflicts(supvisors, ConciliationStrategies.USER, conflicts)
    for mock in [mocked_senicide, mocked_infanticide, mocked_stop, mocked_restart, mocked_failure]:
        assert not mock.called
    assert mocked_user.call_args_list == [call(conflicts)]
    mocked_user.reset_mock()
    # test stop conciliation
    conciliate_conflicts(supvisors, ConciliationStrategies.STOP, conflicts)
    for mock in [mocked_senicide, mocked_infanticide, mocked_user, mocked_restart, mocked_failure]:
        assert not mock.called
    assert mocked_stop.call_args_list == [call(conflicts)]
    mocked_stop.reset_mock()
    # test restart conciliation
    conciliate_conflicts(supvisors, ConciliationStrategies.RESTART, conflicts)
    for mock in [mocked_senicide, mocked_infanticide, mocked_user, mocked_stop, mocked_failure]:
        assert not mock.called
    assert mocked_restart.call_args_list == [call(conflicts)]
    mocked_restart.reset_mock()
    # test restart conciliation
    conciliate_conflicts(supvisors, ConciliationStrategies.RUNNING_FAILURE, conflicts)
    for mock in [mocked_senicide, mocked_infanticide, mocked_user, mocked_stop, mocked_restart]:
        assert not mock.called
    assert mocked_failure.call_args_list == [call(conflicts)]


@pytest.fixture
def handler(supvisors):
    return RunningFailureHandler(supvisors)


def compare_sets(handler, stop_app=None, restart_app=None, restart_proc=None,
                 continue_proc=None, start_app=None, start_proc=None):
    # define compare function
    assert handler.stop_application_jobs == (stop_app or set())
    assert handler.restart_application_jobs == (restart_app or set())
    assert handler.restart_process_jobs == (restart_proc or set())
    assert handler.continue_process_jobs == (continue_proc or set())
    assert handler.start_application_jobs == (start_app or set())
    assert handler.start_process_jobs == (start_proc or set())


def test_running_create(handler):
    """ Test the values set at construction. """
    # test empty structures
    compare_sets(handler)


def test_running_abort(handler):
    """ Test the clearance of internal structures. """
    # add data to sets
    handler.stop_application_jobs = {1, 2}
    handler.restart_application_jobs = {'a', 'b'}
    handler.restart_process_jobs = {1, 0, 'bcd'}
    handler.continue_process_jobs = {'aka', 2}
    handler.start_application_jobs = {1, None}
    handler.start_process_jobs = {0}
    # clear all
    handler.abort()
    # test empty structures
    compare_sets(handler)


@pytest.fixture
def add_jobs():
    """ Return common structure for add_jobs tests. """
    process_1 = Mock(application_name='dummy_application_A')
    process_2 = Mock(application_name='dummy_application_A')
    process_3 = Mock(application_name='dummy_application_B')
    process_list = [process_1, process_2, process_3]
    application_A = Mock(application_name='dummy_application_A',
                         **{'get_start_sequenced_processes.return_value': [process_2]})
    application_B = Mock(application_name='dummy_application_B')
    application_list = [application_A, application_B]
    return process_list, application_list


def test_add_stop_application_job(handler, add_jobs):
    """ Test the addition of a new job using a STOP_APPLICATION strategy. """
    # create dummy applications and processes
    proc_list, app_list = add_jobs
    application_A, application_B = app_list
    _, _, process_3 = proc_list
    # check that stop_application_jobs is updated and that other jobs are cleaned
    for job_set in [handler.restart_application_jobs, handler.start_application_jobs]:
        job_set.update(app_list)
    for job_set in [handler.restart_process_jobs, handler.start_process_jobs, handler.continue_process_jobs]:
        job_set.update(proc_list)
    assert application_A not in handler.stop_application_jobs
    handler.add_stop_application_job(application_A)
    compare_sets(handler, stop_app={application_A}, restart_app={application_B}, start_app={application_B},
                 restart_proc={process_3}, start_proc={process_3}, continue_proc={process_3})


def test_add_restart_application_job(handler, add_jobs):
    """ Test the addition of a new job using a RESTART_APPLICATION strategy. """
    # create dummy applications and processes
    proc_list, (application_A, application_B) = add_jobs
    process_1, process_2, process_3 = proc_list
    # check that restart_application_jobs is not updated when application is already in stop_application_jobs
    assert application_A not in handler.restart_application_jobs
    handler.stop_application_jobs.add(application_A)
    handler.add_restart_application_job(application_A)
    compare_sets(handler, stop_app={application_A})
    # check that restart_application_jobs is not updated when application is already in start_application_jobs
    handler.stop_application_jobs.discard(application_A)
    handler.start_application_jobs.add(application_A)
    handler.add_restart_application_job(application_A)
    compare_sets(handler, start_app={application_A})
    # check that restart_application_jobs is updated otherwise and that other jobs are cleaned
    handler.start_application_jobs.discard(application_A)
    for job_set in [handler.restart_process_jobs, handler.start_process_jobs, handler.continue_process_jobs]:
        job_set.update(proc_list)
    handler.add_restart_application_job(application_A)
    expected_proc_set = {process_1, process_3}
    compare_sets(handler, restart_app={application_A}, restart_proc=expected_proc_set,
                 start_proc=expected_proc_set, continue_proc=expected_proc_set)


def test_add_restart_process_job(add_jobs, handler):
    """ Test the addition of a new job using a RESTART_PROCESS strategy. """
    # create dummy applications and processes
    (process_1, process_2, process_3), (application_A, application_B) = add_jobs
    # check that add_restart_process_job is not updated when application is already in stop_application_jobs
    compare_sets(handler)
    assert process_1 not in handler.continue_process_jobs
    handler.stop_application_jobs.add(application_A)
    compare_sets(handler, stop_app={application_A})
    handler.add_restart_process_job(application_A, process_1)
    compare_sets(handler, stop_app={application_A})
    handler.stop_application_jobs.discard(application_A)
    # check that add_restart_process_job is not updated when application is already in restart_application_jobs
    # or in start_application_jobs and in the application start sequence
    handler.restart_application_jobs.add(application_A)
    compare_sets(handler, restart_app={application_A})
    handler.add_restart_process_job(application_A, process_2)
    compare_sets(handler, restart_app={application_A})
    handler.restart_application_jobs.discard(application_A)
    handler.start_application_jobs.add(application_A)
    compare_sets(handler, start_app={application_A})
    handler.add_restart_process_job(application_A, process_2)
    compare_sets(handler, start_app={application_A})
    handler.start_application_jobs.discard(application_A)
    # check that add_restart_process_job is not updated when process is already in start_process_jobs
    handler.start_process_jobs.add(process_2)
    compare_sets(handler, start_proc={process_2})
    handler.add_restart_process_job(application_A, process_2)
    compare_sets(handler, start_proc={process_2})
    handler.start_process_jobs.discard(process_2)
    # check that add_restart_process_job is updated when application is already in restart_application_jobs
    # or in start_application_jobs and not in the application start sequence
    handler.restart_application_jobs.add(application_A)
    compare_sets(handler, restart_app={application_A})
    handler.add_restart_process_job(application_A, process_1)
    compare_sets(handler, restart_app={application_A}, restart_proc={process_1})
    handler.restart_application_jobs.discard(application_A)
    handler.restart_process_jobs.discard(process_1)
    handler.start_application_jobs.add(application_A)
    compare_sets(handler, start_app={application_A})
    handler.add_restart_process_job(application_A, process_1)
    compare_sets(handler, start_app={application_A}, restart_proc={process_1})


def test_add_continue_process_job(add_jobs, handler):
    """ Test the addition of a new job using a CONTINUE strategy. """
    # create dummy applications and processes
    (process_1, process_2, process_3), (application_A, application_B) = add_jobs
    # check that continue_process_jobs is not updated when application is already in stop_application_jobs
    compare_sets(handler)
    assert process_1 not in handler.continue_process_jobs
    handler.stop_application_jobs.add(application_A)
    compare_sets(handler, stop_app={application_A})
    handler.add_continue_process_job(application_A, process_1)
    compare_sets(handler, stop_app={application_A})
    handler.stop_application_jobs.discard(application_A)
    # check that continue_process_jobs is not updated when application is already in restart_application_jobs
    # or in start_application_jobs and in the application start sequence
    handler.restart_application_jobs.add(application_A)
    compare_sets(handler, restart_app={application_A})
    handler.add_continue_process_job(application_A, process_2)
    compare_sets(handler, restart_app={application_A})
    handler.restart_application_jobs.discard(application_A)
    handler.start_application_jobs.add(application_A)
    compare_sets(handler, start_app={application_A})
    handler.add_continue_process_job(application_A, process_2)
    compare_sets(handler, start_app={application_A})
    handler.start_application_jobs.discard(application_A)
    # check that continue_process_jobs is not updated when process is already in restart_process_jobs
    # or in start_process_jobs
    handler.restart_process_jobs.add(process_2)
    compare_sets(handler, restart_proc={process_2})
    handler.add_continue_process_job(application_A, process_2)
    compare_sets(handler, restart_proc={process_2})
    handler.restart_process_jobs.discard(process_2)
    handler.start_process_jobs.add(process_2)
    compare_sets(handler, start_proc={process_2})
    handler.add_continue_process_job(application_A, process_2)
    compare_sets(handler, start_proc={process_2})
    handler.start_process_jobs.discard(process_2)
    # check that continue_process_jobs is updated when application is already in restart_application_jobs
    # or in start_application_jobs and not in the application start sequence
    handler.restart_application_jobs.add(application_A)
    compare_sets(handler, restart_app={application_A})
    handler.add_continue_process_job(application_A, process_1)
    compare_sets(handler, restart_app={application_A}, continue_proc={process_1})
    handler.restart_application_jobs.discard(application_A)
    handler.continue_process_jobs.discard(process_1)
    handler.start_application_jobs.add(application_A)
    compare_sets(handler, start_app={application_A})
    handler.add_continue_process_job(application_A, process_1)
    compare_sets(handler, start_app={application_A}, continue_proc={process_1})


def test_add_job(mocker, handler):
    """ Test the addition of a new job using a strategy. """
    mocker.patch.object(handler, 'add_stop_application_job')
    mocker.patch.object(handler, 'add_restart_application_job')
    mocker.patch.object(handler, 'add_restart_process_job')
    mocker.patch.object(handler, 'add_continue_process_job')
    # set context
    process = Mock(application_name='dummy_application')
    application = Mock(application_name='dummy_application')
    handler.supvisors.context.applications = {'dummy_application': application}
    # test adding CONTINUE jobs
    handler.add_job(RunningFailureStrategies.CONTINUE, process)
    assert not handler.add_stop_application_job.called
    assert not handler.add_restart_application_job.called
    assert not handler.add_restart_process_job.called
    assert handler.add_continue_process_job.call_args_list == [call(application, process)]
    mocker.resetall()
    # test adding RESTART_PROCESS jobs
    handler.add_job(RunningFailureStrategies.RESTART_PROCESS, process)
    assert not handler.add_stop_application_job.called
    assert not handler.add_restart_application_job.called
    assert handler.add_restart_process_job.call_args_list == [call(application, process)]
    assert not handler.add_continue_process_job.called
    mocker.resetall()
    # test adding RESTART_APPLICATION jobs
    handler.add_job(RunningFailureStrategies.RESTART_APPLICATION, process)
    assert not handler.add_stop_application_job.called
    assert handler.add_restart_application_job.call_args_list == [call(application)]
    assert not handler.add_restart_process_job.called
    assert not handler.add_continue_process_job.called
    mocker.resetall()
    # test adding STOP_APPLICATION jobs
    handler.add_job(RunningFailureStrategies.STOP_APPLICATION, process)
    assert handler.add_stop_application_job.call_args_list == [call(application)]
    assert not handler.add_restart_application_job.called
    assert not handler.add_restart_process_job.called
    assert not handler.add_continue_process_job.called


def test_add_default_job(mocker, handler):
    """ Test the addition of a new job using the strategy configured. """
    mocked_add = mocker.patch.object(handler, 'add_job')
    process = Mock(application_name='dummy_application')
    application = Mock(**{'stopped.return_value': False, 'get_start_sequenced_processes.return_value': []})
    handler.supvisors.context.applications['dummy_application'] = application
    # add a series of jobs without using RESTART_PROCESS
    for strategy in RunningFailureStrategies:
        if strategy != RunningFailureStrategies.RESTART_PROCESS:
            process.rules.running_failure_strategy = strategy
            handler.add_default_job(process)
            assert mocked_add.call_args_list == [call(strategy, process)]
            mocker.resetall()
    # test RESTART_PROCESS on an application still running
    process.rules.running_failure_strategy = RunningFailureStrategies.RESTART_PROCESS
    handler.add_default_job(process)
    assert mocked_add.call_args_list == [call(RunningFailureStrategies.RESTART_PROCESS, process)]
    mocker.resetall()
    # test RESTART_PROCESS on a stopped application but with process out of start sequence
    application.stopped.return_value = True
    handler.add_default_job(process)
    assert mocked_add.call_args_list == [call(RunningFailureStrategies.RESTART_PROCESS, process)]
    mocker.resetall()
    # test RESTART_PROCESS on a stopped application and with process in start sequence
    # a second job is added
    application.get_start_sequenced_processes.return_value = [process]
    handler.add_default_job(process)
    assert mocked_add.call_args_list == [call(RunningFailureStrategies.RESTART_PROCESS, process),
                                         call(RunningFailureStrategies.RESTART_APPLICATION, process)]


def test_get_job_applications(handler):
    """ Test getting the list of applications involved in Started and Stopper. """
    mocked_stopper = handler.supvisors.stopper.get_job_applications
    mocked_stopper.return_value = {'if', 'then'}
    mocked_starter = handler.supvisors.starter.get_job_applications
    mocked_starter.return_value = {'then', 'else'}
    assert handler.get_job_applications() == {'if', 'then', 'else'}


def test_trigger_stop_application_jobs(add_jobs, handler):
    """ Test the triggering of stop application jobs. """
    # create dummy applications and processes
    _, app_list = add_jobs
    application_A, application_B = app_list
    # update context
    compare_sets(handler)
    handler.stop_application_jobs.update(app_list)
    compare_sets(handler, stop_app=set(app_list))
    # test start_process calls depending on process state and involvement in Starter
    handler.trigger_stop_application_jobs({'dummy_application_B'})
    compare_sets(handler, stop_app={application_B})
    assert handler.supvisors.stopper.stop_application.call_args_list == [call(application_A)]


def test_restart_application_jobs(add_jobs, handler):
    """ Test the triggering of restart application jobs. """
    # create dummy applications and processes
    _, app_list = add_jobs
    application_A, application_B = app_list
    # update context
    compare_sets(handler)
    handler.restart_application_jobs.update(app_list)
    compare_sets(handler, restart_app=set(app_list))
    # test start_process calls depending on process state and involvement in Starter
    handler.trigger_restart_application_jobs({'dummy_application_B'})
    compare_sets(handler, restart_app={application_B}, start_app={application_A})
    assert handler.supvisors.stopper.stop_application.call_args_list == [call(application_A)]


def test_trigger_restart_process_jobs(add_jobs, handler):
    """ Test the triggering of restart process jobs. """
    # create dummy applications and processes
    proc_list, _ = add_jobs
    process_1, process_2, process_3 = proc_list
    # update context
    compare_sets(handler)
    handler.restart_process_jobs.update(proc_list)
    compare_sets(handler, restart_proc=set(proc_list))
    # test start_process calls depending on process state and involvement in Starter
    handler.trigger_restart_process_jobs({'dummy_application_B'})
    compare_sets(handler, restart_proc={process_3}, start_proc={process_1, process_2})
    handler.supvisors.stopper.stop_process.assert_has_calls([call(process_1), call(process_2)], any_order=True)
    assert not call(process_3) in handler.supvisors.stopper.stop_process.call_args_list


def test_trigger_start_application_jobs(add_jobs, handler):
    """ Test the triggering of start application jobs. """
    # create dummy applications and processes
    _, app_list = add_jobs
    application_A, application_B = app_list
    # check that continue_process_jobs is not updated when application is already in stop_application_jobs
    compare_sets(handler)
    # update context
    for application, stopped in zip(app_list, [True, False]):
        application.stopped.return_value = stopped
    compare_sets(handler)
    handler.start_application_jobs.update(app_list)
    compare_sets(handler, start_app=set(app_list))
    # test start_application calls depending on application state and involvement in Starter
    handler.trigger_start_application_jobs({'dummy_application_A'})
    compare_sets(handler, start_app=set(app_list))
    assert not handler.supvisors.starter.default_start_process.called
    # test start_process calls depending on process state and involvement in Starter
    handler.trigger_start_application_jobs({'dummy_application_B'})
    compare_sets(handler, start_app={application_B})
    assert handler.supvisors.starter.default_start_application.call_args_list == [call(application_A)]


def test_trigger_start_process_jobs(add_jobs, handler):
    """ Test the triggering of start process jobs. """
    # create dummy applications and processes
    proc_list, _ = add_jobs
    process_1, process_2, process_3 = proc_list
    # update context
    for process, stopped in zip(proc_list, [True, False, True]):
        process.stopped.return_value = stopped
    compare_sets(handler)
    handler.start_process_jobs.update(proc_list)
    compare_sets(handler, start_proc=set(proc_list))
    # test start_process calls depending on process state and involvement in Starter
    handler.trigger_start_process_jobs({'dummy_application_B'})
    compare_sets(handler, start_proc={process_2, process_3})
    assert handler.supvisors.starter.default_start_process.call_args_list == [call(process_1)]


def test_trigger_continue_process_jobs(add_jobs, handler):
    """ Test the triggering of continue jobs. """
    # create dummy applications and processes
    proc_list, _ = add_jobs
    # update context
    compare_sets(handler)
    handler.continue_process_jobs.update(proc_list)
    compare_sets(handler, continue_proc=set(proc_list))
    # check that continue_process_jobs is emptied after call to trigger_continue_process_jobs
    handler.trigger_continue_process_jobs()
    compare_sets(handler)


def test_trigger_jobs(mocker, handler):
    """ Test the processing of jobs. """
    mocker.patch.object(handler, 'trigger_stop_application_jobs')
    mocker.patch.object(handler, 'trigger_restart_application_jobs')
    mocker.patch.object(handler, 'trigger_restart_process_jobs')
    mocker.patch.object(handler, 'trigger_start_application_jobs')
    mocker.patch.object(handler, 'trigger_start_process_jobs')
    mocker.patch.object(handler, 'trigger_continue_process_jobs')
    mocker.patch.object(handler, 'get_job_applications', return_value={'dummy_application_A'})
    # test calls
    handler.trigger_jobs()
    assert handler.trigger_stop_application_jobs.call_args_list == [call({'dummy_application_A'})]
    assert handler.trigger_restart_application_jobs.call_args_list == [call({'dummy_application_A'})]
    assert handler.trigger_restart_process_jobs.call_args_list == [call({'dummy_application_A'})]
    assert handler.trigger_start_application_jobs.call_args_list == [call({'dummy_application_A'})]
    assert handler.trigger_start_process_jobs.call_args_list == [call({'dummy_application_A'})]
    assert handler.trigger_continue_process_jobs.call_args_list == [call()]
