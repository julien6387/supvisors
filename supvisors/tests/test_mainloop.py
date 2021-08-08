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

import pytest

from supvisors.mainloop import *
from supvisors.ttypes import AddressStates
from supvisors.utils import DeferredRequestHeaders

from threading import Thread
from unittest.mock import call, patch, Mock, DEFAULT

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
    assert main_loop.env == {'SUPERVISOR_SERVER_URL': 'http://127.0.0.1:65000',
                             'SUPERVISOR_USERNAME': '',
                             'SUPERVISOR_PASSWORD': ''}
    assert mocked_rpc.call_args_list == [call('localhost', main_loop.env)]


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
    assert mocked_join.call_count == 1


def test_run(mocker, main_loop):
    """ Test the running of the main loop thread. """
    mocked_evt = mocker.patch('supvisors.mainloop.SupvisorsMainLoop.check_events')
    mocked_req = mocker.patch('supvisors.mainloop.SupvisorsMainLoop.check_requests')
    mocked_poll = mocker.patch('supvisors.supvisorszmq.SupvisorsZmq.poll')
    # patch one loops
    mocker.patch.object(main_loop, 'stopping', side_effect=[False, False, True])
    main_loop.run()
    # test that poll was called once
    assert mocked_poll.call_args_list == [call()]
    # test that check_requests was called once
    assert mocked_evt.call_count == 1
    # test that check_events was called once
    assert mocked_req.call_count == 1


def test_check_events(mocker, main_loop):
    """ Test the processing of the events received. """
    mocked_send = mocker.patch('supvisors.mainloop.SupvisorsMainLoop.send_remote_comm_event')
    # prepare context
    mocked_sockets = Mock(**{'check_subscriber.return_value': None})
    # test with empty socks
    main_loop.check_events(mocked_sockets, 'poll result')
    assert mocked_sockets.check_subscriber.call_args_list == [call('poll result')]
    assert not mocked_send.called
    # reset mocks
    mocked_sockets.check_subscriber.reset_mock()
    # test with appropriate socks but with exception
    mocked_sockets.check_subscriber.return_value = 'a message'
    main_loop.check_events(mocked_sockets, 'poll result')
    assert mocked_sockets.check_subscriber.call_args_list == [call('poll result')]
    assert mocked_send.call_args_list == [call('event', '"a message"')]


def test_check_requests(mocker, main_loop):
    """ Test the processing of the requests received. """
    mocked_send = mocker.patch('supvisors.mainloop.SupvisorsMainLoop.send_request')
    # prepare context
    mocked_sockets = Mock(**{'check_puller.return_value': None})
    # test with empty socks
    main_loop.check_requests(mocked_sockets, 'poll result')
    assert mocked_sockets.check_puller.call_args_list == [call('poll result')]
    assert not mocked_sockets.disconnect_subscriber.called
    assert not mocked_send.called
    # reset mocks
    mocked_sockets.check_puller.reset_mock()
    # test with appropriate socks but with exception
    mocked_sockets.check_puller.return_value = DeferredRequestHeaders.ISOLATE_NODES, 'a message'
    main_loop.check_requests(mocked_sockets, 'poll result')
    assert mocked_sockets.check_puller.call_args_list == [call('poll result')]
    assert mocked_sockets.disconnect_subscriber.call_args_list == [call('a message')]
    assert not mocked_send.called
    # reset mocks
    mocked_sockets.check_puller.reset_mock()
    mocked_sockets.disconnect_subscriber.reset_mock()
    # test with appropriate socks but with exception
    mocked_sockets.check_puller.return_value = 'event', 'a message'
    main_loop.check_requests(mocked_sockets, 'poll result')
    assert mocked_sockets.check_puller.call_args_list == [call('poll result')]
    assert not mocked_sockets.disconnect_subscriber.called
    assert mocked_send.call_args_list == [call('event', 'a message')]


def test_check_node(mocker, mocked_rpc, main_loop):
    """ Test the protocol to get the processes handled by a remote Supervisor. """
    mocker.patch('supvisors.mainloop.stderr')
    mocked_evt = mocker.patch('supvisors.mainloop.SupvisorsMainLoop.send_remote_comm_event')
    # test rpc error: no event is sent to local Supervisor
    mocked_rpc.side_effect = ValueError
    main_loop.check_node('10.0.0.1')
    assert mocked_rpc.call_count == 2
    assert mocked_rpc.call_args == call('10.0.0.1', main_loop.env)
    assert mocked_evt.call_count == 0
    # test with a mocked rpc interface
    dummy_info = [{'name': 'proc', 'group': 'appli', 'state': 10, 'start': 5,
                   'now': 10, 'pid': 1234, 'spawnerr': ''}]
    rpc_intf = DummyRpcInterface()
    mocked_all = rpc_intf.supervisor.getAllProcessInfo = Mock()
    mocked_local = rpc_intf.supvisors.get_all_local_process_info = Mock(return_value=dummy_info)
    mocked_addr = rpc_intf.supvisors.get_address_info = Mock()
    rpc_intf.supvisors.get_master_address = Mock(return_value='10.0.0.5')
    rpc_intf.supvisors.get_supvisors_state = Mock(return_value={'statename': 'RUNNING'})
    mocked_rpc.return_value = rpc_intf
    mocked_rpc.side_effect = None
    mocked_rpc.reset_mock()
    # test with address in isolation
    for state in [AddressStates.ISOLATING, AddressStates.ISOLATED]:
        mocked_addr.return_value = {'statecode': state}
        main_loop.check_node('10.0.0.1')
        assert mocked_rpc.call_args_list == [call('10.0.0.1', main_loop.env)]
        expected = 'node_name:10.0.0.1 authorized:False master_node_name:10.0.0.5 supvisors_state:RUNNING'
        assert mocked_evt.call_args_list == [call('auth', expected)]
        assert not mocked_all.called
        # reset counters
        mocked_evt.reset_mock()
        mocked_rpc.reset_mock()
    # test with address not in isolation
    for state in [AddressStates.UNKNOWN, AddressStates.CHECKING, AddressStates.RUNNING, AddressStates.SILENT]:
        mocked_addr.return_value = {'statecode': state}
        main_loop.check_node('10.0.0.1')
        assert mocked_rpc.call_count == 1
        assert mocked_rpc.call_args == call('10.0.0.1', main_loop.env)
        assert mocked_evt.call_count == 2
        assert mocked_local.call_count == 1
        # reset counters
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
    assert mocked_rpc.call_args == call('10.0.0.1', main_loop.env)
    # test with a mocked rpc interface
    rpc_intf = DummyRpcInterface()
    mocked_rpc.side_effect = None
    mocked_rpc.return_value = rpc_intf
    mocked_supvisors = mocker.patch.object(rpc_intf.supvisors, 'start_args')
    main_loop.start_process('10.0.0.1', 'dummy_process', 'extra args')
    assert mocked_rpc.call_count == 3
    assert mocked_rpc.call_args == call('10.0.0.1', main_loop.env)
    assert mocked_supvisors.call_count == 1
    assert mocked_supvisors.call_args == call('dummy_process', 'extra args', False)


def test_stop_process(mocker, mocked_rpc, main_loop):
    """ Test the protocol to stop a process handled by a remote Supervisor. """
    mocker.patch('supvisors.mainloop.stderr')
    # test rpc error
    mocked_rpc.side_effect = ConnectionResetError
    main_loop.stop_process('10.0.0.1', 'dummy_process')
    assert mocked_rpc.call_count == 2
    assert mocked_rpc.call_args == call('10.0.0.1', main_loop.env)
    # test with a mocked rpc interface
    rpc_intf = DummyRpcInterface()
    mocked_rpc.side_effect = None
    mocked_rpc.return_value = rpc_intf
    mocked_supervisor = mocker.patch.object(rpc_intf.supervisor, 'stopProcess')
    main_loop.stop_process('10.0.0.1', 'dummy_process')
    assert mocked_rpc.call_count == 3
    assert mocked_rpc.call_args == call('10.0.0.1', main_loop.env)
    assert mocked_supervisor.call_count == 1
    assert mocked_supervisor.call_args == call('dummy_process', False)


def test_restart(mocker, mocked_rpc, main_loop):
    """ Test the protocol to restart a remote Supervisor. """
    mocker.patch('supvisors.mainloop.stderr')
    # test rpc error
    mocked_rpc.side_effect = OSError
    main_loop.restart('10.0.0.1')
    assert mocked_rpc.call_count == 2
    assert mocked_rpc.call_args == call('10.0.0.1', main_loop.env)
    # test with a mocked rpc interface
    rpc_intf = DummyRpcInterface()
    mocked_rpc.side_effect = None
    mocked_rpc.return_value = rpc_intf
    mocked_supervisor = mocker.patch.object(rpc_intf.supervisor, 'restart')
    main_loop.restart('10.0.0.1')
    assert mocked_rpc.call_count == 3
    assert mocked_rpc.call_args == call('10.0.0.1', main_loop.env)
    assert mocked_supervisor.call_count == 1
    assert mocked_supervisor.call_args == call()


def test_shutdown(mocker, mocked_rpc, main_loop):
    """ Test the protocol to shutdown a remote Supervisor. """
    mocker.patch('supvisors.mainloop.stderr')
    # test rpc error
    mocked_rpc.side_effect = RPCError(12)
    main_loop.shutdown('10.0.0.1')
    assert mocked_rpc.call_count == 2
    assert mocked_rpc.call_args == call('10.0.0.1', main_loop.env)
    # test with a mocked rpc interface
    rpc_intf = DummyRpcInterface()
    mocked_rpc.side_effect = None
    mocked_rpc.return_value = rpc_intf
    mocked_shutdown = mocker.patch.object(rpc_intf.supervisor, 'shutdown')
    main_loop.shutdown('10.0.0.1')
    assert mocked_rpc.call_count == 3
    assert mocked_rpc.call_args == call('10.0.0.1', main_loop.env)
    assert mocked_shutdown.call_count == 1
    assert mocked_shutdown.call_args == call()


def test_restart_all(mocker, mocked_rpc, main_loop):
    """ Test the protocol to restart Supvisors. """
    mocker.patch('supvisors.mainloop.stderr')
    # test rpc error
    mocked_rpc.side_effect = OSError
    main_loop.restart_all('10.0.0.1')
    assert mocked_rpc.call_count == 2
    assert mocked_rpc.call_args == call('10.0.0.1', main_loop.env)
    # test with a mocked rpc interface
    rpc_intf = DummyRpcInterface()
    mocked_rpc.side_effect = None
    mocked_rpc.return_value = rpc_intf
    mocked_supervisor = mocker.patch.object(rpc_intf.supvisors, 'restart')
    main_loop.restart_all('10.0.0.1')
    assert mocked_rpc.call_count == 3
    assert mocked_rpc.call_args == call('10.0.0.1', main_loop.env)
    assert mocked_supervisor.call_count == 1
    assert mocked_supervisor.call_args == call()


def test_shutdown_all(mocker, mocked_rpc, main_loop):
    """ Test the protocol to shutdown Supvisors. """
    mocker.patch('supvisors.mainloop.stderr')
    # test rpc error
    mocked_rpc.side_effect = RPCError(12)
    main_loop.shutdown_all('10.0.0.1')
    assert mocked_rpc.call_count == 2
    assert mocked_rpc.call_args == call('10.0.0.1', main_loop.env)
    # test with a mocked rpc interface
    rpc_intf = DummyRpcInterface()
    mocked_rpc.side_effect = None
    mocked_rpc.return_value = rpc_intf
    mocked_shutdown = mocker.patch.object(rpc_intf.supvisors, 'shutdown')
    main_loop.shutdown_all('10.0.0.1')
    assert mocked_rpc.call_count == 3
    assert mocked_rpc.call_args == call('10.0.0.1', main_loop.env)
    assert mocked_shutdown.call_count == 1
    assert mocked_shutdown.call_args == call()


def test_comm_event(mocker, mocked_rpc, main_loop):
    """ Test the protocol to send a comm event to the local Supervisor. """
    mocker.patch('supvisors.mainloop.stderr')
    # test rpc error
    mocker.patch.object(main_loop.proxy.supervisor, 'sendRemoteCommEvent', side_effect=RPCError(100))
    main_loop.send_remote_comm_event('event type', 'event data')
    # test with a mocked rpc interface
    mocked_supervisor = mocker.patch.object(main_loop.proxy.supervisor, 'sendRemoteCommEvent')
    main_loop.send_remote_comm_event('event type', 'event data')
    assert mocked_supervisor.call_args_list == [call('event type', 'event data')]


def check_call(main_loop, mocked_loop, method_name, request, args):
    """ Perform a main loop request and check what has been called. """
    # send request
    main_loop.send_request(request.value, args)
    # test mocked main loop
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
    mocked_loop = mocker.patch.multiple(main_loop, check_node=DEFAULT,
                                        start_process=DEFAULT, stop_process=DEFAULT,
                                        restart=DEFAULT, shutdown=DEFAULT,
                                        restart_all=DEFAULT, shutdown_all=DEFAULT)
    # test check address
    check_call(main_loop, mocked_loop, 'check_node',
               DeferredRequestHeaders.CHECK_NODE, ('10.0.0.2',))
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
    # test restart_all
    check_call(main_loop, mocked_loop, 'restart_all',
               DeferredRequestHeaders.RESTART_ALL, ('10.0.0.2',))
    # test shutdown
    check_call(main_loop, mocked_loop, 'shutdown_all',
               DeferredRequestHeaders.SHUTDOWN_ALL, ('10.0.0.2',))
