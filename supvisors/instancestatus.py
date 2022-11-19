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

from copy import copy
from typing import Any, Dict, Tuple

from supervisor.loggers import Logger
from supervisor.xmlrpc import capped_int

from .process import ProcessStatus
from .supvisorsmapper import SupvisorsInstanceId
from .ttypes import SupvisorsInstanceStates, SupvisorsStates, InvalidTransition, NamedPidList, Payload
from .utils import TICK_PERIOD


class StateModes(object):

    def __init__(self, state: SupvisorsStates = SupvisorsStates.OFF, starting_jobs: bool = False,
                 stopping_jobs: bool = False):
        """ Initialization of the attributes.

        :param state: the FSM state
        :param starting_jobs: the Starter progress
        :param stopping_jobs: the Stopper progress
        """
        self.state: SupvisorsStates = state
        self.starting_jobs: bool = starting_jobs
        self.stopping_jobs: bool = stopping_jobs

    def __copy__(self):
        """ Create a new StateModes object with the same attributes.

        :return: a copy of this StateModes object
        """
        return type(self)(self.state, self.starting_jobs, self.stopping_jobs)

    def __eq__(self, other) -> bool:
        """ Check if the other object is equivalent.

        :param other: a StateModes object
        :return:
        """
        if isinstance(other, StateModes):
            return (self.state == other.state
                    and self.starting_jobs == other.starting_jobs
                    and self.stopping_jobs == other.stopping_jobs)

    def apply(self, fsm_state: SupvisorsStates = None, starter: bool = None, stopper: bool = None):
        """ Get the Supvisors instance state and modes with changes applied.

        :param fsm_state: the new FSM state
        :param starter: the Starter progress
        :param stopper: the Stopper progress
        :return: True if state and modes have changed, and the changed state and modes
        """
        if fsm_state is not None:
            self.state = fsm_state
        if starter is not None:
            self.starting_jobs = starter
        if stopper is not None:
            self.stopping_jobs = stopper

    def update(self, payload: Payload) -> None:
        """ Get the Supvisors instance state and modes with changes applied.

        :param payload: the Supvisors instance state and modes
        :return: None
        """
        self.state = SupvisorsStates(payload['fsm_statecode'])
        self.starting_jobs = payload['starting_jobs']
        self.stopping_jobs = payload['stopping_jobs']

    def serial(self):
        return {'fsm_statecode': self.state.value, 'fsm_statename': self.state.name,
                'starting_jobs': self.starting_jobs, 'stopping_jobs': self.stopping_jobs}


class SupvisorsInstanceStatus(object):
    """ Class defining the status of a Supvisors instance.

    Attributes:
        - supvisors_id: the parameters identifying where the Supvisors instance is expected to be running ;
        - state: the state of the Supvisors instance in SupvisorsInstanceStates ;
        - sequence_counter: the TICK counter ;
        - local_sequence_counter: the last TICK counter received from the local Supvisors instance ;
        - remote_time: the last date received from the Supvisors instance ;
        - local_time: the last date received from the Supvisors instance, in the local reference time ;
        - processes: the list of processes that are configured in the Supervisor of the Supvisors instance ;
        - state_modes: the Supvisors instance state and modes.
    """

    def __init__(self, supvisors_id: SupvisorsInstanceId, supvisors: Any):
        """ Initialization of the attributes. """
        self.supvisors = supvisors
        self.logger: Logger = supvisors.logger
        # attributes
        self.supvisors_id: SupvisorsInstanceId = supvisors_id
        self._state: SupvisorsInstanceStates = SupvisorsInstanceStates.UNKNOWN
        self.sequence_counter: int = 0
        self.local_sequence_counter: int = 0
        self.start_time: int = 0
        self.remote_time: float = 0.0
        self.local_time: float = 0.0
        self.processes: Dict[str, ProcessStatus] = {}
        # state and modes
        self.state_modes = StateModes()

    def reset(self):
        """ Reset the contextual part of the Supvisors instance.
        Silent and isolated Supvisors instances are not reset.

        :return: None
        """
        if self.state in [SupvisorsInstanceStates.CHECKING, SupvisorsInstanceStates.RUNNING]:
            # do NOT use state setter as transition may be rejected
            self._state = SupvisorsInstanceStates.UNKNOWN
        self.local_sequence_counter = 0
        self.remote_time = 0.0
        self.local_time = 0.0

    # accessors / mutators
    @property
    def identifier(self):
        """ Property for the 'identifier' attribute. """
        return self.supvisors_id.identifier

    @property
    def state(self):
        """ Property for the 'state' attribute. """
        return self._state

    @state.setter
    def state(self, new_state):
        if self._state != new_state:
            if self.check_transition(new_state):
                self._state = new_state
                self.logger.info(f'SupvisorsInstanceStatus.state: Supvisors={self.identifier} is {self.state.name}')
                if new_state in [SupvisorsInstanceStates.SILENT,
                                 SupvisorsInstanceStates.ISOLATING, SupvisorsInstanceStates.ISOLATED]:
                    self.logger.debug(f'SupvisorsInstanceStatus.state: FSM is OFF in Supvisors={self.identifier}')
                    self.state_modes.state = SupvisorsStates.OFF
            else:
                raise InvalidTransition(f'SupvisorsInstanceStatus.state: Supvisors={self.identifier} transition'
                                        f' rejected from {self.state.name} to {new_state.name}')

    # serialization
    def serial(self):
        """ Return a serializable form of the SupvisorsInstanceStatus. """
        payload = {'identifier': self.identifier,
                   'node_name': self.supvisors_id.host_name,
                   'port': self.supvisors_id.http_port,
                   'statecode': self.state.value, 'statename': self.state.name,
                   'sequence_counter': self.sequence_counter,
                   'remote_time': capped_int(self.remote_time),
                   'local_time': capped_int(self.local_time),
                   'loading': self.get_load()}
        payload.update(self.state_modes.serial())
        return payload

    # methods
    def update_state_modes(self, event: Payload) -> None:
        """ Update the Supvisors instance state and modes.

        :param event: the state or the mode updated
        :return: None
        """
        self.state_modes.update(event)

    def apply_state_modes(self, event: Payload) -> Tuple[bool, StateModes]:
        """ Apply the change on a copy of states_modes.

        :param event: the state or the mode updated
        :return: None
        """
        ref_state_modes = copy(self.state_modes)
        self.state_modes.apply(**event)
        return ref_state_modes != self.state_modes, self.state_modes

    def inactive(self, local_sequence_counter: int):
        """ Return True if the latest update was received more than INACTIVITY_TICKS ago.

        :param local_sequence_counter: the current local sequence counter
        :return: the inactivity status
        """
        return (self.state in [SupvisorsInstanceStates.CHECKING, SupvisorsInstanceStates.RUNNING]
                and (local_sequence_counter - self.local_sequence_counter) > self.supvisors.options.inactivity_ticks)

    def in_isolation(self):
        """ Return True if the Supvisors instance is in isolation. """
        return self.state in [SupvisorsInstanceStates.ISOLATING, SupvisorsInstanceStates.ISOLATED]

    def update_times(self, sequence_counter: int, remote_time: float, local_sequence_counter: int, local_time: float):
        """ Update the time attributes of the current object, including the time attributes of all its processes.

        :param sequence_counter: the TICK counter
        :param remote_time: the timestamp received from the Supvisors instance
        :param local_sequence_counter: the last TICK counter received from the local Supvisors instance
        :param local_time: the timestamp received from the Supvisors instance, in the local reference time
        :return:
        """
        if not self.start_time:
            # deduce start time from sequence_counter and TICK_PERIOD
            # approximation is good enough as it is just for Web UI display
            self.start_time = local_time - TICK_PERIOD * sequence_counter
        self.sequence_counter = sequence_counter
        self.local_sequence_counter = local_sequence_counter
        self.remote_time = remote_time
        self.local_time = local_time
        for process in self.processes.values():
            process.update_times(self.identifier, remote_time)

    def get_remote_time(self, local_time: float) -> float:
        """ Return the remote time corresponding to a local time.

        :param local_time: the reference time
        :return: the remote time
        """
        return self.remote_time + (local_time - self.local_time)

    def check_transition(self, new_state):
        """ Check that the state transition is valid. """
        return new_state in self._Transitions[self.state]

    # methods on processes
    def add_process(self, process):
        """ Add a new process to the process list.

        :param process: the process status to be added to the Supvisors instance
        :return: None
        """
        self.processes[process.namespec] = process

    def remove_process(self, process: ProcessStatus) -> None:
        """ Remove a process from the process list.

        :param process: the process to be removed from the Supvisors instance
        :return: None
        """
        del self.processes[process.namespec]

    def running_processes(self):
        """ Return the process running on the Supvisors instance.
        Here, 'running' means that the process state is in Supervisor RUNNING_STATES. """
        return [process for process in self.processes.values()
                if process.running_on(self.identifier)]

    def pid_processes(self) -> NamedPidList:
        """ Return the process running on the Supvisors instance and having a pid.
       Different from running_processes_on because it excludes the states STARTING and BACKOFF.

        :return: A list of process namespecs and PIDs
        """
        return [(process.namespec, process.info_map[self.identifier]['pid'])
                for process in self.processes.values()
                if process.pid_running_on(self.identifier)]

    def get_load(self) -> int:
        """ Return the load of the Supvisors instance, by summing the declared load of the processes running
        on the Supvisors instance.

        :return: the total load
        """
        instance_load = sum(process.rules.expected_load for process in self.running_processes())
        self.logger.trace(f'SupvisorsInstanceStatus.get_load: Supvisors={self.identifier} load={instance_load}')
        return instance_load

    # dictionary for transitions
    _Transitions = {SupvisorsInstanceStates.UNKNOWN: (SupvisorsInstanceStates.CHECKING,
                                                      SupvisorsInstanceStates.ISOLATING,
                                                      SupvisorsInstanceStates.SILENT),
                    SupvisorsInstanceStates.CHECKING: (SupvisorsInstanceStates.RUNNING,
                                                       SupvisorsInstanceStates.ISOLATING,
                                                       SupvisorsInstanceStates.SILENT),
                    SupvisorsInstanceStates.RUNNING: (SupvisorsInstanceStates.SILENT,
                                                      SupvisorsInstanceStates.ISOLATING,
                                                      SupvisorsInstanceStates.CHECKING),
                    SupvisorsInstanceStates.SILENT: (SupvisorsInstanceStates.CHECKING,
                                                     SupvisorsInstanceStates.ISOLATING),
                    SupvisorsInstanceStates.ISOLATING: (SupvisorsInstanceStates.ISOLATED,),
                    SupvisorsInstanceStates.ISOLATED: ()
                    }
