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
import select
import struct
import time
import traceback
from enum import Enum
from socket import error, socket, socketpair, AF_INET, SOCK_STREAM, SOL_SOCKET, SO_LINGER, SO_REUSEADDR, SHUT_RDWR
from threading import Event, Thread
from typing import Any, Dict, Optional, List

from supervisor.loggers import Logger

from supvisors.ttypes import InternalEventHeaders, Ipv4Address, NameList, Payload
from .internalinterface import (InternalCommEmitter, ASYNC_TIMEOUT,
                                bytes_to_payload, payload_to_bytes, read_from_socket, read_stream)
from .mapper import SupvisorsInstanceId

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


# Publisher part
#   done in Sync to work in Supervisor thread
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
        self.poller.register(sock, select.POLLIN)

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
            if event & select.POLLIN:
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
            self.last_send_heartbeat_time = current_time
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

    def emit_message(self, event_type: Enum, event_body: Payload) -> None:
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


# Subscriber part
#   done in Async as working in Supvisors thread
class InternalAsyncSubscriber:
    """ Class for subscribing to Supervisor events. """

    def __init__(self, instance_id: SupvisorsInstanceId,
                 queue: asyncio.Queue, stop_event: asyncio.Event,
                 logger: Logger):
        """ Initialization of the attributes.

        :param instance_id: the identification structure of the publisher to connect.
        :param queue: the queue used to push the messages received.
        :param stop_event: the flag to stop the task.
        :param logger: the Supvisors logger.
        """
        self.instance_id: SupvisorsInstanceId = instance_id
        self.queue: asyncio.Queue = queue
        self.stop_event: asyncio.Event = stop_event
        self.logger: Logger = logger

    @property
    def identifier(self) -> str:
        """ Shortcut to the identifier of the remote Supvisors instance. """
        return self.instance_id.identifier

    @property
    def ip_address(self) -> str:
        """ Shortcut to the IP address of the remote Supvisors instance. """
        return self.instance_id.ip_address

    @property
    def port(self) -> int:
        """ Shortcut to the port of the remote Supvisors instance. """
        return self.instance_id.internal_port

    async def send_heartbeat(self, writer: asyncio.StreamWriter) -> None:
        """ Send a heartbeat message to the publisher.

        :return: None
        """
        message = payload_to_bytes(InternalEventHeaders.HEARTBEAT, (self.identifier,))
        buffer = len(message).to_bytes(4, 'big') + message
        writer.write(buffer)
        await writer.drain()

    async def handle_subscriber(self):
        """ Handle the lifecycle of the TCP connection with the publisher.

        :return: None
        """
        self.logger.debug(f'InternalAsyncSubscriber.handle_subscriber: connecting to {self.identifier}'
                          f' at {self.ip_address}:{self.port}')
        # connect the publisher
        reader, writer = await asyncio.wait_for(asyncio.open_connection(self.ip_address, self.port), ASYNC_TIMEOUT)
        # the publisher is connected
        self.logger.info(f'InternalAsyncSubscriber.handle_subscriber: {self.identifier} connected')
        peer_name = writer.get_extra_info('peername')
        last_hb_recv: float = time.time()
        last_hb_sent: float = 0.0
        # loop until requested to stop, publisher closed or error happened
        while not self.stop_event.is_set() and not reader.at_eof():
            current_time: float = time.time()
            # read the message
            message = await read_stream(reader)
            if message is None:
                self.logger.info('InternalAsyncSubscriber.handle_subscriber: failed to read the message'
                                 f' from {self.identifier}')
                break
            elif not message:
                self.logger.trace(f'InternalAsyncSubscriber.handle_subscriber: nothing to read from {self.identifier}')
            else:
                # process the received message
                msg_type, msg_body = message
                if msg_type == InternalEventHeaders.HEARTBEAT.value:
                    self.logger.trace('InternalAsyncSubscriber.handle_subscriber: heartbeat received'
                                      f' from {self.identifier}')
                    last_hb_recv = current_time
                    # NOTE: at the moment, Supvisors still relies on the TICK to identify a node disconnection
                    #  if more reactivity is needed at some point, the HEARTBEAT could be used and pushed to the queue
                else:
                    # post to queue
                    await self.queue.put((peer_name, message))
            # manage heartbeat emission
            if current_time - last_hb_sent > HEARTBEAT_PERIOD:
                await self.send_heartbeat(writer)
                self.logger.trace(f'InternalAsyncSubscriber.handle_subscriber: heartbeat sent to {self.identifier}')
                last_hb_sent = current_time
            # manage heartbeat reception
            duration = current_time - last_hb_recv
            if duration > HEARTBEAT_TIMEOUT:
                self.logger.warn('InternalAsyncSubscriber.handle_subscriber: no heartbeat received'
                                 f' from {self.identifier} since {duration:.0f} seconds')
                break
        # close the stream writer
        writer.close()

    async def auto_connect(self):
        """ Auto-reconnection to the Publisher. """
        while not self.stop_event.is_set():
            try:
                await self.handle_subscriber()
            except asyncio.TimeoutError:
                self.logger.trace(f'InternalAsyncSubscriber.auto_connect: failed to connect {self.identifier}')
            except ConnectionResetError:
                self.logger.warn(f'InternalAsyncSubscriber.auto_connect: {self.identifier} closed the connection')
            except OSError:
                # OSError takes all other ConnectionError exceptions
                self.logger.debug(f'InternalAsyncSubscriber.auto_connect: connection to {self.identifier} refused')
            else:
                # the subscriber has ended
                self.logger.warn(f'InternalAsyncSubscriber.auto_connect: connection to {self.identifier} closed')
            await asyncio.sleep(2.0)
        self.logger.debug(f'InternalAsyncSubscriber.auto_connect: exit {self.identifier} auto-connect')


class InternalAsyncSubscribers:
    """ This class creates all the tasks that connect to the publishers of the remote Supvisors instances. """

    def __init__(self, queue: asyncio.Queue, stop_event: asyncio.Event, supvisors: Any):
        """ Initialization of the attributes. """
        self.supvisors = supvisors
        self.queue: asyncio.Queue = queue
        self.global_stop_event: asyncio.Event = stop_event
        # create a stop event per subscriber to enable selective stop
        self.stop_events: Dict[str, asyncio.Event] = {}

    def get_coroutines(self) -> List:
        """ Return the subscriber tasks:
            - one per remote Supvisors instance to connect ;
            - one to forward the general stop event.

        NOTE: the local Supvisors instance is not considered.
        """
        identifiers = list(self.supvisors.supvisors_mapper.instances.keys())
        # remove the local Supvisors instance from the list as it will receive events directly
        identifiers.remove(self.supvisors.supvisors_mapper.local_identifier)
        # return the coroutines
        return [self.create_coroutine(identifier) for identifier in identifiers] + [self.check_stop()]

    def create_coroutine(self, identifier: str):
        """ Create a task for a given remote Supvisors instance.

        :param identifier: the identifier structure of the remote Supvisors instance.
        :return:
        """
        instance_id = self.supvisors.supvisors_mapper.instances[identifier]
        self.stop_events[identifier] = stop_event = asyncio.Event()
        subscriber = InternalAsyncSubscriber(instance_id, self.queue, stop_event, self.supvisors.logger)
        return subscriber.auto_connect()

    async def check_stop(self):
        """ Task that waits for the general event to be set and that forwards it to all the subscriber tasks. """
        await self.global_stop_event.wait()
        for event in self.stop_events.values():
            event.set()

    def disconnect_subscribers(self, identifiers: NameList) -> None:
        """ Terminate the corresponding InternalAsyncSubscriber coroutines.

        :param identifiers: the identifiers of the Supvisors instances to disconnect
        :return: None
        """
        for identifier in identifiers:
            event = self.stop_events.get(identifier)
            if event:
                event.set()
                del self.stop_events[identifier]
