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

import asyncio
import json
from enum import Enum
from typing import List, Optional, Tuple

from supvisors.ttypes import InternalEventHeaders, Payload

# timeout for async operations, in seconds
ASYNC_TIMEOUT = 1.0


# Common functions
def payload_to_bytes(msg_type: Enum, payload: Tuple) -> bytes:
    """ Use a JSON serialization and encode the message with UTF-8.

    :param msg_type: the message type
    :param payload: the message body
    :return: the message serialized and encoded, as bytes
    """
    return json.dumps((msg_type.value, payload)).encode('utf-8')


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


class InternalCommEmitter:
    """ Interface for the emission of Supervisor events. """

    def close(self) -> None:
        """ Close the resources used.

        :return: None
        """
        raise NotImplementedError

    def emit_message(self, event_type: Enum, event_body: Payload):
        """ Send the messages to the other Supvisors instances using the technology to be defined in subclasses.

        :param event_type: the type of the event to send
        :param event_body: the body of the event to send
        :return: None
        """
        raise NotImplementedError

    def send_tick_event(self, payload: Payload) -> None:
        """ Send the tick event.

        :param payload: the tick to send
        :return: None
        """
        self.emit_message(InternalEventHeaders.TICK, payload)

    def send_process_state_event(self, payload: Payload) -> None:
        """ Send the process state event.

        :param payload: the process state to send
        :return: None
        """
        self.emit_message(InternalEventHeaders.PROCESS, payload)

    def send_process_added_event(self, payload: Payload) -> None:
        """ Send the process added event.

        :param payload: the added process to send
        :return: None
        """
        self.emit_message(InternalEventHeaders.PROCESS_ADDED, payload)

    def send_process_removed_event(self, payload: Payload) -> None:
        """ Send the process removed event.

        :param payload: the removed process to send
        :return: None
        """
        self.emit_message(InternalEventHeaders.PROCESS_REMOVED, payload)

    def send_process_disability_event(self, payload: Payload) -> None:
        """ Send the process disability event.

        :param payload: the enabled/disabled process to send
        :return: None
        """
        self.emit_message(InternalEventHeaders.PROCESS_DISABILITY, payload)

    def send_host_statistics(self, payload: Payload) -> None:
        """ Send the host statistics.

        :param payload: the statistics to send
        :return: None
        """
        self.emit_message(InternalEventHeaders.HOST_STATISTICS, payload)

    def send_process_statistics(self, payload: Payload) -> None:
        """ Send the process statistics.

        :param payload: the statistics to send
        :return: None
        """
        self.emit_message(InternalEventHeaders.PROCESS_STATISTICS, payload)

    def send_state_event(self, payload: Payload) -> None:
        """ Send the Master state event.

        :param payload: the Supvisors state to send
        :return: None
        """
        self.emit_message(InternalEventHeaders.STATE, payload)

    def send_discovery_event(self, payload: Payload) -> None:
        """ Send the discovery event.

        :param payload: the discovery event to send
        :return: None
        """
        self.emit_message(InternalEventHeaders.DISCOVERY, payload)
