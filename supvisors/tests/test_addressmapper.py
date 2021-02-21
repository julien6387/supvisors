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

import sys
import random
import socket
import unittest

from unittest.mock import patch, Mock

from supervisor.loggers import Logger

from supvisors.tests.base import CompatTestCase


class AddressMapperTest(CompatTestCase):
    """ Test case for the addressmapper module. """

    def setUp(self):
        """ Create a logger that stores log traces. """
        self.logger = Mock(spec=Logger)

    def test_create(self):
        """ Test the values set at construction. """
        from supvisors.addressmapper import AddressMapper
        mapper = AddressMapper(self.logger)
        self.assertIs(self.logger, mapper.logger)
        self.assertFalse(mapper.addresses)
        self.assertIsNone(mapper.local_address)
        # check that hostname is part of the local addresses
        self.assertIn(socket.gethostname(), mapper.local_addresses)

    def test_addresses(self):
        """ Test the storage of the expected addresses. """
        from supvisors.addressmapper import AddressMapper
        mapper = AddressMapper(self.logger)
        # set addresses with hostname inside (IP addresses are not valid on purpose)
        hostname = socket.gethostname()
        address_lst = [hostname, '292.168.0.1', '292.168.0.2']
        mapper.addresses = address_lst
        self.assertListEqual(address_lst, mapper.addresses)
        # check that hostname is the local address
        self.assertEqual(hostname, mapper.local_address)
        # set addresses with invalid IP addresses only
        address_lst = ['292.168.0.1', '292.168.0.2']
        mapper.addresses = address_lst
        self.assertListEqual(address_lst, mapper.addresses)
        # check that the local address is not set
        self.assertIsNone(mapper.local_address)

    def test_valid(self):
        """ Test the valid method. """
        from supvisors.addressmapper import AddressMapper
        mapper = AddressMapper(self.logger)
        # test that nothing is valid before addresses are set
        hostname = socket.gethostname()
        self.assertFalse(mapper.valid(hostname))
        self.assertFalse(mapper.valid('192.168.0.1'))
        self.assertFalse(mapper.valid('192.168.0.3'))
        # set addresses
        address_lst = [hostname, '192.168.0.1', '192.168.0.2']
        mapper.addresses = address_lst
        # test the validity of addresses
        self.assertTrue(mapper.valid(hostname))
        self.assertTrue(mapper.valid('192.168.0.1'))
        self.assertFalse(mapper.valid('192.168.0.3'))

    def test_filter(self):
        """ Test the filter method. """
        from supvisors.addressmapper import AddressMapper
        mapper = AddressMapper(self.logger)
        # set addresses with hostname inside (IP addresses are not valid on purpose)
        hostname = socket.gethostname()
        address_lst = [hostname, '292.168.0.1', '292.168.0.2']
        mapper.addresses = address_lst
        # test that the same list with a different sequence is not filtered
        shuffle_lst1 = address_lst[:]
        random.shuffle(shuffle_lst1)
        self.assertEqual(shuffle_lst1, mapper.filter(shuffle_lst1))
        # test that an subset of the sequence is not filtered
        shuffle_lst2 = shuffle_lst1[:]
        shuffle_lst2.pop()
        self.assertListEqual(shuffle_lst2, mapper.filter(shuffle_lst2))
        # test that an invalid entry in the sequence is filtered
        shuffle_lst2 = ['292.168.0.3'] + shuffle_lst1
        self.assertListEqual(shuffle_lst1, mapper.filter(shuffle_lst2))

    def test_expected(self):
        """ Test the expected method. """
        from supvisors.addressmapper import AddressMapper
        mapper = AddressMapper(self.logger)
        # set addresses with hostname inside (IP addresses are not valid on purpose)
        hostname = socket.gethostname()
        address_lst = ['292.168.0.1', '292.168.0.2', hostname]
        mapper.addresses = address_lst
        # find expected address from list of aliases of the same address
        alias_lst = ['292.168.0.1', '10.0.200.1', '66.51.20.300']
        self.assertEqual('292.168.0.1', mapper.expected(alias_lst))
        # second try
        random.shuffle(alias_lst)
        self.assertEqual('292.168.0.1', mapper.expected(alias_lst))
        # check with list containing no corresponding entry
        alias_lst = ['292.168.0.3', '10.0.200.1', '66.51.20.300']
        self.assertIsNone(mapper.expected(alias_lst))

    def test_ipv4(self):
        """ Test the ipv4 method. """
        # complex to test as it depends on the network configuration of the operating system
        # check that there is at least one entry looking like an IP address
        from supvisors.addressmapper import AddressMapper
        # test that netifaces is installed
        try:
            import netifaces
            netifaces.__name__
        except ImportError:
            raise unittest.SkipTest('cannot test as optional netifaces is not installed')
        # test function
        ip_list = AddressMapper.ipv4()
        self.assertTrue(ip_list)
        for ip in ip_list:
            self.assertRegex(ip, r'^\d{1,3}(.\d{1,3}){3}$')

    @patch.dict('sys.modules', {'netifaces': None})
    def test_ipv4_importerror(self):
        """ Test the ipv4 method with a mocking of import (netifaces not installed). """
        from supvisors.addressmapper import AddressMapper
        ip_list = AddressMapper.ipv4()
        self.assertFalse(ip_list)


def test_suite():
    return unittest.findTestCases(sys.modules[__name__])


if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
