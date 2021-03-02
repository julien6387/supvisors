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
from supvisors.ttypes import AddressStates, SupvisorsStates, Payload
from supvisors.utils import supvisors_shortcuts


class AbstractState(object):
    """ Base class for a state with simple entry / next / exit actions.

    Attributes are:

        - supvisors: the reference to the global Supvisors structure,
        - *shortcuts*: the references to Supvisors attributes used here,
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
                                     .format(func.__name__, status.address_name, status.state_string()))
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

    def enter(self):
        """ When entering in the INITIALIZATION state, reset the status of addresses. """
        self.context.master_address = ''
        self.start_date = int(time())
        # clear any existing job
        self.failure_handler.clear_jobs()
        # re-init addresses that are not isolated
        for status in self.context.addresses.values():
            if not status.in_isolation():
                # do NOT use state setter as transition may be rejected
                status._state = AddressStates.UNKNOWN

    def next(self) -> int:
        """ Wait for nodes to publish until:
            - all are active,
            - or all defined in the optional *force_synchro_if* option are active,
            - or timeout is reached.

        :return: the new Supvisors state
        """
        # cannot get out of this state without local supervisor RUNNING
        addresses = self.context.running_addresses()
        if self.address_name in addresses:
            # synchro done if the state of all addresses is known
            if len(self.context.unknown_addresses()) == 0:
                self.logger.info('InitializationState.next: all nodes are RUNNING')
                return SupvisorsStates.DEPLOYMENT
            # synchro done if the state of all forced addresses is known
            if self.context.forced_addresses and len(self.context.unknown_forced_addresses()) == 0:
                self.logger.info('InitializationState.next: all forced nodes are RUNNING')
                return SupvisorsStates.DEPLOYMENT
            # if synchro timeout reached, stop synchro and work with known addresses
            if (time() - self.start_date) > self.supvisors.options.synchro_timeout:
                self.logger.warn('InitializationState.next: synchro timed out')
                return SupvisorsStates.DEPLOYMENT
            self.logger.debug('InitializationState.next: still waiting for remote Supvisors instances to publish')
        else:
            self.logger.debug('InitializationState.next: local node {} still not RUNNING'.format(self.address_name))
        return SupvisorsStates.INITIALIZATION

    def exit(self):
        """ When leaving the INITIALIZATION state, the working addresses are defined.
        One of them is elected as the MASTER. """
        # force state of missing Supvisors instances
        self.context.end_synchro()
        # arbitrarily choice : master address is the 'lowest' address among running addresses
        addresses = self.context.running_addresses()
        self.logger.info('InitializationState.exit: working with nodes {}'.format(addresses))
        # elect master node among working addresses only if not fixed before
        if not self.context.master_address:
            self.context.master_address = min(addresses)


class DeploymentState(AbstractState):
    """ In the DEPLOYMENT state, Supvisors starts automatically the applications having a starting model. """

    def enter(self):
        """ When entering in the DEPLOYMENT state, define the start and stop sequences.
        Only the MASTER can perform the automatic start and stop. """
        for application in self.context.applications.values():
            application.update_sequences()
            application.update_status()
        # only the Supvisors master starts applications
        if self.context.master:
            self.starter.start_applications()

    def next(self):
        """ Wait for applications to be started. """
        if not self.context.master or self.starter.check_starting():
            return SupvisorsStates.CONCILIATION if self.context.conflicting() else SupvisorsStates.OPERATION
        return SupvisorsStates.DEPLOYMENT


class OperationState(AbstractState):
    """ In the OPERATION state, Supvisors is waiting for requests. """

    def next(self):
        """ Check that all addresses are still active.
        Look after possible conflicts due to multiple running instances of the same program. """
        # check eventual jobs in progress
        if self.starter.check_starting() and self.stopper.check_stopping():
            # check if master and local are still RUNNING
            if self.context.addresses[self.address_name].state != AddressStates.RUNNING:
                return SupvisorsStates.INITIALIZATION
            if self.context.addresses[self.context.master_address].state != AddressStates.RUNNING:
                return SupvisorsStates.INITIALIZATION
            # check duplicated processes
            if self.context.conflicting():
                return SupvisorsStates.CONCILIATION
        return SupvisorsStates.OPERATION


class ConciliationState(AbstractState):
    """ In the CONCILIATION state, Supvisors conciliates the conflicts. """

    def enter(self):
        """ When entering in the CONCILIATION state, conciliate automatically the conflicts.
        Only the MASTER can conciliate conflicts. """
        if self.context.master:
            conciliate_conflicts(self.supvisors,
                                 self.supvisors.options.conciliation_strategy,
                                 self.context.conflicts())

    def next(self):
        """ Check that all addresses are still active.
        Wait for all conflicts to be conciliated. """
        # check eventual jobs in progress
        if self.starter.check_starting() and self.stopper.check_stopping():
            # check if local is still RUNNING
            local_status = self.context.addresses[self.address_name]
            if local_status.state != AddressStates.RUNNING:
                return SupvisorsStates.INITIALIZATION
            # check if master is still RUNNING
            master_status = self.context.addresses[self.context.master_address]
            if master_status.state != AddressStates.RUNNING:
                return SupvisorsStates.INITIALIZATION
            # back to OPERATION when there is no conflict anymore
            if not self.context.conflicting():
                return SupvisorsStates.OPERATION
            # new conflicts may happen while conciliation is in progress
            # call enter again to trigger a new conciliation
            self.enter()
        return SupvisorsStates.CONCILIATION


class RestartingState(AbstractState):
    """ In the RESTARTING state, Supvisors stops all applications before triggering a full restart. """

    def enter(self):
        """ When entering in the RESTARTING state, stop all applications. """
        self.failure_handler.clear_jobs()
        self.starter.abort()
        self.stopper.stop_applications()

    def next(self):
        """ Wait for all processes to be stopped. """
        # check eventual jobs in progress
        if self.stopper.check_stopping():
            return SupvisorsStates.SHUTDOWN
        return SupvisorsStates.RESTARTING

    def exit(self):
        """ When leaving the RESTARTING state, request the full restart. """
        self.apply_addresses_func(self.supvisors.zmq.pusher.send_restart)


class ShuttingDownState(AbstractState):
    """ In the SHUTTING_DOWN state, Supvisors stops all applications before
    triggering a full shutdown. """

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

    def __init__(self, supvisors):
        """ Reset the state machine and the associated context """
        self.supvisors = supvisors
        supvisors_shortcuts(self, ['context', 'failure_handler', 'starter', 'stopper', 'logger'])
        self.state = SupvisorsStates.INITIALIZATION
        self.instance = None
        # Trigger first state / INITIALIZATION
        self.update_instance(SupvisorsStates.INITIALIZATION)

    def state_string(self):
        """ Return the supvisors state as a string. """
        return SupvisorsStates.to_string(self.state)

    def next(self):
        """ Send the event to the state and transitions if possible.
        The state machine re-sends the event as long as it transitions. """
        self.set_state(self.instance.next())

    def set_state(self, next_state):
        """ Send the event to the state and transitions if possible.
        The state machine re-sends the event as long as it transitions. """
        while next_state != self.state and next_state in self.__Transitions[self.state]:
            self.instance.exit()
            self.update_instance(next_state)
            next_state = self.instance.next()

    def update_instance(self, state):
        """ Change the current state.
        The method also triggers the publication of the change. """
        self.state = state
        self.logger.info('FiniteStateMachine.update_instance: Supvisors in {}'.format(self.state_string()))
        self.instance = self.__StateInstances[state](self.supvisors)
        self.instance.enter()
        # publish SupvisorsStatus event
        # the zmq does not exist yet for the first occurrence here
        if self.supvisors.zmq:
            self.supvisors.zmq.publisher.send_supvisors_status(self.serial())

    def on_timer_event(self):
        """ Periodic task used to check if remote Supvisors instances are still active.
        This is also the main event on this state machine. """
        self.context.on_timer_event()
        self.next()
        # fix failures if any (can happen after a node invalidation, a process crash or a conciliation request)
        self.failure_handler.trigger_jobs()
        # check if new isolating remotes and return the list of newly isolated addresses
        # TODO: create an internal event to confirm that socket has been disconnected ?
        return self.context.handle_isolation()

    def on_tick_event(self, address, when):
        """ This event is used to refresh the data related to the address. """
        self.context.on_tick_event(address, when)
        # could call the same behaviour as on_timer_event if necessary

    def on_process_event(self, address, event):
        """ This event is used to refresh the process data related to the event and address.
        This event also triggers the application starter and/or stopper. """
        process = self.context.on_process_event(address, event)
        if process:
            # check if event is related to a starting or stopping application
            starting = self.starter.has_application(process.application_name)
            stopping = self.stopper.has_application(process.application_name)
            # feed starter with event
            self.starter.on_event(process)
            # feed stopper with event
            self.stopper.on_event(process)
            # only the master is allowed to trigger an automatic behaviour for a running failure
            if self.context.master and process.crashed() and not (starting or stopping):
                self.failure_handler.add_default_job(process)
                self.failure_handler.trigger_jobs()

    def on_process_info(self, address_name: str, info) -> None:
        """ This event is used to fill the internal structures with processes available on node. """
        self.context.load_processes(address_name, info)

    def on_authorization(self, address_name: str, authorized: bool, master_address: str) -> None:
        """ This event is used to finalize the port-knocking between Supvisors instances.
        When a new node that has not be part of Supvisors comes in the group, back to INITIALIZATION
        for a new Master election and a possible deployment

        :param address_name: the node name from which the event comes
        :param authorized: the authorization status as seen by the remote node
        :param master_address: the master node perceived by the remote node
        :return: None
        """
        self.logger.info('FiniteStateMachine.on_authorization: address_name={} authorized={} master_address={}'
                         .format(address_name, authorized, master_address))
        if self.context.on_authorization(address_name, authorized):
            if master_address:
                if not self.context.master_address:
                    # local Supvisors doesn't know about a master yet but remote Supvisors does
                    # this is likely due to the fact that the local Supervisor has just been started whereas
                    # a Supvisors group was already operating
                    # so accept remote perception in order to avoid going back to INITIALIZATION state for all
                    self.logger.warn('FiniteStateMachine.on_authorization: accept master={} declared by node={}'
                                     .format(master_address, address_name))
                    self.context.master_address = master_address
                elif master_address != self.context.master_address:
                    # 2 different perceptions of the master, likely due to a split-brain situation
                    # so going back to INITIALIZATION to fix
                    self.logger.warn('FiniteStateMachine.on_authorization: master discrepancy. '
                                     ' local declares {} - remote ({}) declares {}'
                                     .format(self.context.master_address, address_name, master_address))
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
        return {'statecode': self.state, 'statename': self.state_string()}

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
        SupvisorsStates.INITIALIZATION: [SupvisorsStates.DEPLOYMENT],
        SupvisorsStates.DEPLOYMENT: [SupvisorsStates.OPERATION,
                                     SupvisorsStates.CONCILIATION,
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
