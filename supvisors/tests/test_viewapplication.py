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

import pytest

from unittest.mock import call, patch, Mock

from supervisor.http import NOT_DONE_YET
from supervisor.web import MeldView
from supervisor.xmlrpc import RPCError

from supvisors.ttypes import ApplicationStates, StartingStrategies
from supvisors.viewapplication import ApplicationView
from supvisors.viewcontext import APPLI, PROCESS, STRATEGY
from supvisors.viewhandler import ViewHandler
from supvisors.webutils import APPLICATION_PAGE

from .base import DummyHttpContext


@pytest.fixture
def view():
    """ Fixture for the instance to test. """
    return ApplicationView(DummyHttpContext('ui/application.html'))


def test_init(view):
    """ Test the values set at construction. """
    # create instance
    assert isinstance(view, ViewHandler)
    assert isinstance(view, MeldView)
    assert view.application_name == ''
    assert view.application is None


def test_handle_parameters(mocker, view):
    """ Test the handle_parameters method. """
    mocked_message = mocker.patch('supvisors.viewapplication.error_message', return_value='an error')
    mocked_handle = mocker.patch('supvisors.viewhandler.ViewHandler.handle_parameters')
    # patch context
    view.view_ctx = Mock(parameters={APPLI: None})
    # test with no application selected
    view.handle_parameters()
    assert mocked_handle.call_args_list == [call(view)]
    assert view.application is None
    assert view.view_ctx.message.call_args_list == [call('an error')]
    mocked_handle.reset_mock()
    view.view_ctx.message.reset_mock()
    # test with application selected
    view.view_ctx = Mock(parameters={APPLI: 'dummy_appli'})
    view.sup_ctx.applications['dummy_appli'] = 'dummy_appli'
    view.handle_parameters()
    assert mocked_handle.call_args_list == [call(view)]
    assert view.application == 'dummy_appli'
    assert view.view_ctx.message.call_args_list == []


def test_write_navigation(mocker, view):
    """ Test the write_navigation method. """
    mocked_handle = mocker.patch('supvisors.viewhandler.ViewHandler.write_nav')
    view.application_name = 'dummy_appli'
    # test with no application selected
    view.write_navigation('root')
    assert mocked_handle.call_args_list == [call('root', appli='dummy_appli')]


def test_write_header(mocker, view):
    """ Test the write_header method. """
    mocked_action = mocker.patch('supvisors.viewapplication.ApplicationView.write_application_actions')
    mocked_period = mocker.patch('supvisors.viewhandler.ViewHandler.write_periods')
    mocked_strategy = mocker.patch('supvisors.viewapplication.ApplicationView.write_starting_strategy')
    view.application_name = 'dummy_appli'
    view.application = Mock(state=ApplicationStates.STOPPED, major_failure=False, minor_failure=False,
                            **{'running.return_value': False})
    # patch the meld elements
    led_mid = Mock(attrib={'class': ''})
    state_mid = Mock()
    application_mid = Mock()
    mocked_root = Mock(**{'findmeld.side_effect': [application_mid, state_mid, led_mid] * 4})
    # test call with stopped application
    view.write_header(mocked_root)
    assert application_mid.content.call_args_list == [call('dummy_appli')]
    assert state_mid.content.call_args_list == [call('STOPPED')]
    assert led_mid.attrib['class'] == 'status_empty'
    assert mocked_strategy.call_args_list == [call(mocked_root)]
    assert mocked_strategy.call_args_list == [call(mocked_root)]
    assert mocked_action.call_args_list == [call(mocked_root)]
    application_mid.reset_mock()
    state_mid.reset_mock()
    mocked_strategy.reset_mock()
    mocked_period.reset_mock()
    mocked_action.reset_mock()
    # test call with running application and no failure
    view.application = Mock(state=ApplicationStates.STARTING, major_failure=False, minor_failure=False,
                            **{'running.return_value': True})
    view.write_header(mocked_root)
    assert application_mid.content.call_args_list == [call('dummy_appli')]
    assert state_mid.content.call_args_list == [call('STARTING')]
    assert led_mid.attrib['class'] == 'status_green'
    assert mocked_strategy.call_args_list == [call(mocked_root)]
    assert mocked_strategy.call_args_list == [call(mocked_root)]
    assert mocked_action.call_args_list == [call(mocked_root)]
    application_mid.reset_mock()
    state_mid.reset_mock()
    mocked_strategy.reset_mock()
    mocked_period.reset_mock()
    mocked_action.reset_mock()
    # test call with running application and minor failure
    view.application.minor_failure = True
    view.write_header(mocked_root)
    assert application_mid.content.call_args_list == [call('dummy_appli')]
    assert state_mid.content.call_args_list == [call('STARTING')]
    assert led_mid.attrib['class'] == 'status_yellow'
    assert mocked_strategy.call_args_list == [call(mocked_root)]
    assert mocked_strategy.call_args_list == [call(mocked_root)]
    assert mocked_action.call_args_list == [call(mocked_root)]
    application_mid.reset_mock()
    state_mid.reset_mock()
    mocked_strategy.reset_mock()
    mocked_period.reset_mock()
    mocked_action.reset_mock()
    # test call with running application and major failure
    view.application.major_failure = True
    view.write_header(mocked_root)
    assert application_mid.content.call_args_list == [call('dummy_appli')]
    assert state_mid.content.call_args_list == [call('STARTING')]
    assert led_mid.attrib['class'] == 'status_red'
    assert mocked_strategy.call_args_list == [call(mocked_root)]
    assert mocked_strategy.call_args_list == [call(mocked_root)]
    assert mocked_action.call_args_list == [call(mocked_root)]


def test_write_starting_strategy(view):
    """ Test the write_starting_strategy method. """
    # patch the view context
    view.view_ctx = Mock(parameters={STRATEGY: 'CONFIG'}, **{'format_url.return_value': 'an url'})
    # patch the meld elements
    strategy_mids = [Mock(attrib={'class': ''}) for _ in StartingStrategies]
    mocked_root = Mock(**{'findmeld.side_effect': strategy_mids * len(strategy_mids)})
    # test all strategies in loop
    for index, strategy in enumerate(StartingStrategies._member_names_):
        view.view_ctx.parameters[STRATEGY] = strategy
        view.write_starting_strategy(mocked_root)
        # other strategy_mids are not selected
        for idx in range(len(strategy_mids)):
            if idx == index:
                # strategy_mid at same index is selected
                assert strategy_mids[idx].attrib['class'] == 'button off active'
                assert strategy_mids[idx].attributes.call_args_list == []
            else:
                assert strategy_mids[idx].attrib['class'] == ''
                assert strategy_mids[idx].attributes.call_args_list == [call(href='an url')]
            # reset mocks
            strategy_mids[idx].attrib['class'] = ''
            strategy_mids[idx].attributes.reset_mock()


def test_write_application_actions(view):
    """ Test the write_application_actions method. """
    # patch the view context
    view.view_ctx = Mock(**{'format_url.side_effect': ['a start url', 'a stop url', 'a restart url']})
    # patch the meld elements
    actions_mid = (Mock(), Mock(), Mock())
    mocked_root = Mock(**{'findmeld.side_effect': actions_mid})
    # test call
    view.write_application_actions(mocked_root)
    assert view.view_ctx.format_url.call_args_list == [call('', APPLICATION_PAGE, action='startapp'),
                      call('', APPLICATION_PAGE, action='stopapp'),
                      call('', APPLICATION_PAGE, action='restartapp')]
    assert actions_mid[0].attributes.call_args_list == [call(href='a start url')]
    assert actions_mid[1].attributes.call_args_list == [call(href='a stop url')]
    assert actions_mid[2].attributes.call_args_list == [call(href='a restart url')]


def test_write_contents(mocker, view):
    """ Test the write_contents method. """
    mocked_stats = mocker.patch('supvisors.viewhandler.ViewHandler.write_process_statistics')
    mocked_table = mocker.patch('supvisors.viewapplication.ApplicationView.write_process_table')
    mocked_data = mocker.patch('supvisors.viewapplication.ApplicationView.get_process_data',
                               side_effect=([{'namespec': 'dummy'}], [{'namespec': 'dummy'}],
                                            [{'namespec': 'dummy'}], [{'namespec': 'dummy_proc'}],
                                            [{'namespec': 'dummy_proc'}]))
    view.application_name = 'dummy_appli'
    # patch context
    view.view_ctx = Mock(parameters={PROCESS: None}, **{'get_process_status.return_value': None})
    # patch the meld elements
    mocked_root = Mock()
    # test call with no process selected
    view.write_contents(mocked_root)
    assert mocked_data.call_args_list == [call()]
    assert mocked_table.call_args_list == [call(mocked_root, [{'namespec': 'dummy'}])]
    assert mocked_stats.call_args_list == [call(mocked_root, {})]
    mocked_data.reset_mock()
    mocked_table.reset_mock()
    mocked_stats.reset_mock()
    # test call with process selected and no corresponding status
    view.view_ctx.parameters[PROCESS] = 'dummy_proc'
    view.write_contents(mocked_root)
    assert mocked_data.call_args_list == [call()]
    assert mocked_table.call_args_list == [call(mocked_root, [{'namespec': 'dummy'}])]
    assert view.view_ctx.parameters[PROCESS] == ''
    assert mocked_stats.call_args_list == [call(mocked_root, {})]
    mocked_data.reset_mock()
    mocked_table.reset_mock()
    mocked_stats.reset_mock()
    # test call with process selected but belonging to another application
    view.view_ctx.parameters[PROCESS] = 'dummy_proc'
    view.view_ctx.get_process_status.return_value = Mock(application_name='dumb_appli')
    view.write_contents(mocked_root)
    assert mocked_data.call_args_list == [call()]
    assert mocked_table.call_args_list == [call(mocked_root, [{'namespec': 'dummy'}])]
    assert view.view_ctx.parameters[PROCESS] == ''
    assert mocked_stats.call_args_list == [call(mocked_root, {})]
    mocked_data.reset_mock()
    mocked_table.reset_mock()
    mocked_stats.reset_mock()
    # test call with process selected and belonging to the application but stopped
    view.view_ctx.parameters[PROCESS] = 'dummy_proc'
    view.view_ctx.get_process_status.return_value = Mock(application_name='dummy_appli',
                                                         **{'stopped.return_value': True})
    view.write_contents(mocked_root)
    assert mocked_data.call_args_list == [call()]
    assert mocked_table.call_args_list == [call(mocked_root, [{'namespec': 'dummy_proc'}])]
    assert view.view_ctx.parameters[PROCESS] == ''
    assert mocked_stats.call_args_list == [call(mocked_root, {})]
    mocked_data.reset_mock()
    mocked_table.reset_mock()
    mocked_stats.reset_mock()
    # test call with process selected and belonging to the application and running
    view.view_ctx.parameters[PROCESS] = 'dummy_proc'
    view.view_ctx.get_process_status.return_value = Mock(application_name='dummy_appli',
                                                         **{'stopped.return_value': False})
    view.write_contents(mocked_root)
    assert mocked_data.call_args_list == [call()]
    assert mocked_table.call_args_list == [call(mocked_root, [{'namespec': 'dummy_proc'}])]
    assert view.view_ctx.parameters[PROCESS] == 'dummy_proc'
    assert mocked_stats.call_args_list == [call(mocked_root, {'namespec': 'dummy_proc'})]


def test_get_process_last_desc(mocker, view):
    """ Test the ViewApplication.get_process_last_desc method. """
    # build common Mock
    mocked_process = Mock(**{'get_last_description.return_value': ('10.0.0.1', 'the latest comment')})
    view.view_ctx = Mock(**{'get_process_status.return_value': mocked_process})
    # test method return on non-running process
    assert view.get_process_last_desc('dummy_proc') == ('10.0.0.1', 'the latest comment')


def test_get_process_data(mocker, view):
    """ Test the ViewApplication.get_process_data method. """
    # patch the selected application
    process_1 = Mock(application_name='appli_1', process_name='process_1', namespec='namespec_1',
                     running_nodes=set(), state='stopped', rules=Mock(expected_load=20),
                     **{'state_string.return_value': 'stopped'})
    process_2 = Mock(application_name='appli_2', process_name='process_2', namespec='namespec_2',
                     running_nodes=['10.0.0.1', '10.0.0.3'],  # should be a set but hard to test afterwards
                     state='running', rules=Mock(expected_load=1),
                     **{'state_string.return_value': 'running'})
    view.application = Mock(processes={process_1.process_name: process_1, process_2.process_name: process_2})
    # patch context
    mocked_stats = Mock()
    view.view_ctx = Mock(**{'get_process_stats.return_value': (4, mocked_stats)})
    mocker.patch.object(view, 'get_process_last_desc', return_value=('10.0.0.1', 'something'))
    # test call
    data1 = {'application_name': 'appli_1', 'process_name': 'process_1', 'namespec': 'namespec_1',
             'node_name': '10.0.0.1', 'statename': 'stopped', 'statecode': 'stopped', 'gravity': 'stopped',
             'running_nodes': [], 'description': 'something',
             'expected_load': 20, 'nb_cores': 4, 'proc_stats': mocked_stats}
    data2 = {'application_name': 'appli_2', 'process_name': 'process_2', 'namespec': 'namespec_2',
             'node_name': '10.0.0.1', 'statename': 'running', 'statecode': 'running', 'gravity': 'running',
             'running_nodes': ['10.0.0.1', '10.0.0.3'], 'description': 'something',
             'expected_load': 1, 'nb_cores': 4, 'proc_stats': mocked_stats}
    assert view.get_process_data() == [data1, data2]


def test_write_process(view):
    """ Test the write_process method. """
    # create a process-like dict
    info = {'process_name': 'proc1', 'namespec': 'dummy_appli:dummy_proc',
            'running_nodes': [], 'node_name': '10.0.0.2'}
    # patch the view context
    view.view_ctx = Mock(**{'format_url.return_value': 'an url'})
    # patch the meld elements
    running_ul_mid = Mock()
    running_a_mid = Mock(attrib={'class': 'button'})
    running_li_elt = Mock(**{'findmeld.return_value': running_a_mid})
    running_li_mid = Mock(**{'repeat.return_value': [(running_li_elt, '10.0.0.1')]})
    tr_elt = Mock(**{'findmeld.side_effect': [running_ul_mid, running_li_mid]})
    # test call with stopped process
    view.write_process(tr_elt, info)
    assert tr_elt.findmeld.call_args_list == [call('running_ul_mid')]
    assert running_ul_mid.replace.call_args_list == [call('')]
    assert running_a_mid.attributes.call_args_list == []
    assert running_a_mid.content.call_args_list == []
    # reset mock elements
    view.view_ctx.format_url.reset_mock()
    running_ul_mid.replace.reset_mock()
    # test call with running process
    info['running_nodes'] = {'10.0.0.1'}
    info['node_name'] = '10.0.0.1'
    view.write_process(tr_elt, info)
    assert tr_elt.findmeld.call_args_list == [call('running_ul_mid'), call('running_li_mid')]
    assert running_ul_mid.replace.call_args_list == []
    assert running_a_mid.attributes.call_args_list == [call(href='an url')]
    assert running_a_mid.content.call_args_list == [call('10.0.0.1')]


def test_write_process_table(mocker, view):
    """ Test the write_process_table method. """
    mocked_process = mocker.patch('supvisors.viewapplication.ApplicationView.write_process')
    mocked_common = mocker.patch('supvisors.viewhandler.ViewHandler.write_common_process_status',
                                 side_effect=[True, False, False])
    # patch the meld elements
    table_mid = Mock()
    tr_elt_1 = Mock(attrib={'class': ''})
    tr_elt_2 = Mock(attrib={'class': ''})
    tr_elt_3 = Mock(attrib={'class': ''})
    tr_mid = Mock(**{'repeat.return_value': [(tr_elt_1, 'info_1'), (tr_elt_2, 'info_2'), (tr_elt_3, 'info_3')]})
    mocked_root = Mock(**{'findmeld.side_effect': [table_mid, tr_mid]})
    # test call with no data
    view.write_process_table(mocked_root, {})
    assert table_mid.replace.call_args_list == [call('No programs to manage')]
    assert mocked_common.replace.call_args_list == []
    assert mocked_process.replace.call_args_list == []
    assert tr_elt_1.attrib['class'] == ''
    assert tr_elt_2.attrib['class'] == ''
    assert tr_elt_3.attrib['class'] == ''
    table_mid.replace.reset_mock()
    # test call with data and line selected
    view.write_process_table(mocked_root, True)
    assert table_mid.replace.call_args_list == []
    assert mocked_common.call_args_list == [call(tr_elt_1, 'info_1'), call(tr_elt_2, 'info_2'),
                                            call(tr_elt_3, 'info_3')]
    assert mocked_process.call_args_list == [call(tr_elt_1, 'info_1'), call(tr_elt_2, 'info_2'),
                                             call(tr_elt_3, 'info_3')]
    assert tr_elt_1.attrib['class'] == 'brightened'
    assert tr_elt_2.attrib['class'] == 'shaded'
    assert tr_elt_3.attrib['class'] == 'brightened'


def test_make_callback(mocker, view):
    """ Test the make_callback method. """
    mocker.patch('supvisors.viewapplication.delayed_error', return_value='Delayed')
    mocked_clear_proc = mocker.patch.object(view, 'clearlog_process_action', return_value='Clear process logs')
    mocked_restart_proc = mocker.patch.object(view, 'restart_process_action', return_value='Restart process')
    mocked_stop_proc = mocker.patch.object(view, 'stop_process_action', return_value='Stop process')
    mocked_start_proc = mocker.patch.object(view, 'start_process_action', return_value='Start process')
    mocked_restart_app = mocker.patch.object(view, 'restart_application_action', return_value='Restart application')
    mocked_stop_app = mocker.patch.object(view, 'stop_application_action', return_value='Stop application')
    mocked_start_app = mocker.patch.object(view, 'start_application_action', return_value='Start application')
    mocker.patch.object(view, 'refresh_action', return_value='Refresh')
    # patch view context
    view.view_ctx = Mock(parameters={STRATEGY: 'LOCAL'}, **{'get_process_status.return_value': None})
    # test calls for different actions
    assert view.make_callback('', 'refresh') == 'Refresh'
    assert view.make_callback('', 'startapp') == 'Start application'
    assert mocked_start_app.call_args_list == [call(StartingStrategies.LOCAL)]
    assert view.make_callback('', 'stopapp') == 'Stop application'
    assert mocked_stop_app.call_args_list == [call()]
    assert view.make_callback('', 'restartapp') == 'Restart application'
    assert mocked_restart_app.call_args_list == [call(StartingStrategies.LOCAL)]
    assert view.make_callback('dummy', 'anything') == 'Delayed'
    # change view context for the remaining actions
    view.view_ctx.get_process_status.return_value = 'None'
    # test start process
    assert view.make_callback('dummy', 'start') == 'Start process'
    assert mocked_start_proc.call_args_list == [call(StartingStrategies.LOCAL, 'dummy')]
    # test stop process
    assert view.make_callback('dummy', 'stop') == 'Stop process'
    assert mocked_stop_proc.call_args_list == [call('dummy')]
    # test restart process
    assert view.make_callback('dummy', 'restart') == 'Restart process'
    assert mocked_restart_proc.call_args_list == [call(StartingStrategies.LOCAL, 'dummy')]
    # test clear logs process
    assert view.make_callback('dummy', 'clearlog') == 'Clear process logs'
    assert mocked_clear_proc.call_args_list == [call('dummy')]


def test_refresh_action(mocker, view):
    """ Test the refresh_action method. """
    mocked_delayed = mocker.patch('supvisors.viewapplication.delayed_info', return_value='Delayed')
    assert view.refresh_action() == 'Delayed'
    assert mocked_delayed.call_args_list == [call('Page refreshed')]


@pytest.fixture
def messages(mocker):
    """ Install patches on all message functions"""
    patches = [mocker.patch('supvisors.viewapplication.delayed_error', return_value='Delay err'),
               mocker.patch('supvisors.viewapplication.delayed_warn', return_value='Delay warn'),
               mocker.patch('supvisors.viewapplication.delayed_info', return_value='Delay info'),
               mocker.patch('supvisors.viewapplication.error_message', return_value='Msg err'),
               mocker.patch('supvisors.viewapplication.warn_message', return_value='Msg warn'),
               mocker.patch('supvisors.viewapplication.info_message', return_value='Msg info')]
    [p.start() for p in patches]
    yield
    [p.stop() for p in patches]


def check_start_action(view, rpc_name, action_name, *args):
    """ Test the method named action_name. """
    # get methods involved
    rpc_call = getattr(view.supvisors.info_source.supvisors_rpc_interface, rpc_name)
    action = getattr(view, action_name)
    # test call with error on main RPC call
    rpc_call.side_effect = RPCError('failed RPC')
    assert action('strategy', *args) == 'Delay err'
    # test call with direct result (application started)
    rpc_call.side_effect = None
    rpc_call.return_value = True
    assert action('strategy', *args) == 'Delay info'
    # test call with direct result (application NOT started)
    rpc_call.return_value = False
    assert action('strategy', *args) == 'Delay warn'
    # test call with indirect result leading to internal RPC error
    rpc_call.return_value = lambda: (_ for _ in ()).throw(RPCError(''))
    result = action('strategy', *args)
    assert callable(result)
    assert result() == 'Msg err'
    # test call with indirect result leading to unfinished job
    rpc_call.return_value = lambda: NOT_DONE_YET
    result = action('strategy', *args)
    assert callable(result)
    assert result() is NOT_DONE_YET
    # test call with indirect result leading to failure
    rpc_call.return_value = lambda: False
    result = action('strategy', *args)
    assert callable(result)
    assert result() == 'Msg warn'
    # test call with indirect result leading to success
    rpc_call.return_value = lambda: True
    result = action('strategy', *args)
    assert callable(result)
    assert result() == 'Msg info'


def test_start_application_action(view, messages):
    """ Test the start_application_action method. """
    check_start_action(view, 'start_application', 'start_application_action')


def test_restart_application_action(view, messages):
    """ Test the restart_application_action method. """
    check_start_action(view, 'restart_application', 'restart_application_action')


def test_start_process_action(view, messages):
    """ Test the start_process_action method. """
    check_start_action(view, 'start_process', 'start_process_action', 'dummy_proc')


def test_restart_process_action(view, messages):
    """ Test the restart_process_action method. """
    check_start_action(view, 'restart_process', 'restart_process_action', 'dummy_proc')


def check_stop_action(view, rpc_name, action_name, *args):
    """ Test the stop-like method named action_name. """
    # get methods involved
    rpc_call = getattr(view.supvisors.info_source.supvisors_rpc_interface, rpc_name)
    action = getattr(view, action_name)
    # test call with error on main RPC call
    rpc_call.side_effect = RPCError('failed RPC')
    assert action(*args) == 'Delay err'
    # test call with direct result (application started)
    rpc_call.side_effect = None
    rpc_call.return_value = True
    assert action(*args) == 'Delay info'
    # test call with direct result (application NOT started)
    rpc_call.return_value = False
    assert action(*args) == 'Delay warn'
    # test call with indirect result leading to internal RPC error
    rpc_call.return_value = lambda: (_ for _ in ()).throw(RPCError(''))
    result = action(*args)
    assert callable(result)
    assert result() == 'Msg err'
    # test call with indirect result leading to unfinished job
    rpc_call.return_value = lambda: NOT_DONE_YET
    result = action(*args)
    assert callable(result)
    assert result() is NOT_DONE_YET
    # test call with indirect result leading to success
    rpc_call.return_value = lambda: True
    result = action(*args)
    assert callable(result)
    assert result() == 'Msg info'


def test_stop_application_action(view, messages):
    """ Test the stop_application_action method. """
    check_stop_action(view, 'stop_application', 'stop_application_action')


def test_stop_process_action(view, messages):
    """ Test the stop_process_action method. """
    check_stop_action(view, 'stop_process', 'stop_process_action', 'dummy_proc')


def test_clearlog_process_action(view, messages):
    """ Test the clearlog_process_action method. """
    # get rpc involved (mock)
    rpc_call = view.supvisors.info_source.supervisor_rpc_interface.clearProcessLogs
    # test call with error on main RPC call
    rpc_call.side_effect = RPCError(777, 'failed RPC')
    assert view.clearlog_process_action('namespec') == 'Delay err'
    # test call with direct result (application started)
    rpc_call.side_effect = None
    assert view.clearlog_process_action('namespec') == 'Delay info'
