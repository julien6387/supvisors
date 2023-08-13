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

from socket import socketpair

import pytest

from supvisors.internal_com.internalinterface import *


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


def test_deferred_request_headers():
    """ Test the DeferredRequestHeaders enumeration. """
    expected = ['CHECK_INSTANCE', 'ISOLATE_INSTANCES', 'START_PROCESS', 'STOP_PROCESS', 'RESTART', 'SHUTDOWN',
                'RESTART_SEQUENCE', 'RESTART_ALL', 'SHUTDOWN_ALL']
    assert [x.name for x in DeferredRequestHeaders] == expected


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


@pytest.fixture
def push_pull():
    """ Return a pair of sockets to be used for Push / Pull. """
    return socketpair()


def test_read_stream_header_timeout(push_pull):
    """ Test the read_stream coroutine / timeout when reading header. """
    async def read_test():
        reader, _ = await asyncio.open_unix_connection(sock=push_pull[0])
        assert await read_stream(reader) == []

    async def write_test():
        await asyncio.open_unix_connection(sock=push_pull[1])
        await asyncio.sleep(1.5)

    all_tasks = asyncio.gather(read_test(), write_test())
    asyncio.get_event_loop().run_until_complete(all_tasks)


def test_read_stream_incomplete_header(push_pull):
    """ Test the read_stream coroutine / incomplete header. """
    async def read_test():
        reader, _ = await asyncio.open_unix_connection(sock=push_pull[0])
        assert await read_stream(reader) is None

    async def write_test():
        _, writer = await asyncio.open_unix_connection(sock=push_pull[1])
        writer.write(b'foo')
        await writer.drain()
        writer.close()

    all_tasks = asyncio.gather(read_test(), write_test())
    asyncio.get_event_loop().run_until_complete(all_tasks)


def test_read_stream_body_timeout(push_pull):
    """ Test the read_stream coroutine / timeout when reading body. """
    async def read_test():
        reader, _ = await asyncio.open_unix_connection(sock=push_pull[0])
        assert await read_stream(reader) is None

    async def write_test():
        _, writer = await asyncio.open_unix_connection(sock=push_pull[1])
        writer.write(int.to_bytes(4, 4, byteorder='big'))
        await writer.drain()
        await asyncio.sleep(1.5)

    all_tasks = asyncio.gather(read_test(), write_test())
    asyncio.get_event_loop().run_until_complete(all_tasks)


def test_read_stream_incomplete_body(push_pull):
    """ Test the read_stream coroutine / incomplete body. """
    async def read_test():
        reader, _ = await asyncio.open_unix_connection(sock=push_pull[0])
        assert await read_stream(reader) is None

    async def write_test():
        _, writer = await asyncio.open_unix_connection(sock=push_pull[1])
        writer.write(int.to_bytes(4, 4, byteorder='big'))
        writer.write(b'foo')
        await writer.drain()
        writer.close()

    all_tasks = asyncio.gather(read_test(), write_test())
    asyncio.get_event_loop().run_until_complete(all_tasks)


def test_read_stream_correct(push_pull):
    """ Test the read_stream coroutine / correct message. """
    async def read_test():
        reader, _ = await asyncio.open_unix_connection(sock=push_pull[0])
        assert await read_stream(reader) == 'dummy'

    async def write_test():
        _, writer = await asyncio.open_unix_connection(sock=push_pull[1])
        message = json.dumps('dummy').encode('utf-8')
        writer.write(len(message).to_bytes(4, byteorder='big'))
        writer.write(message)
        await writer.drain()
        writer.close()

    all_tasks = asyncio.gather(read_test(), write_test())
    asyncio.get_event_loop().run_until_complete(all_tasks)


def test_push_pull_end_event(supvisors, push_pull):
    """ Test the Push / Pull communication.
    Termination on event. """
    queue = asyncio.Queue()
    event = asyncio.Event()
    # create puller
    supvisors.internal_com.puller_sock = push_pull[1]
    puller = RequestAsyncPuller(queue, event, supvisors)

    async def pusher_task():
        """ test of the pusher """
        pusher = RequestPusher(push_pull[0], supvisors.logger)
        assert pusher.logger is supvisors.logger
        # test push CHECK_INSTANCE
        pusher.send_check_instance('10.0.0.1')
        # test push ISOLATE_INSTANCES
        pusher.send_isolate_instances(['10.0.0.1', '10.0.0.2'])
        # test push START_PROCESS
        pusher.send_start_process('10.0.0.1', 'group:name', 'extra args')
        # test push STOP_PROCESS
        pusher.send_stop_process('10.0.0.1', 'group:name')
        # test push RESTART
        pusher.send_restart('10.0.0.1')
        # test push SHUTDOWN
        pusher.send_shutdown('10.0.0.1')
        # test push RESTART_SEQUENCE
        pusher.send_restart_sequence('10.0.0.1')
        # test push RESTART_ALL
        pusher.send_restart_all('10.0.0.1')
        # test push SHUTDOWN_ALL
        pusher.send_shutdown_all('10.0.0.1')
        # test timeout on reception
        await asyncio.sleep(1.5)
        event.set()

    async def check_output():
        """ test of the puller output """
        # test subscribe CHECK_INSTANCE
        expected = [DeferredRequestHeaders.CHECK_INSTANCE.value, ['10.0.0.1', ]]
        assert await asyncio.wait_for(queue.get(), 1.0) == expected
        # test subscribe ISOLATE_INSTANCES
        expected = [DeferredRequestHeaders.ISOLATE_INSTANCES.value, ['10.0.0.1', '10.0.0.2']]
        assert await asyncio.wait_for(queue.get(), 1.0) == expected
        # test subscribe START_PROCESS
        expected = [DeferredRequestHeaders.START_PROCESS.value, ['10.0.0.1', 'group:name', 'extra args']]
        assert await asyncio.wait_for(queue.get(), 1.0) == expected
        # test subscribe STOP_PROCESS
        expected = [DeferredRequestHeaders.STOP_PROCESS.value, ['10.0.0.1', 'group:name']]
        assert await asyncio.wait_for(queue.get(), 1.0) == expected
        # test subscribe RESTART
        expected = [DeferredRequestHeaders.RESTART.value, ['10.0.0.1', ]]
        assert await asyncio.wait_for(queue.get(), 1.0) == expected
        # test subscribe SHUTDOWN
        expected = [DeferredRequestHeaders.SHUTDOWN.value, ['10.0.0.1', ]]
        assert await asyncio.wait_for(queue.get(), 1.0) == expected
        # test subscribe RESTART_SEQUENCE
        expected = [DeferredRequestHeaders.RESTART_SEQUENCE.value, ['10.0.0.1', ]]
        assert await asyncio.wait_for(queue.get(), 1.0) == expected
        # test subscribe RESTART_ALL
        expected = [DeferredRequestHeaders.RESTART_ALL.value, ['10.0.0.1', ]]
        assert await asyncio.wait_for(queue.get(), 1.0) == expected
        # test subscribe SHUTDOWN_ALL
        expected = [DeferredRequestHeaders.SHUTDOWN_ALL.value, ['10.0.0.1', ]]
        assert await asyncio.wait_for(queue.get(), 1.0) == expected

    # handle_puller can loop forever, so add a wait_for just in case something goes wrong
    all_tasks = asyncio.gather(pusher_task(),
                               asyncio.wait_for(puller.handle_puller(), 5.0),
                               check_output())
    asyncio.get_event_loop().run_until_complete(all_tasks)


def test_push_pull_end_eof(supvisors, push_pull):
    """ Test the Push / Pull communication.
    Termination on EOF. """
    queue = asyncio.Queue()
    event = asyncio.Event()
    # create puller
    supvisors.internal_com.puller_sock = push_pull[1]
    puller = RequestAsyncPuller(queue, event, supvisors)

    async def pusher_task():
        """ test of the pusher """
        pusher = RequestPusher(push_pull[0], supvisors.logger)
        assert pusher.logger is supvisors.logger
        # test push CHECK_INSTANCE
        pusher.send_check_instance('10.0.0.1')
        push_pull[0].close()

    # handle_puller can loop forever, so add a wait_for just in case something goes wrong
    all_tasks = asyncio.gather(pusher_task(),
                               asyncio.wait_for(puller.handle_puller(), 2.0))
    asyncio.get_event_loop().run_until_complete(all_tasks)


def test_push_pull_end_error(supvisors, push_pull):
    """ Test the Push / Pull communication.
    Termination on reading error. """
    queue = asyncio.Queue()
    event = asyncio.Event()
    # create puller
    supvisors.internal_com.puller_sock = push_pull[1]
    puller = RequestAsyncPuller(queue, event, supvisors)

    async def pusher_task():
        """ test of the pusher """
        # send incomplete header
        push_pull[0].sendall(int.to_bytes(4, 4, byteorder='big'))
        push_pull[0].sendall(b'foo')

    # handle_puller can loop forever, so add a wait_for just in case something goes wrong
    all_tasks = asyncio.gather(pusher_task(),
                               asyncio.wait_for(puller.handle_puller(), 5.0))
    asyncio.get_event_loop().run_until_complete(all_tasks)


def test_push_error(supvisors, push_pull):
    """ Test the RequestPusher / push_message exception management.
    The aim is to hit the lines 197-198.
    Check OK with debugger. """
    pusher = RequestPusher(push_pull[0], supvisors.logger)
    push_pull[0].close()
    pusher.send_shutdown('10.0.0.1')
