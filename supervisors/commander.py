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

from supervisors.strategy import get_address
from supervisors.ttypes import DeploymentStrategies
from supervisors.utils import supervisors_short_cuts


class Commander(object):
    """ Base class handling the starting / stopping of processes and applications.
    Attributes are:
    - planned_sequence: the applications to be commanded, as a dictionary of processes,
        grouped by application sequence order, application name and process sequence order,
    - planned_jobs: the current sequence of applications to be commanded,
        as a dictionary of processes, grouped by application name and process sequence order,
    - current_jobs: a dictionary of commanded processes, grouped by application name. """

    def __init__(self, supervisors):
        """ Initialization of the attributes. """
        # keep a reference of the Supervisors data
        self.supervisors = supervisors
        # shortcuts for readability
        supervisors_short_cuts(self, ['logger'])
        #attributes
        self.planned_sequence = {} # {application_sequence: {application_name: {process_sequence: [process]}}}
        self.planned_jobs = {} # {application_name: {process_sequence: [process]}}
        self.current_jobs = {} # {application_name: [process]}

    def in_progress(self):
        """ Return True if there are jobs planned or in progress. """
        self.logger.debug('progress: planned_sequence={} planned_jobs={} current_jobs={}'.format(
            self.printable_planned_sequence(), self.printable_planned_jobs(), self.printable_current_jobs()))
        return len(self.planned_sequence) or len(self.planned_jobs) or len(self.current_jobs)

    # log facilities
    def printable_planned_sequence(self):
        return {application_sequence:
                {application_name:
                    {sequence: self.printable_process_list(processes) for sequence, processes in sequences.items()}
                for application_name, sequences in applications.items()}
            for application_sequence, applications in self.planned_sequence.items()}

    def printable_planned_jobs(self):
        return {application_name:
                {sequence: self.printable_process_list(processes) for sequence, processes in sequences.items()}
            for application_name, sequences in self.planned_jobs.items()}

    def printable_current_jobs(self):
        return {application_name: self.printable_process_list(processes) for application_name, processes in self.current_jobs.items()}

    def printable_process_list(self, processes):
        return [process.namespec() for process in processes]

    def initial_jobs(self):
        self.logger.info('planned_sequence={}'.format(self.printable_planned_sequence()))
        # pop lower application group from planned_sequence
        if self.planned_sequence:
            self.planned_jobs = self.planned_sequence.pop(min(self.planned_sequence.keys()))
            self.logger.info('planned_jobs={}'.format(self.printable_planned_jobs()))
            # iterate on copy to avoid problems with deletions
            for application_name in self.planned_jobs.keys()[:]:
                self.process_application_jobs(application_name)
        else:
            self.logger.info('command completed')

    def process_application_jobs(self, application_name):
        if application_name in self.planned_jobs:
            sequence = self.planned_jobs[application_name]
            self.current_jobs[application_name] = jobs = []
            # loop until there is something to do in sequence
            while sequence and not jobs and application_name in self.planned_jobs:
                # pop lower group from sequence
                group = sequence.pop(min(sequence.keys()))
                self.logger.info('application {} - next group: {}'.format(application_name, self.printable_process_list(group)))
                for process in group:
                    self.logger.trace('{} - state={}'.format(process.namespec(), process.state_string()))
                    self.process_job(process, jobs)
            # if nothing in progress when exiting the loop, delete application entry in current_jobs
            if not jobs:
                self.current_jobs.pop(application_name, None)
            # clean application job if its sequence is empty
            if not sequence:
                self.logger.info('all jobs planned for application {}'.format(application_name))
                self.planned_jobs.pop(application_name, None)
        else:
            self.logger.warn('application {} not found in jobs'.format(application_name))


class Starter(Commander):
    """ Class handling the starting of processes and applications.
    Attributes are:
    - strategy: the deployment strategy applied, defaulted to the value set in the Supervisor configuration file, """

    def __init__(self, supervisors):
        """ Initialization of the attributes. """
        Commander.__init__(self, supervisors)
        #attributes
        self._strategy = supervisors.options.deployment_strategy

    @property
    def strategy(self):
        """ Property for the 'strategy' attribute.
        The setter is used to overload the default strategy (used in rpcinterface and web page). """
        return self._strategy

    @strategy.setter
    def strategy(self, strategy):
        self.logger.info('start applications using strategy {}'.format(DeploymentStrategies._to_string(strategy)))
        self._strategy = strategy

    def start_applications(self, applications):
        """ Plan and start the necessary jobs to start all the applications having a start_sequence.
        It uses the default strategy, as defined in the Supervisor configuration file. """
        self.logger.info('start all applications')
        # internal call: default strategy always used
        self.strategy = self.supervisors.options.deployment_strategy
        # deployment initialization: push program list in todo list
        for application in applications:
            # do not deploy an application that is not properly STOPPED
            if application.stopped() and application.rules.start_sequence > 0:
                self.store_application_start_sequence(application)
        # start work
        self.initial_jobs()

    def start_application(self, strategy, application):
        """ Plan and start the necessary jobs to start the application in parameter, with the strategy requested. """
        self.logger.info('start application {}'.format(application.application_name))
        # called from rpcinterface: strategy is a user choice
        self.strategy = strategy
        # push program list in todo list and start work
        if application.stopped():
            self.store_application_start_sequence(application)
            self.logger.info('planned_sequence={}'.format(self.printable_planned_sequence()))
            # add application immediately to planned jobs
            self.planned_jobs.update(self.planned_sequence.pop(min(self.planned_sequence.keys())))
            self.process_application_jobs(application.application_name)
        # return True when deployment over
        return not self.in_progress()

    def start_process(self, strategy, process):
        """ Plan and start the necessary job to start the process in parameter, with the strategy requested. """
        self.logger.info('start process {}'.format(process.namespec()))
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

    def start_marked_processes(self, processes):
        """ Plan and start the necessary job to start the processes in parameter, with the default strategy. """
        # restart required processes first
        for process in processes:
            if process.rules.required:
                self.start_process(self.supervisors.options.deployment_strategy, process)
                process.mark_for_restart = False
        # restart optional processes
        for process in processes:
            if not process.rules.required:
                self.start_process(self.supervisors.options.deployment_strategy, process)
                process.mark_for_restart = False

    def check_starting(self):
        """ Check the progress of the application starting. """
        self.logger.debug('starting progress: planned_sequence={} planned_jobs={} current_jobs={}'.format(
            self.printable_planned_sequence(), self.printable_planned_jobs(), self.printable_current_jobs()))
        # once the start_process has been called, a STARTING event is expected in less than 5 seconds
        now = time.time()
        processes= [process for process_list in self.current_jobs.values() for process in process_list]
        self.logger.trace('now={} checking processes={}'.format(now,
            [(process.process_name, process.state, process.request_time, process.last_event_time) for process in processes]))
        for process in processes:
            # depending on ini file, it may take a while before the process enters in RUNNING state
            # so just test that is in not in a STOPPED-like state 5 seconds after request_time
            if process.stopped() and max(process.last_event_time, process.request_time) + 5 < now:
                self.process_failure(process, 'Still stopped 5 seconds after start request', True)
        # return True when starting is completed
        return not self.in_progress()

    def on_event(self, process):
        # check if process event has an impact on starting in progress
        if process.application_name in self.current_jobs:
            jobs = self.current_jobs[process.application_name]
            if process in jobs:
                if process.state in [ProcessStates.STOPPED, ProcessStates.STOPPING, ProcessStates.UNKNOWN]:
                    # unexpected event in a starting phase
                    self.logger.error('unexpected event when starting {}'.format(process.namespec()))
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
                        self.process_failure(process, 'unexpected exit')
                elif process.state == ProcessStates.FATAL:
                    # anyway, remove from inProgress
                    process.ignore_wait_exit = False
                    jobs.remove(process)
                    # decide to continue deployment or not
                    self.process_failure(process, 'unexpected crash')
                # check if there are remaining jobs in progress for this application
                if not jobs:
                    # remove application entry from current_jobs
                    del self.current_jobs[process.application_name]
                    # trigger next job for aplication
                    if process.application_name in self.planned_jobs:
                        self.process_application_jobs(process.application_name)
                    else:
                        self.logger.info('starting completed for application {}'.format(process.application_name))
                        # check if there are planned jobs
                        if not self.planned_jobs:
                            # trigger next sequence of applications
                            self.initial_jobs()

    def store_application_start_sequence(self, application):
        # copy sequence and remove programs that are not meant to be deployed automatically, i.e. their start_sequence is 0
        application_sequence = application.start_sequence.copy()
        application_sequence.pop(0, None)
        if len(application_sequence) > 0:
            sequence = self.planned_sequence.setdefault(application.rules.start_sequence, {})
            sequence[application.application_name] = application_sequence

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
                    # push to jobs and timestamp process
                    process.request_time = time.time()
                    self.logger.debug('{} requested to start at {}'.format(namespec, get_asctime(process.request_time)))
                    jobs.append(process)
                    reset_flag = False
                else:
                    # this should not happen but log a critical message, just in case...
                    self.logger.critical('[BUG] RPC internal_start_process failed {}'.format(namespec))
            else:
                self.logger.warn('no resource available to start {}'.format(namespec))
                self.process_failure(process, 'no resource available', True)
        # due to failure, reset ignore_wait_exit flag
        if reset_flag:
            process.ignore_wait_exit = False

    def process_failure(self, process, reason, force_fatal=None):
        application_name = process.application_name
        # impact of failure upon application deployment
        if process.rules.required:
            self.logger.error('{} for required {}: halt deployment for application {}'.format(reason, process.process_name, application_name))
            # remove failed application from deployment
            # do not remove application from InProgress as requests have already been sent
            self.planned_jobs.pop(application_name, None)
        else:
            self.logger.info('{} for optional {}: continue starting of application {}'.format(reason, process.process_name, application_name))
        if force_fatal:
            # publish the process state as FATAL to all Supervisors instances
            self.logger.warn('force {} state to FATAL'.format(process.namespec()))
            try:
                self.supervisors.info_source.force_process_fatal(process.namespec(), reason)
            except KeyError:
                self.logger.error('impossible to force {} state to FATAL. process unknown in this Supervisor'.format(process.namespec()))
                # the Supervisors user is not forced to use the same process configuration on all machines,
                # although it is strongly recommended to avoid troubles.
                # so, publish directly a fake process event
                self.supervisors.listener.force_process_fatal(process.namespec())

class Stopper(Commander):
    """ Class handling the stopping of processes and applications. """

    def stop_applications(self, applications):
        """ Plan and start the necessary jobs to stop all the applications having a stop_sequence. """
        self.logger.info('stop all applications')
        # deployment initialization: push program list in todo list
        for application in applications:
            # do not deploy an application that is not properly STOPPED
            if application.running() and application.rules.stop_sequence >= 0:
                self.store_application_stop_sequence(application)
        # start work
        self.initial_jobs()

    def stop_application(self, application):
        """ Plan and start the necessary jobs to stop the application in parameter. """
        self.logger.info('stop application {}'.format(application.application_name))
        # push program list in todo list and start work
        if application.running():
            self.store_application_stop_sequence(application)
            self.logger.info('planned_sequence={}'.format(self.printable_planned_sequence()))
            # add application immediately to planned jobs
            self.planned_jobs.update(self.planned_sequence.pop(min(self.planned_sequence.keys())))
            self.process_application_jobs(application.application_name)
        # return True when deployment over
        return not self.in_progress()

    def store_application_stop_sequence(self, application):
        if application.stop_sequence:
            sequence = self.planned_sequence.setdefault(application.rules.stop_sequence, {})
            sequence[application.application_name] = application.stop_sequence
 
    def process_job(self, process, jobs):
        if process.running():
            # use xml rpc to stop program
            for address in process.addresses.copy():
                self.logger.info('stopping process {} on {}'.format(process.namespec(), address))
                self.supervisors.requester.stop_process(address, process.namespec(), False)
            # push to jobs and timestamp process
            process.request_time = time.time()
            self.logger.debug('{} requested to stop at {}'.format(process.namespec(), get_asctime(process.request_time)))
            jobs.append(process)

    def on_event(self, process):
        # check if process event has an impact on stopping in progress
        if process.application_name in self.current_jobs:
            jobs = self.current_jobs[process.application_name]
            if process in jobs:
                if process.running():
                    # assuming that we are stopping a process that is starting or unexpected event
                    self.logger.warn('unexpected event when stopping {}'.format(process.namespec()))
                elif process.stopped():
                    # goal reached, whatever the state
                    jobs.remove(process)
                # else STOPPING, on the way
                # check if there are remaining jobs in progress for this application
                if not jobs:
                    # remove application entry from current_jobs
                    del self.current_jobs[process.application_name]
                    # trigger next job for aplication
                    if process.application_name in self.planned_jobs:
                        self.process_application_jobs(process.application_name)
                    else:
                        self.logger.info('starting completed for application {}'.format(process.application_name))
                        # check if there are planned jobs
                        if not self.planned_jobs:
                            # trigger next sequence of applications
                            self.initial_jobs()
