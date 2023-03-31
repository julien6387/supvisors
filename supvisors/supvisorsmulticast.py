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

import select
import struct
import traceback
from enum import Enum
from socket import (inet_aton, socket,
                    AF_INET, INADDR_ANY, SOCK_DGRAM, SOL_SOCKET, SO_REUSEADDR,
                    IPPROTO_IP, IP_ADD_MEMBERSHIP, IP_MULTICAST_TTL)
from typing import Any, List, Optional, Tuple

from supervisor.loggers import Logger

from .internalinterface import (SupvisorsInternalComm, InternalCommEmitter, InternalCommReceiver,
                                payload_to_bytes, bytes_to_payload)
from .supvisorsmapper import SupvisorsInstanceId
from .ttypes import InternalEventHeaders, Ipv4Address, Payload

MULTICAST_TTL = 2  # TODO: set in options
BUFFER_SIZE = 16*1024


class MulticastSender(InternalCommEmitter):

    def __init__(self, identifier: str, address: str, port: int):
        """ Create a socket to multicast messages. """
        self.identifier: str = identifier
        self.address: str = address
        self.port: int = port
        # create the socket
        self.socket = socket(AF_INET, SOCK_DGRAM)
        self.socket.setsockopt(IPPROTO_IP, IP_MULTICAST_TTL, MULTICAST_TTL)

    def close(self) -> None:
        """ Close the UDP socket. """
        self.socket.close()

    def send_message(self, event_type: Enum, event_body: Payload):
        """ Multicast a message. """
        message = payload_to_bytes(event_type, (self.identifier, event_body))
        self.socket.sendto(message, (self.address, self.port))

    def send_tick_event(self, payload: Payload) -> None:
        """ Publish the tick event.

        :param payload: the tick to push
        :return: None
        """
        self.send_message(InternalEventHeaders.TICK, payload)

    def send_process_state_event(self, payload: Payload) -> None:
        """ Publish the process state event.

        :param payload: the process state to publish
        :return: None
        """
        self.send_message(InternalEventHeaders.PROCESS, payload)

    def send_process_added_event(self, payload: Payload) -> None:
        """ Publish the process added event.

        :param payload: the added process to publish
        :return: None
        """
        self.send_message(InternalEventHeaders.PROCESS_ADDED, payload)

    def send_process_removed_event(self, payload: Payload) -> None:
        """ Publish the process removed event.

        :param payload: the removed process to publish
        :return: None
        """
        self.send_message(InternalEventHeaders.PROCESS_REMOVED, payload)

    def send_process_disability_event(self, payload: Payload) -> None:
        """ Publish the process disability event.

        :param payload: the enabled/disabled process to publish
        :return: None
        """
        self.send_message(InternalEventHeaders.PROCESS_DISABILITY, payload)

    def send_host_statistics(self, payload: Payload) -> None:
        """ Publish the host statistics.

        :param payload: the statistics to publish
        :return: None
        """
        self.send_message(InternalEventHeaders.HOST_STATISTICS, payload)

    def send_process_statistics(self, payload: Payload) -> None:
        """ Publish the process statistics.

        :param payload: the statistics to publish
        :return: None
        """
        self.send_message(InternalEventHeaders.PROCESS_STATISTICS, payload)

    def send_state_event(self, payload: Payload) -> None:
        """ Publish the Master state event.

        :param payload: the Supvisors state to publish
        :return: None
        """
        self.send_message(InternalEventHeaders.STATE, payload)


class MulticastReceiver(InternalCommReceiver):

    def __init__(self, puller_sock: socket, address: str, port: int, logger: Logger):
        """ Create the multicast reception and the poller.

        :param puller_sock: the socket pair end used to receive the deferred Supvisors XML-RPC results
        """
        super().__init__(puller_sock, logger)
        self.socket: Optional[socket] = None
        # create the reception socket for the Multicast messages
        self._bind(address, port)
        if self.socket:
            self.poller.register(self.socket, select.POLLIN)

    def _bind(self, address: str, port: int):
        # create the socket
        sock = socket(AF_INET, SOCK_DGRAM)
        sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        try:
            sock.bind((address, port))
            mcast_req = struct.pack('4sl', inet_aton(address), INADDR_ANY)
            sock.setsockopt(IPPROTO_IP, IP_ADD_MEMBERSHIP, mcast_req)
        except OSError:
            self.logger.error(f'MulticastReceiver._bind: cannot bind multicast socket to {address}:{port}')
            self.logger.debug(f'MulticastReceiver._bind: {traceback.format_exc()}')
        else:
            self.logger.info(f'MulticastReceiver._bind: multicast socket bound to {address}:{port}')
            self.socket = sock

    def read_fds(self, fds: List[int]) -> List[Tuple[Ipv4Address, Payload]]:
        """ Read the messages received on the file descriptors.

        :param fds: the file descriptors of the sockets to read
        :return: the messages received
        """
        if self.socket.fileno() in fds:
            # read the message from the socket
            msg_as_bytes, address = self.socket.recvfrom(BUFFER_SIZE)
            return [(address, bytes_to_payload(msg_as_bytes))]
        return []

    def close(self) -> None:
        """ Close the puller, the publisher and the subscribers sockets.
        Should be called only from the SupvisorsMainLoop.

        :return: None
        """
        super().close()
        if self.socket:
            self.poller.unregister(self.socket)
            self.socket.close()


class SupvisorsMulticast(SupvisorsInternalComm):
    """ Class holding all structures used for Supvisors internal communication
    using a UDP Multicast pattern. """

    def __init__(self, supvisors: Any) -> None:
        """ Construction of all communication blocks.

        :param supvisors: the Supvisors global structure
        """
        super().__init__(supvisors)
        # create the Supvisors instance publisher and start it directly
        local_instance: SupvisorsInstanceId = supvisors.supvisors_mapper.local_instance
        self.emitter = MulticastSender(local_instance.identifier,
                                       supvisors.options.multicast_address,
                                       local_instance.internal_port)
        # create the global subscriber that receives deferred XML-RPC requests and events sent by all publishers
        self.receiver = MulticastReceiver(self.puller_sock,
                                          supvisors.options.multicast_address,
                                          local_instance.internal_port,
                                          supvisors.logger)
