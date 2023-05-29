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

import re
from collections import OrderedDict
from socket import getfqdn, gethostbyaddr, gethostname, herror, gaierror
from typing import Any, Dict, Optional, Tuple

from supervisor.loggers import Logger

from .ttypes import NameList


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
        - identifier: the Supervisor identifier or 'host_name[:http_port]' if not provided ;
        - host_id: the host where the Supervisor is running ;
        - http_port: the Supervisor port number ;
        - internal_port: the port number used to publish local events to remote Supvisors instances ;
        - event_port: the port number used to publish all Supvisors events ;
        - host_name: the host name corresponding to the host id, as known by the local network configuration ;
        - ip_address: the main ip_address of the host, as known by the local network configuration.
    """

    PATTERN = re.compile(r'^(<(?P<identifier>[\w\-:]+)>)?(?P<host>[\w\-.]+)(:(?P<http_port>\d{4,5})?'
                         r':(?P<internal_port>\d{4,5})?)?$')

    def __init__(self, item: str, supvisors: Any):
        """ Initialization of the attributes.

        :param item: the Supervisor parameters to be parsed
        """
        self.supvisors = supvisors
        self.logger: Logger = supvisors.logger
        # attributes deduced from input
        self.identifier = None
        self.host_id = None
        self.http_port = None
        self.internal_port = None
        self.event_port = None
        # parse item to get the values
        self.parse_from_string(item)
        self.check_values()
        # choose the node name among the possible node identifiers
        self.host_name = None
        self.ip_address = None
        if self.host_id:
            addresses = get_addresses(self.host_id, self.logger)
            if addresses:
                self.host_name, _, ip_addresses = addresses
                self.ip_address = ip_addresses[0]
                self.logger.debug(f'SupvisorsInstanceId: host_id={self.host_id} host_name={self.host_name}'
                                  f' ip_address={self.ip_address}')

    def check_values(self) -> None:
        """ Complete information where not provided.

        :return: None
        """
        # define identifier
        # NOTE: when default supervisor identifier is used, do not consider it
        if (not self.identifier or self.identifier == 'supervisor') and self.host_id:
            self.identifier = self.host_id
            # use HTTP port in identifier only if it has explicitly been defined
            if self.http_port:
                self.identifier += f':{self.http_port}'
        # if http_port is not provided, use the local http_port value
        if not self.http_port:
            self.http_port = self.supvisors.supervisor_data.server_port
        # if internal_port is not provided, use the option value if set or http_port+1
        if not self.internal_port:
            # assign to internal_port option value if set
            if self.supvisors.options.internal_port:
                self.internal_port = self.supvisors.options.internal_port
            else:
                # by default, assign to http_port + 1
                self.internal_port = self.http_port + 1
        # define event_port using option value if set
        if self.supvisors.options.event_port:
            self.event_port = self.supvisors.options.event_port
        else:
            # by default, assign to event_port + 1, unless this value is already taken by http_port
            if self.http_port != self.internal_port + 1:
                self.event_port = self.internal_port + 1
            else:
                # in this case, assign to http_port + 1
                self.event_port = self.http_port + 1
        self.logger.debug(f'SupvisorsInstanceId.check_values: identifier={self.identifier}'
                          f' host_name={self.host_id} http_port={self.http_port}'
                          f' internal_port={self.internal_port}')

    def parse_from_string(self, item: str):
        """ Parse string according to PATTERN to get the Supvisors instance identification attributes.

        :param item: the parameters to be parsed
        :return: None
        """
        pattern_match = SupvisorsInstanceId.PATTERN.match(item)
        if pattern_match:
            self.identifier = pattern_match.group('identifier')
            self.host_id = pattern_match.group('host')
            # check http port
            port = pattern_match.group('http_port')
            self.http_port = int(port) if port else 0
            # check internal port
            port = pattern_match.group('internal_port')
            self.internal_port = int(port) if port else 0
            self.logger.debug(f'SupvisorsInstanceId.parse_from_string: identifier={self.identifier}'
                              f' host_id={self.host_id} http_port={self.http_port}'
                              f' internal_port={self.internal_port}')

    def __repr__(self) -> str:
        """ Initialization of the attributes.

        :return: the identifier as string representation of the SupvisorsInstanceId object
        """
        return self.identifier


class SupvisorsMapper:
    """ Class used for storage of the Supvisors instances declared in the configuration file.

    Attributes are:
        - supvisors: the global Supvisors structure ;
        - logger: the reference to the common logger ;
        - _instances: the list of Supvisors instances declared in the supvisors section of the Supervisor
          configuration file ;
        - _nodes: the list of Supvisors instances grouped by node names ;
        - _core_identifiers: the list of Supvisors core identifiers declared in the supvisors section of the Supervisor
          configuration file ;
        - local_identifier: the local Supvisors identifier.
    """

    # annotation types
    InstancesMap = Dict[str, SupvisorsInstanceId]

    def __init__(self, supvisors: Any):
        """ Initialization of the attributes.

        :param supvisors: the global Supvisors structure
        """
        # keep reference of common logger
        self.supvisors = supvisors
        self.logger: Logger = supvisors.logger
        # init attributes
        self._instances: SupvisorsMapper.InstancesMap = OrderedDict()
        self._nodes: Dict[str, NameList] = {}
        self._core_identifiers: NameList = []
        self.local_identifier = None

    @property
    def local_instance(self) -> SupvisorsInstanceId:
        """ Property getter for the SupvisorsInstanceId corresponding to local_identifier.

        :return: the local SupvisorsInstanceId
        """
        return self._instances[self.local_identifier]

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
        """ Property getter for the _core_identifiers attribute.

        :return: the minimum Supvisors identifiers to end the synchronization phase
        """
        return self._core_identifiers

    def add_instance(self, item: str, discovery: bool = True) -> SupvisorsInstanceId:
        """ Store a new Supvisors instance using a format compliant with the supvisors_list option.

        :param item: the Supvisors instance to add
        :param discovery: if True, instances are not statically declared in the configuration file and added on-the-fly
        :return: the new Supvisors instance
        """
        supvisors_id = SupvisorsInstanceId(item, self.supvisors)
        if supvisors_id.ip_address:
            if discovery:
                self.logger.info(f'SupvisorsMapper.add_instance: new SupvisorsInstanceId={supvisors_id}')
            self._instances[supvisors_id.identifier] = supvisors_id
            self._nodes.setdefault(supvisors_id.ip_address, []).append(supvisors_id.identifier)
            return supvisors_id
        message = f'could not define a Supvisors identification from "{item}"'
        raise ValueError(message)

    def configure(self, supvisors_list: NameList, core_list: NameList) -> None:
        """ Store the identification of the Supvisors instances declared in the configuration file and determine
        the local Supvisors instance in this list.

        :param supvisors_list: the Supvisors instances declared in the supvisors section of the configuration file
        :param core_list: the minimum Supvisors identifiers to end the synchronization phase
        :return: None
        """
        if supvisors_list:
            # get Supervisor identification from each element
            for item in supvisors_list:
                self.add_instance(item, False)
        else:
            # if supvisors_list is empty, use self identification from supervisor internal data
            # TODO: use FQDN ?
            supervisor = self.supvisors.supervisor_data
            item = f'<{supervisor.identifier}>{gethostname()}:{supervisor.server_port}:'
            self.logger.info(f'SupvisorsMapper.configure: define local Supvisors as {item}')
            self.add_instance(item, False)
        self.logger.info(f'SupvisorsMapper.configure: identifiers={list(self._instances.keys())}')
        self.logger.info(f'SupvisorsMapper.configure: nodes={self.nodes}')
        # get local Supervisor identification from list
        self.find_local_identifier()
        # check core identifiers
        self._core_identifiers = self.filter(core_list)
        self.logger.info(f'SupvisorsMapper.configure: core_identifiers={self._core_identifiers}')

    def find_local_identifier(self):
        """ Find the local Supvisors identification in the list declared in the configuration file.
        It can be either the local Supervisor identifier or a name built using the local host name or any of its known
        IP addresses.

        :return: the identifier of the local Supvisors
        """
        # get the must-match parameters
        local_host_name = getfqdn()
        local_host_name = getfqdn()
        local_http_port = self.supvisors.supervisor_data.server_port
        # search for local Supervisor identifier first
        if self.supvisors.supervisor_data.identifier in self._instances:
            self.local_identifier = self.supvisors.supervisor_data.identifier
            # check consistency
            sup_id = self._instances[self.local_identifier]
            if sup_id.host_name != local_host_name or sup_id.http_port != local_http_port:
                self.logger.warn(f'SupvisorsMapper.find_local_identifier: {sup_id.host_name} != {local_host_name}'
                                 f' or {sup_id.http_port} != {local_http_port}')
                message = f'candidate {self.local_identifier} does not match the local Supvisors'
                self.logger.error(f'SupvisorsMapper.find_local_identifier: {message}')
                raise ValueError(message)
        else:
            # if not found, try to find a Supvisors instance corresponding to the local host name
            # WARN: in this case, there MUST be exactly one unique matching Supvisors instance
            matching_identifiers = [sup_id.identifier
                                    for sup_id in self._instances.values()
                                    if sup_id.host_name == local_host_name and sup_id.http_port == local_http_port]
            if len(matching_identifiers) == 1:
                self.local_identifier = matching_identifiers[0]
            else:
                if len(matching_identifiers) > 1:
                    message = f'multiple candidates for the local Supvisors identifiers={matching_identifiers}'
                else:
                    message = 'could not find the local Supvisors in supvisors_list'
                self.logger.error(f'SupvisorsMapper.find_local_identifier: {message}')
                raise ValueError(message)
        self.logger.info(f'SupvisorsMapper.find_local_identifier: local_identifier={self.local_identifier}')

    def filter(self, identifier_list: NameList) -> NameList:
        """ Check the Supvisors identifiers against the list declared in the configuration file.
        If the identifier is not found, it is removed from the list.
        If more than one occurrence of the same identifier is found, only the first one is kept.

        :param identifier_list: a list of Supvisors identifiers
        :return: the filtered list of Supvisors identifiers
        """
        # filter unknown Supvisors identifiers
        identifiers = [identifier for identifier in identifier_list if identifier in self._instances]
        # log invalid identifiers to warn the user
        for identifier in identifier_list:
            if identifier != '#' and identifier not in identifiers:  # no warn for hashtag
                self.logger.warn(f'SupvisorsMapper.valid: identifier={identifier} invalid')
        # remove duplicates keeping the same ordering
        return list(OrderedDict.fromkeys(identifiers))
