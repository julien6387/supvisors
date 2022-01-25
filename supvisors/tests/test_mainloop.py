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
from supvisors.ttypes import SupvisorsInstanceStates
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
def main_loop(mocker, supvisors):
    mocked_zmq = Mock(publisher=Mock(), subscriber=Mock(), puller=Mock(), poller=Mock(), spec=SupvisorsZmq)
    mocker.patch('supvisors.mainloop.SupvisorsZmq', return_value=mocked_zmq)
    return SupvisorsMainLoop(supvisors)


def test_creation_error(mocker, supvisors, mocked_rpc):
    """ Test the values set at construction. """
    mocker.patch('supvisors.mainloop.SupvisorsZmq', side_effect=ZMQError)
    main_loop = SupvisorsMainLoop(supvisors)
    server_url = main_loop.supvisors.supervisor_data.supervisord.options.serverurl
    assert isinstance(main_loop, Thread)
    assert main_loop.supvisors is supvisors
    assert not main_loop.stop_event.is_set()
    assert main_loop.srv_url.env == {'SUPERVISOR_SERVER_URL': server_url,
                                     'SUPERVISOR_USERNAME': 'user',
                                     'SUPERVISOR_PASSWORD': 'p@$$w0rd'}
    assert mocked_rpc.call_args_list == [call(main_loop.srv_url.env)]
    assert main_loop.supervisor_time == 0
    assert main_loop.reference_time == 0.0
    assert main_loop.reference_counter == 0
    assert main_loop.sockets is None


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
    assert main_loop.supervisor_time == 0
    assert main_loop.reference_time == 0.0
    assert main_loop.reference_counter == 0
    assert main_loop.sockets is not None


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
    mocker.patch('supvisors.mainloop.time', return_value=1234)
    mocked_beat = mocker.patch('supvisors.mainloop.SupvisorsMainLoop.manage_heartbeat')
    mocked_evt = mocker.patch('supvisors.mainloop.SupvisorsMainLoop.check_events')
    mocked_req = mocker.patch('supvisors.mainloop.SupvisorsMainLoop.check_requests')
    # patch one loops
    mocker.patch.object(main_loop, 'stopping', side_effect=[False, False, True])
    main_loop.run()
    assert main_loop.supervisor_time == 1234
    assert main_loop.reference_time == 1234
    assert main_loop.reference_counter == 0
    # test that mocked functions were called once
    assert main_loop.sockets.poll.call_args_list == [call()]
    assert mocked_beat.call_count == 1
    assert mocked_evt.call_count == 1
    assert mocked_req.call_count == 1


def test_manage_heartbeat(mocker, main_loop):
    """ Test the management of the Supvisors heartbeat. """
    mocker.patch('supvisors.mainloop.time', return_value=3600)
    mocker.patch('supvisors.mainloop.stderr')
    # check initial status
    assert main_loop.supervisor_time == 0
    assert main_loop.reference_time == 0.0
    assert main_loop.reference_counter == 0
    # test when period not reached
    main_loop.reference_time = 3597
    main_loop.manage_heartbeat()
    assert main_loop.reference_counter == 0
    assert not main_loop.sockets.publisher.send_tick_event.called
    # test when period reached
    main_loop.reference_time = 3594
    main_loop.manage_heartbeat()
    assert main_loop.reference_counter == 1
    assert main_loop.sockets.publisher.send_tick_event.call_args_list == [call({'sequence_counter': 1, 'when': 3600})]


def test_check_events(mocker, main_loop):
    """ Test the processing of the events received. """
    mocked_send = mocker.patch('supvisors.mainloop.SupvisorsMainLoop.send_remote_comm_event')
    # prepare context
    mocked_sockets = Mock(**{'check_subscriber.return_value': None})
    # test with empty socks
    main_loop.sockets.check_subscriber.return_value = None
    main_loop.check_events('poll result')
    assert main_loop.sockets.check_subscriber.call_args_list == [call('poll result')]
    assert not mocked_send.called
    # reset mocks
    main_loop.sockets.check_subscriber.reset_mock()
    # test with appropriate socks but with exception
    main_loop.sockets.check_subscriber.return_value = 'a message'
    main_loop.check_events('poll result')
    assert main_loop.sockets.check_subscriber.call_args_list == [call('poll result')]
    assert mocked_send.call_args_list == [call('event', '"a message"')]


def test_check_requests(mocker, main_loop):
    """ Test the processing of the requests received. """
    mocked_send = mocker.patch('supvisors.mainloop.SupvisorsMainLoop.send_request')
    # store reference time
    ref_time = main_loop.supervisor_time
    # test with empty socks
    main_loop.sockets.check_puller.return_value = None
    main_loop.check_requests('poll result')
    assert main_loop.sockets.check_puller.call_args_list == [call('poll result')]
    assert main_loop.supervisor_time == ref_time
    assert not main_loop.sockets.publisher.forward_event.called
    assert not main_loop.sockets.disconnect_subscriber.called
    assert not mocked_send.called
    # reset mocks
    main_loop.sockets.check_puller.reset_mock()
    # test with node isolation message
    main_loop.sockets.check_puller.return_value = DeferredRequestHeaders.ISOLATE_INSTANCES.value, 'a message'
    main_loop.check_requests('poll result')
    assert main_loop.sockets.check_puller.call_args_list == [call('poll result')]
    assert main_loop.supervisor_time == ref_time
    assert not main_loop.sockets.publisher.forward_event.called
    assert main_loop.sockets.disconnect_subscriber.call_args_list == [call('a message')]
    assert not mocked_send.called
    # reset mocks
    main_loop.sockets.check_puller.reset_mock()
    main_loop.sockets.disconnect_subscriber.reset_mock()
    # test with other deferred message
    for event in DeferredRequestHeaders:
        if event != DeferredRequestHeaders.ISOLATE_INSTANCES:
            main_loop.sockets.check_puller.return_value = event.value, 'a message'
            main_loop.check_requests('poll result')
            assert main_loop.sockets.check_puller.call_args_list == [call('poll result')]
            assert main_loop.supervisor_time == ref_time
            assert not main_loop.sockets.publisher.forward_event.called
            assert not main_loop.sockets.disconnect_subscriber.called
            assert mocked_send.call_args_list == [call(event, 'a message')]
            # reset mocks
            main_loop.sockets.check_puller.reset_mock()
            mocked_send.reset_mock()
    # test with tick message
    main_loop.sockets.check_puller.return_value = InternalEventHeaders.TICK.value, ('127.0.0.1', {'when': 1234})
    main_loop.check_requests('poll result')
    assert main_loop.sockets.check_puller.call_args_list == [call('poll result')]
    assert main_loop.supervisor_time == 1234
    assert not main_loop.sockets.publisher.forward_event.called
    assert not main_loop.sockets.disconnect_subscriber.called
    assert not mocked_send.called
    # reset mocks
    main_loop.sockets.check_puller.reset_mock()
    # test with deferred publication message
    for event in InternalEventHeaders:
        if event != InternalEventHeaders.TICK:
            main_loop.sockets.check_puller.return_value = event.value, 'a message'
            main_loop.check_requests('poll result')
            assert main_loop.sockets.check_puller.call_args_list == [call('poll result')]
            assert main_loop.supervisor_time == 1234
            assert main_loop.sockets.publisher.forward_event.call_args_list == [call((event.value, 'a message'))]
            assert not main_loop.sockets.disconnect_subscriber.called
            assert not mocked_send.called
            # reset mocks
            main_loop.sockets.check_puller.reset_mock()
            main_loop.sockets.publisher.forward_event.reset_mock()


def test_check_instance_no_com(mocker, mocked_rpc, main_loop):
    """ Test the SupvisorsMainLoop.check_instance with a remote Supervisor that does not respond. """
    mocker.patch('supvisors.mainloop.stderr')
    mocked_evt = mocker.patch.object(main_loop, 'send_remote_comm_event')
    mocked_rpc.reset_mock()
    # test rpc error: SHUTDOWN event is sent to local Supervisor
    mocked_rpc.side_effect = ValueError
    main_loop.check_instance('10.0.0.1')
    assert mocked_rpc.call_args_list == [call(main_loop.srv_url.env)]
    message = 'identifier=10.0.0.1 authorized=None master_identifier= supvisors_state=SHUTDOWN'
    assert mocked_evt.call_args_list == [call('auth', message)]


def test_check_instance_isolation(mocker, mocked_rpc, main_loop):
    """ Test the SupvisorsMainLoop.check_instance with a remote Supervisor that has isolated the local instance. """
    mocker.patch('supvisors.mainloop.stderr')
    mocked_evt = mocker.patch.object(main_loop, 'send_remote_comm_event')
    mocked_rpc.reset_mock()
    # test with a mocked rpc interface
    rpc_intf = DummyRpcInterface()
    mocked_local = mocker.patch.object(rpc_intf.supvisors, 'get_all_local_process_info')
    mocked_instance = mocker.patch.object(rpc_intf.supvisors, 'get_instance_info')
    mocker.patch.object(rpc_intf.supvisors, 'get_master_identifier', return_value='10.0.0.5')
    mocker.patch.object(rpc_intf.supvisors, 'get_supvisors_state',
                        return_value={'statecode': SupvisorsStates.OPERATION})
    mocked_rpc.return_value = rpc_intf
    # test with local Supvisors instance isolated by remote
    for state in [SupvisorsInstanceStates.ISOLATING, SupvisorsInstanceStates.ISOLATED]:
        mocked_instance.return_value = {'statecode': state}
        main_loop.check_instance('10.0.0.1:60000')
        assert mocked_rpc.call_args_list == [call(main_loop.srv_url.env)]
        expected = 'identifier=10.0.0.1:60000 authorized=False master_identifier=10.0.0.5 supvisors_state=OPERATION'
        assert mocked_evt.call_args_list == [call('auth', expected)]
        assert not mocked_local.called
        # reset counters
        mocked_evt.reset_mock()
        mocked_rpc.reset_mock()


def test_check_instance_info_exception(mocker, mocked_rpc, main_loop):
    """ Test the SupvisorsMainLoop.check_instance with a remote Supervisor that has not isolated the local instance
    but that is about to restart or shut down. """
    mocker.patch('supvisors.mainloop.stderr')
    mocked_evt = mocker.patch.object(main_loop, 'send_remote_comm_event')
    mocked_rpc.reset_mock()
    # test with a mocked rpc interface
    dummy_info = [{'name': 'proc', 'group': 'appli', 'state': 10, 'start': 5, 'now': 10, 'pid': 1234, 'spawnerr': ''}]
    rpc_intf = DummyRpcInterface()
    mocked_local = mocker.patch.object(rpc_intf.supvisors, 'get_all_local_process_info', side_effect=ValueError)
    mocked_instance = mocker.patch.object(rpc_intf.supvisors, 'get_instance_info')
    mocker.patch.object(rpc_intf.supvisors, 'get_master_identifier', return_value='10.0.0.5')
    mocker.patch.object(rpc_intf.supvisors, 'get_supvisors_state', return_value={'statecode': 20})
    mocked_rpc.return_value = rpc_intf
    # test with local Supvisors instance not isolated by remote
    # exception on get_all_local_process_info
    for state in [SupvisorsInstanceStates.UNKNOWN, SupvisorsInstanceStates.CHECKING, SupvisorsInstanceStates.RUNNING,
                  SupvisorsInstanceStates.SILENT]:
        for fsm_state in SupvisorsStates:
            rpc_intf.supvisors.get_supvisors_state.return_value = {'statecode': fsm_state.value}
            mocked_instance.return_value = {'statecode': state}
            main_loop.check_instance('10.0.0.1')
            assert mocked_rpc.call_args_list == [call(main_loop.srv_url.env)]
            expected = ('identifier=10.0.0.1 authorized=True master_identifier=10.0.0.5'
                        f' supvisors_state={fsm_state.name}')
            assert mocked_evt.call_args_list == [call('auth', expected)]
            assert mocked_local.called
            # reset counters
            mocked_evt.reset_mock()
            mocked_local.reset_mock()
            mocked_rpc.reset_mock()


def test_check_instance_normal(mocker, mocked_rpc, main_loop):
    """ Test the SupvisorsMainLoop.check_instance with a remote Supervisor that has not isolated the local instance
    and that provide process information. """
    mocker.patch('supvisors.mainloop.stderr')
    mocked_evt = mocker.patch.object(main_loop, 'send_remote_comm_event')
    mocked_rpc.reset_mock()
    # test with a mocked rpc interface
    dummy_info = [{'name': 'proc', 'group': 'appli', 'state': 10, 'start': 5, 'now': 10, 'pid': 1234, 'spawnerr': ''}]
    rpc_intf = DummyRpcInterface()
    mocked_local = mocker.patch.object(rpc_intf.supvisors, 'get_all_local_process_info', return_value=dummy_info)
    mocked_instance = mocker.patch.object(rpc_intf.supvisors, 'get_instance_info')
    mocker.patch.object(rpc_intf.supvisors, 'get_master_identifier', return_value='10.0.0.5')
    mocker.patch.object(rpc_intf.supvisors, 'get_supvisors_state', return_value={'statecode': 20})
    mocked_rpc.return_value = rpc_intf
    # test with local Supvisors instance not isolated by remote and with remote not in closing state
    for state in [SupvisorsInstanceStates.UNKNOWN, SupvisorsInstanceStates.CHECKING, SupvisorsInstanceStates.RUNNING,
                  SupvisorsInstanceStates.SILENT]:
        for fsm_state in [SupvisorsStates.INITIALIZATION, SupvisorsStates.DEPLOYMENT, SupvisorsStates.OPERATION,
                          SupvisorsStates.CONCILIATION]:
            rpc_intf.supvisors.get_supvisors_state.return_value = {'statecode': fsm_state.value}
            mocked_instance.return_value = {'statecode': state}
            main_loop.check_instance('10.0.0.1')
            assert mocked_rpc.call_args_list == [call(main_loop.srv_url.env)]
            expected = ('identifier=10.0.0.1 authorized=True master_identifier=10.0.0.5'
                        f' supvisors_state={fsm_state.name}')
            json_payload = ('["10.0.0.1", [{"name": "proc", "group": "appli", "state": 10, "start": 5, "now": 10,'
                            ' "pid": 1234, "spawnerr": ""}]]')
            assert mocked_evt.call_args_list == [call('auth', expected), call('info', json_payload)]
            assert mocked_local.called
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
    assert mocked_rpc.call_args == call(main_loop.srv_url.env)
    # test with a mocked rpc interface
    rpc_intf = DummyRpcInterface()
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
    rpc_intf = DummyRpcInterface()
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
    rpc_intf = DummyRpcInterface()
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
    rpc_intf = DummyRpcInterface()
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
    rpc_intf = DummyRpcInterface()
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
    rpc_intf = DummyRpcInterface()
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
    rpc_intf = DummyRpcInterface()
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
    main_loop.send_remote_comm_event('event type', 'event data')
    # test with a mocked rpc interface
    mocked_supervisor = mocker.patch.object(main_loop.proxy.supervisor, 'sendRemoteCommEvent')
    main_loop.send_remote_comm_event('event type', 'event data')
    assert mocked_supervisor.call_args_list == [call('event type', 'event data')]


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
