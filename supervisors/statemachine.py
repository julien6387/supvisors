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

from supervisors.addressmapper import addressMapper
from supervisors.context import context
from supervisors.deployer import deployer
from supervisors.options import options
from supervisors.publisher import eventPublisher
from supervisors.remote import RemoteStates
from supervisors.strategy import conciliator
from supervisors.types import SupervisorsStates, supervisorsStateToString


class _AbstractState(object):
    """ Base class for a state with simple entry / next / exit actions """
    def enter(self): pass
    def next(self): pass
    def exit(self): pass


class _InitializationState(_AbstractState):
    def enter(self):
        context.masterAddress = ''
        context.master = False
        self.startDate = int(time())
        # re-init remotes that are not isolated
        for remote in context.remotes.values():
            if not remote.isInIsolation():
                # do NOT use state setter as transition may be rejected
                remote._state = RemoteStates.UNKNOWN
                remote.checked = False

    def next(self):
        # cannot get out of this state without local supervisor RUNNING
        runningRemotes = context.runningRemotes()
        if addressMapper.local_address in runningRemotes:
            if len(context.unknownRemotes()) == 0:
                # synchro done if the state of all remotes is known
                return SupervisorsStates.DEPLOYMENT
            # if synchro timeout reached, stop synchro and work with known remotes
            if (time() - self.startDate) > options.synchroTimeout:
                options.logger.warn('synchro timed out')
                return SupervisorsStates.DEPLOYMENT
            options.logger.debug('still waiting for remote supervisors to synchronize')
        else:
            options.logger.debug('local address {} still not RUNNING'.format(addressMapper.local_address))
        return SupervisorsStates.INITIALIZATION

    def exit(self):
        # force state of missing Remotes
        context.endSynchro()
        # arbitrarily choice : master address is the 'lowest' address among running remotes
        runningRemotes = context.runningRemotes()
        options.logger.info('working with boards {}'.format(runningRemotes))
        context.masterAddress = min(runningRemotes)
        context.master = (context.masterAddress == addressMapper.local_address)
        options.logger.info('Supervisors master is {} self={}'.format(context.masterAddress, context.master))


class _DeploymentState(_AbstractState):
    def enter(self):
        # define ordering iaw Remotes
        for application in context.applications.values():
            application.sequenceDeployment()
        # only Supervisors master deploys applications
        if context.master: deployer.deployApplications(context.applications.values())

    def next(self):
        if deployer.checkDeployment():
                return SupervisorsStates.CONCILIATION if context.hasConflict() else SupervisorsStates.OPERATION
        return SupervisorsStates.DEPLOYMENT


class _OperationState(_AbstractState):
    def next(self):
        # check if master and local are still RUNNING
        if context.remotes[addressMapper.local_address].state != RemoteStates.RUNNING:
            return SupervisorsStates.INITIALIZATION
        if context.remotes[context.masterAddress].state != RemoteStates.RUNNING:
            return SupervisorsStates.INITIALIZATION
        # check duplicated processes
        if context.hasConflict():
            return SupervisorsStates.CONCILIATION
        return SupervisorsStates.OPERATION


class _ConciliationState(_AbstractState):
    def enter(self):
        # the Supervisors Master auto-conciliate conflicts
        if context.master:
            conciliator.conciliate(options.conciliationStrategy, context.getConflicts())

    def next(self):
        # check if master and local are still RUNNING
        if context.remotes[addressMapper.local_address].state != RemoteStates.RUNNING:
            return SupervisorsStates.INITIALIZATION
        if context.remotes[context.masterAddress].state != RemoteStates.RUNNING:
            return SupervisorsStates.INITIALIZATION
        # check conciliation
        if not context.hasConflict():
            return SupervisorsStates.OPERATION
        return SupervisorsStates.CONCILIATION


class FiniteStateMachine:
    """ This class implements a very simple behaviour of FiniteStateMachine based on a single event.
    A state is able to evaluate itself for transitions. """

    def __init__(self, supervisors):
        """ Reset the state machine and the associated context """
        self.supervisors = supervisors
        self.updateStateInstance(SupervisorsStates.INITIALIZATION)
        self.stateInstance.enter()

    def next(self):
        """ Send the event to the state and transitions if possible.
        The state machine re-sends the event as long as it transitions. """
        nextState = self.stateInstance.next()
        while nextState != self.state and nextState in self.__Transitions[self.state]:
            self.stateInstance.exit()
            self.updateStateInstance(nextState)
            options.logger.info('Supervisors in {}'.format(supervisorsStateToString(self.state)))
            self.stateInstance.enter()
            nextState = self.stateInstance.next()

    def updateStateInstance(self, state):
        """ Change the current state.
        The method also triggers the publication of the change. """
        self.state = state
        self.stateInstance = self.__StateInstances[state]()
        # publish RemoteStatus event
        eventPublisher.sendSupervisorsStatus(self)

    def onTimerEvent(self):
        """ Periodic task used to check if remote Supervisors instance are still active.
        This is also the main event on this state machine. """
        context.onTimerEvent()
        self.next()
        # master can fix inconsistencies if any
        if context.master:
            deployer.deployMarkedProcesses(self.getMarkedProcesses())
        # check if new isolating remotes and return the list of newly isolated addresses
        return context.handleIsolation()

    def onTickEvent(self, address, when):
        """ This event is used to refresh the data related to the address. """
        context.onTickEvent(address, when)
        # could call the same behaviour as onTimerEvent if necessary

    def onProcessEvent(self, address, processEvent):
        """ This event is used to refresh the process data related to the event and address.
        This event also triggers the deployer. """
        process = context.onProcessEvent(address, processEvent)
        # trigger deployment work if needed
        if process and deployer.isDeploymentInProgress():
            deployer.deployOnEvent(process)

    # serialization
    def toJSON(self):
        """ Return a JSON-serializable form of the SupervisorState """
        return { 'state': supervisorsStateToString(self.state) }

    # Map between state enumeration and class
    __StateInstances = {
        SupervisorsStates.INITIALIZATION: _InitializationState,
        SupervisorsStates.DEPLOYMENT: _DeploymentState,
        SupervisorsStates.OPERATION: _OperationState,
        SupervisorsStates.CONCILIATION: _ConciliationState
    }

    # Transitions allowed between states
    __Transitions = {
        SupervisorsStates.INITIALIZATION: [ SupervisorsStates.DEPLOYMENT ],
        SupervisorsStates.DEPLOYMENT: [ SupervisorsStates.OPERATION, SupervisorsStates.CONCILIATION ],
        SupervisorsStates.OPERATION: [ SupervisorsStates.CONCILIATION, SupervisorsStates.INITIALIZATION ],
        SupervisorsStates.CONCILIATION: [ SupervisorsStates.OPERATION, SupervisorsStates.INITIALIZATION ]
   }

# Singleton of the State Machine
fsm = FiniteStateMachine()
