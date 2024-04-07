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
from socket import socket
from typing import Tuple

from supervisor.loggers import Logger

from supvisors.ttypes import InternalEventHeaders, RequestHeaders, PublicationHeaders, Payload
from .internalinterface import bytes_to_payload, payload_to_bytes, read_stream


class RpcPusher:
    """ Class for pushing deferred XML-RPC.

    Attributes:
        - supvisors: a reference to the Supvisors global structure ;
        - socket: the push socket.
    """

    def __init__(self, sock: socket, supvisors) -> None:
        """ Initialization of the attributes.

        :param sock: the socket used to push messages.
        :param supvisors: the Supvisors global structure.
        """
        self.supvisors = supvisors
        self.socket = sock

    @property
    def logger(self) -> Logger:
        """ Get the Supvisors logger. """
        return self.supvisors.logger

    def push_message(self, event_type: InternalEventHeaders, event_body: Tuple) -> None:
        """ Serialize the event and send it to the socket.

        :param event_type: the type of the event to send.
        :param event_body: the event to send.
        :return: None.
        """
        # format the event into a message
        message = payload_to_bytes((event_type.value, event_body))
        buffer = len(message).to_bytes(4, 'big') + message
        # send the message bytes
        try:
            self.socket.sendall(buffer)
        except OSError:
            self.logger.critical(f'RpcPusher.send_message: failed to send message={event_body}')

    # Deferred XML-RPC requests
    def push_request(self, request_type: RequestHeaders, request_body: Tuple) -> None:
        """ Serialize the event and send it to the socket.

        :param request_type: the type of the request to send.
        :param request_body: the request_body.
        :return: None
        """
        self.push_message(InternalEventHeaders.REQUEST, (request_type.value, request_body))

    def send_check_instance(self, identifier: str) -> None:
        """ Send request to check authorization to deal with the Supvisors instance.

        :param identifier: the identifier of the Supvisors instance to check
        :return: None
        """
        self.push_request(RequestHeaders.CHECK_INSTANCE, (identifier,))

    def send_start_process(self, identifier: str, namespec: str, extra_args: str) -> None:
        """ Send request to start process.

        :param identifier: the identifier of the Supvisors instance where the process has to be started
        :param namespec: the process namespec
        :param extra_args: the additional arguments to be passed to the command line
        :return: None
        """
        self.push_request(RequestHeaders.START_PROCESS, (identifier, namespec, extra_args))

    def send_stop_process(self, identifier: str, namespec: str) -> None:
        """ Send request to stop process.

        :param identifier: the identifier of the Supvisors instance where the process has to be stopped
        :param namespec: the process namespec
        :return: None
        """
        self.push_request(RequestHeaders.STOP_PROCESS, (identifier, namespec))

    def send_restart(self, identifier: str):
        """ Send request to restart a Supervisor.

        :param identifier: the identifier of the Supvisors instance where Supvisors has to be restarted
        :return: None
        """
        self.push_request(RequestHeaders.RESTART, (identifier,))

    def send_shutdown(self, identifier: str):
        """ Send request to shut down a Supervisor.

        :param identifier: the identifier of the Supvisors instance where Supvisors has to be shut down
        :return: None
        """
        self.push_request(RequestHeaders.SHUTDOWN, (identifier,))

    def send_restart_sequence(self, identifier: str):
        """ Send request to trigger the DEPLOYMENT phase.

        :param identifier: the Master Supvisors instance
        :return: None
        """
        self.push_request(RequestHeaders.RESTART_SEQUENCE, (identifier,))

    def send_restart_all(self, identifier: str):
        """ Send request to restart Supvisors.

        :param identifier: the Master Supvisors instance
        :return: None
        """
        self.push_request(RequestHeaders.RESTART_ALL, (identifier,))

    def send_shutdown_all(self, identifier: str):
        """ Send request to shut down Supvisors.

        :param identifier: the Master Supvisors instance
        :return: None
        """
        self.push_request(RequestHeaders.SHUTDOWN_ALL, (identifier,))

    # Publications
    def push_publication(self, publication_type: PublicationHeaders, publication_body: Payload) -> None:
        """ Serialize the event and send it to the socket.

        :param publication_type: the type of the publication to send.
        :param publication_body: the data to publish.
        :return: None
        """
        self.push_message(InternalEventHeaders.PUBLICATION, (publication_type.value, publication_body))

    def send_tick_event(self, payload: Payload) -> None:
        """ Send the tick event.

        :param payload: the tick to send.
        :return: None.
        """
        self.push_publication(PublicationHeaders.TICK, payload)

    def send_process_state_event(self, payload: Payload) -> None:
        """ Send the process state event.

        :param payload: the process state to send.
        :return: None.
        """
        self.push_publication(PublicationHeaders.PROCESS, payload)

    def send_process_added_event(self, payload: Payload) -> None:
        """ Send the process added event.

        :param payload: the added process to send.
        :return: None.
        """
        self.push_publication(PublicationHeaders.PROCESS_ADDED, payload)

    def send_process_removed_event(self, payload: Payload) -> None:
        """ Send the process removed event.

        :param payload: the removed process to send.
        :return: None.
        """
        self.push_publication(PublicationHeaders.PROCESS_REMOVED, payload)

    def send_process_disability_event(self, payload: Payload) -> None:
        """ Send the process disability event.

        :param payload: the enabled/disabled process to send.
        :return: None.
        """
        self.push_publication(PublicationHeaders.PROCESS_DISABILITY, payload)

    def send_host_statistics(self, payload: Payload) -> None:
        """ Send the host statistics.

        :param payload: the statistics to send.
        :return: None.
        """
        self.push_publication(PublicationHeaders.HOST_STATISTICS, payload)

    def send_process_statistics(self, payload: Payload) -> None:
        """ Send the process statistics.

        :param payload: the statistics to send.
        :return: None.
        """
        self.push_publication(PublicationHeaders.PROCESS_STATISTICS, payload)

    def send_state_event(self, payload: Payload) -> None:
        """ Send the Master state event.

        :param payload: the Supvisors state to send.
        :return: None.
        """
        self.push_publication(PublicationHeaders.STATE, payload)


class AsyncRpcPuller:
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
        self.supvisors = supvisors

    @property
    def logger(self) -> Logger:
        """ Shortcut to the Supvisors logger. """
        return self.supvisors.logger

    async def handle_puller(self):
        """ The main coroutine in charge of receiving messages from the RpcPusher. """
        self.logger.debug(f'AsyncRpcPuller.handle_puller: connecting RpcPusher')
        # connect the RequestPusher
        reader, writer = await asyncio.open_unix_connection(sock=self.puller_sock)
        self.logger.info(f'AsyncRpcPuller.handle_puller: connected')
        # loop until requested to stop, publisher closed or error happened
        while not self.stop_event.is_set() and not reader.at_eof():
            # read the message
            msg_as_bytes = await read_stream(reader)
            if msg_as_bytes is None:
                self.logger.info(f'AsyncRpcPuller.handle_puller: failed to read the message from RpcPusher')
                break
            elif not msg_as_bytes:
                self.logger.blather(f'AsyncRpcPuller.handle_puller: nothing to read from RpcPusher')
            else:
                # push the decoded message to queue
                await self.queue.put(bytes_to_payload(msg_as_bytes))
        # close the stream writer
        writer.close()
        self.logger.debug(f'AsyncRpcPuller.handle_puller: exit RequestPusher')
