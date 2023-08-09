#!/usr/bin/python
# -*- coding: utf-8 -*-

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

from unittest.mock import Mock

import pytest

from supvisors.internalinterface import *


@pytest.fixture
def push_pull():
    """ Return a pair of sockets to be used for Push / Pull. """
    return socketpair()


@pytest.fixture
def receiver(supvisors, push_pull):
    """ Create the InternalCommReceiver instance. """
    return InternalCommReceiver(push_pull[1], supvisors.logger)


@pytest.fixture
def pusher(supvisors, push_pull):
    """ Create the InternalCommReceiver instance. """
    return RequestPusher(push_pull[0], supvisors.logger)


@pytest.fixture
def internal_com(supvisors):
    """ Create the SupvisorsInternalComm instance. """
    return SupvisorsInternalComm(supvisors)


def test_payload_to_bytes_to_payload(supvisors):
    """ Test the serialization and deserialization. """
    class MsgTypeEnum(Enum):
        TEST, TEST_2 = range(2)

    payload = 'a message source', {'body': 'a message body'}
    msg_bytes = payload_to_bytes(MsgTypeEnum.TEST_2, payload)
    assert isinstance(msg_bytes, bytes)
    assert bytes_to_payload(msg_bytes) == [1, ['a message source', {'body': 'a message body'}]]


def test_read_from_socket():
    """ Test the read_from_socket function. """
    pusher_sock, puller_sock = socketpair()
    # test with message lower than BUFFER_SIZE
    msg = b'1234567890'
    pusher_sock.send(msg)
    assert read_from_socket(puller_sock, 4) == b'1234'
    assert read_from_socket(puller_sock, 6) == b'567890'
    # test with message equal to BUFFER_SIZE
    msg = bytearray([i % 10 for i in range(BUFFER_SIZE)])
    pusher_sock.send(msg)
    recv = read_from_socket(puller_sock, BUFFER_SIZE)
    assert recv == msg
    # test with message greater than BUFFER_SIZE
    msg = bytearray([i % 10 for i in range(BUFFER_SIZE + 100)])
    pusher_sock.send(msg)
    recv = read_from_socket(puller_sock, BUFFER_SIZE + 100)
    assert recv == msg


def test_read_socket():
    """ Test the InternalCommReceiver.read_socket. """
    pusher_sock, puller_sock = socketpair()
    # test 0-sized message
    pusher_sock.send(int.to_bytes(0, 4, 'big'))
    assert InternalCommReceiver.read_socket(puller_sock) is None
    # test normal message
    message = b'"dummy"'
    buffer = len(message).to_bytes(4, 'big') + message
    pusher_sock.send(buffer)
    assert InternalCommReceiver.read_socket(puller_sock) == ('', 'dummy')
    # test read exception
    pusher_sock.close()
    assert InternalCommReceiver.read_socket(puller_sock) is None


def test_internal_comm_emitter():
    """ Test the InternalCommEmitter abstract class. """
    abstract_emitter = InternalCommEmitter()
    with pytest.raises(NotImplementedError):
        abstract_emitter.close()
    with pytest.raises(NotImplementedError):
        abstract_emitter.send_tick_event({})
    with pytest.raises(NotImplementedError):
        abstract_emitter.send_process_state_event({})
    with pytest.raises(NotImplementedError):
        abstract_emitter.send_process_added_event({})
    with pytest.raises(NotImplementedError):
        abstract_emitter.send_process_removed_event({})
    with pytest.raises(NotImplementedError):
        abstract_emitter.send_process_disability_event({})
    with pytest.raises(NotImplementedError):
        abstract_emitter.send_host_statistics({})
    with pytest.raises(NotImplementedError):
        abstract_emitter.send_process_statistics({})
    with pytest.raises(NotImplementedError):
        abstract_emitter.send_state_event({})


def test_internal_comm_receiver_creation(supvisors, push_pull, receiver):
    """ Test the InternalCommReceiver creation. """
    # check the instance
    assert receiver.puller_sock is push_pull[1]
    assert receiver.logger is supvisors.logger
    # test calls to empty methods
    with pytest.raises(NotImplementedError):
        receiver.read_fds([])
    with pytest.raises(NotImplementedError):
        receiver.manage_heartbeat()
    with pytest.raises(NotImplementedError):
        receiver.connect_subscribers()
    with pytest.raises(NotImplementedError):
        receiver.disconnect_subscribers([])
    # try polling when nothing sent
    assert receiver.poll() == (False, [])
    # close pusher / puller properly
    receiver.close()


def test_internal_comm_receiver_pull(push_pull, receiver):
    """ Test the pulling of a message using the InternalCommReceiver. """
    msg = b'1234'
    buffer = len(msg).to_bytes(4, 'big') + msg
    push_pull[0].send(buffer)
    assert receiver.poll() == (True, [])
    assert receiver.read_puller() == 1234


def test_internal_comm_receiver_subscribe(receiver):
    """ Test the subscription of a message using the InternalCommReceiver. """
    publisher_sock, subscriber_sock = socketpair()
    # add a subscriber and publish a message
    receiver.poller.register(subscriber_sock, select.POLLIN)
    # send the message and check its reception
    msg = b'1234'
    buffer = len(msg).to_bytes(4, 'big') + msg
    publisher_sock.send(buffer)
    assert receiver.poll() == (False, [subscriber_sock.fileno()])
    assert InternalCommReceiver.read_socket(subscriber_sock) == ('', 1234)


def test_internal_comm_receiver_subscribe_empty(receiver):
    """ Test the reception of a 0-sized message using the InternalCommReceiver. """
    publisher_sock, subscriber_sock = socketpair()
    # add a subscriber and publish a message
    receiver.poller.register(subscriber_sock, select.POLLIN)
    # test the reception of a 0-sized message
    publisher_sock.sendall(int.to_bytes(0, 4, 'big'))
    assert receiver.poll() == (False, [subscriber_sock.fileno()])
    assert receiver.read_socket(subscriber_sock) is None


def test_request_pusher(supvisors, push_pull, pusher):
    """ Test the Supvisors internal communications in one single test. """
    assert pusher.socket is push_pull[0]
    assert pusher.logger is supvisors.logger
    # test push / subscribe for CHECK_INSTANCE
    pusher.send_check_instance('10.0.0.1')
    expected = [DeferredRequestHeaders.CHECK_INSTANCE.value, ['10.0.0.1', ]]
    assert InternalCommReceiver.read_socket(push_pull[1]) == ('', expected)
    # test push / subscribe for ISOLATE_INSTANCES
    pusher.send_isolate_instances(['10.0.0.1', '10.0.0.2'])
    expected = [DeferredRequestHeaders.ISOLATE_INSTANCES.value, ['10.0.0.1', '10.0.0.2']]
    assert InternalCommReceiver.read_socket(push_pull[1]) == ('', expected)
    # test push / subscribe for START_PROCESS
    pusher.send_start_process('10.0.0.1', 'group:name', 'extra args')
    expected = [DeferredRequestHeaders.START_PROCESS.value, ['10.0.0.1', 'group:name', 'extra args']]
    assert InternalCommReceiver.read_socket(push_pull[1]) == ('', expected)
    # test push / subscribe for STOP_PROCESS
    pusher.send_stop_process('10.0.0.1', 'group:name')
    expected = [DeferredRequestHeaders.STOP_PROCESS.value, ['10.0.0.1', 'group:name']]
    assert InternalCommReceiver.read_socket(push_pull[1]) == ('', expected)
    # test push / subscribe for RESTART
    pusher.send_restart('10.0.0.1')
    expected = [DeferredRequestHeaders.RESTART.value, ['10.0.0.1', ]]
    assert InternalCommReceiver.read_socket(push_pull[1]) == ('', expected)
    # test push / subscribe for SHUTDOWN
    pusher.send_shutdown('10.0.0.1')
    expected = [DeferredRequestHeaders.SHUTDOWN.value, ['10.0.0.1', ]]
    assert InternalCommReceiver.read_socket(push_pull[1]) == ('', expected)
    # test push / subscribe for RESTART_SEQUENCE
    pusher.send_restart_sequence('10.0.0.1')
    expected = [DeferredRequestHeaders.RESTART_SEQUENCE.value, ['10.0.0.1', ]]
    assert InternalCommReceiver.read_socket(push_pull[1]) == ('', expected)
    # test push / subscribe for RESTART_ALL
    pusher.send_restart_all('10.0.0.1')
    expected = [DeferredRequestHeaders.RESTART_ALL.value, ['10.0.0.1', ]]
    assert InternalCommReceiver.read_socket(push_pull[1]) == ('', expected)
    # test push / subscribe for SHUTDOWN_ALL
    pusher.send_shutdown_all('10.0.0.1')
    expected = [DeferredRequestHeaders.SHUTDOWN_ALL.value, ['10.0.0.1', ]]
    assert InternalCommReceiver.read_socket(push_pull[1]) == ('', expected)


def test_request_pusher_push_error(push_pull, pusher):
    """ Test the exception handling when emitting and receiving a message through the RequestPusher. """
    push_pull[0].close()
    pusher.send_check_instance('10.0.0.1')
    assert InternalCommReceiver.read_socket(push_pull[1]) is None


def test_internal_com(supvisors, internal_com):
    """ Test the Supvisors internal communications in one single test. """
    assert isinstance(internal_com.pusher, RequestPusher)
    assert internal_com.pusher.socket is internal_com.pusher_sock
    assert internal_com.emitter is None
    assert internal_com.receiver is None
    # test internal sockets
    # send the message and check its reception
    msg = b'1234'
    buffer = len(msg).to_bytes(4, 'big') + msg
    internal_com.pusher.socket.send(buffer)
    assert InternalCommReceiver.read_socket(internal_com.puller_sock) == ('', 1234)
    # test empty check_intf
    internal_com.check_intf([])
    # test close without emitter set
    internal_com.stop()
    with pytest.raises(OSError):
        internal_com.pusher.socket.send(buffer)
    # mock emitter and receiver
    internal_com.emitter = Mock(**{'close.return_value': None})
    internal_com.receiver = Mock(**{'close.return_value': None})
    # test close without emitter set
    internal_com.stop()
    with pytest.raises(OSError):
        internal_com.pusher.socket.send(buffer)
    assert internal_com.emitter.close.called
    assert not internal_com.receiver.close.called


def test_internal_com_creation(supvisors):
    """ Test the factory of Supvisors internal communications. """
    from supvisors.supvisorsmulticast import SupvisorsMulticast
    from supvisors.supvisorspubsub import SupvisorsPubSub
    # by default, no supvisors_list and no multicast_address
    # Publish / Subscribe is the fallback com mode
    instance = create_internal_comm(supvisors)
    instance.stop()
    assert isinstance(instance, SupvisorsPubSub)
    # create a supvisors_list to get a Publish / Subscribe
    supvisors.options.supvisors_list = list(supvisors.supvisors_mapper.instances.keys())
    instance = create_internal_comm(supvisors)
    instance.stop()
    assert isinstance(instance, SupvisorsPubSub)
    # use multicast configuration to get a Multicast
    supvisors.options.multicast_group = '239.0.0.1', 7777
    instance = create_internal_comm(supvisors)
    instance.stop()
    assert isinstance(instance, SupvisorsMulticast)
