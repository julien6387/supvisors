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
from typing import Any, Dict

from supervisor.loggers import Logger
from supervisor.xmlrpc import capped_int

from .internal_com.mapper import SupvisorsInstanceId
from .process import ProcessStatus
from .ttypes import SupvisorsInstanceStates, InvalidTransition, Payload
from .utils import TICK_PERIOD


class SupvisorsTimes:

    def __init__(self, identifier: str, logger: Logger):
        """ Storage of counter, clock and time received from the remote Supvisors instance.
        Upon reception of a remote TICK, the correspondence is made with the local counter, clock and time.

        All calculations must be performed using the monotonic clock times, and in the local Supvisors reference.
        Times are only used for display on the Web UI.

        Attributes:
            - identifier: the identifier of the remote Supvisors instance ;
            - remote_sequence_counter: the TICK counter ;
            - remote_mtime: the last monotonic time received from the remote Supvisors instance ;
            - remote_time: the last time received from the remote Supvisors instance ;
            - local_sequence_counter: remote_sequence_counter in local counter reference ;
            - local_monotonic: remote_monotonic in local monotonic time reference ;
            - local_mtime: remote_time in local time reference ;
            - start_local_mtime: the approximate start time of the remote Supvisors instance,
                in local monotonic time reference.
        """
        self.identifier: str = identifier
        self.logger: Logger = logger
        # counter and times of the remote Supvisors instance
        self.remote_sequence_counter: int = 0
        self.remote_mtime: float = 0.0
        self.remote_time: float = 0.0
        # corresponding counter and times of the local Supvisors instance
        self.local_sequence_counter: int = 0
        self.local_mtime: float = 0.0
        self.local_time: float = 0.0
        # approximate startup monotonic time of the remote Supvisors instance (in the local monotonic time reference)
        # will be used to display the remote Supvisors instance uptime
        self.start_local_mtime: float = -1.0

    @property
    def capped_remote_time(self) -> int:
        """ Return a remote time compliant with XML-RPC limits.
        The xml-rpc integer type will be saturated in jan 2038 ("year 2038 problem").
        """
        return capped_int(self.remote_time)

    @property
    def capped_local_time(self) -> int:
        """ Return a local time compliant with XML-RPC limits.
        The xml-rpc integer type will be saturated in jan 2038 ("year 2038 problem").
        """
        return capped_int(self.local_time)

    def get_current_uptime(self) -> float:
        """ Return the duration since the approximate stat time of the remote Supvisors instance. """
        return time.monotonic() - self.start_local_mtime

    def get_current_remote_time(self, local_mtime: float) -> float:
        """ Return the current time of the remote Supvisors instance.

        Add the last remote time received to the monotonic duration from the last clock time stored.

        :param local_mtime: the monotonic timestamp reference.
        :return: the remote time.
        """
        return self.remote_time + (local_mtime - self.local_mtime)

    def update(self, remote_sequence_counter: int, remote_mtime: float, remote_time: float,
               local_sequence_counter: int):
        """ Update the time counters of the remote Supvisors instance, and make correspondence with self time.

        :param remote_sequence_counter: the TICK counter received from the remote Supvisors instance.
        :param remote_mtime: the monotonic timestamp received from the remote Supvisors instance.
        :param remote_time: the timestamp received from the remote Supvisors instance.
        :param local_sequence_counter: the latest sequence counter received from the local Supvisors instance.
        :return: None.
        """
        if local_sequence_counter < 0:
            # remote Supvisors instance is local Supvisors instance, so use the same input data
            local_sequence_counter = remote_sequence_counter
            local_mtime = remote_mtime
            local_time = remote_time
        else:
            local_mtime = time.monotonic()
            local_time = time.time()
        # check sequence counter to identify stealth supervisor restart
        # (only for remote, cannot happen with local)
        if remote_sequence_counter < self.remote_sequence_counter:
            self.logger.warn(f'SupvisorsTimes.update: stealth restart of Supvisors={self.identifier}')
            # Force Supvisors inactivity by resetting its local_sequence_counter
            # The Supvisors periodical check will handle the node invalidation
            local_sequence_counter = 0
            self.start_local_mtime = -1
        # update remote attributes
        self.remote_sequence_counter = remote_sequence_counter
        self.remote_mtime = remote_mtime
        self.remote_time = remote_time
        # update local correspondent attributes
        self.local_sequence_counter = local_sequence_counter
        self.local_mtime = local_mtime
        self.local_time = local_time
        # approximation of the remote Supvisors instance startup clock (in local clock reference)
        #     from remote_sequence_counter and TICK_PERIOD
        #     good enough as it is just for Web UI display
        if self.start_local_mtime < 0:
            self.start_local_mtime = local_mtime - TICK_PERIOD * remote_sequence_counter

    def serial(self):
        """ Return a serializable form of the SupvisorsTimes instance. """
        return {'remote_sequence_counter': self.remote_sequence_counter,
                'remote_time': self.capped_remote_time,
                'remote_mtime': self.remote_mtime,
                'local_sequence_counter': self.local_sequence_counter,
                'local_time': self.capped_local_time,
                'local_mtime': self.local_mtime}


class SupvisorsInstanceStatus:
    """ Class defining the status of a Supvisors instance.

    Attributes:
        - supvisors_id: the parameters identifying where the Supvisors instance is expected to be running ;
        - state: the state of the Supvisors instance in SupvisorsInstanceStates ;
        - time: the counter, time and clock of the remote Supvisors instance associated to the local ones ;
        - processes: the list of processes that are configured in the Supervisor of the Supvisors instance.
    """

    def __init__(self, supvisors_id: SupvisorsInstanceId, supvisors: Any):
        """ Initialization of the attributes. """
        self.supvisors = supvisors
        # attributes
        self.supvisors_id: SupvisorsInstanceId = supvisors_id
        self._state: SupvisorsInstanceStates = SupvisorsInstanceStates.STOPPED
        self.times: SupvisorsTimes = SupvisorsTimes(self.identifier, self.logger)
        self.processes: Dict[str, ProcessStatus] = {}
        # the local instance may use the process statistics collector
        self.stats_collector = None
        if supvisors.mapper.local_identifier == self.identifier:
            # copy the process collector reference
            if supvisors.options.process_stats_enabled:
                self.stats_collector = supvisors.stats_collector

    @property
    def logger(self) -> Logger:
        """ Shortcut to the Supvisors logger. """
        return self.supvisors.logger

    # accessors / mutators
    @property
    def identifier(self):
        """ Property getter for the 'identifier' attribute of the Supvisors instance. """
        return self.supvisors_id.identifier

    @property
    def usage_identifier(self):
        """ Property getter for the representation of the Supvisors instance. """
        return str(self.supvisors_id)

    @property
    def state(self) -> SupvisorsInstanceStates:
        """ Property getter for the Supvisors instance 'state' attribute. """
        return self._state

    @state.setter
    def state(self, new_state: SupvisorsInstanceStates):
        """ Property setter for the Supvisors instance 'state' attribute. """
        if self._state != new_state:
            if not self.check_transition(new_state):
                raise InvalidTransition(f'SupvisorsInstanceStatus.state: Supvisors={self.usage_identifier}'
                                        f' transition rejected from {self.state.name} to {new_state.name}')
            self._state = new_state
            self.logger.warn(f'SupvisorsInstanceStatus.state: Supvisors={self.usage_identifier} is {self.state.name}')
            # update the information in the local state & modes
            self.supvisors.state_modes.update_instance_state(self.identifier, new_state)

    @property
    def isolated(self) -> bool:
        """ Return True if the Supvisors instance is isolated. """
        return self.state == SupvisorsInstanceStates.ISOLATED

    @property
    def sequence_counter(self):
        """ the remote sequence counter will be used as a reference outside of this class. """
        return self.times.remote_sequence_counter

    # serialization
    def serial(self) -> Payload:
        """ Return a serializable form of the SupvisorsInstanceStatus. """
        payload = {'identifier': self.identifier,
                   'nick_identifier': self.supvisors_id.nick_identifier,
                   'node_name': self.supvisors_id.host_id,
                   'port': self.supvisors_id.http_port,
                   'statecode': self.state.value, 'statename': self.state.name,
                   'loading': self.get_load(),
                   'process_failure': self.has_error()}
        payload.update(self.times.serial())
        return payload

    # methods
    def has_active_state(self) -> bool:
        """ Return True if the instance status is in an active state.

        :return: the activity status.
        """
        return self.state in [SupvisorsInstanceStates.CHECKING, SupvisorsInstanceStates.CHECKED,
                              SupvisorsInstanceStates.RUNNING, SupvisorsInstanceStates.FAILED]

    def is_inactive(self, local_sequence_counter: int) -> bool:
        """ Return True if the latest update was received more than INACTIVITY_TICKS ago.

        :param local_sequence_counter: the current local sequence counter.
        :return: the inactivity status.
        """
        # NOTE: by design, there will be always a gap of 1 between the local_sequence_counter and the latest
        #       local_sequence_counter of the remote Supvisors instance, unless the remote Supvisors instance is stopped
        #       or unreachable, because the periodic check is performed on the new local TICK.
        counter_diff = local_sequence_counter - self.times.local_sequence_counter
        return self.has_active_state() and counter_diff > self.supvisors.options.inactivity_ticks

    def update_tick(self, remote_sequence_counter: int, remote_mtime: float, remote_time: float,
                    local_sequence_counter: int = -1):
        """ Update the time attributes of the current object, including the time attributes of all its processes.

        :param remote_sequence_counter: the TICK counter received from the Supvisors instance ;
        :param remote_time: the timestamp received from the Supvisors instance ;
        :param remote_mtime: the timestamp received from the Supvisors instance ;
        :param local_sequence_counter: the last TICK counter received from the local Supvisors instance ;
        :return: None
        """
        self.logger.debug(f'SupvisorsInstanceStatus.update_tick: update Supvisors={self.usage_identifier}' 
                          f' with sequence_counter={remote_sequence_counter} remote_time={remote_time}'
                          f' remote_mtime={remote_mtime} local_sequence_counter={local_sequence_counter}')
        self.times.update(remote_sequence_counter, remote_mtime, remote_time, local_sequence_counter)
        # update all process times
        for process in self.processes.values():
            process.update_times(self.identifier, self.times.remote_mtime, self.times.remote_time)

    def check_transition(self, new_state):
        """ Check that the state transition is valid. """
        return new_state in self._Transitions[self.state]

    # methods on processes
    def add_process(self, process: ProcessStatus) -> None:
        """ Add a new process to the process list.

        :param process: the process status to be added to the Supvisors instance
        :return: None
        """
        self.processes[process.namespec] = process
        # update the collector withe process if it is already running
        if self.stats_collector:
            pid = process.get_pid(self.identifier)
            if pid > 0:
                self.stats_collector.send_pid(process.namespec, pid)

    def update_process(self, process: ProcessStatus) -> None:
        """ Upon a process state change, check if a pid is available to update the collector.

        :param process: the process status that has been updated
        :return: None
        """
        if self.stats_collector:
            pid = process.get_pid(self.identifier)
            self.stats_collector.send_pid(process.namespec, pid)

    def remove_process(self, process: ProcessStatus) -> None:
        """ Remove a process from the process list.

        :param process: the process to be removed from the Supvisors instance
        :return: None
        """
        del self.processes[process.namespec]
        # update the collector
        if self.stats_collector:
            self.stats_collector.send_pid(process.namespec, 0)

    def running_processes(self):
        """ Return the process running on the Supvisors instance.
        Here, 'running' means that the process state is in Supervisor RUNNING_STATES. """
        return [process for process in self.processes.values()
                if process.running_on(self.identifier)]

    def get_load(self) -> int:
        """ Return the load of the Supvisors instance, by summing the declared load of the processes running
        on the Supvisors instance.

        :return: the total load
        """
        instance_load = sum(process.rules.expected_load for process in self.running_processes())
        self.logger.trace(f'SupvisorsInstanceStatus.get_load: Supvisors={self.usage_identifier} load={instance_load}')
        return instance_load

    def has_error(self) -> bool:
        """ Return True if any process managed by the local Supervisor is in failure.

        :return: the error status
        """
        return (self.state == SupvisorsInstanceStates.RUNNING
                and any(process.crashed(self.identifier)
                        for process in self.processes.values()))

    # dictionary for transitions
    _Transitions = {SupvisorsInstanceStates.STOPPED: (SupvisorsInstanceStates.CHECKING,),
                    SupvisorsInstanceStates.CHECKING: (SupvisorsInstanceStates.STOPPED,
                                                       SupvisorsInstanceStates.CHECKED,
                                                       SupvisorsInstanceStates.FAILED),
                    SupvisorsInstanceStates.CHECKED: (SupvisorsInstanceStates.RUNNING,
                                                      SupvisorsInstanceStates.FAILED),
                    SupvisorsInstanceStates.RUNNING: (SupvisorsInstanceStates.FAILED,),
                    SupvisorsInstanceStates.FAILED: (SupvisorsInstanceStates.STOPPED,
                                                     SupvisorsInstanceStates.ISOLATED),
                    SupvisorsInstanceStates.ISOLATED: ()
                    }
