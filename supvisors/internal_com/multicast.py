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
import threading
import traceback
from socket import (inet_aton, socket,
                    AF_INET, INADDR_ANY, SOCK_DGRAM, SOL_SOCKET, SO_REUSEADDR,
                    IPPROTO_IP, IPPROTO_UDP, IP_ADD_MEMBERSHIP, IP_MULTICAST_TTL)
from typing import Any, Optional, Set, Tuple

from supervisor.loggers import Logger

from supvisors.ttypes import Ipv4Address, NotificationHeaders, Payload
from .internalinterface import payload_to_bytes, bytes_to_payload
from .mapper import SupvisorsInstanceId

# timeout for polling, in milliseconds
POLL_TIMEOUT = 500

# Default size of the Multicast reception buffer (a lot larger than required, which is less than 200 bytes)
BUFFER_SIZE = 1024


# Emission part
class MulticastSender:
    """ Multicast only TICKS for discovery mode. """

    def __init__(self, mc_group: Ipv4Address, mc_ttl: int, logger: Logger):
        """ Create a socket to multicast messages. """
        self.mc_group: Ipv4Address = mc_group
        self.logger: Logger = logger
        # create the socket
        self.socket = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP)
        self.socket.setsockopt(IPPROTO_IP, IP_MULTICAST_TTL, mc_ttl)
        logger.info(f'MulticastSender: socket opened to {mc_group}')

    def close(self) -> None:
        """ Close the UDP socket. """
        self.socket.close()

    def send_discovery_event(self, payload: Payload):
        """ Multicast the discovery event.
        It is not necessary to add a message size. """
        self.logger.trace('MulticastSender.emit_message')
        message = payload_to_bytes((NotificationHeaders.DISCOVERY.value, payload))
        try:
            self.socket.sendto(message, self.mc_group)
        except OSError:
            self.logger.error('MulticastSender.emit_message: failed to send DISCOVERY message')
            self.logger.info(f'MulticastSender.emit_message: {traceback.format_exc()}')


# Reception part
class MulticastReceiver(threading.Thread):
    """ The MulticastReceiver receives datagrams, decodes them and put them into the asynchronous queue. """

    def __init__(self, mc_group: Ipv4Address, mc_interface: Optional[str], callback, logger: Logger):
        """ Initialization of the attributes. """
        super().__init__(daemon=True)
        self.logger: Logger = logger
        self.callback = callback
        # save the multicast parameters
        self.mc_group: Ipv4Address = mc_group
        self.mc_interface: Optional[str] = mc_interface
        # the socket will be created when starting the thread
        self.socket: Optional[socket] = None
        # create an event to stop the thread
        self.stop_event: threading.Event = threading.Event()
        # single warning for new clients
        self.log_warnings: Set[Tuple[str, str]] = set()

    def stop(self):
        """ Set a stop event for this thread.

        :return: None
        """
        self.stop_event.set()

    def stopping(self) -> bool:
        """ Access to the loop attribute.

        :return: True if the condition to stop the main loop is reached.
        """
        return self.stop_event.is_set()

    def run(self):
        """ Multicast reception loop. """
        self.logger.info('MulticastReceiver.run: entering Supvisors Discovery main loop')
        self.open_multicast()
        if self.socket:
            # create poller
            poller = select.poll()
            poller.register(self.socket, select.POLLIN)
            # run the loop until stop is called
            while not self.stopping():
                for fd, event in poller.poll(POLL_TIMEOUT):
                    if event == select.POLLIN and fd == self.socket.fileno():
                        datagram = self.socket.recvfrom(BUFFER_SIZE)
                        self.datagram_received(*datagram)
            self.socket.close()
        self.logger.info('MulticastReceiver.run: exiting Supvisors Discovery main loop')

    def datagram_received(self, data, address: Ipv4Address) -> None:
        """ Decode the message received to put it into the asynchronous queue. """
        self.logger.debug(f'MulticastReceiver.datagram_received: size={len(data)} from {address}')
        msg_type, payload = bytes_to_payload(data)
        if self.callback:
            # check the address (log only once)
            updated_address = address[0], payload['http_port']
            if updated_address not in self.log_warnings and address[0] not in payload['ip_addresses']:
                self.logger.warn(f'MulticastReceiver.datagram_received: UDP address={address[0]} does not fit'
                                 f" the discovery event {payload['ip_addresses']}")
                self.log_warnings.add(updated_address)
            # the payload is not needed for now
            self.callback(((payload['identifier'], payload['nick_identifier'], updated_address), (msg_type, ())))

    def open_multicast(self) -> None:
        """ Join the Supvisors Discovery Multicast group. """
        self.logger.debug(f'MulticastReceiver.open_multicast: creating Supvisors Discovery on {self.mc_group}')
        mc_socket = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP)
        mc_socket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        try:
            mc_socket.bind(self.mc_group)
        except (OverflowError, OSError) as exc:
            self.logger.error(f'MulticastReceiver.open_multicast: failed to bind Supvisors Discovery to {self.mc_group}'
                              f' - {str(exc)}')
            self.logger.debug(f'MulticastReceiver.open_multicast: {traceback.format_exc()}')
            return
        self.logger.info(f'MulticastReceiver.open_multicast: Supvisors Discovery opened on {self.mc_group}')
        # set multicast membership according to the configured interface
        try:
            if self.mc_interface:
                mcast_req = struct.pack('=4s4s', inet_aton(self.mc_group[0]), inet_aton(self.mc_interface))
            else:
                mcast_req = struct.pack('=4sl', inet_aton(self.mc_group[0]), INADDR_ANY)
            mc_socket.setsockopt(IPPROTO_IP, IP_ADD_MEMBERSHIP, mcast_req)
        except OSError as exc:
            self.logger.error(f'MulticastReceiver.open_multicast: failed to add membership of Supvisors Discovery'
                              f' on {self.mc_group} to interface={self.mc_interface}'
                              f' - {str(exc)}')
            self.logger.debug(f'MulticastReceiver.open_multicast: {traceback.format_exc()}')
            return
        # assign the socket
        self.socket = mc_socket


class SupvisorsDiscovery:
    """ Class holding the structures used for the emission and the reception of Supvisors discovery events.
    This is activated only if the multicast mode is configured.
    """

    def __init__(self, supvisors: Any) -> None:
        """ Construction of all internal reception blocks.

        :param supvisors: the Supvisors global structure.
        """
        # keep a reference to the Supvisors instance
        self.supvisors = supvisors
        # get the multicast parameters from the Supvisors options
        mc_group = supvisors.options.multicast_group
        mc_ttl = supvisors.options.multicast_ttl
        mc_interface = supvisors.options.multicast_interface
        # create the Multicast message emitter
        local_instance: SupvisorsInstanceId = supvisors.mapper.local_instance
        self.mc_sender: MulticastSender = MulticastSender(mc_group, mc_ttl, supvisors.logger)
        # create the Multicast message receiver
        callback = supvisors.rpc_handler.push_notification
        self.mc_receiver = MulticastReceiver(mc_group, mc_interface, callback, supvisors.logger)
        self.mc_receiver.start()

    def stop(self) -> None:
        """ Stop the Multicast receiver thread. """
        self.mc_sender.close()
        self.mc_receiver.stop()
        self.mc_receiver.join()
