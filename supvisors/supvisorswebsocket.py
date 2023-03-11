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
import json
from typing import Dict, Set

import websockets
from supervisor.loggers import Logger

from .eventinterface import EventPublisherInterface, EventSubscriber, AsyncEventThread
from .supvisorsmapper import SupvisorsInstanceId
from .ttypes import Payload, EventHeaders

# additional annotation types
WebSocketSubscriptions = Dict[websockets.WebSocketServerProtocol, Set[EventHeaders]]

# the websocket subscriptions
websocket_clients: WebSocketSubscriptions = {}


# Server part
async def ws_handler(websocket: websockets.WebSocketServerProtocol):
    """ Manage websocket client subscriptions. """
    websocket_clients[websocket] = set()
    # manage subscriptions
    subscription_headers = [elt for elt in websocket.path.split('/') if elt]
    all_subscriptions = 'all' in subscription_headers
    for header in EventHeaders:
        if all_subscriptions or header.value in subscription_headers:
            websocket_clients[websocket].add(header)
    # wait until socket is closed (detected by the internal heartbeat)
    await websocket.wait_closed()
    # remove the websocket from the active connections
    del websocket_clients[websocket]


async def ws_server(stop_evt: asyncio.Event, node_name: str, event_port: int):
    """ Run the websocket service until a stop event is received. """
    async with websockets.serve(ws_handler, node_name, event_port, reuse_address=True) as server:
        await stop_evt.wait()
    await server.wait_closed()


class WsEventPublisher(EventPublisherInterface):
    """ Class for websockets publication of Supvisors events. """

    def __init__(self, instance: SupvisorsInstanceId, logger: Logger):
        """ Initialization of the attributes.

        :param instance: the local Supvisors instance identification.
        :param logger: the Supvisors logger.
        """
        self.logger: Logger = logger
        logger.info(f'WsEventPublisher: initiating Websocket event publisher on {instance.event_port}')
        # use binding on all interfaces
        self.thread: AsyncEventThread = AsyncEventThread(ws_server, '', instance.event_port)
        self.thread.start()

    def close(self) -> None:
        """ Close the Websocket.

        :return: None
        """
        self.thread.stop()
        self.thread.join()

    def send_supvisors_status(self, status: Payload) -> None:
        """ Send a JSON-serialized supvisors status through the socket.

        :param status: the status to publish.
        :return: None.
        """
        self.logger.trace(f'WsEventPublisher.send_supvisors_status: {status}')
        clients = [ws for ws, subscriptions in websocket_clients.items()
                   if EventHeaders.SUPVISORS in subscriptions]
        websockets.broadcast(clients, json.dumps((EventHeaders.SUPVISORS.value, status)))

    def send_instance_status(self, status: Payload) -> None:
        """ Send a JSON-serialized Supvisors instance status through the socket.

        :param status: the status to publish.
        :return: None.
        """
        self.logger.trace(f'WsEventPublisher.send_instance_status: {status}')
        clients = [ws for ws, subscriptions in websocket_clients.items()
                   if EventHeaders.INSTANCE in subscriptions]
        websockets.broadcast(clients, json.dumps((EventHeaders.INSTANCE.value, status)))

    def send_application_status(self, status: Payload) -> None:
        """ Send a JSON-serialized application status through the socket.

        :param status: the status to publish.
        :return: None.
        """
        self.logger.trace(f'WsEventPublisher.send_application_status: {status}')
        clients = [ws for ws, subscriptions in websocket_clients.items()
                   if EventHeaders.APPLICATION in subscriptions]
        websockets.broadcast(clients, json.dumps((EventHeaders.APPLICATION.value, status)))

    def send_process_event(self, identifier: str, event: Payload) -> None:
        """ Send a JSON-serialized process event through the socket.

        :param identifier: the identifier used to identify the origin of the event.
        :param event: the event to publish.
        :return: None.
        """
        # build the event before it is sent
        evt = event.copy()
        evt['identifier'] = identifier
        self.logger.trace(f'WsEventPublisher.send_process_event: {evt}')
        clients = [ws for ws, subscriptions in websocket_clients.items()
                   if EventHeaders.PROCESS_EVENT in subscriptions]
        websockets.broadcast(clients, json.dumps((EventHeaders.PROCESS_EVENT.value, evt)))

    def send_process_status(self, status: Payload) -> None:
        """ This method sends a serialized form of the process status through the socket.

        :param status: the status to publish.
        :return: None.
        """
        self.logger.trace(f'WsEventPublisher.send_process_status: {status}')
        clients = [ws for ws, subscriptions in websocket_clients.items()
                   if EventHeaders.PROCESS_STATUS in subscriptions]
        websockets.broadcast(clients, json.dumps((EventHeaders.PROCESS_STATUS.value, status)))

    def send_host_statistics(self, statistics: Payload) -> None:
        """ This method sends host statistics through the socket.

        :param statistics: the statistics to publish.
        :return: None.
        """
        self.logger.trace(f'WsEventPublisher.send_host_statistics: {statistics}')
        clients = [ws for ws, subscriptions in websocket_clients.items()
                   if EventHeaders.HOST_STATISTICS in subscriptions]
        websockets.broadcast(clients, json.dumps((EventHeaders.HOST_STATISTICS.value, statistics)))

    def send_process_statistics(self, statistics: Payload) -> None:
        """ This method sends process statistics through the socket.

        :param statistics: the statistics to publish.
        :return: None;
        """
        self.logger.trace(f'WsEventPublisher.send_process_statistics: {statistics}')
        clients = [ws for ws, subscriptions in websocket_clients.items()
                   if EventHeaders.PROCESS_STATISTICS in subscriptions]
        websockets.broadcast(clients, json.dumps((EventHeaders.PROCESS_STATISTICS.value, statistics)))


# Subscriber part
class WsEventSubscriber(EventSubscriber):
    """ The WsEventSubscriber wraps the websocket that connects to Supvisors.

    The WsEventSubscriber requires:
        - an implementation of the event subscriber interface,
        - the event port number used by Supvisors to publish its events,
        - a logger.
    """

    # timeout to avoid blocking receptions
    RecvTimeout = 0.5

    async def mainloop(self, stop_evt: asyncio.Event, node_name: str, event_port: int) -> None:
        """ Infinite loop as a websocket client.

        :return: None.
        """
        headers = 'all' if self.all_subscriptions() else '/'.join(self.headers)
        uri = f'ws://{node_name}:{event_port}/{headers}'
        while not stop_evt.is_set():
            # open the websocket connection
            self.logger.debug(f'WsEventSubscriber: connecting {uri}')
            async with websockets.connect(uri) as ws:
                self.logger.info(f'WsEventSubscriber.mainloop: Websocket connected on {uri}')
                try:
                    while not stop_evt.is_set():
                        try:
                            # recv in wait_for so that stop_event can be checked periodically
                            message = await asyncio.wait_for(ws.recv(), timeout=WsEventSubscriber.RecvTimeout)
                        except asyncio.exceptions.TimeoutError:
                            self.logger.trace(f'WsEventSubscriber.mainloop: receive timeout on {uri}')
                            continue
                        # a message has been received
                        header, body = json.loads(message)
                        try:
                            self.on_receive(header, body)
                        except ValueError:
                            self.logger.error(f'WsEventSubscriber.mainloop: unexpected header={header}')
                    self.logger.debug(f'WsEventSubscriber.mainloop: exiting Websocket connection on {uri}')
                except websockets.ConnectionClosed:
                    self.logger.warn(f'WsEventSubscriber.mainloop: Websocket server connection closed from {uri}')
                # close the websocket connection
                self.logger.debug(f'WsEventSubscriber.mainloop: close Websocket connection on {uri}')
                await ws.close()
        self.logger.debug('WsEventSubscriber.mainloop: exiting Websocket connection loop')
