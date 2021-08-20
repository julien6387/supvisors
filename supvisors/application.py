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

from typing import Any, Dict, List, Sequence

from supervisor.loggers import Logger
from supervisor.states import ProcessStates

from .process import ProcessStatus
from .ttypes import (ApplicationStates, NameList, Payload, StartingStrategies,
                     StartingFailureStrategies, RunningFailureStrategies)


class ApplicationRules(object):
    """ Definition of the rules for starting an application, iaw rules file.

    Attributes are:
        - managed: set to True when application rules are found from the rules file;
        - distributed: set to False if all processes must be running on the same node;
        - node_names: the nodes where the application can be started (all by default) if not distributed,
        - start_sequence: defines the order of this application when starting all the applications
          in the DEPLOYMENT state (0 means: no automatic start);
        - stop_sequence: defines the order of this application when stopping all the applications
          (0 means: immediate stop);
        - starting_strategy: defines the strategy to apply when choosing the node where the process shall be started
          during the starting of the application;
        - starting_failure_strategy: defines the strategy to apply when a required process cannot be started
          during the starting of the application;
        - running_failure_strategy: defines the default strategy to apply when a required process crashes
          when the application is running.
    """

    def __init__(self) -> None:
        """ Initialization of the attributes. """
        self.managed: bool = False
        self.distributed: bool = True
        self.node_names: NameList = ['*']
        self.start_sequence: int = 0
        self.stop_sequence: int = 0
        self.starting_strategy: StartingStrategies = StartingStrategies.CONFIG
        self.starting_failure_strategy: StartingFailureStrategies = StartingFailureStrategies.ABORT
        self.running_failure_strategy: RunningFailureStrategies = RunningFailureStrategies.CONTINUE

    def __str__(self) -> str:
        """ Get the application rules as string.

        :return: the printable application rules
        """
        return 'managed={} distributed={} node_names={} start_sequence={} stop_sequence={} starting_strategy={}'\
               ' starting_failure_strategy={} running_failure_strategy={}' \
            .format(self.managed, self.distributed, self.node_names, self.start_sequence, self.stop_sequence,
                    self.starting_strategy.name, self.starting_failure_strategy.name,
                    self.running_failure_strategy.name)

    # serialization
    def serial(self) -> Payload:
        """ Get a serializable form of the application rules.
        Do not send not applicable information.

        :return: the application rules in a dictionary
        """
        if self.managed:
            payload = {'managed': True, 'distributed': self.distributed,
                       'start_sequence': self.start_sequence, 'stop_sequence': self.stop_sequence,
                       'starting_strategy': self.starting_strategy.name,
                       'starting_failure_strategy': self.starting_failure_strategy.name,
                       'running_failure_strategy': self.running_failure_strategy.name}
            if not self.distributed:
                payload['addresses'] = self.node_names
            return payload
        return {'managed': False}


class ApplicationStatus(object):
    """ Class defining the status of an application in Supvisors.

    Attributes are:
        - application_name: the name of the application, corresponding to the Supervisor group name,
        - state: the state of the application in ApplicationStates,
        - major_failure: a status telling if a required process is stopped while the application is running,
        - minor_failure: a status telling if an optional process has crashed while the application is running,
        - processes: the map (key is process name) of the ProcessStatus belonging to the application,
        - rules: the ApplicationRules instance applicable to the application,
        - start_sequence: the sequencing to start the processes belonging to the application, as a dictionary.
        - stop_sequence: the sequencing to stop the processes belonging to the application, as a dictionary.

    For start and stop sequences, each entry is a list of processes having the same sequence order, used as key.
    """

    # types for annotations
    ProcessList = List[ProcessStatus]
    ApplicationSequence = Dict[int, ProcessList]
    PrintableApplicationSequence = Dict[int, Sequence[str]]
    ProcessMap = Dict[str, ProcessStatus]

    def __init__(self, application_name: str, rules: ApplicationRules, supvisors: Any) -> None:
        """ Initialization of the attributes.

        :param application_name: the name of the application
        :param rules: the rules applicable to the application
        :param supvisors: the global Supvisors structure
        """
        # keep reference to common logger
        self.supvisors = supvisors
        self.logger: Logger = supvisors.logger
        # information part
        self.application_name: str = application_name
        self._state: ApplicationStates = ApplicationStates.STOPPED
        self.major_failure: bool = False
        self.minor_failure: bool = False
        # process part
        self.processes: ApplicationStatus.ProcessMap = {}
        self.rules: ApplicationRules = rules
        self.start_sequence: ApplicationStatus.ApplicationSequence = {}
        self.stop_sequence: ApplicationStatus.ApplicationSequence = {}

    # access
    def running(self) -> bool:
        """ Return True if the application is running.

        :return: the running status of the application
        """
        return self.state in [ApplicationStates.STARTING, ApplicationStates.RUNNING]

    def stopped(self) -> bool:
        """ Return True if the application is stopped.

        :return: the stopped status of the application
        """
        return self.state == ApplicationStates.STOPPED

    def never_started(self) -> bool:
        """ Return True if the application has never been started.

        :return: True if the processes of the application have never been started
        """
        return all(info['state'] == ProcessStates.STOPPED and info['stop'] == 0
                   for proc in self.processes.values()
                   for info in proc.info_map.values())

    @property
    def state(self) -> ApplicationStates:
        """ Getter of state attribute.

         :return: the application state
         """
        return self._state

    @state.setter
    def state(self, new_state: ApplicationStates) -> None:
        """ Setter of state attribute.

        :param new_state: the new application state
        :return: None
        """
        if self._state != new_state:
            self._state = new_state
            self.logger.info('Application.state: {} is {}'.format(self.application_name, self.state.name))

    def has_running_processes(self) -> bool:
        """ Check if one of the application processes is running.
        The application state may be STOPPED in this case if the running process is out of the starting sequence.

        :return: True if one of the application processes is running
        """
        for process in self.processes.values():
            if process.running():
                return True

    def get_operational_status(self) -> str:
        """ Get a description of the operational status of the application.

        :return: the operational status as string
        """
        if self.state == ApplicationStates.RUNNING:
            if self.major_failure:
                return 'Not Operational'
            if self.minor_failure:
                return 'Degraded'
            return 'Operational'
        return ''

    # serialization
    def serial(self) -> Payload:
        """ Get a serializable form of the application status.

        :return: the application status in a dictionary
        """
        return {'application_name': self.application_name,
                'statecode': self.state.value,
                'statename': self.state.name,
                'major_failure': self.major_failure,
                'minor_failure': self.minor_failure}

    def __str__(self) -> str:
        """ Get the application status as string.

        :return: the printable application status
        """
        return 'application_name={} state={} major_failure={} minor_failure={}' \
            .format(self.application_name, self.state.name, self.major_failure, self.minor_failure)

    # methods
    def add_process(self, process: ProcessStatus) -> None:
        """ Add a new process to the process list.

        :param process: the process status to be added to the application
        :return: None
        """
        self.processes[process.process_name] = process

    def possible_nodes(self) -> NameList:
        """ Return the list of nodes where the application could be started.
        To achieve that, two conditions:
            - the Supervisor node must know all the application programs;
            - the node must be declared in the applicable nodes in the rules file.

        :return: the list of nodes where the program could be started
        """
        node_names = self.rules.node_names
        if '*' in self.rules.node_names:
            node_names = self.supvisors.address_mapper.node_names
        # get the nodes common to all application processes
        actual_nodes = [set(process.info_map.keys()) for process in self.processes.values()]
        if actual_nodes:
            actual_nodes = actual_nodes[0].intersection(*actual_nodes)
        # intersect with rules
        return [node_name for node_name in node_names if node_name in actual_nodes]

    @staticmethod
    def printable_sequence(application_sequence: ApplicationSequence) -> PrintableApplicationSequence:
        """ Get printable application sequence for log traces.
        Only the name of the process is kept.

        :return: the simplified sequence
        """
        return {seq: [proc.process_name for proc in proc_list]
                for seq, proc_list in application_sequence.items()}

    def update_sequences(self) -> None:
        """ Evaluate the sequencing of the starting / stopping application from its list of processes.
        This makes sense only for managed applications.

        :return: None
        """
        self.start_sequence.clear()
        self.stop_sequence.clear()
        # consider only managed applications for start sequence
        if self.rules.managed:
            # fill ordering iaw process rules
            for process in self.processes.values():
                self.start_sequence.setdefault(process.rules.start_sequence, []).append(process)
            self.logger.debug('ApplicationStatus.update_sequences: application_name={} start_sequence={}'
                              .format(self.application_name, self.printable_sequence(self.start_sequence)))
        else:
            self.logger.info('ApplicationStatus.update_sequences: application_name={}'
                             ' is not managed so start sequence is undefined'. format(self.application_name))
        # stop sequence is applicable to all applications
        for process in self.processes.values():
            # fill ordering iaw process rules
            self.stop_sequence.setdefault(process.rules.stop_sequence, []).append(process)
        self.logger.debug('ApplicationStatus.update_sequences: application_name={} stop_sequence={}'
                          .format(self.application_name, self.printable_sequence(self.stop_sequence)))

    def get_start_sequenced_processes(self) -> ProcessList:
        """ Return the processes included in the application start sequence.
        The sequence 0 is removed as it corresponds to processes that are not meant to be auto-started.

        :return: the processes included in the application start sequence.
        """
        return [process for seq, sub_seq in self.start_sequence.items()
                for process in sub_seq if seq > 0]

    def get_start_sequence_expected_load(self) -> int:
        """ Return the sum of the expected loading of the processes in the starting sequence.
        This is used only in the event where the application is not distributed and the whole application loading
        has to be checked on a single node.

        :return: the expected loading of the application.
        """
        return sum(process.rules.expected_load for process in self.get_start_sequenced_processes())

    def update_status(self) -> None:
        """ Update the state of the application iaw the state of its sequenced processes.
        An unmanaged application - or generally without starting sequence - is always STOPPED.

        :return: None
        """
        # always reset failures
        self.major_failure, self.minor_failure, possible_major_failure = (False, ) * 3
        # get the processes from the starting sequence
        sequenced_processes = [process for sub_seq in self.start_sequence.values()
                               for process in sub_seq]
        if not sequenced_processes:
            self.logger.debug('ApplicationStatus.update_status: application_name={}'
                              ' is not managed so always STOPPED'. format(self.application_name))
            self.state = ApplicationStates.STOPPED
            return
        # evaluate application state based on the state of the processes in its start sequence
        starting, running, stopping = (False,) * 3
        for process in sequenced_processes:
            self.logger.trace('ApplicationStatus.update_status: application_name={} process={} state={}'
                              ' required={} exit_expected={}'
                              .format(self.application_name, process.namespec, process.state_string(),
                                      process.rules.required, process.expected_exit))
            if process.state == ProcessStates.RUNNING:
                running = True
            elif process.state in [ProcessStates.STARTING, ProcessStates.BACKOFF]:
                starting = True
            # STOPPING is not in STOPPED_STATES
            elif process.state == ProcessStates.STOPPING:
                stopping = True
            elif (process.state in [ProcessStates.FATAL, ProcessStates.UNKNOWN]
                    or process.state == ProcessStates.EXITED and not process.expected_exit):
                # a major/minor failure is raised in this states depending on the required option
                if process.rules.required:
                    self.major_failure = True
                else:
                    self.minor_failure = True
            elif process.state == ProcessStates.STOPPED:
                # possible major failure raised if STOPPED
                # consideration will depend on the global application state
                if process.rules.required:
                    possible_major_failure = True
            # only remaining case is EXITED + expected
            # TODO: possible_major_failure could be set if it has not been run yet
        self.logger.trace('ApplicationStatus.update_status: application_name={} - starting={} running={} stopping={}'
                          ' major_failure={} minor_failure={} possible_major_failure={}'
                          .format(self.application_name, starting, running, stopping,
                                  self.major_failure, self.minor_failure, possible_major_failure))
        # apply rules for state
        if stopping:
            # if at least one process is STOPPING, let's consider that application is stopping
            # here priority is given to STOPPING over STARTING
            self.state = ApplicationStates.STOPPING
        elif starting:
            # if at least one process is STARTING, let's consider that application is starting
            self.state = ApplicationStates.STARTING
        elif running:
            # all processes in the sequence are RUNNING, so application is RUNNING
            self.state = ApplicationStates.RUNNING
        else:
            # all processes in the sequence are STOPPED, so application is STOPPED
            self.state = ApplicationStates.STOPPED
        # consider possible failure
        if self.state != ApplicationStates.STOPPED:
            self.major_failure |= possible_major_failure
        self.logger.debug('Application {}: state={} major_failure={} minor_failure={}'
                          .format(self.application_name, self.state, self.major_failure, self.minor_failure))
