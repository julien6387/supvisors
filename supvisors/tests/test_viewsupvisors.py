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

from supervisor.web import MeldView
from unittest.mock import call, patch, Mock

from supvisors.tests.base import CompatTestCase

class ViewSupvisorsTest(CompatTestCase):
    """ Test case for the viewsupvisors module. """

    def setUp(self):
        """ Create the instance to be tested. """
        from supvisors.tests.base import DummyHttpContext
        from supvisors.viewsupvisors import SupvisorsView
        self.view = SupvisorsView(DummyHttpContext('ui/hostaddress.html'))

    def test_init(self):
        """ Test the values set at construction. """
        # test instance inheritance
        from supvisors.viewhandler import ViewHandler
        for klass in [ViewHandler, MeldView]:
            self.assertIsInstance(self.view, klass)
        # test parameter page name
        from supvisors.webutils import SUPVISORS_PAGE
        self.assertEqual(SUPVISORS_PAGE, self.view.page_name)
        # test strategy names
        from supvisors.ttypes import ConciliationStrategies
        for strategy in self.view.strategies:
            self.assertIn(strategy.upper(), ConciliationStrategies.strings())
        self.assertNotIn('user', self.view.strategies)
        # test action methods storage
        self.assertTrue(all(callable(cb)) for cb in self.view.global_methods.values())
        self.assertTrue(all(callable(cb)) for cb in self.view.process_methods.values())

    @patch('supvisors.viewsupvisors.SupvisorsView.write_nav')
    def test_write_navigation(self, mocked_nav):
        """ Test the write_navigation method. """
        mocked_root = Mock()
        self.view.write_navigation(mocked_root)
        self.assertEqual([call(mocked_root)], mocked_nav.call_args_list)

    def test_write_header(self):
        """ Test the write_header method. """
        # patch context
        self.view.fsm.state_string.return_value = 'Running'
        # build root structure
        mocked_state_mid = Mock()
        mocked_root = Mock(**{'findmeld.return_value': mocked_state_mid})
        # test call with no auto-refresh
        self.view.write_header(mocked_root)
        self.assertEqual([call('Running')], mocked_state_mid.content.call_args_list)

    @patch('supvisors.viewsupvisors.SupvisorsView.write_node_boxes')
    @patch('supvisors.viewsupvisors.SupvisorsView.write_conciliation_table')
    @patch('supvisors.viewsupvisors.SupvisorsView.write_conciliation_strategies')
    def test_write_contents(self, mocked_strategies, mocked_conflicts, mocked_boxes):
        """ Test the write_contents method. """
        from supvisors.ttypes import SupvisorsStates
        # patch context
        self.view.fsm.state = SupvisorsStates.OPERATION
        self.view.sup_ctx.conflicts.return_value = True
        # build root structure
        mocked_box_mid = Mock()
        mocked_conflict_mid = Mock()
        mocked_root = Mock(**{'findmeld.side_effect': [mocked_conflict_mid, mocked_box_mid]})
        # test call in normal state (no conciliation)
        self.view.write_contents(mocked_root)
        self.assertEqual([call(mocked_root)], mocked_boxes.call_args_list)
        self.assertFalse(mocked_strategies.called)
        self.assertFalse(mocked_conflicts.called)
        self.assertEqual([call('')], mocked_conflict_mid.replace.call_args_list)
        self.assertFalse(mocked_box_mid.replace.called)
        # reset mocks
        mocked_boxes.reset_mock()
        mocked_conflict_mid.replace.reset_mock()
        # test call in conciliation state
        self.view.fsm.state = SupvisorsStates.CONCILIATION
        self.view.write_contents(mocked_root)
        self.assertEqual([call(mocked_root)], mocked_strategies.call_args_list)
        self.assertEqual([call(mocked_root)], mocked_conflicts.call_args_list)
        self.assertFalse(mocked_boxes.called)
        self.assertEqual([call('')], mocked_box_mid.replace.call_args_list)
        self.assertFalse(mocked_conflict_mid.replace.called)

    def test_write_node_box_title(self):
        """ Test the _write_node_box_title method. """
        from supvisors.ttypes import AddressStates
        # patch context
        mocked_status = Mock(address_name='10.0.0.1', state=AddressStates.RUNNING,
                             **{'state_string.return_value': 'running',
                                'loading.return_value': 17})
        self.view.view_ctx = Mock(**{'format_url.return_value': 'an url'})
        # build root structure with one single element
        mocked_node_mid = Mock(attrib={})
        mocked_state_mid = Mock(attrib={})
        mocked_percent_mid = Mock(attrib={})
        mocked_root = Mock(**{'findmeld.side_effect': [mocked_node_mid, mocked_state_mid,
                                                       mocked_percent_mid] * 2})
        # test call in RUNNING state
        self.view._write_node_box_title(mocked_root, mocked_status)
        # test address element
        self.assertEqual('on', mocked_node_mid.attrib['class'])
        self.assertEqual([call(href='an url')], mocked_node_mid.attributes.call_args_list)
        self.assertEqual([call('10.0.0.1')], mocked_node_mid.content.call_args_list)
        # test state element
        self.assertEqual('running state', mocked_state_mid.attrib['class'])
        self.assertEqual([call('running')], mocked_state_mid.content.call_args_list)
        # test loading element
        self.assertEqual([call('17%')], mocked_percent_mid.content.call_args_list)
        # reset mocks and attributes
        mocked_node_mid.reset_mock()
        mocked_state_mid.reset_mock()
        mocked_percent_mid.reset_mock()
        mocked_node_mid.attrib['class'] = ''
        mocked_state_mid.attrib['class'] = ''
        # test call in SILENT state
        mocked_status = Mock(address_name='10.0.0.1', state=AddressStates.SILENT,
                             **{'state_string.return_value': 'silent',
                                'loading.return_value': 0})
        self.view._write_node_box_title(mocked_root, mocked_status)
        # test address element
        self.assertEqual('', mocked_node_mid.attrib['class'])
        self.assertFalse(mocked_node_mid.attributes.called)
        self.assertEqual([call('10.0.0.1')], mocked_node_mid.content.call_args_list)
        # test state element
        self.assertEqual('silent state', mocked_state_mid.attrib['class'])
        self.assertEqual([call('silent')], mocked_state_mid.content.call_args_list)
        # test loading element
        self.assertEqual([call('0%')], mocked_percent_mid.content.call_args_list)

    def test_write_node_box_processes(self):
        """ Test the _write_node_box_processes method. """
        # 1. patch context for no running process on node
        mocked_status = Mock(**{'running_processes.return_value': {}})
        # build root structure with one single element
        mocked_process_li_mid = Mock()
        mocked_appli_tr_mid = Mock(**{'findmeld.return_value': mocked_process_li_mid,
                                      'repeat.return_value': None})
        mocked_root = Mock(**{'findmeld.return_value': mocked_appli_tr_mid})
        # test call with no running process
        self.view._write_node_box_processes(mocked_root, mocked_status)
        # test elements
        self.assertFalse(mocked_appli_tr_mid.repeat.called)
        self.assertEqual([call('')], mocked_process_li_mid.replace.call_args_list)
        # 2. patch context for multiple running process on node
        mocked_process_1 = Mock(application_name='dummy_appli', process_name='dummy_proc')
        mocked_process_2 = Mock(application_name='other_appli', process_name='other_proc')
        mocked_status = Mock(**{'running_processes.return_value': [mocked_process_1, mocked_process_2]})
        # build root structure
        mocked_name_mids = [Mock(), Mock()]
        mocked_process_a_mids = [Mock(), Mock()]
        mocked_process_li_mid = Mock(**{'findmeld.side_effect': mocked_process_a_mids})
        mocked_process_template = Mock(**{'repeat.side_effect': [[(mocked_process_li_mid, mocked_process_1)],
                                                                 [(mocked_process_li_mid, mocked_process_2)]]})
        mocked_appli_tr_mids = [Mock(attrib={},
                                     **{'findmeld.side_effect': [mocked_name_mids[0], mocked_process_template]}),
                                Mock(attrib={},
                                     **{'findmeld.side_effect': [mocked_name_mids[1], mocked_process_template]})]
        mocked_appli_template = Mock(**{'findmeld.return_value': None,
                                        'repeat.return_value': [(mocked_appli_tr_mids[0], 'dummy_appli'),
                                                                (mocked_appli_tr_mids[1], 'other_appli')]})
        mocked_root = Mock(**{'findmeld.return_value': mocked_appli_template})
        # test call with 2 running processes
        self.view._write_node_box_processes(mocked_root, mocked_status)
        # test elements
        self.assertFalse(mocked_appli_template.findmeld.called)
        # test shade in mocked_appli_tr_mids
        self.assertEqual('brightened', mocked_appli_tr_mids[0].attrib['class'])
        self.assertEqual('shaded', mocked_appli_tr_mids[1].attrib['class'])
        # test application names in mocked_name_mids
        self.assertEqual([call('dummy_appli')], mocked_name_mids[0].content.call_args_list)
        self.assertEqual([call('other_appli')], mocked_name_mids[1].content.call_args_list)
        # test process elements in mocked_process_a_mids
        self.assertEqual([call('dummy_proc')], mocked_process_a_mids[0].content.call_args_list)
        self.assertEqual([call('other_proc')], mocked_process_a_mids[1].content.call_args_list)

    @patch('supvisors.viewsupvisors.SupvisorsView._write_node_box_processes')
    @patch('supvisors.viewsupvisors.SupvisorsView._write_node_box_title')
    def test_write_node_boxes(self, mocked_box_title, mocked_box_processes):
        """ Test the write_node_boxes method. """
        # patch context
        mocked_node_1 = Mock(address_name='10.0.0.1')
        mocked_node_2 = Mock(address_name='10.0.0.2')
        self.view.sup_ctx.addresses = {'10.0.0.1': mocked_node_1, '10.0.0.2': mocked_node_2}
        self.view.view_ctx = Mock(**{'format_url.return_value': 'an url'})
        # build root structure with one single element
        mocked_box_mid_1 = Mock()
        mocked_box_mid_2 = Mock()
        mocked_address_template = Mock(**{'repeat.return_value': [(mocked_box_mid_1, '10.0.0.1'),
                                                                  (mocked_box_mid_2, '10.0.0.2')]})
        mocked_root = Mock(**{'findmeld.return_value': mocked_address_template})
        # test call
        self.view.write_node_boxes(mocked_root)
        self.assertEqual([call(mocked_box_mid_1, mocked_node_1), call(mocked_box_mid_2, mocked_node_2)],
                         mocked_box_title.call_args_list)
        self.assertEqual([call(mocked_box_mid_1, mocked_node_1), call(mocked_box_mid_2, mocked_node_2)],
                         mocked_box_processes.call_args_list)

    def test_write_conciliation_strategies(self):
        """ Test the write_conciliation_strategies method. """
        # patch context
        self.view.sup_ctx.master_address = {'10.0.0.1'}
        self.view.view_ctx = Mock(**{'format_url.return_value': 'an url'})
        # build root structure with one single element
        mocked_strategy_mid = Mock()
        mocked_strategy_li = Mock(**{'findmeld.return_value': mocked_strategy_mid})
        mocked_strategy_template = Mock(**{'repeat.return_value': [(mocked_strategy_li, 'infanticide')]})
        mocked_conflicts_mid = Mock(**{'findmeld.return_value': mocked_strategy_template})
        mocked_root = Mock(**{'findmeld.return_value': mocked_conflicts_mid})
        # test call
        self.view.write_conciliation_strategies(mocked_root)
        self.assertEqual([call(href='an url')], mocked_strategy_mid.attributes.call_args_list)
        self.assertEqual([call('Infanticide')], mocked_strategy_mid.content.call_args_list)

    @patch('supvisors.viewsupvisors.SupvisorsView._write_conflict_strategies')
    @patch('supvisors.viewsupvisors.SupvisorsView._write_conflict_process_actions')
    @patch('supvisors.viewsupvisors.SupvisorsView._write_conflict_uptime')
    @patch('supvisors.viewsupvisors.SupvisorsView._write_conflict_address')
    @patch('supvisors.viewsupvisors.SupvisorsView._write_conflict_name')
    @patch('supvisors.viewsupvisors.SupvisorsView.get_conciliation_data')
    def test_write_conciliation_table(self, mocked_data, *args):
        """ Test the write_conciliation_table method. """
        # sample data
        data = [{'namespec': 'proc_1', 'rowspan': 2}, {'namespec': 'proc_1', 'rowspan': 0},
                {'namespec': 'proc_2', 'rowspan': 2}, {'namespec': 'proc_2', 'rowspan': 0}]
        # build simple root structure
        mocked_tr_elt = [Mock(attrib={}) for _ in range(4)]
        mocked_tr_mid = Mock(**{'repeat.return_value': zip(mocked_tr_elt, data)})
        mocked_div_elt = Mock(**{'findmeld.return_value': mocked_tr_mid})
        mocked_root = Mock(**{'findmeld.return_value': mocked_div_elt})
        # test call
        self.view.write_conciliation_table(mocked_root)
        self.assertEqual([call()], mocked_data.call_args_list)
        # check elements background
        self.assertEqual('brightened', mocked_tr_elt[0].attrib['class'])
        self.assertEqual('brightened', mocked_tr_elt[1].attrib['class'])
        self.assertEqual('shaded', mocked_tr_elt[2].attrib['class'])
        self.assertEqual('shaded', mocked_tr_elt[3].attrib['class'])
        self.assertEqual([call(mocked_tr_elt[0], data[0], False), call(mocked_tr_elt[1], data[1], False),
                          call(mocked_tr_elt[2], data[2], True), call(mocked_tr_elt[3], data[3], True)],
                         args[0].call_args_list)
        self.assertEqual([call(mocked_tr_elt[0], data[0]), call(mocked_tr_elt[1], data[1]),
                          call(mocked_tr_elt[2], data[2]), call(mocked_tr_elt[3], data[3])],
                         args[1].call_args_list)
        self.assertEqual([call(mocked_tr_elt[0], data[0]), call(mocked_tr_elt[1], data[1]),
                          call(mocked_tr_elt[2], data[2]), call(mocked_tr_elt[3], data[3])],
                         args[2].call_args_list)
        self.assertEqual([call(mocked_tr_elt[0], data[0]), call(mocked_tr_elt[1], data[1]),
                          call(mocked_tr_elt[2], data[2]), call(mocked_tr_elt[3], data[3])],
                         args[3].call_args_list)
        self.assertEqual([call(mocked_tr_elt[0], data[0], False), call(mocked_tr_elt[1], data[1], False),
                          call(mocked_tr_elt[2], data[2], True), call(mocked_tr_elt[3], data[3], True)],
                         args[4].call_args_list)

    def test_write_conflict_name(self):
        """ Test the _write_conflict_name method. """
        # build root structure with one single element
        mocked_name_mid = Mock(attrib={})
        mocked_root = Mock(**{'findmeld.return_value': mocked_name_mid})
        # test call with different values of rowspan and shade
        # first line, shaded
        info = {'namespec': 'dummy_proc', 'rowspan': 2}
        self.view._write_conflict_name(mocked_root, info, True)
        self.assertEqual([call('name_td_mid')], mocked_root.findmeld.call_args_list)
        self.assertEqual('2', mocked_name_mid.attrib['rowspan'])
        self.assertEqual('shaded', mocked_name_mid.attrib['class'])
        self.assertEqual([call('dummy_proc')], mocked_name_mid.content.call_args_list)
        # reset mocks
        mocked_root.findmeld.reset_mock()
        mocked_name_mid.content.reset_mock()
        mocked_name_mid.attrib = {}
        # first line, non shaded
        self.view._write_conflict_name(mocked_root, info, False)
        self.assertEqual([call('name_td_mid')], mocked_root.findmeld.call_args_list)
        self.assertEqual('2', mocked_name_mid.attrib['rowspan'])
        self.assertEqual('brightened', mocked_name_mid.attrib['class'])
        self.assertEqual([call('dummy_proc')], mocked_name_mid.content.call_args_list)
        self.assertFalse(mocked_name_mid.replace.called)
        # reset mocks
        mocked_root.findmeld.reset_mock()
        mocked_name_mid.content.reset_mock()
        mocked_name_mid.attrib = {}
        # not first line, shaded
        info['rowspan'] = 0
        self.view._write_conflict_name(mocked_root, info, True)
        self.assertEqual([call('name_td_mid')], mocked_root.findmeld.call_args_list)
        self.assertNotIn('rowspan', mocked_name_mid.attrib)
        self.assertNotIn('class', mocked_name_mid.attrib)
        self.assertFalse(mocked_name_mid.content.called)
        self.assertEqual([call('')], mocked_name_mid.replace.call_args_list)
        # reset mocks
        mocked_root.findmeld.reset_mock()
        mocked_name_mid.replace.reset_mock()
        # not first line, non shaded
        self.view._write_conflict_name(mocked_root, info, False)
        self.assertEqual([call('name_td_mid')], mocked_root.findmeld.call_args_list)
        self.assertNotIn('rowspan', mocked_name_mid.attrib)
        self.assertNotIn('class', mocked_name_mid.attrib)
        self.assertFalse(mocked_name_mid.content.called)
        self.assertEqual([call('')], mocked_name_mid.replace.call_args_list)

    def test_write_conflict_address(self):
        """ Test the _write_conflict_address method. """
        from supvisors.webutils import PROC_ADDRESS_PAGE
        # patch context
        self.view.view_ctx = Mock(**{'format_url.return_value': 'an url'})
        # build root structure with one single element
        mocked_addr_mid = Mock()
        mocked_root = Mock(**{'findmeld.return_value': mocked_addr_mid})
        # test call
        self.view._write_conflict_address(mocked_root, {'address': '10.0.0.1'})
        self.assertEqual([call('caddress_a_mid')], mocked_root.findmeld.call_args_list)
        self.assertEqual([call(href='an url')], mocked_addr_mid.attributes.call_args_list)
        self.assertEqual([call('10.0.0.1')], mocked_addr_mid.content.call_args_list)
        self.assertEqual([call('10.0.0.1', PROC_ADDRESS_PAGE)], self.view.view_ctx.format_url.call_args_list)

    def test_write_conflict_uptime(self):
        """ Test the _write_conflict_uptime method. """
        # patch context
        self.view.view_ctx = Mock(**{'format_url.return_value': 'an url'})
        # build root structure with one single element
        mocked_uptime_mid = Mock()
        mocked_root = Mock(**{'findmeld.return_value': mocked_uptime_mid})
        # test call
        self.view._write_conflict_uptime(mocked_root, {'uptime': 1234})
        self.assertEqual([call('uptime_td_mid')], mocked_root.findmeld.call_args_list)
        self.assertEqual([call('00:20:34')], mocked_uptime_mid.content.call_args_list)

    def test_write_conflict_process_actions(self):
        """ Test the _write_conflict_process_actions method. """
        from supvisors.webutils import SUPVISORS_PAGE
        # patch context
        self.view.view_ctx = Mock(**{'format_url.return_value': 'an url'})
        # build root structure with one single element
        mocked_stop_mid = Mock()
        mocked_keep_mid = Mock()
        mocked_root = Mock(**{'findmeld.side_effect': [mocked_stop_mid, mocked_keep_mid]})
        # test call
        info = {'namespec': 'dummy_proc', 'address': '10.0.0.1'}
        self.view._write_conflict_process_actions(mocked_root, info)
        self.assertEqual([call('pstop_a_mid'), call('pkeep_a_mid')], mocked_root.findmeld.call_args_list)
        self.assertEqual([call(href='an url')], mocked_stop_mid.attributes.call_args_list)
        self.assertEqual([call(href='an url')], mocked_keep_mid.attributes.call_args_list)
        self.assertEqual([call('', SUPVISORS_PAGE, action='pstop', address='10.0.0.1', namespec='dummy_proc'),
                          call('', SUPVISORS_PAGE, action='pkeep', address='10.0.0.1', namespec='dummy_proc')],
                         self.view.view_ctx.format_url.call_args_list)

    def test_write_conflict_strategies(self):
        """ Test the _write_conflict_strategies method. """
        from supvisors.webutils import SUPVISORS_PAGE
        # patch context
        self.view.sup_ctx.master_address = '10.0.0.1'
        self.view.view_ctx = Mock(**{'format_url.return_value': 'an url'})
        # build root structure with one single element
        mocked_a_mid = Mock()
        mocked_li_mid = Mock(**{'findmeld.return_value': mocked_a_mid})
        mocked_li_template = Mock(**{'repeat.return_value': [(mocked_li_mid, 'senicide')]})
        mocked_td_mid = Mock(attrib={}, **{'findmeld.return_value': mocked_li_template})
        mocked_root = Mock(**{'findmeld.return_value': mocked_td_mid})
        # test call with different values of rowspan and shade
        # first line, shaded
        info = {'namespec': 'dummy_proc', 'rowspan': 2}
        self.view._write_conflict_strategies(mocked_root, info, True)
        self.assertEqual('2', mocked_td_mid.attrib['rowspan'])
        self.assertEqual('shaded', mocked_td_mid.attrib['class'])
        self.assertEqual([call(href='an url')], mocked_a_mid.attributes.call_args_list)
        self.assertEqual([call('Senicide')], mocked_a_mid.content.call_args_list)
        self.assertEqual([call('10.0.0.1', SUPVISORS_PAGE, action='senicide', namespec='dummy_proc')],
                         self.view.view_ctx.format_url.call_args_list)
        # reset mocks
        self.view.view_ctx.format_url.reset_mock()
        mocked_a_mid.attributes.reset_mock()
        mocked_a_mid.content.reset_mock()
        mocked_td_mid.attrib = {}
        # first line, not shaded
        info = {'namespec': 'dummy_proc', 'rowspan': 2}
        self.view._write_conflict_strategies(mocked_root, info, False)
        self.assertEqual('2', mocked_td_mid.attrib['rowspan'])
        self.assertEqual('brightened', mocked_td_mid.attrib['class'])
        self.assertEqual([call(href='an url')], mocked_a_mid.attributes.call_args_list)
        self.assertEqual([call('Senicide')], mocked_a_mid.content.call_args_list)
        self.assertEqual([call('10.0.0.1', SUPVISORS_PAGE, action='senicide', namespec='dummy_proc')],
                         self.view.view_ctx.format_url.call_args_list)
        # reset mocks
        self.view.view_ctx.format_url.reset_mock()
        mocked_a_mid.attributes.reset_mock()
        mocked_a_mid.content.reset_mock()
        mocked_td_mid.attrib = {}
        # not first line, shaded
        info = {'namespec': 'dummy_proc', 'rowspan': 0}
        self.view._write_conflict_strategies(mocked_root, info, True)
        self.assertNotIn('rowspan', mocked_td_mid.attrib)
        self.assertFalse(mocked_a_mid.attributes.called)
        self.assertFalse(mocked_a_mid.content.called)
        self.assertFalse(mocked_a_mid.content.called)
        self.assertFalse(self.view.view_ctx.format_url.called)
        self.assertEqual([call('')], mocked_td_mid.replace.call_args_list)
        # reset mocks
        mocked_td_mid.replace.reset_mock()
        # not first line, not shaded
        info = {'namespec': 'dummy_proc', 'rowspan': 0}
        self.view._write_conflict_strategies(mocked_root, info, False)
        self.assertNotIn('rowspan', mocked_td_mid.attrib)
        self.assertFalse(mocked_a_mid.attributes.called)
        self.assertFalse(mocked_a_mid.content.called)
        self.assertFalse(mocked_a_mid.content.called)
        self.assertFalse(self.view.view_ctx.format_url.called)
        self.assertEqual([call('')], mocked_td_mid.replace.call_args_list)

    def test_get_conciliation_data(self):
        """ Test the get_conciliation_data method. """
        # patch context
        process_1 = Mock(addresses={'10.0.0.1', '10.0.0.2'},
                         infos={'10.0.0.1': {'uptime': 12}, '10.0.0.2': {'uptime': 11}},
                         **{'namespec.return_value': 'proc_1'})
        process_2 = Mock(addresses={'10.0.0.3', '10.0.0.2'},
                         infos={'10.0.0.3': {'uptime': 10}, '10.0.0.2': {'uptime': 11}},
                         **{'namespec.return_value': 'proc_2'})
        self.view.sup_ctx.conflicts.return_value = [process_1, process_2]
        # test call
        # no direct method in unittests to compare 2 lists of dicts so put all tuples in flat list
        # and use CompatTestCase.assertItemsEqual to compare
        expected = [{'namespec': 'proc_1', 'rowspan': 2, 'address': '10.0.0.1', 'uptime': 12},
                    {'namespec': 'proc_1', 'rowspan': 0, 'address': '10.0.0.2', 'uptime': 11},
                    {'namespec': 'proc_2', 'rowspan': 2, 'address': '10.0.0.3', 'uptime': 10},
                    {'namespec': 'proc_2', 'rowspan': 0, 'address': '10.0.0.2', 'uptime': 11}]
        flat_expected = [item for dico in expected for item in dico.items()]
        actual = self.view.get_conciliation_data()
        flat_actual = [item for dico in actual for item in dico.items()]
        self.assertItemsEqual(flat_expected, flat_actual)

    @patch('supvisors.viewsupvisors.delayed_info', return_value='delayed info')
    def test_refresh_action(self, mocked_info):
        """ Test the refresh_action method. """
        self.assertEqual('delayed info', self.view.refresh_action())
        self.assertEqual([call('Page refreshed')], mocked_info.call_args_list)

    @patch('supvisors.viewsupvisors.info_message', return_value='info')
    @patch('supvisors.viewsupvisors.error_message', return_value='error')
    @patch('supvisors.viewsupvisors.delayed_info', return_value='delayed info')
    @patch('supvisors.viewsupvisors.delayed_error', return_value='delayed error')
    def test_sup_restart_action(self, *args):
        """ Test the sup_shutdown_action method. """
        self._check_sup_action(self.view.sup_restart_action, 'restart', *args)

    @patch('supvisors.viewsupvisors.info_message', return_value='info')
    @patch('supvisors.viewsupvisors.error_message', return_value='error')
    @patch('supvisors.viewsupvisors.delayed_info', return_value='delayed info')
    @patch('supvisors.viewsupvisors.delayed_error', return_value='delayed error')
    def test_sup_shutdown_action(self, *args):
        """ Test the sup_shutdown_action method. """
        self._check_sup_action(self.view.sup_shutdown_action, 'shutdown', *args)

    def _check_sup_action(self, method_cb, rpc_name, mocked_derror, mocked_dinfo, mocked_error, mocked_info):
        """ Test the sup_restart_action & sup_shutdown_action methods. """
        from supervisor.http import NOT_DONE_YET
        from supervisor.xmlrpc import RPCError
        # test RPC error
        with patch.object(self.view.info_source.supvisors_rpc_interface, rpc_name,
                          side_effect=RPCError('failed RPC')) as mocked_rpc:
            self.assertEqual('delayed error', method_cb())
        self.assertTrue(mocked_derror.called)
        self.assertFalse(mocked_dinfo.called)
        self.assertFalse(mocked_error.called)
        self.assertFalse(mocked_info.called)
        # reset mocks
        mocked_derror.reset_mock()
        # test direct result
        with patch.object(self.view.info_source.supvisors_rpc_interface, rpc_name,
                          return_value='not callable object') as mocked_rpc:
            self.assertEqual('delayed info', method_cb())
        self.assertFalse(mocked_derror.called)
        self.assertTrue(mocked_dinfo.called)
        self.assertFalse(mocked_error.called)
        self.assertFalse(mocked_info.called)
        # reset mocks
        mocked_dinfo.reset_mock()
        # test delayed result with RPC error
        mocked_onwait = Mock(side_effect=RPCError('failed RPC'))
        with patch.object(self.view.info_source.supvisors_rpc_interface, rpc_name,
                          return_value=mocked_onwait) as mocked_rpc:
            cb = method_cb()
        self.assertTrue(callable(cb))
        self.assertEqual('error', cb())
        self.assertFalse(mocked_derror.called)
        self.assertFalse(mocked_dinfo.called)
        self.assertTrue(mocked_error.called)
        self.assertFalse(mocked_info.called)
        # reset mocks
        mocked_error.reset_mock()
        # test delayed / uncompleted result
        mocked_onwait = Mock(return_value=NOT_DONE_YET)
        with patch.object(self.view.info_source.supvisors_rpc_interface, rpc_name,
                          return_value=mocked_onwait) as mocked_rpc:
            cb = method_cb()
        self.assertTrue(callable(cb))
        self.assertIs(NOT_DONE_YET, cb())
        self.assertFalse(mocked_derror.called)
        self.assertFalse(mocked_dinfo.called)
        self.assertFalse(mocked_error.called)
        self.assertFalse(mocked_info.called)
        # test delayed / completed result
        mocked_onwait = Mock(return_value='done')
        with patch.object(self.view.info_source.supvisors_rpc_interface, 'shutdown',
                          return_value=mocked_onwait) as mocked_rpc:
            cb = method_cb()
        self.assertTrue(callable(cb))
        self.assertIs('info', cb())
        self.assertFalse(mocked_derror.called)
        self.assertFalse(mocked_dinfo.called)
        self.assertFalse(mocked_error.called)
        self.assertTrue(mocked_info.called)

    @patch('supvisors.viewsupvisors.info_message', return_value='done')
    def test_stop_action(self, mocked_info):
        """ Test the stop_action method. """
        from supervisor.http import NOT_DONE_YET
        # patch context
        self.view.sup_ctx.processes['dummy_proc'] = Mock(addresses=['10.0.0.1', '10.0.0.2', '10.0.0.3'])
        # test call
        with patch.object(self.view.supvisors.zmq.pusher, 'send_stop_process') as mocked_rpc:
            cb = self.view.stop_action('dummy_proc', '10.0.0.2')
        self.assertTrue(callable(cb))
        self.assertEqual([call('10.0.0.2', 'dummy_proc')], mocked_rpc.call_args_list)
        # at this stage, there should be still 3 elements in addresses
        self.assertIs(NOT_DONE_YET, cb())
        self.assertFalse(mocked_info.called)
        # remove one address from list
        self.view.sup_ctx.processes['dummy_proc'].addresses.remove('10.0.0.2')
        self.assertEqual('done', cb())
        self.assertEqual([call('process dummy_proc stopped on 10.0.0.2')], mocked_info.call_args_list)

    @patch('supvisors.viewsupvisors.info_message', return_value='done')
    def test_keep_action(self, mocked_info):
        """ Test the keep_action method. """
        from supervisor.http import NOT_DONE_YET
        # patch context
        self.view.sup_ctx.processes['dummy_proc'] = Mock(addresses=['10.0.0.1', '10.0.0.2', '10.0.0.3'])
        # test call
        with patch.object(self.view.supvisors.zmq.pusher, 'send_stop_process') as mocked_rpc:
            cb = self.view.keep_action('dummy_proc', '10.0.0.2')
        self.assertTrue(callable(cb))
        self.assertEqual([call('10.0.0.1', 'dummy_proc'), call('10.0.0.3', 'dummy_proc')],
                         mocked_rpc.call_args_list)
        # at this stage, there should be still 3 elements in addresses
        self.assertIs(NOT_DONE_YET, cb())
        self.assertFalse(mocked_info.called)
        # remove one address from list
        self.view.sup_ctx.processes['dummy_proc'].addresses.remove('10.0.0.1')
        self.assertIs(NOT_DONE_YET, cb())
        self.assertFalse(mocked_info.called)
        # remove one address from list
        self.view.sup_ctx.processes['dummy_proc'].addresses.remove('10.0.0.3')
        self.assertEqual('done', cb())
        self.assertEqual([call('processes dummy_proc stopped but on 10.0.0.2')], mocked_info.call_args_list)

    @patch('supvisors.viewsupvisors.conciliate_conflicts')
    @patch('supvisors.viewsupvisors.delayed_info', return_value='delayed info')
    def test_conciliation_action(self, mocked_info, mocked_conciliate):
        """ Test the conciliation_action method. """
        from supvisors.ttypes import ConciliationStrategies
        # patch context
        self.view.sup_ctx.processes['proc_conflict'] = 'a process status'
        self.view.sup_ctx.conflicts.return_value = 'all conflicting process status'
        # test with no namespec
        self.assertEqual('delayed info', self.view.conciliation_action(None, 'INFANTICIDE'))
        self.assertEqual([call(self.view.supvisors, ConciliationStrategies.INFANTICIDE,
                               'all conflicting process status')],
                         mocked_conciliate.call_args_list)
        self.assertEqual([call('INFANTICIDE in progress for all conflicts')], mocked_info.call_args_list)
        # reset mocks
        mocked_conciliate.reset_mock()
        mocked_info.reset_mock()
        # test with namespec
        self.assertEqual('delayed info', self.view.conciliation_action('proc_conflict', 'STOP'))
        self.assertEqual([call(self.view.supvisors, ConciliationStrategies.STOP, ['a process status'])],
                         mocked_conciliate.call_args_list)
        self.assertEqual([call('STOP in progress for proc_conflict')], mocked_info.call_args_list)


class ViewSupvisorsActionTest(unittest.TestCase):
    """ Test case for the viewsupvisors module.
    In this class, no default instance is set so that it is possible to patch methods
    before they are stored in instance attributes. """

    @patch('supvisors.viewsupvisors.SupvisorsView.keep_action', return_value='pkeep called')
    @patch('supvisors.viewsupvisors.SupvisorsView.stop_action', return_value='pstop called')
    @patch('supvisors.viewsupvisors.SupvisorsView.sup_shutdown_action', return_value='sup_shutdown called')
    @patch('supvisors.viewsupvisors.SupvisorsView.sup_restart_action', return_value='sup_restart called')
    @patch('supvisors.viewsupvisors.SupvisorsView.refresh_action', return_value='refresh called')
    @patch('supvisors.viewsupvisors.SupvisorsView.conciliation_action', return_value='conciliation')
    def test_make_callback(self, *args):
        """ Test the make_callback method. """
        from supvisors.tests.base import DummyHttpContext
        from supvisors.viewsupvisors import SupvisorsView
        view = SupvisorsView(DummyHttpContext('ui/hostaddress.html'))
        view.view_ctx = Mock(**{'get_address.return_value': '10.0.0.1'})
        # test strategies but USER
        for strategy in view.strategies:
            self.assertEqual('conciliation', view.make_callback('dummy_namespec', strategy))
            self.assertEqual([call('dummy_namespec', strategy.upper())], args[0].call_args_list)
            args[0].reset_mock()
        self.assertFalse(any(mocked.called for mocked in args))
        # test USER strategy
        self.assertFalse(view.make_callback('dummy_namespec', 'user'))
        self.assertFalse(any(mocked.called for mocked in args))
        # test global actions
        for idx, action in enumerate(['refresh', 'sup_restart', 'sup_shutdown'], 1):
            self.assertEqual('%s called' % action, view.make_callback(None, action))
            self.assertEqual([call()], args[idx].call_args_list)
            args[idx].reset_mock()
            self.assertFalse(any(mocked.called for mocked in args))
        # test process actions
        for idx, action in enumerate(['pstop', 'pkeep'], 4):
            self.assertEqual('%s called' % action, view.make_callback('dummy_namespec', action))
            self.assertEqual([call('dummy_namespec', '10.0.0.1')], args[idx].call_args_list)
            args[idx].reset_mock()
            self.assertFalse(any(mocked.called for mocked in args))


def test_suite():
    return unittest.findTestCases(sys.modules[__name__])


if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
