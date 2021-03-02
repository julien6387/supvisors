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

from socket import gethostname
from collections import OrderedDict


class AddressMapper(object):
    """ Class used for storage of the addresses defined in the configuration file.
    These addresses are expected to be host names or IP addresses where a Supvisors instance is running.
    The instance holds:
        - logger: a reference to the common logger,
        - addresses: the list of addresses defined in the Supvisors configuration file,
        - local_addresses: the list of known aliases of the current host, i.e. the host name and the IPv4 addresses,
        - local_address: the usage name of the current host, i.e. the name in the known aliases corresponding to an address of the Supvisors list. """

    def __init__(self, logger):
        """ Initialization of the attributes. """
        # keep reference of common logger
        self.logger = logger
        # init
        self._addresses = []
        self.local_addresses = [gethostname()] + self.ipv4()
        self.local_address = None

    @property
    def addresses(self):
        """ Property for the 'address' attribute.
        The setter stores the addresses of the configuration file and determine the usage name of the local address. """
        return self._addresses

    @addresses.setter
    def addresses(self, addr):
        """ Determine usage name of local address among the addresses provided in option file. """
        self.logger.info('Expected addresses: {}'.format(addr))
        # store IP list as found in config file
        self._addresses = addr
        # get IP list for local node
        self.local_address = self.expected(self.local_addresses)
        self.logger.info('Local addresses: {} - Local address: {}'.format(self.local_addresses, self.local_address))

    def valid(self, address):
        """ Return True if address is among the addresses defined in the configuration file. """
        return address in self._addresses

    def filter(self, address_list):
        """ Returns a list of expected nodes from a list of names or ip addresses identifying different locations. """
        # filter unknown addresses
        addresses = [address for address in address_list if self.valid(address)]
        # remove duplicates keeping the same ordering
        return list(OrderedDict.fromkeys(addresses))

    def expected(self, address_list):
        """ Returns the expected address from a list of names or ip addresses identifying the same location. """
        return next((address for address in address_list if self.valid(address)), None)

    @staticmethod
    def ipv4():
        """ Get all IPv4 addresses for all interfaces. """
        try:
            from netifaces import interfaces, ifaddresses, AF_INET
            # to not take into account loopback addresses (no interest here)
            addresses = []
            for interface in interfaces():
                config = ifaddresses(interface)
                # AF_INET is not always present
                if AF_INET in config.keys():
                    for link in config[AF_INET]:
                        # loopback holds a 'peer' instead of a 'broadcast' address
                        if 'addr' in link.keys() and 'peer' not in link.keys():
                            addresses.append(link['addr'])
            return addresses
        except ImportError:
            return []
