#!/usr/bin/python
#-*- coding: utf-8 -*-

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

from supervisors.types import AddressStates, InvalidTransition


class AddressStatus(object):
    """ Class defining the status of a Supervisors instance.

    Attributes:
    - address: the address where the Supervisor instance is expected to be running,
    - state: the state of the Supervisor instance in AddressStates,
    - checked: a status telling if Supervisors has already checked that it is allowed to deal with the remote Supervisors in,
    - remote_time: the last date received from the Supervisors instance,
    - local_time: the last date received from the Supervisors instance, in the local reference time,
    - processes: the list of processes that are available on this address. """

    def __init__(self, address, logger):
        """ Initialization of the attributes. """
        # keep a reference to the common logger
        self.logger = logger
        # attributes
        self.address = address
        self._state = AddressStates.UNKNOWN
        self.remote_time = 0
        self.local_time = 0
        self.checked = False
        self.processes = {}

    # accessors / mutators
    @property
    def state(self):
        """ Property for the 'state' attribute. """
        return self._state

    @state.setter
    def state(self, newState):
        if self._state != newState:
            if self.check_transition(newState):
                self._state = newState
                self.logger.info('Address {} is {}'.format(self.address, self.state_string()))
            else:
                raise InvalidTransition('Address: transition rejected {} to {}'.format(self.state_string(), AddressStates._to_string(newState)))

    # serialization
    def to_json(self):
        """ Return a JSON-serializable form of the AddressStatus. """
        return {'address': self.address, 'state': self.state_string(), 'checked': self.checked,
            'remote_time': self.remote_time, 'local_time': self.local_time }

    # methods
    def state_string(self):
        """ Return the application state as a string. """
        return AddressStates._to_string(self.state)

    def in_isolation(self):
        """ Return True if the Supervisors instance is in isolation. """
        return self.state in [AddressStates.ISOLATING, AddressStates.ISOLATED]

    def update_times(self, remote_time, local_time):
        """ Update the last times attributes. """
        self.remote_time = remote_time
        self.local_time = local_time

    def check_transition(self, new_state):
        """ Check that the state transition is valid. """
        return new_state in self._Transitions[self.state]

    # methods on processes
    def add_process(self, process):
        """ Add a new process to the process list. """
        self.processes[process.namespec()] = process

    def running_processes(self):
        """ Return the process running on the address.
        Here, 'running' means that the process state is in Supervisor RUNNING_STATES. """
        return [process for process in self.processes.values() if process.running_on(self.address)]

    def pid_processes(self):
        """ Return the process running on the address and having a pid.
       Different from running_processes_on because it excludes the states STARTING and BACKOFF """
        return [(process.namespec(), process.processes[self.address]['pid'])
            for process in self.processes.values() if process.pid_running_on(self.address)]

    def loading(self):
        """ Return the loading of the address, by summing the declared loading of the processes running on that address """
        loading = sum(process.rules.expected_loading for process in self.running_processes())
        self.logger.debug('address={} loading={}'.format(self.address, loading))
        return loading

    # dictionary for transitions
    _Transitions = {
        AddressStates.UNKNOWN: (AddressStates.RUNNING, AddressStates.ISOLATING, AddressStates.SILENT),
        AddressStates.RUNNING: (AddressStates.SILENT, AddressStates.ISOLATING),
        AddressStates.SILENT: (AddressStates.RUNNING, ),
        AddressStates.ISOLATING: (AddressStates.ISOLATED, ), 
        AddressStates.ISOLATED: ()
    }
