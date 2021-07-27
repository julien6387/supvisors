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

from typing import Any, Dict, List

from supervisor.childutils import get_asctime
from supervisor.states import ProcessStates

from .application import ApplicationStatus
from .process import ProcessStatus
from .strategy import get_node
from .ttypes import NameList, StartingStrategies, StartingFailureStrategies


class ProcessCommand(object):
    """ Wrapper of the process to include data only used here.

    Attributes are:
        - process: the process wrapped,
        - strategy: the strategy used to start the process if applicable,
        - request_time: the date when the command is requested,
        - ignore_wait_exit: used to command a process out of its application,
        - extra_args: additional arguments to the command line.
    """
    TIMEOUT = 10

    def __init__(self, process: ProcessStatus, strategy: StartingStrategies = None, repair: bool = False) -> None:
        """ Initialization of the attributes.

        :param process: the process status to wrap
        :param strategy: the applicable starting strategy
        :param repair: a flag telling if the enclosing application is being started or repaired
        """
        self.process = process
        self.strategy = strategy
        self.repair = repair
        self.request_time = 0
        self.ignore_wait_exit = False
        self.extra_args = ''

    def __str__(self) -> str:
        """ Get the process command as string.

        :return: the printable process command
        """
        return 'process={} state={} last_event_time={} strategy={} request_time={} ' \
               'ignore_wait_exit={} extra_args="{}"' \
            .format(self.process.namespec(), self.process.state, self.process.last_event_time,
                    self.strategy.value if self.strategy else 'None',
                    self.request_time,  self.ignore_wait_exit, self.extra_args)

    def timed_out(self, now: int) -> bool:
        """ Return True if there is still no event TIMEOUT seconds past the request.

        :param now: the current time
        :return: the timeout status
        """
        return max(self.process.last_event_time, self.request_time) + ProcessCommand.TIMEOUT < now


class Commander(object):
    """ Base class handling the starting / stopping of processes and applications.

    Attributes are:
        - planned_sequence: the applications to be commanded, as a dictionary of process commands, grouped by application sequence order, application name and process sequence order,
        - planned_jobs: the current sequence of applications to be commanded, as a dictionary of process commands, grouped by application name and process sequence order,
        - current_jobs: a dictionary of process commands, grouped by application name.
    """

    # Annotation types
    CommandList = List[ProcessCommand]
    CurrentJobs = Dict[str, CommandList]  # {app_name: [proc_cmd]}
    PlannedJobs = Dict[str, Dict[int, CommandList]]  # {app_name: {proc_seq: [proc_cmd]}}
    PlannedSequence = Dict[int, PlannedJobs]  # {app_seq: {app_name: {proc_seq: [proc_cmd]}}}

    # Annotation types for printing facilities
    PrintableCommandList = List[str]
    PrintableCurrentJobs = Dict[str, PrintableCommandList]
    PrintablePlannedJobs = Dict[str, Dict[int, PrintableCommandList]]
    PrintablePlannedSequence = Dict[int, PrintablePlannedJobs]

    def __init__(self, supvisors: Any) -> None:
        """ Initialization of the attributes.

        :param supvisors: the global Supvisors structure.
        """
        # keep a reference of the Supvisors data
        self.supvisors = supvisors
        self.logger = supvisors.logger
        # attributes
        self.planned_sequence: Commander.PlannedSequence = {}
        self.planned_jobs: Commander.PlannedJobs = {}
        self.current_jobs: Commander.CurrentJobs = {}

    def in_progress(self) -> bool:
        """ Return True if there are jobs planned or in progress.

        :return: the progress status
        """
        self.logger.trace('Commander.in_progress: planned_sequence={} planned_jobs={} current_jobs={}'
                          .format(self.printable_planned_sequence(),
                                  self.printable_planned_jobs(),
                                  self.printable_current_jobs()))
        return len(self.planned_sequence) > 0 or len(self.planned_jobs) > 0 or len(self.current_jobs) > 0

    def get_job_applications(self) -> NameList:
        """ Return all application names involved in any sequence.

        :return: the list of application names
        """
        planned_applications = {app_name for jobs in self.planned_sequence.values() for app_name in jobs}
        planned_applications.update(self.planned_jobs.keys())
        planned_applications.update(self.current_jobs.keys())
        return planned_applications

    # log facilities
    def printable_planned_sequence(self) -> PrintablePlannedSequence:
        """ Simple form of planned_sequence, so that it can be printed.

        :return: the planned sequence without objects
        """
        return {application_sequence: {application_name: {sequence: Commander.printable_command_list(commands)
                                                          for sequence, commands in sequences.items()}
                                       for application_name, sequences in applications.items()}
                for application_sequence, applications
                in self.planned_sequence.items()}

    def printable_planned_jobs(self) -> PrintablePlannedJobs:
        """ Simple form of planned_jobs, so that it can be printed.

        :return: the planned jobs without objects
        """
        return {application_name: {sequence: Commander.printable_command_list(commands)
                                   for sequence, commands in sequences.items()}
                for application_name, sequences in self.planned_jobs.items()}

    def printable_current_jobs(self) -> PrintableCurrentJobs:
        """ Simple form of current_jobs, so that it can be printed.

        :return: the current jobs without objects
        """
        return {application_name: Commander.printable_command_list(commands)
                for application_name, commands in self.current_jobs.items()}

    @staticmethod
    def printable_command_list(commands: CommandList) -> PrintableCommandList:
        """ Simple form of process_list, so that it can be printed.

        :param commands: the process command list
        :return: the process command list without objects
        """
        return [command.process.namespec() for command in commands]

    @staticmethod
    def get_process_command(process: ProcessStatus, jobs: CommandList) -> ProcessCommand:
        """ Get the process wrapper from list.

        :param process: the process status to search
        :param jobs: the process command list
        :return: the process command found
        """
        return next((command for command in jobs if command.process is process), None)

    def trigger_jobs(self) -> None:
        """ Triggers a sequence of the jobs planned (start or stop).

        :return: None
        """
        self.logger.info('Commander.trigger_jobs: planned_sequence={}'.format(self.printable_planned_sequence()))
        # pop lower sequence from planned_sequence
        while self.planned_sequence and not self.planned_jobs and not self.current_jobs:
            min_sequence = min(self.planned_sequence.keys())
            self.planned_jobs = self.planned_sequence.pop(min_sequence)
            self.logger.debug('Commander.trigger_jobs: min_sequence={} planned_jobs={}'
                              .format(min_sequence, self.printable_planned_jobs()))
            # iterate on copy to avoid problems with key deletions
            for application_name in list(self.planned_jobs.keys()):
                self.logger.info('Commander.trigger_jobs: triggering sequence {} - application_name={}'
                                 .format(min_sequence, application_name))
                self.process_application_jobs(application_name)

    def process_application_jobs(self, application_name: str) -> None:
        """ Triggers the next sequenced group of the application.

        :param application_name: the application name
        :return: None
        """
        if application_name in self.planned_jobs:
            sequence = self.planned_jobs[application_name]
            self.current_jobs[application_name] = jobs = []
            # loop until there is something to do in sequence
            while sequence and not jobs and application_name in self.planned_jobs:
                # pop lower group from sequence
                min_sequence = min(sequence.keys())
                group = sequence.pop(min_sequence)
                self.logger.info('Commander.process_application_jobs: application_name={}'
                                  ' - next group: min_sequence={} group={}'
                                  .format(application_name, min_sequence, self.printable_command_list(group)))
                for command in group:
                    self.logger.info('Commander.process_application_jobs: {} - state={}'
                                      .format(command.process.namespec(), command.process.state_string()))
                    self.process_job(command, jobs)
            self.logger.info('Commander.process_application_jobs: current_jobs={}'
                              .format(self.printable_current_jobs()))
            # if nothing in progress when exiting the loop, delete application entry in current_jobs
            if not jobs:
                self.logger.debug('Commander.process_application_jobs: no more jobs for application {}'
                                  .format(application_name))
                self.current_jobs.pop(application_name, None)
            # clean application job if its sequence is empty
            if not sequence:
                self.logger.debug('Commander.process_application_jobs: all jobs planned for application {}'
                                  .format(application_name))
                self.planned_jobs.pop(application_name, None)
        else:
            self.logger.warn('Commander.process_application_jobs: application {} not found in jobs'
                             .format(application_name))

    def process_job(self, command: ProcessCommand, jobs: CommandList) -> bool:
        """ Perform the action on process and push progress in jobs list.
        Method must be implemented in subclasses Starter and Stopper.

        :param command: the process command
        :param jobs: the reference process command list the process command belongs to
        :return: the job status
        """
        raise NotImplementedError

    def check_progress(self, condition: str, process_state: int) -> bool:
        """ Check the progress of the application starting or stopping.

        :param condition: the ProcessStatus method name to be used
        :param process_state: the process state to force upon failure (among ProcessStates)
        :return: True when starting or stopping is completed
        """
        in_progress = self.in_progress()
        self.logger.debug('Starter.check_progress: in_progress={}'.format(in_progress))
        if in_progress:
            commands = [command for command_list in self.current_jobs.values()
                        for command in command_list]
            if commands:
                # once the start_process (resp. stop_process) has been called, a STARTING (resp. STOPPING) event
                # is expected quite immediately from the Supervisor instance
                # if it doesn't, the whole sequencing would block waiting for an event that may never happen
                # the following instructions have therefore been added for safekeeping, but it has never been reported
                # to occur so far
                now = int(time.time())
                self.logger.trace('Commander.check_progress: now={} checking commands={}'
                                  .format(now, [str(command) for command in commands]))
                for command in commands:
                    # get the ProcessStatus method corresponding to condition and call it
                    class_method = getattr(ProcessStatus, condition)
                    if class_method(command.process):
                        if command.timed_out(now):
                            self.logger.error('Commander.check_progress: {} still {} after {} seconds so abort'
                                              .format(command.process.namespec(), condition, ProcessCommand.TIMEOUT))
                            # generate a process event for this process to inform all Supvisors instances
                            self.supvisors.context.force_process_state(command.process.namespec(), process_state,
                                                                       'Still {} {} seconds after request'
                                                                       .format(condition, ProcessCommand.TIMEOUT))
                            # don't wait for event, just abort the job
                            jobs = self.current_jobs[command.process.application_name]
                            jobs.remove(command)
                            # check if there are remaining jobs in progress for this application
                            if not jobs:
                                self.after_event(command.process.application_name)
            else:
                # no commands in the pipe
                # this can happen when nothing had to be stopped inside the planned_jobs
                self.logger.warn('Starter.check_progress: no commands in progress but planned sequence still ongoing')
                # check if there are planned jobs
                if not self.planned_jobs:
                    # trigger next sequence of applications
                    self.trigger_jobs()
                else:
                    self.logger.critical('Starter.check_progress: UNEXPECTED')
        # return True when starting is completed
        return not self.in_progress()

    def after_event(self, application_name: str) -> None:
        """ This method is called when the last event has been received for the current jobs linked to the application.
        Trigger the next application sub-sequence.

        :param application_name: the name of the application
        :return: None
        """
        # remove application entry from current_jobs
        del self.current_jobs[application_name]
        # trigger next application sub-sequence if any
        if application_name in self.planned_jobs:
            self.process_application_jobs(application_name)
        else:
            # nothing left for this application
            self.logger.info('Commander.after_event: planned jobs completed for application {}'
                             .format(application_name))
            self.after_jobs(application_name)
            # check if there are planned jobs
            if not self.planned_jobs:
                self.logger.info('Commander.after_event: planned jobs completed for all applications')
                # trigger next sequence of applications
                self.trigger_jobs()

    def after_jobs(self, application_name: str) -> None:
        """ Special processing when no more jobs for application.

        :param application_name: the application name
        :return: None
        """


class Starter(Commander):
    """ Class handling the starting of processes and applications. """

    def __init__(self, supvisors: Any) -> None:
        """ Initialization of the attributes.

        :param supvisors: the global Supvisors structure.
        """
        super().__init__(supvisors)
        # attributes
        self.application_stop_requests = []

    def get_default_strategy(self) -> StartingStrategies:
        """ Return the default starting strategy from options.

        :return: the starting strategy set in the supvisors section of the supervisor configuration file
        """
        return self.supvisors.options.starting_strategy

    def abort(self) -> None:
        """ Abort all planned current jobs.
        Do not erase current_jobs. Wait for their completion.

        :return: None
        """
        self.planned_sequence = {}
        self.planned_jobs = {}

    def start_applications(self) -> None:
        """ This method is called in the DEPLOYMENT phase.
        Plan and start the necessary jobs to start or repair all the applications having a start_sequence.
        It uses the default strategy, as defined in the Supvisors section of the Supervisor configuration file.

        :return: None
        """
        strategy = self.get_default_strategy()
        self.logger.info('Starter.start_applications: start all applications using strategy {}'.format(strategy.name))
        # internal call: default strategy always used
        for application in self.supvisors.context.applications.values():
            self.logger.debug('Starter.start_applications: application={} start_sequence={} never_started={}'
                              .format(str(application), application.rules.start_sequence, application.never_started()))
            # applications with start_sequence=0 are not meant to be auto-started
            if application.rules.start_sequence > 0:
                if application.never_started():
                    # if application has never been started, start all in sequence
                    self.store_application_start_sequence(application, strategy)
                elif application.major_failure or application.minor_failure or application.start_failure:
                    # if application is running with failures or starting failed, try to repair it
                    self.store_application_start_sequence(application, strategy, True)
        # start work
        self.trigger_jobs()

    def default_start_application(self, application: ApplicationStatus) -> bool:
        """ Plan and start the necessary jobs to start the application in parameter, with the default strategy.

        :param application: the application to start
        :return: True if start completed (nothing to do actually)
        """
        return self.start_application(self.get_default_strategy(), application)

    def start_application(self, strategy: StartingStrategies, application: ApplicationStatus) -> bool:
        """ Plan and start the necessary jobs to start the application in parameter, with the strategy requested.

        :param strategy: the strategy to be used to start the application
        :param application: the application to start
        :return: True if start completed (nothing to do actually)
        """
        self.logger.info('Starter.start_application: start application {} using strategy {}'
                         .format(application.application_name, strategy.name))
        # push program list in job list and start work
        if application.stopped():
            self.store_application_start_sequence(application, strategy)
            self.logger.debug('Starter.start_application: planned_sequence={}'
                              .format(self.printable_planned_sequence()))
            if self.planned_sequence:
                # add application immediately to planned jobs if something in list
                self.planned_jobs.update(self.planned_sequence.pop(min(self.planned_sequence.keys())))
                self.process_application_jobs(application.application_name)
        # return True when started
        return not self.in_progress()

    def default_start_process(self, process: ProcessStatus) -> bool:
        """ Plan and start the necessary job to start the process in parameter, with the default strategy.

        :param process: the process to start
        :return: True if no job has been queued.
        """
        return self.start_process(self.get_default_strategy(), process)

    def start_process(self, strategy: StartingStrategies, process: ProcessStatus, extra_args: str = '') -> bool:
        """ Plan and start the necessary job to start the process in parameter, with the strategy requested.

        :param strategy: the strategy to be used to start the process
        :param process: the process to start
        :param extra_args: the arguments to be added to the command line
        :return: True if no job has been queued.
        """
        self.logger.info('Starter.start_process: start process {} using strategy {}'
                         .format(process.namespec(), strategy.name))
        # store extra arguments to be passed to the command line
        command = ProcessCommand(process, strategy)
        command.extra_args = extra_args
        # WARN: when starting a single process (outside the scope of an application starting),
        # do NOT consider the 'wait_exit' rule
        command.ignore_wait_exit = True
        # push program list in job list and start work
        job = self.current_jobs.setdefault(process.application_name, [])
        starting = self.process_job(command, job)
        # upon failure, remove inProgress entry if empty
        if not job:
            del self.current_jobs[process.application_name]
        # return True when started
        return not starting

    def check_starting(self) -> bool:
        """ Check the progress of the application starting.

        :return: True when starting is completed
        """
        return self.check_progress('stopped', ProcessStates.FATAL)

    def on_event(self, process) -> None:
        """ Triggers the following of the start sequencing, depending on the new process status. """
        try:
            # first check if event is in the sequence logic, i.e. it corresponds to a process in current jobs
            jobs = self.current_jobs[process.application_name]
            command = self.get_process_command(process, jobs)
            assert command
        except (KeyError, AssertionError):
            # otherwise, check if event impacts the starting sequence
            self.on_event_out_of_sequence(process)
        else:
            self.on_event_in_sequence(command, jobs)

    def on_event_in_sequence(self, command, jobs) -> None:
        """ Manages the impact of an event that is part of the starting sequence. """
        process = command.process
        if process.state in (ProcessStates.STOPPED, ProcessStates.STOPPING, ProcessStates.UNKNOWN):
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
            self.logger.warn('Starter.on_event_in_sequence: problems detected with {}'.format(process.namespec()))
        elif process.state == ProcessStates.EXITED:
            # remove from inProgress
            jobs.remove(command)
            # an EXITED process is accepted if wait_exit is set
            if process.rules.wait_exit and process.expected_exit:
                self.logger.info('Starter.on_event_in_sequence: expected exit for {}'.format(process.namespec()))
            else:
                self.process_failure(process)
        elif process.state == ProcessStates.FATAL:
            # remove from inProgress
            jobs.remove(command)
            # decide to continue starting or not
            self.process_failure(process)
        # check if there are remaining jobs in progress for this application
        if not jobs:
            self.after_event(process.application_name)

    def on_event_out_of_sequence(self, process: ProcessStatus) -> None:
        """ Manages the impact of a crash event that is out of the starting sequence.

        Note: Keeping in mind the possible origins of the event:
            * a request performed by this Starter,
            * a request performed directly on any Supervisor (local or remote),
            * a request performed on a remote Supvisors,
        let's consider the following cases:
            1) The application is in the planned sequence, or process is in the planned jobs.
               => do nothing, give a chance to this Starter.
            2) The process is NOT in the application planned jobs.
               The process was likely started previously in the sequence of this Starter,
               and it crashed after its RUNNING state but before the application is fully started.
               => apply starting failure strategy through basic process_failure
            3) The application is NOT handled in this Starter
               => running failure strategy to be applied outside of here
        """
        # find the conditions of case 2
        if process.crashed() and process.application_name in self.planned_jobs:
            planned_application_jobs = self.planned_jobs[process.application_name]
            planned_process_jobs = [command.process
                                    for commands in planned_application_jobs.values()
                                    for command in commands]
            if process not in planned_process_jobs:
                self.process_failure(process)

    def store_application_start_sequence(self, application, strategy, repair=False) -> None:
        """ Copy the start sequence and remove programs that are not meant to be started automatically,
        i.e. their start_sequence is 0. """
        application_sequence = {seq: [ProcessCommand(process, strategy, repair) for process in processes]
                                for seq, processes in application.start_sequence.items()
                                if seq > 0}
        if len(application_sequence) > 0:
            sequence = self.planned_sequence.setdefault(application.rules.start_sequence, {})
            sequence[application.application_name] = application_sequence

    def process_job(self, command: ProcessCommand, jobs: Commander.CommandList) -> bool:
        """ Start the process on the relevant node.
        In a starting sequence, process must be in stopped-like state.
        In a repairing sequence, process must be in crashed-like state.

        :param command: the wrapper of the process to start
        :param jobs: the list of jobs in progress
        :return: True if a job has been queued.
        """
        starting = False
        process = command.process
        self.logger.debug('Starter.process_job: process={} repair={} crashed={} stopped={}'
                          .format(process.namespec(), command.repair, process.crashed(), process.stopped()))
        # FIXME: probleme ici ?
        if command.repair and process.crashed() or not command.repair and process.stopped():
            # whatever a node is found or not to start the process, the job is considered started
            # in every cases, a notification is expected from Supervisor
            command.request_time = time.time()
            jobs.append(command)
            starting = True
            # find node iaw strategy
            namespec = process.namespec()
            node_name = get_node(self.supvisors, command.strategy, process.possible_nodes(),
                                 process.rules.expected_load)
            if node_name:
                self.logger.info('Starter.process_job: request starting of {} at node={}'.format(namespec, node_name))
                # use asynchronous xml rpc to start program
                self.supvisors.zmq.pusher.send_start_process(node_name, namespec, command.extra_args)
                self.logger.debug('Starter.process_job: {} requested to start on {} at {}'
                                  .format(namespec, node_name, get_asctime(command.request_time)))
            else:
                self.logger.warn('Starter.process_job: no resource available to start {}'.format(namespec))
                self.supvisors.context.force_process_state(namespec, ProcessStates.FATAL, 'no resource available')
        # return True when the job is started
        return starting

    def process_failure(self, process):
        """ Updates the start sequence when a process could not be started. """
        application_name = process.application_name
        # impact of failure on application starting
        if process.rules.required:
            self.logger.warn('Starter.process_failure: starting failed for required {}'.format(process.process_name))
            # get starting failure strategy of related application
            application = self.supvisors.context.applications[application_name]
            failure_strategy = application.rules.starting_failure_strategy
            # apply strategy
            if failure_strategy == StartingFailureStrategies.ABORT:
                self.logger.error('Starter.process_failure: abort starting of application {}'.format(application_name))
                # remove failed application from starting
                # do not remove application from current_jobs as requests have already been sent
                self.planned_jobs.pop(application_name, None)
            elif failure_strategy == StartingFailureStrategies.STOP:
                self.logger.warn('Starter.process_failure: stop application={} requested'.format(application_name))
                self.planned_jobs.pop(application_name, None)
                # defer stop application so that any job in progress are not missed
                self.application_stop_requests.append(application_name)
            else:
                self.logger.warn('Starter.process_failure: continue starting application {}'.format(application_name))
        else:
            self.logger.warn('Starter.process_failure: starting failed for optional {}'.format(process.process_name))
            self.logger.warn('Starter.process_failure: continue starting application {}'.format(application_name))

    def after_jobs(self, application_name: str) -> None:
        """ Trigger any pending application stop once all application jobs are completed.

        :param application_name: the application name
        :return: None
        """
        application = self.supvisors.context.applications[application_name]
        if application_name in self.application_stop_requests:
            self.logger.warn('Starter.after_jobs: apply pending stop application={}'.format(application_name))
            self.application_stop_requests.remove(application_name)
            self.supvisors.stopper.stop_application(application)
        else:
            application.check_start_sequence()


class Stopper(Commander):
    """ Class handling the stopping of processes and applications. """

    def stop_applications(self):
        """ Plan and start the necessary jobs to stop all the applications having a stop_sequence. """
        self.logger.info('Stopper.stop_applications: stop all applications')
        # stopping initialization: push program list in jobs list
        for application in self.supvisors.context.applications.values():
            # do not stop an application that is not running
            if application.running() and application.rules.stop_sequence >= 0:
                self.store_application_stop_sequence(application)
        self.logger.debug('Stopper.stop_applications: planned_sequence={}'.format(self.printable_planned_sequence()))
        # start work
        self.trigger_jobs()

    def stop_application(self, application: ApplicationStatus) -> bool:
        """ Plan and start the necessary jobs to stop the application in parameter. """
        self.logger.info('Stopper.stop_application: stop application {}'.format(application.application_name))
        # push program list in jobs list and start work
        if application.running():
            self.store_application_stop_sequence(application)
            self.logger.debug('Stopper.stop_application: planned_sequence={}'.format(self.printable_planned_sequence()))
            # add application immediately to planned jobs
            self.planned_jobs.update(self.planned_sequence.pop(min(self.planned_sequence.keys())))
            self.process_application_jobs(application.application_name)
        # return True when stopped
        return not self.in_progress()

    def stop_process(self, process):
        """ Plan and start the necessary job to stop the process in parameter.
        Return False when stopping not completed. """
        self.logger.info('Stopper.stop_process: stop process {}'.format(process.namespec()))
        # push program list in current jobs list and start work
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
        application_sequence = {seq: [ProcessCommand(process) for process in processes]
                                for seq, processes in application.stop_sequence.items()}
        sequence = self.planned_sequence.setdefault(application.rules.stop_sequence, {})
        sequence[application.application_name] = application_sequence

    def process_job(self, command: ProcessCommand, jobs):
        """ Stops the process where it is running.
        Return True if process is stopping. """
        process = command.process
        if process.running():
            # use asynchronous xml rpc to stop program
            for node_name in process.running_nodes:
                self.logger.info('Stopper.process_job: stopping process {} on {}'.format(process.namespec(), node_name))
                self.supvisors.zmq.pusher.send_stop_process(node_name, process.namespec())
            # push to jobs and timestamp process
            command.request_time = time.time()
            self.logger.debug('Stopper.process_job: {} requested to stop at {}'
                              .format(process.namespec(), get_asctime(command.request_time)))
            jobs.append(command)
            return True

    def check_stopping(self) -> bool:
        """ Check the progress of the application stopping. """
        return self.check_progress('running', ProcessStates.UNKNOWN)

    def on_event(self, process: ProcessStatus) -> None:
        """ Triggers the following of the stop sequencing, depending on the new process status. """
        # check if process event has an impact on stopping in progress
        if process.application_name in self.current_jobs:
            jobs = self.current_jobs[process.application_name]
            self.logger.debug('Stopper.on_event: jobs={}'.format(self.printable_command_list(jobs)))
            command = self.get_process_command(process, jobs)
            if command:
                if process.running():
                    # several cases:
                    # 1) expected upon conciliation of a conflicting process
                    # 2) concurrent stopping / starting
                    self.logger.warn('Stopper.on_event: {} still running when stopping'.format(process.namespec()))
                elif process.stopped():
                    # goal reached, whatever the state
                    jobs.remove(command)
                # else STOPPING, on the way
                # check if there are remaining jobs in progress for this application
                if not jobs:
                    self.after_event(process.application_name)

    def after_jobs(self, application_name: str) -> None:
        """ Unset the application start failure.

        :param application_name: the application name
        :return: None
        """
        application = self.supvisors.context.applications[application_name]
        application.start_failure = False
