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


def test_SupvisorsInstanceStates():
    """ Test the SupvisorsInstanceStates enumeration. """
    expected = ['UNKNOWN', 'CHECKING', 'RUNNING', 'SILENT', 'ISOLATING', 'ISOLATED']
    assert enum_names(SupvisorsInstanceStates) == expected
    assert enum_values(SupvisorsInstanceStates) == list(range(6))


def test_ApplicationStates():
    """ Test the ApplicationStates enumeration. """
    expected = ['STOPPED', 'STARTING', 'RUNNING', 'STOPPING']
    assert enum_names(ApplicationStates) == expected
    assert enum_values(ApplicationStates) == list(range(4))


def test_StartingStrategies():
    """ Test the StartingStrategies enumeration. """
    expected = ['CONFIG', 'LESS_LOADED', 'MOST_LOADED', 'LOCAL', 'LESS_LOADED_NODE', 'MOST_LOADED_NODE']
    assert enum_names(StartingStrategies) == expected
    assert enum_values(StartingStrategies) == list(range(6))


def test_ConciliationStrategies():
    """ Test the ConciliationStrategies enumeration. """
    expected = ['SENICIDE', 'INFANTICIDE', 'USER', 'STOP', 'RESTART', 'RUNNING_FAILURE']
    assert enum_names(ConciliationStrategies) == expected
    assert enum_values(ConciliationStrategies) == list(range(6))


def test_StartingFailureStrategies():
    """ Test the StartingFailureStrategies enumeration. """
    expected = ['ABORT', 'STOP', 'CONTINUE']
    assert enum_names(StartingFailureStrategies) == expected
    assert enum_values(StartingFailureStrategies) == list(range(3))


def test_RunningFailureStrategies():
    """ Test the RunningFailureStrategies enumeration. """
    expected = ['CONTINUE', 'RESTART_PROCESS', 'STOP_APPLICATION', 'RESTART_APPLICATION', 'SHUTDOWN', 'RESTART']
    assert enum_names(RunningFailureStrategies) == expected
    assert enum_values(RunningFailureStrategies) == list(range(6))


def test_SupvisorsStates():
    """ Test the SupvisorsStates enumeration. """
    expected = ['INITIALIZATION', 'DEPLOYMENT', 'OPERATION', 'CONCILIATION', 'RESTARTING', 'RESTART',
                'SHUTTING_DOWN', 'SHUTDOWN']
    assert enum_names(SupvisorsStates) == expected
    assert enum_values(SupvisorsStates) == list(range(8))


def test_exception():
    """ Test the exception InvalidTransition. """
    # test with unknown attributes
    with pytest.raises(InvalidTransition) as exc:
        raise InvalidTransition('invalid transition')
    assert 'invalid transition' == str(exc.value)


def test_SupvisorsFaults():
    """ Test the SupvisorsFaults enumeration. """
    expected = ['SUPVISORS_CONF_ERROR', 'BAD_SUPVISORS_STATE', 'NOT_MANAGED']
    assert enum_names(SupvisorsFaults) == expected
    assert enum_values(SupvisorsFaults) == list(range(100, 103))


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
