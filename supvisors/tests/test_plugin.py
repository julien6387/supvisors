#!/usr/bin/python
#-*- coding: utf-8 -*-

# ======================================================================
# Copyright 2017 Julien LE CLEACH
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

from mock import call, patch
from supervisor.web import VIEWS, OKView, TailView
from supervisor.xmlrpc import Faults

from supvisors.tests.base import DummySupervisor


class PluginTest(unittest.TestCase):
    """ Test case for the plugin module. """

    def test_codes(self):
        """ Test the addition of Supvisors fault codes to Supervisor's. """
        from supvisors.plugin import SupvisorsFaults, expand_faults
        from supvisors.utils import enum_strings
        # update Supervisor faults
        expand_faults()
        # test that enumerations are in Supervisor
        for enum in enum_strings(SupvisorsFaults.__dict__):
            self.assertTrue(hasattr(Faults, enum))

    def test_update_views(self):
        """ Test the values set at construction. """
        from supvisors.plugin import update_views
        from supvisors.viewsupvisors import SupvisorsView
        from supvisors.viewapplication import ApplicationView
        from supvisors.viewhostaddress import HostAddressView
        from supvisors.viewprocaddress import ProcAddressView
        from supvisors.viewimage import (AddressMemoryImageView, ProcessMemoryImageView,
            AddressCpuImageView, ProcessCpuImageView, AddressNetworkImageView)
        # update Supervisor views
        update_views()
        # check Supvisors views
        view = VIEWS['index.html']
        self.assertRegexpMatches(view['template'], 'supvisors/ui/index.html$')
        self.assertEqual(view['view'], SupvisorsView)
        view = VIEWS['ok.html']
        self.assertEqual(None, view['template'])
        self.assertEqual(view['view'], OKView)
        view = VIEWS['tail.html']
        self.assertEqual('ui/tail.html', view['template'])
        self.assertEqual(view['view'], TailView)
        view = VIEWS['application.html']
        self.assertRegexpMatches(view['template'], 'supvisors/ui/application.html$')
        self.assertEqual(view['view'], ApplicationView)
        view = VIEWS['hostaddress.html']
        self.assertRegexpMatches(view['template'], 'supvisors/ui/hostaddress.html$')
        self.assertEqual(view['view'], HostAddressView)
        view = VIEWS['procaddress.html']
        self.assertRegexpMatches(view['template'], 'supvisors/ui/procaddress.html$')
        self.assertEqual(view['view'], ProcAddressView)
        view = VIEWS['address_mem.png']
        self.assertRegexpMatches(view['template'], 'supvisors/ui/empty.html$')
        self.assertEqual(view['view'], AddressMemoryImageView)
        view = VIEWS['process_mem.png']
        self.assertRegexpMatches(view['template'], 'supvisors/ui/empty.html$')
        self.assertEqual(view['view'], ProcessMemoryImageView)
        view = VIEWS['address_cpu.png']
        self.assertRegexpMatches(view['template'], 'supvisors/ui/empty.html$')
        self.assertEqual(view['view'], AddressCpuImageView)
        view = VIEWS['process_cpu.png']
        self.assertRegexpMatches(view['template'], 'supvisors/ui/empty.html$')
        self.assertEqual(view['view'], ProcessCpuImageView)
        view = VIEWS['address_io.png']
        self.assertRegexpMatches(view['template'], 'supvisors/ui/empty.html$')
        self.assertEqual(view['view'], AddressNetworkImageView)

    @patch('supvisors.plugin.update_views')
    @patch('supvisors.plugin.expand_faults')
    @patch('supvisors.plugin.RPCInterface')
    def test_make_rpc(self, mocked_rpc, mocked_expand, mocked_views):
        """ Test the values set at construction. """
        from supvisors.plugin import make_supvisors_rpcinterface
        supervisord = DummySupervisor
        make_supvisors_rpcinterface(supervisord)
        self.assertEqual([call(supervisord)], mocked_rpc.call_args_list)
        self.assertEqual([call()], mocked_expand.call_args_list)
        self.assertEqual([call()], mocked_views.call_args_list)


def test_suite():
    return unittest.findTestCases(sys.modules[__name__])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
