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

# Supvisors name
SUPVISORS = 'Supvisors'


# all enumerations
class SupvisorsInstanceStates(Enum):
    """ Enumeration class for the state of remote Supvisors instance. """
    UNKNOWN, CHECKING, CHECKED, RUNNING, SILENT, ISOLATING, ISOLATED = range(7)


class SupvisorsStates(Enum):
    """ Synthesis state of Supvisors. """
    OFF, INITIALIZATION, DEPLOYMENT, OPERATION, CONCILIATION, RESTARTING, SHUTTING_DOWN, FINAL = range(8)


class ApplicationStates(Enum):
    """ Class holding the possible enumeration values for an application state. """
    STOPPED, STARTING, RUNNING, STOPPING, DELETED = range(5)


class EventLinks(Enum):
    """ Available link types used to publish all Supvisors events. """
    NONE, ZMQ, WS = range(3)


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


class StatisticsTypes(Enum):
    """ Items to be captured when statistics are enabled. """
    OFF, HOST, PROCESS, ALL = range(4)


class SynchronizationOptions(Enum):
    """ Options to stop the synchronization phase. """
    STRICT, LIST, TIMEOUT, CORE, USER = range(5)


# for internal publish / subscribe
class InternalEventHeaders(Enum):
    """ Enumeration class for the headers in messages between Listener and MainLoop. """
    (HEARTBEAT, TICK, AUTHORIZATION, PROCESS, PROCESS_ADDED, PROCESS_REMOVED, PROCESS_DISABILITY,
     HOST_STATISTICS, PROCESS_STATISTICS, STATE, ALL_INFO, DISCOVERY) = range(12)


class EventHeaders(Enum):
    """ Strings used as headers in messages between EventPublisher and Supvisors' Client. """
    SUPVISORS = 'supvisors'
    INSTANCE = 'instance'
    APPLICATION = 'application'
    PROCESS_EVENT = 'event'
    PROCESS_STATUS = 'process'
    HOST_STATISTICS = 'hstats'
    PROCESS_STATISTICS = 'pstats'


# State lists commonly used
ISOLATION_STATES = [SupvisorsInstanceStates.ISOLATING, SupvisorsInstanceStates.ISOLATED]
WORKING_STATES = [SupvisorsStates.DEPLOYMENT, SupvisorsStates.OPERATION, SupvisorsStates.CONCILIATION]
CLOSING_STATES = [SupvisorsStates.RESTARTING, SupvisorsStates.SHUTTING_DOWN, SupvisorsStates.FINAL]


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
Ipv4Address = Tuple[str, int]
Payload = Dict[str, Any]
PayloadList = List[Payload]
NameList = List[str]
NameSet = Set[str]
LoadMap = Dict[str, int]

# Annotation types for statistics
Jiffies = Tuple[float, float]  # (work, idle)
JiffiesList = List[Jiffies]  # one entry per processor + 1 for average (first element)
CPUInstantStats = List[float]  # in percent. one entry per processor + 1 for average (first element)
TimesHistoryStats = List[float]  # in seconds
CPUHistoryStats = List[List[float]]  # in percent. one list per processor + 1 for average (first element)
MemHistoryStats = List[float]  # in percent
IOBytes = Tuple[int, int]  # recv_bytes, sent_bytes
BytesList = List[float]  # in kilobytes per second
InterfaceInstantStats = Dict[str, IOBytes]  # {interface: (recv_bytes, sent_bytes)}
InterfaceIntegratedStats = Dict[str, Tuple[float, float]]  # {interface: (recv_bytes, sent_bytes)}
InterfaceHistoryStats = Dict[str, Tuple[TimesHistoryStats, BytesList, BytesList]]  # {interface: ([uptimes], [recv_bytes], [sent_bytes])}
ProcessStats = Tuple[float, float]  # work jiffies, memory
ProcessCPUHistoryStats = List[float]  # in percent
ProcessMemHistoryStats = MemHistoryStats  # in percent
