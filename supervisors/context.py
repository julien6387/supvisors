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
from supervisors.datahandlers import *
from supervisors.deployer import deployer
from supervisors.options import mainOptions as opt
from supervisors.remote import RemoteStates
from supervisors.types import SupervisorsStates, supervisorsStateToString

import time

# Context management
class _Context(object):
    def __init__(self):
        self._state = None

    @property
    def state(self): return self._state
    @state.setter
    def state(self, value):
        if self._state != value:
            self._state = value
            opt.logger.warn('Supervisors in %s' % supervisorsStateToString(self.state))

    @property
    def masterAddress(self): return self._masterAddress

    def cleanup(self):
        self.state = SupervisorsStates.INITIALIZATION
        self._startDate = int(time.time())
        self._workingRemotes = [ ]
        self._masterAddress = ''
        # clear entries in handlers
        remotesHandler.cleanup()
        applicationsHandler.cleanup()

    def onTickEvent(self, addresses, tickEvent):
        address = addressMapper.getExpectedAddress(addresses, True)
        if address:
            opt.logger.debug('got tick {} from location={}'.format(tickEvent, address))
            remoteTime = tickEvent['when']
            localTime = int(time.time())
            remotesHandler.updateRemoteTime(address, remoteTime, localTime)
            applicationsHandler.updateRemoteTime(address, remoteTime, localTime)
        else:
            opt.logger.warn('got tick from unexpected location={}'.format(addresses))

    def onProcessEvent(self, addresses, processEvent):
        address = addressMapper.getExpectedAddress(addresses, True)
        if address:
            opt.logger.debug('got event {} from location={}'.format(processEvent, address))
            try:
                process = applicationsHandler.updateProcess(address, processEvent)
            except:
                # process not found. normal when no tick yet received from this address
                opt.logger.debug('reject event {} from location={}'.format(processEvent, address))
            else:
                # trigger deployment work if needed
                if deployer.isDeploymentInProgress():
                    deployer.deployOnEvent(process)
        else:
            opt.logger.error('got process event from unexpected location={}'.format(addresses))

    def onTimerEvent(self):
        # check that all remotes are still publishing
        remotesHandler.checkRemotes()
        # trigger Supervisors state machine
        self._check()

    def onAuthorization(self, address, permit):
        address = addressMapper.getExpectedAddress([address])
        if address:
            remotesHandler.authorize(address, permit)
        else:
            opt.logger.warn('got permit from unexpected location={}'.format(address))

    def _check(self):
        condition = True
        while condition:
            nextState = self.state
            if self.state == SupervisorsStates.INITIALIZATION:
                nextState = self._initializationState()
            elif self.state == SupervisorsStates.ELECTION:
                nextState = self._electionState()
            elif self.state == SupervisorsStates.DEPLOYMENT:
                nextState = self._deploymentState()
            elif self.state == SupervisorsStates.OPERATION:
                nextState = self._operationState()
            elif self.state == SupervisorsStates.CONCILIATION:
                nextState = self._conciliationState()
                # set next state
            condition = (nextState != self.state)
            self.state = nextState

    def _initializationState(self):
        nextState = self.state
        remotes = remotesHandler.sortRemotesByState()
        # need at least one Remote to exit this state
        if len(remotes[RemoteStates.RUNNING]):
            if len(remotes[RemoteStates.UNKNOWN]) == 0 and len(remotes[RemoteStates.CHECKING]) == 0:
                # synchro done
                nextState = SupervisorsStates.ELECTION
            else:
                # if synchro timeout reached, stop synchro and work with known remotes
                if (time.time() - self._startDate) > opt.synchro_timeout:
                    opt.logger.warn('synchro timed out')
                    # force state of missing Remotes then sort again
                    remotesHandler.endSynchro()
                    remotes = remotesHandler.sortRemotesByState()
                    nextState = SupervisorsStates.ELECTION
                else:
                    opt.logger.debug('still waiting for Remotes {} to synchronize'.format(remotes[RemoteStates.UNKNOWN] + remotes[RemoteStates.CHECKING]))
        if nextState != self.state:
            self.__logRemotes(remotes)
            self._workingRemotes = remotes[RemoteStates.RUNNING][:]
        return nextState

    def _electionState(self):
        nextState = self.state
        # arbitrarily choice : master address is the 'greater' address
        self._masterAddress = max(self._workingRemotes)
        self._isSelfMaster = self._masterAddress == addressMapper.expectedAddress
        opt.logger.info('Supervisors master is {} self={}'.format(self.masterAddress, self._isSelfMaster))
        self._enterDeployment = True
        nextState = SupervisorsStates.DEPLOYMENT
        return nextState

    def _deploymentState(self):
        nextState = self.state
        if self._enterDeployment:
            self._enterDeployment = False
            # define ordering iaw Remotes
            applicationsHandler.sequenceDeployment()
            # only Supervisors master deploys applications
            if not self._isSelfMaster or deployer.deployAll():
                nextState = SupervisorsStates.OPERATION
        else:
            if deployer.checkDeployment():
                nextState = SupervisorsStates.OPERATION
        return nextState

    def _operationState(self):
        nextState = self.state
        # TODO: check SILENT Remotes
        # TODO: check duplicated processes
        return nextState

    def _conciliationState(self):
        nextState = self.state
        # TODO: check SILENT Remotes
        # TODO: check conciliation
        return nextState

    def __logRemotes(self, remotes):
        opt.logger.info('working with boards {}'.format(remotes[RemoteStates.RUNNING]))
        opt.logger.info('boards SILENT {}'.format(remotes[RemoteStates.SILENT]))
        opt.logger.info('boards ISOLATED {}'.format(remotes[RemoteStates.ISOLATED]))

    def __checkTransition(self, newState):
        return newState in self.__Transitions[self.state]

    __Transitions = { \
        SupervisorsStates.INITIALIZATION: [ SupervisorsStates.ELECTION ],
        SupervisorsStates.ELECTION: [ SupervisorsStates.DEPLOYMENT ],
        SupervisorsStates.DEPLOYMENT: [ SupervisorsStates.OPERATION ],
        SupervisorsStates.OPERATION: [ SupervisorsStates.CONCILIATION, SupervisorsStates.ELECTION ],
        SupervisorsStates.CONCILIATION: [ SupervisorsStates.OPERATION, SupervisorsStates.ELECTION ]
    }

context = _Context()
