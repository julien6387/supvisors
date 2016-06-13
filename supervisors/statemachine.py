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

from supervisors.addressmapper import addressMapper
from supervisors.context import context
from supervisors.deployer import deployer
from supervisors.options import mainOptions as opt
from supervisors.remote import RemoteStates
from supervisors.types import SupervisorsStates, supervisorsStateToString

import time

# FSM management
class _AbstractState(object):
    def enter(self): pass
    def next(self): pass
    def exit(self): pass

class _InitializationState(_AbstractState):
    def enter(self):
        self.startDate = int(time.time())
        # re-init remotes that are not isolated
        for remote in context.remotes.values():
            if not remote.isInIsolation():
                remote.setState(RemoteStates.UNKNOWN)
                remote.checked = False

    def next(self):
        # cannot get out of this state without local supervisor RUNNING
        runningRemotes = context.runningRemotes()
        if addressMapper.localAddress in runningRemotes:
            if len(context.unknownRemotes()) == 0:
                # synchro done if the state of all remotes is known
                return SupervisorsStates.ELECTION
            # if synchro timeout reached, stop synchro and work with known remotes
            if (time.time() - self.startDate) > opt.synchro_timeout:
                opt.logger.warn('synchro timed out')
                # force state of missing Remotes
                context.endSynchro()
                return SupervisorsStates.ELECTION
            opt.logger.debug('still waiting for remote supervisors to synchronize')
        else:
            opt.logger.debug('local address {} still not RUNNING'.format(addressMapper.localAddress))
        return SupervisorsStates.INITIALIZATION

class _ElectionState(_AbstractState):
    def next(self):
        runningRemotes = context.runningRemotes()
        opt.logger.info('working with boards {}'.format(runningRemotes))
        # arbitrarily choice : master address is the 'greater' address among running remotes
        context.masterAddress = max(runningRemotes)
        context.master = (context.masterAddress == addressMapper.localAddress)
        opt.logger.info('Supervisors master is {} self={}'.format(context.masterAddress, context.master))
        return SupervisorsStates.DEPLOYMENT

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
        if context.remotes[addressMapper.localAddress].state != RemoteStates.RUNNING:
            return SupervisorsStates.INITIALIZATION
        if context.remotes[context.masterAddress].state != RemoteStates.RUNNING:
            return SupervisorsStates.ELECTION
        # check duplicated processes
        if context.hasConflict():
            return SupervisorsStates.CONCILIATION
        return SupervisorsStates.OPERATION

class _ConciliationState(_AbstractState):
    def enter(self):
        # FIXME: trigger auto-conciliation
        pass

    def next(self):
        # check if master and local are still RUNNING
        if context.remotes[addressMapper.localAddress].state != RemoteStates.RUNNING:
            return SupervisorsStates.INITIALIZATION
        if context.remotes[context.masterAddress].state != RemoteStates.RUNNING:
            return SupervisorsStates.ELECTION
        # check conciliation
        if not context.hasConflict():
            return SupervisorsStates.OPERATION
        return SupervisorsStates.CONCILIATION

class _FiniteStateMachine:
    def restart(self):
        self._updateStateInstance(SupervisorsStates.INITIALIZATION)
        self.stateInstance.enter()

    def next(self):
        nextState = self.stateInstance.next()
        while nextState != self.state and nextState in self.__Transitions[self.state]:
            self.stateInstance.exit()
            self._updateStateInstance(nextState)
            opt.logger.info('Supervisors in {}'.format(supervisorsStateToString(self.state)))
            self.stateInstance.enter()
            nextState = self.stateInstance.next()

    def _updateStateInstance(self, state):
        self.state = state
        self.stateInstance = self.__StateInstances[state]()

    __StateInstances = {
        SupervisorsStates.INITIALIZATION: _InitializationState,
        SupervisorsStates.ELECTION: _ElectionState,
        SupervisorsStates.DEPLOYMENT: _DeploymentState,
        SupervisorsStates.OPERATION: _OperationState,
        SupervisorsStates.CONCILIATION: _ConciliationState
    }

    __Transitions = {
        SupervisorsStates.INITIALIZATION: [ SupervisorsStates.ELECTION ],
        SupervisorsStates.ELECTION: [ SupervisorsStates.DEPLOYMENT ],
        SupervisorsStates.DEPLOYMENT: [ SupervisorsStates.OPERATION, SupervisorsStates.CONCILIATION ],
        SupervisorsStates.OPERATION: [ SupervisorsStates.CONCILIATION, SupervisorsStates.INITIALIZATION, SupervisorsStates.ELECTION ],
        SupervisorsStates.CONCILIATION: [ SupervisorsStates.OPERATION, SupervisorsStates.INITIALIZATION, SupervisorsStates.ELECTION ]
   }

fsm = _FiniteStateMachine()
