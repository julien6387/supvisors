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

from supervisors.utils import enumeration_tools


@enumeration_tools
class AddressStates:
    """ Enumeration class for the state of remote Supervisors instance """
    UNKNOWN, RUNNING, SILENT, ISOLATING, ISOLATED = range(5)

@enumeration_tools
class ApplicationStates:
    """ Class holding the possible enumeration values for an application state. """
    STOPPED, STARTING, RUNNING, STOPPING = range(4)

@enumeration_tools
class DeploymentStrategies:
    """ Applicable strategies that can be applied during a deployment. """
    CONFIG, LESS_LOADED, MOST_LOADED = range(3)

@enumeration_tools
class ConciliationStrategies:
    """ Applicable strategies that can be applied during a conciliation. """
    SENICIDE, INFANTICIDE, USER, STOP, RESTART = range(5)

@enumeration_tools
class StartingFailureStrategies:
    """ Applicable strategies that can be applied on a failure of a starting application. """
    ABORT, CONTINUE = range(2)

@enumeration_tools
class RunningFailureStrategies:
    """ Applicable strategies that can be applied on a failure of a running application. """
    CONTINUE, STOP, RESTART = range(3)

@enumeration_tools
class SupervisorsStates:
    """ Internal state of Supervisors. """
    INITIALIZATION, DEPLOYMENT, OPERATION, CONCILIATION = range(4)


# Exceptions
class InvalidTransition(Exception):
    """ Exception used for an invalid transition in state machines. """
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)
    
