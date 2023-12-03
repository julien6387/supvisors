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

from time import time
from typing import Any, Optional

from supervisor.loggers import Logger

from .context import Context
from .options import SupvisorsOptions
from .strategy import conciliate_conflicts
from .ttypes import (SupvisorsInstanceStates, RunningFailureStrategies, SupvisorsStates, SynchronizationOptions,
                     NameList, Payload, PayloadList, WORKING_STATES)


class Forced:
    pass


class AbstractState:
    """ Base class for a state with simple entry / next / exit actions.

    Attributes are:
        - supvisors: the reference to the global Supvisors structure ;
        - context: the reference to the context of the global Supvisors structure ;
        - logger: the reference to the logger of the global Supvisors structure ;
        - local_identifier: the identifier of the local Supvisors instance.
     """

    def __init__(self, supvisors: Any) -> None:
        """ Initialization of the attributes.

        :param supvisors: the global Supvisors structure
        """
        self.supvisors = supvisors
        self.local_identifier = supvisors.mapper.local_identifier

    @property
    def context(self) -> Context:
        """ Shortcut to the Supvisors context structure

        :return:
        """
        return self.supvisors.context

    @property
    def logger(self) -> Logger:
        """ Shortcut to the Supvisors logger structure

        :return:
        """
        return self.supvisors.logger

    def enter(self) -> None:
        """ Actions performed when entering the state.
        May be redefined in subclasses.

        :return: None
        """

    def next(self) -> SupvisorsStates:
        """ Actions performed upon reception of an event.
        May be redefined in subclasses.

        :return: None
        """

    def exit(self) -> None:
        """ Actions performed when leaving the state.
        May be redefined in subclasses.

        :return: None
        """

    def check_instances(self) -> Optional[SupvisorsStates]:
        """ Check that local and Master Supvisors instances are still RUNNING.
        If their ticks are not received anymore, back to INITIALIZATION state to force a synchronization phase.

        Set CHECKED Supvisors instances to RUNNING if no start sequence is in progress (in order to avoid interference).

        :return: the suggested state if local or Master Supvisors instance is not active anymore
        """
        # set all CHECKED Supvisors instances to RUNNING if no starting sequence is in progress
        if not self.supvisors.starter.in_progress():
            self.context.activate_checked()
        # check that the local Supvisors instance is still RUNNING
        if self.context.local_status.state != SupvisorsInstanceStates.RUNNING:
            self.logger.critical('AbstractState.check_instances: local Supvisors instance not RUNNING')
            return SupvisorsStates.INITIALIZATION
        # check that the Master Supvisors instance is still RUNNING
        master_instance = self.context.master_instance
        if not master_instance or master_instance.state != SupvisorsInstanceStates.RUNNING:
            self.logger.warn('AbstractState.check_instances: no Master Supvisors instance RUNNING')
            # in INITIALIZATION, master_identifier is not reset (state is not re-entered)
            self.context.master_identifier = ''
            return SupvisorsStates.INITIALIZATION
        return None

    def abort_jobs(self) -> None:
        """ Abort starting jobs in progress.

        :return: None
        """
        self.supvisors.failure_handler.abort()
        self.supvisors.starter.abort()
        self.supvisors.stopper.abort()


class OffState(AbstractState):

    def next(self) -> SupvisorsStates:
        """ Wait for Supervisor to be RUNNING.

        :return: the new Supvisors state
        """
        # The Supvisors sockets is an easy mark to know that Supervisor is running
        if self.supvisors.internal_com:
            return SupvisorsStates.INITIALIZATION
        return SupvisorsStates.OFF


class InitializationState(AbstractState):
    """ In the INITIALIZATION state, Supvisors synchronizes to all known Supvisors instances. """

    def enter(self) -> None:
        """ When entering the INITIALIZATION state, reset the context.

        :return: None
        """
        # clear any existing job
        self.abort_jobs()
        # reset context, keeping the isolation status
        self.context.reset()

    def _check_end_sync_strict(self) -> bool:
        """ End of sync phase if all Supvisors instances declared in the supvisors_list option are running.
        NOTE: this option is NOT allowed if the supvisors_list is empty (which is expected in discovery mode,
        but still possible).
        """
        if SynchronizationOptions.STRICT in self.supvisors.options.synchro_options:
            if self.context.initial_running():
                self.logger.info('InitializationState._check_end_sync_list: all expected Supvisors instances'
                                 ' are RUNNING')
                return True
        return False

    def _check_end_sync_list(self) -> bool:
        """ End of sync phase if all known Supvisors instances are running.
        NOTE: this includes the Supvisors instances declared in the supvisors_list option and the discovered
        Supvisors instances.
        """
        if SynchronizationOptions.LIST in self.supvisors.options.synchro_options:
            if self.context.all_running():
                self.logger.info('InitializationState._check_end_sync_list: all known Supvisors instances'
                                 ' are RUNNING')
                return True
        return False

    def _check_end_sync_timeout(self, uptime: float) -> bool:
        """ End of sync phase if the uptime has exceeded the synchro_timeout. """
        if SynchronizationOptions.TIMEOUT in self.supvisors.options.synchro_options:
            synchro_timeout = self.supvisors.options.synchro_timeout
            self.logger.debug(f'InitializationState._check_end_sync_timeout: uptime={uptime}'
                              f' synchro_timeout={synchro_timeout}')
            if uptime >= synchro_timeout:
                self.logger.info(f'InitializationState._check_end_sync_timeout: timeout {synchro_timeout} reached')
                return True
        return False

    def _check_end_sync_core(self, uptime: float, running_identifiers: NameList) -> bool:
        """ End of sync phase if all core Supvisors instances are in a known state.
        If the condition is reached, the DEPLOYMENT state may be reached with Supvisors instances still UNKNOWN.
        NOTE: this option is NOT allowed if the core_identifiers is empty (which is expected in discovery mode,
        but still possible). """
        if SynchronizationOptions.CORE in self.supvisors.options.synchro_options:
            # all core Supvisors instances must be running
            # in case of late start, a security limit of SYNCHRO_TIMEOUT_MIN is kept to give a chance
            # to other Supvisors instances and limit the number of redeploy_mark
            if uptime > SupvisorsOptions.SYNCHRO_TIMEOUT_MIN and self.context.running_core_identifiers():
                # in the event where the local Supvisors instance has been started lately, there may be already
                #   a Master Supvisors instance, in which case it must be seen as running
                if not self.context.master_identifier or self.context.master_identifier in running_identifiers:
                    self.logger.info('InitializationState._check_end_sync_core: all core Supvisors instances'
                                     ' are RUNNING')
                    return True
                self.logger.info('InitializationState._check_end_sync_core: all core Supvisors instances'
                                 f' are RUNNING but not the declared Master={self.context.master_identifier}')
        return False

    def _check_end_sync_user(self, running_identifiers: NameList) -> bool:
        """ End of sync phase if the master is known.
        This is meant to be triggered using the Web UI or using the XML-RPC API.
        No time condition applies as the user is responsible.
        """
        if SynchronizationOptions.USER in self.supvisors.options.synchro_options:
            # the Master Supvisors instance must be seen as running
            if self.context.master_identifier and self.context.master_identifier in running_identifiers:
                self.logger.info('InitializationState._check_end_sync_user: the Supvisors Master instance is RUNNING')
                return True
        return False

    def next(self) -> SupvisorsStates:
        """ Wait for Supvisors instances to exchange their data until a condition is reached
        to end the synchronization phase.

        :return: the new Supvisors state
        """
        # set all CHECKED Supvisors instances to RUNNING
        self.context.activate_checked()
        # get duration from start date
        uptime: float = time() - self.context.start_date
        # cannot get out of this state without local Supvisors instance RUNNING
        running_identifiers = self.context.running_identifiers()
        if self.local_identifier in running_identifiers:
            # check end of sync conditions
            self.logger.trace(f'InitializationState.next: synchro_options={self.supvisors.options.synchro_options}')
            strict_sync = self._check_end_sync_strict()
            list_sync = self._check_end_sync_list()
            timeout_synch = self._check_end_sync_timeout(uptime)
            core_sync = self._check_end_sync_core(uptime, running_identifiers)
            user_sync = self._check_end_sync_user(running_identifiers)
            self.logger.debug(f'InitializationState.next: strict_sync={strict_sync} list_sync={list_sync}'
                              f' timeout_synch={timeout_synch} core_sync={core_sync} user_sync={user_sync}')
            if strict_sync or list_sync or timeout_synch or core_sync or user_sync:
                if self.context.master_identifier:
                    # check Master status and reset if not running
                    if self.context.master_instance.state != SupvisorsInstanceStates.RUNNING:
                        self.context.master_identifier = ''
                if not self.context.master_identifier:
                    self.context.elect_master()
                # The Master can exit the INITIALIZATION state by itself
                if self.context.is_master:
                    return SupvisorsStates.DEPLOYMENT
                # The Slaves will follow the Master state
                # WARN: at this point, the Master FSM state may not be known yet
                return self.supvisors.context.supvisors_state
        else:
            # log current status
            if uptime >= SupvisorsOptions.SYNCHRO_TIMEOUT_MIN:
                self.logger.critical(f'InitializationState.next: local Supvisors={self.local_identifier} still'
                                     f' not RUNNING after {int(uptime)} seconds')
            else:
                self.logger.debug(f'InitializationState.next: local Supvisors={self.local_identifier} still'
                                  f' not RUNNING after {int(uptime)} seconds')
        return SupvisorsStates.INITIALIZATION

    def exit(self):
        """ When exiting the INITIALIZATION state, set all non-responsive Supvisors instances to SILENT or ISOLATED.

        :return: None
        """
        self.context.invalid_unknown()


class MasterDeploymentState(AbstractState):
    """ In the DEPLOYMENT state, Supvisors starts automatically the applications having a starting model. """

    def enter(self):
        """ Trigger the automatic start and stop. """
        self.supvisors.starter.start_applications(self.supvisors.fsm.redeploy_mark is Forced)
        self.supvisors.fsm.redeploy_mark = False

    def next(self) -> SupvisorsStates:
        """ Check if the starting tasks are completed.

        :return: the new Supvisors state
        """
        # common check on local and Master Supvisors instances
        next_state = self.check_instances()
        if next_state:
            return next_state
        # Master goes to OPERATION when starting is completed
        if self.supvisors.starter.in_progress():
            return SupvisorsStates.DEPLOYMENT
        return SupvisorsStates.OPERATION


class MasterOperationState(AbstractState):
    """ In the OPERATION state, Supvisors is waiting for requests. """

    def next(self) -> SupvisorsStates:
        """ Check that all Supvisors instances are still active.
        Look after possible conflicts due to multiple running instances of the same process.

        :return: the new Supvisors state
        """
        # common check on local and Master Supvisors instances
        next_state = self.check_instances()
        if next_state:
            return next_state
        # check if jobs are in progress
        if self.supvisors.starter.in_progress() or self.supvisors.stopper.in_progress():
            return SupvisorsStates.OPERATION
        # check duplicated processes
        if self.context.conflicting():
            return SupvisorsStates.CONCILIATION
        # a redeployment mark has been set due to a new alive Supvisors instance
        # back to DEPLOYMENT state to repair what may have failed before
        if self.supvisors.fsm.redeploy_mark:
            return SupvisorsStates.DEPLOYMENT
        return SupvisorsStates.OPERATION


class MasterConciliationState(AbstractState):
    """ In the CONCILIATION state, Supvisors conciliates the conflicts. """

    def enter(self) -> None:
        """ When entering the CONCILIATION state, conciliate automatically the conflicts. """
        conciliate_conflicts(self.supvisors,
                             self.supvisors.options.conciliation_strategy,
                             self.context.conflicts())

    def next(self) -> SupvisorsStates:
        """ Check that all Supvisors instances are still active.
        Wait for all conflicts to be conciliated.

        :return: the new Supvisors state
        """
        # common check on local and Master Supvisors instances
        next_state = self.check_instances()
        if next_state:
            return next_state
        # check if jobs are in progress
        if self.supvisors.starter.in_progress() or self.supvisors.stopper.in_progress():
            return SupvisorsStates.CONCILIATION
        # back to OPERATION when there is no conflict anymore
        if not self.context.conflicting():
            return SupvisorsStates.OPERATION
        # new conflicts may happen while conciliation is in progress
        # call enter again to trigger a new conciliation
        self.enter()
        return SupvisorsStates.CONCILIATION


class MasterRestartingState(AbstractState):
    """ In the RESTARTING state, Supvisors stops all applications before triggering a full restart. """

    def enter(self) -> None:
        """ When entering the RESTARTING state, stop all applications.

        :return: None
        """
        self.abort_jobs()
        self.supvisors.stopper.stop_applications()

    def next(self) -> SupvisorsStates:
        """ Wait for all processes to be stopped.

        :return: the new Supvisors state
        """
        next_state = self.check_instances()
        if next_state:
            # no way going back to INITIALIZATION state at this point
            return SupvisorsStates.FINAL
        # check if stopping jobs are in progress
        if self.supvisors.stopper.in_progress():
            return SupvisorsStates.RESTARTING
        return SupvisorsStates.FINAL

    def exit(self):
        """ When exiting the RESTARTING state, request the Supervisor restart. """
        self.supvisors.internal_com.pusher.send_restart(self.local_identifier)
        # Slave instances will do the same when they will transition out of their RESTARTING state


class MasterShuttingDownState(AbstractState):
    """ In the SHUTTING_DOWN state, Supvisors stops all applications before triggering a full shutdown. """

    def enter(self):
        """ When entering in the SHUTTING_DOWN state, stop all applications. """
        self.abort_jobs()
        self.supvisors.stopper.stop_applications()

    def next(self):
        """ Wait for all processes to be stopped.

        :return: the new Supvisors state
        """
        # check eventual jobs in progress
        next_state = self.check_instances()
        if next_state:
            # no way going back to INITIALIZATION state at this point
            return SupvisorsStates.FINAL
        # check if stopping jobs are in progress
        if self.supvisors.stopper.in_progress():
            return SupvisorsStates.SHUTTING_DOWN
        return SupvisorsStates.FINAL

    def exit(self):
        """ When exiting the SHUTTING_DOWN state, request the Supervisor shutdown. """
        self.supvisors.internal_com.pusher.send_shutdown(self.local_identifier)
        # Slave instances will do the same when they will transition out of their SHUTTING_DOWN state


class SlaveMainState(AbstractState):

    def next(self) -> SupvisorsStates:
        """ The non-master instances are checking if local and Master Supvisors instances are still running.
        Local start / stop requests are evaluated too.

        :return: the new Supvisors state
        """
        # common check on local and Master Supvisors instances
        next_state = self.check_instances()
        if next_state:
            return next_state
        # next state is the Master state (maybe None)
        return self.supvisors.context.supvisors_state


class SlaveRestartingState(AbstractState):
    """ In the RESTARTING state, Supvisors stops all applications before triggering a full restart. """

    def enter(self) -> None:
        """ When entering the RESTARTING state, abort all pending tasks applications.

        :return: None
        """
        self.abort_jobs()

    def next(self) -> SupvisorsStates:
        """ Wait for all processes to be stopped.

        :return: the new Supvisors state
        """
        next_state = self.check_instances()
        if next_state:
            # no way going back to INITIALIZATION state at this point
            return SupvisorsStates.FINAL
        # stay in RESTARTING as long as the Master does
        if self.supvisors.context.supvisors_state == SupvisorsStates.RESTARTING:
            return SupvisorsStates.RESTARTING
        return SupvisorsStates.FINAL

    def exit(self):
        """ When exiting the RESTARTING state, request the full restart.

        NOTE: this has been moved from the former RestartState / enter because a Supvisors Slave
        could move from RESTARTING to any other state if the Master commands so,
        and it's important that Supervisor restarts at this point. """
        self.supvisors.internal_com.pusher.send_restart(self.local_identifier)


class SlaveShuttingDownState(AbstractState):
    """ In the SHUTTING_DOWN state, Supvisors stops all applications before triggering a full shutdown. """

    def enter(self) -> None:
        """ When entering the SHUTTING_DOWN state, abort all pending tasks applications.

        :return: None
        """
        self.abort_jobs()

    def next(self) -> SupvisorsStates:
        """ Wait for all processes to be stopped.

        :return: the new Supvisors state
        """
        next_state = self.check_instances()
        if next_state:
            # no way going back to INITIALIZATION state at this point
            return SupvisorsStates.FINAL
        # stay in SHUTTING_DOWN as long as the Master does
        if self.supvisors.context.supvisors_state == SupvisorsStates.SHUTTING_DOWN:
            return SupvisorsStates.SHUTTING_DOWN
        return SupvisorsStates.FINAL

    def exit(self):
        """ When exiting the SHUTTING_DOWN state, request the Supervisor shutdown.

        NOTE: this has been moved from the former ShutDownState / enter because a Supvisors Slave
        could move from SHUTTING_DOWN to any other state if the Master commands so,
        and it's important that Supervisor shuts down at this point. """
        self.supvisors.internal_com.pusher.send_shutdown(self.local_identifier)


class FinalState(AbstractState):
    """ This is a final state for Master and Slaves.
    Whatever it is a shutdown or a restart, the Supervisor 'session' will end. """


class FiniteStateMachine:
    """ This class implements a very simple behaviour of FiniteStateMachine based on a single event.
    A state is able to evaluate itself for transitions.

    Attributes are:
        - state: the current state of this state machine ;
        - instance: the current state instance ;
        - redeploy_mark: a status telling if a DEPLOYMENT state is pending.
    """

    def __init__(self, supvisors: Any) -> None:
        """ Reset the state machine and the internal context.

        :param supvisors: the Supvisors global structure
        """
        self.supvisors = supvisors
        self.state: SupvisorsStates = SupvisorsStates.OFF
        self.instance: AbstractState = OffState(supvisors)
        self.redeploy_mark: bool = False

    @property
    def logger(self) -> Logger:
        """ Return the Supvisors logger. """
        return self.supvisors.logger

    @property
    def context(self) -> Context:
        """ Return the Supvisors context structure. """
        return self.supvisors.context

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

        :param next_state: the new state
        :return: None
        """
        # in the event of a Slave FSM, the master state may not be known yet, hence the test on next_state
        while next_state and next_state != self.state:
            # check that the transition is allowed
            # a Slave Supvisors will always follow the Master state
            if self.context.is_master and next_state not in self._Transitions[self.state]:
                self.logger.critical(f'FiniteStateMachine.set_state: unexpected transition from {self.state.name}'
                                     f' to {next_state.name}')
                break
            # exit the current state
            self.instance.exit()
            # assign the new state and publish SupvisorsStatus event internally and externally
            self.state = next_state
            self.logger.warn(f'FiniteStateMachine.set_state: Supvisors in {self.state.name}')
            # publish the new state
            self.supvisors.context.publish_state_modes({'fsm_state': self.state})
            # create the new state and enters it
            if self.context.is_master:
                self.instance = self._MasterStateInstances[self.state](self.supvisors)
            else:
                self.instance = self._SlaveStateInstances[self.state](self.supvisors)
            self.instance.enter()
            # evaluate current state
            next_state = self.instance.next()

    def on_timer_event(self, event: Payload) -> None:
        """ Periodic task used to check if remote Supvisors instances are still active.
        This is also the main event trigger of this state machine. """
        invalidated_identifiers, process_failures = self.context.on_timer_event(event)
        self.logger.debug(f'FiniteStateMachine.on_timer_event: invalidated_identifiers={invalidated_identifiers}'
                          f' process_failures={[process.namespec for process in process_failures]}')
        if invalidated_identifiers:
            # inform Starter and Stopper
            # process_failures may be removed if already in their pipes
            self.supvisors.starter.on_instances_invalidation(invalidated_identifiers, process_failures)
            self.supvisors.stopper.on_instances_invalidation(invalidated_identifiers, process_failures)
            # deal with process_failures and isolation only if in DEPLOYMENT, OPERATION or CONCILIATION states
            if self.state in WORKING_STATES:
                # the Master fixes failures if any (can happen after an identifier invalidation, a process crash
                #   or a conciliation request)
                if self.context.is_master:
                    for process in process_failures:
                        self.supvisors.failure_handler.add_default_job(process)
        # trigger remaining jobs in RunningFailureHandler
        if self.context.is_master:
            self.supvisors.failure_handler.trigger_jobs()
        # check if new isolating remotes and isolate them at main loop level
        identifiers = self.context.handle_isolation()
        if identifiers:
            self.supvisors.internal_com.pusher.send_isolate_instances(identifiers)
        # trigger FSM for global status re-evaluation
        # the Master may have been invalidated
        # process_failures could also positively impact the conflicts in the CONCILIATION state
        self.next()

    # Event handling methods
    def on_tick_event(self, identifier: str, event: Payload) -> None:
        """ This event is used to refresh the data related to the Supvisors instance.

        :param identifier: the identifier of the Supvisors instance that sent the event
        :param event: the tick event
        :return:
        """
        if self.context.is_valid(identifier, event['ip_address']):
            # update the Supvisors instance status
            self.context.on_tick_event(identifier, event)

    def on_discovery_event(self, identifier: str, event: Payload) -> None:
        """ This event is used to add new Supvisors instances into the Supvisors system.
        No need to test if the discovery mode is enabled. This is managed in the internal communication layer.

        :param identifier: the identifier of the Supvisors instance that sent the event
        :param event: the discovery event
        :return:
        """
        # When Supvisors is in discovery mode, new Supvisors instances may be added on-the-fly
        if self.context.on_discovery_event(identifier, event):
            self.supvisors.internal_com.pusher.send_connect_instance(identifier)
            # a DEPLOYMENT will be requested if a new Supvisors instance has been inserted
            self.redeploy_mark = True

    def on_process_state_event(self, identifier: str, event: Payload) -> None:
        """ This event is used to refresh the process data related to the event sent from the Supvisors instance.
        This event also triggers the application starter and/or stopper.

        :param identifier: the identifier of the Supvisors instance that sent the event
        :param event: the process event
        :return: None
        """
        process = self.context.on_process_state_event(identifier, event)
        # returned process may be None if the event is linked to an unknown or an isolated instance
        if process:
            # inform starter and stopper
            self.supvisors.starter.on_event(process, identifier)
            self.supvisors.stopper.on_event(process, identifier)
            # trigger an automatic (so master only) behaviour for a running failure
            # process crash triggered only if running failure strategy related to application
            # Supvisors does not replace Supervisor in the present matter (use autorestart if necessary)
            if self.context.is_master and process.crashed():
                # local variables to keep it readable
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

    def on_process_added_event(self, identifier: str, event: Payload) -> None:
        """ This event is used to fill the internal structures when processes have been added on a Supvisors instance.

        :param identifier: the identifier of the Supvisors instance that sent the event
        :param event: the process information
        :return: None
        """
        self.context.load_processes(identifier, [event])

    def on_process_removed_event(self, identifier: str, event: Payload) -> None:
        """ This event is used to fill the internal structures when a process has been added on a Supvisors instance.

        :param identifier: the identifier of the Supvisors instance that sent the event
        :param event: the process identification
        :return: None
        """
        self.context.on_process_removed_event(identifier, event)

    def on_process_disability_event(self, identifier: str, event: Payload) -> None:
        """ This event is used to fill the internal structures when a process has been enabled or disabled
        on a Supvisors instance.

        :param identifier: the identifier of the Supvisors instance that sent the event
        :param event: the process identification
        :return: None
        """
        self.context.on_process_disability_event(identifier, event)

    def on_state_event(self, identifier: str, event: Payload) -> None:
        """ This event is used to get the FSM state of the master Supvisors instance.

        :param identifier: the identifier of the Supvisors instance that sent the event
        :param event: the state event
        :return: None
        """
        self.logger.debug(f'FiniteStateMachine.on_state_event: Supvisors={identifier} sent {event}')
        # WARN: local instance is already up-to-date, could even be a step beyond
        #   so ignore the event if it is a local event
        ref_master = self.context.master_identifier
        ref_supvisors_state = self.context.supvisors_state
        # update the Supvisors instance states and modes
        self.context.on_instance_state_event(identifier, event)
        # check if there has been changes in Master and/or its state
        if ref_master != self.context.master_identifier:
            self.logger.info(f'FiniteStateMachine.on_state_event: new Master Supvisors={self.context.master_identifier}'
                             f' in {self.context.supvisors_state}')
            # if there has been a Master change and the local identifier is involved, the FSM type has to change,
            #   so it is required to go back to INITIALIZATION state
            if self.context.local_identifier in [ref_master, self.context.master_identifier]:
                self.set_state(SupvisorsStates.INITIALIZATION)
        elif ref_supvisors_state != self.context.supvisors_state:
            # the Master has transitioned to another state, so trigger the FSM
            self.next()

    def on_process_info(self, identifier: str, info: PayloadList) -> None:
        """ This event is used to fill the internal structures with processes available on the Supvisors instance.

        :param identifier: the identifier of the Supvisors instance that sent the event
        :param info: the process information
        :return: None
        """
        self.context.load_processes(identifier, info)

    def on_authorization(self, identifier: str, authorized: Optional[bool]) -> None:
        """ This event is used to finalize the port-knocking between Supvisors instances.
        When a new Supvisors instance comes in the group, back to DEPLOYMENT for a possible deployment.

        :param identifier: the identifier of the Supvisors instance that sent the event
        :param authorized: the authorization status as seen by the remote Supvisors instance
        :return: None
        """
        self.logger.debug(f'FiniteStateMachine.on_authorization: identifier={identifier} authorized={authorized}')
        if self.context.on_authorization(identifier, authorized):
            # a new Supvisors instance comes in group
            # a DEPLOYMENT phase is considered as applications could not be fully started due to this missing instance
            # the idea of simply going back to INITIALIZATION is rejected as it would imply a re-synchronization
            if self.context.is_master:
                if self.state in WORKING_STATES:
                    # it may not be relevant to transition directly to DEPLOYMENT from here
                    # the DEPLOYMENT and CONCILIATION states are temporary and pending on actions to be completed
                    # so mark the context to remember that a re-DEPLOYMENT can be considered at OPERATION level
                    self.redeploy_mark = True
                    self.logger.info(f'FiniteStateMachine.on_authorization: new Supvisors={identifier}.'
                                     ' defer re-DEPLOYMENT')

    def on_restart_sequence(self) -> None:
        """ This event is used to transition the state machine to the DEPLOYMENT state.

        :return: None
        """
        if self.context.is_master:
            self.redeploy_mark = Forced
        else:
            # re-route the command to Master
            self.supvisors.internal_com.pusher.send_restart_sequence(self.context.master_identifier)

    def on_restart(self) -> None:
        """ This event is used to transition the state machine to the RESTARTING state.

        :return: None
        """
        if self.context.is_master:
            self.set_state(SupvisorsStates.RESTARTING)
        else:
            if self.context.master_identifier:
                # re-route the command to Master
                self.supvisors.internal_com.pusher.send_restart_all(self.context.master_identifier)
            else:
                message = 'no Master instance to perform the Supvisors restart request'
                self.logger.error(f'FiniteStateMachine.on_restart: {message}')
                raise ValueError(message)

    def on_shutdown(self) -> None:
        """ This event is used to transition the state machine to the SHUTTING_DOWN state.

        :return: None
        """
        if self.context.is_master:
            self.set_state(SupvisorsStates.SHUTTING_DOWN)
        else:
            if self.context.master_identifier:
                # re-route the command to Master
                self.supvisors.internal_com.pusher.send_shutdown_all(self.context.master_identifier)
            else:
                message = 'no Master instance to perform the Supvisors restart request'
                self.logger.error(f'FiniteStateMachine.on_restart: {message}')
                raise ValueError(message)

    def on_end_sync(self, master_identifier: str) -> None:
        """ End the synchronization phase using the given Master or trigger an election.

        :param master_identifier: the identifier of the Master Supvisors instance selected by the user
        :return: None
        """
        if master_identifier:
            self.context.master_identifier = master_identifier
        else:
            self.context.elect_master()
        # re-evaluate the FSM
        self.next()

    # Map between state enumerations and classes
    _MasterStateInstances = {SupvisorsStates.OFF: OffState,
                             SupvisorsStates.INITIALIZATION: InitializationState,
                             SupvisorsStates.DEPLOYMENT: MasterDeploymentState,
                             SupvisorsStates.OPERATION: MasterOperationState,
                             SupvisorsStates.CONCILIATION: MasterConciliationState,
                             SupvisorsStates.RESTARTING: MasterRestartingState,
                             SupvisorsStates.SHUTTING_DOWN: MasterShuttingDownState,
                             SupvisorsStates.FINAL: FinalState}

    _SlaveStateInstances = {SupvisorsStates.OFF: OffState,
                            SupvisorsStates.INITIALIZATION: InitializationState,
                            SupvisorsStates.DEPLOYMENT: SlaveMainState,
                            SupvisorsStates.OPERATION: SlaveMainState,
                            SupvisorsStates.CONCILIATION: SlaveMainState,
                            SupvisorsStates.RESTARTING: SlaveRestartingState,
                            SupvisorsStates.SHUTTING_DOWN: SlaveShuttingDownState,
                            SupvisorsStates.FINAL: FinalState}

    # Transitions allowed between states
    _Transitions = {SupvisorsStates.OFF: [SupvisorsStates.INITIALIZATION],
                    SupvisorsStates.INITIALIZATION: [SupvisorsStates.DEPLOYMENT],
                    SupvisorsStates.DEPLOYMENT: [SupvisorsStates.INITIALIZATION,
                                                 SupvisorsStates.OPERATION,
                                                 SupvisorsStates.RESTARTING,
                                                 SupvisorsStates.SHUTTING_DOWN],
                    SupvisorsStates.OPERATION: [SupvisorsStates.CONCILIATION,
                                                SupvisorsStates.DEPLOYMENT,
                                                SupvisorsStates.INITIALIZATION,
                                                SupvisorsStates.RESTARTING,
                                                SupvisorsStates.SHUTTING_DOWN],
                    SupvisorsStates.CONCILIATION: [SupvisorsStates.OPERATION,
                                                   SupvisorsStates.INITIALIZATION,
                                                   SupvisorsStates.RESTARTING,
                                                   SupvisorsStates.SHUTTING_DOWN],
                    SupvisorsStates.RESTARTING: [SupvisorsStates.FINAL],
                    SupvisorsStates.SHUTTING_DOWN: [SupvisorsStates.FINAL],
                    SupvisorsStates.FINAL: []}
