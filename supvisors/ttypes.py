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

import supervisor.states

from typing import Any, Mapping

from supvisors.utils import *


# all enumerations
@enumeration_tools
class AddressStates:
    """ Enumeration class for the state of remote Supvisors instance """
    UNKNOWN, CHECKING, RUNNING, SILENT, ISOLATING, ISOLATED = range(6)


@enumeration_tools
class ApplicationStates:
    """ Class holding the possible enumeration values for an application state. """
    STOPPED, STARTING, RUNNING, STOPPING = range(4)


# completion of supervisor ProcessStates definition
ProcessStates = enumeration_tools(supervisor.states.ProcessStates)


@enumeration_tools
class StartingStrategies:
    """ Applicable strategies that can be applied to start processes. """
    CONFIG, LESS_LOADED, MOST_LOADED, LOCAL = range(4)


@enumeration_tools
class ConciliationStrategies:
    """ Applicable strategies that can be applied during a conciliation. """
    SENICIDE, INFANTICIDE, USER, STOP, RESTART, RUNNING_FAILURE = range(6)
    # TODO: change to STOP+RESTART PROCESS and add STOP+RESTART APPLICATION ?


@enumeration_tools
class StartingFailureStrategies:
    """ Applicable strategies that can be applied on a failure of a starting application. """
    ABORT, STOP, CONTINUE = range(3)


@enumeration_tools
class RunningFailureStrategies:
    """ Applicable strategies that can be applied on a failure of a running application. """
    CONTINUE, RESTART_PROCESS, STOP_APPLICATION, RESTART_APPLICATION = range(4)


@enumeration_tools
class SupvisorsStates:
    """ Internal state of Supvisors. """
    INITIALIZATION, DEPLOYMENT, OPERATION, CONCILIATION, RESTARTING, SHUTTING_DOWN, SHUTDOWN = range(7)


# Exceptions
class InvalidTransition(Exception):
    """ Exception used for an invalid transition in state machines. """

    def __init__(self, value):
        self.value = value

    def __str__(self):
        return self.value


# Types for annotations
Payload = Mapping[str, Any]
