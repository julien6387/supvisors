#!/usr/bin/python
# -*- coding: utf-8 -*-
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

from socket import gethostbyname, gethostname

import pytest

from supvisors.supvisorspubsub import *
from supvisors.ttypes import DeferredRequestHeaders

local_ip = gethostbyname(gethostname())


@pytest.fixture
def sockets(supvisors):
    """ Create the SupvisorsSockets instance. """
    socks = SupvisorsPubSub(supvisors)
    yield socks
    socks.stop()
    socks.receiver.close()


def check_sockets(subscriber: InternalSubscriber,
                  request: Any,
                  notification: Any,
                  heartbeat_identifier: Optional[str],
                  hb_dates: List[float],
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
            assert subscriber.read_socket(subscriber.puller_sock) == ('', request)
            got_expected_request = True
        # test notification part
        messages = subscriber.read_fds(external_events_sockets)
        for peer, (msg_type, (identifier, msg_body)) in messages:
            assert peer == (local_ip, 65100)
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


def test_global_normal(sockets):
    """ Test the Supvisors TCP publish / subscribe in one single test. """
    subscriber = sockets.receiver
    pusher = sockets.pusher
    publisher = sockets.emitter
    # initial check for connectable instances
    assert sorted(subscriber.instances.keys()) == sorted(sockets.supvisors.supvisors_mapper.instances.keys())
    # wait for publisher server to be alive
    time.sleep(1)
    assert publisher.is_alive()
    # the subscriber has connected the local publisher instance
    local_identifier = sockets.supvisors.supvisors_mapper.local_identifier
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
    # test publish / subscribe for HOST_STATISTICS
    publisher.send_host_statistics({'cpu': 25.3, 'mem': 12.5})
    check_sockets(subscriber, None,
                  [InternalEventHeaders.HOST_STATISTICS.value, {'cpu': 25.3, 'mem': 12.5}],
                  local_identifier, [hb_sent, hb_recv])
    # test publish / subscribe for PROCESS_STATISTICS
    publisher.send_process_statistics({'dummy_process': {'cpu': 25.3, 'mem': 12.5}})
    check_sockets(subscriber, None,
                  [InternalEventHeaders.PROCESS_STATISTICS.value, {'dummy_process': {'cpu': 25.3, 'mem': 12.5}}],
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
    check_sockets(subscriber, None, None, None, [], True)


def test_publisher_restart(sockets):
    """ Test the publisher restart in case of new network interface. """
    # wait for publisher server to be alive
    ref_publisher = sockets.emitter
    time.sleep(1)
    assert ref_publisher.is_alive()
    # first try (init)
    sockets.check_intf(['localhost'])
    assert ref_publisher is sockets.emitter
    assert sockets.intf_names == ['localhost']
    # second try / confirm network interface names
    sockets.check_intf(['localhost'])
    assert ref_publisher is sockets.emitter
    assert sockets.intf_names == ['localhost']
    # third try / add an interface name
    sockets.check_intf(['localhost', 'eth0'])
    assert ref_publisher is not sockets.emitter
    assert sockets.intf_names == ['localhost', 'eth0']
    # wait for publisher server to be alive
    ref_publisher = sockets.emitter
    time.sleep(1)
    assert ref_publisher.is_alive()
    # fourth try / remove an interface name
    sockets.check_intf(['localhost'])
    assert ref_publisher is sockets.emitter
    assert sockets.intf_names == ['localhost']


# testing exception cases (by line number)
def test_publisher_bind_exception(supvisors):
    """ Test the bind exception of the PublisherServer.
    The aim is to hit the lines 112-113 in PublisherServer._bind.
    Checked ok with debugger.
    """
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


def test_publisher_accept_exception(mocker, sockets):
    """ Test the accept exception of the PublisherServer.
    The aim is to hit the line 209-211 in PublisherServer._handle_events.
    Checked ok with debugger.
    """
    subscriber = sockets.receiver
    publisher = sockets.emitter
    # wait for publisher server to be alive
    time.sleep(1)
    assert publisher.is_alive()
    # the subscriber has connected the local publisher instance
    assert len(publisher.clients) == 1
    # socket.accept is read-only and cannot be mocked, so mock _add_client
    mocker.patch.object(publisher, '_add_client', side_effect=OSError)
    # now force the subscriber to reconnect / create new subscriber
    subscriber.close()
    sockets.pusher_sock, sockets.puller_sock = socketpair()
    sockets.receiver = InternalSubscriber(sockets.puller_sock, sockets.supvisors)
    time.sleep(1)
    # check no connection registered
    assert publisher.clients == {}


def test_publisher_forward_empty_message(supvisors, sockets):
    """ Test the robustness when the publisher forwards an empty message.
    The aim is to hit the lines 230-231 in PublisherServer._forward_message.
    Checked ok with debugger.
    """
    subscriber = sockets.receiver
    publisher = sockets.emitter
    # wait for publisher server to be alive
    time.sleep(1)
    assert publisher.is_alive()
    # the subscriber has connected the local publisher instance
    local_identifier = supvisors.supvisors_mapper.local_identifier
    assert list(subscriber.subscribers.keys()) == [local_identifier]
    # send a 0-sized message to the subscriber interface
    assert len(publisher.clients) == 1
    buffer = int.to_bytes(0, 4, 'big')
    publisher.put_sock.sendall(buffer)
    # wait for publisher server to die
    time.sleep(1)
    assert not publisher.is_alive()


def test_publisher_receive_empty_message(sockets):
    """ Test the robustness when the publisher receives an empty message.
    The aim is to hit the lines 246-247 in PublisherServer._receive_client_heartbeat.
    Checked ok with debugger.
    """
    subscriber = sockets.receiver
    publisher = sockets.emitter
    # wait for publisher server to be alive
    time.sleep(1)
    assert publisher.is_alive()
    # the subscriber has connected the local publisher instance
    assert len(publisher.clients) == 1
    # send empty message from the subscriber
    local_identifier = sockets.supvisors.supvisors_mapper.local_identifier
    sock, _, _ = subscriber.subscribers[local_identifier]
    buffer = int.to_bytes(0, 4, 'big')
    sock.sendall(buffer)
    # reconnection will not have time to happen
    time.sleep(1)
    assert publisher.clients == {}


def test_publisher_heartbeat_timeout(mocker, sockets):
    """ Test the exception management in PublisherServer when heartbeat missing from a client.
    The aim is to hit the lines 275-277 in PublisherServer._manage_heartbeats.
    Checked ok with debugger.
    """
    publisher = sockets.emitter
    subscriber = sockets.receiver
    # wait for publisher server to be alive
    time.sleep(1)
    assert publisher.is_alive()
    # the subscriber has connected the local publisher instance
    local_identifier = sockets.supvisors.supvisors_mapper.local_identifier
    assert list(subscriber.subscribers.keys()) == [local_identifier]
    assert len(publisher.clients) == 1
    # poll until heartbeat is received
    max_wait = 40  # 40 loops of 100ms
    external_events_sockets = None
    while not external_events_sockets and max_wait > 0:
        _, external_events_sockets = subscriber.poll()
        max_wait -= 1
    # SubscriberInterface instances cannot be accessed from the sockets structure
    # closing the subscriber will raise the POLLHUP event
    # so mock the InternalSubscriber heartbeat emission and at some point the SubscriberInterface will close
    mocker.patch.object(subscriber, 'manage_heartbeat')
    # remove identifier from InternalSubscriber instances to prevent reconnection
    subscriber.instances = {}
    # read everything during 10 seconds
    target = time.time() + 10
    while time.time() < target:
        _, external_events_sockets = subscriber.poll()
        subscriber.read_fds(external_events_sockets)
    # check disconnection on subscriber side and publisher side
    assert subscriber.subscribers == {}
    assert publisher.clients == {}


def test_publisher_publish_message_exception(sockets):
    """ Test the publish exception management in PublisherServer when the client is closed.
    The aim is to hit the line 291-293 in PublisherServer._publish_message.
    Checked ok with debugger.
    """
    publisher = sockets.emitter
    subscriber = sockets.receiver
    # wait for publisher server to be alive
    time.sleep(1)
    assert publisher.is_alive()
    # the subscriber has connected the local publisher instance
    local_identifier = sockets.supvisors.supvisors_mapper.local_identifier
    assert list(subscriber.subscribers.keys()) == [local_identifier]
    assert len(publisher.clients) == 1
    # close the client and send a message
    client = next(x for x in publisher.clients.values())
    client.socket.shutdown(SHUT_RDWR)
    # publish a message
    publisher._publish_message(b'hello')
    # check that the client is removed
    assert publisher.clients == {}


def test_publisher_publish_exception(sockets):
    """ Test the sendto exception of the PublisherServer.
    The aim is to hit the lines 321-324 in InternalPublisher.emit_message.
    Checked ok with debugger.
    """
    # wait for publisher server to be alive
    publisher = sockets.emitter
    time.sleep(1)
    assert publisher.is_alive()
    # close the internal put socket
    publisher.put_sock.close()
    # try to publish a message
    publisher.emit_message(InternalEventHeaders.TICK, {})
    # wait for publisher server to be alive
    time.sleep(1)
    assert not publisher.is_alive()


def test_subscriber_heartbeat_timeout(sockets):
    """ Test the exception management in subscriber when heartbeat missing from a publisher.
    The aim is to hit the line 398 in InternalSubscriber._check_heartbeat.
    Checked ok with debugger.
    """
    subscriber = sockets.receiver
    # wait for publisher server to be alive
    time.sleep(1)
    assert sockets.emitter.is_alive()
    # the subscriber has connected the local publisher instance
    local_identifier = sockets.supvisors.supvisors_mapper.local_identifier
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


def test_send_heartbeat_exception(sockets):
    """ Test the exception management when sending heartbeat to a socket that has been closed.
    The aim is to trigger the OSError in InternalSubscriber._send_heartbeat (line 413-414).
    Checked ok with debugger.
    """
    subscriber = sockets.receiver
    # wait for publisher server to be alive
    time.sleep(1)
    assert sockets.emitter.is_alive()
    # the subscriber has connected the local publisher instance
    local_identifier = sockets.supvisors.supvisors_mapper.local_identifier
    assert list(subscriber.subscribers.keys()) == [local_identifier]
    # poll until heartbeat is received
    max_wait = 40  # 40 loops of 100ms
    external_events_sockets = None
    while not external_events_sockets and max_wait > 0:
        _, external_events_sockets = subscriber.poll()
        max_wait -= 1
    # close socket before it is used for reading or writing
    client_sock = subscriber.subscribers[local_identifier][0]
    assert client_sock.fileno() in external_events_sockets
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
