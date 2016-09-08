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

from supervisor.states import *

from supervisors.options import options
from supervisors.utils import *
from supervisors.types import StartingFailureStrategies, RunningFailureStrategies


# Enumeration for ApplicationStates
class ApplicationStates:
    UNKNOWN, STOPPED, STARTING, RUNNING, STOPPING = range(5)

def applicationStateToString(value):
    return enumToString(ApplicationStates.__dict__, value)

def stringToApplicationState(strEnum):
    return stringToEnum(ApplicationStates.__dict__, strEnum)


# ApplicationRules class
class ApplicationRules(object):
    """ Defines the rules for starting an application, iaw deployment file """

    def __init__(self):
        self.autostart = False
        # TODO: implement sequence
        self.sequence = -1
        # TODO: implement starting failure strategy
        self.starting_failure_strategy = StartingFailureStrategies.ABORT
        # TODO: implement running failure strategy
        self.running_failure_strategy = RunningFailureStrategies.CONTINUE

    def __str__(self):
        """ Contents as string """
        return 'autostart={}'.format(self.autostart)


# ApplicationStatus class
class ApplicationStatus(object):
    def __init__(self, applicationName):
        # information part
        self.applicationName = applicationName
        self._state = ApplicationStates.UNKNOWN
        self.majorFailure = False
        self.minorFailure = False
        # process part
        self.processes = { }
        self.rules = ApplicationRules()
        self.sequence = { } # { sequence: [ process ] }

    # access
    def isRunning(self):
        return self.state in [ApplicationStates.STARTING, ApplicationStates.RUNNING]

    def isStopped(self):
        return self.state in [ApplicationStates.UNKNOWN, ApplicationStates.STOPPED]
 
    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, newState):
        if self._state != newState:
            self._state = newState
            options.logger.info('Application {} is {}'.format(self.applicationName, self.stateAsString()))

    # serialization
    def toJSON(self):
        return { 'applicationName': self.applicationName, 'state': self.stateAsString(),
            'majorFailure': self.majorFailure, 'minorFailure': self.minorFailure }

    # methods
    def stateAsString(self): return applicationStateToString(self.state)

    def addProcess(self, process):
        self.processes[process.processName] = process

    def sequenceDeployment(self):
        # fill ordering iaw process rules
        self.sequence.clear()
        for process in self.processes.values():
            self.sequence.setdefault(process.rules.sequence, [ ]).append(process)
        options.logger.debug('Application {}: sequence={}'.format(self.applicationName, self.sequence))
        # evaluate application
        self.updateStatus()

    def updateRemoteTime(self, address, remoteTime, localTime):
        for process in self.processes.values():
            process.updateRemoteTime(address, remoteTime, localTime)

    def reinitStatus(self):
        # called before a deployment on this application
        # aim is to force to STOPPED all STOPPED-like processes to simplify later elaboration of application status 
        for process in self.processes.values():
            if process.state in STOPPED_STATES:
                process.state = ProcessStates.STOPPED
        self.updateStatus()

    # try this updateStatus instead of the next one
    def updateStatus(self):
        starting = running = stopping = majorFailure = minorFailure = False
        for process in self.processes.values():
            options.logger.trace('Process {}: state={} required={} exitExpected={}'.
                format(process.getNamespec(), process.stateAsString(), process.rules.required, process.expectedExit))
            if process.state == ProcessStates.RUNNING: running = True
            elif process.state in [ ProcessStates.STARTING, ProcessStates.BACKOFF ]: starting = True
            # STOPPING is not in STOPPED_STATES
            elif process.state == ProcessStates.STOPPING:
                stopping = True
            # a FATAL required (resp. optional) process is a major (resp. minor) failure for application
            # similarly, an EXITED process is a major (resp. minor) failure for application if required (resp. optional) and exit code not expected
            elif (process.state == ProcessStates.FATAL) or (process.state == ProcessStates.EXITED and not process.expectedExit):
               if process.rules.required: majorFailure = True
               else: minorFailure = True
            # all other STOPPED-like states are considered normal
        options.logger.trace('Application {}: starting={} running={} stopping={} majorFailure={} minorFailure={}'.
            format(self.applicationName, starting, running, stopping, majorFailure, minorFailure))
        # apply rules for state
        if starting: self.state = ApplicationStates.STARTING
        elif stopping: self.state = ApplicationStates.STOPPING
        elif running: self.state = ApplicationStates.RUNNING
        else: self.state = ApplicationStates.STOPPED
        # update majorFailure and minorFailure status (only for RUNNING-like applications)
        self.majorFailure = majorFailure and self.isRunning()
        self.minorFailure = minorFailure and self.isRunning()
