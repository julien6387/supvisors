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

from typing import AbstractSet, Any, Optional

from supervisor.options import make_namespec
from supervisor.rpcinterface import SupervisorNamespaceRPCInterface
from supervisor.states import RUNNING_STATES, STOPPED_STATES

from supvisors.ttypes import Payload, ProcessStates, RunningFailureStrategies
from supvisors.utils import *


class ProcessRules(object):
    """ Defines the rules for starting a process, iaw rules file.

    Attributes are:
        - addresses: the nodes where the process can be started (all by default),
        - hash_addresses: when # rule is used, the process can be started on one of these nodes (to be resolved),
        - start_sequence: the order in the starting sequence of the application,
        - stop_sequence: the order in the stopping sequence of the application,
        - required: a status telling if the process is required within the application,
        - wait_exit: a status telling if Supvisors has to wait for the process to exit before triggering the next phase in the starting sequence of the application,
        - expected_loading: the expected loading of the process on the considered hardware (can be anything at the user discretion: CPU, RAM, etc),
        - running_failure_strategy: supersedes the application rule and defines the strategy to apply when the process crashes when the application is running.
    """

    def __init__(self, supvisors: Any) -> None:
        """ Initialization of the attributes.

        :param supvisors: the global Supvisors structure.
        """
        # TODO: think about adding a period for tasks (period > startsecs / autorestart = False)
        # keep a reference to the Supvisors data
        self.supvisors = supvisors
        supvisors_shortcuts(self, ['info_source', 'logger'])
        # attributes
        self.addresses = ['*']
        self.hash_addresses = None
        self.start_sequence = 0
        self.stop_sequence = 0
        self.required = False
        self.wait_exit = False
        self.expected_loading = 1
        self.running_failure_strategy = RunningFailureStrategies.CONTINUE

    def check_dependencies(self, namespec: str) -> None:
        """ Update rules after they have been read from the rules file.
        A required process that is not in the starting sequence is forced to optional.
        Supervisor autorestart is not compatible with RunningFailureStrategy STOP / RESTART.

        :param namespec: the namespec of the program considered.
        """
        # required MUST have start_sequence, so force to optional if
        # start_sequence is not set
        if self.required and self.start_sequence == 0:
            self.logger.warn('ProcessRules.check_dependencies: {} - required forced to False because '
                             'no start_sequence defined'.format(namespec))
            self.required = False
        # disable autorestart when RunningFailureStrategies is not CONTINUE
        if self.running_failure_strategy != RunningFailureStrategies.CONTINUE:
            if self.info_source.autorestart(namespec):
                self.info_source.disable_autorestart(namespec)
                self.logger.warn('ProcessRules.check_dependencies: {} - autorestart disabled due to '
                                 'running failure strategy {}'
                                 .format(namespec,
                                         RunningFailureStrategies.to_string(self.running_failure_strategy)))

    def __str__(self) -> str:
        """ Get the process rules as string.

        :return: the printable process rules
        """
        return 'addresses={} hash_addresses={} start_sequence={} stop_sequence={} required={}' \
               ' wait_exit={} expected_loading={} running_failure_strategy={}'. \
            format(self.addresses, self.hash_addresses,
                   self.start_sequence, self.stop_sequence, self.required,
                   self.wait_exit, self.expected_loading,
                   RunningFailureStrategies.to_string(self.running_failure_strategy))

    def serial(self) -> Payload:
        """ Get a serializable form of the process rules.
        hash_addresses is not exported as used internally to resolve addresses.

        :return: the process rules in a dictionary
        """
        return {'addresses': self.addresses,
                'start_sequence': self.start_sequence,
                'stop_sequence': self.stop_sequence,
                'required': self.required,
                'wait_exit': self.wait_exit,
                'expected_loading': self.expected_loading,
                'running_failure_strategy': RunningFailureStrategies.to_string(self.running_failure_strategy)}


class ProcessStatus(object):
    """ Class defining the status of a process of Supvisors.

    Attributes are:
        - application_name: the application name, or group name from a Supervisor point of view,
        - process_name: the process name,
        - state: the synthetic state of the process, same enumeration as Supervisor,
        - expected_exit: a status telling if the process has exited expectantly,
        - last_event_time: the local date of the last information received,
        - extra_args: the additional arguments passed to the command line,
        - addresses: the list of all addresses where the process is running,
        - infos: a process info dictionary for each address (running or not),
        - rules: the rules related to this process.
    """

    def __init__(self, application_name: str, process_name: str, supvisors: Any) -> None:
        """ Initialization of the attributes.

        :param application_name: the name of the application the process belongs to
        :param process_name: the name of the process
        :param supvisors: the global Supvisors structure
        """
        # keep a reference of the Supvisors data
        self.supvisors = supvisors
        supvisors_shortcuts(self, ['address_mapper', 'info_source', 'logger', 'options'])
        # copy to self the Supervisor method use to describe the process status
        ProcessStatus.update_description = SupervisorNamespaceRPCInterface._interpretProcessInfo
        # attributes
        self.application_name = application_name
        self.process_name = process_name
        self._state = ProcessStates.UNKNOWN
        self.expected_exit = True
        self.last_event_time = 0
        self._extra_args = ''
        # expected one single applicable address
        self.addresses = set()  # addresses
        self.infos = {}  # address: processInfo
        # rules part
        self.rules = ProcessRules(supvisors)

    @property
    def state(self) -> int:
        """ Getter of state attribute.

        :return: the process state
        """
        return self._state

    @state.setter
    def state(self, new_state: int) -> None:
        """ Setter of state attribute.

        :param new_state: the new process state
        :return: None
        """
        if self._state != new_state:
            self._state = new_state
            self.logger.info('ProcessStatus.state: Process {} is {}'.format(self.namespec(), self.state_string()))

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
            self.info_source.update_extra_args(self.namespec(), new_args)

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
                'addresses': list(self.addresses),
                'extra_args': self.extra_args}

    # access
    def namespec(self) -> str:
        """ Get the process namespec from application and process names.

        :return: the process namespec
        """
        return make_namespec(self.application_name, self.process_name)

    def crashed(self) -> bool:
        """ Return True if the process has crashed or has exited unexpectedly.

        :return: the crash status of the process
        """
        return (self.state == ProcessStates.FATAL or (self.state == ProcessStates.EXITED and not self.expected_exit))

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

    def running_on(self, address: str) -> bool:
        """ Return True if the process is running on node.

        :param address: the node name
        :return: the running status of the process on the considered node
        """
        return self.running() and address in self.addresses

    def pid_running_on(self, address: str) -> bool:
        """ Return True if process is RUNNING on address.
        Different from running_on as it considers only the RUNNING state and not STARTING or BACKOFF.
        This is used by the statistics module that requires an existing PID.

        :param address: the node name
        :return: the true running status of the process on the considered node
        """
        return self.state == ProcessStates.RUNNING and address in self.addresses

    def conflicting(self) -> bool:
        """ Return True if the process is in a conflicting state (more than one instance running).

        :return: the conflict status of the process
        """
        return len(self.addresses) > 1

    # methods
    def state_string(self) -> str:
        """ Get the process state as a string.

        :return: the process state as a string
        """
        return ProcessStates.to_string(self.state)

    def add_info(self, address: str, process_info: Payload) -> None:
        """ Insert a new process information in internal list.

        :param address: the name of the node from which the information has been received
        :param process_info: a subset of the dict received from Supervisor.getProcessInfo.
        :return: None
        """
        # keep date of last information received
        # use local time here as there is no guarantee that addresses will be time synchronized
        self.last_event_time = int(time())
        # store information
        info = self.infos[address] = process_info
        info['local_time'] = self.last_event_time
        self.update_uptime(info)
        self.logger.debug('ProcessStatus.add_info: adding {} at {}'.format(info, address))
        # reset extra_args
        info['extra_args'] = ''
        self.extra_args = ''
        # update process status
        self.update_status(address, info['state'], info['expected'])
        # fix address rule iaw '#' option
        if self.rules.hash_addresses:
            self.resolve_hash_address(address)

    def resolve_hash_address(self, address: str) -> None:
        """ When a '#' is set in program rules, an association has to be done between the procnumber of the process
        and the index of the process_info address in the applicable address list.
        In this case, rules.hash_addresses is expected to contain:
            - either ['*'] when all nodes are applicable
            - or any subset of these nodes.

        :param address: the node from which the process information has been received
        :return: None
        """
        procnumber = self.options.procnumbers[self.process_name]
        self.logger.debug('ProcessStatus.resolve_hash_address: namespec={} address={} procnumber={}'
                          .format(self.namespec(), address, procnumber))
        if '*' in self.rules.hash_addresses:
            # all nodes defined in the supvisors section of the supervisor configuration file are applicable
            if self.address_mapper.addresses.index(address) == procnumber:
                self.rules.addresses = [address]
        else:
            # the subset of applicable nodes is the second element of rules addresses
            if address in self.rules.hash_addresses:
                if self.rules.hash_addresses.index(address) == procnumber:
                    self.rules.addresses = [address]

    def update_info(self, address: str, payload: Payload) -> None:
        """ Update the internal process information with event payload.

        :param address: the name of the node from which the information has been received
        :param payload: the process information used to refresh internal data
        :return: None
        """
        # do not consider process event while not added through tick
        if address in self.infos:
            # keep date of last information received
            # use local time here as there is no guarantee that addresses will be time synchonized
            self.last_event_time = int(time())
            # last received extra_args are always applicable
            self.extra_args = payload['extra_args']
            # refresh internal information
            info = self.infos[address]
            info['local_time'] = self.last_event_time
            self.logger.trace('ProcessStatus.update_info: inserting {} into {} at {}'
                              .format(payload, info, address))
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
            # update / check running addresses
            self.update_status(address, new_state, info['expected'])
            self.logger.debug('ProcessStatus.update_info: new process info: {}'.format(info))
        else:
            self.logger.warn('ProcessStatus.update_info: ProcessEvent rejected for {}. wait for tick from {}'
                             .format(self.process_name, address))

    def update_times(self, address: str, remote_time: int) -> None:
        """ Update the internal process information when a new tick is received from the remote Supvisors instance.

        :param address: the name of the node from which the tick has been received
        :param remote_time: the timestamp (seconds from Epoch) of the tick in the reference time of the node
        :return: None
        """
        if address in self.infos:
            info = self.infos[address]
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
            if info['state'] in [ProcessStates.RUNNING, ProcessStates.STOPPING] \
            else 0

    def invalidate_address(self, address: str, is_master: bool) -> None:
        """ Update the status of a process that was running on a lost / non-responsive node.
        If the present process was running on this node, an action has to be taken by the Supvisors master.

        :param address: the node from which no more information is received
        :param is_master: True if the local node is the Supvisors master
        :return: None
        """
        self.logger.debug('ProcessStatus.invalidate_address: {} in validate on {} / {}'
                          .format(self.namespec(), self.addresses, address))
        # reassign the difference between current set and parameter
        if address in self.addresses:
            self.addresses.remove(address)
        if address in self.infos:
            # force process info to UNKNOWN at address
            self.infos[address]['state'] = ProcessStates.UNKNOWN
        # check if conflict still applicable
        if not self.evaluate_conflict():
            if len(self.addresses) == 1:
                # if process is running on only one address,
                # the global state is the state of this process
                self.state = next(self.infos[address]['state'] for address in self.addresses)
            elif self.running():
                # addresses is empty for a running process
                # action expected to fix the inconsistency
                self.logger.warn('ProcessStatus.invalidate_address: no more node for running process {}'
                                 .format(self.namespec()))
                self.state = ProcessStates.FATAL
                # notify the failure to dedicated handler, only if local address is master
                if is_master:
                    self.supvisors.failure_handler.add_default_job(self)
            elif self.state == ProcessStates.STOPPING:
                # STOPPING is the last state received before the address is lost
                # consider STOPPED now
                self.state = ProcessStates.STOPPED
        else:
            self.logger.debug('ProcessStatus.invalidate_address: process {} still in conflict after node invalidation'
                              .format(self.namespec()))

    def update_status(self, address: str, new_state: int, expected: bool) -> None:
        """ Updates the state and list of running address iaw the new event.

        :param address: the node from which new information has been received
        :param new_state: the new state of the process on the considered node
        :param expected: the exit status of the process (only valid for an EXITED state)
        :return: None
        """
        # update addresses list
        if new_state in STOPPED_STATES:
            self.addresses.discard(address)
        elif new_state in RUNNING_STATES:
            # replace if current state stopped-like, add otherwise
            if self.stopped():
                self.addresses = {address}
            else:
                self.addresses.add(address)
        # evaluate state iaw running addresses
        if not self.evaluate_conflict():
            # if zero element, state is the state of the program addressed
            if self.addresses:
                self.state = next(self.infos[address]['state'] for address in self.addresses)
                self.expected_exit = True
            else:
                self.state = new_state
                self.expected_exit = expected
        # log the new status
        log_trace = 'ProcessStatus.update_status: Process {} is {}'.format(self.namespec(), self.state_string())
        if self.addresses:
            log_trace += ' on {}'.format(list(self.addresses))
        self.logger.debug(log_trace)

    def evaluate_conflict(self) -> Optional[bool]:
        """ Get a synthetic state if several processes are in a RUNNING-like state.

        :return: True if a conflict is detected, None otherwise
        """
        if self.conflicting():
            # several processes seems to be in a running state so that becomes tricky
            states = {self.infos[address]['state'] for address in self.addresses}
            self.logger.debug('ProcessStatus.evaluate_conflict: {} multiple states {} for nodes {}'
                              .format(self.process_name,
                                      [ProcessStates.to_string(x) for x in states],
                                      list(self.addresses)))
            # state synthesis done using the sorting of RUNNING_STATES
            self.state = self.running_state(states)
            return True

    @staticmethod
    def running_state(states: AbstractSet[int]) -> int:
        """ Return the first matching running state.
         The sequence defined in the Supervisor RUNNING_STATES is suitable here.

        :param states: a list of all process states of the present process over all nodes
        :return: a running state if found in list, UNKNOWN otherwise
        """
        return next((state for state in RUNNING_STATES if state in states), ProcessStates.UNKNOWN)
