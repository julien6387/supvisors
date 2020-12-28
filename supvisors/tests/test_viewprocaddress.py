#!/usr/bin/python
# -*- coding: utf-8 -*-

# ======================================================================
# Copyright 2020 Julien LE CLEACH
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

from supervisor.web import MeldView, StatusView
from supervisor.xmlrpc import RPCError

from unittest.mock import call, patch, Mock

from supvisors.tests.base import ProcessInfoDatabase


class ViewProcAddressTest(unittest.TestCase):
    """ Test case for the viewprocaddress module. """

    def setUp(self):
        """ Create a logger that stores log traces. """
        # apply the forced inheritance done in supvisors.plugin
        from supvisors.tests.base import DummyHttpContext
        from supvisors.viewhandler import ViewHandler
        from supervisor.web import StatusView
        StatusView.__bases__ = (ViewHandler,)
        # create the instance to be tested
        from supvisors.viewprocaddress import ProcAddressView
        self.view = ProcAddressView(DummyHttpContext('ui/procaddress.html'))

    def test_init(self):
        """ Test the values set at construction. """
        # test instance inheritance
        from supvisors.viewhandler import ViewHandler
        from supvisors.viewsupstatus import SupvisorsAddressView
        from supvisors.webutils import PROC_ADDRESS_PAGE
        for klass in [SupvisorsAddressView, StatusView, ViewHandler, MeldView]:
            self.assertIsInstance(self.view, klass)
        # test default page name
        self.assertEqual(PROC_ADDRESS_PAGE, self.view.page_name)

    @patch('supvisors.viewhandler.ViewHandler.write_process_statistics')
    @patch('supvisors.viewprocaddress.ProcAddressView.write_process_table')
    @patch('supvisors.viewprocaddress.ProcAddressView.get_process_data',
           side_effect=([{'namespec': 'dummy'}], [{'namespec': 'dummy'}],
                        [{'namespec': 'dummy_proc'}], [{'namespec': 'dummy_proc'}]))
    def test_write_contents(self, mocked_data, mocked_table, mocked_stats):
        """ Test the write_contents method. """
        from supvisors.viewcontext import PROCESS
        # patch context
        self.view.view_ctx = Mock(parameters={PROCESS: None}, local_address='10.0.0.1',
                                  **{'get_process_status.return_value': None})
        # patch the meld elements
        mocked_root = Mock()
        # test call with no process selected
        self.view.write_contents(mocked_root)
        self.assertEqual([call()], mocked_data.call_args_list)
        self.assertEqual([call(mocked_root, [{'namespec': 'dummy'}])], mocked_table.call_args_list)
        self.assertEqual([call(mocked_root, {})], mocked_stats.call_args_list)
        mocked_data.reset_mock()
        mocked_table.reset_mock()
        mocked_stats.reset_mock()
        # test call with process selected and no corresponding status
        self.view.view_ctx.parameters[PROCESS] = 'dummy_proc'
        self.view.write_contents(mocked_root)
        self.assertEqual([call()], mocked_data.call_args_list)
        self.assertEqual([call(mocked_root, [{'namespec': 'dummy'}])], mocked_table.call_args_list)
        self.assertEqual('', self.view.view_ctx.parameters[PROCESS])
        self.assertEqual([call(mocked_root, {})], mocked_stats.call_args_list)
        mocked_data.reset_mock()
        mocked_table.reset_mock()
        mocked_stats.reset_mock()
        # test call with process selected but not running on considered address
        self.view.view_ctx.parameters[PROCESS] = 'dummy_proc'
        self.view.view_ctx.get_process_status.return_value = Mock(addresses={'10.0.0.2'})
        self.view.write_contents(mocked_root)
        self.assertEqual([call()], mocked_data.call_args_list)
        self.assertEqual([call(mocked_root, [{'namespec': 'dummy_proc'}])], mocked_table.call_args_list)
        self.assertEqual('', self.view.view_ctx.parameters[PROCESS])
        self.assertEqual([call(mocked_root, {})], mocked_stats.call_args_list)
        mocked_data.reset_mock()
        mocked_table.reset_mock()
        mocked_stats.reset_mock()
        # test call with process selected and running
        self.view.view_ctx.parameters[PROCESS] = 'dummy_proc'
        self.view.view_ctx.get_process_status.return_value = Mock(addresses={'10.0.0.1'})
        self.view.write_contents(mocked_root)
        self.assertEqual([call()], mocked_data.call_args_list)
        self.assertEqual([call(mocked_root, [{'namespec': 'dummy_proc'}])], mocked_table.call_args_list)
        self.assertEqual('dummy_proc', self.view.view_ctx.parameters[PROCESS])
        self.assertEqual([call(mocked_root, {'namespec': 'dummy_proc'})], mocked_stats.call_args_list)

    @patch('supvisors.viewhandler.ViewHandler.sort_processes_by_config',
           return_value=['process_2', 'process_1'])
    def test_get_process_data(self, mocked_sort):
        """ Test the get_process_data method. """
        # patch context
        process_status = Mock(rules=Mock(expected_loading=17))
        self.view.view_ctx = Mock(local_address='10.0.0.1',
                                  **{'get_process_status.side_effect': [None, process_status],
                                     'get_process_stats.side_effect': [(2, 'stats #1'), (8, 'stats #2')]})
        # test RPC Error
        with patch.object(self.view.info_source.supervisor_rpc_interface, 'getAllProcessInfo',
                          side_effect=RPCError('failed RPC')):
            self.assertEqual([], self.view.get_process_data())

        # test using base process info
        def process_info_by_name(name):
            return next((info.copy() for info in ProcessInfoDatabase
                         if info['name'] == name), {})

        with patch.object(self.view.info_source.supervisor_rpc_interface, 'getAllProcessInfo',
                          return_value=[process_info_by_name('xfontsel'),
                                        process_info_by_name('segv')]):
            self.assertEqual(['process_2', 'process_1'], self.view.get_process_data())
            # test intermediate list
            data1 = {'application_name': 'sample_test_1',
                     'process_name': 'xfontsel',
                     'namespec': 'sample_test_1:xfontsel',
                     'address': '10.0.0.1',
                     'statename': 'RUNNING',
                     'statecode': 20,
                     'description': 'pid 80879, uptime 0:01:19',
                     'loading': '?',
                     'nb_cores': 2,
                     'proc_stats': 'stats #1'}
            data2 = {'application_name': 'crash',
                     'process_name': 'segv',
                     'namespec': 'crash:segv',
                     'address': '10.0.0.1',
                     'statename': 'BACKOFF',
                     'statecode': 30,
                     'description': 'Exited too quickly (process log may have details)',
                     'loading': 17,
                     'nb_cores': 8,
                     'proc_stats': 'stats #2'}
            self.assertEqual(1, mocked_sort.call_count)
            self.assertEqual(2, len(mocked_sort.call_args_list[0]))
            # access to internal call data
            call_data = mocked_sort.call_args_list[0][0][0]
            self.assertDictEqual(data1, call_data[0])
            self.assertDictEqual(data2, call_data[1])

    @patch('supvisors.viewprocaddress.ProcAddressView.write_process')
    @patch('supvisors.viewhandler.ViewHandler.write_common_process_status',
           side_effect=[True, False, False])
    def test_write_process_table(self, mocked_common, mocked_process):
        """ Test the write_process_table method. """
        # patch the meld elements
        table_mid = Mock()
        tr_elt_1 = Mock(attrib={'class': ''})
        tr_elt_2 = Mock(attrib={'class': ''})
        tr_elt_3 = Mock(attrib={'class': ''})
        tr_mid = Mock(**{'repeat.return_value': [(tr_elt_1, 'info_1'),
                                                 (tr_elt_2, 'info_2'),
                                                 (tr_elt_3, 'info_3')]})
        mocked_root = Mock(**{'findmeld.side_effect': [table_mid, tr_mid]})
        # test call with no data
        self.view.write_process_table(mocked_root, {})
        self.assertEqual([call('No programs to manage')], table_mid.replace.call_args_list)
        self.assertEqual([], mocked_common.replace.call_args_list)
        self.assertEqual([], mocked_process.replace.call_args_list)
        self.assertEqual('', tr_elt_1.attrib['class'])
        self.assertEqual('', tr_elt_2.attrib['class'])
        self.assertEqual('', tr_elt_3.attrib['class'])
        table_mid.replace.reset_mock()
        # test call with data and line selected
        self.view.write_process_table(mocked_root, True)
        self.assertEqual([], table_mid.replace.call_args_list)
        self.assertEqual([call(tr_elt_1, 'info_1'), call(tr_elt_2, 'info_2'), call(tr_elt_3, 'info_3')],
                         mocked_common.call_args_list)
        self.assertEqual([call(tr_elt_1, 'info_1'), call(tr_elt_2, 'info_2'), call(tr_elt_3, 'info_3')],
                         mocked_process.call_args_list)
        self.assertEqual('brightened', tr_elt_1.attrib['class'])
        self.assertEqual('shaded', tr_elt_2.attrib['class'])
        self.assertEqual('brightened', tr_elt_3.attrib['class'])

    def test_write_process(self):
        """ Test the write_process method. """
        from supvisors.webutils import PROC_ADDRESS_PAGE, TAIL_PAGE
        # create a process-like dict
        info = {'namespec': 'dummy_appli:dummy_proc'}
        # patch the view context
        self.view.view_ctx = Mock(**{'format_url.return_value': 'an url'})
        # patch the meld elements
        name_mid = Mock()
        tr_elt = Mock(**{'findmeld.return_value': name_mid})
        # test call with stopped process
        self.view.write_process(tr_elt, info)
        self.assertEqual([call('name_a_mid')], tr_elt.findmeld.call_args_list)
        self.assertEqual([call('dummy_appli:dummy_proc')], name_mid.content.call_args_list)
        self.assertEqual([call(href='an url')], name_mid.attributes.call_args_list)
        self.assertEqual([call('127.0.0.1', TAIL_PAGE, processname=info['namespec'])],
                         self.view.view_ctx.format_url.call_args_list)


def test_suite():
    return unittest.findTestCases(sys.modules[__name__])


if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
