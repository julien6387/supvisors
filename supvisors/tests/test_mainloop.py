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

import time
from socket import gethostname, gethostbyname
from unittest.mock import call, patch, DEFAULT

import pytest

from supvisors.internal_com.internal_com import SupvisorsInternalEmitter
from supvisors.internal_com.mainloop import *
from supvisors.internal_com.mapper import SupvisorsInstanceId
from supvisors.ttypes import SupvisorsInstanceStates
from .base import DummyRpcInterface
from .conftest import wait_internal_publisher


@pytest.fixture
def mocked_rpc():
    """ Fixture for the instance to test. """
    rpc_patch = patch('supvisors.internal_com.mainloop.getRPCInterface')
    mocked_rpc = rpc_patch.start()
    yield mocked_rpc
    rpc_patch.stop()


@pytest.fixture
def proxy(supvisors):
    return SupervisorProxy(supvisors)


def test_proxy_creation(mocked_rpc, proxy, supvisors):
    """ Test the SupvisorsProxy creation. """
    assert proxy.supvisors is supvisors
    assert isinstance(proxy, threading.Thread)
    assert proxy.queue.empty()
    assert not proxy.event.is_set()
    assert proxy.srv_url.env == {'SUPERVISOR_SERVER_URL': f'http://{gethostname()}:65000',
                                 'SUPERVISOR_USERNAME': 'user',
                                 'SUPERVISOR_PASSWORD': 'p@$$w0rd'}
    assert mocked_rpc.call_args_list == [call(proxy.srv_url.env)]


def test_proxy_run(mocker, proxy):
    """ Test the SupvisorsProxy tread run / stop. """
    mocked_send = mocker.patch.object(proxy, 'send_remote_comm_event')
    mocked_exec = mocker.patch.object(proxy, 'execute')
    # start the thread
    proxy.start()
    time.sleep(1)
    assert proxy.is_alive()
    assert not proxy.event.is_set()
    # send a remote event
    message = ('10.0.0.1', 65100), (InternalEventHeaders.TICK.value, ('10.0.0.1', {'when': 1234}))
    proxy.push_event(message)
    time.sleep(1.0)
    assert mocked_send.call_args_list == [call(message)]
    assert not mocked_exec.called
    mocked_send.reset_mock()
    # send a discovery event
    message = ('10.0.0.2', 51243), (InternalEventHeaders.DISCOVERY.value, ('10.0.0.2', {'when': 4321}))
    proxy.push_event(message)
    time.sleep(1.0)
    assert mocked_send.call_args_list == [call(message)]
    assert not mocked_exec.called
    mocked_send.reset_mock()
    # send a request
    proxy.push_request(DeferredRequestHeaders.RESTART_ALL, '')
    time.sleep(1.0)
    assert not mocked_send.called
    assert mocked_exec.call_args_list == [call(DeferredRequestHeaders.RESTART_ALL, '')]
    mocked_send.reset_mock()
    # stop the thread
    proxy.stop()


def test_proxy_check_instance(mocker, mocked_rpc, proxy):
    """ Test the SupervisorProxy.check_instance method. """
    mocked_auth = mocker.patch.object(proxy, '_is_authorized', return_value=False)
    mocked_mode = mocker.patch.object(proxy, '_transfer_states_modes')
    mocked_info = mocker.patch.object(proxy, '_transfer_process_info')
    mocked_send = mocker.patch.object(proxy, 'send_remote_comm_event')
    # test with no authorization
    proxy.check_instance('10.0.0.1')
    assert mocked_auth.call_args_list == [call('10.0.0.1')]
    assert not mocked_mode.called
    assert not mocked_info.called
    expected = InternalEventHeaders.AUTHORIZATION.value, ('10.0.0.1', False)
    assert mocked_send.call_args_list == [call((('10.0.0.1', 65000), expected))]
    mocker.resetall()
    # test with authorization
    mocked_auth.return_value = True
    proxy.check_instance('10.0.0.1')
    assert mocked_auth.call_args_list == [call('10.0.0.1')]
    assert mocked_mode.call_args_list == [call('10.0.0.1')]
    assert mocked_info.call_args_list == [call('10.0.0.1')]
    expected = InternalEventHeaders.AUTHORIZATION.value, ('10.0.0.1', True)
    assert mocked_send.call_args_list == [call((('10.0.0.1', 65000), expected))]


def test_proxy_is_authorized(mocker, mocked_rpc, proxy):
    """ Test the SupervisorProxy._is_authorized method. """
    mocked_rpc.reset_mock()
    local_identifier = proxy.supvisors.context.local_identifier
    # test with XML-RPC failure
    mocked_rpc.side_effect = ValueError
    assert proxy._is_authorized('10.0.0.1') is None
    assert mocked_rpc.call_args_list == [call(proxy.srv_url.env)]
    mocked_rpc.reset_mock()
    # test with a mocked rpc interface
    rpc_intf = DummyRpcInterface(proxy.supvisors)
    mocked_call = mocker.patch.object(rpc_intf.supvisors, 'get_instance_info')
    mocked_rpc.return_value = rpc_intf
    mocked_rpc.side_effect = None
    # test with local Supvisors instance isolated by remote
    for state in ISOLATION_STATES:
        mocked_call.return_value = {'statecode': state.value}
        assert proxy._is_authorized('10.0.0.1') is False
        assert mocked_call.call_args_list == [call(local_identifier)]
        assert mocked_rpc.call_args_list == [call(proxy.srv_url.env)]
        # reset counters
        mocked_call.reset_mock()
        mocked_rpc.reset_mock()
    # test with local Supvisors instance not isolated by remote
    for state in [x for x in SupvisorsInstanceStates if x not in ISOLATION_STATES]:
        mocked_call.return_value = {'statecode': state.value}
        assert proxy._is_authorized('10.0.0.1') is True
        assert mocked_call.call_args_list == [call(local_identifier)]
        assert mocked_rpc.call_args_list == [call(proxy.srv_url.env)]
        # reset counters
        mocked_call.reset_mock()
        mocked_rpc.reset_mock()
    # test with local Supvisors instance not isolated by remote but returning an unknown state
    mocked_call.return_value = {'statecode': 128}
    assert proxy._is_authorized('10.0.0.1') is False
    assert mocked_call.call_args_list == [call(local_identifier)]
    assert mocked_rpc.call_args_list == [call(proxy.srv_url.env)]


def test_proxy_transfer_process_info(mocker, mocked_rpc, proxy):
    """ Test the SupervisorProxy._transfer_process_info method. """
    mocked_rpc.reset_mock()
    mocked_send = mocker.patch.object(proxy, 'send_remote_comm_event')
    # test with XML-RPC failure
    mocked_rpc.side_effect = ValueError
    proxy._transfer_process_info('10.0.0.1')
    assert mocked_rpc.call_args_list == [call(proxy.srv_url.env)]
    assert not mocked_send.called
    mocked_rpc.reset_mock()
    # test with a mocked rpc interface
    rpc_intf = DummyRpcInterface(proxy.supvisors)
    proc_info = [{'name': 'dummy_1'}, {'name': 'dummy_2'}]
    mocked_call = mocker.patch.object(rpc_intf.supvisors, 'get_all_local_process_info', return_value=proc_info)
    mocked_rpc.return_value = rpc_intf
    mocked_rpc.side_effect = None
    proxy._transfer_process_info('10.0.0.1')
    assert mocked_call.call_args_list == [call()]
    assert mocked_rpc.call_args_list == [call(proxy.srv_url.env)]
    expected = InternalEventHeaders.ALL_INFO.value, ('10.0.0.1', proc_info)
    assert mocked_send.call_args_list == [call((('10.0.0.1', 65000), expected))]


def test_proxy_transfer_states_modes(mocker, mocked_rpc, proxy):
    """ Test the SupervisorProxy._transfer_states_modes method. """
    mocked_rpc.reset_mock()
    mocked_send = mocker.patch.object(proxy, 'send_remote_comm_event')
    # test with XML-RPC failure
    mocked_rpc.side_effect = ValueError
    proxy._transfer_states_modes('10.0.0.1')
    assert mocked_rpc.call_args_list == [call(proxy.srv_url.env)]
    assert not mocked_send.called
    mocked_rpc.reset_mock()
    # test with a mocked rpc interface
    rpc_intf = DummyRpcInterface(proxy.supvisors)
    instance_info = {'identifier': 'supvisors', 'node_name': '10.0.0.1', 'port': 65000, 'loading': 0,
                     'statecode': 3, 'statename': 'RUNNING',
                     'remote_time': 50, 'local_time': 60,
                     'sequence_counter': 28, 'process_failure': False,
                     'fsm_statecode': 6, 'fsm_statename': 'SHUTTING_DOWN',
                     'discovery_mode': True,
                     'master_identifier': '10.0.0.1',
                     'starting_jobs': False, 'stopping_jobs': True}
    mocked_call = mocker.patch.object(rpc_intf.supvisors, 'get_instance_info', return_value=instance_info)
    mocked_rpc.return_value = rpc_intf
    mocked_rpc.side_effect = None
    proxy._transfer_states_modes('10.0.0.1')
    assert mocked_call.call_args_list == [call('10.0.0.1')]
    assert mocked_rpc.call_args_list == [call(proxy.srv_url.env)]
    expected = InternalEventHeaders.STATE.value, ('10.0.0.1', {'fsm_statecode': 6,
                                                               'discovery_mode': True,
                                                               'master_identifier': '10.0.0.1',
                                                               'starting_jobs': False, 'stopping_jobs': True})
    assert mocked_send.call_args_list == [call((('10.0.0.1', 65000), expected))]


def test_proxy_start_process(mocker, mocked_rpc, proxy):
    """ Test the SupervisorProxy function to start a process handled by a remote Supervisor. """
    # test rpc error
    mocked_rpc.side_effect = KeyError
    proxy.start_process('10.0.0.1', 'dummy_process', 'extra args')
    assert mocked_rpc.call_count == 2
    assert mocked_rpc.call_args == call(proxy.srv_url.env)
    # test with a mocked rpc interface
    rpc_intf = DummyRpcInterface(proxy.supvisors)
    mocked_rpc.side_effect = None
    mocked_rpc.return_value = rpc_intf
    mocked_supvisors = mocker.patch.object(rpc_intf.supvisors, 'start_args')
    proxy.start_process('10.0.0.1', 'dummy_process', 'extra args')
    assert mocked_rpc.call_count == 3
    assert mocked_rpc.call_args == call(proxy.srv_url.env)
    assert mocked_supvisors.call_count == 1
    assert mocked_supvisors.call_args == call('dummy_process', 'extra args', False)


def test_proxy_stop_process(mocker, mocked_rpc, proxy):
    """ Test the SupervisorProxy function to stop a process handled by a remote Supervisor. """
    # test rpc error
    mocked_rpc.side_effect = ConnectionResetError
    proxy.stop_process('10.0.0.1', 'dummy_process')
    assert mocked_rpc.call_count == 2
    assert mocked_rpc.call_args == call(proxy.srv_url.env)
    # test with a mocked rpc interface
    rpc_intf = DummyRpcInterface(proxy.supvisors)
    mocked_rpc.side_effect = None
    mocked_rpc.return_value = rpc_intf
    mocked_supervisor = mocker.patch.object(rpc_intf.supervisor, 'stopProcess')
    proxy.stop_process('10.0.0.1', 'dummy_process')
    assert mocked_rpc.call_count == 3
    assert mocked_rpc.call_args == call(proxy.srv_url.env)
    assert mocked_supervisor.call_count == 1
    assert mocked_supervisor.call_args == call('dummy_process', False)


def test_proxy_restart(mocker, mocked_rpc, proxy):
    """ Test the SupervisorProxy function to restart a remote Supervisor. """
    # test rpc error
    mocked_rpc.side_effect = OSError
    proxy.restart('10.0.0.1')
    assert mocked_rpc.call_count == 2
    assert mocked_rpc.call_args == call(proxy.srv_url.env)
    # test with a mocked rpc interface
    rpc_intf = DummyRpcInterface(proxy.supvisors)
    mocked_rpc.side_effect = None
    mocked_rpc.return_value = rpc_intf
    mocked_supervisor = mocker.patch.object(rpc_intf.supervisor, 'restart')
    proxy.restart('10.0.0.1')
    assert mocked_rpc.call_count == 3
    assert mocked_rpc.call_args == call(proxy.srv_url.env)
    assert mocked_supervisor.call_count == 1
    assert mocked_supervisor.call_args == call()


def test_proxy_shutdown(mocker, mocked_rpc, proxy):
    """ Test the SupervisorProxy function to shut down a remote Supervisor. """
    # test rpc error
    mocked_rpc.side_effect = RPCError(12)
    proxy.shutdown('10.0.0.1')
    assert mocked_rpc.call_count == 2
    assert mocked_rpc.call_args == call(proxy.srv_url.env)
    # test with a mocked rpc interface
    rpc_intf = DummyRpcInterface(proxy.supvisors)
    mocked_rpc.side_effect = None
    mocked_rpc.return_value = rpc_intf
    mocked_shutdown = mocker.patch.object(rpc_intf.supervisor, 'shutdown')
    proxy.shutdown('10.0.0.1')
    assert mocked_rpc.call_count == 3
    assert mocked_rpc.call_args == call(proxy.srv_url.env)
    assert mocked_shutdown.call_count == 1
    assert mocked_shutdown.call_args == call()


def test_proxy_restart_sequence(mocker, mocked_rpc, proxy):
    """ Test the SupervisorProxy function to trigger the start_sequence of Supvisors. """
    # test rpc error
    mocked_rpc.side_effect = OSError
    proxy.restart_sequence('10.0.0.1')
    assert mocked_rpc.call_count == 2
    assert mocked_rpc.call_args == call(proxy.srv_url.env)
    # test with a mocked rpc interface
    rpc_intf = DummyRpcInterface(proxy.supvisors)
    mocked_rpc.side_effect = None
    mocked_rpc.return_value = rpc_intf
    mocked_supervisor = mocker.patch.object(rpc_intf.supvisors, 'restart_sequence')
    proxy.restart_sequence('10.0.0.1')
    assert mocked_rpc.call_count == 3
    assert mocked_rpc.call_args == call(proxy.srv_url.env)
    assert mocked_supervisor.call_count == 1
    assert mocked_supervisor.call_args == call()


def test_proxy_restart_all(mocker, mocked_rpc, proxy):
    """ Test the SupervisorProxy function to restart Supvisors. """
    # test rpc error
    mocked_rpc.side_effect = OSError
    proxy.restart_all('10.0.0.1')
    assert mocked_rpc.call_count == 2
    assert mocked_rpc.call_args == call(proxy.srv_url.env)
    # test with a mocked rpc interface
    rpc_intf = DummyRpcInterface(proxy.supvisors)
    mocked_rpc.side_effect = None
    mocked_rpc.return_value = rpc_intf
    mocked_supervisor = mocker.patch.object(rpc_intf.supvisors, 'restart')
    proxy.restart_all('10.0.0.1')
    assert mocked_rpc.call_count == 3
    assert mocked_rpc.call_args == call(proxy.srv_url.env)
    assert mocked_supervisor.call_count == 1
    assert mocked_supervisor.call_args == call()


def test_proxy_shutdown_all(mocker, mocked_rpc, proxy):
    """ Test the SupervisorProxy function to shut down Supvisors. """
    # test rpc error
    mocked_rpc.side_effect = RPCError(12)
    proxy.shutdown_all('10.0.0.1')
    assert mocked_rpc.call_count == 2
    assert mocked_rpc.call_args == call(proxy.srv_url.env)
    # test with a mocked rpc interface
    rpc_intf = DummyRpcInterface(proxy.supvisors)
    mocked_rpc.side_effect = None
    mocked_rpc.return_value = rpc_intf
    mocked_shutdown = mocker.patch.object(rpc_intf.supvisors, 'shutdown')
    proxy.shutdown_all('10.0.0.1')
    assert mocked_rpc.call_count == 3
    assert mocked_rpc.call_args == call(proxy.srv_url.env)
    assert mocked_shutdown.call_count == 1
    assert mocked_shutdown.call_args == call()


def test_proxy_comm_event(mocker, mocked_rpc, proxy):
    """ Test the SupervisorProxy function to send a comm event to the local Supervisor. """
    # test rpc error
    mocker.patch.object(proxy.proxy.supervisor, 'sendRemoteCommEvent', side_effect=RPCError(100))
    proxy.send_remote_comm_event('event data')
    # test with a mocked rpc interface
    mocked_supervisor = mocker.patch.object(proxy.proxy.supervisor, 'sendRemoteCommEvent')
    proxy.send_remote_comm_event('event data')
    assert mocked_supervisor.call_args_list == [call('Supvisors', '"event data"')]


def check_call(proxy, mocked_loop, method_name, request, args):
    """ Perform a main loop request and check what has been called. """
    # send request
    proxy.execute(request, args)
    # test mocked main loop
    assert proxy.srv_url.env['SUPERVISOR_SERVER_URL'] == 'http://10.0.0.2:65000'
    for key, mocked in mocked_loop.items():
        if key == method_name:
            assert mocked.call_count == 1
            assert mocked.call_args == call(*args)
            mocked.reset_mock()
        else:
            assert not mocked.called


def test_proxy_execute(mocker, proxy):
    """ Test the SupervisorProxy function to execute a deferred Supervisor request. """
    # patch main loop subscriber
    mocked_proxy = mocker.patch.multiple(proxy, check_instance=DEFAULT,
                                         start_process=DEFAULT, stop_process=DEFAULT,
                                         restart=DEFAULT, shutdown=DEFAULT, restart_sequence=DEFAULT,
                                         restart_all=DEFAULT, shutdown_all=DEFAULT)
    # test check instance
    check_call(proxy, mocked_proxy, 'check_instance',
               DeferredRequestHeaders.CHECK_INSTANCE, ('10.0.0.2',))
    # test start process
    check_call(proxy, mocked_proxy, 'start_process',
               DeferredRequestHeaders.START_PROCESS, ('10.0.0.2', 'dummy_process', 'extra args'))
    # test stop process
    check_call(proxy, mocked_proxy, 'stop_process',
               DeferredRequestHeaders.STOP_PROCESS, ('10.0.0.2', 'dummy_process'))
    # test restart
    check_call(proxy, mocked_proxy, 'restart',
               DeferredRequestHeaders.RESTART, ('10.0.0.2',))
    # test restart
    check_call(proxy, mocked_proxy, 'shutdown',
               DeferredRequestHeaders.SHUTDOWN, ('10.0.0.2',))
    # test restart_sequence
    check_call(proxy, mocked_proxy, 'restart_sequence',
               DeferredRequestHeaders.RESTART_SEQUENCE, ('10.0.0.2',))
    # test restart_all
    check_call(proxy, mocked_proxy, 'restart_all',
               DeferredRequestHeaders.RESTART_ALL, ('10.0.0.2',))
    # test shutdown
    check_call(proxy, mocked_proxy, 'shutdown_all',
               DeferredRequestHeaders.SHUTDOWN_ALL, ('10.0.0.2',))


def wait_loop_connected(main_loop: SupvisorsMainLoop, max_time: int = 10) -> bool:
    """ Wait for publisher to be alive. """
    nb_tries = max_time
    while nb_tries > 0 and not (main_loop.is_alive() and len(main_loop.supvisors.internal_com.publisher.clients)):
        time.sleep(1.0)
        nb_tries -= 1
    return main_loop.is_alive() and len(main_loop.supvisors.internal_com.publisher.clients) == 1


@pytest.fixture
def main_loop(supvisors):
    """ Create the SupvisorsMainLoop instance to test. """
    # activate discovery mode
    supvisors.options.multicast_group = '239.0.0.1', 7777
    # WARN: local instance has been removed from the subscribers, but it's actually the only instance
    #       that can be tested here
    #       so add a Supvisors instance that has the same parameters as the local Supvisors instance,
    #       but with a different name
    mapper = supvisors.mapper
    local_instance_id: SupvisorsInstanceId = mapper.local_instance
    mapper._instances = {'10.0.0.1': mapper.instances['10.0.0.1'],
                         'async_test': local_instance_id,
                         mapper.local_identifier: local_instance_id}
    # WARN: a real SupvisorsInternalEmitter must have been created before
    supvisors.internal_com = SupvisorsInternalEmitter(supvisors)
    # wait for the publisher to be alive to avoid stop issues
    wait_internal_publisher(supvisors.internal_com.publisher)
    # create the main loop
    loop = SupvisorsMainLoop(supvisors)
    yield loop
    # close the SupvisorsInternalEmitter at the end of the test
    supvisors.internal_com.stop()


def test_mainloop_creation(supvisors, main_loop):
    """ Test the values set at construction. """
    assert isinstance(main_loop, threading.Thread)
    assert main_loop.supvisors is supvisors
    assert main_loop.receiver is None
    assert type(main_loop.proxy) is SupervisorProxy


def test_mainloop_stop(mocker, main_loop):
    """ Test the stopping of the main loop thread. """
    mocked_join = mocker.patch.object(main_loop, 'join')
    mocked_recv = mocker.patch.object(main_loop, 'receiver')
    # try to stop main loop before it is started
    main_loop.stop()
    assert not mocked_recv.stop.called
    assert not mocked_join.called
    # stop main loop when alive
    mocker.patch.object(main_loop, 'is_alive', return_value=True)
    main_loop.stop()
    assert mocked_recv.stop.called
    assert mocked_join.called


def test_mainloop_run(mocker, main_loop):
    """ Test the running of the main loop thread. """
    main_loop.supvisors.logger.info = print
    local_instance_id: SupvisorsInstanceId = main_loop.supvisors.mapper.local_instance
    local_identifier = local_instance_id.identifier
    local_ip = gethostbyname(gethostname())
    # disable the SupervisorProxy thread
    mocked_proxy_start = mocker.patch.object(main_loop.proxy, 'start')
    mocked_proxy_stop = mocker.patch.object(main_loop.proxy, 'stop')
    mocked_proxy_join = mocker.patch.object(main_loop.proxy, 'join')
    # add a Supvisors instance that has the same parameters as the local Supvisors instance, but with a different name
    main_loop.supvisors.mapper.instances['async_test'] = local_instance_id
    # WARN: handle_puller is blocking as long as there is no RequestPusher active,
    #       so make sure it has been started before starting the main loop
    assert main_loop.supvisors.internal_com.pusher is not None
    main_loop.start()
    try:
        assert wait_loop_connected(main_loop)
        assert mocked_proxy_start.called
        # inject basic messages to test the queues
        main_loop.supvisors.internal_com.pusher.send_isolate_instances(['10.0.0.1'])
        main_loop.supvisors.internal_com.pusher.send_connect_instance('10.0.0.1')
        main_loop.supvisors.internal_com.pusher.send_check_instance('10.0.0.3')
        main_loop.supvisors.internal_com.publisher.send_tick_event({'when': 1234})
        main_loop.supvisors.internal_com.mc_sender.send_discovery_event({'when': 4321})
        # check results
        got_request, got_remote, got_discovery = False, False, False
        for _ in range(3):
            # first message may be long to come
            msg_type, message = main_loop.proxy.queue.get(timeout=5.0)
            if msg_type == DeferredRequestHeaders.CHECK_INSTANCE:
                assert message == ['10.0.0.3']
                got_request = True
            else:
                event_origin, (event_type, (event_identifier, event_data)) = message
                if event_type == InternalEventHeaders.TICK.value:
                    # local IP address is mocked
                    assert event_origin[0] == local_ip
                    assert event_origin[1] == 65100
                    assert event_identifier == local_identifier
                    assert event_data == {'when': 1234}
                    got_remote = True
                elif event_type == InternalEventHeaders.DISCOVERY.value:
                    assert event_origin[0] == local_ip
                    # port is variable
                    assert event_identifier == local_identifier
                    assert event_data == {'when': 4321}
                    got_discovery = True
        assert got_request and got_remote and got_discovery
    finally:
        # close the main loop
        main_loop.stop()
        assert mocked_proxy_stop.called
        assert mocked_proxy_join.called
