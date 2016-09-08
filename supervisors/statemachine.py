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

from supervisors.remote import RemoteStates
from supervisors.strategy import conciliate
from supervisors.types import SupervisorsStates, supervisorsStateToString
from supervisors.utils import supervisors_short_cuts


class AbstractState(object):
    """ Base class for a state with simple entry / next / exit actions """

    def __init__(self, supervisors):
        self.supervisors = supervisors
        supervisors_short_cuts(self, ['context', 'logger'])
        self.address = supervisors.address_mapper.local_address

    def enter(self):
        pass

    def next(self):
        pass

    def exit(self):
        pass


class InitializationState(AbstractState):

    def enter(self):
        self.context.master_address = ''
        self.startDate = int(time())
        # re-init remotes that are not isolated
        for remote in self.context.remotes.values():
            if not remote.isInIsolation():
                # do NOT use state setter as transition may be rejected
                remote._state = RemoteStates.UNKNOWN
                remote.checked = False

    def next(self):
        # cannot get out of this state without local supervisor RUNNING
        runningRemotes = self.context.runningRemotes()
        if self.address in runningRemotes:
            if len(self.context.unknownRemotes()) == 0:
                # synchro done if the state of all remotes is known
                return SupervisorsStates.DEPLOYMENT
            # if synchro timeout reached, stop synchro and work with known remotes
            if (time() - self.startDate) > self.supervisors.options.synchroTimeout:
                self.logger.warn('synchro timed out')
                return SupervisorsStates.DEPLOYMENT
            self.logger.debug('still waiting for remote supervisors to synchronize')
        else:
            self.logger.debug('local address {} still not RUNNING'.format(self.address))
        return SupervisorsStates.INITIALIZATION

    def exit(self):
        # force state of missing Remotes
        self.supervisors.context.endSynchro()
        # arbitrarily choice : master address is the 'lowest' address among running remotes
        runningRemotes = self.supervisors.context.runningRemotes()
        self.logger.info('working with boards {}'.format(runningRemotes))
        self.context.master_address = min(runningRemotes)
        self.logger.info('Supervisors master is {} self={}'.format(self.context.master_address, self.context.is_master))


class DeploymentState(AbstractState):

    def enter(self):
        # define ordering iaw Remotes
        for application in self.context.applications.values():
            application.sequenceDeployment()
        # only Supervisors master deploys applications
        if self.context.is_master:
            self.supervisors.deployer.deployApplications(self.context.applications.values())

    def next(self):
        if self.supervisors.deployer.checkDeployment():
                return SupervisorsStates.CONCILIATION if self.context.hasConflict() else SupervisorsStates.OPERATION
        return SupervisorsStates.DEPLOYMENT


class OperationState(AbstractState):

    def next(self):
        # check if master and local are still RUNNING
        if self.context.remotes[self.address].state != RemoteStates.RUNNING:
            return SupervisorsStates.INITIALIZATION
        if self.context.remotes[self.context.master_address].state != RemoteStates.RUNNING:
            return SupervisorsStates.INITIALIZATION
        # check duplicated processes
        if self.context.hasConflict():
            return SupervisorsStates.CONCILIATION
        return SupervisorsStates.OPERATION


class ConciliationState(AbstractState):

    def enter(self):
        # the Supervisors Master auto-conciliate conflicts
        if self.context.is_master:
            conciliate(self.supervisors.options.conciliationStrategy, self.context.getConflicts())

    def next(self):
        # check if master and local are still RUNNING
        if self.context.remotes[self.address].state != RemoteStates.RUNNING:
            return SupervisorsStates.INITIALIZATION
        if self.context.remotes[self.context.master_address].state != RemoteStates.RUNNING:
            return SupervisorsStates.INITIALIZATION
        # check conciliation
        if not self.context.hasConflict():
            return SupervisorsStates.OPERATION
        return SupervisorsStates.CONCILIATION


class FiniteStateMachine:
    """ This class implements a very simple behaviour of FiniteStateMachine based on a single event.
    A state is able to evaluate itself for transitions. """

    def __init__(self, supervisors):
        """ Reset the state machine and the associated context """
        self.supervisors = supervisors
        supervisors_short_cuts(self, ['context', 'deployer', 'logger'])
        self.updateStateInstance(SupervisorsStates.INITIALIZATION)
        self.stateInstance.enter()

    def next(self):
        """ Send the event to the state and transitions if possible.
        The state machine re-sends the event as long as it transitions. """
        nextState = self.stateInstance.next()
        while nextState != self.state and nextState in self.__Transitions[self.state]:
            self.stateInstance.exit()
            self.updateStateInstance(nextState)
            self.logger.info('Supervisors in {}'.format(supervisorsStateToString(self.state)))
            self.stateInstance.enter()
            nextState = self.stateInstance.next()

    def updateStateInstance(self, state):
        """ Change the current state.
        The method also triggers the publication of the change. """
        self.state = state
        self.stateInstance = self.__StateInstances[state](self.supervisors)
        # publish RemoteStatus event
        self.supervisors.publisher.sendSupervisorsStatus(self)

    def onTimerEvent(self):
        """ Periodic task used to check if remote Supervisors instance are still active.
        This is also the main event on this state machine. """
        self.context.onTimerEvent()
        self.next()
        # master can fix inconsistencies if any
        if self.context.is_master:
            self.deployer.deployMarkedProcesses(self.context.getMarkedProcesses())
        # check if new isolating remotes and return the list of newly isolated addresses
        return self.context.handleIsolation()

    def onTickEvent(self, address, when):
        """ This event is used to refresh the data related to the address. """
        self.context.onTickEvent(address, when)
        # could call the same behaviour as onTimerEvent if necessary

    def onProcessEvent(self, address, processEvent):
        """ This event is used to refresh the process data related to the event and address.
        This event also triggers the deployer. """
        process = self.context.onProcessEvent(address, processEvent)
        # trigger deployment work if needed
        if process and self.deployer.isDeploymentInProgress():
            self.deployer.deployOnEvent(process)

    # serialization
    def toJSON(self):
        """ Return a JSON-serializable form of the SupervisorState """
        return { 'state': supervisorsStateToString(self.state) }

    # Map between state enumeration and class
    __StateInstances = {
        SupervisorsStates.INITIALIZATION: InitializationState,
        SupervisorsStates.DEPLOYMENT: DeploymentState,
        SupervisorsStates.OPERATION: OperationState,
        SupervisorsStates.CONCILIATION: ConciliationState
    }

    # Transitions allowed between states
    __Transitions = {
        SupervisorsStates.INITIALIZATION: [ SupervisorsStates.DEPLOYMENT ],
        SupervisorsStates.DEPLOYMENT: [ SupervisorsStates.OPERATION, SupervisorsStates.CONCILIATION ],
        SupervisorsStates.OPERATION: [ SupervisorsStates.CONCILIATION, SupervisorsStates.INITIALIZATION ],
        SupervisorsStates.CONCILIATION: [ SupervisorsStates.OPERATION, SupervisorsStates.INITIALIZATION ]
   }
