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

from unittest.mock import call, Mock

import pytest
from supervisor.web import MeldView

from supvisors.ttypes import ApplicationStates
from supvisors.web.viewapplication import *
from .base import DummyHttpContext
from .conftest import create_element


@pytest.fixture
def view(supvisors):
    """ Fixture for the instance to test. """
    http_context = DummyHttpContext('ui/application.html')
    http_context.supervisord.supvisors = supvisors
    view = ApplicationView(http_context)
    view.view_ctx = Mock(parameters={}, **{'format_url.return_value': 'an url'})
    return view


def test_init(view):
    """ Test the values set at construction. """
    # create instance
    assert isinstance(view, ViewHandler)
    assert isinstance(view, MeldView)
    assert view.application_name == ''
    assert view.application is None


def test_handle_parameters(mocker, view):
    """ Test the handle_parameters method. """
    mocker.patch('supvisors.web.viewapplication.error_message', return_value='an error')
    mocked_handle = mocker.patch('supvisors.web.viewhandler.ViewHandler.handle_parameters')
    # patch context
    view.view_ctx.application_name = None
    # test with no application selected
    view.handle_parameters()
    assert mocked_handle.call_args_list == [call(view)]
    assert view.application is None
    assert view.view_ctx.store_message == 'an error'
    assert view.view_ctx.redirect
    mocked_handle.reset_mock()
    # test with application selected
    view.view_ctx = Mock(application_name='dummy_appli', store_message=None, redirect=False)
    view.sup_ctx.applications['dummy_appli'] = 'dummy_appli'
    view.handle_parameters()
    assert mocked_handle.call_args_list == [call(view)]
    assert view.application == 'dummy_appli'
    assert view.view_ctx.store_message is None
    assert not view.view_ctx.redirect


def test_write_navigation(mocker, view):
    """ Test the write_navigation method. """
    mocked_handle = mocker.patch('supvisors.web.viewhandler.ViewHandler.write_nav')
    view.application_name = 'dummy_appli'
    # test with no application selected
    view.write_navigation('root')
    assert mocked_handle.call_args_list == [call('root', appli='dummy_appli')]


def test_write_status(mocker, view):
    """ Test the write_status method. """
    view.application_name = 'dummy_appli'
    view.application = Mock(state=ApplicationStates.STOPPED, major_failure=False, minor_failure=False,
                            **{'running.return_value': False})
    # patch the meld elements
    led_mid = create_element()
    state_mid = create_element()
    application_mid = create_element()
    mocked_header = create_element({'application_mid': application_mid, 'state_mid': state_mid,
                                    'state_led_mid': led_mid})
    # test call with stopped application
    view.write_status(mocked_header)
    assert application_mid.content.call_args_list == [call('dummy_appli')]
    assert state_mid.content.call_args_list == [call('STOPPED')]
    assert led_mid.attrib['class'] == 'status_empty'
    mocked_header.reset_all()
    mocker.resetall()
    # test call with running application and no failure
    view.application = Mock(state=ApplicationStates.STARTING, major_failure=False, minor_failure=False,
                            **{'running.return_value': True})
    view.write_status(mocked_header)
    assert application_mid.content.call_args_list == [call('dummy_appli')]
    assert state_mid.content.call_args_list == [call('STARTING')]
    assert led_mid.attrib['class'] == 'status_green'
    mocked_header.reset_all()
    mocker.resetall()
    # test call with running application and minor failure
    view.application.minor_failure = True
    view.write_status(mocked_header)
    assert application_mid.content.call_args_list == [call('dummy_appli')]
    assert state_mid.content.call_args_list == [call('STARTING')]
    assert led_mid.attrib['class'] == 'status_yellow'
    mocked_header.reset_all()
    mocker.resetall()
    # test call with running application and major failure
    view.application.major_failure = True
    view.write_status(mocked_header)
    assert application_mid.content.call_args_list == [call('dummy_appli')]
    assert state_mid.content.call_args_list == [call('STARTING')]
    assert led_mid.attrib['class'] == 'status_red'


def test_write_options(mocker, view):
    """ Test the ApplicationView.test_write_options method. """
    mocked_strategy = mocker.patch('supvisors.web.viewapplication.ApplicationView.write_starting_strategy')
    mocked_period = mocker.patch('supvisors.web.viewhandler.ViewHandler.write_periods')
    period_div_mid = create_element()
    mocked_header = create_element({'period_div_mid': period_div_mid})
    # test with process statistics to be displayed
    assert view.has_process_statistics
    view.write_options(mocked_header)
    assert mocked_strategy.call_args_list == [call(mocked_header)]
    assert mocked_period.call_args_list == [call(mocked_header)]
    assert not mocked_header.findmeld.called
    assert not period_div_mid.replace.called
    mocker.resetall()
    # test with process statistics NOT to be displayed
    view.has_process_statistics = False
    view.write_options(mocked_header)
    assert mocked_strategy.call_args_list == [call(mocked_header)]
    assert not mocked_period.called
    assert mocked_header.findmeld.call_args_list == [call('period_div_mid')]
    assert period_div_mid.replace.call_args_list == [call('')]


def test_write_starting_strategy(view):
    """ Test the write_starting_strategy method. """
    # patch the view context
    view.view_ctx = Mock(strategy='CONFIG', **{'format_url.return_value': 'an url'})
    # create the xhtml structure
    strategy_button_mids, strategy_href_mids = {}, {}
    for strategy in StartingStrategies:
        # create hyperlink element
        href_elt = create_element()
        href_name = '%s_a_mid' % strategy.name.lower()
        strategy_href_mids[href_name] = href_elt
        # create button element
        button_elt = create_element({href_name: href_elt})
        button_name = '%s_div_mid' % strategy.name.lower()
        strategy_button_mids[button_name] = button_elt
    header_elt = create_element(strategy_button_mids)
    # test all strategies in loop
    for strategy in StartingStrategies:
        view.view_ctx.strategy = strategy
        view.write_starting_strategy(header_elt)
        # other strategy_mids are not selected
        for strategy2 in StartingStrategies:
            button_name = '%s_div_mid' % strategy2.name.lower()
            href_name = '%s_a_mid' % strategy2.name.lower()
            if strategy2.value == strategy.value:
                assert strategy_button_mids[button_name].attrib['class'] == 'off active'
                assert strategy_href_mids[href_name].attributes.call_args_list == []
            else:
                assert strategy_button_mids[button_name].attrib['class'] == 'on'
                assert strategy_href_mids[href_name].attributes.call_args_list == [call(href='an url')]
        header_elt.reset_all()


def test_write_actions(mocker, view):
    """ Test the write_actions method. """
    mocked_super = mocker.patch('supvisors.web.viewhandler.ViewHandler.write_actions')
    # patch the view context
    view.view_ctx = Mock(**{'format_url.side_effect': ['a start url', 'a stop url', 'a restart url']})
    # patch the meld elements
    startapp_a_mid = create_element()
    stopapp_a_mid = create_element()
    restartapp_a_mid = create_element()
    mocked_header = create_element({'startapp_a_mid': startapp_a_mid, 'stopapp_a_mid': stopapp_a_mid,
                                    'restartapp_a_mid': restartapp_a_mid})
    # test call
    view.write_actions(mocked_header)
    assert mocked_super.call_args_list == [call(mocked_header)]
    assert view.view_ctx.format_url.call_args_list == [call('', APPLICATION_PAGE, action='startapp'),
                                                       call('', APPLICATION_PAGE, action='stopapp'),
                                                       call('', APPLICATION_PAGE, action='restartapp')]
    assert startapp_a_mid.attributes.call_args_list == [call(href='a start url')]
    assert stopapp_a_mid.attributes.call_args_list == [call(href='a stop url')]
    assert restartapp_a_mid.attributes.call_args_list == [call(href='a restart url')]


def test_write_contents(mocker, view):
    """ Test the write_contents method. """
    mocked_stats = mocker.patch('supvisors.web.viewhandler.ViewHandler.write_process_statistics')
    mocked_table = mocker.patch('supvisors.web.viewapplication.ApplicationView.write_process_table')
    mocked_data = mocker.patch('supvisors.web.viewapplication.ApplicationView.get_process_data',
                               side_effect=([{'namespec': 'dummy'}],
                                            [{'namespec': 'dummy'}],
                                            [{'namespec': 'dummy'}],
                                            [{'namespec': 'dummy_proc'}],
                                            [{'namespec': 'dummy_proc', 'identifier': '10.0.0.1'}]))
    view.application_name = 'dummy_appli'
    view.application = Mock()
    # patch context
    view.view_ctx = Mock(process_name=None, identifier='10.0.0.1',
                         **{'get_process_status.return_value': None})
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
    view.view_ctx.process_name = 'dummy_proc'
    view.write_contents(mocked_root)
    assert mocked_data.call_args_list == [call()]
    assert mocked_table.call_args_list == [call(mocked_root, [{'namespec': 'dummy'}])]
    assert view.view_ctx.process_name == ''
    assert mocked_stats.call_args_list == [call(mocked_root, {})]
    mocked_data.reset_mock()
    mocked_table.reset_mock()
    mocked_stats.reset_mock()
    # test call with process selected but belonging to another application
    view.view_ctx.process_name = 'dummy_proc'
    view.view_ctx.get_process_status.return_value = Mock(application_name='dumb_appli')
    view.write_contents(mocked_root)
    assert mocked_data.call_args_list == [call()]
    assert mocked_table.call_args_list == [call(mocked_root, [{'namespec': 'dummy'}])]
    assert view.view_ctx.process_name == ''
    assert mocked_stats.call_args_list == [call(mocked_root, {})]
    mocked_data.reset_mock()
    mocked_table.reset_mock()
    mocked_stats.reset_mock()
    # test call with process selected and belonging to the application but stopped
    view.view_ctx.process_name = 'dummy_proc'
    view.view_ctx.get_process_status.return_value = Mock(application_name='dummy_appli',
                                                         **{'stopped.return_value': True})
    view.write_contents(mocked_root)
    assert mocked_data.call_args_list == [call()]
    assert mocked_table.call_args_list == [call(mocked_root, [{'namespec': 'dummy_proc'}])]
    assert view.view_ctx.process_name == ''
    assert mocked_stats.call_args_list == [call(mocked_root, {})]
    mocked_data.reset_mock()
    mocked_table.reset_mock()
    mocked_stats.reset_mock()
    # test call with process selected and belonging to the application and running
    view.view_ctx.process_name = 'dummy_proc'
    view.view_ctx.get_process_status.return_value = Mock(application_name='dummy_appli',
                                                         **{'stopped.return_value': False})
    view.write_contents(mocked_root)
    assert mocked_data.call_args_list == [call()]
    assert mocked_table.call_args_list == [call(mocked_root, [{'namespec': 'dummy_proc', 'identifier': '10.0.0.1'}])]
    assert view.view_ctx.process_name == 'dummy_proc'
    assert mocked_stats.call_args_list == [call(mocked_root, {'namespec': 'dummy_proc', 'identifier': '10.0.0.1'})]


def test_get_process_data(mocker, view):
    """ Test the ViewApplication.get_process_data method. """
    # patch the selected application
    process_1_10001 = {'group': 'appli_1', 'disabled': False, 'statename': 'STOPPED', 'state': 0,
                       'has_crashed': False, 'description': 'process_1 on 10.0.0.1',
                       'has_stdout': False, 'has_stderr': True}
    process_1 = Mock(application_name='appli_1', process_name='process_1', namespec='namespec_1',
                     state=ProcessStates.EXITED, displayed_state=ProcessStates.STOPPED, expected_exit=False,
                     running_identifiers=set(), rules=Mock(expected_load=20),
                     info_map={'10.0.0.1': process_1_10001},
                     **{'state_string.return_value': 'STOPPED',
                        'displayed_state_string.return_value': 'STOPPED',
                        'get_applicable_details.return_value': ('10.0.0.1', 'stopped', True, False),
                        'has_stdout.return_value': False,
                        'has_stderr.return_value': True,
                        'has_crashed.return_value': False,
                        'disabled.return_value': True,
                        'possible_identifiers.return_value': []})
    process_2 = Mock(application_name='appli_2', process_name='process_2', namespec='namespec_2',
                     running_identifiers=['10.0.0.1', '10.0.0.3'],  # should be a set but hard to test afterward
                     state=ProcessStates.RUNNING, displayed_state=ProcessStates.RUNNING, expected_exit=True,
                     rules=Mock(expected_load=1),
                     info_map={'10.0.0.1': {}, '10.0.0.2': {}, '10.0.0.3': {}, '10.0.0.4': {}},
                     **{'state_string.return_value': 'RUNNING',
                        'displayed_state_string.return_value': 'RUNNING',
                        'get_applicable_details.return_value': (None, 'conflict', False, False),
                        'has_crashed.return_value': True,
                        'has_stdout.return_value': True,
                        'has_stderr.return_value': False,
                        'disabled.return_value': False,
                        'possible_identifiers.return_value': ['10.0.0.1']})
    view.application = Mock(processes={process_1.process_name: process_1, process_2.process_name: process_2})
    # patch context
    mocked_stats = Mock()
    view.view_ctx = Mock(**{'get_process_stats.return_value': (4, mocked_stats),
                            'get_process_shex.side_effect': [(True, None), (False, None)]})
    # test call
    data_1 = {'row_type': ProcessRowTypes.APPLICATION_PROCESS,
              'application_name': 'appli_1', 'process_name': 'process_1', 'namespec': 'namespec_1',
              'identifier': '10.0.0.1', 'disabled': True, 'startable': False, 'stoppable': True,
              'statename': 'STOPPED', 'statecode': ProcessStates.STOPPED, 'gravity': 'FATAL',
              'has_crashed': False, 'running_identifiers': [], 'description': 'stopped',
              'main': True, 'nb_items': 1,
              'expected_load': 20, 'nb_cores': 4, 'proc_stats': mocked_stats,
              'has_stdout': True, 'has_stderr': False}
    data_1_1 = {'row_type': ProcessRowTypes.INSTANCE_PROCESS,
                'application_name': 'appli_1', 'process_name': '', 'namespec': 'namespec_1',
                'identifier': '10.0.0.1', 'disabled': False, 'startable': False, 'stoppable': False,
                'statename': 'STOPPED', 'statecode': ProcessStates.STOPPED, 'gravity': 'STOPPED',
                'has_crashed': False, 'running_identifiers': ['10.0.0.1'], 'description': 'process_1 on 10.0.0.1',
                'main': False, 'nb_items': 0,
                'expected_load': 20, 'nb_cores': 4, 'proc_stats': mocked_stats,
                'has_stdout': False, 'has_stderr': True}
    data_2 = {'row_type': ProcessRowTypes.APPLICATION_PROCESS,
              'application_name': 'appli_2', 'process_name': 'process_2', 'namespec': 'namespec_2',
              'identifier': None, 'disabled': False, 'startable': True, 'stoppable': True,
              'statename': 'RUNNING', 'statecode': ProcessStates.RUNNING, 'gravity': 'RUNNING',
              'has_crashed': True, 'running_identifiers': ['10.0.0.1', '10.0.0.3'], 'description': 'conflict',
              'main': True, 'nb_items': 4,
              'expected_load': 1, 'nb_cores': 0, 'proc_stats': None,
              'has_stdout': False, 'has_stderr': False}
    assert view.get_process_data() == [data_1, data_1_1, data_2]


def test_write_process(view):
    """ Test the write_process method. """
    # create a process-like dict
    info = {'process_name': 'proc1', 'namespec': 'dummy_appli:dummy_proc',
            'running_identifiers': [], 'identifier': '10.0.0.2:25000'}
    # patch the view context
    view.view_ctx = Mock(**{'format_url.return_value': 'an url'})
    # patch the meld elements
    running_span_mid = create_element()
    running_a_mid = create_element({'running_span_mid': running_span_mid})
    tr_elt = create_element({'running_a_mid': running_a_mid})
    # test call with stopped process
    view.write_process(tr_elt, info)
    assert tr_elt.findmeld.call_args_list == [call('running_a_mid')]
    assert running_a_mid.replace.call_args_list == [call('')]
    assert running_a_mid.attributes.call_args_list == []
    assert running_span_mid.content.call_args_list == []
    # reset mock elements
    view.view_ctx.format_url.reset_mock()
    tr_elt.reset_all()
    # test call with running process
    info['running_identifiers'] = ['10.0.0.1:25000']
    info['identifier'] = '10.0.0.1:25000'
    view.write_process(tr_elt, info)
    assert tr_elt.findmeld.call_args_list == [call('running_a_mid')]
    assert running_a_mid.findmeld.call_args_list == [call('running_span_mid')]
    assert running_a_mid.replace.call_args_list == []
    assert running_a_mid.attributes.call_args_list == [call(href='an url')]
    assert running_span_mid.content.call_args_list == [call('10.0.0.1')]
    # reset mock elements
    view.view_ctx.format_url.reset_mock()
    tr_elt.reset_all()
    # test call with multiple running process
    info['running_identifiers'] = ['10.0.0.1:25000', '10.0.0.2:25000']
    info['identifier'] = ['10.0.0.1:25000', '10.0.0.2:25000']
    view.write_process(tr_elt, info)
    assert tr_elt.findmeld.call_args_list == [call('running_a_mid')]
    assert running_a_mid.findmeld.call_args_list == [call('running_span_mid')]
    assert running_a_mid.replace.call_args_list == []
    assert running_a_mid.attributes.call_args_list == [call(href='an url')]
    assert running_span_mid.attrib['class'] == 'blink'
    assert running_span_mid.content.call_args_list == [call('Conciliate')]


def test_write_process_table(mocker, view):
    """ Test the write_process_table method. """
    mocked_shex = mocker.patch.object(view, 'write_process_global_shex')
    mocked_common_table = mocker.patch.object(view, 'write_common_process_table')
    mocked_common_process = mocker.patch.object(view, 'write_common_process_status')
    mocked_process = mocker.patch.object(view, 'write_process')
    mocked_process_shex = mocker.patch.object(view, 'write_process_shex')
    # patch the meld elements
    shex_elts = [create_element() for _ in range(6)]
    tr_elts = [create_element({'shex_td_mid': shex_elt})
               for shex_elt in shex_elts]
    tr_mid = create_element()
    tr_mid.repeat.return_value = [(tr_elts[0], {'row_type': ProcessRowTypes.APPLICATION_PROCESS}),
                                  (tr_elts[1], {'row_type': ProcessRowTypes.INSTANCE_PROCESS}),
                                  (tr_elts[2], {'row_type': ProcessRowTypes.INSTANCE_PROCESS}),
                                  (tr_elts[3], {'row_type': ProcessRowTypes.INSTANCE_PROCESS}),
                                  (tr_elts[4], {'row_type': ProcessRowTypes.APPLICATION_PROCESS}),
                                  (tr_elts[5], {'row_type': ProcessRowTypes.APPLICATION_PROCESS})]
    table_mid = create_element({'tr_mid': tr_mid})
    contents_elt = create_element({'table_mid': table_mid})
    # test call with no data
    view.write_process_table(contents_elt, [])
    assert table_mid.replace.call_args_list == [call('No programs to display')]
    assert mocked_shex.call_args_list == []
    assert mocked_common_table.call_args_list == []
    assert mocked_common_process.call_args_list == []
    assert mocked_process.call_args_list == []
    assert mocked_process_shex.call_args_list == []
    assert all(tr_elt.attrib['class'] == '' for tr_elt in tr_elts)
    assert all(shex_elt.replace.call_args_list == [] for shex_elt in shex_elts)
    # reset mocks
    mocker.resetall()
    table_mid.reset_all()
    for tr_elt in tr_elts:
        tr_elt.reset_all()
    # test call with data and line selected
    view.write_process_table(contents_elt, [{'dummy': 'info'}])
    assert table_mid.replace.call_args_list == []
    assert mocked_shex.call_args_list == [call(table_mid)]
    assert mocked_common_table.call_args_list == [call(table_mid)]
    assert mocked_common_process.call_args_list == [call(tr_elts[0], {'row_type': ProcessRowTypes.APPLICATION_PROCESS}),
                                                    call(tr_elts[1], {'row_type': ProcessRowTypes.INSTANCE_PROCESS}),
                                                    call(tr_elts[2], {'row_type': ProcessRowTypes.INSTANCE_PROCESS}),
                                                    call(tr_elts[3], {'row_type': ProcessRowTypes.INSTANCE_PROCESS}),
                                                    call(tr_elts[4], {'row_type': ProcessRowTypes.APPLICATION_PROCESS}),
                                                    call(tr_elts[5], {'row_type': ProcessRowTypes.APPLICATION_PROCESS})]
    assert mocked_process.call_args_list == [call(tr_elts[0], {'row_type': ProcessRowTypes.APPLICATION_PROCESS}),
                                             call(tr_elts[1], {'row_type': ProcessRowTypes.INSTANCE_PROCESS}),
                                             call(tr_elts[2], {'row_type': ProcessRowTypes.INSTANCE_PROCESS}),
                                             call(tr_elts[3], {'row_type': ProcessRowTypes.INSTANCE_PROCESS}),
                                             call(tr_elts[4], {'row_type': ProcessRowTypes.APPLICATION_PROCESS}),
                                             call(tr_elts[5], {'row_type': ProcessRowTypes.APPLICATION_PROCESS})]
    expected = [call(tr_elts[0], {'row_type': ProcessRowTypes.APPLICATION_PROCESS}, False),
                call(tr_elts[4], {'row_type': ProcessRowTypes.APPLICATION_PROCESS}, True),
                call(tr_elts[5], {'row_type': ProcessRowTypes.APPLICATION_PROCESS}, False)]
    assert mocked_process_shex.call_args_list == expected
    assert all(shex_elt.replace.call_args_list == [call('')] for shex_elt in shex_elts[1:3])
    assert tr_elts[0].attrib['class'] == 'brightened'
    assert tr_elts[1].attrib['class'] == 'shaded'
    assert tr_elts[2].attrib['class'] == 'brightened'
    assert tr_elts[3].attrib['class'] == 'shaded'
    assert tr_elts[4].attrib['class'] == 'shaded'
    assert tr_elts[5].attrib['class'] == 'brightened'


def test_write_process_global_shex(mocker, view):
    """ Test the write_process_global_shex method. """
    mocked_clear_proc = mocker.patch.object(view, 'write_global_shex')
    view.view_ctx = Mock(process_shex='1234',
                         **{'get_default_process_shex.side_effect': lambda x, y: 'ffff' if y else '0000'})
    table_elt = create_element()
    view.write_process_global_shex(table_elt)
    assert mocked_clear_proc.call_args_list == [call(table_elt, PROC_SHRINK_EXPAND, '1234', 'ffff', '0000')]


def test_write_process_shex(view):
    """ Test the write_process_shex method. """
    view.view_ctx = Mock(process_shex='1234',
                         **{'format_url.return_value': 'an url',
                            'get_process_shex.return_value': (True, '0001')})
    shex_a_mid = create_element()
    shex_td_mid = create_element({'shex_a_mid': shex_a_mid})
    tr_elt = create_element({'shex_td_mid': shex_td_mid})
    # test with shex element and shaded
    info = {'process_name': 'process_1', 'nb_items': 3}
    view.write_process_shex(tr_elt, info, True)
    assert view.view_ctx.format_url.call_args_list == [call('', 'application.html', pshex='0001')]
    assert shex_td_mid.attrib['class'] == 'shaded'
    assert shex_a_mid.content.call_args_list == [call(SHEX_SHRINK)]
    assert shex_a_mid.attributes.call_args_list == [call(href='an url')]
    tr_elt.reset_all()
    view.view_ctx.format_url.reset_mock()
    # test without shex element and brightened
    view.view_ctx.get_process_shex.return_value = False, 'fffe'
    view.write_process_shex(tr_elt, info, False)
    assert view.view_ctx.format_url.call_args_list == [call('', 'application.html', pshex='fffe')]
    assert shex_td_mid.attrib['class'] == ''
    assert shex_a_mid.content.call_args_list == [call(SHEX_EXPAND)]
    assert shex_a_mid.attributes.call_args_list == [call(href='an url')]


def test_make_callback(mocker, view):
    """ Test the make_callback method. """
    mocker.patch('supvisors.web.viewapplication.delayed_error', return_value='Delayed')
    mocked_clear_proc = mocker.patch.object(view, 'clearlog_process_action', return_value='Clear process logs')
    mocked_restart_proc = mocker.patch.object(view, 'restart_process_action', return_value='Restart process')
    mocked_stop_proc = mocker.patch.object(view, 'stop_process_action', return_value='Stop process')
    mocked_start_proc = mocker.patch.object(view, 'start_process_action', return_value='Start process')
    mocked_restart_app = mocker.patch.object(view, 'restart_application_action', return_value='Restart application')
    mocked_stop_app = mocker.patch.object(view, 'stop_application_action', return_value='Stop application')
    mocked_start_app = mocker.patch.object(view, 'start_application_action', return_value='Start application')
    # patch view context
    view.view_ctx = Mock(strategy=StartingStrategies.LOCAL, **{'get_process_status.return_value': None})
    # test with no application set
    for action in ['startapp', 'stopapp', 'restartapp', 'anything', 'start', 'stop', 'restart', 'clearlog']:
        assert view.make_callback('dummy', action) == 'Delayed'
    # test with application set
    view.application = Mock()
    # test calls for different actions
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


def test_start_application_action(mocker, view):
    """ Test the start_application_action method. """
    mocked_action = mocker.patch.object(view, 'supvisors_rpc_action')
    view.application_name = 'dummy_appli'
    # test without auto-refresh
    view.view_ctx = Mock(auto_refresh=False)
    view.start_application_action(StartingStrategies.CONFIG)
    assert mocked_action.call_args_list == [call('start_application',
                                                 (StartingStrategies.CONFIG.value, 'dummy_appli', True),
                                                 'Application dummy_appli started')]
    mocker.resetall()
    # test with auto-refresh
    view.view_ctx.auto_refresh = True
    view.start_application_action(StartingStrategies.LOCAL)
    assert mocked_action.call_args_list == [call('start_application',
                                                 (StartingStrategies.LOCAL.value, 'dummy_appli', False),
                                                 'Application dummy_appli started')]


def test_stop_application_action(mocker, view):
    """ Test the stop_application_action method. """
    mocked_action = mocker.patch.object(view, 'supvisors_rpc_action')
    view.application_name = 'dummy_appli'
    # test without auto-refresh
    view.view_ctx = Mock(auto_refresh=False)
    view.stop_application_action()
    assert mocked_action.call_args_list == [call('stop_application', ('dummy_appli', True),
                                                 'Application dummy_appli stopped')]
    mocker.resetall()
    # test with auto-refresh
    view.view_ctx.auto_refresh = True
    view.stop_application_action()
    assert mocked_action.call_args_list == [call('stop_application', ('dummy_appli', False),
                                                 'Application dummy_appli stopped')]


def test_restart_application_action(mocker, view):
    """ Test the restart_application_action method. """
    mocked_action = mocker.patch.object(view, 'supvisors_rpc_action')
    view.application_name = 'dummy_appli'
    # test without auto-refresh
    view.view_ctx = Mock(auto_refresh=False)
    view.restart_application_action(StartingStrategies.LESS_LOADED)
    assert mocked_action.call_args_list == [call('restart_application',
                                                 (StartingStrategies.LESS_LOADED.value, 'dummy_appli', True),
                                                 'Application dummy_appli restarted')]
    mocker.resetall()
    # test with auto-refresh
    view.view_ctx.auto_refresh = True
    view.restart_application_action(StartingStrategies.LESS_LOADED_NODE)
    assert mocked_action.call_args_list == [call('restart_application',
                                                 (StartingStrategies.LESS_LOADED_NODE.value, 'dummy_appli', False),
                                                 'Application dummy_appli restarted')]


def test_start_process_action(mocker, view):
    """ Test the start_process_action method. """
    mocked_action = mocker.patch.object(view, 'supvisors_rpc_action')
    # test without auto-refresh
    view.view_ctx = Mock(auto_refresh=False)
    view.start_process_action(StartingStrategies.MOST_LOADED_NODE, 'dummy_proc')
    assert mocked_action.call_args_list == [call('start_process',
                                                 (StartingStrategies.MOST_LOADED_NODE.value, 'dummy_proc', '', True),
                                                 'Process dummy_proc started')]
    mocker.resetall()
    # test with auto-refresh
    view.view_ctx.auto_refresh = True
    view.start_process_action(StartingStrategies.MOST_LOADED, 'dummy_proc')
    assert mocked_action.call_args_list == [call('start_process',
                                                 (StartingStrategies.MOST_LOADED.value, 'dummy_proc', '', False),
                                                 'Process dummy_proc started')]


def test_stop_process_action(mocker, view):
    """ Test the stop_process_action method. """
    mocked_action = mocker.patch.object(view, 'supvisors_rpc_action')
    # test without auto-refresh
    view.view_ctx = Mock(auto_refresh=False)
    view.stop_process_action('dummy_proc')
    assert mocked_action.call_args_list == [call('stop_process', ('dummy_proc', True),
                                                 'Process dummy_proc stopped')]
    mocker.resetall()
    # test with auto-refresh
    view.view_ctx.auto_refresh = True
    view.stop_process_action('dummy_proc')
    assert mocked_action.call_args_list == [call('stop_process', ('dummy_proc', False),
                                                 'Process dummy_proc stopped')]


def test_restart_process_action(mocker, view):
    """ Test the restart_process_action method. """
    mocked_action = mocker.patch.object(view, 'supvisors_rpc_action')
    # test without auto-refresh
    view.view_ctx = Mock(auto_refresh=False)
    view.restart_process_action(StartingStrategies.LOCAL, 'dummy_proc')
    assert mocked_action.call_args_list == [call('restart_process',
                                                 (StartingStrategies.LOCAL.value, 'dummy_proc', '', True),
                                                 'Process dummy_proc restarted')]
    mocker.resetall()
    # test with auto-refresh
    view.view_ctx.auto_refresh = True
    view.restart_process_action(StartingStrategies.CONFIG, 'dummy_proc')
    assert mocked_action.call_args_list == [call('restart_process',
                                                 (StartingStrategies.CONFIG.value, 'dummy_proc', '', False),
                                                 'Process dummy_proc restarted')]


def test_clearlog_process_action(mocker, view):
    """ Test the clearlog_process_action method. """
    mocked_action = mocker.patch.object(view, 'supervisor_rpc_action')
    view.clearlog_process_action('dummy_proc')
    assert mocked_action.call_args_list == [call('clearProcessLogs', ('dummy_proc', ),
                                                 'Log for dummy_proc cleared')]
