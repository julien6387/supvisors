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

import math
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from supervisor.events import Tick5Event
from supervisor.loggers import Logger
from supervisor.states import ProcessStates, getProcessStateDescription, STOPPED_STATES

from .application import ApplicationStatus
from .instancestatus import SupvisorsInstanceStatus
from .process import ProcessStatus
from .strategy import get_supvisors_instance, get_node
from .ttypes import (DistributionRules, NameList, LoadMap, ProcessRequestResult, StartingStrategies,
                     StartingFailureStrategies)


class ProcessCommand:
    """ Wrapper of the ProcessStatus to manage start and stop requests.

    Attributes are:
        - process: the process wrapped ;
        - logger: a reference to the Supvisors logger ;
        - identifier: the identifier of Supvisors instance where the request has been sent ;
        - instance_status: the status of the corresponding Supvisors instance ;
        - request_sequence_counter: the sequence_counter of the Supvisors instance when the request has been performed ;
        - wait_ticks: the maximum number of ticks to wait before completion of the request.
    """

    # Tick margin, considering that there may already be a TICK in the pipe as the request is being sent
    # This will add a variable margin of [5;10] seconds
    DEFAULT_TICK_TIMEOUT = 2

    def __init__(self, process: ProcessStatus) -> None:
        """ Initialization of the attributes.

        :param process: the ProcessStatus of the process to command
        """
        self.process = process
        self.logger: Logger = process.logger
        self.identifier: Optional[str] = None
        self.instance_status: Optional[SupvisorsInstanceStatus] = None
        self.request_sequence_counter: int = 0
        # Note: a margin (network entanglement factor) is added to the default tick timeout considering the number
        # of active (i.e. non isolated) Supvisors instances
        # based on a real case with +30 Supvisors instances, 1s per 10 Supvisors instances is being considered
        # the worst case is during a full restart with a minimal set of core identifiers
        # the DEPLOYMENT phase is in progress while there are still lots to Supvisors instances in CHECKING state
        self.minimum_ticks = max(ProcessCommand.DEFAULT_TICK_TIMEOUT,
                                 len(process.supvisors.context.valid_instances()) // 10)
        self._wait_ticks: int = self.minimum_ticks

    def __str__(self) -> str:
        """ Get the process command as string.

        :return: the printable process command
        """
        return (f'process={self.process.namespec} state={self.process.state_string()} identifier={self.identifier}'
                f' request_sequence_counter={self.request_sequence_counter} wait_ticks={self.wait_ticks}')

    def __repr__(self) -> str:
        """ Get the process command as string.

        :return: the representation of a process command
        """
        return self.process.namespec

    @property
    def wait_ticks(self):
        """ Getter of the maximum number of ticks to wait before the completion of the request.

        :return: the number of ticks to wait
        """
        return self._wait_ticks

    @wait_ticks.setter
    def wait_ticks(self, wait_secs: int) -> None:
        """ Assign the maximum number of ticks to wait before the completion of the request.
        The TICK unit is 5 seconds. A tick margin is added to give Supervisor enough time to process the events.

        :param wait_secs: the maximum number of seconds to wait before the completion of the request
        :return: None
        """
        self._wait_ticks = math.ceil(wait_secs / Tick5Event.period) + self.minimum_ticks

    def update_identifier(self, identifier: str):
        """ Assign the targeted Supvisors instance.

        :param identifier: the identifier of the targeted Supvisors instance
        :return: None
        """
        self.identifier = identifier
        self.instance_status = self.process.supvisors.context.instances[identifier]

    def update_sequence_counter(self):
        """ Reset the reference sequence counter based on the current sequence counter
        of the targeted Supvisors instance.

        :return: None
        """
        self.request_sequence_counter = self.instance_status.sequence_counter

    def get_instance_info(self):
        """ Return the process info corresponding to the targeted Supvisors instance.

        :return: the current status of the process on the targeted Supvisors instance
        """
        return self.process.info_map.get(self.identifier)

    def timed_out(self) -> Tuple[ProcessStates, ProcessRequestResult, int]:
        """ Check if the request has not been acknowledged in a reasonable time.

        :return: the event expected and the timeout status
        """
        raise NotImplementedError

    def on_event(self):
        """ Evaluate the result of the Process request against the current state of the Process on the Supvisors
        instance where the request has been sent.

        :return: the request status
        """
        raise NotImplementedError


class ProcessStartCommand(ProcessCommand):
    """ Wrapper of the process to be started.

    Additional attributes are:
        - strategy: the strategy used to start the process if applicable,
        - ignore_wait_exit: used to command a process out of its application starting sequence,
        - extra_args: additional arguments to the command line.
    """

    def __init__(self, process: ProcessStatus, strategy: StartingStrategies) -> None:
        """ Initialization of the attributes.

        :param process: the process status to wrap
        :param strategy: the applicable starting strategy
        """
        super().__init__(process)
        # the following attributes are only for Starter
        self.strategy: StartingStrategies = strategy
        self.ignore_wait_exit: bool = False
        self.extra_args: str = ''

    def __str__(self) -> str:
        """ Get the process command as string.

        :return: the printable process command
        """
        return (f'{super().__str__()} strategy={self.strategy.name} ignore_wait_exit={self.ignore_wait_exit}'
                f' extra_args="{self.extra_args}"')

    def update_identifier(self, identifier: str):
        """ Assign the targeted Supvisors instance and the number of ticks to wait.

        :param identifier: the identifier of the targeted Supvisors instance
        :return: None
        """
        super().update_identifier(identifier)
        # define the maximum number of ticks to wait according to the program startsecs
        self.wait_ticks = self.get_instance_info()['startsecs']

    def on_event(self) -> ProcessRequestResult:
        """ Evaluate the result of the Process start request against the current state of the Process on the Supvisors
        instance where the request has been sent.

        :return: the request status
        """
        instance_info = self.get_instance_info()
        process_state = instance_info['state']
        if process_state == ProcessStates.STARTING:
            # all right, on the way
            self.logger.debug(f'ProcessStartCommand.on_event: starting in progress for {self.process.namespec}'
                              f' on {self.identifier}')
            return ProcessRequestResult.IN_PROGRESS
        if process_state == ProcessStates.RUNNING:
            # if no exit is expected, the job is done. otherwise, wait
            if not self.process.rules.wait_exit or self.ignore_wait_exit:
                self.logger.info(f'ProcessStartCommand.on_event: starting completed for {self.process.namespec}'
                                 f' on {self.identifier}')
                return ProcessRequestResult.SUCCESS
            self.logger.info(f'ProcessStartCommand.on_event: waiting exit for {self.process.namespec}'
                             f' on {self.identifier}')
            return ProcessRequestResult.IN_PROGRESS
        if process_state == ProcessStates.EXITED:
            # an EXITED process is accepted if wait_exit is set
            if self.process.rules.wait_exit and instance_info['expected']:
                self.logger.info(f'ProcessStartCommand.on_event: expected exit for {self.process.namespec}'
                                 f' on {self.identifier}')
                return ProcessRequestResult.SUCCESS
            self.logger.error(f'ProcessStartCommand.on_event: unexpected exit for {self.process.namespec}'
                              f' on {self.identifier}')
            return ProcessRequestResult.FAILED
        if process_state == ProcessStates.BACKOFF:
            # something wrong happened, reset sequence_counter to consider new timeout
            self.logger.debug(f'ProcessStartCommand.on_event: reset counter for the starting of {self.process.namespec}'
                              f' on {self.identifier}')
            self.request_sequence_counter = self.instance_status.sequence_counter
            return ProcessRequestResult.IN_PROGRESS
        if process_state == ProcessStates.FATAL:
            self.logger.error(f'ProcessStartCommand.on_event: crash of {self.process.namespec} on {self.identifier}')
            return ProcessRequestResult.FAILED
        if process_state in (ProcessStates.STOPPED, ProcessStates.STOPPING, ProcessStates.UNKNOWN):
            # STOPPED should be impossible as it wouldn't be compliant to ProcessStates transitions logic
            # STOPPING would mean that someone has requested to stop the process as it is starting
            # UNKNOWN is unlikely as it corresponds to an internal supervisord error
            self.logger.error('ProcessStartCommand.on_event:'
                              f' unexpected event={getProcessStateDescription(process_state)}'
                              f' while starting {self.process.namespec} on {self.identifier}')
            return ProcessRequestResult.FAILED

    def timed_out(self) -> Tuple[ProcessStates, ProcessRequestResult, int]:
        """ Check if the request has not been acknowledged in a reasonable time.

        :return: the event expected, the timeout status and the date of the last event received
        """
        # check the process state on the targeted Supvisors instance
        instance_info = self.get_instance_info()
        process_state = instance_info['state']
        process_state_date = instance_info['now']
        # if the evaluation is done in the RUNNING state, the EXITED state must be expected
        # otherwise the ProcessCommand would have been removed
        # this part is a risk for the Supvisors Starter to wait forever
        if process_state == ProcessStates.RUNNING:
            if self.process.rules.wait_exit and not self.ignore_wait_exit:
                return ProcessStates.EXITED, ProcessRequestResult.IN_PROGRESS, process_state_date
            # WARN: very seldom but seen once.
            #       It happened in a context where a Supvisors instance was set to RUNNING during the start sequence
            #       The Supvisors instance was then a possible candidate to start a process.
            #       However, its process information was not received yet.
            #       The new instance has been selected and the process information has been received just after.
            #       The context.load_processes does NOT feed the sequencers.
            self.logger.warn(f'ProcessStartCommand.timed_out: {self.process.namespec} already RUNNING'
                             f' on {self.identifier}')
            return ProcessStates.RUNNING, ProcessRequestResult.SUCCESS, process_state_date
        # once STARTING, the RUNNING state is expected after startsecs seconds
        if process_state in [ProcessStates.BACKOFF, ProcessStates.STARTING]:
            expected_state = ProcessStates.RUNNING
            max_tick_counter = self.request_sequence_counter + self.wait_ticks
            self.logger.debug(f'ProcessStartCommand.timed_out: expect RUNNING for {self.process.namespec} with'
                              f' max_tick_counter={max_tick_counter}'
                              f' sequence_counter={self.instance_status.sequence_counter}')
            if self.instance_status.sequence_counter > max_tick_counter:
                self.logger.error(f'ProcessStartCommand.timed_out: {self.process.namespec} still not RUNNING'
                                  f' on {self.identifier} after {self.wait_ticks} ticks so abort')
                return expected_state, ProcessRequestResult.TIMED_OUT, process_state_date
        else:
            # from STOPPED_STATES, STARTING or BACKOFF event is expected quite immediately
            # STOPPING is unexpected unless an external request has been performed
            # (e.g. stop request while in STARTING state)
            expected_state = ProcessStates.STARTING
            max_tick_counter = self.request_sequence_counter + self.minimum_ticks
            self.logger.debug(f'ProcessStartCommand.timed_out: expect STARTING for {self.process.namespec} with'
                              f' max_tick_counter={max_tick_counter}'
                              f' sequence_counter={self.instance_status.sequence_counter}')
            if self.instance_status.sequence_counter > max_tick_counter:
                self.logger.error(f'ProcessStartCommand.timed_out: {self.process.namespec} still not STARTING'
                                  f' on {self.identifier} after {self.minimum_ticks} ticks so abort')
                return expected_state, ProcessRequestResult.TIMED_OUT, process_state_date
        # time out not reached
        return expected_state, ProcessRequestResult.IN_PROGRESS, process_state_date


class ProcessStopCommand(ProcessCommand):
    """ Wrapper of the process to be stopped. """

    def __init__(self, process: ProcessStatus, identifier: str) -> None:
        """ Initialization of the attributes.

        :param process: the ProcessStatus of the process to command
        :param identifier: the identifier of the Supvisors instance where the process is running and has to be stopped
        """
        super().__init__(process)
        # identifier is known right from the start
        self.update_identifier(identifier)

    def update_identifier(self, identifier: str):
        """ Assign the targeted Supvisors instance and the number of ticks to wait.

        :param identifier: the identifier of the targeted Supvisors instance
        :return: None
        """
        super().update_identifier(identifier)
        # define the maximum number of ticks to wait according to the program stopwaitsecs
        self.wait_ticks = self.get_instance_info()['stopwaitsecs']

    def on_event(self) -> ProcessRequestResult:
        """ Evaluate the result of the Process stop request against the current state of the Process on the Supvisors
        instance where the request has been sent.

        :return: the request status
        """
        instance_info = self.get_instance_info()
        process_state = instance_info['state']
        # check if process event has an impact on stopping in progress
        if process_state in STOPPED_STATES:
            self.logger.info(f'ProcessStopCommand.on_event: stopping completed for {self.process.namespec}'
                             f' on {self.identifier}')
            return ProcessRequestResult.SUCCESS
        # STOPPING: all right, on the way
        return ProcessRequestResult.IN_PROGRESS
        # RUNNING_STATES: should be impossible as it wouldn't be compliant to ProcessStates transitions logic

    def timed_out(self) -> Tuple[ProcessStates, ProcessRequestResult, int]:
        """ Check if the request has not been acknowledged in a reasonable time.

        :return: the event expected and the timeout status
        """
        # check the process state on the targeted Supvisors instance
        instance_info = self.get_instance_info()
        process_state = instance_info['state']
        process_state_time = instance_info['event_time']
        if process_state == ProcessStates.STOPPING:
            # the STOPPED state is expected after stopwaitsecs seconds
            expected_state = ProcessStates.STOPPED
            if self.request_sequence_counter + self.wait_ticks < self.instance_status.sequence_counter:
                self.logger.error(f'ProcessStopCommand.timed_out: {self.process.namespec} still not STOPPED'
                                  f' on {self.identifier} after {self.wait_ticks} ticks so abort')
                return expected_state, ProcessRequestResult.TIMED_OUT, process_state_time
        elif process_state in STOPPED_STATES:
            # WARN: very unlikely. never happened. if the present section is reached, something wrong happened.
            #       It has to be dealt with anyway to avoid the sequencer to block.
            self.logger.critical(f'ProcessStopCommand.timed_out: {self.process.namespec} already stopped'
                                 f' on {self.identifier}. Events have been missed')
            return process_state, ProcessRequestResult.SUCCESS, process_state_time
        else:
            # from RUNNING_STATES, STOPPING event is expected quite immediately
            expected_state = ProcessStates.STOPPING
            # STOPPED_STATES are unexpected because this wrapper would have been removed
            max_tick_counter = self.request_sequence_counter + self.minimum_ticks
            if self.instance_status.sequence_counter > max_tick_counter:
                self.logger.error(f'ProcessStopCommand.timed_out: {self.process.namespec} still not STOPPING'
                                  f' on {self.identifier} after {self.minimum_ticks} ticks so abort')
                return expected_state, ProcessRequestResult.TIMED_OUT, process_state_time
        # time out not reached
        return expected_state, ProcessRequestResult.IN_PROGRESS, process_state_time


class ApplicationJobs(object):
    """ Manages the lifecycle of an application start/stop sequence. """

    # Annotation types
    CommandList = List[ProcessCommand]
    PlannedJobs = Dict[int, CommandList]  # {proc_seq: [proc_cmd]}

    # Annotation types for printing facilities
    PrintableCommandList = List[str]
    PrintablePlannedJobs = Dict[int, PrintableCommandList]

    def __init__(self, application: ApplicationStatus, jobs: PlannedJobs, supvisors: Any) -> None:
        """ Initialization of the attributes.

        :param application: the Supvisors application structure
        :param jobs: the processes to start / stop with the expected sequence
        :param supvisors: the global Supvisors structure
        """
        # keep a reference of the Supvisors data
        self.supvisors = supvisors
        self.logger: Logger = supvisors.logger
        # store reference to application
        self.application: ApplicationStatus = application
        self.application_name: str = application.application_name
        # attributes
        self.planned_jobs: ApplicationJobs.PlannedJobs = jobs
        self.current_jobs: ApplicationJobs.CommandList = []
        # pickup logic is used to pop a subgroup from a sequence
        self.pickup_logic = None
        # failure_state is used to force the process state upon failure
        self.failure_state = ProcessStates.UNKNOWN

    # miscellaneous methods
    def __repr__(self):
        """ Get the applications jobs as string.

        :return: the representation of a process command
        """
        return f'(planned_jobs={self.planned_jobs} current_jobs={self.current_jobs})'

    @staticmethod
    def get_command(jobs: CommandList, process_name: str, identifier: str = None) -> ProcessCommand:
        """ Get the process wrapper from the current_jobs.

        :param jobs: the command list to search in
        :param process_name: the name of the process search
        :param identifier: the identifier to search
        :return: the process command found
        """
        return next((command for command in jobs
                     if ((not identifier or identifier == command.identifier)
                         and command.process.process_name == process_name)),
                    None)

    def get_current_command(self, process_name: str, identifier: str = None) -> ProcessCommand:
        """ Get the process wrapper from the current_jobs.

        :param process_name: the name of the process search
        :param identifier: the identifier to search
        :return: the process command found
        """
        return self.get_command(self.current_jobs, process_name, identifier)

    def get_planned_command(self, process_name: str, identifier: str = None) -> ProcessCommand:
        """ Get the process wrapper from the planned_jobs.

        :param process_name: the name of the process search
        :param identifier: the identifier to search
        :return: the process command found
        """
        planned_commands = sum(self.planned_jobs.values(), [])
        return self.get_command(planned_commands, process_name, identifier)

    def add_commands(self, jobs: PlannedJobs) -> None:
        """ Add a process wrapper to the application jobs, if possible.
        PlannedJobs structure is used but only one element is expected.

        :param jobs: the sequenced process wrapper
        :return: None
        """
        # search for this command in existing lists
        for sequence_number, command_list in jobs.items():
            for command in command_list:
                current_job = self.get_current_command(command.process.process_name, command.identifier)
                planned_job = self.get_planned_command(command.process.process_name, command.identifier)
                if current_job or planned_job:
                    # not relevant to consider a process already considered
                    self.logger.warn(f'ApplicationJobs.add_commands: {command.process.namespec} already planned'
                                     f' on {command.identifier}')
                else:
                    # add the command to planned_jobs
                    self.logger.debug(f'ApplicationJobs.add_commands: {command.process.namespec} planned'
                                      f' on {command.identifier}')
                    self.planned_jobs.setdefault(sequence_number, []).append(command)
                    self.on_command_added(command)

    def on_command_added(self, command: ProcessCommand) -> None:
        """ Notification that a command has been added to the planned jobs.

        :param command: the command added in planned_jobs
        :return: None
        """

    # life cycle methods
    def in_progress(self) -> bool:
        """ Return True if there are application jobs planned or in progress.

        :return: the progress status
        """
        self.logger.trace(f'ApplicationJobs.in_progress: planned_jobs={self.planned_jobs}'
                          f' current_jobs={self.current_jobs}')
        return len(self.planned_jobs) > 0 or len(self.current_jobs) > 0

    def before(self) -> None:
        """ Special processing to be done before command sequences start.

        :return: None
        """

    def next(self) -> None:
        """ Triggers the next sequenced group of the application.

        :return: None
        """
        if not self.current_jobs and self.planned_jobs:
            # pop lower group from sequence
            sequence_number = self.pickup_logic(self.planned_jobs)
            group = self.planned_jobs.pop(sequence_number)
            self.logger.debug(f'ApplicationJobs.next: application_name={self.application_name}'
                              f' - next sequence={sequence_number} group={group}')
            # trigger application jobs
            # do NOT use a list comprehension as pending requests will not be considered in instance load
            # process the jobs one by one and insert them in current_jobs asap
            for command in group:
                if self.process_job(command):
                    self.current_jobs.append(command)
            self.logger.trace(f'ApplicationJobs.next: current_jobs={self.current_jobs}')
            # recursive call in the event where there's already nothing left to do
            self.next()

    def process_job(self, command: ProcessCommand) -> bool:
        """ Perform the action on process and push progress in jobs list.
        Method must be implemented in subclasses Starter and Stopper.

        :param command: the process command
        :return: True if a job request is in progress
        """
        raise NotImplementedError

    def process_failure(self, process: ProcessStatus) -> None:
        """ Special processing when the process job has failed.

        :param process: the process structure
        :return: None
        """

    def check(self) -> None:
        """ Search for requests haven't been acknowledged.
        A timeout is implemented on requests to avoid the whole sequence to be blocked due to a missing event.

        :return: None
        """
        # once the start_process (resp. stop_process) has been called, a STARTING (resp. STOPPING) event
        # is expected quite immediately from the Supervisor instance
        # the RUNNING (resp. STOPPED) event depends on the startsecs (resp. stopwaitsecs) value configured
        self.logger.trace(f'Commander.check: checking commands={self.current_jobs}')
        for command in list(self.current_jobs):
            # get the ProcessStatus method corresponding to condition and call it
            expected_state, result, event_date = command.timed_out()
            if result == ProcessRequestResult.TIMED_OUT:
                # generate a process event for this process to inform all Supvisors instances
                reason = f'process {getProcessStateDescription(expected_state)} event not received in time'
                self.supvisors.listener.force_process_state(command.process, command.identifier, event_date,
                                                            self.failure_state, reason)
                # don't wait for event, abort the job right now
                self.current_jobs.remove(command)
            if result == ProcessRequestResult.SUCCESS:
                # NOTE: the result has been reached outside the scope of the sequencer
                #       the job MUST be removed of the sequencer will block
                self.current_jobs.remove(command)
        # trigger jobs
        self.next()

    # event methods
    def on_event(self, process: ProcessStatus, identifier: str) -> None:
        """ Check the impact of the process event on the jobs in progress.

        :param process: the Supvisors process corresponding to the event
        :param identifier: the identifier of the Supvisors instance that sent the event
        :return: None
        """
        self.logger.debug(f'ApplicationJobs.on_event: process={process.namespec} from Supvisors={identifier}')
        # first check if event is in the sequence logic, i.e. it corresponds to a process in current jobs
        command = self.get_current_command(process.process_name, identifier)
        if command:
            result = command.on_event()
            if result in [ProcessRequestResult.SUCCESS, ProcessRequestResult.FAILED]:
                # on completion, remove the command from current jobs
                self.current_jobs.remove(command)
                # if the command failed, trigger the configured actions
                if result == ProcessRequestResult.FAILED:
                    self.process_failure(command.process)
                # next job activities
                self.next()
        else:
            self.logger.debug(f'ApplicationJobs.on_event: no corresponding job in the current sequence')
            # Various cases may lead to that situation:
            #   * the process has crashed / exited after its RUNNING state but before the application is fully started
            #     => let the running failure strategy deal with that
            #   * the process is not in the automatic application sequence (so the event is related to a manual request)
            #     => just ignore

    def on_instances_invalidation(self, invalidated_identifiers: NameList,
                                  failed_processes: Set[ProcessStatus]) -> None:
        """ Clear the jobs in progress if requests are pending on the Supvisors instances recently declared SILENT.
        In addition to that, clear the processes from failed_processes if a corresponding request is pending or planned.

        :param invalidated_identifiers: the identifiers of the Supvisors instances that have just been declared SILENT
        :param failed_processes: the processes that were running on the invalidated Supvisors instances and thus
        declared in failure
        :return: None
        """
        # clear the invalidated instances from the pending requests
        for command in list(self.current_jobs):
            # if no more pending request, declare a starting failure on the process
            # and remove the process from failed_processes as this is a starting failure, not a running failure
            if command.identifier in invalidated_identifiers:
                self.current_jobs.remove(command)
                self.process_failure(command.process)
                # WARN: if the instance shut down just before it received the start request, the process is still
                # stopped, so it cannot be in failed_processes
                if command.process in failed_processes:
                    failed_processes.remove(command.process)
        # don't trigger an automatic behaviour on processes in failure when jobs are already planned
        for command in sum(self.planned_jobs.values(), []):
            if command.process in failed_processes:
                failed_processes.remove(command.process)
        # no need to trigger jobs
        # this method is already triggered by the upper periodic check that will call self.next() anyway

    def get_load_requests(self) -> LoadMap:
        """ Extract by identifier of Supvisors instance the processes that are planned to start but still stopped
        and sum their expected load. Only applicable to ApplicationStartJobs.

        :return: the additional loading per Supvisors instance
        """


class ApplicationStartJobs(ApplicationJobs):
    """ Specialization of ApplicationJobs to start applications.

    Attributes are:
        - pickup_logic: choose the minimum value (overridden from ApplicationJobs) ;
        - failure_state: used to force the process state upon start failure (overridden from ApplicationJobs) ;
        - starting_strategy: the strategy to choose a Supvisors instance when starting a process of the application ;
        - distribution: the distribution rule of the application
        - identifiers: the applicable identifiers (only set for a non-distributed application) ;
        - stop_request: intended to the Starter to point out an application that needs to be stopped.
    """

    def __init__(self, application: ApplicationStatus, jobs: ApplicationJobs.PlannedJobs,
                 starting_strategy: StartingStrategies, supvisors: Any) -> None:
        """ Initialization of the attributes.

        :param application: the Supvisors application structure
        :param jobs: the processes to start with the expected sequence
        :param starting_strategy: the starting strategy requested for the application
        :param supvisors: the global Supvisors structure
        """
        super().__init__(application, jobs, supvisors)
        # override default pickup logic
        self.pickup_logic = min
        # override default process failure state
        self.failure_state: int = ProcessStates.FATAL
        # store application default rules
        self.starting_strategy: StartingStrategies = starting_strategy
        self.distribution: DistributionRules = self.application.rules.distribution
        self.identifiers: NameList = []
        # flags for use at Starter level
        self.stop_request: bool = False

    # miscellaneous methods
    def on_command_added(self, command: ProcessCommand) -> None:
        """ Notification that a command has been added to the planned jobs.

        :param command: the command added in planned_jobs
        :return: None
        """
        # in the case of a non-distributed application, one of the selected Supvisors instances must be applied
        if self.distribution != DistributionRules.ALL_INSTANCES:
            if not self.identifiers:
                self.logger.debug('ApplicationStartJobs.on_command_added: no candidate Supvisors instance to start'
                                  f' {command.process.namespec}')
                return None
            load = command.process.rules.expected_load
            # check that one of the chosen Supvisors instances can support the new process
            # in a non-distributed application, the application starting_strategy applies
            self.logger.trace('ApplicationStartJobs.on_command_added: searching a Supvisors instance among'
                              f' {self.identifiers} to start {command.process.namespec} with load={load}')
            identifier = get_supvisors_instance(self.supvisors, self.starting_strategy, self.identifiers, load)
            if identifier:
                self.logger.debug(f'ApplicationStartJobs.on_command_added: {command.process.namespec} is planned to'
                                  f' start on Supvisors={identifier}')
                command.update_identifier(identifier)
            else:
                self.logger.debug(f'ApplicationStartJobs.on_command_added: {command.process.namespec} cannot'
                                  f' be started on any of the chosen Supvisors among {self.identifiers}')

    def get_load_requests(self) -> LoadMap:
        """ Extract by Supvisors instance the processes that are planned to start but still stopped
        and sum their expected load.

        :return: the additional loading per Supvisors instance
        """
        load_request_map = {}
        # sum the loading of all jobs having a targeted Supvisors instance and whose process is not fully started yet
        for command in self.current_jobs + sum(self.planned_jobs.values(), []):
            # if process is not stopped, its loading is already considered through SupvisorsInstanceStatus
            if command.process.stopped() and command.identifier:
                identifier = command.identifier
                load_request_map.setdefault(identifier, []).append(command.process.rules.expected_load)
        return {identifier: sum(load_list) for identifier, load_list in load_request_map.items()}

    # lifecycle methods
    def distribute_to_single_node(self) -> None:
        """ Assign Supvisors instances to each process of the non-distributed application, with the assumption
        that all processes must run in Supvisors instances that are running on the same node.

        :return: None
        """
        # FIXME: what if any process of this application is already running (started manually) ?
        # get all ProcessStartCommand of the application
        commands = [process for sequence in self.planned_jobs.values() for process in sequence]
        # find the applicable Supvisors instances iaw strategy
        application_load = self.application.get_start_sequence_expected_load()
        identifiers = self.application.possible_node_identifiers()
        # choose the node that can support the application load
        node_name = get_node(self.supvisors, self.starting_strategy, identifiers, application_load)
        # intersect the identifiers running on the node and the application possible identifiers
        # comprehension based on iteration over application possible identifiers to keep the CONFIG order
        node_identifiers = list(self.supvisors.mapper.nodes.get(node_name, []))
        self.identifiers = [identifier for identifier in identifiers if identifier in node_identifiers]
        if self.identifiers:
            self.logger.trace(f'ApplicationStartJobs.distribute_to_single_node: Supvisors={self.identifiers}'
                              f' of node={node_name} are selected to start {self.application_name}')
            # for all commands, select an identifier from the chosen node
            for command in commands:
                process_load = command.process.rules.expected_load
                identifier = get_supvisors_instance(self.supvisors, self.starting_strategy,
                                                    self.identifiers, process_load)
                self.logger.debug(f'ApplicationStartJobs.distribute_to_single_node: {command.process.namespec}'
                                  f' is planned to start on Supvisors={identifier}')
                command.update_identifier(identifier)
        else:
            self.logger.debug('ApplicationStartJobs.distribute_to_single_node: no Supvisors instance found to plan'
                              f' the starting of {self.application_name} with load={application_load}')

    def distribute_to_single_instance(self) -> None:
        """ Assign a Supvisors instance to each process of the non-distributed application, with the assumption
        that all processes must run in the same Supvisors instance.

        :return: None
        """
        # FIXME: what if any process of this application is already running (started manually) ?
        # get all ProcessStartCommand of the application
        commands = [process for sequence in self.planned_jobs.values() for process in sequence]
        # find the applicable Supvisors instances iaw strategy
        application_load = self.application.get_start_sequence_expected_load()
        identifiers = self.application.possible_identifiers()
        # choose the Supvisors instance that can support the application load
        identifier = get_supvisors_instance(self.supvisors, self.starting_strategy, identifiers, application_load)
        if identifier:
            self.logger.debug(f'ApplicationStartJobs.before: Supvisors={identifier} is selected to start all processes'
                              f' of {self.application_name}')
            # store the selection and apply the identifier to all commands
            self.identifiers = [identifier]
            for command in commands:
                command.update_identifier(identifier)
        else:
            self.logger.debug('ApplicationStartJobs.distribute_to_single_instance: no Supvisors instance found to plan'
                              f' the starting of {self.application_name} with load={application_load}')

    def before(self) -> None:
        """ Prepare the ProcessStartCommand linked to the planned jobs.
        More particularly, in the case of a non-distributed application, the Supvisors instance must be found
        at this stage, considering the load of the whole application at once.

        :return: None
        """
        if self.distribution == DistributionRules.SINGLE_NODE:
            self.distribute_to_single_node()
        elif self.distribution == DistributionRules.SINGLE_INSTANCE:
            self.distribute_to_single_instance()

    def process_job(self, command: ProcessStartCommand) -> bool:
        """ Start the process on the relevant Supvisors instance.

        :param command: the wrapper of the process to start
        :return: True if a job has been queued.
        """
        queued = False
        process = command.process
        self.logger.debug(f'ApplicationStartJobs.process_job: process={process.namespec} stopped={process.stopped()}')
        if process.stopped():
            # TODO: now that load request is in place, selection could be all done before
            # identifier has already been decided for a non-distributed application
            if self.distribution == DistributionRules.ALL_INSTANCES:
                # find Supvisors instance iaw strategy
                identifier = get_supvisors_instance(self.supvisors, command.strategy, process.possible_identifiers(),
                                                    process.rules.expected_load)
                self.logger.debug(f'ApplicationStartJobs.process_job: found Supvisors={identifier} to start'
                                  f' process={process.namespec} with strategy={command.strategy.name}')
                if identifier:
                    command.update_identifier(identifier)
            if command.identifier:
                # use asynchronous xml rpc to start program
                self.supvisors.internal_com.pusher.send_start_process(command.identifier, process.namespec,
                                                                      command.extra_args)
                command.update_sequence_counter()
                self.logger.info(f'ApplicationStartJobs.process_job: {process.namespec} requested to start'
                                 f' on {command.identifier}')
                queued = True
            else:
                self.logger.warn(f'ApplicationStartJobs.process_job: no resource available for {process.namespec}')
                self.supvisors.listener.force_process_state(command.process, '', time.time(),
                                                            self.failure_state, 'no resource available')
                self.process_failure(process)
        # return True when the job is queued
        return queued

    def process_failure(self, process: ProcessStatus) -> None:
        """ Updates the start sequence when a process could not be started.

        :param process: the process that failed to start
        :return: None
        """
        # impact of failure on application starting
        if process.rules.required:
            self.logger.debug(f'ApplicationStartJobs.process_failure: starting failed for required {process.namespec}')
            # apply starting failure strategy
            failure_strategy = process.rules.starting_failure_strategy
            if failure_strategy == StartingFailureStrategies.ABORT:
                self.logger.warn(f'ApplicationStartJobs.process_failure: abort starting {process.application_name}')
                # erase planned_jobs but process current jobs until completion
                self.planned_jobs = {}
            elif failure_strategy == StartingFailureStrategies.STOP:
                self.logger.warn(f'ApplicationStartJobs.process_failure: stop {process.application_name} requested')
                # erase planned_jobs but process current jobs until completion
                # application stop must be deferred so that any job in progress are not missed
                self.planned_jobs = {}
                self.stop_request = True
            else:
                self.logger.info(f'ApplicationStartJobs.process_failure: continue starting {process.application_name}')
        else:
            self.logger.debug(f'ApplicationStartJobs.process_failure: starting failed for optional {process.namespec}')
            self.logger.info(f'ApplicationStartJobs.process_failure: continue starting {process.application_name}')


class ApplicationStopJobs(ApplicationJobs):
    """ Specialization of ApplicationJobs to stop applications. """

    def __init__(self, application: ApplicationStatus, jobs: ApplicationJobs.PlannedJobs, supvisors: Any) -> None:
        """ Initialization of the attributes.

        :param application: the Supvisors application structure.
        :param jobs: the processes to stop with the expected sequence.
        :param supvisors: the global Supvisors structure.
        """
        super().__init__(application, jobs, supvisors)
        # override default pickup logic
        self.pickup_logic = max
        # override default process failure state
        self.failure_state = ProcessStates.STOPPED

    # lifecycle methods
    def process_job(self, command: ProcessCommand) -> bool:
        """ Stops the process where it is running.

        :param command: the wrapper of the process to stop
        :return: True if a job has been queued
        """
        process = command.process
        running = process.running_on(command.identifier)
        self.logger.debug(f'ApplicationStopJobs.process_job: process={process.namespec}'
                          f' running_on({command.identifier})={running}')
        if running:
            # use asynchronous xml rpc to stop program
            self.supvisors.internal_com.pusher.send_stop_process(command.identifier, process.namespec)
            command.update_sequence_counter()
            self.logger.info(f'ApplicationStopJobs.process_job: {process.namespec} requested to stop'
                             f' on {command.identifier}')
            return True


class Commander:
    """ Base class handling the starting / stopping of processes and applications.

    Attributes are:
        - planned_jobs: the application sequences to be commanded, grouped by application sequence order ;
        - current_jobs: the application sequences being commanded.
    """

    # Annotation types
    ApplicationJobsMap = Dict[str, ApplicationJobs]  # {app_name: app_jobs}
    Plan = Dict[int, ApplicationJobsMap]  # {app_seq: {app_name: app_jobs}}

    PrintableApplicationJobs = Dict[str, ApplicationJobs.PrintablePlannedJobs]
    PrintablePlan = Dict[int, ApplicationJobs.PrintablePlannedJobs]

    def __init__(self, supvisors: Any) -> None:
        """ Initialization of the attributes.

        :param supvisors: the global Supvisors structure.
        """
        # keep a reference of the Supvisors data
        self.supvisors = supvisors
        self.logger = supvisors.logger
        # attributes
        self.planned_jobs: Commander.Plan = {}
        self.current_jobs: Commander.ApplicationJobsMap = {}
        # pickup logic
        self.pickup_logic = None
        # used for Logger so that Starter / Stopper are printed instead of Commander
        self.class_name = type(self).__name__

    # misc methods
    def in_progress(self) -> bool:
        """ Return True if there are still jobs planned or in progress.

        :return: the progress status
        """
        self.logger.trace(f'{self.class_name}.in_progress: planned_jobs={self.planned_jobs}'
                          f' current_jobs={self.current_jobs}')
        return len(self.planned_jobs) > 0 or len(self.current_jobs) > 0

    def get_application_job_names(self) -> Set[str]:
        """ Return all application names involved in the Commander.

        :return: the list of application names
        """
        application_job_names = {app_name for jobs in self.planned_jobs.values() for app_name in jobs}
        application_job_names.update(self.current_jobs.keys())
        return application_job_names

    def get_application_job(self, application_name: str) -> Optional[ApplicationJobs]:
        """ Return the ApplicationJobs corresponding to application_name if in planned_jobs or in current_jobs.

        :param application_name: the application name
        :return: the corresponding ApplicationJobs if found
        """
        # search in current_jobs
        if application_name in self.current_jobs:
            return self.current_jobs[application_name]
        # search in planned_jobs
        return next((application_job for planned_jobs in self.planned_jobs.values()
                     for app_name, application_job in planned_jobs.items()
                     if app_name == application_name), None)

    # command methods
    def abort(self) -> None:
        """ Abort all jobs.

        :return: None
        """
        self.planned_jobs = {}
        self.current_jobs = {}

    # lifecycle methods
    def next(self) -> None:
        """ Triggers the next sequence from the jobs planned (start or stop).

        :return: None
        """
        # check the completion of current ApplicationJobs
        for application_name, application_job in list(self.current_jobs.items()):
            if not application_job.in_progress():
                # nothing more to do for this application
                self.after(application_job)
                del self.current_jobs[application_name]
        # if no more current_jobs, pop lower sequence from planned_jobs and trigger application_jobs
        self.logger.debug(f'{self.class_name}.next: current_jobs={list(self.current_jobs.keys())}')
        if self.planned_jobs and not self.current_jobs:
            # pop next sequence of application jobs
            self.logger.trace(f'Commander.next: planned_jobs={self.planned_jobs}')
            sequence_number = self.pickup_logic(self.planned_jobs)
            self.current_jobs = self.planned_jobs.pop(sequence_number)
            self.logger.debug(f'{self.class_name}.next: sequence={sequence_number}'
                              f' current_jobs={self.current_jobs}')
            # iterate on copy to avoid problems with key deletions
            for application_name, application_job in self.current_jobs.copy().items():
                self.logger.info(f'{self.class_name}.next: start processing {application_name}')
                application_job.before()
                application_job.next()
            # recursive call in the event where there's already nothing left to do
            self.next()
        # update context state and modes
        self.supvisors.context.publish_state_modes({self.class_name.lower(): self.in_progress()})

    # periodic check
    def check(self) -> None:
        """ Periodic check of the progress of the application starting or stopping.

        :return: None
        """
        for application_job in self.current_jobs.values():
            application_job.check()
        # trigger jobs
        self.next()

    # event processing
    def on_event(self, process: ProcessStatus, identifier: str) -> None:
        """ Check the impact of the process event on the jobs in progress.

        :param process: the Supvisors process corresponding to the event
        :param identifier: the identifier of the Supvisors instance that sent the event
        :return: None
        """
        # check impact of event in current_jobs
        application_job = self.current_jobs.get(process.application_name)
        if application_job:
            application_job.on_event(process, identifier)
            # trigger jobs
            self.next()

    def on_instances_invalidation(self, invalidated_identifiers: NameList,
                                  failed_processes: Set[ProcessStatus]) -> None:
        """ Clear the jobs in progress if requests are pending on the Supvisors instances recently declared SILENT.
        Pending requests must be removed from the failed_processes as it has to be considered as a starting failure,
        not a running failure.
        Typically, this may happen only if the processes were STARTING, BACKOFF or STOPPING on the lost Supvisors
        instances. Other states would have removed them from the current_jobs list.

        In the same idea, clear the processes from failed_processes if their starting or stopping is planned.
        An additional automatic behaviour on the same entity may not be suitable or even consistent.
        This case may seem a bit far-fetched but it has already happened actually in a degraded environment:
            - let N1 and N2 be 2 running Supvisors instances ;
            - let P be a process running on N2 ;
            - N2 is lost (let's assume a network congestion, NOT a node crash) so P becomes FATAL ;
            - P is requested to restart on N1 (automatic strategy, user action, etc) ;
            - while P is still in planned jobs, N2 comes back and thus P becomes RUNNING again ;
            - N2 gets lost again. P becomes FATAL again whereas its starting on N1 is still in the pipe.

        :param invalidated_identifiers: the identifiers of the Supvisors instances that have just been declared SILENT
        :param failed_processes: the processes that were running on the invalidated Supvisors instances and thus
        declared in failure
        :return: None
        """
        # clear the invalidated Supvisors instances from the pending requests
        for application_jobs in self.current_jobs.values():
            application_jobs.on_instances_invalidation(invalidated_identifiers, failed_processes)
        # perform some cleaning based on the planned jobs too
        for application_jobs_map in self.planned_jobs.values():
            for application_jobs in application_jobs_map.values():
                application_jobs.on_instances_invalidation(invalidated_identifiers, failed_processes)
        # trigger jobs
        self.next()

    def after(self, application_job: ApplicationJobs) -> None:
        """ Special processing when no more jobs for application.

        :param application_job: the application job wrapper
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

    # command methods
    def start_applications(self, forced: bool) -> None:
        """ This method is called in the DEPLOYMENT phase.
        Plan and start the necessary jobs to start all the applications having a start_sequence.
        It uses the default strategy, as defined in the Supvisors section of the Supervisor configuration file.

        :param forced: a status telling if a full restart is required
        :return: None
        """
        self.logger.debug(f'Starter.start_applications: forced={forced}')
        # internal call: default strategy always used
        for application_name, application in self.supvisors.context.applications.items():
            self.logger.debug(f'Starter.start_applications: {str(application)}'
                              f' start_sequence={application.rules.start_sequence}'
                              f' never_started={application.never_started()}')
            # auto-started applications (start_sequence > 0) are not restarted if they have been stopped intentionally
            # exception is made for applications in failure: give them a chance
            if application.rules.start_sequence > 0 and (forced or application.never_started()
                                                         or application.major_failure or application.minor_failure):
                self.logger.debug(f'Starter.start_applications: starting {application_name} planned')
                self.store_application(application)
        self.logger.debug(f'Starter.start_applications: planned_jobs={self.planned_jobs}')
        # trigger jobs
        self.next()

    def default_start_application(self, application: ApplicationStatus, trigger: bool = True) -> None:
        """ Plan and start the necessary jobs to start the application in parameter, with the default strategy.

        :param application: the application to start
        :param trigger: a status telling if the jobs have to be triggered directly or not
        :return: None
        """
        self.start_application(application.rules.starting_strategy, application, trigger)

    def start_application(self, strategy: StartingStrategies, application: ApplicationStatus,
                          trigger: bool = True) -> None:
        """ Plan and start the necessary jobs to start the application in parameter, with the strategy requested.

        :param strategy: the strategy to be used to start the application.
        :param application: the application to start.
        :param trigger: a status telling if the jobs have to be triggered directly or not.
        :return: None
        """
        self.logger.debug(f'Starter.start_application: application={application.application_name}')
        # push program list in job list and start work
        if application.stopped():
            self.store_application(application, strategy)
            self.logger.debug(f'Starter.start_application: planned_jobs={self.planned_jobs}')
            # trigger may be deferred (as in RunningFailureHandler)
            if trigger:
                self.next()
        else:
            self.logger.warn(f'Starter.start_application: application {application.application_name}'
                             ' already started')

    def store_application(self, application: ApplicationStatus, strategy: StartingStrategies = None) -> bool:
        """ Copy the start sequence considering programs that are meant to be started automatically,
        i.e. their start_sequence is > 0.
        When the strategy is not provided, the application default starting strategy is used.

        :param application: the application to start.
        :param strategy: the strategy to be used to choose the Supvisors instances where processes may be started.
        :return: True if application start sequence added to planned_jobs.
        """
        # use application default starting strategy (application rules) if not provided as parameter
        if strategy is None:
            strategy = application.rules.starting_strategy
        # create the start sequence with processes having a strictly positive start_sequence
        start_sequence = {seq: [ProcessStartCommand(process, strategy) for process in processes]
                          for seq, processes in application.start_sequence.items()
                          if seq > 0}
        if start_sequence:
            priority = application.rules.start_sequence
            sequence = self.planned_jobs.setdefault(priority, {})
            # WARN: if an application is already planned (e.g. through a single process), it will be replaced !
            # create and store the ApplicationJob
            job = ApplicationStartJobs(application, start_sequence, strategy, self.supvisors)
            sequence[application.application_name] = job
            self.logger.debug(f'Starter.store_application: starting of {application.application_name}'
                              f' planned using strategy {strategy.name} with priority={priority}')
            # resolve hash rules if necessary
            application.resolve_rules()
            return True
        self.logger.warn(f'Starter.store_application: {application.application_name} has no valid start_sequence')

    def default_start_process(self, process: ProcessStatus, trigger: bool = True) -> None:
        """ Plan and start the necessary job to start the process in parameter, with the default strategy.
        Default strategy is taken from the application owning this process.

        :param process: the process to start
        :param trigger: a status telling if the jobs have to be triggered directly or not
        :return: None
        """
        application = self.supvisors.context.applications[process.application_name]
        self.start_process(application.rules.starting_strategy, process, trigger=trigger)

    def start_process(self, strategy: StartingStrategies, process: ProcessStatus, extra_args: str = '',
                      trigger: bool = True) -> None:
        """ Plan and start the necessary job to start the process in parameter, with the strategy requested.

        :param strategy: the strategy to be used to start the process
        :param process: the process to start
        :param extra_args: the arguments to be added to the command line
        :param trigger: a status telling if the jobs have to be triggered directly or not
        :return: None
        """
        if process.stopped():
            self.logger.info(f'Starter.start_process: start {process.namespec} using strategy {strategy.name}')
            # create process wrapper
            command = ProcessStartCommand(process, strategy)
            command.extra_args = extra_args
            # WARN: when starting a process outside the application starting scope,
            #       do NOT consider the 'wait_exit' rule
            command.ignore_wait_exit = True
            # create simple sequence for this wrapper
            start_sequence = {process.rules.start_sequence: [command]}
            # a corresponding ApplicationJobs may exist
            job = self.get_application_job(process.application_name)
            if job:
                job.add_commands(start_sequence)
            else:
                application = self.supvisors.context.applications[process.application_name]
                # create and store the ApplicationJobs using the start sequencing defined
                job = ApplicationStartJobs(application, start_sequence, strategy, self.supvisors)
                sequence = self.planned_jobs.setdefault(application.rules.start_sequence, {})
                sequence[process.application_name] = job
            # trigger may be deferred (as in RunningFailureHandler)
            if trigger:
                self.next()

    def after(self, application_job: ApplicationStartJobs) -> None:
        """ Trigger any pending application stop once its starting is completed / aborted properly.

        :param application_job: the application starter
        :return: None
        """
        if application_job.stop_request:
            self.logger.warn(f'Starter.after: apply pending stop application={application_job.application_name}')
            application_job.stop_request = False
            # trigger application stop
            self.supvisors.stopper.stop_application(application_job.application)

    def get_load_requests(self) -> LoadMap:
        """ Get the requested load from all current ApplicationJobs.

        :return: the additional loading per Supvisors instance
        """
        load_requests = [application_job.get_load_requests() for application_job in self.current_jobs.values()]
        # get all identifiers found
        identifiers = {identifier for load_request in load_requests for identifier in load_request}
        # sum the loadings per identifier
        return {identifier: sum(load_request.get(identifier, 0) for load_request in load_requests)
                for identifier in identifiers}


class Stopper(Commander):
    """ Class handling the stopping of processes and applications. """

    # Annotation types
    StartApplicationParameters = Tuple[StartingStrategies, ApplicationStatus]
    StartProcessParameters = Tuple[StartingStrategies, ProcessStatus, str]  # str is for extra args

    def __init__(self, supvisors: Any) -> None:
        """ Initialization of the attributes.

        :param supvisors: the global Supvisors structure.
        """
        super().__init__(supvisors)
        # pick jobs from the planned sequence using the greatest sequence number
        self.pickup_logic = max
        # attributes
        self.application_start_requests: Dict[str, Stopper.StartApplicationParameters] = {}
        self.process_start_requests: Dict[str, List[Stopper.StartProcessParameters]] = {}

    def stop_applications(self) -> None:
        """ Plan and start the necessary jobs to stop all the applications having a stop_sequence.

        :return: None
        """
        self.logger.trace('Stopper.stop_applications')
        # populate stopping jobs for all applications
        for application in self.supvisors.context.applications.values():
            # do not check the application state are running processes may be excluded in the evaluation
            if application.has_running_processes():
                self.logger.info(f'Stopper.stop_applications: stopping {application.application_name}')
                self.store_application(application)
        self.logger.debug(f'Stopper.stop_applications: planned_jobs={self.planned_jobs}')
        # trigger jobs
        self.next()

    def stop_application(self, application: ApplicationStatus, trigger: bool = True) -> None:
        """ Plan and start the necessary jobs to stop the application in parameter.

        :param application: the application to stop
        :param trigger: a status telling if the jobs have to be triggered directly or not
        :return: None
        """
        self.logger.trace('Stopper.stop_application: f{application.application_name}')
        # populate stopping jobs for this application
        if application.has_running_processes():
            self.logger.info(f'Stopper.stop_application: stopping {application.application_name}')
            self.store_application(application)
            self.logger.debug(f'Stopper.stop_application: planned_jobs={self.planned_jobs}')
            # trigger may be deferred (as in RunningFailureHandler)
            if trigger:
                self.next()

    def default_restart_application(self, application: ApplicationStatus, trigger: bool = True) -> None:
        """ Plan and start the necessary jobs to restart the application in parameter, with the default strategy.

        :param application: the application to restart
        :param trigger: a status telling if the jobs have to be triggered directly or not
        :return: None
        """
        self.restart_application(application.rules.starting_strategy, application, trigger)

    def restart_application(self, strategy: StartingStrategies, application: ApplicationStatus,
                            trigger: bool = True) -> None:
        """ Plan and trigger the necessary jobs to restart the application in parameter.
        The application start is deferred until the application has been stopped.

        :param strategy: the strategy used to choose a Supvisors instance
        :param application: the application to restart
        :param trigger: a status telling if the jobs have to be triggered directly or not
        :return: None
        """
        if application.has_running_processes():
            # defer start until fully stopped
            self.application_start_requests[application.application_name] = (strategy, application)
            # trigger stop
            self.stop_application(application, trigger)
        else:
            self.logger.debug(f'Stopper.restart_application: application={application.application_name} already stopped'
                              ' so start it directly')
            self.supvisors.starter.start_application(strategy, application, trigger)

    def stop_process(self, process: ProcessStatus, identifiers: NameList = None, trigger: bool = True) -> None:
        """ Plan and trigger the necessary job to stop the process in parameter.

        :param process: the process to stop
        :param identifiers: the list of Supvisors instances where the process has to be stopped
        :param trigger: a status telling if the jobs have to be triggered directly or not
        :return: None
        """
        self.logger.info(f'Stopper.stop_process: stop {process.namespec}')
        # create process wrappers
        commands = [ProcessStopCommand(process, identifier)
                    for identifier in process.running_identifiers
                    if not identifiers or identifier in identifiers]
        if commands:
            # create simple sequence for this wrapper
            stop_sequence = {process.rules.stop_sequence: commands}
            self.logger.info(f'Stopper.stop_process: stop_sequence={stop_sequence}')
            # a corresponding ApplicationJobs may exist
            job = self.get_application_job(process.application_name)
            if job:
                job.add_commands(stop_sequence)
            else:
                application = self.supvisors.context.applications[process.application_name]
                # create and store the ApplicationJobs using the stop sequencing defined
                job = ApplicationStopJobs(application, stop_sequence, self.supvisors)
                sequence = self.planned_jobs.setdefault(application.rules.stop_sequence, {})
                sequence[process.application_name] = job
            # trigger may be deferred (as in RunningFailureHandler)
            if trigger:
                self.next()

    def default_restart_process(self, process: ProcessStatus, trigger: bool = True) -> None:
        """ Plan and start the necessary job to restart the process in parameter, with the default strategy.
        Default strategy is taken from the application owning this process.

        :param process: the process to start
        :param trigger: a status telling if the jobs have to be triggered directly or not
        :return: None
        """
        application = self.supvisors.context.applications[process.application_name]
        self.restart_process(application.rules.starting_strategy, process, trigger=trigger)

    def restart_process(self, strategy: StartingStrategies, process: ProcessStatus, extra_args: str = '',
                        trigger: bool = True) -> None:
        """ Plan and trigger the necessary jobs to restart the process in parameter.
        The process start is deferred until the process has been stopped.
        The method should return False, unless the process is already stopped and no Supvisors instance was found
        to start it.

        :param strategy: the strategy used to choose a Supvisors instance
        :param process: the process to restart
        :param extra_args: extra arguments to be passed to the command line
        :param trigger: a status telling if the jobs have to be triggered directly or not
        :return: None
        """
        if process.running():
            # defer start until fully stopped
            process_list = self.process_start_requests.setdefault(process.application_name, [])
            process_list.append((strategy, process, extra_args))
            # trigger stop on all involved Supvisors instances
            self.stop_process(process, trigger=trigger)
        else:
            self.logger.debug(f'Stopper.restart_process: process={process.namespec} already stopped'
                              ' so start it directly')
            self.supvisors.starter.start_process(strategy, process, extra_args, trigger)

    def store_application(self, application: ApplicationStatus) -> None:
        """ Schedules the application processes to stop.
        This will replace any existing sequence if any.

        :param application: the application to stop
        :return: None
        """
        stop_sequence = {}
        for seq, processes in application.stop_sequence.items():
            command_list = [ProcessStopCommand(process, identifier)
                            for process in processes
                            for identifier in process.running_identifiers]
            if command_list:
                stop_sequence[seq] = command_list
        if stop_sequence:
            priority = application.rules.stop_sequence
            sequence = self.planned_jobs.setdefault(priority, {})
            # create and store the ApplicationJob
            job = ApplicationStopJobs(application, stop_sequence, self.supvisors)
            sequence[application.application_name] = job
            self.logger.debug(f'Stopper.store_application: stopping of {application.application_name}'
                              f' planned with priority={priority}')

    def after(self, application_job: ApplicationStopJobs) -> None:
        """ Once an application has been properly stopped, unset the application start failure.
        Trigger any pending application / process start once all stopper jobs are completed.

        :param application_job: the application stopper
        :return: None
        """
        # trigger pending application start requests
        appli_parameters = self.application_start_requests.pop(application_job.application_name, None)
        if appli_parameters:
            strategy, application = appli_parameters
            self.logger.debug(f'Stopper.after: apply pending start application={application.application_name}')
            self.supvisors.starter.start_application(strategy, application)
        # trigger pending process start requests
        process_list = self.process_start_requests.pop(application_job.application_name, None)
        if process_list:
            for strategy, process, extra_args in process_list:
                self.logger.debug(f'Stopper.after: apply pending start process={process.namespec}')
                self.supvisors.starter.start_process(strategy, process, extra_args)
