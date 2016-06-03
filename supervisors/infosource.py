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

# Abstract class with getters to implement
class ASource(object):
    def getServerUrl(self): raise NotImplementedError('To be implemented in subclass')
    def getServerPort(self): raise NotImplementedError('To be implemented in subclass')
    def getUserName(self): raise NotImplementedError('To be implemented in subclass')
    def getPassword(self): raise NotImplementedError('To be implemented in subclass')


# Supervisors is started in Supervisor so information is available in supervisor instance
class SupervisordSource(ASource):
    def __init__(self, supervisord):
        self._supervisord = supervisord
        if len(supervisord.options.server_configs) == 0:
            raise Exception('no server configuration in config file: {}'.format(supervisord.configfile))
        self._serverConfig = supervisord.options.server_configs[0]
        # server MUST be http, not unix
        serverSection = self._serverConfig['section'] 
        if serverSection != 'inet_http_server':
            raise Exception('inet_http_server expected in config file: {}'.format(supervisord.configfile))
        # shortcuts (not available yet)
        self._systemRpcInterface = None
        self._supervisorRpcInterface = None
        self._supervisorsRpcInterface = None

    @property
    def supervisord(self): return self._supervisord
    @property
    def daemon(self): return not self.supervisord.options.nodaemon
    @property
    def systemRpcInterface(self):
        if not self._systemRpcInterface:
            self._systemRpcInterface = self.supervisord.options.httpservers[0][1].handlers[0].rpcinterface.system
        return self._systemRpcInterface
    @property
    def supervisorRpcInterface(self):
        # need to get internal Supervisor RPC handler to call behaviour from Supervisors
        # XML-RPC call in an other XML-RPC call on the same server is blocking
        # so, not proud of the following line but could not access it any other way
        if not self._supervisorRpcInterface:
            self._supervisorRpcInterface = self.supervisord.options.httpservers[0][1].handlers[0].rpcinterface.supervisor
        return self._supervisorRpcInterface
    @property
    def supervisorsRpcInterface(self):
        if not self._supervisorsRpcInterface:
            self._supervisorsRpcInterface = self.supervisord.options.httpservers[0][1].handlers[0].rpcinterface.supervisors
        return self._supervisorsRpcInterface

    def getServerUrl(self): return self.supervisord.options.serverurl
    def getServerPort(self): return self._serverConfig['port']
    def getUserName(self): return self._serverConfig['username']
    def getPassword(self): return self._serverConfig['password']


class _InfoSource(object):
    def __init__(self):
        self._source = None
 
    @property
    def source(self): return self._source
    @source.setter
    def source(self, value):
        if not issubclass(type(value), ASource):
            raise TypeError('wrong type for source: should inherit from {}'.format(ASource.__name__))
        self._source = value


infoSource = _InfoSource()
