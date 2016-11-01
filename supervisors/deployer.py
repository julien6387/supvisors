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

import time

from supervisor.childutils import get_asctime
from supervisor.states import ProcessStates

from supervisors.application import ApplicationStates
from supervisors.strategy import get_address
from supervisors.ttypes import DeploymentStrategies
from supervisors.utils import supervisors_short_cuts


class Deployer(object):
    """ Class handling the starting of processes and applications.
    Attributes are:
    - strategy: the deployment strategy applied, defaulted to the value set in the Supervisor configuration file,
    - planned_jobs: a dictionary of processes to be started, grouped by application name and sequence order,
    - current_jobs: a dictionary of starting processes, grouped by application name. """

    def __init__(self, supervisors):
        """ Initialization of the attributes. """
        # keep a reference of the Supervisors data
        self.supervisors = supervisors
        # shortcuts for readability
        supervisors_short_cuts(self, ['logger'])
        #attributes
        self._strategy = supervisors.options.deployment_strategy
        self.planned_jobs = {} # {application_name: {sequence: [process]}}
        self.current_jobs = {} # {application_name: [process]}

    @property
    def strategy(self):
        """ Property for the 'strategy' attribute.
        The setter is used to overload the default strategy (used in rpcinterface and web page). """
        return self._strategy

    @strategy.setter
    def strategy(self, strategy):
        self.logger.info('deploy using strategy {}'.format(DeploymentStrategies._to_string(strategy)))
        self._strategy = strategy

    def in_progress(self):
        """ Return True if there are jobs planned or in progress. """
        self.logger.debug('deployment progress: jobs={} inProgress={}'.format(self.printable_planned_jobs(), self.printable_current_jobs()))
        return len(self.planned_jobs) or len(self.current_jobs)

    def deploy_applications(self, applications):
        """ Plan and start the necessary jobs to start all the applications ahving an autostart status.
        It uses the default strategy, as defined in the Supervisor configuration file. """
        self.logger.info('deploy all applications')
        # internal call: default strategy always used
        self.strategy = self.supervisors.options.deployment_strategy
        # deployment initialization: push program list in todo list
        for application in applications:
            # do not deploy an application that is not properly STOPPED
            if application.state == ApplicationStates.STOPPED and application.rules.autostart:
                self.get_application_deployment(application)
        # start work
        self.initial_jobs()

    def deploy_application(self, strategy, application):
        """ Plan and start the necessary jobs to start the application in parameter, with the strategy requested. """
        self.logger.info('deploy application {}'.format(application.application_name))
        # called from rpcinterface: strategy is a user choice
        self.strategy = strategy
        # push program list in todo list and start work
        if application.state == ApplicationStates.STOPPED:
            self.get_application_deployment(application)
            self.process_application_jobs(application.application_name)
        # return True when deployment over
        return not self.in_progress()

    def deploy_process(self, strategy, process):
        """ Plan and start the necessary job to start the process in parameter, with the strategy requested. """
        self.logger.info('deploy process {}'.format(process.namespec()))
        # called from rpcinterface: strategy is a user choice
        self.strategy = strategy
        # WARN: when deploying a single process (outside the scope of an application deployment), do NOT consider the 'wait_exit' rule
        process.ignore_wait_exit = True
        # push program list in todo list and start work
        job = self.current_jobs.setdefault(process.application_name, [])
        self.process_job(process, job)
        # upon failure, remove inProgress entry if empty
        if not job:
            del self.current_jobs[process.application_name]
        # return True when deployment over
        return not self.in_progress()

    def deploy_marked_processes(self, processes):
        """ Plan and start the necessary job to start the processes in parameter, with the default strategy. """
        # restart required processes first
        for process in processes:
            if process.rules.required:
                self.deploy_process(self.supervisors.options.deployment_strategy, process)
                process.mark_for_restart = False
        # restart optional processes
        for process in processes:
            if not process.rules.required:
                self.deploy_process(self.supervisors.options.deployment_strategy, process)
                process.mark_for_restart = False

    def check_deployment(self):
        """ Check the progress of the deployment. """
        self.logger.debug('deployment progress: jobs={} inProgress={}'.format(self.printable_planned_jobs(), self.printable_current_jobs()))
        # once the startProcess has been called, a STARTING event is expected in less than 5 seconds
        now = int(time.time())
        processes= [process for process_list in self.current_jobs.values() for process in process_list]
        self.logger.trace('now={} checking processes={}'.format(now,
            [(process.process_name, process.state, process.start_request, process.last_event_time) for process in processes]))
        for process in processes:
            # depending on ini file, it may take a while before the process enters in RUNNING state
            # so just test that is in not in a STOPPED-like state 5 seconds after start_request
            if process.stopped() and max(process.last_event_time, process.start_request) + 5 < now:
                self.process_failure(process, 'Still stopped 5 seconds after start request', True)
        # return True when deployment is over
        return not self.in_progress()

    def deploy_on_event(self, process):
        # check if process event has an impact on deployment in progress
        if process.application_name in self.current_jobs:
            jobs = self.current_jobs[process.application_name]
            if process in jobs:
                if process.state in [ProcessStates.STOPPED, ProcessStates.STOPPING, ProcessStates.UNKNOWN]:
                    # unexpected event in a deployment phase
                    self.logger.error('unexpected event when deploying {}'.format(process.namespec()))
                elif process.state == ProcessStates.STARTING:
                    # on the way
                    pass
                elif process.state == ProcessStates.RUNNING:
                    # if not exit expected, job done. otherwise, wait
                    if not process.rules.wait_exit or process.ignore_wait_exit:
                        process.ignore_wait_exit = False
                        jobs.remove(process)
                elif process.state == ProcessStates.BACKOFF:
                    # something wrong happened, just wait
                    self.logger.warn('problems detected with {}'.format(process.namespec()))
                elif process.state == ProcessStates.EXITED:
                    # anyway, remove from inProgress
                    process.ignore_wait_exit = False
                    jobs.remove(process)
                    if process.rules.wait_exit and process.expected_exit:
                        self.logger.info('expected exit for {}'.format(process.namespec()))
                    else:
                        # missed. decide to continue degraded or to halt
                        self.process_failure(process, 'Unexpected exit')
                elif process.state == ProcessStates.FATAL:
                    # anyway, remove from inProgress
                    process.ignore_wait_exit = False
                    jobs.remove(process)
                    # decide to continue deployment or not
                    self.process_failure(process, 'Unexpected crash')
                # check remaining jobs
                if len(jobs) == 0:
                    # remove application entry for in_progress
                    del self.current_jobs[process.application_name]
                    # trigger next job for aplication
                    if process.application_name in self.planned_jobs:
                        self.process_application_jobs(process.application_name)
                    else:
                        self.logger.info('deployment completed for application {}'.format(process.application_name))

    def get_application_deployment(self, application):
        # copy sequence and remove programs that are not meant to be deployed automatically
        sequence = application.start_sequence.copy()
        sequence.pop(-1, None)
        if len(sequence) > 0:
            self.planned_jobs[application.application_name] = sequence

    def process_application_jobs(self, application_name):
        if application_name in self.planned_jobs:
            sequence = self.planned_jobs[application_name]
            self.current_jobs[application_name] = jobs = []
            # loop until there is something to check in list inProgress
            while len(sequence) > 0 and application_name in self.planned_jobs and len(jobs) == 0:
                # pop lower group from sequence
                group = sequence.pop(min(sequence.keys()))
                self.logger.debug('application {} - next group: {}'.format(application_name, self.printable_process_list(group)))
                for process in group:
                    # check state and start if not already RUNNING
                    self.logger.trace('{} - state={}'.format(process.namespec(), process.state_string()))
                    self.process_job(process, jobs)
            # if nothing in progress when exiting the loop, delete application entry in list inProgress
            if len(jobs) == 0:
                self.current_jobs.pop(application_name, None)
            # clean application job if its sequence is empty
            if len(sequence) == 0:
                self.logger.info('all jobs planned for application {}'.format(application_name))
                self.planned_jobs.pop(application_name, None)
        else:
            self.logger.warn('application {} not found in jobs'.format(application_name))

    def process_job(self, process, jobs):
        reset_flag = True
        # process is either stopped, or was running on a lost board
        if process.stopped() or process.mark_for_restart:
            namespec = process.namespec()
            address = get_address(self.supervisors, self.strategy, process.rules.addresses, process.rules.expected_loading)
            if address:
                self.logger.info('try to start {} at address={}'.format(namespec, address))
                # use xml rpc to start program
                if self.supervisors.requester.internal_start_process(address, namespec, False):
                    # push to inProgress and timestamp process
                    process.start_request = int(time.time())
                    self.logger.debug('{} requested to start at {}'.format(namespec, get_asctime(process.start_request)))
                    jobs.append(process)
                    reset_flag = False
                else:
                    # when internalStartProcess returns false, this is a huge problem
                    # the process could not be started through supervisord and it is not even referenced in its internal strucutre
                    self.logger.critical('[BUG] RPC internalStartProcess failed {}'.format(namespec))
            else:
                self.logger.warn('no resource available to start {}'.format(namespec))
                self.process_failure(process, 'No resource available', True)
        # due to failure, reset ignoreWaitExit flag
        if reset_flag:
            process.ignore_wait_exit = False

    def initial_jobs(self):
        self.logger.info('deployment work: jobs={}'.format(self.printable_planned_jobs()))
        # iterate on copy to avoid problems with deletions
        for application_name in self.planned_jobs.keys()[:]:
            self.process_application_jobs(application_name)

    def process_failure(self, process, reason, force_fatal=None):
        application_name = process.application_name
        # impact of failure upon application deployment
        if process.rules.required:
            self.logger.error('{} for required {}: halt deployment for application {}'.format(reason, process.process_name, application_name))
            # remove failed application from deployment
            # do not remove application from InProgress as requests have already been sent
            self.planned_jobs.pop(application_name, None)
        else:
            self.logger.info('{} for optional {}: continue deployment for application {}'.format(reason, process.process_name, application_name))
        # force process state to FATAL in supervisor so as it is published
        if force_fatal:
            self.logger.warn('force {} state to FATAL'.format(process.namespec()))
            try:
                self.supervisors.info_source.force_process_fatal(process.namespec(), reason)
            except KeyError:
                self.logger.error('impossible to force {} state to FATAL. process unknown in this Supervisor'.format(process.namespec()))
                # FIXME: what can i do then ?

    # log facilities
    def printable_planned_jobs(self):
        return {application_name: {sequence: self.printable_process_list(processes) for sequence, processes in sequences.items()}
            for application_name, sequences in self.planned_jobs.items()}

    def printable_process_list(self, processes):
        return [process.namespec() for process in processes]

    def printable_current_jobs(self):
        return [process.namespec() for processes in self.current_jobs.values() for process in processes]

