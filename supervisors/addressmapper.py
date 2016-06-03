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

from supervisors.options import mainOptions as opt

class AddressMapper(object):
    def __init__(self):
        import socket
        self._localAddresses = [ socket.gethostname() ] + self.__ipv4_addresses()

    def setAddresses(self,  addresses):
        opt.logger.info('Expected addresses: {}'.format(addresses))
        # store IP list as found in config file
        self._expectedAddresses = addresses
        self._mapping = {}
        # get IP list for local board
        self._localAddress = self.getExpectedAddress(self._localAddresses,  True)
        opt.logger.info('Local addresses: {} - Local address: {}'.format(self._localAddresses, self._localAddress))
 
    @property
    def expectedAddress(self): return self._localAddress
    @property
    def expectedAddresses(self): return self._expectedAddresses
    @property
    def localAddresses(self): return self._localAddresses
 
    # returns the expected address from a list of names or ip addresses identifying the same location
    def getExpectedAddress(self, addressList, insertIfNew=None):
        expectedAddress = None
        if not addressList:
            opt.logger.error('empty address list')
        else:
            # first search in mapping using the first element only, expecting that it corresponds to the hostname.
            # other entries may include an internal network address that may be present several times
            expectedAddress = self.__getMappingAddress(addressList[0])
            if not expectedAddress:
                # if not found, search among Supervisors addresses
                expectedAddress = self.__getExpectedAddress(addressList)
                if not expectedAddress:
                    opt.logger.error('cannot find any of {} in expected addresses {}'.format(addressList, self.expectedAddresses) )
                elif insertIfNew:
                    # add list in mapping using the expected address found
                    self.__updateMapping(expectedAddress,  addressList)
        return expectedAddress

    # returns a list of expected addresses from a list of names or ip addresses identifying different locations
    def getExpectedAddresses(self, addressList):
        addresses = [ self.getExpectedAddress([address]) for address in addressList ]
        from collections import OrderedDict
        return list(OrderedDict.fromkeys(addresses))

    def __getMappingAddress(self, address):
        opt.logger.trace('searching %s in mapping' % address)
        return self._mapping[address] if address in self._mapping else None

    def __getExpectedAddress(self, addressList):
        opt.logger.trace('searching any of {} among expected addresses'.format(addressList))
        return next((address for address in addressList if address in self.expectedAddresses),  None)

    def __updateMapping(self, expectedAddress, addressList):
        opt.logger.info('inserting {} into mapping with correspondence: {}'.format(addressList, expectedAddress))
        self._mapping.update( [ (address,  expectedAddress) for address in addressList] )

    def __ipv4_addresses(self):
        from netifaces import interfaces, ifaddresses, AF_INET
        # get all IPv4 addresses for all interfaces
        ipList = [ link['addr'] for interface in interfaces() for link in ifaddresses(interface)[AF_INET] ]
        # remove loopback address (no interest here)
        ipList.remove('127.0.0.1')
        return ipList

addressMapper = AddressMapper()


# for tests
if __name__ == "__main__":
    import socket
    addressMapper.setAddresses([ socket.gethostname(), 'dumb01'])
    print addressMapper.getExpectedAddress([]) 
    print addressMapper.getExpectedAddress([ 'dumber01', 'dumb01' ]) 
    print addressMapper.getExpectedAddress([ 'dumber01', 'dumb01' ],  False) 
    print addressMapper.getExpectedAddress([ 'dumber01', 'dumb01' ],  True) 
    print addressMapper.getExpectedAddress([ 'dumber01', 'dumb01' ]) 
