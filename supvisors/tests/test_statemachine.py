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

from supervisor.states import ProcessStates
from unittest.mock import call, Mock

from supvisors.address import AddressStatus
from supvisors.statemachine import *
from supvisors.ttypes import AddressStates, SupvisorsStates


@pytest.fixture
def supvisors_ctx(supvisors):
    """ Create a Supvisors-like structure filled with some nodes. """
    nodes = supvisors.context.nodes
    nodes['127.0.0.1']._state = AddressStates.RUNNING
    nodes['10.0.0.1']._state = AddressStates.SILENT
    nodes['10.0.0.2']._state = AddressStates.RUNNING
    nodes['10.0.0.3']._state = AddressStates.ISOLATING
    nodes['10.0.0.4']._state = AddressStates.RUNNING
    nodes['10.0.0.5']._state = AddressStates.ISOLATED
    return supvisors


def test_abstract_state(supvisors_ctx):
    """ Test the Abstract state of the self.fsm. """
    state = AbstractState(supvisors_ctx)
    # check attributes at creation
    assert state.supvisors is supvisors_ctx
    assert state.local_node_name == '127.0.0.1'
    # call empty methods
    state.enter()
    state.next()
    state.exit()
    # test check_nodes method
    # declare local and master address running
    supvisors_ctx.context._master_node_name = '10.0.0.3'
    supvisors_ctx.context.nodes['127.0.0.1']._state = AddressStates.RUNNING
    supvisors_ctx.context.nodes['10.0.0.3']._state = AddressStates.RUNNING
    assert state.check_nodes() is None
    # transition to INITIALIZATION state if the local address or master address is not RUNNING
    supvisors_ctx.context.nodes['127.0.0.1']._state = AddressStates.SILENT
    assert state.check_nodes() == SupvisorsStates.INITIALIZATION
    supvisors_ctx.context.nodes['127.0.0.1']._state = AddressStates.RUNNING
    supvisors_ctx.context.nodes['10.0.0.3']._state = AddressStates.SILENT
    assert state.check_nodes() == SupvisorsStates.INITIALIZATION
    supvisors_ctx.context.nodes['127.0.0.1']._state = AddressStates.SILENT
    assert state.check_nodes() == SupvisorsStates.INITIALIZATION
    # test abort_jobs method
    state.abort_jobs()
    assert supvisors_ctx.failure_handler.abort.called
    assert supvisors_ctx.starter.abort.called


def test_initialization_state(mocker, supvisors_ctx):
    """ Test the Initialization state of the fsm. """
    state = InitializationState(supvisors_ctx)
    assert isinstance(state, AbstractState)
    # 1. test enter method: master and start_date are reset
    # test that all active nodes have been reset to UNKNOWN
    state.enter()
    assert state.context.master_node_name == ''
    nodes = supvisors_ctx.context.nodes
    assert nodes['127.0.0.1'].state == AddressStates.UNKNOWN
    assert nodes['10.0.0.1'].state == AddressStates.SILENT
    assert nodes['10.0.0.2'].state == AddressStates.UNKNOWN
    assert nodes['10.0.0.3'].state == AddressStates.ISOLATING
    assert nodes['10.0.0.4'].state == AddressStates.UNKNOWN
    assert nodes['10.0.0.5'].state == AddressStates.ISOLATED
    # 2. test next method
    # trigger log for synchro time out
    state.context.start_date = 0
    # test that Supvisors wait for all nodes to be running or a given timeout is reached
    # test case no node is running, especially local node
    result = state.next()
    assert result == SupvisorsStates.INITIALIZATION
    # test case where addresses are still unknown and timeout is not reached
    nodes['127.0.0.1']._state = AddressStates.RUNNING
    nodes['10.0.0.2']._state = AddressStates.RUNNING
    nodes['10.0.0.4']._state = AddressStates.SILENT
    result = state.next()
    assert result == SupvisorsStates.INITIALIZATION
    # test case where no more nodes are still unknown
    nodes['10.0.0.1']._state = AddressStates.SILENT
    nodes['10.0.0.3']._state = AddressStates.ISOLATED
    result = state.next()
    assert result == SupvisorsStates.DEPLOYMENT
    # test case where end of synchro is forced based on core nodes running
    supvisors_ctx.options.force_synchro_if = {'10.0.0.2', '10.0.0.4'}
    nodes['10.0.0.3']._state = AddressStates.UNKNOWN
    nodes['10.0.0.4']._state = AddressStates.RUNNING
    # SYNCHRO_TIMEOUT_MIN not passed yet
    state.context.start_date = time() - 10
    result = state.next()
    assert result == SupvisorsStates.INITIALIZATION
    # no master set
    state.context.start_date = 0
    result = state.next()
    assert result == SupvisorsStates.DEPLOYMENT
    # master known, not in core nodes and not running
    supvisors_ctx.context.master_node_name = '10.0.0.3'
    result = state.next()
    assert result == SupvisorsStates.INITIALIZATION
    # master known, not in core nodes and running
    supvisors_ctx.context.master_node_name = '127.0.0.1'
    result = state.next()
    assert result == SupvisorsStates.DEPLOYMENT
    # 3. test exit method
    # test when master_node_name is already set: no change
    state.exit()
    assert supvisors_ctx.context.master_node_name == '127.0.0.1'
    # test when master_node_name is not set and no core nodes
    # check master is the lowest string among running node names
    supvisors_ctx.context.master_node_name = None
    supvisors_ctx.options.force_synchro_if = {}
    state.exit()
    assert supvisors_ctx.context.running_nodes() == ['127.0.0.1', '10.0.0.2', '10.0.0.4']
    assert supvisors_ctx.context.master_node_name == '10.0.0.2'
    # test when master_node_name is not set and forced nodes are used
    # check master is the lowest string among the intersection between running node names and forced nodes
    supvisors_ctx.context.master_node_name = None
    supvisors_ctx.options.force_synchro_if = {'10.0.0.3', '10.0.0.4'}
    state.exit()
    assert supvisors_ctx.context.running_nodes() == ['127.0.0.1', '10.0.0.2', '10.0.0.4']
    assert supvisors_ctx.context.master_node_name == '10.0.0.4'


def test_master_deployment_state(mocker, supvisors_ctx):
    """ Test the Deployment state of the fsm. """
    state = MasterDeploymentState(supvisors_ctx)
    assert isinstance(state, AbstractState)
    # test enter method
    mocked_starter = supvisors_ctx.starter.start_applications
    supvisors_ctx.fsm.redeploy_mark = True
    state.enter()
    assert mocked_starter.called
    assert not supvisors_ctx.fsm.redeploy_mark
    # test next method if check_nodes return something
    mocker.patch.object(state, 'check_nodes', return_value=SupvisorsStates.INITIALIZATION)
    assert state.next() == SupvisorsStates.INITIALIZATION
    assert not supvisors_ctx.starter.is_starting_completed.called
    # test next method if check_nodes return nothing
    state.check_nodes.return_value = None
    # test next method if the local node is master
    supvisors_ctx.context._is_master = True
    # stay in DEPLOYMENT if a start sequence is in progress
    supvisors_ctx.starter.is_starting_completed.return_value = False
    result = state.next()
    assert result == SupvisorsStates.DEPLOYMENT
    # return OPERATION and no start sequence is in progress
    supvisors_ctx.starter.is_starting_completed.return_value = True
    result = state.next()
    assert result == SupvisorsStates.OPERATION
    # no exit implementation. just call it without test
    state.exit()


def test_master_operation_state(mocker, supvisors_ctx):
    """ Test the Operation state of the fsm. """
    mocked_start = supvisors_ctx.starter.is_starting_completed
    # create instance
    state = MasterOperationState(supvisors_ctx)
    assert isinstance(state, AbstractState)
    # no enter implementation. just call it without test
    state.enter()
    # test next method if check_nodes return something
    mocker.patch.object(state, 'check_nodes', return_value=SupvisorsStates.INITIALIZATION)
    assert state.next() == SupvisorsStates.INITIALIZATION
    assert not mocked_start.called
    # test next method if check_nodes return nothing
    state.check_nodes.return_value = None
    # do not leave OPERATION state if a starting or a stopping is in progress
    mocked_start.return_value = False
    result = state.next()
    assert result == SupvisorsStates.OPERATION
    mocked_start.return_value = True
    mocked_stop = mocker.patch.object(supvisors_ctx.stopper, 'is_stopping_completed', return_value=False)
    result = state.next()
    assert result == SupvisorsStates.OPERATION
    mocked_stop.return_value = True
    # create address context
    for node_name in supvisors_ctx.address_mapper.node_names:
        status = AddressStatus(node_name, supvisors_ctx.logger)
        supvisors_ctx.context.nodes[node_name] = status
    # no starting or stopping is in progress
    # stay in OPERATION if no conflict
    mocked_conflict = mocker.patch.object(supvisors_ctx.context, 'conflicting', return_value=False)
    # mark for re-deployment
    supvisors_ctx.fsm.redeploy_mark = True
    result = state.next()
    assert result == SupvisorsStates.DEPLOYMENT
    # transit to CONCILIATION if conflict detected
    mocked_conflict.return_value = True
    result = state.next()
    assert result == SupvisorsStates.CONCILIATION
    # no exit implementation. just call it without test
    state.exit()


def test_master_conciliation_state(mocker, supvisors_ctx):
    """ Test the Conciliation state of the fsm. """
    mocked_conciliate = mocker.patch('supvisors.statemachine.conciliate_conflicts')
    mocked_start = supvisors_ctx.starter.is_starting_completed
    mocked_stop = supvisors_ctx.stopper.is_stopping_completed
    # create instance
    state = MasterConciliationState(supvisors_ctx)
    assert isinstance(state, AbstractState)
    # test enter method
    mocker.patch.object(supvisors_ctx.context, 'conflicts', return_value=[1, 2, 3])
    state.enter()
    assert mocked_conciliate.call_args_list == [call(supvisors_ctx, 0, [1, 2, 3])]
    # test next method if check_nodes return something
    mocker.patch.object(state, 'check_nodes', return_value=SupvisorsStates.INITIALIZATION)
    assert state.next() == SupvisorsStates.INITIALIZATION
    assert not mocked_start.called
    # test next method if check_nodes return nothing
    state.check_nodes.return_value = None
    # do not leave CONCILIATION state if a starting or a stopping is in progress
    mocked_start.return_value = False
    mocked_stop.return_value = False
    result = state.next()
    assert result == SupvisorsStates.CONCILIATION
    mocked_start.return_value = True
    mocked_stop.return_value = False
    result = state.next()
    assert result == SupvisorsStates.CONCILIATION
    mocked_start.return_value = False
    mocked_stop.return_value = True
    result = state.next()
    assert result == SupvisorsStates.CONCILIATION
    # consider that no starting or stopping is in progress
    mocked_start.return_value = True
    mocked_stop.return_value = True
    # if local address and master address are RUNNING and conflict still detected, re-enter CONCILIATION
    mocker.patch.object(supvisors_ctx.context, 'conflicting', return_value=True)
    mocked_enter = mocker.patch.object(state, 'enter')
    result = state.next()
    assert mocked_enter.call_count == 1
    assert result == SupvisorsStates.CONCILIATION
    # transit to OPERATION if local node and master node are RUNNING and no conflict detected
    supvisors_ctx.context.conflicting.return_value = False
    result = state.next()
    assert result == SupvisorsStates.OPERATION
    # no exit implementation. just call it without test
    state.exit()


def test_master_restarting_state(mocker, supvisors_ctx):
    """ Test the Restarting state of the fsm. """
    mocked_starter = supvisors_ctx.starter.abort
    mocked_stopper = supvisors_ctx.stopper.stop_applications
    mocked_stopping = supvisors_ctx.stopper.is_stopping_completed
    # create instance to test
    state = MasterRestartingState(supvisors_ctx)
    assert isinstance(state, AbstractState)
    # test enter method: starting ang stopping in progress are aborted
    state.enter()
    assert mocked_starter.call_count == 1
    assert mocked_stopper.call_count == 1
    # test next method if check_nodes return something
    mocker.patch.object(state, 'check_nodes', return_value=SupvisorsStates.INITIALIZATION)
    assert state.next() == SupvisorsStates.SHUTDOWN
    assert not mocked_stopping.called
    # test next method if check_nodes return nothing
    state.check_nodes.return_value = None
    # test next method: all processes are stopped
    mocked_stopping.return_value = True
    result = state.next()
    assert result == SupvisorsStates.SHUTDOWN
    mocked_stopping.return_value = False
    result = state.next()
    assert result == SupvisorsStates.RESTARTING
    # test exit method: call to pusher send_restart for all addresses
    assert not state.supvisors.zmq.pusher.send_restart.called
    state.exit()
    assert state.supvisors.zmq.pusher.send_restart.call_args_list == [call('127.0.0.1')]


def test_master_shutting_down_state(mocker, supvisors_ctx):
    """ Test the ShuttingDown state of the fsm. """
    mocked_starter = supvisors_ctx.starter.abort
    mocked_stopper = supvisors_ctx.stopper.stop_applications
    mocked_stopping = supvisors_ctx.stopper.is_stopping_completed
    # create instance to test
    state = MasterShuttingDownState(supvisors_ctx)
    assert isinstance(state, AbstractState)
    # test enter method: starting ang stopping in progress are aborted
    state.enter()
    assert mocked_starter.call_count == 1
    assert mocked_stopper.call_count == 1
    # test next method if check_nodes return something
    mocker.patch.object(state, 'check_nodes', return_value=SupvisorsStates.INITIALIZATION)
    assert state.next() == SupvisorsStates.SHUTDOWN
    assert not mocked_stopping.called
    # test next method if check_nodes return nothing
    state.check_nodes.return_value = None
    # test next method: all processes are stopped
    result = state.next()
    assert result == SupvisorsStates.SHUTDOWN
    mocked_stopping.return_value = False
    result = state.next()
    assert result == SupvisorsStates.SHUTTING_DOWN
    # test exit method: call to pusher send_restart for all addresses
    assert not state.supvisors.zmq.pusher.send_shutdown.called
    state.exit()
    assert state.supvisors.zmq.pusher.send_shutdown.call_args_list == [call('127.0.0.1')]


def test_shutdown_state(supvisors_ctx):
    """ Test the ShutDown state of the fsm. """
    state = ShutdownState(supvisors_ctx)
    assert isinstance(state, AbstractState)
    # no enter / next / exit implementation. just call it without test
    state.enter()
    state.next()
    state.exit()


def test_slave_main_state(mocker, supvisors_ctx):
    """ Test the SlaveMain state of the fsm. """
    # create instance to test
    state = SlaveMainState(supvisors_ctx)
    assert isinstance(state, AbstractState)
    # no enter implementation. just call it without test
    state.enter()
    # test next method if check_nodes return something
    mocker.patch.object(state, 'check_nodes', return_value=SupvisorsStates.INITIALIZATION)
    assert state.next() == SupvisorsStates.INITIALIZATION
    # test next method if check_nodes return nothing
    state.check_nodes.return_value = None
    # test next method: no next state proposed
    assert state.next() is None
    # no exit implementation. just call it without test
    state.exit()


def test_slave_restarting_state(mocker, supvisors_ctx):
    """ Test the SlaveRestarting state of the fsm. """
    # create instance to test
    state = SlaveRestartingState(supvisors_ctx)
    assert isinstance(state, AbstractState)
    # no enter implementation. just call it without test
    state.enter()
    # test next method if check_nodes return something
    mocker.patch.object(state, 'check_nodes', return_value=SupvisorsStates.INITIALIZATION)
    assert state.next() == SupvisorsStates.SHUTDOWN
    # test next method if check_nodes return nothing
    state.check_nodes.return_value = None
    # test next method: no next state proposed
    assert state.next() is None
    # test exit
    assert not state.supvisors.zmq.pusher.send_restart.called
    state.exit()
    assert state.supvisors.zmq.pusher.send_restart.call_args_list == [call('127.0.0.1')]


def test_slave_shutting_down_state(mocker, supvisors_ctx):
    """ Test the SlaveShuttingDown state of the fsm. """
    # create instance to test
    state = SlaveShuttingDownState(supvisors_ctx)
    assert isinstance(state, SlaveRestartingState)
    # no enter implementation. just call it without test
    state.enter()
    # test next method if check_nodes return something
    mocker.patch.object(state, 'check_nodes', return_value=SupvisorsStates.INITIALIZATION)
    assert state.next() == SupvisorsStates.SHUTDOWN
    # test next method if check_nodes return nothing
    state.check_nodes.return_value = None
    # test next method: no next state proposed
    assert state.next() is None
    # test exit
    assert not state.supvisors.zmq.pusher.send_shutdown.called
    state.exit()
    assert state.supvisors.zmq.pusher.send_shutdown.call_args_list == [call('127.0.0.1')]


@pytest.fixture
def fsm(supvisors):
    """ Create the FiniteStateMachine instance to test. """
    return FiniteStateMachine(supvisors)


def test_creation(supvisors, fsm):
    """ Test the values set at construction. """
    assert fsm.supvisors is supvisors
    assert not fsm.redeploy_mark
    # test that the INITIALIZATION state is triggered at creation
    assert fsm.state == SupvisorsStates.INITIALIZATION
    assert isinstance(fsm.instance, InitializationState)


def test_state_string(fsm):
    """ Test the string conversion of state machine. """
    # test string conversion for all states
    for state in SupvisorsStates:
        fsm.state = state
        assert fsm.state.name == state.name


def test_serial(fsm):
    """ Test the serialization of state machine. """
    # test serialization for all states
    for state in SupvisorsStates:
        fsm.state = state
        assert fsm.serial() == {'statecode': state.value, 'statename': state.name}


# Patch all state events
MASTER_STATES = [cls.__name__ for cls in FiniteStateMachine._MasterStateInstances.values()]
SLAVE_STATES = ['InitializationState', 'SlaveMainState', 'SlaveRestartingState', 'SlaveShuttingDownState',
                'ShutdownState']
EVENTS = ['enter', 'next', 'exit']


@pytest.fixture
def mock_master_events(mocker):
    return [mocker.patch('supvisors.statemachine.%s.%s' % (cls, evt), return_value=None)
            for cls in MASTER_STATES
            for evt in EVENTS]


@pytest.fixture
def mock_slave_events(mocker):
    return [mocker.patch('supvisors.statemachine.%s.%s' % (cls, evt), return_value=None)
            for cls in SLAVE_STATES
            for evt in EVENTS]


def compare_calls(call_counts, mock_events):
    """ Compare call counts of mocked methods. """
    for call_count, mocked in zip(call_counts, mock_events):
        assert mocked.call_count == call_count
        mocked.reset_mock()


def test_master_simple_set_state(fsm, mock_master_events):
    """ Test single transitions of the state machine using set_state method.
    As it is a Master FSM, transitions are checked.
    Beware of the fixture sequence. If mock_master_events is set before fsm, mocks would capture the calls triggered
    from the FiniteStateMachine constructor.
    """
    instance_ref = fsm.instance
    # test set_state with identical state parameter
    fsm.set_state(SupvisorsStates.INITIALIZATION)
    compare_calls([0, 0, 0, 0, 0, 0], mock_master_events)
    assert fsm.instance is instance_ref
    assert fsm.state == SupvisorsStates.INITIALIZATION
    # test set_state with not authorized transition for master
    fsm.context._is_master = True
    fsm.set_state(SupvisorsStates.OPERATION)
    compare_calls([0, 0, 0, 0, 0, 0], mock_master_events)
    assert fsm.instance is instance_ref
    assert fsm.state == SupvisorsStates.INITIALIZATION
    # test set_state with authorized transition
    fsm.set_state(SupvisorsStates.DEPLOYMENT)
    compare_calls([0, 0, 1, 1, 1, 0], mock_master_events)
    assert fsm.instance is not instance_ref
    assert fsm.state == SupvisorsStates.DEPLOYMENT


def test_slave_simple_set_state(fsm, mock_slave_events):
    """ Test single transitions of the state machine using set_state method.
    Same transition rules apply.
    """
    instance_ref = fsm.instance
    # test set_state with identical state parameter
    fsm.set_state(SupvisorsStates.INITIALIZATION)
    compare_calls([0, 0, 0, 0, 0, 0], mock_slave_events)
    assert fsm.instance is instance_ref
    assert fsm.state == SupvisorsStates.INITIALIZATION
    # test set_state with not authorized transition
    fsm.set_state(SupvisorsStates.OPERATION)
    compare_calls([0, 0, 0, 0, 0, 0], mock_slave_events)
    assert fsm.instance is instance_ref
    assert fsm.state == SupvisorsStates.INITIALIZATION
    # test set_state with authorized transition
    fsm.set_state(SupvisorsStates.DEPLOYMENT)
    compare_calls([0, 0, 1, 1, 1, 0], mock_slave_events)
    assert fsm.instance is not instance_ref
    assert fsm.state == SupvisorsStates.DEPLOYMENT
    # test set_state with unauthorized transition
    fsm.set_state(SupvisorsStates.SHUTDOWN)
    compare_calls([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], mock_slave_events)
    assert fsm.state == SupvisorsStates.DEPLOYMENT
    # test set_state with unauthorized transition but forced
    fsm.set_state(SupvisorsStates.SHUTDOWN, True)
    compare_calls([0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 1, 1, 0], mock_slave_events)
    assert fsm.state == SupvisorsStates.SHUTDOWN


def test_master_complex_set_state(fsm, mock_master_events):
    """ Test multiple transitions of the Master FSM using set_state method. """
    mock_master_events[4].return_value = SupvisorsStates.OPERATION
    instance_ref = fsm.instance
    # test set_state with authorized transition
    fsm.context._is_master = True
    fsm.set_state(SupvisorsStates.DEPLOYMENT)
    compare_calls([0, 0, 1, 1, 1, 1, 1, 1, 0], mock_master_events)
    assert fsm.instance is not instance_ref
    assert fsm.state == SupvisorsStates.OPERATION


def test_master_no_next(fsm, mock_master_events):
    """ Test no transition of the state machine using next_method. """
    mock_master_events[1].return_value = SupvisorsStates.INITIALIZATION
    instance_ref = fsm.instance
    # test set_state with authorized transition
    fsm.context._is_master = True
    fsm.next()
    compare_calls([0, 1, 0], mock_master_events)
    assert fsm.instance is instance_ref
    assert fsm.state == SupvisorsStates.INITIALIZATION


def test_master_simple_next(fsm, mock_master_events):
    """ Test single transition of the state machine using next_method. """
    mock_master_events[1].return_value = SupvisorsStates.DEPLOYMENT
    mock_master_events[4].return_value = SupvisorsStates.DEPLOYMENT
    instance_ref = fsm.instance
    # test set_state with authorized transition
    fsm.context._is_master = True
    fsm.next()
    compare_calls([0, 1, 1, 1, 1, 0], mock_master_events)
    assert fsm.instance is not instance_ref
    assert fsm.state == SupvisorsStates.DEPLOYMENT


def test_master_complex_next(fsm, mock_master_events):
    """ Test multiple transitions of the state machine using next_method. """
    mock_master_events[1].side_effect = [SupvisorsStates.DEPLOYMENT, SupvisorsStates.DEPLOYMENT]
    mock_master_events[4].side_effect = [SupvisorsStates.OPERATION, SupvisorsStates.OPERATION]
    mock_master_events[7].side_effect = [SupvisorsStates.CONCILIATION, SupvisorsStates.INITIALIZATION,
                                         SupvisorsStates.RESTARTING]
    mock_master_events[10].side_effect = [SupvisorsStates.OPERATION]
    mock_master_events[13].return_value = SupvisorsStates.SHUTDOWN
    instance_ref = fsm.instance
    # test set_state with authorized transition
    fsm.context._is_master = True
    fsm.next()
    compare_calls([1, 2, 2, 2, 2, 2, 3, 3, 3, 1, 1, 1, 1, 1, 1, 0, 0, 0, 1, 1, 0], mock_master_events)
    assert fsm.instance is not instance_ref
    assert fsm.state == SupvisorsStates.SHUTDOWN


def test_timer_event(mocker, fsm):
    """ Test the actions triggered in state machine upon reception of a timer event. """
    # apply patches
    mocked_event = mocker.patch.object(fsm.supvisors.context, 'on_timer_event', return_value=['proc_1', 'proc_2'])
    mocked_next = mocker.patch.object(fsm, 'next')
    mocked_add = fsm.supvisors.failure_handler.add_default_job
    mocked_trigger = fsm.supvisors.failure_handler.trigger_jobs
    mocked_isolation = mocker.patch.object(fsm.supvisors.context, 'handle_isolation', return_value=['2', '3'])
    # test when not master
    assert not fsm.context.is_master
    result = fsm.on_timer_event()
    # check result: marked processes are started
    assert result == ['2', '3']
    assert mocked_event.call_count == 1
    assert mocked_next.call_count == 1
    assert not mocked_add.called
    assert not mocked_trigger.called
    assert mocked_isolation.call_count == 1
    # reset mocks
    mocker.resetall()
    # test when not master
    fsm.context._is_master = True
    assert fsm.context.is_master
    result = fsm.on_timer_event()
    # check result: marked processes are started
    assert result == ['2', '3']
    assert mocked_event.call_count == 1
    assert mocked_next.call_count == 1
    assert mocked_add.call_args_list == [call('proc_1'), call('proc_2')]
    assert mocked_trigger.call_count == 1
    assert mocked_isolation.call_count == 1


def test_tick_event(mocker, fsm):
    """ Test the actions triggered in state machine upon reception of a tick event. """
    # inject tick event and test call to context on_tick_event
    mocked_evt = mocker.patch.object(fsm.supvisors.context, 'on_tick_event')
    fsm.on_tick_event('10.0.0.1', {'tick': 1234})
    assert mocked_evt.call_count == 1
    assert mocked_evt.call_args == call('10.0.0.1', {'tick': 1234})


def test_process_event(mocker, fsm):
    """ Test the actions triggered in state machine upon reception of a process event. """
    # prepare context
    fsm.supvisors.context._is_master = True
    process = Mock(application_name='appli', forced_state=None, **{'crashed.return_value': True})
    # get patches
    mocked_ctx = mocker.patch.object(fsm.supvisors.context, 'on_process_event', return_value=None)
    mocked_start_evt = fsm.supvisors.starter.on_event
    mocked_stop_evt = fsm.supvisors.stopper.on_event
    mocked_add = fsm.supvisors.failure_handler.add_default_job
    # context.on_process_event is always called
    # test that starter and stopper are not involved when corresponding process is not found
    fsm.on_process_event('10.0.0.1', {'process_name': 'dummy_proc'})
    assert mocked_ctx.call_args_list == [call('10.0.0.1', {'process_name': 'dummy_proc'})]
    assert not mocked_start_evt.called
    assert not mocked_stop_evt.called
    assert not mocked_add.called
    # when process is found but local node is not master, only starter and stopper are called
    mocked_ctx.return_value = process
    mocked_ctx.reset_mock()
    fsm.supvisors.context._is_master = False
    fsm.on_process_event('10.0.0.1', {'process_name': 'dummy_proc'})
    assert mocked_ctx.call_args_list == [call('10.0.0.1', {'process_name': 'dummy_proc'})]
    assert mocked_start_evt.call_args_list == [call(process)]
    assert mocked_stop_evt.call_args_list == [call(process)]
    assert not mocked_add.called
    # reset mocks
    mocked_ctx.reset_mock()
    mocked_start_evt.reset_mock()
    mocked_stop_evt.reset_mock()
    # process is found and local node is master. starter and stopper are called and the process has crashed
    # test with running_failure_strategy set to CONTINUE / RESTART_PROCESS so job is not added to failure handler
    fsm.supvisors.context._is_master = True
    for strategy in [RunningFailureStrategies.CONTINUE, RunningFailureStrategies.RESTART_PROCESS]:
        process.rules.running_failure_strategy = strategy
        fsm.on_process_event('10.0.0.1', {'process_name': 'dummy_proc'})
        assert mocked_ctx.call_args_list == [call('10.0.0.1', {'process_name': 'dummy_proc'})]
        assert mocked_start_evt.call_args_list == [call(process)]
        assert mocked_stop_evt.call_args_list == [call(process)]
        assert mocked_add.call_args_list == []
        # reset mocks
        mocked_ctx.reset_mock()
        mocked_start_evt.reset_mock()
        mocked_stop_evt.reset_mock()
    # test with running_failure_strategy set to STOP_APPLICATION
    # job is added to failure handler
    process.rules.running_failure_strategy = RunningFailureStrategies.STOP_APPLICATION
    fsm.on_process_event('10.0.0.1', {'process_name': 'dummy_proc'})
    assert mocked_ctx.call_args_list == [call('10.0.0.1', {'process_name': 'dummy_proc'})]
    assert mocked_start_evt.call_args_list == [call(process)]
    assert mocked_stop_evt.call_args_list == [call(process)]
    assert mocked_add.call_args_list == [call(process)]
    # reset mocks
    mocked_ctx.reset_mock()
    mocked_start_evt.reset_mock()
    mocked_stop_evt.reset_mock()
    mocked_add.reset_mock()
    # test with running_failure_strategy set to RESTART_APPLICATION
    # job is added to failure handler only if process crash is 'real' (not forced)
    # test with no forced state
    process.rules.running_failure_strategy = RunningFailureStrategies.RESTART_APPLICATION
    fsm.on_process_event('10.0.0.1', {'process_name': 'dummy_proc'})
    assert mocked_ctx.call_args_list == [call('10.0.0.1', {'process_name': 'dummy_proc'})]
    assert mocked_start_evt.call_args_list == [call(process)]
    assert mocked_stop_evt.call_args_list == [call(process)]
    assert mocked_add.call_args_list == [call(process)]
    # reset mocks
    mocked_ctx.reset_mock()
    mocked_start_evt.reset_mock()
    mocked_stop_evt.reset_mock()
    mocked_add.reset_mock()
    # test with forced state
    process.forced_state = ProcessStates.FATAL
    fsm.on_process_event('10.0.0.1', {'process_name': 'dummy_proc'})
    assert mocked_ctx.call_args_list == [call('10.0.0.1', {'process_name': 'dummy_proc'})]
    assert mocked_start_evt.call_args_list == [call(process)]
    assert mocked_stop_evt.call_args_list == [call(process)]
    assert not mocked_add.called
    # reset mocks
    mocked_ctx.reset_mock()
    mocked_start_evt.reset_mock()
    mocked_stop_evt.reset_mock()
    # test when process has not crashed
    process.crashed.return_value = False
    for strategy in RunningFailureStrategies:
        process.rules.running_failure_strategy = strategy
        fsm.on_process_event('10.0.0.1', {'process_name': 'dummy_proc'})
        assert mocked_ctx.call_args_list == [call('10.0.0.1', {'process_name': 'dummy_proc'})]
        assert mocked_start_evt.call_args_list == [call(process)]
        assert mocked_stop_evt.call_args_list == [call(process)]
        assert not mocked_add.called
        # reset mocks
        mocked_ctx.reset_mock()
        mocked_start_evt.reset_mock()
        mocked_stop_evt.reset_mock()
        mocked_add.reset_mock()


def test_on_process_info(mocker, fsm):
    """ Test the actions triggered in state machine upon reception of a process information. """
    # inject process info and test call to context load_processes
    mocked_load = mocker.patch.object(fsm.supvisors.context, 'load_processes')
    fsm.on_process_info('10.0.0.1', {'info': 'dummy_info'})
    assert mocked_load.call_count == 1
    assert mocked_load.call_args == call('10.0.0.1', {'info': 'dummy_info'})


def test_on_state_event(mocker, fsm):
    """ Test the actions triggered in state machine upon reception of a Master state event. """
    mocked_state = mocker.patch.object(fsm, 'set_state')
    fsm.context.master_node_name = '10.0.0.1'
    # test event not sent by Master node
    for state in SupvisorsStates:
        payload = {'statecode': state}
        fsm.on_state_event('10.0.0.2', payload)
        assert not mocked_state.called
    # test event sent by Master node
    for state in SupvisorsStates:
        payload = {'statecode': state}
        fsm.on_state_event('10.0.0.1', payload)
        assert mocked_state.call_args_list == [call(state)]
        mocker.resetall()


def test_on_authorization(mocker, fsm):
    """ Test the actions triggered in state machine upon reception of an authorization event. """
    # prepare context
    mocked_auth = mocker.patch.object(fsm.context, 'on_authorization', return_value=False)
    # set initial condition
    assert fsm.supvisors.address_mapper.local_node_name == '127.0.0.1'
    nodes = fsm.context.nodes
    nodes['127.0.0.1']._state = AddressStates.RUNNING
    nodes['10.0.0.5']._state = AddressStates.RUNNING
    # test rejected authorization
    fsm.on_authorization('10.0.0.1', False, '10.0.0.5', SupvisorsStates.INITIALIZATION)
    assert mocked_auth.call_args_list == [call('10.0.0.1', False)]
    assert fsm.state == SupvisorsStates.INITIALIZATION
    assert fsm.context.master_node_name == ''
    assert not fsm.redeploy_mark
    # reset mocks
    mocked_auth.reset_mock()
    mocked_auth.return_value = True
    # test authorization when no master node provided
    fsm.on_authorization('10.0.0.1', True, '', SupvisorsStates.INITIALIZATION)
    assert mocked_auth.call_args == call('10.0.0.1', True)
    assert fsm.state == SupvisorsStates.INITIALIZATION
    assert fsm.context.master_node_name == ''
    assert not fsm.redeploy_mark
    # reset mocks
    mocked_auth.reset_mock()
    # test authorization and master node assignment
    fsm.on_authorization('10.0.0.1', True, '10.0.0.5', SupvisorsStates.INITIALIZATION)
    assert mocked_auth.call_args == call('10.0.0.1', True)
    assert fsm.state == SupvisorsStates.INITIALIZATION
    assert fsm.context.master_node_name == '10.0.0.5'
    assert not fsm.redeploy_mark
    # reset mocks
    mocked_auth.reset_mock()
    # test authorization and master node operational
    fsm.on_authorization('10.0.0.5', True, '10.0.0.5', SupvisorsStates.OPERATION)
    assert mocked_auth.call_args == call('10.0.0.5', True)
    assert fsm.state == SupvisorsStates.OPERATION
    assert fsm.context._master_node_name == '10.0.0.5'
    assert not fsm.redeploy_mark
    # reset mocks
    mocked_auth.reset_mock()
    # test authorization and master node conflict
    fsm.on_authorization('10.0.0.3', True, '10.0.0.4', SupvisorsStates.OPERATION)
    assert mocked_auth.call_args == call('10.0.0.3', True)
    assert fsm.state == SupvisorsStates.INITIALIZATION
    assert fsm.context.master_node_name == ''
    assert not fsm.redeploy_mark
    # change context while instance is not master
    nodes['127.0.0.1']._state = AddressStates.RUNNING
    nodes['10.0.0.5']._state = AddressStates.RUNNING
    # as local is not master is operational, no automatic transition
    fsm.set_state(SupvisorsStates.DEPLOYMENT)
    assert fsm.state == SupvisorsStates.DEPLOYMENT
    # set current instance as master
    fsm.supvisors.context._is_master = True
    # test authorization when no master node provided
    fsm.on_authorization('10.0.0.4', True, '', SupvisorsStates.INITIALIZATION)
    assert mocked_auth.call_args == call('10.0.0.4', True)
    assert fsm.state == SupvisorsStates.DEPLOYMENT
    assert fsm.supvisors.context.master_node_name == '10.0.0.5'
    assert fsm.redeploy_mark
    # test authorization and master node conflict
    fsm.on_authorization('10.0.0.5', True, '10.0.0.4', SupvisorsStates.OPERATION)
    assert mocked_auth.call_args == call('10.0.0.5', True)
    assert fsm.state == SupvisorsStates.INITIALIZATION
    assert fsm.supvisors.context.master_node_name == ''
    assert fsm.redeploy_mark


def test_restart_event(mocker, fsm):
    """ Test the actions triggered in state machine upon reception of a restart event. """
    # inject restart event and test call to fsm set_state RESTARTING
    mocked_fsm = mocker.patch.object(fsm, 'set_state')
    mocked_zmq = fsm.supvisors.zmq.pusher.send_restart_all
    fsm.supvisors.context.master_node_name = '10.0.0.1'
    # test when not master
    fsm.on_restart()
    assert not mocked_fsm.called
    assert mocked_zmq.call_args_list == [call('10.0.0.1')]
    mocked_zmq.reset_mock()
    # test when master
    fsm.context._is_master = True
    fsm.on_restart()
    assert not mocked_zmq.called
    assert mocked_fsm.call_args_list == [call(SupvisorsStates.RESTARTING)]


def test_shutdown_event(mocker, fsm):
    """ Test the actions triggered in state machine upon reception of a shutdown event. """
    # inject shutdown event and test call to fsm set_state SHUTTING_DOWN
    mocked_fsm = mocker.patch.object(fsm, 'set_state')
    mocked_zmq = fsm.supvisors.zmq.pusher.send_shutdown_all
    fsm.supvisors.context.master_node_name = '10.0.0.1'
    # test when not master
    fsm.on_shutdown()
    assert not mocked_fsm.called
    assert mocked_zmq.call_args_list == [call('10.0.0.1')]
    mocked_zmq.reset_mock()
    # test when master
    fsm.context._is_master = True
    fsm.on_shutdown()
    assert not mocked_zmq.called
    assert mocked_fsm.call_args_list == [call(SupvisorsStates.SHUTTING_DOWN)]
