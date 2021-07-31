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

import pytest

from supervisor.compat import xmlrpclib
from supvisors.rpcrequests import getRPCInterface


def test_getRPCInterface():
    """ Test the values set at construction. """
    address = '10.0.0.1'
    # test with empty environment
    env = {}
    with pytest.raises(KeyError):
        getRPCInterface(address, env)
    # test with incorrect environment
    env = {'SUPERVISOR_SERVER_URL': 'unix://localhost:1000'}
    with pytest.raises(ValueError):
        getRPCInterface(address, env)
    # test with simple environment
    env = {'SUPERVISOR_SERVER_URL': 'http://localhost:1000'}
    proxy = getRPCInterface(address, env)
    assert isinstance(proxy, xmlrpclib.ServerProxy)
    assert proxy._ServerProxy__handler == '/RPC2'
    assert proxy._ServerProxy__host == '10.0.0.1'
    assert proxy._ServerProxy__transport.serverurl == 'http://10.0.0.1:1000'
    assert proxy._ServerProxy__transport.username == ''
    assert proxy._ServerProxy__transport.password == ''
    # test with authentication environment
    env = {'SUPERVISOR_SERVER_URL': 'http://192.168.1.1:1000', 'SUPERVISOR_USERNAME': 'cliche',
           'SUPERVISOR_PASSWORD': 'p@$$w0rd'}
    proxy = getRPCInterface(address, env)
    assert isinstance(proxy, xmlrpclib.ServerProxy)
    assert proxy._ServerProxy__handler == '/RPC2'
    assert proxy._ServerProxy__host == '10.0.0.1'
    assert proxy._ServerProxy__transport.serverurl == 'http://10.0.0.1:1000'
    assert proxy._ServerProxy__transport.username == 'cliche'
    assert proxy._ServerProxy__transport.password == 'p@$$w0rd'
    # if no server is started, call would block
