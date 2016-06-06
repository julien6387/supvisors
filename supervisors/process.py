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

from supervisors.options import mainOptions as opt
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
        self._addresses = [ '*' ] # all addresses are applicable by default
        self._sequence = -1
        self._required = False
        self._wait_exit = False
        self._expected_loading = 1

    @property
    def addresses(self): return self._addresses
    @addresses.setter
    def addresses(self, value): self._addresses = value
    @property
    def sequence(self): return self._sequence
    @sequence.setter
    def sequence(self, value): self._sequence = value
    @property
    def required(self): return self._required
    @required.setter
    def required(self, value): self._required = value
    @property
    def wait_exit(self): return self._wait_exit
    @wait_exit.setter
    def wait_exit(self, value): self._wait_exit = value
    @property
    def expected_loading(self): return self._expected_loading
    @expected_loading.setter
    def expected_loading(self, value): self._expected_loading = value

    def checkDependencies(self, logName):
        # required MUST have sequence, so force to optional if no sequence
        if self.required and self._sequence == -1:
            opt.logger.warn('{} - required forced to False because no sequence defined'.format(logName))
            self.required = False
        # if no addresses, consider all addresses
        if not self.addresses:
            from supervisors.addressmapper import addressMapper
            self.addresses = addressMapper.expectedAddresses 
            opt.logger.warn('{} - no address defined so all Supervisors addresses are applicable')

    def __str__(self):
        return 'addresses={} sequence={} required={} wait_exit={} loading={}'.format(self.addresses,
            self.sequence, self.required, self.wait_exit, self.expected_loading)


# ProcessStatus class: only storage and access
class ProcessStatus(object):
    def __init__(self, applicationName, processName):
        # TODO: do I really need to keep all process info ? requests to Supervisor give the same...
        # wait for web development to decide
        # TODO: consider using supervisor.process Subprocess and adding missing information ?
        self._applicationName = applicationName
        self._processName = processName
        self._state = ProcessStates.UNKNOWN
        self._expectedExit = True
        self._lastEventTime = None
        self._multipleRunningAllowed = False
        self._runningConflict = False
        # expected one single applicable address, but multiple processes like Listener
        self._addresses = set() # addresses
        self._processes = {} # address: processInfo

    # getters / setters
    @property
    def applicationName(self): return self._applicationName
    @property
    def processName(self): return self._processName
    @property
    def state(self):  return self._state
    @property
    def expectedExit(self):  return self._expectedExit
    @property
    def lastEventTime(self):  return self._lastEventTime
    @property
    def runningConflict(self):  return self._runningConflict
    @property
    def multipleRunningAllowed(self):  return self._multipleRunningAllowed
    @property
    def addresses(self):  return self._addresses
    @property
    def processes(self):  return self._processes

    # methods
    def getNamespec(self): return getNamespec(self.applicationName, self.processName)
    def getProcessInfo(self): return { address: self.processes[address] for address in self.addresses }
    def isRunning(self): return self.state in RUNNING_STATES
    def isStopped(self): return self.state in STOPPED_STATES
    def stateAsString(self): return getProcessStateDescription(self.state)

    def isRunningOn(self, address): return self.isRunning() and address in self.addresses


# Process class: behaviour and setters
class Process(ProcessStatus):
    def __init__(self, address, processInfo):
        super(Process, self).__init__(processInfo['group'], processInfo['name'])
        self._rules = ProcessRules()
        # some rules may be ignored temporarily when starting a process outside the scope of an application
        self._ignoreRules = False
        self.addInfo(address, processInfo)

    @property
    def rules(self): return self._rules
    @property
    def ignoreRules(self): return self._ignoreRules
    @ignoreRules.setter
    def ignoreRules(self, value): self._ignoreRules = value

    def setState(self, state):
        if self.state != state:
            self._state = state
            opt.logger.info('Process {} is {} at {}'.format(self.getNamespec(), self.stateAsString(), list(self.addresses)))

    def setMultipleRunningAllowed(self, value):
        self._multipleRunningAllowed = value

    # methods
    def addInfo(self, address, processInfo):
        self.__filterInfo(processInfo)
        self._lastEventTime = processInfo['now']
        processInfo['eventTime'] = self._lastEventTime
        self._updateTimes(processInfo, self._lastEventTime, int(time.time()))
        opt.logger.debug('adding {} for {}'.format(processInfo, address))
        self.processes[address] = processInfo
        self._updateStatus(address, processInfo['state']) 

    def updateInfo(self, address, processEvent):
        # do not add process in list while not added through tick
        if address in self.processes:
            processInfo = self.processes[address]
            opt.logger.trace('inserting {} into {} at {}'.format(processEvent, processInfo, address))
            newState = processEvent['state']
            processInfo['state'] = newState
            processInfo['statename'] = getProcessStateDescription(newState)
            # update / check running addresses
            self._updateStatus(address, newState)
            # manage times and pid
            remoteTime = processEvent['now']
            processInfo['eventTime'] = remoteTime
            self._lastEventTime = remoteTime
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
            opt.logger.debug('new processInfo: {}'.format(processInfo))
        else: opt.logger.warn('ProcessEvent rejected for {}. wait for tick from {}'.format(self.processName, address))

    def updateRemoteTime(self, address, remoteTime, localTime):
        if address in self.processes:
            processInfo = self.processes[address]
            self._updateTimes(processInfo, remoteTime, localTime)

    # ude to force state, particularly upon error at start request
    def updateState(self, address, newState):
        if address in self.processes:
            processInfo = self.processes[address]
            processInfo['state'] = newState
            processInfo['statename'] = getProcessStateDescription(newState)
            self._updateStatus(address, newState)

    def _updateStatus(self, address, newState):
        if newState == ProcessStates.UNKNOWN:
            opt.logger.warn('unexpected state {} for {} at {}'.format(getProcessStateDescription(newState), self.processName, address))
        else:
            # update addresses list
            if newState in STOPPED_STATES:
                if address in self._addresses: self._addresses.remove(address)
            elif newState in RUNNING_STATES:
                # replace if current state stopped-like, add otherwise
                if self.isStopped():
                    self._addresses = { address }
                else:
                    self.addresses.add(address)
            # determine a synthetic state
            processes = self.getProcessInfo()
            # no running process, so consider the last event as the one applicable
            # it doesn't really make sense to set an address for STOPPED process but information like 'exit expectation' is required
            if len(processes) == 0:
                self._addresses = { address }
                processes = self.getProcessInfo()
            opt.logger.trace('process list {}'.format(processes))
            # if only one element, state is the state of the program addressed
            if len(processes) == 1:
                self.setState(newState)
                self._runningConflict = False
            else:
                # several processes are like running so that becomes tricky
                self._runningConflict = not self.multipleRunningAllowed
                states = { x['state'] for x in processes.itervalues() }
                opt.logger.debug('{} multiple states {} for addresses {}'.format(self.processName, [ getProcessStateDescription(x) for x in states ], list(self.addresses)))
                # state synthesis done using the sorting of RUNNING_STATES
                self.setState(self.__getRunningState(states))

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
