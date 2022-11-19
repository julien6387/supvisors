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
import struct
import time
import traceback
from enum import Enum
from queue import Queue, Empty
from socket import error, socket, socketpair, AF_INET, SOCK_STREAM, SOL_SOCKET, SO_LINGER, SO_REUSEADDR, SHUT_RDWR
from threading import Event, Thread
from typing import Any, Dict, Optional, List, Tuple

from supervisor.loggers import Logger

from .supvisorsmapper import SupvisorsInstanceId
from .ttypes import DeferredRequestHeaders, InternalEventHeaders, Payload, NameList

# additional annotations
SocketList = List[socket]

# Heartbeat management, in seconds
HEARTBEAT_PERIOD = 2
HEARTBEAT_TIMEOUT = 10

# timeout for getting data from queue, in seconds
BLOCK_TIMEOUT = 0.5

# timeout for polling, in milliseconds
POLL_TIMEOUT = 100

# Chunk size to read a socket
BUFFER_SIZE = 2048


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
    """ Receive a message from a socket.

    :param sock: the TCP socket
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


class SubscriberInterface(Thread):
    """ Class used to exchange messages between a unique TCP client and the internal services. """

    def __init__(self, internal_sock: socket, client_sock: socket):
        """ Store the sockets used to exchange information.

        :param internal_sock: the internal publisher socket
        :param client_sock: the client subscriber socket
        """
        super().__init__(daemon=True)
        self.internal_sock: socket = internal_sock
        self.client_sock: socket = client_sock
        # create poller
        self.poller = select.poll()
        self.poller.register(self.internal_sock, select.POLLIN)
        self.poller.register(self.client_sock, select.POLLIN)
        # heartbeat management
        self.last_heartbeat_time = 0

    def run(self) -> None:
        """ Infinite main loop. """
        self.last_heartbeat_time = time.time()
        try:
            while True:
                # poll the sockets registered
                events = self.poller.poll(POLL_TIMEOUT)
                # sort the readable sockets
                for fd, event in events:
                    if event == select.POLLIN:
                        if fd == self.internal_sock.fileno():
                            self.read_internal_message()
                        elif fd == self.client_sock.fileno():
                            self.read_external_message()
                # check heartbeat reception from client
                duration = time.time() - self.last_heartbeat_time
                if duration > HEARTBEAT_TIMEOUT:
                    raise ConnectionError(f'no heartbeat received for {duration} seconds')
        except ConnectionError:
            # client connection closed (detected by the reception of a zero message size)
            # or no heartbeat received anymore
            self.internal_sock.close()
            self.client_sock.close()

    def read_internal_message(self):
        """ Read the internal socket and forward to the client subscriber. """
        msg_size_as_bytes = self.internal_sock.recv(4)
        msg_size = int.from_bytes(msg_size_as_bytes, byteorder='big')
        if msg_size == 0:
            raise ConnectionError(f'empty message')
        msg_body = read_from_socket(self.internal_sock, msg_size)
        self.client_sock.sendall(msg_size_as_bytes + msg_body)

    def read_external_message(self):
        """ Only heartbeat messages are expected. """
        msg_size = int.from_bytes(self.client_sock.recv(4), byteorder='big')
        if msg_size == 0:
            raise ConnectionError(f'incorrect message size {msg_size}')
        read_from_socket(self.client_sock, msg_size)
        # reset the clock everytime anything happens on the socket
        self.last_heartbeat_time = time.time()


class PublisherThread(Thread):
    """ Publisher thread of the simple Publish / Subscribe implementation.
    A heartbeat is added both ways for robustness. """

    def __init__(self, identifier: str):
        """ Initialization of the attributes. """
        super().__init__(daemon=True)
        self.identifier = identifier
        self.queue: Queue = Queue()
        # TCP clients list (mutex protection not needed due to the Python GIL)
        self.clients: List[socket] = []
        # create an event to stop the thread
        self.stop_event: Event = Event()
        # init heartbeat
        self.last_heartbeat_time = 0

    def stopping(self) -> bool:
        """ Access to the loop attribute (used to drive tests on run method).

        :return: the condition to stop the main loop
        """
        return self.stop_event.is_set()

    def add_client(self, sock: socket, *_) -> None:
        """ Add a new TCP client to the publisher.

        :param sock: the client socket
        :return: None
        """
        # set the SO_LINGER option on the socket to avoid TIME_WAIT sockets
        sock.setsockopt(SOL_SOCKET, SO_LINGER, struct.pack('ii', 1, 0))
        # create the message handler
        put_sock, get_sock = socketpair()
        SubscriberInterface(get_sock, sock).start()
        self.clients.append(put_sock)

    def run(self) -> None:
        """ Main loop dedicated to the emitting part.
        The reception part is only managed in the client sockets. """
        while not self.stopping():
            # blocking pop from internal queue
            try:
                message = self.queue.get(timeout=BLOCK_TIMEOUT)
            except Empty:
                message = None
            if not self.stopping():
                # manage heartbeat emission
                self._manage_heartbeat()
                # dispatch the message received to all clients
                if message:
                    self._publish_event(*message)
        # close all sockets
        for client in self.clients:
            client.close()

    def _manage_heartbeat(self) -> None:
        """ Send a periodic heartbeat to all clients. """
        current_time = time.time()
        if current_time - self.last_heartbeat_time > HEARTBEAT_PERIOD:
            self._publish_heartbeat()
            self.last_heartbeat_time = current_time

    def _publish_heartbeat(self) -> None:
        """ Send a heartbeat to all TCP clients.

        :return: None
        """
        message = payload_to_bytes(InternalEventHeaders.HEARTBEAT, (self.identifier, {}))
        self._publish_message(message)

    def _publish_event(self, event_type: Enum, event_body: Payload) -> None:
        """ Send the event to all TCP clients.

        :param event_type: the type of the event to send
        :param event_body: the body of the event to send
        :return: None
        """
        message = payload_to_bytes(event_type, (self.identifier, event_body))
        self._publish_message(message)

    def _publish_message(self, message: bytes) -> None:
        """ Send the message to all TCP clients.

        :param message: the message as bytes
        :return: None
        """
        # prepare the buffer to send by prepending its length
        buffer = len(message).to_bytes(4, 'big') + message
        # send the message to all clients
        for client in self.clients.copy():
            try:
                client.sendall(buffer)
            except error:
                # upon exception, remove the client from the clients list
                self.clients.remove(client)
                client.close()

    def stop(self):
        """ Send a stop event to this thread.

        :return: None
        """
        self.stop_event.set()


class PublisherServer(Thread):
    """ A generic TCP server allowing multiple clients. """

    def __init__(self, identifier: str, port: int, logger: Logger):
        """ Configure the TCP server socket.
        The Publisher publishes the internal events to multiple clients. """
        super().__init__(daemon=True)
        self.logger: Logger = logger
        # bind the TCP server socket
        self.server: Optional[socket] = None
        self._bind(port)
        # the following is done only if the server socket has bound
        if self.server:
            # start the Publisher thread that will publish to all registered clients
            self.publisher_thread: PublisherThread = PublisherThread(identifier)
            self.publisher_thread.start()
            # create an event to stop the thread
            self.stop_event: Event = Event()

    def publish(self, *event) -> None:
        """ Forward the event to the Publisher thread using the queue.

        :param event: the event to publish
        :return: None
        """
        if self.server:
            self.publisher_thread.queue.put(event)

    def _bind(self, port: int) -> None:
        """ Bind the server socket """
        self.logger.debug(f'PublisherServer._bind: binding localhost:{port}')
        try:
            sock = socket(AF_INET, SOCK_STREAM)
            sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
            sock.bind(('', port))
        except OSError:
            self.logger.critical(f'PublisherServer._bind: failed to bind the Supvisors publisher on port {port}')
            self.logger.debug(f'PublisherServer._bind: {traceback.format_exc()}')
        else:
            # assign the server socket when all went well
            self.server = sock

    def run(self) -> None:
        """ Main loop to accept TCP clients.
        A dedicated thread is started for every TCP client connection. """
        if self.server:
            self.server.listen()
            # wait for new clients until stop event is received
            while not self.stop_event.is_set():
                try:
                    self.publisher_thread.add_client(*self.server.accept())
                except OSError:
                    # expected when socket has been closed
                    pass

    def stop(self) -> None:
        """ Close the TCP server, stop this thread and the publisher thread.

        :return: None
        """
        if self.server:
            # stop this thread and close the TCP server socket
            self.logger.debug('PublisherServer.stop: stopping publisher server')
            self.stop_event.set()
            self.server.shutdown(SHUT_RDWR)
            self.server.close()
            self.join()
            self.logger.debug('PublisherServer.stop: publisher server stopped')
            # stop the publisher thread
            self.logger.debug('PublisherServer.stop: stopping publisher thread')
            self.publisher_thread.stop()
            self.publisher_thread.join()
            self.logger.debug('PublisherServer.stop: publisher thread stopped')


class InternalPublisher(PublisherServer):
    """ Class for publishing Supervisor events. """

    def send_tick_event(self, payload: Payload) -> None:
        """ Publish the tick event.

        :param payload: the tick to push
        :return: None
        """
        self.publish(InternalEventHeaders.TICK, payload)

    def send_process_state_event(self, payload: Payload) -> None:
        """ Publish the process state event.

        :param payload: the process state to publish
        :return: None
        """
        self.publish(InternalEventHeaders.PROCESS, payload)

    def send_process_added_event(self, payload: Payload) -> None:
        """ Publish the process added event.

        :param payload: the added process to publish
        :return: None
        """
        self.publish(InternalEventHeaders.PROCESS_ADDED, payload)

    def send_process_removed_event(self, payload: Payload) -> None:
        """ Publish the process removed event.

        :param payload: the removed process to publish
        :return: None
        """
        self.publish(InternalEventHeaders.PROCESS_REMOVED, payload)

    def send_process_disability_event(self, payload: Payload) -> None:
        """ Publish the process disability event.

        :param payload: the enabled/disabled process to publish
        :return: None
        """
        self.publish(InternalEventHeaders.PROCESS_DISABILITY, payload)

    def send_statistics(self, payload: Payload) -> None:
        """ Publish the statistics.

        :param payload: the statistics to publish
        :return: None
        """
        self.publish(InternalEventHeaders.STATISTICS, payload)

    def send_state_event(self, payload: Payload) -> None:
        """ Publish the Master state event.

        :param payload: the Supvisors state to publish
        :return: None
        """
        self.publish(InternalEventHeaders.STATE, payload)


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


class ClientConnectionThread(Thread):

    def __init__(self, instance: SupvisorsInstanceId, internal_subscriber):
        super().__init__(daemon=True)
        self.identifier = instance.identifier
        self.address = instance.host_name, instance.internal_port
        self.internal_subscriber = internal_subscriber

    def run(self):
        # connection loop
        while self.identifier in self.internal_subscriber.instances:
            if self.identifier not in self.internal_subscriber.subscribers:
                try:
                    sock = socket(AF_INET, SOCK_STREAM)
                    sock.connect(self.address)
                except OSError:
                    # failed to connect. will try next time
                    pass
                else:
                    # store socket and register to poller
                    self.internal_subscriber.subscribers[self.identifier] = [sock, 0, time.time()]
                    self.internal_subscriber.poller.register(sock, select.POLLIN | select.POLLERR)
            time.sleep(1)


class InternalSubscriber:
    """ Class for sockets used from the Supvisors thread. """

    # types for annotations
    SubscriberPollinResult = List[Tuple[str, socket]]  # [(identifier, subscriber_sock)]
    PollinResult = Tuple[socket, SubscriberPollinResult]  # (puller_sock, [(identifier, subscriber_sock)])

    def __init__(self, puller_sock: socket, supvisors: Any) -> None:
        """ Create the sockets and the poller.
        The Supervisor logger cannot be used here (not thread-safe).

        :param supvisors: the Supvisors global structure
        """
        self.identifier: str = supvisors.supvisors_mapper.local_identifier
        # create socket pairs for the communication from the Supervisor thread to the Supvisors thread
        self.puller_sock = puller_sock
        # subscriber sockets are TCP clients so connection is to be dealt on-the-fly
        self.instances = supvisors.supvisors_mapper.instances.copy()
        self.subscribers: Dict[str, List] = {}  # {identifier: [socket, hb_sent, hb_recv]}
        # get list of readers for select
        self.poller = select.poll()
        self.poller.register(self.puller_sock, select.POLLIN)
        # start connections threads
        for instance in self.instances.values():
            ClientConnectionThread(instance, self).start()

    def close(self) -> None:
        """ Close the puller, the publisher and the subscribers sockets.
        Should be called only from the SupvisorsMainLoop.

        :return: None
        """
        self.poller.unregister(self.puller_sock)
        self.puller_sock.close()
        for sock, _, _ in self.subscribers.values():
            self.poller.unregister(sock)
            sock.close()

    def manage_heartbeat(self) -> None:
        """ Check heartbeat reception from publishers and send heartbeat to them.

        :return: None
        """
        self._check_heartbeat()
        self._send_heartbeat()

    def _check_heartbeat(self) -> None:
        """ Close every subscriber socket where no heartbeat has been received for a long time.

        :return: None
        """
        current_time = time.time()
        for identifier, (_, _, hb_recv) in self.subscribers.copy().items():
            if current_time - hb_recv > HEARTBEAT_TIMEOUT:
                self.close_subscriber(identifier)

    def _send_heartbeat(self):
        """ Send a heartbeat message to all publishers connected.

        :return: None
        """
        current_time: float = time.time()
        for identifier, (sock, hb_sent, _) in self.subscribers.copy().items():
            if current_time - hb_sent > HEARTBEAT_PERIOD:
                # send the heartbeat
                message = payload_to_bytes(InternalEventHeaders.HEARTBEAT, (self.identifier,))
                buffer = len(message).to_bytes(4, 'big') + message
                try:
                    sock.sendall(buffer)
                except OSError:
                    self.close_subscriber(identifier)
                else:
                    # update the emission time
                    self.subscribers[identifier][1] = current_time

    def poll(self) -> PollinResult:
        """ Poll the sockets during POLL_TIMEOUT milliseconds.

        :return: a list of sockets ready for reading
        """
        event_puller, request_puller = None, None
        subscribers = []
        # poll the sockets registered
        events = self.poller.poll(POLL_TIMEOUT)
        # sort the readable and erroneous sockets
        for fd, event in events:
            # check for error
            if event & select.POLLERR:
                for identifier, (sock, _, _) in self.subscribers.copy().items():
                    if fd == sock.fileno():
                        self.close_subscriber(identifier)
            # check for input
            if event & select.POLLIN:
                if fd == self.puller_sock.fileno():
                    request_puller = self.puller_sock
                else:
                    for identifier, (sock, _, _) in self.subscribers.items():
                        if fd == sock.fileno():
                            subscribers.append((identifier, sock))
        return request_puller, subscribers

    def read_subscribers(self, identifier_socks: SubscriberPollinResult) -> List[Payload]:
        """ Read the messages from the subscriber sockets.
        Disconnect the erroneous sockets.

        :param identifier_socks: the sockets to read
        :return: the messages received
        """
        messages = []
        for identifier, sock in identifier_socks:
            try:
                message = InternalSubscriber.read_socket(sock)
                if message:
                    # update heartbeat reception time on subscriber
                    msg_type, msg_body = message
                    if msg_type == InternalEventHeaders.HEARTBEAT.value:
                        self.subscribers[identifier][2] = time.time()
                    # store message in list
                    messages.append(message)
            except error:
                # unregister and close the socket on error
                self.close_subscriber(identifier)
        return messages

    @staticmethod
    def read_socket(sock: socket) -> Payload:
        """ Return the message received on the socket.

        :param sock: the socket to read
        :return: the message received
        """
        msg_size_as_bytes = sock.recv(4)
        msg_size = int.from_bytes(msg_size_as_bytes, byteorder='big')
        if msg_size > 0:
            msg_as_bytes = read_from_socket(sock, msg_size)
            return bytes_to_payload(msg_as_bytes)
        return {}

    def close_subscriber(self, identifier: str) -> None:
        """ Close the subscriber socket corresponding to the identifier.

        :param identifier: the subscriber identifier
        :return: None
        """
        sock = self.subscribers.pop(identifier)[0]
        try:
            self.poller.unregister(sock)
        except ValueError:
            # if already closed, descriptor is -1
            pass
        sock.close()

    def disconnect_subscriber(self, identifiers: NameList) -> None:
        """ Disconnect forever the Supvisors instances from the subscription socket.

        :param identifiers: the identifiers of the Supvisors instances to disconnect
        :return: None
        """
        for identifier in identifiers:
            self.close_subscriber(identifier)
            del self.instances[identifier]


class SupvisorsSockets:
    """ Class holding all structures used for Supvisors internal communication and external events. """

    def __init__(self, supvisors: Any) -> None:
        """ Construction of all communication blocks.

        :param supvisors: the Supvisors global structure
        """
        # create socket pairs for the deferred requests
        pusher_sock, puller_sock = socketpair()
        # create the pusher used to detach the XML-RPC requests from the Supervisor Thread
        self.pusher = RequestPusher(pusher_sock, supvisors.logger)
        # create the Supvisors instance publisher and start it directly
        local_instance: SupvisorsInstanceId = supvisors.supvisors_mapper.local_instance
        self.publisher = InternalPublisher(local_instance.identifier, local_instance.internal_port, supvisors.logger)
        self.publisher.start()
        # create the global subscriber that receives deferred XML-RPC requests and events sent by all publishers
        self.subscriber = InternalSubscriber(puller_sock, supvisors)

    def stop(self) -> None:
        """ Close the pusher sockets.
        Should be called only from the Supervisor thread.

        :return: None
        """
        self.pusher.socket.close()
        self.publisher.stop()
