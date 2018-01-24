#!/usr/bin/python
#-*- coding: utf-8 -*-

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

from mock import call, patch, Mock, PropertyMock, DEFAULT
from random import shuffle

from supervisor.http import NOT_DONE_YET
from supervisor.states import SupervisorStates

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
        print mocked_meld.attrib
        self.assertEqual([call('supvisors_mid'), call('version_mid')],
                         mocked_root.findmeld.call_args_list)
        self.assertDictEqual({'class': 'blink'}, mocked_meld.attrib)

    def test_handle_parameters(self):
        """ Test the handle_parameters method. """
        from supvisors.viewcontext import ViewContext
        from supvisors.viewhandler import ViewHandler
        handler = ViewHandler(self.http_context, 'index.html')
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

    def test_write_nav_addresses(self):
        """ Test the write_nav_addresses method. """
        from supvisors.viewhandler import ViewHandler
        handler = ViewHandler(self.http_context, 'index.html')
        handler.write_nav_addresses(None, None)
        # TODO

    def test_write_nav_applications(self):
        """ Test the write_nav_applications method. """
        from supvisors.viewhandler import ViewHandler
        handler = ViewHandler(self.http_context, 'index.html')
        handler.write_nav_applications(None, None)
        # TODO

    def test_write_periods(self):
        """ Test the write_periods method. """
        from supvisors.viewhandler import ViewHandler
        handler = ViewHandler(self.http_context, 'index.html')
        handler.write_periods(None)
        # TODO

        """ Test the write_common_process_status method. """
        from supvisors.viewhandler import ViewHandler
        handler = ViewHandler(self.http_context, 'index.html')
        handler.write_common_process_status(None, None)
        # TODO

    def test_write_process_statistics(self):
        """ Test the write_process_statistics method. """
        from supvisors.viewhandler import ViewHandler
        handler = ViewHandler(self.http_context, 'index.html')
        handler.write_process_statistics(None)
        # TODO

    def test_handle_action(self):
        """ Test the handle_action method. """
        from supvisors.viewhandler import ViewHandler
        handler = ViewHandler(self.http_context, 'index.html')
        handler.handle_action()
        # TODO

    def test_get_process_stats(self):
        """ Test the get_process_stats method. """
        from supvisors.viewhandler import ViewHandler
        handler = ViewHandler(self.http_context, 'index.html')
        # test indirection
        with patch.object(handler.view_ctx, 'get_process_stats')\
         as mocked_stats:
            handler.get_process_stats('dummy_proc')
            self.assertEqual([call('dummy_proc')],
                             mocked_stats.call_args_list)

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
