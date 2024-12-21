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


def test_nic_information_not_loopback():
    """ Test the NicInformation class with an interface different from loopback. """
    nic_info = NicInformation('eth0', '192.168.1.1', '255.255.255.0')
    assert nic_info.nic_name == 'eth0'
    assert nic_info.ipv4_address == '192.168.1.1'
    assert nic_info.netmask == '255.255.255.0'
    assert nic_info.network_address == '192.168.1.0'
    assert not nic_info.is_loopback
    assert nic_info.serial() == {'nic_name': 'eth0',
                                 'ipv4_address': '192.168.1.1',
                                 'netmask': '255.255.255.0'}


def test_nic_information_loopback():
    """ Test the NicInformation class with a loopback interface. """
    nic_info = NicInformation('lo', '127.5.10.10', '255.0.0.0')
    assert nic_info.nic_name == 'lo'
    assert nic_info.ipv4_address == '127.5.10.10'
    assert nic_info.netmask == '255.0.0.0'
    assert nic_info.network_address == '127.0.0.0'
    assert nic_info.is_loopback
    assert nic_info.serial() == {'nic_name': 'lo',
                                 'ipv4_address': '127.5.10.10',
                                 'netmask': '255.0.0.0'}


def test_get_interface_info():
    """ Test the get_interface_info method. """
    # complex to test as it depends on the network configuration of the targeted operating system
    # check that the results look like IPv4 addresses
    nic_name = socket.if_nameindex()[0][1]
    ip_address, netmask = get_interface_info(nic_name)
    assert re.match(r'^\d{1,3}(.\d{1,3}){3}$', ip_address)
    assert re.match(r'^\d{1,3}(.\d{1,3}){3}$', netmask)
    # test IOError exception
    assert get_interface_info('jlc') is None


def test_get_network_info():
    """ Test the get_interface_info method. """
    # complex to test as it depends on the network configuration of the targeted operating system
    # check that the results look like IPv4 addresses
    if_names = [x[1] for x in socket.if_nameindex()]
    result = list(get_network_info())
    assert len(result) > 1
    for nic_info in result:
        assert not nic_info.is_loopback
        assert nic_info.nic_name in if_names
        assert re.match(r'^\d{1,3}(.\d{1,3}){3}$', nic_info.ipv4_address)
        assert re.match(r'^\d{1,3}(.\d{1,3}){3}$', nic_info.netmask)


def test_network_address(mocker, logger_instance):
    """ Test the NetworkAddress class. """
    mocked_sock = mocker.patch('socket.gethostbyaddr', side_effect=lambda x: (x, [x], [x]))
    # test NetworkAddress creation with no additional parameters
    addr = NetworkAddress(logger_instance)
    assert addr.host_name == ''
    assert addr.aliases == []
    assert addr.ipv4_addresses == []
    assert addr.nic_info is None
    assert addr.host_matches('')
    assert not addr.host_matches('192.168.1.1')
    assert not addr.host_matches('10.0.0.1')
    assert not addr.host_matches('eth0')
    assert not addr.host_matches('255.255.255.0')
    assert addr.get_network_ip('192.168.1.0') == ''
    assert addr.serial() == {'host_name': '',
                             'aliases': [],
                             'ipv4_addresses': [],
                             'nic_info': None}
    # test NetworkAddress creation with NicInformation
    nic_info = NicInformation('eth0', '192.168.1.1', '255.255.255.0')
    addr = NetworkAddress(logger_instance, nic_info=nic_info)
    assert addr.host_name == '192.168.1.1'
    assert addr.aliases == ['192.168.1.1']
    assert addr.ipv4_addresses == ['192.168.1.1']
    assert addr.nic_info is nic_info
    assert not addr.host_matches('')
    assert addr.host_matches('192.168.1.1')
    assert not addr.host_matches('10.0.0.1')
    assert not addr.host_matches('eth0')
    assert not addr.host_matches('255.255.255.0')
    assert addr.get_network_ip('192.168.1.0') == '192.168.1.1'
    assert addr.get_network_ip('192.168.11.0') == ''
    assert addr.serial() == {'host_name': '192.168.1.1',
                             'aliases': ['192.168.1.1'],
                             'ipv4_addresses': ['192.168.1.1'],
                             'nic_info': {'nic_name': 'eth0',
                                          'ipv4_address': '192.168.1.1',
                                          'netmask': '255.255.255.0'}}
    # test NetworkAddress creation with host id
    addr = NetworkAddress(logger_instance, host_id='10.0.0.1')
    assert addr.host_name == '10.0.0.1'
    assert addr.aliases == ['10.0.0.1']
    assert addr.ipv4_addresses == ['10.0.0.1']
    assert addr.nic_info is None
    assert not addr.host_matches('')
    assert not addr.host_matches('192.168.1.1')
    assert addr.host_matches('10.0.0.1')
    assert not addr.host_matches('eth0')
    assert not addr.host_matches('255.255.255.0')
    assert addr.get_network_ip('192.168.1.0') == ''
    assert addr.serial() == {'host_name': '10.0.0.1',
                             'aliases': ['10.0.0.1'],
                             'ipv4_addresses': ['10.0.0.1'],
                             'nic_info': None}
    # test NetworkAddress creation with both NicInformation and host id
    # NicInformation takes precedence
    addr = NetworkAddress(logger_instance, nic_info=nic_info, host_id='10.0.0.1')
    assert addr.host_name == '192.168.1.1'
    assert addr.aliases == ['192.168.1.1']
    assert addr.ipv4_addresses == ['192.168.1.1']
    assert addr.nic_info is nic_info
    assert not addr.host_matches('')
    assert addr.host_matches('192.168.1.1')
    assert not addr.host_matches('10.0.0.1')
    assert not addr.host_matches('eth0')
    assert not addr.host_matches('255.255.255.0')
    assert addr.get_network_ip('192.168.1.0') == '192.168.1.1'
    assert addr.get_network_ip('192.168.11.0') == ''
    assert addr.serial() == {'host_name': '192.168.1.1',
                             'aliases': ['192.168.1.1'],
                             'ipv4_addresses': ['192.168.1.1'],
                             'nic_info': {'nic_name': 'eth0',
                                          'ipv4_address': '192.168.1.1',
                                          'netmask': '255.255.255.0'}}
    # test NetworkAddress creation from payload
    addr = NetworkAddress(logger_instance, host_id='10.0.0.1')
    addr.from_payload(NetworkAddress(logger_instance, nic_info=nic_info).serial())
    assert addr.host_name == '192.168.1.1'
    assert addr.aliases == ['192.168.1.1']
    assert addr.ipv4_addresses == ['192.168.1.1']
    assert addr.nic_info is not nic_info
    assert addr.nic_info.serial() == nic_info.serial()
    assert not addr.host_matches('')
    assert addr.host_matches('192.168.1.1')
    assert not addr.host_matches('10.0.0.1')
    assert not addr.host_matches('eth0')
    assert not addr.host_matches('255.255.255.0')
    assert addr.get_network_ip('192.168.1.0') == '192.168.1.1'
    assert addr.get_network_ip('192.168.11.0') == ''
    assert addr.serial() == {'host_name': '192.168.1.1',
                             'aliases': ['192.168.1.1'],
                             'ipv4_addresses': ['192.168.1.1'],
                             'nic_info': {'nic_name': 'eth0',
                                          'ipv4_address': '192.168.1.1',
                                          'netmask': '255.255.255.0'}}
    # test NetworkAddress creation with gaierror
    mocked_sock.side_effect = socket.gaierror
    addr = NetworkAddress(logger_instance, nic_info=nic_info)
    assert addr.host_name == ''
    assert addr.aliases == []
    assert addr.ipv4_addresses == []
    assert addr.nic_info is nic_info
    assert addr.host_matches('')
    assert not addr.host_matches('192.168.1.1')
    assert not addr.host_matches('10.0.0.1')
    assert not addr.host_matches('eth0')
    assert not addr.host_matches('255.255.255.0')
    assert addr.get_network_ip('192.168.1.0') == '192.168.1.1'
    assert addr.get_network_ip('192.168.11.0') == ''
    assert addr.serial() == {'host_name': '',
                             'aliases': [],
                             'ipv4_addresses': [],
                             'nic_info': {'nic_name': 'eth0',
                                          'ipv4_address': '192.168.1.1',
                                          'netmask': '255.255.255.0'}}


def test_local_network(logger_instance):
    """ Test the LocalNetwork class. """
    network = LocalNetwork(logger_instance)
    assert network.logger is logger_instance
    assert network.machine_id == '01:23:45:67:89:ab'
    assert network.fqdn == 'supv01.bzh'
    assert sorted(network.addresses.keys()) == [nic_name for _, nic_name in socket.if_nameindex()
                                                if nic_name != 'lo']
    # test host_matches
    assert network.host_matches('10.0.0.1')
    assert not network.host_matches('10.0.0.2')
    assert not network.host_matches('supv03')
    # test get_network_address
    assert network.get_network_address('10.0.0.1') == '10.0.0.0'
    assert network.get_network_address('10.0.0.2') == ''
    # test get_network_address
    assert network.get_network_ip('10.0.0.0') == '10.0.0.1'
    assert network.get_network_ip('10.0.1.0') == ''
    # test serial
    assert network.serial() == {'fqdn': 'supv01.bzh',
                                'machine_id': '01:23:45:67:89:ab',
                                'addresses': {'eth0': {'host_name': 'supv01.bzh',
                                                       'aliases': ['cliche01', 'supv01'],
                                                       'ipv4_addresses': ['10.0.0.1'],
                                                       'nic_info': {'ipv4_address': '10.0.0.1',
                                                                    'netmask': '255.255.255.0',
                                                                    'nic_name': 'eth0'}}}}
    # test LocalNetwork creation from payload
    other = LocalNetwork(logger_instance)
    payload = {'fqdn': 'supv01.bzh',
               'machine_id': '01:23:45:67:89:ab',
               'addresses': {'eth0': {'host_name': 'supv02',
                                      'aliases': ['rocky52'],
                                      'ipv4_addresses': ['10.0.0.2'],
                                      'nic_info': {'ipv4_address': '10.0.0.2',
                                                   'netmask': '255.255.255.0',
                                                   'nic_name': 'eth0'}}}}
    other.from_payload(payload)
    assert other.serial() == payload
    # test LocalNetwork creation from other instance (gethostbyaddr is still patched)
    network.from_network(other)
    assert network.serial() == {'fqdn': 'supv01.bzh',
                                'machine_id': '01:23:45:67:89:ab',
                                'addresses': {'eth0': {'host_name': 'supv02.bzh',
                                                       'aliases': ['cliche02', 'supv02'],
                                                       'ipv4_addresses': ['10.0.0.2'],
                                                       'nic_info': {'ipv4_address': '10.0.0.2',
                                                                    'netmask': '255.255.255.0',
                                                                    'nic_name': 'eth0'}}}}


def test_sup_id_create_no_match(supvisors_instance):
    """ Test the values set at SupvisorsInstanceId construction. """
    no_matches = ['', 'ident>', 'cliche81:12000:', '10.0.0.1:145000']
    # test with no match but default options loaded
    for item in no_matches:
        sup_id = SupvisorsInstanceId(item, supvisors_instance)
        assert sup_id.identifier is None
        assert sup_id.nick_identifier is None
        assert sup_id.host_id is None
        assert sup_id.http_port == 25000  # defaulted to supervisor server port
        assert sup_id.event_port == 25200  # defaulted to options.event_port
        assert sup_id.simple_address is None
        assert sup_id.remote_view is None
        assert sup_id.local_view is None
        assert sup_id.ip_address is None
        assert sup_id.stereotypes == []
        with pytest.raises(TypeError):
            str(sup_id)
        assert sup_id.serial() == {'identifier': None, 'nick_identifier': None,
                                   'host_id': None, 'http_port': 25000,
                                   'stereotypes': []}
        assert sup_id.source == (None, None, (None, 25000))
        assert sup_id.is_valid(('10.0.0.1', 25000))
        assert sup_id.is_valid(('cliche81', 25000))
        assert not sup_id.is_valid(('10.0.0.1', 7777))
        assert sup_id.get_network_ip(None) is None
        assert sup_id.get_network_ip('10.0.0.0') is None
        assert sup_id.get_network_ip('10.0.1.0') is None


def test_sup_id_create_simple_no_default(supvisors_instance):
    """ Test the values set at SupvisorsInstanceId construction. """
    supvisors_instance.options.event_port = 0
    # test with no match and no default option loaded
    sup_id = SupvisorsInstanceId('', supvisors_instance)
    assert sup_id.identifier is None
    assert sup_id.nick_identifier is None
    assert sup_id.host_id is None
    assert sup_id.http_port == 25000  # defaulted to supervisor server port
    assert sup_id.event_port == 25001  # defaulted to http_port + 1
    assert sup_id.simple_address is None
    assert sup_id.remote_view is None
    assert sup_id.local_view is None
    assert sup_id.ip_address is None
    assert sup_id.stereotypes == []
    with pytest.raises(TypeError):
        str(sup_id)
    assert sup_id.serial() == {'identifier': None, 'nick_identifier': None,
                               'host_id': None, 'http_port': 25000,
                               'stereotypes': []}
    assert sup_id.source == (None, None, (None, 25000))
    assert sup_id.is_valid(('10.0.0.1', 25000))
    assert not sup_id.is_valid(('10.0.0.1', 7777))
    assert sup_id.is_valid(('cliche81', 25000))
    assert sup_id.get_network_ip(None) is None
    assert sup_id.get_network_ip('10.0.0.0') is None
    assert sup_id.get_network_ip('10.0.1.0') is None


def test_sup_id_create_host(supvisors_instance):
    """ Test the values set at SupvisorsInstanceId construction. """
    # test with simple host name match
    sup_id = SupvisorsInstanceId('10.0.0.1', supvisors_instance)
    assert sup_id.identifier == '10.0.0.1:25000'
    assert sup_id.nick_identifier == '10.0.0.1'
    assert sup_id.host_id == '10.0.0.1'
    assert sup_id.http_port == 25000  # defaulted to supervisor server port
    assert sup_id.event_port == 25200  # defaulted to options.event_port
    assert sup_id.simple_address.serial() == {'host_name': 'supv01.bzh',
                                              'aliases': ['cliche01', 'supv01'],
                                              'ipv4_addresses': ['10.0.0.1'],
                                              'nic_info': None}
    assert sup_id.remote_view is None
    assert sup_id.local_view is None
    assert sup_id.ip_address == '10.0.0.1'
    assert sup_id.stereotypes == []
    assert str(sup_id) == '<10.0.0.1>10.0.0.1:25000'
    assert sup_id.serial() == {'host_id': '10.0.0.1', 'http_port': 25000,
                               'identifier': '10.0.0.1:25000',
                               'nick_identifier': '10.0.0.1', 'stereotypes': []}
    assert sup_id.source == ('10.0.0.1:25000', '10.0.0.1', ('10.0.0.1', 25000))
    assert sup_id.is_valid(('10.0.0.1', 25000))
    assert not sup_id.is_valid(('10.0.0.1', 7777))
    assert not sup_id.is_valid(('cliche81', 7777))
    assert sup_id.get_network_ip(None) == '10.0.0.1'
    assert sup_id.get_network_ip('10.0.0.0') == '10.0.0.1'
    assert sup_id.get_network_ip('10.0.1.0') == '10.0.0.1'


def test_sup_id_create_host_port(supvisors_instance):
    """ Test the values set at SupvisorsInstanceId construction. """
    # test with host+ports match
    sup_id = SupvisorsInstanceId('10.0.0.1:7777', supvisors_instance)
    assert sup_id.identifier == '10.0.0.1:7777'
    assert sup_id.nick_identifier == '10.0.0.1:7777'
    assert sup_id.host_id == '10.0.0.1'
    assert sup_id.http_port == 7777
    assert sup_id.event_port == 25200  # defaulted to options.event_port
    assert sup_id.simple_address.serial() == {'host_name': 'supv01.bzh',
                                              'aliases': ['cliche01', 'supv01'],
                                              'ipv4_addresses': ['10.0.0.1'],
                                              'nic_info': None}
    assert sup_id.remote_view is None
    assert sup_id.local_view is None
    assert sup_id.ip_address == '10.0.0.1'
    assert sup_id.stereotypes == []
    assert str(sup_id) == '10.0.0.1:7777'
    assert sup_id.serial() == {'host_id': '10.0.0.1', 'http_port': 7777,
                               'identifier': '10.0.0.1:7777',
                               'nick_identifier': '10.0.0.1:7777', 'stereotypes': []}
    assert sup_id.source == ('10.0.0.1:7777', '10.0.0.1:7777', ('10.0.0.1', 7777))
    assert sup_id.is_valid(('10.0.0.1', 7777))
    assert not sup_id.is_valid(('10.0.0.1', 25000))
    assert sup_id.is_valid(('cliche81', 7777))  # no local_view
    assert sup_id.get_network_ip(None) == '10.0.0.1'
    assert sup_id.get_network_ip('10.0.0.0') == '10.0.0.1'
    assert sup_id.get_network_ip('10.0.1.0') == '10.0.0.1'
    # test with host+ports match (internal port defined)
    supvisors_instance.options.event_port = 0
    sup_id = SupvisorsInstanceId('10.0.0.1:7777', supvisors_instance)
    assert sup_id.identifier == '10.0.0.1:7777'
    assert sup_id.nick_identifier == '10.0.0.1:7777'
    assert sup_id.host_id == '10.0.0.1'
    assert sup_id.http_port == 7777
    assert sup_id.event_port == 7778  # defaulted to http_port + 1
    assert sup_id.simple_address.serial() == {'host_name': 'supv01.bzh',
                                              'aliases': ['cliche01', 'supv01'],
                                              'ipv4_addresses': ['10.0.0.1'],
                                              'nic_info': None}
    assert sup_id.remote_view is None
    assert sup_id.local_view is None
    assert sup_id.ip_address == '10.0.0.1'
    assert sup_id.stereotypes == []
    assert str(sup_id) == '10.0.0.1:7777'
    assert sup_id.serial() == {'host_id': '10.0.0.1', 'http_port': 7777,
                               'identifier': '10.0.0.1:7777',
                               'nick_identifier': '10.0.0.1:7777', 'stereotypes': []}
    assert sup_id.source == ('10.0.0.1:7777', '10.0.0.1:7777', ('10.0.0.1', 7777))
    assert sup_id.is_valid(('10.0.0.1', 7777))
    assert not sup_id.is_valid(('10.0.0.1', 25000))
    assert sup_id.is_valid(('cliche81', 7777))  # no local_view
    assert sup_id.get_network_ip(None) == '10.0.0.1'
    assert sup_id.get_network_ip('10.0.0.0') == '10.0.0.1'
    assert sup_id.get_network_ip('10.0.1.0') == '10.0.0.1'


def test_sup_id_create_identifier(supvisors_instance):
    """ Test the values set at SupvisorsInstanceId construction. """
    # test with identifier set and only host name
    sup_id = SupvisorsInstanceId('<supvisors>10.0.0.0', supvisors_instance)
    assert sup_id.identifier == '10.0.0.0:25000'
    assert sup_id.nick_identifier == 'supvisors'
    assert sup_id.host_id == '10.0.0.0'
    assert sup_id.http_port == 25000
    assert sup_id.event_port == 25200  # defaulted to options.event_port
    assert sup_id.simple_address.serial() == {'host_name': 'supv00.bzh',
                                              'aliases': ['cliche00', 'supv00'],
                                              'ipv4_addresses': ['10.0.0.0'],
                                              'nic_info': None}
    assert sup_id.remote_view is None
    assert sup_id.local_view is None
    assert sup_id.ip_address == '10.0.0.0'
    assert sup_id.stereotypes == []
    assert str(sup_id) == '<supvisors>10.0.0.0:25000'
    assert sup_id.serial() == {'host_id': '10.0.0.0', 'http_port': 25000,
                               'identifier': '10.0.0.0:25000',
                               'nick_identifier': 'supvisors', 'stereotypes': []}
    assert sup_id.source == ('10.0.0.0:25000', 'supvisors', ('10.0.0.0', 25000))
    assert sup_id.is_valid(('10.0.0.0', 25000))
    assert sup_id.is_valid(('10.0.0.1', 25000))  # no local_view
    assert not sup_id.is_valid(('cliche81', 7777))
    assert sup_id.get_network_ip(None) == '10.0.0.0'
    assert sup_id.get_network_ip('10.0.0.0') == '10.0.0.0'
    assert sup_id.get_network_ip('10.0.1.0') == '10.0.0.0'
    # test with identifier, host name and http port set
    sup_id = SupvisorsInstanceId('<supvisors>10.0.0.0:8888', supvisors_instance)
    assert sup_id.identifier == '10.0.0.0:8888'
    assert sup_id.nick_identifier == 'supvisors'
    assert sup_id.host_id == '10.0.0.0'
    assert sup_id.http_port == 8888
    assert sup_id.event_port == 25200  # defaulted to options.event_port
    assert sup_id.simple_address.serial() == {'host_name': 'supv00.bzh',
                                              'aliases': ['cliche00', 'supv00'],
                                              'ipv4_addresses': ['10.0.0.0'],
                                              'nic_info': None}
    assert sup_id.remote_view is None
    assert sup_id.local_view is None
    assert sup_id.ip_address == '10.0.0.0'
    assert sup_id.stereotypes == []
    assert str(sup_id) == '<supvisors>10.0.0.0:8888'
    assert sup_id.serial() == {'host_id': '10.0.0.0', 'http_port': 8888,
                               'identifier': '10.0.0.0:8888',
                               'nick_identifier': 'supvisors', 'stereotypes': []}
    assert sup_id.source == ('10.0.0.0:8888', 'supvisors', ('10.0.0.0', 8888))
    assert sup_id.is_valid(('10.0.0.0', 8888))
    assert sup_id.is_valid(('10.0.0.1', 8888))  # no local_view
    assert not sup_id.is_valid(('cliche81', 7777))
    assert sup_id.get_network_ip(None) == '10.0.0.0'
    assert sup_id.get_network_ip('10.0.0.0') == '10.0.0.0'
    assert sup_id.get_network_ip('10.0.1.0') == '10.0.0.0'


@pytest.fixture
def mapper(mocker, supvisors_instance):
    """ Return the instance to test. """
    mocker.patch('uuid.getnode', return_value=1250999896491)
    return SupvisorsMapper(supvisors_instance)


def test_mapper_create(supvisors_instance, mapper):
    """ Test the values set at construction. """
    assert mapper.supvisors is supvisors_instance
    assert mapper.local_network.serial() == {'fqdn': 'supv01.bzh',
                                             'machine_id': '01:23:45:67:89:ab',
                                             'addresses': {'eth0': {'host_name': 'supv01.bzh',
                                                                    'aliases': ['cliche01', 'supv01'],
                                                                    'ipv4_addresses': ['10.0.0.1'],
                                                                    'nic_info': {'ipv4_address': '10.0.0.1',
                                                                                 'netmask': '255.255.255.0',
                                                                                 'nic_name': 'eth0'}}}}
    assert mapper.logger is supvisors_instance.logger
    assert mapper.instances == {}
    assert mapper._nick_identifiers == {}
    assert mapper.nodes == {}
    assert mapper.core_identifiers == []
    assert mapper.local_identifier is None
    assert mapper.initial_identifiers == []
    with pytest.raises(KeyError):
        mapper.local_instance
    with pytest.raises(KeyError):
        mapper.local_nick_identifier


def test_get_nick_identifier(supvisors_instance):
    """ Test the SupvisorsMapper.get_nick_identifier method. """
    smapper = supvisors_instance.mapper
    assert smapper.get_nick_identifier(smapper.local_identifier) == smapper.local_nick_identifier
    assert smapper.get_nick_identifier('10.0.0.1:25000') == '10.0.0.1'
    assert smapper.get_nick_identifier('10.0.0.2:25000') == '10.0.0.2'
    assert smapper.get_nick_identifier('10.0.0.3:25000') == '10.0.0.3'
    assert smapper.get_nick_identifier('10.0.0.4:25000') == '10.0.0.4'
    assert smapper.get_nick_identifier('10.0.0.5:25000') == '10.0.0.5'
    assert smapper.get_nick_identifier('10.0.0.6:25000') == '10.0.0.6'


def test_add_instance(mapper):
    """ Test the SupvisorsMapper.add_instance method. """
    # test error (no IP address)
    with pytest.raises(ValueError):
        mapper.add_instance('<dummy>:1234:')
    assert mapper.instances == {}
    assert mapper._nick_identifiers == {}
    assert mapper.nodes == {}
    with pytest.raises(ValueError):
        mapper.add_instance('<dummy>:1234:4321')
    assert mapper.instances == {}
    assert mapper._nick_identifiers == {}
    assert mapper.nodes == {}
    # test correct format
    mapper.add_instance('<dummy_2>10.0.0.1:1234')
    assert sorted(mapper.instances.keys()) == ['10.0.0.1:1234']
    assert mapper._nick_identifiers == {'dummy_2': '10.0.0.1:1234'}
    mapper.add_instance('10.0.0.1:4321')
    assert sorted(mapper.instances.keys()) == ['10.0.0.1:1234', '10.0.0.1:4321']
    assert mapper._nick_identifiers == {'dummy_2': '10.0.0.1:1234', '10.0.0.1:4321': '10.0.0.1:4321'}
    mapper.add_instance('10.0.0.2')
    assert sorted(mapper.instances.keys()) == ['10.0.0.1:1234', '10.0.0.1:4321', '10.0.0.2:25000']
    assert mapper._nick_identifiers == {'dummy_2': '10.0.0.1:1234', '10.0.0.1:4321': '10.0.0.1:4321',
                                        '10.0.0.2': '10.0.0.2:25000'}
    mapper.add_instance('<dummy_1>10.0.0.3')
    assert sorted(mapper.instances.keys()) == ['10.0.0.1:1234', '10.0.0.1:4321', '10.0.0.2:25000', '10.0.0.3:25000']
    assert mapper._nick_identifiers == {'dummy_2': '10.0.0.1:1234', '10.0.0.1:4321': '10.0.0.1:4321',
                                        '10.0.0.2': '10.0.0.2:25000', 'dummy_1': '10.0.0.3:25000'}


def test_mapper_configure(mocker, mapper):
    """ Test the storage of the expected Supvisors instances. """
    mocked_find = mocker.patch.object(mapper, '_find_local_identifier')
    # configure mapper with elements
    items = ['127.0.0.1', '<supervisor_05>10.0.0.5:7777', '10.0.0.4:15000', '10.0.0.5:9999']
    core_items = ['127.0.0.1', 'supervisor_05', '10.0.0.4:15000', 'supervisor_06', '10.0.0.4']
    mapper.configure(items, {'test'}, core_items)
    assert list(mapper.instances.keys()) == ['127.0.0.1:25000', '10.0.0.5:7777', '10.0.0.4:15000', '10.0.0.5:9999']
    assert mapper._nick_identifiers == {'10.0.0.4:15000': '10.0.0.4:15000',
                                        '10.0.0.5:9999': '10.0.0.5:9999',
                                        '127.0.0.1': '127.0.0.1:25000',
                                        'supervisor_05': '10.0.0.5:7777'}
    assert mapper._core_identifiers == core_items
    assert mapper.core_identifiers == ['127.0.0.1:25000', '10.0.0.5:7777', '10.0.0.4:15000']
    assert mapper.initial_identifiers == ['127.0.0.1:25000', '10.0.0.5:7777', '10.0.0.4:15000', '10.0.0.5:9999']
    assert mocked_find.call_args_list == [call({'test'})]
    mocked_find.reset_mock()
    # configure mapper with one invalid element
    items = ['127.0.0.1', '<dummy_id>', '<supervisor_05>10.0.0.5', '10.0.0.4:15000']
    with pytest.raises(ValueError):
        mapper.configure(items, {''}, core_items)
    assert not mocked_find.called


def test_find_local_identifier(supvisors_instance):
    """ Test the SupvisorsMapper.find_local_identifier method in the default test instance. """
    smapper = supvisors_instance.mapper
    smapper._find_local_identifier({'test'})
    assert smapper.local_identifier == '10.0.0.1:25000'
    for identifier, supvisors_id in smapper.instances.items():
        assert identifier != 'supv01.bzh' or supvisors_id.stereotypes == ['test']


def test_find_local_identifier_fqdn(supvisors_instance, mapper):
    """ Test the SupvisorsMapper.find_local_identifier method when the item host name matches the . """
    fqdn = socket.getfqdn()
    items = [fqdn, '<supervisor>10.0.0.5:7777']
    for item in items:
        supvisors_id = SupvisorsInstanceId(item, supvisors_instance)
        mapper._instances[supvisors_id.identifier] = supvisors_id
        assert supvisors_id.stereotypes == []
    # 1. force host name and aliases
    sup_id = mapper._instances[f'{fqdn}:25000']
    sup_id.host_name = fqdn
    sup_id.aliases = ['dummy']
    # find self
    mapper._find_local_identifier({'test'})
    assert mapper.local_identifier == f'{fqdn}:25000'
    for identifier, supvisors_id in mapper.instances.items():
        assert identifier != fqdn or supvisors_id.stereotypes == ['test']
    # 2. move fqdn
    sup_id.host_name = 'dummy'
    sup_id.aliases = [fqdn]
    sup_id.stereotypes = []
    # find self
    mapper._find_local_identifier({'test_2'})
    assert mapper.local_identifier == f'{fqdn}:25000'
    for identifier, supvisors_id in mapper.instances.items():
        assert identifier != fqdn or supvisors_id.stereotypes == ['test_2']


def test_find_local_identifier_host_name(supvisors_instance, mapper):
    """ Test the SupvisorsMapper.find_local_identifier method when one instance matches the host name and the HTTP
    server port. """
    host_name, fqdn = socket.gethostname(), socket.getfqdn()
    items = ['127.0.0.1', f'{host_name}:25000']
    for item in items:
        supvisors_id = SupvisorsInstanceId(item, supvisors_instance)
        mapper._instances[supvisors_id.identifier] = supvisors_id
        assert supvisors_id.stereotypes == []
    # 1. force host name and aliases
    sup_id = mapper._instances[f'{host_name}:25000']
    sup_id.host_name = fqdn
    sup_id.aliases = ['dummy']
    # find self
    mapper._find_local_identifier({'test'})
    assert mapper.local_identifier == f'{host_name}:25000'
    for identifier, supvisors_id in mapper.instances.items():
        assert identifier != fqdn or supvisors_id.stereotype == ['test']
    # 2. move fqdn
    sup_id.host_name = 'dummy'
    sup_id.aliases = [fqdn]
    # find self
    mapper._find_local_identifier({'test_2'})
    assert mapper.local_identifier == f'{host_name}:25000'
    for identifier, supvisors_id in mapper.instances.items():
        assert identifier != fqdn or supvisors_id.stereotype == ['test_2']


def test_find_local_identifier_ip_address(supvisors_instance, mapper):
    """ Test the SupvisorsMapper.find_local_identifier method when one instance matches the IP address of the host
    and the HTTP server port. """
    host_name, fqdn = socket.gethostname(), socket.getfqdn()
    _, _, ip_addresses = socket.gethostbyaddr(fqdn)
    items = ['127.0.0.1', f'<host>{ip_addresses[0]}:25000']
    for item in items:
        supvisors_id = SupvisorsInstanceId(item, supvisors_instance)
        mapper._instances[supvisors_id.identifier] = supvisors_id
        assert supvisors_id.stereotypes == []
    # 1. force host name and aliases
    sup_id = mapper._instances[f'{ip_addresses[0]}:25000']
    sup_id.host_name = fqdn
    sup_id.aliases = ['dummy']
    # find self
    mapper._find_local_identifier({'test'})
    assert mapper.local_identifier == f'{ip_addresses[0]}:25000'
    for identifier, supvisors_id in mapper.instances.items():
        assert identifier != fqdn or supvisors_id.stereotypes == ['test']
    # 2. move fqdn
    sup_id.host_name = 'dummy'
    sup_id.aliases = [fqdn]
    # find self
    mapper._find_local_identifier({'test_2'})
    assert mapper.local_identifier == f'{ip_addresses[0]}:25000'
    for identifier, supvisors_id in mapper.instances.items():
        assert identifier != fqdn or supvisors_id.stereotypes == ['test_2']


def test_find_local_identifier_inconsistent(supvisors_instance, mapper):
    """ Test the SupvisorsMapper.find_local_identifier method when the identifier corresponds to thr local Supvisors
    instance but the host_name and http_port do not match. """
    host_name = socket.gethostname()
    supvisors_id = SupvisorsInstanceId(f'<{host_name}>10.0.0.5:7777', supvisors_instance)
    mapper._instances[supvisors_id.identifier] = supvisors_id
    assert supvisors_id.stereotypes == []
    # find self
    with pytest.raises(ValueError):
        mapper._find_local_identifier({'test'})
    assert supvisors_id.stereotypes == []


def test_find_local_identifier_multiple(supvisors_instance, mapper):
    """ Test the SupvisorsMapper.find_local_identifier method when more than one instance matches the host name
    or IP address of the host. """
    host_name, fqdn = socket.gethostname(), socket.getfqdn()
    items = ['10.0.0.1', f'{host_name}:25000']
    for item in items:
        supvisors_id = SupvisorsInstanceId(item, supvisors_instance)
        mapper._instances[supvisors_id.identifier] = supvisors_id
        assert supvisors_id.stereotypes == []
        # update default processing of host
        supvisors_id.host_name = fqdn
    # find self
    with pytest.raises(ValueError):
        mapper._find_local_identifier({'test'})
    for supvisors_id in mapper._instances.values():
        assert supvisors_id.stereotypes == []


def test_find_local_identifier_none(supvisors_instance, mapper):
    """ Test the SupvisorsMapper.find_local_identifier method when no instance matches the host name
    or IP address of the host. """
    host_name = socket.gethostname()
    items = ['10.0.0.2', '<dummy>cliche:60000', f'{host_name}:60000']
    for item in items:
        supvisors_id = SupvisorsInstanceId(item, supvisors_instance)
        mapper._instances[supvisors_id.identifier] = supvisors_id
    with pytest.raises(ValueError):
        mapper._find_local_identifier({'test'})
    for supvisors_id in mapper._instances.values():
        assert supvisors_id.stereotypes == []


def test_filter(supvisors_instance, mapper):
    """ Test the SupvisorsMapper.filter method. """
    # add context
    hostname = socket.gethostname()
    items = ['127.0.0.1', '<host>10.0.0.1:2222', f'{hostname}:60000', '10.0.0.2']
    for item in items:
        supvisors_id = SupvisorsInstanceId(item, supvisors_instance)
        mapper._instances[supvisors_id.identifier] = supvisors_id
        mapper._nick_identifiers[supvisors_id.nick_identifier] = supvisors_id.identifier
    # force host name to FQDN
    mapper._instances[f'{hostname}:60000'].host_name = socket.getfqdn()
    # test with a bunch of identifiers
    identifier_list = ['host', f'{hostname}:60000', hostname, 'host', 'supervisor', '10.0.0.1']
    assert mapper.filter(identifier_list) == ['10.0.0.1:2222', f'{hostname}:60000']
    # set stereotype to one of them
    mapper._assign_stereotypes('10.0.0.2:25000', {'supervisor'})
    assert mapper.filter(identifier_list) == ['10.0.0.1:2222', f'{hostname}:60000', '10.0.0.2:25000']


def test_identify(mapper):
    """ Test the SupvisorsMapper.identify method. """
    mapper.configure(['10.0.0.1', '10.0.0.2'], {'test'}, [])
    sup_id: SupvisorsInstanceId = mapper.instances['10.0.0.1:25000']
    assert not sup_id.local_view
    assert not sup_id.remote_view
    payload = mapper.serial()
    assert payload == {'identifier': '10.0.0.1:25000',
                       'nick_identifier': '10.0.0.1',
                       'host_id': '10.0.0.1',
                       'http_port': 25000,
                       'stereotypes': ['test'],
                       'network': {'addresses': {'eth0': {'host_name': 'supv01.bzh',
                                                          'aliases': ['cliche01', 'supv01'],
                                                          'ipv4_addresses': ['10.0.0.1'],
                                                          'nic_info': {'ipv4_address': '10.0.0.1',
                                                                       'netmask': '255.255.255.0',
                                                                       'nic_name': 'eth0'}}},
                                   'fqdn': 'supv01.bzh',
                                   'machine_id': '01:23:45:67:89:ab'}}
    mapper.identify(payload)
    expected = {'fqdn': 'supv01.bzh',
                'machine_id': '01:23:45:67:89:ab',
                'addresses': {'eth0': {'host_name': 'supv01.bzh',
                                       'aliases': ['cliche01', 'supv01'],
                                       'ipv4_addresses': ['10.0.0.1'],
                                       'nic_info': {'ipv4_address': '10.0.0.1',
                                                    'netmask': '255.255.255.0',
                                                    'nic_name': 'eth0'}}}}
    assert sup_id.local_view.serial() == expected
    assert sup_id.remote_view.serial() == expected
    assert sup_id.stereotypes == ['test']


def test_assign_stereotypes(supvisors_instance, mapper):
    """ Test the SupvisorsMapper.assign_stereotypes method. """
    # add context
    items = ['10.0.0.1', '10.0.0.3', '10.0.0.4', '10.0.0.2']
    for item in items:
        supvisors_id = SupvisorsInstanceId(item, supvisors_instance)
        mapper._instances[supvisors_id.identifier] = supvisors_id
        assert supvisors_id.stereotypes == []
    assert mapper.stereotypes == {}
    # test with empty stereotype
    mapper._assign_stereotypes('10.0.0.1:25000', set())
    assert mapper.stereotypes == {}
    assert all(x.stereotypes == [] for x in mapper.instances.values())
    # assign stereotype to a Supvisors instance
    mapper._assign_stereotypes('10.0.0.3:25000', {'test'})
    assert mapper.stereotypes == {'test': ['10.0.0.3:25000']}
    assert mapper.instances['10.0.0.1:25000'].stereotypes == []
    assert mapper.instances['10.0.0.2:25000'].stereotypes == []
    assert mapper.instances['10.0.0.3:25000'].stereotypes == ['test']
    assert mapper.instances['10.0.0.4:25000'].stereotypes == []
    # assign same stereotype to another Supvisors instance that is before in the instances order
    mapper._assign_stereotypes('10.0.0.1:25000', {'test'})
    assert mapper.stereotypes == {'test': ['10.0.0.1:25000', '10.0.0.3:25000']}
    assert mapper.instances['10.0.0.1:25000'].stereotypes == ['test']
    assert mapper.instances['10.0.0.2:25000'].stereotypes == []
    assert mapper.instances['10.0.0.3:25000'].stereotypes == ['test']
    assert mapper.instances['10.0.0.4:25000'].stereotypes == []
    # assign same stereotype to another Supvisors instance that is after in the instances order
    mapper._assign_stereotypes('10.0.0.2:25000', {'test', 'other test'})
    assert mapper.stereotypes == {'test': ['10.0.0.1:25000', '10.0.0.3:25000', '10.0.0.2:25000'],
                                  'other test': ['10.0.0.2:25000']}
    assert mapper.instances['10.0.0.1:25000'].stereotypes == ['test']
    assert sorted(mapper.instances['10.0.0.2:25000'].stereotypes) == sorted(['test', 'other test'])
    assert mapper.instances['10.0.0.3:25000'].stereotypes == ['test']
    assert mapper.instances['10.0.0.4:25000'].stereotypes == []
    # assign another stereotype to another Supvisors instance
    mapper._assign_stereotypes('10.0.0.4:25000', {'other test'})
    assert mapper.stereotypes == {'test': ['10.0.0.1:25000', '10.0.0.3:25000', '10.0.0.2:25000'],
                                  'other test': ['10.0.0.4:25000', '10.0.0.2:25000']}
    assert mapper.instances['10.0.0.1:25000'].stereotypes == ['test']
    assert sorted(mapper.instances['10.0.0.2:25000'].stereotypes) == sorted(['test', 'other test'])
    assert mapper.instances['10.0.0.3:25000'].stereotypes == ['test']
    assert mapper.instances['10.0.0.4:25000'].stereotypes == ['other test']
    # test serial with stereotypes
    assert mapper.instances['10.0.0.1:25000'].serial()['stereotypes'] == ['test']
    assert sorted(mapper.instances['10.0.0.2:25000'].serial()['stereotypes']) == ['other test', 'test']
    assert mapper.instances['10.0.0.3:25000'].serial()['stereotypes'] == ['test']
    assert mapper.instances['10.0.0.4:25000'].serial()['stereotypes'] == ['other test']


def test_check_candidate(supvisors_instance, mapper):
    """ Test the SupvisorsMapper.check_candidate method. """
    # add context
    hostname = socket.gethostname()
    items = ['127.0.0.1', '<host>10.0.0.1:2222', f'{hostname}:60000', '10.0.0.2']
    for item in items:
        supvisors_id = SupvisorsInstanceId(item, supvisors_instance)
        mapper._instances[supvisors_id.identifier] = supvisors_id
        mapper._nick_identifiers[supvisors_id.nick_identifier] = supvisors_id.identifier
    # force host name to FQDN
    mapper._instances[f'{hostname}:60000'].host_name = socket.getfqdn()
    # test existing instances
    assert not mapper.check_candidate('127.0.0.1:25000', '127.0.0.1')
    assert not mapper.check_candidate('10.0.0.1:2222', 'host')
    assert not mapper.check_candidate(f'{hostname}:60000', f'{hostname}:60000')
    assert not mapper.check_candidate('10.0.0.2:25000', '10.0.0.2')
    # test partially known instances (this will trigger log warnings)
    assert not mapper.check_candidate('127.0.0.1:25000', 'host')
    assert not mapper.check_candidate(f'{hostname}:50000', '10.0.0.2')
    # test unknown instances
    assert mapper.check_candidate(f'{hostname}:50000', f'{hostname}:50000')
    assert mapper.check_candidate('10.0.0.3:3333', '10.0.0.3')
