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

from unittest.mock import Mock

import pytest

from supvisors.ttypes import *


def test_supvisors_instance_states():
    """ Test the SupvisorsInstanceStates enumeration. """
    expected = ['UNKNOWN', 'CHECKING', 'CHECKED', 'RUNNING', 'SILENT', 'ISOLATING', 'ISOLATED']
    assert [x.name for x in SupvisorsInstanceStates] == expected


def test_supvisors_states():
    """ Test the SupvisorsStates enumeration. """
    expected = ['OFF', 'INITIALIZATION', 'DEPLOYMENT', 'OPERATION', 'CONCILIATION', 'RESTARTING',
                'SHUTTING_DOWN', 'FINAL']
    assert [x.name for x in SupvisorsStates] == expected


def test_application_states():
    """ Test the ApplicationStates enumeration. """
    expected = ['STOPPED', 'STARTING', 'RUNNING', 'STOPPING', 'DELETED']
    assert [x.name for x in ApplicationStates] == expected


def test_event_links():
    """ Test the EventLinks enumeration. """
    expected = ['NONE', 'ZMQ', 'WS']
    assert [x.name for x in EventLinks] == expected


def test_starting_strategies():
    """ Test the StartingStrategies enumeration. """
    expected = ['CONFIG', 'LESS_LOADED', 'MOST_LOADED', 'LOCAL', 'LESS_LOADED_NODE', 'MOST_LOADED_NODE']
    assert [x.name for x in StartingStrategies] == expected


def test_conciliation_strategies():
    """ Test the ConciliationStrategies enumeration. """
    expected = ['SENICIDE', 'INFANTICIDE', 'USER', 'STOP', 'RESTART', 'RUNNING_FAILURE']
    assert [x.name for x in ConciliationStrategies] == expected


def test_starting_failure_strategies():
    """ Test the StartingFailureStrategies enumeration. """
    expected = ['ABORT', 'STOP', 'CONTINUE']
    assert [x.name for x in StartingFailureStrategies] == expected


def test_running_failure_strategies():
    """ Test the RunningFailureStrategies enumeration. """
    expected = ['CONTINUE', 'RESTART_PROCESS', 'STOP_APPLICATION', 'RESTART_APPLICATION', 'SHUTDOWN', 'RESTART']
    assert [x.name for x in RunningFailureStrategies] == expected


def test_process_request_result():
    """ Test the ProcessRequestResult enumeration. """
    expected = ['IN_PROGRESS', 'SUCCESS', 'FAILED', 'TIMED_OUT']
    assert [x.name for x in ProcessRequestResult] == expected


def test_distribution_rules():
    """ Test the DistributionRules enumeration. """
    expected = ['ALL_INSTANCES', 'SINGLE_INSTANCE', 'SINGLE_NODE']
    assert [x.name for x in DistributionRules] == expected


def test_statistics_types():
    """ Test the StatisticsTypes enumeration. """
    expected = ['OFF', 'HOST', 'PROCESS', 'ALL']
    assert [x.name for x in StatisticsTypes] == expected


def test_synchronization_options():
    """ Test the SynchronizationOptions enumeration. """
    expected = ['STRICT', 'LIST', 'TIMEOUT', 'CORE', 'USER']
    assert [x.name for x in SynchronizationOptions] == expected


def test_internal_event_headers():
    """ Test the InternalEventHeaders enumeration. """
    expected = ['HEARTBEAT', 'TICK', 'AUTHORIZATION', 'PROCESS', 'PROCESS_ADDED', 'PROCESS_REMOVED',
                'PROCESS_DISABILITY', 'HOST_STATISTICS', 'PROCESS_STATISTICS', 'STATE', 'ALL_INFO', 'DISCOVERY']
    assert [x.name for x in InternalEventHeaders] == expected


def test_event_headers():
    """ Test the RemoteCommEvents enumeration. """
    expected = ['SUPVISORS', 'INSTANCE', 'APPLICATION', 'PROCESS_EVENT', 'PROCESS_STATUS',
                'HOST_STATISTICS', 'PROCESS_STATISTICS']
    assert [x.name for x in EventHeaders] == expected


def test_exception():
    """ Test the exception InvalidTransition. """
    # test with unknown attributes
    with pytest.raises(InvalidTransition) as exc:
        raise InvalidTransition('invalid transition')
    assert 'invalid transition' == str(exc.value)


def test_supvisors_faults():
    """ Test the SupvisorsFaults enumeration. """
    expected = ['SUPVISORS_CONF_ERROR', 'BAD_SUPVISORS_STATE', 'NOT_MANAGED', 'DISABLED']
    assert [x.name for x in SupvisorsFaults] == expected
    assert [x.value for x in SupvisorsFaults] == list(range(100, 104))


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
