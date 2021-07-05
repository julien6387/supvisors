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

from unittest.mock import call, patch, Mock

from supvisors.statemachine import FiniteStateMachine
from supvisors.ttypes import SupvisorsStates

from supvisors.tests.base import database_copy
from supvisors.tests.conftest import create_application, create_process


@pytest.fixture
def supvisors_ctx(supvisors):
    """ Create a Supvisors-like structure filled with some nodes. """
    from supvisors.address import AddressStatus
    from supvisors.ttypes import AddressStates
    # assign nodes to context
    nodes = supvisors.context.nodes
    for node_name in supvisors.address_mapper.node_names:
        nodes[node_name] = AddressStatus(node_name, supvisors.logger)
    nodes['127.0.0.1']._state = AddressStates.RUNNING
    nodes['10.0.0.1']._state = AddressStates.SILENT
    nodes['10.0.0.2']._state = AddressStates.RUNNING
    nodes['10.0.0.3']._state = AddressStates.ISOLATING
    nodes['10.0.0.4']._state = AddressStates.RUNNING
    nodes['10.0.0.5']._state = AddressStates.ISOLATED
    return supvisors


def test_abstract_state(supvisors_ctx):
    """ Test the Abstract state of the self.fsm. """
    from supvisors.statemachine import AbstractState
    state = AbstractState(supvisors_ctx)
    # check attributes at creation
    assert state.supvisors is supvisors_ctx
    assert state.local_node_name == '127.0.0.1'
    # call empty methods
    state.enter()
    state.next()
    state.exit()
    # test apply_addresses_func method
    mock_function = Mock()
    mock_function.__name__ = 'dummy_name'
    state.apply_nodes_func(mock_function)
    assert mock_function.call_args_list == [call('10.0.0.2'), call('10.0.0.4'), call('127.0.0.1')]


def test_initialization_state(supvisors_ctx):
    """ Test the Initialization state of the fsm. """
    from supvisors.statemachine import AbstractState, InitializationState
    from supvisors.ttypes import AddressStates, SupvisorsStates
    state = InitializationState(supvisors_ctx)
    assert isinstance(state, AbstractState)
    # 1. test enter method: master and start_date are reset
    # test that all nodes that are not in an isolation state are reset to UNKNOWN
    state.enter()
    assert state.context.master_node_name == ''
    assert int(time.time()) >= state.start_date
    assert supvisors_ctx.context.nodes['127.0.0.1'].state == AddressStates.UNKNOWN
    assert supvisors_ctx.context.nodes['10.0.0.1'].state == AddressStates.UNKNOWN
    assert supvisors_ctx.context.nodes['10.0.0.2'].state == AddressStates.UNKNOWN
    assert supvisors_ctx.context.nodes['10.0.0.3'].state == AddressStates.ISOLATING
    assert supvisors_ctx.context.nodes['10.0.0.4'].state == AddressStates.UNKNOWN
    assert supvisors_ctx.context.nodes['10.0.0.5'].state == AddressStates.ISOLATED
    # 2. test next method
    # test that Supvisors wait for all nodes to be running or a given timeout is reached
    supvisors_ctx.context.forced_nodes = []
    supvisors_ctx.context.running_nodes.return_value = []
    # test case no node is running, especially local node
    result = state.next()
    assert result == SupvisorsStates.INITIALIZATION
    # test case where addresses are still unknown and timeout is not reached
    supvisors_ctx.context.running_nodes.return_value = ['127.0.0.1', '10.0.0.2']
    supvisors_ctx.context.unknown_nodes.return_value = ['10.0.0.1', '10.0.0.3']
    supvisors_ctx.context.unknown_forced_nodes.return_value = []
    result = state.next()
    assert result == SupvisorsStates.INITIALIZATION
    # test case where no addresses are still unknown
    supvisors_ctx.context.running_nodes.return_value = ['127.0.0.1', '10.0.0.2']
    supvisors_ctx.context.unknown_nodes.return_value = []
    supvisors_ctx.context.unknown_forced_nodes.return_value = []
    result = state.next()
    assert result == SupvisorsStates.DEPLOYMENT
    # test case where end of synchro is forced based on a subset of addresses
    supvisors_ctx.context.forced_nodes = ['10.0.0.2', '10.0.0.4']
    supvisors_ctx.context.running_nodes.return_value = ['127.0.0.1', '10.0.0.2']
    supvisors_ctx.context.unknown_nodes.return_value = ['10.0.0.1', '10.0.0.3']
    supvisors_ctx.context.unknown_forced_nodes.return_value = []
    result = state.next()
    assert result == SupvisorsStates.DEPLOYMENT
    # test case where addresses are still unknown and timeout is reached
    supvisors_ctx.context.forced_nodes = []
    state.start_date = time.time() - 11
    result = state.next()
    assert result == SupvisorsStates.DEPLOYMENT
    supvisors_ctx.context.unknown_nodes.return_value = []
    result = state.next()
    assert result == SupvisorsStates.DEPLOYMENT
    # 3. test exit method
    # test that context end_synchro is called and master is the lowest string among address names
    supvisors_ctx.context.running_nodes.return_value = ['127.0.0.1', '10.0.0.2', '10.0.0.4']
    supvisors_ctx.context.end_synchro.return_value = ['127.0.0.1', '10.0.0.2', '10.0.0.4']
    mocked_synchro = supvisors_ctx.context.end_synchro
    state.exit()
    assert mocked_synchro.call_count == 1
    assert supvisors_ctx.context.master_node_name == '10.0.0.2'


def test_deployment_state(supvisors_ctx):
    """ Test the Deployment state of the fsm. """
    from supvisors.statemachine import AbstractState, DeploymentState
    from supvisors.ttypes import ApplicationStates, SupvisorsStates
    state = DeploymentState(supvisors_ctx)
    assert isinstance(state, AbstractState)
    # test enter method
    # test that start_applications is  called only when local address is the master address
    mocked_starter = supvisors_ctx.starter.start_applications
    supvisors_ctx.context.is_master = False
    state.enter()
    assert not mocked_starter.called
    # now master address is local
    supvisors_ctx.context.is_master = True
    state.enter()
    assert mocked_starter.call_count == 1
    # create application context
    application = create_application('sample_test_2', supvisors_ctx)
    supvisors_ctx.context.applications['sample_test_2'] = application
    for info in database_copy():
        if info['group'] == 'sample_test_2':
            process = create_process(info, supvisors_ctx)
            process.rules.start_sequence = len(process.namespec()) % 3
            process.rules.stop_sequence = len(process.namespec()) % 3 + 1
            process.add_info('10.0.0.1', info)
            application.add_process(process)
    # test application updates
    supvisors_ctx.context.is_master = False
    assert application.state == ApplicationStates.STOPPED
    assert not application.minor_failure
    assert not application.major_failure
    assert application.start_sequence == {}
    assert application.stop_sequence == {}
    state.enter()
    application = supvisors_ctx.context.applications['sample_test_2']
    assert application.state == ApplicationStates.RUNNING
    assert application.minor_failure
    assert not application.major_failure
    # list order may differ, so break down
    assert sorted(application.start_sequence.keys()) == [0, 1]
    assert len(application.start_sequence[0]) == 2
    assert all(item in [application.processes['yeux_01'], application.processes['yeux_00']]
               for item in application.start_sequence[0])
    assert application.start_sequence[1] == [application.processes['sleep']]
    assert sorted(application.stop_sequence.keys()) == [1, 2]
    assert len(application.stop_sequence[1]) == 2
    assert all(item in [application.processes['yeux_01'], application.processes['yeux_00']]
               for item in application.stop_sequence[1])
    assert application.stop_sequence[2] == [application.processes['sleep']]
    # test next method if the local node is master
    supvisors_ctx.context.is_master = True
    # stay in DEPLOYMENT if a start sequence is in progress, whatever the local operational status
    supvisors_ctx.starter.check_starting.return_value = False
    for operational in [True, False]:
        supvisors_ctx.context.master_operational = operational
        result = state.next()
        assert result == SupvisorsStates.DEPLOYMENT
    # return OPERATION  and no start sequence is in progress, whatever the local operational status
    supvisors_ctx.starter.check_starting.return_value = True
    for operational in [True, False]:
        supvisors_ctx.context.master_operational = operational
        result = state.next()
        assert result == SupvisorsStates.OPERATION
    # test next method if the local node is NOT master
    supvisors_ctx.context.is_master = False
    # stay in DEPLOYMENT if the master node is not operational, whatever the start sequence status
    supvisors_ctx.context.master_operational = False
    for starting in [True, False]:
        supvisors_ctx.starter.check_starting.return_value = starting
        result = state.next()
        assert result == SupvisorsStates.DEPLOYMENT
    # return OPERATION if the master node is operational, whatever the start sequence status
    supvisors_ctx.context.master_operational = True
    for starting in [True, False]:
        supvisors_ctx.starter.check_starting.return_value = starting
        result = state.next()
        assert result == SupvisorsStates.OPERATION
    # no exit implementation. just call it without test
    state.exit()


def test_operation_state(supvisors_ctx):
    """ Test the Operation state of the fsm. """
    from supvisors.address import AddressStatus
    from supvisors.statemachine import AbstractState, OperationState
    from supvisors.ttypes import AddressStates, SupvisorsStates
    state = OperationState(supvisors_ctx)
    assert isinstance(state, AbstractState)
    # no enter implementation. just call it without test
    state.enter()
    # test next method
    # do not leave OPERATION state if a starting or a stopping is in progress
    with patch.object(supvisors_ctx.starter, 'check_starting', return_value=False):
        result = state.next()
        assert result == SupvisorsStates.OPERATION
    with patch.object(supvisors_ctx.stopper, 'check_stopping', return_value=False):
        result = state.next()
        assert result == SupvisorsStates.OPERATION
    # create address context
    for node_name in supvisors_ctx.address_mapper.node_names:
        status = AddressStatus(node_name, supvisors_ctx.logger)
        supvisors_ctx.context.nodes[node_name] = status
    # declare local and master address running
    supvisors_ctx.context.master_node_name = '10.0.0.3'
    supvisors_ctx.context.nodes['127.0.0.1']._state = AddressStates.RUNNING
    supvisors_ctx.context.nodes['10.0.0.3']._state = AddressStates.RUNNING
    # consider that no starting or stopping is in progress
    with patch.object(supvisors_ctx.starter, 'check_starting', return_value=True):
        with patch.object(supvisors_ctx.stopper, 'check_stopping', return_value=True):
            # stay in OPERATION if local address and master address are RUNNING and no conflict
            with patch.object(supvisors_ctx.context, 'conflicting', return_value=False):
                result = state.next()
                assert result == SupvisorsStates.OPERATION
            # transit to CONCILIATION if local address and master address are RUNNING and conflict detected
            with patch.object(supvisors_ctx.context, 'conflicting', return_value=True):
                result = state.next()
                assert result == SupvisorsStates.CONCILIATION
            # transit to INITIALIZATION state if the local address or master address is not RUNNING
            supvisors_ctx.context.nodes['127.0.0.1']._state = AddressStates.SILENT
            result = state.next()
            assert result == SupvisorsStates.INITIALIZATION
            supvisors_ctx.context.nodes['127.0.0.1']._state = AddressStates.RUNNING
            supvisors_ctx.context.nodes['10.0.0.3']._state = AddressStates.SILENT
            result = state.next()
            assert result == SupvisorsStates.INITIALIZATION
    # no exit implementation. just call it without test
    state.exit()


@patch('supvisors.statemachine.conciliate_conflicts')
def test_conciliation_state(mocked_conciliate, supvisors_ctx):
    """ Test the Conciliation state of the fsm. """
    from supvisors.address import AddressStatus
    from supvisors.statemachine import AbstractState, ConciliationState
    from supvisors.ttypes import AddressStates, SupvisorsStates
    state = ConciliationState(supvisors_ctx)
    assert isinstance(state, AbstractState)
    # test enter method
    supvisors_ctx.context.conflicts.return_value = [1, 2, 3]
    # nothing done if local is not master
    supvisors_ctx.context.is_master = False
    state.enter()
    assert not mocked_conciliate.called
    # conciliation called if local is master
    supvisors_ctx.context.is_master = True
    state.enter()
    assert mocked_conciliate.call_args_list == [call(supvisors_ctx, 0, [1, 2, 3])]
    # test next method
    # do not leave CONCILIATION state if a starting or a stopping is in progress
    supvisors_ctx.starter.check_starting.return_value = False
    supvisors_ctx.stopper.check_stopping.return_value = False
    result = state.next()
    assert result == SupvisorsStates.CONCILIATION
    supvisors_ctx.starter.check_starting.return_value = True
    supvisors_ctx.stopper.check_stopping.return_value = False
    result = state.next()
    assert result == SupvisorsStates.CONCILIATION
    supvisors_ctx.starter.check_starting.return_value = False
    supvisors_ctx.stopper.check_stopping.return_value = True
    result = state.next()
    assert result == SupvisorsStates.CONCILIATION
    # create address context
    nodes = supvisors_ctx.context.nodes
    for address_name in supvisors_ctx.address_mapper.node_names:
        nodes[address_name] = AddressStatus(address_name, supvisors_ctx.logger)
    # declare local and master address running
    supvisors_ctx.context.master_node_name = '10.0.0.3'
    nodes['127.0.0.1']._state = AddressStates.RUNNING
    nodes['10.0.0.3']._state = AddressStates.RUNNING
    # consider that no starting or stopping is in progress
    supvisors_ctx.starter.check_starting.return_value = True
    supvisors_ctx.stopper.check_stopping.return_value = True
    # if local address and master address are RUNNING and conflict still detected, re-enter CONCILIATION
    supvisors_ctx.context.conflicting.return_value = True
    with patch.object(state, 'enter') as mocked_enter:
        result = state.next()
        assert mocked_enter.call_count == 1
        assert result == SupvisorsStates.CONCILIATION
    # transit to OPERATION if local node and master node are RUNNING and no conflict detected
    supvisors_ctx.context.conflicting.return_value = False
    result = state.next()
    assert result == SupvisorsStates.OPERATION
    # transit to INITIALIZATION state if the local address or master address is not RUNNING
    nodes['127.0.0.1']._state = AddressStates.SILENT
    result = state.next()
    assert result == SupvisorsStates.INITIALIZATION
    nodes['127.0.0.1']._state = AddressStates.RUNNING
    nodes['10.0.0.3']._state = AddressStates.SILENT
    result = state.next()
    assert result == SupvisorsStates.INITIALIZATION
    # no exit implementation. just call it without test
    state.exit()


def test_restarting_state(supvisors_ctx):
    """ Test the Restarting state of the fsm. """
    from supvisors.statemachine import AbstractState, RestartingState
    from supvisors.ttypes import SupvisorsStates
    state = RestartingState(supvisors_ctx)
    assert isinstance(state, AbstractState)
    # test enter method: starting ang stopping in progress are aborted
    with patch.object(supvisors_ctx.starter, 'abort') as mocked_starter:
        with patch.object(supvisors_ctx.stopper, 'stop_applications') as mocked_stopper:
            state.enter()
            assert mocked_starter.call_count == 1
            assert mocked_stopper.call_count == 1
    # test next method: all processes are stopped
    with patch.object(supvisors_ctx.stopper, 'check_stopping', return_value=True):
        result = state.next()
        assert result == SupvisorsStates.SHUTDOWN
    with patch.object(supvisors_ctx.stopper, 'check_stopping', return_value=False):
        result = state.next()
        assert result == SupvisorsStates.RESTARTING
    # test exit method: call to pusher send_restart for all addresses
    with patch.object(state, 'apply_nodes_func') as mocked_apply:
        state.exit()
        assert mocked_apply.call_count == 1
        assert mocked_apply.call_args == call(supvisors_ctx.zmq.pusher.send_restart)


def test_shutting_down_state(supvisors_ctx):
    """ Test the ShuttingDown state of the fsm. """
    from supvisors.statemachine import AbstractState, ShuttingDownState
    from supvisors.ttypes import SupvisorsStates
    state = ShuttingDownState(supvisors_ctx)
    assert isinstance(state, AbstractState)
    # test enter method: starting ang stopping in progress are aborted
    with patch.object(supvisors_ctx.starter, 'abort') as mocked_starter:
        with patch.object(supvisors_ctx.stopper, 'stop_applications') as mocked_stopper:
            state.enter()
            assert mocked_starter.call_count == 1
            assert mocked_stopper.call_count == 1
    # test next method: all processes are stopped
    with patch.object(supvisors_ctx.stopper, 'check_stopping', return_value=True):
        result = state.next()
        assert result == SupvisorsStates.SHUTDOWN
    with patch.object(supvisors_ctx.stopper, 'check_stopping', return_value=False):
        result = state.next()
        assert result == SupvisorsStates.SHUTTING_DOWN
    # test exit method: call to pusher send_shutdown for all addresses
    with patch.object(state, 'apply_nodes_func') as mocked_apply:
        state.exit()
        assert mocked_apply.call_count == 1
        assert mocked_apply.call_args == call(supvisors_ctx.zmq.pusher.send_shutdown)


def test_shutdown_state(supvisors_ctx):
    """ Test the ShutDown state of the fsm. """
    from supvisors.statemachine import AbstractState, ShutdownState
    state = ShutdownState(supvisors_ctx)
    assert isinstance(state, AbstractState)
    # no enter / next / exit implementation. just call it without test
    state.enter()
    state.next()
    state.exit()


@pytest.fixture
def fsm(supvisors):
    """ Create the FiniteStateMachine instance to test. """
    # create state machine instance to be tested
    supvisors.context.running_nodes.return_value = {}
    return FiniteStateMachine(supvisors)


def test_creation(supvisors, fsm):
    """ Test the values set at construction. """
    from supvisors.statemachine import InitializationState
    from supvisors.ttypes import SupvisorsStates
    # test that the INITIALIZATION state is triggered at creation
    assert fsm.supvisors is supvisors
    assert fsm.state == SupvisorsStates.INITIALIZATION
    assert isinstance(fsm.instance, InitializationState)


def test_state_string(fsm):
    """ Test the string conversion of state machine. """
    from supvisors.ttypes import SupvisorsStates
    # test string conversion for all states
    for state in SupvisorsStates:
        fsm.state = state
        assert fsm.state.name == state.name


def test_serial(fsm):
    """ Test the serialization of state machine. """
    from supvisors.ttypes import SupvisorsStates
    # test serialization for all states
    for state in SupvisorsStates:
        fsm.state = state
        assert fsm.serial() == {'statecode': state.value, 'statename': state.name}


# Patch all state events
STATES = [cls.__name__ for cls in FiniteStateMachine._StateInstances.values()]
EVENTS = ['enter', 'next', 'exit']


@pytest.fixture
def mock_events(mocker):
    return [mocker.patch('supvisors.statemachine.%s.%s' % (cls, evt))
            for cls in STATES
            for evt in EVENTS]


def compare_calls(call_counts, mock_events):
    """ Compare call counts of mocked methods. """
    for call_count, mocked in zip(call_counts, mock_events):
        assert mocked.call_count == call_count
        mocked.reset_mock()


def test_simple_set_state(fsm, mock_events):
    """ Test single transitions of the state machine using set_state method.
    Beware of the fixture sequence.
    If mock_events is set before fsm, mocks will capture the calls triggered from the FiniteStateMachine constructor.
    """
    instance_ref = fsm.instance
    # test set_state with identical state parameter
    fsm.set_state(SupvisorsStates.INITIALIZATION)
    compare_calls([0, 0, 0, 0, 0, 0], mock_events)
    assert fsm.instance is instance_ref
    assert fsm.state == SupvisorsStates.INITIALIZATION
    # test set_state with not authorized transition
    fsm.set_state(SupvisorsStates.OPERATION)
    compare_calls([0, 0, 0, 0, 0, 0], mock_events)
    assert fsm.instance is instance_ref
    assert fsm.state == SupvisorsStates.INITIALIZATION
    # test set_state with authorized transition
    fsm.set_state(SupvisorsStates.DEPLOYMENT)
    compare_calls([0, 0, 1, 1, 1, 0], mock_events)
    assert fsm.instance is not instance_ref
    assert fsm.state == SupvisorsStates.DEPLOYMENT


def test_complex_set_state(fsm, mock_events):
    """ Test multiple transitions of the state machine using set_state method. """
    mock_events[4].return_value = SupvisorsStates.OPERATION
    instance_ref = fsm.instance
    # test set_state with authorized transition
    fsm.set_state(SupvisorsStates.DEPLOYMENT)
    compare_calls([0, 0, 1, 1, 1, 1, 1, 1, 0], mock_events)
    assert fsm.instance is not instance_ref
    assert fsm.state == SupvisorsStates.OPERATION


def test_no_next(fsm, mock_events):
    """ Test no transition of the state machine using next_method. """
    mock_events[1].return_value = SupvisorsStates.INITIALIZATION
    instance_ref = fsm.instance
    # test set_state with authorized transition
    fsm.next()
    compare_calls([0, 1, 0], mock_events)
    assert fsm.instance is instance_ref
    assert fsm.state == SupvisorsStates.INITIALIZATION


def test_simple_next(fsm, mock_events):
    """ Test single transition of the state machine using next_method. """
    mock_events[1].return_value = SupvisorsStates.DEPLOYMENT
    mock_events[4].return_value = SupvisorsStates.DEPLOYMENT
    instance_ref = fsm.instance
    # test set_state with authorized transition
    fsm.next()
    compare_calls([0, 1, 1, 1, 1, 0], mock_events)
    assert fsm.instance is not instance_ref
    assert fsm.state == SupvisorsStates.DEPLOYMENT


def test_complex_next(fsm, mock_events):
    """ Test multiple transitions of the state machine using next_method. """
    from supvisors.ttypes import SupvisorsStates
    mock_events[1].side_effect = [SupvisorsStates.DEPLOYMENT, SupvisorsStates.DEPLOYMENT]
    mock_events[4].side_effect = [SupvisorsStates.OPERATION, SupvisorsStates.OPERATION]
    mock_events[7].side_effect = [SupvisorsStates.CONCILIATION, SupvisorsStates.INITIALIZATION, SupvisorsStates.RESTARTING]
    mock_events[10].side_effect = [SupvisorsStates.OPERATION]
    mock_events[13].return_value = SupvisorsStates.SHUTDOWN
    instance_ref = fsm.instance
    # test set_state with authorized transition
    fsm.next()
    compare_calls([1, 2, 2, 2, 2, 2, 3, 3, 3, 1, 1, 1, 1, 1, 1, 0, 0, 0, 1, 1, 0], mock_events)
    assert fsm.instance is not instance_ref
    assert fsm.state == SupvisorsStates.SHUTDOWN


def test_timer_event(fsm):
    """ Test the actions triggered in state machine upon reception of a timer event. """
    # apply patches
    mocked_isolation = fsm.supvisors.context.handle_isolation
    mocked_isolation.return_value = [2, 3]
    mocked_event = fsm.supvisors.context.on_timer_event
    mocked_failure = fsm.supvisors.failure_handler.trigger_jobs
    # test that context on_timer_event is always called
    # test that fsm next is always called
    # test that result of context handle_isolation is always returned
    with patch.object(fsm, 'next') as mocked_next:
        result = fsm.on_timer_event()
        # check result: marked processes are started
        assert result == [2, 3]
        assert mocked_next.call_count == 1
        assert mocked_event.call_count == 1
        assert mocked_failure.call_count == 1
        assert mocked_isolation.call_count == 1


def test_tick_event(fsm):
    """ Test the actions triggered in state machine upon reception of a tick event. """
    # inject tick event and test call to context on_tick_event
    with patch.object(fsm.supvisors.context, 'on_tick_event') as mocked_evt:
        fsm.on_tick_event('10.0.0.1', 1234)
        assert mocked_evt.call_count == 1
        assert mocked_evt.call_args == call('10.0.0.1', 1234)


# FIXME: test calls to failure_handler + master + crashed
def test_process_event(fsm):
    """ Test the actions triggered in state machine upon reception of a process event. """
    # prepare context
    process = Mock(application_name='appli')
    # get patches
    mocked_start_evt = fsm.supvisors.starter.on_event
    mocked_stop_evt = fsm.supvisors.stopper.on_event
    mocked_ctx = fsm.supvisors.context.on_process_event
    mocked_start_has = fsm.supvisors.starter.has_application
    mocked_stop_has = fsm.supvisors.stopper.has_application
    # inject process event
    mocked_ctx.return_value = None
    mocked_start_has.return_value = False
    mocked_stop_has.return_value = False
    # test that context on_process_event is always called
    # test that starter and stopper are not involved when corresponding process is not found
    fsm.on_process_event('10.0.0.1', ['dummy_event'])
    assert mocked_ctx.call_args_list == [call('10.0.0.1', ['dummy_event'])]
    assert mocked_start_has.call_count == 0
    assert mocked_stop_has.call_count == 0
    assert mocked_start_evt.call_count == 0
    assert mocked_stop_evt.call_count == 0
    # inject process event
    mocked_ctx.return_value = process
    mocked_ctx.reset_mock()
    # test that context on_process_event is always called
    # test that event is not pushed to starter and stopper when a starting or stopping is not in progress
    fsm.on_process_event('10.0.0.1', ['dummy_event'])
    assert mocked_ctx.call_args_list == [call('10.0.0.1', ['dummy_event'])]
    assert mocked_start_has.call_args_list == [call('appli')]
    assert mocked_stop_has.call_args_list == [call('appli')]
    assert mocked_start_evt.call_args_list == [call(process)]
    assert mocked_stop_evt.call_args_list == [call(process)]
    # inject process event
    mocked_start_has.reset_mock()
    mocked_start_has.return_value = True
    mocked_stop_has.reset_mock()
    mocked_stop_has.return_value = True
    mocked_ctx.reset_mock()
    mocked_start_evt.reset_mock()
    mocked_stop_evt.reset_mock()
    # test that context on_process_event is always called
    # test that event is pushed to starter and stopper when a starting or stopping is in progress
    fsm.on_process_event('10.0.0.1', ['dummy_event'])
    assert mocked_ctx.call_args_list == [call('10.0.0.1', ['dummy_event'])]
    assert mocked_start_has.call_args_list == [call('appli')]
    assert mocked_stop_has.call_args_list == [call('appli')]
    assert mocked_start_evt.call_args_list == [call(process)]
    assert mocked_stop_evt.call_args_list == [call(process)]


def test_on_process_info(fsm):
    """ Test the actions triggered in state machine upon reception of a process information. """
    # inject process info and test call to context load_processes
    with patch.object(fsm.supvisors.context, 'load_processes') as mocked_load:
        fsm.on_process_info('10.0.0.1', {'info': 'dummy_info'})
        assert mocked_load.call_count == 1
        assert mocked_load.call_args == call('10.0.0.1', {'info': 'dummy_info'})


def test_on_state_event(fsm):
    """ Test the actions triggered in state machine upon reception of a Master state event. """
    from supvisors.ttypes import SupvisorsStates
    fsm.context.master_node_name = '10.0.0.1'
    # test event not sent by Master node
    for state in SupvisorsStates:
        payload = {'statecode': state}
        fsm.on_state_event('10.0.0.2', payload)
        assert not fsm.supvisors.context.master_operational.called
    # test event sent by Master node
    for state in SupvisorsStates:
        payload = {'statecode': state}
        fsm.on_state_event('10.0.0.1', payload)
        assert fsm.supvisors.context.master_operational == (state == SupvisorsStates.OPERATION)


def test_on_authorization(fsm):
    """ Test the actions triggered in state machine upon reception of an authorization event. """
    from supvisors.ttypes import SupvisorsStates
    fsm.set_state(SupvisorsStates.OPERATION)
    # prepare context
    fsm.supvisors.context.master_node_name = ''
    fsm.supvisors.context.master_operational = False
    mocked_auth = fsm.context.on_authorization
    mocked_auth.return_value = False
    # test rejected authorization
    fsm.on_authorization('10.0.0.1', False, '10.0.0.5', SupvisorsStates.INITIALIZATION)
    assert mocked_auth.call_args_list == [call('10.0.0.1', False)]
    assert fsm.supvisors.context.master_node_name == ''
    assert not fsm.supvisors.context.master_operational
    # reset mocks
    mocked_auth.reset_mock()
    mocked_auth.return_value = True
    # test authorization when no master node provided
    fsm.on_authorization('10.0.0.1', True, '', SupvisorsStates.INITIALIZATION)
    assert mocked_auth.call_args == call('10.0.0.1', True)
    assert fsm.supvisors.context.master_node_name == ''
    assert not fsm.supvisors.context.master_operational
    # reset mocks
    mocked_auth.reset_mock()
    # test authorization and master node assignment
    fsm.on_authorization('10.0.0.1', True, '10.0.0.5', SupvisorsStates.INITIALIZATION)
    assert mocked_auth.call_args == call('10.0.0.1', True)
    assert fsm.supvisors.context.master_node_name == '10.0.0.5'
    assert not fsm.supvisors.context.master_operational
    # reset mocks
    mocked_auth.reset_mock()
    # test authorization and master node operational
    fsm.on_authorization('10.0.0.5', True, '10.0.0.5', SupvisorsStates.OPERATION)
    assert mocked_auth.call_args == call('10.0.0.5', True)
    assert fsm.supvisors.context.master_node_name == '10.0.0.5'
    assert fsm.supvisors.context.master_operational
    # reset mocks
    mocked_auth.reset_mock()
    # test authorization and master node conflict
    fsm.on_authorization('10.0.0.3', True, '10.0.0.4', SupvisorsStates.OPERATION)
    assert mocked_auth.call_args == call('10.0.0.3', True)
    assert fsm.supvisors.context.master_node_name == '10.0.0.5'
    assert fsm.state == SupvisorsStates.INITIALIZATION
    assert fsm.supvisors.context.master_operational


def test_restart_event(fsm):
    """ Test the actions triggered in state machine upon reception of a restart event. """
    from supvisors.ttypes import SupvisorsStates
    # inject restart event and test call to fsm set_state RESTARTING
    with patch.object(fsm, 'set_state') as mocked_fsm:
        fsm.on_restart()
        assert mocked_fsm.call_count == 1
        assert mocked_fsm.call_args == call(SupvisorsStates.RESTARTING)


def test_shutdown_event(fsm):
    """ Test the actions triggered in state machine upon reception of a shutdown event. """
    from supvisors.ttypes import SupvisorsStates
    # inject shutdown event and test call to fsm set_state SHUTTING_DOWN
    with patch.object(fsm, 'set_state') as mocked_fsm:
        fsm.on_shutdown()
        assert mocked_fsm.call_count == 1
        assert mocked_fsm.call_args == call(SupvisorsStates.SHUTTING_DOWN)
