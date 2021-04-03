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
from typing import Any, Callable

from supvisors.strategy import conciliate_conflicts
from supvisors.ttypes import AddressStates, SupvisorsStates, NodeNameList, Payload
from supvisors.utils import supvisors_shortcuts


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
        supvisors_shortcuts(self, ['context', 'failure_handler', 'logger', 'options',
                                   'starter', 'stopper'])
        self.address_name = supvisors.address_mapper.local_address

    def enter(self) -> None:
        """ Actions performed when entering the state.
        May be redefined in subclasses.

        :return: None
        """

    def next(self) -> None:
        """ Actions performed upon reception of an event.
        May be redefined in subclasses.

        :return: None
        """

    def exit(self) -> None:
        """ Actions performed when leaving the state.
        May be redefined in subclasses.

        :return: None
        """

    def apply_addresses_func(self, func: Callable[[str], None]) -> None:
        """ Perform the action func on all addresses.
        The local address is the last to be performed.

        :param func: the function callable using a node name as parameter
        :return: None
        """
        # send func request to all locals (but self address)
        for status in self.context.addresses.values():
            if status.address_name != self.address_name:
                if status.state == AddressStates.RUNNING:
                    func(status.address_name)
                    self.logger.warn('supervisord {} on {}'.format(func.__name__, status.address_name))
                else:
                    self.logger.info('cannot {} supervisord on {}: Remote state is {}'
                                     .format(func.__name__, status.address_name, status.state.name))
        # send request to self supervisord
        func(self.address_name)


class InitializationState(AbstractState):
    """ In the INITIALIZATION state, Supvisors synchronizes to all known instances.

    Attributes are:
        - start_date: the date when entering this state.
    """

    def __init__(self, supvisors: Any):
        """ Initialization of the attributes.

        :param supvisors: the global Supvisors structure
        """
        AbstractState.__init__(self, supvisors)
        self.start_date = 0

    def enter(self) -> None:
        """ When entering in the INITIALIZATION state, reset the status of addresses.

        :return: None
        """
        self.context.master_node_name = ''
        self.start_date = int(time())
        # clear any existing job
        self.failure_handler.clear_jobs()
        # re-init addresses that are not isolated
        for status in self.context.addresses.values():
            if not status.in_isolation():
                # do NOT use state setter as transition may be rejected
                status._state = AddressStates.UNKNOWN

    def next(self) -> SupvisorsStates:
        """ Wait for nodes to publish until:
            - all are active,
            - or all defined in the optional *force_synchro_if* option are active,
            - or timeout is reached.

        :return: the new Supvisors state
        """
        # cannot get out of this state without local supervisor RUNNING
        addresses = self.context.running_addresses()
        if self.address_name in addresses:
            # synchro done if the state of all nodes is known
            if len(self.context.unknown_addresses()) == 0:
                self.logger.info('InitializationState.next: all nodes are RUNNING')
                return SupvisorsStates.DEPLOYMENT
            # synchro done if the state of all forced nodes is known
            if self.context.forced_addresses and len(self.context.unknown_forced_addresses()) == 0:
                self.logger.info('InitializationState.next: all forced nodes are RUNNING')
                return SupvisorsStates.DEPLOYMENT
            # if synchro timeout reached, stop synchro and work with known nodes
            if (time() - self.start_date) > self.supvisors.options.synchro_timeout:
                self.logger.warn('InitializationState.next: synchro timed out')
                return SupvisorsStates.DEPLOYMENT
            self.logger.debug('InitializationState.next: still waiting for remote Supvisors instances to publish')
        else:
            self.logger.debug('InitializationState.next: local node {} still not RUNNING'.format(self.address_name))
        return SupvisorsStates.INITIALIZATION

    def exit(self) -> None:
        """ When leaving the INITIALIZATION state, the working nodes are defined.
        One of them is elected as the MASTER.

        :return: None
        """
        # force state of missing Supvisors instances
        self.context.end_synchro()
        # arbitrarily choice : master address is the 'lowest' address among running addresses
        nodes = self.context.running_addresses()
        self.logger.info('InitializationState.exit: working with nodes {}'.format(nodes))
        # elect master node among working nodes only if not fixed before
        if not self.context.master_node_name:
            self.context.master_node_name = min(nodes)


class DeploymentState(AbstractState):
    """ In the DEPLOYMENT state, Supvisors starts automatically the applications having a starting model. """

    def enter(self):
        """ When entering in the DEPLOYMENT state, define the start and stop sequences.
        Only the MASTER can perform the automatic start and stop. """
        for application in self.context.applications.values():
            application.update_sequences()
            application.update_status()
        # only the Supvisors master starts applications
        if self.context.is_master:
            self.starter.start_applications()

    def next(self) -> SupvisorsStates:
        """ 2 conditions to exit the state:
            - local is master and starting sequence is over,
            - local is not master and the master node has declared itself operational.

        :return: the new Supvisors state
        """
        if self.context.is_master and self.starter.check_starting() \
                or not self.context.is_master and self.context.master_operational:
            return SupvisorsStates.OPERATION
        return SupvisorsStates.DEPLOYMENT


class OperationState(AbstractState):
    """ In the OPERATION state, Supvisors is waiting for requests. """

    def enter(self) -> None:
        """ When entering in the OPERATION state, the master notifies all other Supvisors instances,
        so that themselves enter in OPERATION state.

        :return: None
        """
        self.context.master_operational = True

    def next(self) -> SupvisorsStates:
        """ Check that all addresses are still active.
        Look after possible conflicts due to multiple running instances of the same program. """
        # check eventual jobs in progress
        if self.starter.check_starting() and self.stopper.check_stopping():
            # check if master and local are still RUNNING
            if self.context.addresses[self.address_name].state != AddressStates.RUNNING:
                return SupvisorsStates.INITIALIZATION
            if self.context.addresses[self.context.master_node_name].state != AddressStates.RUNNING:
                return SupvisorsStates.INITIALIZATION
            # check duplicated processes
            if self.context.conflicting():
                return SupvisorsStates.CONCILIATION
        return SupvisorsStates.OPERATION


class ConciliationState(AbstractState):
    """ In the CONCILIATION state, Supvisors conciliates the conflicts. """

    def enter(self) -> None:
        """ When entering in the CONCILIATION state, conciliate automatically the conflicts.
        Only the MASTER can conciliate conflicts. """
        if self.context.is_master:
            conciliate_conflicts(self.supvisors,
                                 self.supvisors.options.conciliation_strategy,
                                 self.context.conflicts())

    def next(self) -> SupvisorsStates:
        """ Check that all addresses are still active.
        Wait for all conflicts to be conciliated. """
        # check eventual jobs in progress
        if self.starter.check_starting() and self.stopper.check_stopping():
            # check if master and local are still RUNNING
            if self.context.addresses[self.address_name].state != AddressStates.RUNNING:
                return SupvisorsStates.INITIALIZATION
            if self.context.addresses[self.context.master_node_name].state != AddressStates.RUNNING:
                return SupvisorsStates.INITIALIZATION
            # back to OPERATION when there is no conflict anymore
            if not self.context.conflicting():
                if self.context.is_master or self.context.master_operational:
                    return SupvisorsStates.OPERATION
            # new conflicts may happen while conciliation is in progress
            # call enter again to trigger a new conciliation
            self.enter()
        return SupvisorsStates.CONCILIATION


class RestartingState(AbstractState):
    """ In the RESTARTING state, Supvisors stops all applications before triggering a full restart. """

    def enter(self) -> None:
        """ When entering in the RESTARTING state, stop all applications. """
        self.failure_handler.clear_jobs()
        self.starter.abort()
        self.stopper.stop_applications()

    def next(self) -> SupvisorsStates:
        """ Wait for all processes to be stopped. """
        # check eventual jobs in progress
        if self.stopper.check_stopping():
            return SupvisorsStates.SHUTDOWN
        return SupvisorsStates.RESTARTING

    def exit(self) -> None:
        """ When leaving the RESTARTING state, request the full restart. """
        self.apply_addresses_func(self.supvisors.zmq.pusher.send_restart)


class ShuttingDownState(AbstractState):
    """ In the SHUTTING_DOWN state, Supvisors stops all applications before triggering a full shutdown. """

    def enter(self):
        """ When entering in the SHUTTING_DOWN state, stop all applications. """
        self.failure_handler.clear_jobs()
        self.starter.abort()
        self.stopper.stop_applications()

    def next(self):
        """ Wait for all processes to be stopped. """
        # check eventual jobs in progress
        if self.stopper.check_stopping():
            return SupvisorsStates.SHUTDOWN
        return SupvisorsStates.SHUTTING_DOWN

    def exit(self):
        """ When leaving the SHUTTING_DOWN state, request the full shutdown. """
        self.apply_addresses_func(self.supvisors.zmq.pusher.send_shutdown)


class ShutdownState(AbstractState):
    """ This is the final state. """


class FiniteStateMachine:
    """ This class implements a very simple behaviour of FiniteStateMachine based on a single event.
    A state is able to evaluate itself for transitions. """

    def __init__(self, supvisors: Any) -> None:
        """ Reset the state machine and the internal context.

        :param supvisors: the Supvisors global structure
        """
        self.supvisors = supvisors
        supvisors_shortcuts(self, ['context', 'failure_handler', 'starter', 'stopper', 'logger'])
        self.state = None
        self.instance = AbstractState(self.supvisors)
        # Trigger first state / INITIALIZATION
        self.set_state(SupvisorsStates.INITIALIZATION)

    def next(self) -> None:
        """ Send the event to the state and transitions if possible.
        The state machine re-sends the event as long as it transitions.

        :return: None
        """
        self.set_state(self.instance.next())

    def set_state(self, next_state: SupvisorsStates) -> None:
        """ Update the current state of the state machine and transitions as long as possible.

        :param next_state: the new state
        :return: None
        """
        while next_state != self.state and next_state in self.__Transitions[self.state]:
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
            self.instance = self.__StateInstances[self.state](self.supvisors)
            self.instance.enter()
            # evaluate current state
            next_state = self.instance.next()

    def on_timer_event(self) -> NodeNameList:
        """ Periodic task used to check if remote Supvisors instances are still active.
        This is also the main event on this state machine. """
        self.context.on_timer_event()
        self.next()
        # fix failures if any (can happen after a node invalidation, a process crash or a conciliation request)
        self.failure_handler.trigger_jobs()
        # check if new isolating remotes and return the list of newly isolated addresses
        # TODO: create an internal event to confirm that socket has been disconnected ?
        return self.context.handle_isolation()

    def on_tick_event(self, node_name: str, event: Payload):
        """ This event is used to refresh the data related to the address. """
        self.context.on_tick_event(node_name, event)
        # could call the same behaviour as on_timer_event if necessary

    def on_process_event(self, node_name: str, event: Payload) -> None:
        """ This event is used to refresh the process data related to the event and address.
        This event also triggers the application starter and/or stopper.

        :param node_name: the node that sent the event
        :param event: the process event
        :return: None
        """
        process = self.context.on_process_event(node_name, event)
        if process:
            # check if event is related to a starting or stopping application
            starting = self.starter.has_application(process.application_name)
            stopping = self.stopper.has_application(process.application_name)
            # feed starter with event
            self.starter.on_event(process)
            # feed stopper with event
            self.stopper.on_event(process)
            # only the master is allowed to trigger an automatic behaviour for a running failure
            if self.context.is_master and process.crashed() and not (starting or stopping):
                self.failure_handler.add_default_job(process)
                self.failure_handler.trigger_jobs()

    def on_state_event(self, node_name, event: Payload) -> None:
        """ This event is used to get te operational state of the master node.

        :param node_name: the node that sent the event
        :param event: the state event
        :return: None
        """
        if node_name == self.context.master_node_name:
            self.context.master_operational = SupvisorsStates(event['statecode']) == SupvisorsStates.OPERATION

    def on_process_info(self, node_name: str, info: Payload) -> None:
        """ This event is used to fill the internal structures with processes available on node.

        :param node_name: the node that sent the event
        :param info: the process information
        :return: None
        """
        self.context.load_processes(node_name, info)

    def on_authorization(self, node_name: str, authorized: bool, master_node_name: str,
                         supvisors_state: SupvisorsStates) -> None:
        """ This event is used to finalize the port-knocking between Supvisors instances.
        When a new node that has not be part of Supvisors comes in the group, back to INITIALIZATION
        for a new Master election and a possible deployment

        :param node_name: the node name from which the event comes
        :param authorized: the authorization status as seen by the remote node
        :param master_node_name: the master node perceived by the remote node
        :param supvisors_state: the Supvisors state perceived by the remote node
        :return: None
        """
        self.logger.info('FiniteStateMachine.on_authorization: node_name={} authorized={} master_node_name={}'
                         .format(node_name, authorized, master_node_name, supvisors_state))
        if self.context.on_authorization(node_name, authorized):
            if master_node_name:
                if not self.context.master_node_name:
                    # local Supvisors doesn't know about a master yet but remote Supvisors does
                    # typically happens when the local Supervisor has just been started whereas a Supvisors group
                    # was already operating, so accept remote perception
                    self.logger.warn('FiniteStateMachine.on_authorization: accept master_node={} declared by node={}'
                                     .format(master_node_name, node_name))
                    self.context.master_node_name = master_node_name
                if master_node_name == node_name and supvisors_state == SupvisorsStates.OPERATION:
                    # if the remote node is the master, consider the fact it is operational
                    self.context.master_operational = True
                if master_node_name != self.context.master_node_name:
                    # 2 different perceptions of the master, likely due to a split-brain situation
                    # so going back to INITIALIZATION to fix
                    self.logger.warn('FiniteStateMachine.on_authorization: master node conflict. '
                                     ' local declares {} - remote ({}) declares {}'
                                     .format(self.context.master_node_name, node_name, master_node_name))
                    self.set_state(SupvisorsStates.INITIALIZATION)

    def on_restart(self) -> None:
        """ This event is used to transition the state machine to the RESTARTING state.

        :return: None
        """
        self.set_state(SupvisorsStates.RESTARTING)

    def on_shutdown(self) -> None:
        """ This event is used to transition the state machine to the SHUTTING_DOWN state.

        :return: None
        """
        self.set_state(SupvisorsStates.SHUTTING_DOWN)

    # serialization
    def serial(self) -> Payload:
        """ Return a serializable form of the SupvisorsState.

        :return: the Supvisors state as a dictionary
        """
        return {'statecode': self.state.value, 'statename': self.state.name}

    # Map between state enumerations and classes
    __StateInstances = {
        SupvisorsStates.INITIALIZATION: InitializationState,
        SupvisorsStates.DEPLOYMENT: DeploymentState,
        SupvisorsStates.OPERATION: OperationState,
        SupvisorsStates.CONCILIATION: ConciliationState,
        SupvisorsStates.RESTARTING: RestartingState,
        SupvisorsStates.SHUTTING_DOWN: ShuttingDownState,
        SupvisorsStates.SHUTDOWN: ShutdownState
    }

    # Transitions allowed between states
    __Transitions = {
        None: [SupvisorsStates.INITIALIZATION],
        SupvisorsStates.INITIALIZATION: [SupvisorsStates.DEPLOYMENT],
        SupvisorsStates.DEPLOYMENT: [SupvisorsStates.OPERATION,
                                     SupvisorsStates.RESTARTING,
                                     SupvisorsStates.SHUTTING_DOWN],
        SupvisorsStates.OPERATION: [SupvisorsStates.CONCILIATION,
                                    SupvisorsStates.INITIALIZATION,
                                    SupvisorsStates.RESTARTING,
                                    SupvisorsStates.SHUTTING_DOWN],
        SupvisorsStates.CONCILIATION: [SupvisorsStates.OPERATION,
                                       SupvisorsStates.INITIALIZATION,
                                       SupvisorsStates.RESTARTING,
                                       SupvisorsStates.SHUTTING_DOWN],
        SupvisorsStates.RESTARTING: [SupvisorsStates.SHUTDOWN],
        SupvisorsStates.SHUTTING_DOWN: [SupvisorsStates.SHUTDOWN],
        SupvisorsStates.SHUTDOWN: []
    }
