#!/usr/bin/python
# -*- coding: utf-8 -*-

# ======================================================================
# Copyright 2018 Julien LE CLEACH
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

from unittest.mock import call, patch, Mock, PropertyMock
from random import shuffle

from supervisor.http import NOT_DONE_YET
from supervisor.states import (SupervisorStates,
                               RUNNING_STATES,
                               STOPPED_STATES)

from supvisors.tests.base import (DummyAddressMapper,
                                  DummyHttpContext,
                                  ProcessInfoDatabase)


class ViewHandlerTest(unittest.TestCase):
    """ Test case for the viewhandler module. """

    def setUp(self):
        """ Create the instance to be tested. """
        from supvisors.viewhandler import ViewHandler
        self.http_context = DummyHttpContext('ui/index.html')
        self.handler = ViewHandler(self.http_context)
        self.maxDiff = None

    def test_init(self):
        """ Test the values set at construction. """
        self.assertIsNotNone(self.handler.root)
        self.assertIsNotNone(self.handler.root.findmeld('version_mid'))
        self.assertIsNone(self.handler.callback)
        # test MeldView inheritance
        self.assertIs(self.handler.context, self.http_context)
        # test ViewHandler initialization
        self.assertIs(self.handler.supvisors,
                      self.http_context.supervisord.supvisors)
        self.assertIs(self.handler.sup_ctx,
                      self.http_context.supervisord.supvisors.context)
        self.assertEqual(DummyAddressMapper().local_address, self.handler.address)
        self.assertIsNone(self.handler.view_ctx)

    @patch('supvisors.viewhandler.MeldView.__call__',
           side_effect=(NOT_DONE_YET, {'body': u'html_body'}))
    def test_call(self, mocked_call):
        """ Test the call method. """
        # first call to MeldView returns NOT_DONE_YET
        self.assertIs(NOT_DONE_YET, self.handler.__call__())
        # second call to MeldView returns an HTML struct
        self.assertDictEqual({'body': b'html_body'}, self.handler.__call__())

    @patch('supvisors.viewhandler.ViewHandler.write_contents')
    @patch('supvisors.viewhandler.ViewHandler.write_header')
    @patch('supvisors.viewhandler.ViewHandler.write_navigation')
    @patch('supvisors.viewhandler.ViewHandler.write_common')
    @patch('supervisor.web.MeldView.clone')
    @patch('supvisors.viewhandler.ViewHandler.handle_action')
    def test_render_action_in_progress(self, mocked_action, mocked_clone, mocked_common,
                                       mocked_nav, mocked_header, mocked_contents):
        """ Test the render method when Supervisor is in RUNNING state
        and when an action is in progress. """
        # build xml template
        mocked_root = Mock(**{'write_xhtmlstring.return_value': 'xhtml'})
        mocked_clone.return_value = mocked_root
        # 1. test render call when Supervisor is not RUNNING
        self.handler.info_source.supervisor_state = SupervisorStates.RESTARTING
        self.assertFalse(self.handler.render())
        self.assertIsNone(self.handler.view_ctx)
        self.assertFalse(mocked_action.call_count)
        self.assertFalse(self.handler.clone.call_count)
        self.assertFalse(self.handler.write_navigation.call_count)
        self.assertFalse(self.handler.write_header.call_count)
        self.assertFalse(self.handler.write_contents.call_count)
        # 2. test render call when Supervisor is RUNNING and an action is in progress
        self.handler.info_source.supervisor_state = SupervisorStates.RUNNING
        mocked_action.return_value = NOT_DONE_YET
        self.assertEqual(NOT_DONE_YET, self.handler.render())
        self.assertIsNotNone(self.handler.view_ctx)
        self.assertEqual([call()], mocked_action.call_args_list)
        self.assertFalse(mocked_clone.call_count)
        self.assertFalse(mocked_common.call_count)
        self.assertFalse(mocked_nav.call_count)
        self.assertFalse(mocked_header.call_count)
        self.assertFalse(mocked_contents.call_count)
        # 3. test render call when Supervisor is RUNNING and no action is in progress
        mocked_action.reset_mock()
        mocked_action.return_value = None
        self.assertEqual('xhtml', self.handler.render())
        self.assertIsNotNone(self.handler.view_ctx)
        self.assertEqual([call()], mocked_action.call_args_list)
        self.assertEqual([call()], mocked_clone.call_args_list)
        self.assertEqual([call(mocked_root)], mocked_common.call_args_list)
        self.assertEqual([call(mocked_root)], mocked_nav.call_args_list)
        self.assertEqual([call(mocked_root)], mocked_header.call_args_list)
        self.assertEqual([call(mocked_root)], mocked_contents.call_args_list)

    def test_handle_parameters(self):
        """ Test the handle_parameters method. """
        from supvisors.viewcontext import ViewContext
        self.assertIsNone(self.handler.view_ctx)
        self.handler.handle_parameters()
        self.assertIsNotNone(self.handler.view_ctx)
        self.assertIsInstance(self.handler.view_ctx, ViewContext)

    @patch('supvisors.viewhandler.print_message')
    def test_write_common(self, mocked_msg):
        """ Test the write_common method. """
        from supvisors.rpcinterface import API_VERSION
        from supvisors.viewcontext import AUTO
        from supvisors.webutils import SUPVISORS_PAGE
        from supvisors.ttypes import SupvisorsStates
        # patch context
        self.handler.page_name = 'dummy.html'
        self.handler.view_ctx = Mock(parameters={AUTO: True}, **{'format_url.return_value': 'an url',
                                                                 'get_gravity.return_value': 'severe',
                                                                 'get_message.return_value': 'a message'})
        # build xml template
        mocked_meta = Mock(attrib={})
        mocked_supv = Mock(attrib={})
        mocked_version = Mock()
        mocked_refresh = Mock()
        mocked_autorefresh = Mock(attrib={'class': 'button'})
        mocked_root = Mock(**{'findmeld.side_effect': [mocked_meta, mocked_supv, mocked_version,
                                                       mocked_refresh, mocked_autorefresh] * 2})
        # 1. test no conflict and auto-refresh
        self.handler.fsm.state = SupvisorsStates.OPERATION
        self.handler.write_common(mocked_root)
        self.assertEqual([call('meta_mid'), call('supvisors_mid'), call('version_mid'),
                          call('refresh_a_mid'), call('autorefresh_a_mid')],
                         mocked_root.findmeld.call_args_list)
        self.assertFalse(mocked_meta.deparent.called)
        self.assertEqual([call(href='an url')], mocked_supv.attributes.call_args_list)
        self.assertNotIn('class', mocked_supv.attrib)
        self.assertEqual([call(API_VERSION)], mocked_version.content.call_args_list)
        self.assertEqual([call(href='an url')], mocked_refresh.attributes.call_args_list)
        self.assertEqual([call(href='an url')], mocked_autorefresh.attributes.call_args_list)
        self.assertEqual('button active', mocked_autorefresh.attrib['class'])
        self.assertEqual([call('', SUPVISORS_PAGE), call('', 'dummy.html', action='refresh'),
                          call('', 'dummy.html', action='refresh', auto=False)],
                         self.handler.view_ctx.format_url.call_args_list)
        self.assertEqual([call(mocked_root, 'severe', 'a message')], mocked_msg.call_args_list)
        # reset mocks
        mocked_root.findmeld.reset_mock()
        self.handler.view_ctx.format_url.reset_mock()
        mocked_supv.attributes.reset_mock()
        mocked_version.content.reset_mock()
        mocked_refresh.attributes.reset_mock()
        mocked_autorefresh.attributes.reset_mock()
        mocked_autorefresh.attrib['class'] = 'button'
        mocked_msg.reset_mock()
        # 2. test conflicts and no auto-refresh
        self.handler.fsm.state = SupvisorsStates.CONCILIATION
        self.handler.view_ctx.parameters[AUTO] = False
        self.handler.write_common(mocked_root)
        self.assertEqual([call('meta_mid'), call('supvisors_mid'), call('version_mid'),
                          call('refresh_a_mid'), call('autorefresh_a_mid')],
                         mocked_root.findmeld.call_args_list)
        self.assertTrue(mocked_meta.deparent.called)
        self.assertEqual([call(href='an url')], mocked_supv.attributes.call_args_list)
        self.assertDictEqual({'class': 'blink'}, mocked_supv.attrib)
        self.assertEqual([call(API_VERSION)], mocked_version.content.call_args_list)
        self.assertEqual([call(href='an url')], mocked_refresh.attributes.call_args_list)
        self.assertEqual([call(href='an url')], mocked_autorefresh.attributes.call_args_list)
        self.assertEqual('button', mocked_autorefresh.attrib['class'])
        self.assertEqual([call('', SUPVISORS_PAGE), call('', 'dummy.html', action='refresh'),
                          call('', 'dummy.html', action='refresh', auto=True)],
                         self.handler.view_ctx.format_url.call_args_list)
        self.assertEqual([call(mocked_root, 'severe', 'a message')], mocked_msg.call_args_list)

    @patch('supvisors.viewhandler.ViewHandler.write_nav_applications')
    @patch('supvisors.viewhandler.ViewHandler.write_nav_addresses')
    def test_write_nav(self, mocked_addr, mocked_appli):
        """ Test the write_nav method. """
        self.handler.write_nav('root', 'address', 'appli')
        self.assertEqual([call('root', 'address')], mocked_addr.call_args_list)
        self.assertEqual([call('root', 'appli')], mocked_appli.call_args_list)

    def test_write_nav_addresses_address_error(self):
        """ Test the write_nav_addresses method with an address not existing
        in supvisors context. """
        # patch the meld elements
        href_elt = Mock(attrib={})
        address_elt = Mock(attrib={}, **{'findmeld.return_value': href_elt})
        mocked_mid = Mock(**{'repeat.return_value': [(address_elt, '10.0.0.1')]})
        mocked_root = Mock(**{'findmeld.return_value': mocked_mid})
        # test call with no address status in context
        self.handler.write_nav_addresses(mocked_root, '10.0.0.1')
        self.assertEqual([call('address_li_mid')], mocked_root.findmeld.call_args_list)
        self.assertEqual([call(self.handler.address_mapper.addresses)], mocked_mid.repeat.call_args_list)
        self.assertEqual([], address_elt.findmeld.call_args_list)

    def test_write_nav_addresses_silent_address(self):
        """ Test the write_nav_addresses method using a SILENT address. """
        from supvisors.ttypes import AddressStates
        # patch the meld elements
        href_elt = Mock(attrib={})
        address_elt = Mock(attrib={}, **{'findmeld.return_value': href_elt})
        mocked_mid = Mock(**{'repeat.return_value': [(address_elt, '10.0.0.1')]})
        mocked_root = Mock(**{'findmeld.return_value': mocked_mid})
        # test call with address status set in context, SILENT
        # and different from parameter
        self.handler.sup_ctx.addresses['10.0.0.1'] = Mock(state=AddressStates.SILENT,
                                                          **{'state_string.return_value': 'silent'})
        self.handler.write_nav_addresses(mocked_root, '10.0.0.2')
        self.assertEqual([call('address_li_mid')], mocked_root.findmeld.call_args_list)
        self.assertEqual([call(self.handler.address_mapper.addresses)], mocked_mid.repeat.call_args_list)
        self.assertEqual('silent', address_elt.attrib['class'])
        self.assertEqual([call('address_a_mid')], address_elt.findmeld.call_args_list)
        self.assertEqual('off', href_elt.attrib['class'])
        self.assertEqual([call('10.0.0.1')], href_elt.content.call_args_list)
        mocked_root.findmeld.reset_mock()
        mocked_mid.repeat.reset_mock()
        address_elt.findmeld.reset_mock()
        href_elt.content.reset_mock()
        # test call with address status set in context, SILENT
        # and identical to parameter
        self.handler.write_nav_addresses(mocked_root, '10.0.0.1')
        self.assertEqual([call('address_li_mid')], mocked_root.findmeld.call_args_list)
        self.assertEqual([call(self.handler.address_mapper.addresses)], mocked_mid.repeat.call_args_list)
        self.assertEqual('silent active', address_elt.attrib['class'])
        self.assertEqual([call('address_a_mid')], address_elt.findmeld.call_args_list)
        self.assertEqual('off', href_elt.attrib['class'])
        self.assertEqual([call('10.0.0.1')], href_elt.content.call_args_list)

    def test_write_nav_addresses_running_address(self):
        """ Test the write_nav_addresses method using a RUNNING address. """
        from supvisors.ttypes import AddressStates
        # patch the meld elements
        href_elt = Mock(attrib={})
        address_elt = Mock(attrib={}, **{'findmeld.return_value': href_elt})
        mocked_mid = Mock(**{'repeat.return_value': [(address_elt, '10.0.0.1')]})
        mocked_root = Mock(**{'findmeld.return_value': mocked_mid})
        # test call with address status set in context, RUNNING,
        # different from parameter and not MASTER
        self.handler.view_ctx = Mock(**{'format_url.return_value': 'an url'})
        self.handler.sup_ctx.addresses['10.0.0.1'] = Mock(state=AddressStates.RUNNING,
                                                          **{'state_string.return_value': 'running'})
        self.handler.write_nav_addresses(mocked_root, '10.0.0.2')
        self.assertEqual([call('address_li_mid')], mocked_root.findmeld.call_args_list)
        self.assertEqual([call(self.handler.address_mapper.addresses)], mocked_mid.repeat.call_args_list)
        self.assertEqual('running', address_elt.attrib['class'])
        self.assertEqual([call('address_a_mid')], address_elt.findmeld.call_args_list)
        self.assertEqual([call('10.0.0.1', 'procaddress.html')], self.handler.view_ctx.format_url.call_args_list)
        self.assertEqual([call(href='an url')], href_elt.attributes.call_args_list)
        self.assertEqual('on', href_elt.attrib['class'])
        self.assertEqual([call('10.0.0.1')], href_elt.content.call_args_list)
        mocked_root.findmeld.reset_mock()
        mocked_mid.repeat.reset_mock()
        address_elt.findmeld.reset_mock()
        self.handler.view_ctx.format_url.reset_mock()
        href_elt.attributes.reset_mock()
        href_elt.content.reset_mock()
        # test call with address status set in context, RUNNING,
        # identical to parameter and MASTER
        self.handler.sup_ctx.master_address = '10.0.0.1'
        self.handler.write_nav_addresses(mocked_root, '10.0.0.1')
        self.assertEqual([call('address_li_mid')], mocked_root.findmeld.call_args_list)
        self.assertEqual([call(self.handler.address_mapper.addresses)], mocked_mid.repeat.call_args_list)
        self.assertEqual('running active', address_elt.attrib['class'])
        self.assertEqual([call('address_a_mid')], address_elt.findmeld.call_args_list)
        self.assertEqual([call('10.0.0.1', 'procaddress.html')], self.handler.view_ctx.format_url.call_args_list)
        self.assertEqual([call(href='an url')], href_elt.attributes.call_args_list)
        self.assertEqual('on master', href_elt.attrib['class'])
        self.assertEqual([call('10.0.0.1')], href_elt.content.call_args_list)

    def test_write_nav_applications_initialization(self):
        """ Test the write_nav_applications method with Supvisors in its INITIALIZATION state. """
        from supvisors.ttypes import SupvisorsStates
        self.handler.fsm.state = SupvisorsStates.INITIALIZATION
        # patch the meld elements
        href_elt = Mock(attrib={})
        appli_elt = Mock(attrib={}, **{'findmeld.return_value': href_elt})
        mocked_mid = Mock(**{'repeat.return_value': [(appli_elt,
                                                      Mock(application_name='dummy_appli',
                                                           **{'state_string.return_value': 'running'}))]})
        mocked_root = Mock(**{'findmeld.return_value': mocked_mid})
        # test call with application name different from parameter
        self.handler.view_ctx = Mock(**{'format_url.return_value': 'an url'})
        self.handler.write_nav_applications(mocked_root, 'dumb_appli')
        self.assertListEqual(mocked_root.findmeld.call_args_list, [call('appli_li_mid')])
        self.assertListEqual(mocked_mid.repeat.call_args_list, [call([])])
        self.assertEqual('running', appli_elt.attrib['class'])
        self.assertEqual([call('appli_a_mid')], appli_elt.findmeld.call_args_list)
        self.assertEqual('off', href_elt.attrib['class'])
        self.assertEqual([], self.handler.view_ctx.format_url.call_args_list)
        self.assertEqual([], href_elt.attributes.call_args_list)
        self.assertEqual([call('dummy_appli')], href_elt.content.call_args_list)
        mocked_root.findmeld.reset_mock()
        mocked_mid.repeat.reset_mock()
        appli_elt.findmeld.reset_mock()
        href_elt.content.reset_mock()
        # test call with application name identical to parameter
        self.handler.write_nav_applications(mocked_root, 'dummy_appli')
        self.assertEqual([call('appli_li_mid')], mocked_root.findmeld.call_args_list)
        self.assertEqual(mocked_mid.repeat.call_args_list, [call([])])
        self.assertEqual('running active', appli_elt.attrib['class'])
        self.assertEqual([call('appli_a_mid')], appli_elt.findmeld.call_args_list)
        self.assertEqual('off', href_elt.attrib['class'])
        self.assertEqual([], self.handler.view_ctx.format_url.call_args_list)
        self.assertEqual([], href_elt.attributes.call_args_list)
        self.assertEqual([call('dummy_appli')], href_elt.content.call_args_list)

    def test_write_nav_applications_operation(self):
        """ Test the write_nav_applications method with Supvisors in its
        OPERATION state. """
        from supvisors.ttypes import SupvisorsStates
        self.handler.fsm.state = SupvisorsStates.OPERATION
        # patch the meld elements
        href_elt = Mock(attrib={})
        appli_elt = Mock(attrib={}, **{'findmeld.return_value': href_elt})
        mocked_mid = Mock(**{'repeat.return_value': [(appli_elt,
                                                      Mock(application_name='dummy_appli',
                                                           **{'state_string.return_value': 'running'}))]})
        mocked_root = Mock(**{'findmeld.return_value': mocked_mid})
        # test call with application name different from parameter
        self.handler.view_ctx = Mock(**{'format_url.return_value': 'an url'})
        self.handler.write_nav_applications(mocked_root, 'dumb_appli')
        self.assertEqual([call('appli_li_mid')], mocked_root.findmeld.call_args_list)
        self.assertListEqual(mocked_mid.repeat.call_args_list, [call([])])
        self.assertEqual('running', appli_elt.attrib['class'])
        self.assertEqual([call('appli_a_mid')], appli_elt.findmeld.call_args_list)
        self.assertEqual('on', href_elt.attrib['class'])
        self.assertEqual([call('', 'application.html', appliname='dummy_appli')],
                         self.handler.view_ctx.format_url.call_args_list)
        self.assertEqual([call(href='an url')], href_elt.attributes.call_args_list)
        self.assertEqual([call('dummy_appli')], href_elt.content.call_args_list)
        mocked_root.findmeld.reset_mock()
        mocked_mid.repeat.reset_mock()
        appli_elt.findmeld.reset_mock()
        self.handler.view_ctx.format_url.reset_mock()
        href_elt.attributes.reset_mock()
        href_elt.content.reset_mock()
        # test call with application name identical to parameter
        self.handler.write_nav_applications(mocked_root, 'dummy_appli')
        self.assertEqual([call('appli_li_mid')], mocked_root.findmeld.call_args_list)
        self.assertListEqual(mocked_mid.repeat.call_args_list, [call([])])
        self.assertEqual('running active', appli_elt.attrib['class'])
        self.assertEqual([call('appli_a_mid')], appli_elt.findmeld.call_args_list)
        self.assertEqual('on', href_elt.attrib['class'])
        self.assertEqual([call('', 'application.html', appliname='dummy_appli')],
                         self.handler.view_ctx.format_url.call_args_list)
        self.assertEqual([call(href='an url')], href_elt.attributes.call_args_list)
        self.assertEqual([call('dummy_appli')], href_elt.content.call_args_list)

    def test_write_periods(self):
        """ Test the write_periods method. """
        from supvisors.viewcontext import PERIOD
        # patch the meld elements
        href_elt = Mock(attrib={'class': ''})
        period_elt = Mock(attrib={}, **{'findmeld.return_value': href_elt})
        mocked_mid = Mock(**{'repeat.return_value': [(period_elt, 5)]})
        mocked_root = Mock(**{'findmeld.return_value': mocked_mid})
        # test call with period selection identical to parameter
        self.handler.view_ctx = Mock(parameters={PERIOD: 5}, **{'format_url.return_value': 'an url'})
        self.handler.write_periods(mocked_root)
        self.assertEqual([call('period_li_mid')], mocked_root.findmeld.call_args_list)
        self.assertEqual([call(self.handler.options.stats_periods)], mocked_mid.repeat.call_args_list)
        self.assertEqual([call('period_a_mid')], period_elt.findmeld.call_args_list)
        self.assertEqual('button off active', href_elt.attrib['class'])
        self.assertEqual([], self.handler.view_ctx.format_url.call_args_list)
        self.assertEqual([], href_elt.attributes.call_args_list)
        self.assertEqual([call('5s')], href_elt.content.call_args_list)
        mocked_root.findmeld.reset_mock()
        mocked_mid.repeat.reset_mock()
        period_elt.findmeld.reset_mock()
        href_elt.content.reset_mock()
        href_elt.attrib['class'] = ''
        # test call with period selection different from parameter
        self.handler.view_ctx.parameters[PERIOD] = 10
        self.handler.write_periods(mocked_root)
        self.assertEqual([call('period_li_mid')], mocked_root.findmeld.call_args_list)
        self.assertEqual([call(self.handler.options.stats_periods)], mocked_mid.repeat.call_args_list)
        self.assertEqual([call('period_a_mid')], period_elt.findmeld.call_args_list)
        self.assertEqual('', href_elt.attrib['class'])
        self.assertEqual([call('', None, period=5)], self.handler.view_ctx.format_url.call_args_list)
        self.assertEqual([call(href='an url')], href_elt.attributes.call_args_list)
        self.assertEqual([call('5s')], href_elt.content.call_args_list)

    def test_write_common_process_cpu(self):
        """ Test the write_common_process_cpu method. """
        from supvisors.viewcontext import PROCESS
        # patch the view context
        self.handler.view_ctx = Mock(parameters={PROCESS: 'dummy_proc'},
                                     **{'format_url.return_value': 'an url'})
        # patch the meld elements
        cell_elt = Mock(attrib={'class': ''})
        tr_elt = Mock(attrib={}, **{'findmeld.return_value': cell_elt})
        # test with no stats
        info = {'proc_stats': None}
        self.handler.write_common_process_cpu(tr_elt, info)
        self.assertEqual([call('pcpu_a_mid')], tr_elt.findmeld.call_args_list)
        self.assertEqual([call('--')], cell_elt.replace.call_args_list)
        tr_elt.findmeld.reset_mock()
        cell_elt.replace.reset_mock()
        # test with empty stats
        info = {'proc_stats': [[]]}
        self.handler.write_common_process_cpu(tr_elt, info)
        self.assertEqual([call('pcpu_a_mid')], tr_elt.findmeld.call_args_list)
        self.assertEqual([call('--')], cell_elt.replace.call_args_list)
        tr_elt.findmeld.reset_mock()
        cell_elt.replace.reset_mock()
        # test with filled stats on selected process, irix mode
        self.handler.options.stats_irix_mode = True
        info = {'namespec': 'dummy_proc', 'proc_stats': [[10, 20]], 'nb_cores': 2}
        self.handler.write_common_process_cpu(tr_elt, info)
        self.assertEqual([call('pcpu_a_mid')], tr_elt.findmeld.call_args_list)
        self.assertEqual([], cell_elt.replace.call_args_list)
        self.assertEqual([call('20.00%')], cell_elt.content.call_args_list)
        self.assertEqual([call(href='#')], cell_elt.attributes.call_args_list)
        self.assertEqual('button off active', cell_elt.attrib['class'])
        tr_elt.findmeld.reset_mock()
        cell_elt.content.reset_mock()
        cell_elt.attributes.reset_mock()
        # test with filled stats on not selected process, solaris mode
        self.handler.options.stats_irix_mode = False
        info = {'namespec': 'dummy', 'address': '10.0.0.1', 'proc_stats': [[10, 20, 30]], 'nb_cores': 2}
        self.handler.write_common_process_cpu(tr_elt, info)
        self.assertEqual([call('pcpu_a_mid')], tr_elt.findmeld.call_args_list)
        self.assertEqual([], cell_elt.replace.call_args_list)
        self.assertEqual([call('15.00%')], cell_elt.content.call_args_list)
        self.assertEqual([call('', None, processname='dummy', address='10.0.0.1')],
                         self.handler.view_ctx.format_url.call_args_list)
        self.assertEqual([call(href='an url')], cell_elt.attributes.call_args_list)
        self.assertEqual('button on', cell_elt.attrib['class'])

    def test_write_common_process_mem(self):
        """ Test the write_common_process_mem method. """
        from supvisors.viewcontext import PROCESS
        # patch the view context
        self.handler.view_ctx = Mock(parameters={PROCESS: 'dummy_proc'},
                                     **{'format_url.return_value': 'an url'})
        # patch the meld elements
        cell_elt = Mock(attrib={'class': ''})
        tr_elt = Mock(attrib={}, **{'findmeld.return_value': cell_elt})
        # test with no stats
        info = {'proc_stats': []}
        self.handler.write_common_process_mem(tr_elt, info)
        self.assertEqual([call('pmem_a_mid')], tr_elt.findmeld.call_args_list)
        self.assertEqual([call('--')], cell_elt.replace.call_args_list)
        tr_elt.findmeld.reset_mock()
        cell_elt.replace.reset_mock()
        # test with empty stats
        info = {'proc_stats': ([], [])}
        self.handler.write_common_process_mem(tr_elt, info)
        self.assertEqual([call('pmem_a_mid')], tr_elt.findmeld.call_args_list)
        self.assertEqual([call('--')], cell_elt.replace.call_args_list)
        tr_elt.findmeld.reset_mock()
        cell_elt.replace.reset_mock()
        # test with filled stats on selected process
        info = {'namespec': 'dummy_proc', 'proc_stats': ([], [10, 20])}
        self.handler.write_common_process_mem(tr_elt, info)
        self.assertEqual([call('pmem_a_mid')], tr_elt.findmeld.call_args_list)
        self.assertEqual([], cell_elt.replace.call_args_list)
        self.assertEqual([call('20.00%')], cell_elt.content.call_args_list)
        self.assertEqual([call(href='#')], cell_elt.attributes.call_args_list)
        self.assertEqual('button off active', cell_elt.attrib['class'])
        tr_elt.findmeld.reset_mock()
        cell_elt.content.reset_mock()
        cell_elt.attributes.reset_mock()
        # test with filled stats on not selected process
        info = {'namespec': 'dummy', 'address': '10.0.0.2', 'proc_stats': ([], [10, 20, 30])}
        self.handler.write_common_process_mem(tr_elt, info)
        self.assertEqual([call('pmem_a_mid')], tr_elt.findmeld.call_args_list)
        self.assertEqual([], cell_elt.replace.call_args_list)
        self.assertEqual([call('30.00%')], cell_elt.content.call_args_list)
        self.assertEqual([call('', None, processname='dummy', address='10.0.0.2')],
                         self.handler.view_ctx.format_url.call_args_list)
        self.assertEqual([call(href='an url')], cell_elt.attributes.call_args_list)
        self.assertEqual('button on', cell_elt.attrib['class'])

    @patch('supvisors.viewhandler.ViewHandler._write_process_button')
    def test_write_process_start_button(self, mocked_button):
        """ Test the write_process_start_button method. """
        self.handler.page_name = 'My Page'
        # test call indirection
        info = {'namespec': 'dummy_proc', 'statecode': 'stopped'}
        self.handler.write_process_start_button('elt', info)
        self.assertEqual([call('elt', 'start_a_mid', '', 'My Page', 'start', 'dummy_proc', 'stopped', STOPPED_STATES)],
                         mocked_button.call_args_list)

    @patch('supvisors.viewhandler.ViewHandler._write_process_button')
    def test_write_process_stop_button(self, mocked_button):
        """ Test the write_process_stop_button method. """
        self.handler.page_name = 'My Page'
        # test call indirection
        info = {'namespec': 'dummy_proc', 'statecode': 'starting'}
        self.handler.write_process_stop_button('elt', info)
        self.assertEqual([call('elt', 'stop_a_mid', '', 'My Page', 'stop', 'dummy_proc', 'starting', RUNNING_STATES)],
                         mocked_button.call_args_list)

    @patch('supvisors.viewhandler.ViewHandler._write_process_button')
    def test_write_process_restart_button(self, mocked_button):
        """ Test the write_process_restart_button method. """
        self.handler.page_name = 'My Page'
        # test call indirection
        info = {'namespec': 'dummy_proc', 'statecode': 'running'}
        self.handler.write_process_restart_button('elt', info)
        self.assertEqual([call('elt', 'restart_a_mid', '', 'My Page', 'restart', 'dummy_proc',
                               'running', RUNNING_STATES)],
                         mocked_button.call_args_list)

    @patch('supvisors.viewhandler.ViewHandler._write_process_button')
    def test_write_process_clear_button(self, mocked_button):
        """ Test the write_process_clear_button method. """
        self.handler.page_name = 'My Page'
        # test call indirection
        info = {'namespec': 'dummy_proc', 'address': '10.0.0.1'}
        self.handler.write_process_clear_button('elt', info)
        self.assertEqual([call('elt', 'clear_a_mid', '10.0.0.1', 'My Page', 'clearlog', 'dummy_proc', '', '')],
                         mocked_button.call_args_list)

    @patch('supvisors.viewhandler.ViewHandler._write_process_button')
    def test_write_process_stdout_button(self, mocked_button):
        """ Test the write_process_stdout_button method. """
        self.handler.page_name = 'My Page'
        # test call indirection
        info = {'namespec': 'dummy_proc', 'address': '10.0.0.1'}
        self.handler.write_process_stdout_button('elt', info)
        self.assertEqual([call('elt', 'tailout_a_mid', '10.0.0.1', 'logtail/dummy_proc', '', '', '', '')],
                         mocked_button.call_args_list)

    @patch('supvisors.viewhandler.ViewHandler._write_process_button')
    def test_write_process_stderr_button(self, mocked_button):
        """ Test the write_process_stderr_button method. """
        self.handler.page_name = 'My Page'
        # test call indirection
        info = {'namespec': 'dummy_proc', 'address': '10.0.0.1'}
        self.handler.write_process_stderr_button('elt', info)
        self.assertEqual([call('elt', 'tailerr_a_mid', '10.0.0.1', 'logtail/dummy_proc/stderr', '', '', '', '')],
                         mocked_button.call_args_list)

    def test_write_process_button(self):
        """ Test the _write_process_button method. """
        # patch the view context
        self.handler.view_ctx = Mock(**{'format_url.return_value': 'an url'})
        # patch the meld elements
        cell_elt = Mock(attrib={'class': ''})
        tr_elt = Mock(**{'findmeld.return_value': cell_elt})
        # test with process state not in expected list
        self.handler._write_process_button(tr_elt, 'meld_id', '10.0.0.1', 'index.html', 'action', 'dummy_proc',
                                           'running', ['stopped', 'stopping'])
        self.assertEqual([call('meld_id')], tr_elt.findmeld.call_args_list)
        self.assertEqual('button off', cell_elt.attrib['class'])
        self.assertEqual([], cell_elt.attributes.call_args_list)
        tr_elt.findmeld.reset_mock()
        # test with filled stats on selected process
        self.handler._write_process_button(tr_elt, 'meld_id', '10.0.0.1', 'index.html', 'action', 'dummy_proc',
                                           'running', ['running', 'starting'])
        self.assertEqual([call('meld_id')], tr_elt.findmeld.call_args_list)
        self.assertEqual('button on', cell_elt.attrib['class'])
        self.assertEqual([call('10.0.0.1', 'index.html', action='action', namespec='dummy_proc')],
                         self.handler.view_ctx.format_url.call_args_list)
        self.assertEqual([call(href='an url')], cell_elt.attributes.call_args_list)

    @patch('supvisors.viewhandler.ViewHandler.write_process_stderr_button')
    @patch('supvisors.viewhandler.ViewHandler.write_process_stdout_button')
    @patch('supvisors.viewhandler.ViewHandler.write_process_clear_button')
    @patch('supvisors.viewhandler.ViewHandler.write_process_restart_button')
    @patch('supvisors.viewhandler.ViewHandler.write_process_stop_button')
    @patch('supvisors.viewhandler.ViewHandler.write_process_start_button')
    @patch('supvisors.viewhandler.ViewHandler.write_common_process_mem')
    @patch('supvisors.viewhandler.ViewHandler.write_common_process_cpu')
    def test_write_common_process_status(self, mocked_cpu, mocked_mem,
                                         mocked_start, mocked_stop, mocked_restart,
                                         mocked_clear, mocked_stdout, mocked_stderr):
        """ Test the write_common_process_status method. """
        from supvisors.viewcontext import PROCESS
        # patch the view context
        self.handler.view_ctx = Mock(parameters={PROCESS: 'dummy_proc'})
        # patch the meld elements
        state_elt = Mock(attrib={'class': ''})
        desc_elt = Mock(attrib={'class': ''})
        load_elt = Mock(attrib={'class': ''})
        tr_elt = Mock(attrib={}, **{'findmeld.side_effect': [state_elt, desc_elt, load_elt]})
        # test call on selected process
        param = {'namespec': 'dummy_proc', 'loading': 35, 'statename': 'running', 'statecode': 7,
                 'description': 'something'}
        self.handler.write_common_process_status(tr_elt, param)
        self.assertEqual([call('state_td_mid'), call('desc_td_mid'), call('load_td_mid')],
                         tr_elt.findmeld.call_args_list)
        self.assertEqual('running', state_elt.attrib['class'])
        self.assertEqual([call('running')], state_elt.content.call_args_list)
        self.assertEqual([call('something')], desc_elt.content.call_args_list)
        self.assertEqual([call('35%')], load_elt.content.call_args_list)
        self.assertEqual([call(tr_elt, param)], mocked_cpu.call_args_list)
        self.assertEqual([call(tr_elt, param)], mocked_mem.call_args_list)
        self.assertEqual([call(tr_elt, param)], mocked_start.call_args_list)
        self.assertEqual([call(tr_elt, param)], mocked_stop.call_args_list)
        self.assertEqual([call(tr_elt, param)], mocked_restart.call_args_list)
        self.assertEqual([call(tr_elt, param)], mocked_clear.call_args_list)
        self.assertEqual([call(tr_elt, param)], mocked_stdout.call_args_list)
        self.assertEqual([call(tr_elt, param)], mocked_stderr.call_args_list)

    def test_write_detailed_process_cpu(self):
        """ Test the write_detailed_process_cpu method. """
        # patch the meld elements
        val_elt = Mock(attrib={'class': ''})
        avg_elt, slope_elt, dev_elt = Mock(), Mock(), Mock()
        stats_elt = Mock(**{'findmeld.side_effect': [val_elt, avg_elt,
                                                     slope_elt, dev_elt] * 2})
        # create fake stats
        proc_stats = ([10, 16, 13],)
        # test call with empty stats
        self.assertFalse(self.handler.write_detailed_process_cpu(stats_elt, [], 4))
        self.assertFalse(self.handler.write_detailed_process_cpu(stats_elt, ([], []), 4))
        # test call with irix mode
        self.handler.options.stats_irix_mode = True
        self.assertTrue(self.handler.write_detailed_process_cpu(stats_elt, proc_stats, 4))
        self.assertEqual('decrease', val_elt.attrib['class'])
        self.assertEqual([call('13.00%')], val_elt.content.call_args_list)
        self.assertEqual([call('13.00%')], avg_elt.content.call_args_list)
        self.assertEqual([call('1.50')], slope_elt.content.call_args_list)
        self.assertEqual([call('2.45')], dev_elt.content.call_args_list)
        val_elt.content.reset_mock()
        avg_elt.content.reset_mock()
        slope_elt.content.reset_mock()
        dev_elt.content.reset_mock()
        # test call with solaris mode
        proc_stats = ([10, 16, 24],)
        self.handler.options.stats_irix_mode = False
        self.assertTrue(self.handler.write_detailed_process_cpu(stats_elt, proc_stats, 4))
        self.assertEqual('increase', val_elt.attrib['class'])
        self.assertEqual([call('6.00%')], val_elt.content.call_args_list)
        self.assertEqual([call('16.67%')], avg_elt.content.call_args_list)
        self.assertEqual([call('7.00')], slope_elt.content.call_args_list)
        self.assertEqual([call('5.73')], dev_elt.content.call_args_list)

    def test_write_detailed_process_mem(self):
        """ Test the write_detailed_process_mem method. """
        # patch the meld elements
        val_elt = Mock(attrib={'class': ''})
        avg_elt, slope_elt, dev_elt = Mock(), Mock(), Mock()
        stats_elt = Mock(**{'findmeld.side_effect': [val_elt, avg_elt,
                                                     slope_elt, dev_elt] * 2})
        # create fake stats
        proc_stats = ((), [20, 32, 32])
        # test call with empty stats
        self.assertFalse(self.handler.write_detailed_process_mem(stats_elt, [], ))
        self.assertFalse(self.handler.write_detailed_process_mem(stats_elt, ([], [])))
        # test call with irix mode
        self.handler.options.stats_irix_mode = True
        self.assertTrue(self.handler.write_detailed_process_mem(stats_elt, proc_stats))
        self.assertEqual('stable', val_elt.attrib['class'])
        self.assertEqual([call('32.00%')], val_elt.content.call_args_list)
        self.assertEqual([call('28.00%')], avg_elt.content.call_args_list)
        self.assertEqual([call('6.00')], slope_elt.content.call_args_list)
        self.assertEqual([call('5.66')], dev_elt.content.call_args_list)

    def test_test_matplotlib_import(self):
        """ Test the test_matplotlib_import function in the event of matplotlib import error. """
        from supvisors.viewhandler import test_matplotlib_import
        # test correct behaviour depending on environment
        try:
            import matplotlib
        except ImportError:
            self.assertFalse(test_matplotlib_import())
        else:
            self.assertTrue(test_matplotlib_import())
            # force import error
            with patch('matplotlib.get_backend', side_effect=ImportError):
                self.assertFalse(test_matplotlib_import())

    def test_write_process_plots_no_plot(self):
        """ Test the write_process_plots method in the event of matplotlib import error. """
        # import context
        from supvisors import viewhandler
        viewhandler.HAS_PLOT = False
        # test call
        self.handler.write_process_plots([])
        # test that plot methods are not called
        # can't test what is not called from a module that cannot even be imported

    def test_write_process_plots(self):
        """ Test the write_process_plots method. """
        # skip test if matplotlib is not installed
        try:
            import matplotlib
            matplotlib.__name__
        except ImportError:
            raise unittest.SkipTest('cannot test as optional matplotlib is not installed')
        # test considering that matplotlib is installed
        from supvisors.viewimage import process_cpu_img, process_mem_img
        # test call with dummy stats
        with patch('supvisors.plot.StatisticsPlot.export_image') as mocked_export:
            with patch('supvisors.plot.StatisticsPlot.add_plot') as mocked_add:
                proc_stats = ([10, 16, 24], [20, 32, 32])
                self.handler.write_process_plots(proc_stats)
                self.assertEqual([call('CPU', '%', [10, 16, 24]), call('MEM', '%', [20, 32, 32])],
                                 mocked_add.call_args_list)
                self.assertEqual([call(process_cpu_img), call(process_mem_img)],
                                 mocked_export.call_args_list)

    @patch('supvisors.viewhandler.ViewHandler.write_process_plots')
    @patch('supvisors.viewhandler.ViewHandler.write_detailed_process_mem', return_value=False)
    @patch('supvisors.viewhandler.ViewHandler.write_detailed_process_cpu', return_value=False)
    def test_write_process_statistics(self, mocked_cpu, mocked_mem, mocked_plots):
        """ Test the write_process_statistics method. """
        from supvisors.viewcontext import PROCESS
        # patch the view context
        self.handler.view_ctx = Mock(parameters={PROCESS: None})
        # patch the meld elements
        row_elt = Mock(attrib={})
        title_elt = Mock()
        stats_elt = Mock(attrib={}, **{'findmeld.side_effect': [title_elt, row_elt]})
        root_elt = Mock(attrib={}, **{'findmeld.return_value': stats_elt})
        # test call with no namespec selection
        info = {}
        self.handler.write_process_statistics(root_elt, info)
        self.assertEqual([call('pstats_div_mid')], root_elt.findmeld.call_args_list)
        self.assertEqual([call('')], stats_elt.replace.call_args_list)
        self.assertEqual([], stats_elt.findmeld.call_args_list)
        self.assertEqual([], mocked_cpu.call_args_list)
        self.assertEqual([], mocked_mem.call_args_list)
        self.assertEqual([], title_elt.content.call_args_list)
        self.assertNotIn('class', row_elt.attrib)
        self.assertEqual([], mocked_plots.call_args_list)
        root_elt.findmeld.reset_mock()
        stats_elt.replace.reset_mock()
        # test call with namespec selection and no stats found
        info = {'namespec': 'dummy_proc', 'address': '10.0.0.1', 'proc_stats': 'dummy_stats', 'nb_cores': 8}
        self.handler.write_process_statistics(root_elt, info)
        self.assertEqual([call('pstats_div_mid')], root_elt.findmeld.call_args_list)
        self.assertEqual([], stats_elt.replace.call_args_list)
        self.assertEqual([], stats_elt.findmeld.call_args_list)
        self.assertEqual([call(stats_elt, 'dummy_stats', 8)], mocked_cpu.call_args_list)
        self.assertEqual([call(stats_elt, 'dummy_stats')], mocked_mem.call_args_list)
        self.assertEqual([], title_elt.content.call_args_list)
        self.assertNotIn('class', row_elt.attrib)
        self.assertEqual([], mocked_plots.call_args_list)
        root_elt.findmeld.reset_mock()
        mocked_cpu.reset_mock()
        mocked_mem.reset_mock()
        # test call with namespec selection and stats found
        mocked_cpu.return_value = True
        self.handler.write_process_statistics(root_elt, info)
        self.assertEqual([call('pstats_div_mid')], root_elt.findmeld.call_args_list)
        self.assertEqual([call('process_h_mid'), call('address_fig_mid')],
                         stats_elt.findmeld.call_args_list)
        self.assertEqual([], stats_elt.replace.call_args_list)
        self.assertEqual([call(stats_elt, 'dummy_stats', 8)], mocked_cpu.call_args_list)
        self.assertEqual([call(stats_elt, 'dummy_stats')], mocked_mem.call_args_list)
        self.assertEqual([call('dummy_proc')], title_elt.content.call_args_list)
        self.assertEqual([call('dummy_stats')], mocked_plots.call_args_list)

    def test_handle_action(self):
        """ Test the handle_action method. """
        self.handler.view_ctx = Mock(parameters={'namespec': 'dummy_proc'},
                                **{'get_action.return_value': 'test'})
        self.handler.callback = None
        self.handler.make_callback = Mock(return_value=lambda: NOT_DONE_YET)
        # test no action in progress
        self.assertEqual(NOT_DONE_YET, self.handler.handle_action())
        self.assertEqual([call('dummy_proc', 'test')],
                         self.handler.make_callback.call_args_list)
        self.handler.make_callback.reset_mock()
        # test action in progress
        self.assertEqual(NOT_DONE_YET, self.handler.handle_action())
        self.assertEqual([], self.handler.make_callback.call_args_list)
        # test action completed
        self.handler.callback = None
        self.handler.make_callback = Mock(return_value=lambda: 'a message')
        self.assertEqual(NOT_DONE_YET, self.handler.handle_action())
        self.assertEqual([call('dummy_proc', 'test')],
                         self.handler.make_callback.call_args_list)
        self.handler.make_callback.reset_mock()
        self.assertFalse(self.handler.handle_action())
        self.assertEqual([], self.handler.make_callback.call_args_list)
        self.assertEqual([call(('info', 'a message'))],
                         self.handler.view_ctx.message.call_args_list)

    def test_set_slope_class(self):
        """ Test the set_slope_class method. """
        from supvisors.viewhandler import ViewHandler
        elt = Mock(attrib={})
        # test with values around 0
        ViewHandler.set_slope_class(elt, 0)
        self.assertEqual('stable', elt.attrib['class'])
        ViewHandler.set_slope_class(elt, 0.0049)
        self.assertEqual('stable', elt.attrib['class'])
        ViewHandler.set_slope_class(elt, -0.0049)
        self.assertEqual('stable', elt.attrib['class'])
        # test with values around greater than 0 but not around 0
        ViewHandler.set_slope_class(elt, 0.005)
        self.assertEqual('increase', elt.attrib['class'])
        ViewHandler.set_slope_class(elt, 10)
        self.assertEqual('increase', elt.attrib['class'])
        # test with values around lower than 0 but not around 0
        ViewHandler.set_slope_class(elt, -0.005)
        self.assertEqual('decrease', elt.attrib['class'])
        ViewHandler.set_slope_class(elt, -10)
        self.assertEqual('decrease', elt.attrib['class'])

    def test_sort_processes_by_config(self):
        """ Test the sort_processes_by_config method. """
        # test empty parameter
        self.assertEqual([], self.handler.sort_processes_by_config(None))
        # build process list
        processes = [{'application_name': info['group'],
                      'process_name': info['name']}
                     for info in ProcessInfoDatabase]
        shuffle(processes)

        # define group and process config ordering
        def create_mock(proc_name):
            proc = Mock()
            type(proc).name = PropertyMock(return_value=proc_name)
            return proc

        self.handler.info_source.get_group_config.side_effect = [
            # first group is crash
            # late_segv is forgotten to test ordering with unknown processes
            Mock(process_configs=[create_mock('segv')]),
            # next group is firefox
            Mock(process_configs=[create_mock('firefox')]),
            # next group is sample_test_1
            # xfontsel is forgotten to test ordering with unknown processes
            Mock(process_configs=[create_mock('xclock'),
                                  create_mock('xlogo')]),
            # next group is sample_test_2
            # sleep is forgotten to test ordering with unknown processes
            Mock(process_configs=[create_mock('yeux_00'),
                                  create_mock('yeux_01')])]
        # test ordering
        self.assertEqual(self.handler.sort_processes_by_config(processes),
                         [{'application_name': 'crash', 'process_name': 'segv'},
                          {'application_name': 'crash', 'process_name': 'late_segv'},
                          {'application_name': 'firefox', 'process_name': 'firefox'},
                          {'application_name': 'sample_test_1', 'process_name': 'xclock'},
                          {'application_name': 'sample_test_1', 'process_name': 'xlogo'},
                          {'application_name': 'sample_test_1', 'process_name': 'xfontsel'},
                          {'application_name': 'sample_test_2', 'process_name': 'yeux_00'},
                          {'application_name': 'sample_test_2', 'process_name': 'yeux_01'},
                          {'application_name': 'sample_test_2', 'process_name': 'sleep'}])


def test_suite():
    return unittest.findTestCases(sys.modules[__name__])


if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
