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

from unittest.mock import call, Mock, DEFAULT

import pytest
from supervisor.events import *
from supervisor.xmlrpc import Faults

from supvisors.listener import *
from supvisors.publisherinterface import EventPublisherInterface


@pytest.fixture
def listener(supvisors):
    """ Fixture for the instance to test. """
    return SupervisorListener(supvisors)


def test_creation_no_collector(mocker, supvisors):
    """ Test the values set at construction. """
    mocker.patch.dict('sys.modules', {'supvisors.statscollector': None})
    listener = SupervisorListener(supvisors)
    # check attributes
    assert listener.supvisors == supvisors
    assert listener.collector is None
    assert listener.local_identifier == supvisors.supvisors_mapper.local_identifier
    assert listener.main_loop is None
    assert listener.publisher is None
    # test that callbacks are set in Supervisor
    assert (SupervisorRunningEvent, listener.on_running) in callbacks
    assert (SupervisorStoppingEvent, listener.on_stopping) in callbacks
    assert (ProcessStateEvent, listener.on_process_state) in callbacks
    assert (ProcessAddedEvent, listener.on_process_added) in callbacks
    assert (ProcessRemovedEvent, listener.on_process_removed) in callbacks
    assert (ProcessEnabledEvent, listener.on_process_disability) in callbacks
    assert (ProcessDisabledEvent, listener.on_process_disability) in callbacks
    assert (ProcessGroupAddedEvent, listener.on_group_added) in callbacks
    assert (ProcessGroupRemovedEvent, listener.on_group_removed) in callbacks
    assert (Tick5Event, listener.on_tick) in callbacks
    assert (RemoteCommunicationEvent, listener.on_remote_event) in callbacks


def test_creation(mocker, supvisors, listener):
    """ Test the values set at construction. """
    mocked_collector = mocker.patch.object(listener, 'collector')
    # check attributes
    assert listener.supvisors is supvisors
    assert listener.collector is mocked_collector
    assert listener.local_identifier == supvisors.supvisors_mapper.local_identifier
    assert listener.main_loop is None
    assert listener.publisher is None
    # test that callbacks are set in Supervisor
    assert (SupervisorRunningEvent, listener.on_running) in callbacks
    assert (SupervisorStoppingEvent, listener.on_stopping) in callbacks
    assert (ProcessStateEvent, listener.on_process_state) in callbacks
    assert (ProcessAddedEvent, listener.on_process_added) in callbacks
    assert (ProcessRemovedEvent, listener.on_process_removed) in callbacks
    assert (ProcessEnabledEvent, listener.on_process_disability) in callbacks
    assert (ProcessDisabledEvent, listener.on_process_disability) in callbacks
    assert (ProcessGroupAddedEvent, listener.on_group_added) in callbacks
    assert (ProcessGroupRemovedEvent, listener.on_group_removed) in callbacks
    assert (Tick5Event, listener.on_tick) in callbacks
    assert (RemoteCommunicationEvent, listener.on_remote_event) in callbacks


def test_on_running_exception(mocker, listener):
    """ Test the protection of the Supervisor thread in case of exception while processing a SupervisorRunningEvent. """
    mocker.patch.object(listener.supvisors.supervisor_data, 'replace_default_handler', side_effect=TypeError)
    listener.on_running('')


def test_on_running(mocker, listener):
    """ Test the reception of a Supervisor RUNNING event. """
    ref_publisher = listener.publisher
    ref_main_loop = listener.main_loop
    mocked_prepare = mocker.patch.object(listener.supvisors.supervisor_data, 'update_supervisor')
    mocked_sockets = mocker.patch('supvisors.listener.SupvisorsSockets')
    mocked_publisher = mocker.patch('supvisors.listener.create_external_publisher')
    mocked_loop = mocker.patch('supvisors.listener.SupvisorsMainLoop')
    listener.on_running('')
    # test attributes and calls
    assert mocked_prepare.called
    assert mocked_sockets.called
    assert mocked_publisher.called
    assert listener.publisher is not ref_publisher
    assert mocked_loop.called
    assert listener.main_loop is not ref_main_loop
    assert listener.main_loop.start.called


def test_on_stopping_exception(mocker, listener):
    """ Test the protection of the Supervisor thread in case of exception while processing a
    SupervisorStoppingEvent. """
    mocker.patch.object(listener.supvisors.supervisor_data, 'close_httpservers', side_effect=TypeError)
    listener.on_stopping('')


def test_on_stopping(mocker, listener):
    """ Test the reception of a Supervisor STOPPING event. """
    # create a main_loop patch
    listener.main_loop = Mock(**{'stop.return_value': None})
    mocked_infosource = mocker.patch.object(listener.supvisors.supervisor_data, 'close_httpservers')
    # create an external publisher patch
    listener.supvisors.external_publisher = Mock(spec=EventPublisherInterface)
    # 1. test with unmarked logger, i.e. meant to be the supervisor logger
    listener.on_stopping('')
    assert callbacks == []
    assert mocked_infosource.called
    assert listener.main_loop.stop.called
    assert listener.supvisors.sockets.stop.called
    assert listener.supvisors.external_publisher.close.called
    assert not listener.supvisors.logger.close.called
    # reset mocks
    mocked_infosource.reset_mock()
    listener.main_loop.stop.reset_mock()
    listener.supvisors.sockets.stop.reset_mock()
    listener.supvisors.external_publisher.close.reset_mock()
    # 2. test with marked logger, i.e. meant to be the Supvisors logger
    listener.logger.SUPVISORS = None
    listener.on_stopping('')
    assert callbacks == []
    assert mocked_infosource.called
    assert listener.main_loop.stop.called
    assert listener.supvisors.sockets.stop.called
    assert listener.supvisors.external_publisher.close.called
    assert listener.supvisors.logger.close.called


def test_on_process_state_exception(listener):
    """ Test the protection of the Supervisor thread in case of exception while processing a ProcessStateEvent. """
    listener.on_process_state(None)


def test_on_process_state(mocker, listener):
    """ Test the reception of a Supervisor PROCESS event. """
    mocker.patch('supvisors.listener.time.time', return_value=77)
    # create a publisher patch
    listener.publisher = Mock(**{'send_process_state_event.return_value': None})
    # test process event
    process = Mock(pid=1234, spawnerr='resource not available',
                   **{'config.name': 'dummy_process',
                      'config.extra_args': '-s test',
                      'config.disabled': True,
                      'group.config.name': 'dummy_group'})
    event = ProcessStateFatalEvent(process, '')
    listener.on_process_state(event)
    expected = [call({'name': 'dummy_process', 'group': 'dummy_group', 'state': 200,
                      'extra_args': '-s test', 'now': 77, 'pid': 1234, 'disabled': True,
                      'expected': True, 'spawnerr': 'resource not available'})]
    assert listener.publisher.send_process_state_event.call_args_list == expected


def test_on_process_added_exception(listener):
    """ Test the protection of the Supervisor thread in case of exception while processing a ProcessAddedEvent. """
    listener.on_process_added(None)


def test_get_local_process_info(listener):
    """ Test the SupervisorListener._get_local_process_info method """
    process_info = {'name': 'dummy_process', 'group': 'dummy_group', 'state': 200,
                    'extra_args': '-s test', 'disabled': True, 'now': 77, 'pid': 1234,
                    'expected': True, 'spawnerr': 'resource not available'}
    rpc = listener.supvisors.supervisor_data.supvisors_rpc_interface.get_local_process_info
    # test normal behavior
    rpc.return_value = process_info
    assert listener._get_local_process_info('dummy_group:dummy_process') == process_info
    # test exception
    rpc.side_effect = RPCError(Faults.BAD_NAME, 'dummy_group:dummy_process')
    assert listener._get_local_process_info('dummy_group:dummy_process') is None


def test_on_process_added(mocker, listener):
    """ Test the reception of a Supervisor PROCESS_ADDED event. """
    # patch context
    process_info = {'name': 'dummy_process', 'group': 'dummy_group', 'state': 200,
                    'extra_args': '-s test', 'now': 77, 'pid': 1234,
                    'expected': True, 'spawnerr': 'resource not available'}
    mocked_get = mocker.patch.object(listener, '_get_local_process_info', return_value=process_info)
    listener.publisher = Mock(**{'send_process_state_event.return_value': None})
    # test process event
    process = Mock(**{'config.name': 'dummy_process', 'group.config.name': 'dummy_group'})
    event = ProcessAddedEvent(process)
    listener.on_process_added(event)
    assert listener.publisher.send_process_added_event.call_args_list == [call([process_info])]
    listener.publisher.send_process_added_event.reset_mock()
    # test exception
    mocked_get.return_value = None
    listener.on_process_added(event)
    assert not listener.publisher.send_process_added_event.called


def test_on_process_removed_exception(listener):
    """ Test the protection of the Supervisor thread in case of exception while processing a ProcessRemovedEvent. """
    listener.on_process_removed(None)


def test_on_process_removed(listener):
    """ Test the reception of a Supervisor PROCESS_REMOVED event. """
    # create a publisher patch
    listener.publisher = Mock(**{'send_process_state_event.return_value': None})
    # test process event
    process = Mock(**{'config.name': 'dummy_process', 'group.config.name': 'dummy_group'})
    event = ProcessRemovedEvent(process)
    listener.on_process_removed(event)
    expected = [call({'name': 'dummy_process', 'group': 'dummy_group'})]
    assert listener.publisher.send_process_removed_event.call_args_list == expected


def test_on_process_disability_exception(listener):
    """ Test the protection of the Supervisor thread in case of exception while processing a ProcessEnabledEvent or
    a ProcessDisabledEvent. """
    listener.publisher = Mock(**{'send_process_disability_event.return_value': None})
    listener.on_process_disability(None)
    assert not listener.publisher.send_process_disability_event.called


def test_on_process_disability(mocker, listener):
    """ Test the reception of a Supervisor PROCESS_ENABLED or a PROCESS_DISABLED event. """
    # patch context
    process_info = {'name': 'dummy_process', 'group': 'dummy_group', 'state': 200,
                    'extra_args': '-s test', 'now': 77, 'pid': 1234,
                    'expected': True, 'spawnerr': 'resource not available'}
    mocker.patch.object(listener, '_get_local_process_info', return_value=process_info)
    listener.publisher = Mock(**{'send_process_disability_event.return_value': None})
    # test PROCESS_ENABLED event
    process_info['disabled'] = False
    process = Mock(**{'config.name': 'dummy_process', 'group.config.name': 'dummy_group'})
    event = ProcessEnabledEvent(process)
    listener.on_process_disability(event)
    assert listener.publisher.send_process_disability_event.call_args_list == [call(process_info)]
    listener.publisher.send_process_disability_event.reset_mock()
    # test PROCESS_DISABLED event
    process_info['disabled'] = True
    process = Mock(**{'config.name': 'dummy_process', 'group.config.name': 'dummy_group'})
    event = ProcessDisabledEvent(process)
    listener.on_process_disability(event)
    assert listener.publisher.send_process_disability_event.call_args_list == [call(process_info)]


def test_on_group_added_exception(listener):
    """ Test the protection of the Supervisor thread in case of exception while processing
    a ProcessGroupAddedEvent. """
    listener.publisher = Mock(**{'send_process_added_event.return_value': None})
    listener.on_group_added(None)
    assert not listener.publisher.send_process_added_event.called


def test_on_group_added(mocker, listener):
    """ Test the reception of a Supervisor PROCESS_GROUP_ADDED event. """
    mocked_prepare = mocker.patch.object(listener.supvisors.supervisor_data, 'update_internal_data')
    mocked_processes = mocker.patch.object(listener.supvisors.supervisor_data, 'get_group_processes',
                                           return_value={'dummy_proc': Mock()})
    mocked_local = mocker.patch.object(listener, '_get_local_process_info', return_value={'namespec': 'dummy_proc'})
    listener.publisher = Mock(**{'send_process_added_event.return_value': None})
    # test process event
    event = ProcessGroupAddedEvent('dummy_application')
    listener.on_group_added(event)
    assert mocked_prepare.call_args_list == [call('dummy_application')]
    assert mocked_processes.call_args_list == [call('dummy_application')]
    assert mocked_local.call_args_list == [call('dummy_application:dummy_proc')]
    assert listener.publisher.send_process_added_event.call_args_list == [call([{'namespec': 'dummy_proc'}])]


def test_on_group_removed_exception(listener):
    """ Test the protection of the Supervisor thread in case of exception while processing
    a ProcessGroupRemovedEvent. """
    listener.publisher = Mock(**{'send_process_removed_event.return_value': None})
    listener.on_group_removed(None)
    assert not listener.publisher.send_process_removed_event.called


def test_on_group_removed(listener):
    """ Test the reception of a Supervisor PROCESS_GROUP_REMOVED event. """
    listener.publisher = Mock(**{'send_process_removed_event.return_value': None})
    # test process event
    event = ProcessGroupRemovedEvent('dummy_application')
    listener.on_group_removed(event)
    expected = {'name': '*', 'group': 'dummy_application'}
    assert listener.publisher.send_process_removed_event.call_args_list == [call(expected)]


def test_on_tick_exception(listener):
    """ Test the protection of the Supervisor thread in case of exception while processing a TickEvent. """
    listener.on_tick(None)


def test_on_tick(mocker, listener):
    """ Test the reception of a Supervisor TICK event. """
    mocker.patch('time.time', return_value=1234.56)
    mocker.patch.object(listener, 'collector', return_value=(8.5, [(25, 400)], 76.1, {'lo': (500, 500)}, {}))
    # create patches
    listener.publisher = Mock(**{'send_tick_event.return_value': None,
                                 'send_statistics.return_value': None})
    listener.supvisors.context.instances['127.0.0.1'] = Mock(**{'pid_processes.return_value': []})
    # test process event
    event = Tick60Event(120, None)
    listener.on_tick(event)
    assert listener.publisher.send_tick_event.call_args_list == [call({'when': 1234.56, 'sequence_counter': 0})]
    assert listener.publisher.send_statistics.call_args_list == [call((8.5, [(25, 400)], 76.1, {'lo': (500, 500)}, {}))]
    listener.publisher.reset_mock()
    # test process event when statistics disabled
    event = Tick60Event(150, None)
    listener.supvisors.options.stats_enabled = False
    listener.on_tick(event)
    assert listener.publisher.send_tick_event.call_args_list == [call({'when': 1234.56, 'sequence_counter': 1})]
    assert not listener.publisher.send_statistics.called
    listener.publisher.reset_mock()
    # test process event when statistics collector is not available
    event = Tick60Event(150, None)
    listener.supvisors.options.stats_enabled = True
    listener.collector = None
    listener.on_tick(event)
    assert listener.publisher.send_tick_event.call_args_list == [call({'when': 1234.56, 'sequence_counter': 2})]
    assert not listener.publisher.send_statistics.called


def test_unstack_event_heartbeat(listener):
    """ Test the processing of a Supvisors HEARTBEAT event. """
    listener.unstack_event('[0, ["10.0.0.1", []]]')
    assert not listener.supvisors.fsm.on_tick_event.called
    assert not listener.supvisors.fsm.on_process_state_event.called
    assert not listener.supvisors.fsm.on_process_added_event.called
    assert not listener.supvisors.fsm.on_process_removed_event.called
    assert not listener.supvisors.fsm.on_process_disability_event.called
    assert not listener.supvisors.fsm.on_state_event.called
    assert not listener.supvisors.statistician.push_statistics.called


def test_unstack_event_tick(listener):
    """ Test the processing of a Supvisors TICK event. """
    listener.unstack_event('[1, ["10.0.0.1", "data"]]')
    expected = [call('10.0.0.1', 'data')]
    assert listener.supvisors.fsm.on_tick_event.call_args_list == expected
    assert not listener.supvisors.fsm.on_process_state_event.called
    assert not listener.supvisors.fsm.on_process_added_event.called
    assert not listener.supvisors.fsm.on_process_removed_event.called
    assert not listener.supvisors.fsm.on_process_disability_event.called
    assert not listener.supvisors.fsm.on_state_event.called
    assert not listener.supvisors.statistician.push_statistics.called


def test_unstack_event_process_state(listener):
    """ Test the processing of a Supvisors process state event. """
    listener.unstack_event('[2, ["10.0.0.2", {"name": "dummy"}]]')
    expected = [call('10.0.0.2', {'name': 'dummy'})]
    assert not listener.supvisors.fsm.on_tick_event.called
    assert listener.supvisors.fsm.on_process_state_event.call_args_list == expected
    assert not listener.supvisors.fsm.on_process_added_event.called
    assert not listener.supvisors.fsm.on_process_removed_event.called
    assert not listener.supvisors.fsm.on_process_disability_event.called
    assert not listener.supvisors.fsm.on_state_event.called
    assert not listener.supvisors.statistician.push_statistics.called


def test_unstack_event_process_added(listener):
    """ Test the processing of a Supvisors process added event. """
    listener.unstack_event('[3, ["10.0.0.1", {"group": "dummy_group", "name": "dummy_process"}]]')
    expected = [call('10.0.0.1', {'group': 'dummy_group', 'name': 'dummy_process'})]
    assert not listener.supvisors.fsm.on_tick_event.called
    assert not listener.supvisors.fsm.on_process_state_event.called
    assert listener.supvisors.fsm.on_process_added_event.call_args_list == expected
    assert not listener.supvisors.fsm.on_process_removed_event.called
    assert not listener.supvisors.fsm.on_process_disability_event.called
    assert not listener.supvisors.fsm.on_state_event.called
    assert not listener.supvisors.statistician.push_statistics.called


def test_unstack_event_process_removed(listener):
    """ Test the processing of a Supvisors process removed event. """
    listener.unstack_event('[4, ["10.0.0.1", {"group": "dummy_group", "name": "dummy_process"}]]')
    expected = [call('10.0.0.1', {'group': 'dummy_group', 'name': 'dummy_process'})]
    assert not listener.supvisors.fsm.on_tick_event.called
    assert not listener.supvisors.fsm.on_process_state_event.called
    assert not listener.supvisors.fsm.on_process_added_event.called
    assert listener.supvisors.fsm.on_process_removed_event.call_args_list == expected
    assert not listener.supvisors.fsm.on_process_disability_event.called
    assert not listener.supvisors.fsm.on_state_event.called
    assert not listener.supvisors.statistician.push_statistics.called


def test_unstack_event_process_disability(listener):
    """ Test the processing of a Supvisors process enabled event. """
    listener.unstack_event('[5, ["10.0.0.1", {"group": "dummy_group", "name": "dummy_process"}]]')
    expected = [call('10.0.0.1', {'group': 'dummy_group', 'name': 'dummy_process'})]
    assert not listener.supvisors.fsm.on_tick_event.called
    assert not listener.supvisors.fsm.on_process_state_event.called
    assert not listener.supvisors.fsm.on_process_added_event.called
    assert not listener.supvisors.fsm.on_process_removed_event.called
    assert listener.supvisors.fsm.on_process_disability_event.call_args_list == expected
    assert not listener.supvisors.fsm.on_state_event.called
    assert not listener.supvisors.statistician.push_statistics.called


def test_unstack_event_statistics(listener):
    """ Test the processing of a Supvisors statistics event. """
    listener.unstack_event('[6, ["10.0.0.3", [0, [[20, 30]], {"lo": [100, 200]}, {}]]]')
    assert not listener.supvisors.fsm.on_tick_event.called
    assert not listener.supvisors.fsm.on_process_state_event.called
    assert not listener.supvisors.fsm.on_process_added_event.called
    assert not listener.supvisors.fsm.on_process_removed_event.called
    assert not listener.supvisors.fsm.on_process_disability_event.called
    assert not listener.supvisors.fsm.on_state_event.called
    expected = [call('10.0.0.3', [0, [[20, 30]], {'lo': [100, 200]}, {}])]
    assert listener.supvisors.statistician.push_statistics.call_args_list == expected


def test_unstack_event_state(listener):
    """ Test the processing of a Supvisors state event. """
    listener.unstack_event('[7, ["10.0.0.1", {"statecode": 10, "statename": "RUNNING"}]]')
    expected = [call('10.0.0.1', {'statecode': 10, 'statename': 'RUNNING'})]
    assert not listener.supvisors.fsm.on_tick_event.called
    assert not listener.supvisors.fsm.on_process_state_event.called
    assert not listener.supvisors.fsm.on_process_added_event.called
    assert not listener.supvisors.fsm.on_process_removed_event.called
    assert not listener.supvisors.fsm.on_process_disability_event.called
    assert listener.supvisors.fsm.on_state_event.call_args_list == expected
    assert not listener.supvisors.statistician.push_statistics.called


def test_unstack_info(listener):
    """ Test the processing of a Supvisors information. """
    listener.unstack_info('["10.0.0.4", {"name": "dummy"}]')
    assert listener.supvisors.fsm.on_process_info.call_args_list == [call('10.0.0.4', {"name": "dummy"})]


def test_authorization(listener):
    """ Test the processing of a Supvisors authorization. """
    listener.authorization('["10.0.0.5:60000", false, "10.0.0.1"]')
    expected = [call('10.0.0.5:60000', False, '10.0.0.1')]
    assert listener.supvisors.fsm.on_authorization.call_args_list == expected


def test_on_remote_event_exception(mocker, listener):
    """ Test the protection of the Supervisor thread in case of exception while processing
    a RemoteCommunicationEvent. """
    mocker.patch.object(listener, 'unstack_event', side_effect=KeyError)
    mocker.patch.object(listener, 'unstack_info', side_effect=KeyError)
    mocker.patch.object(listener, 'authorization', side_effect=KeyError)
    # test event
    event = Mock(type='event', data={'state': 'RUNNING'})
    listener.on_remote_event(event)
    # test info
    event = Mock(type='info', data={'name': 'dummy_process'})
    listener.on_remote_event(event)
    # test authorization
    event = Mock(type='auth', data=('10.0.0.1', True))
    listener.on_remote_event(event)


def test_on_remote_event(mocker, listener):
    """ Test the reception of a Supervisor remote comm event. """
    # add patches for what is tested just above
    mocker.patch.multiple(listener, unstack_event=DEFAULT, unstack_info=DEFAULT, authorization=DEFAULT)
    # test unknown type
    event = Mock(type='unknown', data='')
    listener.on_remote_event(event)
    assert not listener.unstack_event.called
    assert not listener.unstack_info.called
    assert not listener.authorization.called
    # test event
    event = Mock(type='event', data={'state': 'RUNNING'})
    listener.on_remote_event(event)
    assert listener.unstack_event.call_args_list == [call({'state': 'RUNNING'})]
    assert not listener.unstack_info.called
    assert not listener.authorization.called
    listener.unstack_event.reset_mock()
    # test info
    event = Mock(type='info', data={'name': 'dummy_process'})
    listener.on_remote_event(event)
    assert not listener.unstack_event.called
    assert listener.unstack_info.call_args_list == [call({'name': 'dummy_process'})]
    assert not listener.authorization.called
    listener.unstack_info.reset_mock()
    # test authorization
    event = Mock(type='auth', data=('10.0.0.1', True))
    listener.on_remote_event(event)
    assert not listener.unstack_event.called
    assert not listener.unstack_info.called
    assert listener.authorization.call_args_list == [call(('10.0.0.1', True))]


def test_force_process_state(mocker, listener):
    """ Test the sending of a fake Supervisor process event. """
    mocker.patch('supvisors.listener.time.time', return_value=56)
    # patch publisher
    listener.publisher = Mock(**{'send_process_state_event.return_value': None})
    # test the call
    process = Mock(application_name='appli', process_name='process', extra_args='-h')
    listener.force_process_state(process, '10.0.0.1', 56, ProcessStates.FATAL, 'bad luck')
    expected = [call({'name': 'process', 'group': 'appli', 'state': ProcessStates.FATAL, 'identifier': '10.0.0.1',
                      'forced': True, 'extra_args': '-h', 'now': 56, 'pid': 0, 'expected': False,
                      'spawnerr': 'bad luck'})]
    assert listener.publisher.send_process_state_event.call_args_list == expected
    listener.publisher.send_process_state_event.reset_mock()
