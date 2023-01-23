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

import pytest

from supvisors.supvisorsmapper import *


def test_get_addresses(supvisors):
    """ Test the SupvisorsMapper.get_addresses method. """
    # complex to test as it depends on the network configuration of the operating system
    # check that there is at least one entry looking like an IPv4 address
    host_name, aliases, ip_list = get_addresses(gethostname(), supvisors.logger)
    assert re.match(r'^\d{1,3}(.\d{1,3}){3}$', ip_list[0])
    assert host_name == getfqdn()
    # test exception on unknown IP address and unknown host name
    assert get_addresses('10.4', supvisors.logger) is None
    assert get_addresses('unknown node', supvisors.logger) is None


def test_sup_id_create_no_match(supvisors):
    """ Test the values set at SupvisorsInstanceId construction. """
    no_matches = ['', 'ident>', 'cliche81:12000', '10.0.0.1:145000:28']
    # test with no match but default options loaded
    for item in no_matches:
        sup_id = SupvisorsInstanceId(item, supvisors)
        assert sup_id.identifier is None
        assert sup_id.host_id is None
        assert sup_id.http_port == 65000  # defaulted to supervisor server port
        assert sup_id.internal_port == 65100  # defaulted to options.internal_port
        assert sup_id.event_port == 65200  # defaulted to options.event_port
        assert sup_id.host_name is None
        assert sup_id.ip_address is None
        with pytest.raises(TypeError):
            str(sup_id)


def test_sup_id_create_simple_no_default(supvisors):
    """ Test the values set at SupvisorsInstanceId construction. """
    supvisors.options.internal_port = 0
    supvisors.options.event_port = 0
    # test with no match and no default option loaded
    sup_id = SupvisorsInstanceId('', supvisors)
    assert sup_id.identifier is None
    assert sup_id.host_id is None
    assert sup_id.http_port == 65000  # defaulted to supervisor server port
    assert sup_id.internal_port == 65001  # defaulted to http_port + 1
    assert sup_id.event_port == 65002  # defaulted to http_port + 2
    assert sup_id.host_name is None
    assert sup_id.ip_address is None
    with pytest.raises(TypeError):
        str(sup_id)


def test_sup_id_create_host(supvisors):
    """ Test the values set at SupvisorsInstanceId construction. """
    # test with simple host name match
    sup_id = SupvisorsInstanceId('10.0.0.1', supvisors)
    assert sup_id.identifier == '10.0.0.1'
    assert sup_id.host_id == '10.0.0.1'
    assert sup_id.http_port == 65000  # defaulted to supervisor server port
    assert sup_id.internal_port == 65100  # defaulted to options.internal_port
    assert sup_id.event_port == 65200  # defaulted to options.event_port
    assert sup_id.host_name == '10.0.0.1'
    assert sup_id.ip_address == '10.0.0.1'
    assert str(sup_id) == '10.0.0.1'


def test_sup_id_create_host_port(supvisors):
    """ Test the values set at SupvisorsInstanceId construction. """
    # test with host+ports match (internal port not defined but still in options)
    sup_id = SupvisorsInstanceId('10.0.0.1:7777:', supvisors)
    assert sup_id.identifier == '10.0.0.1:7777'
    assert sup_id.host_id == '10.0.0.1'
    assert sup_id.ip_address == '10.0.0.1'
    assert sup_id.http_port == 7777
    assert sup_id.internal_port == 65100  # defaulted to options.internal_port
    assert sup_id.event_port == 65200  # defaulted to options.event_port
    assert str(sup_id) == '10.0.0.1:7777'
    # test with host+ports match (internal port defined)
    supvisors.options.event_port = 0
    sup_id = SupvisorsInstanceId('10.0.0.1:7777:8000', supvisors)
    assert sup_id.identifier == '10.0.0.1:7777'
    assert sup_id.host_id == '10.0.0.1'
    assert sup_id.ip_address == '10.0.0.1'
    assert sup_id.http_port == 7777
    assert sup_id.internal_port == 8000
    assert sup_id.event_port == 8001  # defaulted to internal_port + 1
    assert str(sup_id) == '10.0.0.1:7777'
    # test with host+ports match (internal port defined before HTTP port)
    supvisors.options.event_port = 0
    sup_id = SupvisorsInstanceId('10.0.0.1:7777:7776', supvisors)
    assert sup_id.identifier == '10.0.0.1:7777'
    assert sup_id.host_id == '10.0.0.1'
    assert sup_id.ip_address == '10.0.0.1'
    assert sup_id.http_port == 7777
    assert sup_id.internal_port == 7776
    assert sup_id.event_port == 7778  # defaulted to http_port + 1
    assert str(sup_id) == '10.0.0.1:7777'


def test_sup_id_create_identifier(supvisors):
    """ Test the values set at SupvisorsInstanceId construction. """
    # test with identifier set and only host name
    sup_id = SupvisorsInstanceId('<supvisors>cliche81', supvisors)
    assert sup_id.identifier == 'supvisors'
    assert sup_id.host_id == 'cliche81'
    assert sup_id.ip_address == 'cliche81'
    assert sup_id.http_port == 65000
    assert sup_id.internal_port == 65100  # defaulted to options.internal_port
    assert sup_id.event_port == 65200  # defaulted to options.event_port
    # test with identifier set
    sup_id = SupvisorsInstanceId('<supvisors>cliche81:8888:5555', supvisors)
    assert sup_id.identifier == 'supvisors'
    assert sup_id.host_id == 'cliche81'
    assert sup_id.ip_address == 'cliche81'
    assert sup_id.http_port == 8888
    assert sup_id.internal_port == 5555  # defaulted to options.internal_port
    assert sup_id.event_port == 65200  # defaulted to options.event_port


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
    for item in items:
        supvisors_id = SupvisorsInstanceId(item, mapper.supvisors)
        mapper._instances[supvisors_id.identifier] = supvisors_id
    # force host name to FQDN
    mapper._instances[host_name].host_name = getfqdn()
    # find self
    mapper.find_local_identifier()
    assert mapper.local_identifier == host_name


def test_find_local_identifier_host_name(mapper):
    """ Test the SupvisorsMapper.find_local_identifier method when one instance matches the host name and the HTTP
    server port. """
    host_name = gethostname()
    items = ['127.0.0.1', f'{host_name}:65000:7777']
    for item in items:
        supvisors_id = SupvisorsInstanceId(item, mapper.supvisors)
        mapper._instances[supvisors_id.identifier] = supvisors_id
    # force host name to FQDN
    mapper._instances[f'{host_name}:65000'].host_name = getfqdn()
    # find self
    mapper.find_local_identifier()
    assert mapper.local_identifier == f'{host_name}:65000'


def test_find_local_identifier_ip_address(mapper):
    """ Test the SupvisorsMapper.find_local_identifier method when one instance matches the IP address of the host
    and the HTTP server port. """
    host_name, _, ip_addresses = gethostbyaddr(gethostname())
    items = ['127.0.0.1', f'<host>{ip_addresses[0]}:65000:7777']
    for item in items:
        supvisors_id = SupvisorsInstanceId(item, mapper.supvisors)
        mapper._instances[supvisors_id.identifier] = supvisors_id
    # force host name to FQDN
    mapper._instances['host'].host_name = getfqdn()
    # find self
    mapper.find_local_identifier()
    assert mapper.local_identifier == 'host'


def test_find_local_identifier_inconsistent(mapper):
    """ Test the SupvisorsMapper.find_local_identifier method when the identifier corresponds to thr local Supvisors
    instance but the host_name and http_port do not match. """
    host_name = gethostname()
    supvisors_id = SupvisorsInstanceId(f'<{host_name}>10.0.0.5:7777:', mapper.supvisors)
    mapper._instances[supvisors_id.identifier] = supvisors_id
    # find self
    print(mapper.supvisors.supervisor_data.identifier)
    with pytest.raises(ValueError):
        mapper.find_local_identifier()


def test_find_local_identifier_multiple(mapper):
    """ Test the SupvisorsMapper.find_local_identifier method when more than one instance matches the host name
    or IP address of the host. """
    host_name = gethostname()
    fqdn = getfqdn()
    items = ['10.0.0.1', f'{host_name}:65000:7777']
    for item in items:
        supvisors_id = SupvisorsInstanceId(item, mapper.supvisors)
        mapper._instances[supvisors_id.identifier] = supvisors_id
        # update default processing of host
        supvisors_id.host_name = fqdn
    # find self
    with pytest.raises(ValueError):
        mapper.find_local_identifier()


def test_find_local_identifier_none(mapper):
    """ Test the SupvisorsMapper.find_local_identifier method when no instance matches the host name
    or IP address of the host. """
    host_name = gethostname()
    items = ['10.0.0.2', '<dummy>cliche:60000:7777', f'{host_name}:60000:7777']
    for item in items:
        supvisors_id = SupvisorsInstanceId(item, mapper.supvisors)
        mapper._instances[supvisors_id.identifier] = supvisors_id
    with pytest.raises(ValueError):
        mapper.find_local_identifier()


def test_valid(mapper):
    """ Test the SupvisorsMapper.valid method. """
    # add context
    hostname = gethostname()
    items = ['127.0.0.1', '<host>10.0.0.1:2222:', f'{hostname}:60000:7777']
    for item in items:
        supvisors_id = SupvisorsInstanceId(item, mapper.supvisors)
        mapper._instances[supvisors_id.identifier] = supvisors_id
    # force host name to FQDN
    mapper._instances[f'{hostname}:60000'].host_name = getfqdn()
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
    for item in items:
        supvisors_id = SupvisorsInstanceId(item, mapper.supvisors)
        mapper._instances[supvisors_id.identifier] = supvisors_id
    # force host name to FQDN
    mapper._instances[f'{hostname}:60000'].host_name = getfqdn()
    # test with a bunch of identifiers
    identifier_list = ['127.0.0.1', 'host', f'{hostname}:60000', hostname, 'host', 'supervisor', '10.0.0.1']
    assert mapper.filter(identifier_list) == ['127.0.0.1', 'host', f'{hostname}:60000']
