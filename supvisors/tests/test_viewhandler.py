#!/usr/bin/python
#-*- coding: utf-8 -*-

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

from mock import call, patch, Mock, PropertyMock, DEFAULT
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
        """ Create a logger that stores log traces. """
        self.http_context = DummyHttpContext('')

    def test_init(self):
        """ Test the values set at construction. """
        from supvisors.viewhandler import ViewHandler
        handler = ViewHandler(self.http_context, 'index.html')
        self.assertIs(handler.supvisors,
                      self.http_context.supervisord.supvisors)
        self.assertIs(handler.sup_ctx,
                      self.http_context.supervisord.supvisors.context)
        self.assertEqual(DummyAddressMapper().local_address, handler.address)
        self.assertIsNone(handler.view_ctx)

    @patch('supvisors.viewhandler.ViewHandler.handle_action')
    def test_render_not_ready(self, mocked_action):
        """ Test the render method when Supervisor is not in RUNNING state. """
        from supvisors.ttypes import SupvisorsStates
        from supvisors.viewhandler import ViewHandler
        handler = ViewHandler(self.http_context, 'index.html')
        handler.info_source.supervisor_state = SupervisorStates.RESTARTING
        # heavy patch on handler
        # ViewHandler is designed to be used as a superclass in conjunction
        # with a MeldView subclass, so a few methods are expected to be defined
        handler.clone = Mock()
        handler.write_navigation = Mock()
        handler.write_header = Mock()
        handler.write_contents = Mock()
        # test render call
        self.assertFalse(handler.render())
        self.assertIsNone(handler.view_ctx)
        self.assertFalse(mocked_action.call_count)
        self.assertFalse(handler.clone.call_count)
        self.assertFalse(handler.write_navigation.call_count)
        self.assertFalse(handler.write_header.call_count)
        self.assertFalse(handler.write_contents.call_count)

    @patch('supvisors.viewhandler.ViewHandler.handle_action',
           return_value=NOT_DONE_YET)
    def test_render_action_in_progress(self, mocked_action):
        """ Test the render method when Supervisor is in RUNNING state
        and when an action is in progress. """
        from supvisors.ttypes import SupvisorsStates
        from supvisors.viewhandler import ViewHandler
        handler = ViewHandler(self.http_context, 'index.html')
        handler.context = self.http_context
        handler.info_source.supervisor_state = SupervisorStates.RUNNING
        handler.fsm.state = SupvisorsStates.OPERATION
        # heavy patch on handler
        # ViewHandler is designed to be used as a superclass in conjunction
        # with a MeldView subclass, so a few methods are expected to be defined
        handler.clone = Mock()
        handler.write_navigation = Mock()
        handler.write_header = Mock()
        handler.write_contents = Mock()
        # test render call
        self.assertEqual(NOT_DONE_YET, handler.render())
        self.assertIsNotNone(handler.view_ctx)
        self.assertEqual([call()], mocked_action.call_args_list)
        self.assertFalse(handler.clone.call_count)
        self.assertFalse(handler.write_navigation.call_count)
        self.assertFalse(handler.write_header.call_count)
        self.assertFalse(handler.write_contents.call_count)

    @patch('supvisors.viewhandler.print_message')
    @patch('supvisors.viewhandler.ViewHandler.handle_action')
    def test_render_no_conflict(self, mocked_action, mocked_print):
        """ Test the render method when Supervisor is in RUNNING state,
        when no action is in progress and no conflict is found. """
        from supvisors.ttypes import SupvisorsStates
        from supvisors.viewhandler import ViewHandler
        handler = ViewHandler(self.http_context, 'index.html')
        handler.context = self.http_context
        handler.info_source.supervisor_state = SupervisorStates.RUNNING
        handler.fsm.state = SupvisorsStates.OPERATION
        # heavy patch on handler
        # ViewHandler is designed to be used as a superclass in conjunction
        # with a MeldView subclass, so a few methods are expected to be defined
        mocked_meld = Mock(attrib={})
        mocked_root = Mock(**{'findmeld.return_value': mocked_meld,
                              'write_xhtmlstring.return_value': 'xhtml'})
        handler.clone = Mock(return_value=mocked_root)
        handler.write_navigation = Mock()
        handler.write_header = Mock()
        handler.write_contents = Mock()
        # test render call
        mocked_action.return_value = False
        self.assertEqual('xhtml', handler.render())
        self.assertIsNotNone(handler.view_ctx)
        self.assertEqual([call()], mocked_action.call_args_list)
        self.assertEqual([call()], handler.clone.call_args_list)
        self.assertEqual([call(mocked_root)],
                         handler.write_navigation.call_args_list)
        self.assertEqual([call(mocked_root)],
                         handler.write_header.call_args_list)
        self.assertEqual([call(mocked_root)],
                         handler.write_contents.call_args_list)
        self.assertEqual([call('version_mid')],
                         mocked_root.findmeld.call_args_list)
        self.assertDictEqual({}, mocked_meld.attrib)

    @patch('supvisors.viewhandler.print_message')
    @patch('supvisors.viewhandler.ViewHandler.handle_action')
    def test_render_no_conflict(self, mocked_action, mocked_print):
        """ Test the render method when Supervisor is in RUNNING state,
        when no action is in progress and conflicts are found. """
        from supvisors.ttypes import SupvisorsStates
        from supvisors.viewhandler import ViewHandler
        handler = ViewHandler(self.http_context, 'index.html')
        handler.context = self.http_context
        handler.info_source.supervisor_state = SupervisorStates.RUNNING
        handler.fsm.state = SupvisorsStates.CONCILIATION
        handler.sup_ctx.conflicts.return_value = ['conflict_1', 'conflict_2']
        # heavy patch on handler
        # ViewHandler is designed to be used as a superclass in conjunction
        # with a MeldView subclass, so a few methods are expected to be defined
        mocked_meld = Mock(attrib={})
        mocked_root = Mock(**{'findmeld.return_value': mocked_meld,
                              'write_xhtmlstring.return_value': 'xhtml'})
        handler.clone = Mock(return_value=mocked_root)
        handler.write_navigation = Mock()
        handler.write_header = Mock()
        handler.write_contents = Mock()
        # test render call
        mocked_action.return_value = False
        self.assertEqual('xhtml', handler.render())
        self.assertIsNotNone(handler.view_ctx)
        self.assertEqual([call()], mocked_action.call_args_list)
        self.assertEqual([call()], handler.clone.call_args_list)
        self.assertEqual([call(mocked_root)],
                         handler.write_navigation.call_args_list)
        self.assertEqual([call(mocked_root)],
                         handler.write_header.call_args_list)
        self.assertEqual([call(mocked_root)],
                         handler.write_contents.call_args_list)
        self.assertEqual([call('supvisors_mid'), call('version_mid')],
                         mocked_root.findmeld.call_args_list)
        self.assertDictEqual({'class': 'blink'}, mocked_meld.attrib)

    def test_handle_parameters(self):
        """ Test the handle_parameters method. """
        from supvisors.viewcontext import ViewContext
        from supvisors.viewhandler import ViewHandler
        handler = ViewHandler(self.http_context, 'index.html')
        handler.context = self.http_context
        self.assertIsNone(handler.view_ctx)
        handler.handle_parameters()
        self.assertIsNotNone(handler.view_ctx)
        self.assertIsInstance(handler.view_ctx, ViewContext)

    @patch('supvisors.viewhandler.ViewHandler.write_nav_applications')
    @patch('supvisors.viewhandler.ViewHandler.write_nav_addresses')
    def test_write_nav(self, mocked_addr, mocked_appli):
        """ Test the write_nav method. """
        from supvisors.viewhandler import ViewHandler
        handler = ViewHandler(self.http_context, 'index.html')
        handler.write_nav('root', 'address', 'appli')
        self.assertEqual([call('root', 'address')],
                         mocked_addr.call_args_list)
        self.assertEqual([call('root', 'appli')],
                         mocked_appli.call_args_list)

    def test_write_nav_addresses_address_error(self):
        """ Test the write_nav_addresses method with an address not existing
        in supvisors context. """
        from supvisors.viewhandler import ViewHandler
        handler = ViewHandler(self.http_context, 'index.html')
        # patch the meld elements
        href_elt = Mock(attrib={})
        address_elt = Mock(attrib={}, **{'findmeld.return_value': href_elt})
        mocked_mid = Mock(**{'repeat.return_value':
                             [(address_elt, '10.0.0.1')]})
        mocked_root = Mock(**{'findmeld.return_value': mocked_mid})
        # test call with no address status in context
        handler.write_nav_addresses(mocked_root, '10.0.0.1')
        self.assertEqual([call('address_li_mid')],
                         mocked_root.findmeld.call_args_list)
        self.assertEqual([call(handler.address_mapper.addresses)],
                         mocked_mid.repeat.call_args_list)
        self.assertEqual([], address_elt.findmeld.call_args_list)

    def test_write_nav_addresses_silent_address(self):
        """ Test the write_nav_addresses method using a SILENT address. """
        from supvisors.ttypes import AddressStates
        from supvisors.viewhandler import ViewHandler
        handler = ViewHandler(self.http_context, 'index.html')
        # patch the meld elements
        href_elt = Mock(attrib={})
        address_elt = Mock(attrib={}, **{'findmeld.return_value': href_elt})
        mocked_mid = Mock(**{'repeat.return_value':
                             [(address_elt, '10.0.0.1')]})
        mocked_root = Mock(**{'findmeld.return_value': mocked_mid})
        # test call with address status set in context, SILENT
        # and different from parameter
        handler.sup_ctx.addresses['10.0.0.1'] = \
            Mock(state=AddressStates.SILENT,
                 **{'state_string.return_value': 'silent'})
        handler.write_nav_addresses(mocked_root, '10.0.0.2')
        self.assertEqual([call('address_li_mid')],
                         mocked_root.findmeld.call_args_list)
        self.assertEqual([call(handler.address_mapper.addresses)],
                         mocked_mid.repeat.call_args_list)
        self.assertEqual('silent', address_elt.attrib['class'])
        self.assertEqual([call('address_a_mid')],
                         address_elt.findmeld.call_args_list)
        self.assertEqual('off', href_elt.attrib['class'])
        self.assertEqual([call('10.0.0.1')],
                         href_elt.content.call_args_list)
        mocked_root.findmeld.reset_mock()
        mocked_mid.repeat.reset_mock()
        address_elt.findmeld.reset_mock()
        href_elt.content.reset_mock()
        # test call with address status set in context, SILENT
        # and identical to parameter
        handler.write_nav_addresses(mocked_root, '10.0.0.1')
        self.assertEqual([call('address_li_mid')],
                         mocked_root.findmeld.call_args_list)
        self.assertEqual([call(handler.address_mapper.addresses)],
                         mocked_mid.repeat.call_args_list)
        self.assertEqual('silent active', address_elt.attrib['class'])
        self.assertEqual([call('address_a_mid')],
                         address_elt.findmeld.call_args_list)
        self.assertEqual('off', href_elt.attrib['class'])
        self.assertEqual([call('10.0.0.1')],
                         href_elt.content.call_args_list)

    def test_write_nav_addresses_running_address(self):
        """ Test the write_nav_addresses method using a RUNNING address. """
        from supvisors.ttypes import AddressStates
        from supvisors.viewhandler import ViewHandler
        handler = ViewHandler(self.http_context, 'index.html')
        # patch the meld elements
        href_elt = Mock(attrib={})
        address_elt = Mock(attrib={}, **{'findmeld.return_value': href_elt})
        mocked_mid = Mock(**{'repeat.return_value':
                             [(address_elt, '10.0.0.1')]})
        mocked_root = Mock(**{'findmeld.return_value': mocked_mid})
        # test call with address status set in context, RUNNING,
        # different from parameter and not MASTER
        handler.view_ctx = Mock(**{'format_url.return_value': 'an url'})
        handler.sup_ctx.addresses['10.0.0.1'] = \
            Mock(state=AddressStates.RUNNING,
                 **{'state_string.return_value': 'running'})
        handler.write_nav_addresses(mocked_root, '10.0.0.2')
        self.assertEqual([call('address_li_mid')],
                         mocked_root.findmeld.call_args_list)
        self.assertEqual([call(handler.address_mapper.addresses)],
                         mocked_mid.repeat.call_args_list)
        self.assertEqual('running', address_elt.attrib['class'])
        self.assertEqual([call('address_a_mid')],
                         address_elt.findmeld.call_args_list)
        self.assertEqual([call('10.0.0.1', 'procaddress.html')],
                          handler.view_ctx.format_url.call_args_list)
        self.assertEqual([call(href='an url')],
                          href_elt.attributes.call_args_list)
        self.assertEqual('on', href_elt.attrib['class'])
        self.assertEqual([call('10.0.0.1')],
                         href_elt.content.call_args_list)
        mocked_root.findmeld.reset_mock()
        mocked_mid.repeat.reset_mock()
        address_elt.findmeld.reset_mock()
        handler.view_ctx.format_url.reset_mock()
        href_elt.attributes.reset_mock()
        href_elt.content.reset_mock()
        # test call with address status set in context, RUNNING,
        # identical to parameter and MASTER
        handler.sup_ctx.master_address = '10.0.0.1'
        handler.write_nav_addresses(mocked_root, '10.0.0.1')
        self.assertEqual([call('address_li_mid')],
                         mocked_root.findmeld.call_args_list)
        self.assertEqual([call(handler.address_mapper.addresses)],
                         mocked_mid.repeat.call_args_list)
        self.assertEqual('running active', address_elt.attrib['class'])
        self.assertEqual([call('address_a_mid')],
                         address_elt.findmeld.call_args_list)
        self.assertEqual([call('10.0.0.1', 'procaddress.html')],
                          handler.view_ctx.format_url.call_args_list)
        self.assertEqual([call(href='an url')],
                          href_elt.attributes.call_args_list)
        self.assertEqual('on master', href_elt.attrib['class'])
        self.assertEqual([call('10.0.0.1')],
                         href_elt.content.call_args_list)

    def test_write_nav_applications_initialization(self):
        """ Test the write_nav_applications method with Supvisors in its
        INITIALIZATION state. """
        from supvisors.ttypes import SupvisorsStates
        from supvisors.viewhandler import ViewHandler
        handler = ViewHandler(self.http_context, 'index.html')
        handler.fsm.state = SupvisorsStates.INITIALIZATION
        # patch the meld elements
        href_elt = Mock(attrib={})
        appli_elt = Mock(attrib={}, **{'findmeld.return_value': href_elt})
        mocked_mid = Mock(**{'repeat.return_value':
                             [(appli_elt,
                               Mock(application_name='dummy_appli',
                                    **{'state_string.return_value': 'running'})
                               )]})
        mocked_root = Mock(**{'findmeld.return_value': mocked_mid})
        # test call with application name different from parameter
        handler.view_ctx = Mock(**{'format_url.return_value': 'an url'})
        handler.write_nav_applications(mocked_root, 'dumb_appli')
        self.assertEqual([call('appli_li_mid')],
                         mocked_root.findmeld.call_args_list)
        self.assertEqual([call([])], mocked_mid.repeat.call_args_list)
        self.assertEqual('running', appli_elt.attrib['class'])
        self.assertEqual([call('appli_a_mid')],
                         appli_elt.findmeld.call_args_list)
        self.assertEqual('off', href_elt.attrib['class'])
        self.assertEqual([], handler.view_ctx.format_url.call_args_list)
        self.assertEqual([], href_elt.attributes.call_args_list)
        self.assertEqual([call('dummy_appli')],
                         href_elt.content.call_args_list)
        mocked_root.findmeld.reset_mock()
        mocked_mid.repeat.reset_mock()
        appli_elt.findmeld.reset_mock()
        href_elt.content.reset_mock()
        # test call with application name identical to parameter
        handler.write_nav_applications(mocked_root, 'dummy_appli')
        self.assertEqual([call('appli_li_mid')],
                         mocked_root.findmeld.call_args_list)
        self.assertEqual([call([])], mocked_mid.repeat.call_args_list)
        self.assertEqual('running active', appli_elt.attrib['class'])
        self.assertEqual([call('appli_a_mid')],
                         appli_elt.findmeld.call_args_list)
        self.assertEqual('off', href_elt.attrib['class'])
        self.assertEqual([], handler.view_ctx.format_url.call_args_list)
        self.assertEqual([], href_elt.attributes.call_args_list)
        self.assertEqual([call('dummy_appli')],
                         href_elt.content.call_args_list)

    def test_write_nav_applications_operation(self):
        """ Test the write_nav_applications method with Supvisors in its
        OPERATION state. """
        from supvisors.ttypes import SupvisorsStates
        from supvisors.viewhandler import ViewHandler
        handler = ViewHandler(self.http_context, 'index.html')
        handler.fsm.state = SupvisorsStates.OPERATION
        # patch the meld elements
        href_elt = Mock(attrib={})
        appli_elt = Mock(attrib={}, **{'findmeld.return_value': href_elt})
        mocked_mid = Mock(**{'repeat.return_value':
                             [(appli_elt,
                               Mock(application_name='dummy_appli',
                                    **{'state_string.return_value': 'running'})
                               )]})
        mocked_root = Mock(**{'findmeld.return_value': mocked_mid})
        # test call with application name different from parameter
        handler.view_ctx = Mock(**{'format_url.return_value': 'an url'})
        handler.write_nav_applications(mocked_root, 'dumb_appli')
        self.assertEqual([call('appli_li_mid')],
                         mocked_root.findmeld.call_args_list)
        self.assertEqual([call([])], mocked_mid.repeat.call_args_list)
        self.assertEqual('running', appli_elt.attrib['class'])
        self.assertEqual([call('appli_a_mid')],
                         appli_elt.findmeld.call_args_list)
        self.assertEqual('on', href_elt.attrib['class'])
        self.assertEqual([call('', 'application.html',
                               appliname='dummy_appli')],
                         handler.view_ctx.format_url.call_args_list)
        self.assertEqual([call(href='an url')],
                         href_elt.attributes.call_args_list)
        self.assertEqual([call('dummy_appli')],
                         href_elt.content.call_args_list)
        mocked_root.findmeld.reset_mock()
        mocked_mid.repeat.reset_mock()
        appli_elt.findmeld.reset_mock()
        handler.view_ctx.format_url.reset_mock()
        href_elt.attributes.reset_mock()
        href_elt.content.reset_mock()
        # test call with application name identical to parameter
        handler.write_nav_applications(mocked_root, 'dummy_appli')
        self.assertEqual([call('appli_li_mid')],
                         mocked_root.findmeld.call_args_list)
        self.assertEqual([call([])], mocked_mid.repeat.call_args_list)
        self.assertEqual('running active', appli_elt.attrib['class'])
        self.assertEqual([call('appli_a_mid')],
                         appli_elt.findmeld.call_args_list)
        self.assertEqual('on', href_elt.attrib['class'])
        self.assertEqual([call('', 'application.html',
                               appliname='dummy_appli')],
                         handler.view_ctx.format_url.call_args_list)
        self.assertEqual([call(href='an url')],
                         href_elt.attributes.call_args_list)
        self.assertEqual([call('dummy_appli')],
                         href_elt.content.call_args_list)

    def test_write_periods(self):
        """ Test the write_periods method. """
        from supvisors.viewcontext import PERIOD
        from supvisors.viewhandler import ViewHandler
        handler = ViewHandler(self.http_context, 'index.html')
        # patch the meld elements
        href_elt = Mock(attrib={'class': ''})
        period_elt = Mock(attrib={}, **{'findmeld.return_value': href_elt})
        mocked_mid = Mock(**{'repeat.return_value': [(period_elt, 5)]})
        mocked_root = Mock(**{'findmeld.return_value': mocked_mid})
        # test call with period selection identical to parameter
        handler.view_ctx = Mock(parameters={PERIOD: 5},
                                **{'format_url.return_value': 'an url'})
        handler.write_periods(mocked_root)
        self.assertEqual([call('period_li_mid')],
                         mocked_root.findmeld.call_args_list)
        self.assertEqual([call(handler.options.stats_periods)],
                         mocked_mid.repeat.call_args_list)
        self.assertEqual([call('period_a_mid')],
                         period_elt.findmeld.call_args_list)
        self.assertEqual('button off active', href_elt.attrib['class'])
        self.assertEqual([], handler.view_ctx.format_url.call_args_list)
        self.assertEqual([], href_elt.attributes.call_args_list)
        self.assertEqual([call('5s')], href_elt.content.call_args_list)
        mocked_root.findmeld.reset_mock()
        mocked_mid.repeat.reset_mock()
        period_elt.findmeld.reset_mock()
        href_elt.content.reset_mock()
        href_elt.attrib['class'] = ''
        # test call with period selection different from parameter
        handler.view_ctx.parameters[PERIOD] = 10
        handler.write_periods(mocked_root)
        self.assertEqual([call('period_li_mid')],
                         mocked_root.findmeld.call_args_list)
        self.assertEqual([call(handler.options.stats_periods)],
                         mocked_mid.repeat.call_args_list)
        self.assertEqual([call('period_a_mid')],
                         period_elt.findmeld.call_args_list)
        self.assertEqual('', href_elt.attrib['class'])
        self.assertEqual([call('', 'index.html', period=5)],
                         handler.view_ctx.format_url.call_args_list)
        self.assertEqual([call(href='an url')],
                         href_elt.attributes.call_args_list)
        self.assertEqual([call('5s')], href_elt.content.call_args_list)

    def test_write_common_process_cpu(self):
        """ Test the write_common_process_cpu method. """
        from supvisors.viewcontext import PROCESS
        from supvisors.viewhandler import ViewHandler
        handler = ViewHandler(self.http_context, 'index.html')
        # patch the view context
        handler.view_ctx = Mock(parameters={PROCESS: 'dummy_proc'},
                                **{'format_url.return_value': 'an url'})
        # patch the meld elements
        cell_elt = Mock(attrib={'class': ''})
        tr_elt = Mock(attrib={}, **{'findmeld.return_value': cell_elt})
        # test with no stats
        handler.write_common_process_cpu(tr_elt, None, None, 0)
        self.assertEqual([call('pcpu_a_mid')],
                         tr_elt.findmeld.call_args_list)
        self.assertEqual([call('--')],
                         cell_elt.replace.call_args_list)
        tr_elt.findmeld.reset_mock()
        cell_elt.replace.reset_mock()
        # test with empty stats
        handler.write_common_process_cpu(tr_elt, None, ([], []), 0)
        self.assertEqual([call('pcpu_a_mid')],
                         tr_elt.findmeld.call_args_list)
        self.assertEqual([call('--')],
                         cell_elt.replace.call_args_list)
        tr_elt.findmeld.reset_mock()
        cell_elt.replace.reset_mock()
        # test with filled stats on selected process, irix mode
        handler.options.stats_irix_mode = True
        handler.write_common_process_cpu(tr_elt, 'dummy_proc',
                                         ([10, 20], ), 2)
        self.assertEqual([call('pcpu_a_mid')],
                         tr_elt.findmeld.call_args_list)
        self.assertEqual([], cell_elt.replace.call_args_list)
        self.assertEqual([call('20.00%')],
                         cell_elt.content.call_args_list)
        self.assertEqual([call(href='#')],
                         cell_elt.attributes.call_args_list)
        self.assertEqual('button off active', cell_elt.attrib['class'])
        tr_elt.findmeld.reset_mock()
        cell_elt.content.reset_mock()
        cell_elt.attributes.reset_mock()
        # test with filled stats on not selected process, solaris mode
        handler.options.stats_irix_mode = False
        handler.write_common_process_cpu(tr_elt, 'dummy',
                                         ([10, 20, 30], ), 2)
        self.assertEqual([call('pcpu_a_mid')],
                         tr_elt.findmeld.call_args_list)
        self.assertEqual([], cell_elt.replace.call_args_list)
        self.assertEqual([call('15.00%')],
                         cell_elt.content.call_args_list)
        self.assertEqual([call('', 'index.html', processname='dummy')],
                         handler.view_ctx.format_url.call_args_list)
        self.assertEqual([call(href='an url')],
                         cell_elt.attributes.call_args_list)
        self.assertEqual('button on', cell_elt.attrib['class'])

    def test_write_common_process_mem(self):
        """ Test the write_common_process_mem method. """
        from supvisors.viewcontext import PROCESS
        from supvisors.viewhandler import ViewHandler
        handler = ViewHandler(self.http_context, 'index.html')
        # patch the view context
        handler.view_ctx = Mock(parameters={PROCESS: 'dummy_proc'},
                                **{'format_url.return_value': 'an url'})
        # patch the meld elements
        cell_elt = Mock(attrib={'class': ''})
        tr_elt = Mock(attrib={}, **{'findmeld.return_value': cell_elt})
        # test with no stats
        handler.write_common_process_mem(tr_elt, None, None)
        self.assertEqual([call('pmem_a_mid')],
                         tr_elt.findmeld.call_args_list)
        self.assertEqual([call('--')],
                         cell_elt.replace.call_args_list)
        tr_elt.findmeld.reset_mock()
        cell_elt.replace.reset_mock()
        # test with empty stats
        handler.write_common_process_mem(tr_elt, None, ([], []))
        self.assertEqual([call('pmem_a_mid')],
                         tr_elt.findmeld.call_args_list)
        self.assertEqual([call('--')],
                         cell_elt.replace.call_args_list)
        tr_elt.findmeld.reset_mock()
        cell_elt.replace.reset_mock()
        # test with filled stats on selected process
        handler.write_common_process_mem(tr_elt, 'dummy_proc', ([], [10, 20]))
        self.assertEqual([call('pmem_a_mid')],
                         tr_elt.findmeld.call_args_list)
        self.assertEqual([], cell_elt.replace.call_args_list)
        self.assertEqual([call('20.00%')],
                         cell_elt.content.call_args_list)
        self.assertEqual([call(href='#')],
                         cell_elt.attributes.call_args_list)
        self.assertEqual('button off active', cell_elt.attrib['class'])
        tr_elt.findmeld.reset_mock()
        cell_elt.content.reset_mock()
        cell_elt.attributes.reset_mock()
        # test with filled stats on not selected process
        handler.write_common_process_mem(tr_elt, 'dummy', ([], [10, 20, 30]))
        self.assertEqual([call('pmem_a_mid')],
                         tr_elt.findmeld.call_args_list)
        self.assertEqual([], cell_elt.replace.call_args_list)
        self.assertEqual([call('30.00%')],
                         cell_elt.content.call_args_list)
        self.assertEqual([call('', 'index.html', processname='dummy')],
                         handler.view_ctx.format_url.call_args_list)
        self.assertEqual([call(href='an url')],
                         cell_elt.attributes.call_args_list)
        self.assertEqual('button on', cell_elt.attrib['class'])

    @patch('supvisors.viewhandler.ViewHandler._write_process_button')
    def test_write_process_start_button(self, mocked_button):
        """ Test the write_process_start_button method. """
        from supvisors.viewhandler import ViewHandler
        handler = ViewHandler(self.http_context, 'index.html')
        # test call indirection
        handler.write_process_start_button('elt', 'dummy_proc', 'stopped')
        self.assertEqual([call('elt', 'start_a_mid', 'start', 'dummy_proc',
                               'stopped', STOPPED_STATES)],
                         mocked_button.call_args_list)

    @patch('supvisors.viewhandler.ViewHandler._write_process_button')
    def test_write_process_stop_button(self, mocked_button):
        """ Test the write_process_stop_button method. """
        from supvisors.viewhandler import ViewHandler
        handler = ViewHandler(self.http_context, 'index.html')
        # test call indirection
        handler.write_process_stop_button('elt', 'dummy_proc', 'starting')
        self.assertEqual([call('elt', 'stop_a_mid', 'stop', 'dummy_proc',
                               'starting', RUNNING_STATES)],
                         mocked_button.call_args_list)

    @patch('supvisors.viewhandler.ViewHandler._write_process_button')
    def test_write_process_restart_button(self, mocked_button):
        """ Test the write_process_restart_button method. """
        from supvisors.viewhandler import ViewHandler
        handler = ViewHandler(self.http_context, 'index.html')
        # test call indirection
        handler.write_process_restart_button('elt', 'dummy_proc', 'running')
        self.assertEqual([call('elt', 'restart_a_mid', 'restart', 'dummy_proc',
                               'running', RUNNING_STATES)],
                         mocked_button.call_args_list)

    def test_write_process_button(self):
        """ Test the _write_process_button method. """
        from supvisors.viewhandler import ViewHandler
        handler = ViewHandler(self.http_context, 'index.html')
        # patch the view context
        handler.view_ctx = Mock(**{'format_url.return_value': 'an url'})
        # patch the meld elements
        cell_elt = Mock(attrib={'class': ''})
        tr_elt = Mock(**{'findmeld.return_value': cell_elt})
        # test with process state not in expected list
        handler._write_process_button(tr_elt, 'meld_id', 'action',
                                      'dummy_proc', 'running',
                                      ['stopped', 'stopping'])
        self.assertEqual([call('meld_id')],
                         tr_elt.findmeld.call_args_list)
        self.assertEqual('button off', cell_elt.attrib['class'])
        self.assertEqual([], cell_elt.attributes.call_args_list)
        tr_elt.findmeld.reset_mock()
        # test with filled stats on selected process
        handler._write_process_button(tr_elt, 'meld_id', 'action',
                                      'dummy_proc', 'running',
                                      ['running', 'starting'])
        self.assertEqual([call('meld_id')],
                         tr_elt.findmeld.call_args_list)
        self.assertEqual('button on', cell_elt.attrib['class'])
        self.assertEqual([call('', 'index.html',
                               action='action', namespec='dummy_proc')],
                         handler.view_ctx.format_url.call_args_list)
        self.assertEqual([call(href='an url')],
                         cell_elt.attributes.call_args_list)

    @patch('supvisors.viewhandler.ViewHandler.write_process_restart_button')
    @patch('supvisors.viewhandler.ViewHandler.write_process_stop_button')
    @patch('supvisors.viewhandler.ViewHandler.write_process_start_button')
    @patch('supvisors.viewhandler.ViewHandler.write_common_process_mem')
    @patch('supvisors.viewhandler.ViewHandler.write_common_process_cpu')
    @patch('supvisors.viewhandler.ViewHandler.get_process_stats',
           return_value=('proc_stats', 4))
    def test_write_common_process_status(self, mocked_stats,
                                         mocked_cpu, mocked_mem,
                                         mocked_start, mocked_stop,
                                         mocked_restart):
        """ Test the write_common_process_status method. """
        from supvisors.viewcontext import PROCESS
        from supvisors.viewhandler import ViewHandler
        handler = ViewHandler(self.http_context, 'index.html')
        # patch the view context
        handler.view_ctx = Mock(parameters={PROCESS: 'dummy_proc'})
        # patch the meld elements
        state_elt = Mock(attrib={'class': ''})
        load_elt = Mock(attrib={'class': ''})
        tr_elt = Mock(attrib={}, **{'findmeld.side_effect':
                                    [state_elt, load_elt]})
        # test call on selected process
        param = {'namespec': 'dummy_proc',
                 'statename': 'running',
                 'loading': 35,
                 'statecode': 7}
        self.assertTrue(handler.write_common_process_status(tr_elt, param))
        self.assertEqual([call('state_td_mid'), call('load_td_mid')],
                         tr_elt.findmeld.call_args_list)
        self.assertEqual('running', state_elt.attrib['class'])
        self.assertEqual([call('running')], state_elt.content.call_args_list)
        self.assertEqual([call('35%')], load_elt.content.call_args_list)
        self.assertEqual([call('dummy_proc')], mocked_stats.call_args_list)
        self.assertEqual([call(tr_elt, 'dummy_proc', 'proc_stats', 4)],
                         mocked_cpu.call_args_list)
        self.assertEqual([call(tr_elt, 'dummy_proc', 'proc_stats')],
                         mocked_mem.call_args_list)
        self.assertEqual([call(tr_elt, 'dummy_proc', 7)],
                         mocked_start.call_args_list)
        self.assertEqual([call(tr_elt, 'dummy_proc', 7)],
                         mocked_stop.call_args_list)
        self.assertEqual([call(tr_elt, 'dummy_proc', 7)],
                         mocked_restart.call_args_list)
        # test call on not selected process
        param['namespec'] = 'dummy'
        tr_elt.findmeld.side_effect = [state_elt, load_elt]
        self.assertFalse(handler.write_common_process_status(tr_elt, param))

    def test_write_detailed_process_cpu(self):
        """ Test the write_detailed_process_cpu method. """
        from supvisors.viewhandler import ViewHandler
        handler = ViewHandler(self.http_context, 'index.html')
        # patch the meld elements
        val_elt = Mock(attrib={'class': ''})
        avg_elt, slope_elt, dev_elt = Mock(), Mock(), Mock()
        stats_elt = Mock(**{'findmeld.side_effect': [val_elt, avg_elt,
                                                     slope_elt, dev_elt] * 2})
        # create fake stats
        proc_stats = ([10, 16, 13], )
        # test call with empty stats
        self.assertFalse(handler.write_detailed_process_cpu(stats_elt, [], 4))
        self.assertFalse(handler.write_detailed_process_cpu(stats_elt,
                                                            ([], []), 4))
        # test call with irix mode
        handler.options.stats_irix_mode = True
        self.assertTrue(handler.write_detailed_process_cpu(stats_elt,
                                                           proc_stats, 4))
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
        proc_stats = ([10, 16, 24], )
        handler.options.stats_irix_mode = False
        self.assertTrue(handler.write_detailed_process_cpu(stats_elt,
                                                           proc_stats, 4))
        self.assertEqual('increase', val_elt.attrib['class'])
        self.assertEqual([call('6.00%')], val_elt.content.call_args_list)
        self.assertEqual([call('16.67%')], avg_elt.content.call_args_list)
        self.assertEqual([call('7.00')], slope_elt.content.call_args_list)
        self.assertEqual([call('5.73')], dev_elt.content.call_args_list)

    def test_write_detailed_process_mem(self):
        """ Test the write_detailed_process_mem method. """
        from supvisors.viewhandler import ViewHandler
        handler = ViewHandler(self.http_context, 'index.html')
        # patch the meld elements
        val_elt = Mock(attrib={'class': ''})
        avg_elt, slope_elt, dev_elt = Mock(), Mock(), Mock()
        stats_elt = Mock(**{'findmeld.side_effect': [val_elt, avg_elt,
                                                     slope_elt, dev_elt] * 2})
        # create fake stats
        proc_stats = ((), [20, 32, 32])
        # test call with empty stats
        self.assertFalse(handler.write_detailed_process_mem(stats_elt, [],))
        self.assertFalse(handler.write_detailed_process_mem(stats_elt,
                                                            ([], [])))
        # test call with irix mode
        handler.options.stats_irix_mode = True
        self.assertTrue(handler.write_detailed_process_mem(stats_elt,
                                                           proc_stats))
        self.assertEqual('stable', val_elt.attrib['class'])
        self.assertEqual([call('32.00%')], val_elt.content.call_args_list)
        self.assertEqual([call('28.00%')], avg_elt.content.call_args_list)
        self.assertEqual([call('6.00')], slope_elt.content.call_args_list)
        self.assertEqual([call('5.66')], dev_elt.content.call_args_list)

    @patch('supvisors.plot.StatisticsPlot.export_image')
    @patch('supvisors.plot.StatisticsPlot.add_plot')
    @patch('supvisors.plot.StatisticsPlot', side_effect=ImportError)
    def test_write_process_plots_import_error(self, mocked_import,
                                              moked_add, mocked_export):
        """ Test the write_process_plots method. """
        from supvisors.plot import StatisticsPlot
        from supvisors.viewhandler import ViewHandler
        handler = ViewHandler(self.http_context, 'index.html')
        # create fake stats
        with patch('supvisors.plot.StatisticsPlot.StatisticsPlot') \
            as mocked_plot:
            handler.write_process_plots([])
        self.assertEqual([], mocked_plot.call_args_list)
        self.assertEqual([], moked_add.call_args_list)
        self.assertEqual([], mocked_export.call_args_list)

    @patch('supvisors.plot.StatisticsPlot.export_image')
    @patch('supvisors.plot.StatisticsPlot.add_plot')
    def test_write_process_plots(self, moked_add, mocked_export):
        """ Test the write_process_plots method. """
        from supvisors.viewhandler import ViewHandler
        from supvisors.viewimage import process_cpu_image, process_mem_image
        handler = ViewHandler(self.http_context, 'index.html')
         # create fake stats
        proc_stats = ([10, 16, 24], [20, 32, 32])
        # test call
        handler.write_process_plots(proc_stats)
        self.assertEqual([call('CPU', '%', [10, 16, 24]),
                          call('MEM', '%', [20, 32, 32])],
                         moked_add.call_args_list)
        self.assertEqual([call(process_cpu_image), call(process_mem_image)],
                         mocked_export.call_args_list)

    @patch('supvisors.viewhandler.ViewHandler.write_process_plots')
    @patch('supvisors.viewhandler.ViewHandler.write_detailed_process_mem',
           return_value=False)
    @patch('supvisors.viewhandler.ViewHandler.write_detailed_process_cpu',
           return_value=False)
    @patch('supvisors.viewhandler.ViewHandler.get_process_stats',
           return_value=(([], []), 0))
    def test_write_process_statistics(self, mocked_stats, mocked_cpu,
                                      mocked_mem, mocked_plots):
        """ Test the write_process_statistics method. """
        from supvisors.viewcontext import PROCESS
        from supvisors.viewhandler import ViewHandler
        handler = ViewHandler(self.http_context, 'index.html')
        # patch the view context
        handler.view_ctx = Mock(parameters={PROCESS: ''})
        # patch the meld elements
        title_elt = Mock()
        stats_elt = Mock(attrib={}, **{'findmeld.return_value': title_elt})
        root_elt = Mock(attrib={}, **{'findmeld.return_value': stats_elt})
        # test call with no namespec selection
        handler.write_process_statistics(root_elt)
        self.assertEqual([call('')], stats_elt.replace.call_args_list)
        self.assertEqual([], mocked_cpu.call_args_list)
        self.assertEqual([], mocked_mem.call_args_list)
        self.assertEqual([], mocked_plots.call_args_list)
        stats_elt.replace.reset_mock()
        # test call with namespec selection and no stats found
        handler.view_ctx = Mock(parameters={PROCESS: 'dummy_proc'})
        handler.write_process_statistics(root_elt)
        self.assertEqual([], stats_elt.replace.call_args_list)
        self.assertEqual([call(stats_elt, ([], []), 0)],
                         mocked_cpu.call_args_list)
        self.assertEqual([call(stats_elt, ([], []))],
                         mocked_mem.call_args_list)
        self.assertEqual([], mocked_plots.call_args_list)
        mocked_cpu.reset_mock()
        mocked_mem.reset_mock()
        # test call with namespec selection and stats found
        mocked_cpu.return_value = True
        handler.write_process_statistics(root_elt)
        self.assertEqual([], stats_elt.replace.call_args_list)
        self.assertEqual([], stats_elt.replace.call_args_list)
        self.assertEqual([call(stats_elt, ([], []), 0)],
                         mocked_cpu.call_args_list)
        self.assertEqual([call(stats_elt, ([], []))],
                         mocked_mem.call_args_list)
        self.assertEqual([call(([], []))], mocked_plots.call_args_list)

    def test_handle_action(self):
        """ Test the handle_action method. """
        from supvisors.viewhandler import ViewHandler
        handler = ViewHandler(self.http_context, 'index.html')
        handler.view_ctx = Mock(parameters={'namespec': 'dummy_proc'},
                                **{'get_action.return_value': 'test'})
        handler.callback = None
        handler.make_callback = Mock(return_value=lambda: NOT_DONE_YET)
        # test no action in progress
        self.assertEqual(NOT_DONE_YET, handler.handle_action())
        self.assertEqual([call('dummy_proc', 'test')],
                         handler.make_callback.call_args_list)
        handler.make_callback.reset_mock()
        # test action in progress
        self.assertEqual(NOT_DONE_YET, handler.handle_action())
        self.assertEqual([], handler.make_callback.call_args_list)
        # test action completed
        handler.callback = None
        handler.make_callback = Mock(return_value=lambda: 'a message')
        self.assertEqual(NOT_DONE_YET, handler.handle_action())
        self.assertEqual([call('dummy_proc', 'test')],
                         handler.make_callback.call_args_list)
        handler.make_callback.reset_mock()
        self.assertFalse(handler.handle_action())
        self.assertEqual([], handler.make_callback.call_args_list)
        self.assertEqual([call(('info', 'a message'))],
                         handler.view_ctx.message.call_args_list)

    def test_get_process_stats(self):
        """ Test the get_process_stats method. """
        from supvisors.viewhandler import ViewHandler
        handler = ViewHandler(self.http_context, 'index.html')
        # patch view context
        handler.view_ctx = Mock()
        # test indirection
        handler.get_process_stats('dummy_proc')
        self.assertEqual([call('dummy_proc')],
                         handler.view_ctx.get_process_stats.call_args_list)

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
        from supvisors.viewhandler import ViewHandler
        handler = ViewHandler(self.http_context, 'index.html')
        # test empty parameter
        self.assertEqual([], handler.sort_processes_by_config(None))
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
        handler.info_source.get_group_config.side_effect = [
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
        self.assertEqual(handler.sort_processes_by_config(processes),
                         [{'application_name': 'crash',
                           'process_name': 'segv'},
                          {'application_name': 'crash',
                           'process_name': 'late_segv'},
                          {'application_name': 'firefox',
                           'process_name': 'firefox'},
                          {'application_name': 'sample_test_1',
                           'process_name': 'xclock'},
                          {'application_name': 'sample_test_1',
                           'process_name': 'xlogo'},
                          {'application_name': 'sample_test_1',
                           'process_name': 'xfontsel'},
                          {'application_name': 'sample_test_2',
                           'process_name': 'yeux_00'},
                          {'application_name': 'sample_test_2',
                           'process_name': 'yeux_01'},
                          {'application_name': 'sample_test_2',
                           'process_name': 'sleep'}])


def test_suite():
    return unittest.findTestCases(sys.modules[__name__])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
