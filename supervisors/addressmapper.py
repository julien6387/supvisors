#!/usr/bin/python
#-*- coding: utf-8 -*-

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

from supervisors.options import options

class _AddressMapper(object):
    def __init__(self):
        import socket
        self.localAddresses = [ socket.gethostname() ] + self.__ipv4_addresses()

    def setAddresses(self, addresses):
        options.logger.info('Expected addresses: {}'.format(addresses))
        # store IP list as found in config file
        self.expectedAddresses = addresses
        self.mapping = {}
        # get IP list for local board
        self.localAddress = self._getExpectedAddress(self.localAddresses)
        options.logger.info('Local addresses: {} - Local address: {}'.format(self.localAddresses, self.localAddress))
 
    def isAddressValid(self, address):
        return address in self.expectedAddresses

    # returns a list of expected addresses from a list of names or ip addresses identifying different locations
    def filterAddresses(self, addressList):
        # filter unknown addresses
        addresses = [ address for address in addressList if self.isAddressValid(address) ]
        # remove duplicates keeping the same ordering
        from collections import OrderedDict
        return list(OrderedDict.fromkeys(addresses))

   # returns the expected address from a list of names or ip addresses identifying the same location
    def _getExpectedAddress(self, addressList):
        return next((address for address in addressList if self.isAddressValid(address)),  None)

   # WARN: the following version is dead code
   # it might be somehow reactivated if aliases are allowed for XML-RPC
    def __getExpectedAddress(self, addressList):
        expectedAddress = None
        if not addressList:
            options.logger.error('empty address list')
        else:
            # first search in mapping using the first element only, expecting that it corresponds to the hostname.
            # other entries may include an internal network address that may be present several times
            expectedAddress = self.mapping.get(addressList[0], None)
            if not expectedAddress:
                # if not found, search among Supervisors addresses
                options.logger.trace('searching any of {} among expected addresses'.format(addressList))
                expectedAddress = next((address for address in addressList if self.isAddressValid(address)),  None)
                if not expectedAddress:
                    options.logger.error('cannot find any of {} in expected addresses {}'.format(addressList, self.expectedAddresses) )
                else:
                    # add list in mapping using the expected address found
                    options.logger.info('inserting {} into mapping with correspondence: {}'.format(addressList, expectedAddress))
                    self.mapping.update( [ (address, expectedAddress) for address in addressList ] )
        return expectedAddress

    def __ipv4_addresses(self):
        from netifaces import interfaces, ifaddresses, AF_INET
        # get all IPv4 addresses for all interfaces
        ipList = [ link['addr'] for interface in interfaces() for link in ifaddresses(interface)[AF_INET] ]
        # remove loopback address (no interest here)
        ipList.remove('127.0.0.1')
        return ipList

addressMapper = _AddressMapper()
