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
from typing import Any, Optional, Set, Tuple

from supervisor.loggers import Logger

from .context import Context
from .instancestatus import SupvisorsInstanceStatus
from .options import SupvisorsOptions
from .process import ProcessStatus
from .statemodes import SupvisorsStateModes
from .strategy import conciliate_conflicts
from .ttypes import (SupvisorsInstanceStates, SupvisorsStates, SynchronizationOptions,
                     RunningFailureStrategies, SupvisorsFailureStrategies,
                     NameList, Payload, PayloadList, WORKING_STATES)


# FSM base states
class SupvisorsBaseState:
    """ Base class for a state with simple entry / next / exit actions. """

    def __init__(self, supvisors: Any) -> None:
        """ Initialization of the attributes. """
        self.supvisors = supvisors
        self.invalidated_identifiers: NameList = []
        self.failed_processes: Set[ProcessStatus] = set()

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
        May be specialized in subclasses, but this method should be called anyway.

        :return: the next Supvisors state.
        """
        # acknowledge CHECKED instances
        self.context.activate_checked()
        # acknowledge FAILED instances and store the invalidated Supvisors instances and processes
        # NOTE: it's up to the subclasses to process this information or not
        self.invalidated_identifiers, self.failed_processes = self.context.invalidate_failed()
        # various check on Supvisors stability, depending on the FSM state
        next_state = self._check_instances()
        if next_state:
            return next_state
        return None

    def exit(self) -> None:
        """ Actions performed when leaving the state.
        May be specialized in subclasses.

        :return: None.
        """

    def _check_instances(self) -> Optional[SupvisorsStates]:
        """ Check that the local Supvisors instance is still RUNNING.

        This is the symptom of an internal bug.
        If this occurs, it is unlikely that Supvisors will go back to an operation state.

        :return: the suggested state if the local Supvisors instance is not active anymore.
        """
        # check that the local Supvisors instance is still RUNNING
        if self.context.local_status.state != SupvisorsInstanceStates.RUNNING:
            self.logger.critical('SupvisorsBaseState.check_instances: the local Supvisors instance is not RUNNING')
            return SupvisorsStates.OFF
        return None

    def _check_strict_failure(self, sync: bool = False) -> Optional[bool]:
        """ Return the running status of the expected Supvisors instances.

        More particularly, if the STRICT option is set, return False if all the Supvisors instances declared
        in the supvisors_list option are running, and True otherwise.
        Return None if the STRICT option is not set. """
        if SynchronizationOptions.STRICT in self.supvisors.options.synchro_options:
            if self.context.initial_running():
                if sync:
                    # log only during the synchronization phase
                    self.logger.info('SupvisorsBaseState.check_strict: all expected Supvisors instances are RUNNING')
                return False
            if not sync:
                # log only outside the synchronization phase
                self.logger.warn('SupvisorsBaseState.check_strict: at least one expected Supvisors instance is not RUNNING')
            # TODO: set degraded ? think about unsetting it at some point
            return True
        return None

    def _check_list_failure(self, sync: bool = False) -> Optional[bool]:
        """ Return the running status of the known Supvisors instances.

        More particularly, if the LIST option is set, return False if all the known Supvisors instances (i.e. those
        declared in the supvisors_list option and those discovered) are running, and True otherwise.
        Return None if the LIST option is not set. """
        if SynchronizationOptions.LIST in self.supvisors.options.synchro_options:
            if self.context.all_running():
                if sync:
                    self.logger.info('SupvisorsBaseState.check_list: all known Supvisors instances are RUNNING')
                return False
            if not sync:
                # log only outside the synchronization phase
                self.logger.warn('SupvisorsBaseState.check_list: at least one known Supvisors instance is not RUNNING')
            # TODO: set degraded ? think about unsetting it at some point
            return True
        return None

    def _check_core_failure(self, sync: bool = False) -> Optional[bool]:
        """ Return the running status of the core Supvisors instances.

        More particularly, if the CORE option is set, return False if all the core Supvisors instances are running,
        and True otherwise.
        Return None if the CORE option is not set. """
        if SynchronizationOptions.CORE in self.supvisors.options.synchro_options:
            if self.context.core_identifiers_running():
                if sync:
                    self.logger.info('SupvisorsBaseState.check_core: all core Supvisors instances are RUNNING')
                return False
            self.logger.debug('SupvisorsBaseState.check_core: at least one core Supvisors instance is not RUNNING')
            # TODO: set degraded ? think about unsetting it at some point
            return True
        return None

    def _check_user_failure(self) -> Optional[bool]:
        """ Return the running status of the active Supvisors instances.

        More particularly, if the USER option is set, return False if all the active Supvisors instances are running,
        and True otherwise.
        Return None if the USER option is not set. """
        if SynchronizationOptions.USER in self.supvisors.options.synchro_options:
            if self.context.failed_identifiers():
                self.logger.warn('SupvisorsBaseState.check_user: at least one Supvisors instance is not RUNNING')
                return True
            return False
        return None

    def _abort_jobs(self) -> None:
        """ Abort starting jobs in progress.

        :return: None.
        """
        self.supvisors.failure_handler.abort()
        self.supvisors.starter.abort()
        self.supvisors.stopper.abort()


class PostSynchronizationState(SupvisorsBaseState):
    """ Increase the level of checking instances to go back to SYNCHRONIZATION state
    when the initial conditions are not met anymore. """

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
        core_failure = not user_failure and self._check_core_failure()
        strict_failure = not user_failure and not core_failure and self._check_strict_failure()
        list_failure = not user_failure and not core_failure and not strict_failure and self._check_list_failure()
        if strict_failure or list_failure or core_failure or user_failure:
            # TODO: set degraded ? think about unsetting it at some point
            strategy = self.supvisors.options.supvisors_failure_strategy
            if strategy == SupvisorsFailureStrategies.RESYNC:
                return SupvisorsStates.SYNCHRONIZATION
            # NOTE: about RESTART and SHUTDOWN strategies
            #       if the Master is set, it will just drive the other Supvisors instances, as usual
            #       if the Master is lost, the next call to check_instances in RESTARTING / SHUTTING_DOWN
            #           will return ELECTION, which will trigger the FINAL state
            if strategy == SupvisorsFailureStrategies.RESTART:
                return SupvisorsStates.RESTARTING  # FIXME: useless
            if strategy == SupvisorsFailureStrategies.SHUTDOWN:
                return SupvisorsStates.SHUTTING_DOWN
            # NOTE: just let it go with SupvisorsFailureStrategies CONTINUE
        return None

    def _check_instances(self) -> Optional[SupvisorsStates]:
        """ Check that local and Master Supvisors instances are still RUNNING.
        If their ticks are not received anymore, back to SYNCHRONIZATION state to force a synchronization phase.

        :return: the suggested state if local or Master Supvisors instance is not active anymore.
        """
        # check that the local Supvisors instance is still RUNNING
        next_state: Optional[SupvisorsStates] = super()._check_instances()
        if next_state:
            return next_state
        # check that initial conditions are still valid
        next_state = self._check_failure_strategy()
        if next_state:
            return next_state
        return None


class MasterSlaveState(PostSynchronizationState):
    """ xxx. """

    def enter(self) -> None:
        """ Actions performed when entering the state.
        Depending on Master/Slave status, the behaviour may be different.

        :return: None.
        """
        if self.context.is_master:
            self._master_enter()
        else:
            self._slave_enter()

    def _master_enter(self) -> None:
        """ Actions performed by the Supvisors Master instance when entering the state.
        May be redefined in subclasses.

        :return: None
        """

    def _slave_enter(self) -> None:
        """ Actions performed by a Supvisors Slave instance when entering the state.
        May be redefined in subclasses.

        :return: None
        """

    def next(self) -> Optional[SupvisorsStates]:
        """ Evaluate the current Supvisors status to decide if the FSM should transition.
        Depending on Master/Slave status, the behaviour may be different.

        :return: the next Supvisors state.
        """
        next_state: Optional[SupvisorsStates] = super().next()
        if next_state:
            return next_state
        # specific behaviour
        if self.context.is_master:
            return self._master_next()
        return self._slave_next()

    def _master_next(self) -> SupvisorsStates:
        """ Evaluate the current Supvisors status for the Supvisors Master instance to decide
        if the FSM should transition.

        Must be redefined in subclasses.

        :return: the next Supvisors state.
        """
        raise NotImplementedError

    def _slave_next(self) -> Optional[SupvisorsStates]:
        """ A Supvisors slave instance generally follows the Master state (that may be not defined yet).

        :return: the Supvisors Master state.
        """
        return self.state_modes.master_state

    def exit(self) -> None:
        """ Actions performed when leaving the state.
        Depending on Master/Slave status, the behaviour may be different.

        :return: None.
        """
        if self.context.is_master:
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

    def _check_instances(self) -> Optional[SupvisorsStates]:
        """ Check that the Master Supvisors instance is set, unique and is still RUNNING.

        :return: the suggested state if the Master Supvisors instance is missing.
        """
        next_state: Optional[SupvisorsStates] = super()._check_instances()
        if next_state:
            return next_state
        # check that the unique Master Supvisors instance is still RUNNING
        if not self.state_modes.check_master():
            self.logger.warn('MasterSlaveState.check_instances: unique Supvisors Master instance RUNNING'
                             ' - condition failed')
            return SupvisorsStates.ELECTION
        return None

class WorkingState(MasterSlaveState):
    """ Base class for working (DISTRIBUTION, OPERATION, CONCILIATION) states.
    TODO: TBC for DISTRIBUTION
    """

    def _check_process_failures(self) -> None:
        """ Handle process failures if a Supvisors instance is lost. """
        # At this point, there may be a list of FAILED Supvisors instances
        self.logger.debug(f'WorkingState.check_process_failures: invalidated_identifiers={self.invalidated_identifiers}'
                          f' process_failures={[process.namespec for process in self.failed_processes]}')
        if self.invalidated_identifiers:
            # inform Starter and Stopper because processes in failure may be removed if already in their pipes
            self.supvisors.starter.on_instances_invalidation(self.invalidated_identifiers, self.failed_processes)
            self.supvisors.stopper.on_instances_invalidation(self.invalidated_identifiers, self.failed_processes)
            # the Master fixes failures if any
            if self.context.is_master:
                for process in self.failed_processes:
                    self.supvisors.failure_handler.add_default_job(process)
        # trigger remaining jobs in RunningFailureHandler
        if self.context.is_master:
            self.supvisors.failure_handler.trigger_jobs()

    def _check_instances(self) -> Optional[SupvisorsStates]:
        """ Check that local and Master Supvisors instances are still RUNNING.
        If their ticks are not received anymore, back to SYNCHRONIZATION state to force a synchronization phase.

        :return: the suggested state if local or Master Supvisors instance is not active anymore.
        """
        next_state: Optional[SupvisorsStates] = super()._check_instances()
        if next_state:
            return next_state
        # handle process failures if a Supvisors instance other than Local / Master has been lost
        # FIXME: what if processes were running in the Master. who will repair ?
        #        is the DISTRIBUTION phase enough to cope with running failure strategies ?
        # TODO: post everything to failure_handler in all cases
        #       manager trigger_jobs in Distribution state for master (cancel for slave)
        #       impact on starter.start_applications to be assessed
        self._check_process_failures()
        return None


class EndingState(MasterSlaveState):
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

    def _check_instances(self) -> Optional[SupvisorsStates]:
        """ Force the ending process if the local or Master Supvisors instance is lost.

        :return: the suggested state if a Supvisors instance is not active anymore.
        """
        # NOTE: no process failure handling here, as everything is going to be stopped anyway
        next_state = super()._check_instances()
        if next_state:
            # even if the Master has been lost, it is excluded to transition back to SYNCHRONIZATION state
            # at this point, so just reach the FINAL state
            return SupvisorsStates.FINAL
        return None


# FSM real states
class OffState(SupvisorsBaseState):
    """ Entry state of the Supvisors FSM.

    No Master / slave at this stage.
    No further processing on invalidated Supvisors instances and processes.
    """

    def _check_instances(self) -> Optional[SupvisorsStates]:
        """ Check that the local Supvisors instance is RUNNING.

        The parent _check_instances logic is reversed to transition to the SYNCHRONIZATION state
        when the local Supvisors is actually RUNNING.

        :return: the suggested state if the local Supvisors instance is active.
        """
        if self.context.local_status.state == SupvisorsInstanceStates.RUNNING:
            return SupvisorsStates.SYNCHRONIZATION
        self.logger.debug('OffState.check_instances: the local Supvisors instance is not RUNNING')
        return None


class SynchronizationState(SupvisorsBaseState):
    """ In the SYNCHRONIZATION state, Supvisors synchronizes all known Supvisors instances.

    No Master / slave at this stage.
    No further processing on invalidated Supvisors instances and processes.
    """

    start_date: float = 0.0

    @property
    def uptime(self) -> float:
        """ Get the uptime since Supvisors entered in SYNCHRONIZATION state. """
        return time.monotonic() - self.start_date

    def enter(self) -> None:
        """ When entering the SYNCHRONIZATION state, abort all existing jobs and reset the start date.

        :return: None.
        """
        self._abort_jobs()
        self.start_date = time.monotonic()

    def _check_end_sync_timeout(self, uptime: float) -> bool:
        """ End of sync phase if the uptime has exceeded the synchro_timeout.

        If the condition is reached, the ELECTION state may be reached with Supvisors instances still STOPPED.
        """
        if SynchronizationOptions.TIMEOUT in self.supvisors.options.synchro_options:
            synchro_timeout = self.supvisors.options.synchro_timeout
            self.logger.debug(f'SynchronizationState.check_end_sync_timeout: uptime={uptime}'
                              f' synchro_timeout={synchro_timeout}')
            if uptime >= synchro_timeout:
                self.logger.info(f'SynchronizationState.check_end_sync_timeout: timeout {synchro_timeout} reached')
                return True
        return False

    def _check_end_sync_core(self, uptime: float) -> bool:
        """ End of sync phase if all core Supvisors instances are in a known state.

        If the condition is reached, the ELECTION state may be reached with Supvisors instances still STOPPED.

        NOTE: this option is NOT allowed if the core_identifiers is empty (which is expected in discovery mode,
              although not incompatible).
        """
        core_sync = self._check_core_failure(True)
        if not core_sync:
            # all core Supvisors instances are running
            # in case of late start, a security limit of SYNCHRO_TIMEOUT_MIN is kept to give a chance
            # to other Supvisors instances and limit the number of re-distributions
            if uptime > SupvisorsOptions.SYNCHRO_TIMEOUT_MIN:
                self.logger.info('SynchronizationState.check_end_sync_core: all core Supvisors instances are RUNNING')
                return True
        return False

    def _check_end_sync_user(self, running_identifiers: NameList) -> bool:
        """ End of sync phase if the master is known.

        This is meant to be triggered using the Web UI or using the XML-RPC API.
        No time condition applies as the user is responsible.
        """
        if SynchronizationOptions.USER in self.supvisors.options.synchro_options:
            # the Master Supvisors instance must be seen as running
            if self.context.master_identifier and self.context.master_identifier in running_identifiers:
                self.logger.info('SynchronizationState.check_end_sync_user: the Supvisors Master instance is RUNNING')
                return True
        return False

    def next(self) -> SupvisorsStates:
        """ Wait for Supvisors instances to exchange data until a condition is reached to end the synchronization phase.

        No further processing on invalidated Supvisors instances and processes.

        :return: the new Supvisors state.
        """
        next_state: Optional[SupvisorsStates] = super().next()
        if next_state:
            return next_state
        # get duration from start date
        uptime: float = self.uptime
        # cannot get out of this state without local Supvisors instance RUNNING
        running_identifiers = self.context.running_identifiers()
        if self.local_identifier in running_identifiers:
            # check end of sync conditions
            self.logger.trace(f'SynchronizationState.next: synchro_options={self.supvisors.options.synchro_options}')
            strict_sync = not self._check_strict_failure(True)
            list_sync = self._check_list_failure(True)
            timeout_sync = self._check_end_sync_timeout(uptime)
            core_sync = self._check_end_sync_core(uptime)
            user_sync = self._check_end_sync_user(running_identifiers)
            self.logger.debug(f'SynchronizationState.next: strict_sync={strict_sync} list_sync={list_sync}'
                              f' timeout_sync={timeout_sync} core_sync={core_sync} user_sync={user_sync}')
            if strict_sync or list_sync or timeout_sync or core_sync or user_sync:
                # FIXME: if TIMEOUT used combined with STRICT / LIST / CORE, we have a degraded state
                return SupvisorsStates.ELECTION
        else:
            # log current status
            if uptime >= SupvisorsOptions.SYNCHRO_TIMEOUT_MIN:
                self.logger.critical(f'SynchronizationState.next: local Supvisors={self.local_identifier} still'
                                     f' not RUNNING after {int(uptime)} seconds')
            else:
                self.logger.debug(f'SynchronizationState.next: local Supvisors={self.local_identifier} still'
                                  f' not RUNNING after {int(uptime)} seconds')
        return SupvisorsStates.SYNCHRONIZATION


class ElectionState(PostSynchronizationState):
    """ In the ELECTION state, a Supvisors Master instance is elected. """

    def enter(self) -> None:
        """ When entering the ELECTION state, abort all pending jobs.

        :return: None.
        """
        self._abort_jobs()

    def next(self) -> Optional[SupvisorsStates]:
        """ . """
        next_state: Optional[SupvisorsStates] = super().next()
        if next_state:
            return next_state
        # exit only when ALL active Supvisors instances agree on the same identifier
        if self.state_modes.check_master():
            return SupvisorsStates.DISTRIBUTION
        # re-evaluate the context to possibly get a more relevant Master
        self.state_modes.update_stability()
        if self.state_modes.stable_identifiers:
            self.state_modes.select_master()
            # NOTE: after local Master selection, wait for selection to be shared and agreed
            #       among all Supvisors instances
        self.logger.info('ElectionState.next: waiting for a suitable Master'
                         f' (current={self.state_modes.master_identifier})')
        return SupvisorsStates.ELECTION


class DistributionState(WorkingState):
    """ In the DISTRIBUTION state, Supvisors starts automatically the applications having a starting model.

    The distribution jobs are driven by the Supvisors Master instance only.
    """

    def _master_enter(self):
        """ Trigger the automatic start and stop. """
        self.supvisors.starter.start_applications(self.supvisors.fsm.force_distribution)
        self.supvisors.fsm.force_distribution = False

    def _master_next(self) -> SupvisorsStates:
        """ Check if the starting tasks are completed.

        :return: the next Supvisors state.
        """
        # TODO: manage invalidate_failed TBC
        # Master goes to OPERATION when starting is completed
        if self.supvisors.starter.in_progress():
            return SupvisorsStates.DISTRIBUTION
        # TODO: do NOT activate checked in DISTRIBUTION
        # new Supvisors instances may have arrived in the gap
        #checked_identifiers = self.context.activate_checked()
        #if checked_identifiers:
        #    # call enter again to trigger a new distribution
        #    self.logger.info('DistributionState.master_next: re-enter DISTRIBUTION because of new'
        #                     f' Supvisors instances={checked_identifiers}')
        #    self.master_enter()
        #    return SupvisorsStates.DISTRIBUTION
        return SupvisorsStates.OPERATION


class OperationState(WorkingState):
    """ In the OPERATION state, Supvisors is waiting for requests. """

    def next(self):
        """ TODO

        :return:
        """
        next_state: Optional[SupvisorsStates] = super().next()
        if next_state:
            return next_state
        # TODO: transition all CHECKED Supvisors instances to RUNNING
        checked_identifiers = self.context.activate_checked()
        if checked_identifiers:
            # call enter again to trigger a new distribution
            self.logger.info('DistributionState.master_next: re-enter DISTRIBUTION because of new'
                             f' Supvisors instances={checked_identifiers}')
            return SupvisorsStates.DISTRIBUTION

    def _master_next(self) -> SupvisorsStates:
        """ Check that all Supvisors instances are still active.
        Look after possible conflicts due to multiple running instances of the same process.

        :return: the new Supvisors state
        """
        # check if jobs are in progress
        if self.supvisors.starter.in_progress() or self.supvisors.stopper.in_progress():
            return SupvisorsStates.OPERATION
        # check duplicated processes
        if self.context.conflicting():
            return SupvisorsStates.CONCILIATION
        # new Supvisors instances may have arrived in the gap
        checked_identifiers = self.context.activate_checked()
        if checked_identifiers:
            # back to DISTRIBUTION state to repair what may have failed before
            self.logger.info('OperationState.master_next: transition to DISTRIBUTION because of new'
                             f' Supvisors instances={checked_identifiers}')
            return SupvisorsStates.DISTRIBUTION
        return SupvisorsStates.OPERATION


class ConciliationState(WorkingState):
    """ In the CONCILIATION state, Supvisors conciliates the conflicts.

    The conciliation jobs are driven by the Supvisors Master instance only.
    """

    def _master_enter(self) -> None:
        """ When entering the CONCILIATION state, conciliate automatically the conflicts. """
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


class RestartingState(EndingState):
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
        # stay in RESTARTING as long as the Master does
        if self.state_modes.master_state == SupvisorsStates.RESTARTING:
            return SupvisorsStates.RESTARTING
        # the Master is expected to transition to the FINAL state
        if self.state_modes.master_state != SupvisorsStates.FINAL:
            self.logger.error('RestartingState.slave_next: unexpected transition from the Master'
                              f' ({self.state_modes.master_state.name})')
        return SupvisorsStates.FINAL

    def exit(self):
        """ When exiting the RESTARTING state, request the local Supervisor restart.
        Same action for Master and Slaves. """
        self.supvisors.rpc_handler.send_restart(self.local_identifier)


class ShuttingDownState(EndingState):
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
        # stay in RESTARTING as long as the Master does
        if self.state_modes.master_state == SupvisorsStates.SHUTTING_DOWN:
            return SupvisorsStates.SHUTTING_DOWN
        # the Master is expected to transition to the FINAL state
        if self.state_modes.master_state != SupvisorsStates.FINAL:
            self.logger.error('ShuttingDownState.slave_next: unexpected transition from the Master'
                              f' ({self.state_modes.master_state.name})')
        return SupvisorsStates.FINAL

    def exit(self):
        """ When exiting the SHUTTING_DOWN state, request the local Supervisor shutdown.
        Same action for Master and Slaves. """
        self.supvisors.rpc_handler.send_shutdown(self.local_identifier)


class FinalState(SupvisorsBaseState):
    """ This is a final state for Master and Slaves.
    Whatever it is consecutive to a shutdown or a restart, the Supervisor 'session' will end. """


class FiniteStateMachine:
    """ This class implements a very simple behaviour of FiniteStateMachine based on a single event.
    A state is able to evaluate itself for transitions.

    Attributes are:
        - state: the current state of this state machine ;
        - instance: the current state instance ;
        - force_distribution: a status telling if a DISTRIBUTION state is pending.
    """

    def __init__(self, supvisors: Any) -> None:
        """ Reset the state machine and the internal context.

        :param supvisors: the Supvisors global structure
        """
        self.supvisors = supvisors
        self.instance: SupvisorsBaseState = OffState(supvisors)
        self.force_distribution: bool = False

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

        :return: None
        """
        # periodic check of start / stop jobs
        self.supvisors.starter.check()
        self.supvisors.stopper.check()
        # check state machine
        self.set_state(self.instance.next())

    def set_state(self, next_state: Optional[SupvisorsStates]) -> None:
        """ Update the current state of the state machine and transitions as long as possible.
        The transition can be forced, especially when getting the first Master state.

        :param next_state: the new state.
        :return: None.
        """
        # NOTE: in the event of a Slave FSM, the master state may not be known yet, hence the test on next_state
        while next_state and next_state != self.state:
            # check that the transition is allowed
            # a Slave Supvisors will always follow the Master state
            if self.context.is_master and next_state not in self._Transitions[self.state]:
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

    def on_timer_event(self, event: Payload) -> None:
        """ Periodic task used to check if remote Supvisors instances are still active. """
        self.context.on_timer_event(event)
        self.next()

    def handle_instance_failures(self, invalidated_identifiers: NameList,
                                 failed_processes: Set[ProcessStatus]) -> None:
        """ Upon failure of at least one Supvisors instance.

        :param invalidated_identifiers: the identifiers of the invalidated Supvisors instances.
        :param failed_processes: the processes in failure.
        :return: None.
        """
        self.logger.debug(f'FiniteStateMachine.handle_failures: invalidated_identifiers={invalidated_identifiers}'
                          f' process_failures={[process.namespec for process in failed_processes]}')
        if invalidated_identifiers:
            # inform Starter and Stopper
            # process_failures may be removed if already in their pipes
            self.supvisors.starter.on_instances_invalidation(invalidated_identifiers, failed_processes)
            self.supvisors.stopper.on_instances_invalidation(invalidated_identifiers, failed_processes)
            # deal with process_failures and isolation only if in DEPLOYMENT, OPERATION or CONCILIATION states
            if self.state in WORKING_STATES:
                # the Master fixes failures if any (can happen after an identifier invalidation, a process crash
                #   or a conciliation request)
                if self.context.is_master:
                    for process in failed_processes:
                        self.supvisors.failure_handler.add_default_job(process)
        # trigger remaining jobs in RunningFailureHandler
        if self.context.is_master:
            self.supvisors.failure_handler.trigger_jobs()
        # trigger FSM for global status re-evaluation
        #   -> the Master may have been invalidated
        #   -> process_failures could also positively impact the conflicts in the CONCILIATION state
        self.next()

    # Event handling methods
    def on_tick_event(self, status: SupvisorsInstanceStatus, event: Payload) -> None:
        """ This event is used to refresh the data related to the Supvisors instance.

        :param status: the Supvisors instance that sent the event.
        :param event: the tick event.
        :return: None.
        """
        self.context.on_tick_event(status, event)

    def on_discovery_event(self, event: Tuple) -> None:
        """ This event is used to add new Supvisors instances into the Supvisors system.
        No need to test if the discovery mode is enabled. This is managed in the internal communication layer.

        :param event: the discovery event.
        :return: None.
        """
        self.context.on_discovery_event(event[0], event[1])

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
            # trigger an automatic (so master only) behaviour for a running failure
            # process crash triggered only if running failure strategy related to application
            # Supvisors does not replace Supervisor in the present matter (use autorestart if necessary)
            if self.context.is_master and process.crashed():
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
                    # (no instance found) so retry is useless
                    if (stop_strategy or restart_strategy) and process.forced_state is None:
                        self.supvisors.failure_handler.add_default_job(process)

    def on_process_added_event(self, status: SupvisorsInstanceStatus, event: Payload) -> None:
        """ This event is used to fill the internal structures when processes have been added on a Supvisors instance.

        :param status: the Supvisors instance that sent the event.
        :param event: the process information.
        :return: None.
        """
        self.context.load_processes(status, [event])

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
        """ This event is used to get the FSM state of the master Supvisors instance.

        :param status: the Supvisors instance that sent the event.
        :param event: the state event.
        :return: None.
        """
        self.logger.debug(f'FiniteStateMachine.on_state_event: Supvisors={status.usage_identifier} sent {event}')
        self.state_modes.on_instance_state_event(status.identifier, event)
        # the event may impact the Master selection, so trigger the FSM
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

    def on_authorization(self, status: SupvisorsInstanceStatus, authorized: Optional[bool]) -> None:
        """ This event is used to finalize the port-knocking between Supvisors instances.
        When a new Supvisors instance comes in the group, back to DEPLOYMENT for a possible deployment.

        :param status: the Supvisors instance that sent the event.
        :param authorized: the authorization status as seen by the remote Supvisors instance.
        :return: None.
        """
        self.logger.debug(f'FiniteStateMachine.on_authorization: identifier={status.usage_identifier}'
                          f' authorized={authorized}')
        self.context.on_authorization(status, authorized)

    def on_restart_sequence(self) -> None:
        """ This event is used to transition the state machine to the DEPLOYMENT state.

        :return: None.
        """
        if self.context.is_master:
            self.force_distribution = True
        else:
            # re-route the command to Master
            self.supvisors.rpc_handler.send_restart_sequence(self.context.master_identifier)

    def on_restart(self) -> None:
        """ This event is used to transition the state machine to the RESTARTING state.

        :return: None.
        """
        if self.context.is_master:
            self.set_state(SupvisorsStates.RESTARTING)
        else:
            if self.context.master_identifier:
                # re-route the command to Master
                self.supvisors.rpc_handler.send_restart_all(self.context.master_identifier)
            else:
                message = 'no Master instance to perform the Supvisors restart request'
                self.logger.error(f'FiniteStateMachine.on_restart: {message}')
                raise ValueError(message)

    def on_shutdown(self) -> None:
        """ This event is used to transition the state machine to the SHUTTING_DOWN state.

        :return: None.
        """
        if self.context.is_master:
            self.set_state(SupvisorsStates.SHUTTING_DOWN)
        else:
            if self.context.master_identifier:
                # re-route the command to Master
                self.supvisors.rpc_handler.send_shutdown_all(self.context.master_identifier)
            else:
                message = 'no Master instance to perform the Supvisors restart request'
                self.logger.error(f'FiniteStateMachine.on_restart: {message}')
                raise ValueError(message)

    def on_end_sync(self, master_identifier: str) -> None:
        """ End the synchronization phase using the given Master or trigger an election.

        :param master_identifier: the identifier of the Master Supvisors instance selected by the user
        :return: None
        """
        # FIXME
        if master_identifier:
            self.state_modes.master_identifier = master_identifier
        else:
            self.state_modes.select_master()
        # re-evaluate the FSM
        self.next()

    # Map between state enumerations and classes
    _StateInstances = {SupvisorsStates.OFF: OffState,
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
                                               SupvisorsStates.DISTRIBUTION],
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
