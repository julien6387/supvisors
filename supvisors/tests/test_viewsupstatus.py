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
from unittest.mock import call, patch, Mock


class ViewSupvisorsStatusTest(unittest.TestCase):
    """ Test case for the viewsupstatus module. """

    def setUp(self):
        """ Create the instance to be tested. """
        # apply the forced inheritance done in supvisors.plugin
        from supvisors.viewhandler import ViewHandler
        StatusView.__bases__ = (ViewHandler,)
        # create the instance to be tested
        from supvisors.tests.base import DummyHttpContext
        from supvisors.viewsupstatus import SupvisorsAddressView
        from supvisors.webutils import HOST_ADDRESS_PAGE
        self.view = SupvisorsAddressView(DummyHttpContext('ui/hostaddress.html'), HOST_ADDRESS_PAGE)

    def test_init(self):
        """ Test the values set at construction. """
        # test instance inheritance
        from supvisors.viewhandler import ViewHandler
        for klass in [StatusView, ViewHandler, MeldView]:
            self.assertIsInstance(self.view, klass)
        # test parameter page name
        from supvisors.webutils import HOST_ADDRESS_PAGE
        self.assertEqual(HOST_ADDRESS_PAGE, self.view.page_name)

    def test_render(self):
        """ Test the render method. """
        with patch('supvisors.viewhandler.ViewHandler.render', return_value='default') as mocked_render:
            self.assertEqual('default', self.view.render())
            self.assertEqual([call(self.view)], mocked_render.call_args_list)

    def test_write_navigation(self):
        """ Test the write_navigation method. """
        with patch.object(self.view, 'write_nav') as mocked_nav:
            mocked_root = Mock()
            self.view.write_navigation(mocked_root)
            self.assertEqual([call(mocked_root, address='127.0.0.1')], mocked_nav.call_args_list)

    @patch('supvisors.viewsupstatus.simple_localtime', return_value='07:05:30')
    @patch('supvisors.viewsupstatus.SupvisorsAddressView.write_address_actions')
    @patch('supvisors.viewsupstatus.SupvisorsAddressView.write_periods')
    def test_write_header(self, mocked_periods, mocked_actions, mocked_time):
        """ Test the write_header method. """
        # set context (meant to be set through render)
        # build root structure
        mocked_mids = [Mock(attrib={}) for _ in range(4)]
        mocked_root = Mock(**{'findmeld.side_effect': mocked_mids * 2})
        # first call tests with not master
        mocked_status = Mock(remote_time=3600,
                             **{'state_string.return_value': 'running',
                                'loading.return_value': 12})
        self.view.supvisors.context.master = False
        self.view.supvisors.context.addresses['127.0.0.1'] = mocked_status
        self.view.write_header(mocked_root)
        self.assertEqual([call('address_mid'), call('state_mid'), call('percent_mid'), call('date_mid')],
                         mocked_root.findmeld.call_args_list)
        self.assertDictEqual({}, mocked_mids[0].attrib)
        self.assertEqual([call('127.0.0.1')], mocked_mids[0].content.call_args_list)
        self.assertEqual([call('running')], mocked_mids[1].content.call_args_list)
        self.assertEqual([call('12%')], mocked_mids[2].content.call_args_list)
        self.assertEqual([call('07:05:30')], mocked_mids[3].content.call_args_list)
        self.assertEqual([call(mocked_root)], mocked_periods.call_args_list)
        self.assertEqual([call(mocked_root)], mocked_actions.call_args_list)
        # reset mocks
        mocked_root.findmeld.reset_mock()
        mocked_periods.reset_mock()
        mocked_actions.reset_mock()
        for mocked_mid in mocked_mids:
            mocked_mid.content.reset_mock()
        # second call tests with master
        self.view.supvisors.context.master = True
        self.view.write_header(mocked_root)
        self.assertEqual([call('address_mid'), call('state_mid'), call('percent_mid'), call('date_mid')],
                         mocked_root.findmeld.call_args_list)
        self.assertDictEqual({'class': 'master'}, mocked_mids[0].attrib)
        self.assertEqual([call('127.0.0.1')], mocked_mids[0].content.call_args_list)
        self.assertEqual([call('running')], mocked_mids[1].content.call_args_list)
        self.assertEqual([call('12%')], mocked_mids[2].content.call_args_list)
        self.assertEqual([call('07:05:30')], mocked_mids[3].content.call_args_list)
        self.assertEqual([call(mocked_root)], mocked_periods.call_args_list)
        self.assertEqual([call(mocked_root)], mocked_actions.call_args_list)

    def test_write_address_actions(self):
        """ Test the write_address_actions method. """
        from supvisors.viewcontext import ACTION
        from supvisors.webutils import PROC_ADDRESS_PAGE, HOST_ADDRESS_PAGE
        # set context (meant to be set through render)
        self.view.view_ctx = Mock(**{'format_url.return_value': 'an url'})
        # build root structure
        mocked_view_mid = Mock(attrib={'class': ''})
        mocked_stop_mid = Mock(attrib={'class': ''})
        mocked_root = Mock(**{'findmeld.side_effect': [mocked_view_mid, mocked_stop_mid] * 2})
        # test call
        self.view.write_address_actions(mocked_root)
        self.assertEqual([call('view_a_mid'), call('stopall_a_mid')], mocked_root.findmeld.call_args_list)
        self.assertEqual([call('', PROC_ADDRESS_PAGE), call('', HOST_ADDRESS_PAGE, **{ACTION: 'stopall'})],
                         self.view.view_ctx.format_url.call_args_list)
        self.assertEqual([call(href='an url')], mocked_view_mid.attributes.call_args_list)
        self.assertEqual([call(href='an url')], mocked_stop_mid.attributes.call_args_list)
        # reset mocks
        mocked_root.findmeld.reset_mock()
        self.view.view_ctx.format_url.reset_mock()
        mocked_view_mid.attributes.reset_mock()
        mocked_stop_mid.attributes.reset_mock()
        # test call with PROC_ADDRESS_PAGE as self.page_name
        self.view.page_name = PROC_ADDRESS_PAGE
        self.view.write_address_actions(mocked_root)
        self.assertEqual([call('view_a_mid'), call('stopall_a_mid')], mocked_root.findmeld.call_args_list)
        self.assertEqual([call('', HOST_ADDRESS_PAGE),
                          call('', PROC_ADDRESS_PAGE, **{ACTION: 'stopall'})],
                         self.view.view_ctx.format_url.call_args_list)
        self.assertEqual([call(href='an url')], mocked_view_mid.attributes.call_args_list)
        self.assertEqual([call(href='an url')], mocked_stop_mid.attributes.call_args_list)

    def test_make_callback(self):
        """ Test the make_callback method. """
        # test restart
        with patch.object(self.view, 'restart_sup_action', return_value='restart') as mocked_action:
            self.assertEqual('restart', self.view.make_callback('namespec', 'restartsup'))
            self.assertEqual([call()], mocked_action.call_args_list)
        # test shutdown
        with patch.object(self.view, 'shutdown_sup_action', return_value='shutdown') as mocked_action:
            self.assertEqual('shutdown', self.view.make_callback('namespec', 'shutdownsup'))
            self.assertEqual([call()], mocked_action.call_args_list)
        # test restart
        with patch('supervisor.web.StatusView.make_callback', return_value='default') as mocked_action:
            self.assertEqual('default', self.view.make_callback('namespec', 'other'))
            self.assertEqual([call(self.view, 'namespec', 'other')], mocked_action.call_args_list)

    @patch('supvisors.viewsupstatus.delayed_warn', return_value='delayed warn')
    def test_restart_sup_action(self, mocked_warn):
        """ Test the restart_sup_action method. """
        with patch.object(self.view.supvisors.zmq.pusher, 'send_restart') as mocked_pusher:
            self.assertEqual('delayed warn', self.view.restart_sup_action())
            self.assertEqual([call('127.0.0.1')], mocked_pusher.call_args_list)

    @patch('supvisors.viewsupstatus.delayed_warn', return_value='delayed warn')
    def test_shutdown_sup_action(self, mocked_warn):
        """ Test the shutdown_sup_action method. """
        with patch.object(self.view.supvisors.zmq.pusher, 'send_shutdown') as mocked_pusher:
            self.assertEqual('delayed warn', self.view.shutdown_sup_action())
            self.assertEqual([call('127.0.0.1')], mocked_pusher.call_args_list)


def test_suite():
    return unittest.findTestCases(sys.modules[__name__])


if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
