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

from typing import Dict, List, Sequence

from supervisor.loggers import Logger
from supervisor.states import *

from supvisors.process import ProcessStatus
from supvisors.ttypes import (ApplicationStates, Payload,
                              StartingFailureStrategies,
                              RunningFailureStrategies)


class ApplicationRules(object):
    """ Definition of the rules for starting an application, iaw rules file.

    Attributes are:
        - default: True if not overwritten by rules file
        - start_sequence: defines the order of this application when starting all the applications in the DEPLOYMENT state (0 means: no automatic start),
        - stop_sequence: defines the order of this application when stopping all the applications (0 means: immediate stop),
        - starting_failure_strategy: defines the strategy (in StartingFailureStrategies) to apply when a required process cannot be started during the starting of the application,
        - running_failure_strategy: defines the default strategy (in RunningFailureStrategies) to apply when a required process crashes when the application is running.
    """

    def __init__(self) -> None:
        """ Initialization of the attributes. """
        self.managed = False
        self.start_sequence = 0
        self.stop_sequence = 0
        self.starting_failure_strategy = StartingFailureStrategies.ABORT
        self.running_failure_strategy = RunningFailureStrategies.CONTINUE

    def __str__(self) -> str:
        """ Get the application rules as string.

        :return: the printable application rules
        """
        return 'managed={} start_sequence={} stop_sequence={} starting_failure_strategy={} running_failure_strategy={}' \
            .format(self.managed, self.start_sequence, self.stop_sequence,
                    self.starting_failure_strategy.name,
                    self.running_failure_strategy.name)

    # serialization
    def serial(self) -> Payload:
        """ Get a serializable form of the application rules.

        :return: the application rules in a dictionary
        """
        return {'managed': self.managed,
                'start_sequence': self.start_sequence,
                'stop_sequence': self.stop_sequence,
                'starting_failure_strategy': self.starting_failure_strategy.name,
                'running_failure_strategy': self.running_failure_strategy.name}


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
    ApplicationSequence = Dict[int, List[ProcessStatus]]
    PrintableApplicationSequence = Dict[int, Sequence[str]]
    ProcessMap = Dict[str, ProcessStatus]

    def __init__(self, application_name: str, rules: ApplicationRules, logger: Logger) -> None:
        """ Initialization of the attributes.

        :param application_name: the name of the application
        :param rules: the rules applicable to the application
        :param logger: the common logger used throughout Supvisors
        """
        # keep reference to common logger
        self.logger = logger
        # information part
        self.application_name = application_name
        self._state = ApplicationStates.STOPPED
        self.major_failure = False
        self.minor_failure = False
        # process part
        self.processes: ApplicationStatus.ProcessMap = {}
        self.rules = rules
        self.start_sequence: ApplicationStatus.ApplicationSequence = {}
        self.stop_sequence: ApplicationStatus.ApplicationSequence = {}

    # access
    def running(self) -> bool:
        """ Return True if the application is running.

        :return: the running status of the process
        """
        return self.state in [ApplicationStates.STARTING, ApplicationStates.RUNNING]

    def stopped(self) -> bool:
        """ Return True if the application is stopped.

        :return: the stopped status of the process
        """
        return self.state == ApplicationStates.STOPPED

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

    # methods
    def add_process(self, process: ProcessStatus) -> None:
        """ Add a new process to the process list.

        :param process: the process status to be added to the application
        :return: None
        """
        self.processes[process.process_name] = process

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

        :return: None
        """
        # fill ordering iaw process rules
        self.start_sequence.clear()
        self.stop_sequence.clear()
        for process in self.processes.values():
            self.start_sequence.setdefault(process.rules.start_sequence, []).append(process)
            self.stop_sequence.setdefault(process.rules.stop_sequence, []).append(process)
        self.logger.debug('ApplicationStatus.update_sequences: application_name={} start_sequence={} stop_sequence={}'
                          .format(self.application_name,
                                  self.printable_sequence(self.start_sequence),
                                  self.printable_sequence(self.stop_sequence)))

    def update_status(self) -> None:
        """ Update the state of the application iaw the state of its processes.

        :return: None
        """
        starting, running, stopping, major_failure, minor_failure = (False,) * 5
        for process in self.processes.values():
            self.logger.trace('ApplicationStatus.update_status: application_name={} process={} state={}'
                              ' required={} exit_expected={}'
                              .format(self.application_name, process.namespec(), process.state_string(),
                                      process.rules.required, process.expected_exit))
            if process.state == ProcessStates.RUNNING:
                running = True
            elif process.state in [ProcessStates.STARTING, ProcessStates.BACKOFF]:
                starting = True
            # STOPPING is not in STOPPED_STATES
            elif process.state == ProcessStates.STOPPING:
                stopping = True
            elif process.state in STOPPED_STATES:
                if process.rules.required:
                    # any required stopped process is a major failure for a running application
                    # exception is made for an EXITED process with an expected exit code
                    if process.state != ProcessStates.EXITED or not process.expected_exit:
                        major_failure = True
                else:
                    # an optional process is a minor failure for a running application
                    # when its state is FATAL or unexpectedly EXITED
                    if ((process.state == ProcessStates.FATAL) or
                            (process.state == ProcessStates.EXITED and not process.expected_exit)):
                        minor_failure = True
            # all other STOPPED-like states are considered normal
        self.logger.trace('ApplicationStatus.update_status: application_name={} starting={} running={} stopping={}'
                          ' major_failure={} minor_failure={}'
                          .format(self.application_name, starting, running, stopping, major_failure, minor_failure))
        # apply rules for state
        if starting:
            self.state = ApplicationStates.STARTING
        elif stopping:
            self.state = ApplicationStates.STOPPING
        elif running:
            self.state = ApplicationStates.RUNNING
        else:
            self.state = ApplicationStates.STOPPED
        # update major_failure and minor_failure status (only for running applications)
        self.major_failure = major_failure and self.running()
        self.minor_failure = minor_failure and self.running()
        self.logger.debug('Application {}: major_failure={} minor_failure={}'
                          .format(self.application_name, self.major_failure, self.minor_failure))
