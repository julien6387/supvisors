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

from supervisors.options import options
from supervisors.types import InvalidTransition
from supervisors.utils import *

# Enumeration for RemoteStates
class RemoteStates:
    UNKNOWN, RUNNING, SILENT, ISOLATING, ISOLATED = range(5)

def remoteStateToString(value):
    return enumToString(RemoteStates.__dict__, value)

def stringToRemoteState(strEnum):
    return stringToEnum(RemoteStates.__dict__, strEnum)

def remoteStatesValues():
    return enumValues(RemoteStates.__dict__)

def remoteStatesStrings():
    return enumStrings(RemoteStates.__dict__)

# RemoteStatus class
class RemoteStatus(object):
    def __init__(self, address):
        self.address = address
        self.state = RemoteStates.UNKNOWN
        self.checked = False
        self.remoteTime = 0
        self.localTime = 0

    # serialization
    def toJSON(self):
        return { 'address': self.address, 'state': self.stateAsString(), 'checked': self.checked,
            'remoteTime': self.remoteTime, 'localTime': self.localTime }

    # access
    def isInIsolation(self):
        return self.state in [ RemoteStates.ISOLATING, RemoteStates.ISOLATED ]

    def setState(self, state):
        if self.state != state:
            if self.__checkTransition(state):
                self.state = state
                options.logger.info('Remote {} is {}'.format(self.address, remoteStateToString(self.state)))
            else:
                raise InvalidTransition('Remote: transition rejected {} to {}'.format(remoteStateToString(self.state), remoteStateToString(state)))

    # methods
    def stateAsString(self): return remoteStateToString(self.state)

    def updateRemoteTime(self, remoteTime, localTime):
        self.remoteTime = remoteTime
        self.localTime = localTime

    def __checkTransition(self, newState):
        return newState in self.__Transitions[self.state]

    __Transitions = {
        RemoteStates.UNKNOWN: (RemoteStates.RUNNING, RemoteStates.ISOLATING, RemoteStates.SILENT),
        RemoteStates.RUNNING: (RemoteStates.SILENT, RemoteStates.ISOLATING),
        RemoteStates.SILENT: (RemoteStates.RUNNING, ),
        RemoteStates.ISOLATING: (RemoteStates.ISOLATED, ), 
        RemoteStates.ISOLATED: ()
    }
