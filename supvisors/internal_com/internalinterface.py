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

import asyncio
import json
from typing import List, Optional

# timeout for async operations, in seconds
ASYNC_TIMEOUT = 1.0


# Common functions
def payload_to_bytes(message) -> bytes:
    """ Use a JSON serialization and encode the message with UTF-8.

    :param message: the message to encode.
    :return: the message serialized and encoded, as bytes.
    """
    return json.dumps(message).encode('utf-8')


def bytes_to_payload(message: bytes) -> List:
    """ Decode and de-serialize the bytearray into a message header and body.

    :param message: the message as bytes
    :return: the message header and body
    """
    return json.loads(message.decode('utf-8'))


async def read_stream(reader: asyncio.StreamReader) -> Optional[bytes]:
    """ Read a message from an asyncio StreamReader.

    :param reader: the asyncio StreamReader.
    :return: None if reader is closed, empty bytes if nothing to read, or the message as bytes.
    """
    try:
        # read the message size
        msg_size_as_bytes = await asyncio.wait_for(reader.readexactly(4), 1.0)
    except asyncio.TimeoutError:
        # nothing to read
        return b''
    except (asyncio.IncompleteReadError, ConnectionResetError):
        # socket closed during read operation read interruption
        return None
    # decode the message size
    msg_size = int.from_bytes(msg_size_as_bytes, byteorder='big')
    if msg_size == 0:
        return None
    try:
        # read the message itself
        msg_as_bytes = await asyncio.wait_for(reader.readexactly(msg_size), 1.0)
    except (asyncio.TimeoutError, asyncio.IncompleteReadError, ConnectionResetError):
        # unexpected message without body or socket closed during read operation
        return None
    # return the non-decoded message
    return msg_as_bytes


async def write_stream(writer: asyncio.StreamWriter, msg_as_bytes: bytes) -> bool:
    """ Write a message to an asyncio StreamWriter.

    :param writer: the asyncio StreamReader.
    :param msg_as_bytes: the message as bytes.
    :return: True if no exception.
    """
    buffer = len(msg_as_bytes).to_bytes(4, 'big') + msg_as_bytes
    try:
        writer.write(buffer)
        await writer.drain()
    except ConnectionResetError:
        return False
    return True
