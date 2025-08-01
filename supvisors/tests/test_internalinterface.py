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


def test_payload_to_bytes_to_payload():
    """ Test the serialization and deserialization. """
    payload = 'a message source', {'body': 'a message body'}
    msg_bytes = payload_to_bytes(payload)
    assert isinstance(msg_bytes, bytes)
    assert bytes_to_payload(msg_bytes) == ['a message source', {'body': 'a message body'}]


@pytest.fixture
def push_pull():
    """ Return a pair of sockets to be used for Push / Pull. """
    return socketpair()


@pytest.mark.asyncio
async def test_read_stream_header_timeout(push_pull):
    """ Test the read_stream coroutine / timeout when reading header. """
    async def read_test():
        reader, _ = await asyncio.open_unix_connection(sock=push_pull[0])
        assert await read_stream(reader) == b''

    async def write_test():
        _, writer = await asyncio.open_unix_connection(sock=push_pull[1])
        await asyncio.sleep(1.5)

    await asyncio.gather(read_test(), write_test())


@pytest.mark.asyncio
async def test_read_stream_incomplete_header(push_pull):
    """ Test the read_stream coroutine / incomplete header. """
    async def read_test():
        reader, _ = await asyncio.open_unix_connection(sock=push_pull[0])
        assert await read_stream(reader) is None

    async def write_test():
        _, writer = await asyncio.open_unix_connection(sock=push_pull[1])
        writer.write(b'foo')
        await writer.drain()
        writer.close()

    await asyncio.gather(read_test(), write_test())


@pytest.mark.asyncio
async def test_read_stream_body_timeout(push_pull):
    """ Test the read_stream coroutine / timeout when reading body. """
    async def read_test():
        reader, _ = await asyncio.open_unix_connection(sock=push_pull[0])
        assert await read_stream(reader) is None

    async def write_test():
        _, writer = await asyncio.open_unix_connection(sock=push_pull[1])
        writer.write(int.to_bytes(0, 4, byteorder='big'))
        await writer.drain()
        await asyncio.sleep(1.5)

    await asyncio.gather(read_test(), write_test())


@pytest.mark.asyncio
async def test_read_stream_incomplete_body(push_pull):
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

    await asyncio.gather(read_test(), write_test())


@pytest.mark.asyncio
async def test_read_stream_correct(push_pull):
    """ Test the read_stream coroutine / correct message. """
    async def read_test():
        reader, _ = await asyncio.open_unix_connection(sock=push_pull[0])
        assert await read_stream(reader) == b'"dummy"'

    async def write_test():
        _, writer = await asyncio.open_unix_connection(sock=push_pull[1])
        message = json.dumps('dummy').encode('utf-8')
        assert await write_stream(writer, message)
        writer.close()
        # hit ConnectionResetError
        assert not await write_stream(writer, message)

    await asyncio.gather(read_test(), write_test())
