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

from supvisors.supvisorsmapper import *


def test_supid_create_no_match(supvisors):
    """ Test the values set at SupvisorsInstanceId construction. """
    no_matches = ['', 'ident>', 'cliche81:12000', '10.0.0.1:145000:28']
    # test with no match but default options loaded
    for item in no_matches:
        supid = SupvisorsInstanceId(item, supvisors)
        assert supid.identifier is None
        assert supid.host_name is None
        assert supid.http_port == 65000  # defaulted to supervisor server port
        assert supid.internal_port == 65100  # defaulted to options.internal_port
        assert supid.event_port == 65200  # defaulted to options.event_port
        with pytest.raises(TypeError):
            str(supid)


def test_supid_create_simple_no_default(supvisors):
    """ Test the values set at SupvisorsInstanceId construction. """
    supvisors.options.internal_port = 0
    supvisors.options.event_port = 0
    # test with no match and no default option loaded
    supid = SupvisorsInstanceId('', supvisors)
    assert supid.identifier is None
    assert supid.host_name is None
    assert supid.http_port == 65000  # defaulted to supervisor server port
    assert supid.internal_port == 65001  # defaulted to http_port + 1
    assert supid.event_port == 65002  # defaulted to http_port + 2
    with pytest.raises(TypeError):
        str(supid)


def test_supid_create_host(supvisors):
    """ Test the values set at SupvisorsInstanceId construction. """
    # test with simple host name match
    supid = SupvisorsInstanceId('10.0.0.1', supvisors)
    assert supid.identifier == '10.0.0.1'
    assert supid.host_name == '10.0.0.1'
    assert supid.http_port == 65000  # defaulted to supervisor server port
    assert supid.internal_port == 65100  # defaulted to options.internal_port
    assert supid.event_port == 65200  # defaulted to options.event_port
    assert str(supid) == '10.0.0.1'


def test_supid_create_host_port(supvisors):
    """ Test the values set at SupvisorsInstanceId construction. """
    # test with host+ports match (internal port not defined but still in options)
    supid = SupvisorsInstanceId('10.0.0.1:7777:', supvisors)
    assert supid.identifier == '10.0.0.1:7777'
    assert supid.host_name == '10.0.0.1'
    assert supid.http_port == 7777
    assert supid.internal_port == 65100  # defaulted to options.internal_port
    assert supid.event_port == 65200  # defaulted to options.event_port
    assert str(supid) == '10.0.0.1:7777'
    # test with host+ports match (internal port defined)
    supvisors.options.event_port = 0
    supid = SupvisorsInstanceId('10.0.0.1:7777:8000', supvisors)
    assert supid.identifier == '10.0.0.1:7777'
    assert supid.host_name == '10.0.0.1'
    assert supid.http_port == 7777
    assert supid.internal_port == 8000
    assert supid.event_port == 8001  # defaulted to internal_port + 1
    assert str(supid) == '10.0.0.1:7777'
    # test with host+ports match (internal port defined before HTTP port)
    supvisors.options.event_port = 0
    supid = SupvisorsInstanceId('10.0.0.1:7777:7776', supvisors)
    assert supid.identifier == '10.0.0.1:7777'
    assert supid.host_name == '10.0.0.1'
    assert supid.http_port == 7777
    assert supid.internal_port == 7776
    assert supid.event_port == 7778  # defaulted to http_port + 1
    assert str(supid) == '10.0.0.1:7777'


def test_supid_create_identifier(supvisors):
    """ Test the values set at SupvisorsInstanceId construction. """
    # test with identifier set and only host name
    supid = SupvisorsInstanceId('<supvisors>cliche81', supvisors)
    assert supid.identifier == 'supvisors'
    assert supid.host_name == 'cliche81'
    assert supid.http_port == 65000
    assert supid.internal_port == 65100  # defaulted to options.internal_port
    assert supid.event_port == 65200  # defaulted to options.event_port
    # test with identifier set
    supid = SupvisorsInstanceId('<supvisors>cliche81:8888:5555', supvisors)
    assert supid.identifier == 'supvisors'
    assert supid.host_name == 'cliche81'
    assert supid.http_port == 8888
    assert supid.internal_port == 5555  # defaulted to options.internal_port
    assert supid.event_port == 65200  # defaulted to options.event_port


@pytest.fixture
def mapper(supvisors):
    """ Return the instance to test. """
    return SupvisorsMapper(supvisors)


def test_mapper_create(supvisors, mapper):
    """ Test the values set at construction. """
    assert mapper.supvisors is supvisors
    assert mapper.logger is supvisors.logger
    assert mapper.instances == {}
    assert mapper.nodes == {}
    assert mapper.local_identifier is None
    # check that hostname is part of the local addresses
    assert gethostname() in mapper.local_node_references


def test_mapper_configure(mocker, mapper):
    """ Test the storage of the expected Supvisors instances. """
    mocked_find = mocker.patch.object(mapper, 'find_local_identifier')
    # configure mapper with elements
    items = ['127.0.0.1', '<supervisor_05>10.0.0.5:7777:', '10.0.0.4:15000:8888', '10.0.0.5:9999:']
    core_items = ['127.0.0.1', 'supervisor_05', '10.0.0.4:15000', 'supervisor_06', '10.0.0.4']
    mapper.configure(items, core_items)
    assert list(mapper.instances.keys()) == ['127.0.0.1', 'supervisor_05', '10.0.0.4:15000', '10.0.0.5:9999']
    assert mapper.core_identifiers == ['127.0.0.1', 'supervisor_05', '10.0.0.4:15000']
    assert mapper.nodes == {'127.0.0.1': ['127.0.0.1'], '10.0.0.5': ['supervisor_05', '10.0.0.5:9999'],
                            '10.0.0.4': ['10.0.0.4:15000']}
    assert mocked_find.called
    mocked_find.reset_mock()
    # configure mapper with one invalid element
    items = ['127.0.0.1', '<dummy_id>', '<supervisor_05>10.0.0.5', '10.0.0.4:15000']
    with pytest.raises(ValueError):
        mapper.configure(items, core_items)
    assert not mocked_find.called


def test_find_local_identifier_identifier(mapper):
    """ Test the SupvisorsMapper.find_local_identifier method when Supervisor identifier is among the instances. """
    host_name = gethostname()
    items = [host_name, '<supervisor>10.0.0.5:7777:']
    mapper.configure(items, [])
    assert mapper.local_identifier == host_name


def test_find_local_identifier_host_name(mapper):
    """ Test the SupvisorsMapper.find_local_identifier method when one instance matches the host name. """
    hostname = gethostname()
    items = ['127.0.0.1', f'{hostname}:60000:7777']
    mapper.configure(items, [])
    assert mapper.local_identifier == f'{hostname}:60000'


def test_find_local_identifier_ip_address(mapper):
    """ Test the SupvisorsMapper.find_local_identifier method when one instance matches the IP address of the host. """
    hostname = gethostname()
    mapper.local_node_references = [hostname, '10.0.0.1']
    items = ['127.0.0.1', '<host>10.0.0.1:60000:7777']
    mapper.configure(items, [])
    assert mapper.local_identifier == 'host'


def test_find_local_identifier_multiple(mapper):
    """ Test the SupvisorsMapper.find_local_identifier method when more than one instance matches the host name
    or IP address of the host. """
    hostname = gethostname()
    mapper.local_node_references = [hostname, '10.0.0.1']
    items = ['10.0.0.1', f'{hostname}:60000:7777']
    with pytest.raises(ValueError):
        mapper.configure(items, [])


def test_find_local_identifier_none(mapper):
    """ Test the SupvisorsMapper.find_local_identifier method when more than no instance matches the host name
    or IP address of the host. """
    mapper.local_node_references = ['10.0.0.1']
    items = ['10.0.0.2', '<dummy>cliche:60000:7777']
    with pytest.raises(ValueError):
        mapper.configure(items, [])


def test_valid(mapper):
    """ Test the SupvisorsMapper.valid method. """
    # add context
    hostname = gethostname()
    items = ['127.0.0.1', '<host>10.0.0.1:2222:', f'{hostname}:60000:7777']
    mapper.configure(items, [])
    # test calls
    assert mapper.valid('127.0.0.1')
    assert mapper.valid('host')
    assert mapper.valid(f'{hostname}:60000')
    assert not mapper.valid(hostname)
    assert not mapper.valid('supervisor')
    assert not mapper.valid('10.0.0.1')


def test_filter(mapper):
    """ Test the SupvisorsMapper.filter method. """
    # add context
    hostname = gethostname()
    items = ['127.0.0.1', '<host>10.0.0.1:2222:', f'{hostname}:60000:7777']
    mapper.configure(items, [])
    # test with a bunch of identifiers
    identifier_list = ['127.0.0.1', 'host', f'{hostname}:60000', hostname, 'host', 'supervisor', '10.0.0.1']
    assert mapper.filter(identifier_list) == ['127.0.0.1', 'host', f'{hostname}:60000']


def test_ipv4():
    """ Test the ipv4 method. """
    # complex to test as it depends on the network configuration of the operating system
    # check that there is at least one entry looking like an IP address
    # test that psutil is installed
    pytest.importorskip('psutil', reason='cannot test as optional psutil is not installed')
    # test function
    ip_list = SupvisorsMapper.ipv4()
    assert ip_list
    for ip in ip_list:
        assert re.match(r'^\d{1,3}(.\d{1,3}){3}$', ip)


def test_ipv4_importerror(mocker):
    """ Test the ipv4 method with a mocking of import (psutil not installed). """
    mocker.patch.dict('sys.modules', {'psutil': None})
    assert SupvisorsMapper.ipv4() == []
