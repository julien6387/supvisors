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

from unittest.mock import call

import pytest

from supvisors.internal_com.mapper import *


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
        assert sup_id.aliases is None
        assert sup_id.ip_addresses is None
        assert sup_id.ip_address is None
        assert sup_id.stereotypes == []
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
    assert sup_id.aliases is None
    assert sup_id.ip_addresses is None
    assert sup_id.ip_address is None
    assert sup_id.stereotypes == []
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
    assert sup_id.aliases == ['10.0.0.1']
    assert sup_id.ip_addresses == ['10.0.0.1']
    assert sup_id.ip_address == '10.0.0.1'
    assert sup_id.stereotypes == []
    assert str(sup_id) == '10.0.0.1'


def test_sup_id_create_host_port(supvisors):
    """ Test the values set at SupvisorsInstanceId construction. """
    # test with host+ports match (internal port not defined but still in options)
    sup_id = SupvisorsInstanceId('10.0.0.1:7777:', supvisors)
    assert sup_id.identifier == '10.0.0.1:7777'
    assert sup_id.host_id == '10.0.0.1'
    assert sup_id.http_port == 7777
    assert sup_id.internal_port == 65100  # defaulted to options.internal_port
    assert sup_id.event_port == 65200  # defaulted to options.event_port
    assert sup_id.host_name == '10.0.0.1'
    assert sup_id.aliases == ['10.0.0.1']
    assert sup_id.ip_addresses == ['10.0.0.1']
    assert sup_id.ip_address == '10.0.0.1'
    assert sup_id.stereotypes == []
    assert str(sup_id) == '10.0.0.1:7777'
    # test with host+ports match (internal port defined)
    supvisors.options.event_port = 0
    sup_id = SupvisorsInstanceId('10.0.0.1:7777:8000', supvisors)
    assert sup_id.identifier == '10.0.0.1:7777'
    assert sup_id.host_id == '10.0.0.1'
    assert sup_id.http_port == 7777
    assert sup_id.internal_port == 8000
    assert sup_id.host_name == '10.0.0.1'
    assert sup_id.aliases == ['10.0.0.1']
    assert sup_id.ip_addresses == ['10.0.0.1']
    assert sup_id.ip_address == '10.0.0.1'
    assert sup_id.event_port == 8001  # defaulted to internal_port + 1
    assert sup_id.stereotypes == []
    assert str(sup_id) == '10.0.0.1:7777'
    # test with host+ports match (internal port defined before HTTP port)
    supvisors.options.event_port = 0
    sup_id = SupvisorsInstanceId('10.0.0.1:7777:7776', supvisors)
    assert sup_id.identifier == '10.0.0.1:7777'
    assert sup_id.host_id == '10.0.0.1'
    assert sup_id.http_port == 7777
    assert sup_id.internal_port == 7776
    assert sup_id.event_port == 7778  # defaulted to http_port + 1
    assert sup_id.host_name == '10.0.0.1'
    assert sup_id.aliases == ['10.0.0.1']
    assert sup_id.ip_addresses == ['10.0.0.1']
    assert sup_id.ip_address == '10.0.0.1'
    assert sup_id.stereotypes == []
    assert str(sup_id) == '10.0.0.1:7777'


def test_sup_id_create_identifier(supvisors):
    """ Test the values set at SupvisorsInstanceId construction. """
    # test with identifier set and only host name
    sup_id = SupvisorsInstanceId('<supvisors>cliche81', supvisors)
    assert sup_id.identifier == 'supvisors'
    assert sup_id.host_id == 'cliche81'
    assert sup_id.http_port == 65000
    assert sup_id.internal_port == 65100  # defaulted to options.internal_port
    assert sup_id.event_port == 65200  # defaulted to options.event_port
    assert sup_id.host_name == 'cliche81'
    assert sup_id.aliases == ['cliche81']
    assert sup_id.ip_addresses == ['cliche81']
    assert sup_id.ip_address == 'cliche81'
    assert sup_id.stereotypes == []
    # test with identifier set
    sup_id = SupvisorsInstanceId('<supvisors>cliche81:8888:5555', supvisors)
    assert sup_id.identifier == 'supvisors'
    assert sup_id.host_id == 'cliche81'
    assert sup_id.http_port == 8888
    assert sup_id.internal_port == 5555  # defaulted to options.internal_port
    assert sup_id.event_port == 65200  # defaulted to options.event_port
    assert sup_id.host_name == 'cliche81'
    assert sup_id.aliases == ['cliche81']
    assert sup_id.ip_addresses == ['cliche81']
    assert sup_id.ip_address == 'cliche81'
    assert sup_id.stereotypes == []


def test_sup_id_host_matches(supvisors):
    """ Test the SupvisorsInstanceId.host_matches method. """
    sup_id = SupvisorsInstanceId('<supvisors>cliche81', supvisors)
    sup_id.aliases = ['cliche', 'rocky51']
    assert sup_id.host_matches('cliche81')
    assert sup_id.host_matches('cliche')
    assert sup_id.host_matches('rocky51')
    assert not sup_id.host_matches('rocky')


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
    assert mapper.initial_identifiers == []


def test_add_instance(mapper):
    """ Test the SupvisorsMapper.add_instance method. """
    # test error (no IP address)
    with pytest.raises(ValueError):
        mapper.add_instance('<dummy>:1234:', False)
    assert mapper.instances == {}
    assert mapper.nodes == {}
    with pytest.raises(ValueError):
        mapper.add_instance('<dummy>:1234:4321')
    assert mapper.instances == {}
    assert mapper.nodes == {}
    # test correct format without discovery log
    mapper.add_instance('<dummy_1>10.0.0.1:1234:4321', False)
    assert list(mapper.instances.keys()) == ['dummy_1']
    assert mapper.nodes == {'10.0.0.1': ['dummy_1']}
    mapper.add_instance('10.0.0.2:1234:', False)
    assert sorted(mapper.instances.keys()) == ['10.0.0.2:1234', 'dummy_1']
    assert mapper.nodes == {'10.0.0.1': ['dummy_1'], '10.0.0.2': ['10.0.0.2:1234']}
    # test correct format with discovery log
    mapper.add_instance('<dummy_2>10.0.0.1:1234:4321')
    assert sorted(mapper.instances.keys()) == ['10.0.0.2:1234', 'dummy_1', 'dummy_2']
    assert mapper.nodes == {'10.0.0.1': ['dummy_1', 'dummy_2'], '10.0.0.2': ['10.0.0.2:1234']}
    mapper.add_instance('10.0.0.2:4321:', True)
    assert sorted(mapper.instances.keys()) == ['10.0.0.2:1234', '10.0.0.2:4321', 'dummy_1', 'dummy_2']
    assert mapper.nodes == {'10.0.0.1': ['dummy_1', 'dummy_2'], '10.0.0.2': ['10.0.0.2:1234', '10.0.0.2:4321']}


def test_mapper_configure(mocker, mapper):
    """ Test the storage of the expected Supvisors instances. """
    mocked_find = mocker.patch.object(mapper, 'find_local_identifier')
    # configure mapper with elements
    items = ['127.0.0.1', '<supervisor_05>10.0.0.5:7777:', '10.0.0.4:15000:8888', '10.0.0.5:9999:']
    core_items = ['127.0.0.1', 'supervisor_05', '10.0.0.4:15000', 'supervisor_06', '10.0.0.4']
    mapper.configure(items, 'test', core_items)
    assert list(mapper.instances.keys()) == ['127.0.0.1', 'supervisor_05', '10.0.0.4:15000', '10.0.0.5:9999']
    assert mapper.core_identifiers == ['127.0.0.1', 'supervisor_05', '10.0.0.4:15000']
    assert mapper.nodes == {'127.0.0.1': ['127.0.0.1'], '10.0.0.5': ['supervisor_05', '10.0.0.5:9999'],
                            '10.0.0.4': ['10.0.0.4:15000']}
    assert mapper.initial_identifiers == ['127.0.0.1', 'supervisor_05', '10.0.0.4:15000', '10.0.0.5:9999']
    assert mocked_find.call_args_list == [call('test')]
    mocked_find.reset_mock()
    # configure mapper with one invalid element
    items = ['127.0.0.1', '<dummy_id>', '<supervisor_05>10.0.0.5', '10.0.0.4:15000']
    with pytest.raises(ValueError):
        mapper.configure(items, '', core_items)
    assert not mocked_find.called


def test_find_local_identifier_fqdn(mapper):
    """ Test the SupvisorsMapper.find_local_identifier method when the item host name matches the . """
    fqdn = getfqdn()
    items = [fqdn, '<supervisor>10.0.0.5:7777:']
    for item in items:
        supvisors_id = SupvisorsInstanceId(item, mapper.supvisors)
        mapper._instances[supvisors_id.identifier] = supvisors_id
        assert supvisors_id.stereotypes == []
    # 1. force host name and aliases
    sup_id = mapper._instances[fqdn]
    sup_id.host_name = fqdn
    sup_id.aliases = ['dummy']
    # find self
    mapper.find_local_identifier({'test'})
    assert mapper.local_identifier == fqdn
    for identifier, supvisors_id in mapper.instances.items():
        assert identifier != fqdn or supvisors_id.stereotypes == ['test']
    # 2. move fqdn
    sup_id.host_name = 'dummy'
    sup_id.aliases = [fqdn]
    sup_id.stereotypes = []
    # find self
    mapper.find_local_identifier({'test_2'})
    assert mapper.local_identifier == fqdn
    for identifier, supvisors_id in mapper.instances.items():
        assert identifier != fqdn or supvisors_id.stereotypes == ['test_2']


def test_find_local_identifier_host_name(mapper):
    """ Test the SupvisorsMapper.find_local_identifier method when one instance matches the host name and the HTTP
    server port. """
    host_name, fqdn = gethostname(), getfqdn()
    items = ['127.0.0.1', f'{host_name}:65000:7777']
    for item in items:
        supvisors_id = SupvisorsInstanceId(item, mapper.supvisors)
        mapper._instances[supvisors_id.identifier] = supvisors_id
        assert supvisors_id.stereotypes == []
    # 1. force host name and aliases
    sup_id = mapper._instances[f'{host_name}:65000']
    sup_id.host_name = fqdn
    sup_id.aliases = ['dummy']
    # find self
    mapper.find_local_identifier({'test'})
    assert mapper.local_identifier == f'{host_name}:65000'
    for identifier, supvisors_id in mapper.instances.items():
        assert identifier != fqdn or supvisors_id.stereotype == ['test']
    # 2. move fqdn
    sup_id.host_name = 'dummy'
    sup_id.aliases = [fqdn]
    # find self
    mapper.find_local_identifier({'test_2'})
    assert mapper.local_identifier == f'{host_name}:65000'
    for identifier, supvisors_id in mapper.instances.items():
        assert identifier != fqdn or supvisors_id.stereotype == ['test_2']


def test_find_local_identifier_ip_address(mapper):
    """ Test the SupvisorsMapper.find_local_identifier method when one instance matches the IP address of the host
    and the HTTP server port. """
    host_name, fqdn = gethostname(), getfqdn()
    _, _, ip_addresses = get_addresses(fqdn, mapper.logger)
    items = ['127.0.0.1', f'<host>{ip_addresses[0]}:65000:7777']
    for item in items:
        supvisors_id = SupvisorsInstanceId(item, mapper.supvisors)
        mapper._instances[supvisors_id.identifier] = supvisors_id
        assert supvisors_id.stereotypes == []
    # 1. force host name and aliases
    sup_id = mapper._instances[f'host']
    sup_id.host_name = fqdn
    sup_id.aliases = ['dummy']
    # find self
    mapper.find_local_identifier({'test'})
    assert mapper.local_identifier == 'host'
    for identifier, supvisors_id in mapper.instances.items():
        assert identifier != fqdn or supvisors_id.stereotypes == ['test']
    # 2. move fqdn
    sup_id.host_name = 'dummy'
    sup_id.aliases = [fqdn]
    # find self
    mapper.find_local_identifier({'test_2'})
    assert mapper.local_identifier == 'host'
    for identifier, supvisors_id in mapper.instances.items():
        assert identifier != fqdn or supvisors_id.stereotypes == ['test_2']


def test_find_local_identifier_inconsistent(mapper):
    """ Test the SupvisorsMapper.find_local_identifier method when the identifier corresponds to thr local Supvisors
    instance but the host_name and http_port do not match. """
    host_name = gethostname()
    supvisors_id = SupvisorsInstanceId(f'<{host_name}>10.0.0.5:7777:', mapper.supvisors)
    mapper._instances[supvisors_id.identifier] = supvisors_id
    assert supvisors_id.stereotypes == []
    # find self
    print(mapper.supvisors.supervisor_data.identifier)
    with pytest.raises(ValueError):
        mapper.find_local_identifier({'test'})
    assert supvisors_id.stereotypes == []


def test_find_local_identifier_multiple(mapper):
    """ Test the SupvisorsMapper.find_local_identifier method when more than one instance matches the host name
    or IP address of the host. """
    host_name = gethostname()
    fqdn = getfqdn()
    items = ['10.0.0.1', f'{host_name}:65000:7777']
    for item in items:
        supvisors_id = SupvisorsInstanceId(item, mapper.supvisors)
        mapper._instances[supvisors_id.identifier] = supvisors_id
        assert supvisors_id.stereotypes == []
        # update default processing of host
        supvisors_id.host_name = fqdn
    # find self
    with pytest.raises(ValueError):
        mapper.find_local_identifier({'test'})
    for supvisors_id in mapper._instances.values():
        assert supvisors_id.stereotypes == []


def test_find_local_identifier_none(mapper):
    """ Test the SupvisorsMapper.find_local_identifier method when no instance matches the host name
    or IP address of the host. """
    host_name = gethostname()
    items = ['10.0.0.2', '<dummy>cliche:60000:7777', f'{host_name}:60000:7777']
    for item in items:
        supvisors_id = SupvisorsInstanceId(item, mapper.supvisors)
        mapper._instances[supvisors_id.identifier] = supvisors_id
    with pytest.raises(ValueError):
        mapper.find_local_identifier({'test'})
    for supvisors_id in mapper._instances.values():
        assert supvisors_id.stereotypes == []


def test_assign_stereotypes(mapper):
    """ Test the SupvisorsMapper.assign_stereotypes method. """
    # add context
    items = ['10.0.0.1', '10.0.0.3', '10.0.0.4', '10.0.0.2']
    for item in items:
        supvisors_id = SupvisorsInstanceId(item, mapper.supvisors)
        mapper._instances[supvisors_id.identifier] = supvisors_id
        assert supvisors_id.stereotypes == []
    assert mapper.stereotypes == {}
    # test with empty stereotype
    mapper.assign_stereotypes('10.0.0.1', set())
    assert mapper.stereotypes == {}
    assert all(x.stereotypes == [] for x in mapper.instances.values())
    # assign stereotype to a Supvisors instance
    mapper.assign_stereotypes('10.0.0.3', {'test'})
    assert mapper.stereotypes == {'test': ['10.0.0.3']}
    assert mapper.instances['10.0.0.1'].stereotypes == []
    assert mapper.instances['10.0.0.2'].stereotypes == []
    assert mapper.instances['10.0.0.3'].stereotypes == ['test']
    assert mapper.instances['10.0.0.4'].stereotypes == []
    # assign same stereotype to another Supvisors instance that is before in the instances order
    mapper.assign_stereotypes('10.0.0.1', {'test'})
    assert mapper.stereotypes == {'test': ['10.0.0.1', '10.0.0.3']}
    assert mapper.instances['10.0.0.1'].stereotypes == ['test']
    assert mapper.instances['10.0.0.2'].stereotypes == []
    assert mapper.instances['10.0.0.3'].stereotypes == ['test']
    assert mapper.instances['10.0.0.4'].stereotypes == []
    # assign same stereotype to another Supvisors instance that is after in the instances order
    mapper.assign_stereotypes('10.0.0.2', {'test', 'other test'})
    assert mapper.stereotypes == {'test': ['10.0.0.1', '10.0.0.3', '10.0.0.2'], 'other test': ['10.0.0.2']}
    assert mapper.instances['10.0.0.1'].stereotypes == ['test']
    assert sorted(mapper.instances['10.0.0.2'].stereotypes) == sorted(['test', 'other test'])
    assert mapper.instances['10.0.0.3'].stereotypes == ['test']
    assert mapper.instances['10.0.0.4'].stereotypes == []
    # assign another stereotype to another Supvisors instance
    mapper.assign_stereotypes('10.0.0.4', {'other test'})
    assert mapper.stereotypes == {'test': ['10.0.0.1', '10.0.0.3', '10.0.0.2'], 'other test': ['10.0.0.4', '10.0.0.2']}
    assert mapper.instances['10.0.0.1'].stereotypes == ['test']
    assert sorted(mapper.instances['10.0.0.2'].stereotypes) == sorted(['test', 'other test'])
    assert mapper.instances['10.0.0.3'].stereotypes == ['test']
    assert mapper.instances['10.0.0.4'].stereotypes == ['other test']


def test_filter(mapper):
    """ Test the SupvisorsMapper.filter method. """
    # add context
    hostname = gethostname()
    items = ['127.0.0.1', '<host>10.0.0.1:2222:', f'{hostname}:60000:7777', '10.0.0.2']
    for item in items:
        supvisors_id = SupvisorsInstanceId(item, mapper.supvisors)
        mapper._instances[supvisors_id.identifier] = supvisors_id
    # force host name to FQDN
    mapper._instances[f'{hostname}:60000'].host_name = getfqdn()
    # test with a bunch of identifiers
    identifier_list = ['host', f'{hostname}:60000', hostname, 'host', 'supervisor', '10.0.0.1']
    assert mapper.filter(identifier_list) == ['host', f'{hostname}:60000']
    # set stereotype to one of them
    mapper.assign_stereotypes('10.0.0.2', {'supervisor'})
    assert mapper.filter(identifier_list) == ['host', f'{hostname}:60000', '10.0.0.2']
