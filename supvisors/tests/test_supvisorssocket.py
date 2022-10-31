#!/usr/bin/python
# -*- coding: utf-8 -*-
import socket
import time

# ======================================================================
# Copyright 2022 Julien LE CLEACH
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

from supvisors.supvisorssocket import *


def test_payload_to_bytes_to_payload(supvisors):
    """ Test the serialization and deserialization. """
    msg_type_enum = Enum('MessageType', ['TEST', 'TEST_2'])
    payload = 'a message source', {'body': 'a message body'}
    msg_bytes = payload_to_bytes(msg_type_enum.TEST_2, payload)
    assert isinstance(msg_bytes, bytes)
    assert bytes_to_payload(msg_bytes) == [2, ['a message source', {'body': 'a message body'}]]


@pytest.fixture
def sockets(supvisors):
    """ Create the SupvisorsSockets instance. """
    socks = SupvisorsSockets(supvisors)
    yield socks
    socks.stop()
    socks.subscriber.close()


def check_sockets(subscriber: InternalSubscriber,
                  request: Any,
                  notification: Any,
                  heartbeat_identifier: str, hb_dates: List[float],
                  heartbeat_required: bool = False):
    """ Check that requests, notifications or heartbeats have been received as expected.
    Poll timeout is 100ms, so this method waits up to 3 seconds to get the messages expected.
    Heartbeat period is set to 2 seconds so at least one heartbeat is always expected here. """
    got_expected_request, got_expected_notification, got_heartbeat = False, False, False
    for _ in range(30):
        requests_socket, external_events_sockets = subscriber.poll()
        # test request part
        assert not requests_socket or request
        if requests_socket:
            assert requests_socket is subscriber.puller_sock
            assert subscriber.read_socket(requests_socket) == request
            got_expected_request = True
        # test notification part
        messages = subscriber.read_subscribers(external_events_sockets)
        for msg_type, (identifier, msg_body) in messages:
            # test heartbeat part
            if msg_type == InternalEventHeaders.HEARTBEAT.value:
                assert identifier == heartbeat_identifier
                assert msg_body == {}
                got_heartbeat = True
            else:
                # test events
                assert identifier == heartbeat_identifier
                assert msg_type == notification[0]
                assert msg_body == notification[1]
                got_expected_notification = True
        # send heartbeats
        subscriber.manage_heartbeat()
        # exit for loop if request received
        if got_expected_request and not heartbeat_required and not notification:
            break
        # exit for loop if notification received
        if got_expected_notification and not heartbeat_required and not request:
            break
    # final check
    assert not request or got_expected_request
    assert not notification or got_expected_notification
    # heartbeats must have been sent and received
    assert not heartbeat_required or not heartbeat_identifier or got_heartbeat
    if got_heartbeat:
        current_time = time.time()
        _, hb_sent, hb_recv = subscriber.subscribers[heartbeat_identifier]
        assert current_time > hb_sent > hb_dates[0]
        assert current_time > hb_recv > hb_dates[1]
        hb_dates[:] = [hb_sent, hb_recv]


def test_global_normal(supvisors, sockets):
    """ Test the Supvisors internal communications in one single test. """
    subscriber = sockets.subscriber
    pusher = sockets.pusher
    publisher = sockets.publisher
    # initial check for connectable instances
    assert sorted(subscriber.instances.keys()) == sorted(supvisors.supvisors_mapper.instances.keys())
    # wait for publisher server to be alive
    time.sleep(1)
    assert publisher.is_alive()
    # the subscriber has connected the local publisher instance
    local_identifier = supvisors.supvisors_mapper.local_identifier
    assert list(subscriber.subscribers.keys()) == [local_identifier]
    client_sock, hb_sent, hb_recv = subscriber.subscribers[local_identifier]
    assert isinstance(client_sock, socket)
    assert hb_sent == 0
    assert time.time() > hb_recv > 0
    # poll during 3 seconds: nothing sent but heartbeat
    check_sockets(subscriber, None, None, local_identifier, [hb_sent, hb_recv], True)
    # test push / subscribe for CHECK_INSTANCE
    pusher.send_check_instance('10.0.0.1')
    check_sockets(subscriber,
                  [DeferredRequestHeaders.CHECK_INSTANCE.value, ['10.0.0.1', ]],
                  None, local_identifier, [hb_sent, hb_recv])
    # test push / subscribe for ISOLATE_INSTANCES
    pusher.send_isolate_instances(['10.0.0.1', '10.0.0.2'])
    check_sockets(subscriber,
                  [DeferredRequestHeaders.ISOLATE_INSTANCES.value, ['10.0.0.1', '10.0.0.2']],
                  None, local_identifier, [hb_sent, hb_recv])
    # test push / subscribe for START_PROCESS
    pusher.send_start_process('10.0.0.1', 'group:name', 'extra args')
    check_sockets(subscriber,
                  [DeferredRequestHeaders.START_PROCESS.value, ['10.0.0.1', 'group:name', 'extra args']],
                  None, local_identifier, [hb_sent, hb_recv])
    # test push / subscribe for STOP_PROCESS
    pusher.send_stop_process('10.0.0.1', 'group:name')
    check_sockets(subscriber,
                  [DeferredRequestHeaders.STOP_PROCESS.value, ['10.0.0.1', 'group:name']],
                  None, local_identifier, [hb_sent, hb_recv])
    # test push / subscribe for RESTART
    pusher.send_restart('10.0.0.1')
    check_sockets(subscriber,
                  [DeferredRequestHeaders.RESTART.value, ['10.0.0.1', ]],
                  None, local_identifier, [hb_sent, hb_recv])
    # test push / subscribe for SHUTDOWN
    pusher.send_shutdown('10.0.0.1')
    check_sockets(subscriber,
                  [DeferredRequestHeaders.SHUTDOWN.value, ['10.0.0.1', ]],
                  None, local_identifier, [hb_sent, hb_recv])
    # test push / subscribe for RESTART_SEQUENCE
    pusher.send_restart_sequence('10.0.0.1')
    check_sockets(subscriber,
                  [DeferredRequestHeaders.RESTART_SEQUENCE.value, ['10.0.0.1', ]],
                  None, local_identifier, [hb_sent, hb_recv])
    # test push / subscribe for RESTART_ALL
    pusher.send_restart_all('10.0.0.1')
    check_sockets(subscriber,
                  [DeferredRequestHeaders.RESTART_ALL.value, ['10.0.0.1', ]],
                  None, local_identifier, [hb_sent, hb_recv])
    # test push / subscribe for SHUTDOWN_ALL
    pusher.send_shutdown_all('10.0.0.1')
    check_sockets(subscriber,
                  [DeferredRequestHeaders.SHUTDOWN_ALL.value, ['10.0.0.1', ]],
                  None, local_identifier, [hb_sent, hb_recv])
    # test publish / subscribe for HEARTBEAT (not yet)
    # test publish / subscribe for TICK
    publisher.send_tick_event({'when': 1234})
    check_sockets(subscriber, None,
                  [InternalEventHeaders.TICK.value, {'when': 1234}],
                  local_identifier, [hb_sent, hb_recv])
    # test publish / subscribe for PROCESS
    publisher.send_process_state_event({'namespec': 'dummy_group:dummy_name', 'state': 'running'})
    check_sockets(subscriber, None,
                  [InternalEventHeaders.PROCESS.value, {'namespec': 'dummy_group:dummy_name', 'state': 'running'}],
                  local_identifier, [hb_sent, hb_recv])
    # test publish / subscribe for PROCESS_ADDED
    publisher.send_process_added_event({'namespec': 'dummy_group:dummy_name'})
    check_sockets(subscriber, None,
                  [InternalEventHeaders.PROCESS_ADDED.value, {'namespec': 'dummy_group:dummy_name'}],
                  local_identifier, [hb_sent, hb_recv])
    # test publish / subscribe for PROCESS_REMOVED
    publisher.send_process_removed_event({'namespec': 'dummy_group:dummy_name'})
    check_sockets(subscriber, None,
                  [InternalEventHeaders.PROCESS_REMOVED.value, {'namespec': 'dummy_group:dummy_name'}],
                  local_identifier, [hb_sent, hb_recv])
    # test publish / subscribe for PROCESS_DISABILITY
    publisher.send_process_disability_event({'name': 'dummy_name', 'disabled': True})
    check_sockets(subscriber, None,
                  [InternalEventHeaders.PROCESS_DISABILITY.value, {'name': 'dummy_name', 'disabled': True}],
                  local_identifier, [hb_sent, hb_recv])
    # test publish / subscribe for STATISTICS
    publisher.send_statistics({'cpu': 25.3, 'mem': 12.5})
    check_sockets(subscriber, None,
                  [InternalEventHeaders.STATISTICS.value, {'cpu': 25.3, 'mem': 12.5}],
                  local_identifier, [hb_sent, hb_recv])
    # test publish / subscribe for STATE
    publisher.send_state_event({'state': 'operational', 'mode': 'starting'})
    check_sockets(subscriber, None,
                  [InternalEventHeaders.STATE.value, {'state': 'operational', 'mode': 'starting'}],
                  local_identifier, [hb_sent, hb_recv])
    # test subscriber disconnect and check that nothing is received anymore
    subscriber.disconnect_subscriber([local_identifier])
    assert subscriber.subscribers == {}
    assert local_identifier not in subscriber.instances
    # check that nothing is received anymore by the subscribers
    publisher.send_state_event({'state': 'operational', 'mode': 'starting'})
    check_sockets(subscriber, None, None, None, None, True)


def test_read_socket_zero_message_size():
    """ Test of the reception of a 0-sized message in the InternalSubscriber.read_socket method. """
    send_sock, recv_sock = socketpair()
    send_sock.sendall(int.to_bytes(0, 4, 'big'))
    assert InternalSubscriber.read_socket(recv_sock) == {}


def test_read_subscribers_exception(supvisors, sockets):
    """ Test the exception management when reading from a socket that has been closed after poll returned a result. """
    subscriber = sockets.subscriber
    # wait for publisher server to be alive
    time.sleep(1)
    assert sockets.publisher.is_alive()
    # the subscriber has connected the local publisher instance
    local_identifier = supvisors.supvisors_mapper.local_identifier
    assert list(subscriber.subscribers.keys()) == [local_identifier]
    # poll until heartbeat is received
    max_wait = 40  # 40 loops of 100ms
    external_events_sockets = None
    while not external_events_sockets and max_wait > 0:
        _, external_events_sockets = subscriber.poll()
        max_wait -= 1
    # close socket before it is used for reading or writing
    client_sock = subscriber.subscribers[local_identifier][0]
    assert (local_identifier, client_sock) in external_events_sockets
    client_sock.close()
    # try to read from it
    assert subscriber.read_subscribers(external_events_sockets) == []
    assert local_identifier not in subscriber.subscribers
    # check that a new subscriber socket is created after a while
    time.sleep(2)
    assert list(subscriber.subscribers.keys()) == [local_identifier]
    client_sock, hb_sent, hb_recv = subscriber.subscribers[local_identifier]
    assert isinstance(client_sock, socket)
    assert hb_sent == 0
    assert time.time() > hb_recv > 0


def test_send_heartbeat_exception(supvisors, sockets):
    """ Test the exception management when sending heartbeat to a socket that has been closed. """
    subscriber = sockets.subscriber
    # wait for publisher server to be alive
    time.sleep(1)
    assert sockets.publisher.is_alive()
    # the subscriber has connected the local publisher instance
    local_identifier = supvisors.supvisors_mapper.local_identifier
    assert list(subscriber.subscribers.keys()) == [local_identifier]
    # poll until heartbeat is received
    max_wait = 40  # 40 loops of 100ms
    external_events_sockets = None
    while not external_events_sockets and max_wait > 0:
        _, external_events_sockets = subscriber.poll()
        max_wait -= 1
    # close socket before it is used for reading or writing
    client_sock = subscriber.subscribers[local_identifier][0]
    assert (local_identifier, client_sock) in external_events_sockets
    client_sock.close()
    # try to write to it
    subscriber._send_heartbeat()
    # check that socket has been removed from the subscribers
    assert local_identifier not in subscriber.subscribers
    # check that a new subscriber socket is created after a while
    time.sleep(2)
    assert list(subscriber.subscribers.keys()) == [local_identifier]
    client_sock, hb_sent, hb_recv = subscriber.subscribers[local_identifier]
    assert isinstance(client_sock, socket)
    assert hb_sent == 0
    assert time.time() > hb_recv > 0


def test_publisher_heartbeat_timeout(supvisors, sockets):
    """ Test the exception management in publisher when heartbeat missing from a subscriber. """
    subscriber = sockets.subscriber
    # wait for publisher server to be alive
    time.sleep(1)
    assert sockets.publisher.is_alive()
    # the subscriber has connected the local publisher instance
    local_identifier = supvisors.supvisors_mapper.local_identifier
    assert list(subscriber.subscribers.keys()) == [local_identifier]
    # poll until heartbeat is received
    max_wait = 40  # 40 loops of 100ms
    external_events_sockets = None
    while not external_events_sockets and max_wait > 0:
        _, external_events_sockets = subscriber.poll()
        max_wait -= 1
    # socket is closed in publisher after 10 seconds without heartbeat
    assert local_identifier in subscriber.subscribers
    ref_sock = subscriber.subscribers[local_identifier][0]
    # wait for 10 seconds without sending heartbeats
    # force heartbeat reception date
    subscriber.subscribers[local_identifier][2] = 0
    subscriber._check_heartbeat()
    assert local_identifier not in subscriber.subscribers
    # check that a new subscriber socket is created after a while
    time.sleep(2)
    assert list(subscriber.subscribers.keys()) == [local_identifier]
    client_sock, hb_sent, hb_recv = subscriber.subscribers[local_identifier]
    assert client_sock is not ref_sock
    assert isinstance(client_sock, socket)
    assert hb_sent == 0
    assert time.time() > hb_recv > 0


def test_push_message_exception(supvisors):
    """ Test the socket exception when pushing a message with the RequestPusher.push_message method. """
    push_sock, pull_sock = socketpair()
    pusher = RequestPusher(push_sock, supvisors.logger)
    # normal case
    pusher.push_message(DeferredRequestHeaders.START_PROCESS, ('a message',))
    assert InternalSubscriber.read_socket(pull_sock) == [2, ['a message']]
    # exception case
    push_sock.close()
    pusher.push_message(DeferredRequestHeaders.START_PROCESS, ('a message',))
    assert InternalSubscriber.read_socket(pull_sock) == {}


def test_publisher_bind_exception(supvisors):
    """ Test the bind exception of the PublisherServer. """
    local_instance: SupvisorsInstanceId = supvisors.supvisors_mapper.local_instance
    # start a first publisher server
    server1 = PublisherServer(local_instance.identifier, local_instance.internal_port, supvisors.logger)
    assert server1.server is not None
    # wait for publisher server to be alive
    server1.start()
    time.sleep(1)
    assert server1.is_alive()
    # start a second publisher server on the same port
    server2 = PublisherServer(local_instance.identifier, local_instance.internal_port, supvisors.logger)
    assert server2.server is None
    # the publisher server thread will stop immediately
    server2.start()
    time.sleep(1)
    assert not server2.is_alive()
    # close all
    server1.stop()
    server2.stop()


def test_publisher_forward_empty_message(supvisors, sockets):
    """ . """
    subscriber = sockets.subscriber
    publisher = sockets.publisher
    # wait for publisher server to be alive
    time.sleep(1)
    assert publisher.is_alive()
    # the subscriber has connected the local publisher instance
    local_identifier = supvisors.supvisors_mapper.local_identifier
    assert list(subscriber.subscribers.keys()) == [local_identifier]
    ref_sock = subscriber.subscribers[local_identifier][0]
    # send a 0-sized message to the subscriber interface
    assert len(publisher.publisher_thread.clients) == 1
    put_socket = publisher.publisher_thread.clients[0]
    buffer = int.to_bytes(0, 4, 'big')
    put_socket.sendall(buffer)
    # this will cause an exception that will end the subscriber interface
    # error is detected in PublisherThread at next message emission from publisher thread
    publisher.publisher_thread._publish_heartbeat()
    # error is detected in Subscriber / ClientConnectionThread at heartbeat emission
    reached = False
    for idx in range(120):  # HEARTBEAT_TIMEOUT + margin
        _, external_events_sockets = subscriber.poll()
        subscriber.read_subscribers(external_events_sockets)
        subscriber.manage_heartbeat()
        # check if a new subscriber socket has been created
        if local_identifier in subscriber.subscribers:
            client_sock, _, _ = subscriber.subscribers[local_identifier]
            if client_sock is not ref_sock:
                reached = True
                break
    assert reached
