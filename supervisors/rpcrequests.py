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
        if info_source.serverurl:
            serverurl = info_source.serverurl.split(':')
            if len(serverurl) == 3:
                serverurl[1] = '//' + address
                serverurl = ':'.join(serverurl)
                self.transport = SupervisorTransport(info_source.username, info_source.password, serverurl)
        self.proxy = xmlrpclib.ServerProxy('http://{0}'.format(address), self.transport)


class RpcRequester(object):

    def __init__(self, supervisors):
        self.supervisors = supervisors

    # utilities to determine if using XmlRpcClient or internal handler directly
    def use_proxy(self, address):
        """ Return True if RPC address is NOT the local address. """
        return address != self.supervisors.address_mapper.local_address

    def supervisor_proxy(self, address):
        # return client so as is it not destroyed when exiting
        client = XmlRpcClient(address, self.supervisors.info_source)
        return client, client.proxy.supervisor

    def supervisors_proxy(self, address):
        # return client so as is it not destroyed when exiting
        client = XmlRpcClient(address, self.supervisors.info_source)
        return client, client.proxy.supervisors

    def internal_supervisor(self):
        return None, self.supervisors.info_source.supervisor_rpc_interface

    def internal_supervisors(self):
        return None, self.supervisors.info_source.supervisors_rpc_interface

    def get_supervisor(self, address):
        return self.supervisor_proxy(address) if self.use_proxy(address) else self.internal_supervisor()

    def get_supervisors(self, address):
        return self.supervisors_proxy(address) if self.use_proxy(address) else self.internal_supervisors()

    # Requests
    def all_process_info(self, address):
        client, supervisor = self.get_supervisor(address)
        return supervisor.getAllProcessInfo()

    def supervisors_state(self, address):
        client, supervisors = self.get_supervisors(address)
        return supervisors.get_supervisors_state()

    def internal_start_process(self, address, program, extra_args):
        client, supervisors = self.get_supervisors(address)
        return supervisors.internal_start_process(program, extra_args)

    def address_info(self, address, remote_address):
        client, supervisors = self.get_supervisors(address)
        return supervisors.get_address_info(remote_address)

    def start_process(self, address, program, wait):
        client, supervisor = self.get_supervisor(address)
        return supervisor.startProcess(program, wait)

    def stop_process(self, address, program, wait):
        client, supervisor = self.get_supervisor(address)
        return supervisor.stopProcess(program, wait)

    def restart(self, address):
        client, supervisor = self.get_supervisor(address)
        return supervisor.restart()

    def shutdown(self, address):
        client, supervisor = self.get_supervisor(address)
        return supervisor.shutdown()
