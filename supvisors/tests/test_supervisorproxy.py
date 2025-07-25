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

import http.client
import socket
from unittest.mock import call, patch, Mock, DEFAULT

import pytest
from supervisor.xmlrpc import Faults

from supvisors.internal_com.supervisorproxy import *
from supvisors.rpcinterface import SupvisorsFaults
from supvisors.ttypes import (SupvisorsInstanceStates, ConciliationStrategies, StartingStrategies,
                              SupvisorsFailureStrategies)


def test_internal_event_headers():
    """ Test the InternalEventHeaders enumeration. """
    expected = ['REQUEST', 'PUBLICATION', 'NOTIFICATION']
    assert [x.name for x in InternalEventHeaders] == expected


@pytest.fixture
def mocked_rpc():
    """ Fixture for the instance to test. """
    rpc_patch = patch('supvisors.internal_com.supervisorproxy.getRPCInterface')
    mocked_rpc = rpc_patch.start()
    yield mocked_rpc
    rpc_patch.stop()


@pytest.fixture
def proxy(supvisors_instance, mocked_rpc):
    status = supvisors_instance.context.instances['10.0.0.2:25000']
    return SupervisorProxy(status, supvisors_instance)


@pytest.fixture
def proxy_thread(supvisors_instance, mocked_rpc):
    status = supvisors_instance.context.instances['10.0.0.2:25000']
    return SupervisorProxyThread(status, supvisors_instance)


@pytest.fixture
def proxy_server(supvisors_instance, mocked_rpc):
    server = supvisors_instance.rpc_handler.proxy_server
    yield server
    server.stop()


def test_proxy_creation(mocked_rpc, proxy, supvisors_instance):
    """ Test the SupvisorsProxy creation. """
    assert proxy.supvisors is supvisors_instance
    assert proxy.status is supvisors_instance.context.instances['10.0.0.2:25000']
    assert proxy._proxy is None
    assert 0.0 < proxy.last_used < time.monotonic()
    assert proxy.logger is supvisors_instance.logger
    assert proxy.local_identifier == supvisors_instance.mapper.local_identifier



def test_proxy_proxy(mocked_rpc, supvisors_instance, proxy):
    """ Test the SupvisorsProxy proxy property. """
    # test with non-local proxy
    assert proxy._proxy is None
    assert proxy.status.supvisors_id.identifier != proxy.local_identifier
    assert proxy.proxy is not None
    assert mocked_rpc.call_args_list == [call({'SUPERVISOR_SERVER_URL': 'http://10.0.0.2:25000',
                                               'SUPERVISOR_USERNAME': 'user',
                                               'SUPERVISOR_PASSWORD': 'p@$$w0rd'})]
    ref_proxy = proxy._proxy
    ref_usage = proxy.last_used
    mocked_rpc.reset_mock()
    # retry
    assert proxy.proxy is ref_proxy
    assert ref_usage == proxy.last_used
    # test with local proxy and recent usage
    proxy.status = supvisors_instance.context.local_status
    assert proxy.status.supvisors_id.identifier == proxy.local_identifier
    assert proxy.proxy is ref_proxy
    assert proxy.last_used == ref_usage
    # test with local proxy and old usage (cannot test everything due to patch)
    proxy.last_used = time.monotonic() - LOCAL_PROXY_DURATION - 1
    assert proxy.proxy
    assert proxy.last_used > ref_usage


def test_get_origin(supvisors_instance, proxy):
    """ Test the SupervisorProxy._get_origin method. """
    local_instance = supvisors_instance.mapper.local_instance
    assert proxy._get_origin(proxy.local_identifier) == local_instance.source
    assert proxy._get_origin('10.0.0.1:25000') == ('10.0.0.1:25000', '10.0.0.1', ('10.0.0.1', 25000))


def test_proxy_xml_rpc(proxy):
    """ Test the SupervisorProxy function to send any XML-RPC to a Supervisor instance. """
    ref_usage = proxy.last_used
    mocked_fct = Mock()
    # test no error
    proxy.xml_rpc('normal', mocked_fct, ())
    assert mocked_fct.call_args_list == [call()]
    assert proxy.last_used > ref_usage
    ref_usage = proxy.last_used
    mocked_fct.reset_mock()
    proxy.xml_rpc('normal', mocked_fct, ('hello',))
    assert mocked_fct.call_args_list == [call('hello')]
    assert proxy.last_used > ref_usage
    ref_usage = proxy.last_used
    mocked_fct.reset_mock()
    proxy.xml_rpc('normal', mocked_fct, ('hello', 28))
    assert mocked_fct.call_args_list == [call('hello', 28)]
    assert proxy.last_used > ref_usage
    ref_usage = proxy.last_used
    mocked_fct.reset_mock()
    # test minor exception (remote Supvisors instance is operational)
    for exc_class in [RPCError(code=58), xmlrpclib.Fault(77, 'fault')]:
        mocked_fct.side_effect = exc_class
        proxy.xml_rpc('normal', mocked_fct, ('hello', 28))
        assert mocked_fct.call_args_list == [call('hello', 28)]
        assert proxy.last_used > ref_usage
        ref_usage = proxy.last_used
        mocked_fct.reset_mock()
    # test major exception (remote Supvisors instance is NOT operational)
    for exc_class in [OSError, HTTPException, KeyError, ValueError, TypeError]:
        mocked_fct.side_effect = exc_class
        with pytest.raises(SupervisorProxyException):
            proxy.xml_rpc('normal', mocked_fct, ('hello',))
        assert mocked_fct.call_args_list == [call('hello')]
        assert proxy.last_used > ref_usage
        ref_usage = proxy.last_used
        mocked_fct.reset_mock()


def test_proxy_comm_event(mocker, proxy):
    """ Test the SupervisorProxy function to send a remote communication event to a Supervisor instance. """
    mocked_call = mocker.patch.object(proxy, 'xml_rpc')
    # test with a mocked rpc interface
    proxy.send_remote_comm_event('supvisors', 'event data')
    assert mocked_call.call_args_list == [call('supervisor.sendRemoteCommEvent',
                                               proxy.proxy.supervisor.sendRemoteCommEvent,
                                               ('supvisors', '"event data"'))]


def test_publish(mocker, supvisors_instance, proxy):
    """ Test the SupervisorProxy.publish method. """
    mocked_call = mocker.patch.object(proxy, 'xml_rpc')
    # update node states
    instance_status = supvisors_instance.context.instances['10.0.0.2:25000']
    # test incorrect publication type
    proxy.publish('10.0.0.3:25000', (28, {'message': 'hello'}))
    assert not mocked_call.called
    # test TICK publication
    for state in SupvisorsInstanceStates:
        # actually, publish is not called with ISOLATED state, but it is dealt before
        proxy.publish('10.0.0.2:25000', (PublicationHeaders.TICK.value, {'message': 'TICK'}))
        instance_status._state = state
        expected_json = '[["10.0.0.2:25000", "10.0.0.2", ["10.0.0.2", 25000]], [0, {"message": "TICK"}]]'
        assert mocked_call.call_args_list == [call('supervisor.sendRemoteCommEvent',
                                                   proxy.proxy.supervisor.sendRemoteCommEvent,
                                                   (SUPVISORS_PUBLICATION, expected_json))]
        mocker.resetall()
    # test non-TICK publication with non-active state
    for state in [SupvisorsInstanceStates.STOPPED, SupvisorsInstanceStates.ISOLATED]:
        instance_status._state = state
        proxy.publish('10.0.0.2:25000', (PublicationHeaders.STATE.value, {'message': 'hello'}))
        assert not mocked_call.called
    # test non-TICK publication with active state
    for state in [SupvisorsInstanceStates.CHECKING, SupvisorsInstanceStates.CHECKED,
                  SupvisorsInstanceStates.RUNNING, SupvisorsInstanceStates.FAILED]:
        instance_status._state = state
        proxy.publish('10.0.0.2:25000', (PublicationHeaders.STATE.value, {'message': 'STATE'}))
        expected_json = '[["10.0.0.2:25000", "10.0.0.2", ["10.0.0.2", 25000]], [7, {"message": "STATE"}]]'
        assert mocked_call.call_args_list == [call('supervisor.sendRemoteCommEvent',
                                                   proxy.proxy.supervisor.sendRemoteCommEvent,
                                                   (SUPVISORS_PUBLICATION, expected_json))]
        mocker.resetall()


def test_proxy_check_instance(mocker, proxy_server, mocked_rpc, proxy):
    """ Test the SupervisorProxy.check_instance method. """
    mocker.patch('time.monotonic', return_value=1234.56)
    mocked_auth = mocker.patch.object(proxy, '_is_authorized', return_value=AuthorizationTypes.NOT_AUTHORIZED)
    mocked_netw = mocker.patch.object(proxy, '_transfer_network_info')
    mocked_mode = mocker.patch.object(proxy, '_transfer_states_modes')
    mocked_info = mocker.patch.object(proxy, '_transfer_process_info')
    mocked_send = mocker.patch.object(proxy_server, 'push_notification')
    # test with no authorization
    proxy.check_instance()
    assert mocked_netw.call_args_list == [call(1234.56)]
    assert mocked_auth.call_args_list == [call()]
    assert not mocked_mode.called
    assert not mocked_info.called
    expected = NotificationHeaders.AUTHORIZATION.value, {'authorization': AuthorizationTypes.NOT_AUTHORIZED.value,
                                                         'now_monotonic': 1234.56}
    assert mocked_send.call_args_list == [call((('10.0.0.2:25000', '10.0.0.2', ('10.0.0.2', 25000)), expected))]
    mocked_netw.reset_mock()
    mocked_send.reset_mock()
    mocker.resetall()
    # test with authorization
    mocked_auth.return_value = AuthorizationTypes.AUTHORIZED
    proxy.check_instance()
    assert mocked_netw.call_args_list == [call(1234.56)]
    assert mocked_auth.call_args_list == [call()]
    assert mocked_mode.call_args_list == [call()]
    assert mocked_info.call_args_list == [call()]
    expected = NotificationHeaders.AUTHORIZATION.value, {'authorization': AuthorizationTypes.AUTHORIZED.value,
                                                         'now_monotonic': 1234.56}
    assert mocked_send.call_args_list == [call((('10.0.0.2:25000', '10.0.0.2', ('10.0.0.2', 25000)), expected))]


def test_proxy_is_authorized(mocked_rpc, supvisors_instance, proxy):
    """ Test the SupervisorProxy._is_authorized method. """
    info_rpc = proxy.proxy.supvisors.get_instance_info
    strategy_rpc = proxy.proxy.supvisors.get_strategies
    # test with transport failure
    info_rpc.side_effect = OSError
    with pytest.raises(SupervisorProxyException):
        proxy._is_authorized()
    assert info_rpc.call_args_list == [call(proxy.local_identifier)]
    info_rpc.reset_mock()
    # test with XML-RPC application failure
    info_rpc.side_effect = RPCError(Faults.NOT_EXECUTABLE)
    assert proxy._is_authorized() == AuthorizationTypes.UNKNOWN
    assert info_rpc.call_args_list == [call(proxy.local_identifier)]
    info_rpc.reset_mock()
    # test with a mocked rpc interface
    info_rpc.side_effect = None
    # test with local Supvisors instance isolated by remote
    info_rpc.return_value = [{'statecode': SupvisorsInstanceStates.ISOLATED.value}]
    assert proxy._is_authorized() == AuthorizationTypes.NOT_AUTHORIZED
    assert info_rpc.call_args_list == [call(proxy.local_identifier)]
    info_rpc.reset_mock()
    # test with local Supvisors instance not isolated by remote
    # test inconsistency
    strategy_rpc.return_value = {'auto-fencing': False,
                                 'starting': StartingStrategies.MOST_LOADED.name,
                                 'conciliation': ConciliationStrategies.SENICIDE.name,
                                 'supvisors_failure': SupvisorsFailureStrategies.RESYNC.name}
    for state in [x for x in SupvisorsInstanceStates if x != SupvisorsInstanceStates.ISOLATED]:
        info_rpc.return_value = [{'statecode': state.value}]
        assert proxy._is_authorized() == AuthorizationTypes.INCONSISTENT
        assert info_rpc.call_args_list == [call(proxy.local_identifier)]
        info_rpc.reset_mock()
    # test consistency
    strategy_rpc.return_value = {'auto-fencing': True,
                                 'starting': 'CONFIG',
                                 'conciliation': 'USER',
                                 'supvisors_failure': 'CONTINUE'}
    for state in [x for x in SupvisorsInstanceStates if x != SupvisorsInstanceStates.ISOLATED]:
        info_rpc.return_value = [{'statecode': state.value}]
        assert proxy._is_authorized() == AuthorizationTypes.AUTHORIZED
        assert info_rpc.call_args_list == [call(proxy.local_identifier)]
        info_rpc.reset_mock()
    # test with local Supvisors instance not isolated by remote but returning an unknown state
    info_rpc.return_value = [{'statecode': 128}]
    assert proxy._is_authorized() == AuthorizationTypes.NOT_AUTHORIZED
    assert info_rpc.call_args_list == [call(proxy.local_identifier)]


def test_proxy_transfer_network_info(mocker, proxy_server, mocked_rpc, proxy):
    """ Test the SupervisorProxy._transfer_network_info method. """
    info_rpc = proxy.proxy.supvisors.get_network_info
    mocked_send = mocker.patch.object(proxy_server, 'push_notification')
    # test with transport failure
    info_rpc.side_effect = HTTPException
    with pytest.raises(SupervisorProxyException):
        proxy._transfer_network_info(1234.56)
    assert info_rpc.call_args_list == [call('10.0.0.2:25000')]
    assert not mocked_send.called
    info_rpc.reset_mock()
    # test with XML-RPC application failure
    info_rpc.side_effect = RPCError(Faults.ABNORMAL_TERMINATION)
    proxy._transfer_network_info(1234.56)
    assert info_rpc.call_args_list == [call('10.0.0.2:25000')]
    expected = NotificationHeaders.IDENTIFICATION.value, None
    assert mocked_send.call_args_list == [call((('10.0.0.2:25000', '10.0.0.2', ('10.0.0.2', 25000)), expected))]
    info_rpc.reset_mock()
    mocked_send.reset_mock()
    # test with a mocked rpc interface
    netw_info = {'identifier': '10.0.0.1:25000',
                'nick_identifier': '10.0.0.1',
                'host_id': '10.0.0.1',
                'http_port': 25000,
                 'now_monotonic': 1234.56}
    info_rpc.side_effect = None
    info_rpc.return_value = netw_info
    proxy._transfer_network_info(1234.56)
    assert info_rpc.call_args_list == [call('10.0.0.2:25000')]
    expected = NotificationHeaders.IDENTIFICATION.value, netw_info
    assert mocked_send.call_args_list == [call((('10.0.0.2:25000', '10.0.0.2', ('10.0.0.2', 25000)), expected))]


def test_proxy_transfer_process_info(mocker, proxy_server, mocked_rpc, proxy):
    """ Test the SupervisorProxy._transfer_process_info method. """
    info_rpc = proxy.proxy.supvisors.get_all_local_process_info
    mocked_send = mocker.patch.object(proxy_server, 'push_notification')
    # test with transport failure
    info_rpc.side_effect = HTTPException
    with pytest.raises(SupervisorProxyException):
        proxy._transfer_process_info()
    assert info_rpc.call_args_list == [call()]
    assert not mocked_send.called
    info_rpc.reset_mock()
    # test with XML-RPC application failure
    info_rpc.side_effect = RPCError(Faults.ABNORMAL_TERMINATION)
    proxy._transfer_process_info()
    assert info_rpc.call_args_list == [call()]
    expected = NotificationHeaders.ALL_INFO.value, None
    assert mocked_send.call_args_list == [call((('10.0.0.2:25000', '10.0.0.2', ('10.0.0.2', 25000)), expected))]
    info_rpc.reset_mock()
    mocked_send.reset_mock()
    # test with a mocked rpc interface
    all_info = [{'name': 'dummy_1'}, {'name': 'dummy_2'}]
    info_rpc.side_effect = None
    info_rpc.return_value = all_info
    proxy._transfer_process_info()
    assert info_rpc.call_args_list == [call()]
    expected = NotificationHeaders.ALL_INFO.value, all_info
    assert mocked_send.call_args_list == [call((('10.0.0.2:25000', '10.0.0.2', ('10.0.0.2', 25000)), expected))]


def test_proxy_transfer_states_modes(mocker, proxy_server, mocked_rpc, proxy):
    """ Test the SupervisorProxy._transfer_states_modes method. """
    sm_rpc = proxy.proxy.supvisors.get_instance_state_modes
    mocked_send = mocker.patch.object(proxy_server, 'push_notification')
    # test with transport failure
    sm_rpc.side_effect = xmlrpclib.Fault
    with pytest.raises(SupervisorProxyException):
        proxy._transfer_states_modes()
    assert sm_rpc.call_args_list == [call('10.0.0.2:25000')]
    assert not mocked_send.called
    mocked_rpc.reset_mock()
    # test with XML-RPC application failure
    sm_rpc.side_effect = RPCError(Faults.NO_FILE, 'a file')
    proxy._transfer_states_modes()
    assert sm_rpc.call_args_list == [call('10.0.0.2:25000')]
    assert not mocked_send.called
    sm_rpc.reset_mock()
    # test with a mocked rpc interface
    instance_info = {'fsm_statecode': 6, 'fsm_statename': 'SHUTTING_DOWN',
                     'degraded_mode': True, 'discovery_mode': True,
                     'master_identifier': '10.0.0.2',
                     'starting_jobs': False, 'stopping_jobs': True,
                     'instance_states': {}}
    sm_rpc.side_effect = None
    sm_rpc.return_value = [instance_info]
    proxy._transfer_states_modes()
    assert sm_rpc.call_args_list == [call('10.0.0.2:25000')]
    expected = NotificationHeaders.STATE.value, instance_info
    assert mocked_send.call_args_list == [call((('10.0.0.2:25000', '10.0.0.2', ('10.0.0.2', 25000)), expected))]


def test_proxy_start_process(mocked_rpc, proxy):
    """ Test the SupervisorProxy function to start a process handled by a remote Supervisor. """
    start_rpc = proxy.proxy.supvisors.start_args
    # test with JSON failure
    start_rpc.side_effect = KeyError
    with pytest.raises(SupervisorProxyException):
        proxy.start_process('dummy_process', 'extra args')
    assert start_rpc.call_args_list == [call('dummy_process', 'extra args', False)]
    start_rpc.reset_mock()
    # test with XML-RPC application failure
    start_rpc.side_effect = RPCError(Faults.ALREADY_STARTED)
    proxy.start_process('dummy_process', 'extra args')
    assert start_rpc.call_args_list == [call('dummy_process', 'extra args', False)]
    start_rpc.reset_mock()
    # test with a mocked rpc interface
    start_rpc.side_effect = None
    proxy.start_process('dummy_process', 'extra args')
    assert start_rpc.call_args_list == [call('dummy_process', 'extra args', False)]


def test_proxy_stop_process(mocked_rpc, proxy):
    """ Test the SupervisorProxy function to stop a process handled by a remote Supervisor. """
    stop_rpc = proxy.proxy.supervisor.stopProcess
    # test with transport failure
    stop_rpc.side_effect = ConnectionResetError
    with pytest.raises(SupervisorProxyException):
        proxy.stop_process('dummy_process')
    assert stop_rpc.call_args_list == [call('dummy_process', False)]
    stop_rpc.reset_mock()
    # test with XML-RPC application failure
    stop_rpc.side_effect = RPCError(Faults.NOT_RUNNING)
    proxy.stop_process('dummy_process')
    assert stop_rpc.call_args_list == [call('dummy_process', False)]
    stop_rpc.reset_mock()
    # test with a mocked rpc interface
    stop_rpc.side_effect = None
    proxy.stop_process('dummy_process')
    assert stop_rpc.call_args_list == [call('dummy_process', False)]


def test_proxy_restart(mocked_rpc, proxy):
    """ Test the SupervisorProxy function to restart a remote Supervisor. """
    restart_rpc = proxy.proxy.supervisor.restart
    # test with JSON failure
    restart_rpc.side_effect = TypeError
    with pytest.raises(SupervisorProxyException):
        proxy.restart()
    assert restart_rpc.call_args_list == [call()]
    restart_rpc.reset_mock()
    # test with XML-RPC application failure
    restart_rpc.side_effect = RPCError(Faults.SHUTDOWN_STATE)
    proxy.restart()
    assert restart_rpc.call_args_list == [call()]
    restart_rpc.reset_mock()
    # test with a mocked rpc interface
    restart_rpc.side_effect = None
    proxy.restart()
    assert restart_rpc.call_args_list == [call()]


def test_proxy_shutdown(mocked_rpc, proxy):
    """ Test the SupervisorProxy function to shut down a remote Supervisor. """
    shutdown_rpc = proxy.proxy.supervisor.shutdown
    # test with JSON failure
    shutdown_rpc.side_effect = socket.gaierror
    with pytest.raises(SupervisorProxyException):
        proxy.shutdown()
    assert shutdown_rpc.call_args_list == [call()]
    shutdown_rpc.reset_mock()
    # test with XML-RPC application failure
    shutdown_rpc.side_effect = RPCError(SupvisorsFaults.BAD_SUPVISORS_STATE)
    proxy.shutdown()
    assert shutdown_rpc.call_args_list == [call()]
    shutdown_rpc.reset_mock()
    # test with a mocked rpc interface
    shutdown_rpc.side_effect = None
    proxy.shutdown()
    assert shutdown_rpc.call_args_list == [call()]


def test_proxy_restart_all(mocked_rpc, proxy):
    """ Test the SupervisorProxy function to restart Supvisors. """
    restart_rpc = proxy.proxy.supvisors.restart
    # test with transport failure
    restart_rpc.side_effect = http.client.CannotSendHeader
    with pytest.raises(SupervisorProxyException):
        proxy.restart_all()
    assert restart_rpc.call_args_list == [call()]
    restart_rpc.reset_mock()
    # test with XML-RPC application failure
    restart_rpc.side_effect = RPCError(Faults.FAILED)
    proxy.restart_all()
    assert restart_rpc.call_args_list == [call()]
    restart_rpc.reset_mock()
    # test with a mocked rpc interface
    restart_rpc.side_effect = None
    proxy.restart_all()
    assert restart_rpc.call_args_list == [call()]


def test_proxy_shutdown_all(mocked_rpc, proxy):
    """ Test the SupervisorProxy function to shut down Supvisors. """
    shutdown_rpc = proxy.proxy.supvisors.shutdown
    # test with transport failure
    shutdown_rpc.side_effect = ConnectionRefusedError
    with pytest.raises(SupervisorProxyException):
        proxy.shutdown_all()
    assert shutdown_rpc.call_args_list == [call()]
    shutdown_rpc.reset_mock()
    # test with XML-RPC application failure
    shutdown_rpc.side_effect = RPCError(Faults.UNKNOWN_METHOD)
    proxy.shutdown_all()
    assert shutdown_rpc.call_args_list == [call()]
    shutdown_rpc.reset_mock()
    # test with a mocked rpc interface
    shutdown_rpc.side_effect = None
    proxy.shutdown_all()
    assert shutdown_rpc.call_args_list == [call()]


def check_call(proxy, mocked_loop, method_name, request, args):
    """ Perform a main loop request and check what has been called. """
    # send request
    proxy.execute((request.value, args))
    # test mocked main loop
    for key, mocked in mocked_loop.items():
        if key == method_name:
            assert mocked.call_count == 1
            assert mocked.call_args == call(*args) if args else call()
            mocked.reset_mock()
        else:
            assert not mocked.called


def test_proxy_execute(mocker, proxy):
    """ Test the SupervisorProxy function to execute a deferred Supervisor request. """
    # patch main loop subscriber
    mocked_proxy = mocker.patch.multiple(proxy, check_instance=DEFAULT,
                                         start_process=DEFAULT, stop_process=DEFAULT,
                                         restart=DEFAULT, shutdown=DEFAULT,
                                         restart_all=DEFAULT, shutdown_all=DEFAULT)
    # test incorrect request type
    proxy.execute((28, 'error'))
    for mocked in mocked_proxy.values():
        assert not mocked.called
    # test check instance
    check_call(proxy, mocked_proxy, 'check_instance', RequestHeaders.CHECK_INSTANCE, None)
    # test start process
    check_call(proxy, mocked_proxy, 'start_process', RequestHeaders.START_PROCESS, ('dummy_process', 'extra args'))
    # test stop process
    check_call(proxy, mocked_proxy, 'stop_process', RequestHeaders.STOP_PROCESS, ('dummy_process',))
    # test restart
    check_call(proxy, mocked_proxy, 'restart', RequestHeaders.RESTART, None)
    # test shutdown
    check_call(proxy, mocked_proxy, 'shutdown', RequestHeaders.SHUTDOWN, None)
    # test restart_all
    check_call(proxy, mocked_proxy, 'restart_all', RequestHeaders.RESTART_ALL, None)
    # test shutdown
    check_call(proxy, mocked_proxy, 'shutdown_all', RequestHeaders.SHUTDOWN_ALL, None)


def test_proxy_thread_creation(mocked_rpc, proxy_thread, supvisors_instance):
    """ Test the SupervisorProxyThread creation. """
    assert isinstance(proxy_thread, threading.Thread)
    assert isinstance(proxy_thread, SupervisorProxy)
    assert proxy_thread.supvisors is supvisors_instance
    assert proxy_thread.logger is supvisors_instance.logger
    assert proxy_thread.queue.empty()
    assert not proxy_thread.live_event.is_set()
    assert not proxy_thread.stop_event.is_set()


def test_proxy_run(mocker, proxy_server, proxy_thread):
    """ Test the SupvisorsProxy thread run / stop. """
    mocked_close = mocker.patch.object(proxy_server, 'on_proxy_closing')
    # start the thread
    proxy_thread.start()
    assert not proxy_thread.stop_event.is_set()
    proxy_thread.live_event.wait()
    assert proxy_thread.is_alive()
    # send a publication event to hit process_event
    message = '10.0.0.2:25000', (PublicationHeaders.TICK.value, {'when': 1234})
    proxy_thread.push_message((InternalEventHeaders.PUBLICATION, message))
    # wait more than 1 second to hit queue.Empty
    time.sleep(2.0)
    # wait more than 1 second to hit queue.Empty
    assert not mocked_close.called
    # stop the thread
    proxy_thread.stop()
    proxy_thread.join()
    assert not proxy_thread.is_alive()
    assert mocked_close.call_args_list == [call('10.0.0.2:25000')]


def test_proxy_handle_exception(mocker, supvisors_instance, proxy_thread):
    """ Test the SupvisorsProxy thread run / stop with an exception on the local proxy. """
    mocked_push = mocker.patch.object(supvisors_instance.rpc_handler.proxy_server, 'push_notification')
    # test with non-local and non-active state
    supvisors_instance.context.instances['10.0.0.2:25000']._state = SupvisorsInstanceStates.STOPPED
    proxy_thread.handle_exception()
    assert not mocked_push.called
    # test with non-local and active state
    supvisors_instance.context.instances['10.0.0.2:25000']._state = SupvisorsInstanceStates.RUNNING
    proxy_thread.handle_exception()
    assert mocked_push.call_args_list == [call((('10.0.0.2:25000', '10.0.0.2', ('10.0.0.2', 25000)),
                                                (NotificationHeaders.INSTANCE_FAILURE.value, None)))]
    mocked_push.reset_mock()
    # test with local
    supvisors_instance.mapper.local_identifier = proxy_thread.status.identifier
    proxy_thread.handle_exception()
    assert not mocked_push.called


def test_proxy_process_event(mocker, proxy_thread):
    """ Test the SupvisorsProxy thread run / stop. """
    mocked_exec = mocker.patch.object(proxy_thread, 'execute')
    mocked_publish = mocker.patch.object(proxy_thread, 'publish')
    mocked_send = mocker.patch.object(proxy_thread, 'send_remote_comm_event')
    mocked_handle = mocker.patch.object(proxy_thread, 'handle_exception')
    # send a publication event
    message = '10.0.0.2', (PublicationHeaders.TICK.value, {'when': 1234})
    proxy_thread.process_event((InternalEventHeaders.PUBLICATION, message))
    assert mocked_publish.call_args_list == [call(*message)]
    assert not mocked_exec.called
    assert not mocked_send.called
    assert not mocked_handle.called
    mocked_publish.reset_mock()
    # send a discovery event
    message = (('identifier', ('10.0.0.2', 51243)), (InternalEventHeaders.NOTIFICATION.value, {'when': 4321}))
    proxy_thread.process_event((InternalEventHeaders.NOTIFICATION, message))
    assert mocked_send.call_args_list == [call(SUPVISORS_NOTIFICATION, message)]
    assert not mocked_publish.called
    assert not mocked_exec.called
    assert not mocked_handle.called
    mocked_send.reset_mock()
    # send a request
    proxy_thread.process_event((InternalEventHeaders.REQUEST, ('10.0.0.2', (RequestHeaders.RESTART_ALL, ''))))
    assert mocked_exec.call_args_list == [call((RequestHeaders.RESTART_ALL, ''))]
    assert not mocked_publish.called
    assert not mocked_send.called
    assert not mocked_handle.called
    mocked_exec.reset_mock()
    # test exception
    mocked_exec.side_effect = SupervisorProxyException
    proxy_thread.process_event((InternalEventHeaders.REQUEST, ('10.0.0.2', (RequestHeaders.RESTART_ALL, ''))))
    assert mocked_exec.call_args_list == [call((RequestHeaders.RESTART_ALL, ''))]
    assert not mocked_publish.called
    assert not mocked_send.called
    assert mocked_handle.call_args_list == [call()]


def test_proxy_server_creation(supvisors_instance, proxy_server):
    """ Test the SupervisorProxyServer creation. """
    assert proxy_server.supvisors is supvisors_instance
    assert proxy_server.proxies == {}
    assert not proxy_server.stop_event.is_set()
    assert proxy_server.local_identifier == supvisors_instance.mapper.local_identifier


def test_proxy_server_get_proxy(mocker, supvisors_instance, proxy_server):
    """ Test the SupervisorProxyServer get_proxy method. """
    assert proxy_server.proxies == {}
    # get a proxy from a non-isolated instance (instance not stored)
    supvisors_instance.context.instances['10.0.0.1:25000']._state = SupvisorsInstanceStates.RUNNING
    proxy_1 = proxy_server.get_proxy('10.0.0.1:25000')
    proxy_1.live_event.wait()
    assert proxy_1 is not None
    assert proxy_1.is_alive()
    assert proxy_1.status.identifier == '10.0.0.1:25000'
    assert proxy_server.proxies == {'10.0.0.1:25000': proxy_1}
    # get a proxy from a non-isolated instance (instance not stored / double test)
    supvisors_instance.context.instances['10.0.0.2:25000']._state = SupvisorsInstanceStates.STOPPED
    proxy_2 = proxy_server.get_proxy('10.0.0.2:25000')
    proxy_2.live_event.wait()
    assert proxy_2 is not None
    assert proxy_2.is_alive()
    assert proxy_2.status.identifier == '10.0.0.2:25000'
    assert proxy_server.proxies == {'10.0.0.1:25000': proxy_1, '10.0.0.2:25000': proxy_2}
    # get a proxy from an isolated instance (instance not stored)
    supvisors_instance.context.instances['10.0.0.3:25000']._state = SupvisorsInstanceStates.ISOLATED
    proxy_3 = proxy_server.get_proxy('10.0.0.3:25000')
    assert proxy_3 is None
    assert proxy_server.proxies == {'10.0.0.1:25000': proxy_1, '10.0.0.2:25000': proxy_2}
    # get a proxy from a non-isolated instance (instance stored)
    proxy_1bis = proxy_server.get_proxy('10.0.0.1:25000')
    proxy_1bis.live_event.wait()
    assert proxy_1bis is proxy_1
    # get a proxy from an isolated instance (instance stored)
    supvisors_instance.context.instances['10.0.0.1:25000']._state = SupvisorsInstanceStates.ISOLATED
    proxy_1ter = proxy_server.get_proxy('10.0.0.1:25000')
    assert proxy_1ter is None
    assert not proxy_1.is_alive()
    with proxy_server.mutex:
        assert proxy_server.proxies == {'10.0.0.2:25000': proxy_2}
    # test stop
    proxy_server.stop()
    assert not proxy_2.is_alive()
    assert proxy_server.stop_event.is_set()
    with proxy_server.mutex:
        assert proxy_server.proxies == {}
    # hit lines corresponding to incomplete stop
    proxy_server.stop_event.clear()
    proxy_2 = proxy_server.get_proxy('10.0.0.2:25000')
    proxy_2.live_event.wait()
    assert proxy_2.is_alive()
    mocker.patch.object(proxy_server, 'on_proxy_closing')
    proxy_server.stop()
    assert not proxy_1.is_alive()
    with proxy_server.mutex:
        assert proxy_server.proxies == {'10.0.0.2:25000': proxy_2}


def test_server_proxy_push_message(mocker, supvisors_instance, mocked_rpc, proxy_server):
    """ Test the SupervisorProxy function to send a remote communication event to a Supervisor instance. """
    mocked_push = mocker.patch('supvisors.internal_com.supervisorproxy.SupervisorProxyThread.push_message')
    # get a proxy from a non-isolated instance (instance not stored)
    supvisors_instance.context.instances['10.0.0.1:25000']._state = SupvisorsInstanceStates.RUNNING
    supvisors_instance.context.instances['10.0.0.2:25000']._state = SupvisorsInstanceStates.STOPPED
    supvisors_instance.context.instances['10.0.0.3:25000']._state = SupvisorsInstanceStates.ISOLATED
    supvisors_instance.context.instances['10.0.0.4:25000']._state = SupvisorsInstanceStates.ISOLATED
    supvisors_instance.context.instances['10.0.0.5:25000']._state = SupvisorsInstanceStates.CHECKING
    supvisors_instance.context.instances['10.0.0.6:25000']._state = SupvisorsInstanceStates.FAILED
    assert proxy_server.proxies == {}
    local_identifier = supvisors_instance.mapper.local_identifier
    # test request to a non-isolated Supervisor
    proxy_server.push_request('10.0.0.1:25000', {'message': 'test request'})
    assert mocked_push.call_args_list == [call((InternalEventHeaders.REQUEST,
                                                (local_identifier, {'message': 'test request'})))]
    assert sorted(proxy_server.proxies.keys()) == ['10.0.0.1:25000']
    mocked_push.reset_mock()
    # test request to an isolated Supervisor
    proxy_server.push_request('10.0.0.3:25000', {'message': 'test failed request'})
    assert not mocked_push.called
    assert sorted(proxy_server.proxies.keys()) == ['10.0.0.1:25000']
    # stop all and reset
    proxy_server.stop()
    assert proxy_server.stop_event.is_set()
    proxy_server.proxies = {}
    # stopped flag is set, so proxy creation is disabled
    proxy_server.push_request('10.0.0.1:25000', {'message': 'test request'})
    proxy_server.push_publication({'message': 'test publish'})
    proxy_server.push_notification({'message': 'test discovery'})
    assert not mocked_push.called
    # test publish
    proxy_server.stop_event.clear()
    proxy_server.push_publication({'message': 'test publish'})
    assert len(mocked_push.call_args_list) == 3
    for called in mocked_push.call_args_list:
        assert called == call((InternalEventHeaders.PUBLICATION, (local_identifier, {'message': 'test publish'})))
    assert sorted(proxy_server.proxies.keys()) == ['10.0.0.2:25000', '10.0.0.5:25000', '10.0.0.6:25000']
    mocked_push.reset_mock()
    # stop all and reset
    proxy_server.stop()
    assert proxy_server.stop_event.is_set()
    proxy_server.proxies = {}
    proxy_server.stop_event.clear()
    # test post_discovery
    proxy_server.push_notification({'message': 'test discovery'})
    assert mocked_push.call_args_list == [call((InternalEventHeaders.NOTIFICATION, {'message': 'test discovery'}))]
    assert sorted(proxy_server.proxies.keys()) == [local_identifier]
