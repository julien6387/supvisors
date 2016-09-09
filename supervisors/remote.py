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

from supervisors.types import InvalidTransition
from supervisors.utils import *


@enumerationTools
class AddressStates:
    """ Enumeration class for the state of remote Supervisors instance """
    UNKNOWN, RUNNING, SILENT, ISOLATING, ISOLATED = range(5)


class AddressStatus(object):
    """ TODO """

    def __init__(self, address, logger):
        self.logger = logger
        self.address = address
        self._state = AddressStates.UNKNOWN
        self.checked = False
        self.remoteTime = 0
        self.localTime = 0

    # serialization
    def to_json(self):
        return {'address': self.address, 'state': self.state_string(), 'checked': self.checked,
            'remote_time': self.remote_time, 'local_time': self.local_time }

    # accessors / mutators
    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, newState):
        if self._state != newState:
            if self.checkTransition(newState):
                self._state = newState
                self.logger.info('Address {} is {}'.format(self.address, self.state_string()))
            else:
                raise InvalidTransition('Address: transition rejected {} to {}'.format(self.state_string(), AddressStates.to_string(newState)))

    # methods
    def state_string(self):
        return AddressStates.to_string(self.state)

    def in_isolation(self):
        return self.state in [RemoteStates.ISOLATING, RemoteStates.ISOLATED]

    def update_times(self, remote_time, local_time):
        self.remote_time = remote_time
        self.local_time = local_time

    def checkTransition(self, newState):
        return newState in self.__Transitions[self.state]

    __Transitions = {
        AddressStates.UNKNOWN: (AddressStates.RUNNING, AddressStates.ISOLATING, AddressStates.SILENT),
        AddressStates.RUNNING: (AddressStates.SILENT, AddressStates.ISOLATING),
        AddressStates.SILENT: (AddressStates.RUNNING, ),
        AddressStates.ISOLATING: (AddressStates.ISOLATED, ), 
        AddressStates.ISOLATED: ()
    }
