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

import zmq

from supervisor.loggers import Logger
from typing import Any, Tuple

from .publisherinterface import EventPublisherInterface
from .supvisorsmapper import SupvisorsInstanceId
from .ttypes import Payload, EventHeaders

# Constant for Zmq sockets
ZMQ_LINGER = 0

# reference to the Zmq Context instance
ZmqContext = zmq.Context.instance()


class EventPublisher(EventPublisherInterface):
    """ Class for PyZmq publication of Supvisors events. """

    def __init__(self, instance: SupvisorsInstanceId, logger: Logger):
        """ Initialization of the attributes.

        :param instance: the local Supvisors instance identification
        :param logger: the Supvisors logger
        """
        self.logger: Logger = logger
        logger.info('EventPublisher: initiating PyZmq event publisher')
        self.socket: zmq.Socket = ZmqContext.socket(zmq.PUB)
        # WARN: this is a local binding, only visible to processes located on the same host
        url = f'tcp://127.0.0.1:{instance.event_port}'
        self.logger.debug(f'EventPublisher: binding {url}')
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
        self.logger.trace(f'EventPublisher.send_supvisors_status: {status}')
        self.socket.send_string(EventHeaders.SUPVISORS.value, zmq.SNDMORE)
        self.socket.send_json(status)

    def send_instance_status(self, status: Payload) -> None:
        """ Send a JSON-serialized Supvisors instance status through the socket.

        :param status: the status to publish
        :return: None
        """
        self.logger.trace(f'EventPublisher.send_instance_status: {status}')
        self.socket.send_string(EventHeaders.INSTANCE.value, zmq.SNDMORE)
        self.socket.send_json(status)

    def send_application_status(self, status: Payload) -> None:
        """ Send a JSON-serialized application status through the socket.

        :param status: the status to publish
        :return: None
        """
        self.logger.trace(f'EventPublisher.send_application_status: {status}')
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
        self.logger.trace(f'EventPublisher.send_process_event: {evt}')
        self.socket.send_string(EventHeaders.PROCESS_EVENT.value, zmq.SNDMORE)
        self.socket.send_json(evt)

    def send_process_status(self, status: Payload) -> None:
        """ This method sends a serialized form of the process status through the socket.

        :param status: the status to publish
        :return: None
        """
        self.logger.trace(f'EventPublisher.send_process_status: {status}')
        self.socket.send_string(EventHeaders.PROCESS_STATUS.value, zmq.SNDMORE)
        self.socket.send_json(status)


class EventSubscriber(object):
    """ The EventSubscriber wraps the PyZmq socket that connects to **Supvisors**.

    The TCP socket is configured with a PyZmq ``SUBSCRIBE`` pattern.
    It is connected to the **Supvisors** instance running on the localhost and bound on the event port.

    The EventSubscriber requires:
        - the event port number used by **Supvisors** to publish its events,
        - a logger reference to log traces.

    Attributes:
        - logger: the reference to the logger,
        - socket: the PyZmq socket connected to **Supvisors**.
    """

    def __init__(self, zmq_context: zmq.Context, port: int, logger: Logger) -> None:
        """ Initialization of the attributes.

        :param zmq_context: the PyZmq context instance
        :param port: the port number of the TCP socket
        :param logger: the Supvisors logger
        """
        self.logger = logger
        # create ZeroMQ socket
        self.socket = zmq_context.socket(zmq.SUB)
        # WARN: this is a local binding, only visible to processes located on the same host
        url = f'tcp://127.0.0.1:{port}'
        self.logger.debug(f'EventSubscriber: connecting {url}')
        self.socket.connect(url)

    def close(self) -> None:
        """ Close the PyZmq socket.

        :return: None
        """
        self.socket.close(ZMQ_LINGER)

    # subscription part
    def subscribe_all(self) -> None:
        """ Subscribe to all events.

        :return: None
        """
        self.socket.setsockopt(zmq.SUBSCRIBE, b'')

    def subscribe_supvisors_status(self) -> None:
        """ Subscribe to Supvisors Status messages.

        :return: None
        """
        self.subscribe(EventHeaders.SUPVISORS.value)

    def subscribe_instance_status(self) -> None:
        """ Subscribe to Supvisors Instance Status messages.

        :return: None
        """
        self.subscribe(EventHeaders.INSTANCE.value)

    def subscribe_application_status(self) -> None:
        """ Subscribe to Application Status messages.

        :return: None
        """
        self.subscribe(EventHeaders.APPLICATION.value)

    def subscribe_process_event(self) -> None:
        """ Subscribe to Process Event messages.

        :return: None
        """
        self.subscribe(EventHeaders.PROCESS_EVENT.value)

    def subscribe_process_status(self) -> None:
        """ Subscribe to Process Status messages.

        :return: None
        """
        self.subscribe(EventHeaders.PROCESS_STATUS.value)

    def subscribe(self, code: str) -> None:
        """ Subscribe to the event named code.

        :param code: the message code for subscription
        :return: None
        """
        self.socket.setsockopt(zmq.SUBSCRIBE, code.encode('utf-8'))

    # unsubscription part
    def unsubscribe_all(self) -> None:
        """ Unsubscribe from all events.

        :return: None
        """
        self.socket.setsockopt(zmq.UNSUBSCRIBE, b'')

    def unsubscribe_supvisors_status(self) -> None:
        """ Unsubscribe from Supvisors Status messages

        :return: None
        """
        self.unsubscribe(EventHeaders.SUPVISORS.value)

    def unsubscribe_instance_status(self) -> None:
        """ Unsubscribe from Supvisors Instance Status messages

        :return: None
        """
        self.unsubscribe(EventHeaders.INSTANCE.value)

    def unsubscribe_application_status(self) -> None:
        """ Unsubscribe from Application Status messages

        :return: None
        """
        self.unsubscribe(EventHeaders.APPLICATION.value)

    def unsubscribe_process_event(self) -> None:
        """ Unsubscribe from Process Event messages

        :return: None
        """
        self.unsubscribe(EventHeaders.PROCESS_EVENT.value)

    def unsubscribe_process_status(self) -> None:
        """ Unsubscribe from Process Status messages

        :return: None
        """
        self.unsubscribe(EventHeaders.PROCESS_STATUS.value)

    def unsubscribe(self, code: str) -> None:
        """ Remove subscription to the event named code.

        :param code: the message code for unsubscription
        :return: None
        """
        self.socket.setsockopt(zmq.UNSUBSCRIBE, code.encode('utf-8'))

    # reception part
    def receive(self) -> Tuple[str, Any]:
        """ Reception of two-parts message:
            - header as a unicode string,
            - data encoded in JSON.

        :return: a tuple with header and body
        """
        return self.socket.recv_string(), self.socket.recv_json()
