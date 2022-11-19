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

from enum import Enum
from typing import Any, Dict, List, Set, Tuple, TypeVar

from supervisor.events import Event


# all enumerations
class SupvisorsInstanceStates(Enum):
    """ Enumeration class for the state of remote Supvisors instance. """
    UNKNOWN, CHECKING, RUNNING, SILENT, ISOLATING, ISOLATED = range(6)


class SupvisorsStates(Enum):
    """ Synthesis state of Supvisors. """
    OFF, INITIALIZATION, DEPLOYMENT, OPERATION, CONCILIATION, RESTARTING, RESTART, SHUTTING_DOWN, SHUTDOWN = range(9)


class ApplicationStates(Enum):
    """ Class holding the possible enumeration values for an application state. """
    STOPPED, STARTING, RUNNING, STOPPING, DELETED = range(5)


class EventLinks(Enum):
    """ Available link types used to publish all Supvisors events. """
    NONE, ZMQ = range(2)


class StartingStrategies(Enum):
    """ Applicable strategies that can be applied to start processes. """
    CONFIG, LESS_LOADED, MOST_LOADED, LOCAL, LESS_LOADED_NODE, MOST_LOADED_NODE = range(6)


class ConciliationStrategies(Enum):
    """ Applicable strategies that can be applied during a conciliation. """
    SENICIDE, INFANTICIDE, USER, STOP, RESTART, RUNNING_FAILURE = range(6)
    # TODO: change to STOP+RESTART PROCESS and add STOP+RESTART APPLICATION ?


class StartingFailureStrategies(Enum):
    """ Applicable strategies that can be applied on a failure of a starting application. """
    ABORT, STOP, CONTINUE = range(3)


class RunningFailureStrategies(Enum):
    """ Applicable strategies that can be applied on a failure of a running application. """
    CONTINUE, RESTART_PROCESS, STOP_APPLICATION, RESTART_APPLICATION, SHUTDOWN, RESTART = range(6)


class ProcessRequestResult(Enum):
    """ The possible results after a process request. """
    IN_PROGRESS, SUCCESS, FAILED, TIMED_OUT = range(4)


class DistributionRules(Enum):
    """ Rule applicable to the distribution of an application. """
    ALL_INSTANCES, SINGLE_INSTANCE, SINGLE_NODE = range(3)


# for internal publish / subscribe
class InternalEventHeaders(Enum):
    """ Enumeration class for the headers in messages between Listener and MainLoop. """
    HEARTBEAT, TICK, PROCESS, PROCESS_ADDED, PROCESS_REMOVED, PROCESS_DISABILITY, STATISTICS, STATE = range(8)


# for deferred XML-RPC requests
class DeferredRequestHeaders(Enum):
    """ Enumeration class for the headers of deferred XML-RPC messages sent to MainLoop. """
    (CHECK_INSTANCE, ISOLATE_INSTANCES, START_PROCESS, STOP_PROCESS,
     RESTART, SHUTDOWN, RESTART_SEQUENCE, RESTART_ALL, SHUTDOWN_ALL) = range(9)


class RemoteCommEvents(Enum):
    """ Strings used for remote communication between the Supvisors main loop and the listener. """
    SUPVISORS_AUTH = u'auth'
    SUPVISORS_EVENT = u'event'
    SUPVISORS_INFO = u'info'


class EventHeaders(Enum):
    """ Strings used as headers in messages between EventPublisher and Supvisors' Client. """
    SUPVISORS = 'supvisors'
    INSTANCE = 'instance'
    APPLICATION = 'application'
    PROCESS_EVENT = 'event'
    PROCESS_STATUS = 'process'


# State lists commonly used
ISOLATION_STATES = [SupvisorsInstanceStates.ISOLATING, SupvisorsInstanceStates.ISOLATED]
CLOSING_STATES = [SupvisorsStates.RESTARTING, SupvisorsStates.RESTART,
                  SupvisorsStates.SHUTTING_DOWN, SupvisorsStates.SHUTDOWN]


# Exceptions
class InvalidTransition(Exception):
    """ Exception used for an invalid transition in state machines. """

    def __init__(self, value):
        self.value = value

    def __str__(self):
        return self.value


# Supvisors related faults
FAULTS_OFFSET = 100


class SupvisorsFaults(Enum):
    SUPVISORS_CONF_ERROR, BAD_SUPVISORS_STATE, NOT_MANAGED, DISABLED = range(FAULTS_OFFSET, FAULTS_OFFSET + 4)


# Additional events
class ProcessEvent(Event):

    def __init__(self, process):
        self.process = process

    def payload(self):
        groupname = ''
        if self.process.group:
            groupname = self.process.group.config.name
        return 'processname:{} groupname:{} '.format(self.process.config.name, groupname)


class ProcessAddedEvent(ProcessEvent):
    pass


class ProcessRemovedEvent(ProcessEvent):
    pass


class ProcessEnabledEvent(ProcessEvent):
    pass


class ProcessDisabledEvent(ProcessEvent):
    pass


# Annotation types
EnumClassType = TypeVar('EnumClassType', bound='Type[Enum]')
EnumType = TypeVar('EnumType', bound='Enum')
Payload = Dict[str, Any]
PayloadList = List[Payload]
NameList = List[str]
NameSet = Set[str]
LoadMap = Dict[str, int]

# Annotation types for statistics
NamedPid = Tuple[str, int]  # namespec, PID
NamedPidList = List[NamedPid]
Jiffies = Tuple[float, float]  # (work, idle)
JiffiesList = List[Jiffies]  # one entry per processor + 1 for average (first element)
CPUInstantStats = List[float]  # in percent. one entry per processor + 1 for average (first element)
CPUHistoryStats = List[List[float]]  # in percent. one list per processor + 1 for average (first element)
MemHistoryStats = List[float]  # in percent
IOBytes = Tuple[int, int]  # recv_bytes, sent_bytes
BytesList = List[float]  # in kilobytes per second
InterfaceInstantStats = Dict[str, IOBytes]  # {interface: (recv_bytes, sent_bytes)}
InterfaceIntegratedStats = Dict[str, Tuple[float, float]]  # {interface: (recv_bytes, sent_bytes)}
InterfaceHistoryStats = Dict[str, Tuple[BytesList, BytesList]]  # {interface: ([recv_bytes], [sent_bytes])}
ProcessStats = Tuple[float, float]  # jiffies, memory
ProcessStatsMap = Dict[str, Tuple[int, ProcessStats]]  # {namespec: (PID, ProcessStats)}
ProcessHistoryStats = Tuple[CPUInstantStats, MemHistoryStats]
ProcessHistoryStatsMap = Dict[NamedPid, ProcessHistoryStats]
InstantStatistics = Tuple[float, JiffiesList, float, InterfaceInstantStats, ProcessStatsMap]
