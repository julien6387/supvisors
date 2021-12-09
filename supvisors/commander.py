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

from typing import Any, Dict, List, Set

from supervisor.childutils import get_asctime
from supervisor.states import ProcessStates

from .application import ApplicationStatus
from .process import ProcessRules, ProcessStatus
from .strategy import get_node, LoadRequestMap
from .ttypes import NameList, Payload, StartingStrategies, StartingFailureStrategies


class ProcessCommand(object):
    """ Wrapper of the process to include data only used here.

    Attributes are:
        - process: the process wrapped,
        - node_names: the nodes where the commands are requested,
        - request_time: the date when the command is requested,
        - strategy: the strategy used to start the process if applicable,
        - distributed: set to False if the process belongs to an application that cannot be distributed,
        - ignore_wait_exit: used to command a process out of its application starting sequence,
        - extra_args: additional arguments to the command line.
    """
    TIMEOUT = 10

    def __init__(self, process: ProcessStatus, strategy: StartingStrategies = None) -> None:
        """ Initialization of the attributes.

        :param process: the process status to wrap
        :param strategy: the applicable starting strategy
        """
        self.process: ProcessStatus = process
        self.node_names: NameList = []
        self.request_time: int = 0
        # the following attributes are only for Starter
        self.strategy: StartingStrategies = strategy
        self.distributed: bool = True
        self.ignore_wait_exit: bool = False
        self.extra_args: str = ''

    def __str__(self) -> str:
        """ Get the process command as string.

        :return: the printable process command
        """
        return 'process={} state={} last_event_time={} node_names={} request_time={} strategy={}' \
               ' distributed=True ignore_wait_exit={} extra_args="{}"' \
            .format(self.process.namespec, self.process.state, self.process.last_event_time,
                    self.node_names, self.request_time, self.strategy.value if self.strategy else 'None',
                    self.ignore_wait_exit, self.extra_args)

    def timed_out(self, now: int) -> bool:
        """ Return True if there is still no event TIMEOUT seconds past the request.

        :param now: the current time
        :return: the timeout status
        """
        return max(self.process.last_event_time, self.request_time) + ProcessCommand.TIMEOUT < now


class Commander(object):
    """ Base class handling the starting / stopping of processes and applications.

    Attributes are:
        - planned_sequence: the applications to be commanded, as a dictionary of process commands,
          grouped by application sequence order, application name and process sequence order,
        - planned_jobs: the current sequence of applications to be commanded, as a dictionary of process commands,
          grouped by application name and process sequence order,
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
        # pickup logic
        self.pickup_logic = None

    def in_progress(self) -> bool:
        """ Return True if there are jobs planned or in progress.

        :return: the progress status
        """
        self.logger.trace('Commander.in_progress: planned_sequence={} planned_jobs={} current_jobs={}'
                          .format(self.printable_planned_sequence(),
                                  self.printable_planned_jobs(),
                                  self.printable_current_jobs()))
        return len(self.planned_sequence) > 0 or len(self.planned_jobs) > 0 or len(self.current_jobs) > 0

    def abort(self) -> None:
        """ Abort all jobs.

        :return: None
        """
        self.planned_sequence = {}
        self.planned_jobs = {}
        self.current_jobs = {}

    def get_job_applications(self) -> Set[str]:
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
                for application_sequence, applications in self.planned_sequence.items()}

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
        return [command.process.namespec for command in commands]

    @staticmethod
    def get_process_command(node_name: str, process_name: str, jobs: CommandList) -> ProcessCommand:
        """ Get the process wrapper from list.

        :param node_name: the process status to search
        :param process_name: the name of the process search
        :param jobs: the process command list
        :return: the process command found
        """
        return next((command for command in jobs
                     if node_name in command.node_names and command.process.process_name == process_name),
                    None)

    def trigger_jobs(self) -> None:
        """ Triggers the next sequence from the jobs planned (start or stop).

        :return: None
        """
        self.logger.info('Commander.trigger_jobs: planned_sequence={}'.format(self.printable_planned_sequence()))
        # pop lower sequence from planned_sequence
        while self.planned_sequence and not self.planned_jobs and not self.current_jobs:
            sequence = self.pickup_logic(self.planned_sequence.keys())
            self.planned_jobs = self.planned_sequence.pop(sequence)
            self.logger.debug('Commander.trigger_jobs: sequence={} planned_jobs={}'
                              .format(sequence, self.printable_planned_jobs()))
            # iterate on copy to avoid problems with key deletions
            for application_name in list(self.planned_jobs.keys()):
                self.logger.info('Commander.trigger_jobs: triggering sequence {} - application_name={}'
                                 .format(sequence, application_name))
                self.prepare_application_jobs(application_name)
                self.process_application_jobs(application_name)

    def prepare_application_jobs(self, application_name, application: ApplicationStatus = None) -> None:
        """ Prepare the ProcessCommand instances linked to application planned jobs.
        Implemented in Starter only.

        :param application_name: the application name
        :param application: the application if available
        :return: None
        """

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
                app_sequence = self.pickup_logic(sequence.keys())
                group = sequence.pop(app_sequence)
                self.logger.debug('Commander.process_application_jobs: application_name={}'
                                  ' - next group: app_sequence={} group={}'
                                  .format(application_name, app_sequence, self.printable_command_list(group)))
                for command in group:
                    self.logger.debug('Commander.process_application_jobs: {} - state={}'
                                      .format(command.process.namespec, command.process.state_string()))
                    self.process_job(command, jobs)
            self.logger.debug('Commander.process_application_jobs: current_jobs={}'
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

    def is_job_completed(self, condition: str, process_state: ProcessStates) -> bool:
        """ Check the progress of the application starting or stopping.

        :param condition: the ProcessStatus method name to be used to check progress
        :param process_state: the process state to force upon failure
        :return: True when there is no more pending jobs
        """
        in_progress = self.in_progress()
        self.logger.trace('Commander.is_job_completed: in_progress={}'.format(in_progress))
        if in_progress:
            commands = [command for command_list in self.current_jobs.values()
                        for command in command_list]
            if commands:
                # once the start_process (resp. stop_process) has been called, a STARTING (resp. STOPPING) event
                # is expected quite immediately from the Supervisor instance
                # if it doesn't, the whole sequencing would block waiting for an event that may never happen
                # typically, this can happen if request is sent to a supervisor that is shutting down
                now = int(time.time())
                self.logger.trace('Commander.is_job_completed: now={} checking commands={}'
                                  .format(now, [str(command) for command in commands]))
                for command in commands:
                    # get the ProcessStatus method corresponding to condition and call it
                    class_method = getattr(ProcessStatus, condition)
                    if class_method(command.process):
                        if command.timed_out(now):
                            self.logger.error('Commander.is_job_completed: {} still {} after {} seconds so abort'
                                              .format(command.process.namespec, condition, ProcessCommand.TIMEOUT))
                            # generate a process event for this process to inform all Supvisors instances
                            reason = 'Still {} {} seconds after request'.format(condition, ProcessCommand.TIMEOUT)
                            self.supvisors.listener.force_process_state(command.process.namespec, process_state, reason)
                            # don't wait for event, just abort the job
                            jobs = self.current_jobs[command.process.application_name]
                            jobs.remove(command)
                            # check if there are remaining jobs in progress for this application
                            if not jobs:
                                self.after_event(command.process.application_name)
            else:
                # no commands in the pipe
                # this can happen when nothing had to be stopped inside the planned_jobs
                self.logger.warn('Commander.is_job_completed: no current job but planned sequence still ongoing')
                # check if there are planned jobs
                if not self.planned_jobs:
                    # trigger next sequence of applications
                    self.trigger_jobs()
                else:
                    self.logger.critical('Starter.is_job_completed: UNEXPECTED')
        # return True when no more pending jobs
        return not self.in_progress()

    def on_nodes_invalidation(self, invalidated_nodes: NameList, process_failures: Set[ProcessStatus]) -> None:
        """ Clear the jobs in progress if requests are pending on the nodes recently declared SILENT.
        Indeed, this has to be considered as a starting failure, not a running failure.
        Typically, this may happen only if the processes were STARTING, BACKOFF or STOPPING on the lost nodes.
        Other states would have removed them from the current_jobs list.

        Clear the processes from process_failures if their starting or stopping is planned.
        An additional automatic behaviour on the same entity may not be suitable or even consistent.
        This case may seem a bit far-fetched but it has already happened actually in a degraded environment:
            - let N1 and N2 be 2 running nodes ;
            - let P be a process running on N2 ;
            - N2 is lost (let's assume a network congestion, NOT a node crash) so P becomes FATAL ;
            - P is requested to restart on N1 (automatic strategy, user action, etc) ;
            - while P is still in planned jobs, N2 comes back and thus P becomes RUNNING again ;
            - N2 gets lost again. P becomes FATAL again whereas its starting on N1 is still in the pipe.

        :param invalidated_nodes: the nodes that have just been declared SILENT
        :param process_failures: the processes that were running on these nodes and declared in failure
        :return: None
        """
        # clear the invalidated nodes from the pending requests
        for application_name, command_list in list(self.current_jobs.items()):
            for command in command_list:
                command.node_names = [node_name for node_name in command.node_names
                                      if node_name not in invalidated_nodes]
                # if no more pending request, declare a starting failure on the process
                # and remove from running process_failures set
                if not command.node_names:
                    self.process_failure(command.process)
                    process_failures.remove(command.process)
            # rebuild the command list
            jobs = [command for command in command_list if command.node_names]
            self.current_jobs[application_name] = jobs
            if not jobs:
                self.after_event(application_name)
        # don't trigger an automatic behaviour on processes in failure when jobs are already planned
        self.clear_process_failures(process_failures)

    def clear_process_failures(self, process_failures: Set[ProcessStatus]) -> None:
        """ Clear the processes from process_failures if their starting or stopping is planned.
        An additional automatic behaviour on the same entity may not be suitable or even consistent.

        This case may seem a bit far-fetched but it has already happened actually in a degraded environment:
            - let N1 and N2 be 2 running nodes ;
            - let P be a process running on N2 ;
            - N2 is lost (let's assume a network congestion, NOT a node crash) so P becomes FATAL ;
            - P is requested to restart on N1 (automatic strategy, user action, etc) ;
            - while P is still in planned jobs, N2 comes back and thus P becomes RUNNING again ;
            - N2 gets lost again. P becomes FATAL again whereas its starting on N1 is still in the pipe.

        :param process_failures: the processes declared in failure
        :return: None
        """
        for process in list(process_failures):
            # clear process failure if the process is included in the planned jobs in progress
            self.clear_process_failure(process, self.planned_jobs, process_failures)
            # clear process failure if the process is included in the planned sequence
            for planned_jobs in self.planned_sequence.values():
                self.clear_process_failure(process, planned_jobs, process_failures)

    @staticmethod
    def clear_process_failure(process: ProcessStatus, planned_jobs: PlannedJobs,
                              process_failures: Set[ProcessStatus]) -> None:
        """ Clear the process from process_failures if its starting or stopping is planned.

        :param process: the process declared in failure
        :param planned_jobs: a dictionary of planned jobs
        :param process_failures: the original list of processes declared in failure
        :return: None
        """
        planned_application_jobs = planned_jobs.get(process.application_name, {})
        planned_process_jobs = [command.process
                                for commands in planned_application_jobs.values()
                                for command in commands]
        if process in planned_process_jobs:
            # process command is planned so just wait
            process_failures.remove(process)

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
            self.logger.info('Commander.after_event: application={} - planned jobs completed'
                             .format(application_name))
            self.after_jobs(application_name)
            # check if there are planned jobs
            if not self.planned_jobs:
                self.logger.debug('Commander.after_event: planned jobs completed for all applications')
                # trigger next sequence of applications
                self.trigger_jobs()

    def after_jobs(self, application_name: str) -> None:
        """ Special processing when no more jobs for application.

        :param application_name: the application name
        :return: None
        """

    def process_failure(self, process: ProcessStatus) -> None:
        """ Special processing when the process job has failed.

        :param process: the process structure
        :return: None
        """


class Starter(Commander):
    """ Class handling the starting of processes and applications. """

    def __init__(self, supvisors: Any) -> None:
        """ Initialization of the attributes.

        :param supvisors: the global Supvisors structure.
        """
        super().__init__(supvisors)
        # pick jobs from the planned sequence using the lowest sequence number
        self.pickup_logic = min
        # attributes
        self.application_stop_requests: List[str] = []

    def start_applications(self, forced: bool) -> None:
        """ This method is called in the DEPLOYMENT phase.
        Plan and start the necessary jobs to start all the applications having a start_sequence.
        It uses the default strategy, as defined in the Supvisors section of the Supervisor configuration file.

        :param forced: a status telling if a full restart is required
        :return: None
        """
        self.logger.info('Starter.start_applications: start all applications')
        # internal call: default strategy always used
        for application in self.supvisors.context.applications.values():
            self.logger.debug('Starter.start_applications: application={} start_sequence={} never_started={}'
                              .format(str(application), application.rules.start_sequence, application.never_started()))
            # auto-started applications (start_sequence > 0) are not restarted if they have been stopped intentionally
            # give a chance to all applications in failure
            if application.rules.start_sequence > 0 and (forced or application.never_started()
                                                         or application.major_failure or application.minor_failure):
                self.store_application_start_sequence(application)
        # start work
        self.trigger_jobs()

    def default_start_application(self, application: ApplicationStatus) -> bool:
        """ Plan and start the necessary jobs to start the application in parameter, with the default strategy.

        :param application: the application to start
        :return: True if start completed (nothing to do actually)
        """
        return self.start_application(application.rules.starting_strategy, application)

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
            in_progress = self.in_progress()
            self.store_application_start_sequence(application, strategy)
            self.logger.debug('Starter.start_application: planned_sequence={}'
                              .format(self.printable_planned_sequence()))
            # if nothing in progress, trigger the jobs
            # else let the Starter logic take the new jobs when relevant
            if not in_progress:
                self.trigger_jobs()
        # return True when started
        return not self.in_progress()

    def default_start_process(self, process: ProcessStatus) -> bool:
        """ Plan and start the necessary job to start the process in parameter, with the default strategy.
        Default strategy is taken from the application owning this process.

        :param process: the process to start
        :return: True if no job has been queued.
        """
        application = self.supvisors.context.applications[process.application_name]
        return self.start_process(application.rules.starting_strategy, process)

    def start_process(self, strategy: StartingStrategies, process: ProcessStatus, extra_args: str = '') -> bool:
        """ Plan and start the necessary job to start the process in parameter, with the strategy requested.

        :param strategy: the strategy to be used to start the process
        :param process: the process to start
        :param extra_args: the arguments to be added to the command line
        :return: True if no job has been queued.
        """
        self.logger.info('Starter.start_process: start process {} using strategy {}'
                         .format(process.namespec, strategy.name))
        # store extra arguments to be passed to the command line
        command = ProcessCommand(process, strategy)
        command.extra_args = extra_args
        # WARN: when starting a single process (outside the scope of an application starting),
        # do NOT consider the 'wait_exit' rule
        command.ignore_wait_exit = True
        # push program list in job list and start work
        job = self.current_jobs.setdefault(process.application_name, [])
        queued = self.process_job(command, job)
        # upon failure, remove inProgress entry if empty
        if not job:
            del self.current_jobs[process.application_name]
        # return True when job queued
        return not queued

    def is_starting_completed(self) -> bool:
        """ Check the progress of the application starting.

        :return: True when starting is completed
        """
        return self.is_job_completed('stopped', ProcessStates.FATAL)

    def on_event(self, process: ProcessStatus, node_name: str, event: Payload) -> None:
        """ Triggers the following of the start sequencing, depending on the new process status. """
        try:
            # first check if event is in the sequence logic, i.e. it corresponds to a process in current jobs
            jobs = self.current_jobs[process.application_name]
            command = self.get_process_command(node_name, process.process_name, jobs)
            assert command
        except (KeyError, AssertionError):
            # otherwise, check if event impacts the starting sequence
            self.logger.debug('Starter.on_event: event {} from node={} does not match the current starting sequence'
                              .format(event, node_name))
            self.on_event_out_of_sequence(process, event)
        else:
            self.on_event_in_sequence(command, event, jobs)

    def on_event_in_sequence(self, command: ProcessCommand, event: Payload, jobs: Commander.CommandList) -> None:
        """ Manages the impact of an event that is part of the starting sequence.

        :param command: the process wrapper used in the jobs
        :param event: the process event received
        :param jobs: the jobs list being considered
        :return: None
        """
        process = command.process
        process_state, expected_exit = event['state'], event['expected']
        if process_state in (ProcessStates.STOPPED, ProcessStates.STOPPING, ProcessStates.UNKNOWN):
            # unexpected event in a starting phase: someone has requested to stop the process as it is starting
            # remove from inProgress
            # note that STOPPED should be impossible as it wouldn't be compliant to ProcessStates transitions logic
            # UNKNOWN is unlikely as it corresponds to an internal supervisord error
            jobs.remove(command)
            # decide to continue starting or not
            self.process_failure(process)
        elif process_state == ProcessStates.STARTING:
            # on the way
            pass
        elif process_state == ProcessStates.RUNNING:
            # if not exit expected, job done. otherwise, wait
            if not process.rules.wait_exit or command.ignore_wait_exit:
                jobs.remove(command)
        elif process_state == ProcessStates.BACKOFF:
            # something wrong happened, just wait
            self.logger.warn('Starter.on_event_in_sequence: problems detected with {}'.format(process.namespec))
        elif process_state == ProcessStates.EXITED:
            # remove from inProgress
            jobs.remove(command)
            # an EXITED process is accepted if wait_exit is set
            if process.rules.wait_exit and expected_exit:
                self.logger.info('Starter.on_event_in_sequence: expected exit for {}'.format(process.namespec))
            else:
                self.process_failure(process)
        elif process_state == ProcessStates.FATAL:
            # remove from inProgress
            jobs.remove(command)
            # decide to continue starting or not
            self.process_failure(process)
        # check if there are remaining jobs in progress for this application
        if not jobs:
            self.after_event(process.application_name)

    def on_event_out_of_sequence(self, process: ProcessStatus, event: Payload) -> None:
        """ Manages the impact of a crash event that is out of the starting sequence.

        Note: Keeping in mind the possible origins of the event:
            * a request performed by this Starter,
            * a request performed directly on any Supervisor (local or remote),
            * a request performed on a remote Supvisors,
        let's consider the following cases:
            1) The application is in the planned sequence, or process is in the planned jobs.
               => do nothing, give a chance to the Starter.
            2) The process is NOT in the application planned jobs.
               The process was likely started previously in the sequence of this Starter,
               and it crashed after its RUNNING state but before the application is fully started.
               => apply starting failure strategy through basic process_failure
            3) The application is NOT handled in this Starter
               => running failure strategy to be considered outside of the Starter scope
        """
        # find the conditions of case 2
        has_crashed = ProcessStatus.is_crashed_event(event['state'], event['expected'])
        if has_crashed and process.application_name in self.planned_jobs:
            planned_application_jobs = self.planned_jobs[process.application_name]
            planned_process_jobs = [command.process
                                    for commands in planned_application_jobs.values()
                                    for command in commands]
            if process not in planned_process_jobs:
                self.process_failure(process)

    def store_application_start_sequence(self, application: ApplicationStatus,
                                         strategy: StartingStrategies = None) -> None:
        """ Copy the start sequence and remove programs that are not meant to be started automatically,
        i.e. their start_sequence is 0.
        When strategy is not provided, use the application default starting strategy.

        :param application: the application to start
        :param strategy: the strategy to be used to choose nodes where programs shall be started
        :return: None
        """
        if strategy is None:
            strategy = application.rules.starting_strategy
        application_sequence = {seq: [ProcessCommand(process, strategy) for process in processes]
                                for seq, processes in application.start_sequence.items()
                                if seq > 0}
        if len(application_sequence) > 0:
            sequence = self.planned_sequence.setdefault(application.rules.start_sequence, {})
            sequence[application.application_name] = application_sequence
            self.logger.debug('Starter.store_application_start_sequence: start sequence stored for application_name={}'
                              ' with strategy={}'.format(application.application_name, strategy.name))

    def prepare_application_jobs(self, application_name, application: ApplicationStatus = None) -> None:
        """ Prepare the ProcessCommand instances linked to application planned jobs.

        :param application_name: the application name
        :param application: the application if available
        :return: None
        """
        # get application if not provided
        if not application:
            application = self.supvisors.context.applications[application_name]
        if not application.rules.distributed:
            # get all ProcessCommand instances of the application
            commands = [process for sequence in self.planned_jobs[application_name].values()
                        for process in sequence]
            strategy = next((command.strategy for command in commands if command.strategy is not None),
                            application.rules.starting_strategy)
            # find node iaw strategy
            node_name = get_node(self.supvisors, strategy, application.possible_nodes(),
                                 application.get_start_sequence_expected_load(), self.get_load_requests())
            self.logger.info('Starter.prepare_application_jobs: node_name={} found for non-distributed'
                             ' application_name={} using strategy={}'
                             .format(node_name, application_name, strategy.name))
            # apply the node to all commands
            for command in commands:
                # distributed information must be set to differentiate 2 cases:
                #     * application is distributed, so node_name has to be resolved later in process_jobs
                #     * application is not distributed and no applicable node_name has been found
                command.distributed = False
                command.node_names.append(node_name)

    def process_job(self, command: ProcessCommand, jobs: Commander.CommandList) -> bool:
        """ Start the process on the relevant node.

        :param command: the wrapper of the process to start
        :param jobs: the list of jobs in progress
        :return: True if a job has been queued.
        """
        queued = False
        process = command.process
        self.logger.debug('Starter.process_job: process={} stopped={}'.format(process.namespec, process.stopped()))
        if process.stopped():
            # node_name has already been decided for a non-distributed application
            if command.distributed:
                # find node iaw strategy
                node_name = get_node(self.supvisors, command.strategy, process.possible_nodes(),
                                     process.rules.expected_load, self.get_load_requests())
                self.logger.debug('Starter.process_job: found node={} to start process={} with strategy={}'
                                  .format(node_name, process.namespec, command.strategy.name))
                if node_name:
                    command.node_names.append(node_name)
            if command.node_names:
                # in Starter, only one node in node_names
                node_name = command.node_names[0]
                # use asynchronous xml rpc to start program
                self.supvisors.zmq.pusher.send_start_process(node_name, process.namespec, command.extra_args)
                self.logger.info('Starter.process_job: {} requested to start on {} at {}'
                                 .format(process.namespec, node_name, get_asctime(command.request_time)))
                # push command into current jobs
                command.request_time = time.time()
                jobs.append(command)
                queued = True
            else:
                self.logger.warn('Starter.process_job: no resource available to start {}'.format(process.namespec))
                self.supvisors.listener.force_process_state(process.namespec, ProcessStates.FATAL,
                                                            'no resource available')
                self.process_failure(process)
        # return True when the job is queued
        return queued

    def process_failure(self, process: ProcessStatus) -> None:
        """ Updates the start sequence when a process could not be started. """
        # impact of failure on application starting
        if process.rules.required:
            self.logger.warn('Starter.process_failure: starting failed for required {}'.format(process.namespec))
            # get starting failure strategy of related application
            application = self.supvisors.context.applications[process.application_name]
            failure_strategy = application.rules.starting_failure_strategy
            # apply strategy
            if failure_strategy == StartingFailureStrategies.ABORT:
                self.logger.warn('Starter.process_failure: abort starting of application {}'
                                 .format(process.application_name))
                # remove failed application from starting
                # do not remove application from current_jobs as requests have already been sent
                self.planned_jobs.pop(process.application_name, None)
            elif failure_strategy == StartingFailureStrategies.STOP:
                self.logger.warn('Starter.process_failure: stop application={} requested'
                                 .format(process.application_name))
                self.planned_jobs.pop(process.application_name, None)
                # defer stop application so that any job in progress are not missed
                self.application_stop_requests.append(process.application_name)
            else:
                self.logger.info('Starter.process_failure: continue starting application {}'
                                 .format(process.application_name))
        else:
            self.logger.warn('Starter.process_failure: starting failed for optional {}'.format(process.namespec))
            self.logger.info('Starter.process_failure: continue starting application {}'
                             .format(process.application_name))

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

    def get_load_requests(self) -> LoadRequestMap:
        """ From current_jobs, extract by node the processes that are requested to start but still stopped
        and sum their expected load.

        :return: the additional loading per node
        """
        load_request_map = {}
        # for distributed applications, add loading of current jobs
        for command_list in self.current_jobs.values():
            for command in command_list:
                # if process is not stopped, its loading is already considered in AddressStatus
                if command.process.stopped():
                    node_name = command.node_names[0]
                    load_request_map.setdefault(node_name, []).append(command.process.rules.expected_load)
        # for non-distributed applications, add loading of planned jobs
        for application_sequence in self.planned_jobs.values():
            for command_list in application_sequence.values():
                for command in command_list:
                    # if process is not stopped, its loading is already considered in AddressStatus
                    if not command.distributed and command.process.stopped():
                        node_name = command.node_names[0]
                        load_request_map.setdefault(node_name, []).append(command.process.rules.expected_load)
        return {node_name: sum(load_list) for node_name, load_list in load_request_map.items() if node_name}


class Stopper(Commander):
    """ Class handling the stopping of processes and applications. """

    def __init__(self, supvisors: Any) -> None:
        """ Initialization of the attributes.

        :param supvisors: the global Supvisors structure.
        """
        super().__init__(supvisors)
        # pick jobs from the planned sequence using the greatest sequence number
        self.pickup_logic = max

    def stop_applications(self):
        """ Plan and start the necessary jobs to stop all the applications having a stop_sequence. """
        self.logger.info('Stopper.stop_applications: stop all applications')
        # stopping initialization: push program list in jobs list
        for application in self.supvisors.context.applications.values():
            # do not check the application state are running processes may be excluded in the evaluation
            if application.has_running_processes():
                self.store_application_stop_sequence(application)
        self.logger.debug('Stopper.stop_applications: planned_sequence={}'.format(self.printable_planned_sequence()))
        # start work
        self.trigger_jobs()

    def stop_application(self, application: ApplicationStatus) -> bool:
        """ Plan and start the necessary jobs to stop the application in parameter. """
        self.logger.info('Stopper.stop_application: stop application {}'.format(application.application_name))
        # push program list in jobs list and start work
        if application.has_running_processes():
            in_progress = self.in_progress()
            self.store_application_stop_sequence(application)
            self.logger.debug('Stopper.stop_application: planned_sequence={}'.format(self.printable_planned_sequence()))
            # if nothing in progress, trigger the jobs
            # else let the Stopper logic take the new jobs when relevant
            if not in_progress:
                self.trigger_jobs()
        # return True when no job in progress
        return not self.in_progress()

    def stop_process(self, process):
        """ Plan and start the necessary job to stop the process in parameter.
        Return False when stopping not completed. """
        self.logger.info('Stopper.stop_process: stop process {}'.format(process.namespec))
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
                self.logger.info('Stopper.process_job: stopping process {} on {}'.format(process.namespec, node_name))
                self.supvisors.zmq.pusher.send_stop_process(node_name, process.namespec)
                command.node_names.append(node_name)
            # push to jobs and timestamp process
            command.request_time = time.time()
            self.logger.debug('Stopper.process_job: {} requested to stop at {}'
                              .format(process.namespec, get_asctime(command.request_time)))
            jobs.append(command)
            return True

    def is_stopping_completed(self) -> bool:
        """ Check the progress of the application stopping.
        If no corresponding process event received before long, consider the process STOPPED
        as very likely due to a supervisor being shut down.

        :return: True when stopping jobs are completed
        """
        return self.is_job_completed('running', ProcessStates.STOPPED)

    def on_event(self, process: ProcessStatus, node_name: str) -> None:
        """ Triggers the following of the stop sequencing, depending on the new process status. """
        # check if process event has an impact on stopping in progress
        if process.application_name in self.current_jobs:
            jobs = self.current_jobs[process.application_name]
            self.logger.debug('Stopper.on_event: jobs={}'.format(self.printable_command_list(jobs)))
            command = self.get_process_command(node_name, process.process_name, jobs)
            if command:
                if process.running():
                    # two cases:
                    # 1) stopping applications with multiple running instances of a program (unmanaged or conflict)
                    # 2) concurrent stopping / starting from multiple Supervisors
                    self.logger.debug('Stopper.on_event: {} still running when stopping'.format(process.namespec))
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
