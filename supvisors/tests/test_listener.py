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

from unittest.mock import call, Mock

import pytest
from supervisor.events import *
from supervisor.xmlrpc import Faults

from supvisors.listener import *


@pytest.fixture
def listener(supvisors_instance):
    """ Fixture for the instance to test. """
    events.clear()
    return SupervisorListener(supvisors_instance)


@pytest.fixture
def discovery_listener(supvisors_instance):
    """ Fixture for the instance to test. """
    events.clear()
    supvisors_instance.options.multicast_group = '239.0.0.1', 7777
    return SupervisorListener(supvisors_instance)


def test_creation(supvisors_instance, listener):
    """ Test the values set at construction. """
    # check attributes
    assert listener.supvisors is supvisors_instance
    assert listener.local_instance == supvisors_instance.mapper.local_instance
    assert listener.local_identifier == supvisors_instance.mapper.local_identifier
    assert listener.stats_collector is supvisors_instance.stats_collector
    assert listener.host_compiler is supvisors_instance.host_compiler
    assert listener.process_compiler is supvisors_instance.process_compiler
    assert listener.fsm is supvisors_instance.fsm
    assert listener.rpc_handler is supvisors_instance.rpc_handler
    assert listener.mc_sender is None
    assert listener.external_publisher is None
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


def test_on_running_external(mocker, supvisors_instance, listener):
    """ Test the reception of a Supervisor RUNNING event.
    No discovery service, but an external publisher. """
    mocked_prepare = mocker.patch.object(supvisors_instance.supervisor_updater, 'on_supervisor_start')
    mocked_external_publisher = Mock()
    mocked_publisher_creation = mocker.patch('supvisors.listener.create_external_publisher',
                                             return_value=mocked_external_publisher)
    mocked_collect = mocker.patch.object(supvisors_instance.stats_collector, 'start')
    listener.on_running('')
    # test attributes and calls
    assert mocked_prepare.called
    assert mocked_publisher_creation.called
    assert supvisors_instance.discovery_handler is None
    assert listener.external_publisher is mocked_external_publisher
    assert supvisors_instance.external_publisher is listener.external_publisher
    assert mocked_collect.called


def test_on_running_discovery(mocker, supvisors_instance, discovery_listener):
    """ Test the reception of a Supervisor RUNNING event.
    Discovery service, but no external publisher. """
    mocked_prepare = mocker.patch.object(supvisors_instance.supervisor_updater, 'on_supervisor_start')
    mocked_publisher_creation = mocker.patch('supvisors.listener.create_external_publisher',
                                             return_value=None)
    mocked_collect = mocker.patch.object(supvisors_instance.stats_collector, 'start')
    discovery_listener.on_running('')
    # test attributes and calls
    assert mocked_prepare.called
    assert mocked_publisher_creation.called
    assert supvisors_instance.discovery_handler is not None
    assert discovery_listener.external_publisher is None
    assert supvisors_instance.external_publisher is discovery_listener.external_publisher
    assert mocked_collect.called


def test_on_stopping_exception(mocker, listener):
    """ Test the protection of the Supervisor thread in case of exception while processing a
    SupervisorStoppingEvent. """
    mocker.patch.object(listener.supvisors.supervisor_data, 'close_httpservers', side_effect=TypeError)
    listener.on_stopping('')


def test_on_stopping_unmarked(mocker, supvisors_instance, listener):
    """ Test the reception of a Supervisor STOPPING event with unmarked logger,
    i.e. meant to be the supervisor logger. """
    # patch the complex structures
    mocked_infosource = mocker.patch.object(supvisors_instance.supervisor_data, 'close_httpservers')
    supvisors_instance.stats_collector = Mock(**{'stop.return_value': None})
    supvisors_instance.rpc_handler = Mock(spec=RpcHandler)
    supvisors_instance.discovery_handler = Mock(spec=SupvisorsDiscovery)
    supvisors_instance.external_publisher = Mock(spec=EventPublisherInterface)
    # test
    listener.on_stopping('')
    assert callbacks == []
    assert mocked_infosource.called
    assert listener.rpc_handler.stop.called
    assert supvisors_instance.discovery_handler.stop.called
    assert listener.external_publisher.close.called
    assert not listener.logger.close.called
    assert listener.stats_collector.stop.called


def test_on_stopping(mocker, supvisors_instance, listener):
    """ Test the reception of a Supervisor STOPPING event with marked logger,
    i.e. meant to be the Supvisors logger. """
    # patch the complex structures
    mocked_infosource = mocker.patch.object(supvisors_instance.supervisor_data, 'close_httpservers')
    supvisors_instance.stats_collector = Mock(**{'stop.return_value': None})
    supvisors_instance.rpc_handler = Mock(spec=RpcHandler)
    supvisors_instance.discovery_handler = Mock(spec=SupvisorsDiscovery)
    supvisors_instance.external_publisher = Mock(spec=EventPublisherInterface)
    # test
    listener.logger.SUPVISORS = None
    listener.on_stopping('')
    assert callbacks == []
    assert mocked_infosource.called
    assert listener.rpc_handler.stop.called
    assert supvisors_instance.discovery_handler.stop.called
    assert listener.external_publisher.close.called
    assert listener.logger.close.called
    assert listener.stats_collector.stop.called


def test_on_tick_exception(mocker, listener):
    """ Test the protection of the Supervisor thread in case of exception while processing a TickEvent. """
    mocker.patch.object(listener.supvisors.fsm, 'on_timer_event', side_effect=KeyError)
    listener.on_tick({})


def test_on_tick(mocker, supvisors_instance, discovery_listener):
    """ Test the reception of a Supervisor TICK event. """
    # create patches
    mocker.patch('time.monotonic', return_value=34.56)
    mocked_tick = mocker.patch.object(supvisors_instance.context, 'on_local_tick_event')
    mocked_send = mocker.patch.object(discovery_listener.rpc_handler, 'send_tick_event')
    mocked_timer = supvisors_instance.fsm.on_timer_event
    mocked_stats = mocker.patch.object(discovery_listener, '_on_tick_stats')
    # create discovery_handler, as done in listener.on_running
    supvisors_instance.discovery_handler = Mock()
    # test tick event
    event = Tick60Event(120, None)
    discovery_listener.on_tick(event)
    expected_tick = {'when': 120, 'when_monotonic': 34.56, 'sequence_counter': 0}
    expected_discovery = {'identifier': discovery_listener.local_identifier,
                                 'nick_identifier': discovery_listener.local_instance.nick_identifier,
                                 'host_id': discovery_listener.local_instance.host_id,
                                 'http_port': discovery_listener.local_instance.http_port,
                                 'stereotypes': ['supvisors_test']}
    assert mocked_tick.call_args_list == [call(expected_tick)]
    assert mocked_timer.call_args_list == [call(expected_tick)]
    assert mocked_send.call_args_list == [call(expected_tick)]
    assert discovery_listener.mc_sender.send_discovery_event.call_args_list == [call(expected_discovery)]
    assert mocked_stats.call_args_list == [call()]


def test_on_tick_stats(mocker, supvisors_instance, discovery_listener):
    """ Test the reception of a Supervisor TICK event. """
    # create patches
    mocked_host = mocker.patch.object(discovery_listener, 'on_host_statistics')
    mocked_proc = mocker.patch.object(discovery_listener, 'on_process_statistics')
    mocked_send_host = mocker.patch.object(discovery_listener.rpc_handler, 'send_host_statistics')
    mocked_send_proc = mocker.patch.object(discovery_listener.rpc_handler, 'send_process_statistics')
    # add some data to the statistics collector
    supvisors_instance.stats_collector = mocked_collector = Mock()
    host_stats = [{'now': 8.5, 'cpu': [(25, 400)], 'mem': 76.1, 'io': {'lo': (500, 500)}}]
    mocked_collector.get_host_stats.return_value = host_stats
    proc_stats = [{'namespec': 'dummy_1'}, {'namespec': 'dummy_2'}]
    mocked_collector.get_process_stats.return_value = proc_stats
    # test tick event with stats_collector set but Supvisors state not in WORKING_STATES
    for state in [SupvisorsStates.OFF, SupvisorsStates.SYNCHRONIZATION, SupvisorsStates.RESTARTING,
                  SupvisorsStates.SHUTTING_DOWN, SupvisorsStates.FINAL]:
        supvisors_instance.state_modes.state = state
        discovery_listener._on_tick_stats()
        assert mocked_host.call_args_list == [call(discovery_listener.local_identifier, host_stats[0])]
        assert mocked_collector.alive.called
        assert mocked_proc.call_args_list == [call(discovery_listener.local_identifier, proc_stats[0]),
                                              call(discovery_listener.local_identifier, proc_stats[1])]
        assert not mocked_send_host.called
        assert not mocked_send_proc.called
        mocked_collector.reset_mock()
        mocker.resetall()
    # test tick event with stats_collector set but Supvisors state not in WORKING_STATES
    for state in WORKING_STATES:
        supvisors_instance.state_modes.state = state
        discovery_listener._on_tick_stats()
        assert mocked_host.call_args_list == [call(discovery_listener.local_identifier, host_stats[0])]
        assert mocked_collector.alive.called
        assert mocked_proc.call_args_list == [call(discovery_listener.local_identifier, proc_stats[0]),
                                              call(discovery_listener.local_identifier, proc_stats[1])]
        assert mocked_send_host.call_args_list == [call(host_stats[0])]
        assert mocked_send_proc.call_args_list == [call(proc_stats[0]), call(proc_stats[1])]
        mocked_collector.reset_mock()
        mocker.resetall()
    # test tick event when statistics collector is not available
    supvisors_instance.stats_collector = None
    discovery_listener._on_tick_stats()
    assert not mocked_host.called
    assert not mocked_collector.alive.called
    assert not mocked_proc.called
    assert not mocked_send_host.called
    assert not mocked_send_proc.called


def test_on_process_state_exception(listener):
    """ Test the protection of the Supervisor thread in case of exception while processing a ProcessStateEvent. """
    mocked_fsm = listener.supvisors.fsm.on_process_removed_event
    listener.on_process_state(None)
    assert not mocked_fsm.called


def test_on_process_state(mocker, supvisors_instance, listener):
    """ Test the reception of a Supervisor PROCESS event. """
    mocker.patch('supvisors.listener.time.time', return_value=77)
    mocker.patch('supvisors.listener.time.monotonic', return_value=23.9)
    mocked_fsm = supvisors_instance.fsm.on_process_state_event
    mocked_send = mocker.patch.object(listener.rpc_handler, 'send_process_state_event')
    mocked_start = mocker.patch.object(supvisors_instance.supervisor_data, 'update_start')
    mocked_stop = mocker.patch.object(supvisors_instance.supervisor_data, 'update_stop')
    # test process event
    process = Mock(pid=1234, spawnerr='resource not available', backoff=2,
                   **{'config.name': 'dummy_process',
                      'extra_args': '-s test',
                      'supvisors_config.program_config.disabled': True,
                      'group.config.name': 'dummy_group'})
    test_cases = [(ProcessStates.STOPPED, ProcessStateStoppedEvent, False, True),
                  (ProcessStates.STARTING, ProcessStateStartingEvent, True, False),
                  (ProcessStates.RUNNING, ProcessStateRunningEvent, False, False),
                  (ProcessStates.BACKOFF, ProcessStateBackoffEvent, False, True),
                  (ProcessStates.STOPPING, ProcessStateStoppingEvent, False, False),
                  (ProcessStates.EXITED, ProcessStateExitedEvent, False, True),
                  (ProcessStates.FATAL, ProcessStateFatalEvent, False, False),
                  (ProcessStates.UNKNOWN, ProcessStateUnknownEvent, False, False)]
    for event_code, event_class, call_start, call_stop in test_cases:
        event = event_class(process, '')
        listener.on_process_state(event)
        expected = {'identifier': listener.local_identifier,
                    'nick_identifier': listener.local_instance.nick_identifier,
                    'name': 'dummy_process', 'group': 'dummy_group',
                    'state': event_code,
                    'extra_args': '-s test',
                    'now': 77, 'now_monotonic': 23.9,
                    'pid': 1234, 'disabled': True,
                    'expected': True, 'spawnerr': 'resource not available'}
        assert mocked_fsm.call_args_list == [call(listener.local_status, expected)]
        assert mocked_send.call_args_list == [call(expected)]
        if call_start:
            assert mocked_start.call_args_list == [call('dummy_group:dummy_process')]
        if call_stop:
            assert mocked_stop.call_args_list == [call('dummy_group:dummy_process')]
        # reset the mocks
        mocked_fsm.reset_mock()
        mocker.resetall()


def test_on_process_added_exception(supvisors_instance, listener):
    """ Test the protection of the Supervisor thread in case of exception while processing a ProcessAddedEvent. """
    mocked_fsm = supvisors_instance.fsm.on_process_removed_event
    listener.on_process_added(None)
    assert not mocked_fsm.called


def test_get_local_process_info(supvisors_instance, listener):
    """ Test the SupervisorListener._get_local_process_info method """
    process_info = {'name': 'dummy_process', 'group': 'dummy_group', 'state': 200,
                    'extra_args': '-s test', 'disabled': True, 'now': 77, 'pid': 1234,
                    'expected': True, 'spawnerr': 'resource not available'}
    rpc = supvisors_instance.supervisor_data.supvisors_rpc_interface.get_local_process_info
    # test normal behavior
    rpc.return_value = process_info
    assert listener._get_local_process_info('dummy_group:dummy_process') == process_info
    # test exception
    rpc.side_effect = RPCError(Faults.BAD_NAME, 'dummy_group:dummy_process')
    assert listener._get_local_process_info('dummy_group:dummy_process') is None


def test_on_process_added(mocker, supvisors_instance, listener):
    """ Test the reception of a Supervisor PROCESS_ADDED event. """
    mocked_fsm = supvisors_instance.fsm.on_process_added_event
    mocked_send = mocker.patch.object(listener.rpc_handler, 'send_process_added_event')
    # patch context
    process_info = {'name': 'dummy_process', 'group': 'dummy_group', 'state': 200,
                    'extra_args': '-s test', 'now': 77, 'pid': 1234,
                    'expected': True, 'spawnerr': 'resource not available'}
    mocked_get = mocker.patch.object(listener, '_get_local_process_info', return_value=process_info)
    # test process event
    process = Mock(**{'config.name': 'dummy_process', 'group.config.name': 'dummy_group'})
    event = ProcessAddedEvent(process)
    listener.on_process_added(event)
    assert mocked_fsm.call_args_list == [call(listener.local_status, process_info)]
    assert mocked_send.call_args_list == [call(process_info)]
    mocked_send.reset_mock()
    # test exception
    mocked_get.return_value = None
    listener.on_process_added(event)
    assert mocked_fsm.call_args_list == [call(listener.local_status, process_info)]
    assert not mocked_send.called


def test_on_process_removed_exception(supvisors_instance, listener):
    """ Test the protection of the Supervisor thread in case of exception while processing a ProcessRemovedEvent. """
    mocked_fsm = supvisors_instance.fsm.on_process_removed_event
    listener.on_process_removed(None)
    assert not mocked_fsm.called


def test_on_process_removed(mocker, supvisors_instance, listener):
    """ Test the reception of a Supervisor PROCESS_REMOVED event. """
    mocked_fsm = supvisors_instance.fsm.on_process_removed_event
    mocked_send = mocker.patch.object(listener.rpc_handler, 'send_process_removed_event')
    # test process event
    process = Mock(**{'config.name': 'dummy_process', 'group.config.name': 'dummy_group'})
    event = ProcessRemovedEvent(process)
    listener.on_process_removed(event)
    expected = {'name': 'dummy_process', 'group': 'dummy_group'}
    assert mocked_fsm.call_args_list == [call(listener.local_status, expected)]
    assert mocked_send.call_args_list == [call(expected)]


def test_on_process_disability_exception(mocker, listener):
    """ Test the protection of the Supervisor thread in case of exception while processing a ProcessEnabledEvent or
    a ProcessDisabledEvent. """
    mocked_send = mocker.patch.object(listener.rpc_handler, 'send_process_disability_event')
    listener.on_process_disability(None)
    assert not mocked_send.called


def test_on_process_disability(mocker, listener):
    """ Test the reception of a Supervisor PROCESS_ENABLED or a PROCESS_DISABLED event. """
    # patch context
    process_info = {'name': 'dummy_process', 'group': 'dummy_group', 'state': 200,
                    'extra_args': '-s test', 'now': 77, 'pid': 1234,
                    'expected': True, 'spawnerr': 'resource not available'}
    mocker.patch.object(listener, '_get_local_process_info', return_value=process_info)
    mocked_send = mocker.patch.object(listener.rpc_handler, 'send_process_disability_event')
    # test PROCESS_ENABLED event
    process_info['disabled'] = False
    process = Mock(**{'config.name': 'dummy_process', 'group.config.name': 'dummy_group'})
    event = ProcessEnabledEvent(process)
    listener.on_process_disability(event)
    assert mocked_send.call_args_list == [call(process_info)]
    mocked_send.reset_mock()
    # test PROCESS_DISABLED event
    process_info['disabled'] = True
    process = Mock(**{'config.name': 'dummy_process', 'group.config.name': 'dummy_group'})
    event = ProcessDisabledEvent(process)
    listener.on_process_disability(event)
    assert mocked_send.call_args_list == [call(process_info)]


def test_on_group_added_exception(mocker, listener):
    """ Test the protection of the Supervisor thread in case of exception while processing
    a ProcessGroupAddedEvent. """
    mocked_send = mocker.patch.object(listener.rpc_handler, 'send_process_added_event')
    listener.on_group_added(None)
    assert not mocked_send.called


def test_on_group_added(mocker, supvisors_instance, listener):
    """ Test the reception of a Supervisor PROCESS_GROUP_ADDED event. """
    mocked_fsm = supvisors_instance.fsm.on_process_added_event
    mocked_send = mocker.patch.object(listener.rpc_handler, 'send_process_added_event')
    mocked_prepare = mocker.patch.object(supvisors_instance.supervisor_updater, 'on_group_added')
    mocked_processes = mocker.patch.object(supvisors_instance.supervisor_data, 'get_group_processes',
                                           return_value={'dummy_proc': Mock()})
    mocked_local = mocker.patch.object(listener, '_get_local_process_info', return_value={'namespec': 'dummy_proc'})
    # test process event
    event = ProcessGroupAddedEvent('dummy_application')
    listener.on_group_added(event)
    assert mocked_prepare.call_args_list == [call('dummy_application')]
    assert mocked_processes.call_args_list == [call('dummy_application')]
    assert mocked_local.call_args_list == [call('dummy_application:dummy_proc')]
    assert mocked_fsm.call_args_list == [call(listener.local_status, {'namespec': 'dummy_proc'})]
    assert mocked_send.call_args_list == [call({'namespec': 'dummy_proc'})]


def test_on_group_removed_exception(mocker, supvisors_instance, listener):
    """ Test the protection of the Supervisor thread in case of exception while processing
    a ProcessGroupRemovedEvent. """
    mocked_send = mocker.patch.object(listener.rpc_handler, 'send_process_removed_event')
    mocked_fsm = supvisors_instance.fsm.on_process_removed_event
    listener.on_group_removed(None)
    assert not mocked_fsm.called
    assert not mocked_send.called


def test_on_group_removed(mocker, supvisors_instance, listener):
    """ Test the reception of a Supervisor PROCESS_GROUP_REMOVED event. """
    mocked_send = mocker.patch.object(listener.rpc_handler, 'send_process_removed_event')
    mocked_fsm = supvisors_instance.fsm.on_process_removed_event
    # test process event
    event = ProcessGroupRemovedEvent('dummy_application')
    listener.on_group_removed(event)
    expected = {'name': '*', 'group': 'dummy_application'}
    assert mocked_fsm.call_args_list == [call(listener.local_status, expected)]
    assert mocked_send.call_args_list == [call(expected)]


def test_read_notification_wrong_type(supvisors_instance, listener):
    """ Test the processing of a wrong Supvisors notification. """
    with pytest.raises(ValueError):
        listener.read_notification('[["10.0.0.1", ["10.0.0.1", 25000]], [6, {"name": "dummy"}]]')
    fsm = supvisors_instance.fsm
    assert not fsm.on_discovery_event.called
    assert not fsm.on_identification_event.called
    assert not fsm.on_authorization.called
    assert not fsm.on_state_event.called
    assert not fsm.on_all_process_info.called
    assert not fsm.on_instance_failure.called


def test_read_notification_invalid_origin(supvisors_instance, listener):
    """ Test the processing of a notification coming from an invalid source. """
    listener.read_notification('[["10.0.0.2", "10.0.0.2", ["localhost", 65100]], [2, {"name": "dummy"}]]')
    fsm = supvisors_instance.fsm
    assert not fsm.on_discovery_event.called
    assert not fsm.on_identification_event.called
    assert not fsm.on_authorization.called
    assert not fsm.on_state_event.called
    assert not fsm.on_all_process_info.called
    assert not fsm.on_instance_failure.called


def test_read_notification_discovery(supvisors_instance, listener):
    """ Test the processing of a Supvisors DISCOVERY notification. """
    listener.read_notification('[["10.0.0.4:65100", "10.0.0.4", ["10.0.0.4", 65100]], [4, {"server_port": 6666}]]')
    expected = [call(['10.0.0.4:65100', '10.0.0.4', ['10.0.0.4', 65100]])]
    fsm = supvisors_instance.fsm
    assert fsm.on_discovery_event.call_args_list == expected
    assert not fsm.on_identification_event.called
    assert not fsm.on_authorization.called
    assert not fsm.on_state_event.called
    assert not fsm.on_all_process_info.called
    assert not fsm.on_instance_failure.called


def test_read_notification_identification(supvisors_instance, listener):
    """ Test the processing of a Supvisors IDENTIFICATION notification. """
    listener.read_notification('[["10.0.0.4:65100", "10.0.0.4", ["10.0.0.4", 65100]], [0, {"server_port": 6666}]]')
    expected = [call({'server_port': 6666})]
    fsm = supvisors_instance.fsm
    assert not fsm.on_discovery_event.called
    assert fsm.on_identification_event.call_args_list == expected
    assert not fsm.on_authorization.called
    assert not fsm.on_state_event.called
    assert not fsm.on_all_process_info.called
    assert not fsm.on_instance_failure.called


def test_read_notification_authorization(supvisors_instance, listener):
    """ Test the processing of a Supvisors AUTHORIZATION notification. """
    listener.read_notification('[["10.0.0.5:25000", "10.0.0.5", ["10.0.0.5", 25000]], [1, false]]')
    expected = [call(supvisors_instance.context.instances['10.0.0.5:25000'], False)]
    fsm = supvisors_instance.fsm
    assert not fsm.on_discovery_event.called
    assert not fsm.on_identification_event.called
    assert fsm.on_authorization.call_args_list == expected
    assert not fsm.on_state_event.called
    assert not fsm.on_all_process_info.called
    assert not fsm.on_instance_failure.called


def test_read_notification_state(supvisors_instance, listener):
    """ Test the processing of a Supvisors state notification. """
    listener.read_notification('[["10.0.0.1:25000", "10.0.0.1", ["10.0.0.1", 25000]],'
                               '[2, {"statecode": 10, "statename": "RUNNING"}]]')
    expected = [call(supvisors_instance.context.instances['10.0.0.1:25000'], {'statecode': 10, 'statename': 'RUNNING'})]
    fsm = supvisors_instance.fsm
    assert not fsm.on_discovery_event.called
    assert not fsm.on_identification_event.called
    assert not fsm.on_authorization.called
    assert fsm.on_state_event.call_args_list == expected
    assert not fsm.on_all_process_info.called
    assert not fsm.on_instance_failure.called


def test_read_notification_all_info(supvisors_instance, listener):
    """ Test the processing of a Supvisors all process information notification. """
    listener.read_notification('[["10.0.0.4:25000", "10.0.0.4", ["10.0.0.4", 25000]], [3, {"name": "dummy"}]]')
    expected = [call(supvisors_instance.context.instances['10.0.0.4:25000'], {'name': 'dummy'})]
    fsm = supvisors_instance.fsm
    assert not fsm.on_discovery_event.called
    assert not fsm.on_identification_event.called
    assert not fsm.on_authorization.called
    assert not fsm.on_state_event.called
    assert fsm.on_all_process_info.call_args_list == expected
    assert not fsm.on_instance_failure.called


def test_read_notification_instance_failure(supvisors_instance, listener):
    """ Test the processing of a Supvisors instance failure notification. """
    listener.read_notification('[["10.0.0.4:25000", "10.0.0.4", ["10.0.0.4", 25000]], [5, null]]')
    fsm = supvisors_instance.fsm
    assert not fsm.on_discovery_event.called
    assert not fsm.on_identification_event.called
    assert not fsm.on_authorization.called
    assert not fsm.on_state_event.called
    assert not fsm.on_all_process_info.called
    assert fsm.on_instance_failure.call_args_list == [call(supvisors_instance.context.instances['10.0.0.4:25000'])]


def test_read_publication_wrong_type(mocker, supvisors_instance, listener):
    """ Test the processing of a wring Supvisors publication. """
    mocked_host = mocker.patch.object(supvisors_instance.host_compiler, 'push_statistics')
    mocked_proc = mocker.patch.object(supvisors_instance.process_compiler, 'push_statistics')
    with pytest.raises(ValueError):
        listener.read_publication('[["10.0.0.1:25000", "10.0.0.1", ["10.0.0.1", 25000]], [10, {"name": "dummy"}]]')
    fsm = supvisors_instance.fsm
    assert not fsm.on_tick_event.called
    assert not fsm.on_process_state_event.called
    assert not fsm.on_process_added_event.called
    assert not fsm.on_process_removed_event.called
    assert not fsm.on_process_disability_event.called
    assert not fsm.on_state_event.called
    assert not mocked_host.called
    assert not mocked_proc.called


def test_read_publication_invalid_origin(mocker, supvisors_instance, listener):
    """ Test the processing of a publication coming from an invalid source. """
    mocked_host = mocker.patch.object(supvisors_instance.host_compiler, 'push_statistics')
    mocked_proc = mocker.patch.object(supvisors_instance.process_compiler, 'push_statistics')
    listener.read_publication('[["10.0.0.1", "10.0.0.2", ["localhost", 65100]], [2, {"name": "dummy"}]]')
    fsm = supvisors_instance.fsm
    assert not fsm.on_tick_event.called
    assert not fsm.on_process_state_event.called
    assert not fsm.on_process_added_event.called
    assert not fsm.on_process_removed_event.called
    assert not fsm.on_process_disability_event.called
    assert not fsm.on_state_event.called
    assert not mocked_host.called
    assert not mocked_proc.called


def test_read_publication_tick(mocker, supvisors_instance, listener):
    """ Test the processing of a Supvisors TICK publication. """
    mocked_host = mocker.patch.object(supvisors_instance.host_compiler, 'push_statistics')
    mocked_proc = mocker.patch.object(supvisors_instance.process_compiler, 'push_statistics')
    listener.read_publication('[["10.0.0.1:25000", "10.0.0.1", ["10.0.0.1", 25000]], [0, "data"]]')
    expected = [call(supvisors_instance.context.instances['10.0.0.1:25000'], 'data')]
    fsm = supvisors_instance.fsm
    assert fsm.on_tick_event.call_args_list == expected
    assert not fsm.on_process_state_event.called
    assert not fsm.on_process_added_event.called
    assert not fsm.on_process_removed_event.called
    assert not fsm.on_process_disability_event.called
    assert not fsm.on_state_event.called
    assert not mocked_host.called
    assert not mocked_proc.called


def test_read_publication_process_state(mocker, supvisors_instance, listener):
    """ Test the processing of a Supvisors process state publication. """
    mocked_host = mocker.patch.object(supvisors_instance.host_compiler, 'push_statistics')
    mocked_proc = mocker.patch.object(supvisors_instance.process_compiler, 'push_statistics')
    listener.read_publication('[["10.0.0.2:25000", "10.0.0.2", ["10.0.0.2", 25000]], [1, {"name": "dummy"}]]')
    expected = [call(supvisors_instance.context.instances['10.0.0.2:25000'], {'name': 'dummy'})]
    fsm = supvisors_instance.fsm
    assert not fsm.on_tick_event.called
    assert fsm.on_process_state_event.call_args_list == expected
    assert not fsm.on_process_added_event.called
    assert not fsm.on_process_removed_event.called
    assert not fsm.on_process_disability_event.called
    assert not fsm.on_state_event.called
    assert not mocked_host.called
    assert not mocked_proc.called


def test_read_publication_process_added(mocker, supvisors_instance, listener):
    """ Test the processing of a Supvisors process added publication. """
    mocked_host = mocker.patch.object(supvisors_instance.host_compiler, 'push_statistics')
    mocked_proc = mocker.patch.object(supvisors_instance.process_compiler, 'push_statistics')
    listener.read_publication('[["10.0.0.1:25000", "10.0.0.1", ["10.0.0.1", 25000]],'
                              '[2, {"group": "dummy_group", "name": "dummy_process"}]]')
    expected = [call(supvisors_instance.context.instances['10.0.0.1:25000'],
                     {'group': 'dummy_group', 'name': 'dummy_process'})]
    fsm = supvisors_instance.fsm
    assert not fsm.on_tick_event.called
    assert not fsm.on_process_state_event.called
    assert fsm.on_process_added_event.call_args_list == expected
    assert not fsm.on_process_removed_event.called
    assert not fsm.on_process_disability_event.called
    assert not fsm.on_state_event.called
    assert not mocked_host.called
    assert not mocked_proc.called


def test_read_publication_process_removed(mocker, supvisors_instance, listener):
    """ Test the processing of a Supvisors process removed publication. """
    mocked_host = mocker.patch.object(supvisors_instance.host_compiler, 'push_statistics')
    mocked_proc = mocker.patch.object(supvisors_instance.process_compiler, 'push_statistics')
    listener.read_publication('[["10.0.0.1:25000", "10.0.0.1", ["10.0.0.1", 25000]],'
                              '[3, {"group": "dummy_group", "name": "dummy_process"}]]')
    expected = [call(supvisors_instance.context.instances['10.0.0.1:25000'],
                     {'group': 'dummy_group', 'name': 'dummy_process'})]
    fsm = supvisors_instance.fsm
    assert not fsm.on_tick_event.called
    assert not fsm.on_process_state_event.called
    assert not fsm.on_process_added_event.called
    assert fsm.on_process_removed_event.call_args_list == expected
    assert not fsm.on_process_disability_event.called
    assert not fsm.on_state_event.called
    assert not mocked_host.called
    assert not mocked_proc.called


def test_read_publication_process_disability(mocker, supvisors_instance, listener):
    """ Test the processing of a Supvisors process enabled publication. """
    mocked_host = mocker.patch.object(supvisors_instance.host_compiler, 'push_statistics')
    mocked_proc = mocker.patch.object(supvisors_instance.process_compiler, 'push_statistics')
    listener.read_publication('[["10.0.0.1:25000", "10.0.0.1", ["10.0.0.1", 25000]],'
                              '[4, {"group": "dummy_group", "name": "dummy_process"}]]')
    expected = [call(supvisors_instance.context.instances['10.0.0.1:25000'],
                     {'group': 'dummy_group', 'name': 'dummy_process'})]
    fsm = supvisors_instance.fsm
    assert not fsm.on_tick_event.called
    assert not fsm.on_process_state_event.called
    assert not fsm.on_process_added_event.called
    assert not fsm.on_process_removed_event.called
    assert fsm.on_process_disability_event.call_args_list == expected
    assert not fsm.on_state_event.called
    assert not mocked_host.called
    assert not mocked_proc.called


def test_read_publication_host_statistics(mocker, supvisors_instance, listener):
    """ Test the processing of a Supvisors host statistics publication. """
    mocked_host = mocker.patch.object(supvisors_instance.host_compiler, 'push_statistics', return_value=[])
    mocked_proc = mocker.patch.object(supvisors_instance.process_compiler, 'push_statistics', return_value=None)
    # message definition
    message = '[["10.0.0.3:25000", "10.0.0.3", ["10.0.0.3", 25000]],[5, [0, [[20, 30]], {"lo": [100, 200]}]]]'
    # 1. external_publisher is None
    listener.read_publication(message)
    fsm = supvisors_instance.fsm
    assert not fsm.on_tick_event.called
    assert not fsm.on_process_state_event.called
    assert not fsm.on_process_added_event.called
    assert not fsm.on_process_removed_event.called
    assert not fsm.on_process_disability_event.called
    assert not fsm.on_state_event.called
    assert mocked_host.call_args_list == [call('10.0.0.3:25000', [0, [[20, 30]], {'lo': [100, 200]}])]
    assert not mocked_proc.called
    mocker.resetall()
    # 2. set external_publisher but still no returned value for push_statistics
    supvisors_instance.external_publisher = Mock(**{'send_host_statistics.return_value': None})
    listener.read_publication(message)
    assert mocked_host.call_args_list == [call('10.0.0.3:25000', [0, [[20, 30]], {'lo': [100, 200]}])]
    assert not listener.external_publisher.send_host_statistics.called
    assert not mocked_proc.called
    mocker.resetall()
    # 3. external_publisher set and integrated value available for push_statistics
    mocked_host.return_value = [{'uptime': 1234}]
    listener.read_publication(message)
    assert mocked_host.call_args_list == [call('10.0.0.3:25000', [0, [[20, 30]], {'lo': [100, 200]}])]
    assert listener.external_publisher.send_host_statistics.call_args_list == [call({'uptime': 1234})]
    assert not mocked_proc.called
    mocker.resetall()
    listener.external_publisher.send_host_statistics.reset_mock()


def test_read_publication_process_statistics(mocker, supvisors_instance, listener):
    """ Test the processing of a Supvisors process statistics publication. """
    mocked_host = mocker.patch.object(supvisors_instance.host_compiler, 'push_statistics', return_value=None)
    mocked_proc = mocker.patch.object(supvisors_instance.process_compiler, 'push_statistics')
    # 1. external_publisher is None
    listener.read_publication('[["10.0.0.3:25000", "10.0.0.3", ["10.0.0.3", 25000]],'
                              '[6, [{"cpu": [100, 200]}, {"cpu": [50, 20]}]]]')
    fsm = supvisors_instance.fsm
    assert not fsm.on_tick_event.called
    assert not fsm.on_process_state_event.called
    assert not fsm.on_process_added_event.called
    assert not fsm.on_process_removed_event.called
    assert not fsm.on_process_disability_event.called
    assert not fsm.on_state_event.called
    assert not mocked_host.called
    assert mocked_proc.call_args_list == [call('10.0.0.3:25000', [{"cpu": [100, 200]}, {"cpu": [50, 20]}])]
    mocked_proc.reset_mock()
    # 2. set external_publisher but still no returned value for push_statistics
    listener.supvisors.external_publisher = Mock(**{'send_process_statistics.return_value': None})
    listener.read_publication('[["10.0.0.3:25000", "10.0.0.3", ["10.0.0.3", 25000]],'
                              '[6, [{"cpu": [100, 200]}, {"cpu": [50, 20]}]]]')
    assert not mocked_host.called
    assert mocked_proc.call_args_list == [call('10.0.0.3:25000', [{'cpu': [100, 200]}, {'cpu': [50, 20]}])]
    assert not listener.external_publisher.send_process_statistics.called
    mocked_proc.reset_mock()
    # 3. external_publisher set and integrated value available for push_statistics
    mocked_proc.return_value = [{'uptime': 1234}]
    listener.read_publication('[["10.0.0.3:25000", "10.0.0.3", ["10.0.0.3", 25000]],'
                              '[6, [{"cpu": [100, 200]}, {"cpu": [50, 20]}]]]')
    assert not mocked_host.called
    assert mocked_proc.call_args_list == [call('10.0.0.3:25000', [{'cpu': [100, 200]}, {'cpu': [50, 20]}])]
    assert listener.external_publisher.send_process_statistics.call_args_list == [call({'uptime': 1234})]


def test_read_publication_state(mocker, supvisors_instance, listener):
    """ Test the processing of a Supvisors state event. """
    mocked_host = mocker.patch.object(supvisors_instance.host_compiler, 'push_statistics')
    mocked_proc = mocker.patch.object(supvisors_instance.process_compiler, 'push_statistics')
    listener.read_publication('[["10.0.0.1:25000", "10.0.0.1", ["10.0.0.1", 25000]],'
                              '[7, {"statecode": 10, "statename": "RUNNING"}]]')
    expected = [call(supvisors_instance.context.instances['10.0.0.1:25000'], {'statecode': 10, 'statename': 'RUNNING'})]
    fsm = supvisors_instance.fsm
    assert not fsm.on_tick_event.called
    assert not fsm.on_process_state_event.called
    assert not fsm.on_process_added_event.called
    assert not fsm.on_process_removed_event.called
    assert not fsm.on_process_disability_event.called
    assert fsm.on_state_event.call_args_list == expected
    assert not mocked_host.called
    assert not mocked_proc.called


def test_on_remote_event(mocker, listener):
    """ Test the reception of a Supervisor remote comm event. """
    # add patches for what is tested just above
    mocker.patch.object(listener, 'read_publication')
    mocker.patch.object(listener, 'read_notification')
    # test exception
    event = Mock(type=SUPVISORS_PUBLICATION, data={})
    listener.read_publication.side_effect = ValueError
    listener.on_remote_event(event)
    assert listener.read_publication.call_args_list == [call({})]
    listener.read_publication.reset_mock()
    # test exception
    event = Mock(type=SUPVISORS_NOTIFICATION, data={})
    listener.read_notification.side_effect = ValueError
    listener.on_remote_event(event)
    assert listener.read_notification.call_args_list == [call({})]
    listener.read_notification.reset_mock()
    # test unknown type
    event = Mock(type='unknown', data='')
    listener.on_remote_event(event)
    assert not listener.read_publication.called
    assert not listener.read_notification.called
    # test notification
    event = Mock(type=SUPVISORS_NOTIFICATION, data={'state': 'RUNNING'})
    listener.on_remote_event(event)
    assert listener.read_notification.call_args_list == [call({'state': 'RUNNING'})]
    assert not listener.read_publication.called
    listener.read_notification.reset_mock()
    # test publication
    event = Mock(type=SUPVISORS_PUBLICATION, data={'state': 'RUNNING'})
    listener.on_remote_event(event)
    assert listener.read_publication.call_args_list == [call({'state': 'RUNNING'})]
    assert not listener.read_notification.called
    listener.read_publication.reset_mock()


def test_force_process_state(mocker, supvisors_instance, listener):
    """ Test the sending of a fake Supervisor process event. """
    mocker.patch('time.time', return_value=45.6)
    # patch publisher
    mocked_fsm = mocker.patch.object(supvisors_instance.fsm, 'on_process_state_event')
    mocked_send = mocker.patch.object(listener.rpc_handler, 'send_process_state_event')
    # test the call
    process = Mock(application_name='appli', process_name='process', extra_args='-h')
    listener.force_process_state(process, '10.0.0.1:25000', 56, ProcessStates.FATAL, 'bad luck')
    expected = {'identifier': '10.0.0.1:25000',
                'nick_identifier': '10.0.0.1',
                'name': 'process', 'group': 'appli', 'state': ProcessStates.FATAL,
                'forced': True, 'extra_args': '-h',
                'now': 45.6, 'now_monotonic': 56,
                'pid': 0, 'expected': False,
                'spawnerr': 'bad luck'}
    assert mocked_fsm.call_args_list == [call(listener.local_status, expected)]
    assert mocked_send.call_args_list == [call(expected)]
