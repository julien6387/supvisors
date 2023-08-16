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
import struct
import traceback
from enum import Enum
from socket import (inet_aton, error, socket,
                    AF_INET, INADDR_ANY, SOCK_DGRAM,
                    IPPROTO_IP, IPPROTO_UDP, IP_ADD_MEMBERSHIP, IP_MULTICAST_TTL)
from typing import Any

from supervisor.loggers import Logger

from supvisors.ttypes import Ipv4Address, Payload
from .internalinterface import InternalCommEmitter, payload_to_bytes, bytes_to_payload

# Default size of the Multicast reception buffer
BUFFER_SIZE = 16 * 1024


# Emission part
#   done in Sync to work in Supervisor thread
class MulticastSender(InternalCommEmitter):
    """ only TICKS for discovery mode. """

    def __init__(self, identifier: str, mc_group: Ipv4Address, ttl: int, logger: Logger):
        """ Create a socket to multicast messages. """
        self.identifier: str = identifier
        self.mc_group: Ipv4Address = mc_group
        self.logger: Logger = logger
        # create the socket
        self.socket = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP)
        self.socket.setsockopt(IPPROTO_IP, IP_MULTICAST_TTL, ttl)
        logger.info(f'MulticastSender: socket opened to {mc_group}')

    def close(self) -> None:
        """ Close the UDP socket. """
        self.socket.close()

    def emit_message(self, event_type: Enum, event_body: Payload):
        """ Multicast a message.
        It is not necessary to add a message size . """
        message = payload_to_bytes(event_type, (self.identifier, event_body))
        self.logger.debug(f'MulticastSender.emit_message: size={len(message)}')
        try:
            self.socket.sendto(message, self.mc_group)
        except OSError:
            self.logger.error(f'MulticastSender.emit_message: failed to send event (type={event_type.name})')
            self.logger.info(f'MulticastSender.emit_message: {traceback.format_exc()}')


# Reception part
#   done in Async as working in Supvisors thread
class MulticastReceiver(asyncio.Protocol):
    """ The MulticastReceiver receives datagrams, decodes them and put them into the asynchronous queue. """

    def __init__(self, queue: asyncio.Queue, logger: Logger):
        """ Initialization of the attributes. """
        self.logger: Logger = logger
        self.queue: asyncio.Queue = queue

    def connection_made(self, transport: asyncio.DatagramTransport):
        """ Just for information. Not used. """
        self.logger.debug(f'MulticastReceiver.connection_made')

    def datagram_received(self, data, address):
        """ Decode the message received to put it into the asynchronous queue. """
        self.logger.debug(f'MulticastReceiver.datagram_received: from {address}')
        self.queue.put_nowait((address, bytes_to_payload(data)))


async def handle_mc_receiver(queue: asyncio.Queue, stop_event: asyncio.Event, supvisors: Any):
    """ The main coroutine in charge of receiving messages from the MulticastSender. """
    mc_address = supvisors.options.multicast_group
    mc_interface = supvisors.options.multicast_interface
    supvisors.logger.debug(f'handle_mc_receiver: creating MulticastReceiver on {mc_address}')
    # open the MulticastReceiver
    loop = asyncio.get_event_loop()
    try:
        transport, protocol = await loop.create_datagram_endpoint(lambda: MulticastReceiver(queue, supvisors.logger),
                                                                  family=AF_INET, proto=IPPROTO_UDP,
                                                                  local_addr=mc_address, reuse_port=True)
    except error as exc:
        supvisors.logger.error(f'handle_mc_receiver: failed to open endpoint to {mc_address} - {str(exc)}')
    else:
        supvisors.logger.info(f'handle_mc_receiver: endpoint opened to {mc_address}')
        try:
            if mc_interface:
                mcast_req = struct.pack('=4s4s', inet_aton(mc_address[0]), inet_aton(mc_interface))
            else:
                mcast_req = struct.pack('=4sl', inet_aton(mc_address[0]), INADDR_ANY)
            # WARN: public access to underlying socket is sadly not provided
            transport._sock.setsockopt(IPPROTO_IP, IP_ADD_MEMBERSHIP, mcast_req)
        except error as exc:
            supvisors.logger.error(f'handle_mc_receiver: failed to set membership {mc_interface or "INADDR_ANY"}'
                                   f' to {mc_address} - {str(exc)}')
        else:
            supvisors.logger.debug(f'handle_mc_receiver: membership set for {mc_address}')
            # wait for task termination
            await stop_event.wait()
        transport.close()
    supvisors.logger.debug(f'handle_mc_receiver: exit')
