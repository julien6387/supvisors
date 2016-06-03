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

from supervisors.options import mainOptions as opt
from supervisors.types import InvalidTransition
from supervisors.utils import *

# Enumeration for RemoteStates
class RemoteStates:
    UNKNOWN, CHECKING, RUNNING, SILENT, ISOLATED = range(5)

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
        self._address = address
        self._state = RemoteStates.UNKNOWN
        self._checked = False
        self._remoteTime = 0
        self._localTime = 0

    @property
    def address(self): return self._address
    @property
    def state(self): return self._state
    @property
    def checked(self): return self._checked
    @property
    def remoteTime(self): return self._remoteTime
    @property
    def localTime(self): return self._localTime
    

# Remote class
class RemoteInfo(RemoteStatus):
    def __init__(self, address):
        super(RemoteInfo, self).__init__(address)

    def setState(self, state):
        if self.state != state:
            if self.__checkTransition(state):
                self._state = state
                opt.logger.info('Remote {} is {}'.format(self.address, remoteStateToString(self.state)))
            else:
                raise InvalidTransition('Remote: transition rejected {} to {}'.format(remoteStateToString(self.state), remoteStateToString(state)))

    def setChecked(self, value):
        self._checked = value

    # methods
    def updateRemoteTime(self, remoteTime, localTime):
        self._remoteTime = remoteTime
        self._localTime = localTime

    def __checkTransition(self, newState):
        return newState in self.__Transitions[self.state]

    __Transitions = { \
        RemoteStates.UNKNOWN: (RemoteStates.CHECKING, RemoteStates.RUNNING, RemoteStates.ISOLATED, RemoteStates.SILENT),
        RemoteStates.CHECKING: (RemoteStates.RUNNING, RemoteStates.ISOLATED),
        RemoteStates.RUNNING: (RemoteStates.SILENT, RemoteStates.ISOLATED),
        RemoteStates.SILENT: (RemoteStates.RUNNING, RemoteStates.CHECKING),
        RemoteStates.ISOLATED: ()
    }


# for tests
if __name__ == "__main__":
    status = RemoteInfo('cliche01')
    status.state = RemoteStates.CHECKING
