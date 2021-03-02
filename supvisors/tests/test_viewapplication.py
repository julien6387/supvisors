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

from unittest.mock import call, patch, Mock
from supervisor.http import NOT_DONE_YET
from supervisor.web import MeldView
from supervisor.xmlrpc import RPCError

from supvisors.tests.base import DummyHttpContext


class ViewApplicationTest(unittest.TestCase):
    """ Test case for the ApplicationView class of the viewapplication
    module. """

    def setUp(self):
        """ Create the instance to be tested. """
        from supvisors.viewapplication import ApplicationView
        self.view = ApplicationView(DummyHttpContext('ui/application.html'))
        # unit test feature to print all discrepancies
        self.maxDiff = None

    def test_init(self):
        """ Test the values set at construction. """
        from supvisors.viewhandler import ViewHandler
        # create instance
        self.assertIsInstance(self.view, ViewHandler)
        self.assertIsInstance(self.view, MeldView)
        self.assertEqual('', self.view.application_name)
        self.assertIsNone(self.view.application)

    @patch('supvisors.viewapplication.error_message', return_value='an error')
    @patch('supvisors.viewhandler.ViewHandler.handle_parameters')
    def test_handle_parameters(self, mocked_handle, mocked_message):
        """ Test the handle_parameters method. """
        from supvisors.viewcontext import APPLI
        # patch context
        self.view.view_ctx = Mock(parameters={APPLI: None})
        # test with no application selected
        self.view.handle_parameters()
        self.assertEqual([call(self.view)], mocked_handle.call_args_list)
        self.assertIsNone(self.view.application)
        self.assertEqual([call('an error')],
                         self.view.view_ctx.message.call_args_list)
        mocked_handle.reset_mock()
        self.view.view_ctx.message.reset_mock()
        # test with application selected
        self.view.view_ctx = Mock(parameters={APPLI: 'dummy_appli'})
        self.view.sup_ctx.applications['dummy_appli'] = 'dummy_appli'
        self.view.handle_parameters()
        self.assertEqual([call(self.view)], mocked_handle.call_args_list)
        self.assertEqual('dummy_appli', self.view.application)
        self.assertEqual([], self.view.view_ctx.message.call_args_list)

    @patch('supvisors.viewhandler.ViewHandler.write_nav')
    def test_write_navigation(self, mocked_handle):
        """ Test the write_navigation method. """
        self.view.application_name = 'dummy_appli'
        # test with no application selected
        self.view.write_navigation('root')
        self.assertEqual([call('root', appli='dummy_appli')],
                         mocked_handle.call_args_list)

    @patch('supvisors.viewapplication.ApplicationView.write_application_actions')
    @patch('supvisors.viewhandler.ViewHandler.write_periods')
    @patch('supvisors.viewapplication.ApplicationView.write_starting_strategy')
    def test_write_header(self, mocked_strategy, mocked_period, mocked_action):
        """ Test the write_header method. """
        self.view.application_name = 'dummy_appli'
        self.view.application = Mock(**{'state_string.return_value': 'stopped',
                                        'running.return_value': False})
        # patch the meld elements
        led_mid = Mock(attrib={'class': ''})
        state_mid = Mock()
        application_mid = Mock()
        mocked_root = Mock(**{'findmeld.side_effect': [application_mid,
                                                       state_mid,
                                                       led_mid] * 4})
        # test call with stopped application
        self.view.write_header(mocked_root)
        self.assertEqual([call('dummy_appli')],
                         application_mid.content.call_args_list)
        self.assertEqual([call('stopped')],
                         state_mid.content.call_args_list)
        self.assertEqual('status_empty', led_mid.attrib['class'])
        self.assertEqual([call(mocked_root)], mocked_strategy.call_args_list)
        self.assertEqual([call(mocked_root)], mocked_strategy.call_args_list)
        self.assertEqual([call(mocked_root)], mocked_action.call_args_list)
        application_mid.reset_mock()
        state_mid.reset_mock()
        mocked_strategy.reset_mock()
        mocked_period.reset_mock()
        mocked_action.reset_mock()
        # test call with running application and no failure
        self.view.application = Mock(major_failure=False,
                                     minor_failure=False,
                                     **{'state_string.return_value': 'starting',
                                        'running.return_value': True})
        self.view.write_header(mocked_root)
        self.assertEqual([call('dummy_appli')],
                         application_mid.content.call_args_list)
        self.assertEqual([call('starting')],
                         state_mid.content.call_args_list)
        self.assertEqual('status_green', led_mid.attrib['class'])
        self.assertEqual([call(mocked_root)], mocked_strategy.call_args_list)
        self.assertEqual([call(mocked_root)], mocked_strategy.call_args_list)
        self.assertEqual([call(mocked_root)], mocked_action.call_args_list)
        application_mid.reset_mock()
        state_mid.reset_mock()
        mocked_strategy.reset_mock()
        mocked_period.reset_mock()
        mocked_action.reset_mock()
        # test call with running application and minor failure
        self.view.application.minor_failure = True
        self.view.write_header(mocked_root)
        self.assertEqual([call('dummy_appli')],
                         application_mid.content.call_args_list)
        self.assertEqual([call('starting')],
                         state_mid.content.call_args_list)
        self.assertEqual('status_yellow', led_mid.attrib['class'])
        self.assertEqual([call(mocked_root)], mocked_strategy.call_args_list)
        self.assertEqual([call(mocked_root)], mocked_strategy.call_args_list)
        self.assertEqual([call(mocked_root)], mocked_action.call_args_list)
        application_mid.reset_mock()
        state_mid.reset_mock()
        mocked_strategy.reset_mock()
        mocked_period.reset_mock()
        mocked_action.reset_mock()
        # test call with running application and major failure
        self.view.application.major_failure = True
        self.view.write_header(mocked_root)
        self.assertEqual([call('dummy_appli')],
                         application_mid.content.call_args_list)
        self.assertEqual([call('starting')],
                         state_mid.content.call_args_list)
        self.assertEqual('status_red', led_mid.attrib['class'])
        self.assertEqual([call(mocked_root)], mocked_strategy.call_args_list)
        self.assertEqual([call(mocked_root)], mocked_strategy.call_args_list)
        self.assertEqual([call(mocked_root)], mocked_action.call_args_list)

    def test_write_starting_strategy(self):
        """ Test the write_starting_strategy method. """
        from supvisors.ttypes import StartingStrategies
        from supvisors.viewcontext import STRATEGY
        # patch the view context
        self.view.view_ctx = Mock(parameters={STRATEGY: 'CONFIG'}, **{'format_url.return_value': 'an url'})
        # patch the meld elements
        strategy_mids = [Mock(attrib={'class': ''}) for _ in StartingStrategies.values()]
        mocked_root = Mock(**{'findmeld.side_effect': strategy_mids * len(strategy_mids)})
        # test all strategies in loop
        for index, strategy in enumerate(StartingStrategies.strings()):
            self.view.view_ctx.parameters[STRATEGY] = strategy
            self.view.write_starting_strategy(mocked_root)
            # other strategy_mids are not selected
            for idx in range(len(strategy_mids)):
                if idx == index:
                    # strategy_mid at same index is selected
                    self.assertEqual('button off active', strategy_mids[idx].attrib['class'])
                    self.assertEqual([], strategy_mids[idx].attributes.call_args_list)
                else:
                    self.assertEqual('', strategy_mids[idx].attrib['class'])
                    self.assertEqual([call(href='an url')], strategy_mids[idx].attributes.call_args_list)
                # reset mocks
                strategy_mids[idx].attrib['class'] = ''
                strategy_mids[idx].attributes.reset_mock()

    def test_write_application_actions(self):
        """ Test the write_application_actions method. """
        from supvisors.webutils import APPLICATION_PAGE
        # patch the view context
        self.view.view_ctx = Mock(**{'format_url.side_effect': ['a start url', 'a stop url', 'a restart url']})
        # patch the meld elements
        actions_mid = (Mock(), Mock(), Mock())
        mocked_root = Mock(**{'findmeld.side_effect': actions_mid})
        # test call
        self.view.write_application_actions(mocked_root)
        self.assertEqual([call('', APPLICATION_PAGE, action='startapp'),
                          call('', APPLICATION_PAGE, action='stopapp'),
                          call('', APPLICATION_PAGE, action='restartapp')],
                         self.view.view_ctx.format_url.call_args_list)
        self.assertEqual([call(href='a start url')],
                         actions_mid[0].attributes.call_args_list)
        self.assertEqual([call(href='a stop url')],
                         actions_mid[1].attributes.call_args_list)
        self.assertEqual([call(href='a restart url')],
                         actions_mid[2].attributes.call_args_list)

    @patch('supvisors.viewhandler.ViewHandler.write_process_statistics')
    @patch('supvisors.viewapplication.ApplicationView.write_process_table')
    @patch('supvisors.viewapplication.ApplicationView.get_process_data',
           side_effect=([{'namespec': 'dummy'}], [{'namespec': 'dummy'}], [{'namespec': 'dummy'}],
                        [{'namespec': 'dummy_proc'}], [{'namespec': 'dummy_proc'}]))
    def test_write_contents(self, mocked_data, mocked_table, mocked_stats):
        """ Test the write_contents method. """
        from supvisors.viewcontext import PROCESS
        self.view.application_name = 'dummy_appli'
        # patch context
        self.view.view_ctx = Mock(parameters={PROCESS: None},
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
        # test call with process selected but belonging to another application
        self.view.view_ctx.parameters[PROCESS] = 'dummy_proc'
        self.view.view_ctx.get_process_status.return_value = Mock(application_name='dumb_appli')
        self.view.write_contents(mocked_root)
        self.assertEqual([call()], mocked_data.call_args_list)
        self.assertEqual([call(mocked_root, [{'namespec': 'dummy'}])], mocked_table.call_args_list)
        self.assertEqual('', self.view.view_ctx.parameters[PROCESS])
        self.assertEqual([call(mocked_root, {})], mocked_stats.call_args_list)
        mocked_data.reset_mock()
        mocked_table.reset_mock()
        mocked_stats.reset_mock()
        # test call with process selected and belonging to the application but stopped
        self.view.view_ctx.parameters[PROCESS] = 'dummy_proc'
        self.view.view_ctx.get_process_status.return_value = Mock(application_name='dummy_appli',
                                                                  **{'stopped.return_value': True})
        self.view.write_contents(mocked_root)
        self.assertEqual([call()], mocked_data.call_args_list)
        self.assertEqual([call(mocked_root, [{'namespec': 'dummy_proc'}])], mocked_table.call_args_list)
        self.assertEqual('', self.view.view_ctx.parameters[PROCESS])
        self.assertEqual([call(mocked_root, {})], mocked_stats.call_args_list)
        mocked_data.reset_mock()
        mocked_table.reset_mock()
        mocked_stats.reset_mock()
        # test call with process selected and belonging to the application and running
        self.view.view_ctx.parameters[PROCESS] = 'dummy_proc'
        self.view.view_ctx.get_process_status.return_value = Mock(application_name='dummy_appli',
                                                                  **{'stopped.return_value': False})
        self.view.write_contents(mocked_root)
        self.assertEqual([call()], mocked_data.call_args_list)
        self.assertEqual([call(mocked_root, [{'namespec': 'dummy_proc'}])], mocked_table.call_args_list)
        self.assertEqual('dummy_proc', self.view.view_ctx.parameters[PROCESS])
        self.assertEqual([call(mocked_root, {'namespec': 'dummy_proc'})], mocked_stats.call_args_list)

    @patch('supvisors.viewhandler.ViewHandler.sort_processes_by_config',
           return_value=['process_2', 'process_1'])
    def test_get_process_data(self, mocked_sort):
        """ Test the get_process_data method. """
        # patch the selected application
        process_1 = Mock(application_name='appli_1',
                         process_name='process_1',
                         addresses=set(),
                         state='stopped',
                         rules=Mock(expected_loading=20),
                         **{'namespec.return_value': 'namespec_1',
                            'state_string.return_value': 'stopped'})
        process_2 = Mock(application_name='appli_2',
                         process_name='process_2',
                         addresses=['10.0.0.1', '10.0.0.3'],  # should be a set but hard to test afterwards
                         state='running',
                         rules=Mock(expected_loading=1),
                         **{'namespec.return_value': 'namespec_2',
                            'state_string.return_value': 'running'})
        self.view.application = Mock(processes={process_1.process_name: process_1,
                                                process_2.process_name: process_2})
        # patch context
        mocked_stats = Mock()
        self.view.view_ctx = Mock(**{'get_process_stats.return_value': (4, mocked_stats),
                                     'get_process_last_desc.return_value': ('10.0.0.1', 'something')})
        # test call
        self.assertEqual(self.view.get_process_data(), ['process_2', 'process_1'])
        data1 = {'application_name': 'appli_1',
                 'process_name': 'process_1',
                 'namespec': 'namespec_1',
                 'address': '10.0.0.1',
                 'statename': 'stopped',
                 'statecode': 'stopped',
                 'running_list': [],
                 'description': 'something',
                 'loading': 20,
                 'nb_cores': 4,
                 'proc_stats': mocked_stats}
        data2 = {'application_name': 'appli_2',
                 'process_name': 'process_2',
                 'namespec': 'namespec_2',
                 'address': '10.0.0.1',
                 'running_list': ['10.0.0.1', '10.0.0.3'],
                 'description': 'something',
                 'statename': 'running',
                 'statecode': 'running',
                 'loading': 1,
                 'nb_cores': 4,
                 'proc_stats': mocked_stats}
        self.assertEqual(1, mocked_sort.call_count)
        self.assertEqual(2, len(mocked_sort.call_args_list[0]))
        # access to internal call data
        call_data = mocked_sort.call_args_list[0][0][0]
        self.assertDictEqual(data1, call_data[0])
        self.assertDictEqual(data2, call_data[1])

    def test_write_process(self):
        """ Test the write_process method. """
        from supvisors.webutils import PROC_ADDRESS_PAGE, TAIL_PAGE
        # create a process-like dict
        info = {'process_name': 'proc1',
                'namespec': 'dummy_appli:dummy_proc',
                'running_list': [],
                'address': '10.0.0.2'}
        # patch the view context
        self.view.view_ctx = Mock(**{'format_url.return_value': 'an url'})
        # patch the meld elements
        name_mid = Mock()
        running_ul_mid = Mock()
        running_a_mid = Mock(attrib={'class': 'button'})
        running_li_elt = Mock(**{'findmeld.return_value': running_a_mid})
        running_li_mid = Mock(**{'repeat.return_value': [(running_li_elt, '10.0.0.1')]})
        tr_elt = Mock(**{'findmeld.side_effect': [name_mid, running_ul_mid, name_mid, running_li_mid]})
        # test call with stopped process
        self.view.write_process(tr_elt, info)
        self.assertEqual([call('name_a_mid'), call('running_ul_mid')], tr_elt.findmeld.call_args_list)
        self.assertEqual([call('proc1')], name_mid.content.call_args_list)
        self.assertEqual([call(href='an url')], name_mid.attributes.call_args_list)
        self.assertEqual([call('10.0.0.2', TAIL_PAGE, processname=info['namespec'])],
                         self.view.view_ctx.format_url.call_args_list)
        self.assertEqual([call('')], running_ul_mid.replace.call_args_list)
        self.assertEqual([], running_a_mid.attributes.call_args_list)
        self.assertEqual([], running_a_mid.content.call_args_list)
        # reset mock elements
        name_mid.reset_mock()
        self.view.view_ctx.format_url.reset_mock()
        running_ul_mid.replace.reset_mock()
        # test call with running process
        info['running_list'] = {'10.0.0.1'}
        info['address'] = '10.0.0.1'
        self.view.write_process(tr_elt, info)
        self.assertEqual([call('name_a_mid'), call('running_ul_mid'), call('name_a_mid'), call('running_li_mid')],
                         tr_elt.findmeld.call_args_list)
        self.assertEqual([call('proc1')], name_mid.content.call_args_list)
        self.assertEqual([call(href='an url')], name_mid.attributes.call_args_list)
        self.assertEqual([call('10.0.0.1', TAIL_PAGE, processname=info['namespec']),
                          call('10.0.0.1', PROC_ADDRESS_PAGE)],
                         self.view.view_ctx.format_url.call_args_list)
        self.assertEqual([call(href='an url')], name_mid.attributes.call_args_list)
        self.assertEqual([call('proc1')], name_mid.content.call_args_list)
        self.assertEqual([], running_ul_mid.replace.call_args_list)
        self.assertEqual([call(href='an url')], running_a_mid.attributes.call_args_list)
        self.assertEqual([call('10.0.0.1')], running_a_mid.content.call_args_list)

    @patch('supvisors.viewapplication.ApplicationView.write_process')
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

    @patch('supvisors.viewapplication.delayed_error', return_value='Delayed')
    @patch('supvisors.viewapplication.ApplicationView.clearlog_process_action',
           return_value='Clear process logs')
    @patch('supvisors.viewapplication.ApplicationView.restart_process_action',
           return_value='Restart process')
    @patch('supvisors.viewapplication.ApplicationView.stop_process_action',
           return_value='Stop process')
    @patch('supvisors.viewapplication.ApplicationView.start_process_action',
           return_value='Start process')
    @patch('supvisors.viewapplication.ApplicationView.restart_application_action',
           return_value='Restart application')
    @patch('supvisors.viewapplication.ApplicationView.stop_application_action',
           return_value='Stop application')
    @patch('supvisors.viewapplication.ApplicationView.start_application_action',
           return_value='Start application')
    @patch('supvisors.viewapplication.ApplicationView.refresh_action',
           return_value='Refresh')
    def test_make_callback(self, mocked_refresh, mocked_start_app, mocked_stop_app,
                           mocked_restart_app, mocked_start_proc, mocked_stop_proc,
                           mocked_restart_proc, mocked_clear_proc, mocked_delayed):
        """ Test the make_callback method. """
        from supvisors.ttypes import StartingStrategies
        from supvisors.viewcontext import STRATEGY
        # patch view context
        self.view.view_ctx = Mock(parameters={STRATEGY: 'LOCAL'},
                                  **{'get_process_status.return_value': None})
        # test calls for different actions
        self.assertEqual('Refresh', self.view.make_callback('', 'refresh'))
        self.assertEqual('Start application', self.view.make_callback('', 'startapp'))
        self.assertEqual([call(StartingStrategies.LOCAL)], mocked_start_app.call_args_list)
        self.assertEqual('Stop application', self.view.make_callback('', 'stopapp'))
        self.assertEqual([call()], mocked_stop_app.call_args_list)
        self.assertEqual('Restart application', self.view.make_callback('', 'restartapp'))
        self.assertEqual([call(StartingStrategies.LOCAL)], mocked_restart_app.call_args_list)
        self.assertEqual('Delayed', self.view.make_callback('dummy', 'anything'))
        # change view context for the remaining actions
        self.view.view_ctx.get_process_status.return_value = 'None'
        # test start process
        self.assertEqual('Start process', self.view.make_callback('dummy', 'start'))
        self.assertEqual([call(StartingStrategies.LOCAL, 'dummy')], mocked_start_proc.call_args_list)
        # test stop process
        self.assertEqual('Stop process', self.view.make_callback('dummy', 'stop'))
        self.assertEqual([call('dummy')], mocked_stop_proc.call_args_list)
        # test restart process
        self.assertEqual('Restart process', self.view.make_callback('dummy', 'restart'))
        self.assertEqual([call(StartingStrategies.LOCAL, 'dummy')], mocked_restart_proc.call_args_list)
        # test clear logs process
        self.assertEqual('Clear process logs', self.view.make_callback('dummy', 'clearlog'))
        self.assertEqual([call('dummy')], mocked_clear_proc.call_args_list)

    @patch('supvisors.viewapplication.delayed_info', return_value='Delayed')
    def test_refresh_action(self, mocked_delayed):
        """ Test the refresh_action method. """
        self.assertEqual('Delayed', self.view.refresh_action())
        self.assertEqual([call('Page refreshed')], mocked_delayed.call_args_list)


class ViewApplicationActionTest(unittest.TestCase):
    """ Test case for the start/stop methods of the ApplicationView class of the viewapplication module. """

    def setUp(self):
        """ Create a common context and apply common patches. """
        from supvisors.viewapplication import ApplicationView
        self.view = ApplicationView(DummyHttpContext('ui/application.html'))
        # add the common patches
        self.patches = [patch('supvisors.viewapplication.delayed_error', return_value='Delay err'),
                        patch('supvisors.viewapplication.delayed_warn', return_value='Delay warn'),
                        patch('supvisors.viewapplication.delayed_info', return_value='Delay info'),
                        patch('supvisors.viewapplication.error_message', return_value='Msg err'),
                        patch('supvisors.viewapplication.warn_message', return_value='Msg warn'),
                        patch('supvisors.viewapplication.info_message', return_value='Msg info')]
        self.mocked = [p.start() for p in self.patches]

    def tearDown(self):
        """ Remove patches. """
        [p.stop() for p in self.patches]

    def test_start_application_action(self):
        """ Test the start_application_action method. """
        self.check_start_action('start_application', 'start_application_action')

    def test_stop_application_action(self):
        """ Test the stop_application_action method. """
        self.check_stop_action('stop_application', 'stop_application_action')

    def test_restart_application_action(self):
        """ Test the restart_application_action method. """
        self.check_start_action('restart_application', 'restart_application_action')

    def test_start_process_action(self):
        """ Test the start_process_action method. """
        self.check_start_action('start_process', 'start_process_action', 'dummy_proc')

    def test_stop_process_action(self):
        """ Test the stop_process_action method. """
        self.check_stop_action('stop_process', 'stop_process_action', 'dummy_proc')

    def test_restart_process_action(self):
        """ Test the restart_process_action method. """
        self.check_start_action('restart_process', 'restart_process_action', 'dummy_proc')

    def check_start_action(self, rpc_name, action_name, *args):
        """ Test the method named action_name. """
        # get methods involved
        rpc_call = getattr(self.view.info_source.supvisors_rpc_interface, rpc_name)
        action = getattr(self.view, action_name)
        # test call with error on main RPC call
        rpc_call.side_effect = RPCError('failed RPC')
        self.assertEqual('Delay err', action('strategy', *args))
        # test call with direct result (application started)
        rpc_call.side_effect = None
        rpc_call.return_value = True
        self.assertEqual('Delay info', action('strategy', *args))
        # test call with direct result (application NOT started)
        rpc_call.return_value = False
        self.assertEqual('Delay warn', action('strategy', *args))
        # test call with indirect result leading to internal RPC error
        rpc_call.return_value = lambda: (_ for _ in ()).throw(RPCError(''))
        result = action('strategy', *args)
        self.assertTrue(callable(result))
        self.assertEqual('Msg err', result())
        # test call with indirect result leading to unfinished job
        rpc_call.return_value = lambda: NOT_DONE_YET
        result = action('strategy', *args)
        self.assertTrue(callable(result))
        self.assertIs(NOT_DONE_YET, result())
        # test call with indirect result leading to failure
        rpc_call.return_value = lambda: False
        result = action('strategy', *args)
        self.assertTrue(callable(result))
        self.assertEqual('Msg warn', result())
        # test call with indirect result leading to success
        rpc_call.return_value = lambda: True
        result = action('strategy', *args)
        self.assertTrue(callable(result))
        self.assertEqual('Msg info', result())

    def check_stop_action(self, rpc_name, action_name, *args):
        """ Test the stop-like method named action_name. """
        # get methods involved
        rpc_call = getattr(self.view.info_source.supvisors_rpc_interface, rpc_name)
        action = getattr(self.view, action_name)
        # test call with error on main RPC call
        rpc_call.side_effect = RPCError('failed RPC')
        self.assertEqual('Delay err', action(*args))
        # test call with direct result (application started)
        rpc_call.side_effect = None
        rpc_call.return_value = True
        self.assertEqual('Delay info', action(*args))
        # test call with direct result (application NOT started)
        rpc_call.return_value = False
        self.assertEqual('Delay warn', action(*args))
        # test call with indirect result leading to internal RPC error
        rpc_call.return_value = lambda: (_ for _ in ()).throw(RPCError(''))
        result = action(*args)
        self.assertTrue(callable(result))
        self.assertEqual('Msg err', result())
        # test call with indirect result leading to unfinished job
        rpc_call.return_value = lambda: NOT_DONE_YET
        result = action(*args)
        self.assertTrue(callable(result))
        self.assertIs(NOT_DONE_YET, result())
        # test call with indirect result leading to success
        rpc_call.return_value = lambda: True
        result = action(*args)
        self.assertTrue(callable(result))
        self.assertEqual('Msg info', result())

    def test_clearlog_process_action(self):
        """ Test the clearlog_process_action method. """
        # get rpc involved (mock)
        rpc_call = self.view.info_source.supervisor_rpc_interface.clearProcessLogs
        # test call with error on main RPC call
        rpc_call.side_effect = RPCError(777, 'failed RPC')
        self.assertEqual('Delay err', self.view.clearlog_process_action('namespec'))
        # test call with direct result (application started)
        rpc_call.side_effect = None
        self.assertEqual('Delay info', self.view.clearlog_process_action('namespec'))


def test_suite():
    return unittest.findTestCases(sys.modules[__name__])


if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
