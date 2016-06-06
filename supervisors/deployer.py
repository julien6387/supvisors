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
from supervisors.datahandlers import *
from supervisors.options import mainOptions as opt
from supervisors.rpcrequests import internalStartProcess
from supervisors.strategy import addressSelector
from supervisors.types import DeploymentStrategies, deploymentStrategyToString

from supervisor.childutils import get_asctime
from supervisor.states import ProcessStates

import time

class _Deployer(object):
    def __init__(self):
        self._strategy = DeploymentStrategies.CONFIG_ORDER
        self._inProgress = {} # { applicationName: [ process ] }
        self._jobs = {} # { applicationName: { sequence: [ processName ] } }

    @property
    def strategy(self): return self._strategy
    @strategy.setter
    def strategy(self, strategy): self._strategy = strategy

    def isDeploymentInProgress(self):
        opt.logger.debug('deployment progress: jobs={} inProgress={}'.format(self._jobs,
            [ process.getNamespec() for processes in self._inProgress.values() for process in processes ]))
        return len(self._jobs) != 0 or len(self._inProgress) != 0

    def deployAll(self):
        opt.logger.info('deploy all applications with strategy {}'.format(deploymentStrategyToString(self.strategy)))
        # deployment initialization: push program list in todo list
        for application in applicationsHandler.applications.values():
            # do not deploy an application that is not properly STOPPED
            if application.state == ApplicationStates.STOPPED and application.rules.autostart:
                self._getApplicationDeployment(application)
                application.reinitStatus()
        # start work
        self._initialJobs()
        # return True when deployment over
        return not self.isDeploymentInProgress()

    def deployApplication(self, applicationName):
        opt.logger.info('deploy application {} with strategy {}'.format(applicationName, deploymentStrategyToString(self.strategy)))
        # push program list in todo list and start work
        application = applicationsHandler.applications[applicationName]
        if application.state == ApplicationStates.STOPPED:
            self._getApplicationDeployment(application)
            application.reinitStatus()
            self._processApplicationJobs(applicationName)
        # return True when deployment over
        return not self.isDeploymentInProgress()

    def deployProcess(self, process):
        opt.logger.info('deploy process {} with strategy {}'.format(process.getNamespec(), deploymentStrategyToString(self.strategy)))
        # WARN: when deploying a single process (outside the scope of an application deployment),
        # only the 'addresses' and 'theoretical_loading' rules are considered
        process.ignoreRules = True
        # push program list in todo list and start work
        inProgress = self._inProgress.setdefault(process.applicationName, [ ])
        self._processJob(process, inProgress)
        # upon failure, remove inProgress entry if empty
        if not inProgress:
            del self._inProgress[process.applicationName]
        # return True when deployment over
        return not self.isDeploymentInProgress()

    def checkDeployment(self):
        opt.logger.debug('deployment progress: jobs={} inProgress={}'.format(self._jobs,
            [ process.getNamespec() for processes in self._inProgress.values() for process in processes ]))
        # once the startProcess has been called, a STARTING event is expected in less than 5 seconds
        now = int(time.time())
        processes= [ process for processList in self._inProgress.values() for process in processList ]
        opt.logger.trace('now={} checking processes={}'.format(now, [ (process.processName, process.state, process.startRequest, process.lastEventTime) for process in processes ]))
        for process in processes:
            # depending on ini file, it may take a while before the process enters in RUNNING state
            # so just test that is in not in a STOPPED-like state 5 seconds after startRequest
            if process.isStopped() and max(process.lastEventTime, process.startRequest) + 5 < now:
                self._processFailure(process, 'start failed')
        # return True when deployment is over
        return not self.isDeploymentInProgress()

    def deployOnEvent(self, process):
        # check if process event has an impact on deployment in progress
        if process.applicationName in self._inProgress:
            inProgress = self._inProgress[process.applicationName]
            if process in inProgress:
                if process.state in [ ProcessStates.STOPPED, ProcessStates.STOPPING, ProcessStates.UNKNOWN ]:
                    # unexpected event in a deployment phase
                    opt.logger.error('unexpected event when deploying {}'.format(process.getNamespec()))
                elif process.state == ProcessStates.STARTING:
                    # on the way
                    pass
                elif process.state == ProcessStates.RUNNING:
                    # if not exit expected, job done. otherwise, wait
                    if not process.rules.wait_exit or process.ignoreRules:
                        process.ignoreRules = False
                        inProgress.remove(process)
                elif process.state == ProcessStates.BACKOFF:
                    # something wrong happened, just wait
                    opt.logger.warn('problems detected with {}'.format(process.getNamespec()))
                elif process.state == ProcessStates.EXITED:
                    # anyway, remove from inProgress
                    inProgress.remove(process)
                    if process.ignoreRules:
                        process.ignoreRules = False
                    elif process.rules.wait_exit and process.expectedExit:
                        opt.logger.info('expected exit for {}'.format(process.getNamespec()))
                    else:
                        # missed. decide to continue degraded or to halt
                        self._processFailure(process, 'unexpected exit')
                elif process.state == ProcessStates.FATAL:
                    # anyway, remove from inProgress
                    inProgress.remove(process)
                    if process.ignoreRules:
                        process.ignoreRules = False
                    else:
                        # decide to continue deployment or not
                        self._processFailure(process, 'unexpected crash')
                # check remaining jobs
                if len(inProgress) == 0:
                    # remove application entry for inProgress
                    del self._inProgress[process.applicationName]
                    # trigger next job for aplication
                    if process.applicationName in self._jobs:
                        self._processApplicationJobs(process.applicationName)
                    else: opt.logger.info('deployment completed for application {}'.format(process.applicationName))

    def _getApplicationDeployment(self, application):
        # copy sequence and remove programs that are not meant to be deployed automatically
        sequence = application.sequence.copy()
        if -1 in sequence: del sequence[-1]
        if len(sequence) > 0: self._jobs[application.applicationName] = sequence

    def _getStartingAddress(self, process):
        # find address iaw deployment rules, state of remotes and strategy
        return addressSelector.getRemote(self.strategy, process.rules.addresses, process.rules.expected_loading)

    def _processApplicationJobs(self, applicationName):
        if applicationName in self._jobs:
            sequence = self._jobs[applicationName]
            self._inProgress[applicationName] = inProgress = [ ]
            # loop until there is something to check in list inProgress
            while len(sequence) > 0 and applicationName in self._inProgress and len(inProgress) == 0:
                # pop lower group from sequence
                group = sequence.pop(min(sequence.keys()))
                opt.logger.debug('application {} - next group: {}'.format(applicationName, group))
                for program in group:
                    # check state and start if not already RUNNING
                    process = applicationsHandler.getProcess(applicationName, program)
                    opt.logger.trace('{} - state={}'.format(process.getNamespec(), process.stateAsString()))
                    self._processJob(process, inProgress)
            # if nothing in progress when exiting the loop, delete application entry in list inProgress
            if applicationName in self._inProgress and len(inProgress) == 0:
                del self._inProgress[applicationName]
            # clean application job if its sequence is empty
            if len(sequence) == 0:
                opt.logger.info('all jobs planned for application {}'.format(applicationName))
                if applicationName in self._jobs.keys(): del self._jobs[applicationName]
        else: opt.logger.warn('application {} not found in jobs'.format(applicationName))

    def _processJob(self, process, inProgress):
        resetIgnoreRules = True
        if process.isStopped():
            fullProgramName = process.getNamespec()
            address = self._getStartingAddress(process)
            if address:
                opt.logger.info('try to start {} at address={}'.format(fullProgramName, address))
                # use xml rpc to start program
                if internalStartProcess(address, fullProgramName, False):
                    # push to inProgress and timestamp process
                    process.startRequest = int(time.time())
                    opt.logger.debug('{} requested to start at {}'.format(fullProgramName, get_asctime(process.startRequest)))
                    inProgress.append(process)
                    resetIgnoreRules = False
                else:
                    # when internalStartProcess returns false, this is a huge problem
                    # the process could not be started through supervisord and it is not even referenced in its internal strucutre
                    opt.logger.critical('[BUG] RPC internalStartProcess failed {}'.format(fullProgramName))
            else:
                opt.logger.warn('no resource available to start {}'.format(fullProgramName))
                if not process.ignoreRules:
                    self._processFailure(process, 'no resource available')
        # due to failure, reset ignoreRules flag
        if resetIgnoreRules: process.ignoreRules = False

    def _initialJobs(self):
        opt.logger.info('deployment work: jobs={}'.format(self._jobs))
        # iterate on copy to avoid problems with deletions
        for applicationName in self._jobs.keys()[:]:
            self._processApplicationJobs(applicationName)

    def _processFailure(self, process, reason):
        applicationName = process.applicationName
        # impact of failure upon application deployment
        if process.rules.required:
            opt.logger.error('{} for required {}: halt deployment for application {}'.format(reason, process.processName, applicationName))
            # remove failed application from deployment
            # do not remove application from InProgress as requests have already been sent
            if applicationName in self._jobs: del self._jobs[applicationName]
        else:
            opt.logger.info('{} for optional {}: continue deployment for application {}'.format(reason, process.processName, applicationName))


deployer = _Deployer()

