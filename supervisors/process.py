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

from supervisors.options import options
from supervisors.utils import *
from supervisor.states import *

import time

def stringToProcessStates(strEnum):
    return stringToEnum(ProcessStates.__dict__, strEnum)

# Rules for starting a process, iaw deployment file
class ProcessRules(object):
    def __init__(self):
        # TODO: see if restart_strategy (process, application) is to be implemented
        # TODO: see if dependency (process, application) is to be implemented
        self.addresses = [ '*' ] # all addresses are applicable by default
        self.sequence = -1
        self.required = False
        self.wait_exit = False
        self.expected_loading = 1

    def checkDependencies(self, logName):
        # required MUST have sequence, so force to optional if no sequence
        if self.required and self.sequence == -1:
            options.logger.warn('{} - required forced to False because no sequence defined'.format(logName))
            self.required = False
        # if no addresses, consider all addresses
        if not self.addresses:
            from supervisors.addressmapper import addressMapper
            self.addresses = addressMapper.expectedAddresses 
            options.logger.warn('{} - no address defined so all Supervisors addresses are applicable')

    def __str__(self):
        return 'addresses={} sequence={} required={} wait_exit={} loading={}'.format(self.addresses,
            self.sequence, self.required, self.wait_exit, self.expected_loading)


# ProcessStatus class: only storage and access
class ProcessStatus(object):
    def __init__(self, address, processInfo):
        # TODO: do I really need to keep all process info ? requests to Supervisor give the same...
        # wait for web development to decide
        # TODO: consider using supervisor.process Subprocess and adding missing information ?
        self.applicationName = processInfo['group']
        self.processName = processInfo['name']
        self.state = ProcessStates.UNKNOWN
        self.expectedExit = True
        self.lastEventTime = None
        # FIXME: replace runningConflict with a method len(addresses) > 1
        self.runningConflict = False
        # expected one single applicable address
        self.addresses = set() # addresses
        self.processes = {} # address: processInfo
        # rules part
        self.rules = ProcessRules()
        self.ignoreWaitExit = False
        # init parameters
        self.addInfo(address, processInfo)

    # access
    def getNamespec(self): return getNamespec(self.applicationName, self.processName)
    def stateAsString(self): return getProcessStateDescription(self.state)

    def isStopped(self): return self.state in STOPPED_STATES
    def isRunning(self): return self.state in RUNNING_STATES
    def isRunningOn(self, address): return self.isRunning() and address in self.addresses
    def isRunningLost(self): return self.isRunning() and not self.addresses

    def setState(self, state):
        if self.state != state:
            self.state = state
            options.logger.info('Process {} is {} at {}'.format(self.getNamespec(), self.stateAsString(), list(self.addresses)))

    # methods
    def addInfo(self, address, processInfo):
        # remove useless fields
        self.__filterInfo(processInfo)
        # store time info
        self.lastEventTime = processInfo['now']
        processInfo['eventTime'] = self.lastEventTime
        self._updateTimes(processInfo, self.lastEventTime, int(time.time()))
        # add info entry to process
        options.logger.debug('adding {} for {}'.format(processInfo, address))
        self.processes[address] = processInfo
        # update process status
        self._updateStatus(address, processInfo['state'], not processInfo['spawnerr']) 

    def updateInfo(self, address, processEvent):
        # do not add process in list while not added through tick
        if address in self.processes:
            processInfo = self.processes[address]
            options.logger.trace('inserting {} into {} at {}'.format(processEvent, processInfo, address))
            newState = processEvent['state']
            processInfo['state'] = newState
            processInfo['statename'] = getProcessStateDescription(newState)
            # manage times and pid
            remoteTime = processEvent['now']
            processInfo['eventTime'] = remoteTime
            self.lastEventTime = remoteTime
            self._updateTimes(processInfo, remoteTime, int(time.time()))
            if newState == ProcessStates.RUNNING:
                processInfo['pid'] = processEvent['pid']
            elif newState in [ ProcessStates.STARTING, ProcessStates.BACKOFF ]:
                processInfo['start'] = remoteTime
                processInfo['stop'] = 0
                processInfo['uptime'] = 0
            elif newState in STOPPED_STATES:
                processInfo['stop'] = remoteTime
                processInfo['pid'] = -1
                if newState == ProcessStates.EXITED:
                    # unexpected status is declared in spawnerr
                    processInfo['spawnerr'] = '' if processEvent['expected'] else 'Bad exit code (unknown)'
            # update / check running addresses
            self._updateStatus(address, newState, processEvent.get('expected', True))
            options.logger.debug('new processInfo: {}'.format(processInfo))
        else: options.logger.warn('ProcessEvent rejected for {}. wait for tick from {}'.format(self.processName, address))

    def updateRemoteTime(self, address, remoteTime, localTime):
        if address in self.processes:
            processInfo = self.processes[address]
            self._updateTimes(processInfo, remoteTime, localTime)

    def invalidateAddress(self, address):
        options.logger.debug("{} invalidateAddress {} / {}".format(self.getNamespec(), self.addresses, address))
        # reassign the difference between current set and parameter
        if address in self.addresses: self.addresses.remove(address)
        # check if conflict still applicable
        if not self._evaluateConflictingState():
            if len(self.addresses) == 1:
                # if only one address where process is running, the global state is the state of this process
                state = next(self.processes[address]['state'] for address in self.addresses)
                self.setState(state)
            elif self.isRunning():
                # addresses is empty for a running process. action expected to fix the inconsistency
                options.logger.warn('no more address for running process {}'.format(self.getNamespec()))
            elif self.state == ProcessStates.STOPPING:
                # STOPPING is the last state received before the address is lost. consider STOPPED now
                self.setState(ProcessStates.STOPPED)
        else:
            options.logger.debug('process {} still in conflict after address invalidation'.format(self.getNamespec()))

    def _updateStatus(self, address, newState, expected):
        if newState == ProcessStates.UNKNOWN:
            options.logger.warn('unexpected state {} for {} at {}'.format(getProcessStateDescription(newState), self.getNamespec(), address))
        else:
            # update addresses list
            if newState in STOPPED_STATES:
                self.addresses.discard(address)
            elif newState in RUNNING_STATES:
                # replace if current state stopped-like, add otherwise
                if self.isStopped():
                    self.addresses = { address }
                else:
                    self.addresses.add(address)
            # evaluate state iaw running addresses
            if not self._evaluateConflictingState():
                # if zero element, state is the state of the program addressed
                state = newState if not self.addresses else next(self.processes[address]['state'] for address in self.addresses)
                self.setState(state)
                self.expectedExit = expected

    def _evaluateConflictingState(self):
        if len(self.addresses) > 1:
            # several processes seems to be in a running state so that becomes tricky
            self.runningConflict = True
            states = { self.processes[address]['state'] for address in self.addresses }
            options.logger.debug('{} multiple states {} for addresses {}'.format(self.processName, [ getProcessStateDescription(x) for x in states ], list(self.addresses)))
            # state synthesis done using the sorting of RUNNING_STATES
            self.setState(self.__getRunningState(states))
            return True
        # no conflict anymore (if any before)
        self.runningConflict = False

    def _updateTimes(self, processInfo, remoteTime, localTime):
        processInfo['now'] = remoteTime
        processInfo['localTime'] = localTime
        if processInfo['state'] in [ ProcessStates.RUNNING, ProcessStates.STOPPING ]:
            processInfo['uptime'] = remoteTime - processInfo['start']

    def __filterInfo(self, processInfo):
        # remove following fields because not used in Supervisors and/or cannot be updated through process events
        useless_fields = [ 'description', 'stderr_logfile', 'stdout_logfile', 'logfile', 'exitstatus' ]
        for field in useless_fields: del processInfo[field]

    def __getRunningState(self, states):
        for state in RUNNING_STATES:
            if state in states: return state
        return ProcessStates.UNKNOWN
