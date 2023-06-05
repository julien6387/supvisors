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

import json
import select
from enum import Enum
from socket import error, socket, socketpair
from typing import Any, Optional, List, Tuple

from supervisor.loggers import Logger

from .ttypes import DeferredRequestHeaders, Ipv4Address, Payload, NameList

# timeout for polling, in milliseconds
POLL_TIMEOUT = 100

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


class InternalCommEmitter:
    """ Interface for the emission of Supervisor events. """

    def close(self) -> None:
        """ Close the resources used.

        :return: None
        """
        raise NotImplementedError

    def send_tick_event(self, payload: Payload) -> None:
        """ Send the tick event.

        :param payload: the tick to send
        :return: None
        """
        raise NotImplementedError

    def send_process_state_event(self, payload: Payload) -> None:
        """ Send the process state event.

        :param payload: the process state to send
        :return: None
        """
        raise NotImplementedError

    def send_process_added_event(self, payload: Payload) -> None:
        """ Send the process added event.

        :param payload: the added process to send
        :return: None
        """
        raise NotImplementedError

    def send_process_removed_event(self, payload: Payload) -> None:
        """ Send the process removed event.

        :param payload: the removed process to send
        :return: None
        """
        raise NotImplementedError

    def send_process_disability_event(self, payload: Payload) -> None:
        """ Send the process disability event.

        :param payload: the enabled/disabled process to send
        :return: None
        """
        raise NotImplementedError

    def send_host_statistics(self, payload: Payload) -> None:
        """ Send the host statistics.

        :param payload: the statistics to send
        :return: None
        """
        raise NotImplementedError

    def send_process_statistics(self, payload: Payload) -> None:
        """ Send the process statistics.

        :param payload: the statistics to send
        :return: None
        """
        raise NotImplementedError

    def send_state_event(self, payload: Payload) -> None:
        """ Send the Master state event.

        :param payload: the Supvisors state to send
        :return: None
        """
        raise NotImplementedError


class InternalCommReceiver:
    """ Interface for the reception of Supervisor events. """

    # additional annotation types
    PollinResult = Tuple[bool, List[int]]  # (puller_sock, [other_socks])

    def __init__(self, puller_sock: socket, logger: Logger):
        """ Create the multicast reception and the poller.

        :param puller_sock: the socket pair end used to receive the deferred Supvisors XML-RPC results
        """
        self.puller_sock: socket = puller_sock
        self.logger = logger
        # get list of readers for select
        self.poller = select.poll()
        self.poller.register(self.puller_sock, select.POLLIN)

    def close(self) -> None:
        """ Close the resources used.
        Should be called only from the SupvisorsMainLoop.

        :return: None
        """
        self.poller.unregister(self.puller_sock)
        self.puller_sock.close()

    def poll(self) -> PollinResult:
        """ Poll the sockets during POLL_TIMEOUT milliseconds.

        :return: a list of sockets ready for reading
        """
        puller_event = False
        fds = []
        # poll the sockets registered
        events = self.poller.poll(POLL_TIMEOUT)
        # check for the readable sockets
        for fd, event in events:
            if event & select.POLLIN:
                if fd == self.puller_sock.fileno():
                    puller_event = True
                else:
                    fds.append(fd)
        return puller_event, fds

    def read_puller(self) -> List:
        """ Read the message received on the puller socket. """
        return self.read_socket(self.puller_sock)[1]

    def read_fds(self, fds) -> List[Tuple[Ipv4Address, Payload]]:
        """ Read the messages received on the file descriptors. """
        return []

    def manage_heartbeat(self) -> None:
        """ Check heartbeat reception from publishers and send heartbeat to them.

        :return: None
        """

    def disconnect_subscriber(self, identifiers: NameList) -> None:
        """ Disconnect forever the Supvisors instances from the subscription socket.

        :param identifiers: the identifiers of the Supvisors instances to disconnect
        :return: None
        """

    @staticmethod
    def read_socket(sock: socket) -> Optional[Tuple[Ipv4Address, List]]:
        """ Return the message received on the socket.
        ONLY valid for TCP and UNIX sockets.

        :param sock: the socket to read
        :return: the message received
        """
        try:
            msg_size_as_bytes = sock.recv(4)
            msg_size = int.from_bytes(msg_size_as_bytes, byteorder='big')
            if msg_size > 0:
                msg_as_bytes = read_from_socket(sock, msg_size)
                return sock.getpeername(), bytes_to_payload(msg_as_bytes)
        except error:
            # failed to read from socket
            pass
        return None


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


class SupvisorsInternalComm:
    """ Base class for Supvisors internal communication.

    The push / pull sockets are used to defer XML-RPC to the Supvisors thread.
    The emitter / receiver protocol will be defined in inherited classes. """

    def __init__(self, supvisors: Any) -> None:
        """ Construction of all communication blocks.

        :param supvisors: the Supvisors global structure
        """
        # create socket pairs for the deferred requests
        self.pusher_sock, self.puller_sock = socketpair()
        # create the pusher used to detach the XML-RPC requests from the Supervisor Thread
        # events will be received in the receiver
        self.pusher = RequestPusher(self.pusher_sock, supvisors.logger)
        # declare the emitter and receiver instances
        self.emitter: Optional[InternalCommEmitter] = None
        self.receiver: Optional[InternalCommReceiver] = None

    def stop(self) -> None:
        """ Close all sockets.
        Should be called only from the Supervisor thread.

        :return: None
        """
        if self.emitter:
            self.emitter.close()
        self.pusher_sock.close()
        # WARN: do NOT close receiver and puller_sock as it will be done from the Supvisors thread (mainloop.py)


def create_internal_comm(supvisors: Any) -> Optional[SupvisorsInternalComm]:
    """ Create the relevant internal publisher in accordance with the option selected.

    :param supvisors: the global Supvisors instance
    :return: the internal publisher instance
    """
    publisher_instance = None
    publisher_class = None
    if supvisors.options.discovery_mode:
        # create a Multicast factory
        from supvisors.supvisorsmulticast import SupvisorsMulticast
        supvisors.logger.info('create_internal_publisher: using UDP Multicast for internal communications')
        publisher_class = SupvisorsMulticast
    else:
        # no need to check for supvisors_list as this is the fallback com
        # get a Publish / Subscribe factory
        from supvisors.supvisorspubsub import SupvisorsPubSub
        supvisors.logger.info('create_internal_publisher: using TCP Publish-Subscribe for internal communications')
        publisher_class = SupvisorsPubSub
    # create the publisher instance
    if publisher_class:
        publisher_instance = publisher_class(supvisors)
    return publisher_instance
