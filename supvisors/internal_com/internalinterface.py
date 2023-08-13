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
from socket import socket
from typing import Optional, List, Tuple

from supervisor.loggers import Logger

from supvisors.ttypes import InternalEventHeaders, Payload, NameList

# timeout for polling, in milliseconds
POLL_TIMEOUT = 100

# timeout for async operations, in seconds
ASYNC_TIMEOUT = 1.0

# Chunk size to read a socket
BUFFER_SIZE = 4096


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


def read_from_socket(sock: socket, msg_size: int) -> bytes:
    """ Receive a message from a TPC or UNIX socket.

    :param sock: the TCP or UNIX socket
    :param msg_size: the message size
    :return: the message, as bytes
    """
    message_parts = []
    to_read = msg_size
    while to_read > 0:
        buffer = sock.recv(min(BUFFER_SIZE, to_read))
        message_parts.append(buffer)
        to_read -= len(buffer)
    return b''.join(message_parts)


# Enumeration for deferred XML-RPC requests
class DeferredRequestHeaders(Enum):
    """ Enumeration class for the headers of deferred XML-RPC messages sent to MainLoop. """
    (CHECK_INSTANCE, ISOLATE_INSTANCES,
     START_PROCESS, STOP_PROCESS,
     RESTART, SHUTDOWN, RESTART_SEQUENCE, RESTART_ALL, SHUTDOWN_ALL) = range(9)


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


class RequestPusher:
    """ Class for pushing deferred XML-RPC.

    Attributes:
        - logger: a reference to the Supvisors logger ;
        - socket: the push socket.
    """

    def __init__(self, sock: socket, logger: Logger) -> None:
        """ Initialization of the attributes.

        :param sock: the socket used to push messages
        :param logger: the Supvisors logger
        """
        self.logger = logger
        self.socket = sock

    def push_message(self, *event) -> None:
        """ Serialize the event and send it to the socket.

        :param event: the event to send, as a tuple
        :return: None
        """
        # format the event into a message
        message = payload_to_bytes(*event)
        buffer = len(message).to_bytes(4, 'big') + message
        # send the message bytes
        try:
            self.socket.sendall(buffer)
        except OSError:
            self.logger.error(f'RequestPusher.send_message: failed to send message type={event[0].name}')

    def send_check_instance(self, identifier: str) -> None:
        """ Send request to check authorization to deal with the Supvisors instance.

        :param identifier: the identifier of the Supvisors instance to check
        :return: None
        """
        self.push_message(DeferredRequestHeaders.CHECK_INSTANCE, (identifier,))

    def send_isolate_instances(self, identifiers: NameList) -> None:
        """ Send request to isolate instances.

        :param identifiers: the identifiers of the Supvisors instances to isolate
        :return: None
        """
        self.push_message(DeferredRequestHeaders.ISOLATE_INSTANCES, tuple(identifiers))

    def send_start_process(self, identifier: str, namespec: str, extra_args: str) -> None:
        """ Send request to start process.

        :param identifier: the identifier of the Supvisors instance where the process has to be started
        :param namespec: the process namespec
        :param extra_args: the additional arguments to be passed to the command line
        :return: None
        """
        self.push_message(DeferredRequestHeaders.START_PROCESS, (identifier, namespec, extra_args))

    def send_stop_process(self, identifier: str, namespec: str) -> None:
        """ Send request to stop process.

        :param identifier: the identifier of the Supvisors instance where the process has to be stopped
        :param namespec: the process namespec
        :return: None
        """
        self.push_message(DeferredRequestHeaders.STOP_PROCESS, (identifier, namespec))

    def send_restart(self, identifier: str):
        """ Send request to restart a Supervisor.

        :param identifier: the identifier of the Supvisors instance where Supvisors has to be restarted
        :return: None
        """
        self.push_message(DeferredRequestHeaders.RESTART, (identifier,))

    def send_shutdown(self, identifier: str):
        """ Send request to shut down a Supervisor.

        :param identifier: the identifier of the Supvisors instance where Supvisors has to be shut down
        :return: None
        """
        self.push_message(DeferredRequestHeaders.SHUTDOWN, (identifier,))

    def send_restart_sequence(self, identifier: str):
        """ Send request to trigger the DEPLOYMENT phase.

        :param identifier: the Master Supvisors instance
        :return: None
        """
        self.push_message(DeferredRequestHeaders.RESTART_SEQUENCE, (identifier,))

    def send_restart_all(self, identifier: str):
        """ Send request to restart Supvisors.

        :param identifier: the Master Supvisors instance
        :return: None
        """
        self.push_message(DeferredRequestHeaders.RESTART_ALL, (identifier,))

    def send_shutdown_all(self, identifier: str):
        """ Send request to shut down Supvisors.

        :param identifier: the Master Supvisors instance
        :return: None
        """
        self.push_message(DeferredRequestHeaders.SHUTDOWN_ALL, (identifier,))


async def read_stream(reader: asyncio.StreamReader) -> Optional[List]:
    """ Read a message from an asyncio StreamReader.

    :param reader: the type of the event to send
    :return: None if reader is closed, empty list if nothing to read, or the 2-parts message
    """
    try:
        # read the message size
        msg_size_as_bytes = await asyncio.wait_for(reader.readexactly(4), 1.0)
    except asyncio.TimeoutError:
        # nothing to read
        return []
    except asyncio.IncompleteReadError:
        # socket closed during read operation read interruption
        return None
    # decode the message size
    msg_size = int.from_bytes(msg_size_as_bytes, byteorder='big')
    try:
        # read the message itself
        msg_as_bytes = await asyncio.wait_for(reader.readexactly(msg_size), 1.0)
    except (asyncio.TimeoutError, asyncio.IncompleteReadError):
        # unexpected message without body or socket closed during read operation
        return None
    # return the decoded message
    return bytes_to_payload(msg_as_bytes)


class RequestAsyncPuller:
    """ Class for pulling deferred XML-RPC using the asynchronous event loop.

    Attributes:
        - puller_sock: the pull socket ;
        - queue: the asynchronous queue used to store events pulled ;
        - stop_event: the termination event ;
        - logger: a reference to the Supvisors logger.
    """

    def __init__(self, queue: asyncio.Queue, stop_event: asyncio.Event, supvisors):
        """ Initialization of the attributes. """
        self.puller_sock: socket = supvisors.internal_com.puller_sock
        self.queue: asyncio.Queue = queue
        self.stop_event: asyncio.Event = stop_event
        self.logger: Logger = supvisors.logger

    async def handle_puller(self):
        """ The main coroutine in charge of receiving messages from the RequestPusher. """
        self.logger.debug(f'RequestAsyncPuller.handle_puller: connecting RequestPusher')
        # connect the RequestPusher
        reader, writer = await asyncio.open_unix_connection(sock=self.puller_sock)
        self.logger.info(f'RequestAsyncPuller.handle_puller: connected')
        # loop until requested to stop, publisher closed or error happened
        while not self.stop_event.is_set() and not reader.at_eof():
            # read the message
            message = await read_stream(reader)
            if message is None:
                self.logger.info(f'RequestAsyncPuller.handle_puller: failed to read the message from RequestPusher')
                break
            elif not message:
                self.logger.trace(f'RequestAsyncPuller.handle_puller: nothing to read from RequestPusher')
            else:
                # push the message to queue
                await self.queue.put(message)
        # close the stream writer
        writer.close()
        self.logger.debug(f'RequestAsyncPuller.handle_puller: exit RequestPusher')
