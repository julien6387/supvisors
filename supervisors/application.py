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

# Enumeration for ApplicationStates: same as ProcessStates without EXITED and BACKOFF
class ApplicationStates:
    UNKNOWN, STOPPED, STARTING, RUNNING, STOPPING, FATAL = range(6)

def applicationStateToString(value):
    return enumToString(ApplicationStates.__dict__, value)

def stringToApplicationState(strEnum):
    return stringToEnum(ApplicationStates.__dict__, strEnum)


# ApplicationRules class
class ApplicationRules(object):
    def __init__(self):
        # TODO: see if auto_order is to be implemented
        # TODO: see if stop_on_fatal is to be implemented
        self._autostart = False

    @property
    def autostart(self): return self._autostart
    @autostart.setter
    def autostart(self, value): self._autostart = value

    def __str__(self):
        return 'autostart={}'.format(self.autostart)


# ApplicationStatus class
class ApplicationStatus(object):
    def __init__(self, applicationName):
        # information part
        self._applicationName = applicationName
        self._state = ApplicationStates.UNKNOWN
        self._degraded = False
        # process part
        self._processes = { }
 
    # getters / setters
    @property
    def applicationName(self): return self._applicationName
    @property
    def processes(self): return self._processes
    @property
    def state(self): return self._state
    @property
    def degraded(self): return self._degraded

    # methods
    def stateAsString(self): return applicationStateToString(self.state)


# Application class
class ApplicationInfo(ApplicationStatus):
    def __init__(self, applicationName):
        super(ApplicationInfo, self).__init__(applicationName)
        self._rules = ApplicationRules()
        self._sequence = { } # sequence: processName

    # getters / setters
    @property
    def rules(self): return self._rules
    @property
    def sequence(self): return self._sequence

    def setState(self, state):
        if self.state != state:
            self._state = state
            opt.logger.info('Application {} is {}'.format(self.applicationName, self.stateAsString()))

    def setDegraded(self, degraded): self._degraded = degraded
    
   # methods
    def addProcess(self, process):
        self._processes[process.processName] = process

    def sequenceDeployment(self):
        # fill ordering iaw process rules
        self.sequence.clear()
        for process in self.processes.values():
            if process.rules.sequence in self.sequence:
                self.sequence[process.rules.sequence].append(process.processName)
            else:
                self.sequence.update( { process.rules.sequence: [ process.processName ] } )
        opt.logger.debug('Application {}: sequence={}'.format(self.applicationName, self.sequence))
        # TODO: check that process deployment addresses are compatible to supervisord config on that address
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
                process.setState(ProcessStates.STOPPED)
        self.updateStatus()

    def updateStatus(self):
        deployableSequence = [ x for x in self.sequence.keys() if x != -1 ]
        opt.logger.trace('Application {}: deployable={}'. format(self.applicationName, len(deployableSequence)))
        if len(deployableSequence): self._updateDeployableStatus()
        else: self._updateNonDeployableStatus()
        self._updateDegradedStatus()

    def _updateDeployableStatus(self):
        # application has a deployment definition. its state is only based upon the programs that are deployable
        starting = running = stopped = stopping = exited = fatal = False
        for process in self.processes.values():
            opt.logger.trace('Process {}: state={} required={} exitExpected={} sequence={}'. 
                format(process.getNamespec(), process.stateAsString(), process.rules.required, process.expectedExit, process.rules.sequence))
            if process.rules.sequence != -1:
                if process.state == ProcessStates.RUNNING: running = True
                elif process.state in [ ProcessStates.STARTING, ProcessStates.BACKOFF ]: starting = True
                # STOPPED-like cases are more complex
                # a FATAL required process is FATAL for application
                elif process.state == ProcessStates.FATAL and process.rules.required: fatal = True 
                # a FATAL optional process is not FATAL for application and should not prevent application to become RUNNING (leads to degraded only)
                elif process.state == ProcessStates.FATAL: exited = True 
                # similarly, an EXITED process is FATAL for application if required and exit code not expected (if not required, leads to degraded only)
                elif process.state == ProcessStates.EXITED and process.rules.required and not process.expectedExit: fatal = True
                # an expected EXITED state can be in STOPPED or RUNNING application
                elif process.state == ProcessStates.EXITED and process.expectedExit: exited = True
                # all other STOPPED-like states are considered normal
                elif process.state in STOPPED_STATES: stopped = True
                # STOPPING is not in STOPPED_STATES
                elif process.state == ProcessStates.STOPPING: stopping = True
        opt.logger.trace('Application {}: starting={} running={} stopped={} stopping={} exited={} fatal={}'. \
            format(self.applicationName, starting, running, stopped, stopping, exited, fatal))
        # apply rules for state
        if fatal: self.setState(ApplicationStates.FATAL)
        elif starting: self.setState(ApplicationStates.STARTING)
        elif stopping: self.setState(ApplicationStates.STOPPING)
        elif running and not stopped: self.setState(ApplicationStates.RUNNING) # whatever exited value
        elif (stopped or exited) and not running: self.setState( ApplicationStates.STOPPED)
        elif stopped and running: # whatever exited value
            # complex to decide if STARTING or STOPPING or FATAL
            # processes may be (maliciously ?) stopped / started using directly Supervisor, without any integrity control for the application
            # finally, accept that the user is knowing what he's doing and if not that's his loss
            if self.state in [ ApplicationStates.STOPPED, ApplicationStates.STARTING ]: self.setState(ApplicationStates.STARTING)
            elif self.state in [ ApplicationStates.RUNNING, ApplicationStates.STOPPING ]: self.setState(ApplicationStates.STOPPING)
            elif self.state == ApplicationStates.UNKNOWN:
                # apparently, either Supervisors has been started with a context mixing autostarted processes in ini files and deployment for these processes (thanks...)
                # or it has been restarted and depending on the situation, we can be in almost every state (help...)
                # as a conclusion, take the assumption that application is really in UNKNOWN state
                # for now, only a user request to stop the application could solve the problem
                pass
            # no need to consider current state FATAL because a STOPPING / STARTING process state is expected before arriving here
        else:
            opt.logger.error('Application {}: UNEXPECTED case - starting={} running={} stopped={} stopping={} exited={} fatal={}'. \
                format(self.applicationName, starting, running, stopped, stopping, exited, fatal))
            self.setState(ApplicationStates.UNKNOWN)

    def _updateNonDeployableStatus(self):
        # application has no deployment definition
        starting = running = unknown = stopping = False
        for process in self.processes.values():
                if process.state == ProcessStates.RUNNING: running = True
                elif process.state in [ ProcessStates.STARTING, ProcessStates.BACKOFF ]: starting = True
                elif process.state in STOPPED_STATES: unknown = True
                elif process.state == ProcessStates.STOPPING: stopping = True
        opt.logger.trace('Application {}: starting={} running={} unknown={} stopping={}'. \
            format(self.applicationName, starting, running, unknown, stopping))
        # apply rules for state
        if starting: self.setState(ApplicationStates.STARTING)
        elif stopping: self.setState(ApplicationStates.STOPPING)
        elif running: self.setState(ApplicationStates.RUNNING)
        else: self.setState(ApplicationStates.UNKNOWN)

    def _updateDegradedStatus(self):
        # the definition of the degraded status is common
        self.setDegraded(False)
        if self.state != ApplicationStates.FATAL: # FATAL is enough
            for process in self.processes.values():
                if not process.rules.required and (process.state == ProcessStates.FATAL or \
                    (process.state == ProcessStates.EXITED and not process.expectedExit)):
                    self.setDegraded(True)
                    break


# unit test
if __name__ == "__main__":
    print ApplicationStates.STARTING
    print ApplicationStateToString(ApplicationStates.STARTING)
    print stringToApplicationState('FATAL')
