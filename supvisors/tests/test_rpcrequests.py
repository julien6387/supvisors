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

import sys
import unittest

from supervisor.compat import xmlrpclib


class RpcRequestsTest(unittest.TestCase):
    """ Test case for the rpcrequests module. """

    def test_getRPCInterface(self):
        """ Test the values set at construction. """
        from supvisors.rpcrequests import getRPCInterface
        address = '10.0.0.1'
        # test with empty environment
        env = {}
        with self.assertRaises(KeyError):
            getRPCInterface(address, env)
        # test with incorrect environment
        env = {'SUPERVISOR_SERVER_URL': 'unix://localhost:1000'}
        with self.assertRaises(ValueError):
            getRPCInterface(address, env)
        # test with simple environment
        env = {'SUPERVISOR_SERVER_URL': 'http://localhost:1000'}
        proxy = getRPCInterface(address, env)
        self.assertIsInstance(proxy, xmlrpclib.ServerProxy)
        self.assertEqual('/RPC2', proxy._ServerProxy__handler)
        self.assertEqual('10.0.0.1', proxy._ServerProxy__host)
        self.assertEqual('http://10.0.0.1:1000', proxy._ServerProxy__transport.serverurl)
        self.assertEqual('', proxy._ServerProxy__transport.username)
        self.assertEqual('', proxy._ServerProxy__transport.password)
        # test with authentification environment
        env = {'SUPERVISOR_SERVER_URL': 'http://192.168.1.1:1000', 'SUPERVISOR_USERNAME': 'cliche',
               'SUPERVISOR_PASSWORD': 'p@$$w0rd'}
        proxy = getRPCInterface(address, env)
        self.assertIsInstance(proxy, xmlrpclib.ServerProxy)
        self.assertEqual('/RPC2', proxy._ServerProxy__handler)
        self.assertEqual('10.0.0.1', proxy._ServerProxy__host)
        self.assertEqual('http://10.0.0.1:1000', proxy._ServerProxy__transport.serverurl)
        self.assertEqual('cliche', proxy._ServerProxy__transport.username)
        self.assertEqual('p@$$w0rd', proxy._ServerProxy__transport.password)
        # if no server is started, call would block


def test_suite():
    return unittest.findTestCases(sys.modules[__name__])


if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
