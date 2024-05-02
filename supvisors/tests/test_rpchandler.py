# ======================================================================
# Copyright 2023 Julien LE CLEACH
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

from unittest.mock import call

from supvisors.internal_com.rpchandler import *


def test_all_requests(mocker, supvisors):
    """ Test the requests of the RpcHandler communication. """
    handler = RpcHandler(supvisors)
    assert handler.logger is supvisors.logger
    # mock proxy server
    proxy_server = mocker.patch.object(handler, 'proxy_server')
    # test push CHECK_INSTANCE
    handler.send_check_instance('10.0.0.1')
    expected = '10.0.0.1', (RequestHeaders.CHECK_INSTANCE.value, None)
    assert proxy_server.push_request.call_args_list == [call(*expected)]
    proxy_server.push_request.reset_mock()
    # test push START_PROCESS
    handler.send_start_process('10.0.0.1', 'group:name', 'extra args')
    expected = '10.0.0.1', (RequestHeaders.START_PROCESS.value, ('group:name', 'extra args'))
    assert proxy_server.push_request.call_args_list == [call(*expected)]
    proxy_server.push_request.reset_mock()
    # test push STOP_PROCESS
    handler.send_stop_process('10.0.0.1', 'group:name')
    expected = '10.0.0.1', (RequestHeaders.STOP_PROCESS.value, ('group:name',))
    assert proxy_server.push_request.call_args_list == [call(*expected)]
    proxy_server.push_request.reset_mock()
    # test push RESTART
    handler.send_restart('10.0.0.1')
    expected = '10.0.0.1', (RequestHeaders.RESTART.value, None)
    assert proxy_server.push_request.call_args_list == [call(*expected)]
    proxy_server.push_request.reset_mock()
    # test push SHUTDOWN
    handler.send_shutdown('10.0.0.1')
    expected = '10.0.0.1', (RequestHeaders.SHUTDOWN.value, None)
    assert proxy_server.push_request.call_args_list == [call(*expected)]
    proxy_server.push_request.reset_mock()
    # test push RESTART_SEQUENCE
    handler.send_restart_sequence('10.0.0.1')
    expected = '10.0.0.1', (RequestHeaders.RESTART_SEQUENCE.value, None)
    assert proxy_server.push_request.call_args_list == [call(*expected)]
    proxy_server.push_request.reset_mock()
    # test push RESTART_ALL
    handler.send_restart_all('10.0.0.1')
    expected = '10.0.0.1', (RequestHeaders.RESTART_ALL.value, None)
    assert proxy_server.push_request.call_args_list == [call(*expected)]
    proxy_server.push_request.reset_mock()
    # test push SHUTDOWN_ALL
    handler.send_shutdown_all('10.0.0.1')
    expected = '10.0.0.1', (RequestHeaders.SHUTDOWN_ALL.value, None)
    assert proxy_server.push_request.call_args_list == [call(*expected)]
    proxy_server.push_request.reset_mock()
    # check that the other methods have not been called
    assert not proxy_server.post_discovery.called
    assert not proxy_server.publish.called
    # call stop
    handler.stop()
    assert proxy_server.stop.call_args_list == [call()]


def test_all_publications(mocker, supvisors):
    """ Test the publications of the RpcHandler communication. """
    handler = RpcHandler(supvisors)
    assert handler.logger is supvisors.logger
    # mock proxy server
    proxy_server = mocker.patch.object(handler, 'proxy_server')
    # test push TICK
    handler.send_tick_event({'when': 1234})
    expected = PublicationHeaders.TICK.value, {'when': 1234}
    assert proxy_server.push_publication.call_args_list == [call(expected)]
    proxy_server.push_publication.reset_mock()
    # test push PROCESS
    handler.send_process_state_event({'name': 'dummy', 'state': 'RUNNING'})
    expected = PublicationHeaders.PROCESS.value, {'name': 'dummy', 'state': 'RUNNING'}
    assert proxy_server.push_publication.call_args_list == [call(expected)]
    proxy_server.push_publication.reset_mock()
    # test push PROCESS_ADDED
    handler.send_process_added_event({'name': 'dummy'})
    expected = PublicationHeaders.PROCESS_ADDED.value, {'name': 'dummy'}
    assert proxy_server.push_publication.call_args_list == [call(expected)]
    proxy_server.push_publication.reset_mock()
    # test push PROCESS_REMOVED
    handler.send_process_removed_event({'name': 'dummy'})
    expected = PublicationHeaders.PROCESS_REMOVED.value, {'name': 'dummy'}
    assert proxy_server.push_publication.call_args_list == [call(expected)]
    proxy_server.push_publication.reset_mock()
    # test push PROCESS_DISABILITY
    handler.send_process_disability_event({'name': 'dummy_program'})
    expected = PublicationHeaders.PROCESS_DISABILITY.value, {'name': 'dummy_program'}
    assert proxy_server.push_publication.call_args_list == [call(expected)]
    proxy_server.push_publication.reset_mock()
    # test push HOST_STATISTICS
    handler.send_host_statistics({'cpu': 1.0})
    expected = PublicationHeaders.HOST_STATISTICS.value, {'cpu': 1.0}
    assert proxy_server.push_publication.call_args_list == [call(expected)]
    proxy_server.push_publication.reset_mock()
    # test push PROCESS_STATISTICS
    handler.send_process_statistics({'dummy_process': {'cpu': 1.0}})
    expected = PublicationHeaders.PROCESS_STATISTICS.value, {'dummy_process': {'cpu': 1.0}}
    assert proxy_server.push_publication.call_args_list == [call(expected)]
    proxy_server.push_publication.reset_mock()
    # test push STATE
    handler.send_state_event({'state': 'INIT'})
    expected = PublicationHeaders.STATE.value, {'state': 'INIT'}
    assert proxy_server.push_publication.call_args_list == [call(expected)]
    proxy_server.push_publication.reset_mock()
    # check that the other methods have not been called
    assert not proxy_server.post_discovery.called
    assert not proxy_server.post_request.called
    # call stop
    handler.stop()
    assert proxy_server.stop.call_args_list == [call()]


def test_discovery_event(mocker, supvisors):
    """ Test the discovery events of the RpcHandler communication. """
    handler = RpcHandler(supvisors)
    assert handler.logger is supvisors.logger
    # mock proxy server
    proxy_server = mocker.patch.object(handler, 'proxy_server')
    # test push STATE
    expected = (('10.0.0.1', ('10.0.0.1', 7777)), {'state': 'INIT'})
    handler.push_notification(expected)
    assert proxy_server.push_notification.call_args_list == [call(expected)]
    proxy_server.push_notification.reset_mock()
    # check that the other methods have not been called
    assert not proxy_server.post_request.called
    assert not proxy_server.publish.called
    # call stop
    handler.stop()
    assert proxy_server.stop.call_args_list == [call()]
