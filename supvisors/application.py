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

import re

from typing import Any, Dict, List, Sequence

from supervisor.loggers import Logger
from supervisor.states import ProcessStates

from .process import ProcessStatus
from .ttypes import (ApplicationStates, DistributionRules, NameList, Payload, StartingStrategies,
                     StartingFailureStrategies, RunningFailureStrategies)


class ApplicationRules(object):
    """ Definition of the rules for starting an application, iaw rules file.

    Attributes are:
        - managed: set to True when application rules are found from the rules file ;
        - distribution: the distribution rule of the application ;
        - identifiers: the Supervisors where the application can be started if not distributed (default: all) ;
        - hash_identifiers: when # rule is used, the application can be started on one of the Supervisors identified ;
        - start_sequence: defines the order of this application when starting all the applications
          in the DEPLOYMENT state (0 means: no automatic start);
        - stop_sequence: defines the order of this application when stopping all the applications
          (0 means: immediate stop);
        - starting_strategy: defines the strategy to apply when choosing the identifier where the process
          shall be started during the starting of the application;
        - starting_failure_strategy: defines the strategy to apply when a required process cannot be started
          during the starting of the application;
        - running_failure_strategy: defines the default strategy to apply when a required process crashes
          when the application is running.
    """

    def __init__(self, supvisors: Any) -> None:
        """ Initialization of the attributes. """
        # keep a reference to the Supvisors global structure
        self.supvisors = supvisors
        self.logger: Logger = supvisors.logger
        # attributes
        self.managed: bool = False
        self.distributed: bool = True
        self.distribution: DistributionRules = DistributionRules.ALL_INSTANCES
        self.identifiers: NameList = ['*']
        self.hash_identifiers: NameList = []
        self.start_sequence: int = 0
        self.stop_sequence: int = -1
        self.starting_strategy: StartingStrategies = StartingStrategies.CONFIG
        self.starting_failure_strategy: StartingFailureStrategies = StartingFailureStrategies.ABORT
        self.running_failure_strategy: RunningFailureStrategies = RunningFailureStrategies.CONTINUE

    def check_stop_sequence(self, application_name: str) -> None:
        """ Check the stop_sequence value.
        If stop_sequence hasn't been set from the rules file, use the same value as start_sequence.

        :param application_name: the name of the application considered.
        :return: None
        """
        if self.stop_sequence < 0:
            self.logger.trace(f'ApplicationRules.check_stop_sequence: {application_name}'
                              f' - set stop_sequence to {self.start_sequence} ')
            self.stop_sequence = self.start_sequence

    def check_hash_identifiers(self, application_name: str) -> None:
        """ When a '#' is set in application rules, an association has to be done between the 'index' of the application
        and the index of the Supervisor in the applicable identifier list.
        Unlike programs, there is no unquestionable index that Supvisors could get because Supervisor does not support
        homogeneous applications. It thus has to be a convention.
        The chosen convention is that the application_name MUST match r'[-_]\\d+$'. The first index name is 1.

        hash_identifiers is expected to contain:
            - either ['*'] when all Supervisors are applicable
            - or any subset of these Supervisors.

        :param application_name: the name of the application considered.
        :return: None
        """
        error = True
        result = re.match(r'.*[-_](\d+)$', application_name)
        if not result:
            self.logger.error(f'ApplicationRules.check_hash_identifiers: {application_name} incompatible'
                              ' with the use of #')
        else:
            application_number = int(result.group(1)) - 1
            if application_number < 0:
                self.logger.error(f'ApplicationRules.check_hash_identifiers: index of {application_name} must be > 0')
            else:
                self.logger.debug(f'ApplicationRules.check_hash_identifiers: application_name={application_name}'
                                  f' application_number={application_number}')
                if '*' in self.hash_identifiers:
                    # all identifiers defined in the supvisors section of the supervisor configuration are applicable
                    ref_identifiers = list(self.supvisors.supvisors_mapper.instances.keys())
                else:
                    # the subset of applicable identifiers is the hash_identifiers
                    ref_identifiers = self.hash_identifiers
                if application_number < len(ref_identifiers):
                    self.identifiers = [ref_identifiers[application_number]]
                    error = False
                else:
                    self.logger.error(f'ApplicationRules.check_hash_identifiers: {application_name} has no'
                                      ' applicable identifier')
        if error:
            self.logger.warn(f'ApplicationRules.check_hash_identifiers: {application_name} start_sequence reset')
            self.start_sequence = 0

    def check_dependencies(self, application_name: str) -> None:
        """ Update rules after they have been read from the rules file.

        :param application_name: the name of the application considered.
        :return: None
        """
        self.check_stop_sequence(application_name)
        if self.hash_identifiers:
            self.check_hash_identifiers(application_name)

    def __str__(self) -> str:
        """ Get the application rules as string.

        :return: the printable application rules
        """
        return (f'managed={self.managed} distribution={self.distribution.name} identifiers={self.identifiers}'
                f' start_sequence={self.start_sequence} stop_sequence={self.stop_sequence}'
                f' starting_strategy={self.starting_strategy.name}'
                f' starting_failure_strategy={self.starting_failure_strategy.name}'
                f' running_failure_strategy={self.running_failure_strategy.name}')

    # serialization
    def serial(self) -> Payload:
        """ Get a serializable form of the application rules.
        No information for unmanaged applications.

        :return: the application rules in a dictionary
        """
        if self.managed:
            payload = {'managed': True, 'distributed': self.distribution == DistributionRules.ALL_INSTANCES,  # DEPRECATED
                       'distribution': self.distribution.name, 'identifiers': self.identifiers,  # TODO: add / replace by nodes / targets ?
                       'start_sequence': self.start_sequence, 'stop_sequence': self.stop_sequence,
                       'starting_strategy': self.starting_strategy.name,
                       'starting_failure_strategy': self.starting_failure_strategy.name,
                       'running_failure_strategy': self.running_failure_strategy.name}
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
        - rules: the ApplicationRules applicable to this application,
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
            self.logger.info(f'Application.state: {self.application_name} is {self.state.name}')

    def has_running_processes(self) -> bool:
        """ Check if one of the application processes is running.
        The application state may be STOPPED in this case if the running process is out of the starting sequence.

        :return: True if any of the application processes is running
        """
        return any(process.running() for process in self.processes.values())

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
        return {'application_name': self.application_name, 'managed': self.rules.managed,
                'statecode': self.state.value, 'statename': self.state.name,
                'major_failure': self.major_failure, 'minor_failure': self.minor_failure}

    def __str__(self) -> str:
        """ Get the application status as string.

        :return: the printable application status
        """
        return (f'application_name={self.application_name} managed={self.rules.managed} state={self.state.name}'
                f' major_failure={self.major_failure} minor_failure={self.minor_failure}')

    # methods
    def add_process(self, process: ProcessStatus) -> None:
        """ Add a new process to the process list.

        :param process: the process status to be added to the application
        :return: None
        """
        self.processes[process.process_name] = process

    def remove_process(self, process_name: str) -> None:
        """ Add a new process to the process list.

        :param process_name: the process to be removed from the application
        :return: None
        """
        self.logger.info(f'ApplicationStatus.remove_process: {self.application_name} - removing process={process_name}')
        del self.processes[process_name]
        # re-evaluate sequences and status
        self.update_sequences()
        self.update_status()

    def possible_identifiers(self) -> NameList:
        """ Return the list of Supervisor identifiers where the application could be started.
        To achieve that, two conditions:
            - the Supervisor must know all the application programs ;
            - the Supervisor identifier must be declared in the rules file.

        :return: the list of identifiers where the program could be started
        """
        identifiers = self.rules.identifiers
        if '*' in self.rules.identifiers:
            identifiers = self.supvisors.supvisors_mapper.instances
        # get the identifiers common to all application processes
        actual_identifiers = [set(process.info_map.keys()) for process in self.processes.values()]
        if actual_identifiers:
            actual_identifiers = actual_identifiers[0].intersection(*actual_identifiers)
        # intersect with rules
        return [identifier for identifier in identifiers if identifier in actual_identifiers]

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
            self.logger.debug(f'ApplicationStatus.update_sequences: application_name={self.application_name}'
                              f' start_sequence={self.printable_sequence(self.start_sequence)}')
        else:
            self.logger.info(f'ApplicationStatus.update_sequences: application_name={self.application_name}'
                             ' is not managed so start sequence is undefined')
        # stop sequence is applicable to all applications
        for process in self.processes.values():
            # fill ordering iaw process rules
            self.stop_sequence.setdefault(process.rules.stop_sequence, []).append(process)
        self.logger.debug(f'ApplicationStatus.update_sequences: application_name={self.application_name}'
                          f' stop_sequence={self.printable_sequence(self.stop_sequence)}')

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
        has to be checked on a single Supervisor.

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
            self.logger.debug(f'ApplicationStatus.update_status: application_name={self.application_name}'
                              ' is not managed so always STOPPED')
            self.state = ApplicationStates.STOPPED
            return
        # evaluate application state based on the state of the processes in its start sequence
        starting, running, stopping = (False,) * 3
        for process in sequenced_processes:
            self.logger.trace(f'ApplicationStatus.update_status: application_name={self.application_name}'
                              f' process={process.namespec} state={process.state_string()}'
                              f' required={process.rules.required} exit_expected={process.expected_exit}')
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
        self.logger.trace(f'ApplicationStatus.update_status: application_name={self.application_name}'
                          f' - starting={starting} running={running} stopping={stopping}'
                          f' major_failure={self.major_failure} minor_failure={self.minor_failure}'
                          f' possible_major_failure={possible_major_failure}')
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
        self.logger.debug(f'Application.update_status: application_name={self.application_name} state={self.state}'
                          f' major_failure={self.major_failure} minor_failure={self.minor_failure}')
