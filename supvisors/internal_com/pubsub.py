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
import threading
import time
import traceback
from enum import Enum
from socket import error, socketpair
from typing import Any, Dict, Optional, List

from supervisor.loggers import Logger

from supvisors.ttypes import InternalEventHeaders, Ipv4Address, NameList, Payload
from .internalinterface import (InternalCommEmitter, ASYNC_TIMEOUT,
                                bytes_to_payload, payload_to_bytes, read_stream, write_stream)
from .mapper import SupvisorsInstanceId

# Heartbeat management, in seconds
HEARTBEAT_PERIOD = 2
HEARTBEAT_TIMEOUT = 10


# Publisher part
class SubscriberClient:
    """ Simple structure for a connected TCP client. """

    def __init__(self, writer: asyncio.StreamWriter, heartbeat_message: bytes, logger: Logger):
        """ Store attributes and configure the socket. """
        self.writer: asyncio.StreamWriter = writer
        self.logger: Logger = logger
        self.addr: Ipv4Address = writer.get_extra_info('peername')
        self.identifier: Optional[str] = None
        # heartbeat part
        self.heartbeat_message: bytes = heartbeat_message
        self.last_recv_heartbeat_time: float = time.time()
        self.last_sent_heartbeat_time: float = 0.0

    def __str__(self) -> str:
        """ ID shortcut for logs. """
        return self.identifier if self.identifier else f'{self.addr[0]}:{self.addr[1]}'

    def process_heartbeat(self, msg_as_bytes: bytes):
        """ Reset the heartbeat reception time.

        :param msg_as_bytes: the heartbeat message as bytes.
        :return: None.
        """
        # optional decoding to get the identifier corresponding to the socket
        if not self.identifier:
            msg_type, msg_body = bytes_to_payload(msg_as_bytes)
            if msg_type == InternalEventHeaders.HEARTBEAT.value:
                self.identifier = msg_body[0]
                self.logger.info(f'SubscriberClient.process_heartbeat: client {self.addr} identified'
                                 f' as {self.identifier}')
        # reset the clock everytime anything happens on the socket
        self.last_recv_heartbeat_time = time.time()

    async def manage_heartbeat(self) -> bool:
        """ Manages the periodic heartbeat emission and check its reception.

        :return: True if heartbeat messages are still received periodically.
        """
        current_time: float = time.time()
        # check heartbeat emission
        if current_time - self.last_sent_heartbeat_time > HEARTBEAT_PERIOD:
            if not await write_stream(self.writer, self.heartbeat_message):
                return False
            self.last_sent_heartbeat_time = current_time
            self.logger.trace(f'SubscriberClient.manage_heartbeat: heartbeat emitted at {current_time} to {str(self)}')
        # check heartbeat reception
        duration = current_time - self.last_recv_heartbeat_time
        if duration > HEARTBEAT_TIMEOUT:
            self.logger.warn(f'SubscriberClient.handle_tcp_client: no heartbeat received from {str(self)}'
                             f' for {duration:.2f} seconds')
            return False
        return True


class PublisherServer(threading.Thread):
    """ Publisher thread of the simple Publish / Subscribe implementation.
    It creates the server side of the TCP connection.
    A heartbeat is added both ways for robustness. """

    def __init__(self, identifier: str, port: int, logger: Logger):
        """ Configure the TCP server socket.
        The Publisher publishes the internal events to multiple clients. """
        super().__init__(daemon=True)
        self.identifier = identifier
        self.logger: Logger = logger
        # publication FIFO using UNIX sockets
        self.put_sock, self.get_sock = socketpair()
        # the TCP server port and instance
        self.port: int = port
        self.server: Optional[asyncio.Server] = None
        # the list of TCP clients
        self.clients: List[SubscriberClient] = []
        # asyncio loop attributes
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.stop_event: Optional[asyncio.Event] = None
        # common heartbeat message
        self.heartbeat_message = payload_to_bytes(InternalEventHeaders.HEARTBEAT, (self.identifier, {}))

    def stop(self) -> None:
        """ The stop method is meant to be called from outside the async loop.
        This will stop all asynchronous tasks.

        :return: None
        """
        self.logger.debug(f'PublisherServer.stop: loop={self.loop} event={self.stop_event}')
        if self.loop and self.stop_event:
            # fire the event within the event loop
            async def stop_it() -> None:
                """ Set the Future stop_event to stop all asynchronous tasks. """
                self.stop_event.set()
                self.logger.debug('PublisherServer.stop: stop event set')
            asyncio.run_coroutine_threadsafe(stop_it(), self.loop).result()

    def run(self) -> None:
        """ Main loop to accept TCP clients.
        A dedicated thread is started for every TCP client connection. """
        self.logger.info('PublisherServer.run: entering main loop')
        # assign a new asynchronous event loop to this thread
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        # create the stop event
        self.stop_event = asyncio.Event()
        # define the tasks
        all_coro = ([self.open_supvisors_server(),
                     self.handle_publications()])
        all_tasks = asyncio.gather(*all_coro)
        # run the asynchronous event loop with the given tasks
        self.loop.run_until_complete(all_tasks)
        self.logger.info('PublisherServer.run: exiting main loop')
        self.loop.close()
        self.loop = None

    async def handle_publications(self):
        """ The coroutine in charge of receiving messages to be published. """
        self.logger.debug(f'PublisherServer.handle_publications: connecting internal UNIX socket')
        # connect the internal UNIX socket
        reader, writer = await asyncio.open_unix_connection(sock=self.get_sock)
        self.logger.debug('RequestAsyncPuller.handle_publications: connected')
        # loop until requested to stop or put_sock closed
        while not self.stop_event.is_set() and not reader.at_eof():
            # read the message
            msg_as_bytes = await read_stream(reader)
            if msg_as_bytes is None:
                self.logger.critical('PublisherServer.handle_publications: failed to read the internal message')
                self.stop_event.set()
            elif not msg_as_bytes:
                self.logger.blather('PublisherServer.handle_publications: nothing to read')
            else:
                # forward the message to all clients
                for client in self.clients.copy():
                    try:
                        await write_stream(client.writer, msg_as_bytes)
                    except OSError:
                        self.clients.remove(client)
                        client.writer.close()
        # close the stream writer
        writer.close()
        self.logger.debug('RequestAsyncPuller.handle_publications: exit')

    async def handle_supvisors_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """ Manage the Subscriber TCP client connection. """
        # push writer to clients list
        client = SubscriberClient(writer, self.heartbeat_message, self.logger)
        self.logger.info(f'PublisherServer.handle_supvisors_client: new client={str(client)}')
        self.clients.append(client)
        # loop until subscriber closed or stop event set
        while not self.stop_event.is_set() and not reader.at_eof():
            # read the message
            msg_as_bytes = await read_stream(reader)
            if msg_as_bytes is None:
                self.logger.error('PublisherServer.handle_supvisors_client: failed to read the message'
                                  f' from {self.identifier}')
                break
            elif not msg_as_bytes:
                self.logger.trace(f'PublisherServer.handle_supvisors_client: nothing to read from {self.identifier}')
            else:
                # a heartbeat message has been received
                client.process_heartbeat(msg_as_bytes)
            # send heartbeat if enough time has passed
            heartbeat_ok = await client.manage_heartbeat()
            if not heartbeat_ok:
                # exit the loop if heartbeat messages are not received anymore
                break
        # remove writer from clients list (if not already done by handle_publications)
        if client in self.clients:
            self.clients.remove(client)
            writer.close()
        self.logger.info(f'PublisherServer.handle_supvisors_client: done with client={str(client)}')

    async def open_supvisors_server(self):
        """ Start the TCP server for internal messages publication. """
        # bind the TCP server and give a chance to retry
        first_log: bool = True
        while not self.server and not self.stop_event.is_set():
            try:
                self.server = await asyncio.start_server(self.handle_supvisors_client, '', self.port)
                self.logger.info(f'PublisherServer.open_supvisors_server: local Supvisors server bound to {self.port}')
            except OSError:
                if first_log:
                    self.logger.critical('PublisherServer.open_supvisors_server: failed to bind local Supvisors server'
                                         f' to {self.port} (will retry)')
                    self.logger.debug(f'PublisherServer.open_supvisors_server: {traceback.format_exc()}')
                    first_log = False
                await asyncio.sleep(ASYNC_TIMEOUT)
        # either server has bound or stop event has been set
        if not self.stop_event.is_set():
            self.logger.debug('PublisherServer.open_supvisors_server: waiting for stop event')
            # wait until stop event is set
            await self.stop_event.wait()
        # close the server if it has been created
        if self.server:
            # wait until the server is really closed
            self.logger.debug('PublisherServer.open_supvisors_server: closing server')
            self.server.close()
            await self.server.wait_closed()
            # handle_supvisors_client tasks are not known by global run_until_complete
            # so wait here until these tasks exit
            self.logger.debug('PublisherServer.open_supvisors_server: waiting for client tasks to end')
            # NOTE: cannot use asyncio.wait(asyncio.all_tasks()) as not available in Python 3.6
            while self.clients:
                await asyncio.sleep(ASYNC_TIMEOUT)
        self.logger.debug('PublisherServer.open_supvisors_server: exiting')


class InternalPublisher(PublisherServer, InternalCommEmitter):
    """ Class for publishing Supervisor events.
    All messages are written to a UNIX socket.
    A thread with asynchronous tasks will read the UNIX socket and publish the message to all subscribers. """

    def close(self) -> None:
        """ Close the resources used.

        :return: None
        """
        if self.is_alive():
            self.logger.debug('InternalPublisher.close: requesting publisher server to stop')
            self.stop()
            self.join()
            self.logger.debug('InternalPublisher.close: publisher server stopped')

    def emit_message(self, event_type: Enum, event_body: Payload) -> None:
        """ Encode and forward the event to the Publisher thread using the FIFO.

        :param event_type: the type of the event to send
        :param event_body: the body of the event to send
        :return: None
        """
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
            msg_as_bytes = await read_stream(reader)
            if msg_as_bytes is None:
                self.logger.info('InternalAsyncSubscriber.handle_subscriber: failed to read the message'
                                 f' from {self.identifier}')
                break
            elif not msg_as_bytes:
                self.logger.trace('InternalAsyncSubscriber.handle_subscriber: nothing to read'
                                  f' from {self.identifier}')
            else:
                # process the received message
                message = bytes_to_payload(msg_as_bytes)
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
        identifiers = list(self.supvisors.mapper.instances.keys())
        # remove the local Supvisors instance from the list as it will receive events directly
        identifiers.remove(self.supvisors.mapper.local_identifier)
        # return the coroutines
        return [self.create_coroutine(identifier) for identifier in identifiers] + [self.check_stop()]

    def create_coroutine(self, identifier: str):
        """ Create a task for a given remote Supvisors instance.

        :param identifier: the identifier structure of the remote Supvisors instance.
        :return:
        """
        instance_id = self.supvisors.mapper.instances.get(identifier)
        if instance_id:
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
