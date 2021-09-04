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

import pytest

from unittest.mock import Mock

from supvisors.ttypes import *


def test_AddressStates():
    """ Test the AddressStates enumeration. """
    expected = ['UNKNOWN', 'CHECKING', 'RUNNING', 'SILENT', 'ISOLATING', 'ISOLATED']
    assert AddressStates._member_names_ == expected
    assert list(AddressStates._value2member_map_.keys()) == list(range(6))


def test_ApplicationStates():
    """ Test the ApplicationStates enumeration. """
    expected = ['STOPPED', 'STARTING', 'RUNNING', 'STOPPING']
    assert expected == ApplicationStates._member_names_
    assert list(ApplicationStates._value2member_map_.keys()) == list(range(4))


def test_StartingStrategies():
    """ Test the StartingStrategies enumeration. """
    expected = ['CONFIG', 'LESS_LOADED', 'MOST_LOADED', 'LOCAL']
    assert StartingStrategies._member_names_ == expected
    assert list(StartingStrategies._value2member_map_.keys()) == list(range(4))


def test_ConciliationStrategies():
    """ Test the ConciliationStrategies enumeration. """
    expected = ['SENICIDE', 'INFANTICIDE', 'USER', 'STOP', 'RESTART', 'RUNNING_FAILURE']
    assert ConciliationStrategies._member_names_ == expected
    assert list(ConciliationStrategies._value2member_map_.keys()) == list(range(6))


def test_StartingFailureStrategies():
    """ Test the StartingFailureStrategies enumeration. """
    expected = ['ABORT', 'STOP', 'CONTINUE']
    assert StartingFailureStrategies._member_names_ == expected
    assert list(StartingFailureStrategies._value2member_map_.keys()) == list(range(3))


def test_RunningFailureStrategies():
    """ Test the RunningFailureStrategies enumeration. """
    expected = ['CONTINUE', 'RESTART_PROCESS', 'STOP_APPLICATION', 'RESTART_APPLICATION']
    assert RunningFailureStrategies._member_names_ == expected
    assert list(RunningFailureStrategies._value2member_map_.keys()) == list(range(4))


def test_SupvisorsStates():
    """ Test the SupvisorsStates enumeration. """
    expected = ['INITIALIZATION', 'DEPLOYMENT', 'OPERATION', 'CONCILIATION', 'RESTARTING',
                'SHUTTING_DOWN', 'SHUTDOWN']
    assert SupvisorsStates._member_names_ == expected
    assert list(SupvisorsStates._value2member_map_.keys()) == list(range(7))


def test_exception():
    """ Test the exception InvalidTransition. """
    # test with unknown attributes
    with pytest.raises(InvalidTransition) as exc:
        raise InvalidTransition('invalid transition')
    assert 'invalid transition' == str(exc.value)


def test_SupvisorsFaults():
    """ Test the SupvisorsFaults enumeration. """
    expected = ['SUPVISORS_CONF_ERROR', 'BAD_SUPVISORS_STATE']
    assert SupvisorsFaults._member_names_ == expected
    assert list(SupvisorsFaults._value2member_map_.keys()) == list(range(100, 102))


def test_process_event():
    """ Test the ProcessEvent classes. """
    # attribute called 'name' cannot be mocked at creation
    process = Mock(config=Mock(), group=None)
    process.config.name = 'dummy_process'
    # test ProcessEvent creation
    event = ProcessEvent(process)
    assert isinstance(event, Event)
    assert event.process is process
    # test payload with no group
    assert event.payload() == 'processname:dummy_process groupname: '
    # test payload with no group
    process.group = Mock(config=Mock())
    process.group.config.name = 'dummy_group'
    assert event.payload() == 'processname:dummy_process groupname:dummy_group '
    # test ProcessAddedEvent creation
    event = ProcessAddedEvent(process)
    assert isinstance(event, ProcessEvent)
    assert event.payload() == 'processname:dummy_process groupname:dummy_group '
    # test ProcessRemovedEvent creation
    event = ProcessRemovedEvent(process)
    assert isinstance(event, ProcessEvent)
    assert event.payload() == 'processname:dummy_process groupname:dummy_group '
