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

import fcntl
import ipaddress
import re
import socket
import struct
import uuid
from collections import OrderedDict
from typing import Any, Dict, Iterator, Optional, Tuple

from supervisor.loggers import Logger

from supvisors.ttypes import Ipv4Address, NameList, NameSet, Payload

# default identifier given by Supervisor
DEFAULT_IDENTIFIER = 'supervisor'

# additional annotation types
HostAddresses = Tuple[str, NameList, NameList]

# ioctl codes
SIOCGIFADDR = 0x8915
SIOCGIFNETMASK = 0x891b


class NicInformation:
    """ Identification of a network link. """

    def __init__(self, nic_name: str, ipv4_address: str, netmask: str):
        """ Declare attributes. """
        self.nic_name: str = nic_name
        self.ipv4_address: str = ipv4_address
        self.netmask: str = netmask
        # get the network address based on IP address and netmask
        network = ipaddress.ip_network(f'{ipv4_address}/{netmask}', strict=False)
        self.network_address = network.network_address.compressed

    @property
    def is_loopback(self):
        return ipaddress.ip_address(self.ipv4_address).is_loopback

    def serial(self) -> Payload:
        return {'nic_name': self.nic_name,
                'ipv4_address': self.ipv4_address,
                'netmask': self.netmask}


def get_interface_info(nic_name: str) -> Optional[Tuple[str, str]]:
    """ Get the local IPv4 address and netmask linked to a network interface. """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # get IP address
        result = fcntl.ioctl(sock.fileno(), SIOCGIFADDR, struct.pack('256s', nic_name[:15].encode()))
        ip_address = socket.inet_ntoa(result[20:24])
        # get netmask
        result = fcntl.ioctl(sock.fileno(), SIOCGIFNETMASK, struct.pack('256s', nic_name[:15].encode()))
        netmask = socket.inet_ntoa(result[20:24])
        return ip_address, netmask
    except IOError:
        return None


def get_network_info() -> Iterator[NicInformation]:
    """ Get all IPv4 addresses on all network interfaces (loopback excepted).

    :return: the IPv4 addresses.
    """
    for _, nic_name in socket.if_nameindex():
        addr = get_interface_info(nic_name)
        if addr:
            nic_info = NicInformation(nic_name, *addr)
            if not nic_info.is_loopback:
                yield nic_info


class NetworkAddress:
    """ All address representations for one network interface. """

    def __init__(self, logger: Logger, nic_info: Optional[NicInformation] = None, host_id: Optional[str] = None):
        """ Declare attributes. """
        self.logger: Logger = logger
        # the address information
        self.host_name: str = ''
        self.aliases: NameList = []
        self.ipv4_addresses: NameList = []
        # complete information from network information if provided
        self.nic_info: Optional[NicInformation] = nic_info
        if nic_info:
            self._get_local_view(nic_info.ipv4_address)
        elif host_id:
            self._get_local_view(host_id)

    def _get_local_view(self, host_id: str) -> None:
        """ Get hostname, aliases and all IP addresses for the host_id.

        :param host_id: the host name or IP address.
        :return: None.
        """
        try:
            self.host_name, self.aliases, self.ipv4_addresses = socket.gethostbyaddr(host_id)
            self.logger.debug(f'NetworkAddress: host_id={host_id} - host_name={self.host_name}'
                              f' aliases={self.aliases} ipv4_addresses={self.ipv4_addresses}')
        except (socket.herror, socket.gaierror):
            self.logger.error(f'NetworkAddress.get_local_view: unknown address {host_id}')

    def host_matches(self, host_id: str) -> bool:
        """ Return True if one local address matches the host identifier passed in parameter.
        Use all addresses returned by gethostbyaddr. """
        return host_id in [self.host_name] + self.aliases + self.ipv4_addresses

    def ip_matches(self, ip_address: str) -> bool:
        """ Return True if this instance matches the ip_address passed in parameter. """
        if self.nic_info:
            return ip_address == self.nic_info.ipv4_address
        return False

    def name_matches(self, host_name: str) -> bool:
        """ Return True if the host name or any alias matches the host identifier passed in parameter.

        The test of nic_info is not an error, as this method is used to get the network address corresponding
        to the host name in parameter. The network address is only available in the NicInformation.
        """
        if self.nic_info:
            return host_name in [self.host_name] + self.aliases
        return False

    def get_network_ip(self, network_address: str) -> str:
        """ Return the main IPv4 address if corresponding to the same network. """
        if self.nic_info and self.nic_info.network_address == network_address:
            return self.nic_info.ipv4_address
        return ''

    def from_payload(self, payload: Payload) -> None:
        """ Take the address information as it is. """
        self.host_name = payload['host_name']
        self.aliases = payload['aliases']
        self.ipv4_addresses = payload['ipv4_addresses']
        self.nic_info = NicInformation(**payload['nic_info'])

    def serial(self) -> Payload:
        """ Get a serializable form of the address information. """
        return {'host_name': self.host_name,
                'aliases': self.aliases,
                'ipv4_addresses': self.ipv4_addresses,
                'nic_info': self.nic_info.serial() if self.nic_info else None}


class LocalNetwork:
    """ All address representations for all network interfaces. """

    def __init__(self, logger: Logger):
        """ Init from supvisors_list. """
        self.logger: Logger = logger
        self.machine_id: str = ':'.join(re.findall('..', f'{uuid.getnode():012x}'))
        self.fqdn: str = socket.getfqdn()
        self.addresses: Dict[str, NetworkAddress] = {nic_info.nic_name: NetworkAddress(self.logger, nic_info=nic_info)
                                                     for nic_info in get_network_info()}

    def host_matches(self, host_id: str) -> bool:
        """ Return True if any local address matches the host identifier passed in parameter.
        This is only used to find the local identifier.
        """
        return next((True for netw in self.addresses.values()
                     if netw.host_matches(host_id)), False)

    def get_network_address(self, host_id: str) -> str:
        """ Return the network address of the interface matching the host_id.
        This is only used for web navigation.
        """
        # first try: host_id is an IP address
        for netw in self.addresses.values():
            if netw.ip_matches(host_id):
                # if there is a match, there must be a NicInformation
                return netw.nic_info.network_address
        # second try: host_id is a host name or alias
        # WARN: this may not identify a unique network interface
        for netw in self.addresses.values():
            if netw.name_matches(host_id):
                # if there is a match, there must be a NicInformation
                return netw.nic_info.network_address
        self.logger.debug('LocalNetwork.get_network_address: cannot find any network address matching'
                          f' hostname={host_id}')
        return ''

    def get_network_ip(self, network_address: str) -> str:
        """ Return the IPv4 address if one interface matches the network address. """
        for netw in self.addresses.values():
            ipv4_address = netw.get_network_ip(network_address)
            if ipv4_address:
                return ipv4_address
        self.logger.debug('LocalNetwork.get_network_ip: cannot find any IP address matching'
                          f' network_address={network_address}')
        return ''

    def from_payload(self, payload: Payload) -> None:
        """ Take the address information as it is. """
        self.machine_id = payload['machine_id']
        self.fqdn = payload['fqdn']
        for nic_name, address in payload['addresses'].items():
            self.addresses[nic_name] = addr = NetworkAddress(self.logger)
            addr.from_payload(address)

    def from_network(self, network) -> None:
        """ Rebuild a local view from a remote view. """
        self.machine_id = network.machine_id
        self.fqdn = socket.getfqdn(network.fqdn)
        self.addresses = {nic_name: NetworkAddress(self.logger, nic_info=addr.nic_info)
                          for nic_name, addr in network.addresses.items()}

    def serial(self) -> Payload:
        """ Get a serializable form of the local network. """
        return {'machine_id': self.machine_id,
                'fqdn': self.fqdn,
                'addresses': {nic_name: addr.serial()
                              for nic_name, addr in self.addresses.items()}}


class SupvisorsInstanceId:
    """ Identification attributes for a Supvisors instance.

    The Supvisors instance uses the Supervisor identifier if provided, or builds an identifier from the host name and
    the HTTP port used by this Supervisor.

    Attributes are:
        - identifier: the Supvisors identifier 'host_name:http_port' ;
        - nick_identifier: the Supervisor identifier (defaulted to identifier) if not provided ;
        - host_id: the host where the Supervisor is running ;
        - http_port: the Supervisor port number ;
        - event_port: the port number used to publish all Supvisors events ;
        - host_name: the host name corresponding to the host id, as known by the local network configuration ;
        - ip_address: the main ip_address of the host, as known by the local network configuration ;
        - stereotype: the stereotype (used for rules).
    """

    PATTERN = re.compile(r'^(<(?P<identifier>[\w\-:.]+)>)?(?P<host>[\w\-.]+)(:(?P<http_port>\d{4,5}))?$')

    # attributes taken from input
    identifier: str = None
    nick_identifier: str = None
    host_id: str = None
    http_port: int = None
    event_port: int = None

    simple_address: NetworkAddress = None
    remote_view: LocalNetwork = None  # as received from remote
    local_view: LocalNetwork = None  # local view from remote

    def __init__(self, item: str, supvisors: Any):
        """ Initialization of the attributes.

        :param item: the Supervisor parameters to be parsed.
        """
        self.supvisors = supvisors
        # attributes set a posteriori
        self.stereotypes: NameList = []
        # parse item to get the values
        self.parse_from_string(item)
        self.check_values()
        # get minimal information about the host identified
        if self.host_id:
            self.simple_address = NetworkAddress(supvisors.logger, host_id=self.host_id)

    @property
    def logger(self) -> Logger:
        """ Shortcut to the Supvisors logger. """
        return self.supvisors.logger

    @property
    def ip_address(self) -> Optional[str]:
        """ Return the main IP address. """
        if self.simple_address:
            if self.simple_address.ipv4_addresses:
                return self.simple_address.ipv4_addresses[0]
        return None

    @property
    def source(self) -> Tuple[str, str, Ipv4Address]:
        """ Return the identification details of the instance. """
        return self.identifier, self.nick_identifier, (self.ip_address, self.http_port)

    def is_valid(self, ipv4_address: Ipv4Address) -> bool:
        """ Return True if the IPv4 address fits the Supvisors identification.
        Some flexibility is given until the remote network is received.
        """
        ip_address, http_port = ipv4_address
        return self.http_port == http_port and (not self.local_view or self.local_view.host_matches(ip_address))

    def check_values(self) -> None:
        """ Complete information where not provided.

        :return: None.
        """
        http_port = self.http_port or self.supvisors.supervisor_data.server_port
        # define common identifier
        if self.host_id:
            self.identifier = f'{self.host_id}:{http_port}'
            # if nick_identifier is not set or default Supervisor identifier is used, assign an automatic identifier
            if not self.nick_identifier or self.nick_identifier == DEFAULT_IDENTIFIER:
                if self.http_port:
                    self.nick_identifier = self.identifier
                else:
                    self.nick_identifier = self.host_id
        # if http_port is not provided, use the local http_port value
        if not self.http_port:
            self.http_port = http_port
        # define event_port using option value if set
        if self.supvisors.options.event_port:
            self.event_port = self.supvisors.options.event_port
        else:
            # by default, assign to http_port + 1
            self.event_port = self.http_port + 1
        self.logger.debug(f'SupvisorsInstanceId.check_values: identifier={self.identifier}'
                          f' nick_identifier={self.nick_identifier}'
                          f' host_id={self.host_id} http_port={self.http_port}')

    def get_network_ip(self, network_address: Optional[str]) -> str:
        """ Return the IPv4 address if one interface matches the network address. """
        ip = ''
        if network_address and self.local_view:
            ip = self.local_view.get_network_ip(network_address)
        return ip or self.host_id

    def parse_from_string(self, item: str):
        """ Parse string according to PATTERN to get the Supvisors instance identification attributes.

        :param item: the parameters to be parsed
        :return: None
        """
        pattern_match = SupvisorsInstanceId.PATTERN.match(item)
        if pattern_match:
            self.nick_identifier = pattern_match.group('identifier')
            self.host_id = pattern_match.group('host')
            # check http port
            port = pattern_match.group('http_port')
            self.http_port = int(port) if port else 0
            self.logger.debug(f'SupvisorsInstanceId.parse_from_string: identifier={self.identifier}'
                              f' host_id={self.host_id} http_port={self.http_port}')

    def serial(self, with_network: Optional[bool] = True) -> Payload:
        """ Get a serializable form of the instance parameters.

        :return: the instance parameters in a dictionary.
        """
        payload = {'identifier': self.identifier,
                   'nick_identifier': self.nick_identifier,
                   'host_id': self.host_id,
                   'http_port': self.http_port,
                   'stereotypes': self.stereotypes}
        if self.local_view and with_network:
            payload['network'] = self.local_view.serial()
        return payload

    def __repr__(self) -> str:
        """ Initialization of the attributes.

        :return: the identifier as string representation of the SupvisorsInstanceId object.
        """
        if self.identifier == self.nick_identifier:
            return self.identifier
        return f'<{self.nick_identifier}>{self.identifier}'


class SupvisorsMapper:
    """ Class used for storage of the Supvisors instances declared in the configuration file.

    Attributes are:
        - supvisors: the global Supvisors structure ;
        - logger: the reference to the common logger ;
        - _instances: the list of Supvisors instances declared in the supvisors section of the Supervisor
          configuration file ;
        - _nick_identifiers: the list of nick identifiers that can be used on all Supvisors user interfaces ;
        - nodes: the list of Supvisors instances grouped by node names ;
        - _core_identifiers: the list of Supvisors core identifiers declared in the supvisors section of the Supervisor
          configuration file ;
        - local_identifier: the local Supvisors identifier ;
        - initial_identifiers: the initial list of Supvisors instances (excluding the discovered ones) ;
        - stereotypes: the Supvisors identifiers, sorted by stereotype.
    """

    # annotation types
    InstancesMap = Dict[str, SupvisorsInstanceId]

    def __init__(self, supvisors: Any):
        """ Initialization of the attributes.

        :param supvisors: the global Supvisors structure.
        """
        self.supvisors = supvisors
        self.local_network: LocalNetwork = LocalNetwork(supvisors.logger)
        self._instances: SupvisorsMapper.InstancesMap = OrderedDict()  # {identifier: supvisors_id}
        self._nick_identifiers: Dict[str, str] = {}  # {nick_identifier: identifier}
        self.nodes: Dict[str, NameList] = {}  # {machine_id: identifier}
        self._core_identifiers: NameList = []
        self.local_identifier: Optional[str] = None
        self.initial_identifiers: NameList = []
        self.stereotypes: Dict[str, NameList] = {}

    @property
    def logger(self) -> Logger:
        """ Return the Supvisors logger. """
        return self.supvisors.logger

    @property
    def local_instance(self) -> SupvisorsInstanceId:
        """ Property getter for the SupvisorsInstanceId corresponding to local_identifier.

        :return: the local SupvisorsInstanceId.
        """
        return self._instances[self.local_identifier]

    @property
    def local_nick_identifier(self) -> str:
        """ Property getter for the nick identifier of the local Supvisors instance.

        :return: the local nick identifier.
        """
        return self.local_instance.nick_identifier

    @property
    def instances(self) -> InstancesMap:
        """ Property getter for the _instances attribute.

        :return: the list of Supvisors instances configured in Supvisors
        """
        return self._instances

    @property
    def core_identifiers(self) -> NameList:
        """ Get the known Supvisors core identifiers.

        :return: the minimum Supvisors identifiers to end the synchronization phase
        """
        return self.filter(self._core_identifiers)

    def get_nick_identifier(self, identifier: str) -> str:
        """ Property getter for the nick identifier of the Supvisors instance.

        :return: the nick identifier.
        """
        return self.instances[identifier].nick_identifier

    def add_instance(self, item: str) -> SupvisorsInstanceId:
        """ Store a new Supvisors instance using a format compliant with the supvisors_list option.

        :param item: the Supvisors instance to add.
        :return: the new Supvisors instance.
        """
        supvisors_id = SupvisorsInstanceId(item, self.supvisors)
        if supvisors_id.ip_address:
            self._instances[supvisors_id.identifier] = supvisors_id
            self._nick_identifiers[supvisors_id.nick_identifier] = supvisors_id.identifier
            return supvisors_id
        raise ValueError(f'could not define a Supvisors identification from "{item}"')

    def configure(self, supvisors_list: NameList, stereotypes: NameSet, core_list: NameList) -> None:
        """ Store the identification of the Supvisors instances declared in the configuration file and determine
        the local Supvisors instance in this list.

        :param supvisors_list: the Supvisors instances declared in the supvisors section of the configuration file.
        :param stereotypes: the local Supvisors instance stereotypes.
        :param core_list: the minimum Supvisors identifiers to end the synchronization phase.
        :return: None.
        """
        if supvisors_list:
            # get Supervisor identification from each element
            for item in supvisors_list:
                self.add_instance(item)
            # keep information about the initial Supvisors identifiers added to the configuration
            self.initial_identifiers = list(self._instances.keys())
        else:
            # if supvisors_list is empty, use self identification from supervisor internal data
            supervisor = self.supvisors.supervisor_data
            item = f'<{supervisor.identifier}>{socket.gethostname()}:{supervisor.server_port}'
            self.logger.info(f'SupvisorsMapper.configure: define local Supvisors as {item}')
            self.add_instance(item)
        self.logger.info(f'SupvisorsMapper.configure: identifiers={self._nick_identifiers}')
        self.logger.info(f'SupvisorsMapper.configure: nodes={self.nodes}')
        # get local Supervisor identification from list
        self._find_local_identifier(stereotypes)
        # NOTE: store the core identifiers without filtering as is.
        #       they can only be filtered on access because of discovery mode.
        self._core_identifiers = core_list
        self.logger.info(f'SupvisorsMapper.configure: core_identifiers={core_list}')

    def _find_local_identifier(self, stereotypes: NameSet):
        """ Find the local Supvisors identification in the list declared in the configuration file.

        It can be either the Supervisor identifier or a name built using the host name or any of its known IP addresses.

        :param stereotypes: the local Supvisors instance stereotypes.
        :return: the identifier of the Supvisors instance.
        """
        http_port = self.supvisors.supervisor_data.server_port
        # try to find a Supvisors instance corresponding to the network configuration
        # WARN: there MUST be exactly one unique matching Supvisors instance
        matching_identifiers = [sup_id.identifier
                                for sup_id in self._instances.values()
                                if self.local_network.host_matches(sup_id.host_id) and sup_id.http_port == http_port]
        if len(matching_identifiers) == 1:
            self.local_identifier = matching_identifiers[0]
            self.logger.info(f'SupvisorsMapper.find_local_identifier: {str(self.local_instance)}')
            # assign the local network to the instance
            self.local_instance.local_view = self.local_network
            # check consistence with Supervisor configuration
            configured_identifier = self.supvisors.supervisor_data.identifier
            if configured_identifier not in [DEFAULT_IDENTIFIER, self.local_nick_identifier]:
                self.logger.warn('SupvisorsMapper.find_local_identifier: mismatch between Supervisor identifier'
                                 f' "{configured_identifier}" and local Supvisors identified in supvisors_list'
                                 f' "{self.local_nick_identifier}"')
            # assign the generic Supvisors instance stereotype
            self._assign_stereotypes(self.local_identifier, stereotypes)
        else:
            if len(matching_identifiers) > 1:
                message = f'multiple candidates for the Supvisors identifiers={matching_identifiers}'
            else:
                message = 'could not find the Supvisors in supvisors_list'
            self.logger.error(f'SupvisorsMapper.find_supvisors_instance: {message}')
            raise ValueError(message)

    def filter(self, identifier_list: NameList) -> NameList:
        """ Check the identifiers list against the identifiers declared in the configuration file
        or via the discovery mode.

        The identifier list can be made of Supvisors identifiers, Supervisor identifiers and/or stereotypes.

        If the identifier is not found, it is removed from the list.
        If more than one occurrence of the same identifier is found, only the first one is kept.

        :param identifier_list: a list of Supvisors identifiers and/or nick identifiers and/or stereotypes.
        :return: the filtered list of Supvisors identifiers.
        """
        identifiers = []
        # filter unknown Supvisors identifiers and expand the stereotypes
        for identifier in identifier_list:
            if identifier in self._instances:
                identifiers.append(identifier)
            elif identifier in self._nick_identifiers:
                identifiers.append(self._nick_identifiers[identifier])
            elif identifier in self.stereotypes:
                # identifier is a stereotype
                identifiers.extend(self.stereotypes[identifier])
            else:
                self.logger.warn(f'SupvisorsMapper.filter: identifier={identifier} invalid')
        # remove duplicates keeping the same order
        return list(OrderedDict.fromkeys(identifiers))

    def identify(self, payload: Payload) -> None:
        """ Associate the remote detailed network information to a SupvisorsId instance.

        :param payload: the network information of the remote Supvisors instance.
        :return: None.
        """
        self.logger.debug(f'SupvisorsMapper.identify: {payload}')
        identifier = payload['identifier']
        sup_id: SupvisorsInstanceId = self.instances[identifier]
        # build LocalNetwork from the payload as it is, and assign it to the remote view
        sup_id.remote_view = remote_view = LocalNetwork(self.logger)
        remote_view.from_payload(payload['network'])
        # build a local view from it (local instance already configured)
        if not sup_id.local_view:
            sup_id.local_view = local_view = LocalNetwork(self.logger)
            local_view.from_network(remote_view)
        # update nodes using machine id as a key
        self.nodes.setdefault(remote_view.machine_id, []).append(sup_id.identifier)
        # assign the stereotypes
        self._assign_stereotypes(identifier, payload['stereotypes'])

    def _assign_stereotypes(self, identifier: str, stereotypes: NameSet) -> None:
        """ Assign stereotypes to the Supvisors instance.

        The method maintains a map of Supvisors instances per stereotype.
        The list of Supvisors instances per stereotype is ordered the same way as the Supvisors instances themselves.

        :param identifier: the identifier of the Supvisors instance.
        :param stereotypes: the stereotypes of the Supvisors instance.
        :return: None.
        """
        # assign stereotypes on the first attempt only
        sup_id: SupvisorsInstanceId = self.instances[identifier]
        if stereotypes and not sup_id.stereotypes:
            self.logger.info(f'SupvisorsMapper.assign_stereotype: identifier={identifier} stereotypes={stereotypes}')
            # set stereotype in SupvisorsInstanceId
            sup_id.stereotypes = list(stereotypes)
            # update map
            for stereotype in stereotypes:
                if stereotype in self.stereotypes:
                    # a new identifier has to be added to the list, keeping the same order as in self._instances
                    identifiers = self.stereotypes[stereotype]
                    identifiers.append(identifier)
                    self.stereotypes[stereotype] = [x for x in self.instances.keys() if x in identifiers]
                else:
                    self.stereotypes[stereotype] = [identifier]

    def check_candidate(self, identifier: str, nick_identifier: str) -> bool:
        """ Return True if the candidate is eligible as a new Supvisors instance.

        :param identifier: the candidate identifier.
        :param nick_identifier: the candidate nick identifier.
        :return: True if the candidate is unknown.
        """
        if nick_identifier in self._nick_identifiers:
            known_identifier = self._nick_identifiers[nick_identifier]
            if known_identifier != identifier:
                self.logger.warn(f'SupvisorsMapper.check_candidate: candidate=<{nick_identifier}>{identifier}'
                                 f' incompatible with the Supvisors instance known as'
                                 f' <{nick_identifier}>{known_identifier}')
            return False
        if identifier in self.instances:
            known_nick_identifier = self.get_nick_identifier(identifier)
            if known_nick_identifier != nick_identifier:
                self.logger.warn(f'SupvisorsMapper.check_candidate: candidate=<{nick_identifier}>{identifier}'
                                 f' incompatible with the Supvisors instance known as'
                                 f' <{known_nick_identifier}>{identifier}')
            return False
        return True
