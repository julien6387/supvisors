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

import re
from collections import OrderedDict
from socket import getfqdn, gethostbyaddr, gethostname, herror, gaierror
from typing import Any, Dict, Optional, Tuple

from supervisor.loggers import Logger

from supvisors.ttypes import Ipv4Address, NameList, NameSet, Payload

# default identifier given by Supervisor
DEFAULT_IDENTIFIER = 'supervisor'


def get_addresses(host_id: str, logger: Logger) -> Optional[Tuple[str, NameList, NameList]]:
    """ Get hostname, aliases and all IP addresses for the host_id.

    :param host_id: the host_name used in the Supvisors option
    :param logger: the Supvisors logger
    :return: the list of possible node name or IP addresses
    """
    try:
        return gethostbyaddr(host_id)  # hostname, aliases, ip_addresses
    except (herror, gaierror):
        logger.error(f'get_addresses: unknown address {host_id}')


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
    identifier = None
    nick_identifier = None
    host_id = None
    http_port = None
    event_port = None
    # attributes got from network
    host_name = None
    aliases = None
    ip_addresses = None

    def __init__(self, item: str, supvisors: Any):
        """ Initialization of the attributes.

        :param item: the Supervisor parameters to be parsed
        """
        self.supvisors = supvisors
        # attributes set a posteriori
        self.stereotypes: NameList = []
        # parse item to get the values
        self.parse_from_string(item)
        self.check_values()
        # choose the node name among the possible node identifiers
        if self.host_id:
            addresses = get_addresses(self.host_id, self.logger)
            if addresses:
                self.host_name, self.aliases, self.ip_addresses = addresses
                self.logger.debug(f'SupvisorsInstanceId: host_id={self.host_id} host_name={self.host_name}'
                                  f' aliases={self.aliases} ip_addresses={self.ip_addresses}')

    @property
    def logger(self) -> Logger:
        """ Shortcut to the Supvisors logger. """
        return self.supvisors.logger

    @property
    def ip_address(self) -> Optional[str]:
        """ Return the main IP address. """
        return self.ip_addresses[0] if self.ip_addresses else None

    @property
    def source(self) -> Tuple[str, str, Ipv4Address]:
        """ Return the identification details of the instance. """
        return self.identifier, self.nick_identifier, (self.ip_address, self.http_port)

    def host_matches(self, fdqn: str) -> bool:
        """ Check if the fully-qualified domain name matches the host name or any alias.

        :param fdqn: the fully-qualified domain name to check
        :return: True if fdqn is the local host name or a known alias
        """
        return fdqn == self.host_name or fdqn in self.aliases

    def check_values(self) -> None:
        """ Complete information where not provided.

        :return: None
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

    def serial(self) -> Payload:
        """ Get a serializable form of the instance parameters.

        :return: the instance parameters in a dictionary.
        """
        return {'identifier': self.identifier,
                'nick_identifier': self.nick_identifier,
                'host_id': self.host_id,
                'http_port': self.http_port,
                'host_name': self.host_name,
                'ip_addresses': self.ip_addresses,
                'stereotypes': self.stereotypes}

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
        - _nodes: the list of Supvisors instances grouped by node names ;
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
        self._instances: SupvisorsMapper.InstancesMap = OrderedDict()
        self._nick_identifiers: Dict[str, str] = {}
        self._nodes: Dict[str, NameList] = {}
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
    def nodes(self) -> Dict[str, NameList]:
        """ Property getter for the _nodes attribute.

        :return: the Supvisors identifiers per node
        """
        return self._nodes

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
            self._nodes.setdefault(supvisors_id.ip_address, []).append(supvisors_id.identifier)
            return supvisors_id
        message = f'could not define a Supvisors identification from "{item}"'
        raise ValueError(message)

    def configure(self, supvisors_list: NameList, stereotypes: NameSet, core_list: NameList) -> None:
        """ Store the identification of the Supvisors instances declared in the configuration file and determine
        the local Supvisors instance in this list.

        :param supvisors_list: the Supvisors instances declared in the supvisors section of the configuration file.
        :param stereotypes: the local Supvisors instance stereotypes.
        :param core_list: the minimum Supvisors identifiers to end the synchronization phase.
        :return: None
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
            item = f'<{supervisor.identifier}>{gethostname()}:{supervisor.server_port}'
            self.logger.info(f'SupvisorsMapper.configure: define local Supvisors as {item}')
            self.add_instance(item)
        self.logger.info(f'SupvisorsMapper.configure: identifiers={self._nick_identifiers}')
        self.logger.info(f'SupvisorsMapper.configure: nodes={self.nodes}')
        # get local Supervisor identification from list
        self.find_local_identifier(stereotypes)
        # NOTE: store the core identifiers without filtering as is.
        #       they can only be filtered on access because of discovery mode.
        self._core_identifiers = core_list
        self.logger.info(f'SupvisorsMapper.configure: core_identifiers={core_list}')

    def find_local_identifier(self, stereotypes: NameSet):
        """ Find the local Supvisors identification in the list declared in the configuration file.
        It can be either the local Supervisor identifier or a name built using the local host name or any of its known
        IP addresses.

        :param stereotypes: the local Supvisors instance stereotypes.
        :return: the identifier of the local Supvisors.
        """
        # get the must-match parameters
        local_host_name = getfqdn()
        local_http_port = self.supvisors.supervisor_data.server_port
        # try to find a Supvisors instance corresponding to the local configuration
        # WARN: there MUST be exactly one unique matching Supvisors instance
        matching_identifiers = [sup_id.identifier
                                for sup_id in self._instances.values()
                                if sup_id.host_matches(local_host_name) and sup_id.http_port == local_http_port]
        if len(matching_identifiers) == 1:
            self.local_identifier = matching_identifiers[0]
            if ((self.supvisors.supervisor_data.identifier != DEFAULT_IDENTIFIER)
                    and (self.local_nick_identifier != self.supvisors.supervisor_data.identifier)):
                self.logger.warn('SupvisorsMapper.find_local_identifier: mismatch between Supervisor identifier'
                                 f' "{self.supvisors.supervisor_data.identifier}"'
                                 f' and local Supvisors in supvisors_list "{self.local_nick_identifier}"')
            # assign the generic Supvisors instance stereotype
            self.assign_stereotypes(self.local_identifier, stereotypes)
        else:
            if len(matching_identifiers) > 1:
                message = f'multiple candidates for the local Supvisors identifiers={matching_identifiers}'
            else:
                message = 'could not find the local Supvisors in supvisors_list'
            self.logger.error(f'SupvisorsMapper.find_local_identifier: {message}')
            raise ValueError(message)
        self.logger.info(f'SupvisorsMapper.find_local_identifier: {str(self.local_instance)}')

    def assign_stereotypes(self, identifier: str, stereotypes: NameSet) -> None:
        """ Assign stereotypes to the Supvisors instance.

        The method maintains a map of Supvisors instances per stereotype.
        The list of Supvisors instances per stereotype is ordered the same way as the Supvisors instances themselves.

        :param identifier: the identifier of the Supvisors instance.
        :param stereotypes: the stereotypes of the Supvisors instance.
        :return: None
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
