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
from supervisor.options import ProcessConfig

# Supvisors name
SUPVISORS_PUBLICATION = 'SupvisorsPublication'
SUPVISORS_NOTIFICATION = 'SupvisorsNotification'


# all enumerations
class SupvisorsInstanceStates(Enum):
    """ Enumeration class for the state of remote Supvisors instance. """
    UNKNOWN, CHECKING, CHECKED, RUNNING, SILENT, ISOLATED = range(6)


class SupvisorsStates(Enum):
    """ Synthesis state of Supvisors. """
    OFF, INITIALIZATION, DISTRIBUTION, OPERATION, CONCILIATION, RESTARTING, SHUTTING_DOWN, FINAL = range(8)


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
class PublicationHeaders(Enum):
    """ Enumeration class for the publication headers in messages between Listener and MainLoop. """
    (TICK, PROCESS, PROCESS_ADDED, PROCESS_REMOVED, PROCESS_DISABILITY,
     HOST_STATISTICS, PROCESS_STATISTICS, STATE) = range(8)


# for deferred XML-RPC requests
class RequestHeaders(Enum):
    """ Enumeration class for the headers of deferred XML-RPC messages sent to SupervisorProxyServer. """
    (CHECK_INSTANCE,
     START_PROCESS, STOP_PROCESS,
     RESTART, SHUTDOWN, RESTART_SEQUENCE, RESTART_ALL, SHUTDOWN_ALL) = range(8)


class NotificationHeaders(Enum):
    """ Enumeration class for the notification headers in messages between Listener and MainLoop. """
    AUTHORIZATION, STATE, ALL_INFO, DISCOVERY, INSTANCE_FAILURE = range(5)


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
WORKING_STATES = [SupvisorsStates.DISTRIBUTION, SupvisorsStates.OPERATION, SupvisorsStates.CONCILIATION]
CLOSING_STATES = [SupvisorsStates.RESTARTING, SupvisorsStates.SHUTTING_DOWN, SupvisorsStates.FINAL]


# Exceptions
class SupvisorsException(Exception):
    """ Basic exception. """

    message: str = ''

    def __init__(self, message):
        self.message = message

    def __str__(self):
        return self.message


class InvalidTransition(SupvisorsException):
    """ Exception used for an invalid transition in state machines. """


class ApplicationStatusParseError(SupvisorsException):
    """ Exception used for errors in the evaluation of the application status. """


# Supvisors related faults
FAULTS_OFFSET = 100


class SupvisorsFaults(Enum):
    """ The additional XML-RPC faults that complement Supervisor's Faults. """
    (SUPVISORS_CONF_ERROR, BAD_SUPVISORS_STATE, NOT_MANAGED, DISABLED,
     NOT_APPLICABLE, NOT_INSTALLED) = range(FAULTS_OFFSET, FAULTS_OFFSET + 6)


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


# General annotation types
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
DiskUsage = Dict[str, float]  # {disk_path: percent}
DiskUsageHistoryStats = Dict[str, List[float]]  # {disk_path: [percent]}
InterfaceInstantStats = Dict[str, IOBytes]  # {interface: (recv/read bytes, sent/write bytes)}
InterfaceIntegratedStats = Dict[str, List[float]]  # {interface: [bytes rate]}
InterfaceHistoryStats = Dict[str, Tuple[TimesHistoryStats, List[BytesList]]]  # {interface: ([uptimes], [[bytes]])}
ProcessStats = Tuple[float, float]  # work jiffies, memory
ProcessCPUHistoryStats = List[float]  # in percent
ProcessMemHistoryStats = MemHistoryStats  # in percent


# Program config annotation types
ProcessConfigList = List[ProcessConfig]
GroupConfigInfo = Dict[str, ProcessConfigList]  # {group_name: [process_config]}
ProcessConfigType = TypeVar('ProcessConfigType', bound='Type[ProcessConfig]')


class ProgramConfig:
    """ Class used to store program information not retained by Supervisor while parsing the configuration files. """

    def __init__(self, program_name: str, klass: ProcessConfigType):
        self.name: str = program_name
        self.klass: ProcessConfigType = klass
        self.numprocs: int = 1
        self.group_config_info: GroupConfigInfo = {}
        self.disabled: bool = False


class SupvisorsProcessConfig:
    """ Class used to store process configuration not retained by Supervisor while parsing the configuration files. """

    def __init__(self, program_config: ProgramConfig, process_index: int, command_ref: str):
        self.program_config: ProgramConfig = program_config
        self.process_index: int = process_index
        self.command_ref: str = command_ref
