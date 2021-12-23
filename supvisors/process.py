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

from .ttypes import NameList, Payload, RunningFailureStrategies
from .utils import *


class ProcessRules(object):
    """ Defines the rules for starting a process, iaw rules file.

    Attributes are:
        - node_names: the nodes where the process can be started (all by default),
        - hash_node_names: when # rule is used, the process can be started on one of these nodes (to be resolved),
        - start_sequence: the order in the starting sequence of the application,
        - stop_sequence: the order in the stopping sequence of the application,
        - required: a status telling if the process is required within the application,
        - wait_exit: a status telling if Supvisors has to wait for the process to exit before triggering the next phase
          in the starting sequence of the application,
        - expected_load: the expected loading of the process on the considered hardware (can be anything
          at the user discretion: CPU, RAM, etc),
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
        self.node_names: NameList = ['*']
        self.hash_node_names: NameList = []
        self.start_sequence: int = 0
        self.stop_sequence: int = -1
        self.required: bool = False
        self.wait_exit: bool = False
        self.expected_load: int = 0
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
        In these cases, Supvisors triggers behaviors that are different so supervisor.

        :param namespec: the namespec of the program considered.
        :return: None
        """
        if self.running_failure_strategy in [RunningFailureStrategies.STOP_APPLICATION,
                                             RunningFailureStrategies.RESTART_APPLICATION]:
            try:
                if self.supvisors.info_source.autorestart(namespec):
                    self.supvisors.info_source.disable_autorestart(namespec)
                    self.logger.warn(f'ProcessRules.check_autorestart: namespec={namespec} - autorestart disabled'
                                     f' due to running failure strategy {self.running_failure_strategy.name}')
            except KeyError:
                self.logger.debug(f'ProcessRules.check_autorestart: namespec={namespec} unknown to local Supervisor')

    def check_hash_nodes(self, namespec: str) -> None:
        """ When a '#' is set in program rules, an association has to be done between the procnumber of the process
        and the index of the node in the applicable node list.
        In this case, rules.hash_nodes is expected to contain:
            - either ['*'] when all nodes are applicable
            - or any subset of these nodes.

        :param namespec: the namespec of the program considered.
        :return: None
        """
        error = True
        _, process_name = split_namespec(namespec)
        try:
            procnumber = self.supvisors.server_options.procnumbers[process_name]
        except KeyError:
            self.logger.error(f'ProcessRules.check_hash_nodes: cannot apply "#" to unknown program={namespec}')
        else:
            self.logger.debug(f'ProcessRules.check_hash_nodes: namespec={namespec} procnumber={procnumber}')
            if '*' in self.hash_node_names:
                # all nodes defined in the supvisors section of the supervisor configuration file are applicable
                ref_node_names = self.supvisors.node_mapper.node_names
            else:
                # the subset of applicable nodes is the second element of rule nodes
                ref_node_names = self.hash_node_names
            if procnumber < len(ref_node_names):
                self.node_names = [ref_node_names[procnumber]]
                error = False
            else:
                self.logger.error(f'ProcessRules.check_hash_nodes: program={namespec} has no applicable node')
        if error:
            self.logger.warn(f'ProcessRules.check_hash_nodes: program={namespec} start_sequence reset')
            self.start_sequence = 0

    def check_dependencies(self, namespec: str) -> None:
        """ Update rules after they have been read from the rules file.

        :param namespec: the namespec of the program considered.
        :return: None
        """
        self.check_start_sequence(namespec)
        self.check_stop_sequence(namespec)
        self.check_autorestart(namespec)
        if self.hash_node_names:
            self.check_hash_nodes(namespec)

    def __str__(self) -> str:
        """ Get the process rules as string.

        :return: the printable process rules
        """
        return (f'node_names={self.node_names} hash_node_names={self.hash_node_names}'
                f' start_sequence={self.start_sequence} stop_sequence={self.stop_sequence} required={self.required}'
                f' wait_exit={self.wait_exit} expected_load={self.expected_load}'
                f' running_failure_strategy={self.running_failure_strategy.name}')

    def serial(self) -> Payload:
        """ Get a serializable form of the process rules.
        hash_node_names is not exported as used internally to resolve nodes.

        :return: the process rules in a dictionary
        """
        return {'nodes': self.node_names,
                'start_sequence': self.start_sequence,
                'stop_sequence': self.stop_sequence,
                'required': self.required,
                'wait_exit': self.wait_exit,
                'expected_loading': self.expected_load,
                'running_failure_strategy': self.running_failure_strategy.name}


class ProcessStatus(object):
    """ Class defining the status of a process of Supvisors.

    Attributes are:
        - application_name: the application name, or group name from a Supervisor point of view,
        - process_name: the process name,
        - namespec: the process namespec,
        - state: the synthetic state of the process, same enumeration as Supervisor,
        - forced_state: the state forced by Supvisors upon unexpected event,
        - forced_reason: the reason why the state would be forced,
        - expected_exit: a status telling if the process has exited expectantly,
        - last_event_time: the local date of the last information received,
        - extra_args: the additional arguments passed to the command line,
        - running_nodes: the list of all nodes where the process is running,
        - info_map: a process info dictionary for each node (running or not),
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
        # one single running node is expected
        self.running_nodes: Set[str] = set()  # node_names
        self.info_map: Dict[str, Payload] = {}  # node_name: process_info

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

    def force_state(self, state: ProcessStates, reason: str = None) -> None:
        """ Force the process state due to an unexpected event.

        :param state: the forced state
        :param reason: the reason why the state is forced
        :return: None
        """
        self.last_event_time = int(time())
        self.forced_state = state
        self.forced_reason = reason

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
                self.supvisors.info_source.update_extra_args(self.namespec, new_args)
            except KeyError:
                self.logger.debug(f'ProcessStatus.extra_args: namespec={self.namespec} unknown to local Supervisor')

    def serial(self) -> Payload:
        """ Get a serializable form of the ProcessStatus.

        :return: the process status in a dictionary
        """
        return {'application_name': self.application_name,
                'process_name': self.process_name,
                'statecode': self.state,
                'statename': self.state_string(),
                'expected_exit': self.expected_exit,
                'last_event_time': self.last_event_time,
                'nodes': list(self.running_nodes),
                'addresses': list(self.running_nodes),  # TODO: DEPRECATED
                'extra_args': self.extra_args}

    # access
    def possible_nodes(self) -> NameList:
        """ Return the list of nodes where the program could be started.
        To achieve that, two conditions:
            - the Supervisor node must know the program;
            - the node must be declared in the applicable nodes in the rules file.

        :return: the list of nodes where the program could be started
        """
        node_names = self.rules.node_names
        if '*' in self.rules.node_names:
            node_names = self.supvisors.node_mapper.node_names
        return [node_name for node_name in node_names
                if node_name in self.info_map.keys()]

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

    def running_on(self, node_name: str) -> bool:
        """ Return True if the process is running on node.

        :param node_name: the node name
        :return: the running status of the process on the considered node
        """
        return self.running() and node_name in self.running_nodes

    def pid_running_on(self, node_name: str) -> bool:
        """ Return True if process is RUNNING on node_name.
        Different from running_on as it considers only the RUNNING state and not STARTING or BACKOFF.
        This is used by the statistics module that requires an existing PID.

        :param node_name: the node name
        :return: the true running status of the process on the considered node
        """
        return self.state == ProcessStates.RUNNING and node_name in self.running_nodes

    def conflicting(self) -> bool:
        """ Return True if the process is in a conflicting state (more than one instance running).

        :return: the conflict status of the process
        """
        return len(self.running_nodes) > 1

    @staticmethod
    def update_description(info: Payload) -> str:
        """ Return the Supervisor way to describe the process status.

        :param info: a subset of the dict received from Supervisor.getProcessInfo.
        :return: the description of the process status
        """
        # IDE warning on first parameter but ignored as the Supervisor function should have been set as staticmethod
        return SupervisorNamespaceRPCInterface._interpretProcessInfo(None, info)

    def get_last_description(self) -> Tuple[Optional[str], str]:
        """ Get the latest description received from the process across all nodes.
        Priority is taken in the following order:
            1. the forced state,
            2. the information coming from a node where the process is running,
            3. the most recent information coming from a node where the process has been stopped.

        :return: the node where the description comes, the process state description
        """
        self.logger.trace(f'ProcessStatus.get_last_description: START namespec={self.namespec}')
        # if the state is forced, return the reason why
        if self.forced_state is not None:
            self.logger.trace(f'ProcessStatus.get_last_description: namespec={self.namespec}'
                              f' - node_name=None [FORCED]description={self.forced_reason}')
            return None, self.forced_reason
        # search for process info where process is running
        info_map = dict(filter(lambda x: x[0] in self.running_nodes, self.info_map.items()))
        if info_map:
            # sort info_map them by local_time (local_time is local time of latest received event)
            node_name, info = max(info_map.items(), key=lambda x: x[1]['local_time'])
            self.logger.trace(f'ProcessStatus.get_last_description: namespec={self.namespec}'
                              f' - node_name={node_name} [running]description={info["description"]}')
        else:
            # none running. sort info_map them by stop date
            node_name, info = max(self.info_map.items(), key=lambda x: x[1]['stop'])
            self.logger.trace(f'ProcessStatus.get_last_description: namespec={self.namespec}'
                              f' - node_name={node_name} [stopped]description={info["description"]}')
        # extract description from information found and add node_name
        desc = info['description']
        if desc and desc != 'Not started':
            desc = desc + ' on ' + node_name
        return node_name, desc

    # methods
    def state_string(self) -> str:
        """ Get the process state as a string.

        :return: the process state as a string
        """
        return getProcessStateDescription(self.state)

    def add_info(self, node_name: str, payload: Payload) -> None:
        """ Insert a new process information in internal list.

        :param node_name: the name of the node from which the information has been received
        :param payload: a subset of the dict received from Supervisor.getProcessInfo.
        :return: None
        """
        # keep date of last information received
        # use local time here as there is no guarantee that nodes will be time-synchronized
        self.last_event_time = int(time())
        # store information
        info = self.info_map[node_name] = payload
        info['local_time'] = self.last_event_time
        self.update_uptime(info)
        # TODO: why reset extra_args ?
        info['extra_args'] = ''
        self.extra_args = ''
        self.logger.trace(f'ProcessStatus.add_info: namespec={self.namespec} - payload={info}'
                          f' added to node_name={node_name}')
        # reset forced_state upon reception of new information only if not STOPPED (default state in supervisor)
        if self.forced_state is not None and info['state'] != ProcessStates.STOPPED:
            self.forced_state = None
            self.forced_reason = ''
            self.logger.debug(f'ProcessStatus.add_info: namespec={self.namespec} - forced_state unset')
        # update process status
        self.update_status(node_name, info['state'])

    def update_info(self, node_name: str, payload: Payload) -> None:
        """ Update the internal process information with event payload.

        :param node_name: the name of the node from which the information has been received
        :param payload: the process information used to refresh internal data
        :return: None
        """
        # do not consider process event while not added through tick
        if node_name in self.info_map:
            # keep date of last information received
            # use local time here as there is no guarantee that nodes will be time synchronized
            self.last_event_time = int(time())
            # last received extra_args are always applicable
            self.extra_args = payload['extra_args']
            # refresh internal information
            info = self.info_map[node_name]
            self.logger.trace(f'ProcessStatus.update_info: namespec={self.namespec} - updating info[{node_name}]={info}'
                              f' with payload={payload}')
            info['local_time'] = self.last_event_time
            info.update(payload)
            # re-evaluate description using Supervisor function
            info['description'] = self.update_description(info)
            # reset start time if process in a starting state
            new_state = info['state']
            if new_state in [ProcessStates.STARTING, ProcessStates.BACKOFF]:
                info['start'] = info['now']
            if new_state in STOPPED_STATES:
                info['stop'] = info['now']
            self.update_uptime(info)
            # always reset forced_state upon reception of new information
            if self.forced_state is not None:
                self.forced_state = None
                self.forced_reason = None
                self.logger.debug(f'ProcessStatus.update_info: namespec={self.namespec} - forced_state unset')
            # update / check running nodes
            self.update_status(node_name, new_state)
            self.logger.debug(f'ProcessStatus.update_info: namespec={self.namespec} '
                              f'- new info[{node_name}]={info}')
        else:
            self.logger.warn(f'ProcessStatus.update_info: namespec={self.namespec} - ProcessEvent rejected.'
                             f' Tick expected from {node_name}')

    def update_times(self, node_name: str, remote_time: float) -> None:
        """ Update the internal process information when a new tick is received from the remote Supvisors instance.

        :param node_name: the name of the node from which the tick has been received
        :param remote_time: the timestamp (seconds from Epoch) of the tick in the reference time of the node
        :return: None
        """
        if node_name in self.info_map:
            info = self.info_map[node_name]
            info['now'] = remote_time
            self.update_uptime(info)
            # it may have an impact on the description depending on the process state
            info['description'] = self.update_description(info)

    @staticmethod
    def update_uptime(info: Payload) -> None:
        """ Update uptime entry of a process information.

        :param info: the process information related to a given node
        :return: None
        """
        info['uptime'] = (info['now'] - info['start']) \
            if info['state'] in [ProcessStates.RUNNING, ProcessStates.STOPPING] else 0

    def invalidate_node(self, node_name: str) -> bool:
        """ Update the status of a process that was running on a lost / non-responsive node.

        :param node_name: the node from which no more information is received
        :return: True if process not running anywhere anymore
        """
        self.logger.debug(f'ProcessStatus.invalidate_node: namespec={self.namespec} '
                          f'- node_name={node_name} invalidated')
        failure = False
        if node_name in self.running_nodes:
            # update process status with a FATAL payload
            info = self.info_map[node_name]
            payload = {'now': info['now'], 'state': ProcessStates.FATAL, 'extra_args': info['extra_args'],
                       'expected': False, 'spawnerr': f'node {node_name} lost'}
            self.update_info(node_name, payload)
            failure = self.running_nodes == set()
        return failure

    def remove_node(self, node_name: str) -> bool:
        """ Update the status of a process that has been removed from the node, following an XML-RPC update_numprocs

        :param node_name: the node from which the process has been removed
        :return: True if the process is not defined anywhere anymore
        """
        del self.info_map[node_name]
        return self.info_map == {}

    def update_status(self, node_name: str, new_state: ProcessStates) -> None:
        """ Updates the state and list of running nodes iaw the new event.

        :param node_name: the node from which new information has been received
        :param new_state: the new state of the process on the considered node
        :return: None
        """
        # update running nodes list
        if new_state in STOPPED_STATES:
            self.running_nodes.discard(node_name)
        elif new_state in RUNNING_STATES:
            # replace if current state stopped-like, add otherwise
            if self.stopped():
                self.running_nodes = {node_name}
            else:
                self.running_nodes.add(node_name)
        # evaluate state iaw running nodes
        if self.conflicting():
            self._evaluate_conflict()
        else:
            # no conflict so there's at most one element running
            if self.running_nodes:
                self.state = self.info_map[list(self.running_nodes)[0]]['state']
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
        if LevelsByName.DEBG >= self.logger.level:
            log_trace = f'ProcessStatus.update_status: namespec={self.namespec} - is {self.state_string()}'
            if self.running_nodes:
                log_trace += f' on {list(self.running_nodes)}'
            self.logger.trace(log_trace)

    def _evaluate_conflict(self) -> None:
        """ Get a synthetic state if several processes are in a RUNNING-like state.

        :return: True if a conflict is detected, None otherwise
        """
        # several processes seems to be in a running state so that becomes tricky
        states = {self.info_map[running_node_name]['state'] for running_node_name in self.running_nodes}
        self.logger.debug(f'ProcessStatus.evaluate_conflict: {self.process_name} multiple states'
                          f' {[getProcessStateDescription(x) for x in states]} for nodes {list(self.running_nodes)}')
        # state synthesis done using the sorting of RUNNING_STATES
        self.state = self.running_state(states)

    @staticmethod
    def running_state(states: AbstractSet[int]) -> int:
        """ Return the first matching running state.
         The sequence defined in the Supervisor RUNNING_STATES is suitable here.

        :param states: a list of all process states of the present process over all nodes
        :return: a running state if found in list, STOPPING otherwise
        """
        # There may be STOPPING states in the list
        # In this state, the process is not removed yet from the running_nodes
        return next((state for state in list(RUNNING_STATES) + [ProcessStates.STOPPING]
                     if state in states), ProcessStates.UNKNOWN)
