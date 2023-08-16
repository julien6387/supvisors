#!/usr/bin/python
# -*- coding: utf-8 -*-

# ======================================================================
# Copyright 2016 Julien LE CLEACH
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

import zmq
import zmq.asyncio
from supervisor.loggers import Logger

from supvisors.external_com.eventinterface import EventPublisherInterface, EventSubscriber, EventSubscriberInterface
from supvisors.internal_com.mapper import SupvisorsInstanceId
from supvisors.ttypes import Payload, EventHeaders

# Constant for Zmq sockets
ZMQ_LINGER = 0

# reference to the Zmq Context instance
ZmqContext = zmq.Context.instance()


class ZmqEventPublisher(EventPublisherInterface):
    """ Class for PyZmq publication of Supvisors events. """

    def __init__(self, instance: SupvisorsInstanceId, logger: Logger):
        """ Initialization of the attributes.

        :param instance: the local Supvisors instance identification
        :param logger: the Supvisors logger
        """
        self.logger: Logger = logger
        logger.info(f'ZmqEventPublisher: initiating PyZmq event publisher on {instance.event_port}')
        self.socket: zmq.Socket = ZmqContext.socket(zmq.PUB)
        url = f'tcp://0.0.0.0:{instance.event_port}'
        self.logger.debug(f'ZmqEventPublisher: binding {url}')
        self.socket.bind(url)

    def close(self) -> None:
        """ Close the PyZmq socket.

        :return: None
        """
        self.socket.close(ZMQ_LINGER)

    def send_supvisors_status(self, status: Payload) -> None:
        """ Send a JSON-serialized supvisors status through the socket.

        :param status: the status to publish
        :return: None
        """
        self.logger.trace(f'ZmqEventPublisher.send_supvisors_status: {status}')
        self.socket.send_string(EventHeaders.SUPVISORS.value, zmq.SNDMORE)
        self.socket.send_json(status)

    def send_instance_status(self, status: Payload) -> None:
        """ Send a JSON-serialized Supvisors instance status through the socket.

        :param status: the status to publish
        :return: None
        """
        self.logger.trace(f'ZmqEventPublisher.send_instance_status: {status}')
        self.socket.send_string(EventHeaders.INSTANCE.value, zmq.SNDMORE)
        self.socket.send_json(status)

    def send_application_status(self, status: Payload) -> None:
        """ Send a JSON-serialized application status through the socket.

        :param status: the status to publish
        :return: None
        """
        self.logger.trace(f'ZmqEventPublisher.send_application_status: {status}')
        self.socket.send_string(EventHeaders.APPLICATION.value, zmq.SNDMORE)
        self.socket.send_json(status)

    def send_process_event(self, identifier: str, event: Payload) -> None:
        """ Send a JSON-serialized process event through the socket.

        :param identifier: the identifier used to identify the origin of the event
        :param event: the event to publish
        :return: None
        """
        # build the event before it is sent
        evt = event.copy()
        evt['identifier'] = identifier
        self.logger.trace(f'ZmqEventPublisher.send_process_event: {evt}')
        self.socket.send_string(EventHeaders.PROCESS_EVENT.value, zmq.SNDMORE)
        self.socket.send_json(evt)

    def send_process_status(self, status: Payload) -> None:
        """ This method sends a serialized form of the process status through the socket.

        :param status: the status to publish
        :return: None
        """
        self.logger.trace(f'ZmqEventPublisher.send_process_status: {status}')
        self.socket.send_string(EventHeaders.PROCESS_STATUS.value, zmq.SNDMORE)
        self.socket.send_json(status)

    def send_host_statistics(self, statistics: Payload) -> None:
        """ This method sends host statistics through the socket.

        :param statistics: the statistics to publish
        :return: None
        """
        self.logger.trace(f'ZmqEventPublisher.send_host_statistics: {statistics}')
        self.socket.send_string(EventHeaders.HOST_STATISTICS.value, zmq.SNDMORE)
        self.socket.send_json(statistics)

    def send_process_statistics(self, statistics: Payload) -> None:
        """ This method sends process statistics through the socket.

        :param statistics: the statistics to publish
        :return: None
        """
        self.logger.trace(f'ZmqEventPublisher.send_process_statistics: {statistics}')
        self.socket.send_string(EventHeaders.PROCESS_STATISTICS.value, zmq.SNDMORE)
        self.socket.send_json(statistics)


class ZmqEventSubscriber(EventSubscriber):
    """ The ZmqEventSubscriber wraps the PyZmq socket that connects to Supvisors.

    The TCP socket is configured with a PyZmq SUBSCRIBE pattern.
    It is connected to the Supvisors instance running on the localhost and bound on the event port.

    The ZmqEventSubscriber requires:
        - the event port number used by Supvisors to publish its events,
        - a logger reference to log traces.

    Attributes:
        - logger: the reference to the logger,
        - socket: the PyZmq socket connected to Supvisors.

    Constants:
        - _Poll_timeout: duration used to time out the PyZMQ poller, defaulted to 500 milliseconds.
    """

    # timeout to avoid blocking reception
    _Poll_timeout = 500

    def __init__(self, zmq_context: zmq.asyncio.Context, intf: EventSubscriberInterface,
                 node_name: str, event_port: int, logger: Logger) -> None:
        """ Initialization of the attributes.

        :param zmq_context: the PyZmq context instance
        :param intf: the event subscriber interface used to provide the messages received
        :param node_name: the node name of the Supvisors instance that publishes events
        :param event_port: the port used by the Supvisors instance to publish events from the node
        :param logger: the Supvisors logger
        """
        super().__init__(intf, node_name, event_port, logger)
        self.zmq_context = zmq_context

    async def mainloop(self, stop_evt: asyncio.Event, node_name: str, event_port: int) -> None:
        """ Main loop of the thread. """
        # create the PyZMQ socket
        socket: zmq.asyncio.Socket = self.zmq_context.socket(zmq.SUB)
        # set subscriptions
        if self.all_subscriptions():
            socket.setsockopt(zmq.SUBSCRIBE, b'')
        else:
            for header in self.headers:
                socket.setsockopt(zmq.SUBSCRIBE, header.encode('utf-8'))
        # define the URI
        uri = f'tcp://{node_name}:{event_port}'
        while not stop_evt.is_set():
            self.logger.debug(f'ZmqEventSubscriber: connecting {uri}')
            socket.connect(uri)
            # create poller and register event subscriber
            poller = zmq.asyncio.Poller()
            poller.register(socket, zmq.POLLIN)
            # poll events every seconds
            self.logger.info('ZmqEventSubscriber.run: entering main loop')
            while not stop_evt.is_set():
                socks = dict(await poller.poll(ZmqEventSubscriber._Poll_timeout))
                # check if something happened on the socket
                if socket in socks and socks[socket] == zmq.POLLIN:
                    self.logger.debug('ZmqEventSubscriber.run: got message on subscriber')
                    try:
                        header = await socket.recv_string()
                        body = await socket.recv_json()
                    except zmq.ZMQError as exc:
                        self.logger.error(f'ZmqEventSubscriber.run: socket error on subscriber: {exc}')
                    except UnicodeDecodeError:
                        self.logger.error(f'ZmqEventSubscriber.run: incompatible data type received from {uri}')
                    else:
                        try:
                            self.on_receive(header, body)
                        except ValueError:
                            self.logger.error(f'ZmqEventSubscriber.run: unexpected event type {header}')
            self.logger.warn('ZmqEventSubscriber.run: exiting main loop')
            socket.close(ZMQ_LINGER)
