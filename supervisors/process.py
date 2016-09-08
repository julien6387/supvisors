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

from supervisor.options import make_namespec
from supervisor.states import *

from supervisors.addressmapper import addressMapper
from supervisors.options import options
from supervisors.utils import *


def stringToProcessStates(strEnum):
    """ Get a string from Supervisor ProcessStates enumeration """
    return stringToEnum(ProcessStates.__dict__, strEnum)


class ProcessRules(object):
    """ Defines the rules for starting a process, iaw deployment file """

    def __init__(self):
        """ The constructor initializes the following attributes:
        - the addresses where the process can be started (all by default)
        - the order in the starting sequence of the application
        - a status telling if the process is required within the application
        - a status telling if Supervisors has to wait for the process to exit before triggering the next phase in the starting sequence of the application
        - the expected loading of the process on the considered hardware (can be anything at the user discretion: CPU, RAM, etc)
        """
        # TODO: see if dependency (process, application) is to be implemented
        self.addresses = ['*']
        self.sequence = -1
        self.required = False
        self.wait_exit = False
        self.expected_loading = 1

    def checkDependencies(self, logName):
        """ Update rules after they have been read from the deployment file
        a required process that is not in the starting sequence is forced to optional
        If addresses are not defined, all addresses are applicable """
        # required MUST have sequence, so force to optional if no sequence
        if self.required and self.sequence == -1:
            options.logger.warn('{} - required forced to False because no sequence defined'.format(logName))
            self.required = False
        # if no addresses, consider all addresses
        if not self.addresses:
            self.addresses = addressMapper.addresses
            options.logger.warn('{} - no address defined so all Supervisors addresses are applicable')

    def __str__(self):
        """ Contents as string """
        return 'addresses={} sequence={} required={} wait_exit={} loading={}'.format(self.addresses,
            self.sequence, self.required, self.wait_exit, self.expected_loading)


# ProcessStatus class
class ProcessStatus(object):
    """ Class defining the status of a process of Supervisors. It contains:
    - the application name, or group name from a Supervisor point of view
    - the process name
    - the synthetic state of the process, same enumeration as Supervisor
    - a status telling if the process has exited expectantly
    - the date of the last event received
    - a mark to restart the process when it is stopped (used when address is lost or when using a restart conciliation strategy)
    - the list of all addresses where the process is running
    - a Supervisor-like process info dictionary for each address (running or not)
    - the starting rules related to this process
    - a status telling if the waitExit rule is applicable (should be temporary)
    """
    def __init__(self, address, processInfo):
        # TODO: do I really need to keep all process info ? requests to Supervisor give the same...
        # wait for web development to decide
        self.applicationName = processInfo['group']
        self.processName = processInfo['name']
        self._state = ProcessStates.UNKNOWN
        self.expectedExit = True
        self.lastEventTime = None
        self.markForRestart = False
        # expected one single applicable address
        self.addresses = set() # addresses
        self.processes = {} # address: processInfo
        # rules part
        self.rules = ProcessRules()
        self.ignoreWaitExit = False
        # init parameters
        self.addInfo(address, processInfo)

    # access
    def getNamespec(self):
        """ Returns a namespec from application and process names """
        return make_namespec(self.applicationName, self.processName)

    def isStopped(self):
        """ Return True if process is stopped, as designed in Supervisor """
        return self.state in STOPPED_STATES

    def isRunning(self):
        """ Return True if process is running, as designed in Supervisor """
        return self.state in RUNNING_STATES

    def isRunningOn(self, address):
        """ Return True if process is running on address """
        return self.isRunning() and address in self.addresses

    def hasRunningPidOn(self, address):
        """ Return True if process is RUNNING on address 
        Different from isRunningOn as it considers only the RUNNING state and not STARTING or BACKOFF
        This is used by the statistics module that requires an existing PID """
        return self.state == ProcessStates.RUNNING and address in self.addresses

    # property for state access
    def _getState(self): return self._state
    def _setState(self, state):
        if self._state != state:
            self._state = state
            options.logger.info('Process {} is {} at {}'.format(self.getNamespec(), self.stateAsString(), list(self.addresses)))
    state = property(_getState, _setState)

    def runningConflict(self):
        """ Return True if the process is in a conflicting state (more than one instance running) """
        return len(self.addresses) > 1

    # serialization
    def toJSON(self):
        """ Return a JSON-serializable form of the ProcessStatus """
        return { 'applicationName': self.applicationName, 'processName': self.processName, 'state': self.stateAsString(),
            'expectedExit': self.expectedExit, 'lastEventTime': self.lastEventTime, 'addresses': list(self.addresses) }

    # methods
    def stateAsString(self):
        """ Return the state as a string """
        return getProcessStateDescription(self.state)

    def addInfo(self, address, processInfo):
        """ Insert a new Supervisor ProcessInfo in internal list """
        # remove useless fields
        self.__filterInfo(processInfo)
        # store time info
        self.lastEventTime = processInfo['now']
        processInfo['eventTime'] = self.lastEventTime
        self._updateTimes(processInfo, self.lastEventTime, int(time()))
        # add info entry to process
        options.logger.debug('adding {} for {}'.format(processInfo, address))
        self.processes[address] = processInfo
        # update process status
        self.updateStatus(address, processInfo['state'], not processInfo['spawnerr']) 

    def updateInfo(self, address, processEvent):
        """ Update the internal ProcessInfo from event received """
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
            self._updateTimes(processInfo, remoteTime, int(time()))
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
            self.updateStatus(address, newState, processEvent.get('expected', True))
            options.logger.debug('new processInfo: {}'.format(processInfo))
        else: options.logger.warn('ProcessEvent rejected for {}. wait for tick from {}'.format(self.processName, address))

    def updateRemoteTime(self, address, remoteTime, localTime):
        """ Update the time fields of the internal ProcessInfo when a new tick is received from the remote Supervisors instance """
        if address in self.processes:
            processInfo = self.processes[address]
            self._updateTimes(processInfo, remoteTime, localTime)

    def invalidateAddress(self, address):
        """ Update status of a process that was running on a lost address """
        options.logger.debug("{} invalidateAddress {} / {}".format(self.getNamespec(), self.addresses, address))
        # reassign the difference between current set and parameter
        if address in self.addresses: self.addresses.remove(address)
        # check if conflict still applicable
        if not self._evaluateConflictingState():
            if len(self.addresses) == 1:
                # if only one address where process is running, the global state is the state of this process
                state = next(self.processes[address]['state'] for address in self.addresses)
                self.state = state
            elif self.isRunning():
                # addresses is empty for a running process. action expected to fix the inconsistency
                options.logger.warn('no more address for running process {}'.format(self.getNamespec()))
                self.state = ProcessStates.FATAL
                self.markForRestart = True
            elif self.state == ProcessStates.STOPPING:
                # STOPPING is the last state received before the address is lost. consider STOPPED now
                self.state = ProcessStates.STOPPED
        else:
            options.logger.debug('process {} still in conflict after address invalidation'.format(self.getNamespec()))

    def updateStatus(self, address, newState, expected):
        """ Updates the state and list of running address iaw the new event """
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
                self.state = newState if not self.addresses else next(self.processes[address]['state'] for address in self.addresses)
                self.expectedExit = expected

    def _evaluateConflictingState(self):
        """ Gets a synthetic state if several processes are in a RUNNING-like state """
        if self.runningConflict():
            # several processes seems to be in a running state so that becomes tricky
            states = { self.processes[address]['state'] for address in self.addresses }
            options.logger.debug('{} multiple states {} for addresses {}'.format(self.processName, [ getProcessStateDescription(x) for x in states ], list(self.addresses)))
            # state synthesis done using the sorting of RUNNING_STATES
            self.state = self.__getRunningState(states)
            return True

    def _updateTimes(self, processInfo, remoteTime, localTime):
        """ Update time fields """
        processInfo['now'] = remoteTime
        processInfo['localTime'] = localTime
        if processInfo['state'] in [ ProcessStates.RUNNING, ProcessStates.STOPPING ]:
            processInfo['uptime'] = remoteTime - processInfo['start']

    def __filterInfo(self, processInfo):
        """ Remove from dictionary the fields that are not used in Supervisors and/or not updated through process events """
        map(processInfo.pop, [ 'description', 'stderr_logfile', 'stdout_logfile', 'logfile', 'exitstatus' ])

    def __getRunningState(self, states):
        """ Return the first matching state in RUNNING_STATES """
        return next((state for state in RUNNING_STATES if state in states), ProcessStates.UNKNOWN)

