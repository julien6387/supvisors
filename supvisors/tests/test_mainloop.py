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
from supvisors.ttypes import DeferredRequestHeaders, SupvisorsStates, SupvisorsInstanceStates
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
    server_url = main_loop.supvisors.supervisor_data.supervisord.options.serverurl
    assert main_loop.srv_url.env == {'SUPERVISOR_SERVER_URL': server_url,
                                     'SUPERVISOR_USERNAME': 'user',
                                     'SUPERVISOR_PASSWORD': 'p@$$w0rd'}
    assert mocked_rpc.call_args_list == [call(main_loop.srv_url.env)]
    assert main_loop.subscriber is not None


def test_stopping(mocked_rpc, main_loop):
    """ Test the get_loop method. """
    assert not main_loop.stopping()
    main_loop.stop_event.set()
    assert main_loop.stopping()


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
    main_loop.subscriber.poll.return_value = ('requests', ['events'])
    # patch one loop
    mocker.patch.object(main_loop, 'stopping', side_effect=[False, False, True])
    main_loop.run()
    # test that mocked functions were called once
    assert main_loop.subscriber.poll.call_args_list == [call()]
    assert main_loop.subscriber.manage_heartbeat.call_args_list == [call()]
    assert mocked_evt.call_args_list == [call(['events'])]
    assert mocked_req.call_args_list == [call('requests')]


def test_check_external_events(mocker, main_loop):
    """ Test the processing of the events received. """
    mocked_send = mocker.patch('supvisors.mainloop.SupvisorsMainLoop.send_remote_comm_event')
    # test with appropriate socks but with exception
    main_loop.subscriber.read_subscribers.return_value = ['a message', 'a second message']
    main_loop.check_external_events(['poll result'])
    assert main_loop.subscriber.read_subscribers.call_args_list == [call(['poll result'])]
    assert mocked_send.call_args_list == [call(RemoteCommEvents.SUPVISORS_EVENT, 'a message'),
                                          call(RemoteCommEvents.SUPVISORS_EVENT, 'a second message')]


def test_check_requests(mocker, main_loop):
    """ Test the processing of the requests received. """
    mocked_send = mocker.patch('supvisors.mainloop.SupvisorsMainLoop.send_request')
    # test with empty socks
    main_loop.check_requests(None)
    assert not main_loop.subscriber.read_socket.called
    assert not main_loop.subscriber.disconnect_subscriber.called
    assert not mocked_send.called
    # test with empty message
    main_loop.subscriber.read_socket.return_value = None
    main_loop.check_requests('socket')
    assert main_loop.subscriber.read_socket.call_args_list == [call('socket')]
    assert not main_loop.subscriber.disconnect_subscriber.called
    assert not mocked_send.called
    # reset mocks
    main_loop.subscriber.read_socket.reset_mock()
    # test with node isolation message
    main_loop.subscriber.read_socket.return_value = DeferredRequestHeaders.ISOLATE_INSTANCES.value, 'a message'
    main_loop.check_requests('socket')
    assert main_loop.subscriber.read_socket.call_args_list == [call('socket')]
    assert main_loop.subscriber.disconnect_subscriber.call_args_list == [call('a message')]
    assert not mocked_send.called
    # reset mocks
    main_loop.subscriber.read_socket.reset_mock()
    main_loop.subscriber.disconnect_subscriber.reset_mock()
    # test with other deferred message
    for event in DeferredRequestHeaders:
        if event != DeferredRequestHeaders.ISOLATE_INSTANCES:
            main_loop.subscriber.read_socket.return_value = event.value, 'a message'
            main_loop.check_requests('socket')
            assert main_loop.subscriber.read_socket.call_args_list == [call('socket')]
            assert not main_loop.subscriber.disconnect_subscriber.called
            assert mocked_send.call_args_list == [call(event, 'a message')]
            # reset mocks
            main_loop.subscriber.read_socket.reset_mock()
            mocked_send.reset_mock()


def test_check_instance_no_com(mocker, mocked_rpc, main_loop):
    """ Test the SupvisorsMainLoop.check_instance with a remote Supervisor that does not respond. """
    mocker.patch('supvisors.mainloop.stderr')
    mocked_evt = mocker.patch.object(main_loop, 'send_remote_comm_event')
    mocked_rpc.reset_mock()
    # test rpc error: SHUTDOWN event is sent to local Supervisor
    mocked_rpc.side_effect = ValueError
    main_loop.check_instance('10.0.0.1')
    assert mocked_rpc.call_args_list == [call(main_loop.srv_url.env)]
    auth_message = '10.0.0.1', None, ''
    state_message = InternalEventHeaders.STATE.value, ('10.0.0.1', {'fsm_statecode': 0, 'starting_jobs': False,
                                                                    'stopping_jobs': False})
    assert mocked_evt.call_args_list == [call(RemoteCommEvents.SUPVISORS_AUTH, auth_message),
                                         call(RemoteCommEvents.SUPVISORS_EVENT, state_message)]


def test_check_instance_isolation(mocker, mocked_rpc, main_loop):
    """ Test the SupvisorsMainLoop.check_instance with a remote Supervisor that has isolated the local instance. """
    mocker.patch('supvisors.mainloop.stderr')
    mocked_evt = mocker.patch.object(main_loop, 'send_remote_comm_event')
    mocked_rpc.reset_mock()
    hostname = gethostname()
    # test with a mocked rpc interface
    rpc_intf = DummyRpcInterface(main_loop.supvisors)
    mocked_local = mocker.patch.object(rpc_intf.supvisors, 'get_all_local_process_info')
    mocked_instance = mocker.patch.object(rpc_intf.supvisors, 'get_instance_info')
    mocker.patch.object(rpc_intf.supvisors, 'get_master_identifier', return_value='10.0.0.5')
    mocked_rpc.return_value = rpc_intf
    # test with local Supvisors instance isolated by remote
    instance_info = {'fsm_statecode': SupvisorsStates.CONCILIATION.value, 'starting_jobs': False, 'stopping_jobs': True}
    auth_message = '10.0.0.1:60000', False, '10.0.0.5'
    state_message = InternalEventHeaders.STATE.value, ('10.0.0.1:60000', instance_info)
    for state in [SupvisorsInstanceStates.ISOLATING, SupvisorsInstanceStates.ISOLATED]:
        mocked_instance.return_value = dict(instance_info, **{'statecode': state.value})
        main_loop.check_instance('10.0.0.1:60000')
        assert mocked_instance.call_args_list == [call(hostname), call('10.0.0.1:60000')]
        assert mocked_rpc.call_args_list == [call(main_loop.srv_url.env)]
        assert mocked_evt.call_args_list == [call(RemoteCommEvents.SUPVISORS_AUTH, auth_message),
                                             call(RemoteCommEvents.SUPVISORS_EVENT, state_message)]
        assert not mocked_local.called
        # reset counters
        mocked_instance.reset_mock()
        mocked_evt.reset_mock()
        mocked_rpc.reset_mock()


def test_check_instance_info_exception(mocker, mocked_rpc, main_loop):
    """ Test the SupvisorsMainLoop.check_instance with a remote Supervisor that has not isolated the local instance
    but that is about to restart or shut down. """
    mocker.patch('supvisors.mainloop.stderr')
    mocked_evt = mocker.patch.object(main_loop, 'send_remote_comm_event')
    mocked_rpc.reset_mock()
    hostname = gethostname()
    # test with a mocked rpc interface
    rpc_intf = DummyRpcInterface(main_loop.supvisors)
    mocked_local = mocker.patch.object(rpc_intf.supvisors, 'get_all_local_process_info', side_effect=ValueError)
    mocked_instance = mocker.patch.object(rpc_intf.supvisors, 'get_instance_info')
    mocker.patch.object(rpc_intf.supvisors, 'get_master_identifier', return_value='10.0.0.5')
    mocked_rpc.return_value = rpc_intf
    # test with local Supvisors instance not isolated by remote
    # exception on get_all_local_process_info
    instance_info = {'fsm_statecode': SupvisorsStates.CONCILIATION.value, 'starting_jobs': False, 'stopping_jobs': True}
    auth_message = '10.0.0.1', True, '10.0.0.5'
    state_message = InternalEventHeaders.STATE.value, ('10.0.0.1', instance_info)
    for state in [SupvisorsInstanceStates.UNKNOWN, SupvisorsInstanceStates.CHECKING, SupvisorsInstanceStates.RUNNING,
                  SupvisorsInstanceStates.SILENT]:
        mocked_instance.return_value = dict(instance_info, **{'statecode': state.value})
        main_loop.check_instance('10.0.0.1')
        assert mocked_instance.call_args_list == [call(hostname), call('10.0.0.1')]
        assert mocked_rpc.call_args_list == [call(main_loop.srv_url.env)]
        assert mocked_evt.call_args_list == [call(RemoteCommEvents.SUPVISORS_AUTH, auth_message),
                                             call(RemoteCommEvents.SUPVISORS_EVENT, state_message)]
        assert mocked_local.called
        # reset counters
        mocked_instance.reset_mock()
        mocked_evt.reset_mock()
        mocked_local.reset_mock()
        mocked_rpc.reset_mock()


def test_check_instance_normal(mocker, mocked_rpc, main_loop):
    """ Test the SupvisorsMainLoop.check_instance with a remote Supervisor that has not isolated the local instance
    and that provide process information. """
    mocker.patch('supvisors.mainloop.stderr')
    mocked_evt = mocker.patch.object(main_loop, 'send_remote_comm_event')
    mocked_rpc.reset_mock()
    hostname = gethostname()
    # test with a mocked rpc interface
    dummy_info = [{'name': 'proc', 'group': 'appli', 'state': 10, 'start': 5, 'now': 10, 'pid': 1234, 'spawnerr': ''}]
    rpc_intf = DummyRpcInterface(main_loop.supvisors)
    mocked_local = mocker.patch.object(rpc_intf.supvisors, 'get_all_local_process_info', return_value=dummy_info)
    mocked_instance = mocker.patch.object(rpc_intf.supvisors, 'get_instance_info')
    mocker.patch.object(rpc_intf.supvisors, 'get_master_identifier', return_value='10.0.0.5')
    mocked_rpc.return_value = rpc_intf
    # test with local Supvisors instance not isolated by remote and with remote not in closing state
    instance_info = {'fsm_statecode': SupvisorsStates.OPERATION.value, 'starting_jobs': True, 'stopping_jobs': False}
    auth_message = '10.0.0.1', True, '10.0.0.5'
    info_message = '10.0.0.1', dummy_info
    state_message = InternalEventHeaders.STATE.value, ('10.0.0.1', instance_info)
    for state in [SupvisorsInstanceStates.UNKNOWN, SupvisorsInstanceStates.CHECKING, SupvisorsInstanceStates.RUNNING,
                  SupvisorsInstanceStates.SILENT]:
        mocked_instance.return_value = dict(instance_info, **{'statecode': state.value})
        main_loop.check_instance('10.0.0.1')
        assert mocked_instance.call_args_list == [call(hostname), call('10.0.0.1')]
        assert mocked_rpc.call_args_list == [call(main_loop.srv_url.env)]
        assert mocked_evt.call_args_list == [call(RemoteCommEvents.SUPVISORS_AUTH, auth_message),
                                             call(RemoteCommEvents.SUPVISORS_EVENT, state_message),
                                             call(RemoteCommEvents.SUPVISORS_INFO, info_message)]
        assert mocked_local.called
        # reset counters
        mocked_instance.reset_mock()
        mocked_evt.reset_mock()
        mocked_local.reset_mock()
        mocked_rpc.reset_mock()


def test_start_process(mocker, mocked_rpc, main_loop):
    """ Test the protocol to start a process handled by a remote Supervisor. """
    mocker.patch('supvisors.mainloop.stderr')
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
    mocker.patch('supvisors.mainloop.stderr')
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
    mocker.patch('supvisors.mainloop.stderr')
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
    """ Test the protocol to shutdown a remote Supervisor. """
    mocker.patch('supvisors.mainloop.stderr')
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
    mocker.patch('supvisors.mainloop.stderr')
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
    mocker.patch('supvisors.mainloop.stderr')
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
    """ Test the protocol to shutdown Supvisors. """
    mocker.patch('supvisors.mainloop.stderr')
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
    mocker.patch('supvisors.mainloop.stderr')
    # test rpc error
    mocker.patch.object(main_loop.proxy.supervisor, 'sendRemoteCommEvent', side_effect=RPCError(100))
    main_loop.send_remote_comm_event(RemoteCommEvents.SUPVISORS_AUTH, 'event data')
    # test with a mocked rpc interface
    mocked_supervisor = mocker.patch.object(main_loop.proxy.supervisor, 'sendRemoteCommEvent')
    main_loop.send_remote_comm_event(RemoteCommEvents.SUPVISORS_AUTH, 'event data')
    assert mocked_supervisor.call_args_list == [call('auth', '"event data"')]


def check_call(main_loop, mocked_loop, method_name, request, args):
    """ Perform a main loop request and check what has been called. """
    # send request
    main_loop.send_request(request, args)
    # test mocked main loop
    assert main_loop.srv_url.parsed_url.geturl() == 'http://10.0.0.2:65000'
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
