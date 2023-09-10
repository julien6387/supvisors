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

import asyncio
from enum import Enum
from socket import socket

from supervisor.loggers import Logger

from supvisors.ttypes import NameList
from .internalinterface import bytes_to_payload, payload_to_bytes, read_stream


# Enumeration for deferred XML-RPC requests
class DeferredRequestHeaders(Enum):
    """ Enumeration class for the headers of deferred XML-RPC messages sent to MainLoop. """
    (CHECK_INSTANCE, ISOLATE_INSTANCES, CONNECT_INSTANCE,
     START_PROCESS, STOP_PROCESS,
     RESTART, SHUTDOWN, RESTART_SEQUENCE, RESTART_ALL, SHUTDOWN_ALL) = range(10)


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

    def send_connect_instance(self, identifier: str) -> None:
        """ Send request to connect a Supvisors instance when in discovery mode.

        :param identifier: the identifier of the Supvisors instance to connect
        :return: None
        """
        self.push_message(DeferredRequestHeaders.CONNECT_INSTANCE, (identifier,))

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
            msg_as_bytes = await read_stream(reader)
            if msg_as_bytes is None:
                self.logger.info(f'RequestAsyncPuller.handle_puller: failed to read the message from RequestPusher')
                break
            elif not msg_as_bytes:
                self.logger.blather(f'RequestAsyncPuller.handle_puller: nothing to read from RequestPusher')
            else:
                # push the decoded message to queue
                await self.queue.put(bytes_to_payload(msg_as_bytes))
        # close the stream writer
        writer.close()
        self.logger.debug(f'RequestAsyncPuller.handle_puller: exit RequestPusher')
