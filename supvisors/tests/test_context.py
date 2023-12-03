#!/usr/bin/python
# -*- coding: utf-8 -*-

# ======================================================================
# Copyright 2017 Julien LE CLEACH
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

import random
from socket import gethostname
from unittest.mock import call, Mock

import pytest
from supervisor.process import ProcessStates

from supvisors.context import *
from supvisors.external_com import EventPublisherInterface
from supvisors.instancestatus import SupvisorsInstanceId, StateModes
from supvisors.ttypes import (SupvisorsInstanceStates, ApplicationStates, SupvisorsStates,
                              StartingFailureStrategies, RunningFailureStrategies, ISOLATION_STATES)
from .base import database_copy, any_process_info
from .conftest import create_application, create_process


@pytest.fixture
def context(supvisors):
    """ Return the instance to test. """
    return Context(supvisors)


def load_application_rules(_, rules):
    """ Simple Parser.load_application_rules behaviour to avoid setdefault_process to always return None. """
    rules.managed = True
    rules.starting_failure_strategy = StartingFailureStrategies.STOP
    rules.running_failure_strategy = RunningFailureStrategies.RESTART_APPLICATION


@pytest.fixture
def filled_context(context):
    """ Push ProcessInfoDatabase process info in SupvisorsInstanceStatus. """
    context.supvisors.parser.load_application_rules = load_application_rules
    for info in database_copy():
        identifier = random.choice(list(context.instances.keys()))
        process = context.setdefault_process(identifier, info)
        context.instances[identifier].add_process(process)
    return context


def test_create(supvisors, context):
    """ Test the values set at construction of Context. """
    assert supvisors is context.supvisors
    assert supvisors.logger is context.logger
    assert set(supvisors.mapper.instances.keys()), set(context.instances.keys())
    for identifier, instance_status in context.instances.items():
        assert instance_status.identifier == identifier
        assert isinstance(instance_status, SupvisorsInstanceStatus)
    hostname = gethostname()
    assert context.local_identifier == hostname
    assert context.local_status == context.instances[hostname]
    assert context.applications == {}
    assert context.master_identifier == ''
    assert not context.is_master
    assert context.start_date == 0


def test_reset(mocker, context):
    """ Test the reset of Context values. """
    mocker.patch('supvisors.context.time.time', return_value=3600)
    # change master definition
    local_identifier = context.supvisors.mapper.local_identifier
    context.master_identifier = local_identifier
    assert context.is_master
    # change node states
    context.local_status._state = SupvisorsInstanceStates.RUNNING
    context.instances['10.0.0.1']._state = SupvisorsInstanceStates.SILENT
    context.instances['10.0.0.2']._state = SupvisorsInstanceStates.ISOLATING
    context.instances['10.0.0.3']._state = SupvisorsInstanceStates.ISOLATED
    context.instances['10.0.0.4']._state = SupvisorsInstanceStates.RUNNING
    # add an application
    application = create_application('dummy_appli', context.supvisors)
    context.applications['dummy_appli'] = application
    # call reset and check result
    context.reset()
    assert set(context.supvisors.mapper.instances), set(context.instances.keys())
    context.local_status._state = SupvisorsInstanceStates.UNKNOWN
    context.instances['10.0.0.1']._state = SupvisorsInstanceStates.SILENT
    context.instances['10.0.0.2']._state = SupvisorsInstanceStates.ISOLATING
    context.instances['10.0.0.3']._state = SupvisorsInstanceStates.ISOLATED
    context.instances['10.0.0.4']._state = SupvisorsInstanceStates.UNKNOWN
    assert context.applications == {'dummy_appli': application}
    assert context.master_identifier == ''
    assert not context.is_master
    assert context.start_date == 3600


def test_master_identifier(context):
    """ Test the access to master identifier. """
    local_identifier = context.supvisors.mapper.local_identifier
    assert context.master_identifier == ''
    assert not context.is_master
    context.master_identifier = '10.0.0.1'
    assert context.master_identifier == '10.0.0.1'
    assert not context.is_master
    context.master_identifier = local_identifier
    assert context.master_identifier == local_identifier
    assert context.is_master


def test_elect_master(context):
    """ Test the Context.elect_master method. """
    assert context.master_identifier == ''
    # test with no running Supvisors instance
    context.elect_master()
    assert context.master_identifier == ''
    # test with running Supvisors instances and no known Master
    context.instances['10.0.0.2']._state = SupvisorsInstanceStates.RUNNING
    context.instances['10.0.0.4']._state = SupvisorsInstanceStates.RUNNING
    context.elect_master()
    assert context.master_identifier == '10.0.0.2'
    # test with running Supvisors instances and a known Master not RUNNING
    context.master_identifier = '10.0.0.1'
    context.elect_master()
    assert context.master_identifier == '10.0.0.2'
    # test with running Supvisors instances and a known Master RUNNING
    context.elect_master()
    assert context.master_identifier == '10.0.0.2'
    # test with running Supvisors instances, no known Master and core_identifiers not running
    context.master_identifier = ''
    context.supvisors.mapper._core_identifiers = ['10.0.0.1', '10.0.0.3']
    context.elect_master()
    assert context.master_identifier == '10.0.0.2'
    # test with running Supvisors instances, a known Master and one of the core_identifiers running
    context.instances['10.0.0.3']._state = SupvisorsInstanceStates.RUNNING
    context.elect_master()
    assert context.master_identifier == '10.0.0.2'
    # test with running Supvisors instances, no known Master and one of the core_identifiers running
    context.master_identifier = ''
    context.elect_master()
    assert context.master_identifier == '10.0.0.3'


def test_on_discovery_event(context):
    """ Test the Context.on_discovery_event method. """
    # store reference
    sup_id: SupvisorsInstanceId = context.instances['10.0.0.1'].supvisors_id
    ref_ip_address, ref_port = sup_id.ip_address, sup_id.http_port
    # test in discovery mode and identifier known and identical
    assert not context.on_discovery_event('10.0.0.1', {'ip_address': '10.0.0.1', 'server_port': 65000})
    assert sup_id.ip_address == ref_ip_address
    assert sup_id.http_port == ref_port
    # test in discovery mode and identifier known and changed
    assert not context.on_discovery_event('10.0.0.1', {'ip_address': '10.0.0.2', 'server_port': 6000})
    assert sup_id.ip_address == ref_ip_address
    assert sup_id.http_port == ref_port
    # test in discovery mode and identifier unknown
    assert context.on_discovery_event('rocky52', {'ip_address': '192.168.1.2', 'server_port': 5000})
    assert sup_id.ip_address == ref_ip_address
    assert sup_id.http_port == ref_port
    assert 'rocky52' in context.instances
    sup_id: SupvisorsInstanceId = context.instances['rocky52'].supvisors_id
    assert sup_id.ip_address == '192.168.1.2'
    assert sup_id.http_port == 5000


def test_is_valid(context):
    """ Test the Context.is_valid method. """
    # change states
    context.instances['10.0.0.1']._state = SupvisorsInstanceStates.SILENT
    context.instances['10.0.0.2']._state = SupvisorsInstanceStates.ISOLATING
    context.instances['10.0.0.3']._state = SupvisorsInstanceStates.ISOLATED
    context.instances['10.0.0.4']._state = SupvisorsInstanceStates.RUNNING
    # test unknown identifier
    assert not context.is_valid('rocky52', '192.168.1.2')
    # test known identifier but isolated
    assert not context.is_valid('10.0.0.2', '192.168.1.2')
    assert not context.is_valid('10.0.0.3', '10.0.0.3')
    # test known identifier, not isolated but with wrong IP address
    assert not context.is_valid('10.0.0.1', '192.168.1.2')
    assert not context.is_valid('10.0.0.4', '192.168.1.2')
    # test known identifier not isolated and with correct IP address
    assert context.is_valid('10.0.0.1', '10.0.0.1')
    assert context.is_valid('10.0.0.4', '10.0.0.4')


def test_publish_state_modes(context):
    """ Test the Context.publish_state_modes method. """
    mocked_send_state = context.supvisors.internal_com.publisher.send_state_event
    # test unchanged
    context.publish_state_modes({'starter': False})
    assert not mocked_send_state.called
    # test changed
    context.publish_state_modes({'starter': True})
    assert mocked_send_state.call_args_list == [call({'fsm_statecode': 0, 'fsm_statename': 'OFF',
                                                      'discovery_mode': False,
                                                      'master_identifier': '',
                                                      'starting_jobs': True, 'stopping_jobs': False})]


def test_get_state_modes(context):
    """ Test the Context.get_state_modes method. """
    assert context.get_state_modes() == {'fsm_statecode': 0, 'fsm_statename': 'OFF',
                                         'discovery_mode': False,
                                         'master_identifier': '',
                                         'starting_jobs': [], 'stopping_jobs': []}
    # assign state and set some jobs
    context.local_status.state_modes.state = SupvisorsStates.OPERATION
    context.local_status.state_modes.discovery_mode = True
    context.local_status.state_modes.master_identifier = '10.0.0.1'
    for idx, status in enumerate(context.instances.values()):
        status.state_modes.starting_jobs = (idx % 3) == 0
        status.state_modes.stopping_jobs = (idx % 4) == 0
    assert context.get_state_modes() == {'fsm_statecode': 3, 'fsm_statename': 'OPERATION',
                                         'discovery_mode': True,
                                         'master_identifier': '10.0.0.1',
                                         'starting_jobs': ['10.0.0.1', '10.0.0.4', 'test'],
                                         'stopping_jobs': ['10.0.0.1', '10.0.0.5']}


def test_publish_state_mode(context):
    """ Test the Context._publish_state_mode method. """
    context.supvisors.external_publisher = Mock(**{'send_supvisors_status.return_value': None})
    mocked_send = context.supvisors.external_publisher.send_supvisors_status
    # first call publishes the default
    context._publish_state_mode()
    assert mocked_send.call_args_list == [call({'fsm_statecode': 0, 'fsm_statename': 'OFF',
                                                'discovery_mode': False,
                                                'master_identifier': '',
                                                'starting_jobs': [], 'stopping_jobs': []})]
    mocked_send.reset_mock()
    # second call: no change so no publication
    context._publish_state_mode()
    assert not mocked_send.called
    # for third call, assign state and set some jobs
    context.local_status.state_modes.state = SupvisorsStates.OPERATION
    context.local_status.state_modes.discovery_mode = True
    context.local_status.state_modes.master_identifier = '10.0.0.1'
    for idx, status in enumerate(context.instances.values()):
        status.state_modes.starting_jobs = (idx % 3) == 0
        status.state_modes.stopping_jobs = (idx % 4) == 0
    context._publish_state_mode()
    assert mocked_send.call_args_list == [call({'fsm_statecode': 3, 'fsm_statename': 'OPERATION',
                                                'discovery_mode': True,
                                                'master_identifier': '10.0.0.1',
                                                'starting_jobs': ['10.0.0.1', '10.0.0.4', 'test'],
                                                'stopping_jobs': ['10.0.0.1', '10.0.0.5']})]
    mocked_send.reset_mock()
    # fourth call: no change so no publication
    context._publish_state_mode()
    assert not mocked_send.called


def test_export_status(mocker, context):
    """ Test the Context.export_status method. """
    mocked_publish = mocker.patch.object(context, '_publish_state_mode')
    # test with no external publisher
    context.supvisors.external_publisher = None
    context.export_status(context.local_status)
    assert not mocked_publish.called
    # test with external publisher
    context.supvisors.external_publisher = Mock()
    context.export_status(context.local_status)
    expected = {'identifier': context.local_identifier, 'node_name': context.local_status.supvisors_id.host_name,
                'port': 65000, 'statecode': 0, 'statename': 'UNKNOWN',
                'sequence_counter': 0, 'remote_time': 0, 'local_time': 0,
                'loading': 0, 'process_failure': False,
                'fsm_statecode': 0, 'fsm_statename': 'OFF', 'discovery_mode': False,
                'master_identifier': '', 'starting_jobs': False, 'stopping_jobs': False}
    assert context.external_publisher.send_instance_status.call_args_list == [call(expected)]
    assert mocked_publish.call_args_list == [call()]


def test_get_nodes_load(mocker, context):
    """ Test the Context.get_nodes_load method. """
    sup_id = context.local_status.supvisors_id
    # empty test
    assert context.get_nodes_load() == {'10.0.0.1': 0, '10.0.0.2': 0, '10.0.0.3': 0, '10.0.0.4': 0, '10.0.0.5': 0,
                                        sup_id.host_id: 0}
    # update context for some values
    mocker.patch.object(context.local_status, 'get_load', return_value=10)
    mocker.patch.object(context.instances['10.0.0.2'], 'get_load', return_value=8)
    mocker.patch.object(context.instances['test'], 'get_load', return_value=5)
    assert context.get_nodes_load() == {'10.0.0.1': 0, '10.0.0.2': 8, '10.0.0.3': 0, '10.0.0.4': 0, '10.0.0.5': 0,
                                        sup_id.ip_address: 15}


def test_initial_running(context):
    """ Test the check of initial Supvisors instances running. """
    # update mapper
    context.supvisors.mapper.initial_identifiers = ['10.0.0.1', '10.0.0.2', '10.0.0.3']
    assert not context.initial_running()
    # add some RUNNING
    context.local_status._state = SupvisorsInstanceStates.RUNNING
    context.instances['10.0.0.1']._state = SupvisorsInstanceStates.RUNNING
    context.instances['10.0.0.2']._state = SupvisorsInstanceStates.RUNNING
    context.instances['10.0.0.4']._state = SupvisorsInstanceStates.RUNNING
    assert not context.initial_running()
    # add some RUNNING so that all initial instances are RUNNING
    context.instances['10.0.0.3']._state = SupvisorsInstanceStates.RUNNING
    assert context.initial_running()
    # set all RUNNING
    for instance in context.instances.values():
        instance._state = SupvisorsInstanceStates.RUNNING
    assert context.initial_running()


def test_all_running(context):
    """ Test the check of all Supvisors instances running. """
    assert not context.all_running()
    # add some RUNNING
    context.local_status._state = SupvisorsInstanceStates.RUNNING
    context.instances['10.0.0.1']._state = SupvisorsInstanceStates.RUNNING
    context.instances['10.0.0.2']._state = SupvisorsInstanceStates.RUNNING
    context.instances['10.0.0.4']._state = SupvisorsInstanceStates.RUNNING
    assert not context.all_running()
    # set all RUNNING
    for instance in context.instances.values():
        instance._state = SupvisorsInstanceStates.RUNNING
    assert context.all_running()


def test_instances_by_states(context):
    """ Test the access to instances in unknown state. """
    local_identifier = context.supvisors.mapper.local_identifier
    # test initial states
    all_instances = sorted(context.supvisors.mapper.instances.keys())
    assert not context.all_running()
    assert not context.running_core_identifiers()
    assert context.running_identifiers() == []
    assert context.isolating_instances() == []
    assert context.isolation_instances() == []
    assert context.valid_instances() == all_instances
    assert sorted(context.isolation_instances() + context.valid_instances()) == all_instances
    assert context.instances_by_states([SupvisorsInstanceStates.RUNNING, SupvisorsInstanceStates.ISOLATED]) == []
    assert context.instances_by_states([SupvisorsInstanceStates.SILENT]) == []
    assert sorted(context.instances_by_states([SupvisorsInstanceStates.UNKNOWN])) == \
           sorted(context.supvisors.mapper.instances.keys())
    # change states
    context.local_status._state = SupvisorsInstanceStates.RUNNING
    context.instances['10.0.0.1']._state = SupvisorsInstanceStates.SILENT
    context.instances['10.0.0.2']._state = SupvisorsInstanceStates.ISOLATING
    context.instances['10.0.0.3']._state = SupvisorsInstanceStates.ISOLATED
    context.instances['10.0.0.4']._state = SupvisorsInstanceStates.RUNNING
    # test new states
    assert not context.all_running()
    assert not context.running_core_identifiers()
    assert context.running_identifiers() == ['10.0.0.4', local_identifier]
    assert context.isolating_instances() == ['10.0.0.2']
    assert context.isolation_instances() == ['10.0.0.2', '10.0.0.3']
    assert context.valid_instances() == ['10.0.0.1', '10.0.0.4', '10.0.0.5', gethostname(), 'test']
    assert sorted(context.isolation_instances() + context.valid_instances()) == all_instances
    assert context.instances_by_states([SupvisorsInstanceStates.RUNNING, SupvisorsInstanceStates.ISOLATED]) == \
           ['10.0.0.3', '10.0.0.4', local_identifier]
    assert context.instances_by_states([SupvisorsInstanceStates.SILENT]) == ['10.0.0.1']
    assert context.instances_by_states([SupvisorsInstanceStates.UNKNOWN]) == ['10.0.0.5', 'test']


def test_running_core_identifiers_empty(supvisors):
    """ Test if the core instances are in a RUNNING state. """
    supvisors.mapper._core_identifiers = []
    assert supvisors.mapper.core_identifiers == []
    context = Context(supvisors)
    assert not context.running_core_identifiers()


def test_running_core_identifiers_invalid(supvisors):
    """ Test if the core instances are in a RUNNING state. """
    supvisors.mapper._core_identifiers = ['dummy']
    assert supvisors.mapper.core_identifiers == []
    context = Context(supvisors)
    assert not context.running_core_identifiers()


def test_running_core_identifiers(supvisors):
    """ Test if the core instances are in a RUNNING state. """
    supvisors.mapper._core_identifiers = ['10.0.0.1', '10.0.0.4', '<10.0.0.1>10.0.0.1']
    assert supvisors.mapper.core_identifiers == ['10.0.0.1', '10.0.0.4']
    context = Context(supvisors)
    # test initial states
    assert not context.all_running()
    assert not context.running_core_identifiers()
    # change states
    context.local_status._state = SupvisorsInstanceStates.RUNNING
    context.instances['10.0.0.2']._state = SupvisorsInstanceStates.ISOLATING
    context.instances['10.0.0.3']._state = SupvisorsInstanceStates.ISOLATED
    context.instances['10.0.0.4']._state = SupvisorsInstanceStates.RUNNING
    # test new states
    assert not context.all_running()
    assert not context.running_core_identifiers()
    # change states
    context.instances['10.0.0.1']._state = SupvisorsInstanceStates.SILENT
    # test new states
    assert not context.all_running()
    assert not context.running_core_identifiers()
    # change states
    context.instances['10.0.0.1']._state = SupvisorsInstanceStates.RUNNING
    # test new states
    assert not context.all_running()
    assert context.running_core_identifiers()


def test_activate_checked(context):
    """ Test the activation of checked Supvisors instances. """
    # change node states
    context.local_status._state = SupvisorsInstanceStates.RUNNING
    context.instances['10.0.0.1']._state = SupvisorsInstanceStates.SILENT
    context.instances['10.0.0.2']._state = SupvisorsInstanceStates.ISOLATING
    context.instances['10.0.0.3']._state = SupvisorsInstanceStates.ISOLATED
    context.instances['10.0.0.4']._state = SupvisorsInstanceStates.CHECKED
    context.instances['10.0.0.5']._state = SupvisorsInstanceStates.CHECKING
    # check status after call to activate_checked
    context.activate_checked()
    assert context.local_status.state == SupvisorsInstanceStates.RUNNING
    assert context.instances['10.0.0.1'].state == SupvisorsInstanceStates.SILENT
    assert context.instances['10.0.0.2'].state == SupvisorsInstanceStates.ISOLATING
    assert context.instances['10.0.0.3'].state == SupvisorsInstanceStates.ISOLATED
    assert context.instances['10.0.0.4'].state == SupvisorsInstanceStates.RUNNING
    assert context.instances['10.0.0.5'].state == SupvisorsInstanceStates.CHECKING


def test_invalid_unknown(context):
    """ Test the invalidation of unknown Supvisors instances. """
    # change node states
    context.local_status._state = SupvisorsInstanceStates.RUNNING
    context.instances['10.0.0.1']._state = SupvisorsInstanceStates.SILENT
    context.instances['10.0.0.2']._state = SupvisorsInstanceStates.UNKNOWN
    context.instances['10.0.0.3']._state = SupvisorsInstanceStates.ISOLATED
    context.instances['10.0.0.4']._state = SupvisorsInstanceStates.CHECKED
    context.instances['10.0.0.5']._state = SupvisorsInstanceStates.CHECKING
    # check status after call to activate_checked
    context.invalid_unknown()
    assert context.local_status.state == SupvisorsInstanceStates.RUNNING
    assert context.instances['10.0.0.1'].state == SupvisorsInstanceStates.SILENT
    assert context.instances['10.0.0.2'].state == SupvisorsInstanceStates.SILENT
    assert context.instances['10.0.0.3'].state == SupvisorsInstanceStates.ISOLATED
    assert context.instances['10.0.0.4'].state == SupvisorsInstanceStates.CHECKED
    assert context.instances['10.0.0.5'].state == SupvisorsInstanceStates.CHECKING


def test_invalid_remove(context):
    """ Test the invalidation of a remote Supvisors instance.
    Publication is not tested here as already done in test_invalid_local
    and SupvisorsInstanceStatus.serial is tested elsewhere. """
    assert context.supvisors.external_publisher is None
    # check default context
    status = context.instances['10.0.0.1']
    assert context.supvisors_state is None
    assert status.state_modes.state == SupvisorsStates.OFF
    # with this context, only the fence parameter makes a difference
    for fence in [True, False]:
        for auto_fence in [True, False]:
            for state in [SupvisorsInstanceStates.UNKNOWN, SupvisorsInstanceStates.CHECKING,
                          SupvisorsInstanceStates.CHECKED, SupvisorsInstanceStates.RUNNING]:
                # set context
                context.supvisors.options.auto_fence = auto_fence
                status._state = state
                # call for invalidation
                context.invalid(status, fence)
                assert status.state == (SupvisorsInstanceStates.ISOLATING if fence else SupvisorsInstanceStates.SILENT)
    # set Master
    context.master_identifier = '10.0.0.1'
    # fence impact has been checked
    # test auto_fence option not set / no isolation
    context.supvisors.options.auto_fence = False
    for supvisors_state in SupvisorsStates:
        for state in [SupvisorsInstanceStates.UNKNOWN, SupvisorsInstanceStates.CHECKING,
                      SupvisorsInstanceStates.CHECKED, SupvisorsInstanceStates.RUNNING]:
            # set context
            context.master_instance.state_modes.state = supvisors_state
            status._state = state
            # call for invalidation
            context.invalid(status, fence)
            assert status.state == SupvisorsInstanceStates.SILENT
    # test auto_fence option set / isolation made if Supvisors is in a working state
    context.supvisors.options.auto_fence = True
    for supvisors_state in SupvisorsStates:
        working_state = supvisors_state in WORKING_STATES
        for state in [SupvisorsInstanceStates.UNKNOWN, SupvisorsInstanceStates.CHECKING,
                      SupvisorsInstanceStates.CHECKED, SupvisorsInstanceStates.RUNNING]:
            # set context
            context.master_instance.state_modes.state = supvisors_state
            status._state = state
            # call for invalidation
            context.invalid(status, fence)
            assert status.state == (SupvisorsInstanceStates.ISOLATING if working_state
                                    else SupvisorsInstanceStates.SILENT)


def test_invalid_local(mocker, context):
    """ Test the invalidation of the local Supvisors instance. """
    mocked_export = mocker.patch.object(context, 'export_status')
    # get context
    status = context.local_status
    # set Master
    context.master_identifier = '10.0.0.1'
    assert mocked_export.call_args_list == [call(status)]
    mocked_export.reset_mock()
    # same result whatever the fence parameter, auto_fence option, Supvisors state and self FSM state
    for fence in [True, False]:
        for auto_fence in [True, False]:
            for supvisors_state in SupvisorsStates:
                for state in [SupvisorsInstanceStates.UNKNOWN, SupvisorsInstanceStates.CHECKING,
                              SupvisorsInstanceStates.CHECKED, SupvisorsInstanceStates.RUNNING]:
                    # set context
                    context.supvisors.options.auto_fence = auto_fence
                    context.master_instance.state_modes.state = supvisors_state
                    status._state = state
                    # call for invalidation
                    context.invalid(status, fence)
                    assert status.state == SupvisorsInstanceStates.SILENT
                    # check publication
                    assert mocked_export.call_args_list == [call(status)]
                    mocked_export.reset_mock()


def test_get_managed_applications(filled_context):
    """ Test getting all managed applications. """
    # in this test, all applications are managed by default
    expected = ['crash', 'firefox', 'sample_test_1', 'sample_test_2']
    assert sorted(filled_context.get_managed_applications().keys()) == expected
    # de-manage a few ones
    filled_context.applications['firefox'].rules.managed = False
    filled_context.applications['sample_test_1'].rules.managed = False
    # re-test
    assert sorted(filled_context.get_managed_applications().keys()) == ['crash', 'sample_test_2']


def test_is_namespec(filled_context):
    """ Test checking if namespec is known across all supvisors instances. """
    assert filled_context.is_namespec('crash:late_segv')
    assert filled_context.is_namespec('firefox')
    assert filled_context.is_namespec('firefox:firefox')
    assert filled_context.is_namespec('sample_test_1:*')
    assert filled_context.is_namespec('sample_test_2:')
    assert not filled_context.is_namespec('sample_test_2:yeux')
    assert not filled_context.is_namespec('sample_test_2:yeux_03')
    assert not filled_context.is_namespec('sleep')


def test_get_process(filled_context):
    """ Test getting a ProcessStatus based on its namespec. """
    # test with existing namespec
    process = filled_context.get_process('sample_test_1:xclock')
    assert process.application_name == 'sample_test_1'
    assert process.process_name == 'xclock'
    # test with existing namespec (no group)
    process = filled_context.get_process('firefox')
    assert process.application_name == 'firefox'
    assert process.process_name == 'firefox'
    # test with unknown application or process
    with pytest.raises(KeyError):
        filled_context.get_process('unknown:xclock')
    with pytest.raises(KeyError):
        filled_context.get_process('sample_test_2:xclock')


def test_find_runnable_processes(filled_context):
    """ Test getting all processes that are not running and whose namespec matches a regex. """
    all_stopped_namespecs = ['firefox', 'sample_test_1:xclock', 'sample_test_1:xlogo',
                             'sample_test_2:sleep', 'sample_test_2:yeux_00']
    # use regex that returns everything
    processes = filled_context.find_runnable_processes('')
    assert sorted([process.namespec for process in processes]) == all_stopped_namespecs
    processes = filled_context.find_runnable_processes('^.*$')
    assert sorted([process.namespec for process in processes]) == all_stopped_namespecs
    # use regex that returns a selection
    processes = filled_context.find_runnable_processes(':x')
    assert sorted([process.namespec for process in processes]) == ['sample_test_1:xclock', 'sample_test_1:xlogo']
    processes = filled_context.find_runnable_processes('[ox]$')
    assert sorted([process.namespec for process in processes]) == ['firefox', 'sample_test_1:xlogo']


def test_conflicts(filled_context):
    """ Test the detection of conflicting processes. """
    # test no conflict
    assert not filled_context.conflicting()
    assert filled_context.conflicts() == []
    # add instances to one process
    process1 = next(process for application in filled_context.applications.values()
                    for process in application.processes.values()
                    if process.running())
    process1.running_identifiers.update(filled_context.instances.keys())
    # test conflict is detected
    assert filled_context.conflicting()
    assert filled_context.conflicts() == [process1]
    # add instances to one other process
    process2 = next(process for application in filled_context.applications.values()
                    for process in application.processes.values()
                    if process.stopped())
    process2.running_identifiers.update(filled_context.instances.keys())
    # test conflict is detected
    assert filled_context.conflicting()
    assert filled_context.conflicts() == [process1, process2]
    # empty instances of first process list
    process1.running_identifiers.clear()
    # test conflict is still detected
    assert filled_context.conflicting()
    assert filled_context.conflicts() == [process2]
    # empty instances of second process list
    process2.running_identifiers.clear()
    # test no conflict
    assert not filled_context.conflicting()
    assert filled_context.conflicts() == []


def test_setdefault_application(context):
    """ Test the access / creation of an application status. """
    # check application list
    assert context.applications == {}
    # in this test, there is no rules file so application rules managed won't be changed by load_application_rules
    application1 = context.setdefault_application('dummy_1')
    assert context.applications == {'dummy_1': application1}
    assert not application1.rules.managed
    assert application1.rules.starting_failure_strategy == StartingFailureStrategies.ABORT
    assert application1.rules.running_failure_strategy == RunningFailureStrategies.CONTINUE
    # so patch load_application_rules to avoid that
    context.supvisors.parser.load_application_rules = load_application_rules
    # get application
    application1 = context.setdefault_application('dummy_1')
    # check application list. rules are not re-evaluated so application still not managed
    assert context.applications == {'dummy_1': application1}
    assert not application1.rules.managed
    assert application1.rules.starting_failure_strategy == StartingFailureStrategies.ABORT
    assert application1.rules.running_failure_strategy == RunningFailureStrategies.CONTINUE
    # get application
    application2 = context.setdefault_application('dummy_2')
    # check application list
    assert context.applications == {'dummy_1': application1, 'dummy_2': application2}
    assert application2.rules.managed
    assert application2.rules.starting_failure_strategy == StartingFailureStrategies.STOP
    assert application2.rules.running_failure_strategy == RunningFailureStrategies.RESTART_APPLICATION


def test_setdefault_process(context):
    """ Test the access / creation of a process status. """
    # check application list
    assert context.applications == {}
    # test data
    dummy_info1 = any_process_info()
    dummy_info1.update({'group': 'dummy_application_1', 'name': 'dummy_process_1'})
    dummy_info2 = any_process_info()
    dummy_info2.update({'group': 'dummy_application_2', 'name': 'dummy_process_2'})
    # in this test, there is no rules file so application rules managed won't be changed by load_application_rules
    process1 = context.setdefault_process('10.0.0.1', dummy_info1)
    assert process1.application_name == 'dummy_application_1'
    assert process1.process_name == 'dummy_process_1'
    assert list(context.applications.keys()) == ['dummy_application_1']
    application1 = context.applications['dummy_application_1']
    assert application1.processes == {'dummy_process_1': process1}
    assert not application1.rules.managed
    assert application1.rules.starting_failure_strategy == StartingFailureStrategies.ABORT
    assert application1.rules.running_failure_strategy == RunningFailureStrategies.CONTINUE
    assert process1.rules.starting_failure_strategy == StartingFailureStrategies.ABORT
    assert process1.rules.running_failure_strategy == RunningFailureStrategies.CONTINUE
    # so patch load_application_rules to avoid that
    context.supvisors.parser.load_application_rules = load_application_rules
    # get process
    process1 = context.setdefault_process('10.0.0.1', dummy_info1)
    # check application still unmanaged
    application1 = context.applications['dummy_application_1']
    assert not application1.rules.managed
    # no change on rules because application already exists
    assert application1.rules.starting_failure_strategy == StartingFailureStrategies.ABORT
    assert application1.rules.running_failure_strategy == RunningFailureStrategies.CONTINUE
    assert process1.rules.starting_failure_strategy == StartingFailureStrategies.ABORT
    assert process1.rules.running_failure_strategy == RunningFailureStrategies.CONTINUE
    # get application
    process2 = context.setdefault_process('10.0.0.1', dummy_info2)
    # check application and process list
    assert sorted(context.applications.keys()) == ['dummy_application_1', 'dummy_application_2']
    application1 = context.applications['dummy_application_1']
    application2 = context.applications['dummy_application_2']
    assert application1.processes == {'dummy_process_1': process1}
    assert application2.processes == {'dummy_process_2': process2}
    assert not application1.rules.managed
    assert application2.rules.managed
    assert application2.rules.starting_failure_strategy == StartingFailureStrategies.STOP
    assert application2.rules.running_failure_strategy == RunningFailureStrategies.RESTART_APPLICATION
    assert process2.rules.starting_failure_strategy == StartingFailureStrategies.STOP
    assert process2.rules.running_failure_strategy == RunningFailureStrategies.RESTART_APPLICATION


def test_load_processes(mocker, context):
    """ Test the storage of processes handled by Supervisor on a given node. """
    mocker.patch('supvisors.application.ApplicationStatus.update_sequences')
    mocker.patch('supvisors.application.ApplicationStatus.update_status')
    mocked_write = mocker.patch.object(context.supvisors.supervisor_data, 'write_disabilities')
    # check application list
    assert context.applications == {}
    for node in context.instances.values():
        assert node.processes == {}
    # load ProcessInfoDatabase in unknown node
    with pytest.raises(KeyError):
        context.load_processes('10.0.0.0', database_copy())
    assert context.applications == {}
    for node in context.instances.values():
        assert node.processes == {}
    assert not mocked_write.called
    # force local_identifier
    context.supvisors.mapper.local_identifier = '10.0.0.2'
    # load ProcessInfoDatabase with known node
    context.load_processes('10.0.0.1', database_copy())
    # check context contents
    assert sorted(context.applications.keys()) == ['crash', 'firefox', 'sample_test_1', 'sample_test_2']
    assert sorted(context.applications['crash'].processes.keys()) == ['late_segv', 'segv']
    assert sorted(context.applications['firefox'].processes.keys()) == ['firefox']
    assert sorted(context.applications['sample_test_1'].processes.keys()) == ['xclock', 'xfontsel', 'xlogo']
    assert sorted(context.applications['sample_test_2'].processes.keys()) == ['sleep', 'yeux_00', 'yeux_01']
    assert sorted(context.instances['10.0.0.1'].processes.keys()) == ['crash:late_segv', 'crash:segv', 'firefox',
                                                                      'sample_test_1:xclock', 'sample_test_1:xfontsel',
                                                                      'sample_test_1:xlogo', 'sample_test_2:sleep',
                                                                      'sample_test_2:yeux_00', 'sample_test_2:yeux_01']
    assert context.instances['10.0.0.2'].processes == {}
    assert not mocked_write.called
    # check application calls
    assert all(application.update_sequences.called and application.update_status.called
               for application in context.applications.values())
    mocker.resetall()
    # load ProcessInfoDatabase in other known node
    context.load_processes('10.0.0.2', database_copy())
    # check context contents
    assert sorted(context.applications.keys()) == ['crash', 'firefox', 'sample_test_1', 'sample_test_2']
    assert sorted(context.applications['crash'].processes.keys()) == ['late_segv', 'segv']
    assert sorted(context.applications['firefox'].processes.keys()) == ['firefox']
    assert sorted(context.applications['sample_test_1'].processes.keys()) == ['xclock', 'xfontsel', 'xlogo']
    assert sorted(context.applications['sample_test_2'].processes.keys()) == ['sleep', 'yeux_00', 'yeux_01']
    expected = ['crash:late_segv', 'crash:segv', 'firefox', 'sample_test_1:xclock', 'sample_test_1:xfontsel',
                'sample_test_1:xlogo', 'sample_test_2:sleep', 'sample_test_2:yeux_00', 'sample_test_2:yeux_01']
    assert sorted(context.instances['10.0.0.2'].processes.keys()) == expected
    assert context.instances['10.0.0.1'].processes == context.instances['10.0.0.2'].processes
    assert mocked_write.call_args_list == [call(False)]
    # check application calls
    assert all(application.update_sequences.called and application.update_status.called
               for application in context.applications.values())
    mocker.resetall()
    # load different database in other known node
    info = any_process_info()
    info.update({'group': 'dummy_application', 'name': 'dummy_process'})
    database = [info]
    context.load_processes('10.0.0.4', database)
    # check context contents
    assert sorted(context.applications.keys()) == ['crash', 'dummy_application', 'firefox',
                                                   'sample_test_1', 'sample_test_2']
    assert list(context.instances['10.0.0.4'].processes.keys()) == ['dummy_application:dummy_process']
    assert sorted(context.applications['crash'].processes.keys()) == ['late_segv', 'segv']
    assert sorted(context.applications['dummy_application'].processes.keys()) == ['dummy_process']
    assert sorted(context.applications['firefox'].processes.keys()) == ['firefox']
    assert sorted(context.applications['sample_test_1'].processes.keys()) == ['xclock', 'xfontsel', 'xlogo']
    assert sorted(context.applications['sample_test_2'].processes.keys()) == ['sleep', 'yeux_00', 'yeux_01']
    assert not mocked_write.called
    # check application calls
    assert all(application.update_sequences.called and application.update_status.called
               for application in context.applications.values())


def test_on_instance_state_event_unknown(mocker, context):
    """ Test the Context.on_instance_state_event method with unknown identifier. """
    context.supvisors.external_publisher = Mock(spec=EventPublisherInterface)
    mocked_send = context.supvisors.external_publisher.send_instance_status
    mocked_publish = mocker.patch.object(context, '_publish_state_mode')
    event = {'fsm_statecode': 2, 'fsm_statename': 'DEPLOYMENT',
             'discovery_mode': True,
             'master_identifier': '',
             'starting_jobs': True, 'stopping_jobs': False}
    with pytest.raises(KeyError):
        context.on_instance_state_event('10.0.0.0', event)
    assert not mocked_publish.called
    assert not mocked_send.called
    assert not context.supvisors.external_publisher.send_instance_status.called


def test_on_instance_state_event_isolated(mocker, context):
    """ Test the Context.on_instance_state_event method with isolated supvisors instance. """
    context.supvisors.external_publisher = Mock(spec=EventPublisherInterface)
    mocked_send = context.supvisors.external_publisher.send_instance_status
    mocked_publish = mocker.patch.object(context, '_publish_state_mode')
    # test both isolation states
    for state in ISOLATION_STATES:
        context.instances['10.0.0.2']._state = state
        event = {'fsm_statecode': 2, 'fsm_statename': 'DEPLOYMENT',
                 'discovery_mode': True,
                 'master_identifier': '',
                 'starting_jobs': True, 'stopping_jobs': False}
        assert not context.on_instance_state_event('10.0.0.2', event)
        assert context.instances['10.0.0.2'].state_modes == StateModes()
        assert not mocked_publish.called
        assert not mocked_send.called
        assert not context.supvisors.external_publisher.send_instance_status.called


def test_on_instance_state_event(mocker, context):
    """ Test the Context.on_instance_state_event method with non-isolated Supvisors instance. """
    context.supvisors.external_publisher = Mock(spec=EventPublisherInterface)
    mocked_send = context.supvisors.external_publisher.send_instance_status
    mocked_publish = mocker.patch.object(context, '_publish_state_mode')
    # test using the RUNNING state
    context.instances['10.0.0.1']._state = SupvisorsInstanceStates.RUNNING
    # test with no Master in the event
    event = {'fsm_statecode': 2, 'fsm_statename': 'DEPLOYMENT',
             'discovery_mode': False,
             'master_identifier': '',
             'starting_jobs': True, 'stopping_jobs': False}
    context.on_instance_state_event('10.0.0.1', event)
    assert context.instances['10.0.0.1'].state_modes == StateModes(SupvisorsStates.DEPLOYMENT, False, '', True, False)
    expected = {'identifier': '10.0.0.1', 'node_name': '10.0.0.1', 'port': 65000,
                'statecode': 3, 'statename': 'RUNNING',
                'sequence_counter': 0, 'remote_time': 0, 'local_time': 0, 'loading': 0, 'process_failure': False,
                'fsm_statecode': 2, 'fsm_statename': 'DEPLOYMENT', 'discovery_mode': False, 'master_identifier': '',
                'starting_jobs': True, 'stopping_jobs': False}
    assert mocked_send.call_args_list == [call(expected)]
    assert mocked_publish.called
    # test with Master in the event and no Master known by the local Supvisors instance
    # the Master is accepted by the local Supvisors instance
    event['master_identifier'] = '10.0.0.2'
    context.on_instance_state_event('10.0.0.1', event)
    assert context.master_identifier == '10.0.0.2'
    assert context.instances['10.0.0.1'].state_modes == StateModes(SupvisorsStates.DEPLOYMENT, False,
                                                                   '10.0.0.2', True, False)
    # test with Master in the event and different from the Master known by the local Supvisors instance
    event['master_identifier'] = '10.0.0.3'
    context.on_instance_state_event('10.0.0.1', event)
    assert context.master_identifier == '10.0.0.2'
    assert context.instances['10.0.0.1'].state_modes == StateModes(SupvisorsStates.DEPLOYMENT, False,
                                                                   '10.0.0.3', True, False)
    # try the latest 2 steps with an event coming from a Supvisors instance about to restart or shut down
    event.update({'fsm_statecode': 5, 'fsm_statename': 'RESTARTING'})
    context.on_instance_state_event('10.0.0.1', event)
    assert context.master_identifier == '10.0.0.2'
    assert context.instances['10.0.0.1'].state_modes == StateModes(SupvisorsStates.RESTARTING, False,
                                                                   '10.0.0.3', True, False)
    # and Master is not accepted
    context.master_identifier = ''
    event.update({'fsm_statecode': 7, 'fsm_statename': 'FINAL'})
    context.on_instance_state_event('10.0.0.1', event)
    assert context.master_identifier == ''
    assert context.instances['10.0.0.1'].state_modes == StateModes(SupvisorsStates.FINAL, False,
                                                                   '10.0.0.3', True, False)


def test_authorization_unknown(context):
    """ Test the Context.on_authorization method with unknown identifier. """
    # check no exception / no change
    for fencing in [True, False]:
        context.supvisors.options.auto_fence = fencing
        for authorization in [True, False]:
            with pytest.raises(KeyError):
                context.on_authorization('10.0.0.0', authorization)
            assert '10.0.0.0' not in context.instances


def test_authorization_not_checking(context):
    """ est the Context.on_authorization method with non-CHECKING identifier. """
    # check no change
    for fencing in [True, False]:
        context.supvisors.options.auto_fence = fencing
        for authorization in [True, False]:
            for state in SupvisorsInstanceStates:
                if state != SupvisorsInstanceStates.CHECKING:
                    context.instances['10.0.0.1']._state = state
                    context.on_authorization('10.0.0.1', authorization)
                    assert context.instances['10.0.0.1'].state == state


def test_authorization_checking_normal(mocker, context):
    """ Test the handling of an authorization event. """
    mocked_invalid = mocker.patch.object(context, 'invalid')
    # test current state not CHECKING
    status = context.instances['10.0.0.1']
    status._state = SupvisorsInstanceStates.RUNNING
    assert not context.on_authorization('10.0.0.1', True)
    assert not mocked_invalid.called
    # test authorization None (error in handshake)
    status._state = SupvisorsInstanceStates.CHECKING
    assert not context.on_authorization('10.0.0.1', None)
    assert not mocked_invalid.called
    assert status.state == SupvisorsInstanceStates.UNKNOWN
    # test not authorized
    status._state = SupvisorsInstanceStates.CHECKING
    assert not context.on_authorization('10.0.0.1', False)
    assert mocked_invalid.call_args_list == [call(status, True)]
    mocked_invalid.reset_mock()
    # test authorized
    assert context.on_authorization('10.0.0.1', True)
    assert not mocked_invalid.called


def test_on_local_tick_event(mocker, context):
    """ Test the handling of a TICK event on the local Supvisors instance. """
    mocker.patch('supvisors.context.time.time', return_value=3600)
    mocked_check = context.supvisors.internal_com.pusher.send_check_instance
    context.supvisors.external_publisher = Mock(spec=EventPublisherInterface)
    mocked_send = context.supvisors.external_publisher.send_instance_status
    # check the current context
    status = context.local_status
    assert status.state == SupvisorsInstanceStates.UNKNOWN
    status.sequence_counter = 7
    status.local_sequence_counter = 7
    assert status.remote_time == 0
    assert status.local_time == 0
    # when a TICK is received from a SILENT or UNKNOWN state, check that:
    #   * Supvisors instance is CHECKING
    #   * time is updated using local time
    #   * send_check_instance is called
    #   * Supvisors instance status is sent
    for state in [SupvisorsInstanceStates.UNKNOWN, SupvisorsInstanceStates.SILENT]:
        status._state = state
        context.on_local_tick_event({'sequence_counter': 31, 'when': 1234})
        assert status.state == SupvisorsInstanceStates.CHECKING
        assert status.sequence_counter == 31
        assert status.local_sequence_counter == 31  # same as sequence_counter
        assert status.remote_time == 1234
        assert status.local_time == 1234  # same as remote_time
        assert mocked_check.call_args_list == [call(context.local_identifier)]
        expected = {'identifier': context.local_identifier,
                    'node_name': context.local_status.supvisors_id.host_name,
                    'port': 65000, 'sequence_counter': 31,
                    'statecode': 1, 'statename': 'CHECKING',
                    'remote_time': 1234, 'local_time': 1234,
                    'loading': 0, 'process_failure': False,
                    'fsm_statecode': 0, 'fsm_statename': 'OFF',
                    'discovery_mode': False, 'master_identifier': '',
                    'starting_jobs': False, 'stopping_jobs': False}
        assert mocked_send.call_args_list == [call(expected)]
        mocked_check.reset_mock()
        mocked_send.reset_mock()
    # when a TICK is received from a CHECKING / CHECKED or RUNNING state, check that:
    #   * Supvisors instance state is unchanged
    #   * time is updated using local time
    #   * send_check_instance is NOT called
    #   * Supvisors instance status is sent
    for state in [SupvisorsInstanceStates.CHECKING, SupvisorsInstanceStates.CHECKED, SupvisorsInstanceStates.RUNNING]:
        status._state = state
        context.on_local_tick_event({'sequence_counter': 57, 'when': 5678})
        assert status.state == state
        assert status.sequence_counter == 57
        assert status.local_sequence_counter == 57  # same as sequence_counter
        assert status.remote_time == 5678
        assert status.local_time == 5678  # same as remote_time
        assert not mocked_check.called
        expected = {'identifier': context.local_identifier,
                    'node_name': context.local_status.supvisors_id.host_name,
                    'port': 65000, 'sequence_counter': 57,
                    'statecode': state.value, 'statename': state.name,
                    'remote_time': 5678, 'local_time': 5678,
                    'loading': 0, 'process_failure': False,
                    'fsm_statecode': 0, 'fsm_statename': 'OFF',
                    'discovery_mode': False, 'master_identifier': '',
                    'starting_jobs': False, 'stopping_jobs': False}
        assert mocked_send.call_args_list == [call(expected)]
        mocked_send.reset_mock()


def test_on_tick_event(mocker, context):
    """ Test the handling of a tick event from a remote Supvisors instance. """
    mocker.patch('supvisors.context.time.time', return_value=3600)
    mocked_stereotype = mocker.patch.object(context.supvisors.mapper, 'assign_stereotypes')
    mocked_check = context.supvisors.internal_com.pusher.send_check_instance
    context.supvisors.external_publisher = Mock(spec=EventPublisherInterface)
    mocked_send = context.supvisors.external_publisher.send_instance_status
    # check the current context
    assert context.local_identifier != '10.0.0.1'
    context.instances[context.local_identifier].sequence_counter = 7
    # get reference Supvisors instance (not the local one)
    status = context.instances['10.0.0.1']
    assert status.state == SupvisorsInstanceStates.UNKNOWN
    assert status.sequence_counter == 0
    assert status.local_sequence_counter == 0
    assert status.remote_time == 0
    assert status.local_time == 0
    # check no processing as long as local Supvisors instance is not RUNNING
    assert context.local_status.state == SupvisorsInstanceStates.UNKNOWN
    event = {'sequence_counter': 31, 'when': 1234, 'stereotypes': {'test'}}
    context.on_tick_event('10.0.0.1', event)
    assert not mocked_stereotype.called
    assert not mocked_check.called
    assert not mocked_send.called
    assert status.state == SupvisorsInstanceStates.UNKNOWN
    assert status.sequence_counter == 0
    assert status.local_sequence_counter == 0
    assert status.remote_time == 0
    assert status.local_time == 0
    # set local Supvisors instance state to RUNNING
    context.local_status._state = SupvisorsInstanceStates.RUNNING
    # check no change with known Supvisors instance in isolation
    for state in [SupvisorsInstanceStates.ISOLATING, SupvisorsInstanceStates.ISOLATED]:
        status._state = state
        context.on_tick_event('10.0.0.1', event)
        assert status.state == state
        assert status.sequence_counter == 0
        assert status.local_sequence_counter == 0
        assert status.remote_time == 0
        assert status.local_time == 0
        assert not mocked_stereotype.called
        assert not mocked_check.called
        assert not mocked_send.called
    # when a TICK is received from a SILENT or UNKNOWN state on a remote Supvisors instance, check that:
    #   * Supvisors instance is CHECKING
    #   * time is updated using local time
    #   * send_check_instance is called
    #   * Supvisors instance status is sent
    for state in [SupvisorsInstanceStates.UNKNOWN, SupvisorsInstanceStates.SILENT]:
        status._state = state
        context.on_tick_event('10.0.0.1', event)
        assert status.state == SupvisorsInstanceStates.CHECKING
        assert status.sequence_counter == 31
        assert status.local_sequence_counter == 7
        assert status.remote_time == 1234
        assert status.local_time == 3600
        assert mocked_stereotype.call_args_list == [call('10.0.0.1', {'test'})]
        assert mocked_check.call_args_list == [call('10.0.0.1')]
        expected = {'identifier': '10.0.0.1', 'node_name': '10.0.0.1',
                    'port': 65000, 'sequence_counter': 31,
                    'statecode': 1, 'statename': 'CHECKING',
                    'remote_time': 1234, 'local_time': 3600,
                    'loading': 0, 'process_failure': False,
                    'fsm_statecode': 0, 'fsm_statename': 'OFF',
                    'discovery_mode': False, 'master_identifier': '',
                    'starting_jobs': False, 'stopping_jobs': False}
        assert mocked_send.call_args_list == [call(expected)]
        mocked_stereotype.reset_mock()
        mocked_check.reset_mock()
        mocked_send.reset_mock()
    # check that node time is updated and node status is sent
    event = {'sequence_counter': 57, 'when': 5678, 'stereotypes': {'test'}}
    for state in [SupvisorsInstanceStates.CHECKING, SupvisorsInstanceStates.RUNNING]:
        status._state = state
        context.on_tick_event('10.0.0.1', event)
        assert status.state == state
        assert status.sequence_counter == 57
        assert status.local_sequence_counter == 7
        assert status.remote_time == 5678
        assert status.local_time == 3600
        assert mocked_stereotype.call_args_list == [call('10.0.0.1', {'test'})]
        assert not mocked_check.called
        expected = {'identifier': '10.0.0.1', 'node_name': '10.0.0.1', 'port': 65000, 'sequence_counter': 57,
                    'statecode': state.value, 'statename': state.name,
                    'remote_time': 5678, 'local_time': 3600,
                    'loading': 0, 'process_failure': False,
                    'fsm_statecode': 0, 'fsm_statename': 'OFF',
                    'discovery_mode': False, 'master_identifier': '',
                    'starting_jobs': False, 'stopping_jobs': False}
        assert mocked_send.call_args_list == [call(expected)]
        mocked_stereotype.reset_mock()
        mocked_send.reset_mock()
    # check that the Supvisors instance local_sequence_counter is forced to 0 when its sequence_counter
    #   is lower than expected (stealth restart)
    status._state = SupvisorsInstanceStates.RUNNING
    event = {'sequence_counter': 2, 'when': 6789, 'stereotypes': set()}
    context.on_tick_event('10.0.0.1', event)
    assert status.state == SupvisorsInstanceStates.RUNNING
    assert status.sequence_counter == 2
    assert status.local_sequence_counter == 0  # invalidated
    assert status.remote_time == 6789
    assert status.local_time == 3600
    assert mocked_stereotype.call_args_list == [call('10.0.0.1', set())]
    assert not mocked_check.called
    expected = {'identifier': '10.0.0.1', 'node_name': '10.0.0.1',
                'port': 65000, 'sequence_counter': 2,
                'statecode': state.value, 'statename': state.name,
                'remote_time': 6789, 'local_time': 3600,
                'loading': 0, 'process_failure': False,
                'fsm_statecode': 0, 'fsm_statename': 'OFF',
                'discovery_mode': False, 'master_identifier': '',
                'starting_jobs': False, 'stopping_jobs': False}
    mocked_stereotype.reset_mock()
    assert mocked_send.call_args_list == [call(expected)]


def test_check_process_exception_closing(mocker, context):
    """ Test the Context.check_process method with expected context. """
    mocked_invalid = mocker.patch.object(context, 'invalid')
    event = {'group': 'dummy_appli', 'name': 'dummy_process'}
    # test with unknown application
    for fsm_state in CLOSING_STATES:
        context.supvisors.fsm.state = fsm_state
        assert context.check_process(context.instances['10.0.0.1'], event) is None
        assert not mocked_invalid.called
    # test with unknown process
    application = context.applications['dummy_appli'] = create_application('dummy_appli', context.supvisors)
    for fsm_state in CLOSING_STATES:
        context.supvisors.fsm.state = fsm_state
        assert context.check_process(context.instances['10.0.0.1'], event) is None
        assert not mocked_invalid.called
    # test with no information in process for identifier
    application.processes['dummy_process'] = create_process(event, context.supvisors)
    for fsm_state in CLOSING_STATES:
        context.supvisors.fsm.state = fsm_state
        assert context.check_process(context.instances['10.0.0.1'], event) is None
        assert not mocked_invalid.called


def test_check_process_exception_operational(mocker, context):
    """ Test the Context.check_process method with expected context. """
    mocked_invalid = mocker.patch.object(context, 'invalid')
    normal_states = [SupvisorsStates.INITIALIZATION, SupvisorsStates.DEPLOYMENT, SupvisorsStates.OPERATION,
                     SupvisorsStates.CONCILIATION]
    event = {'group': 'dummy_appli', 'name': 'dummy_process'}
    # test with unknown application
    for fsm_state in normal_states:
        context.supvisors.fsm.state = fsm_state
        assert context.check_process(context.instances['10.0.0.1'], event) is None
        assert mocked_invalid.call_args_list == [call(context.instances['10.0.0.1'])]
        mocker.resetall()
    # test with unknown process
    application = context.applications['dummy_appli'] = create_application('dummy_appli', context.supvisors)
    for fsm_state in normal_states:
        context.supvisors.fsm.state = fsm_state
        assert context.check_process(context.instances['10.0.0.1'], event) is None
        assert mocked_invalid.call_args_list == [call(context.instances['10.0.0.1'])]
        mocker.resetall()
    # test with no information in process for identifier
    application.processes['dummy_process'] = create_process(event, context.supvisors)
    for fsm_state in normal_states:
        context.supvisors.fsm.state = fsm_state
        assert context.check_process(context.instances['10.0.0.1'], event) is None
        assert mocked_invalid.call_args_list == [call(context.instances['10.0.0.1'])]
        mocker.resetall()


def test_check_process_normal(mocker, context):
    """ Test the Context.check_process method with expected context. """
    mocked_invalid = mocker.patch.object(context, 'invalid')
    # test with process information related to identifier
    event = {'group': 'dummy_appli', 'name': 'dummy_process'}
    application = context.applications['dummy_appli'] = create_application('dummy_appli', context.supvisors)
    process = application.processes['dummy_process'] = create_process(event, context.supvisors)
    process.info_map['10.0.0.1'] = {}
    group_event = {'group': 'dummy_appli', 'name': '*'}
    process_event = {'group': 'dummy_appli', 'name': 'dummy_process'}
    for fsm_state in SupvisorsStates:
        # test with group and process information
        context.supvisors.fsm.state = fsm_state
        assert context.check_process(context.instances['10.0.0.1'], process_event) == (application, process)
        assert not mocked_invalid.called
        # test with group information only
        assert context.check_process(context.instances['10.0.0.1'], group_event) == (application, None)
        assert not mocked_invalid.called


def test_process_removed_event_unknown_identifier(context):
    """ Test the Context.on_process_removed_event with an unknown Supvisors instance. """
    context.supvisors.external_publisher = Mock(spec=EventPublisherInterface)
    mocked_publisher = context.supvisors.external_publisher
    with pytest.raises(KeyError):
        context.on_process_removed_event('10.0.0.0', {})
    assert not mocked_publisher.send_process_event.called
    assert not mocked_publisher.send_process_status.called
    assert not mocked_publisher.send_application_status.called


def test_process_removed_event_not_running(context):
    """ Test the Context.on_process_removed_event with a non-RUNNING Supvisors instance. """
    context.supvisors.external_publisher = Mock(spec=EventPublisherInterface)
    mocked_publisher = context.supvisors.external_publisher
    # get instance status used for tests
    instance_status = context.instances['10.0.0.1']
    # check no change with known instance not RUNNING
    for state in SupvisorsInstanceStates:
        if state not in [SupvisorsInstanceStates.CHECKED, SupvisorsInstanceStates.RUNNING]:
            instance_status._state = state
            context.on_process_removed_event('10.0.0.1', {})
            assert not mocked_publisher.send_process_event.called
            assert not mocked_publisher.send_process_status.called
            assert not mocked_publisher.send_application_status.called


def test_process_removed_event_running_process_unknown(mocker, context):
    """ Test the Context.on_process_removed_event with a RUNNING Supvisors instance and an unknown process. """
    mocker.patch.object(context, 'check_process', return_value=None)
    context.supvisors.external_publisher = Mock(spec=EventPublisherInterface)
    mocked_publisher = context.supvisors.external_publisher
    assert context.supvisors.options.auto_fence
    event = {'group': 'dummy_appli', 'name': 'dummy_process'}
    # get instance status used for tests
    instance_status = context.instances['10.0.0.1']
    instance_status._state = SupvisorsInstanceStates.RUNNING
    # check no change with unknown process
    context.on_process_removed_event('10.0.0.1', event)
    assert not mocked_publisher.send_process_event.called
    assert not mocked_publisher.send_process_status.called
    assert not mocked_publisher.send_application_status.called


def test_on_process_removed_event_running_process(mocker, context):
    """ Test the handling of a known process removed event coming from a RUNNING Supvisors instance. """
    mocker.patch('supvisors.process.time', return_value=1234)
    context.supvisors.external_publisher = Mock(spec=EventPublisherInterface)
    mocked_publisher = context.supvisors.external_publisher
    # add context. processes removed are expected to be STOPPED
    application = context.applications['dummy_application'] = create_application('dummy_application', context.supvisors)
    dummy_info_1 = {'group': 'dummy_application', 'name': 'dummy_process_1', 'expected': True, 'state': 0,
                    'now': 1234, 'stop': 1230, 'extra_args': '-h',
                    'program_name': 'dummy_process', 'process_index': 0}
    dummy_info_2 = {'group': 'dummy_application', 'name': 'dummy_process_2', 'expected': True, 'state': 0,
                    'now': 4321, 'stop': 4300, 'extra_args': '',
                    'program_name': 'dummy_process', 'process_index': 1}
    process_1 = create_process(dummy_info_1, context.supvisors)
    process_2 = create_process(dummy_info_2, context.supvisors)
    application.add_process(process_2)
    process_1.add_info('10.0.0.1', dummy_info_1)
    process_1.add_info('10.0.0.2', dummy_info_1)
    process_2.add_info('10.0.0.2', dummy_info_2)
    application.add_process(process_1)
    application.add_process(process_2)
    context.instances['10.0.0.1'].processes[process_1.namespec] = process_1
    context.instances['10.0.0.2'].processes[process_1.namespec] = process_1
    context.instances['10.0.0.2'].processes[process_2.namespec] = process_2
    # get instances status used for tests
    context.instances['10.0.0.1']._state = SupvisorsInstanceStates.RUNNING
    context.instances['10.0.0.2']._state = SupvisorsInstanceStates.RUNNING
    # update sequences for the test
    application.rules.managed = True
    application.update_sequences()
    application.update_status()
    assert application.state == ApplicationStates.STOPPED
    # payload for parameter
    dummy_event = {'group': 'dummy_application', 'name': 'dummy_process_1'}
    mocker.patch.object(context, 'check_process', return_value=(application, process_1))
    # check normal behaviour in RUNNING state when process_1 is removed from 10.0.0.1
    # as process will still include a definition on 10.0.0.2, no impact expected on process and application
    context.on_process_removed_event('10.0.0.1', dummy_event)
    assert sorted(process_1.info_map.keys()) == ['10.0.0.2']
    assert sorted(process_2.info_map.keys()) == ['10.0.0.2']
    assert application.state == ApplicationStates.STOPPED
    assert sorted(context.instances['10.0.0.1'].processes.keys()) == []
    assert sorted(context.instances['10.0.0.2'].processes.keys()) == ['dummy_application:dummy_process_1',
                                                                      'dummy_application:dummy_process_2']
    expected = '10.0.0.1', {'group': 'dummy_application', 'name': 'dummy_process_1', 'state': -1}
    assert mocked_publisher.send_process_event.call_args_list == [call(*expected)]
    assert not mocked_publisher.send_process_status.called
    assert not mocked_publisher.send_application_status.called
    mocked_publisher.send_process_event.reset_mock()
    # check normal behaviour in RUNNING state when process_1 is removed from 10.0.0.2
    # process_1 is removed from application and instance status but application is still STARTING due to process_2
    context.on_process_removed_event('10.0.0.2', dummy_event)
    assert list(process_1.info_map.keys()) == []
    assert sorted(process_2.info_map.keys()) == ['10.0.0.2']
    assert application.state == ApplicationStates.STOPPED
    assert sorted(context.instances['10.0.0.1'].processes.keys()) == []
    assert sorted(context.instances['10.0.0.2'].processes.keys()) == ['dummy_application:dummy_process_2']
    expected = '10.0.0.2', {'group': 'dummy_application', 'name': 'dummy_process_1', 'state': -1}
    assert mocked_publisher.send_process_event.call_args_list == [call(*expected)]
    expected = {'application_name': 'dummy_application', 'process_name': 'dummy_process_1',
                'statecode': -1, 'statename': 'DELETED', 'expected_exit': True,
                'last_event_time': 1234, 'identifiers': [], 'extra_args': ''}
    assert mocked_publisher.send_process_status.call_args_list == [call(expected)]
    expected = {'application_name': 'dummy_application', 'managed': True,
                'statecode': 0, 'statename': 'STOPPED',
                'major_failure': False, 'minor_failure': False}
    assert mocked_publisher.send_application_status.call_args_list == [call(expected)]
    mocked_publisher.send_process_event.reset_mock()
    mocked_publisher.send_process_status.reset_mock()
    mocked_publisher.send_application_status.reset_mock()
    # check normal behaviour in RUNNING state when process_2 is removed from 10.0.0.2
    # no more process in application and instance status so application is removed
    dummy_event = {'group': 'dummy_application', 'name': 'dummy_process_2'}
    mocker.patch.object(context, 'check_process', return_value=(application, process_2))
    context.on_process_removed_event('10.0.0.2', dummy_event)
    assert list(process_1.info_map.keys()) == []
    assert list(process_2.info_map.keys()) == []
    assert application.state == ApplicationStates.DELETED
    expected = '10.0.0.2', {'group': 'dummy_application', 'name': 'dummy_process_2', 'state': -1}
    assert mocked_publisher.send_process_event.call_args_list == [call(*expected)]
    expected = {'application_name': 'dummy_application', 'process_name': 'dummy_process_2',
                'statecode': -1, 'statename': 'DELETED', 'expected_exit': True,
                'last_event_time': 1234, 'identifiers': [], 'extra_args': ''}
    assert mocked_publisher.send_process_status.call_args_list == [call(expected)]
    expected = {'application_name': 'dummy_application', 'managed': True,
                'statecode': 4, 'statename': 'DELETED',
                'major_failure': False, 'minor_failure': False}
    assert mocked_publisher.send_application_status.call_args_list == [call(expected)]


def test_on_process_removed_event_running_group(mocker, context):
    """ Test the handling of a known group removed event coming from a RUNNING Supvisors instance. """
    mocker.patch('supvisors.process.time', return_value=1234)
    context.supvisors.external_publisher = Mock(spec=EventPublisherInterface)
    mocked_publisher = context.supvisors.external_publisher
    # add context. processes removed are expected to be STOPPED
    application = create_application('dummy_application', context.supvisors)
    context.applications['dummy_application'] = application
    dummy_info_1 = {'group': 'dummy_application', 'name': 'dummy_process_1', 'expected': True, 'state': 0,
                    'now': 1234, 'stop': 1230, 'extra_args': '-h',
                    'program_name': 'dummy_process', 'process_index': 0}
    dummy_info_2 = {'group': 'dummy_application', 'name': 'dummy_process_2', 'expected': True, 'state': 0,
                    'now': 4321, 'stop': 4300, 'extra_args': '',
                    'program_name': 'dummy_process', 'process_index': 1}
    process_1 = create_process(dummy_info_1, context.supvisors)
    process_2 = create_process(dummy_info_2, context.supvisors)
    process_1.add_info('10.0.0.1', dummy_info_1)
    process_1.add_info('10.0.0.2', dummy_info_1)
    process_2.add_info('10.0.0.2', dummy_info_2)
    application.add_process(process_1)
    application.add_process(process_2)
    context.instances['10.0.0.1'].processes[process_1.namespec] = process_1
    context.instances['10.0.0.2'].processes[process_1.namespec] = process_1
    context.instances['10.0.0.2'].processes[process_2.namespec] = process_2
    # get instances status used for tests
    context.instances['10.0.0.1']._state = SupvisorsInstanceStates.RUNNING
    context.instances['10.0.0.2']._state = SupvisorsInstanceStates.RUNNING
    # update sequences for the test
    application.rules.managed = True
    application.update_sequences()
    application.update_status()
    assert application.state == ApplicationStates.STOPPED
    # payload for parameter
    dummy_event = {'group': 'dummy_application', 'name': '*'}
    mocker.patch.object(context, 'check_process', return_value=(application, None))
    # check normal behaviour in RUNNING state when dummy_application is removed from 10.0.0.1
    # as processes still includes a definition on 10.0.0.2, no impact expected on process and application
    context.on_process_removed_event('10.0.0.1', dummy_event)
    assert sorted(process_1.info_map.keys()) == ['10.0.0.2']
    assert sorted(process_2.info_map.keys()) == ['10.0.0.2']
    assert application.state == ApplicationStates.STOPPED
    assert sorted(context.instances['10.0.0.1'].processes.keys()) == []
    assert sorted(context.instances['10.0.0.2'].processes.keys()) == ['dummy_application:dummy_process_1',
                                                                      'dummy_application:dummy_process_2']
    expected = '10.0.0.1', {'group': 'dummy_application', 'name': 'dummy_process_1', 'state': -1}
    assert mocked_publisher.send_process_event.call_args_list == [call(*expected)]
    assert not mocked_publisher.send_process_status.called
    assert not mocked_publisher.send_application_status.called
    mocked_publisher.send_process_event.reset_mock()
    # check normal behaviour in RUNNING state when dummy_application is removed from 10.0.0.2
    # no more process in application and instance status so application is removed
    context.on_process_removed_event('10.0.0.2', dummy_event)
    assert list(process_1.info_map.keys()) == []
    assert list(process_2.info_map.keys()) == []
    assert application.state == ApplicationStates.DELETED
    expected_1 = '10.0.0.2', {'group': 'dummy_application', 'name': 'dummy_process_1', 'state': -1}
    expected_2 = '10.0.0.2', {'group': 'dummy_application', 'name': 'dummy_process_2', 'state': -1}
    assert mocked_publisher.send_process_event.call_args_list == [call(*expected_1), call(*expected_2)]
    expected_1 = {'application_name': 'dummy_application', 'process_name': 'dummy_process_1',
                  'statecode': -1, 'statename': 'DELETED', 'expected_exit': True,
                  'last_event_time': 1234, 'identifiers': [], 'extra_args': ''}
    expected_2 = {'application_name': 'dummy_application', 'process_name': 'dummy_process_2',
                  'statecode': -1, 'statename': 'DELETED', 'expected_exit': True,
                  'last_event_time': 1234, 'identifiers': [], 'extra_args': ''}
    assert mocked_publisher.send_process_status.call_args_list == [call(expected_1), call(expected_2)]
    expected = {'application_name': 'dummy_application', 'managed': True,
                'statecode': 4, 'statename': 'DELETED',
                'major_failure': False, 'minor_failure': False}
    assert mocked_publisher.send_application_status.call_args_list == [call(expected)]


def test_on_process_disability_event_unknown_identifier(context):
    """ Test the handling of a process disability event coming from an unknown Supvisors instance. """
    context.supvisors.external_publisher = Mock(spec=EventPublisherInterface)
    mocked_publisher = context.supvisors.external_publisher
    with pytest.raises(KeyError):
        context.on_process_disability_event('10.0.0.0', {})
    assert not mocked_publisher.send_process_event.called


def test_on_process_disability_event_not_running_instance(context):
    """ Test the handling of a process disability event coming from a non-running Supvisors instance. """
    context.supvisors.external_publisher = Mock(spec=EventPublisherInterface)
    mocked_publisher = context.supvisors.external_publisher
    # get instance status used for tests
    instance_status = context.instances['10.0.0.1']
    # check no change with known node not RUNNING
    for state in SupvisorsInstanceStates:
        if state not in [SupvisorsInstanceStates.CHECKED, SupvisorsInstanceStates.RUNNING]:
            instance_status._state = state
            context.on_process_disability_event('10.0.0.1', {})
            assert not mocked_publisher.send_process_event.called


def test_on_process_disability_event_running_process_unknown(mocker, context):
    """ Test the Context.on_process_disability_event with a RUNNING Supvisors instance and an unknown process. """
    mocker.patch.object(context, 'check_process', return_value=None)
    context.supvisors.external_publisher = Mock(spec=EventPublisherInterface)
    mocked_publisher = context.supvisors.external_publisher
    assert context.supvisors.options.auto_fence
    event = {'group': 'dummy_appli', 'name': 'dummy_process'}
    # get instance status used for tests
    instance_status = context.instances['10.0.0.1']
    instance_status._state = SupvisorsInstanceStates.RUNNING
    # check no change with unknown process
    context.on_process_disability_event('10.0.0.1', event)
    assert not mocked_publisher.send_process_event.called


def test_on_process_disability_event(mocker, context):
    """ Test the Context.on_process_disability_event with a RUNNING Supvisors instance and a known process. """
    context.supvisors.external_publisher = Mock(spec=EventPublisherInterface)
    mocked_publisher = context.supvisors.external_publisher
    event = {'group': 'dummy_appli', 'name': 'dummy_process', 'disabled': True}
    # get instance status used for tests
    instance_status = context.instances['10.0.0.1']
    instance_status._state = SupvisorsInstanceStates.RUNNING
    # patch load_application_rules
    context.supvisors.parser.load_application_rules = load_application_rules
    # fill context with one process
    dummy_info = {'group': 'dummy_application', 'name': 'dummy_process', 'expected': True, 'state': 0,
                  'now': 1234, 'stop': 0, 'extra_args': '-h', 'disabled': False,
                  'program_name': 'dummy_process', 'process_index': 0}
    process = context.setdefault_process('10.0.0.2', dummy_info)
    process.add_info('10.0.0.2', dummy_info)
    mocker.patch.object(context, 'check_process', return_value=(None, process))
    # check that process disabled status is not updated if the process has no information from the Supvisors instance
    context.on_process_disability_event('10.0.0.1', event)
    assert '10.0.0.1' not in process.info_map
    assert not process.info_map['10.0.0.2']['disabled']
    assert mocked_publisher.send_process_event.call_args_list == [call('10.0.0.1', event)]
    mocked_publisher.send_process_event.reset_mock()
    # check that process disabled status is updated if the process has information from the Supvisors instance
    process.add_info('10.0.0.1', dummy_info)
    context.on_process_disability_event('10.0.0.1', event)
    assert process.info_map['10.0.0.1']['disabled']
    assert mocked_publisher.send_process_event.call_args_list == [call('10.0.0.1', event)]


def test_on_process_state_event_unknown_identifier(mocker, context):
    """ Test the handling of a process state event coming from an unknown Supvisors instance. """
    context.supvisors.external_publisher = Mock(spec=EventPublisherInterface)
    mocked_publisher = context.supvisors.external_publisher
    mocked_update_args = mocker.patch.object(context.supvisors.supervisor_data, 'update_extra_args')
    with pytest.raises(KeyError):
        context.on_process_state_event('10.0.0.0', {})
    assert not mocked_update_args.called
    assert not mocked_publisher.send_process_event.called
    assert not mocked_publisher.send_process_status.called
    assert not mocked_publisher.send_application_status.called


def test_on_process_state_event_not_running_instance(mocker, context):
    """ Test the handling of a process state event coming from a non-running Supvisors instance. """
    context.supvisors.external_publisher = Mock(spec=EventPublisherInterface)
    mocked_publisher = context.supvisors.external_publisher
    mocked_update_args = mocker.patch.object(context.supvisors.supervisor_data, 'update_extra_args')
    # get instance status used for tests
    instance_status = context.instances['10.0.0.1']
    # check no change with known node not RUNNING
    for state in SupvisorsInstanceStates:
        if state not in [SupvisorsInstanceStates.CHECKED, SupvisorsInstanceStates.RUNNING]:
            instance_status._state = state
            assert context.on_process_state_event('10.0.0.1', {}) is None
            assert not mocked_update_args.called
            assert not mocked_publisher.send_process_event.called
            assert not mocked_publisher.send_process_status.called
            assert not mocked_publisher.send_application_status.called


def test_on_process_state_event_running_process_unknown(mocker, context):
    """ Test the Context.on_process_state_event with a RUNNING Supvisors instance and an unknown process. """
    mocker.patch.object(context, 'check_process', return_value=None)
    context.supvisors.external_publisher = Mock(spec=EventPublisherInterface)
    mocked_publisher = context.supvisors.external_publisher
    assert context.supvisors.options.auto_fence
    event = {'group': 'dummy_appli', 'name': 'dummy_process'}
    # get instance status used for tests
    instance_status = context.instances['10.0.0.1']
    instance_status._state = SupvisorsInstanceStates.RUNNING
    # check no change with unknown application
    assert context.on_process_state_event('10.0.0.1', event) is None
    assert not mocked_publisher.send_process_event.called
    assert not mocked_publisher.send_process_status.called
    assert not mocked_publisher.send_application_status.called


def test_on_process_state_event_locally_unknown_forced(mocker, context):
    """ Test the Context.on_process_state_event with a RUNNING Supvisors instance and a process known by the local
    Supvisors instance but not configured on the instance that raised the event.
    This is a forced event that will be accepted in the ProcessStatus. """
    mocker.patch('supvisors.process.time', return_value=2345)
    context.supvisors.external_publisher = Mock(spec=EventPublisherInterface)
    mocked_publisher = context.supvisors.external_publisher
    # get instance status used for tests
    instance_status = context.instances['10.0.0.1']
    instance_status._state = SupvisorsInstanceStates.RUNNING
    # patch load_application_rules
    context.supvisors.parser.load_application_rules = load_application_rules
    # fill context with one process
    dummy_info = {'group': 'dummy_application', 'name': 'dummy_process', 'state': ProcessStates.RUNNING,
                  'now': 1234, 'start': 1230, 'expected': True, 'extra_args': '-h',
                  'program_name': 'dummy_process', 'process_index': 0}
    process = context.setdefault_process('10.0.0.1', dummy_info)
    assert 'dummy_application' in context.applications
    application = context.applications['dummy_application']
    assert 'dummy_process' in application.processes
    # update sequences for the test
    application.rules.managed = True
    application.update_sequences()
    application.update_status()
    assert application.state == ApplicationStates.RUNNING
    # check there is no issue when a forced event is raised using an identifier not used in the process configuration
    # check the forced event will be accepted because the stored event has the same date as the forced event
    event = {'group': 'dummy_application', 'name': 'dummy_process', 'state': ProcessStates.FATAL,
             'identifier': '10.0.0.2', 'forced': True, 'now': 1234, 'pid': 0,
             'expected': False, 'spawnerr': 'bad luck', 'extra_args': '-h'}
    assert context.on_process_state_event('10.0.0.1', event) is process
    assert instance_status.state == SupvisorsInstanceStates.RUNNING
    assert application.state == ApplicationStates.STOPPED
    expected = {'group': 'dummy_application', 'name': 'dummy_process', 'pid': 0, 'expected': False,
                'state': ProcessStates.FATAL, 'extra_args': '-h', 'now': 1234, 'spawnerr': 'bad luck'}
    assert mocked_publisher.send_process_event.call_args_list == [call('10.0.0.1', expected)]
    expected = {'application_name': 'dummy_application', 'process_name': 'dummy_process',
                'statecode': ProcessStates.FATAL, 'statename': 'FATAL', 'expected_exit': True,
                'last_event_time': 2345, 'identifiers': ['10.0.0.1'], 'extra_args': ''}
    assert mocked_publisher.send_process_status.call_args_list == [call(expected)]
    expected = {'application_name': 'dummy_application', 'managed': True, 'statecode': ApplicationStates.STOPPED.value,
                'statename': ApplicationStates.STOPPED.name, 'major_failure': False, 'minor_failure': True}
    assert mocked_publisher.send_application_status.call_args_list == [call(expected)]


def test_on_process_state_event_locally_known_forced_dismissed(context):
    """ Test the Context.on_process_state_event with a RUNNING Supvisors instance and a process known by the local
    Supvisors instance and configured on the instance that raised the event.
    This is a forced event that will be dismissed in the ProcessStatus. """
    context.supvisors.external_publisher = Mock(spec=EventPublisherInterface)
    mocked_publisher = context.supvisors.external_publisher
    assert context.supvisors.options.auto_fence
    # get instance status used for tests
    instance_status = context.instances['10.0.0.1']
    instance_status._state = SupvisorsInstanceStates.RUNNING
    # patch load_application_rules
    context.supvisors.parser.load_application_rules = load_application_rules
    # fill context with one process
    dummy_info = {'group': 'dummy_application', 'name': 'dummy_process', 'state': ProcessStates.RUNNING,
                  'now': 1234, 'start': 1230, 'expected': True, 'extra_args': '-h',
                  'program_name': 'dummy_process', 'process_index': 0}
    context.setdefault_process('10.0.0.1', dummy_info)
    application = context.applications['dummy_application']
    # update sequences for the test
    application.rules.managed = True
    application.update_sequences()
    application.update_status()
    assert application.state == ApplicationStates.RUNNING
    # check there is no issue when a forced event is raised using an identifier not used in the process configuration
    # check the forced event will be dismissed because the stored event is more recent
    context.logger.trace = context.logger.debug = context.logger.info = print
    event = {'group': 'dummy_application', 'name': 'dummy_process', 'state': ProcessStates.FATAL,
             'identifier': '10.0.0.1', 'forced': True, 'now': 1230, 'pid': 0,
             'expected': False, 'spawnerr': 'bad luck', 'extra_args': '-h'}
    assert context.on_process_state_event('10.0.0.1', event) is None
    assert instance_status.state == SupvisorsInstanceStates.RUNNING
    assert application.state == ApplicationStates.RUNNING
    assert not mocked_publisher.send_process_event.called
    assert not mocked_publisher.send_process_status.called
    assert not mocked_publisher.send_application_status.called


def test_on_process_state_event(mocker, context):
    """ Test the handling of a process event. """
    mocker.patch('supvisors.process.time', return_value=1234)
    context.supvisors.external_publisher = Mock(spec=EventPublisherInterface)
    mocked_publisher = context.supvisors.external_publisher
    mocked_update_args = mocker.patch.object(context.supvisors.supervisor_data, 'update_extra_args')
    # get node status used for tests
    node = context.instances['10.0.0.1']
    # patch load_application_rules
    context.supvisors.parser.load_application_rules = load_application_rules
    # fill context with one process
    dummy_info = {'group': 'dummy_application', 'name': 'dummy_process', 'expected': True, 'state': 0,
                  'now': 1234, 'stop': 0, 'extra_args': '-h',
                  'program_name': 'dummy_process', 'process_index': 0}
    process = context.setdefault_process('10.0.0.1', dummy_info)
    application = context.applications['dummy_application']
    assert application.state == ApplicationStates.STOPPED
    # update sequences for the test
    application.rules.managed = True
    application.update_sequences()
    # payload for parameter
    dummy_event = {'group': 'dummy_application', 'name': 'dummy_process', 'state': 10, 'extra_args': '',
                   'now': 2345, 'stop': 0}
    # check normal behaviour in RUNNING state
    node._state = SupvisorsInstanceStates.RUNNING
    result = context.on_process_state_event('10.0.0.1', dummy_event)
    assert result is process
    assert process.state == 10
    assert application.state == ApplicationStates.STARTING
    assert mocked_update_args.call_args_list == [call('dummy_application:dummy_process', '')]
    expected = {'group': 'dummy_application', 'name': 'dummy_process',
                'state': 10, 'extra_args': '', 'now': 2345, 'stop': 0}
    assert mocked_publisher.send_process_event.call_args_list == [call('10.0.0.1', expected)]
    expected = {'application_name': 'dummy_application', 'process_name': 'dummy_process',
                'statecode': 10, 'statename': 'STARTING', 'expected_exit': True,
                'last_event_time': 1234, 'identifiers': ['10.0.0.1'], 'extra_args': ''}
    assert mocked_publisher.send_process_status.call_args_list == [call(expected)]
    expected = {'application_name': 'dummy_application', 'managed': True, 'statecode': 1, 'statename': 'STARTING',
                'major_failure': False, 'minor_failure': False}
    assert mocked_publisher.send_application_status.call_args_list == [call(expected)]
    # reset mocks
    mocked_update_args.reset_mock()
    mocked_publisher.send_process_event.reset_mock()
    mocked_publisher.send_process_status.reset_mock()
    mocked_publisher.send_application_status.reset_mock()
    # check degraded behaviour with process to Supvisors but unknown to Supervisor (remote program)
    # basically same check as previous, just being confident that no exception is raised by the method
    mocked_update_args.side_effect = KeyError
    result = context.on_process_state_event('10.0.0.1', dummy_event)
    assert result is process
    assert process.state == 10
    assert application.state == ApplicationStates.STARTING
    assert mocked_update_args.call_args_list == [call('dummy_application:dummy_process', '')]
    expected = {'group': 'dummy_application', 'name': 'dummy_process',
                'state': 10, 'extra_args': '', 'now': 2345, 'stop': 0}
    assert mocked_publisher.send_process_event.call_args_list == [call('10.0.0.1', expected)]
    expected = {'application_name': 'dummy_application', 'process_name': 'dummy_process',
                'statecode': 10, 'statename': 'STARTING', 'expected_exit': True,
                'last_event_time': 1234, 'identifiers': ['10.0.0.1'], 'extra_args': ''}
    assert mocked_publisher.send_process_status.call_args_list == [call(expected)]
    expected = {'application_name': 'dummy_application', 'managed': True, 'statecode': 1, 'statename': 'STARTING',
                'major_failure': False, 'minor_failure': False}
    assert mocked_publisher.send_application_status.call_args_list == [call(expected)]


def test_on_timer_event(mocker, context):
    """ Test the handling of a timer event in the local Supvisors instance. """
    context.supvisors.external_publisher = Mock(spec=EventPublisherInterface)
    mocked_send = context.supvisors.external_publisher.send_instance_status
    # update context instances
    context.local_status.__dict__.update({'_state': SupvisorsInstanceStates.RUNNING,
                                          'sequence_counter': 31,
                                          'local_sequence_counter': 31})
    context.instances['10.0.0.1'].__dict__.update({'_state': SupvisorsInstanceStates.RUNNING,
                                                   'local_sequence_counter': 30})
    context.instances['10.0.0.2'].__dict__.update({'_state': SupvisorsInstanceStates.RUNNING,
                                                   'local_sequence_counter': 29})
    context.instances['10.0.0.3'].__dict__.update({'_state': SupvisorsInstanceStates.SILENT,
                                                   'local_sequence_counter': 10})
    context.instances['10.0.0.4'].__dict__.update({'_state': SupvisorsInstanceStates.ISOLATING,
                                                   'local_sequence_counter': 0})
    context.instances['10.0.0.5'].__dict__.update({'_state': SupvisorsInstanceStates.UNKNOWN,
                                                   'local_sequence_counter': 0})
    context.instances['test'].__dict__.update({'_state': SupvisorsInstanceStates.SILENT,
                                               'local_sequence_counter': 0})
    # update context applications
    application_1 = Mock()
    context.applications['dummy_application'] = application_1
    # patch the expected future invalidated node
    proc_1 = Mock(rules=Mock(expected_load=3), **{'invalidate_identifier.return_value': False})
    proc_2 = Mock(application_name='dummy_application', rules=Mock(expected_load=12),
                  **{'invalidate_identifier.return_value': True})
    mocker.patch.object(context.instances['10.0.0.2'], 'running_processes', return_value=[proc_1, proc_2])
    # test when synchro_timeout has passed
    assert context.on_timer_event({'sequence_counter': 32, 'when': 3600}) == (['10.0.0.2'], {proc_2})
    expected_1 = {'identifier': '10.0.0.2', 'node_name': '10.0.0.2', 'port': 65000,
                  'statecode': 4, 'statename': 'SILENT',
                  'remote_time': 0, 'local_time': 0, 'loading': 15,
                  'sequence_counter': 0, 'process_failure': False,
                  'fsm_statecode': 0, 'fsm_statename': 'OFF',
                  'discovery_mode': False, 'master_identifier': '',
                  'starting_jobs': False, 'stopping_jobs': False}
    assert mocked_send.call_args_list == [call(expected_1)]
    assert proc_2.invalidate_identifier.call_args_list == [call('10.0.0.2')]
    assert application_1.update_status.call_args_list == [call()]
    # only '10.0.0.2' and '10.0.0.5' instances changed state
    local_identifier = context.supvisors.mapper.local_identifier
    for identifier, state in [(local_identifier, SupvisorsInstanceStates.RUNNING),
                              ('10.0.0.1', SupvisorsInstanceStates.RUNNING),
                              ('10.0.0.2', SupvisorsInstanceStates.SILENT),
                              ('10.0.0.3', SupvisorsInstanceStates.SILENT),
                              ('10.0.0.4', SupvisorsInstanceStates.ISOLATING),
                              ('10.0.0.5', SupvisorsInstanceStates.UNKNOWN)]:
        assert context.instances[identifier].state == state


def test_handle_isolation(context):
    """ Test the isolation of instances. """
    context.supvisors.external_publisher = Mock(spec=EventPublisherInterface)
    mocked_send_instance = context.supvisors.external_publisher.send_instance_status
    mocked_send_supvisors = context.supvisors.external_publisher.send_supvisors_status
    # update node states
    context.local_status._state = SupvisorsInstanceStates.CHECKING
    context.instances['10.0.0.1']._state = SupvisorsInstanceStates.RUNNING
    context.instances['10.0.0.2']._state = SupvisorsInstanceStates.SILENT
    context.instances['10.0.0.3']._state = SupvisorsInstanceStates.ISOLATED
    context.instances['10.0.0.4']._state = SupvisorsInstanceStates.ISOLATING
    context.instances['10.0.0.5']._state = SupvisorsInstanceStates.ISOLATING
    # call method and check result
    assert context.handle_isolation() == ['10.0.0.4', '10.0.0.5']
    assert context.local_status.state == SupvisorsInstanceStates.CHECKING
    assert context.instances['10.0.0.1'].state == SupvisorsInstanceStates.RUNNING
    assert context.instances['10.0.0.2'].state == SupvisorsInstanceStates.SILENT
    assert context.instances['10.0.0.3'].state == SupvisorsInstanceStates.ISOLATED
    assert context.instances['10.0.0.4'].state == SupvisorsInstanceStates.ISOLATED
    assert context.instances['10.0.0.5'].state == SupvisorsInstanceStates.ISOLATED
    # check calls to publisher.send_instance_status
    expected_1 = {'identifier': '10.0.0.4', 'node_name': '10.0.0.4', 'port': 65000,
                  'statecode': 6, 'statename': 'ISOLATED',
                  'remote_time': 0, 'local_time': 0, 'loading': 0,
                  'sequence_counter': 0, 'process_failure': False,
                  'fsm_statecode': 0, 'fsm_statename': 'OFF',
                  'discovery_mode': False, 'master_identifier': '',
                  'starting_jobs': False, 'stopping_jobs': False}
    expected_2 = {'identifier': '10.0.0.5', 'node_name': '10.0.0.5', 'port': 65000,
                  'statecode': 6, 'statename': 'ISOLATED',
                  'remote_time': 0, 'local_time': 0, 'loading': 0,
                  'sequence_counter': 0, 'process_failure': False,
                  'fsm_statecode': 0, 'fsm_statename': 'OFF',
                  'discovery_mode': False, 'master_identifier': '',
                  'starting_jobs': False, 'stopping_jobs': False}
    assert mocked_send_instance.call_args_list == [call(expected_1), call(expected_2)]
    # no change in state and modes. only one publication expected
    expected_3 = {'fsm_statecode': 0, 'fsm_statename': 'OFF',
                  'discovery_mode': False, 'master_identifier': '',
                  'starting_jobs': [], 'stopping_jobs': []}
    assert mocked_send_supvisors.call_args_list == [call(expected_3)]
