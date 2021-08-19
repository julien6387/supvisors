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

from typing import Dict

from supervisor.loggers import Logger
from supervisor.xmlrpc import capped_int

from .process import ProcessStatus
from .ttypes import AddressStates, InvalidTransition


class AddressStatus(object):
    """ Class defining the status of a Supvisors instance.

    Attributes:
    - node_name: the node where the Supervisor instance is expected to be running,
    - state: the state of the Supervisor instance in AddressStates,
    - sequence_counter: the TICK counter,
    - remote_time: the last date received from the Supvisors instance,
    - local_time: the last date received from the Supvisors instance, in the local reference time,
    - processes: the list of processes that are available on this address. """

    # Timeout in seconds from which Supvisors considers that a node is inactive if no tick has been received in the gap.
    # TODO: could be an option in configuration file
    INACTIVITY_TIMEOUT = 10

    def __init__(self, node_name: str, logger: Logger):
        """ Initialization of the attributes. """
        # keep a reference to the common logger
        self.logger: Logger = logger
        # attributes
        self.node_name: str = node_name
        self._state: AddressStates = AddressStates.UNKNOWN
        self.sequence_counter: int = 0
        self.remote_time: int = 0
        self.local_time: int = 0
        self.processes: Dict[str, ProcessStatus] = {}

    def reset(self):
        """ Reset the contextual part of the node.
        Silent and isolated node are not reset.

        :return: None
        """
        if self.state in [AddressStates.CHECKING, AddressStates.RUNNING]:
            # do NOT use state setter as transition may be rejected
            self._state = AddressStates.UNKNOWN
        self.remote_time = 0
        self.local_time = 0

    # accessors / mutators
    @property
    def state(self):
        """ Property for the 'state' attribute. """
        return self._state

    @state.setter
    def state(self, new_state):
        if self._state != new_state:
            if self.check_transition(new_state):
                self._state = new_state
                self.logger.info('AddressStatus.state: {} is {}'.format(self.node_name, self.state.name))
            else:
                raise InvalidTransition('AddressStatus.state: {} transition rejected from {} to {}'
                                        .format(self.node_name, self.state.name, new_state.name))

    # serialization
    def serial(self):
        """ Return a serializable form of the AddressStatus. """
        return {'address_name': self.node_name,
                'statecode': self.state.value,
                'statename': self.state.name,
                'sequence_counter': self.sequence_counter,
                'remote_time': capped_int(self.remote_time),
                'local_time': capped_int(self.local_time),
                'loading': self.get_loading()}

    # methods
    def inactive(self, current_time: float):
        """ Return True if the latest update was received more than INACTIVITY_TIMEOUT seconds ago.

        :param current_time: the current time
        :return: the inactivity status
        """
        return (self.state in [AddressStates.CHECKING, AddressStates.RUNNING]
                and (current_time - self.local_time) > self.INACTIVITY_TIMEOUT)

    def in_isolation(self):
        """ Return True if the Supvisors instance is in isolation. """
        return self.state in [AddressStates.ISOLATING, AddressStates.ISOLATED]

    def update_times(self, sequence_counter: int, remote_time: int, local_time: int):
        """ Update the time attributes of the AddressStatus and of all the processes running on it. """
        self.sequence_counter = sequence_counter
        self.remote_time = remote_time
        self.local_time = local_time
        for process in self.processes.values():
            process.update_times(self.node_name, remote_time)

    def check_transition(self, new_state):
        """ Check that the state transition is valid. """
        return new_state in self._Transitions[self.state]

    # methods on processes
    def add_process(self, process):
        """ Add a new process to the process list. """
        self.processes[process.namespec] = process

    def running_processes(self):
        """ Return the process running on the address.
        Here, 'running' means that the process state is in Supervisor RUNNING_STATES. """
        return [process for process in self.processes.values()
                if process.running_on(self.node_name)]

    def pid_processes(self):
        """ Return the process running on the address and having a pid.
       Different from running_processes_on because it excludes the states STARTING and BACKOFF. """
        return [(process.namespec, process.info_map[self.node_name]['pid'])
                for process in self.processes.values()
                if process.pid_running_on(self.node_name)]

    def get_loading(self) -> int:
        """ Return the loading of the node, by summing the declared load of the processes running on that node.

        :return: the total loading
        """
        node_load = sum(process.rules.expected_load for process in self.running_processes())
        self.logger.debug('AddressStatus.get_loading: node_name={} node_load={}'.format(self.node_name, node_load))
        return node_load

    # dictionary for transitions
    _Transitions = {AddressStates.UNKNOWN: (AddressStates.CHECKING, AddressStates.ISOLATING, AddressStates.SILENT),
                    AddressStates.CHECKING: (AddressStates.RUNNING, AddressStates.ISOLATING, AddressStates.SILENT),
                    AddressStates.RUNNING: (AddressStates.SILENT, AddressStates.ISOLATING),
                    AddressStates.SILENT: (AddressStates.CHECKING, AddressStates.ISOLATING),
                    AddressStates.ISOLATING: (AddressStates.ISOLATED,),
                    AddressStates.ISOLATED: ()
                    }
