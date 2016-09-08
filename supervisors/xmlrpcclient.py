#!/usr/bin/python
#-*- coding: utf-8 -*-

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

import xmlrpclib

from supervisor.xmlrpc import SupervisorTransport


class XmlRpcClient(object):

    def __init__(self, address, info_source):
        self.info_source = info_source
        self.transport = self.getRpcTransport(address)
        self.proxy = xmlrpclib.ServerProxy('http://{0}'.format(address), self.transport) if self.transport else None

    def getRpcTransport(self, address):
        if self.info_source.serverUrl:
            serverUrl = self.info_source.serverUrl.split(':')
            if len(serverUrl) == 3:
                serverUrl[1] = '//' + address
                serverUrl = ':'.join(serverUrl)
                return SupervisorTransport(self.info_source.userName, self.info_source.password, serverUrl)
