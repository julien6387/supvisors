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
from socket import gethostname, AF_INET
from supervisor.loggers import Logger
from typing import Any, Dict

from .ttypes import NameList


class SupvisorsInstanceId(object):
    """ Identification attributes for a Supvisors instance.
    The Supvisors instance uses the Supervisor identifier if provided, or builds an identifier from the host name and
    the HTTP port used by this Supervisor.

    Attributes are:
        - identifier: the Supervisor identifier or 'host_name[:http_port]' if not provided ;
        - host_name: the host where the Supervisor is running ;
        - http_port: the Supervisor port number ;
        - internal_port: the port number used to publish local events to remote Supvisors instances ;
        - event_port: the port number used to publish all Supvisors events.
    """

    PATTERN = re.compile(r'^(<(?P<identifier>[\w\-]+)>)?(?P<host>[\w\-.]+)(:(?P<http_port>\d{4,5})?'
                         r':(?P<internal_port>\d{4,5})?)?$')

    def __init__(self, item: str, supvisors: Any):
        """ Initialization of the attributes.

        :param item: the Supervisor parameters to be parsed
        """
        self.identifier = None
        self.host_name = None
        self.http_port = None
        self.internal_port = None
        self.event_port = None
        # parse item to get the values
        self.parse_from_string(item)
        self.check_values(supvisors)

    def check_values(self, supvisors: Any) -> None:
        """ Complete information where not provided.

        :return: None
        """
        # define identifier
        if not self.identifier and self.host_name:
            self.identifier = self.host_name
            # use HTTP port in identifier only if it has explicitly been defined
            if self.http_port:
                self.identifier += f':{self.http_port}'
        # if http_port is not provided, use the local http_port value
        if not self.http_port:
            self.http_port = supvisors.supervisor_data.serverport
        # if internal_port is not provided, use the option value if set or http_port+1
        if not self.internal_port:
            # assign to internal_port option value if set
            if supvisors.options.internal_port:
                self.internal_port = supvisors.options.internal_port
            else:
                # by default, assign to http_port + 1
                self.internal_port = self.http_port + 1
        # define event_port using option value if set
        if supvisors.options.event_port:
            self.event_port = supvisors.options.event_port
        else:
            # by default, assign to event_port + 1, unless this value is already taken by http_port
            if self.http_port != self.internal_port + 1:
                self.event_port = self.internal_port + 1
            else:
                # in this case, assign to http_port + 1
                self.event_port = self.http_port + 1

    def parse_from_string(self, item: str):
        """ Parse string according to PATTERN to get the Supvisors instance identification attributes.

        :param item: the parameters to be parsed
        :return: None
        """
        pattern_match = SupvisorsInstanceId.PATTERN.match(item)
        if pattern_match:
            self.identifier = pattern_match.group('identifier')
            self.host_name = pattern_match.group('host')
            # check http port
            port = pattern_match.group('http_port')
            self.http_port = int(port) if port else 0
            # check internal port
            port = pattern_match.group('internal_port')
            self.internal_port = int(port) if port else 0

    def __repr__(self) -> str:
        """ Initialization of the attributes.

        :return: the identifier as string representation of the SupvisorsInstanceId object
        """
        return self.identifier


class SupvisorsMapper(object):
    """ Class used for storage of the Supvisors instances declared in the configuration file.

    Attributes are:
        - supvisors: the global Supvisors structure ;
        - logger: the reference to the common logger ;
        - _instances: the list of Supvisors instances declared in the supvisors section of the Supervisor
          configuration file ;
        - _nodes: the list of Supvisors instances grouped by node names ;
        - _core_identifiers: the list of Supvisors core identifiers declared in the supvisors section of the Supervisor
          configuration file ;
        - local_node_references: the list of known aliases of the current node, i.e. the host name
          and the IPv4 addresses ;
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
        self.local_node_references = [gethostname(), *self.ipv4()]
        self.logger.debug(f'SupvisorsMapper: local_node_references={self.local_node_references}')
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
    def nodes(self) -> NameList:
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

    def configure(self, supvisors_list: NameList, core_list: NameList) -> None:
        """ Store the identification of the Supvisors instances declared in the configuration file and determine
        the local Supvisors instance in this list.

        :param supvisors_list: the Supvisors instances declared in the supvisors section of the configuration file
        :param core_list: the minimum Supvisors identifiers to end the synchronization phase
        :return: None
        """
        # get Supervisor identification from each element
        for item in supvisors_list:
            supvisors_id = SupvisorsInstanceId(item, self.supvisors)
            if supvisors_id.identifier:
                self.logger.debug(f'SupvisorsMapper.configure: new SupvisorsInstanceId={supvisors_id}')
                self._instances[supvisors_id.identifier] = supvisors_id
                self._nodes.setdefault(supvisors_id.host_name, []).append(supvisors_id.identifier)
            else:
                message = f'could not parse Supvisors identification from {item}'
                self.logger.error(f'SupvisorsMapper.instances: {message}')
                raise ValueError(message)
        self.logger.info(f'SupvisorsMapper.configure: identifiers={list(self._instances.keys())}')
        self.logger.debug(f'SupvisorsMapper.configure: nodes={self.nodes}')
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
        # search for local Supervisor identifier first
        if self.supvisors.supervisor_data.identifier in self._instances:
            self.local_identifier = self.supvisors.supervisor_data.identifier
        else:
            # if not found, try to find a Supvisors instance corresponding to local host name or known IP addresses
            # WARN: in this case, there MUST be exactly one unique matching Supvisors instance
            matching_identifiers = [supervisor_id.identifier
                                    for supervisor_id in self._instances.values()
                                    if supervisor_id.host_name in self.local_node_references]
            if len(matching_identifiers) == 1:
                self.local_identifier = matching_identifiers[0]
            else:
                if len(matching_identifiers) > 1:
                    message = f'multiple candidates for the local Supvisors: {matching_identifiers}'
                else:
                    message = 'could not find local the local Supvisors in supvisors_list'
                self.logger.error(f'SupvisorsMapper.find_local_identifier: {message}')
                raise ValueError(message)
        self.logger.info(f'SupvisorsMapper.find_local_identifier: local_identifier={self.local_identifier}')

    def valid(self, identifier: str) -> bool:
        """ Check if the identifier is among the Supvisors instances list defined in the configuration file.

        :param identifier: the Supvisors identifier to check
        :return: True if the Supvisors identifier is found in the configured Supvisors identifiers
        """
        return identifier in self._instances

    def filter(self, identifier_list: NameList) -> NameList:
        """ Check the Supvisors identifiers against the list declared in the configuration file.
        If the identifier is not found, it is removed from the list.
        If more than one occurrence of the same identifier is found, only the first one is kept.

        :param identifier_list: a list of Supvisors identifiers
        :return: the filtered list of Supvisors identifiers
        """
        # filter unknown Supvisors identifiers
        identifiers = [identifier for identifier in identifier_list if self.valid(identifier)]
        # log invalid identifiers to warn the user
        for identifier in identifier_list:
            if identifier != '#' and identifier not in identifiers:  # no warn for hashtag
                self.logger.warn(f'SupvisorsMapper.valid: identifier={identifier} invalid')
        # remove duplicates keeping the same ordering
        return list(OrderedDict.fromkeys(identifiers))

    @staticmethod
    def ipv4() -> NameList:
        """ Get all IPv4 addresses of the local node for all interfaces.
        Loopback address is excluded as useless from Supvisors perspective.

        :return: the IPv4 addresses of the local node
        """
        try:
            from psutil import net_if_addrs
            # loopback 'broadcast' address is not defined
            return [link.address
                    for config in net_if_addrs().values()
                    for link in config
                    if link.family == AF_INET and link.broadcast]
        except ImportError:
            return []
