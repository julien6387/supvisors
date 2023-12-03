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
from threading import Thread
from typing import Any, Callable, Optional, Set

from supervisor.loggers import Logger

from supvisors.internal_com.mapper import SupvisorsInstanceId
from supvisors.ttypes import EventHeaders, EventLinks, Payload

# timeout for async operations, in seconds
ASYNC_TIMEOUT = 1.0


class EventPublisherInterface:
    """ Interface for the publication of Supvisors events. """

    def close(self) -> None:
        """ Close the publisher.

        :return: None
        """
        raise NotImplementedError

    def send_supvisors_status(self, status: Payload) -> None:
        """ Send a JSON-serialized supvisors status through the socket.

        :param status: the status to publish
        :return: None
        """
        raise NotImplementedError

    def send_instance_status(self, status: Payload) -> None:
        """ Send a Supvisors instance status.

        :param status: the status to publish
        :return: None
        """
        raise NotImplementedError

    def send_application_status(self, status: Payload) -> None:
        """ Send an application status.

        :param status: the status to publish
        :return: None
        """
        raise NotImplementedError

    def send_process_event(self, identifier: str, event: Payload) -> None:
        """ Send a process event.

        :param identifier: the identifier used to identify the origin of the event
        :param event: the event to publish
        :return: None
        """
        raise NotImplementedError

    def send_process_status(self, status: Payload) -> None:
        """ Send a process status.

        :param status: the status to publish
        :return: None
        """
        raise NotImplementedError

    def send_host_statistics(self, statistics: Payload) -> None:
        """ Send host statistics.

        :param statistics: the statistics to publish
        :return: None
        """
        raise NotImplementedError

    def send_process_statistics(self, statistics: Payload) -> None:
        """ Send process statistics.

        :param statistics: the statistics to publish
        :return: None
        """
        raise NotImplementedError


def create_external_publisher(supvisors: Any) -> EventPublisherInterface:
    """ Create the relevant event publisher in accordance with the option selected.

    :param supvisors: the global Supvisors instance
    :return: the event publisher instance
    """
    publisher_instance = None
    publisher_class = None
    if supvisors.options.event_link == EventLinks.ZMQ:
        # get a PyZMQ publisher factory
        try:
            import zmq
            from supvisors.external_com.supvisorszmq import ZmqEventPublisher
            publisher_class = ZmqEventPublisher
        except (ImportError, ModuleNotFoundError):
            supvisors.logger.error('create_external_publisher: failed to import PyZmq')
    elif supvisors.options.event_link == EventLinks.WS:
        # get a Websocket publisher factory
        try:
            import websockets
            from supvisors.external_com.supvisorswebsocket import WsEventPublisher
            publisher_class = WsEventPublisher
        except (ImportError, ModuleNotFoundError):
            supvisors.logger.error('create_external_publisher: failed to import websockets')
    # create the publisher instance
    if publisher_class:
        local_instance: SupvisorsInstanceId = supvisors.mapper.local_instance
        publisher_instance = publisher_class(local_instance, supvisors.logger)
    return publisher_instance


class EventSubscriberInterface:
    """ Interface for the subscription of Supvisors events. """

    def on_supvisors_status(self, data):
        """ Reception of the Supvisors Status message. """
        raise NotImplementedError

    def on_instance_status(self, data):
        """ Reception of the Supvisors Instance Status message. """
        raise NotImplementedError

    def on_application_status(self, data):
        """ Reception of the Application Status message. """
        raise NotImplementedError

    def on_process_event(self, data):
        """ Reception of the Process Event message. """
        raise NotImplementedError

    def on_process_status(self, data):
        """ Reception of the Process Status message. """
        raise NotImplementedError

    def on_host_statistics(self, data):
        """ Reception of the Host Statistics message. """
        raise NotImplementedError

    def on_process_statistics(self, data):
        """ Reception of the Process Statistics message. """
        raise NotImplementedError


class EventSubscriber:
    """ Common class providing the event to the implementation of the event subscriber interface. """

    def __init__(self, intf: EventSubscriberInterface, node_name: str, event_port: int, logger: Logger):
        """ Initialization of the attributes.

        :param intf: the event subscriber interface used to provide the messages received
        :param node_name: the node name of the Supvisors instance that publishes events
        :param event_port: the port used by the Supvisors instance to publish events from the node
        :param logger: the Supvisors logger
        """
        self.intf = intf
        self.node_name: str = node_name
        self.event_port: int = event_port
        self.logger: Logger = logger
        # the subscriptions registered
        self.headers: Set[str] = set()
        # create the thread wrapping the Websockets client
        self.thread: Optional[AsyncEventThread] = None
        self.reset()

    def reset(self) -> None:
        """ Create a new thread to handle the event subscriber. """
        self.thread = AsyncEventThread(self.mainloop, self.node_name, self.event_port)

    async def mainloop(self, stop_evt: asyncio.Event, node_name: str, event_port: int) -> None:
        """ Infinite loop to be implemented in subclass.

        :return: None
        """
        raise NotImplementedError

    def start(self) -> None:
        """ Start the thread wrapping the event subscriber.
        Subscriptions must be done before. """
        self.thread.start()

    def stop(self) -> None:
        """ Stop and join the thread wrapping the Websocket client.

        :return: None
        """
        if self.thread.is_alive():
            self.thread.stop()
            self.thread.join()

    def on_receive(self, header, body):
        """ Called upon the reception of data from the websocket client.
        This will raise a ValueError if the header is not compliant to the EventHeaders Enum. """
        event = EventHeaders(header)
        if event == EventHeaders.SUPVISORS:
            self.intf.on_supvisors_status(body)
        elif event == EventHeaders.INSTANCE:
            self.intf.on_instance_status(body)
        elif event == EventHeaders.APPLICATION:
            self.intf.on_application_status(body)
        elif event == EventHeaders.PROCESS_EVENT:
            self.intf.on_process_event(body)
        elif event == EventHeaders.PROCESS_STATUS:
            self.intf.on_process_status(body)
        elif event == EventHeaders.HOST_STATISTICS:
            self.intf.on_host_statistics(body)
        elif event == EventHeaders.PROCESS_STATISTICS:
            self.intf.on_process_statistics(body)

    # subscription part
    def all_subscriptions(self) -> bool:
        """ Check if all events are subscribed.

        :return: True if all events are subscribed
        """
        return all(header.value in self.headers for header in EventHeaders)

    def subscribe_all(self) -> None:
        """ Subscribe to all event types.

        :return: None
        """
        self.headers = {header.value for header in EventHeaders}

    def subscribe(self, header: EventHeaders) -> None:
        """ Subscribe to an event type.

        :param header: the header to subscribe
        :return: None
        """
        self.headers.add(header.value)

    def subscribe_supvisors_status(self) -> None:
        """ Subscribe to Supvisors Status messages.

        :return: None
        """
        self.subscribe(EventHeaders.SUPVISORS)

    def subscribe_instance_status(self) -> None:
        """ Subscribe to Supvisors Instance Status messages.

        :return: None
        """
        self.subscribe(EventHeaders.INSTANCE)

    def subscribe_application_status(self) -> None:
        """ Subscribe to Application Status messages.

        :return: None
        """
        self.subscribe(EventHeaders.APPLICATION)

    def subscribe_process_event(self) -> None:
        """ Subscribe to Process Event messages.

        :return: None
        """
        self.subscribe(EventHeaders.PROCESS_EVENT)

    def subscribe_process_status(self) -> None:
        """ Subscribe to Process Status messages.

        :return: None
        """
        self.subscribe(EventHeaders.PROCESS_STATUS)

    def subscribe_host_statistics(self) -> None:
        """ Subscribe to Host Statistics messages.

        :return: None
        """
        self.subscribe(EventHeaders.HOST_STATISTICS)

    def subscribe_process_statistics(self) -> None:
        """ Subscribe to Process Statistics messages.

        :return: None
        """
        self.subscribe(EventHeaders.PROCESS_STATISTICS)

    # unsubscription part
    def unsubscribe_all(self) -> None:
        """ Unsubscribe from all events.

        :return: None
        """
        self.headers = set()

    def unsubscribe(self, header: EventHeaders) -> None:
        """ Unsubscribe from an event.

        :param header: the header to unsubscribe
        :return: None
        """
        if header.value in self.headers:
            self.headers.remove(header.value)

    def unsubscribe_supvisors_status(self) -> None:
        """ Unsubscribe from Supvisors Status messages

        :return: None
        """
        self.unsubscribe(EventHeaders.SUPVISORS)

    def unsubscribe_instance_status(self) -> None:
        """ Unsubscribe from Supvisors Instance Status messages

        :return: None
        """
        self.unsubscribe(EventHeaders.INSTANCE)

    def unsubscribe_application_status(self) -> None:
        """ Unsubscribe from Application Status messages

        :return: None
        """
        self.unsubscribe(EventHeaders.APPLICATION)

    def unsubscribe_process_event(self) -> None:
        """ Unsubscribe from Process Event messages

        :return: None
        """
        self.unsubscribe(EventHeaders.PROCESS_EVENT)

    def unsubscribe_process_status(self) -> None:
        """ Unsubscribe from Process Status messages

        :return: None
        """
        self.unsubscribe(EventHeaders.PROCESS_STATUS)

    def unsubscribe_host_statistics(self) -> None:
        """ Unsubscribe from Host Statistics messages.

        :return: None
        """
        self.unsubscribe(EventHeaders.HOST_STATISTICS)

    def unsubscribe_process_statistics(self) -> None:
        """ Unsubscribe from Process Statistics messages.

        :return: None
        """
        self.unsubscribe(EventHeaders.PROCESS_STATISTICS)


class AsyncEventThread(Thread):
    """ Wrapper to start an asynchronous coroutine in a thread. """

    def __init__(self, coro: Callable, node_name: str = '', event_port: int = 9003):
        """ Initialization of the attributes.

        :param coro: the coroutine to start
        :param node_name: the node to bind or connect
        :param event_port: the port to bind or connect
        """
        super().__init__(daemon=True)
        self.coro: Callable = coro
        self.node_name = node_name
        self.event_port = event_port
        # prepare references for the event loop and the stop event
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.stop_event: Optional[asyncio.Event] = None

    def run(self):
        """ Start the websocket service or client in a new event loop. """
        # create the event loop and the stop event
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.stop_event = asyncio.Event()
        # start the task and wait for its termination
        self.loop.run_until_complete(self.coro(self.stop_event, self.node_name, self.event_port))
        self.loop.close()
        self.loop = None

    def stop(self):
        """ Stop the websocket service or client. """
        if self.loop and self.loop.is_running() and self.stop_event and not self.stop_event.is_set():
            # fire the event within the event loop
            async def stop_it():
                self.stop_event.set()
            asyncio.run_coroutine_threadsafe(stop_it(), self.loop).result()
