# ======================================================================
# Copyright 2024 Julien LE CLEACH
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

from unittest.mock import call, Mock

import pytest

from supvisors.statemodes import *


def test_state_modes(mocker, supvisors_instance):
    """ Test the StateModes class. """
    mocker.patch('time.monotonic', return_value=1234.56)
    sup_id = SupvisorsInstanceId('10.0.0.1', supvisors_instance)
    sm = StateModes(sup_id)
    assert sm.identifier == '10.0.0.1:25000'
    assert sm.nick_identifier == '10.0.0.1'
    assert sm.state == SupvisorsStates.OFF
    assert not sm.degraded_mode
    assert not sm.discovery_mode
    assert sm.master_identifier == ''
    assert not sm.starting_jobs
    assert not sm.stopping_jobs
    assert sm.instance_states == {}
    assert sm.serial() == {'identifier': '10.0.0.1:25000', 'nick_identifier': '10.0.0.1',
                           'now_monotonic': 1234.56,
                           'fsm_statecode': 0, 'fsm_statename': 'OFF',
                           'degraded_mode': False, 'discovery_mode': False,
                           'master_identifier': '',
                           'starting_jobs': False, 'stopping_jobs': False,
                           'instance_states': {}}
    assert sm.get_stable_running_identifiers() == set()
    assert sm.running_identifiers() == set()
    # update the context (no stability)
    payload = {'identifier': '10.0.0.1:25000', 'nick_identifier': '10.0.0.1',
               'now_monotonic': 1234.56,
               'fsm_statecode': SupvisorsStates.ELECTION.value,
               'fsm_statename': SupvisorsStates.ELECTION.name,
               'degraded_mode': True,
               'discovery_mode': True,
               'master_identifier': '10.0.0.1',
               'starting_jobs': True,
               'stopping_jobs': True,
               'instance_states': {f'10.0.0.{state.value}': state.name
                                   for state in SupvisorsInstanceStates}}
    sm.update(payload)
    assert sm.identifier == '10.0.0.1:25000'
    assert sm.nick_identifier == '10.0.0.1'
    assert sm.state == SupvisorsStates.ELECTION
    assert sm.degraded_mode
    assert sm.discovery_mode
    assert sm.master_identifier == '10.0.0.1'
    assert sm.starting_jobs
    assert sm.stopping_jobs
    assert sm.instance_states == {'10.0.0.0': SupvisorsInstanceStates.STOPPED,
                                  '10.0.0.1': SupvisorsInstanceStates.CHECKING,
                                  '10.0.0.2': SupvisorsInstanceStates.CHECKED,
                                  '10.0.0.3': SupvisorsInstanceStates.RUNNING,
                                  '10.0.0.4': SupvisorsInstanceStates.FAILED,
                                  '10.0.0.5': SupvisorsInstanceStates.ISOLATED}
    assert sm.serial() == {'identifier': '10.0.0.1:25000', 'nick_identifier': '10.0.0.1',
                           'now_monotonic': 1234.56,
                           'fsm_statecode': 2, 'fsm_statename': 'ELECTION',
                           'degraded_mode': True, 'discovery_mode': True,
                           'master_identifier': '10.0.0.1',
                           'starting_jobs': True, 'stopping_jobs': True,
                           'instance_states': {'10.0.0.0': 'STOPPED',
                                               '10.0.0.1': 'CHECKING',
                                               '10.0.0.2': 'CHECKED',
                                               '10.0.0.3': 'RUNNING',
                                               '10.0.0.4': 'FAILED',
                                               '10.0.0.5': 'ISOLATED'}}
    assert sm.get_stable_running_identifiers() == set()
    assert sm.running_identifiers() == {'10.0.0.3'}
    # update the context (force stability)
    sm.instance_states['10.0.0.1'] = SupvisorsInstanceStates.RUNNING
    sm.instance_states['10.0.0.2'] = SupvisorsInstanceStates.RUNNING
    sm.instance_states['10.0.0.4'] = SupvisorsInstanceStates.STOPPED
    assert sm.get_stable_running_identifiers() == {'10.0.0.3', '10.0.0.1', '10.0.0.2'}
    assert sm.running_identifiers() == {'10.0.0.1', '10.0.0.2', '10.0.0.3'}


@pytest.fixture
def state_modes(supvisors_instance):
    """ Create a SupvisorsStateModes with no discovery mode. """
    supvisors_instance.options.multicast_group = None
    return SupvisorsStateModes(supvisors_instance)


@pytest.fixture
def state_modes_discovery(supvisors_instance):
    """ Create a SupvisorsStateModes with discovery mode. """
    supvisors_instance.options.multicast_group = '239.0.0.1:6666'
    return SupvisorsStateModes(supvisors_instance)


@pytest.fixture
def simple_sm(supvisors_instance):
    """ Create a SupvisorsStateModes with no discovery mode and simplified mapper. """
    supvisors_instance.options.multicast_group = None
    supvisors_instance.mapper._instances = {k: v for k, v in supvisors_instance.mapper.instances.items()
                                            if k.startswith('10.0.0.')}
    supvisors_instance.mapper.local_identifier = '10.0.0.1:25000'
    return SupvisorsStateModes(supvisors_instance)


def test_supvisors_state_modes(supvisors_instance, state_modes):
    """ Test the SupvisorsStateModes creation. """
    assert state_modes.supvisors is supvisors_instance
    assert state_modes.logger is supvisors_instance.logger
    assert state_modes.mapper is supvisors_instance.mapper
    assert state_modes.external_publisher is supvisors_instance.external_publisher
    assert sorted(state_modes.instance_state_modes.keys()) == sorted(supvisors_instance.mapper.instances.keys())
    for identifier, sm in state_modes.instance_state_modes.items():
        assert type(sm) is StateModes
        assert identifier == sm.identifier
        if identifier == supvisors_instance.mapper.local_identifier:
            assert sm.instance_states == {identifier: SupvisorsInstanceStates.STOPPED
                                          for identifier in supvisors_instance.mapper.instances}
        else:
            assert sm.instance_states == {}
    assert not state_modes.discovery_mode
    assert not state_modes.local_state_modes.discovery_mode
    assert state_modes.stable_identifiers == set()

    # test accessors
    assert state_modes.local_identifier == supvisors_instance.mapper.local_identifier
    assert state_modes.local_state_modes is state_modes.instance_state_modes[supvisors_instance.mapper.local_identifier]
    assert state_modes.master_state_modes is None
    assert state_modes.starting_identifiers == []
    assert state_modes.stopping_identifiers == []
    assert state_modes.master_state is None
    assert state_modes.state == SupvisorsStates.OFF
    assert not state_modes.degraded_mode
    assert state_modes.master_identifier == ''
    assert not state_modes.starting_jobs
    assert not state_modes.stopping_jobs
    for identifier in supvisors_instance.mapper.instances:
        assert not state_modes.is_running(identifier)


def test_supvisors_state_modes_discovery(mocker, supvisors_instance, state_modes_discovery):
    """ Test the SupvisorsStateModes creation with discovery mode (simplified). """
    mocker.patch('time.monotonic', return_value=1234.56)
    assert state_modes_discovery.discovery_mode
    assert state_modes_discovery.local_state_modes.discovery_mode
    # add discovered instance
    supvisors_instance.mapper.instances['10.0.0.0'] = sup_id = SupvisorsInstanceId('10.0.0.0', supvisors_instance)
    state_modes_discovery.add_instance('10.0.0.0')
    assert not state_modes_discovery.is_running('10.0.0.0')
    assert state_modes_discovery.instance_state_modes['10.0.0.0'].serial() == StateModes(sup_id).serial()


def test_supvisors_state_modes_normal(mocker, supvisors_instance, simple_sm):
    """ Test the SupvisorsStateModes accessors on the local state & modes.
    Follow the expected logic of events in a normal Supvisors startup.
    """
    mocker.patch('time.monotonic', return_value=1234.56)
    mocked_send = mocker.patch.object(supvisors_instance.rpc_handler, 'send_state_event')
    # The local Supvisors instance becomes RUNNING
    assert not simple_sm.update_mark
    simple_sm.update_instance_state('10.0.0.1:25000', SupvisorsInstanceStates.RUNNING)
    assert simple_sm.local_state_modes.instance_states['10.0.0.1:25000'] == SupvisorsInstanceStates.RUNNING
    assert simple_sm.update_mark
    assert not mocked_send.called
    # Notification of local state & modes event
    expected = simple_sm.local_state_modes.serial()
    simple_sm.on_instance_state_event('10.0.0.1:25000', expected)
    assert simple_sm.instance_state_modes['10.0.0.1:25000'].serial() == expected
    assert not mocked_send.called
    # the local Supvisors instance goes to SYNCHRONIZATION
    simple_sm.state = SupvisorsStates.SYNCHRONIZATION
    assert simple_sm.state == SupvisorsStates.SYNCHRONIZATION
    expected.update({'fsm_statecode': 1, 'fsm_statename': 'SYNCHRONIZATION'})
    assert mocked_send.call_args_list == [call(expected)]
    mocked_send.reset_mock()
    # degraded_mode set because lots of Supvisors instances are missing
    assert supvisors_instance.external_publisher is None
    simple_sm.degraded_mode = True
    assert simple_sm.degraded_mode
    assert mocked_send.call_args_list == [call(simple_sm.local_state_modes.serial())]
    mocked_send.reset_mock()
    # Notification of local state & modes event
    expected = simple_sm.local_state_modes.serial()
    simple_sm.on_instance_state_event('10.0.0.1:25000', expected)
    assert simple_sm.instance_state_modes['10.0.0.1:25000'].serial() == expected
    assert not mocked_send.called
    # a remote instance state is RUNNING
    simple_sm.update_instance_state('10.0.0.2:25000', SupvisorsInstanceStates.RUNNING)
    assert simple_sm.local_state_modes.instance_states['10.0.0.2:25000'] == SupvisorsInstanceStates.RUNNING
    expected['instance_states']['10.0.0.2:25000'] = 'RUNNING'
    assert simple_sm.update_mark
    assert not mocked_send.called
    # Notification of remote state & modes event
    event = {'identifier': '10.0.0.2:25000', 'nick_identifier': '10.0.0.2',
             'now_monotonic': 1234.56,
             'fsm_statecode': 2, 'fsm_statename': 'ELECTION',
             'degraded_mode': False, 'discovery_mode': False,
             'master_identifier': '',
             'starting_jobs': False, 'stopping_jobs': False,
             'instance_states': {'10.0.0.1:25000': 'CHECKING',
                                 '10.0.0.2:25000': 'RUNNING',
                                 '10.0.0.3:25000': 'STOPPED',
                                 '10.0.0.4:25000': 'STOPPED',
                                 '10.0.0.5:25000': 'STOPPED',
                                 '10.0.0.6:25000': 'STOPPED'}}
    simple_sm.on_instance_state_event('10.0.0.2:25000', event)
    assert simple_sm.instance_state_modes['10.0.0.2:25000'].serial() == event
    assert not mocked_send.called
    # the local Supvisors instance goes to ELECTION
    simple_sm.state = SupvisorsStates.ELECTION
    assert simple_sm.state == SupvisorsStates.ELECTION
    expected.update({'fsm_statecode': 2, 'fsm_statename': 'ELECTION'})
    assert mocked_send.call_args_list == [call(expected)]
    mocked_send.reset_mock()
    # Notification of local state & modes event
    expected = simple_sm.local_state_modes.serial()
    simple_sm.on_instance_state_event('10.0.0.1:25000', expected)
    assert simple_sm.instance_state_modes['10.0.0.1:25000'].serial() == expected
    assert not mocked_send.called
    # Master management
    # add an external publisher
    supvisors_instance.external_publisher = Mock()
    # the context is not stable because 10.0.0.2:25000 has a CHECKING state
    simple_sm.evaluate_stability()
    assert simple_sm.stable_identifiers == set()
    assert simple_sm.get_master_identifiers() == {''}
    assert not simple_sm.check_master()
    assert not simple_sm.check_master(False)
    # Notification of remote state & modes event
    event['instance_states']['10.0.0.1:25000'] = 'RUNNING'
    simple_sm.on_instance_state_event('10.0.0.2:25000', event)
    assert simple_sm.instance_state_modes['10.0.0.2:25000'].serial() == event
    simple_sm.evaluate_stability()
    assert simple_sm.stable_identifiers == {'10.0.0.1:25000', '10.0.0.2:25000'}
    assert simple_sm.get_master_identifiers() == {''}
    assert not simple_sm.check_master()
    assert not simple_sm.check_master(False)
    assert not supvisors_instance.rpc_handler.send_state_event.called
    published = dict(expected, **{'starting_jobs': [], 'stopping_jobs': []})
    assert supvisors_instance.external_publisher.send_supvisors_status.call_args_list == [call(published)]
    supvisors_instance.external_publisher.send_supvisors_status.reset_mock()
    # Trigger Master selection (no core identifiers)
    assert not supvisors_instance.mapper.core_identifiers
    simple_sm.select_master()
    assert simple_sm.master_identifier == '10.0.0.1:25000'
    assert simple_sm.master_state_modes is simple_sm.instance_state_modes['10.0.0.1:25000']
    assert simple_sm.master_state == SupvisorsStates.ELECTION
    assert simple_sm.get_master_identifiers() == {'10.0.0.1:25000', ''}
    assert not simple_sm.check_master()
    assert not simple_sm.check_master(False)
    expected.update({'master_identifier': '10.0.0.1:25000'})
    assert supvisors_instance.rpc_handler.send_state_event.call_args_list == [call(expected)]
    published = dict(expected, **{'starting_jobs': [], 'stopping_jobs': []})
    assert supvisors_instance.external_publisher.send_supvisors_status.call_args_list == [call(published)]
    supvisors_instance.rpc_handler.send_state_event.reset_mock()
    supvisors_instance.external_publisher.send_supvisors_status.reset_mock()
    # set local starting jobs
    simple_sm.starting_jobs = True
    assert simple_sm.starting_jobs
    assert supvisors_instance.rpc_handler.send_state_event.call_args_list == [call(simple_sm.local_state_modes.serial())]
    published = dict(expected, **{'starting_jobs': ['10.0.0.1:25000'], 'stopping_jobs': []})
    assert supvisors_instance.external_publisher.send_supvisors_status.call_args_list == [call(published)]
    supvisors_instance.rpc_handler.send_state_event.reset_mock()
    supvisors_instance.external_publisher.send_supvisors_status.reset_mock()
    # Notification of remote state & modes event including stopping jobs and Master update
    event.update({'master_identifier': '10.0.0.1:25000', 'stopping_jobs': True})
    simple_sm.on_instance_state_event('10.0.0.2:25000', event)
    assert simple_sm.instance_state_modes['10.0.0.2:25000'].serial() == event
    assert simple_sm.get_master_identifiers() == {'10.0.0.1:25000'}
    assert simple_sm.check_master()
    assert simple_sm.check_master(False)
    assert not supvisors_instance.rpc_handler.send_state_event.called
    published = dict(expected, **{'starting_jobs': ['10.0.0.1:25000'], 'stopping_jobs': ['10.0.0.2:25000']})
    assert supvisors_instance.external_publisher.send_supvisors_status.call_args_list == [call(published)]
    supvisors_instance.external_publisher.send_supvisors_status.reset_mock()
    # set local stopping jobs
    simple_sm.stopping_jobs = True
    assert simple_sm.stopping_jobs
    assert supvisors_instance.rpc_handler.send_state_event.call_args_list == [call(simple_sm.local_state_modes.serial())]
    published = dict(expected, **{'starting_jobs': ['10.0.0.1:25000'],
                                  'stopping_jobs': ['10.0.0.1:25000', '10.0.0.2:25000']})
    assert supvisors_instance.external_publisher.send_supvisors_status.call_args_list == [call(published)]
    supvisors_instance.rpc_handler.send_state_event.reset_mock()
    supvisors_instance.external_publisher.send_supvisors_status.reset_mock()
    # Notification of remote state & modes event including stopping jobs and Master update
    event.update({'master_identifier': '10.0.0.1:25000', 'stopping_jobs': True})
    simple_sm.on_instance_state_event('10.0.0.2:25000', event)
    assert simple_sm.instance_state_modes['10.0.0.2:25000'].serial() == event
    assert simple_sm.get_master_identifiers() == {'10.0.0.1:25000'}
    assert simple_sm.check_master()
    assert simple_sm.check_master(False)
    assert not supvisors_instance.rpc_handler.send_state_event.called
    published = dict(expected, **{'starting_jobs': ['10.0.0.1:25000'],
                                  'stopping_jobs': ['10.0.0.1:25000', '10.0.0.2:25000']})
    assert supvisors_instance.external_publisher.send_supvisors_status.call_args_list == [call(published)]
    supvisors_instance.external_publisher.send_supvisors_status.reset_mock()
    # code coverage completion on SupvisorsStateModes.update_instance_state
    # stop the Master
    supvisors_instance.external_publisher = None
    simple_sm.master_identifier = '10.0.0.2:25000'
    supvisors_instance.rpc_handler.send_state_event.reset_mock()
    simple_sm.update_instance_state('10.0.0.2:25000', SupvisorsInstanceStates.STOPPED)
    sup_id = supvisors_instance.mapper.instances['10.0.0.2:25000']
    assert simple_sm.instance_state_modes['10.0.0.2:25000'].serial() == StateModes(sup_id).serial()
    assert simple_sm.master_identifier == ''
    assert simple_sm.stable_identifiers == {'10.0.0.1:25000', '10.0.0.2:25000'}
    assert simple_sm.get_master_identifiers() == {''}
    assert not simple_sm.check_master()
    assert not simple_sm.check_master(False)
    assert supvisors_instance.rpc_handler.send_state_event.call_args_list == [call(simple_sm.local_state_modes.serial())]
    supvisors_instance.rpc_handler.send_state_event.reset_mock()
    # use deferred_publish_status to publish the pending updates
    simple_sm.deferred_publish_status()
    assert not simple_sm.update_mark
    assert supvisors_instance.rpc_handler.send_state_event.call_args_list == [call(simple_sm.local_state_modes.serial())]


def test_select_master_core(supvisors_instance, simple_sm):
    """ Test Master selection when core_identifiers are involved. """
    supvisors_instance.mapper._core_identifiers = ['10.0.0.2', '10.0.0.3']
    # quickly set context as previous test, just before select_master call
    event = {'fsm_statecode': 2, 'fsm_statename': 'ELECTION',
             'degraded_mode': False, 'discovery_mode': False,
             'master_identifier': '',
             'starting_jobs': False, 'stopping_jobs': False,
             'instance_states': {'10.0.0.1:25000': 'RUNNING',
                                 '10.0.0.2:25000': 'RUNNING',
                                 '10.0.0.3:25000': 'STOPPED',
                                 '10.0.0.4:25000': 'STOPPED',
                                 '10.0.0.5:25000': 'STOPPED',
                                 '10.0.0.6:25000': 'STOPPED'}}
    simple_sm.instance_state_modes['10.0.0.1:25000'].update(event)
    simple_sm.instance_state_modes['10.0.0.2:25000'].update(event)
    # check conditions
    simple_sm.evaluate_stability()
    assert not simple_sm.core_instances_running()
    assert simple_sm.stable_identifiers == {'10.0.0.1:25000', '10.0.0.2:25000'}
    assert simple_sm.get_master_identifiers() == {''}
    assert not simple_sm.check_master()
    assert not simple_sm.check_master(False)
    # Trigger Master selection
    simple_sm.select_master()
    assert simple_sm.master_identifier == '10.0.0.2:25000'
    assert simple_sm.master_state_modes is simple_sm.instance_state_modes['10.0.0.2:25000']
    assert simple_sm.master_state == SupvisorsStates.ELECTION
    assert simple_sm.get_master_identifiers() == {'10.0.0.2:25000', ''}
    assert not simple_sm.check_master()
    assert not simple_sm.check_master(False)
    # test completion on SupvisorsStateModes.core_instances_running
    event['instance_states']['10.0.0.3:25000'] = 'RUNNING'
    simple_sm.instance_state_modes['10.0.0.1:25000'].update(event)
    simple_sm.instance_state_modes['10.0.0.2:25000'].update(event)
    # still not stable ('10.0.0.2:25000' missing)
    simple_sm.evaluate_stability()
    assert simple_sm.stable_identifiers == set()
    assert not simple_sm.core_instances_running()
    # full stability
    simple_sm.on_instance_state_event('10.0.0.3:25000', event)
    simple_sm.evaluate_stability()
    assert simple_sm.stable_identifiers == {'10.0.0.1:25000', '10.0.0.2:25000', '10.0.0.3:25000'}
    assert simple_sm.core_instances_running()


def test_supvisors_state_modes_established(supvisors_instance, simple_sm):
    """ Test the SupvisorsStateModes accessors on the local state & modes.
    Follow the expected logic of events in a case where the local Supvisors instance is started
    in a fully established Supvisors context.
    """
    # quickly set context
    event = {'fsm_statecode': 3, 'fsm_statename': 'ELECTION',
             'degraded_mode': True, 'discovery_mode': False,
             'master_identifier': '',
             'starting_jobs': False, 'stopping_jobs': False,
             'instance_states': {'10.0.0.1:25000': 'RUNNING',
                                 '10.0.0.2:25000': 'RUNNING',
                                 '10.0.0.3:25000': 'RUNNING',
                                 '10.0.0.4:25000': 'STOPPED',
                                 '10.0.0.5:25000': 'STOPPED',
                                 '10.0.0.6:25000': 'STOPPED'}}
    simple_sm.instance_state_modes['10.0.0.1:25000'].update(event)
    event.update({'fsm_statecode': 4, 'fsm_statename': 'OPERATION',
                  'master_identifier': '10.0.0.3:25000'})
    simple_sm.instance_state_modes['10.0.0.2:25000'].update(event)
    simple_sm.instance_state_modes['10.0.0.3:25000'].update(event)
    # check conditions
    assert simple_sm.master_identifier == ''
    simple_sm.evaluate_stability()
    assert simple_sm.stable_identifiers == {'10.0.0.1:25000', '10.0.0.2:25000', '10.0.0.3:25000'}
    assert simple_sm.get_master_identifiers() == {'10.0.0.3:25000', ''}
    assert not simple_sm.check_master()
    assert not simple_sm.check_master(False)
    # Trigger Master selection
    simple_sm.select_master()
    assert simple_sm.master_identifier == '10.0.0.3:25000'
    assert simple_sm.master_state == SupvisorsStates.OPERATION
    assert simple_sm.get_master_identifiers() == {'10.0.0.3:25000'}
    assert simple_sm.check_master()
    assert simple_sm.check_master(False)


def test_supvisors_state_modes_split_brain(supvisors_instance, simple_sm):
    """ Test the SupvisorsStateModes accessors on the local state & modes.
    Follow the expected logic of events in a case where the local Supvisors instance is started
    in a Supvisors split-brain context.
    """
    # quickly set context
    event = {'fsm_statecode': 4, 'fsm_statename': 'OPERATION',
             'degraded_mode': True, 'discovery_mode': False,
             'master_identifier': '10.0.0.3:25000',
             'starting_jobs': False, 'stopping_jobs': False,
             'instance_states': {'10.0.0.1:25000': 'RUNNING',
                                 '10.0.0.2:25000': 'RUNNING',
                                 '10.0.0.3:25000': 'RUNNING',
                                 '10.0.0.4:25000': 'STOPPED',
                                 '10.0.0.5:25000': 'STOPPED',
                                 '10.0.0.6:25000': 'STOPPED'}}
    simple_sm.instance_state_modes['10.0.0.1:25000'].update(event)
    simple_sm.instance_state_modes['10.0.0.3:25000'].update(event)
    event.update({'master_identifier': '10.0.0.2:25000'})
    simple_sm.instance_state_modes['10.0.0.2:25000'].update(event)
    # check conditions
    assert simple_sm.master_identifier == '10.0.0.3:25000'
    simple_sm.evaluate_stability()
    assert simple_sm.stable_identifiers == {'10.0.0.1:25000', '10.0.0.2:25000', '10.0.0.3:25000'}
    assert simple_sm.get_master_identifiers() == {'10.0.0.2:25000', '10.0.0.3:25000'}
    assert not simple_sm.check_master()
    assert not simple_sm.check_master(False)
    # Trigger Master selection
    simple_sm.select_master()
    assert simple_sm.master_identifier == '10.0.0.2:25000'
    assert simple_sm.master_state == SupvisorsStates.OPERATION
    assert simple_sm.get_master_identifiers() == {'10.0.0.2:25000', '10.0.0.3:25000'}
    assert not simple_sm.check_master()
    assert not simple_sm.check_master(False)
    # 10.0.0.2 do not change and 10.0.0.3 changes
    simple_sm.on_instance_state_event('10.0.0.3:25000', event)
    simple_sm.evaluate_stability()
    assert simple_sm.stable_identifiers == {'10.0.0.1:25000', '10.0.0.2:25000', '10.0.0.3:25000'}
    assert simple_sm.get_master_identifiers() == {'10.0.0.2:25000'}
    assert simple_sm.check_master()
    assert simple_sm.check_master(False)


def test_supvisors_state_modes_split_brain_core(supvisors_instance, simple_sm):
    """ Same test in a Supvisors split-brain context with core_identifiers. """
    supvisors_instance.mapper._core_identifiers = ['10.0.0.4', '10.0.0.3']
    # quickly set context
    event = {'fsm_statecode': 4, 'fsm_statename': 'OPERATION',
             'degraded_mode': True, 'discovery_mode': False,
             'master_identifier': '10.0.0.3:25000',
             'starting_jobs': False, 'stopping_jobs': False,
             'instance_states': {'10.0.0.1:25000': 'RUNNING',
                                 '10.0.0.2:25000': 'RUNNING',
                                 '10.0.0.3:25000': 'RUNNING',
                                 '10.0.0.4:25000': 'STOPPED',
                                 '10.0.0.5:25000': 'STOPPED',
                                 '10.0.0.6:25000': 'STOPPED'}}
    simple_sm.instance_state_modes['10.0.0.1:25000'].update(event)
    simple_sm.instance_state_modes['10.0.0.3:25000'].update(event)
    event.update({'master_identifier': '10.0.0.2:25000'})
    simple_sm.instance_state_modes['10.0.0.2:25000'].update(event)
    # check conditions
    assert simple_sm.master_identifier == '10.0.0.3:25000'
    simple_sm.evaluate_stability()
    assert simple_sm.stable_identifiers == {'10.0.0.1:25000', '10.0.0.2:25000', '10.0.0.3:25000'}
    assert simple_sm.get_master_identifiers() == {'10.0.0.2:25000', '10.0.0.3:25000'}
    assert not simple_sm.check_master()
    # Trigger Master selection
    simple_sm.select_master()
    assert simple_sm.master_identifier == '10.0.0.3:25000'
    assert simple_sm.master_state == SupvisorsStates.OPERATION
    assert simple_sm.get_master_identifiers() == {'10.0.0.2:25000', '10.0.0.3:25000'}
    assert not simple_sm.check_master()
    # 10.0.0.3 do not change and 10.0.0.2 changes
    event.update({'master_identifier': '10.0.0.3:25000'})
    simple_sm.on_instance_state_event('10.0.0.2:25000', event)
    simple_sm.evaluate_stability()
    assert simple_sm.stable_identifiers == {'10.0.0.1:25000', '10.0.0.2:25000', '10.0.0.3:25000'}
    assert simple_sm.get_master_identifiers() == {'10.0.0.3:25000'}
    assert simple_sm.check_master()


def test_supvisors_state_modes_user(supvisors_instance, simple_sm):
    """ Test the SupvisorsStateModes accessors on the local state & modes.
    Follow the expected logic of events in a case where the Supvisors user has selected a Master
    on a remote Supvisors instance with USER sync option.
    """
    # quickly set context
    event = {'fsm_statecode': 1, 'fsm_statename': 'SYNCHRONIZATION',
             'degraded_mode': True, 'discovery_mode': False,
             'master_identifier': '',
             'starting_jobs': False, 'stopping_jobs': False,
             'instance_states': {'10.0.0.1:25000': 'RUNNING',
                                 '10.0.0.2:25000': 'RUNNING',
                                 '10.0.0.3:25000': 'RUNNING',
                                 '10.0.0.4:25000': 'STOPPED',
                                 '10.0.0.5:25000': 'STOPPED',
                                 '10.0.0.6:25000': 'STOPPED'}}
    simple_sm.instance_state_modes['10.0.0.1:25000'].update(event)
    simple_sm.instance_state_modes['10.0.0.3:25000'].update(event)
    event.update({'master_identifier': '10.0.0.3:25000'})
    simple_sm.instance_state_modes['10.0.0.2:25000'].update(event)
    # check conditions
    assert simple_sm.master_identifier == ''
    simple_sm.evaluate_stability()
    assert simple_sm.stable_identifiers == {'10.0.0.1:25000', '10.0.0.2:25000', '10.0.0.3:25000'}
    assert simple_sm.get_master_identifiers() == {'', '10.0.0.3:25000'}
    assert not simple_sm.check_master()
    # Trigger Master selection
    simple_sm.accept_master()
    assert simple_sm.master_identifier == '10.0.0.3:25000'
    assert simple_sm.master_state == SupvisorsStates.SYNCHRONIZATION
    assert simple_sm.get_master_identifiers() == {'', '10.0.0.3:25000'}
    assert not simple_sm.check_master()
    # 10.0.0.2 do not change and 10.0.0.3 changes
    event.update({'master_identifier': '10.0.0.3:25000'})
    simple_sm.on_instance_state_event('10.0.0.3:25000', event)
    simple_sm.evaluate_stability()
    assert simple_sm.stable_identifiers == {'10.0.0.1:25000', '10.0.0.2:25000', '10.0.0.3:25000'}
    assert simple_sm.get_master_identifiers() == {'10.0.0.3:25000'}
    assert simple_sm.check_master()


def test_all_running(simple_sm):
    """ Test the check of all Supvisors instances running. """
    assert simple_sm.stable_identifiers == set()
    assert simple_sm.mapper.core_identifiers == []
    simple_sm.mapper.initial_identifiers = []
    # initial test
    assert not simple_sm.all_running()
    assert not simple_sm.initial_running()
    assert not simple_sm.core_instances_running()
    # add initial identifiers
    simple_sm.mapper.initial_identifiers = ['10.0.0.1:25000', '10.0.0.2:25000', '10.0.0.3:25000']
    assert not simple_sm.all_running()
    assert not simple_sm.initial_running()
    assert not simple_sm.core_instances_running()
    # add some as stable and add some core identifiers
    simple_sm.stable_identifiers = {'10.0.0.1:25000', '10.0.0.2:25000', '10.0.0.3:25000'}
    simple_sm.mapper._core_identifiers = ['10.0.0.2:25000', '10.0.0.4:25000']
    assert not simple_sm.all_running()
    assert simple_sm.initial_running()
    assert not simple_sm.core_instances_running()
    # add some as stable and add some core identifiers
    simple_sm.stable_identifiers.add('10.0.0.4:25000')
    assert not simple_sm.all_running()
    assert simple_sm.initial_running()
    assert simple_sm.core_instances_running()
    # set all as stable
    simple_sm.stable_identifiers.update({'10.0.0.5:25000', '10.0.0.6:25000'})
    assert simple_sm.all_running()
    assert simple_sm.initial_running()
    assert simple_sm.core_instances_running()
