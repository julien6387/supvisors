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
