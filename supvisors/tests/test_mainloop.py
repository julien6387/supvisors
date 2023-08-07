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

from socket import gethostname
from unittest.mock import call, patch, DEFAULT

import pytest

from supvisors.mainloop import *
from supvisors.ttypes import DeferredRequestHeaders, SupvisorsInstanceStates
from .base import DummyRpcInterface


@pytest.fixture
def mocked_rpc():
    """ Fixture for the instance to test. """
    rpc_patch = patch('supvisors.mainloop.getRPCInterface')
    mocked_rpc = rpc_patch.start()
    yield mocked_rpc
    rpc_patch.stop()


@pytest.fixture
def main_loop(supvisors):
    return SupvisorsMainLoop(supvisors)


def test_creation(supvisors, mocked_rpc, main_loop):
    """ Test the values set at construction. """
    assert isinstance(main_loop, Thread)
    assert main_loop.supvisors is supvisors
    assert not main_loop.stop_event.is_set()
    assert main_loop.srv_url.env == {'SUPERVISOR_SERVER_URL': f'http://{gethostname()}:65000',
                                     'SUPERVISOR_USERNAME': 'user',
                                     'SUPERVISOR_PASSWORD': 'p@$$w0rd'}
    assert mocked_rpc.call_args_list == [call(main_loop.srv_url.env)]
    assert main_loop.receiver is not None


def test_stopping(mocked_rpc, main_loop):
    """ Test the get_loop method. """
    assert not main_loop.stopping
    main_loop.stop_event.set()
    assert main_loop.stopping


def test_stop(mocker, mocked_rpc, main_loop):
    """ Test the stopping of the main loop thread. """
    mocked_join = mocker.patch.object(main_loop, 'join')
    # try to stop main loop before it is started
    main_loop.stop()
    assert not main_loop.stop_event.is_set()
    assert not mocked_join.called
    # stop main loop when alive
    mocker.patch.object(main_loop, 'is_alive', return_value=True)
    main_loop.stop()
    assert main_loop.stop_event.is_set()
    assert mocked_join.called


def test_run(mocker, main_loop):
    """ Test the running of the main loop thread. """
    mocked_evt = mocker.patch('supvisors.mainloop.SupvisorsMainLoop.check_external_events')
    mocked_req = mocker.patch('supvisors.mainloop.SupvisorsMainLoop.check_requests')
    main_loop.receiver.poll.return_value = ('requests', ['events'])
    # patch two loop
    mocker.patch.object(main_loop.stop_event, 'is_set', side_effect=[False, False, True]*2)
    main_loop.run()
    # test that mocked functions were called once
    assert main_loop.receiver.poll.call_args_list == [call()]
    assert main_loop.receiver.manage_heartbeat.call_args_list == [call()]
    assert mocked_evt.call_args_list == [call(['events'])]
    assert mocked_req.call_args_list == [call('requests')]
    mocker.resetall()
    main_loop.receiver.poll.reset_mock()
    main_loop.receiver.manage_heartbeat.reset_mock()
    # test exception management
    mocked_evt.side_effect = KeyError
    mocked_req.side_effect = KeyError
    main_loop.run()
    # test that mocked functions were called once
    assert main_loop.receiver.poll.call_args_list == [call()]
    assert main_loop.receiver.manage_heartbeat.call_args_list == [call()]
    assert mocked_evt.call_args_list == [call(['events'])]
    assert mocked_req.call_args_list == [call('requests')]
    mocker.resetall()


def test_check_external_events(mocker, main_loop):
    """ Test the processing of the events received. """
    mocked_send = mocker.patch('supvisors.mainloop.SupvisorsMainLoop.send_remote_comm_event')
    # test with appropriate socks but with exception
    main_loop.receiver.read_fds.return_value = ['a message', 'a second message']
    main_loop.check_external_events([1])
    assert main_loop.receiver.read_fds.call_args_list == [call([1])]
    assert mocked_send.call_args_list == [call(RemoteCommEvents.SUPVISORS_EVENT, 'a message'),
                                          call(RemoteCommEvents.SUPVISORS_EVENT, 'a second message')]


def test_check_requests(mocker, main_loop):
    """ Test the processing of the requests received. """
    mocked_send = mocker.patch('supvisors.mainloop.SupvisorsMainLoop.send_request')
    # test with empty socks
    main_loop.check_requests(False)
    assert not main_loop.receiver.read_socket.called
    assert not main_loop.receiver.disconnect_subscriber.called
    assert not mocked_send.called
    # test with empty message
    main_loop.receiver.read_puller.return_value = None
    main_loop.check_requests(True)
    assert main_loop.receiver.read_puller.call_args_list == [call()]
    assert not main_loop.receiver.disconnect_subscriber.called
    assert not mocked_send.called
    # reset mocks
    main_loop.receiver.read_puller.reset_mock()
    # test with node isolation message
    main_loop.receiver.read_puller.return_value = DeferredRequestHeaders.ISOLATE_INSTANCES.value, 'a message'
    main_loop.check_requests(True)
    assert main_loop.receiver.read_puller.call_args_list == [call()]
    assert main_loop.receiver.disconnect_subscriber.call_args_list == [call('a message')]
    assert not mocked_send.called
    # reset mocks
    main_loop.receiver.read_puller.reset_mock()
    main_loop.receiver.disconnect_subscriber.reset_mock()
    # test with other deferred message
    for event in DeferredRequestHeaders:
        if event != DeferredRequestHeaders.ISOLATE_INSTANCES:
            main_loop.receiver.read_puller.return_value = event.value, 'a message'
            main_loop.check_requests(True)
            assert main_loop.receiver.read_puller.call_args_list == [call()]
            assert not main_loop.receiver.disconnect_subscriber.called
            assert mocked_send.call_args_list == [call(event, 'a message')]
            # reset mocks
            main_loop.receiver.read_puller.reset_mock()
            mocked_send.reset_mock()


def test_check_instance(mocker, mocked_rpc, main_loop):
    """ Test the SupvisorsMainLoop.check_instance method. """
    mocked_auth = mocker.patch.object(main_loop, '_is_authorized', return_value=False)
    mocked_mode = mocker.patch.object(main_loop, '_transfer_states_modes')
    mocked_info = mocker.patch.object(main_loop, '_transfer_process_info')
    mocked_send = mocker.patch.object(main_loop, 'send_remote_comm_event')
    # test with no authorization
    main_loop.check_instance('10.0.0.1')
    assert mocked_auth.call_args_list == [call('10.0.0.1')]
    assert not mocked_mode.called
    assert not mocked_info.called
    assert mocked_send.call_args_list == [call(RemoteCommEvents.SUPVISORS_AUTH, ('10.0.0.1', False))]
    mocker.resetall()
    # test with authorization
    mocked_auth.return_value = True
    main_loop.check_instance('10.0.0.1')
    assert mocked_auth.call_args_list == [call('10.0.0.1')]
    assert mocked_mode.call_args_list == [call('10.0.0.1')]
    assert mocked_info.call_args_list == [call('10.0.0.1')]
    assert mocked_send.call_args_list == [call(RemoteCommEvents.SUPVISORS_AUTH, ('10.0.0.1', True))]


def test_is_authorized(mocker, mocked_rpc, main_loop):
    """ Test the SupvisorsMainLoop._is_authorized method. """
    mocked_rpc.reset_mock()
    local_identifier = main_loop.supvisors.context.local_identifier
    # test with XML-RPC failure
    mocked_rpc.side_effect = ValueError
    assert main_loop._is_authorized('10.0.0.1') is None
    assert mocked_rpc.call_args_list == [call(main_loop.srv_url.env)]
    mocked_rpc.reset_mock()
    # test with a mocked rpc interface
    rpc_intf = DummyRpcInterface(main_loop.supvisors)
    mocked_call = mocker.patch.object(rpc_intf.supvisors, 'get_instance_info')
    mocked_rpc.return_value = rpc_intf
    mocked_rpc.side_effect = None
    # test with local Supvisors instance isolated by remote
    for state in ISOLATION_STATES:
        mocked_call.return_value = {'statecode': state.value}
        assert main_loop._is_authorized('10.0.0.1') is False
        assert mocked_call.call_args_list == [call(local_identifier)]
        assert mocked_rpc.call_args_list == [call(main_loop.srv_url.env)]
        # reset counters
        mocked_call.reset_mock()
        mocked_rpc.reset_mock()
    # test with local Supvisors instance not isolated by remote
    for state in [x for x in SupvisorsInstanceStates if x not in ISOLATION_STATES]:
        mocked_call.return_value = {'statecode': state.value}
        assert main_loop._is_authorized('10.0.0.1') is True
        assert mocked_call.call_args_list == [call(local_identifier)]
        assert mocked_rpc.call_args_list == [call(main_loop.srv_url.env)]
        # reset counters
        mocked_call.reset_mock()
        mocked_rpc.reset_mock()
    # test with local Supvisors instance not isolated by remote but returning an unknown state
    mocked_call.return_value = {'statecode': 128}
    assert main_loop._is_authorized('10.0.0.1') is False
    assert mocked_call.call_args_list == [call(local_identifier)]
    assert mocked_rpc.call_args_list == [call(main_loop.srv_url.env)]


def test_transfer_process_info(mocker, mocked_rpc, main_loop):
    """ Test the SupvisorsMainLoop._transfer_process_info method. """
    mocked_rpc.reset_mock()
    mocked_send = mocker.patch.object(main_loop, 'send_remote_comm_event')
    # test with XML-RPC failure
    mocked_rpc.side_effect = ValueError
    main_loop._transfer_process_info('10.0.0.1')
    assert mocked_rpc.call_args_list == [call(main_loop.srv_url.env)]
    assert not mocked_send.called
    mocked_rpc.reset_mock()
    # test with a mocked rpc interface
    rpc_intf = DummyRpcInterface(main_loop.supvisors)
    proc_info = [{'name': 'dummy_1'}, {'name': 'dummy_2'}]
    mocked_call = mocker.patch.object(rpc_intf.supvisors, 'get_all_local_process_info', return_value=proc_info)
    mocked_rpc.return_value = rpc_intf
    mocked_rpc.side_effect = None
    main_loop._transfer_process_info('10.0.0.1')
    assert mocked_call.call_args_list == [call()]
    assert mocked_rpc.call_args_list == [call(main_loop.srv_url.env)]
    assert mocked_send.call_args_list == [call(RemoteCommEvents.SUPVISORS_INFO, ('10.0.0.1', proc_info))]


def test_transfer_states_modes(mocker, mocked_rpc, main_loop):
    """ Test the SupvisorsMainLoop._transfer_states_modes method. """
    mocked_rpc.reset_mock()
    mocked_send = mocker.patch.object(main_loop, 'send_remote_comm_event')
    # test with XML-RPC failure
    mocked_rpc.side_effect = ValueError
    main_loop._transfer_states_modes('10.0.0.1')
    assert mocked_rpc.call_args_list == [call(main_loop.srv_url.env)]
    assert not mocked_send.called
    mocked_rpc.reset_mock()
    # test with a mocked rpc interface
    rpc_intf = DummyRpcInterface(main_loop.supvisors)
    instance_info = {'identifier': 'supvisors', 'node_name': '10.0.0.1', 'port': 65000, 'loading': 0,
                     'statecode': 3, 'statename': 'RUNNING',
                     'remote_time': 50, 'local_time': 60,
                     'sequence_counter': 28, 'process_failure': False,
                     'fsm_statecode': 7, 'fsm_statename': 'SHUTTING_DOWN',
                     'discovery_mode': True,
                     'master_identifier': '10.0.0.1',
                     'starting_jobs': False, 'stopping_jobs': True}
    mocked_call = mocker.patch.object(rpc_intf.supvisors, 'get_instance_info', return_value=instance_info)
    mocked_rpc.return_value = rpc_intf
    mocked_rpc.side_effect = None
    main_loop._transfer_states_modes('10.0.0.1')
    assert mocked_call.call_args_list == [call('10.0.0.1')]
    assert mocked_rpc.call_args_list == [call(main_loop.srv_url.env)]
    assert mocked_send.call_args_list == [call(RemoteCommEvents.SUPVISORS_EVENT,
                                               (('10.0.0.1', 65000),
                                                (InternalEventHeaders.STATE.value,
                                                 ('10.0.0.1', {'fsm_statecode': 7, 'fsm_statename': 'SHUTTING_DOWN',
                                                               'discovery_mode': True,
                                                               'master_identifier': '10.0.0.1',
                                                               'starting_jobs': False, 'stopping_jobs': True}))))]


def test_start_process(mocker, mocked_rpc, main_loop):
    """ Test the protocol to start a process handled by a remote Supervisor. """
    # test rpc error
    mocked_rpc.side_effect = KeyError
    main_loop.start_process('10.0.0.1', 'dummy_process', 'extra args')
    assert mocked_rpc.call_count == 2
    assert mocked_rpc.call_args == call(main_loop.srv_url.env)
    # test with a mocked rpc interface
    rpc_intf = DummyRpcInterface(main_loop.supvisors)
    mocked_rpc.side_effect = None
    mocked_rpc.return_value = rpc_intf
    mocked_supvisors = mocker.patch.object(rpc_intf.supvisors, 'start_args')
    main_loop.start_process('10.0.0.1', 'dummy_process', 'extra args')
    assert mocked_rpc.call_count == 3
    assert mocked_rpc.call_args == call(main_loop.srv_url.env)
    assert mocked_supvisors.call_count == 1
    assert mocked_supvisors.call_args == call('dummy_process', 'extra args', False)


def test_stop_process(mocker, mocked_rpc, main_loop):
    """ Test the protocol to stop a process handled by a remote Supervisor. """
    # test rpc error
    mocked_rpc.side_effect = ConnectionResetError
    main_loop.stop_process('10.0.0.1', 'dummy_process')
    assert mocked_rpc.call_count == 2
    assert mocked_rpc.call_args == call(main_loop.srv_url.env)
    # test with a mocked rpc interface
    rpc_intf = DummyRpcInterface(main_loop.supvisors)
    mocked_rpc.side_effect = None
    mocked_rpc.return_value = rpc_intf
    mocked_supervisor = mocker.patch.object(rpc_intf.supervisor, 'stopProcess')
    main_loop.stop_process('10.0.0.1', 'dummy_process')
    assert mocked_rpc.call_count == 3
    assert mocked_rpc.call_args == call(main_loop.srv_url.env)
    assert mocked_supervisor.call_count == 1
    assert mocked_supervisor.call_args == call('dummy_process', False)


def test_restart(mocker, mocked_rpc, main_loop):
    """ Test the protocol to restart a remote Supervisor. """
    # test rpc error
    mocked_rpc.side_effect = OSError
    main_loop.restart('10.0.0.1')
    assert mocked_rpc.call_count == 2
    assert mocked_rpc.call_args == call(main_loop.srv_url.env)
    # test with a mocked rpc interface
    rpc_intf = DummyRpcInterface(main_loop.supvisors)
    mocked_rpc.side_effect = None
    mocked_rpc.return_value = rpc_intf
    mocked_supervisor = mocker.patch.object(rpc_intf.supervisor, 'restart')
    main_loop.restart('10.0.0.1')
    assert mocked_rpc.call_count == 3
    assert mocked_rpc.call_args == call(main_loop.srv_url.env)
    assert mocked_supervisor.call_count == 1
    assert mocked_supervisor.call_args == call()


def test_shutdown(mocker, mocked_rpc, main_loop):
    """ Test the protocol to shut down a remote Supervisor. """
    # test rpc error
    mocked_rpc.side_effect = RPCError(12)
    main_loop.shutdown('10.0.0.1')
    assert mocked_rpc.call_count == 2
    assert mocked_rpc.call_args == call(main_loop.srv_url.env)
    # test with a mocked rpc interface
    rpc_intf = DummyRpcInterface(main_loop.supvisors)
    mocked_rpc.side_effect = None
    mocked_rpc.return_value = rpc_intf
    mocked_shutdown = mocker.patch.object(rpc_intf.supervisor, 'shutdown')
    main_loop.shutdown('10.0.0.1')
    assert mocked_rpc.call_count == 3
    assert mocked_rpc.call_args == call(main_loop.srv_url.env)
    assert mocked_shutdown.call_count == 1
    assert mocked_shutdown.call_args == call()


def test_restart_sequence(mocker, mocked_rpc, main_loop):
    """ Test the protocol to trigger the start_sequence of Supvisors. """
    # test rpc error
    mocked_rpc.side_effect = OSError
    main_loop.restart_sequence('10.0.0.1')
    assert mocked_rpc.call_count == 2
    assert mocked_rpc.call_args == call(main_loop.srv_url.env)
    # test with a mocked rpc interface
    rpc_intf = DummyRpcInterface(main_loop.supvisors)
    mocked_rpc.side_effect = None
    mocked_rpc.return_value = rpc_intf
    mocked_supervisor = mocker.patch.object(rpc_intf.supvisors, 'restart_sequence')
    main_loop.restart_sequence('10.0.0.1')
    assert mocked_rpc.call_count == 3
    assert mocked_rpc.call_args == call(main_loop.srv_url.env)
    assert mocked_supervisor.call_count == 1
    assert mocked_supervisor.call_args == call()


def test_restart_all(mocker, mocked_rpc, main_loop):
    """ Test the protocol to restart Supvisors. """
    # test rpc error
    mocked_rpc.side_effect = OSError
    main_loop.restart_all('10.0.0.1')
    assert mocked_rpc.call_count == 2
    assert mocked_rpc.call_args == call(main_loop.srv_url.env)
    # test with a mocked rpc interface
    rpc_intf = DummyRpcInterface(main_loop.supvisors)
    mocked_rpc.side_effect = None
    mocked_rpc.return_value = rpc_intf
    mocked_supervisor = mocker.patch.object(rpc_intf.supvisors, 'restart')
    main_loop.restart_all('10.0.0.1')
    assert mocked_rpc.call_count == 3
    assert mocked_rpc.call_args == call(main_loop.srv_url.env)
    assert mocked_supervisor.call_count == 1
    assert mocked_supervisor.call_args == call()


def test_shutdown_all(mocker, mocked_rpc, main_loop):
    """ Test the protocol to shut down Supvisors. """
    # test rpc error
    mocked_rpc.side_effect = RPCError(12)
    main_loop.shutdown_all('10.0.0.1')
    assert mocked_rpc.call_count == 2
    assert mocked_rpc.call_args == call(main_loop.srv_url.env)
    # test with a mocked rpc interface
    rpc_intf = DummyRpcInterface(main_loop.supvisors)
    mocked_rpc.side_effect = None
    mocked_rpc.return_value = rpc_intf
    mocked_shutdown = mocker.patch.object(rpc_intf.supvisors, 'shutdown')
    main_loop.shutdown_all('10.0.0.1')
    assert mocked_rpc.call_count == 3
    assert mocked_rpc.call_args == call(main_loop.srv_url.env)
    assert mocked_shutdown.call_count == 1
    assert mocked_shutdown.call_args == call()


def test_comm_event(mocker, mocked_rpc, main_loop):
    """ Test the protocol to send a comm event to the local Supervisor. """
    # test rpc error
    mocker.patch.object(main_loop.proxy.supervisor, 'sendRemoteCommEvent', side_effect=RPCError(100))
    main_loop.send_remote_comm_event(RemoteCommEvents.SUPVISORS_AUTH, 'event data')
    # test with a mocked rpc interface
    mocked_supervisor = mocker.patch.object(main_loop.proxy.supervisor, 'sendRemoteCommEvent')
    main_loop.send_remote_comm_event(RemoteCommEvents.SUPVISORS_AUTH, 'event data')
    assert mocked_supervisor.call_args_list == [call('supv_auth', '"event data"')]


def check_call(main_loop, mocked_loop, method_name, request, args):
    """ Perform a main loop request and check what has been called. """
    # send request
    main_loop.send_request(request, args)
    # test mocked main loop
    assert main_loop.srv_url.env['SUPERVISOR_SERVER_URL'] == 'http://10.0.0.2:65000'
    for key, mocked in mocked_loop.items():
        if key == method_name:
            assert mocked.call_count == 1
            assert mocked.call_args == call(*args)
            mocked.reset_mock()
        else:
            assert not mocked.called


def test_send_request(mocker, main_loop):
    """ Test the execution of a deferred Supervisor request. """
    # patch main loop subscriber
    mocked_loop = mocker.patch.multiple(main_loop, check_instance=DEFAULT,
                                        start_process=DEFAULT, stop_process=DEFAULT,
                                        restart=DEFAULT, shutdown=DEFAULT, restart_sequence=DEFAULT,
                                        restart_all=DEFAULT, shutdown_all=DEFAULT)
    # test check instance
    check_call(main_loop, mocked_loop, 'check_instance',
               DeferredRequestHeaders.CHECK_INSTANCE, ('10.0.0.2',))
    # test start process
    check_call(main_loop, mocked_loop, 'start_process',
               DeferredRequestHeaders.START_PROCESS, ('10.0.0.2', 'dummy_process', 'extra args'))
    # test stop process
    check_call(main_loop, mocked_loop, 'stop_process',
               DeferredRequestHeaders.STOP_PROCESS, ('10.0.0.2', 'dummy_process'))
    # test restart
    check_call(main_loop, mocked_loop, 'restart',
               DeferredRequestHeaders.RESTART, ('10.0.0.2',))
    # test shutdown
    check_call(main_loop, mocked_loop, 'shutdown',
               DeferredRequestHeaders.SHUTDOWN, ('10.0.0.2',))
    # test restart_sequence
    check_call(main_loop, mocked_loop, 'restart_sequence',
               DeferredRequestHeaders.RESTART_SEQUENCE, ('10.0.0.2',))
    # test restart_all
    check_call(main_loop, mocked_loop, 'restart_all',
               DeferredRequestHeaders.RESTART_ALL, ('10.0.0.2',))
    # test shutdown
    check_call(main_loop, mocked_loop, 'shutdown_all',
               DeferredRequestHeaders.SHUTDOWN_ALL, ('10.0.0.2',))
