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

from supervisors.application import ApplicationStates
from supervisors.infosource import infoSource
from supervisors.options import options
from supervisors.rpcrequests import internalStartProcess
from supervisors.types import deploymentStrategyToString

from supervisor.childutils import get_asctime
from supervisor.states import ProcessStates

import time

class _Deployer(object):
    def __init__(self):
        self.inProgress = {} # { applicationName: [ process ] }
        self.jobs = {} # { applicationName: { sequence: [ process ] } }
        self.strategy = options.deploymentStrategy

    # used to overload the default stragey (used in rpcinterface)
    def useStrategy(self, strategy):
        options.logger.info('deploy using strategy {}'.format(deploymentStrategyToString(strategy)))
        self.strategy = strategy

    def isDeploymentInProgress(self):
        options.logger.debug('deployment progress: jobs={} inProgress={}'.format(self._getPrintJobs(), self._getPrintInProgress()))
        return len(self.jobs) or len(self.inProgress)

    def deployApplications(self, applications):
        options.logger.info('deploy all applications')
        # internal call: default strategy always used
        self.useStrategy(options.deploymentStrategy)
        # deployment initialization: push program list in todo list
        for application in applications:
            # do not deploy an application that is not properly STOPPED
            if application.state == ApplicationStates.STOPPED and application.rules.autostart:
                self._getApplicationDeployment(application)
                application.reinitStatus()
        # start work
        self._initialJobs()

    def deployApplication(self, strategy, application):
        options.logger.info('deploy application {}'.format(application.applicationName))
        # called from rpcinterface: strategy is a user choice
        self.useStrategy(strategy)
        # push program list in todo list and start work
        if application.state == ApplicationStates.STOPPED:
            self._getApplicationDeployment(application)
            application.reinitStatus()
            self._processApplicationJobs(application.applicationName)
        # return True when deployment over
        return not self.isDeploymentInProgress()

    def deployProcess(self, strategy, process):
        options.logger.info('deploy process {}'.format(process.getNamespec()))
        # called from rpcinterface: strategy is a user choice
        self.useStrategy(strategy)
        # WARN: when deploying a single process (outside the scope of an application deployment), do NOT consider the 'wait_exit' rule
        process.ignoreWaitExit = True
        # push program list in todo list and start work
        inProgress = self.inProgress.setdefault(process.applicationName, [ ])
        self._processJob(process, inProgress)
        # upon failure, remove inProgress entry if empty
        if not inProgress:
            del self.inProgress[process.applicationName]
        # return True when deployment over
        return not self.isDeploymentInProgress()

    def deployMarkedProcesses(self, markedProcesses):
        # restart required processes first
        for process in markedProcesses:
            if process.rules.required:
                self.deployProcess(options.deploymentStrategy, process)
                process.markForRestart = False
        # restart optional processes
        for process in markedProcesses:
            if not process.rules.required:
                self.deployProcess(options.deploymentStrategy, process)
                process.markForRestart = False

    def checkDeployment(self):
        options.logger.debug('deployment progress: jobs={} inProgress={}'.format(self._getPrintJobs(), self._getPrintInProgress()))
        # once the startProcess has been called, a STARTING event is expected in less than 5 seconds
        now = int(time.time())
        processes= [ process for processList in self.inProgress.values() for process in processList ]
        options.logger.trace('now={} checking processes={}'.format(now, [ (process.processName, process.state, process.startRequest, process.lastEventTime) for process in processes ]))
        for process in processes:
            # depending on ini file, it may take a while before the process enters in RUNNING state
            # so just test that is in not in a STOPPED-like state 5 seconds after startRequest
            if process.isStopped() and max(process.lastEventTime, process.startRequest) + 5 < now:
                self._processFailure(process, 'Still stopped 5 seconds after start request', True)
        # return True when deployment is over
        return not self.isDeploymentInProgress()

    def deployOnEvent(self, process):
        # check if process event has an impact on deployment in progress
        if process.applicationName in self.inProgress:
            inProgress = self.inProgress[process.applicationName]
            if process in inProgress:
                if process.state in [ ProcessStates.STOPPED, ProcessStates.STOPPING, ProcessStates.UNKNOWN ]:
                    # unexpected event in a deployment phase
                    options.logger.error('unexpected event when deploying {}'.format(process.getNamespec()))
                elif process.state == ProcessStates.STARTING:
                    # on the way
                    pass
                elif process.state == ProcessStates.RUNNING:
                    # if not exit expected, job done. otherwise, wait
                    if not process.rules.wait_exit or process.ignoreWaitExit:
                        process.ignoreWaitExit = False
                        inProgress.remove(process)
                elif process.state == ProcessStates.BACKOFF:
                    # something wrong happened, just wait
                    options.logger.warn('problems detected with {}'.format(process.getNamespec()))
                elif process.state == ProcessStates.EXITED:
                    # anyway, remove from inProgress
                    process.ignoreWaitExit = False
                    inProgress.remove(process)
                    if process.rules.wait_exit and process.expectedExit:
                        options.logger.info('expected exit for {}'.format(process.getNamespec()))
                    else:
                        # missed. decide to continue degraded or to halt
                        self._processFailure(process, 'Unexpected exit')
                elif process.state == ProcessStates.FATAL:
                    # anyway, remove from inProgress
                    process.ignoreWaitExit = False
                    inProgress.remove(process)
                    # decide to continue deployment or not
                    self._processFailure(process, 'Unexpected crash')
                # check remaining jobs
                if len(inProgress) == 0:
                    # remove application entry for inProgress
                    del self.inProgress[process.applicationName]
                    # trigger next job for aplication
                    if process.applicationName in self.jobs:
                        self._processApplicationJobs(process.applicationName)
                    else: options.logger.info('deployment completed for application {}'.format(process.applicationName))

    def _getApplicationDeployment(self, application):
        # copy sequence and remove programs that are not meant to be deployed automatically
        sequence = application.sequence.copy()
        sequence.pop(-1, None)
        if len(sequence) > 0: self.jobs[application.applicationName] = sequence

    def _getStartingAddress(self, process):
        # find address iaw deployment rules, state of remotes and strategy
        from supervisors.strategy import addressSelector
        return addressSelector.getRemote(self.strategy, process.rules.addresses, process.rules.expected_loading)

    def _processApplicationJobs(self, applicationName):
        if applicationName in self.jobs:
            sequence = self.jobs[applicationName]
            self.inProgress[applicationName] = inProgress = [ ]
            # loop until there is something to check in list inProgress
            while len(sequence) > 0 and applicationName in self.jobs and len(inProgress) == 0:
                # pop lower group from sequence
                group = sequence.pop(min(sequence.keys()))
                options.logger.debug('application {} - next group: {}'.format(applicationName, self._getPrintProcessList(group)))
                for process in group:
                    # check state and start if not already RUNNING
                    options.logger.trace('{} - state={}'.format(process.getNamespec(), process.stateAsString()))
                    self._processJob(process, inProgress)
            # if nothing in progress when exiting the loop, delete application entry in list inProgress
            if len(inProgress) == 0:
                self.inProgress.pop(applicationName, None)
            # clean application job if its sequence is empty
            if len(sequence) == 0:
                options.logger.info('all jobs planned for application {}'.format(applicationName))
                self.jobs.pop(applicationName, None)
        else: options.logger.warn('application {} not found in jobs'.format(applicationName))

    def _processJob(self, process, inProgress):
        resetFlag = True
        # process is either stopped, or was running on a lost board
        if process.isStopped() or process.markedForRestart:
            fullProgramName = process.getNamespec()
            address = self._getStartingAddress(process)
            if address:
                options.logger.info('try to start {} at address={}'.format(fullProgramName, address))
                # use xml rpc to start program
                if internalStartProcess(address, fullProgramName, False):
                    # push to inProgress and timestamp process
                    process.startRequest = int(time.time())
                    options.logger.debug('{} requested to start at {}'.format(fullProgramName, get_asctime(process.startRequest)))
                    inProgress.append(process)
                    resetFlag = False
                else:
                    # when internalStartProcess returns false, this is a huge problem
                    # the process could not be started through supervisord and it is not even referenced in its internal strucutre
                    options.logger.critical('[BUG] RPC internalStartProcess failed {}'.format(fullProgramName))
            else:
                options.logger.warn('no resource available to start {}'.format(fullProgramName))
                self._processFailure(process, 'No resource available', True)
        # due to failure, reset ignoreWaitExit flag
        if resetFlag: process.ignoreWaitExit = False

    def _initialJobs(self):
        options.logger.info('deployment work: jobs={}'.format(self._getPrintJobs()))
        # iterate on copy to avoid problems with deletions
        for applicationName in self.jobs.keys()[:]:
            self._processApplicationJobs(applicationName)

    def _processFailure(self, process, reason, forceFatal=None):
        applicationName = process.applicationName
        # impact of failure upon application deployment
        if process.rules.required:
            options.logger.error('{} for required {}: halt deployment for application {}'.format(reason, process.processName, applicationName))
            # remove failed application from deployment
            # do not remove application from InProgress as requests have already been sent
            self.jobs.pop(applicationName, None)
        else:
            options.logger.info('{} for optional {}: continue deployment for application {}'.format(reason, process.processName, applicationName))
        # force process state to FATAL in supervisor so as it is published
        if forceFatal:
            options.logger.warn('force {} state to FATAL'.format(process.getNamespec()))
            infoSource.forceProcessFatalState(process.getNamespec(), reason)

    # log facilities
    def _getPrintJobs(self):
        return { applicationName: { sequence: self._getPrintProcessList(processes) for sequence, processes in sequences.items() }
            for applicationName, sequences in self.jobs.items() }

    def _getPrintProcessList(self, processes):
        return [ process.getNamespec() for process in processes ]

    def _getPrintInProgress(self):
        return [ process.getNamespec() for processes in self.inProgress.values() for process in processes ]

deployer = _Deployer()

