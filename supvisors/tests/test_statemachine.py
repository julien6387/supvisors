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

import socket
from unittest.mock import call, patch, Mock, DEFAULT

import pytest
from supervisor.states import ProcessStates

from supvisors.statemachine import *
from supvisors.ttypes import ConciliationStrategies, SupvisorsInstanceStates, SupvisorsStates


@pytest.fixture
def supvisors_ctx(supvisors):
    """ Create a Supvisors-like structure filled with some instances. """
    local_identifier = supvisors.mapper.local_identifier
    nodes = supvisors.context.instances
    nodes[local_identifier]._state = SupvisorsInstanceStates.RUNNING
    nodes['10.0.0.1:25000']._state = SupvisorsInstanceStates.STOPPED
    nodes['10.0.0.2:25000']._state = SupvisorsInstanceStates.RUNNING
    nodes['10.0.0.3:25000']._state = SupvisorsInstanceStates.CHECKING
    nodes['10.0.0.4:25000']._state = SupvisorsInstanceStates.FAILED
    nodes['10.0.0.5:25000']._state = SupvisorsInstanceStates.ISOLATED
    nodes[f'{socket.getfqdn()}:15000']._state = SupvisorsInstanceStates.STOPPED
    return supvisors


def test_base_state(supvisors_ctx):
    """ Test the SupvisorsBaseState of the FSM. """
    state = SupvisorsBaseState(supvisors_ctx)
    # check attributes at creation
    assert state.supvisors is supvisors_ctx
    assert state.lost_instances == []
    assert state.lost_processes == set()
    assert state.sync_alerts == {SynchronizationOptions.STRICT: False,
                                 SynchronizationOptions.LIST: False,
                                 SynchronizationOptions.TIMEOUT: False,
                                 SynchronizationOptions.CORE: False,
                                 SynchronizationOptions.USER: False}
    assert state.logger is supvisors_ctx.logger
    assert state.context is supvisors_ctx.context
    assert state.state_modes is supvisors_ctx.state_modes
    assert state.local_identifier == supvisors_ctx.mapper.local_identifier
    # call empty methods
    state.enter()
    state.exit()
    state._check_consistence()
    # test next: first call will transition CHECKED and FAILED instances
    assert state.next() is None
    assert state.lost_instances == ['10.0.0.4:25000']
    assert state.lost_processes == set()
    for identifier, instance_state in [(state.local_identifier, SupvisorsInstanceStates.RUNNING),
                                       ('10.0.0.1:25000', SupvisorsInstanceStates.STOPPED),
                                       ('10.0.0.2:25000', SupvisorsInstanceStates.RUNNING),
                                       ('10.0.0.3:25000', SupvisorsInstanceStates.CHECKING),
                                       ('10.0.0.4:25000', SupvisorsInstanceStates.STOPPED),
                                       ('10.0.0.5:25000', SupvisorsInstanceStates.ISOLATED),
                                       (f'{socket.getfqdn()}:15000', SupvisorsInstanceStates.STOPPED)]:
        assert state.context.instances[identifier].state == instance_state
    # test abort_jobs method
    state._abort_jobs()
    assert supvisors_ctx.failure_handler.abort.called
    assert supvisors_ctx.starter.abort.called
    assert supvisors_ctx.stopper.abort.called


def check_on_state(fsm_state: OnState, forced_state: SupvisorsStates = None, default_state: SupvisorsStates = None):
    """ Test the transitions from any state inheriting from OnState. """
    # default: local is RUNNING and no sync option set
    assert fsm_state.next() == default_state
    # set local to STOPPED => transition to OFF
    fsm_state.context.local_status._state = SupvisorsInstanceStates.STOPPED
    assert fsm_state.next() == forced_state or SupvisorsStates.OFF
    fsm_state.context.local_status._state = SupvisorsInstanceStates.RUNNING


def test_on_state(supvisors_ctx):
    """ Test the OnState of the FSM. """
    state = OnState(supvisors_ctx)
    assert isinstance(state, SupvisorsBaseState)
    # set local to STOPPED => transition to OFF
    check_on_state(state)
    # reset FAILED and call next to get lost instances
    supvisors_ctx.context.instances['10.0.0.4:25000']._state = SupvisorsInstanceStates.FAILED
    assert state.next() is None
    # test options - none set by default
    assert state._check_strict_failure() is None
    assert state._check_list_failure() is None
    assert state._check_core_failure() is None
    assert state._check_user_failure() is None
    # add all options at once
    supvisors_ctx.options.synchro_options = [opt for opt in SynchronizationOptions]
    assert state._check_strict_failure() is True  # some non-RUNNING
    assert state._check_list_failure() is True  # some non-RUNNING
    assert state._check_core_failure() is False  # no core instances
    assert state._check_user_failure() is True  # one FAILED instance
    assert state.sync_alerts == {SynchronizationOptions.STRICT: True,
                                 SynchronizationOptions.LIST: True,
                                 SynchronizationOptions.TIMEOUT: False,
                                 SynchronizationOptions.CORE: False,
                                 SynchronizationOptions.USER: True}
    # raise CORE failure and fix FAILED
    supvisors_ctx.mapper._core_identifiers = ['10.0.0.1:25000']
    state.lost_instances = []
    assert state._check_strict_failure() is True  # some not RUNNING
    assert state._check_list_failure() is True  # some not RUNNING
    assert state._check_core_failure() is True  # core instance not RUNNING and no stable context
    assert state._check_user_failure() is False
    assert state.sync_alerts == {SynchronizationOptions.STRICT: True,
                                 SynchronizationOptions.LIST: True,
                                 SynchronizationOptions.TIMEOUT: False,
                                 SynchronizationOptions.CORE: True,
                                 SynchronizationOptions.USER: False}
    # force state context stabilization
    state.state_modes.stable_identifiers = set(supvisors_ctx.mapper.instances.keys())
    assert state._check_strict_failure() is True  # some not RUNNING
    assert state._check_list_failure() is True  # some not RUNNING
    assert state._check_core_failure() is True  # core instance still not RUNNING
    assert state._check_user_failure() is False
    assert state.sync_alerts == {SynchronizationOptions.STRICT: True,
                                 SynchronizationOptions.LIST: True,
                                 SynchronizationOptions.TIMEOUT: False,
                                 SynchronizationOptions.CORE: True,
                                 SynchronizationOptions.USER: False}
    # ack all alerts for code coverage
    for identifier in supvisors_ctx.mapper.instances:
        supvisors_ctx.context.instances[identifier]._state = SupvisorsInstanceStates.RUNNING
        supvisors_ctx.state_modes.local_state_modes.instance_states[identifier] = SupvisorsInstanceStates.RUNNING
    assert state._check_strict_failure() is False
    assert state._check_list_failure() is False
    assert state._check_core_failure() is False
    assert state._check_user_failure() is False
    assert state.sync_alerts == {SynchronizationOptions.STRICT: False,
                                 SynchronizationOptions.LIST: False,
                                 SynchronizationOptions.TIMEOUT: False,
                                 SynchronizationOptions.CORE: False,
                                 SynchronizationOptions.USER: False}


def check_synchronized_state(fsm_state: SynchronizedState, forced_state: SupvisorsStates = None,
                             default_state: SupvisorsStates = None):
    """ Test the transitions from any state inheriting from SynchronizedState. """
    # OnState test is applicable
    check_on_state(fsm_state, forced_state, default_state)
    assert not fsm_state.supvisors.state_modes.degraded_mode
    # SynchronizedState specific
    # test no transition with STRICT failure and CONTINUE strategy
    fsm_state.context.local_status._state = SupvisorsInstanceStates.RUNNING
    fsm_state.supvisors.options.synchro_options = [SynchronizationOptions.STRICT]
    fsm_state.supvisors.options.supvisors_failure_strategy = SupvisorsFailureStrategies.CONTINUE
    assert fsm_state._check_strict_failure()
    assert fsm_state.next() == default_state
    assert fsm_state.state_modes.degraded_mode
    fsm_state.state_modes.degraded_mode = False
    # test transition to SYNCHRONIZATION with LIST failure and RESYNC strategy
    fsm_state.supvisors.options.synchro_options = [SynchronizationOptions.LIST]
    fsm_state.supvisors.options.supvisors_failure_strategy = SupvisorsFailureStrategies.RESYNC
    assert fsm_state._check_list_failure()
    assert fsm_state.next() == forced_state or SupvisorsStates.SYNCHRONIZATION
    assert fsm_state.state_modes.degraded_mode
    fsm_state.state_modes.degraded_mode = False
    # test transition to SHUTTING_DOWN with CORE failure and SHUTDOWN strategy
    fsm_state.supvisors.options.synchro_options = [SynchronizationOptions.CORE]
    fsm_state.supvisors.options.supvisors_failure_strategy = SupvisorsFailureStrategies.SHUTDOWN
    fsm_state.supvisors.mapper._core_identifiers = ['10.0.0.1:25000']
    assert fsm_state._check_core_failure()
    assert fsm_state.next() == forced_state or SupvisorsStates.SHUTTING_DOWN
    assert fsm_state.state_modes.degraded_mode
    fsm_state.state_modes.degraded_mode = False
    # test no transition with USER failure and CONTINUE strategy
    # USER do not set a degraded mode
    fsm_state.supvisors.options.synchro_options = [SynchronizationOptions.USER]
    fsm_state.supvisors.options.supvisors_failure_strategy = SupvisorsFailureStrategies.CONTINUE
    fsm_state.context.instances['10.0.0.4:25000']._state = SupvisorsInstanceStates.FAILED
    fsm_state.supvisors.mapper._core_identifiers = []
    assert fsm_state.next() == default_state
    assert fsm_state._check_user_failure()
    assert not fsm_state.state_modes.degraded_mode
    # test no transition with no CORE failure, STRICT failure and RESYNC strategy
    fsm_state.supvisors.options.synchro_options = [SynchronizationOptions.CORE, SynchronizationOptions.STRICT]
    fsm_state.supvisors.options.supvisors_failure_strategy = SupvisorsFailureStrategies.RESYNC
    fsm_state.supvisors.mapper._core_identifiers = []
    assert fsm_state.next() == default_state
    assert fsm_state._check_core_failure() is False
    assert fsm_state._check_strict_failure()
    assert fsm_state.state_modes.degraded_mode
    fsm_state.state_modes.degraded_mode = False
    # test no transition with no USER failure, CORE failure and SHUTDOWN strategy
    fsm_state.supvisors.options.synchro_options = [SynchronizationOptions.CORE, SynchronizationOptions.USER]
    fsm_state.supvisors.options.supvisors_failure_strategy = SupvisorsFailureStrategies.SHUTDOWN
    fsm_state.supvisors.mapper._core_identifiers = ['10.0.0.1:25000']
    assert fsm_state.next() == default_state
    assert fsm_state._check_user_failure() is False
    assert fsm_state._check_core_failure()
    assert fsm_state.state_modes.degraded_mode
    # reset options for next tests
    fsm_state.supvisors.options.synchro_options = []
    fsm_state.supvisors.options.supvisors_failure_strategy = SupvisorsFailureStrategies.CONTINUE


def test_synchronized_state(supvisors_ctx):
    """ Test the SynchronizedState of the FSM. """
    state = SynchronizedState(supvisors_ctx)
    assert isinstance(state, SupvisorsBaseState)
    assert isinstance(state, OnState)
    # test all applicable to SynchronizedState
    check_synchronized_state(state)


def check_master_slave_state(fsm_state: MasterSlaveState, forced_state: SupvisorsStates = None,
                             default_state: SupvisorsStates = None):
    """ Test the transitions from any state inheriting from MasterSlaveState. """
    ref_master_identifier = fsm_state.state_modes.master_identifier

    # SynchronizedState test is applicable (includes OnState)
    check_synchronized_state(fsm_state, forced_state, default_state)

    # MasterSlaveState specific
    # prepare stability
    for sm in fsm_state.state_modes.instance_state_modes.values():
        sm.master_identifier = ref_master_identifier
        sm.instance_states = {identifier: SupvisorsInstanceStates.RUNNING
                              for identifier in fsm_state.supvisors.mapper.instances}
    unstable_sm = fsm_state.state_modes.instance_state_modes['10.0.0.5:25000']

    # stable and Master shared
    fsm_state.state_modes.evaluate_stability()
    assert fsm_state.state_modes.stable_identifiers
    assert fsm_state.state_modes.check_master()
    assert fsm_state.next() == forced_state or SupvisorsStates.OFF  # Master state in slave

    # stable and Master not shared
    # WARN: next() calls evaluate_stability
    fsm_state.state_modes.evaluate_stability()
    unstable_sm.master_identifier = '10.0.0.5:25000'
    assert not fsm_state.state_modes.check_master()
    assert fsm_state.state_modes.stable_identifiers
    assert fsm_state.next() == forced_state or SupvisorsStates.ELECTION

    # unstable and Master shared
    unstable_sm.master_identifier = ref_master_identifier
    unstable_sm.instance_states = {}
    fsm_state.state_modes.evaluate_stability()
    assert not fsm_state.state_modes.stable_identifiers
    assert fsm_state.state_modes.check_master()
    assert fsm_state.next() == forced_state or SupvisorsStates.OFF  # Master state in slave

    # unstable and no Master shared
    unstable_sm.master_identifier = '10.0.0.5:25000'
    fsm_state.state_modes.evaluate_stability()
    assert not fsm_state.state_modes.stable_identifiers
    assert not fsm_state.state_modes.check_master()
    result = fsm_state.next()
    if fsm_state.context.is_master:
        assert result == default_state
    else:
        assert result == default_state or SupvisorsStates.OFF  # No-Master state in slave


def test_master_slave_state(supvisors_ctx):
    """ Test the MasterSlaveState of the FSM. """
    state = MasterSlaveState(supvisors_ctx)
    assert isinstance(state, SupvisorsBaseState)
    assert isinstance(state, OnState)
    assert isinstance(state, SynchronizedState)
    # call empty enter / exit methods
    state._master_enter()
    state._slave_enter()
    state._master_exit()
    state._slave_exit()
    # call next methods
    state._common_next()
    assert state._master_next() is None
    assert state._slave_next() is None
    # set master
    supvisors_ctx.state_modes.master_identifier = '10.0.0.1:25000'
    assert state._slave_next() == SupvisorsStates.OFF
    supvisors_ctx.state_modes.master_identifier = ''

    # test dependency between action and master/slave action
    with patch.multiple(state, _common_next=DEFAULT,
                        _master_enter=DEFAULT, _master_next=DEFAULT, _master_exit=DEFAULT,
                        _slave_enter=DEFAULT, _slave_next=DEFAULT, _slave_exit=DEFAULT) as patches:
        # test on slave
        assert not supvisors_ctx.context.is_master

        state.enter()
        assert all(not p.called or pname == '_slave_enter' for pname, p in patches.items())
        patches['_slave_enter'].reset_mock()

        state.next()
        assert all(not p.called or pname in ['_slave_next', '_common_next']
                   for pname, p in patches.items())
        patches['_common_next'].reset_mock()
        patches['_slave_next'].reset_mock()

        state.exit()
        assert all(not p.called or pname == '_slave_exit' for pname, p in patches.items())
        patches['_slave_exit'].reset_mock()

        # test on master
        supvisors_ctx.state_modes.master_identifier = state.local_identifier
        assert supvisors_ctx.context.is_master

        state.enter()
        assert all(not p.called or pname == '_master_enter' for pname, p in patches.items())
        patches['_master_enter'].reset_mock()

        state.next()
        assert all(not p.called or pname in ['_master_next', '_common_next']
                   for pname, p in patches.items())
        patches['_common_next'].reset_mock()
        patches['_master_next'].reset_mock()

        state.exit()
        assert all(not p.called or pname == '_master_exit' for pname, p in patches.items())
        patches['_master_exit'].reset_mock()

    # test all applicable to MasterSlaveState
    # test Master
    supvisors_ctx.state_modes.master_identifier = supvisors_ctx.mapper.local_identifier
    assert state.context.is_master
    check_master_slave_state(state)
    # test Slave
    supvisors_ctx.state_modes.master_identifier = '10.0.0.1:25000'
    assert not state.context.is_master
    check_master_slave_state(state, default_state=SupvisorsStates.OFF)


def check_working_state(state: WorkingState, forced_state: SupvisorsStates = None,
                        default_state: SupvisorsStates = None):
    """ Test the transitions from any state inheriting from WorkingState. """
    # MasterSlaveState test is applicable (includes OnState and SynchronizedState)
    check_master_slave_state(state, forced_state, default_state)

    # WorkingState specific
    status = state.context.instances['10.0.0.3:25000']
    # presence of CHECKED instances
    status._state = SupvisorsInstanceStates.CHECKED
    assert state.next() == SupvisorsStates.ELECTION  # presence of CHECKED instance
    assert status.state == SupvisorsInstanceStates.RUNNING
    # force_distribution
    state.supvisors.fsm.force_distribution = True
    assert state.next() == SupvisorsStates.ELECTION
    state.supvisors.fsm.force_distribution = False


def test_working_state(mocker, supvisors_ctx):
    """ Test the WorkingState of the FSM. """
    state = WorkingState(supvisors_ctx)
    assert isinstance(state, SupvisorsBaseState)
    assert isinstance(state, OnState)
    assert isinstance(state, SynchronizedState)
    assert isinstance(state, MasterSlaveState)

    # mock FAILED instance
    mocker.patch.object(state.context, 'publish_process_failures')
    status = state.context.instances['10.0.0.4:25000']
    proc_1 = Mock(**{'invalidate_identifier.return_value': False})
    proc_2 = Mock(**{'invalidate_identifier.return_value': True})
    mocker.patch.object(status, 'running_processes', return_value=[proc_1, proc_2])

    # Test Slave part
    supvisors_ctx.state_modes.master_identifier = '10.0.0.1:25000'
    assert not state.context.is_master

    # test all applicable to WorkingState
    check_working_state(state, default_state=SupvisorsStates.OFF)

    # lost_instances / no trigger
    supvisors_ctx.starter.reset_mock()
    supvisors_ctx.stopper.reset_mock()
    status._state = SupvisorsInstanceStates.FAILED
    assert state.next() == SupvisorsStates.OFF
    assert state.lost_instances == ['10.0.0.4:25000']
    assert supvisors_ctx.starter.on_instances_invalidation.call_args_list == [call(['10.0.0.4:25000'], {proc_2})]
    assert supvisors_ctx.stopper.on_instances_invalidation.call_args_list == [call(['10.0.0.4:25000'], {proc_2})]
    assert not supvisors_ctx.failure_handler.add_default_job.called
    assert not supvisors_ctx.failure_handler.trigger_jobs.called

    # Test Master part
    supvisors_ctx.state_modes.master_identifier = supvisors_ctx.mapper.local_identifier
    assert state.context.is_master

    # test all applicable to WorkingState
    check_working_state(state)

    # lost_instances / trigger
    supvisors_ctx.starter.reset_mock()
    supvisors_ctx.stopper.reset_mock()
    supvisors_ctx.failure_handler.add_default_job.reset_mock()
    supvisors_ctx.failure_handler.trigger_jobs.reset_mock()

    status._state = SupvisorsInstanceStates.FAILED
    assert state.next() is None
    assert state.lost_instances == ['10.0.0.4:25000']
    assert supvisors_ctx.starter.on_instances_invalidation.call_args_list == [call(['10.0.0.4:25000'], {proc_2})]
    assert supvisors_ctx.stopper.on_instances_invalidation.call_args_list == [call(['10.0.0.4:25000'], {proc_2})]
    assert supvisors_ctx.failure_handler.add_default_job.call_args_list == [call(proc_2)]
    assert supvisors_ctx.failure_handler.trigger_jobs.called


def test_ending_state(mocker, supvisors_ctx):
    """ Test the EndingState of the FSM. """
    state = EndingState(supvisors_ctx)
    assert isinstance(state, SupvisorsBaseState)
    assert isinstance(state, OnState)
    assert isinstance(state, SynchronizedState)
    assert isinstance(state, MasterSlaveState)

    # check calls to abort_jobs / stop_applications
    mocked_abort = mocker.patch.object(state, '_abort_jobs')
    supvisors_ctx.stopper.reset_mock()

    # Test Slave part
    supvisors_ctx.state_modes.master_identifier = '10.0.0.1:25000'
    assert not state.context.is_master

    state.enter()
    assert mocked_abort.called
    assert not supvisors_ctx.stopper.stop_applications.called

    # test all applicable to WorkingState
    check_master_slave_state(state, forced_state=SupvisorsStates.FINAL, default_state=SupvisorsStates.OFF)

    # Test Master part
    supvisors_ctx.state_modes.master_identifier = supvisors_ctx.mapper.local_identifier
    assert state.context.is_master

    state.enter()
    assert mocked_abort.called
    assert supvisors_ctx.stopper.stop_applications.called

    # test all applicable to WorkingState
    check_master_slave_state(state, forced_state=SupvisorsStates.FINAL)



def test_off_state(supvisors_ctx):
    """ Test the OffState state of the Supvisors FSM. """
    state = OffState(supvisors_ctx)
    assert isinstance(state, SupvisorsBaseState)
    # 1. test enter method
    assert state.context.start_date == 0.0
    state.enter()
    assert state.context.start_date > 0.0
    # 2. test next method
    # local instance RUNNING by default
    assert state.next() == SupvisorsStates.SYNCHRONIZATION
    # set local instance not ready
    state.context.local_status._state = SupvisorsInstanceStates.CHECKING
    assert state.next() == SupvisorsStates.OFF
    # increase uptime for code coverage
    state.context.start_date -= SupvisorsOptions.SYNCHRO_TIMEOUT_MIN * 2
    assert state.next() == SupvisorsStates.OFF


@pytest.fixture
def sync_state(supvisors_ctx) -> SynchronizationState:
    """ Create a Synchronization state. """
    return SynchronizationState(supvisors_ctx)


def test_synchronization_state_enter(supvisors_ctx, sync_state):
    """ Test the SynchronizationState of the Supvisors FSM / enter method. """
    assert isinstance(sync_state, SupvisorsBaseState)
    assert isinstance(sync_state, OnState)
    # test that jobs are aborted
    sync_state.enter()
    assert supvisors_ctx.failure_handler.abort.called
    assert supvisors_ctx.starter.abort.called
    assert supvisors_ctx.stopper.abort.called


def test_synchronization_state_check_end_sync_strict(supvisors, sync_state):
    """ Test the SynchronizationState of the Supvisors FSM / _check_end_sync_strict method. """
    supvisors.mapper.initial_identifiers = ['10.0.0.1:25000', '10.0.0.2:25000']
    assert sync_state.context.instances['10.0.0.1:25000']._state == SupvisorsInstanceStates.STOPPED
    assert sync_state.context.instances['10.0.0.2:25000']._state == SupvisorsInstanceStates.RUNNING
    # test with option STRICT not set
    supvisors.options.synchro_options = []
    assert sync_state._check_end_sync_strict() is None
    # test with option STRICT set
    supvisors.options.synchro_options = [SynchronizationOptions.STRICT]
    # test when there are still UNKNOWN Supvisors instances
    assert sync_state._check_end_sync_strict() is False
    # test when all initial instances are RUNNING, even there are still unknown states
    sync_state.context.instances['10.0.0.1:25000']._state = SupvisorsInstanceStates.RUNNING
    assert sync_state._check_end_sync_strict()


def test_synchronization_state_check_end_sync_list(supvisors, sync_state):
    """ Test the SynchronizationState state of the Supvisors FSM / _check_end_sync_list method. """
    # test with option LIST not set
    supvisors.options.synchro_options = []
    assert sync_state._check_end_sync_list() is None
    # test with option LIST set
    supvisors.options.synchro_options = [SynchronizationOptions.LIST]
    # test when there are still non-RUNNING Supvisors instances
    sync_state.context.instances['10.0.0.1:25000']._state = SupvisorsInstanceStates.RUNNING
    assert sync_state._check_end_sync_list() is False
    sync_state.context.instances[f'{socket.getfqdn()}:15000']._state = SupvisorsInstanceStates.RUNNING
    sync_state.context.instances['10.0.0.3:25000']._state = SupvisorsInstanceStates.RUNNING
    assert not sync_state._check_end_sync_list()
    # test when all Supvisors instances are RUNNING
    for instance in sync_state.context.instances.values():
        instance._state = SupvisorsInstanceStates.RUNNING
    assert sync_state._check_end_sync_list()


def test_synchronization_state_check_end_sync_timeout(supvisors, sync_state):
    """ Test the SynchronizationState state of the Supvisors FSM / _check_end_sync_timeout method. """
    # test with option TIMEOUT not set
    supvisors.options.synchro_options = []
    supvisors.options.synchro_timeout = 60
    assert sync_state._check_end_sync_timeout(80) is None
    # test with option TIMEOUT set
    supvisors.options.synchro_options = [SynchronizationOptions.TIMEOUT]
    # test when the timeout is not reached
    assert sync_state._check_end_sync_timeout(59.9) is False
    # test when there are no more unknown and transitory (UNKNOWN, ISOLATING, CHECKING) Supvisors instances
    assert sync_state._check_end_sync_timeout(60.1)


def test_synchronization_state_check_end_sync_core(supvisors, sync_state):
    """ Test the SynchronizationState state of the Supvisors FSM / _check_end_sync_core method. """
    # test with option CORE not set
    supvisors.options.synchro_options = []
    assert sync_state._check_end_sync_core(80) is None
    # test with option CORE set
    supvisors.options.synchro_options = [SynchronizationOptions.CORE]
    # test when with no core instances
    assert sync_state._check_end_sync_core(SupvisorsOptions.SYNCHRO_TIMEOUT_MIN - 1) is False
    assert sync_state._check_end_sync_core(SupvisorsOptions.SYNCHRO_TIMEOUT_MIN + 1)
    # test with NOT all core instances running
    supvisors.mapper._core_identifiers = ['10.0.0.1:25000', '10.0.0.2:25000']
    assert sync_state._check_end_sync_core(SupvisorsOptions.SYNCHRO_TIMEOUT_MIN - 1) is False
    assert sync_state._check_end_sync_core(SupvisorsOptions.SYNCHRO_TIMEOUT_MIN + 1) is False
    # test with all core instances running / unstability
    supvisors.mapper._core_identifiers = ['10.0.0.2:25000']
    assert sync_state._check_end_sync_core(SupvisorsOptions.SYNCHRO_TIMEOUT_MIN - 1) is False
    assert sync_state._check_end_sync_core(SupvisorsOptions.SYNCHRO_TIMEOUT_MIN + 1) is False
    # test with all core instances running / stability
    supvisors.state_modes.stable_identifiers = {identifier for identifier in supvisors.mapper.instances}
    supvisors.state_modes.local_state_modes.instance_states['10.0.0.2:25000'] = SupvisorsInstanceStates.RUNNING
    assert sync_state._check_end_sync_core(SupvisorsOptions.SYNCHRO_TIMEOUT_MIN - 1) is False
    assert sync_state._check_end_sync_core(SupvisorsOptions.SYNCHRO_TIMEOUT_MIN + 1)


def test_synchronization_state_check_end_sync_user(supvisors, sync_state):
    """ Test the SynchronizationState state of the Supvisors FSM / _check_end_sync_user method. """
    # test with option USER not set
    supvisors.options.synchro_options = []
    assert sync_state._check_end_sync_user() is None
    # test with option USER set
    supvisors.options.synchro_options = [SynchronizationOptions.USER]
    # test with no Master
    assert sync_state._check_end_sync_user() is False
    # test with NOT running Master
    supvisors.state_modes.master_identifier = '10.0.0.1:25000'
    assert sync_state._check_end_sync_user() is False
    # test with running Master
    supvisors.state_modes.master_identifier = '10.0.0.2:25000'
    assert sync_state._check_end_sync_user()


def test_synchronization_state_next(mocker, supvisors, sync_state):
    """ Test the SynchronizationState state of the Supvisors FSM / next method. """
    mock_list = ['_check_end_sync_strict', '_check_end_sync_list', '_check_end_sync_timeout',
                 '_check_end_sync_core', '_check_end_sync_user']
    patches = {mock: mocker.patch.object(sync_state, mock, return_value=False)
               for mock in mock_list}
    # OnState test is applicable
    check_on_state(sync_state, default_state=SupvisorsStates.SYNCHRONIZATION)
    # activate any condition / degraded mode
    for mock in mock_list:
        for pname, pvalue in patches.items():
            pvalue.return_value = mock == pname
        assert sync_state.next() == SupvisorsStates.ELECTION
        assert sync_state.state_modes.degraded_mode
    # activate any condition / no degraded mode
    for mock in mock_list:
        for pname, pvalue in patches.items():
            pvalue.return_value = True if mock == pname else None
        assert sync_state.next() == SupvisorsStates.ELECTION
        assert sync_state.state_modes.degraded_mode == False
    # activate all conditions
    for pname, pvalue in patches.items():
        pvalue.return_value = True
    assert sync_state.next() == SupvisorsStates.ELECTION
    assert sync_state.state_modes.degraded_mode == False


def test_election_state_next(mocker, supvisors_ctx):
    """ Test the ElectionState state of the Supvisors FSM / next method. """
    state = ElectionState(supvisors_ctx)
    assert isinstance(state, SupvisorsBaseState)
    assert isinstance(state, OnState)
    assert isinstance(state, SynchronizedState)
    # test that jobs are aborted on enter
    mocked_abort = mocker.patch.object(state, '_abort_jobs')
    state.enter()
    assert mocked_abort.called

    # SynchronizedState test is applicable
    check_synchronized_state(state, default_state=SupvisorsStates.ELECTION)

    # ElectionState specific
    # prepare stability
    for sm in state.state_modes.instance_state_modes.values():
        sm.instance_states = {identifier: SupvisorsInstanceStates.RUNNING
                              for identifier in supvisors_ctx.mapper.instances}

    # unstable context already tested, so set stability
    state.state_modes.evaluate_stability()
    assert state.state_modes.stable_identifiers
    assert not state.state_modes.check_master()
    assert state.state_modes.master_identifier == ''

    # call to next sets the local Master
    assert state.next() == SupvisorsStates.ELECTION
    assert state.state_modes.master_identifier == '10.0.0.1:25000'

    # no change until acknowledged by all Supvisors instances
    assert not state.state_modes.check_master()
    assert state.next() == SupvisorsStates.ELECTION
    assert state.state_modes.master_identifier == '10.0.0.1:25000'

    # test ack
    for sm in state.state_modes.instance_state_modes.values():
        sm.master_identifier = state.state_modes.master_identifier

    assert state.state_modes.check_master()
    assert state.next() == SupvisorsStates.DISTRIBUTION


def test_distribution_state_master(supvisors_ctx):
    """ Test the DistributionState of the Supvisors FSM / Master case. """
    state = DistributionState(supvisors_ctx)
    state.state_modes.master_identifier = supvisors_ctx.mapper.local_identifier
    assert isinstance(state, SupvisorsBaseState)
    assert isinstance(state, OnState)
    assert isinstance(state, SynchronizedState)
    assert isinstance(state, MasterSlaveState)
    assert isinstance(state, WorkingState)

    # test enter
    for forced in [True, False]:
        supvisors_ctx.fsm.force_distribution = forced
        state.enter()
        assert supvisors_ctx.starter.start_applications.call_args_list == [call(forced)]
        assert not supvisors_ctx.fsm.force_distribution
        supvisors_ctx.starter.start_applications.reset_mock()

    # test no change on CHECKED instance
    checked_status = supvisors_ctx.context.instances['10.0.0.3:25000']
    checked_status._state = SupvisorsInstanceStates.CHECKED

    # MasterSlaveState test is applicable (includes OnState and SynchronizedState)
    # WorkingState is NOT applicable because it relies on inactivated _activate_instances
    supvisors_ctx.starter.in_progress.return_value = False
    check_master_slave_state(state, default_state=SupvisorsStates.OPERATION)
    assert checked_status.state == SupvisorsInstanceStates.CHECKED

    # DistributionState specific
    # stay in DISTRIBUTION while there are starting jobs locally, then go to OPERATION
    state.state_modes.master_identifier = supvisors_ctx.mapper.local_identifier
    supvisors_ctx.starter.in_progress.return_value = True
    assert state.next() == SupvisorsStates.DISTRIBUTION
    supvisors_ctx.starter.in_progress.return_value = False
    assert state.next() == SupvisorsStates.OPERATION


def test_distribution_state_slave(supvisors_ctx):
    """ Test the DistributionState of the Supvisors FSM / Slave case. """
    state = DistributionState(supvisors_ctx)
    state.state_modes.master_identifier = '10.0.0.2:25000'
    assert isinstance(state, SupvisorsBaseState)
    assert isinstance(state, OnState)
    assert isinstance(state, SynchronizedState)
    assert isinstance(state, MasterSlaveState)
    assert isinstance(state, WorkingState)

    # test enter
    for forced in [True, False]:
        supvisors_ctx.fsm.force_distribution = forced
        state.enter()
        assert not supvisors_ctx.starter.start_applications.called
        assert not supvisors_ctx.fsm.force_distribution

    # test no change on CHECKED instance
    checked_status = supvisors_ctx.context.instances['10.0.0.3:25000']
    checked_status._state = SupvisorsInstanceStates.CHECKED

    # MasterSlaveState test is applicable (includes OnState and SynchronizedState)
    # WorkingState is NOT applicable because it relies on inactivated _activate_instances
    supvisors_ctx.starter.in_progress.return_value = False
    check_master_slave_state(state, default_state=state.state_modes.master_state)
    assert checked_status.state == SupvisorsInstanceStates.CHECKED


def test_operation_state_master(mocker, supvisors_ctx):
    """ Test the OperationState of the Supvisors FSM / Master case.
    Slave is a WorkingState. """
    mocked_start = supvisors_ctx.starter.in_progress
    mocked_stop = supvisors_ctx.stopper.in_progress
    # create instance
    state = OperationState(supvisors_ctx)
    state.state_modes.master_identifier = supvisors_ctx.mapper.local_identifier
    assert isinstance(state, SupvisorsBaseState)
    assert isinstance(state, OnState)
    assert isinstance(state, SynchronizedState)
    assert isinstance(state, MasterSlaveState)
    assert isinstance(state, WorkingState)

    # WorkingState test is applicable (includes OnState, SynchronizedState and MasterSlaveState)
    mocked_start.return_value = True
    mocked_stop.return_value = True
    check_working_state(state, default_state=SupvisorsStates.OPERATION)

    # OperationState specific
    state.state_modes.master_identifier = supvisors_ctx.mapper.local_identifier
    assert not state.context.conflicting()

    # starting and/or stopping jobs: stay in OPERATION
    for mocked_start.return_value, mocked_stop.return_value in [(True, False), (False, True), (True, True)]:
        assert state.next() == SupvisorsStates.OPERATION

    # no conflict, no mark, no job: stay in OPERATION
    mocked_start.return_value = False
    mocked_stop.return_value = False
    assert state.next() == SupvisorsStates.OPERATION

    # go back to ELECTION if a new Supvisors instance is CHECKED
    checked_status = supvisors_ctx.context.instances['10.0.0.3:25000']
    checked_status._state = SupvisorsInstanceStates.CHECKED
    assert state.next() == SupvisorsStates.ELECTION

    # go to CONCILIATION if conflicts arise
    mocker.patch.object(supvisors_ctx.context, 'conflicting', return_value=True)
    assert state.next() == SupvisorsStates.CONCILIATION


def test_conciliation_state_master(mocker, supvisors_ctx):
    """ Test the ConciliationState of the Supvisors FSM / Master case.
    Slave is a WorkingState. """
    mocked_conciliate = mocker.patch('supvisors.statemachine.conciliate_conflicts')
    mocker.patch.object(supvisors_ctx.context, 'conflicts', return_value=[1, 2, 3])
    mocker.patch.object(supvisors_ctx.context, 'conflicting', return_value=True)
    mocked_start = supvisors_ctx.starter.in_progress
    mocked_stop = supvisors_ctx.stopper.in_progress
    # create instance
    state = ConciliationState(supvisors_ctx)
    state.state_modes.master_identifier = supvisors_ctx.mapper.local_identifier
    assert isinstance(state, SupvisorsBaseState)
    assert isinstance(state, OnState)
    assert isinstance(state, SynchronizedState)
    assert isinstance(state, MasterSlaveState)
    assert isinstance(state, WorkingState)

    # WorkingState test is applicable (includes OnState, SynchronizedState and MasterSlaveState)
    mocked_start.return_value = True
    mocked_stop.return_value = True
    check_working_state(state, default_state=SupvisorsStates.CONCILIATION)

    # ConciliationState specific
    state.state_modes.master_identifier = supvisors_ctx.mapper.local_identifier
    mocker.resetall()

    # test enter method
    state.enter()
    assert mocked_conciliate.call_args_list == [call(supvisors_ctx, ConciliationStrategies.USER, [1, 2, 3])]
    mocked_conciliate.reset_mock()

    # starting and/or stopping jobs: stay in CONCILIATION
    for mocked_start.return_value, mocked_stop.return_value in [(True, False), (False, True), (True, True)]:
        assert state.next() == SupvisorsStates.CONCILIATION

    # consider that no starting or stopping is in progress
    mocked_start.return_value = False
    mocked_stop.return_value = False

    # if conflicts are still detected, call enter method
    assert state.next() == SupvisorsStates.CONCILIATION
    assert mocked_conciliate.call_args_list == [call(supvisors_ctx, ConciliationStrategies.USER, [1, 2, 3])]

    # transit to OPERATION if local node and master node are RUNNING and no conflict detected
    supvisors_ctx.context.conflicting.return_value = False
    assert state.next() == SupvisorsStates.OPERATION


def test_restarting_state_master(supvisors_ctx):
    """ Test the RestartingState of the Supvisors FSM / Master case. """
    mocked_stopping = supvisors_ctx.stopper.in_progress
    # create instance to test
    state = RestartingState(supvisors_ctx)
    state.state_modes.master_identifier = supvisors_ctx.mapper.local_identifier
    assert isinstance(state, SupvisorsBaseState)
    assert isinstance(state, OnState)
    assert isinstance(state, SynchronizedState)
    assert isinstance(state, MasterSlaveState)
    assert isinstance(state, EndingState)

    # test all applicable to WorkingState
    mocked_stopping.return_value = False
    check_master_slave_state(state, forced_state=SupvisorsStates.FINAL, default_state=SupvisorsStates.FINAL)

    # RestartingState specific
    # stay in RESTARTING while stopping is in progress
    mocked_stopping.return_value = True
    assert state.next() == SupvisorsStates.RESTARTING
    mocked_stopping.return_value = False
    assert state.next() == SupvisorsStates.FINAL
    # test exit method: call Supervisor restart
    state.exit()
    assert supvisors_ctx.rpc_handler.send_restart.call_args_list == [call(state.local_identifier)]


def test_restarting_state_slave(supvisors_ctx):
    """ Test the RestartingState of the Supvisors FSM / Slave case. """
    # create instance to test
    state = RestartingState(supvisors_ctx)
    state.state_modes.master_identifier = '10.0.0.1:25000'
    assert isinstance(state, SupvisorsBaseState)
    assert isinstance(state, OnState)
    assert isinstance(state, SynchronizedState)
    assert isinstance(state, MasterSlaveState)
    assert isinstance(state, EndingState)

    # test all applicable to WorkingState
    check_master_slave_state(state, forced_state=SupvisorsStates.FINAL, default_state=SupvisorsStates.FINAL)

    # RestartingState specific
    # master_state if OFF by default
    assert state.next() == SupvisorsStates.FINAL
    # force Master FSM state to RESTARTING
    supvisors_ctx.state_modes.master_state_modes.state = SupvisorsStates.RESTARTING
    assert state.next() == SupvisorsStates.RESTARTING
    # test all other Master states
    for fsm_state in SupvisorsStates:
        supvisors_ctx.state_modes.master_state_modes.state = fsm_state
        if fsm_state != SupvisorsStates.RESTARTING:
            assert state.next() == SupvisorsStates.FINAL
    # lose Master
    state.state_modes.master_identifier = ''
    assert state.next() == SupvisorsStates.FINAL

    # test exit method: call Supervisor restart
    state.exit()
    assert supvisors_ctx.rpc_handler.send_restart.call_args_list == [call(state.local_identifier)]


def test_shutting_down_state_master(supvisors_ctx):
    """ Test the ShuttingDownState of the Supvisors FSM / Master case. """
    mocked_stopping = supvisors_ctx.stopper.in_progress
    # create instance to test
    state = ShuttingDownState(supvisors_ctx)
    state.state_modes.master_identifier = supvisors_ctx.mapper.local_identifier
    assert isinstance(state, SupvisorsBaseState)
    assert isinstance(state, OnState)
    assert isinstance(state, SynchronizedState)
    assert isinstance(state, MasterSlaveState)
    assert isinstance(state, EndingState)

    # test all applicable to WorkingState
    mocked_stopping.return_value = False
    check_master_slave_state(state, forced_state=SupvisorsStates.FINAL, default_state=SupvisorsStates.FINAL)

    # ShuttingDownState specific
    # stay in SHUTTING_DOWN while stopping is in progress
    mocked_stopping.return_value = True
    assert state.next() == SupvisorsStates.SHUTTING_DOWN
    mocked_stopping.return_value = False
    assert state.next() == SupvisorsStates.FINAL
    # test exit method: call Supervisor restart
    state.exit()
    assert supvisors_ctx.rpc_handler.send_shutdown.call_args_list == [call(state.local_identifier)]


def test_shutting_down_state_slave(supvisors_ctx):
    """ Test the ShuttingDownState of the Supvisors FSM / Slave case. """
    # create instance to test
    state = ShuttingDownState(supvisors_ctx)
    state.state_modes.master_identifier = '10.0.0.1:25000'
    assert isinstance(state, SupvisorsBaseState)
    assert isinstance(state, OnState)
    assert isinstance(state, SynchronizedState)
    assert isinstance(state, MasterSlaveState)
    assert isinstance(state, EndingState)

    # test all applicable to WorkingState
    check_master_slave_state(state, forced_state=SupvisorsStates.FINAL, default_state=SupvisorsStates.FINAL)

    # ShuttingDownState specific
    # master_state if OFF by default
    assert state.next() == SupvisorsStates.FINAL
    # force Master FSM state to SHUTTING_DOWN
    supvisors_ctx.state_modes.master_state_modes.state = SupvisorsStates.SHUTTING_DOWN
    assert state.next() == SupvisorsStates.SHUTTING_DOWN
    # test all other Master states
    for fsm_state in SupvisorsStates:
        supvisors_ctx.state_modes.master_state_modes.state = fsm_state
        if fsm_state != SupvisorsStates.SHUTTING_DOWN:
            assert state.next() == SupvisorsStates.FINAL
    # lose Master
    state.state_modes.master_identifier = ''
    assert state.next() == SupvisorsStates.FINAL

    # test exit method: call Supervisor restart
    state.exit()
    assert supvisors_ctx.rpc_handler.send_shutdown.call_args_list == [call(state.local_identifier)]


def test_final_state(supvisors_ctx):
    """ Test the Final state of the fsm. """
    state = FinalState(supvisors_ctx)
    assert isinstance(state, SupvisorsBaseState)
    # no enter / next / exit implementation. just call it without test
    state.enter()
    state.next()
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
    assert fsm.logger is supvisors.logger
    assert fsm.context is supvisors.context
    assert fsm.state_modes is supvisors.state_modes
    assert not fsm.force_distribution
    # test that the INITIALIZATION state is triggered at creation
    assert fsm.state == SupvisorsStates.OFF
    assert isinstance(fsm.instance, OffState)


def test_fsm_next(mocker, supvisors, fsm):
    """ Test the principle of the FiniteStateMachine / next method. """
    mocker_state = mocker.patch.object(fsm, 'set_state')
    fsm.next()
    assert supvisors.starter.check.called
    assert supvisors.stopper.check.called
    assert mocker_state.called


def test_set_state_slave(supvisors, fsm):
    """ Test the state transitions in a Slave FSM. """
    assert fsm.state == SupvisorsStates.OFF
    # test that any transition is accepted in Slave
    supvisors.state_modes.master_identifier = '10.0.0.1:25000'
    # no change
    fsm.set_state(None)
    assert fsm.state == SupvisorsStates.OFF
    # all proposals back to OFF because the local instance is not RUNNING
    # exception made for ending states, that will go forward to FINAL
    assert supvisors.context.local_status.state == SupvisorsInstanceStates.STOPPED
    for fsm_state in SupvisorsStates:
        if fsm_state in [SupvisorsStates.RESTARTING, SupvisorsStates.SHUTTING_DOWN, SupvisorsStates.FINAL]:
            fsm.set_state(fsm_state)
            assert fsm.state == SupvisorsStates.FINAL
        else:
            fsm.set_state(fsm_state)
            assert fsm.state == SupvisorsStates.OFF
    # set the local instance to RUNNING
    supvisors.context.local_status._state = SupvisorsInstanceStates.RUNNING
    # test that invalid transitions may be accepted
    supvisors.state_modes.state = SupvisorsStates.OFF
    assert SupvisorsStates.ELECTION not in FiniteStateMachine._Transitions[SupvisorsStates.OFF]
    fsm.set_state(SupvisorsStates.ELECTION)
    assert fsm.state == SupvisorsStates.ELECTION
    # CONCILIATION proposal back to OFF (Master state), then SYNCHRONIZATION
    assert SupvisorsStates.CONCILIATION not in FiniteStateMachine._Transitions[SupvisorsStates.ELECTION]
    fsm.set_state(SupvisorsStates.CONCILIATION)
    assert fsm.state == SupvisorsStates.SYNCHRONIZATION


def test_set_state_master(supvisors, fsm):
    """ Test the state transitions in a MAster FSM. """
    assert fsm.state == SupvisorsStates.OFF
    # test that any transition is accepted in Slave
    supvisors.state_modes.master_identifier = supvisors.mapper.local_identifier
    # no change
    fsm.set_state(None)
    assert fsm.state == SupvisorsStates.OFF
    # test that invalid transitions are not accepted
    supvisors.state_modes.state = SupvisorsStates.OFF
    assert SupvisorsStates.ELECTION not in FiniteStateMachine._Transitions[SupvisorsStates.OFF]
    fsm.set_state(SupvisorsStates.ELECTION)
    assert fsm.state == SupvisorsStates.OFF
    # TODO: to be continued


def test_on_timer_event(mocker, supvisors, fsm):
    """ Test the actions triggered in state machine upon reception of a timer event. """
    mocked_timer = mocker.patch.object(supvisors.context, 'on_timer_event')
    mocked_next = mocker.patch.object(supvisors.fsm, 'next')
    event = {'counter': 1234}
    fsm.on_timer_event(event)
    assert mocked_timer.call_args_list == [call(event)]
    assert mocked_next.called


def test_on_tick_event(mocker, supvisors, fsm):
    """ Test the actions triggered in state machine upon reception of a tick event. """
    mocked_evt = mocker.patch.object(supvisors.context, 'on_tick_event')
    event = {'tick': 1234, 'ip_address': '10.0.0.1', 'server_port': 65000}
    fsm.on_tick_event(supvisors.context.local_status, event)
    assert mocked_evt.call_args_list == [call(supvisors.context.local_status, event)]


def test_discovery_event(mocker, supvisors, fsm):
    """ Test the actions triggered in state machine upon reception of a discovery event. """
    mocked_evt = mocker.patch.object(supvisors.context, 'on_discovery_event')
    event = '192.168.1.1:5000', 'dummy_identifier', ['10.0.0.1', 7777]
    fsm.on_discovery_event(event)
    assert mocked_evt.call_args_list == [call('192.168.1.1:5000', 'dummy_identifier')]


def test_process_state_event_process_not_found(mocker, supvisors, fsm):
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
    fsm.on_process_state_event(supvisors.context.local_status, {'process_name': 'dummy_proc'})
    assert mocked_ctx.call_args_list == [call(supvisors.context.local_status, {'process_name': 'dummy_proc'})]
    assert not mocked_start_evt.called
    assert not mocked_stop_evt.called
    assert not mocked_restart.called
    assert not mocked_shutdown.called
    assert not mocked_add.called


def test_process_state_event_not_master(mocker, supvisors, fsm):
    """ Test the actions triggered in state machine upon reception of a process state event.
    Test case: process is found but local Supvisors instance is not master. """
    # prepare context
    process = Mock()
    # get patches
    mocked_restart = mocker.patch.object(fsm, 'on_restart')
    mocked_shutdown = mocker.patch.object(fsm, 'on_shutdown')
    mocked_ctx = mocker.patch.object(supvisors.context, 'on_process_state_event', return_value=process)
    mocked_start_evt = supvisors.starter.on_event
    mocked_stop_evt = supvisors.stopper.on_event
    mocked_add = supvisors.failure_handler.add_default_job
    # when process is found but local Supvisors instance is not master, only starter and stopper are called
    event = {'process_name': 'dummy_proc'}
    status = supvisors.context.instances['10.0.0.1:25000']
    fsm.on_process_state_event(status, event)
    assert mocked_ctx.call_args_list == [call(status, event)]
    assert mocked_start_evt.call_args_list == [call(process, '10.0.0.1:25000')]
    assert mocked_stop_evt.call_args_list == [call(process, '10.0.0.1:25000')]
    assert not mocked_restart.called
    assert not mocked_shutdown.called
    assert not mocked_add.called


def test_process_state_event_no_crash(mocker, supvisors, fsm):
    """ Test the actions triggered in state machine upon reception of a process state event.
    Test case: process is found - no crash, local Supvisors instance is master. """
    # prepare context
    fsm.state_modes.master_identifier = fsm.context.local_identifier
    process = Mock(**{'crashed.return_value': False})
    event = {'process_name': 'dummy_proc'}
    # get patches
    mocked_restart = mocker.patch.object(fsm, 'on_restart')
    mocked_shutdown = mocker.patch.object(fsm, 'on_shutdown')
    mocked_ctx = mocker.patch.object(supvisors.context, 'on_process_state_event', return_value=process)
    mocked_start_evt = supvisors.starter.on_event
    mocked_stop_evt = supvisors.stopper.on_event
    mocked_add = supvisors.failure_handler.add_default_job
    # test when process has not crashed
    status = supvisors.context.instances['10.0.0.1:25000']
    for process.rules.running_failure_strategy in RunningFailureStrategies:
        fsm.on_process_state_event(status, event)
        assert mocked_ctx.call_args_list == [call(status, event)]
        assert mocked_start_evt.call_args_list == [call(process, '10.0.0.1:25000')]
        assert mocked_stop_evt.call_args_list == [call(process, '10.0.0.1:25000')]
        assert not mocked_restart.called
        assert not mocked_shutdown.called
        assert not mocked_add.called
        # reset mocks
        mocked_ctx.reset_mock()
        mocked_start_evt.reset_mock()
        mocked_stop_evt.reset_mock()
        mocked_add.reset_mock()


def test_process_state_event_crash_restart(mocker, supvisors, fsm):
    """ Test the actions triggered in state machine upon reception of a process state event.
    Test case: process is found, event is a crash, rule is RESTART, local Supvisors instance is master. """
    # prepare context
    fsm.state_modes.master_identifier = fsm.context.local_identifier
    process = Mock(**{'crashed.return_value': True})
    event = {'process_name': 'dummy_proc'}
    # get patches
    mocked_restart = mocker.patch.object(fsm, 'on_restart')
    mocked_shutdown = mocker.patch.object(fsm, 'on_shutdown')
    mocked_ctx = mocker.patch.object(supvisors.context, 'on_process_state_event', return_value=process)
    mocked_start_evt = supvisors.starter.on_event
    mocked_stop_evt = supvisors.stopper.on_event
    mocked_add = supvisors.failure_handler.add_default_job
    # test when process has crashed and rule is RESTART
    process.rules.running_failure_strategy = RunningFailureStrategies.RESTART
    status = supvisors.context.instances['10.0.0.1:25000']
    fsm.on_process_state_event(status, event)
    assert mocked_ctx.call_args_list == [call(status, event)]
    assert mocked_start_evt.call_args_list == [call(process, '10.0.0.1:25000')]
    assert mocked_stop_evt.call_args_list == [call(process, '10.0.0.1:25000')]
    assert mocked_restart.called
    assert not mocked_shutdown.called
    assert not mocked_add.called


def test_process_state_event_crash_shutdown(mocker, supvisors, fsm):
    """ Test the actions triggered in state machine upon reception of a process state event.
    Test case: process is found, event is a crash, rule is SHUTDOWN, local Supvisors instance is master. """
    # prepare context
    fsm.state_modes.master_identifier = fsm.context.local_identifier
    process = Mock(**{'crashed.return_value': True})
    event = {'process_name': 'dummy_proc'}
    # get patches
    mocked_restart = mocker.patch.object(fsm, 'on_restart')
    mocked_shutdown = mocker.patch.object(fsm, 'on_shutdown')
    mocked_ctx = mocker.patch.object(supvisors.context, 'on_process_state_event', return_value=process)
    mocked_start_evt = supvisors.starter.on_event
    mocked_stop_evt = supvisors.stopper.on_event
    mocked_add = supvisors.failure_handler.add_default_job
    # test when process has crashed and rule is shutdown
    process.rules.running_failure_strategy = RunningFailureStrategies.SHUTDOWN
    status = supvisors.context.instances['10.0.0.1:25000']
    fsm.on_process_state_event(status, event)
    assert mocked_ctx.call_args_list == [call(status, event)]
    assert mocked_start_evt.call_args_list == [call(process, '10.0.0.1:25000')]
    assert mocked_stop_evt.call_args_list == [call(process, '10.0.0.1:25000')]
    assert not mocked_restart.called
    assert mocked_shutdown.called
    assert not mocked_add.called


def test_process_state_event_crash_continue(mocker, supvisors, fsm):
    """ Test the actions triggered in state machine upon reception of a process state event.
    Test case: process is found, event is a crash, rule is CONTINUE, local Supvisors instance is master. """
    # prepare context
    fsm.state_modes.master_identifier = fsm.context.local_identifier
    process = Mock(**{'crashed.return_value': True})
    event = {'process_name': 'dummy_proc'}
    # get patches
    mocked_restart = mocker.patch.object(fsm, 'on_restart')
    mocked_shutdown = mocker.patch.object(fsm, 'on_shutdown')
    mocked_ctx = mocker.patch.object(supvisors.context, 'on_process_state_event', return_value=process)
    mocked_start_evt = supvisors.starter.on_event
    mocked_stop_evt = supvisors.stopper.on_event
    mocked_add = supvisors.failure_handler.add_default_job
    # test with running_failure_strategy set to CONTINUE so job is not added to failure handler
    process.rules.running_failure_strategy = RunningFailureStrategies.CONTINUE
    status = supvisors.context.instances['10.0.0.1:25000']
    fsm.on_process_state_event(status, event)
    assert mocked_ctx.call_args_list == [call(status, event)]
    assert mocked_start_evt.call_args_list == [call(process, '10.0.0.1:25000')]
    assert mocked_stop_evt.call_args_list == [call(process, '10.0.0.1:25000')]
    assert not mocked_restart.called
    assert not mocked_shutdown.called
    assert mocked_add.call_args_list == []


def test_process_state_event_crash_restart_process(mocker, supvisors, fsm):
    """ Test the actions triggered in state machine upon reception of a process state event.
    Test case: process is found, event is a crash, rule is RESTART_PROCESS, local Supvisors instance is master. """
    # prepare context
    fsm.state_modes.master_identifier = fsm.context.local_identifier
    process = Mock(**{'crashed.return_value': True})
    event = {'process_name': 'dummy_proc'}
    # get patches
    mocked_restart = mocker.patch.object(fsm, 'on_restart')
    mocked_shutdown = mocker.patch.object(fsm, 'on_shutdown')
    mocked_ctx = mocker.patch.object(supvisors.context, 'on_process_state_event', return_value=process)
    mocked_start_evt = supvisors.starter.on_event
    mocked_stop_evt = supvisors.stopper.on_event
    mocked_add = supvisors.failure_handler.add_default_job
    # test with running_failure_strategy set to CONTINUE / RESTART_PROCESS so job is not added to failure handler
    process.rules.running_failure_strategy = RunningFailureStrategies.RESTART_PROCESS
    status = supvisors.context.instances['10.0.0.1:25000']
    fsm.on_process_state_event(status, event)
    assert mocked_ctx.call_args_list == [call(status, event)]
    assert mocked_start_evt.call_args_list == [call(process, '10.0.0.1:25000')]
    assert mocked_stop_evt.call_args_list == [call(process, '10.0.0.1:25000')]
    assert not mocked_restart.called
    assert not mocked_shutdown.called
    assert mocked_add.call_args_list == []


def test_process_state_event_crash_stop_application(mocker, supvisors, fsm):
    """ Test the actions triggered in state machine upon reception of a process state event.
    Test case: process is found, event is a crash (not forced), rule is STOP_APPLICATION, local Supvisors instance
    is master. """
    # prepare context
    fsm.state_modes.master_identifier = fsm.context.local_identifier
    process = Mock(forced_state=None, **{'crashed.return_value': True})
    event = {'process_name': 'dummy_proc'}
    # get patches
    mocked_restart = mocker.patch.object(fsm, 'on_restart')
    mocked_shutdown = mocker.patch.object(fsm, 'on_shutdown')
    mocked_ctx = mocker.patch.object(fsm.supvisors.context, 'on_process_state_event', return_value=process)
    mocked_start_evt = supvisors.starter.on_event
    mocked_stop_evt = supvisors.stopper.on_event
    mocked_add = supvisors.failure_handler.add_default_job
    # job is added to failure handler
    process.rules.running_failure_strategy = RunningFailureStrategies.STOP_APPLICATION
    status = supvisors.context.instances['10.0.0.1:25000']
    fsm.on_process_state_event(status, event)
    assert mocked_ctx.call_args_list == [call(status, event)]
    assert mocked_start_evt.call_args_list == [call(process, '10.0.0.1:25000')]
    assert mocked_stop_evt.call_args_list == [call(process, '10.0.0.1:25000')]
    assert not mocked_restart.called
    assert not mocked_shutdown.called
    assert mocked_add.call_args_list == [call(process)]


def test_process_state_event_crash_restart_application(mocker, supvisors, fsm):
    """ Test the actions triggered in state machine upon reception of a process state event.
    Test case: process is found, event is a crash (not forced), rule is RESTART_APPLICATION, local Supvisors instance
    is master. """
    # prepare context
    fsm.state_modes.master_identifier = fsm.context.local_identifier
    process = Mock(forced_state=None, **{'crashed.return_value': True})
    event = {'process_name': 'dummy_proc'}
    # get patches
    mocked_restart = mocker.patch.object(fsm, 'on_restart')
    mocked_shutdown = mocker.patch.object(fsm, 'on_shutdown')
    mocked_ctx = mocker.patch.object(supvisors.context, 'on_process_state_event', return_value=process)
    mocked_start_evt = supvisors.starter.on_event
    mocked_stop_evt = supvisors.stopper.on_event
    mocked_add = supvisors.failure_handler.add_default_job
    # job is added to failure handler
    process.rules.running_failure_strategy = RunningFailureStrategies.RESTART_APPLICATION
    status = supvisors.context.instances['10.0.0.1:25000']
    fsm.on_process_state_event(status, event)
    assert mocked_ctx.call_args_list == [call(status, event)]
    assert mocked_start_evt.call_args_list == [call(process, '10.0.0.1:25000')]
    assert mocked_stop_evt.call_args_list == [call(process, '10.0.0.1:25000')]
    assert not mocked_restart.called
    assert not mocked_shutdown.called
    assert mocked_add.call_args_list == [call(process)]


def test_process_state_event_forced_crash(mocker, supvisors, fsm):
    """ Test the actions triggered in state machine upon reception of a process state event. """
    # prepare context
    fsm.state_modes.master_identifier = fsm.context.local_identifier
    process = Mock(forced_state=ProcessStates.FATAL, **{'crashed.return_value': True})
    event = {'process_name': 'dummy_proc'}
    # get patches
    mocked_restart = mocker.patch.object(fsm, 'on_restart')
    mocked_shutdown = mocker.patch.object(fsm, 'on_shutdown')
    mocked_ctx = mocker.patch.object(supvisors.context, 'on_process_state_event', return_value=process)
    mocked_start_evt = supvisors.starter.on_event
    mocked_stop_evt = supvisors.stopper.on_event
    mocked_add = supvisors.failure_handler.add_default_job
    # job is added to failure handler only if process crash is 'real' (not forced)
    status = supvisors.context.instances['10.0.0.1:25000']
    for process.rules.running_failure_strategy in [RunningFailureStrategies.RESTART_APPLICATION,
                                                   RunningFailureStrategies.STOP_APPLICATION]:
        fsm.on_process_state_event(status, event)
        assert mocked_ctx.call_args_list == [call(status, event)]
        assert mocked_start_evt.call_args_list == [call(process, '10.0.0.1:25000')]
        assert mocked_stop_evt.call_args_list == [call(process, '10.0.0.1:25000')]
        assert not mocked_restart.called
        assert not mocked_shutdown.called
        assert not mocked_add.called
        mocker.resetall()
        mocked_start_evt.reset_mock()
        mocked_stop_evt.reset_mock()


def test_on_process_added_event(mocker, supvisors, fsm):
    """ Test the actions triggered in state machine upon reception of a process added event. """
    mocked_load = mocker.patch.object(fsm.context, 'load_processes')
    status = supvisors.context.instances['10.0.0.1:25000']
    fsm.on_process_added_event(status, {'info': 'dummy_info'})
    assert mocked_load.call_args_list == [call(status, [{'info': 'dummy_info'}])]


def test_on_process_removed_event(mocker, supvisors, fsm):
    """ Test the actions triggered in state machine upon reception of a process removed event. """
    mocked_context = mocker.patch.object(fsm.context, 'on_process_removed_event')
    status = supvisors.context.instances['10.0.0.1:25000']
    fsm.on_process_removed_event(status, {'info': 'dummy_info'})
    assert mocked_context.call_args_list == [call(status, {'info': 'dummy_info'})]


def test_on_process_disability_event(mocker, supvisors, fsm):
    """ Test the actions triggered in state machine upon reception of a process enabled event. """
    mocked_context = mocker.patch.object(fsm.context, 'on_process_disability_event')
    status = supvisors.context.instances['10.0.0.1:25000']
    fsm.on_process_disability_event(status, {'info': 'dummy_info', 'disabled': True})
    assert mocked_context.call_args_list == [call(status, {'info': 'dummy_info', 'disabled': True})]


def test_on_state_event(mocker, supvisors, fsm):
    """ Test the actions triggered in state machine upon reception of a Master state event. """
    mocked_sm = mocker.patch.object(fsm.state_modes, 'on_instance_state_event')
    mocked_next = mocker.patch.object(fsm, 'next')
    payload = {'fsm_statecode': SupvisorsStates.OPERATION,
               'degraded_mode': False,
               'discovery_mode': True,
               'master_identifier': '10.0.0.1:25000',
               'starting_jobs': False, 'stopping_jobs': False}
    status = supvisors.context.instances['10.0.0.1:25000']
    fsm.on_state_event(status, payload)
    assert mocked_sm.call_args_list == [call('10.0.0.1:25000', payload)]
    assert mocked_next.called


def test_on_all_process_info(mocker, supvisors, fsm):
    """ Test the actions triggered in state machine upon reception of a process information. """
    # inject process info and test call to context load_processes
    mocked_load = mocker.patch.object(fsm.context, 'load_processes')
    status = supvisors.context.instances['10.0.0.1:25000']
    fsm.on_all_process_info(status, [{'info': 'dummy_info'}])
    assert mocked_load.call_args_list == [call(status, [{'info': 'dummy_info'}])]


def test_on_instance_failure(mocker, supvisors, fsm):
    """ Test the actions triggered in state machine upon reception of a Supvisors instance failure. """
    mocked_fail = mocker.patch.object(fsm.context, 'on_instance_failure')
    status = supvisors.context.instances['10.0.0.1:25000']
    fsm.on_instance_failure(status)
    assert mocked_fail.call_args_list == [call(status)]


def test_on_authorization(mocker, supvisors, fsm):
    """ Test the actions triggered in state machine upon reception of an authorization event. """
    mocked_auth = mocker.patch.object(fsm.context, 'on_authorization', return_value=False)
    status = supvisors.context.instances['10.0.0.1:25000']
    fsm.on_authorization(status, True)
    assert mocked_auth.call_args == call(status, True)


def test_restart_sequence_event(supvisors, fsm):
    """ Test the actions triggered in state machine upon reception of a restart_sequence event. """
    # inject restart event and test setting of redeploy_mark
    mocked_restart = supvisors.rpc_handler.send_restart_sequence
    supvisors.state_modes.master_identifier = '10.0.0.1'
    assert not fsm.force_distribution
    # test when not master
    fsm.on_restart_sequence()
    assert not fsm.force_distribution
    assert mocked_restart.call_args_list == [call('10.0.0.1')]
    mocked_restart.reset_mock()
    # test when master
    fsm.state_modes.master_identifier = fsm.context.local_identifier
    fsm.on_restart_sequence()
    assert not mocked_restart.called
    assert fsm.force_distribution


def test_restart_event(mocker, supvisors, fsm):
    """ Test the actions triggered in state machine upon reception of a restart event. """
    # inject restart event and test call to fsm set_state RESTARTING
    mocked_fsm = mocker.patch.object(fsm, 'set_state')
    mocked_send = supvisors.rpc_handler.send_restart_all
    # test when not master and Master not set
    with pytest.raises(ValueError):
        fsm.on_restart()
    assert not mocked_fsm.called
    assert not mocked_send.called
    # test when not master and Master set
    supvisors.state_modes.master_identifier = '10.0.0.1'
    fsm.on_restart()
    assert not mocked_fsm.called
    assert mocked_send.call_args_list == [call('10.0.0.1')]
    mocked_send.reset_mock()
    # test when master
    fsm.state_modes.master_identifier = fsm.context.local_identifier
    fsm.on_restart()
    assert not mocked_send.called
    assert mocked_fsm.call_args_list == [call(SupvisorsStates.RESTARTING)]


def test_shutdown_event(mocker, supvisors, fsm):
    """ Test the actions triggered in state machine upon reception of a shutdown event. """
    # inject shutdown event and test call to fsm set_state SHUTTING_DOWN
    mocked_fsm = mocker.patch.object(fsm, 'set_state')
    mocked_send = supvisors.rpc_handler.send_shutdown_all
    # test when not master and Master not set
    with pytest.raises(ValueError):
        fsm.on_shutdown()
    assert not mocked_fsm.called
    assert not mocked_send.called
    # test when not master and Master set
    supvisors.state_modes.master_identifier = '10.0.0.1'
    fsm.on_shutdown()
    assert not mocked_fsm.called
    assert mocked_send.call_args_list == [call('10.0.0.1')]
    mocked_send.reset_mock()
    # test when master
    fsm.state_modes.master_identifier = fsm.context.local_identifier
    fsm.on_shutdown()
    assert not mocked_send.called
    assert mocked_fsm.call_args_list == [call(SupvisorsStates.SHUTTING_DOWN)]


def test_on_end_sync(mocker, fsm):
    """ Test the actions triggered in state machine upon request of end_synchro. """
    mocked_next = mocker.patch.object(fsm, 'next')
    mocked_elect = mocker.patch.object(fsm.state_modes, 'select_master')
    # test with empty parameter
    assert not fsm.state_modes.master_identifier
    fsm.on_end_sync('')
    assert mocked_elect.called
    assert mocked_next.called
    # election is mocked so master_identifier remains empty
    assert not fsm.state_modes.master_identifier
    mocker.resetall()
    # test with master parameter
    fsm.on_end_sync('10.0.0.1')
    assert fsm.state_modes.master_identifier == '10.0.0.1'
    assert not mocked_elect.called
    assert mocked_next.called
