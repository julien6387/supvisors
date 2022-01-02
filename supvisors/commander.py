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

from typing import Any, Dict, List, Optional, Set, Tuple

from supervisor.childutils import get_asctime
from supervisor.loggers import Logger
from supervisor.states import ProcessStates, getProcessStateDescription, STOPPED_STATES

from .application import ApplicationStatus
from .process import ProcessStatus
from .strategy import get_supvisors_instance, LoadRequestMap
from .ttypes import NameList, Payload, StartingStrategies, StartingFailureStrategies


class ProcessCommand(object):
    """ Wrapper of the process to include data only used here.

    Attributes are:
        - process: the process wrapped ;
        - identifiers: the identifiers of the Supvisors instances where the commands are requested ;
        - request_time: the date when the command is requested.
    """
    TIMEOUT = 3

    def __init__(self, process: ProcessStatus) -> None:
        """ Initialization of the attributes.

        :param process: the process status to wrap
        """
        self.process: ProcessStatus = process
        self.logger: Logger = process.logger
        self.identifiers: NameList = []
        self.request_time: int = 0

    def __str__(self) -> str:
        """ Get the process command as string.

        :return: the printable process command
        """
        return (f'process={self.process.namespec} state={self.process.state}'
                f' identifiers={self.identifiers} request_time={self.request_time}')

    def __repr__(self) -> str:
        """ Get the process command as string.

        :return: the representation of a process command
        """
        return self.process.namespec

    def timed_out(self, now: float) -> bool:
        """ Return True if the request has not been acknowledged in a reasonable time.

        :param now: the current time
        :return: the timeout status
        """
        raise NotImplementedError


class ProcessStartCommand(ProcessCommand):
    """ Wrapper of the process to be started.

    Additional attributes are:
        - strategy: the strategy used to start the process if applicable,
        - distributed: set to False if the process belongs to an application that cannot be distributed,
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
        return super().__str__() + (f' strategy={self.strategy.name} ignore_wait_exit={self.ignore_wait_exit}'
                                    f' extra_args="{self.extra_args}"')

    def timed_out(self, now: float) -> bool:
        """ Return True if the request has not been acknowledged in a reasonable time.

        :param now: the current time
        :return: the timeout status
        """
        # actually, only one identifier in self.identifiers
        for identifier in self.identifiers:
            # check the process state on the targeted Supvisors instance
            local_info = self.process.info_map[identifier]
            local_state = local_info['state']
            if local_state in [ProcessStates.BACKOFF, ProcessStates.STARTING]:
                # the RUNNING state is expected after startsecs seconds
                delay = local_info['startsecs'] + ProcessCommand.TIMEOUT
                if self.request_time + delay < now:
                    self.logger.error(f'ProcessStartCommand.timed_out: {self.process.namespec}'
                                      f' still not RUNNING after {delay} seconds so abort')
                    return True
            elif local_state == ProcessStates.RUNNING:
                # if the evaluation is done in this state, the EXITED state must be expected
                # this is a risk for the Supvisors Starter lifecycle but wait forever
                pass
            else:
                # from STOPPED_STATES, STARTING or BACKOFF event is expected quite immediately
                # a STOPPING state is unexpected unless an external request has been performed (e.g. stop request while
                # in STARTING state)
                if self.request_time + ProcessCommand.TIMEOUT < now:
                    self.logger.error(f'ProcessStartCommand.timed_out: {self.process.namespec}'
                                      f' still not STARTING or BACKOFF after {ProcessCommand.TIMEOUT} seconds so abort')
                    return True
        return False


class ProcessStopCommand(ProcessCommand):
    """ Wrapper of the process to be started.

    Attributes are:
        - strategy: the strategy used to start the process if applicable,
        - distributed: set to False if the process belongs to an application that cannot be distributed,
        - ignore_wait_exit: used to command a process out of its application starting sequence,
        - extra_args: additional arguments to the command line.
    """

    def timed_out(self, now: float) -> bool:
        """ Return True if the request has not been acknowledged in a reasonable time.

        :param now: the current time
        :return: the timeout status
        """
        # multiple identifiers are possible
        for identifier in self.identifiers:
            # check the process state on the targeted Supvisors instance
            local_info = self.process.info_map[identifier]
            local_state = local_info['state']
            if local_state == ProcessStates.STOPPING:
                # the STOPPED state is expected after stopwaitsecs seconds
                delay = local_info['stopwaitsecs'] + ProcessCommand.TIMEOUT
                if self.request_time + delay < now:
                    self.logger.error(f'ProcessStopCommand.timed_out: {self.process.namespec}'
                                      f' still not STOPPED after {delay} seconds so abort')
                    return True
            else:
                # from RUNNING_STATES, STOPPING event is expected quite immediately
                # STOPPED_STATES are unexpected because this wrapper would have been removed
                if self.request_time + ProcessCommand.TIMEOUT < now:
                    self.logger.error(f'ProcessStopCommand.timed_out: {self.process.namespec}'
                                      f' still not STOPPING after {ProcessCommand.TIMEOUT} seconds so abort')
                    return True
        return False


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
                     if ((not identifier or identifier in command.identifiers)
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

    def add_command(self, jobs: PlannedJobs) -> None:
        """ Add a process wrapper to the application jobs, if possible.
        PlannedJobs structure is used but only one element is expected.

        :param jobs: the sequenced process wrapper
        :return: True if added to planned_jobs
        """
        # search for this command in existing lists
        sequence_number, command_list = next(iter(jobs.items()))
        command = next(iter(command_list))
        current_job = self.get_current_command(command.process.process_name)
        planned_job = self.get_planned_command(command.process.process_name)
        if current_job or planned_job:
            # not relevant to consider a process already considered
            self.logger.warn(f'ApplicationJobs.add_command: {command.process.namespec} already planned')
        else:
            # add the command to planned_jobs
            self.logger.debug(f'ApplicationJobs.add_command: {command.process.namespec} planned')
            self.planned_jobs.setdefault(sequence_number, []).append(command)

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
        now = time.time()
        self.logger.trace(f'Commander.check: now={now:.2f} checking commands={self.current_jobs}')
        for command in list(self.current_jobs):
            # get the ProcessStatus method corresponding to condition and call it
            if command.timed_out(now):
                # generate a process event for this process to inform all Supvisors instances
                reason = f'no process event received in time'
                self.supvisors.listener.force_process_state(command.process.namespec, self.failure_state, reason)
                # don't wait for event, abort the job right now
                self.current_jobs.remove(command)
        # trigger jobs
        self.next()

    # event methods
    def on_event(self, process: ProcessStatus, identifier: str, event: Payload) -> None:
        """ Check the impact of the process event on the jobs in progress.

        :param process: the Supvisors process corresponding to the event
        :param identifier: the identifier of the Supvisors instance that sent the event
        :param event: the event payload
        :return: None
        """
        self.logger.debug(f'ApplicationJobs.on_event: process={process.namespec} event={event}'
                          f' from Supvisors={identifier}')
        # first check if event is in the sequence logic, i.e. it corresponds to a process in current jobs
        command = self.get_current_command(process.process_name, identifier)
        if command:
            self.on_event_in_sequence(command, identifier, event)
        else:
            self.logger.debug(f'ApplicationJobs.on_event: event {event} from Supvisors={identifier} does not match'
                              ' with the current sequence')
            # Various cases may lead to that situation:
            #   * the process has crashed / exited after its RUNNING state but before the application is fully started
            #     => let the running failure strategy deal with that
            #   * the process is not in the automatic application sequence (so the event is related to a manual request)
            #     => just ignore

    def on_event_in_sequence(self, command: ProcessCommand, identifier: str, event: Payload) -> None:
        """ Check the impact of the process event on the jobs in progress.

        :param command: the process wrapper used in the jobs
        :param identifier: the identifier of the Supvisors instance that sent the event
        :param event: the process event received
        :return: None
        """
        raise NotImplementedError

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
            # rebuild identifiers
            command.identifiers = [identifier for identifier in command.identifiers
                                   if identifier not in invalidated_identifiers]
            # if no more pending request, declare a starting failure on the process
            # and remove the process from failed_processes as this is a starting failure, not a running failure
            if not command.identifiers:
                self.current_jobs.remove(command)
                self.process_failure(command.process)
                failed_processes.remove(command.process)
        # don't trigger an automatic behaviour on processes in failure when jobs are already planned
        for command in sum(self.planned_jobs.values(), []):
            if command.process in failed_processes:
                failed_processes.remove(command.process)
        # no need to trigger jobs
        # this method is already triggered by the upper periodic check that will call self.next() anyway

    def get_load_requests(self) -> LoadRequestMap:
        """ Extract by identifier of Supvisors instance the processes that are planned to start but still stopped
        and sum their expected load. Only applicable to ApplicationStartJobs.

        :return: the additional loading per Supvisors instance
        """


class ApplicationStartJobs(ApplicationJobs):
    """ Specialization of ApplicationJobs to start applications. """

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
        self.distributed: bool = self.application.rules.distributed
        self.identifier: Optional[str] = None  # only set for a non-distributed application
        # flags for use at Starter level
        self.stop_request: bool = False

    # miscellaneous methods
    def add_command(self, jobs: ApplicationJobs.PlannedJobs) -> None:
        """ Add a process wrapper to the application jobs, if possible.
        If the wrapper has been planned in the superclass and in the case of a non-distributed application, check that
        the process added can be started on the same Supvisors instance than the others.

        :param jobs: the sequenced process wrapper
        :return: None
        """
        super().add_command(jobs)
        # whatever the job has been really added to planned_jobs or not, it must apply the same Supvisors instance
        # as the other commands of a non-distributed application
        command = next(iter(jobs.values()))[0]
        if not self.distributed and self.identifier and not command.identifiers:
            # self.identifier may be None (no Supvisors instance found)
            # identifiers may be already set (command was already there)
            load = command.process.rules.expected_load
            # check that the chosen Supvisors instance can support the new process
            # in a non-distributed application, the application starting_strategy applies
            identifier = get_supvisors_instance(self.supvisors, self.starting_strategy, [self.identifier], load)
            if identifier:
                command.identifiers.append(identifier)
            else:
                self.logger.info(f'ApplicationStartJobs.add_command: {command.process.namespec} cannot be started'
                                 f' on the chosen Supvisors={self.identifier}')

    def get_load_requests(self) -> LoadRequestMap:
        """ Extract by Supvisors instance the processes that are planned to start but still stopped
        and sum their expected load.

        :return: the additional loading per Supvisors instance
        """
        load_request_map = {}
        # sum the loading of all jobs having a targeted Supvisors instance and whose process is not fully started yet
        for command in self.current_jobs + sum(self.planned_jobs.values(), []):
            # if process is not stopped, its loading is already considered through SupvisorsInstanceStatus
            if command.process.stopped() and command.identifiers:
                identifier = command.identifiers[0]
                load_request_map.setdefault(identifier, []).append(command.process.rules.expected_load)
        return {identifier: sum(load_list) for identifier, load_list in load_request_map.items()}

    # lifecycle methods
    def before(self) -> None:
        """ Prepare the ProcessStartCommand linked to the planned jobs.
        More particularly, in the case of a non-distributed application, the Supvisors instance must be found
        at this stage, considering the load of the whole application at once.

        :return: None
        """
        # FIXME: what if any process of a non-distributed application is already running ?
        #  is it a new case of CONCILIATION ?
        if not self.distributed:
            # get all ProcessStartCommand of the application
            commands = [process for sequence in self.planned_jobs.values()
                        for process in sequence]
            # find the Supvisors instance iaw strategy
            load = self.application.get_start_sequence_expected_load()
            self.identifier = get_supvisors_instance(self.supvisors, self.starting_strategy,
                                                     self.application.possible_identifiers(), load)
            self.logger.info(f'ApplicationStartJobs.before: identifier={self.identifier} assigned to non-distributed'
                             f' application_name={self.application_name} using strategy={self.starting_strategy.name}')
            # apply the identifier to all commands
            if self.identifier:
                for command in commands:
                    command.identifiers.append(self.identifier)

    def process_job(self, command: ProcessStartCommand) -> bool:
        """ Start the process on the relevant Supvisors instance.

        :param command: the wrapper of the process to start
        :return: True if a job has been queued.
        """
        queued = False
        process = command.process
        self.logger.debug(f'ApplicationStartJobs.process_job: process={process.namespec} stopped={process.stopped()}')
        if process.stopped():
            # identifier has already been decided for a non-distributed application
            if self.distributed:
                # find Supvisors instance iaw strategy
                identifier = get_supvisors_instance(self.supvisors, command.strategy, process.possible_identifiers(),
                                                    process.rules.expected_load)
                self.logger.debug(f'ApplicationStartJobs.process_job: found Supvisors={identifier} to start'
                                  f' process={process.namespec} with strategy={command.strategy.name}')
                if identifier:
                    command.identifiers.append(identifier)
            if command.identifiers:
                # in Starter, only one identifier in identifiers
                identifier = command.identifiers[0]
                # use asynchronous xml rpc to start program
                self.supvisors.zmq.pusher.send_start_process(identifier, process.namespec, command.extra_args)
                command.request_time = time.time()
                self.logger.info(f'ApplicationStartJobs.process_job: {process.namespec} requested to start'
                                 f' on {identifier} at {get_asctime(command.request_time)}')
                queued = True
            else:
                self.logger.warn(f'ApplicationStartJobs.process_job: no resource available for {process.namespec}')
                self.supvisors.listener.force_process_state(process.namespec, ProcessStates.FATAL,
                                                            'no resource available')
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
            self.logger.warn(f'ApplicationStartJobs.process_failure: starting failed for required {process.namespec}')
            # get starting failure strategy of related application
            failure_strategy = self.application.rules.starting_failure_strategy
            # apply strategy
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
            self.logger.warn(f'ApplicationStartJobs.process_failure: starting failed for optional {process.namespec}')
            self.logger.info(f'ApplicationStartJobs.process_failure: continue starting {process.application_name}')

    # event methods
    def on_event_in_sequence(self, command: ProcessStartCommand, identifier: str, event: Payload) -> None:
        """ Manages the impact of an event that is part of the starting sequence.

        :param command: the process wrapper used in the jobs
        :param identifier: the identifier of the Supvisors instance that sent the event (not used)
        :param event: the process event received
        :return: None
        """
        process = command.process
        process_state, expected_exit = event['state'], event['expected']
        if process_state in (ProcessStates.STOPPED, ProcessStates.STOPPING, ProcessStates.UNKNOWN):
            # STOPPED should be impossible as it wouldn't be compliant to ProcessStates transitions logic
            # STOPPING would mean that someone has requested to stop the process as it is starting
            # UNKNOWN is unlikely as it corresponds to an internal supervisord error
            self.logger.error(f'ApplicationStartJobs.on_event_in_sequence:'
                              f' unexpected event={getProcessStateDescription(process_state)}'
                              f' while starting {process.namespec}')
            self.current_jobs.remove(command)
            self.process_failure(process)
        elif process_state == ProcessStates.STARTING:
            # all right, on the way
            pass
        elif process_state == ProcessStates.RUNNING:
            # if no exit is expected, the job is done. otherwise, wait
            if not process.rules.wait_exit or command.ignore_wait_exit:
                self.current_jobs.remove(command)
        elif process_state == ProcessStates.BACKOFF:
            # something wrong happened, reset request_time to consider new timeout
            self.logger.debug(f'ApplicationStartJobs.on_event_in_sequence: reset request_time on {process.namespec}')
            command.request_time = time.time()
        elif process_state == ProcessStates.EXITED:
            # remove from current_jobs
            self.current_jobs.remove(command)
            # an EXITED process is accepted if wait_exit is set
            if process.rules.wait_exit and expected_exit:
                self.logger.info(f'ApplicationStartJobs.on_event_in_sequence: expected exit for {process.namespec}')
            else:
                self.process_failure(process)
        elif process_state == ProcessStates.FATAL:
            # remove from current_jobs and decide to continue starting or not
            self.current_jobs.remove(command)
            self.process_failure(process)
        # almost all events require to trigger jobs
        self.next()


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
        if process.running():
            # use asynchronous xml rpc to stop program
            for identifier in process.running_identifiers:
                self.logger.info(f'ApplicationStopJobs.process_job: stopping {process.namespec} on {identifier}')
                self.supvisors.zmq.pusher.send_stop_process(identifier, process.namespec)
                command.identifiers.append(identifier)
            # push to jobs and timestamp process
            command.request_time = time.time()
            self.logger.debug(f'ApplicationStopJobs.process_job: {process.namespec} requested to stop'
                              f' at {get_asctime(command.request_time)}')
            return True

    # event methods
    def on_event_in_sequence(self, command: ProcessCommand, identifier: str, event: Payload) -> None:
        """ Manages the impact of an event that is part of the stopping sequence.

        :param command: the process wrapper used in the jobs
        :param identifier: the identifier of the Supvisors instance that sent the event
        :param event: the process event received (not used)
        :return: None
        """
        process_state = event['state']
        # check if process event has an impact on stopping in progress
        if process_state in STOPPED_STATES:
            # goal reached, whatever the state
            command.identifiers.remove(identifier)
            if not command.identifiers:
                self.current_jobs.remove(command)
                # trigger jobs
                self.next()
        # STOPPING: all right, on the way
        # RUNNING_STATES: should be impossible as it wouldn't be compliant to ProcessStates transitions logic


class Commander(object):
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
        self.klass = type(self).__name__

    # misc methods
    def in_progress(self) -> bool:
        """ Return True if there are still jobs planned or in progress.

        :return: the progress status
        """
        self.logger.trace(f'{self.klass}.in_progress: planned_jobs={self.planned_jobs}'
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
        self.logger.debug(f'{self.klass}.next: current_jobs={list(self.current_jobs.keys())}')
        if self.planned_jobs and not self.current_jobs:
            # pop next sequence of application jobs
            self.logger.trace(f'Commander.next: planned_jobs={self.planned_jobs}')
            sequence_number = self.pickup_logic(self.planned_jobs)
            self.current_jobs = self.planned_jobs.pop(sequence_number)
            self.logger.debug(f'{self.klass}.next: sequence={sequence_number}'
                              f' current_jobs={self.current_jobs}')
            # iterate on copy to avoid problems with key deletions
            for application_name, application_job in self.current_jobs.items():
                self.logger.info(f'{self.klass}.next: start processing {application_name}')
                application_job.before()
                application_job.next()
            # recursive call in the event where there's already nothing left to do
            self.next()

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
    def on_event(self, process: ProcessStatus, identifier: str, event: Payload) -> None:
        """ Check the impact of the process event on the jobs in progress.

        :param process: the Supvisors process corresponding to the event
        :param identifier: the identifier of the Supvisors instance that sent the event
        :param event: the event payload
        :return: None
        """
        # check impact of event in current_jobs
        application_job = self.current_jobs.get(process.application_name)
        if application_job:
            application_job.on_event(process, identifier, event)
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

    def default_start_application(self, application: ApplicationStatus) -> None:
        """ Plan and start the necessary jobs to start the application in parameter, with the default strategy.

        :param application: the application to start
        :return: None
        """
        self.start_application(application.rules.starting_strategy, application)

    def start_application(self, strategy: StartingStrategies, application: ApplicationStatus) -> None:
        """ Plan and start the necessary jobs to start the application in parameter, with the strategy requested.

        :param strategy: the strategy to be used to start the application
        :param application: the application to start
        :return: None
        """
        self.logger.debug(f'Starter.start_application: application={application.application_name}')
        # push program list in job list and start work
        if application.stopped():
            self.store_application(application, strategy)
            self.logger.debug(f'Starter.start_application: planned_jobs={self.planned_jobs}')
            self.next()
        else:
            self.logger.warn(f'Starter.start_application: application {application.application_name}'
                             ' already started')

    def store_application(self, application: ApplicationStatus, strategy: StartingStrategies = None) -> bool:
        """ Copy the start sequence considering programs that are meant to be started automatically,
        i.e. their start_sequence is > 0.
        When the strategy is not provided, the application default starting strategy is used.

        :param application: the application to start
        :param strategy: the strategy to be used to choose the Supvisors instances where processes may be started
        :return: True if application start sequence added to planned_jobs
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
            return True
        self.logger.warn(f'Starter.store_application: {application.application_name} has no valid start_sequence')

    def default_start_process(self, process: ProcessStatus) -> None:
        """ Plan and start the necessary job to start the process in parameter, with the default strategy.
        Default strategy is taken from the application owning this process.

        :param process: the process to start
        :return: None
        """
        application = self.supvisors.context.applications[process.application_name]
        self.start_process(application.rules.starting_strategy, process)

    def start_process(self, strategy: StartingStrategies, process: ProcessStatus, extra_args: str = '') -> None:
        """ Plan and start the necessary job to start the process in parameter, with the strategy requested.

        :param strategy: the strategy to be used to start the process
        :param process: the process to start
        :param extra_args: the arguments to be added to the command line
        :return: None
        """
        if process.stopped():
            self.logger.info(f'Starter.start_process: start {process.namespec} using strategy {strategy.name}')
            # create process wrapper
            command = ProcessStartCommand(process, strategy)
            command.extra_args = extra_args
            # WARN: when starting a process outside of the application starting scope,
            #       do NOT consider the 'wait_exit' rule
            command.ignore_wait_exit = True
            # create simple sequence for this wrapper
            start_sequence = {process.rules.start_sequence: [command]}
            # a corresponding ApplicationJobs may exist
            job = self.get_application_job(process.application_name)
            if job:
                job.add_command(start_sequence)
            else:
                application = self.supvisors.context.applications[process.application_name]
                # create and store the ApplicationJobs using the start sequencing defined
                job = ApplicationStartJobs(application, start_sequence, strategy, self.supvisors)
                sequence = self.planned_jobs.setdefault(application.rules.start_sequence, {})
                sequence[process.application_name] = job
            # trigger jobs
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

    def get_load_requests(self) -> LoadRequestMap:
        """ Get the requested load from all current ApplicationJobs.
        TODO: check if should be grouped by host name rather than by Supvisors identifier

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

    def stop_application(self, application: ApplicationStatus) -> None:
        """ Plan and start the necessary jobs to stop the application in parameter.

        :param application: the application to stop
        :return: None
        """
        self.logger.trace('Stopper.stop_application: f{application.application_name}')
        # populate stopping jobs for this application
        if application.has_running_processes():
            self.logger.info(f'Stopper.stop_application: stopping {application.application_name}')
            self.store_application(application)
            self.logger.debug(f'Stopper.stop_application: planned_jobs={self.planned_jobs}')
            # trigger jobs
            self.next()

    def restart_application(self, strategy: StartingStrategies, application: ApplicationStatus) -> None:
        """ Plan and trigger the necessary jobs to restart the application in parameter.
        The application start is deferred until the application has been stopped.

        :param strategy: the strategy used to choose a Supvisors instance
        :param application: the application to restart
        :return: None
        """
        # application is stopping. defer start until fully stopped
        self.application_start_requests[application.application_name] = (strategy, application)
        # trigger stop
        self.stop_application(application)

    def stop_process(self, process: ProcessStatus) -> None:
        """ Plan and trigger the necessary job to stop the process in parameter.

        :param process: the process to stop
        :return: None
        """
        if process.running():
            self.logger.info(f'Starter.stop_process: stop {process.namespec}')
            # create process wrapper
            command = ProcessStopCommand(process)
            # create simple sequence for this wrapper
            stop_sequence = {process.rules.stop_sequence: [command]}
            # a corresponding ApplicationJobs may exist
            job = self.get_application_job(process.application_name)
            if job:
                job.add_command(stop_sequence)
            else:
                application = self.supvisors.context.applications[process.application_name]
                # create and store the ApplicationJobs using the stop sequencing defined
                job = ApplicationStopJobs(application, stop_sequence, self.supvisors)
                sequence = self.planned_jobs.setdefault(application.rules.stop_sequence, {})
                sequence[process.application_name] = job
            # trigger jobs
            self.next()

    def restart_process(self, strategy: StartingStrategies, process: ProcessStatus, extra_args: str) -> None:
        """ Plan and trigger the necessary jobs to restart the process in parameter.
        The process start is deferred until the process has been stopped.
        The method should return False, unless the process is already stopped and no Supvisors instance was found
        to start it.

        :param strategy: the strategy used to choose a Supvisors instance
        :param process: the process to restart
        :param extra_args: extra arguments to be passed to the command line
        :return: None
        """
        # defer start until fully stopped
        process_list = self.process_start_requests.setdefault(process.application_name, [])
        process_list.append((strategy, process, extra_args))
        # trigger stop
        self.stop_process(process)

    def store_application(self, application: ApplicationStatus) -> None:
        """ Schedules the application processes to stop.
        This will replace any existing sequence if any.

        :param application: the application to stop
        :return: None
        """
        stop_sequence = {seq: [ProcessStopCommand(process) for process in processes]
                         for seq, processes in application.stop_sequence.items()}
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
