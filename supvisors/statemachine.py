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
from .strategy import conciliate_conflicts
from .ttypes import SupvisorsInstanceStates, RunningFailureStrategies, SupvisorsStates, Payload, PayloadList


class Forced:
    pass


class AbstractState(object):
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
        self.context = supvisors.context
        self.logger = supvisors.logger
        self.local_identifier = supvisors.supvisors_mapper.local_identifier

    def enter(self) -> None:
        """ Actions performed when entering the state.
        May be redefined in subclasses.

        :return: None
        """

    def next(self) -> Optional[SupvisorsStates]:
        """ Actions performed upon reception of an event.
        May be redefined in subclasses.

        :return: None
        """

    def exit(self) -> None:
        """ Actions performed when leaving the state.
        May be redefined in subclasses.

        :return: None
        """

    def check_instances(self) -> SupvisorsStates:
        """ Check that local and Master Supvisors instances are still RUNNING.
        If their ticks are not received anymore, back to INITIALIZATION state to force a synchronization phase.

        :return: the suggested state if local or Master Supvisors instance is not active anymore
        """
        # FIXME: for local, this cannot happen anymore
        if self.context.instances[self.local_identifier].state != SupvisorsInstanceStates.RUNNING:
            self.logger.critical('AbstractState.check_instances: local Supvisors instance not RUNNING anymore')
            return SupvisorsStates.INITIALIZATION
        if self.context.instances[self.context.master_identifier].state != SupvisorsInstanceStates.RUNNING:
            self.logger.warn('AbstractState.check_instances: Master Supvisors instance not RUNNING anymore')
            return SupvisorsStates.INITIALIZATION

    def abort_jobs(self) -> None:
        """ Abort starting jobs in progress.

        :return: None
        """
        self.supvisors.failure_handler.abort()
        self.supvisors.starter.abort()
        self.supvisors.stopper.abort()


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

    def next(self) -> SupvisorsStates:
        """ Wait for Supvisors instances to publish until:
            - all are active,
            - or all core instances defined in the optional *force_synchro_if* option are active,
            - or timeout is reached.

        :return: the new Supvisors state
        """
        uptime = time() - self.context.start_date
        if uptime > self.supvisors.options.synchro_timeout:
            self.logger.warn('InitializationState.next: synchro timed out')
        # cannot get out of this state without local Supvisors instance RUNNING
        running_identifiers = self.context.running_identifiers()
        if self.local_identifier in running_identifiers:
            # synchro done if the state of all Supvisors instances is known
            if len(self.context.unknown_identifiers()) == 0:
                self.logger.info('InitializationState.next: all Supvisors instances are in a known state')
                return SupvisorsStates.DEPLOYMENT
            # for an end of sync based on a subset of Supvisors instances, cannot get out of this state before
            # SYNCHRO_TIMEOUT_MIN seconds have passed
            # in case of a Supervisor restart, this gives a chance to all Supvisors instances to send their tick
            if uptime > self.supvisors.options.SYNCHRO_TIMEOUT_MIN:
                # check synchro on core instances
                if self.context.running_core_identifiers():
                    # if ok, master must be running if already known
                    if self.context.master_identifier and self.context.master_identifier not in running_identifiers:
                        self.logger.info('InitializationState.next: all core Supvisors instances are RUNNING but not'
                                         f' Master={self.context.master_identifier}')
                        return SupvisorsStates.INITIALIZATION
                    self.logger.info('InitializationState.next: all core Supvisors instances are RUNNING')
                    return SupvisorsStates.DEPLOYMENT
            self.logger.debug('InitializationState.next: still waiting for remote Supvisors instances to publish')
        else:
            self.logger.debug(f'InitializationState.next: local Supvisors={self.local_identifier} still not RUNNING')
        return SupvisorsStates.INITIALIZATION

    def exit(self) -> None:
        """ When leaving the INITIALIZATION state, the working Supvisors instances are defined.
        One of them is elected as the *Master*.

        :return: None
        """
        # force state of missing Supvisors instances
        running_identifiers = self.context.running_identifiers()
        self.logger.info(f'InitializationState.exit: working with Supvisors instances {running_identifiers}')
        # elect master instance among working instances only if not fixed before
        # of course master instance must be running
        self.logger.debug(f'InitializationState.exit: master_identifier={self.context.master_identifier}')
        if not self.context.master_identifier or self.context.master_identifier not in running_identifiers:
            # choose Master among the core instances because these instances are expected to be more stable
            core_identifiers = self.supvisors.supvisors_mapper.core_identifiers
            self.logger.info(f'InitializationState.exit: core_identifiers={core_identifiers}')
            if core_identifiers:
                running_core_identifiers = set(running_identifiers).intersection(core_identifiers)
                if running_core_identifiers:
                    running_identifiers = running_core_identifiers
            # arbitrarily choice : master instance has the 'lowest' identifier among running instances
            self.context.master_identifier = min(running_identifiers)


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
            return SupvisorsStates.RESTART
        # check if stopping jobs are in progress
        if self.supvisors.stopper.in_progress():
            return SupvisorsStates.RESTARTING
        return SupvisorsStates.RESTART


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
            return SupvisorsStates.SHUTDOWN
        # check if stopping jobs are in progress
        if self.supvisors.stopper.in_progress():
            return SupvisorsStates.SHUTTING_DOWN
        return SupvisorsStates.SHUTDOWN


class RestartState(AbstractState):
    """ This is a final state. """

    def enter(self):
        """ When entering the RESTART state, request the full restart. """
        self.supvisors.zmq.pusher.send_restart(self.local_identifier)
        # other instances will shut down on reception of RESTART state


class ShutdownState(AbstractState):
    """ This is the final state. """

    def enter(self):
        """ When entering the SHUTDOWN state, request the Supervisor shutdown. """
        self.supvisors.zmq.pusher.send_shutdown(self.local_identifier)
        # other instances will shut down on reception of SHUTDOWN state


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
        # next state is the Master state
        return self.supvisors.fsm.master_state


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
            return SupvisorsStates.RESTART
        # next state is the Master state
        return self.supvisors.fsm.master_state


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
            return SupvisorsStates.SHUTDOWN
        # next state is the Master state
        return self.supvisors.fsm.master_state


class FiniteStateMachine:
    """ This class implements a very simple behaviour of FiniteStateMachine based on a single event.
    A state is able to evaluate itself for transitions.

    Attributes are:
        - state: the current state of this state machine ;
        - master_state: the state of the Master state machine ;
        - instance: the current state instance ;
        - redeploy_mark: a status telling if a DEPLOYMENT state is pending.
    """

    def __init__(self, supvisors: Any) -> None:
        """ Reset the state machine and the internal context.

        :param supvisors: the Supvisors global structure
        """
        self.supvisors = supvisors
        self.context: Context = supvisors.context
        self.logger: Logger = supvisors.logger
        self.state: Optional[SupvisorsStates] = None
        self.master_state: Optional[SupvisorsStates] = None
        self.instance: AbstractState = AbstractState(supvisors)
        self.redeploy_mark: bool = False
        # Trigger first state / INITIALIZATION
        self.set_state(SupvisorsStates.INITIALIZATION)

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

    def set_state(self, next_state: SupvisorsStates) -> None:
        """ Update the current state of the state machine and transitions as long as possible.
        The transition can be forced, especially when getting the first Master state.

        :param next_state: the new state
        :return: None
        """
        while next_state is not None and next_state != self.state:
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
            self.logger.info(f'FiniteStateMachine.set_state: Supvisors in {self.state.name}')
            # publish the new state
            if self.supvisors.zmq:
                # the zmq does not exist yet for the first occurrence here
                self.supvisors.zmq.pusher.send_state_event(self.serial())
                self.supvisors.zmq.publisher.send_supvisors_status(self.serial())
            # create the new state and enters it
            if self.context.is_master:
                self.instance = self._MasterStateInstances[self.state](self.supvisors)
            else:
                self.instance = self._SlaveStateInstances[self.state](self.supvisors)
            self.instance.enter()
            # evaluate current state
            next_state = self.instance.next()

    def periodic_check(self, event: Payload) -> None:
        """ Periodic task used to check if remote Supvisors instances are still active.
        This is also the main event on this state machine. """
        invalidated_identifiers, process_failures = self.context.on_timer_event(event)
        self.logger.debug(f'FiniteStateMachine.periodic_check: invalidated_identifiers={invalidated_identifiers}'
                          f' process_failures={[process.namespec for process in process_failures]}')
        # inform Starter and Stopper. process_failures may be removed
        if invalidated_identifiers:
            self.supvisors.starter.on_instances_invalidation(invalidated_identifiers, process_failures)
            self.supvisors.stopper.on_instances_invalidation(invalidated_identifiers, process_failures)
        # get invalidated instances / use next / update processes on invalidated instances ?
        self.next()
        # fix failures if any (can happen after an identifier invalidation, a process crash or a conciliation request)
        if self.context.is_master:
            for process in process_failures:
                self.supvisors.failure_handler.add_default_job(process)
            self.supvisors.failure_handler.trigger_jobs()
        # check if new isolating remotes and isolate them at main loop level
        identifiers = self.context.handle_isolation()
        if identifiers:
            self.supvisors.zmq.pusher.send_isolate_instances(identifiers)

    def on_tick_event(self, identifier: str, event: Payload) -> None:
        """ This event is used to refresh the data related to the Supvisors instance.
        If the local instance is updated, perform a global check on all Supvisors instances.

        :param identifier: the identifier of the Supvisors instance that sent the event
        :param event: the tick event
        :return:
        """
        self.context.on_tick_event(identifier, event)
        if identifier == self.instance.local_identifier:
            # trigger periodic check
            self.periodic_check(event)

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
        """ This event is used to fill the internal structures when a process has been added on a Supvisors instance.

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

    def on_state_event(self, identifier: str, event: Payload) -> None:
        """ This event is used to get the FSM state of the master Supvisors instance.

        :param identifier: the identifier of the Supvisors instance that sent the event
        :param event: the state event
        :return: None
        """
        if not self.context.is_master and identifier == self.context.master_identifier:
            master_state = SupvisorsStates(event['statecode'])
            self.logger.info(f'FiniteStateMachine.on_state_event: Master Supvisors={identifier} transitioned'
                             f' to state={master_state}')
            self.master_state = master_state
            # WARN: cannot wait for next tick. There is a chance that the Master transitions goes fast and important
            # actions can be missed in the Slave StateMachine
            # More particularly, if the SHUTTING_DOWN state is missed, the corresponding exit action is not executed
            # and the Supervisor instance will not shut down
            # WARN: do not apply directly the master state as the current Supvisors instance may need to stay in
            # INITIALIZATION state
            self.set_state(self.instance.next())

    def on_process_info(self, identifier: str, info: PayloadList) -> None:
        """ This event is used to fill the internal structures with processes available on the Supvisors instance.

        :param identifier: the identifier of the Supvisors instance that sent the event
        :param info: the process information
        :return: None
        """
        self.context.load_processes(identifier, info)

    def on_authorization(self, identifier: str, authorized: Optional[bool], master_identifier: str,
                         supvisors_state: SupvisorsStates) -> None:
        """ This event is used to finalize the port-knocking between Supvisors instances.
        When a new Supvisors instance comes in the group, back to DEPLOYMENT for a possible deployment.

        :param identifier: the identifier of the Supvisors instance that sent the event
        :param authorized: the authorization status as seen by the remote Supvisors instance
        :param master_identifier: the identifier of the Master instance perceived by the remote Supvisors instance
        :param supvisors_state: the Supvisors state perceived by the remote Supvisors instance
        :return: None
        """
        self.logger.debug(f'FiniteStateMachine.on_authorization: identifier={identifier} authorized={authorized}'
                          f' master_identifier={master_identifier} supvisors_state={supvisors_state}')
        if self.context.on_authorization(identifier, authorized):
            # a new Supvisors instance comes in group
            # a DEPLOYMENT phase is considered as applications could not be fully started due to this missing instance
            # the idea of simply going back to INITIALIZATION is rejected as it would imply a re-synchronization
            if self.context.is_master:
                if self.state in [SupvisorsStates.DEPLOYMENT, SupvisorsStates.OPERATION, SupvisorsStates.CONCILIATION]:
                    # it may not be relevant to transition directly to DEPLOYMENT from here
                    # the DEPLOYMENT and CONCILIATION states are temporary and pending on actions to be completed
                    # so mark the context to remember that a re-DEPLOYMENT can be considered at OPERATION level
                    self.redeploy_mark = True
                    self.logger.info(f'FiniteStateMachine.on_authorization: new Supvisors={identifier}.'
                                     ' defer re-DEPLOYMENT')
            # A Master is known to the newcomer
            if master_identifier:
                if not self.context.master_identifier:
                    # local Supvisors doesn't know about a master yet but remote Supvisors does
                    # typically happen when the local Supervisor has just been started whereas a Supvisors group
                    # was already operating, so accept remote perception
                    self.logger.warn(f'FiniteStateMachine.on_authorization: accept Master={master_identifier}'
                                     f' declared by Supvisors={identifier}')
                    self.context.master_identifier = master_identifier
                if master_identifier != self.context.master_identifier:
                    # 2 different perceptions of the master, likely due to a split-brain situation
                    # so going back to INITIALIZATION to fix
                    self.logger.warn('FiniteStateMachine.on_authorization: Master instance conflict. '
                                     f' Local declares {self.context.master_identifier}'
                                     f' - Supvisors={identifier} declares Master={master_identifier}')
                    # no need to restrict to [DEPLOYMENT, OPERATION, CONCILIATION] as other transitions are forbidden
                    self.set_state(SupvisorsStates.INITIALIZATION)
                elif master_identifier == identifier:
                    # accept the remote Master state provided by the Master
                    self.logger.info(f'FiniteStateMachine.on_authorization: Master={identifier} is in'
                                     f' state={supvisors_state.name}')
                    self.master_state = supvisors_state
                    self.set_state(self.instance.next())

    def on_restart_sequence(self) -> None:
        """ This event is used to transition the state machine to the DEPLOYMENT state.

        :return: None
        """
        if self.context.is_master:
            self.redeploy_mark = Forced
        else:
            # re-route the command to Master
            self.supvisors.zmq.pusher.send_restart_sequence(self.context.master_identifier)

    def on_restart(self) -> None:
        """ This event is used to transition the state machine to the RESTARTING state.

        :return: None
        """
        if self.context.is_master:
            self.set_state(SupvisorsStates.RESTARTING)
        else:
            # re-route the command to Master
            self.supvisors.zmq.pusher.send_restart_all(self.context.master_identifier)

    def on_shutdown(self) -> None:
        """ This event is used to transition the state machine to the SHUTTING_DOWN state.

        :return: None
        """
        if self.context.is_master:
            self.set_state(SupvisorsStates.SHUTTING_DOWN)
        else:
            # re-route the command to Master
            self.supvisors.zmq.pusher.send_shutdown_all(self.context.master_identifier)

    # serialization
    def serial(self) -> Payload:
        """ Return a serializable form of the SupvisorsState.

        :return: the Supvisors state as a dictionary
        """
        return {'statecode': self.state.value, 'statename': self.state.name}

    # Map between state enumerations and classes
    _MasterStateInstances = {SupvisorsStates.INITIALIZATION: InitializationState,
                             SupvisorsStates.DEPLOYMENT: MasterDeploymentState,
                             SupvisorsStates.OPERATION: MasterOperationState,
                             SupvisorsStates.CONCILIATION: MasterConciliationState,
                             SupvisorsStates.RESTARTING: MasterRestartingState,
                             SupvisorsStates.RESTART: RestartState,
                             SupvisorsStates.SHUTTING_DOWN: MasterShuttingDownState,
                             SupvisorsStates.SHUTDOWN: ShutdownState}

    _SlaveStateInstances = {SupvisorsStates.INITIALIZATION: InitializationState,
                            SupvisorsStates.DEPLOYMENT: SlaveMainState,
                            SupvisorsStates.OPERATION: SlaveMainState,
                            SupvisorsStates.CONCILIATION: SlaveMainState,
                            SupvisorsStates.RESTARTING: SlaveRestartingState,
                            SupvisorsStates.RESTART: RestartState,
                            SupvisorsStates.SHUTTING_DOWN: SlaveShuttingDownState,
                            SupvisorsStates.SHUTDOWN: ShutdownState}

    _Transitions = {None: [SupvisorsStates.INITIALIZATION],
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
                    SupvisorsStates.RESTARTING: [SupvisorsStates.RESTART],
                    SupvisorsStates.RESTART: [],
                    SupvisorsStates.SHUTTING_DOWN: [SupvisorsStates.SHUTDOWN],
                    SupvisorsStates.SHUTDOWN: []}
    # Transitions allowed between states
