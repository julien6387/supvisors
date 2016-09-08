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


class RpcRequester(object):

    def __init__(self, supervisors):
        self.supervisors = supervisors

    # utilities to determine if using XmlRpcClient or internal handler directly
    def useProxy(self, address):
        return address != self.supervisors.address_mapper.local_address

    def getSupervisorProxy(self, address):
        # return client so as is it not destroyed when exiting
        client = XmlRpcClient(address, self.supervisors.infoSource)
        return client, client.proxy.supervisor

    def getSupervisorsProxy(self, address):
        # return client so as is it not destroyed when exiting
        client = XmlRpcClient(address, self.supervisors.infoSource)
        return client, client.proxy.supervisors

    def getInternalSupervisor(self):
        return None, self.supervisors.infoSource.getSupervisorRpcInterface()

    def getInternalSupervisors(self):
        return None, self.supervisors.infoSource.getSupervisorsRpcInterface()

    def getSupervisor(self, address):
        return self.getSupervisorProxy(address) if self.useProxy(address) else self.getInternalSupervisor()

    def getSupervisors(self, address):
        return self.getSupervisorsProxy(address) if self.useProxy(address) else self.getInternalSupervisors()

    # Requests
    def getAllProcessInfo(self, address):
        client, supervisor = self.getSupervisor(address)
        return supervisor.getAllProcessInfo()

    def getSupervisorsState(self, address):
        client, supervisors = self.getSupervisors(address)
        return supervisors.getSupervisorsState()

    def internalStartProcess(self, address, program, wait):
        client, supervisors = self.getSupervisors(address)
        return supervisors.internalStartProcess(program, wait)

    def getRemoteInfo(self, address, remoteAddress):
        client, supervisors = self.getSupervisors(address)
        return supervisors.getRemoteInfo(remoteAddress)

    def startProcess(self, address, program, wait):
        client, supervisor = self.getSupervisor(address)
        return supervisor.startProcess(program, wait)

    def stopProcess(self, address, program, wait):
        client, supervisor = self.getSupervisor(address)
        return supervisor.stopProcess(program, wait)

    def restart(self, address):
        client, supervisor = self.getSupervisor(address)
        return supervisor.restart()

    def shutdown(self, address):
        client, supervisor = self.getSupervisor(address)
        return supervisor.shutdown()
