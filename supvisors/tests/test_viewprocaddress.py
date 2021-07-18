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

from random import shuffle

from supervisor.states import ProcessStates
from supervisor.web import MeldView, StatusView
from supervisor.xmlrpc import RPCError

from unittest.mock import call, patch, Mock

from supvisors.ttypes import ApplicationStates

from .base import ProcessInfoDatabase


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
        from supvisors.webutils import PROC_NODE_PAGE
        for klass in [SupvisorsAddressView, StatusView, ViewHandler, MeldView]:
            self.assertIsInstance(self.view, klass)
        # test default page name
        self.assertEqual(PROC_NODE_PAGE, self.view.page_name)

    @patch('supvisors.viewhandler.ViewHandler.write_process_statistics')
    @patch('supvisors.viewprocaddress.ProcAddressView.write_process_table')
    @patch('supvisors.viewprocaddress.ProcAddressView.get_process_data',
           side_effect=([{'namespec': 'dummy'}], [{'namespec': 'dummy'}],
                        [{'namespec': 'dummy_proc'}], [{'namespec': 'dummy_proc'}]))
    def test_write_contents(self, mocked_data, mocked_table, mocked_stats):
        """ Test the write_contents method. """
        from supvisors.viewcontext import PROCESS
        # patch context
        self.view.view_ctx = Mock(parameters={PROCESS: None}, local_node_name='10.0.0.1',
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
        self.view.view_ctx.get_process_status.return_value = Mock(running_nodes={'10.0.0.2'})
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
        self.view.view_ctx.get_process_status.return_value = Mock(running_nodes={'10.0.0.1'})
        self.view.write_contents(mocked_root)
        self.assertEqual([call()], mocked_data.call_args_list)
        self.assertEqual([call(mocked_root, [{'namespec': 'dummy_proc'}])], mocked_table.call_args_list)
        self.assertEqual('dummy_proc', self.view.view_ctx.parameters[PROCESS])
        self.assertEqual([call(mocked_root, {'namespec': 'dummy_proc'})], mocked_stats.call_args_list)

    def test_get_process_data(self):
        """ Test the get_process_data method. """
        # patch context
        process_status = Mock(rules=Mock(expected_load=17))
        self.view.sup_ctx.get_process.side_effect = [None, process_status]
        self.view.view_ctx = Mock(local_node_name='10.0.0.1',
                                  **{'get_process_stats.side_effect': [(2, 'stats #1'), (8, 'stats #2')]})
        # test RPC Error
        with patch.object(self.view.supvisors.info_source.supervisor_rpc_interface, 'getAllProcessInfo',
                          side_effect=RPCError('failed RPC')):
            self.assertEqual([], self.view.get_process_data())

        # test using base process info
        def process_info_by_name(name):
            return next((info.copy() for info in ProcessInfoDatabase if info['name'] == name), {})

        with patch.object(self.view, 'sort_data', return_value=['process_2', 'process_1']) as mocked_sort:
            with patch.object(self.view.supvisors.info_source.supervisor_rpc_interface, 'getAllProcessInfo',
                              return_value=[process_info_by_name('xfontsel'), process_info_by_name('segv')]):
                self.assertEqual(['process_2', 'process_1'], self.view.get_process_data())
        # test intermediate list
        data1 = {'application_name': 'sample_test_1', 'process_name': 'xfontsel',
                 'namespec': 'sample_test_1:xfontsel', 'node_name': '10.0.0.1',
                 'statename': 'RUNNING', 'statecode': 20,
                 'description': 'pid 80879, uptime 0:01:19',
                 'expected_load': '?', 'nb_cores': 2, 'proc_stats': 'stats #1'}
        data2 = {'application_name': 'crash', 'process_name': 'segv',
                 'namespec': 'crash:segv', 'node_name': '10.0.0.1',
                 'statename': 'BACKOFF', 'statecode': 30,
                 'description': 'Exited too quickly (process log may have details)',
                 'expected_load': 17, 'nb_cores': 8, 'proc_stats': 'stats #2'}
        self.assertEqual(1, mocked_sort.call_count)
        self.assertEqual(2, len(mocked_sort.call_args_list[0]))
        # access to internal call data
        call_data = mocked_sort.call_args_list[0][0][0]
        self.assertDictEqual(data1, call_data[0])
        self.assertDictEqual(data2, call_data[1])

    @patch('supvisors.viewprocaddress.ProcAddressView.get_application_summary',
           side_effect=[{'application_name': 'crash', 'process_name': None},
                        {'application_name': 'firefox', 'process_name': None},
                        {'application_name': 'sample_test_1', 'process_name': None},
                        {'application_name': 'sample_test_2', 'process_name': None}] * 2)
    def test_sort_data(self, mocked_summary):
        """ Test the ProcAddressView.sort_data method. """
        # test empty parameter
        assert self.view.sort_data([]) == []
        # build process list
        processes = [{'application_name': info['group'], 'process_name': info['name']}
                     for info in ProcessInfoDatabase]
        shuffle(processes)
        # patch context
        self.view.view_ctx = Mock(**{'get_application_shex.side_effect': [(True, 0), (True, 0), (True, 0), (True, 0),
                                                                          (True, 0), (True, 0), (False, 0), (False, 0)]})
        # test ordering
        actual = self.view.sort_data(processes)
        assert actual == [{'application_name': 'crash', 'process_name': None},
                          {'application_name': 'crash', 'process_name': 'late_segv'},
                          {'application_name': 'crash', 'process_name': 'segv'},
                          {'application_name': 'firefox', 'process_name': None},
                          {'application_name': 'firefox', 'process_name': 'firefox'},
                          {'application_name': 'sample_test_1', 'process_name': None},
                          {'application_name': 'sample_test_1', 'process_name': 'xclock'},
                          {'application_name': 'sample_test_1', 'process_name': 'xfontsel'},
                          {'application_name': 'sample_test_1', 'process_name': 'xlogo'},
                          {'application_name': 'sample_test_2', 'process_name': None},
                          {'application_name': 'sample_test_2', 'process_name': 'sleep'},
                          {'application_name': 'sample_test_2', 'process_name': 'yeux_00'},
                          {'application_name': 'sample_test_2', 'process_name': 'yeux_01'}]
        # test with some shex on applications
        actual = self.view.sort_data(processes)
        assert actual == [{'application_name': 'crash', 'process_name': None},
                          {'application_name': 'crash', 'process_name': 'late_segv'},
                          {'application_name': 'crash', 'process_name': 'segv'},
                          {'application_name': 'firefox', 'process_name': None},
                          {'application_name': 'firefox', 'process_name': 'firefox'},
                          {'application_name': 'sample_test_1', 'process_name': None},
                          {'application_name': 'sample_test_2', 'process_name': None}]

    def test_get_application_summary(self):
        """ Test the ProcAddressView.get_application_summary method. """
        # patch the context
        self.view.view_ctx = Mock(local_node_name='10.0.0.1')
        self.view.sup_ctx.applications['dummy_appli'] = Mock(state=ApplicationStates.RUNNING,
                                                             **{'get_operational_status.return_value': 'good'})
        # prepare parameters
        proc_1 = {'statecode': ProcessStates.RUNNING, 'expected_load': 5, 'nb_cores': 8, 'proc_stats': [[10], [5]]}
        proc_2 = {'statecode': ProcessStates.STARTING, 'expected_load': 15, 'nb_cores': 8, 'proc_stats': [[], []]}
        proc_3 = {'statecode': ProcessStates.BACKOFF, 'expected_load': 7, 'nb_cores': 8, 'proc_stats': [[8], [22]]}
        proc_4 = {'statecode': ProcessStates.FATAL, 'expected_load': 25, 'nb_cores': 8, 'proc_stats': None}
        # test with empty list of processes
        expected = {'application_name': 'dummy_appli', 'process_name': None, 'namespec': None,
                    'node_name': '10.0.0.1', 'statename': 'RUNNING', 'statecode': 2,
                    'description': 'good', 'nb_processes': 0,
                    'expected_load': 0, 'nb_cores': 0, 'proc_stats': None}
        assert self.view.get_application_summary('dummy_appli', []) == expected
        # test with non-running processes
        expected.update({'nb_processes': 1})
        assert self.view.get_application_summary('dummy_appli', [proc_4]) == expected
        # test with a mix of running and non-running processes
        expected.update({'nb_processes': 4, 'expected_load': 27, 'nb_cores': 8, 'proc_stats': [[18], [27]]})
        assert self.view.get_application_summary('dummy_appli', [proc_1, proc_2, proc_3, proc_4]) == expected

    @patch('supvisors.viewprocaddress.ProcAddressView.write_application_status')
    @patch('supvisors.viewhandler.ViewHandler.write_common_process_status')
    def test_write_process_table(self, mocked_common, mocked_appli):
        """ Test the ProcAddressView.write_process_table method. """
        # patch the meld elements
        table_mid = Mock()
        tr_elt_1 = Mock(attrib={'class': ''}, **{'findmeld.return_value': Mock()})
        tr_elt_2 = Mock(attrib={'class': ''}, **{'findmeld.return_value': Mock()})
        tr_elt_3 = Mock(attrib={'class': ''}, **{'findmeld.return_value': Mock()})
        tr_elt_4 = Mock(attrib={'class': ''}, **{'findmeld.return_value': Mock()})
        tr_elt_5 = Mock(attrib={'class': ''}, **{'findmeld.return_value': Mock()})
        tr_mid = Mock(**{'repeat.return_value': [(tr_elt_1, {'process_name': None}),
                                                 (tr_elt_2, {'process_name': 'info_2'}),
                                                 (tr_elt_3, {'process_name': 'info_3'}),
                                                 (tr_elt_4, {'process_name': None}),
                                                 (tr_elt_5, {'process_name': 'info_5'})]})
        mocked_root = Mock(**{'findmeld.side_effect': [table_mid, tr_mid]})
        # test call with no data
        self.view.write_process_table(mocked_root, {})
        self.assertEqual([call('No programs to manage')], table_mid.replace.call_args_list)
        self.assertFalse(mocked_common.called)
        self.assertFalse(mocked_appli.called)
        self.assertFalse(tr_elt_1.findmeld.return_value.replace.called)
        self.assertFalse(tr_elt_2.findmeld.return_value.replace.called)
        self.assertFalse(tr_elt_3.findmeld.return_value.replace.called)
        self.assertFalse(tr_elt_4.findmeld.return_value.replace.called)
        self.assertFalse(tr_elt_5.findmeld.return_value.replace.called)
        self.assertEqual('', tr_elt_1.attrib['class'])
        self.assertEqual('', tr_elt_2.attrib['class'])
        self.assertEqual('', tr_elt_3.attrib['class'])
        self.assertEqual('', tr_elt_4.attrib['class'])
        self.assertEqual('', tr_elt_5.attrib['class'])
        table_mid.replace.reset_mock()
        # test call with data and line selected
        self.view.write_process_table(mocked_root, [{}])
        self.assertFalse(table_mid.replace.called)
        self.assertEqual([call(tr_elt_2, {'process_name': 'info_2'}), call(tr_elt_3, {'process_name': 'info_3'}),
                          call(tr_elt_5, {'process_name': 'info_5'})],
                         mocked_common.call_args_list)
        self.assertEqual([call(tr_elt_1, {'process_name': None}, False),
                          call(tr_elt_4, {'process_name': None}, True)],
                         mocked_appli.call_args_list)
        self.assertFalse(tr_elt_1.findmeld.return_value.replace.called)
        self.assertEqual([call('')], tr_elt_2.findmeld.return_value.replace.call_args_list)
        self.assertEqual([call('')], tr_elt_3.findmeld.return_value.replace.call_args_list)
        self.assertFalse(tr_elt_4.findmeld.return_value.replace.called)
        self.assertEqual([call('')], tr_elt_5.findmeld.return_value.replace.call_args_list)
        self.assertEqual('brightened', tr_elt_1.attrib['class'])
        self.assertEqual('shaded', tr_elt_2.attrib['class'])
        self.assertEqual('brightened', tr_elt_3.attrib['class'])
        self.assertEqual('shaded', tr_elt_4.attrib['class'])
        self.assertEqual('brightened', tr_elt_5.attrib['class'])

    @patch('supvisors.viewhandler.ViewHandler.write_common_status')
    def test_write_application_status(self, mocked_common):
        """ Test the ProcAddressView.write_application_status method. """
        # patch the context
        self.view.view_ctx = Mock(**{'get_application_shex.side_effect': [(False, '010'), (True, '101')],
                                     'format_url.return_value': 'an url'})
        # patch the meld elements
        shex_a_mid = Mock(attrib={})
        shex_td_mid = Mock(attrib={}, **{'findmeld.return_value': shex_a_mid})
        name_a_mid = Mock(attrib={})
        start_td_mid = Mock(attrib={})
        stop_td_mid = Mock(attrib={})
        restart_td_mid = Mock(attrib={})
        clear_td_mid = Mock(attrib={})
        tailout_td_mid = Mock(attrib={})
        tailerr_td_mid = Mock(attrib={})
        mid_list = [shex_td_mid, name_a_mid, start_td_mid, clear_td_mid,
                    stop_td_mid, restart_td_mid, tailout_td_mid, tailerr_td_mid]
        mocked_root = Mock(**{'findmeld.side_effect': mid_list * 2})
        # prepare parameters
        info = {'application_name': 'dummy_appli', 'nb_processes': 4}
        # test call with application processes hidden
        self.view.write_application_status(mocked_root, info, True)
        self.assertEqual([call(mocked_root, info)], mocked_common.call_args_list)
        assert 'rowspan' not in shex_td_mid.attrib
        assert 'class' not in shex_td_mid.attrib
        assert shex_a_mid.content.call_args_list == [call('[+]')]
        assert shex_a_mid.attributes.call_args_list == [call(href='an url')]
        assert self.view.view_ctx.format_url.call_args_list == [call('', 'procaddress.html', shex='010'),
                                                                call('', 'application.html', appliname='dummy_appli')]
        assert name_a_mid.content.call_args_list == [call('dummy_appli')]
        assert name_a_mid.attributes.call_args_list == [call(href='an url')]
        for mid in [start_td_mid, clear_td_mid]:
            assert mid.attrib['colspan'] == '3'
            assert mid.content.call_args_list == [call('')]
        for mid in [stop_td_mid, restart_td_mid, tailout_td_mid, tailerr_td_mid]:
            assert mid.replace.call_args_list == [call('')]
        # reset context
        mocked_common.reset_mock()
        shex_a_mid.content.reset_mock()
        shex_a_mid.attributes.reset_mock()
        for mid in mid_list:
            mid.content.reset_mock()
            mid.attributes.reset_mock()
            mid.replace.reset_mock()
            mid.attrib = {}
        self.view.view_ctx.format_url.reset_mock()
        # test call with application processes displayed
        self.view.write_application_status(mocked_root, info, False)
        self.assertEqual([call(mocked_root, info)], mocked_common.call_args_list)
        assert shex_td_mid.attrib['rowspan'] == '5'
        assert shex_td_mid.attrib['class'] == 'brightened'
        assert shex_a_mid.content.call_args_list == [call('[\u2013]')]
        assert shex_a_mid.attributes.call_args_list == [call(href='an url')]
        assert self.view.view_ctx.format_url.call_args_list == [call('', 'procaddress.html', shex='101'),
                                                                call('', 'application.html', appliname='dummy_appli')]
        assert name_a_mid.content.call_args_list == [call('dummy_appli')]
        assert name_a_mid.attributes.call_args_list == [call(href='an url')]
        for mid in [start_td_mid, clear_td_mid]:
            assert mid.attrib['colspan'] == '3'
            assert mid.content.call_args_list == [call('')]
        for mid in [stop_td_mid, restart_td_mid, tailout_td_mid, tailerr_td_mid]:
            assert mid.replace.call_args_list == [call('')]


def test_suite():
    return unittest.findTestCases(sys.modules[__name__])


if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
