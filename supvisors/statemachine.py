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

import time
from typing import Any, Dict, Optional, Set, Tuple, Callable

from supervisor.loggers import Logger

from .context import Context
from .instancestatus import SupvisorsInstanceStatus
from .options import SupvisorsOptions
from .process import ProcessStatus
from .statemodes import SupvisorsStateModes
from .strategy import conciliate_conflicts
from .ttypes import (SupvisorsInstanceStates, SupvisorsStates, SynchronizationOptions,
                     RunningFailureStrategies, SupvisorsFailureStrategies,
                     NameList, Payload, PayloadList)


# FSM base states
class _SupvisorsBaseState:
    """ Base class for a state with simple entry / next / exit actions. """

    def __init__(self, supvisors: Any) -> None:
        """ Initialization of the attributes. """
        self.supvisors = supvisors
        # lost Supvisors instances
        self.lost_instances: NameList = []
        self.lost_processes: Set[ProcessStatus] = set()
        # list sync alerts to avoid periodic logs while on state
        self.sync_alerts: Dict[SynchronizationOptions, bool] = {option: False for option in SynchronizationOptions}

    @property
    def logger(self) -> Logger:
        """ Shortcut to the Supvisors logger structure.

        :return: the Supvisors logger.
        """
        return self.supvisors.logger

    @property
    def context(self) -> Context:
        """ Shortcut to the Supvisors context structure.

        :return: the Supvisors context.
        """
        return self.supvisors.context

    @property
    def state_modes(self) -> SupvisorsStateModes:
        """ Shortcut to the Supvisors state & modes structure.

        :return: the Supvisors state & modes.
        """
        return self.supvisors.state_modes

    @property
    def local_identifier(self) -> Optional[str]:
        """ Shortcut to local Supvisors instance identifier.

        :return: the identifier of the local Supvisors instance.
        """
        return self.supvisors.mapper.local_identifier

    # FSM actions
    def enter(self) -> None:
        """ Actions performed when entering the state.

        May be specialized in subclasses.

        :return: None.
        """

    def next(self) -> Optional[SupvisorsStates]:
        """ Evaluate the current Supvisors status to decide if the FSM should transition.

        May be specialized in subclasses.

        :return: the next Supvisors state.
        """
        # check the new Supvisors instances and the lost ones
        # this will change the Supvisors instance state for all new/lost instances
        next_state = self._check_instances()
        if next_state:
            return next_state
        # evaluate the Supvisors stability (result is stored internally)
        self.state_modes.evaluate_stability()
        # various check on Supvisors consistence, depending on the FSM state
        next_state: Optional[SupvisorsStates] = self._check_consistence()
        if next_state:
            return next_state
        return None

    def exit(self) -> None:
        """ Actions performed when leaving the state.

        May be specialized in subclasses.

        :return: None.
        """

    def _check_consistence(self) -> Optional[SupvisorsStates]:
        """ Check that the local Supvisors instance is still RUNNING.

        This is the symptom of an internal bug.
        If this occurs, it is unlikely that Supvisors will go back to an operation state.

        :return: the suggested state if the local Supvisors instance is not active anymore.
        """
        return None

    def _check_instances(self) -> Optional[SupvisorsStates]:
        """ Check that the local Supvisors instance is still RUNNING.

        This is the symptom of an internal bug.
        If this occurs, it is unlikely that Supvisors will go back to an operation state.

        :return: the suggested state if the local Supvisors instance is not active anymore.
        """
        # acknowledge FAILED instances and store the invalidated Supvisors instances and processes
        # NOTE: it's up to the subclasses to process this information or not
        self.lost_instances, self.lost_processes = self.context.invalidate_failed()
        # acknowledge CHECKED instances
        return self._activate_instances()

    def _activate_instances(self) -> Optional[SupvisorsStates]:
        """ Allow CHECKED instances to be considered in distribution.
        By default, the list of new Supvisors instances is not used.
        """
        self.context.activate_checked()
        return None

    def _abort_jobs(self) -> None:
        """ Abort starting jobs in progress.

        :return: None.
        """
        self.supvisors.failure_handler.abort()
        self.supvisors.starter.abort()
        self.supvisors.stopper.abort()


class OffState(_SupvisorsBaseState):
    """ Entry state of the Supvisors FSM.

    No Master / slave at this stage.
    No further processing on invalidated Supvisors instances and processes.
    """

    def enter(self) -> None:
        """ Reset the Supvisors start date when entering the OFF state.

        :return: None.
        """
        self.context.start_date = time.monotonic()
        self.logger.info(f'OffState.enter: start_date={self.context.start_date}')

    def _check_consistence(self) -> Optional[SupvisorsStates]:
        """ Check that the local Supvisors instance is RUNNING.

        :return: the suggested state if the local Supvisors instance is active.
        """
        if self.context.local_status.state == SupvisorsInstanceStates.RUNNING:
            return SupvisorsStates.SYNCHRONIZATION
        # get duration from start date
        uptime: float = self.context.uptime
        # log current status
        if uptime >= SupvisorsOptions.SYNCHRO_TIMEOUT_MIN:
            self.logger.critical(f'OffState.next: local Supvisors={self.local_identifier} still'
                                 f' not RUNNING after {int(uptime)} seconds')
        else:
            self.logger.debug(f'OffState.next: local Supvisors={self.local_identifier} still'
                              f' not RUNNING after {int(uptime)} seconds')
        return SupvisorsStates.OFF


class _OnState(_SupvisorsBaseState):
    """ Base class for all states when the local Supvisors instance is operational.

    No Master / slave at this stage.
    No further processing on invalidated Supvisors instances and processes.
    """

    def _check_consistence(self) -> Optional[SupvisorsStates]:
        """ Check that the local Supvisors instance is still RUNNING.

        This is the symptom of an internal bug.
        If this occurs, it is unlikely that Supvisors will go back to an operational state.

        :return: the suggested state if the local Supvisors instance is not active anymore.
        """
        # check that the local Supvisors instance is still RUNNING
        if self.context.local_status.state != SupvisorsInstanceStates.RUNNING:
            self.logger.critical('OnState.check_consistence: the local Supvisors instance is not RUNNING')
            return SupvisorsStates.OFF
        return None

    # Check utils on synchronization options
    def _check_strict_failure(self) -> Optional[bool]:
        """ Return the running status of the expected Supvisors instances.

        More particularly, if the STRICT option is set, return False if all the Supvisors instances declared
        in the supvisors_list option are running, and True otherwise.
        Return None if the STRICT option is not set. """
        if SynchronizationOptions.STRICT in self.supvisors.options.synchro_options:
            if self.state_modes.initial_running():
                if self.sync_alerts[SynchronizationOptions.STRICT]:
                    self.sync_alerts[SynchronizationOptions.STRICT] = False
                    self.logger.warn('OnState.check_strict_failure: all expected Supvisors instances are RUNNING')
                return False
            if not self.sync_alerts[SynchronizationOptions.STRICT]:
                self.sync_alerts[SynchronizationOptions.STRICT] = True
                self.logger.warn('OnState.check_strict_failure: at least one expected Supvisors instance'
                                 ' is not RUNNING')
            return True
        return None

    def _check_list_failure(self) -> Optional[bool]:
        """ Return the running status of the known Supvisors instances.

        More particularly, if the LIST option is set, return False if all the known Supvisors instances (i.e. those
        declared in the supvisors_list option and those discovered) are running, and True otherwise.
        Return None if the LIST option is not set. """
        if SynchronizationOptions.LIST in self.supvisors.options.synchro_options:
            if self.state_modes.all_running():
                if self.sync_alerts[SynchronizationOptions.LIST]:
                    self.sync_alerts[SynchronizationOptions.LIST] = False
                    self.logger.warn('OnState.check_list_failure: all known Supvisors instances are RUNNING')
                return False
            if not self.sync_alerts[SynchronizationOptions.LIST]:
                self.sync_alerts[SynchronizationOptions.LIST] = True
                self.logger.warn('OnState.check_list_failure: at least one known Supvisors instance is not RUNNING')
            return True
        return None

    def _check_core_failure(self) -> Optional[bool]:
        """ Return the running status of the core Supvisors instances.

        More particularly, if the CORE option is set, return False if all the core Supvisors instances are running,
        and True otherwise.
        Return None if the CORE option is not set.

        NOTE: the CORE option is unset at startup if core_identifiers is not set or empty, so it is considered
              as a failure here (not meant to happen anyway).
        """
        if SynchronizationOptions.CORE in self.supvisors.options.synchro_options:
            if self.state_modes.core_instances_running():
                if self.sync_alerts[SynchronizationOptions.CORE]:
                    self.sync_alerts[SynchronizationOptions.CORE] = False
                    self.logger.info('OnState.check_core_failure: all core Supvisors instances are RUNNING')
                return False
            if not self.sync_alerts[SynchronizationOptions.CORE]:
                self.sync_alerts[SynchronizationOptions.CORE] = True
                self.logger.warn('OnState.check_core_failure: at least one core Supvisors instance is not RUNNING')
            return True
        return None

    def _check_user_failure(self) -> Optional[bool]:
        """ Return the running status of the active Supvisors instances.

        More particularly, if the USER option is set, return False if all the active Supvisors instances are running,
        and True otherwise.
        Return None if the USER option is not set. """
        if SynchronizationOptions.USER in self.supvisors.options.synchro_options:
            if self.lost_instances:
                if not self.sync_alerts[SynchronizationOptions.USER]:
                    self.sync_alerts[SynchronizationOptions.USER] = True
                    self.logger.warn('OnState.check_user: at least one Supvisors instance FAILED')
                return True
            if self.sync_alerts[SynchronizationOptions.USER]:
                self.sync_alerts[SynchronizationOptions.USER] = False
                self.logger.info('OnState.check_user: all Supvisors instances are RUNNING')
            return False
        return None


class SynchronizationState(_OnState):
    """ In the SYNCHRONIZATION state, Supvisors synchronizes all known Supvisors instances.

    The Supvisors local instance must be RUNNING.

    No Master / slave at this stage.
    No further processing on lost Supvisors instances and processes.
    """

    def enter(self) -> None:
        """ When entering the SYNCHRONIZATION state, abort all existing jobs and reset the start date.

        :return: None.
        """
        self._abort_jobs()

    def _check_end_sync_strict(self) -> Optional[bool]:
        """ End of sync phase if the STRICT option is set, and all the Supvisors instances declared in the Supervisor
        configuration file are RUNNING.

        NOTE: If the condition is reached, the ELECTION state will eventually be reached with discovered Supvisors
              instances still STOPPED.

        :return: True if all expected Supvisors instances are RUNNING with the STRICT option set.
        """
        failure = self._check_strict_failure()
        if failure is False:
            return True
        return False if failure else None

    def _check_end_sync_list(self) -> Optional[bool]:
        """ End of sync phase if the LIST option is set, and all the Supvisors instances declared in the Supervisor
        configuration file are RUNNING.

        :return: True if all known Supvisors instances are RUNNING with the LIST option set.
        """
        failure = self._check_list_failure()
        if failure is False:
            return True
        return False if failure else None

    def _check_end_sync_timeout(self, uptime: float) -> Optional[bool]:
        """ End of sync phase if the TIMEOUT option is set, and the uptime has exceeded the synchro_timeout.

        NOTE: If the condition is reached, the ELECTION state will eventually be reached with Supvisors instances
              still STOPPED.

        :return: True if synchro_timeout has passed with the TIMEOUT option set.
        """
        if SynchronizationOptions.TIMEOUT in self.supvisors.options.synchro_options:
            synchro_timeout = self.supvisors.options.synchro_timeout
            self.logger.debug(f'SynchronizationState.check_end_sync_timeout: uptime={uptime}'
                              f' synchro_timeout={synchro_timeout}')
            if uptime >= synchro_timeout:
                self.logger.info(f'SynchronizationState.check_end_sync_timeout: timeout {synchro_timeout} reached')
                return True
            return False
        return None

    def _check_end_sync_core(self, uptime: float) -> Optional[bool]:
        """ End of sync phase if the CORE option is set, and all core Supvisors instances are RUNNING.

        NOTE: If the condition is reached, the ELECTION state will eventually be reached with non-core Supvisors
              instances still STOPPED.

        NOTE: this option is NOT allowed if the core_identifiers is empty
            (which is expected in discovery mode, although not incompatible).

        :return: True if all core Supvisors instances are RUNNING with the CORE option set.
        """
        failure = self._check_core_failure()
        if failure is False:
            # all core Supvisors instances are running
            # in case of late start, a security limit of SYNCHRO_TIMEOUT_MIN is kept to give a chance
            # to other Supvisors instances and limit the number of re-distributions
            if uptime >= SupvisorsOptions.SYNCHRO_TIMEOUT_MIN:
                return True
            self.logger.info('SynchronizationState.check_end_sync_core: all core Supvisors instances are RUNNING,'
                             f' waiting ({uptime} < {SupvisorsOptions.SYNCHRO_TIMEOUT_MIN})')
            return False
        return False if failure else None

    def _check_end_sync_user(self) -> Optional[bool]:
        """ End of sync phase if the USER option is set, and the master is set.

        This is meant to be triggered using the Web UI or using the XML-RPC API.
        No time condition applies as the user is responsible.

        :return: True if a RUNNING Master exists with the USER option set.
        """
        if SynchronizationOptions.USER in self.supvisors.options.synchro_options:
            # accept any master remotely selected
            self.state_modes.accept_master()
            # the Master Supvisors instance must be seen as running
            if self.state_modes.master_identifier and self.context.master_instance.running:
                self.logger.info('SynchronizationState.check_end_sync_user: the Supvisors Master instance is RUNNING')
                return True
            return False
        return None

    def next(self) -> Optional[SupvisorsStates]:
        """ Wait for Supvisors instances to exchange data until a condition is reached to end the synchronization phase.

        No further processing on invalidated Supvisors instances and processes.

        :return: the new Supvisors state.
        """
        next_state: Optional[SupvisorsStates] = super().next()
        if next_state:
            return next_state
        # get duration from start date
        uptime: float = self.context.uptime
        # check end of sync conditions
        self.logger.trace(f'SynchronizationState.next: synchro_options={self.supvisors.options.synchro_options}')
        strict_sync = self._check_end_sync_strict()
        list_sync = self._check_end_sync_list()
        timeout_sync = self._check_end_sync_timeout(uptime)
        core_sync = self._check_end_sync_core(uptime)
        user_sync = self._check_end_sync_user()
        self.logger.debug(f'SynchronizationState.next: strict_sync={strict_sync} list_sync={list_sync}'
                          f' timeout_sync={timeout_sync} core_sync={core_sync} user_sync={user_sync}')
        # a degraded state is declared if an expected Supvisors instance is missing, although another sync condition
        # allows to transition forward
        # NOTE: degraded mode does not apply with USER option alone
        degraded_sync_list = [strict_sync, list_sync, core_sync]
        self.state_modes.degraded_mode = any(sync is False for sync in degraded_sync_list)
        # if any sync condition is reached, transition to the ELECTION state
        if strict_sync or list_sync or timeout_sync or core_sync or user_sync:
            return SupvisorsStates.ELECTION
        return SupvisorsStates.SYNCHRONIZATION

    def exit(self):
        """ Print status before exiting SYNCHRONIZATION state. """
        self.logger.info(f'SynchronizationState.exit: running_identifiers={self.context.running_identifiers()}')
        self.logger.info(f'SynchronizationState.exit: nodes={self.supvisors.mapper.nodes}')


class _SynchronizedState(_OnState):
    """ The SynchronizedState is applicable to all FSM states past the SYNCHRONIZATION state.

    It increases the level of checking instances to go back to SYNCHRONIZATION state
    when the initial conditions are not met anymore.
    """

    def _check_failure_strategy(self):
        """ Check that the initial conditions are still valid.

        WARNING: the combination of multiple synchro_options makes things a bit complicated here.
                 e.g.: applying STRICT+CORE could get Supvisors out of SYNCHRONIZATION when CORE is satisfied.
                       however, Supvisors shall NOT go back to SYNCHRONIZATION if STRICT is not satisfied and CORE is.
                 That's why TIMEOUT synchro_options invalidates any SupvisorsFailureStrategies.
                 As a general rule, the following precedence is applied: USER > CORE > STRICT > LIST.

        :return: the suggested state if an important Supvisors instance is lost.
        """
        # check SynchronizationOptions STRICT / LIST / CORE / USER conditions
        user_failure = self._check_user_failure()
        core_failure = self._check_core_failure()
        strict_failure = self._check_strict_failure()
        list_failure = self._check_list_failure()
        # a degraded state is declared if an expected Supvisors instance is missing, although another sync condition
        # allows to transition forward
        # NOTE: degraded mode does not apply with USER option alone
        degraded_failure_list = [strict_failure, list_failure, core_failure]
        self.state_modes.degraded_mode = any(sync for sync in degraded_failure_list)
        # apply some priorities in failure consideration, as explained above
        global_failure = next((failure for failure in [user_failure, core_failure, strict_failure, list_failure]
                               if failure is not None), False)
        if global_failure:
            strategy = self.supvisors.options.supvisors_failure_strategy
            if strategy == SupvisorsFailureStrategies.RESYNC:
                self.logger.info(f'SynchronizationState.exit: running_identifiers={self.context.running_identifiers()}')
                return SupvisorsStates.SYNCHRONIZATION
            # NOTE: about SHUTDOWN strategy
            #       if the Master is set, it will just drive the other Supvisors instances, as usual
            #       if the Master is lost, the next call to check_instances in SHUTTING_DOWN
            #           will return ELECTION, which will trigger the FINAL state
            if strategy == SupvisorsFailureStrategies.SHUTDOWN:
                return SupvisorsStates.SHUTTING_DOWN
            # NOTE: just let it go with SupvisorsFailureStrategies CONTINUE
        return None

    def _check_consistence(self) -> Optional[SupvisorsStates]:
        """ Check that local and Master Supvisors instances are still RUNNING.
        If their ticks are not received anymore, back to SYNCHRONIZATION state to force a synchronization phase.

        :return: the suggested state if local or Master Supvisors instance is not active anymore.
        """
        # check that the local Supvisors instance is still RUNNING
        next_state: Optional[SupvisorsStates] = super()._check_consistence()
        if next_state:
            return next_state
        # check that initial conditions are still valid
        next_state = self._check_failure_strategy()
        if next_state:
            return next_state
        return None


class ElectionState(_SynchronizedState):
    """ In the ELECTION state, a Supvisors Master instance is elected. """

    def enter(self) -> None:
        """ When entering the ELECTION state, abort all pending jobs.

        :return: None.
        """
        self._abort_jobs()

    def next(self) -> Optional[SupvisorsStates]:
        """ Stay in ELECTION state until the Supvisors context is stable and a single RUNNING Master instance
        is fully shared. """
        next_state: Optional[SupvisorsStates] = super().next()
        if next_state:
            return next_state
        # check the Supvisors stability
        if self.state_modes.is_stable():
            # all Supvisors instances see the same list of running Supvisors instances
            # check that every Supvisors instance agrees on the same Master
            if self.state_modes.check_master():
                # WARN: a non-conditioned transition to DISTRIBUTION may loop infinitely
                #       if the Master is still seen in ELECTION
                # the Master transitions to DISTRIBUTION
                if self.state_modes.is_master():
                    return SupvisorsStates.DISTRIBUTION
                # the Slave waits for the Master to transition
                if self.state_modes.master_state == SupvisorsStates.DISTRIBUTION:
                    return SupvisorsStates.DISTRIBUTION
            # re-evaluate the context to possibly get a more relevant Master
            self.state_modes.select_master()
            # NOTE: after Master local selection, wait for selection to be shared and agreed
            #       among all Supvisors instances
        else:
            self.logger.info('ElectionState.next: waiting for the Supvisors context to stabilize')
        return SupvisorsStates.ELECTION


class _MasterSlaveState(_SynchronizedState):
    """ The PostSynchronizationState is applicable to all FSM states past the ELECTION state.

    It assumes that a Supvisors Master instance is available. If it's not the case anymore, back to ELECTION.

    From this point, the Supvisors local instance can either be the Master or not (= Slave).
    Only the Supvisors Master instance drives the working states (DISTRIBUTION, OPERATION, CONCILIATION)
    and the ending states (RESTARTING, SHUTTING_DOWN, FINAL)
    """

    # Split enter action
    def enter(self) -> None:
        """ Actions performed when entering the state.

        Depending on Master/Slave status, the behaviour may be different.

        :return: None.
        """
        if self.state_modes.is_master():
            self._master_enter()
        else:
            self._slave_enter()

    def _master_enter(self) -> None:
        """ Actions performed by the Supvisors Master instance when entering the state.

        May be redefined in subclasses.

        :return: None.
        """

    def _slave_enter(self) -> None:
        """ Actions performed by a Supvisors Slave instance when entering the state.

        May be redefined in subclasses.

        :return: None.
        """

    # Split next action
    def next(self) -> Optional[SupvisorsStates]:
        """ Evaluate the current Supvisors status to decide if the FSM should transition.

        Depending on Master/Slave status, the behaviour may be different.

        :return: the next Supvisors state.
        """
        next_state: Optional[SupvisorsStates] = super().next()
        if next_state:
            return next_state
        # common behaviour
        self._common_next()
        # specific behaviour
        if self.state_modes.is_master():
            return self._master_next()
        return self._slave_next()

    def _common_next(self) -> None:
        """ Operations to be performed by Master and Slaves.

        :return: None.
        """
        # At this point, there may be a list of FAILED Supvisors instances
        self.logger.debug(f'MasterSlaveState.common_next: invalid={self.lost_instances}')
        if self.lost_instances:
            # inform Starter and Stopper because processes in failure may be removed if already in their pipes
            # NOTE: any Supvisors instance can be requested by the user to plan and drive an application start sequence
            #       only the automatic start sequence (DISTRIBUTION) is driven by the Master instance
            self.supvisors.starter.on_instances_invalidation(self.lost_instances, self.lost_processes)
            self.supvisors.stopper.on_instances_invalidation(self.lost_instances, self.lost_processes)

    def _master_next(self) -> Optional[SupvisorsStates]:
        """ Evaluate the current Supvisors status for the Supvisors Master instance to decide
        if the FSM should transition.

        Must be redefined in subclasses.

        :return: the next Supvisors state.
        """
        return None

    def _slave_next(self) -> Optional[SupvisorsStates]:
        """ A Supvisors slave instance generally follows the Master state (that may be not defined yet).

        :return: the Supvisors Master state.
        """
        return self.state_modes.master_state

    # Split exit action
    def exit(self) -> None:
        """ Actions performed when leaving the state.
        Depending on Master/Slave status, the behaviour may be different.

        :return: None.
        """
        if self.state_modes.is_master():
            self._master_exit()
        else:
            self._slave_exit()

    def _master_exit(self) -> None:
        """ Actions performed by the Supvisors Master instance when leaving the state.

        May be redefined in subclasses.

        :return: None.
        """

    def _slave_exit(self) -> None:
        """ Actions performed by a Supvisors Slave instance when leaving the state.

        May be redefined in subclasses.

        :return: None.
        """

    def _check_consistence(self) -> Optional[SupvisorsStates]:
        """ Check that the Master Supvisors instance is set, unique and is still RUNNING.

        :return: The suggested state if the Master Supvisors instance is missing.
        """
        next_state: Optional[SupvisorsStates] = super()._check_consistence()
        if next_state:
            return next_state
        # check that the unique Master Supvisors instance is still RUNNING
        # NOTE: this evaluation could be based on the stable context, but it could take a few ticks to trigger
        #       some reactivity is expected here
        if not self.state_modes.check_master(False):
            self.logger.debug('WorkingState.check_consistence: Master not checked')
            return SupvisorsStates.ELECTION
        return None


class DistributionState(_MasterSlaveState):
    """ In the DISTRIBUTION state, Supvisors starts automatically the applications having a starting model.

    Only the Supvisors Master instance drives the distribution jobs.
    """

    def _activate_instances(self) -> Optional[SupvisorsStates]:
        """ Do NOT allow CHECKED instances to be considered in distribution.

        When a start sequence is started, it is better to avoid adding new instances in the plan.
        New Supvisors instances will be activated in OPERATION state, leading to a new ELECTION / DISTRIBUTION phase.
        """
        return None

    def _master_enter(self):
        """ Trigger the automatic start and stop. """
        self.supvisors.starter.start_applications()

    def _master_next(self) -> Optional[SupvisorsStates]:
        """ Check if the starting tasks are completed.

        :return: the next Supvisors state.
        """
        # WorkingState._master_next() returns always None
        super()._master_next()
        # Master goes to OPERATION when starting is completed
        if self.supvisors.starter.in_progress():
            return SupvisorsStates.DISTRIBUTION
        return SupvisorsStates.OPERATION


class _WorkingState(_MasterSlaveState):
    """ Base class for working (OPERATION, CONCILIATION) states.

    It transitions back to ELECTION when new Supvisors instances come into Supvisors.

    It manages the impact on start/stop sequences when Supvisors instances are lost.
    The Master may re-distribute the lost processes.
    """

    def _activate_instances(self) -> Optional[SupvisorsStates]:
        """ Back to ELECTION when a new Supvisors instance is detected. """
        checked_identifiers = self.context.activate_checked()
        if checked_identifiers:
            # call enter again to trigger a new distribution
            self.logger.info('WorkingState.activate_instances: ELECTION required because of new'
                             f' Supvisors instances={checked_identifiers}')
            return SupvisorsStates.ELECTION
        return None

    def _master_next(self) -> Optional[SupvisorsStates]:
        """ A Master instance in a working state tries to re-distribute the processes that were running
        on a Supvisors instance that has been lost.

        :return: None.
        """
        # At this point, there may be a list of FAILED Supvisors instances
        if self.lost_processes:
            # the Master fixes failures if any
            for process in self.lost_processes:
                self.supvisors.failure_handler.add_default_job(process)
            # trigger remaining jobs in RunningFailureHandler
            self.supvisors.failure_handler.trigger_jobs()
        # no state decision at this stage
        return None


class OperationState(_WorkingState):
    """ In the OPERATION state, Supvisors is waiting for requests. """

    def _master_next(self) -> SupvisorsStates:
        """ Check that all Supvisors instances are still active.
        Look after possible conflicts due to multiple running instances of the same process.

        :return: The new Supvisors state.
        """
        super()._master_next()
        # check if jobs are in progress
        if self.supvisors.starter.in_progress() or self.supvisors.stopper.in_progress():
            return SupvisorsStates.OPERATION
        # check duplicated processes
        if self.context.conflicting():
            return SupvisorsStates.CONCILIATION
        return SupvisorsStates.OPERATION


class ConciliationState(_WorkingState):
    """ In the CONCILIATION state, Supvisors conciliates the conflicts.

    Only the Supvisors Master instance drives the conciliation jobs.
    """

    def _master_enter(self) -> None:
        """ When entering the CONCILIATION state, automatically conciliate the conflicts. """
        conciliate_conflicts(self.supvisors,
                             self.supvisors.options.conciliation_strategy,
                             self.context.conflicts())

    def _master_next(self) -> SupvisorsStates:
        """ Check that all Supvisors instances are still active.
        Wait for all conflicts to be conciliated.

        :return: the next Supvisors state.
        """
        # check if jobs are in progress
        if self.supvisors.starter.in_progress() or self.supvisors.stopper.in_progress():
            return SupvisorsStates.CONCILIATION
        # back to OPERATION when there is no conflict anymore
        if not self.context.conflicting():
            return SupvisorsStates.OPERATION
        # new conflicts may happen while conciliation is in progress
        # call enter again to trigger a new conciliation
        self._master_enter()
        return SupvisorsStates.CONCILIATION


class _EndingState(_MasterSlaveState):
    """ Base class for ending (RESTARTING, SHUTTING_DOWN) states. """

    def _master_enter(self) -> None:
        """ When entering an ending state, the Supvisors Master instance aborts all pending tasks
        and stops all applications.

        :return: None.
        """
        self._abort_jobs()
        self.supvisors.stopper.stop_applications()

    def _slave_enter(self) -> None:
        """ When entering an ending state, a Supvisors Slave instance aborts all pending tasks.

        :return: None.
        """
        self._abort_jobs()

    def _check_consistence(self) -> Optional[SupvisorsStates]:
        """ Force the ending process if the local or Master Supvisors instance is lost.

        :return: the suggested state if a Supvisors instance is not active anymore.
        """
        # NOTE: no process failure handling here, as everything is going to be stopped anyway
        next_state = super()._check_consistence()
        if next_state:
            # it is excluded to transition back to any state at this point
            # so just reach the FINAL state
            return SupvisorsStates.FINAL
        return None


class RestartingState(_EndingState):
    """ In the RESTARTING state, Supvisors stops all applications before triggering a restart
    of the local Supvisors instance.

    The stop sequence is driven by the Master only.
    """

    def _master_next(self) -> SupvisorsStates:
        """ The Master waits for all processes to be stopped.

        :return: the next Supvisors state.
        """
        # check if stopping jobs are in progress
        if self.supvisors.stopper.in_progress():
            return SupvisorsStates.RESTARTING
        return SupvisorsStates.FINAL

    def _slave_next(self) -> SupvisorsStates:
        """ Wait for all processes to be stopped.

        :return: the next Supvisors state.
        """
        master_state = self.state_modes.master_state
        if master_state is not None:
            # stay in RESTARTING as long as the Master does
            if master_state == SupvisorsStates.RESTARTING:
                return SupvisorsStates.RESTARTING
            # the Master is expected to transition to the FINAL state
            if master_state != SupvisorsStates.FINAL:
                self.logger.error('RestartingState.slave_next: unexpected transition from the Master'
                                  f' ({self.state_modes.master_state.name})')
        else:
            self.logger.warn('RestartingState.slave_next: Master lost')
        return SupvisorsStates.FINAL

    def exit(self):
        """ When exiting the RESTARTING state, request the local Supervisor restart.
        Same action for Master and Slaves. """
        self.supvisors.rpc_handler.send_restart(self.local_identifier)


class ShuttingDownState(_EndingState):
    """ In the SHUTTING_DOWN state, Supvisors stops all applications before triggering a shutdown
    of the local Supvisors instance.

    The stop sequence is driven by the Master only.
    """

    def _master_next(self) -> SupvisorsStates:
        """ The Master waits for all processes to be stopped.

        :return: the next Supvisors state.
        """
        # check if stopping jobs are in progress
        if self.supvisors.stopper.in_progress():
            return SupvisorsStates.SHUTTING_DOWN
        return SupvisorsStates.FINAL

    def _slave_next(self) -> SupvisorsStates:
        """ Wait for all processes to be stopped.

        :return: the next Supvisors state.
        """
        master_state = self.state_modes.master_state
        if master_state is not None:
            # stay in SHUTTING_DOWN as long as the Master does
            if master_state == SupvisorsStates.SHUTTING_DOWN:
                return SupvisorsStates.SHUTTING_DOWN
            # the Master is expected to transition to the FINAL state
            if master_state != SupvisorsStates.FINAL:
                self.logger.error('ShuttingDownState.slave_next: unexpected transition from the Master'
                                  f' ({self.state_modes.master_state.name})')
        else:
            self.logger.warn('ShuttingDownState.slave_next: Master lost')
        return SupvisorsStates.FINAL

    def exit(self):
        """ When exiting the SHUTTING_DOWN state, request the local Supervisor shutdown.
        Same action for Master and Slaves. """
        self.supvisors.rpc_handler.send_shutdown(self.local_identifier)


class FinalState(_SupvisorsBaseState):
    """ This is a final state for Master and Slaves.
    Whatever it is consecutive to a shutdown or a restart, the Supervisor 'session' will end. """


class FiniteStateMachine:
    """ This class implements a very simple behaviour of FiniteStateMachine based on a single event.
    A state is able to evaluate itself for transitions.

    Attributes are:
        - state: the current state of this state machine;
        - instance: the current state instance.
    """

    def __init__(self, supvisors: Any) -> None:
        """ Reset the state machine and the internal context.

        :param supvisors: the Supvisors global structure
        """
        self.supvisors = supvisors
        self.instance: _SupvisorsBaseState = OffState(supvisors)
        self.instance.enter()

    @property
    def logger(self) -> Logger:
        """ Return the Supvisors logger. """
        return self.supvisors.logger

    @property
    def context(self) -> Context:
        """ Return the Supvisors context structure. """
        return self.supvisors.context

    @property
    def state_modes(self) -> SupvisorsStateModes:
        """ Return the Supvisors state & modes object. """
        return self.supvisors.state_modes

    @property
    def state(self) -> SupvisorsStates:
        """ Return the Supvisors current state. """
        return self.state_modes.state

    def next(self) -> None:
        """ Send the event to the state and transitions if possible.
        The state machine re-sends the event as long as it transitions.

        :return: None.
        """
        # periodic check of start / stop jobs
        self.supvisors.starter.check()
        self.supvisors.stopper.check()
        # periodic check of failure jobs
        self.supvisors.failure_handler.trigger_jobs()
        # check state machine
        self.set_state(self.instance.next())

    def set_state(self, next_state: Optional[SupvisorsStates]) -> None:
        """ Update the current state of the state machine, and transition as much as possible.

        :param next_state: The new FSM state.
        :return: None.
        """
        # NOTE: in the event of a Slave FSM, the Master state may not be known yet, hence the test on next_state
        while next_state and next_state != self.state:
            # check that the transition is allowed
            # although a Slave Supvisors always follows the Master state, it is expected not to miss a transition
            if next_state not in self._Transitions[self.state]:
                self.logger.critical(f'FiniteStateMachine.set_state: unexpected transition from {self.state.name}'
                                     f' to {next_state.name}')
                break
            # exit the current state
            self.instance.exit()
            # assign the new Supvisors state
            self.state_modes.state = next_state
            # create the new state and enter it
            self.instance = self._StateInstances[self.state](self.supvisors)
            self.instance.enter()
            # evaluate current state
            next_state = self.instance.next()

    # Event handling methods
    def on_timer_event(self, event: Payload) -> None:
        """ Periodic task used to check if remote Supvisors instances are still active. """
        self.context.on_timer_event(event)
        self.state_modes.deferred_publish_status()
        self.next()

    def on_tick_event(self, status: SupvisorsInstanceStatus, event: Payload) -> None:
        """ This event is used to refresh the data related to the Supvisors instance.

        :param status: The Supvisors instance that sent the event.
        :param event: The tick event.
        :return: None.
        """
        self.context.on_tick_event(status, event)

    def on_discovery_event(self, event: Tuple) -> None:
        """ This event is used to add new Supvisors instances into the Supvisors system.

        No need to test if the discovery mode is enabled.
        This is managed in the internal communication layer.

        :param event: The discovery event.
        :return: None.
        """
        self.context.on_discovery_event(event[0], event[1])

    def on_identification_event(self, event: Payload) -> None:
        """ This event is used during the handshake between Supvisors instances.
        It contains the network information of the remote Supvisors instance.

        :param event: the network information of the remote Supvisors instance.
        :return: None.
        """
        self.context.on_identification_event(event)

    def on_authorization(self, status: SupvisorsInstanceStatus, event: Payload) -> None:
        """ This event is used during the handshake between Supvisors instances.

        :param status: the Supvisors instance that sent the event.
        :param event: the authorization event.
        :return: None.
        """
        self.logger.debug(f'FiniteStateMachine.on_authorization: identifier={status.usage_identifier}'
                          f' event={event}')
        self.context.on_authorization(status, event)

    def on_process_state_event(self, status: SupvisorsInstanceStatus, event: Payload) -> None:
        """ This event is used to refresh the process data related to the event sent from the Supvisors instance.
        This event also triggers the application starter and/or stopper.

        :param status: the Supvisors instance that sent the event.
        :param event: the process event.
        :return: None.
        """
        process = self.context.on_process_state_event(status, event)
        # returned process may be None if the event is linked to an unknown or an isolated instance
        if process:
            # inform starter and stopper
            self.supvisors.starter.on_event(process, status.identifier)
            self.supvisors.stopper.on_event(process, status.identifier)
            # trigger an automatic (so involving the Master only) behaviour for a running failure
            # process crash triggered only if running failure strategy related to application
            # Supvisors does not replace Supervisor in the present matter (use autorestart if necessary)
            if self.state_modes.is_master() and process.crashed():
                strategy = process.rules.running_failure_strategy
                if strategy == RunningFailureStrategies.RESTART:
                    self.on_restart()
                elif strategy == RunningFailureStrategies.SHUTDOWN:
                    self.on_shutdown()
                else:
                    stop_strategy = strategy == RunningFailureStrategies.STOP_APPLICATION
                    restart_strategy = strategy == RunningFailureStrategies.RESTART_APPLICATION
                    # to avoid infinite application restart, exclude the case where process state is forced
                    # indeed the process state forced to FATAL can only happen during a starting sequence
                    # (no instance found) so retrying is useless
                    if (stop_strategy or restart_strategy) and process.forced_state is None:
                        self.supvisors.failure_handler.add_default_job(process)
                        self.supvisors.failure_handler.trigger_jobs()

    def on_process_added_event(self, status: SupvisorsInstanceStatus, event: Payload) -> None:
        """ This event is used to fill the internal structures when processes have been added on a Supvisors instance.

        :param status: the Supvisors instance that sent the event.
        :param event: the process information.
        :return: None.
        """
        self.context.load_processes(status, [event], check_state=False)

    def on_process_removed_event(self, status: SupvisorsInstanceStatus, event: Payload) -> None:
        """ This event is used to fill the internal structures when a process has been added on a Supvisors instance.

        :param status: the Supvisors instance that sent the event.
        :param event: the process identification
        :return: None
        """
        self.context.on_process_removed_event(status, event)

    def on_process_disability_event(self, status: SupvisorsInstanceStatus, event: Payload) -> None:
        """ This event is used to fill the internal structures when a process has been enabled or disabled
        on a Supvisors instance.

        :param status: the Supvisors instance that sent the event.
        :param event: the process identification
        :return: None
        """
        self.context.on_process_disability_event(status, event)

    def on_state_event(self, status: SupvisorsInstanceStatus, event: Payload) -> None:
        """ This event is used to update the FSM state of the remote Supvisors instance.

        :param status: the Supvisors instance that sent the event.
        :param event: the state event.
        :return: None.
        """
        self.logger.debug(f'FiniteStateMachine.on_state_event: Supvisors={status.usage_identifier} sent {event}')
        self.state_modes.on_instance_state_event(status.identifier, event)
        # NOTE: any update on the Master state and modes must be considered immediately
        if status.identifier == self.state_modes.master_identifier:
            self.next()

    def on_all_process_info(self, status: SupvisorsInstanceStatus, all_info: Optional[PayloadList]) -> None:
        """ This event is used to fill the internal structures with processes available on the Supvisors instance.

        :param status: the Supvisors instance that sent the event.
        :param all_info: all the processes' information.
        :return: None.
        """
        self.context.load_processes(status, all_info)

    def on_instance_failure(self, status: SupvisorsInstanceStatus) -> None:
        """ This event is received when a Supervisor proxy raised a failure.

        :param status: the Supvisors instance that sent the event.
        :return: None.
        """
        self.context.on_instance_failure(status)

    def on_restart(self) -> None:
        """ This event is used to transition the state machine to the RESTARTING state.

        :return: None.
        """
        if self.state_modes.is_master():
            self.set_state(SupvisorsStates.RESTARTING)
        else:
            if self.state_modes.master_identifier:
                # re-route the command to Master
                self.supvisors.rpc_handler.send_restart_all(self.state_modes.master_identifier)
            else:
                message = 'no Master instance to perform the Supvisors restart request'
                self.logger.error(f'FiniteStateMachine.on_restart: {message}')
                raise RuntimeError(message)

    def on_shutdown(self) -> None:
        """ This event is used to transition the state machine to the SHUTTING_DOWN state.

        :return: None.
        """
        if self.state_modes.is_master():
            self.set_state(SupvisorsStates.SHUTTING_DOWN)
        else:
            if self.state_modes.master_identifier:
                # re-route the command to Master
                self.supvisors.rpc_handler.send_shutdown_all(self.state_modes.master_identifier)
            else:
                message = 'no Master instance to perform the Supvisors restart request'
                self.logger.error(f'FiniteStateMachine.on_restart: {message}')
                raise ValueError(message)

    def on_end_sync(self, master_identifier: str) -> None:
        """ End the synchronization phase using the given Master or trigger an election.

        :param master_identifier: the identifier of the Master Supvisors instance selected by the user.
        :return: None.
        """
        if master_identifier:
            self.state_modes.master_identifier = master_identifier
        else:
            self.state_modes.select_master()
        # re-evaluate the FSM
        self.next()

    # Map between state enumerations and classes
    _StateInstances: Dict[SupvisorsStates, Callable] = {SupvisorsStates.OFF: OffState,
                                                        SupvisorsStates.SYNCHRONIZATION: SynchronizationState,
                                                        SupvisorsStates.ELECTION: ElectionState,
                                                        SupvisorsStates.DISTRIBUTION: DistributionState,
                                                        SupvisorsStates.OPERATION: OperationState,
                                                        SupvisorsStates.CONCILIATION: ConciliationState,
                                                        SupvisorsStates.RESTARTING: RestartingState,
                                                        SupvisorsStates.SHUTTING_DOWN: ShuttingDownState,
                                                        SupvisorsStates.FINAL: FinalState}

    # Transitions allowed between states
    _Transitions = {SupvisorsStates.OFF: [SupvisorsStates.SYNCHRONIZATION],
                    SupvisorsStates.SYNCHRONIZATION: [SupvisorsStates.OFF,
                                                      SupvisorsStates.ELECTION],
                    SupvisorsStates.ELECTION: [SupvisorsStates.OFF,
                                               SupvisorsStates.SYNCHRONIZATION,
                                               SupvisorsStates.DISTRIBUTION,
                                               SupvisorsStates.SHUTTING_DOWN],
                    SupvisorsStates.DISTRIBUTION: [SupvisorsStates.OFF,
                                                   SupvisorsStates.ELECTION,
                                                   SupvisorsStates.OPERATION,
                                                   SupvisorsStates.RESTARTING,
                                                   SupvisorsStates.SHUTTING_DOWN],
                    SupvisorsStates.OPERATION: [SupvisorsStates.OFF,
                                                SupvisorsStates.SYNCHRONIZATION,
                                                SupvisorsStates.ELECTION,
                                                SupvisorsStates.CONCILIATION,
                                                SupvisorsStates.RESTARTING,
                                                SupvisorsStates.SHUTTING_DOWN],
                    SupvisorsStates.CONCILIATION: [SupvisorsStates.OFF,
                                                   SupvisorsStates.SYNCHRONIZATION,
                                                   SupvisorsStates.OPERATION,
                                                   SupvisorsStates.RESTARTING,
                                                   SupvisorsStates.SHUTTING_DOWN],
                    SupvisorsStates.RESTARTING: [SupvisorsStates.FINAL],
                    SupvisorsStates.SHUTTING_DOWN: [SupvisorsStates.FINAL],
                    SupvisorsStates.FINAL: []}
