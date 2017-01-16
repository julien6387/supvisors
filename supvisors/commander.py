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

from supvisors.strategy import get_address
from supvisors.ttypes import DeploymentStrategies
from supvisors.utils import supvisors_short_cuts


class Commander(object):
    """ Base class handling the starting / stopping of processes and applications.

    Attributes are:
        - planned_sequence: the applications to be commanded, as a dictionary of processes,
            grouped by application sequence order, application name and process sequence order,
        - planned_jobs: the current sequence of applications to be commanded,
            as a dictionary of processes, grouped by application name and process sequence order,
        - current_jobs: a dictionary of commanded processes, grouped by application name. """

    def __init__(self, supvisors):
        """ Initialization of the attributes. """
        # keep a reference of the Supvisors data
        self.supvisors = supvisors
        # shortcuts for readability
        supvisors_short_cuts(self, ['logger'])
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
        """ Simple form of planned_sequence, so that it can be printed. """
        return {application_sequence:
                {application_name:
                    {sequence: self.printable_process_list(processes) for sequence, processes in sequences.items()}
                for application_name, sequences in applications.items()}
            for application_sequence, applications in self.planned_sequence.items()}

    def printable_planned_jobs(self):
        """ Simple form of planned_jobs, so that it can be printed. """
        return {application_name:
                {sequence: self.printable_process_list(processes) for sequence, processes in sequences.items()}
            for application_name, sequences in self.planned_jobs.items()}

    def printable_current_jobs(self):
        """ Simple form of current_jobs, so that it can be printed. """
        return {application_name: self.printable_process_list(processes) for application_name, processes in self.current_jobs.items()}

    def printable_process_list(self, processes):
        """ Simple form of process_list, so that it can be printed. """
        return [process.namespec() for process in processes]

    def initial_jobs(self):
        """ Initializes the planning of the jobs (start or stop). """
        self.logger.debug('planned_sequence={}'.format(self.printable_planned_sequence()))
        # pop lower application group from planned_sequence
        if self.planned_sequence:
            self.planned_jobs = self.planned_sequence.pop(min(self.planned_sequence.keys()))
            self.logger.debug('planned_jobs={}'.format(self.printable_planned_jobs()))
            # iterate on copy to avoid problems with deletions
            for application_name in self.planned_jobs.keys()[:]:
                self.process_application_jobs(application_name)
        else:
            self.logger.debug('command completed')

    def process_application_jobs(self, application_name):
        """ Triggers the starting of a subset of the application. """
        if application_name in self.planned_jobs:
            sequence = self.planned_jobs[application_name]
            self.current_jobs[application_name] = jobs = []
            # loop until there is something to do in sequence
            while sequence and not jobs and application_name in self.planned_jobs:
                # pop lower group from sequence
                group = sequence.pop(min(sequence.keys()))
                self.logger.debug('application {} - next group: {}'.format(application_name, self.printable_process_list(group)))
                for process in group:
                    self.logger.trace('{} - state={}'.format(process.namespec(), process.state_string()))
                    self.process_job(process, jobs)
            self.logger.debug('current_jobs={}'.format(self.printable_current_jobs()))
            # if nothing in progress when exiting the loop, delete application entry in current_jobs
            if not jobs:
                self.logger.debug('no more jobs for application {}'.format(application_name))
                self.current_jobs.pop(application_name, None)
            # clean application job if its sequence is empty
            if not sequence:
                self.logger.debug('all jobs planned for application {}'.format(application_name))
                self.planned_jobs.pop(application_name, None)
        else:
            self.logger.warn('application {} not found in jobs'.format(application_name))


class Starter(Commander):
    """ Class handling the starting of processes and applications.
    Attributes are:
    - strategy: the deployment strategy applied, defaulted to the value set in the Supervisor configuration file, """

    def __init__(self, supvisors):
        """ Initialization of the attributes. """
        Commander.__init__(self, supvisors)
        #attributes
        self._strategy = supvisors.options.deployment_strategy

    @property
    def strategy(self):
        """ Property for the 'strategy' attribute.
        The setter is used to overload the default strategy (used in rpcinterface and web page). """
        return self._strategy

    @strategy.setter
    def strategy(self, strategy):
        self.logger.info('start processes using strategy {}'.format(DeploymentStrategies._to_string(strategy)))
        self._strategy = strategy

    def abort(self):
        """ Abort all planned and current jobs. """
        self.planned_sequence = {}
        self.planned_jobs = {}
        self.current_jobs = {}

    def start_applications(self):
        """ Plan and start the necessary jobs to start all the applications having a start_sequence.
        It uses the default strategy, as defined in the Supervisor configuration file. """
        self.logger.info('start all applications')
        # internal call: default strategy always used
        self.strategy = self.supvisors.options.deployment_strategy
        # deployment initialization: push program list in todo list
        for application in self.supvisors.context.applications.values():
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
            self.logger.debug('planned_sequence={}'.format(self.printable_planned_sequence()))
            if self.planned_sequence:
                # add application immediately to planned jobs if something in list
                self.planned_jobs.update(self.planned_sequence.pop(min(self.planned_sequence.keys())))
                self.process_application_jobs(application.application_name)
        # return True when started
        return not self.in_progress()

    def start_process(self, strategy, process, extra_args=''):
        """ Plan and start the necessary job to start the process in parameter, with the strategy requested. """
        self.logger.info('start process {}'.format(process.namespec()))
        # called from rpcinterface: strategy is a user choice
        self.strategy = strategy
        # store extra arguments to be passed to the command line
        process.extra_args = extra_args
        # WARN: when deploying a single process (outside the scope of an application deployment), do NOT consider the 'wait_exit' rule
        process.ignore_wait_exit = True
        # push program list in todo list and start work
        job = self.current_jobs.setdefault(process.application_name, [])
        self.process_job(process, job)
        # upon failure, remove inProgress entry if empty
        if not job:
            del self.current_jobs[process.application_name]
        # return True when started
        return not self.in_progress()

    def start_marked_processes(self, processes):
        """ Plan and start the necessary job to start the processes in parameter, with the default strategy. """
        # restart required processes first
        for process in processes:
            if process.rules.required:
                self.start_process(self.supvisors.options.deployment_strategy, process)
                process.mark_for_restart = False
        # restart optional processes
        for process in processes:
            if not process.rules.required:
                self.start_process(self.supvisors.options.deployment_strategy, process)
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
        """ Triggers the following of the start sequencing, depending on the new process status. """
        if process.application_name in self.current_jobs:
            jobs = self.current_jobs[process.application_name]
            if process in jobs:
                if process.state in [ProcessStates.STOPPED, ProcessStates.STOPPING, ProcessStates.UNKNOWN]:
                    # unexpected event in a starting phase: someone has requested to stop the process as it is starting
                    # remove from inProgress
                    process.ignore_wait_exit = False
                    jobs.remove(process)
                    # decide to continue deployment or not
                    self.process_failure(process, 'unexpected event when starting')
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
                    # remove from inProgress
                    process.ignore_wait_exit = False
                    jobs.remove(process)
                    if process.rules.wait_exit and process.expected_exit:
                        self.logger.info('expected exit for {}'.format(process.namespec()))
                    else:
                        # missed. decide to continue degraded or to halt
                        self.process_failure(process, 'unexpected exit')
                elif process.state == ProcessStates.FATAL:
                    # remove from inProgress
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
        """ Copy the start sequence and remove programs that are not meant to be
        started automatically, i.e. their start_sequence is 0. """
        application_sequence = application.start_sequence.copy()
        application_sequence.pop(0, None)
        if len(application_sequence) > 0:
            sequence = self.planned_sequence.setdefault(application.rules.start_sequence, {})
            sequence[application.application_name] = application_sequence

    def process_job(self, process, jobs):
        """ Start the process on the relevant address. """
        reset_flag = True
        # process is either stopped, or was running on a lost board
        if process.stopped() or process.mark_for_restart:
            namespec = process.namespec()
            address = get_address(self.supvisors, self.strategy, process.rules.addresses, process.rules.expected_loading)
            if address:
                self.logger.info('try to start {} at address={}'.format(namespec, address))
                # use asynchronous xml rpc to start program
                self.supvisors.zmq.pusher.send_start_process(address, namespec, process.extra_args)
                # push to jobs and timestamp process
                process.request_time = time.time()
                self.logger.debug('{} requested to start at {}'.format(namespec, get_asctime(process.request_time)))
                jobs.append(process)
                reset_flag = False
                # reset extra arguments
                process.extra_args = ''
            else:
                self.logger.warn('no resource available to start {}'.format(namespec))
                self.process_failure(process, 'no resource available', True)
        # due to failure, reset ignore_wait_exit flag
        if reset_flag:
            process.ignore_wait_exit = False

    def process_failure(self, process, reason, force_fatal=None):
        """ Updates the start sequencing when a process could not be started. """
        application_name = process.application_name
        # impact of failure upon application deployment
        if process.rules.required:
            # get starting failure strategy of related application
            application = self.context.applications[application_name]
            failure_strategy = application.rules.starting_failure_strategy
            # apply strategy
            if failure_strategy == StartingFailureStrategies.ABORT:
                self.logger.error('{} for required {}: abort starting of application {}'.format(reason, process.process_name, application_name))
                # remove failed application from deployment
                # do not remove application from InProgress as requests have already been sent
                self.planned_jobs.pop(application_name, None)
            elif failure_strategy == StartingFailureStrategies.STOP:
                self.logger.error('{} for required {}: stop application {}'.format(reason, process.process_name, application_name))
                self.planned_jobs.pop(application_name, None)
                self.supvisors.stopper.stop_application(application)
            else:
                self.logger.warn('{} for required {}: continue starting of application {}'.format(reason, process.process_name, application_name))
        else:
            self.logger.warn('{} for optional {}: continue starting of application {}'.format(reason, process.process_name, application_name))
        if force_fatal:
            # publish the process state as FATAL to all Supvisors instances
            self.logger.warn('force {} state to FATAL'.format(process.namespec()))
            try:
                self.supvisors.info_source.force_process_fatal(process.namespec(), reason)
            except KeyError:
                self.logger.error('impossible to force {} state to FATAL. process unknown in this Supervisor'.format(process.namespec()))
                # the Supvisors user is not forced to use the same process configuration on all machines,
                # although it is strongly recommended to avoid troubles.
                # so, publish directly a fake process event
                self.supvisors.listener.force_process_fatal(process.namespec())


class Stopper(Commander):
    """ Class handling the stopping of processes and applications. """

    def stop_applications(self):
        """ Plan and start the necessary jobs to stop all the applications having a stop_sequence. """
        self.logger.info('stop all applications')
        # deployment initialization: push program list in todo list
        for application in self.supvisors.context.applications.values():
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
            self.logger.debug('planned_sequence={}'.format(self.printable_planned_sequence()))
            # add application immediately to planned jobs
            self.planned_jobs.update(self.planned_sequence.pop(min(self.planned_sequence.keys())))
            self.process_application_jobs(application.application_name)
        # return True when stopped
        return not self.in_progress()

    def stop_process(self, process):
        """ Plan and start the necessary job to stop the process in parameter. """
        self.logger.info('stop process {}'.format(process.namespec()))
        # push program list in todo list and start work
        job = self.current_jobs.setdefault(process.application_name, [])
        self.process_job(process, job)
        # upon failure, remove inProgress entry if empty
        if not job:
            del self.current_jobs[process.application_name]
        # return True when stopped
        return not self.in_progress()

    def store_application_stop_sequence(self, application):
        """ Schedules the application processes to stop. """
        if application.stop_sequence:
            sequence = self.planned_sequence.setdefault(application.rules.stop_sequence, {})
            sequence[application.application_name] = application.stop_sequence.copy()

    def process_job(self, process, jobs):
        """ Stops the process where it is running. """
        if process.running():
            # use asynchronous xml rpc to stop program
            for address in process.addresses:
                self.logger.info('stopping process {} on {}'.format(process.namespec(), address))
                self.supvisors.zmq.pusher.send_stop_process(address, process.namespec())
            # push to jobs and timestamp process
            process.request_time = time.time()
            self.logger.debug('{} requested to stop at {}'.format(process.namespec(), get_asctime(process.request_time)))
            jobs.append(process)

    def check_stopping(self):
        """ Check the progress of the application stopping. """
        self.logger.debug('stopping progress: planned_sequence={} planned_jobs={} current_jobs={}'.format(
            self.printable_planned_sequence(), self.printable_planned_jobs(), self.printable_current_jobs()))
        # once the stop_process has been called, a STOPPING event is expected in less than 5 seconds
        now = time.time()
        processes= [process for process_list in self.current_jobs.values() for process in process_list]
        self.logger.trace('now={} checking processes={}'.format(now,
            [(process.process_name, process.state, process.request_time, process.last_event_time) for process in processes]))
        for process in processes:
            # depending on ini file, it may take a while before the process enters in STOPPED state
            # so just test that is in not in a RUNNING-like state 5 seconds after request_time
            if process.running() and max(process.last_event_time, process.request_time) + 5 < now:
                self.process_failure(process.namespec(), 'Still running 5 seconds after stop request', True)
        # return True when starting is completed
        return not self.in_progress()

    def on_event(self, process):
        """ Triggers the following of the stop sequencing, depending on the new process status. """
        self.logger.info('Stopping {} - event={}'.format(process.namespec(), process.state_string()))
        # check if process event has an impact on stopping in progress
        if process.application_name in self.current_jobs:
            jobs = self.current_jobs[process.application_name]
            self.logger.debug('jobs={}'.format(self.printable_current_jobs()))
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
                        self.logger.info('stopping completed for application {}'.format(process.application_name))
                        # check if there are planned jobs
                        if not self.planned_jobs:
                            # trigger next sequence of applications
                            self.initial_jobs()

    def process_failure(self, namespec, reason):
        """ Updates the stop sequencing when a process could not be stopped. """
        # publish the process state as UNKNOWN to all Supvisors instances
        self.logger.warn('force {} state to UNKNOWN'.format(namespec))
        try:
            self.supvisors.info_source.force_process_unknown(namespec, reason)
        except KeyError:
            self.logger.error('impossible to force {} state to UNKNOWN. process unknown in this Supervisor'.format(namespec))
            # the Supvisors user is not forced to use the same process configuration on all machines,
            # although it is strongly recommended to avoid troubles.
            # so, publish directly a fake process event
            self.supvisors.listener.force_process_unknown(namespec)
