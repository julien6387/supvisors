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
from supvisors.process import ProcessStatus
from supvisors.strategy import *
from supvisors.ttypes import AddressStates, ConciliationStrategies, RunningFailureStrategies, StartingStrategies


def mock_node(mocker, status: AddressStatus, node_state: AddressStates, load: int):
    """ Mock the AddressStatus. """
    status._state = node_state
    mocker.patch.object(status, 'get_load', return_value=load)


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
def starting_strategy(filled_nodes):
    """ Create the AbstractStartingStrategy instance to test. """
    return AbstractStartingStrategy(filled_nodes)


def test_is_loading_valid(starting_strategy):
    """ Test the validity of an address with an additional loading. """
    # test unknown address
    assert starting_strategy.is_loading_valid('10.0.0.0', 1) == (False, 0)
    # test not RUNNING address
    assert starting_strategy.is_loading_valid('10.0.0.1', 1) == (False, 0)
    assert starting_strategy.is_loading_valid('10.0.0.2', 1) == (False, 0)
    assert starting_strategy.is_loading_valid('10.0.0.4', 1) == (False, 0)
    # test loaded RUNNING address
    assert starting_strategy.is_loading_valid('127.0.0.1', 55) == (False, 50)
    assert starting_strategy.is_loading_valid('10.0.0.3', 85) == (False, 20)
    assert starting_strategy.is_loading_valid('10.0.0.5', 25) == (False, 80)
    # test not loaded RUNNING address
    assert starting_strategy.is_loading_valid('127.0.0.1', 45) == (True, 50)
    assert starting_strategy.is_loading_valid('10.0.0.3', 75) == (True, 20)
    assert starting_strategy.is_loading_valid('10.0.0.5', 15) == (True, 80)


def test_get_loading_and_validity(starting_strategy):
    """ Test the determination of the valid addresses with an additional loading. """
    # test valid addresses with different additional loadings
    node_names = starting_strategy.supvisors.address_mapper.node_names
    # first test
    expected = {'127.0.0.1': (True, 50), '10.0.0.1': (False, 0), '10.0.0.2': (False, 0),
                '10.0.0.3': (True, 20), '10.0.0.4': (False, 0), '10.0.0.5': (True, 80)}
    assert starting_strategy.get_loading_and_validity(node_names, 15) == expected
    # second test
    expected = {'127.0.0.1': (True, 50), '10.0.0.1': (False, 0), '10.0.0.2': (False, 0),
                '10.0.0.3': (True, 20), '10.0.0.4': (False, 0), '10.0.0.5': (False, 80)}
    assert starting_strategy.get_loading_and_validity(starting_strategy.supvisors.context.nodes.keys(), 45) == expected
    # third test
    expected = {'127.0.0.1': (False, 50), '10.0.0.3': (True, 20), '10.0.0.5': (False, 80)}
    assert starting_strategy.get_loading_and_validity(['127.0.0.1', '10.0.0.3', '10.0.0.5'], 75) == expected
    # fourth test
    expected = {'127.0.0.1': (False, 50), '10.0.0.3': (False, 20), '10.0.0.5': (False, 80)}
    assert starting_strategy.get_loading_and_validity(['127.0.0.1', '10.0.0.3', '10.0.0.5'], 85) == expected


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


def test_config_strategy(filled_nodes):
    """ Test the choice of an address according to the CONFIG strategy. """
    strategy = ConfigStrategy(filled_nodes)
    # test CONFIG strategy with different values
    node_names = filled_nodes.address_mapper.node_names
    assert strategy.get_node(node_names, 15) == '127.0.0.1'
    assert strategy.get_node(node_names, 45) == '127.0.0.1'
    assert strategy.get_node(node_names, 75) == '10.0.0.3'
    assert strategy.get_node(node_names, 85) is None


def test_less_loaded_strategy(filled_nodes):
    """ Test the choice of an address according to the LESS_LOADED strategy. """
    strategy = LessLoadedStrategy(filled_nodes)
    # test LESS_LOADED strategy with different values
    node_names = filled_nodes.address_mapper.node_names
    assert strategy.get_node(node_names, 15) == '10.0.0.3'
    assert strategy.get_node(node_names, 45) == '10.0.0.3'
    assert strategy.get_node(node_names, 75) == '10.0.0.3'
    assert strategy.get_node(node_names, 85) is None


def test_most_loaded_strategy(filled_nodes):
    """ Test the choice of an address according to the MOST_LOADED strategy. """
    strategy = MostLoadedStrategy(filled_nodes)
    # test MOST_LOADED strategy with different values
    node_names = filled_nodes.address_mapper.node_names
    assert strategy.get_node(node_names, 15) == '10.0.0.5'
    assert strategy.get_node(node_names, 45) == '127.0.0.1'
    assert strategy.get_node(node_names, 75) == '10.0.0.3'
    assert strategy.get_node(node_names, 85) is None


def test_local_strategy(filled_nodes):
    """ Test the choice of an address according to the LOCAL strategy. """
    strategy = LocalStrategy(filled_nodes)
    # test LOCAL strategy with different values
    node_names = filled_nodes.address_mapper.node_names
    assert strategy.supvisors.address_mapper.local_node_name == '127.0.0.1'
    assert strategy.get_node(node_names, 15) == '127.0.0.1'
    assert strategy.get_node(node_names, 45) == '127.0.0.1'
    assert strategy.get_node(node_names, 75) is None


def test_get_node(filled_nodes):
    """ Test the choice of a node according to a strategy. """
    # test CONFIG strategy
    node_names = filled_nodes.address_mapper.node_names
    assert get_node(filled_nodes, StartingStrategies.CONFIG, node_names, 15) == '127.0.0.1'
    assert get_node(filled_nodes, StartingStrategies.CONFIG, node_names, 75) == '10.0.0.3'
    assert get_node(filled_nodes, StartingStrategies.CONFIG, node_names, 85) is None
    # test LESS_LOADED strategy
    assert get_node(filled_nodes, StartingStrategies.LESS_LOADED, node_names, 15) == '10.0.0.3'
    assert get_node(filled_nodes, StartingStrategies.LESS_LOADED, node_names, 75) == '10.0.0.3'
    assert get_node(filled_nodes, StartingStrategies.LESS_LOADED, node_names, 85) is None
    # test MOST_LOADED strategy
    assert get_node(filled_nodes, StartingStrategies.MOST_LOADED, node_names, 15) == '10.0.0.5'
    assert get_node(filled_nodes, StartingStrategies.MOST_LOADED, node_names, 75) == '10.0.0.3'
    assert get_node(filled_nodes, StartingStrategies.MOST_LOADED, node_names, 85) is None
    # test LOCAL strategy
    assert get_node(filled_nodes, StartingStrategies.LOCAL, node_names, 15) == '127.0.0.1'
    assert get_node(filled_nodes, StartingStrategies.LOCAL, node_names, 75) is None


def create_process_status(name, timed_nodes):
    process_status = Mock(spec=ProcessStatus, process_name=name,
                          running_nodes=set(timed_nodes.keys()),
                          info_map={address_name: {'uptime': time} for address_name, time in timed_nodes.items()})
    process_status.namespec.return_value = name
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


def test_add_job(handler):
    """ Test the addition of a new job using a strategy. """
    # create a dummy process
    process_1 = Mock(application_name='dummy_application_A')
    process_2 = Mock(application_name='dummy_application_A')
    process_3 = Mock(application_name='dummy_application_B')
    # add a series of jobs
    handler.add_job(RunningFailureStrategies.CONTINUE, process_1)
    compare_sets(handler, continue_proc={process_1})
    handler.add_job(RunningFailureStrategies.RESTART_PROCESS, process_2)
    compare_sets(handler, restart_proc={process_2}, continue_proc={process_1})
    handler.add_job(RunningFailureStrategies.RESTART_PROCESS, process_1)
    compare_sets(handler, restart_proc={process_2, process_1})
    handler.add_job(RunningFailureStrategies.RESTART_PROCESS, process_3)
    compare_sets(handler, restart_proc={process_2, process_1, process_3})
    handler.add_job(RunningFailureStrategies.RESTART_PROCESS, process_3)
    compare_sets(handler, restart_proc={process_2, process_1, process_3})
    handler.add_job(RunningFailureStrategies.RESTART_APPLICATION, process_1)
    compare_sets(handler, restart_app={'dummy_application_A'}, restart_proc={process_3})
    handler.add_job(RunningFailureStrategies.STOP_APPLICATION, process_2)
    compare_sets(handler, stop_app={'dummy_application_A'}, restart_proc={process_3})
    handler.add_job(RunningFailureStrategies.RESTART_APPLICATION, process_2)
    compare_sets(handler, stop_app={'dummy_application_A'}, restart_proc={process_3})
    handler.add_job(RunningFailureStrategies.STOP_APPLICATION, process_1)
    compare_sets(handler, stop_app={'dummy_application_A'}, restart_proc={process_3})


def test_add_default_job(mocker, handler):
    """ Test the addition of a new job using the strategy configured. """
    # create a dummy process
    process = Mock()
    process.rules = Mock(running_failure_strategy=2)
    # add a series of jobs
    mocked_add = mocker.patch.object(handler, 'add_job')
    handler.add_default_job(process)
    assert mocked_add.call_args_list == [call(2, process)]


def test_get_job_applications(handler):
    """ Test getting the list of applications involved in Started and Stopper. """
    mocked_stopper = handler.supvisors.stopper.get_job_applications
    mocked_stopper.return_value = {'if', 'then'}
    mocked_starter = handler.supvisors.starter.get_job_applications
    mocked_starter.return_value = {'then', 'else'}
    assert handler.get_job_applications() == {'if', 'then', 'else'}


def mocked_application(supvisors, application_name, stopped):
    """ Return a mocked ApplicationStatus. """
    application = Mock(application_name=application_name, **{'stopped.side_effect': [stopped, True]})
    supvisors.context.applications[application_name] = application
    return application


def mocked_process(namespec, application_name, stopped):
    """ Return a mocked ProcessStatus. """
    return Mock(application_name=application_name, **{'namespec.return_value': namespec,
                                                      'stopped.side_effect': [stopped, True]})


def test_trigger_jobs(mocker, handler):
    """ Test the processing of jobs. """
    # create mocked applications
    stop_appli_A = mocked_application(handler.supvisors, 'stop_application_A', False)
    stop_appli_B = mocked_application(handler.supvisors, 'stop_application_B', False)
    restart_appli_A = mocked_application(handler.supvisors, 'restart_application_A', False)
    restart_appli_B = mocked_application(handler.supvisors, 'restart_application_B', False)
    start_appli_A = mocked_application(handler.supvisors, 'start_application_A', True)
    start_appli_B = mocked_application(handler.supvisors, 'start_application_B', True)
    # create mocked processes
    restart_process_1 = mocked_process('restart_process_1', 'restart_application_1', False)
    restart_process_2 = mocked_process('restart_process_2', 'restart_application_2', False)
    start_process_1 = mocked_process('start_process_1', 'start_application_1', True)
    start_process_2 = mocked_process('start_process_2', 'start_application_2', True)
    continue_process = mocked_process('continue_process', 'continue_application', False)
    # pre-fill sets
    handler.stop_application_jobs = {'stop_application_A', 'stop_application_B'}
    handler.restart_application_jobs = {'restart_application_A', 'restart_application_B'}
    handler.restart_process_jobs = {restart_process_1, restart_process_2}
    handler.continue_process_jobs = {continue_process}
    handler.start_application_jobs = {start_appli_A, start_appli_B}
    handler.start_process_jobs = {start_process_1, start_process_2}
    # get patches to starter and stopper
    mocked_stop_app = handler.supvisors.stopper.stop_application
    mocked_start_app = handler.supvisors.starter.default_start_application
    mocked_stop_proc = handler.supvisors.stopper.stop_process
    mocked_start_proc = handler.supvisors.starter.default_start_process
    # patch check_commander so that it is considered that applications are already being handled in Start / Stopper
    application_list = {'stop_application_A', 'stop_application_B', 'restart_application_A', 'restart_application_B',
                        'start_application_A', 'start_application_B', 'restart_application_1', 'restart_application_2',
                        'start_application_1', 'start_application_2', 'continue_application'}
    mocked_jobs = mocker.patch.object(handler, 'get_job_applications', return_value=application_list)
    # test jobs trigger
    handler.trigger_jobs()
    print(mocked_start_app.call_args_list)
    # check there has been no application calls
    assert not mocked_stop_app.called
    assert not mocked_start_app.called
    assert not mocked_stop_proc.called
    assert not mocked_start_proc.called
    # check impact on sets
    compare_sets(handler, stop_app={'stop_application_A', 'stop_application_B'},
                 restart_app={'restart_application_A', 'restart_application_B'},
                 start_app={start_appli_A, start_appli_B},
                 restart_proc={restart_process_1, restart_process_2},
                 start_proc={start_process_1, start_process_2})
    # patch check_commander so that it is considered that applications are not being handled in Start / Stopper
    mocked_jobs.return_value = set()
    handler.trigger_jobs()
    # check stop application calls
    expected = [call(stop_appli_A), call(stop_appli_B), call(restart_appli_A), call(restart_appli_B)]
    mocked_stop_app.assert_has_calls(expected, any_order=True)
    # test start application calls
    expected = [call(start_appli_A), call(start_appli_B)]
    mocked_start_app.assert_has_calls(expected, any_order=True)
    # test stop process calls
    expected = [call(restart_process_1), call(restart_process_2)]
    mocked_stop_proc.assert_has_calls(expected, any_order=True)
    # test start process calls
    expected = [call(start_process_1), call(start_process_2)]
    mocked_start_proc.assert_has_calls(expected, any_order=True)
    # check impact on sets
    compare_sets(handler, start_app={restart_appli_A, restart_appli_B},
                 start_proc={restart_process_1, restart_process_2})
