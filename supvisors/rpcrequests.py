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

from typing import Mapping

from supervisor.compat import xmlrpclib
from supervisor.xmlrpc import SupervisorTransport


def getRPCInterface(node_name: str, env: Mapping[str, str]):
    """ The getRPCInterface creates a proxy to a supervisor XML-RPC server.
    Information about the HTTP configuration is required in env. """
    # get configuration info from env
    try:
        serverurl = env['SUPERVISOR_SERVER_URL']
    except KeyError:
        raise KeyError('SUPERVISOR_SERVER_URL must be set in environment')
    username = env.get('SUPERVISOR_USERNAME', '')
    password = env.get('SUPERVISOR_PASSWORD', '')
    # check that Supervisor is configured in HTTP
    if not serverurl.startswith('http://'):
        raise ValueError('Incompatible protocol for Supvisors: serverurl={}'.format(serverurl))
    # replace address in URL
    serverurl = serverurl.split(':')
    serverurl[1] = '//' + node_name
    serverurl = ':'.join(serverurl)
    # create transport and return proxy
    transport = SupervisorTransport(username, password, serverurl)
    return xmlrpclib.ServerProxy('http://{}'.format(node_name), transport)
