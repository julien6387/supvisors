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
from .ttypes import AddressStates, RunningFailureStrategies, SupvisorsStates, NameList, Payload, PayloadList


class AbstractState(object):
    """ Base class for a state with simple entry / next / exit actions.

    Attributes are:
        - supvisors: the reference to the global Supvisors structure,
        - address_name: the name of the local node.
     """

    def __init__(self, supvisors: Any) -> None:
        """ Initialization of the attributes.

        :param supvisors: the global Supvisors structure
        """
        self.supvisors = supvisors
        self.context = supvisors.context
        self.logger = supvisors.logger
        self.local_node_name = supvisors.address_mapper.local_node_name

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

    def check_nodes(self) -> SupvisorsStates:
        """ Check that local and Master nodes are still RUNNING.
        If their ticks are not received anymore, back to INITIALIZATION state to force a synchronization phase.

        :return: the suggested state if local or Master node is not active anymore
        """
        if self.context.nodes[self.local_node_name].state != AddressStates.RUNNING:
            self.logger.critical('AbstractState.check_nodes: local node not RUNNING anymore')
            return SupvisorsStates.INITIALIZATION
        if self.context.nodes[self.context.master_node_name].state != AddressStates.RUNNING:
            self.logger.warn('AbstractState.check_nodes: Master node not RUNNING anymore')
            return SupvisorsStates.INITIALIZATION

    def abort_jobs(self) -> None:
        """ Abort starting jobs in progress.

        :return: None
        """
        self.supvisors.failure_handler.abort()
        self.supvisors.starter.abort()


class InitializationState(AbstractState):
    """ In the INITIALIZATION state, Supvisors synchronizes to all known instances.

    Attributes are:
        - start_date: the date when entering this state.
    """

    def enter(self) -> None:
        """ When entering in the INITIALIZATION state, reset the context.

        :return: None
        """
        # clear any existing job
        self.abort_jobs()
        # reset context, keeping the isolation status
        self.context.reset()

    def next(self) -> SupvisorsStates:
        """ Wait for nodes to publish until:
            - all are active,
            - or all core nodes defined in the optional *force_synchro_if* option are active,
            - or timeout is reached.

        :return: the new Supvisors state
        """
        uptime = time() - self.context.start_date
        if uptime > self.supvisors.options.synchro_timeout:
            self.logger.warn('InitializationState.next: synchro timed out')
        # cannot get out of this state without local node RUNNING
        running_nodes = self.context.running_nodes()
        if self.local_node_name in running_nodes:
            # synchro done if the state of all nodes is known
            if len(self.context.unknown_nodes()) == 0:
                self.logger.info('InitializationState.next: all nodes are in a known state')
                return SupvisorsStates.DEPLOYMENT
            # for a partial end of sync, cannot get out of this state SYNCHRO_TIMEOUT_MIN
            # in case of a Supervisor restart, this gives a chance to all nodes to send their tick
            if uptime > self.supvisors.options.SYNCHRO_TIMEOUT_MIN:
                # check synchro on core nodes
                if self.context.running_core_nodes():
                    # if ok, master must be running if already known
                    if self.context.master_node_name and self.context.master_node_name not in running_nodes:
                        self.logger.info('InitializationState.next: all core nodes are RUNNING but not Master={}'
                                         .format(self.context.master_node_name))
                        return SupvisorsStates.INITIALIZATION
                    self.logger.info('InitializationState.next: all core nodes are RUNNING')
                    return SupvisorsStates.DEPLOYMENT
            self.logger.debug('InitializationState.next: still waiting for remote Supvisors instances to publish')
        else:
            self.logger.debug('InitializationState.next: local node {} still not RUNNING'.format(self.local_node_name))
        return SupvisorsStates.INITIALIZATION

    def exit(self) -> None:
        """ When leaving the INITIALIZATION state, the working nodes are defined.
        One of them is elected as the MASTER.

        :return: None
        """
        # force state of missing Supvisors instances
        node_names = self.context.running_nodes()
        self.logger.info('InitializationState.exit: working with nodes {}'.format(node_names))
        # elect master node among working nodes only if not fixed before
        # of course master node must be running
        if not self.context.master_node_name or self.context.master_node_name not in node_names:
            # choose Master among the core nodes because these nodes are expected to be more present
            if self.supvisors.options.force_synchro_if:
                running_core_node_names = set(node_names).intersection(self.supvisors.options.force_synchro_if)
                if running_core_node_names:
                    node_names = running_core_node_names
            # arbitrarily choice : master node has the 'lowest' node_name among running nodes
            self.context.master_node_name = min(node_names)


class MasterDeploymentState(AbstractState):
    """ In the DEPLOYMENT state, Supvisors starts automatically the applications having a starting model. """

    def enter(self):
        """ Trigger the automatic start and stop. """
        self.supvisors.fsm.redeploy_mark = False
        self.supvisors.starter.start_applications()

    def next(self) -> SupvisorsStates:
        """ Check if the starting tasks are completed.

        :return: the new Supvisors state
        """
        # common check on local and Master nodes
        next_state = self.check_nodes()
        if next_state:
            return next_state
        # Master goes to OPERATION when starting is completed
        if self.supvisors.starter.is_starting_completed():
            return SupvisorsStates.OPERATION
        # stay in current state
        return SupvisorsStates.DEPLOYMENT


class MasterOperationState(AbstractState):
    """ In the OPERATION state, Supvisors is waiting for requests. """

    def next(self) -> SupvisorsStates:
        """ Check that all nodes are still active.
        Look after possible conflicts due to multiple running instances of the same program. """
        # common check on local and Master nodes
        next_state = self.check_nodes()
        if next_state:
            return next_state
        # normal behavior. check if jobs in progress
        if self.supvisors.starter.is_starting_completed() and self.supvisors.stopper.is_stopping_completed():
            # check duplicated processes
            if self.context.conflicting():
                return SupvisorsStates.CONCILIATION
            # a redeploy mark has set due to a new node in Supvisors
            # back to DEPLOYMENT state to repair what may have failed before
            if self.supvisors.fsm.redeploy_mark:
                return SupvisorsStates.DEPLOYMENT
        return SupvisorsStates.OPERATION


class MasterConciliationState(AbstractState):
    """ In the CONCILIATION state, Supvisors conciliates the conflicts. """

    def enter(self) -> None:
        """ When entering in the CONCILIATION state, conciliate automatically the conflicts. """
        conciliate_conflicts(self.supvisors,
                             self.supvisors.options.conciliation_strategy,
                             self.context.conflicts())

    def next(self) -> SupvisorsStates:
        """ Check that all addresses are still active.
        Wait for all conflicts to be conciliated. """
        # common check on local and Master nodes
        next_state = self.check_nodes()
        if next_state:
            return next_state
        # check eventual jobs in progress
        if self.supvisors.starter.is_starting_completed() and self.supvisors.stopper.is_stopping_completed():
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
        """ When entering in the RESTARTING state, stop all applications.
        The current design is that the current node drives the job and not necessarily the Master.

        :return: None
        """
        self.abort_jobs()
        self.supvisors.stopper.stop_applications()

    def next(self) -> SupvisorsStates:
        """ Wait for all processes to be stopped. """
        next_state = self.check_nodes()
        if next_state:
            # no way going back to INITIALIZATION state at this point
            return SupvisorsStates.SHUTDOWN
        if self.supvisors.stopper.is_stopping_completed():
            return SupvisorsStates.SHUTDOWN
        return SupvisorsStates.RESTARTING

    def exit(self) -> None:
        """ When leaving the RESTARTING state, request the full restart. """
        self.supvisors.zmq.pusher.send_restart(self.local_node_name)
        # other nodes will shutdown on reception of SHUTDOWN state
        # due to Supvisors design, the state publication will be fired before the send_shutdown


class MasterShuttingDownState(AbstractState):
    """ In the SHUTTING_DOWN state, Supvisors stops all applications before triggering a full shutdown. """

    def enter(self):
        """ When entering in the SHUTTING_DOWN state, stop all applications. """
        self.abort_jobs()
        self.supvisors.stopper.stop_applications()

    def next(self):
        """ Wait for all processes to be stopped. """
        # check eventual jobs in progress
        next_state = self.check_nodes()
        if next_state:
            # no way going back to INITIALIZATION state at this point
            return SupvisorsStates.SHUTDOWN
        if self.supvisors.stopper.is_stopping_completed():
            return SupvisorsStates.SHUTDOWN
        return SupvisorsStates.SHUTTING_DOWN

    def exit(self):
        """ When leaving the SHUTTING_DOWN state, request the Supervisor shutdown. """
        self.supvisors.zmq.pusher.send_shutdown(self.local_node_name)
        # other nodes will shutdown on reception of SHUTDOWN state
        # due to Supvisors design, the state publication will be fired before the send_shutdown


class ShutdownState(AbstractState):
    """ This is the final state. """


class SlaveMainState(AbstractState):

    def next(self) -> SupvisorsStates:
        """ the non-master instances are just checking if local and Master instances are still running.

        :return: the next state
        """
        # common check on local and Master nodes
        next_state = self.check_nodes()
        if next_state:
            return next_state


class SlaveRestartingState(AbstractState):
    """ In the RESTARTING state, Supvisors stops all applications before triggering a full restart. """

    def enter(self) -> None:
        """ When entering in the RESTARTING state, abort all pending tasks applications.

        :return: None
        """
        self.abort_jobs()

    def next(self) -> SupvisorsStates:
        """ Wait for all processes to be stopped. """
        next_state = self.check_nodes()
        if next_state:
            # no way going back to INITIALIZATION state at this point
            return SupvisorsStates.SHUTDOWN

    def exit(self) -> None:
        """ When leaving the RESTARTING state, request the Supervisor restart. """
        self.supvisors.zmq.pusher.send_restart(self.local_node_name)


class SlaveShuttingDownState(SlaveRestartingState):
    """ In the SHUTTING_DOWN state, Supvisors stops all applications before triggering a full shutdown.
    Only the exit actions are different from the RESTARTING state.
    """

    def exit(self) -> None:
        """ When leaving the SHUTTING_DOWN state, request the Supervisor shutdown. """
        self.supvisors.zmq.pusher.send_shutdown(self.local_node_name)


class FiniteStateMachine:
    """ This class implements a very simple behaviour of FiniteStateMachine based on a single event.
    A state is able to evaluate itself for transitions. """

    def __init__(self, supvisors: Any) -> None:
        """ Reset the state machine and the internal context.

        :param supvisors: the Supvisors global structure
        """
        self.supvisors = supvisors
        self.context: Context = supvisors.context
        self.logger: Logger = supvisors.logger
        self.state: Optional[SupvisorsStates] = None
        self.instance: AbstractState = AbstractState(supvisors)
        self.redeploy_mark: bool = False
        # Trigger first state / INITIALIZATION
        self.set_state(SupvisorsStates.INITIALIZATION)

    def next(self) -> None:
        """ Send the event to the state and transitions if possible.
        The state machine re-sends the event as long as it transitions.

        :return: None
        """
        self.set_state(self.instance.next())

    def set_state(self, next_state: SupvisorsStates, force_transition: bool = None) -> None:
        """ Update the current state of the state machine and transitions as long as possible.
        The transition can be forced, especially when getting the first Master state.

        :param next_state: the new state
        :param force_transition: if True, transition validity is not checked
        :return: None
        """
        while next_state is not None and next_state != self.state:
            # check that the transition is allowed
            if not force_transition and next_state not in self._Transitions[self.state]:
                self.logger.critical('FiniteStateMachine.set_state: unexpected transition from {} to {}'
                                     .format(self.state, next_state))
                break
            # exit the current state
            self.instance.exit()
            # assign the new state and publish SupvisorsStatus event internally and externally
            self.state = next_state
            self.logger.info('FiniteStateMachine.set_state: Supvisors in {}'.format(self.state.name))
            if self.supvisors.zmq:
                # the zmq does not exist yet for the first occurrence here
                self.supvisors.zmq.internal_publisher.send_state_event(self.serial())
                self.supvisors.zmq.publisher.send_supvisors_status(self.serial())
            # create the new state and enters it
            if self.context.is_master:
                self.instance = self._MasterStateInstances[self.state](self.supvisors)
            else:
                self.instance = self._SlaveStateInstances[self.state](self.supvisors)
            self.instance.enter()
            # evaluate current state
            next_state = self.instance.next()

    def on_timer_event(self) -> NameList:
        """ Periodic task used to check if remote Supvisors instances are still active.
        This is also the main event on this state machine. """
        process_failures = self.context.on_timer_event()
        self.logger.debug('FiniteStateMachine.on_timer_event: process_failures={}'.format(process_failures))
        # get invalidated nodes / use next / update processes on invalidated nodes ?
        self.next()
        # fix failures if any (can happen after a node invalidation, a process crash or a conciliation request)
        if self.context.is_master:
            for process in process_failures:
                self.supvisors.failure_handler.add_default_job(process)
            self.supvisors.failure_handler.trigger_jobs()
        # check if new isolating remotes and return the list of newly isolated nodes
        return self.context.handle_isolation()

    def on_tick_event(self, node_name: str, event: Payload):
        """ This event is used to refresh the data related to the address. """
        self.context.on_tick_event(node_name, event)

    def on_process_event(self, node_name: str, event: Payload) -> None:
        """ This event is used to refresh the process data related to the event and address.
        This event also triggers the application starter and/or stopper.

        :param node_name: the node that sent the event
        :param event: the process event
        :return: None
        """
        process = self.context.on_process_event(node_name, event)
        # returned process may be None if the event is linked to an unknown or an isolated node
        if process:
            # feed starter with event
            self.supvisors.starter.on_event(process)
            # feed stopper with event
            self.supvisors.stopper.on_event(process)
            # trigger an automatic (so master only) behaviour for a running failure
            # process crash triggered only if running failure strategy related to application
            # Supvisors does not replace Supervisor in the present matter (use autorestart if necessary)
            if self.context.is_master and process.crashed():
                # local variables to keep it readable
                strategy = process.rules.running_failure_strategy
                stop_strategy = strategy == RunningFailureStrategies.STOP_APPLICATION
                restart_strategy = strategy == RunningFailureStrategies.RESTART_APPLICATION
                # to avoid infinite application restart, exclude the case where process state is forced
                # indeed the process state forced to FATAL can only happen during a starting sequence (no node found)
                # retry is useless
                if stop_strategy or restart_strategy and process.forced_state is None:
                    self.supvisors.failure_handler.add_default_job(process)

    def on_state_event(self, node_name, event: Payload) -> None:
        """ This event is used to get the FSM state of the master node.

        :param node_name: the node that sent the event
        :param event: the state event
        :return: None
        """
        if not self.context.is_master and node_name == self.context.master_node_name:
            master_state = SupvisorsStates(event['statecode'])
            self.logger.info('FiniteStateMachine.on_state_event: Master node_name={} transitioned to state={}'
                             .format(node_name, master_state))
            self.set_state(master_state)

    def on_process_info(self, node_name: str, info: PayloadList) -> None:
        """ This event is used to fill the internal structures with processes available on node.

        :param node_name: the node that sent the event
        :param info: the process information
        :return: None
        """
        self.context.load_processes(node_name, info)

    def on_authorization(self, node_name: str, authorized: bool, master_node_name: str,
                         supvisors_state: SupvisorsStates) -> None:
        """ This event is used to finalize the port-knocking between Supvisors instances.
        When a new node comes in the group, back to DEPLOYMENT for a possible deployment.

        :param node_name: the node name from which the event comes
        :param authorized: the authorization status as seen by the remote node
        :param master_node_name: the master node perceived by the remote node
        :param supvisors_state: the Supvisors state perceived by the remote node
        :return: None
        """
        self.logger.info('FiniteStateMachine.on_authorization: node_name={} authorized={} master_node_name={}'
                         ' supvisors_state={}'.format(node_name, authorized, master_node_name, supvisors_state))
        if self.context.on_authorization(node_name, authorized):
            # a new node comes in group
            # a DEPLOYMENT phase is considered as applications could not be fully started due to this missing node
            # the idea of simply going back to INITIALIZATION is rejected as it would imply a re-synchronization
            if self.context.is_master:
                if self.state in [SupvisorsStates.DEPLOYMENT, SupvisorsStates.OPERATION, SupvisorsStates.CONCILIATION]:
                    # it may not be relevant to transition directly to DEPLOYMENT from here
                    # the DEPLOYMENT and CONCILIATION states are temporary and pending on actions to be completed
                    # so mark the context to remember that a re-DEPLOYMENT can be considered at OPERATION level
                    self.redeploy_mark = True
                    self.logger.info('FiniteStateMachine.on_authorization: new node={}. defer re-DEPLOYMENT'
                                     .format(node_name))
            if master_node_name:
                if not self.context.master_node_name:
                    # local Supvisors doesn't know about a master yet but remote Supvisors does
                    # typically happens when the local Supervisor has just been started whereas a Supvisors group
                    # was already operating, so accept remote perception
                    self.logger.warn('FiniteStateMachine.on_authorization: accept master_node={} declared by node={}'
                                     .format(master_node_name, node_name))
                    self.context.master_node_name = master_node_name
                if master_node_name != self.context.master_node_name:
                    # 2 different perceptions of the master, likely due to a split-brain situation
                    # so going back to INITIALIZATION to fix
                    self.logger.warn('FiniteStateMachine.on_authorization: master node conflict. '
                                     ' local declares {} - remote ({}) declares {}'
                                     .format(self.context.master_node_name, node_name, master_node_name))
                    # no need to restrict to [DEPLOYMENT, OPERATION, CONCILIATION] as other transitions are forbidden
                    self.set_state(SupvisorsStates.INITIALIZATION)
                elif master_node_name == node_name:
                    # accept the remote Master state
                    # FIXME: not possible as long as local node itself is not authorized !
                    self.logger.info('FiniteStateMachine.on_authorization: Master node_name={} is in state={}'
                                     .format(node_name, supvisors_state))
                    self.set_state(supvisors_state, True)

    def on_restart(self) -> None:
        """ This event is used to transition the state machine to the RESTARTING state.

        :return: None
        """
        if self.context.is_master:
            self.set_state(SupvisorsStates.RESTARTING)
        else:
            # re-route command to Master
            self.supvisors.zmq.pusher.send_restart_all(self.context.master_node_name)

    def on_shutdown(self) -> None:
        """ This event is used to transition the state machine to the SHUTTING_DOWN state.

        :return: None
        """
        if self.context.is_master:
            self.set_state(SupvisorsStates.SHUTTING_DOWN)
        else:
            # re-route command to Master
            self.supvisors.zmq.pusher.send_shutdown_all(self.context.master_node_name)

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
                             SupvisorsStates.SHUTTING_DOWN: MasterShuttingDownState,
                             SupvisorsStates.SHUTDOWN: ShutdownState}

    _SlaveStateInstances = {SupvisorsStates.INITIALIZATION: InitializationState,
                            SupvisorsStates.DEPLOYMENT: SlaveMainState,
                            SupvisorsStates.OPERATION: SlaveMainState,
                            SupvisorsStates.CONCILIATION: SlaveMainState,
                            SupvisorsStates.RESTARTING: SlaveRestartingState,
                            SupvisorsStates.SHUTTING_DOWN: SlaveShuttingDownState,
                            SupvisorsStates.SHUTDOWN: ShutdownState}

    # Transitions allowed between states
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
                    SupvisorsStates.RESTARTING: [SupvisorsStates.SHUTDOWN],
                    SupvisorsStates.SHUTTING_DOWN: [SupvisorsStates.SHUTDOWN],
                    SupvisorsStates.SHUTDOWN: []}
