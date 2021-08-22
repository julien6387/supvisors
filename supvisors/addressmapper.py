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

from collections import OrderedDict
from socket import gethostname, AF_INET
from supervisor.loggers import Logger

from .ttypes import NameList


class AddressMapper(object):
    """ Class used for storage of the addresses defined in the configuration file.
    These addresses are expected to be host names or IP addresses where a Supvisors instance is running.
    The instance holds:
        - logger: a reference to the common logger;
        - _node_names: the list of nodes defined in the Supvisors configuration file;
        - local_node_references: the list of known aliases of the current node, i.e. the host name
          and the IPv4 addresses;
        - local_node_name: the usage name of the current node, i.e. the name in the known aliases corresponding
          to a node of the Supvisors list. """

    def __init__(self, logger: Logger):
        """ Initialization of the attributes. """
        # keep reference of common logger
        self.logger = logger
        # init
        self._node_names = []
        self.local_node_references = [gethostname(), *self.ipv4()]
        self.local_node_name = None

    @property
    def node_names(self):
        """ Property getter for the _node_names attribute. """
        return self._node_names

    @node_names.setter
    def node_names(self, node_name_list: NameList) -> None:
        """ Store the nodes of the configuration file and determine the usage name of the local node among this list.

        :param node_name_list: the nodes defined in the supvisors section of the configuration file
        :return: None
        """
        self.logger.info('AddressMapper.node_names: expected nodes: {}'.format(node_name_list))
        # store IP list as found in config file
        self._node_names = node_name_list
        # get IP list for local node
        self.local_node_name = self.expected(self.local_node_references)
        self.logger.info('AddressMapper.node_names: local node references: {} - local node name: {}'
                         .format(self.local_node_references, self.local_node_name))

    def valid(self, node_name: str) -> bool:
        """ Return True if the node name is among the node list defined in the configuration file.

        :param node_name: the node name to check
        :return: True if the node name is found in the node names
        """
        return node_name in self._node_names

    def filter(self, node_name_list: NameList) -> NameList:
        """ Check the node names against the list defined in the configuration file.
        If the node name is not found, it is removed from the list.
        If more than one occurrence of the same node name is found, only the first one is kept.

        :param node_name_list: a list of node names
        :return: the filtered list of node names
        """
        # filter unknown addresses
        node_names = [node_name for node_name in node_name_list if self.valid(node_name)]
        # remove duplicates keeping the same ordering
        return list(OrderedDict.fromkeys(node_names))

    def expected(self, node_name_list: NameList) -> str:
        """ Return the usage name from a list of names or IP addresses identifying the same node.
        Usage name is defined as the name used in the configuration file.

        :param node_name_list: the list of possible names for the node
        :return: the usage name of the node
        """
        return next((node_name for node_name in node_name_list if self.valid(node_name)), None)

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
