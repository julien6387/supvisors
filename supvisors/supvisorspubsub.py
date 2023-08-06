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

import select
import struct
import time
import traceback
from enum import Enum
from socket import error, socket, socketpair, AF_INET, SOCK_STREAM, SOL_SOCKET, SO_LINGER, SO_REUSEADDR, SHUT_RDWR
from threading import Event, Thread
from typing import Any, Dict, Optional, List, Tuple

from supervisor.loggers import Logger

from .internalinterface import (InternalCommEmitter, InternalCommReceiver, SupvisorsInternalComm,
                                bytes_to_payload, payload_to_bytes, read_from_socket)
from .supvisorsmapper import SupvisorsInstanceId
from .ttypes import InternalEventHeaders, Ipv4Address, NameList

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
BUFFER_SIZE = 4096


class SubscriberClient:
    """ Simple structure for a connected TCP client. """

    def __init__(self, sock: socket, addr: Ipv4Address):
        """ Store attributes and configure the socket. """
        self.socket: socket = sock
        self.addr: Ipv4Address = addr
        self.identifier: Optional[str] = None
        self.last_recv_heartbeat_time: float = time.time()
        # set the SO_LINGER option on the socket to avoid TIME_WAIT sockets
        sock.setsockopt(SOL_SOCKET, SO_LINGER, struct.pack('ii', 1, 0))
        # non-blocking socket
        sock.setblocking(False)

    @property
    def fd(self) -> int:
        return self.socket.fileno()

    def __str__(self) -> str:
        """ ID shortcut for logs. """
        return self.identifier if self.identifier else f'{self.addr[0]}:{self.addr[1]}'


class PublisherServer(Thread):
    """ Publisher thread of the simple Publish / Subscribe implementation.
    It creates the server side of the TCP connection.
    A heartbeat is added both ways for robustness. """

    def __init__(self, identifier: str, port: int, logger: Logger):
        """ Configure the TCP server socket.
        The Publisher publishes the internal events to multiple clients. """
        super().__init__(daemon=True)
        self.identifier = identifier
        self.logger: Logger = logger
        # create a poller to select incoming messages from all sockets
        self.poller = select.poll()
        # publication FIFO using UNIX sockets
        self.put_sock: Optional[socket] = None
        self.get_sock: Optional[socket] = None
        # bind the TCP server socket
        self.server: Optional[socket] = None
        self._bind(port)
        # heartbeat emission
        self.last_send_heartbeat_time: float = 0.0
        self.heartbeat_message = payload_to_bytes(InternalEventHeaders.HEARTBEAT, (self.identifier, {}))
        # List of TCP clients
        self.clients: Dict[int, SubscriberClient] = {}  # {fd: subscriber}
        # create an event to stop the thread
        self.stop_event: Event = Event()

    def _bind(self, port: int) -> None:
        """ Bind the server socket """
        self.logger.debug(f'PublisherServer._bind: binding localhost:{port}')
        try:
            sock = socket(AF_INET, SOCK_STREAM)
            sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
            sock.setblocking(False)
            sock.bind(('', port))
        except OSError:
            self.logger.critical(f'PublisherServer._bind: failed to bind the Supvisors publisher on port {port}')
            self.logger.debug(f'PublisherServer._bind: {traceback.format_exc()}')
        else:
            # assign the server socket when all went well and register it in the poller
            self.logger.info(f'PublisherServer._bind: localhost:{port} success')
            self.server = sock
            self.poller.register(self.server, select.POLLIN)
            # create the UNIX sockets as an internal FIFO and register the reception socket in the poller
            self.put_sock, self.get_sock = socketpair()
            self.poller.register(self.get_sock, select.POLLIN)

    def stop(self) -> None:
        """ Stop the PublisherServer when close is called.

        :return: None
        """
        if self.server:
            self.logger.debug('PublisherServer.stop: requesting publisher server to stop')
            self.stop_event.set()
            self.join()
            self.put_sock.close()
            self.logger.debug('PublisherServer.stop: publisher server stopped')

    def run(self) -> None:
        """ Main loop to accept TCP clients.
        A dedicated thread is started for every TCP client connection. """
        self.logger.info(f'PublisherServer.run: entering main loop')
        if self.server:
            # start to listen for clients
            self.server.listen()
            # start the heartbeat counter
            self.last_send_heartbeat_time = time.time()
            # wait for new clients until stop event is received
            while not self.stop_event.is_set():
                # poll the sockets registered
                events = self.poller.poll(POLL_TIMEOUT)
                self._handle_events(events)
                # manage heartbeat emission and reception
                self._manage_heartbeats()
            # close all sockets when exiting the loop
            self._close_sockets()
        self.logger.info(f'PublisherServer.run: exiting main loop')

    def _close_sockets(self):
        """ Close all sockets.

        :return: None
        """
        # close all TCP client sockets
        for client in self.clients.values():
            client.socket.close()
        # close the internal socket
        self.get_sock.close()
        # close the TCP server socket
        # as it will be reused, shut it down properly before
        self.server.shutdown(SHUT_RDWR)
        self.server.close()

    def _add_client(self, sock: socket, addr: Ipv4Address) -> None:
        """ Add a new TCP client to the publisher.

        :param sock: the client socket
        :param addr: the client address
        :return: None
        """
        self.clients[sock.fileno()] = SubscriberClient(sock, addr)
        self.logger.debug(f'PublisherThread._add_client: new subscriber client accepted from {addr}')
        # register the client socket into the poller
        self.poller.register(sock, select.POLLIN | select.POLLHUP)

    def _remove_client(self, fd):
        """ Remove a TCP client from the subscribers.

        :param fd: the descriptor of the client socket
        :return: None
        """
        self.poller.unregister(fd)
        client = self.clients.pop(fd)
        client.socket.close()
        self.logger.debug(f'PublisherServer._remove_client: client={str(client)} closed')

    def _handle_events(self, events):
        """ Extract the messages from the readable sockets.

        :return: None
        """
        for fd, event in events:
            # first get socket closure on client sockets
            if event & select.POLLHUP:
                if fd in self.clients:
                    # other end has closed. unregister and close too
                    self._remove_client(fd)
            elif event & select.POLLIN:
                if fd == self.server.fileno():
                    # got a new client to accept
                    try:
                        self._add_client(*self.server.accept())
                    except OSError:
                        # expected when socket has been closed
                        self.logger.debug('PublisherServer._handle_events: failed accepting a new client')
                elif fd == self.get_sock.fileno():
                    # got something to forward to all clients
                    self._forward_message()
                elif fd in self.clients:
                    # only heartbeats are expected from clients
                    self._receive_client_heartbeat(fd)

    def _forward_message(self) -> None:
        """ Forward the encoded message in the internal socket to all TCP clients.

        :return: None
        """
        msg_size_as_bytes = self.get_sock.recv(4)
        msg_size = int.from_bytes(msg_size_as_bytes, byteorder='big')
        self.logger.trace(f'PublisherServer._forward_message: message received {msg_size} bytes')
        if msg_size == 0:
            # very unlikely from internal UNIX socket
            # critical error. internal UNIX socket is broken. cannot go on
            self.logger.critical('PublisherServer._forward_message: internal socket error - empty message')
            self.stop_event.set()
        else:
            msg_body = read_from_socket(self.get_sock, msg_size)
            self._publish_message(msg_body)

    def _receive_client_heartbeat(self, fd):
        """ Store the reception time of the client heartbeat.

        :param fd: the descriptor of the client socket
        :return: None
        """
        client = self.clients[fd]
        msg_size = int.from_bytes(client.socket.recv(4), byteorder='big')
        self.logger.trace(f'PublisherServer._receive_client_heartbeat: message received {msg_size} bytes')
        if msg_size == 0:
            self.logger.warn(f'PublisherServer._receive_client_heartbeat: empty message from {str(client)}')
            self._remove_client(fd)
        else:
            # read the socket message
            msg_as_bytes = read_from_socket(client.socket, msg_size)
            if not client.identifier:
                # optional decoding to get the identifier corresponding to the socket
                msg_type, msg_body = bytes_to_payload(msg_as_bytes)
                if msg_type == InternalEventHeaders.HEARTBEAT.value:
                    old_id = str(client)
                    client.identifier = msg_body[0]
                    self.logger.trace(f'PublisherServer._receive_client_heartbeat: client {old_id} identified'
                                      f' as {str(client)}')
            # reset the clock everytime anything happens on the socket
            client.last_recv_heartbeat_time = time.time()

    def _manage_heartbeats(self) -> None:
        """ Send a periodic heartbeat to all TCP clients.
        Check the heartbeat reception from the TCP clients. """
        current_time = time.time()
        # check heartbeat emission
        if current_time - self.last_send_heartbeat_time > HEARTBEAT_PERIOD:
            self._publish_message(self.heartbeat_message)
            self.last_snd_heartbeat_time = current_time
            self.logger.trace(f'PublisherServer._manage_heartbeat: heartbeat emitted at {current_time}')
        # check heartbeat reception
        for client in list(self.clients.values()):
            duration = current_time - client.last_recv_heartbeat_time
            if duration > HEARTBEAT_TIMEOUT:
                self.logger.trace(f'PublisherServer._manage_heartbeat: no heartbeat received from {str(client)}'
                                  f' for {duration:.2f} seconds')
                self._remove_client(client.fd)

    def _publish_message(self, message: bytes) -> None:
        """ Send the message to all TCP clients.

        :param message: the message as bytes
        :return: None
        """
        # prepare the buffer to send by prepending its length
        buffer = len(message).to_bytes(4, 'big') + message
        # send the message to all clients
        for client in list(self.clients.values()):
            try:
                client.socket.sendall(buffer)
            except error:
                # upon message send exception, remove the client from the clients list
                self._remove_client(client.fd)


class InternalPublisher(PublisherServer, InternalCommEmitter):
    """ Class for publishing Supervisor events. """

    def close(self) -> None:
        """ Close the resources used.

        :return: None
        """
        self.stop()

    def emit_message(self, event_type: Enum, event_body: Any) -> None:
        """ Encode and forward the event to the Publisher thread using the FIFO.

        :param event_type: the type of the event to send
        :param event_body: the body of the event to send
        :return: None
        """
        if self.put_sock:
            # encode the message
            message = payload_to_bytes(event_type, (self.identifier, event_body))
            # prepare the buffer to send by prepending its length
            buffer = len(message).to_bytes(4, 'big') + message
            # send the message to the publication thread
            try:
                self.put_sock.sendall(buffer)
            except error as exc:
                # critical error. cannot go on
                self.logger.critical(f'PublisherServer.publish: internal socket error - {str(exc)}')
                self.stop()


class ClientConnectionThread(Thread):

    def __init__(self, instance: SupvisorsInstanceId, internal_subscriber):
        super().__init__(daemon=True)
        self.identifier = instance.identifier
        self.address = instance.host_id, instance.internal_port
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
                    self.internal_subscriber.poller.register(sock, select.POLLIN)
            time.sleep(1)


class InternalSubscriber(InternalCommReceiver):
    """ Class for sockets used from the Supvisors thread. """

    def __init__(self, puller_sock: socket, supvisors: Any) -> None:
        """ Create the sockets and the poller.

        :param puller_sock: the socket pair end used to receive the deferred Supvisors XML-RPC results
        :param supvisors: the Supvisors global structure
        """
        super().__init__(puller_sock, supvisors.logger)
        self.identifier: str = supvisors.supvisors_mapper.local_identifier
        # subscriber sockets are TCP clients so connection is to be dealt on-the-fly
        self.instances = supvisors.supvisors_mapper.instances.copy()
        self.subscribers: Dict[str, List] = {}  # {identifier: [socket, hb_sent, hb_recv]}
        # start connections threads
        for instance in self.instances.values():
            ClientConnectionThread(instance, self).start()

    def close(self) -> None:
        """ Close the subscribers sockets.
        Should be called only from the SupvisorsMainLoop.

        :return: None
        """
        super().close()
        for sock, _, _ in self.subscribers.values():
            self.poller.unregister(sock)
            sock.close()
        # TODO: add join on ClientConnectionThread ?

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

    def read_fds(self, fds: List[int]) -> List[Tuple[Ipv4Address, List]]:
        """ Read the messages from the subscriber sockets.
        Disconnect the erroneous sockets.

        :param fds: the file descriptors of the sockets to read
        :return: the messages received
        """
        messages = []
        for identifier, (sock, _, _) in self.subscribers.copy().items():
            if sock.fileno() in fds:
                message = InternalCommReceiver.read_socket(sock)
                if message:
                    # update heartbeat reception time on subscriber
                    peer, (msg_type, msg_body) = message
                    if msg_type == InternalEventHeaders.HEARTBEAT.value:
                        self.subscribers[identifier][2] = time.time()
                    # store message in list
                    messages.append(message)
                else:
                    # message of 0 or negative size. socket closed
                    self.close_subscriber(identifier)
        return messages

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


class SupvisorsPubSub(SupvisorsInternalComm):
    """ Class holding all structures used for Supvisors internal communication
    using a TCP Publish-Subscribe custom pattern. """

    def __init__(self, supvisors: Any) -> None:
        """ Construction of all communication blocks.

        :param supvisors: the Supvisors global structure
        """
        super().__init__(supvisors)
        # create the publisher
        self._start_publisher()
        # create the global subscriber that receives deferred XML-RPC requests and events sent by all publishers
        self.receiver = InternalSubscriber(self.puller_sock, supvisors)
        # store network interface names
        self.intf_names: List[str] = []

    def check_intf(self, intf_names: List[str]):
        """ Restart the Publisher when a new network interfaces is added. """
        if self.intf_names:
            # check if there's a new network interface
            new_intf_names = [x for x in intf_names if x not in self.intf_names]
            if new_intf_names:
                if self.emitter:
                    self.supvisors.logger.warn('SupvisorsPubSub.restart: publisher restart'
                                               f' due to new network interfaces {new_intf_names}')
                    self.emitter.close()
                # create a new publisher
                self._start_publisher()
        # store current list
        self.intf_names = intf_names

    def _start_publisher(self):
        """ Start the Publisher thread. """
        local_instance: SupvisorsInstanceId = self.supvisors.supvisors_mapper.local_instance
        self.emitter = InternalPublisher(local_instance.identifier,
                                         local_instance.internal_port,
                                         self.supvisors.logger)
        self.emitter.start()
