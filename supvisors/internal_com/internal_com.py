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
from socket import socketpair
from typing import Any, List, Optional, Coroutine

from .mapper import SupvisorsInstanceId
from .multicast import MulticastSender, handle_mc_receiver
from .pubsub import InternalPublisher, InternalAsyncSubscribers
from .pushpull import RequestPusher, RequestAsyncPuller


class SupvisorsInternalEmitter:
    """ Class holding the structures used for the emission part Supvisors internal communication
    using a TCP Publish-Subscribe custom pattern. """

    def __init__(self, supvisors: Any) -> None:
        """ Construction of all internal emission blocks.

        :param supvisors: the Supvisors global structure
        """
        self.supvisors = supvisors
        # create socket pairs for the deferred requests
        self.pusher_sock, self.puller_sock = socketpair()
        # create the pusher used to detach the XML-RPC requests from the Supervisor Thread
        # events will be received in the SupvisorsMainLoop thread
        self.pusher = RequestPusher(self.pusher_sock, supvisors.logger)
        # create the publisher
        self.publisher: InternalPublisher = self._create_publisher()
        # create the Multicast message emitter if the discovery mode is enabled
        self.mc_sender: Optional[MulticastSender] = None
        if self.supvisors.options.discovery_mode:
            local_instance: SupvisorsInstanceId = supvisors.mapper.local_instance
            self.mc_sender = MulticastSender(local_instance.identifier,
                                             supvisors.options.multicast_group,
                                             supvisors.options.multicast_ttl,
                                             supvisors.logger)
        # store network interface names
        self.intf_names: List[str] = []

    def stop(self) -> None:
        """ Close all sockets.
        Should be called only from the Supervisor thread.

        :return: None
        """
        if self.mc_sender:
            self.mc_sender.close()
        self.publisher.close()
        self.pusher_sock.close()
        # WARN: do NOT close puller_sock as it will be done from the Supvisors thread (mainloop.py)

    def check_intf(self, intf_names: List[str]):
        """ Restart the Publisher when a new network interfaces is added. """
        if self.intf_names:
            # check if there's a new network interface
            new_intf_names = [x for x in intf_names if x not in self.intf_names]
            if new_intf_names:
                if self.publisher:
                    self.supvisors.logger.warn('SupvisorsInternalEmitter.restart: publisher restart'
                                               f' due to new network interfaces {new_intf_names}')
                    self.publisher.close()
                # create a new publisher
                self.publisher = self._create_publisher()
        # store current list
        self.intf_names = intf_names

    def _create_publisher(self) -> InternalPublisher:
        """ Start the Publisher thread. """
        local_instance: SupvisorsInstanceId = self.supvisors.mapper.local_instance
        publisher = InternalPublisher(local_instance.identifier, local_instance.internal_port, self.supvisors.logger)
        publisher.start()
        return publisher


class SupvisorsInternalReceiver:
    """ Class holding the structures used for the reception part Supvisors internal communication
    using a TCP Publish-Subscribe custom pattern. """

    def __init__(self, async_loop: asyncio.AbstractEventLoop, supvisors: Any) -> None:
        """ Construction of all internal reception blocks.

        :param async_loop: the asynchronous loop event where the com tasks will run.
        :param supvisors: the Supvisors global structure.
        """
        # keep a reference to the Supvisors instance
        self.supvisors = supvisors
        # asyncio loop attributes
        self.loop: asyncio.AbstractEventLoop = async_loop
        self.stop_event: asyncio.Event = asyncio.Event()
        # asyncio queues
        self.requester_queue = asyncio.Queue()
        self.subscriber_queue = asyncio.Queue()
        self.discovery_queue = asyncio.Queue()
        # asyncio tasks
        self.puller: RequestAsyncPuller = RequestAsyncPuller(self.requester_queue, self.stop_event, supvisors)
        self.subscribers: InternalAsyncSubscribers = InternalAsyncSubscribers(self.subscriber_queue,
                                                                              self.stop_event,
                                                                              supvisors)
        self.discovery_coro: Optional[Coroutine] = None
        if self.supvisors.options.discovery_mode:
            self.discovery_coro = handle_mc_receiver(self.discovery_queue, self.stop_event, supvisors)

    def stop(self) -> None:
        """ The stop method is meant to be called from outside the async loop.
        This will stop all asynchronous tasks.
        """
        if self.loop and self.loop.is_running() and self.stop_event and not self.stop_event.is_set():
            # fire the event within the event loop
            async def stop_it() -> None:
                """ Set the Future stop_event to stop all asynchronous tasks. """
                self.stop_event.set()
            asyncio.run_coroutine_threadsafe(stop_it(), self.loop).result()

    def get_tasks(self) -> List:
        """ Return the tasks necessary to receive:
            - internal requests from the local Supvisors instance,
            - events from the other Supvisors instances ;
            - optionally discovery events from the other Supvisors instances.
        """
        # get the mandatory tasks
        all_coro = [self.puller.handle_puller()]
        all_coro.extend(self.subscribers.get_coroutines())
        # add the optional task for discovery mode
        if self.discovery_coro:
            all_coro.append(self.discovery_coro)
        return all_coro
