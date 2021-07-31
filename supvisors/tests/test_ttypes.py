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


def test_AddressStates():
    """ Test the AddressStates enumeration. """
    from supvisors.ttypes import AddressStates
    expected = ['UNKNOWN', 'CHECKING', 'RUNNING', 'SILENT', 'ISOLATING', 'ISOLATED']
    assert expected == AddressStates._member_names_


def test_ApplicationStates():
    """ Test the ApplicationStates enumeration. """
    from supvisors.ttypes import ApplicationStates
    expected = ['STOPPED', 'STARTING', 'RUNNING', 'STOPPING']
    assert expected == ApplicationStates._member_names_


def test_StartingStrategies():
    """ Test the StartingStrategies enumeration. """
    from supvisors.ttypes import StartingStrategies
    expected = ['CONFIG', 'LESS_LOADED', 'MOST_LOADED', 'LOCAL']
    assert expected == StartingStrategies._member_names_


def test_ConciliationStrategies():
    """ Test the ConciliationStrategies enumeration. """
    from supvisors.ttypes import ConciliationStrategies
    expected = ['SENICIDE', 'INFANTICIDE', 'USER', 'STOP', 'RESTART', 'RUNNING_FAILURE']
    assert expected == ConciliationStrategies._member_names_


def test_StartingFailureStrategies():
    """ Test the StartingFailureStrategies enumeration. """
    from supvisors.ttypes import StartingFailureStrategies
    expected = ['ABORT', 'STOP', 'CONTINUE']
    assert expected == StartingFailureStrategies._member_names_


def test_RunningFailureStrategies():
    """ Test the RunningFailureStrategies enumeration. """
    from supvisors.ttypes import RunningFailureStrategies
    expected = ['CONTINUE', 'RESTART_PROCESS', 'STOP_APPLICATION', 'RESTART_APPLICATION']
    assert expected == RunningFailureStrategies._member_names_


def test_SupvisorsStates():
    """ Test the SupvisorsStates enumeration. """
    from supvisors.ttypes import SupvisorsStates
    expected = ['INITIALIZATION', 'DEPLOYMENT', 'OPERATION', 'CONCILIATION', 'RESTARTING',
                'SHUTTING_DOWN', 'SHUTDOWN']
    assert expected == SupvisorsStates._member_names_


def test_exception():
    """ Test the exception InvalidTransition. """
    from supvisors.ttypes import InvalidTransition
    # test with unknown attributes
    with pytest.raises(InvalidTransition) as exc:
        raise InvalidTransition('invalid transition')
    assert 'invalid transition' == str(exc.value)
