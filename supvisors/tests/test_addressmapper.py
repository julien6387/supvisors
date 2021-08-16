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

import pytest
import random
import re
import socket

from supvisors.addressmapper import AddressMapper


@pytest.fixture
def mapper(supvisors):
    """ Return the instance to test. """
    return AddressMapper(supvisors.logger)


def test_create(supvisors, mapper):
    """ Test the values set at construction. """
    assert mapper.logger == supvisors.logger
    assert mapper.node_names == []
    assert mapper.local_node_name is None
    # check that hostname is part of the local addresses
    assert socket.gethostname() in mapper.local_node_references


def test_addresses(mapper):
    """ Test the storage of the expected addresses. """
    # set addresses with hostname inside (IP addresses are not valid on purpose)
    hostname = socket.gethostname()
    address_lst = [hostname, '292.168.0.1', '292.168.0.2']
    mapper.node_names = address_lst
    assert mapper.node_names == address_lst
    # check that hostname is the local address
    assert mapper.local_node_name == hostname
    # set addresses with invalid IP addresses only
    address_lst = ['292.168.0.1', '292.168.0.2']
    mapper.node_names = address_lst
    assert mapper.node_names == address_lst
    # check that the local address is not set
    assert mapper.local_node_name is None


def test_valid(mapper):
    """ Test the valid method. """
    # test that nothing is valid before addresses are set
    hostname = socket.gethostname()
    assert not mapper.valid(hostname)
    assert not mapper.valid('192.168.0.1')
    assert not mapper.valid('192.168.0.3')
    # set addresses
    address_lst = [hostname, '192.168.0.1', '192.168.0.2']
    mapper.node_names = address_lst
    # test the validity of addresses
    assert mapper.valid(hostname)
    assert mapper.valid('192.168.0.1')
    assert not mapper.valid('192.168.0.3')


def test_filter(mapper):
    """ Test the filter method. """
    # set addresses with hostname inside (IP addresses are not valid on purpose)
    hostname = socket.gethostname()
    node_lst = [hostname, '292.168.0.1', '292.168.0.2']
    mapper.node_names = node_lst
    # test that the same list with a different sequence is not filtered
    shuffle_lst1 = node_lst[:]
    random.shuffle(shuffle_lst1)
    assert mapper.filter(shuffle_lst1) == shuffle_lst1
    # test that an subset of the sequence is not filtered
    shuffle_lst2 = shuffle_lst1[:]
    shuffle_lst2.pop()
    assert mapper.filter(shuffle_lst2) == shuffle_lst2
    # test that an invalid entry in the sequence is filtered
    shuffle_lst2 = ['292.168.0.3'] + shuffle_lst1
    assert mapper.filter(shuffle_lst2) == shuffle_lst1


def test_expected(mapper):
    """ Test the expected method. """
    # set addresses with hostname inside (IP addresses are not valid on purpose)
    hostname = socket.gethostname()
    node_lst = ['292.168.0.1', '292.168.0.2', hostname]
    mapper.node_names = node_lst
    # find expected address from list of aliases of the same address
    alias_lst = ['292.168.0.1', '10.0.200.1', '66.51.20.300']
    assert mapper.expected(alias_lst) == '292.168.0.1'
    # second try
    random.shuffle(alias_lst)
    assert mapper.expected(alias_lst) == '292.168.0.1'
    # check with list containing no corresponding entry
    alias_lst = ['292.168.0.3', '10.0.200.1', '66.51.20.300']
    assert mapper.expected(alias_lst) is None


def test_ipv4():
    """ Test the ipv4 method. """
    # complex to test as it depends on the network configuration of the operating system
    # check that there is at least one entry looking like an IP address
    # test that psutil is installed
    pytest.importorskip('psutil', reason='cannot test as optional psutil is not installed')
    # test function
    ip_list = AddressMapper.ipv4()
    assert ip_list
    for ip in ip_list:
        assert re.match(r'^\d{1,3}(.\d{1,3}){3}$', ip)


def test_ipv4_importerror(mocker):
    """ Test the ipv4 method with a mocking of import (psutil not installed). """
    mocker.patch.dict('sys.modules', {'psutil': None})
    assert AddressMapper.ipv4() == []
