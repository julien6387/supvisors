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

from typing import AbstractSet, Any, Dict, Optional, Set, Tuple

from supervisor.loggers import Logger, LevelsByName
from supervisor.options import make_namespec, split_namespec
from supervisor.rpcinterface import SupervisorNamespaceRPCInterface
from supervisor.states import ProcessStates, getProcessStateDescription, RUNNING_STATES, STOPPED_STATES

from .ttypes import NameList, Payload, RunningFailureStrategies, StartingFailureStrategies
from .utils import *


class ProcessRules(object):
    """ Defines the rules for starting a process, iaw rules file.

    Attributes are:
        - identifiers: the identifiers of the Supvisors instances where the process can be started (default: all) ;
        - hash_identifiers: when # rule is used, the process can be started on only one of the Supvisors instances ;
        - start_sequence: the order in the starting sequence of the application ;
        - stop_sequence: the order in the stopping sequence of the application ;
        - required: a status telling if the process is required within the application ;
        - wait_exit: a status telling if Supvisors has to wait for the process to exit before triggering the next phase
          in the starting sequence of the application ;
        - expected_load: the expected loading of the process on the considered hardware (can be anything
          at the user discretion: CPU, RAM, etc.) ;
        - starting_failure_strategy: supersedes the application rule and defines the strategy to apply
          when the process crashes when the application is starting ;
        - running_failure_strategy: supersedes the application rule and defines the strategy to apply
          when the process crashes when the application is running.
    """

    def __init__(self, supvisors: Any) -> None:
        """ Initialization of the attributes.

        :param supvisors: the global Supvisors structure.
        """
        # keep a reference to the Supvisors global structure
        self.supvisors = supvisors
        self.logger: Logger = supvisors.logger
        # attributes
        self.identifiers: NameList = ['*']
        self.hash_identifiers: NameList = []
        self.start_sequence: int = 0
        self.stop_sequence: int = -1
        self.required: bool = False
        self.wait_exit: bool = False
        self.expected_load: int = 0
        self.starting_failure_strategy: StartingFailureStrategies = StartingFailureStrategies.ABORT
        self.running_failure_strategy: RunningFailureStrategies = RunningFailureStrategies.CONTINUE

    def check_start_sequence(self, namespec: str) -> None:
        """ ProcessRules having required=True MUST have start_sequence > 0,
        so force required to False if start_sequence is not set.

        :param namespec: the namespec of the program considered.
        :return: None
        """
        if self.required and self.start_sequence == 0:
            self.logger.warn(f'ProcessRules.check_start_sequence: {namespec} - required forced to False'
                             ' because no start_sequence defined')
            self.required = False

    def check_stop_sequence(self, namespec: str) -> None:
        """ Check the stop_sequence value.
        If stop_sequence hasn't been set from the rules file, use the same value as start_sequence.

        :param namespec: the namespec of the program considered.
        :return: None
        """
        if self.stop_sequence < 0:
            self.logger.trace(f'ProcessRules.check_stop_sequence: {namespec}'
                              f' - set stop_sequence to {self.start_sequence}')
            self.stop_sequence = self.start_sequence

    def check_autorestart(self, namespec: str) -> None:
        """ Disable autorestart when RunningFailureStrategies is related to applications.
        In these cases, Supvisors triggers behaviors that are different to Supervisor.

        :param namespec: the namespec of the program considered.
        :return: None
        """
        if self.running_failure_strategy in [RunningFailureStrategies.STOP_APPLICATION,
                                             RunningFailureStrategies.RESTART_APPLICATION]:
            try:
                if self.supvisors.supervisor_data.autorestart(namespec):
                    self.supvisors.supervisor_data.disable_autorestart(namespec)
                    self.logger.warn(f'ProcessRules.check_autorestart: namespec={namespec} - autorestart disabled'
                                     f' due to running failure strategy {self.running_failure_strategy.name}')
            except KeyError:
                self.logger.debug(f'ProcessRules.check_autorestart: namespec={namespec} unknown to local Supervisor')

    def check_hash_identifiers(self, namespec: str) -> None:
        """ When a '#' is set in program rules, an association has to be made between the procnumber of the process
        and the index of the Supvisors identifier in the applicable identifiers list.
        In this case, rules.hash_identifiers is expected to contain:
            - either ['*'] when all Supervisors are applicable
            - or any subset of these Supervisors.

        :param namespec: the namespec of the program considered.
        :return: None
        """
        error = True
        _, process_name = split_namespec(namespec)
        try:
            procnumber = self.supvisors.server_options.procnumbers[process_name]
        except KeyError:
            self.logger.error(f'ProcessRules.check_hash_identifiers: cannot apply "#" to unknown program={namespec}')
        else:
            self.logger.debug(f'ProcessRules.check_hash_identifiers: namespec={namespec} procnumber={procnumber}')
            if '*' in self.hash_identifiers:
                # all identifiers defined in the supvisors section of the supervisor configuration file are applicable
                ref_identifiers = list(self.supvisors.supvisors_mapper.instances.keys())
            else:
                # the subset of applicable identifiers is the second element of rule 'identifiers'
                ref_identifiers = self.hash_identifiers
            if procnumber < len(ref_identifiers):
                self.identifiers = [ref_identifiers[procnumber]]
                error = False
            else:
                self.logger.error(f'ProcessRules.check_hash_identifiers: namespec={namespec} has no applicable'
                                  ' Supvisors identifier')
        if error:
            self.logger.warn(f'ProcessRules.check_hash_identifiers: namespec={namespec} start_sequence reset')
            self.start_sequence = 0

    def check_dependencies(self, namespec: str) -> None:
        """ Update rules after they have been read from the rules file.

        :param namespec: the namespec of the program considered.
        :return: None
        """
        self.check_start_sequence(namespec)
        self.check_stop_sequence(namespec)
        self.check_autorestart(namespec)
        if self.hash_identifiers:
            self.check_hash_identifiers(namespec)

    def __str__(self) -> str:
        """ Get the process rules as string.

        :return: the printable process rules
        """
        return (f'identifiers={self.identifiers} hash_identifiers={self.hash_identifiers}'
                f' start_sequence={self.start_sequence} stop_sequence={self.stop_sequence} required={self.required}'
                f' wait_exit={self.wait_exit} expected_load={self.expected_load}'
                f' starting_failure_strategy={self.starting_failure_strategy.name}'
                f' running_failure_strategy={self.running_failure_strategy.name}')

    def serial(self) -> Payload:
        """ Get a serializable form of the process rules.
        hash_identifiers is not exported as used internally to resolve identifiers.

        :return: the process rules in a dictionary
        """
        return {'identifiers': self.identifiers,
                'start_sequence': self.start_sequence, 'stop_sequence': self.stop_sequence,
                'required': self.required,  'wait_exit': self.wait_exit, 'expected_loading': self.expected_load,
                'starting_failure_strategy': self.starting_failure_strategy.name,
                'running_failure_strategy': self.running_failure_strategy.name}


class ProcessStatus(object):
    """ Class defining the status of a process of Supvisors.

    Attributes are:
        - application_name: the application name, or group name from a Supervisor point of view ;
        - process_name: the process name ;
        - namespec: the process namespec ;
        - state: the synthetic state of the process, same enumeration as Supervisor ;
        - forced_state: the state forced by Supvisors upon unexpected event ;
        - forced_reason: the reason why the state would be forced ;
        - expected_exit: a status telling if the process has exited expectantly ;
        - last_event_time: the local date of the last information received ;
        - extra_args: the additional arguments passed to the command line ;
        - running_identifiers: the list of all Supervisors where the process is running ;
        - info_map: a process info dictionary for each Supvisors identifier (running or not) ;
        - rules: the rules related to this process.
    """

    def __init__(self, application_name: str, process_name: str, rules: ProcessRules, supvisors: Any) -> None:
        """ Initialization of the attributes.

        :param application_name: the name of the application the process belongs to
        :param process_name: the name of the process
        :param rules: the rules loaded from the rules file
        :param supvisors: the global Supvisors structure
        """
        # keep a reference of the Supvisors data
        self.supvisors = supvisors
        self.logger: Logger = supvisors.logger
        # attributes
        self.application_name: str = application_name
        self.process_name: str = process_name
        self.namespec = make_namespec(application_name, process_name)
        self._state: ProcessStates = ProcessStates.UNKNOWN
        self.forced_state: Optional[ProcessStates] = None
        self.forced_reason: str = ''
        self.expected_exit: bool = True
        self.last_event_time: int = 0
        self._extra_args: str = ''
        # rules part
        self.rules: ProcessRules = rules
        # one single running identifier is expected
        self.running_identifiers: Set[str] = set()  # identifiers
        self.info_map: Dict[str, Payload] = {}  # identifier: process_info

    @property
    def state(self) -> ProcessStates:
        """ Getter of state attribute.
        Returns forced state in priority if set.

        :return: the process state
        """
        return self._state if self.forced_state is None else self.forced_state

    @state.setter
    def state(self, new_state: ProcessStates) -> None:
        """ Setter of state attribute.

        :param new_state: the new process state
        :return: None
        """
        if self._state != new_state:
            self._state = new_state
            self.logger.info(f'ProcessStatus.state: {self.namespec} is {self.state_string()}')

    def force_state(self, event: Payload) -> None:
        """ Force the process state due to an unexpected event.
        This may be caused by a process command that has not been acknowledged in due time, so here is a final check
        for the expected state, in the event where messages have crossed.

        :param event: the forced event
        :return: None
        """
        reached = False
        # check current state on targeted identifier
        identifier = event['identifier']
        if identifier in self.info_map:
            instance_info = self.info_map[identifier]
            reached = instance_info['state'] == event['state']
        # if expected event not reached, apply forced state
        if not reached:
            self.last_event_time = int(time())
            self.forced_state = event['forced_state']
            self.forced_reason = event['spawnerr']
            self.logger.info(f'ProcessStatus.force_state: {self.namespec} is {self.state_string()}'
                             f' ({self.forced_reason})')

    def reset_forced_state(self, state: ProcessStates = None):
        """ Reset forced_state upon reception of new information only if not STOPPED (default state in Supervisor).

        :param state: the new state (provided only when Supervisor information is added for the first time)
        :return: None
        """
        if self.forced_state is not None and state != ProcessStates.STOPPED:
            self.forced_state = None
            self.forced_reason = ''
            self.logger.debug(f'ProcessStatus.reset_forced_state: namespec={self.namespec}')

    @property
    def extra_args(self) -> str:
        """ Getter of extra arguments attribute.

        :return: the extra arguments applicable to the command line of the process
        """
        return self._extra_args

    @extra_args.setter
    def extra_args(self, new_args: str) -> None:
        """ Setter of extra arguments attribute.

        :param new_args: the extra arguments applicable to the command line of the process
        :return: None
        """
        if self._extra_args != new_args:
            self._extra_args = new_args
            try:
                self.supvisors.supervisor_data.update_extra_args(self.namespec, new_args)
            except KeyError:
                self.logger.debug(f'ProcessStatus.extra_args: namespec={self.namespec} unknown to local Supervisor')

    def serial(self) -> Payload:
        """ Get a serializable form of the ProcessStatus.

        :return: the process status in a dictionary
        """
        return {'application_name': self.application_name,
                'process_name': self.process_name,
                'statecode': self.state, 'statename': self.state_string(),
                'expected_exit': self.expected_exit,
                'last_event_time': self.last_event_time,
                'identifiers': list(self.running_identifiers),
                'extra_args': self.extra_args}

    # access
    def possible_identifiers(self) -> NameList:
        """ Return the list of identifier where the program could be started.
        To achieve that, two conditions:
            - the Supervisor of the Supvisors instance must know the program ;
            - the Supvisors identifier must be declared in the rules file.

        :return: the list of identifiers where the program could be started
        """
        identifiers = self.rules.identifiers
        if '*' in self.rules.identifiers:
            identifiers = self.supvisors.supvisors_mapper.instances
        return [identifier for identifier in identifiers if identifier in self.info_map]

    def has_crashed(self) -> bool:
        """ Return True if the any of the processes has ever crashed or has ever exited unexpectedly.

        :return: the crash status of the process
        """
        return any(info['has_crashed'] for info in self.info_map.values())

    def crashed(self) -> bool:
        """ Return True if the process has crashed or has exited unexpectedly.

        :return: the crash status of the process
        """
        return ProcessStatus.is_crashed_event(self.state, self.expected_exit)

    @staticmethod
    def is_crashed_event(state: ProcessStates, expected_exit: bool) -> bool:
        """ Return True if the process has crashed or has exited unexpectedly.

        :return: the crash status of the process
        """
        return state == ProcessStates.FATAL or (state == ProcessStates.EXITED and not expected_exit)

    def stopped(self) -> bool:
        """ Return True if the process is stopped, as designed in Supervisor.

        :return: the stopped status of the process
        """
        return self.state in STOPPED_STATES

    def running(self) -> bool:
        """ Return True if the process is running, as designed in Supervisor.

        :return: the running status of the process
        """
        return self.state in RUNNING_STATES

    def running_on(self, identifier: str) -> bool:
        """ Check if the process is running on the Supvisors instance identified.

        :param identifier: the Supvisors instance identifier
        :return: the running status of the process on the considered Supvisors instance
        """
        return self.running() and identifier in self.running_identifiers

    def pid_running_on(self, identifier: str) -> bool:
        """ Check if process is RUNNING on the Supvisors instance identified.
        Different from running_on as it considers only the RUNNING state and not STARTING or BACKOFF.
        This is used by the statistics module that requires an existing PID.

        :param identifier: the Supvisors instance identifier
        :return: the true running status of the process on the considered Supervisor
        """
        return self.state == ProcessStates.RUNNING and identifier in self.running_identifiers

    def conflicting(self) -> bool:
        """ Check if the process is in a conflicting state (more than one instance running).

        :return: the conflict status of the process
        """
        return len(self.running_identifiers) > 1

    @staticmethod
    def update_description(info: Payload) -> str:
        """ Return the Supervisor way to describe the process status.

        :param info: a subset of the dict received from Supervisor.getProcessInfo.
        :return: the description of the process status
        """
        # IDE warning on first parameter but ignored as the Supervisor function should have been set as staticmethod
        return SupervisorNamespaceRPCInterface._interpretProcessInfo(None, info)

    def get_last_description(self) -> Tuple[Optional[str], str]:
        """ Get the latest description received from the process across all Supvisors instances.
        Priority is taken in the following order:
            1. the forced state ;
            2. the information coming from a Supervisor where the process is running ;
            3. the most recent information coming from a Supervisor where the process has been stopped.

        :return: the identifier of the Supervisor where the description comes, the process state description
        """
        self.logger.trace(f'ProcessStatus.get_last_description: START namespec={self.namespec}')
        # if the state is forced, return the reason why
        if self.forced_state is not None:
            self.logger.trace(f'ProcessStatus.get_last_description: namespec={self.namespec}'
                              f' - Supvisors=None [FORCED]description={self.forced_reason}')
            return None, self.forced_reason
        # search for process info where process is running
        info_map = dict(filter(lambda x: x[0] in self.running_identifiers, self.info_map.items()))
        if info_map:
            # sort info_map them by local_time (local_time is local time of latest received event)
            identifier, info = max(info_map.items(), key=lambda x: x[1]['local_time'])
            self.logger.trace(f'ProcessStatus.get_last_description: namespec={self.namespec}'
                              f' - Supvisors={identifier} [running]description={info["description"]}')
        else:
            # none running. sort info_map them by stop date
            identifier, info = max(self.info_map.items(), key=lambda x: x[1]['stop'])
            self.logger.trace(f'ProcessStatus.get_last_description: namespec={self.namespec}'
                              f' - Supvisors={identifier} [stopped]description={info["description"]}')
        # extract description from information found and add identifier
        desc = info['description']
        if desc and desc != 'Not started':
            desc = desc + ' on ' + identifier
        return identifier, desc

    # methods
    def state_string(self) -> str:
        """ Get the process state as a string.

        :return: the process state as a string
        """
        return getProcessStateDescription(self.state)

    def add_info(self, identifier: str, payload: Payload) -> None:
        """ Insert a new process information in internal list.

        :param identifier: the identifier of the Supvisors instance from which the information has been received
        :param payload: a subset of the dict received from Supervisor.getProcessInfo.
        :return: None
        """
        info = self.info_map[identifier] = payload
        # keep date of last information received
        # use local time here as there is no guarantee that Supvisors instances will be time-synchronized
        self.last_event_time = int(time())
        info['local_time'] = self.last_event_time
        self.update_uptime(info)
        # WARN: when a new Supvisors instance comes in group, extra_args is kept only if information ties in
        if self.extra_args != info['extra_args']:
            # difference of view, reset
            info['extra_args'] = ''
            self.extra_args = ''
        # keep history that the process has ever crashed in the Supvisors instance
        has_crashed = ProcessStatus.is_crashed_event(info['state'], info['expected'])
        info['has_crashed'] = has_crashed | info.get('has_crashed', False)
        # log final payload
        self.logger.trace(f'ProcessStatus.add_info: namespec={self.namespec} - payload={info}'
                          f' added to Supvisors={identifier}')
        # process synthetic information
        self.reset_forced_state(info['state'])
        # update process status
        self.update_status(identifier, info['state'])

    def update_info(self, identifier: str, payload: Payload, external: bool = True) -> None:
        """ Update the internal process information with event payload.
        Event information is less complete than initial information.

        :param identifier: the identifier of the Supvisors instance from which the information has been received
        :param payload: the process information used to refresh internal data
        :param external: True if the event comes from another Supvisors instance
        :return: None
        """
        # refresh internal information
        info = self.info_map[identifier]
        self.logger.trace(f'ProcessStatus.update_info: namespec={self.namespec}'
                          f' - updating info[{identifier}]={info} with payload={payload}')
        info.update(payload)
        # keep date of last information received
        # use local time here as there is no guarantee that Supervisors will be time synchronized
        self.last_event_time = int(time())
        info['local_time'] = self.last_event_time
        # last received extra_args are always applicable
        self.extra_args = payload['extra_args']
        # complete missing information
        info['statename'] = getProcessStateDescription(info['state'])
        # re-evaluate description using Supervisor function
        info['description'] = self.update_description(info)
        # reset start time if process in a starting state
        new_state = info['state']
        if new_state in [ProcessStates.STARTING, ProcessStates.BACKOFF]:
            info['start'] = info['now']
        if new_state in STOPPED_STATES:
            info['stop'] = info['now']
        self.update_uptime(info)
        # keep history that the process has ever crashed in the Supvisors instance
        if external:
            # typically, an instance invalidation will not impact the has_crashed status
            info['has_crashed'] |= ProcessStatus.is_crashed_event(info['state'], info['expected'])
        # log final payload
        self.logger.debug(f'ProcessStatus.update_info: namespec={self.namespec} - new info[{identifier}]={info}')
        # process synthetic information
        self.reset_forced_state()
        # update / check running Supervisors
        self.update_status(identifier, new_state)

    def update_times(self, identifier: str, remote_time: float) -> None:
        """ Update the internal process information when a new tick is received from the remote Supvisors instance.

        :param identifier: the identifier of the Supvisors instance from which the tick has been received
        :param remote_time: the TICK timestamp (seconds from Epoch) in the reference time of the Supvisors instance
        :return: None
        """
        if identifier in self.info_map:
            info = self.info_map[identifier]
            info['now'] = remote_time
            self.update_uptime(info)
            # it may have an impact on the description depending on the process state
            info['description'] = self.update_description(info)

    @staticmethod
    def update_uptime(info: Payload) -> None:
        """ Update uptime entry of a process information.

        :param info: the process information related to a given Supervisor
        :return: None
        """
        info['uptime'] = ((info['now'] - info['start'])
                          if info['state'] in [ProcessStates.RUNNING, ProcessStates.STOPPING] else 0)

    def invalidate_identifier(self, identifier: str) -> bool:
        """ Update the status of a process that was running on a lost / non-responsive Supvisors instance.

        :param identifier: the identifier of the Supvisors instance from which no more information is received
        :return: True if process not running anywhere anymore
        """
        self.logger.debug(f'ProcessStatus.invalidate_identifier: namespec={self.namespec}'
                          f' - Supvisors={identifier} invalidated')
        failure = False
        if identifier in self.running_identifiers:
            # update process status with a FATAL payload
            info = self.info_map[identifier]
            payload = {'now': info['now'], 'state': ProcessStates.FATAL, 'extra_args': info['extra_args'],
                       'expected': False, 'spawnerr': f'Supervisor {identifier} lost'}
            self.update_info(identifier, payload, False)
            failure = self.running_identifiers == set()
        return failure

    def remove_identifier(self, identifier: str) -> bool:
        """ Update the status of a process that has been removed from the identified Supvisors instance,
        following an XML-RPC update_numprocs.

        :param identifier: the identifier of the Supvisors instance from which the process has been removed
        :return: True if the process is not defined anywhere anymore
        """
        del self.info_map[identifier]
        return self.info_map == {}

    def update_status(self, identifier: str, new_state: ProcessStates) -> None:
        """ Updates the state and list of running Supvisors instances iaw the new event.

        :param identifier: the identifier of the Supvisors instance from which new information has been received
        :param new_state: the new state of the process on the considered Supervisor
        :return: None
        """
        # update running identifiers list
        if new_state in STOPPED_STATES:
            self.running_identifiers.discard(identifier)
        elif new_state in RUNNING_STATES:
            # replace if current state stopped-like, add otherwise
            if self.stopped():
                self.running_identifiers = {identifier}
            else:
                self.running_identifiers.add(identifier)
        # evaluate state iaw running identifiers
        if self.conflicting():
            self._evaluate_conflict()
        else:
            # no conflict so there's at most one element running
            if self.running_identifiers:
                self.state = self.info_map[list(self.running_identifiers)[0]]['state']
                self.expected_exit = True
            else:
                # priority set on STOPPING
                if any(info['state'] == ProcessStates.STOPPING for info in self.info_map.values()):
                    self.state = ProcessStates.STOPPING
                    self.expected_exit = True
                else:
                    # for STOPPED_STATES, consider the most recent stop date
                    info = max(self.info_map.values(), key=lambda x: x['stop'])
                    self.state = info['state']
                    self.expected_exit = info['expected']
        # log the new status
        if LevelsByName.TRAC >= self.logger.level:
            log_trace = f'ProcessStatus.update_status: namespec={self.namespec} is {self.state_string()}'
            if self.running_identifiers:
                log_trace += f' on {list(self.running_identifiers)}'
            self.logger.trace(log_trace)

    def _evaluate_conflict(self) -> None:
        """ Get a synthetic state if several processes are in a RUNNING-like state.

        :return: True if a conflict is detected, None otherwise
        """
        # several processes seem to be in a running state so that becomes tricky
        states = {self.info_map[identifier]['state'] for identifier in self.running_identifiers}
        self.logger.debug(f'ProcessStatus.evaluate_conflict: {self.process_name} multiple states'
                          f' {[getProcessStateDescription(x) for x in states]}'
                          f' for Supvisors={list(self.running_identifiers)}')
        # state synthesis done using the sorting of RUNNING_STATES
        self.state = self.running_state(states)

    @staticmethod
    def running_state(states: AbstractSet[int]) -> int:
        """ Return the first matching running state.
         The sequence defined in the Supervisor RUNNING_STATES is suitable here.

        :param states: a list of all process states of the present process over all Supervisors
        :return: a running state if found in list, STOPPING otherwise
        """
        # There may be STOPPING states in the list
        # In this state, the process is not removed yet from the running_identifiers
        return next((state for state in list(RUNNING_STATES) + [ProcessStates.STOPPING]
                     if state in states), ProcessStates.UNKNOWN)
