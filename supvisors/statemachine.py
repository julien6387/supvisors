#!/usr/bin/python
#-*- coding: utf-8 -*-

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

from supvisors.strategy import conciliate
from supvisors.ttypes import AddressStates, SupvisorsStates
from supvisors.utils import supvisors_short_cuts


class AbstractState(object):
    """ Base class for a state with simple entry / next / exit actions """

    def __init__(self, supvisors):
        self.supvisors = supvisors
        supvisors_short_cuts(self, ['context', 'logger', 'starter', 'stopper'])
        self.address = supvisors.address_mapper.local_address

    def enter(self):
        pass

    def next(self):
        pass

    def exit(self):
        pass


class InitializationState(AbstractState):

    def enter(self):
        self.context.master_address = ''
        self.start_date = int(time())
        # re-init addresses that are not isolated
        for status in self.context.addresses.values():
            if not status.in_isolation():
                # do NOT use state setter as transition may be rejected
                status._state = AddressStates.UNKNOWN

    def next(self):
        # cannot get out of this state without local supervisor RUNNING
        addresses = self.context.running_addresses()
        if self.address in addresses:
            if len(self.context.unknown_addresses()) == 0:
                # synchro done if the state of all addresses is known
                return SupvisorsStates.DEPLOYMENT
            # if synchro timeout reached, stop synchro and work with known addresses
            if (time() - self.start_date) > self.supvisors.options.synchro_timeout:
                self.logger.warn('synchro timed out')
                return SupvisorsStates.DEPLOYMENT
            self.logger.debug('still waiting for remote supvisors to synchronize')
        else:
            self.logger.debug('local address {} still not RUNNING'.format(self.address))
        return SupvisorsStates.INITIALIZATION

    def exit(self):
        # force state of missing Supvisors instances
        self.context.end_synchro()
        # arbitrarily choice : master address is the 'lowest' address among running addresses
        addresses = self.context.running_addresses()
        self.logger.info('working with boards {}'.format(addresses))
        self.context.master_address = min(addresses)


class DeploymentState(AbstractState):

    def enter(self):
        # TODO: make a restriction of addresses in process rules, iaw process location in Supervisor instances
        # define ordering iaw Addresses
        for application in self.context.applications.values():
            application.update_sequences()
            application.update_status()
        # only the Supvisors master deploys applications
        if self.context.master:
            self.starter.start_applications(self.context.applications.values())

    def next(self):
        if not self.context.master or self.starter.check_starting():
                return SupvisorsStates.CONCILIATION if self.context.conflicting() else SupvisorsStates.OPERATION
        return SupvisorsStates.DEPLOYMENT


class OperationState(AbstractState):

    def next(self):
        # check eventual jobs in progress
        if self.starter.check_starting() and self.stopper.check_stopping():
            # check if master and local are still RUNNING
            if self.context.addresses[self.address].state != AddressStates.RUNNING:
                return SupvisorsStates.INITIALIZATION
            if self.context.addresses[self.context.master_address].state != AddressStates.RUNNING:
                return SupvisorsStates.INITIALIZATION
            # check duplicated processes
            if self.context.conflicting():
                return SupvisorsStates.CONCILIATION
        return SupvisorsStates.OPERATION


class ConciliationState(AbstractState):

    def enter(self):
        # the Supvisors Master auto-conciliates conflicts
        if self.context.master:
            conciliate(self.supvisors, self.supvisors.options.conciliation_strategy, self.context.conflicts())

    def next(self):
        # check eventual jobs in progress
        if self.starter.check_starting() and self.stopper.check_stopping():
            # check if master and local are still RUNNING
            if self.context.addresses[self.address].state != AddressStates.RUNNING:
                return SupvisorsStates.INITIALIZATION
            if self.context.addresses[self.context.master_address].state != AddressStates.RUNNING:
                return SupvisorsStates.INITIALIZATION
            # check conciliation
            if not self.context.conflicting():
                return SupvisorsStates.OPERATION
        return SupvisorsStates.CONCILIATION


class FiniteStateMachine:
    """ This class implements a very simple behaviour of FiniteStateMachine based on a single event.
    A state is able to evaluate itself for transitions. """

    def __init__(self, supvisors):
        """ Reset the state machine and the associated context """
        self.supvisors = supvisors
        supvisors_short_cuts(self, ['context', 'starter', 'stopper', 'logger'])
        self.update_instance(SupvisorsStates.INITIALIZATION)
        self.instance.enter()

    def state_string(self):
        """ Return the supvisors state as a string. """
        return SupvisorsStates._to_string(self.state)

    def next(self):
        """ Send the event to the state and transitions if possible.
        The state machine re-sends the event as long as it transitions. """
        next_state = self.instance.next()
        while next_state != self.state and next_state in self.__Transitions[self.state]:
            self.instance.exit()
            self.update_instance(next_state)
            self.logger.info('Supvisors in {}'.format(self.state_string()))
            self.instance.enter()
            next_state = self.instance.next()

    def update_instance(self, state):
        """ Change the current state.
        The method also triggers the publication of the change. """
        self.state = state
        self.instance = self.__StateInstances[state](self.supvisors)
        # publish SupvisorsStatus event
        self.supvisors.publisher.send_supvisors_status(self)

    def on_timer_event(self):
        """ Periodic task used to check if remote Supvisors instances are still active.
        This is also the main event on this state machine. """
        self.context.on_timer_event()
        self.next()
        # master can fix inconsistencies if any
        if self.context.master:
            self.starter.start_marked_processes(self.context.marked_processes())
        # check if new isolating remotes and return the list of newly isolated addresses
        return self.context.handle_isolation()

    def on_tick_event(self, address, when):
        """ This event is used to refresh the data related to the address. """
        self.context.on_tick_event(address, when)
        # could call the same behaviour as on_timer_event if necessary

    def on_process_event(self, address, event):
        """ This event is used to refresh the process data related to the event and address.
        This event also triggers the application starter. """
        process = self.context.on_process_event(address, event)
        if process:
            # wake up starter if needed
            if self.starter.in_progress():
                self.starter.on_event(process)
            # wake up stopper if needed
            if self.stopper.in_progress():
                self.stopper.on_event(process)

    def on_process_info(self, address_name, info):
        """ This event is used to fill the internal structures with processes available on address. """
        self.context.load_processes(address_name, info)

    def on_authorization(self, address_name, authorized):
        """ This event is used to finalize the port-knocking between Supvisors instances. """
        self.context.on_authorization(address_name, authorized)

    # serialization
    def to_json(self):
        """ Return a JSON-serializable form of the SupvisorsState """
        return {'statecode': self.state, 'statename': self.state_string()}

    # Map between state enumerations and classes
    __StateInstances = {
        SupvisorsStates.INITIALIZATION: InitializationState,
        SupvisorsStates.DEPLOYMENT: DeploymentState,
        SupvisorsStates.OPERATION: OperationState,
        SupvisorsStates.CONCILIATION: ConciliationState
    }

    # Transitions allowed between states
    __Transitions = {
        SupvisorsStates.INITIALIZATION: [ SupvisorsStates.DEPLOYMENT ],
        SupvisorsStates.DEPLOYMENT: [ SupvisorsStates.OPERATION, SupvisorsStates.CONCILIATION ],
        SupvisorsStates.OPERATION: [ SupvisorsStates.CONCILIATION, SupvisorsStates.INITIALIZATION ],
        SupvisorsStates.CONCILIATION: [ SupvisorsStates.OPERATION, SupvisorsStates.INITIALIZATION ]
   }
