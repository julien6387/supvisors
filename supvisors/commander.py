#!/usr/bin/python
# -*- coding: utf-8 -*-

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
from supvisors.ttypes import StartingStrategies, StartingFailureStrategies
from supvisors.utils import supvisors_shortcuts


class ProcessCommand(object):
    """ Wrapper of the process to include data only used here.

    Attributes are:
        - process: the process wrapped,
        - request_time: the date when the command is requested,
        - ignore_wait_exit: used to command a process out of its application,
        - extra_args: additional arguments to the command line.
    """

    def __init__(self, process):
        """ Initialization of the attributes. """
        self.process = process
        self.request_time = 0
        self.ignore_wait_exit = False
        self.extra_args = ''

    def __str__(self):
        """ Contents as string. """
        return 'process={} state={} last_event_time={} ' \
               'request_time={} ignore_wait_exit={} extra_args="{}"' \
            .format(self.process.namespec(), self.process.state,
                    self.process.last_event_time, self.request_time,
                    self.ignore_wait_exit, self.extra_args)

    def timeout(self, now):
        """ Return True if there is still no event 5 seconds past the request. """
        return max(self.process.last_event_time, self.request_time) + 5 < now


class Commander(object):
    """ Base class handling the starting / stopping of processes and
    applications.

    Attributes are:
        - planned_sequence: the applications to be commanded, as a dictionary
        of process commands, grouped by application sequence order,
        application name and process sequence order,
        - planned_jobs: the current sequence of applications to be commanded,
        as a dictionary of process commands, grouped by application name and
        process sequence order,
        - current_jobs: a dictionary of process commands, grouped by
        application name.
    """

    def __init__(self, supvisors):
        """ Initialization of the attributes. """
        # keep a reference of the Supvisors data
        self.supvisors = supvisors
        # shortcuts for readability
        supvisors_shortcuts(self, ['logger'])
        # attributes
        self.planned_sequence = {}  # {app_seq: {app_name: {proc_seq: [proc_cmd]}}}
        self.planned_jobs = {}  # {app_name: {proc_seq: [proc_cmd]}}
        self.current_jobs = {}  # {app_name: [proc_cmd]}

    def in_progress(self):
        """ Return True if there are jobs planned or in progress. """
        self.logger.debug('progress: planned_sequence={} planned_jobs={} '
                          'current_jobs={}'
                          .format(self.printable_planned_sequence(),
                                  self.printable_planned_jobs(),
                                  self.printable_current_jobs()))
        return len(self.planned_sequence) or len(self.planned_jobs) or len(self.current_jobs)

    def has_application(self, application_name):
        """ Return True if application is in jobs. """
        # get all planned applications
        planned_applications = [app_name for jobs
                                in self.planned_sequence.values()
                                for app_name in jobs]
        # search for application name in internal structures
        return (application_name in planned_applications
                or application_name in self.planned_jobs
                or application_name in self.current_jobs)

    # log facilities
    def printable_planned_sequence(self):
        """ Simple form of planned_sequence, so that it can be printed. """
        return {application_sequence: {application_name: {sequence: Commander.printable_command_list(commands)
                                                          for sequence, commands in sequences.items()}
                                       for application_name, sequences in applications.items()}
                for application_sequence, applications
                in self.planned_sequence.items()}

    def printable_planned_jobs(self):
        """ Simple form of planned_jobs, so that it can be printed. """
        return {application_name: {sequence: Commander.printable_command_list(commands)
                                   for sequence, commands in sequences.items()}
                for application_name, sequences in self.planned_jobs.items()}

    def printable_current_jobs(self):
        """ Simple form of current_jobs, so that it can be printed. """
        return {application_name: Commander.printable_command_list(commands)
                for application_name, commands in self.current_jobs.items()}

    @staticmethod
    def printable_command_list(commands):
        """ Simple form of process_list, so that it can be printed. """
        return [command.process.namespec() for command in commands]

    def get_process_command(self, process, jobs):
        """ Get the process wrapper from list. """
        return next((command for command in jobs
                     if command.process == process), None)

    def initial_jobs(self):
        """ Initializes the planning of the jobs (start or stop). """
        self.logger.debug('planned_sequence={}'
                          .format(self.printable_planned_sequence()))
        # pop lower application group from planned_sequence
        if self.planned_sequence:
            self.planned_jobs = self.planned_sequence.pop(
                min(self.planned_sequence.keys()))
            self.logger.debug('planned_jobs={}'
                              .format(self.printable_planned_jobs()))
            # iterate on copy to avoid problems with deletions
            for application_name in list(self.planned_jobs.keys()):
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
                self.logger.debug('application {} - next group: {}'
                                  .format(application_name,
                                          self.printable_command_list(group)))
                for command in group:
                    self.logger.trace('{} - state={}'
                                      .format(command.process.namespec(),
                                              command.process.state_string()))
                    self.process_job(command, jobs)
            self.logger.debug('current_jobs={}'
                              .format(self.printable_current_jobs()))
            # if nothing in progress when exiting the loop,
            # delete application entry in current_jobs
            if not jobs:
                self.logger.debug('no more jobs for application {}'
                                  .format(application_name))
                self.current_jobs.pop(application_name, None)
            # clean application job if its sequence is empty
            if not sequence:
                self.logger.debug('all jobs planned for application {}'
                                  .format(application_name))
                self.planned_jobs.pop(application_name, None)
        else:
            self.logger.warn('application {} not found in jobs'
                             .format(application_name))

    def process_job(self, command, jobs):
        """ Perform the action on process and push progress in jobs list.
        Method must be implemented in subclasses. """
        raise NotImplementedError


class Starter(Commander):
    """ Class handling the starting of processes and applications.

    Attributes are:
        - strategy: the starting strategy applied, defaulted to the value
        set in the Supervisor configuration file.
    """

    def __init__(self, supvisors):
        """ Initialization of the attributes. """
        Commander.__init__(self, supvisors)
        self._strategy = self.get_default_strategy()

    @property
    def strategy(self):
        """ Property for the 'strategy' attribute.
        The setter is used to overload the default strategy (used in
        rpcinterface and web page). """
        return self._strategy

    @strategy.setter
    def strategy(self, strategy):
        self.logger.info('start processes using strategy {}'.format(
            StartingStrategies.to_string(strategy)))
        self._strategy = strategy

    def get_default_strategy(self):
        """ Return the default starting strategy from options. """
        return self.supvisors.options.starting_strategy

    def abort(self):
        """ Abort all planned and current jobs. """
        self.planned_sequence = {}
        self.planned_jobs = {}
        self.current_jobs = {}

    def start_applications(self):
        """ Plan and start the necessary jobs to start all the applications
        having a start_sequence.
        It uses the default strategy, as defined in the Supervisor
        configuration file. """
        self.logger.info('start all applications')
        # internal call: default strategy always used
        self.strategy = self.get_default_strategy()
        # starting initialization: push program list in todo list
        for application in self.supvisors.context.applications.values():
            # do not start an application that is not properly STOPPED
            if application.stopped() and application.rules.start_sequence > 0:
                self.store_application_start_sequence(application)
        # start work
        self.initial_jobs()

    def default_start_application(self, application):
        """ Plan and start the necessary jobs to start the application in
        parameter, with the default strategy. """
        return self.start_application(self.get_default_strategy(), application)

    def start_application(self, strategy, application):
        """ Plan and start the necessary jobs to start the application in
        parameter, with the strategy requested. """
        self.logger.info('start application {}'
                         .format(application.application_name))
        # called from rpcinterface: strategy is a user choice
        self.strategy = strategy
        # push program list in todo list and start work
        if application.stopped():
            self.store_application_start_sequence(application)
            self.logger.debug('planned_sequence={}'
                              .format(self.printable_planned_sequence()))
            if self.planned_sequence:
                # add application immediately to planned jobs
                # if something in list
                self.planned_jobs.update(
                    self.planned_sequence.pop(
                        min(self.planned_sequence.keys())))
                self.process_application_jobs(application.application_name)
        # return True when started
        return not self.in_progress()

    def default_start_process(self, process):
        """ Plan and start the necessary job to start the process in parameter,
        with the default strategy.
        Return False when starting not completed. """
        return self.start_process(self.get_default_strategy(), process)

    def start_process(self, strategy, process, extra_args=''):
        """ Plan and start the necessary job to start the process in parameter,
        with the strategy requested.
        Return False when starting not completed. """
        self.logger.info('start process {}'.format(process.namespec()))
        # called from rpcinterface: strategy is a user choice
        self.strategy = strategy
        # store extra arguments to be passed to the command line
        command = ProcessCommand(process)
        command.extra_args = extra_args
        # WARN: when starting a single process (outside the scope of an application starting),
        # do NOT consider the 'wait_exit' rule
        command.ignore_wait_exit = True
        # push program list in todo list and start work
        job = self.current_jobs.setdefault(process.application_name, [])
        starting = self.process_job(command, job)
        # upon failure, remove inProgress entry if empty
        if not job:
            del self.current_jobs[process.application_name]
        # return True when started
        return not starting

    def check_starting(self):
        """ Check the progress of the application starting. """
        self.logger.debug('starting progress: planned_sequence={} '
                          'planned_jobs={} current_jobs={}'
                          .format(self.printable_planned_sequence(),
                                  self.printable_planned_jobs(),
                                  self.printable_current_jobs()))
        # once the start_process has been called, a STARTING event is expected
        # in less than 5 seconds
        now = time.time()
        commands = [command
                    for command_list in self.current_jobs.values()
                    for command in command_list]
        self.logger.trace('now={} checking commands={}'
                          .format(now, [str(command) for command in commands]))
        for command in commands:
            # depending on ini file, it may take a while before the process
            # enters in RUNNING state so just test that is in not in a
            # STOPPED-like state 5 seconds after request_time
            if command.process.stopped() and command.timeout(now):
                # generate a FATAL event for this process
                self.force_process_fatal(command.process.namespec(),
                                         'Still stopped 5 seconds after start request')
        # return True when starting is completed
        return not self.in_progress()

    def on_event(self, process):
        """ Triggers the following of the start sequencing, depending on the
        new process status. """
        try:
            # first check if event is in the sequence logic,
            # i.e. it corresponds to a process in current jobs
            jobs = self.current_jobs[process.application_name]
            command = self.get_process_command(process, jobs)
            assert command
        except (KeyError, AssertionError):
            # otherwise, check if event impacts the starting sequence
            self.on_event_out_of_sequence(process)
        else:
            self.on_event_in_sequence(command, jobs)

    def on_event_in_sequence(self, command, jobs):
        """ Manages the impact of an event that is part of the starting
        sequence. """
        process = command.process
        if process.state in (ProcessStates.STOPPED,
                             ProcessStates.STOPPING,
                             ProcessStates.UNKNOWN):
            # unexpected event in a starting phase:
            # someone has requested to stop the process as it is starting
            # remove from inProgress
            jobs.remove(command)
            # decide to continue starting or not
            self.process_failure(process)
        elif process.state == ProcessStates.STARTING:
            # on the way
            pass
        elif command.process.state == ProcessStates.RUNNING:
            # if not exit expected, job done. otherwise, wait
            if not process.rules.wait_exit or command.ignore_wait_exit:
                jobs.remove(command)
        elif process.state == ProcessStates.BACKOFF:
            # something wrong happened, just wait
            self.logger.warn('problems detected with {}'
                             .format(process.namespec()))
        elif process.state == ProcessStates.EXITED:
            # remove from inProgress
            jobs.remove(command)
            # an EXITED process is accepted if wait_exit is set
            if process.rules.wait_exit and process.expected_exit:
                self.logger.info('expected exit for {}'
                                 .format(process.namespec()))
            else:
                self.process_failure(process)
        elif process.state == ProcessStates.FATAL:
            # remove from inProgress
            jobs.remove(command)
            # decide to continue starting or not
            self.process_failure(process)
        # check if there are remaining jobs in progress for this application
        if not jobs:
            # remove application entry from current_jobs
            del self.current_jobs[process.application_name]
            # trigger next job for aplication
            if process.application_name in self.planned_jobs:
                self.process_application_jobs(process.application_name)
            else:
                self.logger.info('starting completed for application {}'
                                 .format(process.application_name))
                # check if there are planned jobs
                if not self.planned_jobs:
                    # trigger next sequence of applications
                    self.initial_jobs()

    def on_event_out_of_sequence(self, process):
        """ Manages the impact of a crash event that is out of the starting
        sequence.

        Note: Keeping in mind the possible origins of the event:
            * a request performed by this Starter,
            * a request performed directly on any Supervisor (local or remote),
            * a request performed on a remote Supvisors,
        let's consider the following cases:
            1) The application is in the planned sequence, or process is in
            the planned jobs.
               => do nothing, give a chance to this Starter.
            2) The process is NOT in the application planned jobs.
               The process was likely started previously in the sequence of
               this Starter, and it crashed after its RUNNING state but before
               the application is fully started.
               => apply starting failure strategy through basic process_failure
            3) The application is NOT handled in this Starter
               => running failure strategy could be applied outside of here
        """
        # find the conditions of case 2
        if process.crashed() and process.application_name in self.planned_jobs:
            planned_application_jobs = self.planned_jobs[process.application_name]
            planned_process_jobs = [
                command.process
                for commands in planned_application_jobs.values()
                for command in commands]
            if process not in planned_process_jobs:
                self.process_failure(process)

    def store_application_start_sequence(self, application):
        """ Copy the start sequence and remove programs that are not meant
        to be started automatically, i.e. their start_sequence is 0. """
        application_sequence = {
            seq: [ProcessCommand(process) for process in processes]
            for seq, processes in application.start_sequence.items()
            if seq > 0}
        if len(application_sequence) > 0:
            sequence = self.planned_sequence.setdefault(
                application.rules.start_sequence, {})
            sequence[application.application_name] = application_sequence

    def process_job(self, command, jobs):
        """ Start the process on the relevant address.
        Return True if process is starting. """
        starting = False
        # process must be stopped
        process = command.process
        if process.stopped():
            namespec = process.namespec()
            address = get_address(self.supvisors, self.strategy,
                                  process.rules.addresses,
                                  process.rules.expected_loading)
            if address:
                self.logger.info('try to start {} at address={}'
                                 .format(namespec, address))
                # use asynchronous xml rpc to start program
                self.supvisors.zmq.pusher.send_start_process(address, namespec, command.extra_args)
                # push to jobs and timestamp process
                command.request_time = time.time()
                self.logger.debug('{} requested to start at {}'
                                  .format(namespec, get_asctime(command.request_time)))
                jobs.append(command)
                starting = True
            else:
                self.logger.warn('no resource available to start {}'.format(namespec))
                self.force_process_fatal(namespec, 'no resource available')
        # return True when process is starting
        return starting

    def process_failure(self, process):
        """ Updates the start sequence when a process could not be started. """
        application_name = process.application_name
        # impact of failure on application starting
        if process.rules.required:
            self.logger.warn('starting failed for required {}'
                             .format(process.process_name))
            # get starting failure strategy of related application
            application = self.supvisors.context.applications[application_name]
            failure_strategy = application.rules.starting_failure_strategy
            # apply strategy
            if failure_strategy == StartingFailureStrategies.ABORT:
                self.logger.error('abort starting of application {}'
                                  .format(application_name))
                # remove failed application from starting
                # do not remove application from current_jobs as requests
                # have already been sent
                self.planned_jobs.pop(application_name, None)
            elif failure_strategy == StartingFailureStrategies.STOP:
                self.logger.error('stop application {}'
                                  .format(application_name))
                self.planned_jobs.pop(application_name, None)
                self.supvisors.stopper.stop_application(application)
            else:
                self.logger.warn('continue starting of application {}'
                                 .format(application_name))
        else:
            self.logger.warn('starting failed for optional {}'
                             .format(process.process_name))
            self.logger.warn('continue starting of application {}'
                             .format(application_name))

    def force_process_fatal(self, namespec, reason):
        """ Publish the process state as FATAL to all Supvisors instances. """
        self.logger.warn('force {} state to FATAL'.format(namespec))
        try:
            # this call updates the Supervisor data model
            self.supvisors.info_source.force_process_fatal(namespec, reason)
        except KeyError:
            self.logger.error('process {} unknown to this Supervisor.'
                              .format(namespec))
            # the Supvisors user is not forced to use the same process
            # configuration on all machines,
            # although it is strongly recommended to avoid troubles.
            # => publish directly a fake process event to all Supvisors instances
            self.supvisors.listener.force_process_fatal(namespec)


class Stopper(Commander):
    """ Class handling the stopping of processes and applications. """

    def stop_applications(self):
        """ Plan and start the necessary jobs to stop all the applications
        having a stop_sequence. """
        self.logger.info('stop all applications')
        # stopping initialization: push program list in todo list
        for application in self.supvisors.context.applications.values():
            # do not stop an application that is not running
            if application.running() and application.rules.stop_sequence >= 0:
                self.store_application_stop_sequence(application)
        # start work
        self.initial_jobs()

    def stop_application(self, application):
        """ Plan and start the necessary jobs to stop the application in
        parameter. """
        self.logger.info('stop application {}'
                         .format(application.application_name))
        # push program list in todo list and start work
        if application.running():
            self.store_application_stop_sequence(application)
            self.logger.debug('planned_sequence={}'
                              .format(self.printable_planned_sequence()))
            # add application immediately to planned jobs
            self.planned_jobs.update(self.planned_sequence.pop(
                min(self.planned_sequence.keys())))
            self.process_application_jobs(application.application_name)
        # return True when stopped
        return not self.in_progress()

    def stop_process(self, process):
        """ Plan and start the necessary job to stop the process in parameter.
        Return False when stopping not completed. """
        self.logger.info('stop process {}'.format(process.namespec()))
        # push program list in todo list and start work
        job = self.current_jobs.setdefault(process.application_name, [])
        command = ProcessCommand(process)
        stopping = self.process_job(command, job)
        # upon failure, remove inProgress entry if empty
        if not job:
            del self.current_jobs[process.application_name]
        # return True when stopped
        return not stopping

    def store_application_stop_sequence(self, application):
        """ Schedules the application processes to stop. """
        application_sequence = {
            seq: [ProcessCommand(process) for process in processes]
            for seq, processes in application.stop_sequence.items()}
        sequence = self.planned_sequence.setdefault(
            application.rules.stop_sequence, {})
        sequence[application.application_name] = application_sequence

    def process_job(self, command, jobs):
        """ Stops the process where it is running.
        Return True if process is stopping. """
        process = command.process
        if process.running():
            # use asynchronous xml rpc to stop program
            for address in process.addresses:
                self.logger.info('stopping process {} on {}'
                                 .format(process.namespec(), address))
                self.supvisors.zmq.pusher.send_stop_process(
                    address, process.namespec())
            # push to jobs and timestamp process
            command.request_time = time.time()
            self.logger.debug('{} requested to stop at {}'
                              .format(process.namespec(),
                                      get_asctime(command.request_time)))
            jobs.append(command)
            return True

    def check_stopping(self):
        """ Check the progress of the application stopping. """
        self.logger.debug('stopping progress: planned_sequence={} '
                          'planned_jobs={} current_jobs={}'
                          .format(self.printable_planned_sequence(),
                                  self.printable_planned_jobs(),
                                  self.printable_current_jobs()))
        # once the stop_process has been called, a STOPPING event is expected
        # in less than 5 seconds
        now = time.time()
        commands = [command
                    for command_list in self.current_jobs.values()
                    for command in command_list]
        self.logger.trace('now={} checking processes={}'
                          .format(now, [command for command in commands]))
        for command in commands:
            # depending on ini file, it may take a while before the process
            # enters in STOPPED state
            # so just test that is in not in a RUNNING-like state 5 seconds
            # after request_time
            if command.process.running() and command.timeout(now):
                self.force_process_unknown(command.process.namespec(),
                                           'Still running 5 seconds after stop request')
        # return True when starting is completed
        return not self.in_progress()

    def on_event(self, process):
        """ Triggers the following of the stop sequencing, depending on
        the new process status. """
        # check if process event has an impact on stopping in progress
        if process.application_name in self.current_jobs:
            jobs = self.current_jobs[process.application_name]
            self.logger.debug('jobs={}'
                              .format(self.printable_command_list(jobs)))
            command = self.get_process_command(process, jobs)
            if command:
                if process.running():
                    # several cases:
                    # 1) expected upon conciliation of a conflicting process
                    # 2) concurrent stopping / starting
                    self.logger.warn('{} still running when stopping'
                                     .format(process.namespec()))
                elif process.stopped():
                    # goal reached, whatever the state
                    jobs.remove(command)
                # else STOPPING, on the way
                # check if there are remaining jobs in progress for this
                # application
                if not jobs:
                    # remove application entry from current_jobs
                    del self.current_jobs[process.application_name]
                    # trigger next job for application
                    if process.application_name in self.planned_jobs:
                        self.process_application_jobs(process.application_name)
                    else:
                        self.logger.info('application {} stopped'
                                         .format(process.application_name))
                        # check if there are planned jobs
                        if not self.planned_jobs:
                            # trigger next sequence of applications
                            self.initial_jobs()

    def force_process_unknown(self, namespec, reason):
        """ Updates the stop sequencing when a process could not be stopped. """
        # publish the process state as UNKNOWN to all Supvisors instances
        self.logger.warn('force {} state to UNKNOWN'.format(namespec))
        try:
            self.supvisors.info_source.force_process_unknown(namespec, reason)
        except KeyError:
            self.logger.error('impossible to force {} state to UNKNOWN. '
                              'process unknown in this Supervisor'.format(namespec))
            # the Supvisors user is not forced to use the same process
            # configuration on all machines,
            # although it is strongly recommended to avoid troubles.
            # so, publish directly a fake process event to all instances
            self.supvisors.listener.force_process_unknown(namespec)
