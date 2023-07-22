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

from unittest.mock import call, Mock

import pytest
from supervisor.states import ProcessStates

from supvisors.instancestatus import SupvisorsInstanceStatus
from supvisors.statemachine import *
from supvisors.ttypes import ConciliationStrategies, SupvisorsInstanceStates, SupvisorsStates


@pytest.fixture
def supvisors_ctx(supvisors):
    """ Create a Supvisors-like structure filled with some instances. """
    local_identifier = supvisors.supvisors_mapper.local_identifier
    nodes = supvisors.context.instances
    nodes[local_identifier]._state = SupvisorsInstanceStates.RUNNING
    nodes['10.0.0.1']._state = SupvisorsInstanceStates.SILENT
    nodes['10.0.0.2']._state = SupvisorsInstanceStates.RUNNING
    nodes['10.0.0.3']._state = SupvisorsInstanceStates.ISOLATING
    nodes['10.0.0.4']._state = SupvisorsInstanceStates.RUNNING
    nodes['10.0.0.5']._state = SupvisorsInstanceStates.ISOLATED
    nodes['test']._state = SupvisorsInstanceStates.SILENT
    return supvisors


def test_abstract_state(supvisors_ctx):
    """ Test the Abstract state of the self.fsm. """
    state = AbstractState(supvisors_ctx)
    # check attributes at creation
    assert state.supvisors is supvisors_ctx
    assert state.local_identifier == supvisors_ctx.supvisors_mapper.local_identifier
    # call empty methods
    state.enter()
    with pytest.raises(NotImplementedError):
        state.next()
    state.exit()
    # test check_instances method
    # declare local and master address running
    supvisors_ctx.context._master_identifier = '10.0.0.3'
    supvisors_ctx.context.instances[state.local_identifier]._state = SupvisorsInstanceStates.RUNNING
    supvisors_ctx.context.instances['10.0.0.3']._state = SupvisorsInstanceStates.RUNNING
    assert state.check_instances() is None
    # transition to INITIALIZATION state if the local address or master address is not RUNNING
    supvisors_ctx.context.instances[state.local_identifier]._state = SupvisorsInstanceStates.SILENT
    assert state.check_instances() == SupvisorsStates.INITIALIZATION
    supvisors_ctx.context.instances[state.local_identifier]._state = SupvisorsInstanceStates.RUNNING
    supvisors_ctx.context.instances['10.0.0.3']._state = SupvisorsInstanceStates.SILENT
    assert state.check_instances() == SupvisorsStates.INITIALIZATION
    supvisors_ctx.context.instances[state.local_identifier]._state = SupvisorsInstanceStates.SILENT
    assert state.check_instances() == SupvisorsStates.INITIALIZATION
    # test abort_jobs method
    state.abort_jobs()
    assert supvisors_ctx.failure_handler.abort.called
    assert supvisors_ctx.starter.abort.called
    assert supvisors_ctx.stopper.abort.called


def test_off_state(supvisors_ctx):
    """ Test the Initialization state of the fsm. """
    state = OffState(supvisors_ctx)
    assert isinstance(state, AbstractState)
    local_identifier = state.local_identifier
    # 1. test enter method: no behaviour
    state.enter()
    # 2. test next method
    assert supvisors_ctx.sockets
    assert state.next() == SupvisorsStates.INITIALIZATION
    supvisors_ctx.sockets = None
    assert state.next() == SupvisorsStates.OFF
    # 3. test exit method: no behaviour
    state.exit()


def test_initialization_state(mocker, supvisors_ctx):
    """ Test the Initialization state of the fsm. """
    mocker.patch('supvisors.statemachine.time', return_value=1234)
    state = InitializationState(supvisors_ctx)
    assert isinstance(state, AbstractState)
    local_identifier = state.local_identifier
    # 1. test enter method: master and start_date are reset
    # test that all active instances have been reset to UNKNOWN
    state.enter()
    assert state.context.master_identifier == ''
    instances = supvisors_ctx.context.instances
    assert instances[local_identifier].state == SupvisorsInstanceStates.UNKNOWN
    assert instances['10.0.0.1'].state == SupvisorsInstanceStates.SILENT
    assert instances['10.0.0.2'].state == SupvisorsInstanceStates.UNKNOWN
    assert instances['10.0.0.3'].state == SupvisorsInstanceStates.ISOLATING
    assert instances['10.0.0.4'].state == SupvisorsInstanceStates.UNKNOWN
    assert instances['10.0.0.5'].state == SupvisorsInstanceStates.ISOLATED
    # 2. test next method
    #    Supvisors wait for all instances to be running or a timeout is reached
    # test case no Supvisors instance is yet running, especially the local instance, even if timeout is reached
    for start_date in [0, 1230]:
        state.context.start_date = start_date
        result = state.next()
        assert result == SupvisorsStates.INITIALIZATION
    # from now, the local Supvisors instance is running
    #  and working with no core instances
    instances[local_identifier]._state = SupvisorsInstanceStates.RUNNING
    assert not supvisors_ctx.supvisors_mapper._core_identifiers
    # test case where some Supvisors instances are still unknown and timeout is reached
    # NOTE: in the normal FSM, the instances state is set by the reception of a tick or by the periodic check
    state.context.start_date = 0
    instances['10.0.0.2']._state = SupvisorsInstanceStates.RUNNING
    instances['10.0.0.4']._state = SupvisorsInstanceStates.SILENT
    result = state.next()
    assert result == SupvisorsStates.INITIALIZATION
    # test case where no more instances are still unknown, whatever if the timeout is reached or not
    #  only when NOT in discovery mode
    assert not supvisors_ctx.options.discovery_mode
    instances['10.0.0.1']._state = SupvisorsInstanceStates.SILENT
    instances['10.0.0.3']._state = SupvisorsInstanceStates.ISOLATED
    for start_date in [0, 1230]:
        state.context.start_date = start_date
        result = state.next()
        assert result == SupvisorsStates.DEPLOYMENT
    # same test in discovery mode but timeout not reached yet
    state.context.start_date = 1230
    supvisors_ctx.options.multicast_address = '239.0.0.1'
    assert supvisors_ctx.options.discovery_mode
    result = state.next()
    assert result == SupvisorsStates.INITIALIZATION
    # when the min timeout is reached and in discovery mode, DEPLOYMENT can be reached
    state.context.start_date = 0
    result = state.next()
    assert result == SupvisorsStates.DEPLOYMENT
    # test case where end of synchro is forced based on core instances running
    state.context.start_date = 1234 - SupvisorsOptions.SYNCHRO_TIMEOUT_MIN - 1
    supvisors_ctx.supvisors_mapper._core_identifiers = {'10.0.0.2', '10.0.0.4'}
    # still one core instance to wait
    instances['10.0.0.2']._state = SupvisorsInstanceStates.UNKNOWN
    instances['10.0.0.4']._state = SupvisorsInstanceStates.RUNNING
    result = state.next()
    assert result == SupvisorsStates.INITIALIZATION
    # one core instance SILENT and force another to be UNKOWN to avoid transition due to all in known state
    instances['10.0.0.2']._state = SupvisorsInstanceStates.SILENT
    instances['10.0.0.3']._state = SupvisorsInstanceStates.UNKNOWN
    result = state.next()
    assert result == SupvisorsStates.INITIALIZATION
    # all core instances running and no master set
    instances['10.0.0.2']._state = SupvisorsInstanceStates.RUNNING
    assert not supvisors_ctx.context.master_identifier
    result = state.next()
    assert result == SupvisorsStates.DEPLOYMENT
    # master known, not in core instances and not running (unknown in the present case)
    supvisors_ctx.context.master_identifier = '10.0.0.3'
    result = state.next()
    assert result == SupvisorsStates.INITIALIZATION
    # master known, not in core instances and running
    supvisors_ctx.context.master_identifier = local_identifier
    result = state.next()
    assert result == SupvisorsStates.DEPLOYMENT
    # when the min timeout is NOT reached, do not transition
    state.context.start_date = 1234 - SupvisorsOptions.SYNCHRO_TIMEOUT_MIN
    result = state.next()
    assert result == SupvisorsStates.INITIALIZATION
    # 3. test exit method
    # test when master_identifier is already set: no change
    state.exit()
    assert supvisors_ctx.context.master_identifier == local_identifier
    # test when master_identifier is not set and no core instances
    # check master is the lowest string among running node names
    supvisors_ctx.context.master_identifier = None
    supvisors_ctx.supvisors_mapper._core_identifiers = {}
    state.exit()
    assert supvisors_ctx.context.running_identifiers() == ['10.0.0.2', '10.0.0.4', local_identifier]
    assert supvisors_ctx.context.master_identifier == '10.0.0.2'
    # test when master_identifier is not set and core instances are used
    # check master is the lowest string among the intersection between running node names and forced instances
    supvisors_ctx.context.master_identifier = None
    supvisors_ctx.supvisors_mapper._core_identifiers = {'10.0.0.3', '10.0.0.4'}
    state.exit()
    assert supvisors_ctx.context.running_identifiers() == ['10.0.0.2', '10.0.0.4', local_identifier]
    assert supvisors_ctx.context.master_identifier == '10.0.0.4'


def test_master_deployment_state(mocker, supvisors_ctx):
    """ Test the Deployment state of the fsm. """
    state = MasterDeploymentState(supvisors_ctx)
    assert isinstance(state, AbstractState)
    # test enter method with redeploy_mark as a boolean
    mocked_starter = supvisors_ctx.starter.start_applications
    for mark in [True, False]:
        supvisors_ctx.fsm.redeploy_mark = mark
        state.enter()
        assert not supvisors_ctx.fsm.redeploy_mark
        assert mocked_starter.call_args_list == [call(False)]
        mocked_starter.reset_mock()
    # test enter method with full restart required
    supvisors_ctx.fsm.redeploy_mark = Forced
    state.enter()
    assert not supvisors_ctx.fsm.redeploy_mark
    assert mocked_starter.call_args_list == [call(True)]
    mocked_starter.reset_mock()
    # test next method if check_instances return something
    mocker.patch.object(state, 'check_instances', return_value=SupvisorsStates.INITIALIZATION)
    assert state.next() == SupvisorsStates.INITIALIZATION
    assert not supvisors_ctx.starter.in_progress.called
    # test next method if check_instances return nothing
    state.check_instances.return_value = None
    # test next method if the local node is master
    supvisors_ctx.context._is_master = True
    # stay in DEPLOYMENT if a start sequence is in progress
    supvisors_ctx.starter.in_progress.return_value = True
    result = state.next()
    assert result == SupvisorsStates.DEPLOYMENT
    # return OPERATION and no start sequence is in progress
    supvisors_ctx.starter.in_progress.return_value = False
    result = state.next()
    assert result == SupvisorsStates.OPERATION
    # no exit implementation. just call it without test
    state.exit()


def test_master_operation_state(mocker, supvisors_ctx):
    """ Test the Operation state of the fsm. """
    mocked_start = supvisors_ctx.starter.in_progress
    mocked_stop = supvisors_ctx.stopper.in_progress
    # create instance
    state = MasterOperationState(supvisors_ctx)
    assert isinstance(state, AbstractState)
    # 1. no enter implementation. just call it without test
    state.enter()
    # 2. test next method if check_instances return something
    mocker.patch.object(state, 'check_instances', return_value=SupvisorsStates.INITIALIZATION)
    assert state.next() == SupvisorsStates.INITIALIZATION
    assert not mocked_start.called
    # test next method if check_instances return nothing
    state.check_instances.return_value = None
    # no conflict, no mark, no job: keep in OPERATION
    mocked_start.return_value = False
    mocked_stop.return_value = False
    result = state.next()
    assert result == SupvisorsStates.OPERATION
    # do not leave OPERATION state if a starting or a stopping is in progress
    mocked_start.return_value = True
    result = state.next()
    assert result == SupvisorsStates.OPERATION
    mocked_start.return_value = False
    mocked_stop.return_value = True
    result = state.next()
    assert result == SupvisorsStates.OPERATION
    mocked_stop.return_value = False
    # create instance context
    for instance_id in supvisors_ctx.supvisors_mapper.instances.values():
        status = SupvisorsInstanceStatus(instance_id, supvisors_ctx)
        supvisors_ctx.context.instances[instance_id.identifier] = status
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
    # 3. no exit implementation. just call it without test
    state.exit()


def test_master_conciliation_state(mocker, supvisors_ctx):
    """ Test the Conciliation state of the fsm. """
    mocked_conciliate = mocker.patch('supvisors.statemachine.conciliate_conflicts')
    mocked_start = supvisors_ctx.starter.in_progress
    mocked_stop = supvisors_ctx.stopper.in_progress
    # create instance
    state = MasterConciliationState(supvisors_ctx)
    assert isinstance(state, AbstractState)
    # test enter method
    mocker.patch.object(supvisors_ctx.context, 'conflicts', return_value=[1, 2, 3])
    state.enter()
    assert mocked_conciliate.call_args_list == [call(supvisors_ctx, ConciliationStrategies.USER, [1, 2, 3])]
    # test next method if check_instances return something
    mocker.patch.object(state, 'check_instances', return_value=SupvisorsStates.INITIALIZATION)
    assert state.next() == SupvisorsStates.INITIALIZATION
    assert not mocked_start.called
    # test next method if check_instances return nothing
    state.check_instances.return_value = None
    # do not leave CONCILIATION state if a starting or a stopping is in progress
    mocked_start.return_value = True
    mocked_stop.return_value = True
    result = state.next()
    assert result == SupvisorsStates.CONCILIATION
    mocked_start.return_value = False
    mocked_stop.return_value = True
    result = state.next()
    assert result == SupvisorsStates.CONCILIATION
    mocked_start.return_value = True
    mocked_stop.return_value = False
    result = state.next()
    assert result == SupvisorsStates.CONCILIATION
    # consider that no starting or stopping is in progress
    mocked_start.return_value = False
    mocked_stop.return_value = False
    # if local node and master node are RUNNING and conflict still detected, re-enter CONCILIATION without transition
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
    mocked_stopping = supvisors_ctx.stopper.in_progress
    # create instance to test
    state = MasterRestartingState(supvisors_ctx)
    assert isinstance(state, AbstractState)
    local_identifier = state.local_identifier
    # test enter method: starting ang stopping in progress are aborted
    state.enter()
    assert mocked_starter.call_count == 1
    assert mocked_stopper.call_count == 1
    # test next method if check_instances return something
    mocker.patch.object(state, 'check_instances', return_value=SupvisorsStates.INITIALIZATION)
    assert state.next() == SupvisorsStates.RESTART
    assert not mocked_stopping.called
    # test next method if check_instances return nothing
    state.check_instances.return_value = None
    # test next method: all processes are stopped
    mocked_stopping.return_value = False
    result = state.next()
    assert result == SupvisorsStates.RESTART
    mocked_stopping.return_value = True
    result = state.next()
    assert result == SupvisorsStates.RESTARTING
    # no exit method implementation
    state.exit()


def test_master_shutting_down_state(mocker, supvisors_ctx):
    """ Test the ShuttingDown state of the fsm. """
    mocked_starter = supvisors_ctx.starter.abort
    mocked_stopper = supvisors_ctx.stopper.stop_applications
    mocked_stopping = supvisors_ctx.stopper.in_progress
    # create instance to test
    state = MasterShuttingDownState(supvisors_ctx)
    assert isinstance(state, AbstractState)
    # test enter method: starting ang stopping in progress are aborted
    state.enter()
    assert mocked_starter.call_count == 1
    assert mocked_stopper.call_count == 1
    # test next method if check_instances return something
    mocker.patch.object(state, 'check_instances', return_value=SupvisorsStates.INITIALIZATION)
    assert state.next() == SupvisorsStates.SHUTDOWN
    assert not mocked_stopping.called
    # test next method if check_instances return nothing
    state.check_instances.return_value = None
    # test next method: all processes are stopped
    mocked_stopping.return_value = False
    result = state.next()
    assert result == SupvisorsStates.SHUTDOWN
    mocked_stopping.return_value = True
    result = state.next()
    assert result == SupvisorsStates.SHUTTING_DOWN
    # no exit method implementation
    state.exit()


def test_restart_state(supvisors_ctx):
    """ Test the ShutDown state of the fsm. """
    state = RestartState(supvisors_ctx)
    assert isinstance(state, AbstractState)
    # test exit method: call to pusher send_restart for all instances
    assert not state.supvisors.sockets.pusher.send_restart.called
    state.enter()
    assert state.supvisors.sockets.pusher.send_restart.call_args_list == [call(state.local_identifier)]
    # no next / exit implementation. just call it without test
    state.next()
    state.exit()


def test_shutdown_state(supvisors_ctx):
    """ Test the ShutDown state of the fsm. """
    state = ShutdownState(supvisors_ctx)
    assert isinstance(state, AbstractState)
    # test exit method: call to pusher send_restart for all instances
    assert not state.supvisors.sockets.pusher.send_shutdown.called
    state.enter()
    assert state.supvisors.sockets.pusher.send_shutdown.call_args_list == [call(state.local_identifier)]
    # no next / exit implementation. just call it without test
    state.next()
    state.exit()


def test_slave_main_state(mocker, supvisors_ctx):
    """ Test the SlaveMain state of the fsm. """
    supvisors_ctx.fsm.master_state = SupvisorsStates.CONCILIATION
    # create instance to test
    state = SlaveMainState(supvisors_ctx)
    assert isinstance(state, AbstractState)
    # no enter implementation. just call it without test
    state.enter()
    # test next method if check_instances return something
    mocker.patch.object(state, 'check_instances', return_value=SupvisorsStates.INITIALIZATION)
    assert state.next() == SupvisorsStates.INITIALIZATION
    # test next method if check_instances return nothing
    state.check_instances.return_value = None
    # test next method: return master state by default
    assert state.next() == SupvisorsStates.CONCILIATION
    # no exit implementation. just call it without test
    state.exit()


def test_slave_restarting_state(mocker, supvisors_ctx):
    """ Test the SlaveRestarting state of the fsm. """
    supvisors_ctx.fsm.master_state = SupvisorsStates.RESTARTING
    # create instance to test
    state = SlaveRestartingState(supvisors_ctx)
    assert isinstance(state, AbstractState)
    # no enter implementation. just call it without test
    state.enter()
    # test next method if check_instances return something
    mocker.patch.object(state, 'check_instances', return_value=SupvisorsStates.INITIALIZATION)
    assert state.next() == SupvisorsStates.RESTART
    # test next method if check_instances return nothing
    state.check_instances.return_value = None
    # test next method: return master state by default
    assert state.next() == SupvisorsStates.RESTARTING
    # no exit implementation
    state.exit()


def test_slave_shutting_down_state(mocker, supvisors_ctx):
    """ Test the SlaveShuttingDown state of the fsm. """
    supvisors_ctx.fsm.master_state = SupvisorsStates.SHUTTING_DOWN
    # create instance to test
    state = SlaveShuttingDownState(supvisors_ctx)
    assert isinstance(state, AbstractState)
    # no enter implementation. just call it without test
    state.enter()
    # test next method if check_instances return something
    mocker.patch.object(state, 'check_instances', return_value=SupvisorsStates.INITIALIZATION)
    assert state.next() == SupvisorsStates.SHUTDOWN
    # test next method if check_instances return nothing
    state.check_instances.return_value = None
    # test next method: return master state by default
    assert state.next() == SupvisorsStates.SHUTTING_DOWN
    # no exit implementation
    state.exit()


@pytest.fixture
def fsm(supvisors):
    """ Create the FiniteStateMachine instance to test. """
    state_machine = FiniteStateMachine(supvisors)
    supvisors.fsm = state_machine
    return state_machine


def test_creation(supvisors, fsm):
    """ Test the values set at construction. """
    assert fsm.supvisors is supvisors
    assert not fsm.redeploy_mark
    # test that the INITIALIZATION state is triggered at creation
    assert fsm.state == SupvisorsStates.OFF
    assert isinstance(fsm.instance, OffState)


def test_state_string(fsm):
    """ Test the string conversion of state machine. """
    # test string conversion for all states
    for state in SupvisorsStates:
        fsm.state = state
        assert fsm.state.name == state.name


# Patch all state events
MASTER_STATES = [(state, cls.__name__) for state, cls in FiniteStateMachine._MasterStateInstances.items()]
SLAVE_STATES = [(state, cls.__name__) for state, cls in FiniteStateMachine._SlaveStateInstances.items()]
EVENTS = ['enter', 'next', 'exit']


@pytest.fixture
def mock_master_events(mocker):
    return [[(f'{state}.{evt}', mocker.patch(f'supvisors.statemachine.{cls}.{evt}', return_value=state))
             for evt in EVENTS]
            for state, cls in MASTER_STATES]


@pytest.fixture
def mock_slave_events(mocker):
    return [[(f'{state}.{evt}', mocker.patch(f'supvisors.statemachine.{cls}.{evt}', return_value=state))
             for evt in EVENTS]
            for state, cls in SLAVE_STATES]


def compare_calls(call_counts, mock_events):
    """ Compare call counts of mocked methods. """
    for state_call_counts, state_mock_events in zip(call_counts, mock_events):
        for call_count, (tested, mocked) in zip(state_call_counts, state_mock_events):
            assert mocked.call_count == call_count, tested
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
    compare_calls([(0, 0, 1), (1, 1, 0), (0, 0, 0)], mock_master_events)
    assert fsm.instance is not instance_ref
    assert fsm.state == SupvisorsStates.INITIALIZATION
    # test set_state with not authorized transition for master
    fsm.context._is_master = True
    fsm.set_state(SupvisorsStates.OPERATION)
    compare_calls([(0, 0, 0), (0, 0, 0), (0, 0, 0)], mock_master_events)
    assert fsm.instance is not instance_ref
    assert fsm.state == SupvisorsStates.INITIALIZATION
    # test set_state with authorized transition
    fsm.set_state(SupvisorsStates.DEPLOYMENT)
    compare_calls([(0, 0, 0), (0, 0, 1), (1, 1, 0)], mock_master_events)
    assert fsm.instance is not instance_ref
    assert fsm.state == SupvisorsStates.DEPLOYMENT


def test_slave_simple_set_state(fsm, mock_slave_events):
    """ Test single transitions of the state machine using set_state method.
    All transition are applicable for Slave states.
    """
    fsm.master_state = SupvisorsStates.CONCILIATION
    instance_ref = fsm.instance
    # test set_state with identical state parameter
    fsm.set_state(SupvisorsStates.INITIALIZATION)
    compare_calls([(0, 0, 1), (1, 1, 0), (0, 0, 0)], mock_slave_events)
    assert fsm.instance is not instance_ref
    assert fsm.state == SupvisorsStates.INITIALIZATION
    # test set_state with not authorized transition in Master but authorized in Slave
    # as DEPLOYMENT, OPERATION and CONCILIATION are a common state in Slave FSM, only CONCILIATION holds the change
    # in SlaveMainState, automatic transition is allowed from OPERATION to CONCILIATION (Master state)
    fsm.set_state(SupvisorsStates.OPERATION)
    compare_calls([(0, 0, 0), (0, 0, 1), (0, 0, 0), (0, 0, 0), (2, 2, 1)], mock_slave_events)
    assert fsm.instance is not instance_ref
    assert fsm.state == SupvisorsStates.CONCILIATION
    # in SlaveMainState, automatic transition is allowed from DEPLOYMENT to CONCILIATION (Master state)
    fsm.set_state(SupvisorsStates.DEPLOYMENT)
    compare_calls([(0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0), (2, 2, 2)], mock_slave_events)
    assert fsm.instance is not instance_ref
    assert fsm.state == SupvisorsStates.CONCILIATION
    # test set_state with unauthorized transition
    fsm.set_state(SupvisorsStates.SHUTDOWN)
    compare_calls([(0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 1), (0, 0, 0), (0, 0, 0), (0, 0, 0), (1, 1, 0)],
                  mock_slave_events)
    assert fsm.state == SupvisorsStates.SHUTDOWN


def test_master_complex_set_state(fsm, mock_master_events):
    """ Test multiple transitions of the Master FSM using set_state method. """
    mock_master_events[0][1][1].return_value = SupvisorsStates.INITIALIZATION
    mock_master_events[1][1][1].return_value = SupvisorsStates.DEPLOYMENT
    mock_master_events[2][1][1].return_value = SupvisorsStates.OPERATION
    instance_ref = fsm.instance
    # test set_state with authorized transition
    fsm.context._is_master = True
    fsm.set_state(SupvisorsStates.INITIALIZATION)
    compare_calls([(0, 0, 1), (1, 1, 1), (1, 1, 1), (1, 1, 0)], mock_master_events)
    assert fsm.instance is not instance_ref
    assert fsm.state == SupvisorsStates.OPERATION


def test_fsm_next(mocker, fsm):
    """ Test the principle of the FiniteStateMachine.next method. """
    mocker_state = mocker.patch.object(fsm, 'set_state')
    fsm.next()
    assert fsm.supvisors.starter.check.called
    assert fsm.supvisors.stopper.check.called
    assert mocker_state.called


def test_master_no_next(fsm, mock_master_events):
    """ Test no transition of the state machine using next method. """
    mock_master_events[0][1][1].return_value = SupvisorsStates.OFF
    instance_ref = fsm.instance
    # test set_state with authorized transition
    fsm.context._is_master = True
    fsm.next()
    compare_calls([(0, 1, 0)], mock_master_events)
    assert fsm.instance is instance_ref
    assert fsm.state == SupvisorsStates.OFF


def test_master_simple_next(fsm, mock_master_events):
    """ Test single transition of the state machine using next_method. """
    mock_master_events[0][1][1].return_value = SupvisorsStates.INITIALIZATION
    mock_master_events[1][1][1].return_value = SupvisorsStates.DEPLOYMENT
    mock_master_events[2][1][1].return_value = SupvisorsStates.DEPLOYMENT
    instance_ref = fsm.instance
    # test set_state with authorized transition
    fsm.context._is_master = True
    fsm.next()
    compare_calls([(0, 1, 1), (1, 1, 1), (1, 1, 0)], mock_master_events)
    assert fsm.instance is not instance_ref
    assert fsm.state == SupvisorsStates.DEPLOYMENT


def test_master_complex_next(fsm, mock_master_events):
    """ Test multiple transitions of the state machine using next_method. """
    mock_master_events[0][1][1].return_value = SupvisorsStates.INITIALIZATION
    mock_master_events[1][1][1].side_effect = [SupvisorsStates.DEPLOYMENT, SupvisorsStates.DEPLOYMENT]
    mock_master_events[2][1][1].side_effect = [SupvisorsStates.OPERATION, SupvisorsStates.OPERATION]
    mock_master_events[3][1][1].side_effect = [SupvisorsStates.CONCILIATION, SupvisorsStates.INITIALIZATION,
                                               SupvisorsStates.RESTARTING]
    mock_master_events[4][1][1].side_effect = [SupvisorsStates.OPERATION]
    mock_master_events[5][1][1].return_value = SupvisorsStates.RESTART
    instance_ref = fsm.instance
    # test set_state with authorized transition
    fsm.context._is_master = True
    fsm.next()
    compare_calls([(0, 1, 1), (2, 2, 2), (2, 2, 2), (3, 3, 3), (1, 1, 1), (1, 1, 1), (1, 1, 0), (0, 0, 0), (0, 0, 0)],
                  mock_master_events)
    assert fsm.instance is not instance_ref
    assert fsm.state == SupvisorsStates.RESTART


def test_timer_event(mocker, fsm):
    """ Test the actions triggered in state machine upon reception of a timer event. """
    # apply patches
    proc_1 = Mock(namespec='proc_1')
    proc_2 = Mock(namespec='proc_2')
    mocked_event = mocker.patch.object(fsm.supvisors.context, 'on_timer_event',
                                       return_value=(['10.0.0.3'], [proc_1, proc_2]))
    mocked_next = mocker.patch.object(fsm, 'next')
    mocked_starter = fsm.supvisors.starter.on_instances_invalidation
    mocked_stopper = fsm.supvisors.stopper.on_instances_invalidation
    mocked_add = fsm.supvisors.failure_handler.add_default_job
    mocked_trigger = fsm.supvisors.failure_handler.trigger_jobs
    mocked_isolation = mocker.patch.object(fsm.supvisors.context, 'handle_isolation',
                                           return_value=['10.0.0.2', '10.0.0.3'])
    mocked_isolate = fsm.supvisors.sockets.pusher.send_isolate_instances
    # test when not master and instances to isolate
    assert not fsm.context.is_master
    event = {'counter': 1234}
    fsm.on_timer_event(event)
    # check result: marked processes are started
    assert mocked_event.call_args_list == [call(event)]
    assert mocked_starter.call_args_list == [call(['10.0.0.3'], [proc_1, proc_2])]
    assert mocked_stopper.call_args_list == [call(['10.0.0.3'], [proc_1, proc_2])]
    assert mocked_next.call_args_list == [call()]
    assert not mocked_add.called
    assert not mocked_trigger.called
    assert mocked_isolation.call_args_list == [call()]
    assert mocked_isolate.call_args_list == [call(['10.0.0.2', '10.0.0.3'])]
    # reset mocks
    mocker.resetall()
    mocked_isolate.reset_mock()
    mocked_starter.reset_mock()
    mocked_stopper.reset_mock()
    # test when not master and no node to isolate
    fsm.context._is_master = True
    mocked_isolation.return_value = []
    assert fsm.context.is_master
    fsm.on_timer_event(event)
    # check result: marked processes are started
    assert mocked_event.call_args_list == [call(event)]
    assert mocked_starter.call_args_list == [call(['10.0.0.3'], [proc_1, proc_2])]
    assert mocked_stopper.call_args_list == [call(['10.0.0.3'], [proc_1, proc_2])]
    assert mocked_next.call_args_list == [call()]
    assert mocked_add.call_args_list == [call(proc_1), call(proc_2)]
    assert mocked_trigger.call_args_list == [call()]
    assert mocked_isolation.call_args_list == [call()]
    assert not mocked_isolate.called


def test_tick_event(mocker, fsm):
    """ Test the actions triggered in state machine upon reception of a tick event. """
    # inject tick event and test call to context on_tick_event
    mocked_evt = mocker.patch.object(fsm.supvisors.context, 'on_tick_event')
    # test when tick comes from another node
    event = {'tick': 1234, 'ip_address': '10.0.0.1', 'server_port': 1234}
    fsm.on_tick_event('10.0.0.1', event)
    assert mocked_evt.call_args_list == [call('10.0.0.1', event)]
    assert not fsm.redeploy_mark
    mocker.resetall()
    # test when tick comes from local node
    local_identifier = fsm.supvisors.supvisors_mapper.local_identifier
    event['ip_address'] = fsm.supvisors.supvisors_mapper.local_instance.ip_address
    fsm.on_tick_event(local_identifier, event)
    assert mocked_evt.call_args_list == [call(local_identifier, event)]
    assert not fsm.redeploy_mark
    mocker.resetall()
    # activate discovery mode
    fsm.supvisors.options.multicast_address = '239.0.0.1'
    event = {'tick': 1357, 'ip_address': '192.168.1.1', 'server_port': 5000}
    fsm.on_tick_event('rocky52', event)
    assert mocked_evt.call_args_list == [call('rocky52', event)]
    assert fsm.redeploy_mark


def test_process_state_event_process_not_found(mocker, fsm):
    """ Test the actions triggered in state machine upon reception of a process state event.
    Test case: event is about an unknown process. """
    # get patches
    mocked_restart = mocker.patch.object(fsm, 'on_restart')
    mocked_shutdown = mocker.patch.object(fsm, 'on_shutdown')
    mocked_ctx = mocker.patch.object(fsm.supvisors.context, 'on_process_state_event', return_value=None)
    mocked_start_evt = fsm.supvisors.starter.on_event
    mocked_stop_evt = fsm.supvisors.stopper.on_event
    mocked_add = fsm.supvisors.failure_handler.add_default_job
    # test that no action is triggered when corresponding process is not found
    fsm.on_process_state_event('10.0.0.1', {'process_name': 'dummy_proc'})
    assert mocked_ctx.call_args_list == [call('10.0.0.1', {'process_name': 'dummy_proc'})]
    assert not mocked_start_evt.called
    assert not mocked_stop_evt.called
    assert not mocked_restart.called
    assert not mocked_shutdown.called
    assert not mocked_add.called


def test_process_state_event_not_master(mocker, fsm):
    """ Test the actions triggered in state machine upon reception of a process state event.
    Test case: process is found but local Supvisors instance is not master. """
    # prepare context
    fsm.supvisors.context._is_master = False
    process = Mock()
    # get patches
    mocked_restart = mocker.patch.object(fsm, 'on_restart')
    mocked_shutdown = mocker.patch.object(fsm, 'on_shutdown')
    mocked_ctx = mocker.patch.object(fsm.supvisors.context, 'on_process_state_event', return_value=process)
    mocked_start_evt = fsm.supvisors.starter.on_event
    mocked_stop_evt = fsm.supvisors.stopper.on_event
    mocked_add = fsm.supvisors.failure_handler.add_default_job
    # when process is found but local Supvisors instance is not master, only starter and stopper are called
    event = {'process_name': 'dummy_proc'}
    fsm.on_process_state_event('10.0.0.1', event)
    assert mocked_ctx.call_args_list == [call('10.0.0.1', event)]
    assert mocked_start_evt.call_args_list == [call(process, '10.0.0.1')]
    assert mocked_stop_evt.call_args_list == [call(process, '10.0.0.1')]
    assert not mocked_restart.called
    assert not mocked_shutdown.called
    assert not mocked_add.called


def test_process_state_event_no_crash(mocker, fsm):
    """ Test the actions triggered in state machine upon reception of a process state event.
    Test case: process is found - no crash, local Supvisors instance is master. """
    # prepare context
    fsm.supvisors.context._is_master = True
    process = Mock(**{'crashed.return_value': False})
    event = {'process_name': 'dummy_proc'}
    # get patches
    mocked_restart = mocker.patch.object(fsm, 'on_restart')
    mocked_shutdown = mocker.patch.object(fsm, 'on_shutdown')
    mocked_ctx = mocker.patch.object(fsm.supvisors.context, 'on_process_state_event', return_value=process)
    mocked_start_evt = fsm.supvisors.starter.on_event
    mocked_stop_evt = fsm.supvisors.stopper.on_event
    mocked_add = fsm.supvisors.failure_handler.add_default_job
    # test when process has not crashed
    for strategy in RunningFailureStrategies:
        process.rules.running_failure_strategy = strategy
        fsm.on_process_state_event('10.0.0.1', event)
        assert mocked_ctx.call_args_list == [call('10.0.0.1', event)]
        assert mocked_start_evt.call_args_list == [call(process, '10.0.0.1')]
        assert mocked_stop_evt.call_args_list == [call(process, '10.0.0.1')]
        assert not mocked_restart.called
        assert not mocked_shutdown.called
        assert not mocked_add.called
        # reset mocks
        mocked_ctx.reset_mock()
        mocked_start_evt.reset_mock()
        mocked_stop_evt.reset_mock()
        mocked_add.reset_mock()


def test_process_state_event_crash_restart(mocker, fsm):
    """ Test the actions triggered in state machine upon reception of a process state event.
    Test case: process is found, event is a crash, rule is RESTART, local Supvisors instance is master. """
    # prepare context
    fsm.supvisors.context._is_master = True
    process = Mock(**{'crashed.return_value': True})
    event = {'process_name': 'dummy_proc'}
    # get patches
    mocked_restart = mocker.patch.object(fsm, 'on_restart')
    mocked_shutdown = mocker.patch.object(fsm, 'on_shutdown')
    mocked_ctx = mocker.patch.object(fsm.supvisors.context, 'on_process_state_event', return_value=process)
    mocked_start_evt = fsm.supvisors.starter.on_event
    mocked_stop_evt = fsm.supvisors.stopper.on_event
    mocked_add = fsm.supvisors.failure_handler.add_default_job
    # test when process has crashed and rule is RESTART
    process.rules.running_failure_strategy = RunningFailureStrategies.RESTART
    fsm.on_process_state_event('10.0.0.1', event)
    assert mocked_ctx.call_args_list == [call('10.0.0.1', event)]
    assert mocked_start_evt.call_args_list == [call(process, '10.0.0.1')]
    assert mocked_stop_evt.call_args_list == [call(process, '10.0.0.1')]
    assert mocked_restart.called
    assert not mocked_shutdown.called
    assert not mocked_add.called


def test_process_state_event_crash_shutdown(mocker, fsm):
    """ Test the actions triggered in state machine upon reception of a process state event.
    Test case: process is found, event is a crash, rule is SHUTDOWN, local Supvisors instance is master. """
    # prepare context
    fsm.supvisors.context._is_master = True
    process = Mock(**{'crashed.return_value': True})
    event = {'process_name': 'dummy_proc'}
    # get patches
    mocked_restart = mocker.patch.object(fsm, 'on_restart')
    mocked_shutdown = mocker.patch.object(fsm, 'on_shutdown')
    mocked_ctx = mocker.patch.object(fsm.supvisors.context, 'on_process_state_event', return_value=process)
    mocked_start_evt = fsm.supvisors.starter.on_event
    mocked_stop_evt = fsm.supvisors.stopper.on_event
    mocked_add = fsm.supvisors.failure_handler.add_default_job
    # test when process has crashed and rule is shutdown
    process.rules.running_failure_strategy = RunningFailureStrategies.SHUTDOWN
    fsm.on_process_state_event('10.0.0.1', event)
    assert mocked_ctx.call_args_list == [call('10.0.0.1', event)]
    assert mocked_start_evt.call_args_list == [call(process, '10.0.0.1')]
    assert mocked_stop_evt.call_args_list == [call(process, '10.0.0.1')]
    assert not mocked_restart.called
    assert mocked_shutdown.called
    assert not mocked_add.called


def test_process_state_event_crash_continue(mocker, fsm):
    """ Test the actions triggered in state machine upon reception of a process state event.
    Test case: process is found, event is a crash, rule is CONTINUE, local Supvisors instance is master. """
    # prepare context
    fsm.supvisors.context._is_master = True
    process = Mock(**{'crashed.return_value': True})
    event = {'process_name': 'dummy_proc'}
    # get patches
    mocked_restart = mocker.patch.object(fsm, 'on_restart')
    mocked_shutdown = mocker.patch.object(fsm, 'on_shutdown')
    mocked_ctx = mocker.patch.object(fsm.supvisors.context, 'on_process_state_event', return_value=process)
    mocked_start_evt = fsm.supvisors.starter.on_event
    mocked_stop_evt = fsm.supvisors.stopper.on_event
    mocked_add = fsm.supvisors.failure_handler.add_default_job
    # test with running_failure_strategy set to CONTINUE so job is not added to failure handler
    process.rules.running_failure_strategy = RunningFailureStrategies.CONTINUE
    fsm.on_process_state_event('10.0.0.1', event)
    assert mocked_ctx.call_args_list == [call('10.0.0.1', event)]
    assert mocked_start_evt.call_args_list == [call(process, '10.0.0.1')]
    assert mocked_stop_evt.call_args_list == [call(process, '10.0.0.1')]
    assert not mocked_restart.called
    assert not mocked_shutdown.called
    assert mocked_add.call_args_list == []


def test_process_state_event_crash_restart_process(mocker, fsm):
    """ Test the actions triggered in state machine upon reception of a process state event.
    Test case: process is found, event is a crash, rule is RESTART_PROCESS, local Supvisors instance is master. """
    # prepare context
    fsm.supvisors.context._is_master = True
    process = Mock(**{'crashed.return_value': True})
    event = {'process_name': 'dummy_proc'}
    # get patches
    mocked_restart = mocker.patch.object(fsm, 'on_restart')
    mocked_shutdown = mocker.patch.object(fsm, 'on_shutdown')
    mocked_ctx = mocker.patch.object(fsm.supvisors.context, 'on_process_state_event', return_value=process)
    mocked_start_evt = fsm.supvisors.starter.on_event
    mocked_stop_evt = fsm.supvisors.stopper.on_event
    mocked_add = fsm.supvisors.failure_handler.add_default_job
    # test with running_failure_strategy set to CONTINUE / RESTART_PROCESS so job is not added to failure handler
    process.rules.running_failure_strategy = RunningFailureStrategies.RESTART_PROCESS
    fsm.on_process_state_event('10.0.0.1', event)
    assert mocked_ctx.call_args_list == [call('10.0.0.1', event)]
    assert mocked_start_evt.call_args_list == [call(process, '10.0.0.1')]
    assert mocked_stop_evt.call_args_list == [call(process, '10.0.0.1')]
    assert not mocked_restart.called
    assert not mocked_shutdown.called
    assert mocked_add.call_args_list == []


def test_process_state_event_crash_stop_application(mocker, fsm):
    """ Test the actions triggered in state machine upon reception of a process state event.
    Test case: process is found, event is a crash (not forced), rule is STOP_APPLICATION, local Supvisors instance
    is master. """
    # prepare context
    fsm.supvisors.context._is_master = True
    process = Mock(forced_state=None, **{'crashed.return_value': True})
    event = {'process_name': 'dummy_proc'}
    # get patches
    mocked_restart = mocker.patch.object(fsm, 'on_restart')
    mocked_shutdown = mocker.patch.object(fsm, 'on_shutdown')
    mocked_ctx = mocker.patch.object(fsm.supvisors.context, 'on_process_state_event', return_value=process)
    mocked_start_evt = fsm.supvisors.starter.on_event
    mocked_stop_evt = fsm.supvisors.stopper.on_event
    mocked_add = fsm.supvisors.failure_handler.add_default_job
    # job is added to failure handler
    process.rules.running_failure_strategy = RunningFailureStrategies.STOP_APPLICATION
    fsm.on_process_state_event('10.0.0.1', event)
    assert mocked_ctx.call_args_list == [call('10.0.0.1', event)]
    assert mocked_start_evt.call_args_list == [call(process, '10.0.0.1')]
    assert mocked_stop_evt.call_args_list == [call(process, '10.0.0.1')]
    assert not mocked_restart.called
    assert not mocked_shutdown.called
    assert mocked_add.call_args_list == [call(process)]


def test_process_state_event_crash_restart_application(mocker, fsm):
    """ Test the actions triggered in state machine upon reception of a process state event.
    Test case: process is found, event is a crash (not forced), rule is RESTART_APPLICATION, local Supvisors instance
    is master. """
    # prepare context
    fsm.supvisors.context._is_master = True
    process = Mock(forced_state=None, **{'crashed.return_value': True})
    event = {'process_name': 'dummy_proc'}
    # get patches
    mocked_restart = mocker.patch.object(fsm, 'on_restart')
    mocked_shutdown = mocker.patch.object(fsm, 'on_shutdown')
    mocked_ctx = mocker.patch.object(fsm.supvisors.context, 'on_process_state_event', return_value=process)
    mocked_start_evt = fsm.supvisors.starter.on_event
    mocked_stop_evt = fsm.supvisors.stopper.on_event
    mocked_add = fsm.supvisors.failure_handler.add_default_job
    # job is added to failure handler
    process.rules.running_failure_strategy = RunningFailureStrategies.RESTART_APPLICATION
    fsm.on_process_state_event('10.0.0.1', event)
    assert mocked_ctx.call_args_list == [call('10.0.0.1', event)]
    assert mocked_start_evt.call_args_list == [call(process, '10.0.0.1')]
    assert mocked_stop_evt.call_args_list == [call(process, '10.0.0.1')]
    assert not mocked_restart.called
    assert not mocked_shutdown.called
    assert mocked_add.call_args_list == [call(process)]


def test_process_state_event_forced_crash(mocker, fsm):
    """ Test the actions triggered in state machine upon reception of a process state event. """
    # prepare context
    fsm.supvisors.context._is_master = True
    process = Mock(forced_state=ProcessStates.FATAL, **{'crashed.return_value': True})
    event = {'process_name': 'dummy_proc'}
    # get patches
    mocked_restart = mocker.patch.object(fsm, 'on_restart')
    mocked_shutdown = mocker.patch.object(fsm, 'on_shutdown')
    mocked_ctx = mocker.patch.object(fsm.supvisors.context, 'on_process_state_event', return_value=process)
    mocked_start_evt = fsm.supvisors.starter.on_event
    mocked_stop_evt = fsm.supvisors.stopper.on_event
    mocked_add = fsm.supvisors.failure_handler.add_default_job
    # job is added to failure handler only if process crash is 'real' (not forced)
    for strategy in [RunningFailureStrategies.RESTART_APPLICATION, RunningFailureStrategies.STOP_APPLICATION]:
        process.rules.running_failure_strategy = strategy
        fsm.on_process_state_event('10.0.0.1', event)
        assert mocked_ctx.call_args_list == [call('10.0.0.1', event)]
        assert mocked_start_evt.call_args_list == [call(process, '10.0.0.1')]
        assert mocked_stop_evt.call_args_list == [call(process, '10.0.0.1')]
        assert not mocked_restart.called
        assert not mocked_shutdown.called
        assert not mocked_add.called
        mocker.resetall()
        mocked_start_evt.reset_mock()
        mocked_stop_evt.reset_mock()


def test_on_process_added_event(mocker, fsm):
    """ Test the actions triggered in state machine upon reception of a process added event. """
    mocked_load = mocker.patch.object(fsm.context, 'load_processes')
    fsm.on_process_added_event('10.0.0.1', [{'info': 'dummy_info'}])
    assert mocked_load.call_args_list == [call('10.0.0.1', [{'info': 'dummy_info'}])]


def test_on_process_removed_event(mocker, fsm):
    """ Test the actions triggered in state machine upon reception of a process removed event. """
    mocked_context = mocker.patch.object(fsm.context, 'on_process_removed_event')
    fsm.on_process_removed_event('10.0.0.1', {'info': 'dummy_info'})
    assert mocked_context.call_args_list == [call('10.0.0.1', {'info': 'dummy_info'})]


def test_on_process_disability_event(mocker, fsm):
    """ Test the actions triggered in state machine upon reception of a process enabled event. """
    mocked_context = mocker.patch.object(fsm.context, 'on_process_disability_event')
    fsm.on_process_disability_event('10.0.0.1', {'info': 'dummy_info', 'disabled': True})
    assert mocked_context.call_args_list == [call('10.0.0.1', {'info': 'dummy_info', 'disabled': True})]


def test_on_process_info(mocker, fsm):
    """ Test the actions triggered in state machine upon reception of a process information. """
    # inject process info and test call to context load_processes
    mocked_load = mocker.patch.object(fsm.context, 'load_processes')
    fsm.on_process_info('10.0.0.1', {'info': 'dummy_info'})
    assert mocked_load.call_args_list == [call('10.0.0.1', {'info': 'dummy_info'})]


def test_on_state_event(mocker, fsm):
    """ Test the actions triggered in state machine upon reception of a Master state event. """
    mocked_state = mocker.patch.object(fsm, 'set_state')
    fsm.master_state = SupvisorsStates.OPERATION
    fsm.context.master_identifier = '10.0.0.1'
    payload = {'starting_jobs': False, 'stopping_jobs': False}
    # test event not sent by Master node
    for state in SupvisorsStates:
        payload['fsm_statecode'] = state.value
        fsm.on_state_event('10.0.0.2', payload)
        assert fsm.master_state == SupvisorsStates.OPERATION
        assert not mocked_state.called
    # test event sent by Master node
    for state in SupvisorsStates:
        mocker.patch.object(fsm.instance, 'next', return_value=state)
        payload['fsm_statecode'] = state.value
        fsm.on_state_event('10.0.0.1', payload)
        assert fsm.master_state == state
        assert mocked_state.call_args_list == [call(state)]
        mocker.resetall()


def test_on_authorization(mocker, fsm):
    """ Test the actions triggered in state machine upon reception of an authorization event. """
    # prepare context
    mocked_auth = mocker.patch.object(fsm.context, 'on_authorization', return_value=False)
    # set initial condition
    local_identifier = fsm.supvisors.supvisors_mapper.local_identifier
    nodes = fsm.context.instances
    nodes[local_identifier]._state = SupvisorsInstanceStates.RUNNING
    nodes['10.0.0.5']._state = SupvisorsInstanceStates.RUNNING
    fsm.set_state(SupvisorsStates.INITIALIZATION)
    # test rejected authorization
    fsm.on_authorization('10.0.0.1', False, '10.0.0.5')
    assert mocked_auth.call_args_list == [call('10.0.0.1', False)]
    assert fsm.state == SupvisorsStates.INITIALIZATION
    assert fsm.context.master_identifier == ''
    assert not fsm.redeploy_mark
    # reset mocks
    mocked_auth.reset_mock()
    mocked_auth.return_value = True
    # test authorization when no master node provided
    fsm.on_authorization('10.0.0.1', True, '')
    assert mocked_auth.call_args == call('10.0.0.1', True)
    assert fsm.state == SupvisorsStates.INITIALIZATION
    assert fsm.context.master_identifier == ''
    assert not fsm.redeploy_mark
    # reset mocks
    mocked_auth.reset_mock()
    # test authorization and master node assignment
    fsm.on_authorization('10.0.0.1', True, '10.0.0.5')
    assert mocked_auth.call_args == call('10.0.0.1', True)
    assert fsm.state == SupvisorsStates.INITIALIZATION
    assert fsm.context.master_identifier == '10.0.0.5'
    assert not fsm.redeploy_mark
    # reset mocks
    mocked_auth.reset_mock()
    # test authorization and master node conflict
    fsm.state = SupvisorsStates.OPERATION
    fsm.instance = MasterOperationState(fsm.supvisors)
    fsm.on_authorization('10.0.0.3', True, '10.0.0.4')
    assert mocked_auth.call_args == call('10.0.0.3', True)
    assert fsm.state == SupvisorsStates.INITIALIZATION
    assert fsm.context.master_identifier == ''
    assert not fsm.redeploy_mark
    # change context while instance is not master
    nodes[local_identifier]._state = SupvisorsInstanceStates.RUNNING
    nodes['10.0.0.5']._state = SupvisorsInstanceStates.RUNNING
    fsm.master_state = SupvisorsStates.OPERATION
    # as local is not master and master is operational, automatic transition
    fsm.set_state(SupvisorsStates.DEPLOYMENT)
    assert fsm.state == SupvisorsStates.OPERATION
    # set current instance as master
    fsm.supvisors.context._is_master = True
    # test authorization when no master node provided
    fsm.on_authorization('10.0.0.4', True, '')
    assert mocked_auth.call_args == call('10.0.0.4', True)
    assert fsm.state == SupvisorsStates.OPERATION
    assert fsm.supvisors.context.master_identifier == '10.0.0.5'
    assert fsm.redeploy_mark
    # test authorization and master node conflict
    fsm.on_authorization('10.0.0.5', True, '10.0.0.4')
    assert mocked_auth.call_args == call('10.0.0.5', True)
    assert fsm.state == SupvisorsStates.INITIALIZATION
    assert fsm.supvisors.context.master_identifier == ''
    assert fsm.redeploy_mark


def test_restart_sequence_event(fsm):
    """ Test the actions triggered in state machine upon reception of a restart_sequence event. """
    # inject restart event and test setting of redeploy_mark
    mocked_zmq = fsm.supvisors.sockets.pusher.send_restart_sequence
    fsm.supvisors.context.master_identifier = '10.0.0.1'
    assert not fsm.redeploy_mark
    # test when not master
    fsm.on_restart_sequence()
    assert not fsm.redeploy_mark
    assert mocked_zmq.call_args_list == [call('10.0.0.1')]
    mocked_zmq.reset_mock()
    # test when master
    fsm.context._is_master = True
    fsm.on_restart_sequence()
    assert not mocked_zmq.called
    assert fsm.redeploy_mark is Forced


def test_restart_event(mocker, fsm):
    """ Test the actions triggered in state machine upon reception of a restart event. """
    # inject restart event and test call to fsm set_state RESTARTING
    mocked_fsm = mocker.patch.object(fsm, 'set_state')
    mocked_zmq = fsm.supvisors.sockets.pusher.send_restart_all
    fsm.supvisors.context.master_identifier = '10.0.0.1'
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
    mocked_zmq = fsm.supvisors.sockets.pusher.send_shutdown_all
    fsm.supvisors.context.master_identifier = '10.0.0.1'
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
