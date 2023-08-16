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

from random import shuffle
from unittest.mock import call, Mock

import pytest
from supervisor.web import MeldView, StatusView

from supvisors.ttypes import ApplicationStates
from supvisors.web.viewhandler import ViewHandler
from supvisors.web.viewprocinstance import *
from supvisors.web.webutils import PROC_INSTANCE_PAGE
from .base import DummyHttpContext, ProcessInfoDatabase, process_info_by_name
from .conftest import create_application, create_process, create_element


@pytest.fixture
def http_context(supvisors):
    """ Fixture for a consistent mocked HTTP context provided by Supervisor. """
    http_context = DummyHttpContext('ui/proc_instance.html')
    http_context.supervisord.supvisors = supvisors
    supvisors.supervisor_data.supervisord = http_context.supervisord
    return http_context


@pytest.fixture
def view(http_context):
    """ Return the instance to test. """
    # apply the forced inheritance done in supvisors.plugin
    StatusView.__bases__ = (ViewHandler,)
    # create the instance to be tested
    return ProcInstanceView(http_context)


def test_init(view):
    """ Test the values set at construction of ProcInstanceView. """
    # test instance inheritance
    for klass in [SupvisorsInstanceView, StatusView, ViewHandler, MeldView]:
        assert isinstance(view, klass)
    # test default page name
    assert view.page_name == PROC_INSTANCE_PAGE


def test_write_periods(mocker, view):
    """ Test the ProcInstanceView.write_periods method. """
    mocked_period = mocker.patch.object(view, 'write_periods_availability')
    mocked_root = Mock()
    # test with process statistics to be displayed
    view.write_periods(mocked_root)
    assert mocked_period.call_args_list == [call(mocked_root, True)]
    mocked_period.reset_mock()
    # test with process statistics NOT to be displayed
    view.has_process_statistics = False
    view.write_periods(mocked_root)
    assert mocked_period.call_args_list == [call(mocked_root, False)]


def test_write_contents(mocker, view):
    """ Test the ProcInstanceView.write_contents method. """
    mocked_stats = mocker.patch.object(view, 'write_process_statistics')
    mocked_table = mocker.patch.object(view, 'write_process_table')
    mocked_data = mocker.patch.object(view, 'get_process_data',
                                      side_effect=(([{'namespec': 'dummy'}], []),
                                                   ([{'namespec': 'dummy'}], [{'namespec': 'dummy_proc'}]),
                                                   ([{'namespec': 'dummy'}], [{'namespec': 'dummy_proc'}]),
                                                   ([{'namespec': 'dummy_proc'}], [{'namespec': 'dummy'}])))
    # patch context
    view.view_ctx = Mock(parameters={PROCESS: None}, local_identifier='10.0.0.1',
                         **{'get_process_status.return_value': None})
    # patch the meld elements
    mocked_root = Mock()
    # test call with no process selected
    view.write_contents(mocked_root)
    assert mocked_data.call_args_list == [call()]
    assert mocked_table.call_args_list == [call(mocked_root, [{'namespec': 'dummy'}], [])]
    assert mocked_stats.call_args_list == [call(mocked_root, {})]
    mocker.resetall()
    # test call with process selected and no corresponding status
    # process set in excluded_list but not passed to write_process_statistics because unselected due to missing status
    view.view_ctx.parameters[PROCESS] = 'dummy_proc'
    view.write_contents(mocked_root)
    assert mocked_data.call_args_list == [call()]
    assert mocked_table.call_args_list == [call(mocked_root, [{'namespec': 'dummy'}], [{'namespec': 'dummy_proc'}])]
    assert view.view_ctx.parameters[PROCESS] == ''
    assert mocked_stats.call_args_list == [call(mocked_root, {})]
    mocker.resetall()
    # test call with process selected but not running on considered node
    # process set in excluded_list
    view.view_ctx.parameters[PROCESS] = 'dummy_proc'
    view.view_ctx.get_process_status.return_value = Mock(running_identifiers={'10.0.0.2'})
    view.write_contents(mocked_root)
    assert mocked_data.call_args_list == [call()]
    assert mocked_table.call_args_list == [call(mocked_root, [{'namespec': 'dummy'}], [{'namespec': 'dummy_proc'}])]
    assert view.view_ctx.parameters[PROCESS] == ''
    assert mocked_stats.call_args_list == [call(mocked_root, {})]
    mocker.resetall()
    # test call with process selected and running
    view.view_ctx.parameters[PROCESS] = 'dummy'
    view.view_ctx.get_process_status.return_value = Mock(running_identifiers={'10.0.0.1'})
    view.write_contents(mocked_root)
    assert mocked_data.call_args_list == [call()]
    assert mocked_table.call_args_list == [call(mocked_root, [{'namespec': 'dummy_proc'}], [{'namespec': 'dummy'}])]
    assert view.view_ctx.parameters[PROCESS] == 'dummy'
    assert mocked_stats.call_args_list == [call(mocked_root, {'namespec': 'dummy'})]


def test_get_process_data(mocker, view):
    """ Test the ProcInstanceView.get_process_data method. """
    mocker.patch.object(view, 'sort_data', side_effect=lambda x: (sorted(x, key=lambda y: y['namespec']), []))
    mocked_data = mocker.patch.object(view, 'get_supervisord_data', return_value={'namespec': 'supervisord'})
    # get context
    instance_status = view.sup_ctx.instances['10.0.0.1']
    # test with empty context
    view.view_ctx = Mock(local_identifier='10.0.0.1',
                         **{'get_process_stats.side_effect': [(2, 'stats #1'), (1, None), (4, 'stats #3')]})
    assert view.get_process_data() == ([{'namespec': 'supervisord'}], [])
    assert mocked_data.call_args_list == [call(instance_status)]
    # patch context
    for application_name in ['sample_test_1', 'crash', 'firefox']:
        view.sup_ctx.applications[application_name] = create_application(application_name, view.supvisors)
    process_data = [('xfontsel', 8, True, False), ('segv', 17, False, False), ('firefox', 26, False, True)]
    for process_name, load, has_crashed, disabled in process_data:
        # create process
        info = process_info_by_name(process_name)
        info['has_crashed'] = has_crashed
        info['disabled'] = disabled
        process = create_process(info, view.supvisors)
        process.rules.expected_load = load
        process.add_info('10.0.0.1', info)
        # add to application
        view.sup_ctx.applications[process.application_name].processes[process.namespec] = process
        # add to supvisors instance status
        instance_status.processes[process.namespec] = process
    # test normal behavior
    sorted_data, excluded_data = view.get_process_data()
    # test intermediate list
    data1 = {'application_name': 'sample_test_1', 'process_name': 'xfontsel', 'namespec': 'sample_test_1:xfontsel',
             'single': False, 'identifier': '10.0.0.1', 'disabled': False, 'startable': True,
             'statename': 'RUNNING', 'statecode': 20, 'gravity': 'RUNNING', 'has_crashed': True,
             'description': 'pid 80879, uptime 0:01:19',
             'expected_load': 8, 'nb_cores': 2, 'proc_stats': 'stats #1'}
    data2 = {'application_name': 'crash', 'process_name': 'segv', 'namespec': 'crash:segv',
             'single': False, 'identifier': '10.0.0.1', 'disabled': False, 'startable': True,
             'statename': 'BACKOFF', 'statecode': 30, 'gravity': 'BACKOFF', 'has_crashed': False,
             'description': 'Exited too quickly (process log may have details)',
             'expected_load': 17, 'nb_cores': 1, 'proc_stats': None}
    data3 = {'application_name': 'firefox', 'process_name': 'firefox', 'namespec': 'firefox',
             'single': True, 'identifier': '10.0.0.1', 'disabled': True, 'startable': False,
             'statename': 'EXITED', 'statecode': 100, 'gravity': 'EXITED', 'has_crashed': False,
             'description': 'Sep 14 05:18 PM',
             'expected_load': 26, 'nb_cores': 4, 'proc_stats': 'stats #3'}
    assert sorted_data == [data2, data3, data1, {'namespec': 'supervisord'}]
    assert excluded_data == []


def test_get_supervisord_data(view):
    """ Test the ProcInstanceView.get_supervisord_data method. """
    view.view_ctx = Mock(local_identifier='10.0.0.1', **{'get_process_stats.return_value': (2, 'stats #1')})
    # get context
    instance_status = view.sup_ctx.instances['10.0.0.1']
    pid = os.getpid()
    # test call on empty time values
    supervisord_info = {'application_name': 'supervisord', 'process_name': 'supervisord', 'namespec': 'supervisord',
                        'single': True, 'identifier': '10.0.0.1', 'disabled': False, 'startable': False,
                        'description': f'pid {pid}, uptime 0:00:00',
                        'statecode': 20, 'statename': 'RUNNING', 'gravity': 'RUNNING', 'has_crashed': False,
                        'expected_load': 0, 'nb_cores': 2, 'proc_stats': 'stats #1'}
    assert view.get_supervisord_data(instance_status) == supervisord_info
    # test call on relevant time values
    instance_status.start_time = 1000
    instance_status.local_time = 185618
    supervisord_info = {'application_name': 'supervisord', 'process_name': 'supervisord', 'namespec': 'supervisord',
                        'single': True, 'identifier': '10.0.0.1', 'disabled': False, 'startable': False,
                        'description': f'pid {pid}, uptime 2 days, 3:16:58',
                        'statecode': 20, 'statename': 'RUNNING', 'gravity': 'RUNNING', 'has_crashed': False,
                        'expected_load': 0, 'nb_cores': 2, 'proc_stats': 'stats #1'}
    assert view.get_supervisord_data(instance_status) == supervisord_info


def test_sort_data(mocker, view):
    """ Test the ProcInstanceView.sort_data method. """
    mocker.patch.object(view, 'get_application_summary',
                        side_effect=[{'application_name': 'crash', 'process_name': None},
                                     {'application_name': 'sample_test_1', 'process_name': None},
                                     {'application_name': 'sample_test_2', 'process_name': None}] * 2)
    view.view_ctx = Mock(local_identifier='10.0.0.1', **{'get_process_stats.return_value': (2, 'stats #1')})
    # build process list
    processes = [{'application_name': info['group'], 'process_name': info['name'],
                  'single': info['group'] == info['name']}
                 for info in ProcessInfoDatabase]
    shuffle(processes)
    # patch context
    view.view_ctx.get_application_shex.side_effect = [(True, 0), (True, 0), (True, 0),
                                                      (True, 0), (False, 0), (False, 0)]
    # test ordering
    actual, excluded = view.sort_data(processes)
    assert actual == [{'application_name': 'crash', 'process_name': None},
                      {'application_name': 'crash', 'process_name': 'late_segv', 'single': False},
                      {'application_name': 'crash', 'process_name': 'segv', 'single': False},
                      {'application_name': 'firefox', 'process_name': 'firefox', 'single': True},
                      {'application_name': 'sample_test_1', 'process_name': None},
                      {'application_name': 'sample_test_1', 'process_name': 'xclock', 'single': False},
                      {'application_name': 'sample_test_1', 'process_name': 'xfontsel', 'single': False},
                      {'application_name': 'sample_test_1', 'process_name': 'xlogo', 'single': False},
                      {'application_name': 'sample_test_2', 'process_name': None},
                      {'application_name': 'sample_test_2', 'process_name': 'sleep', 'single': False},
                      {'application_name': 'sample_test_2', 'process_name': 'yeux_00', 'single': False},
                      {'application_name': 'sample_test_2', 'process_name': 'yeux_01', 'single': False}]
    assert excluded == []
    # test with some shex on applications
    actual, excluded = view.sort_data(processes)
    assert actual == [{'application_name': 'crash', 'process_name': None},
                      {'application_name': 'crash', 'process_name': 'late_segv', 'single': False},
                      {'application_name': 'crash', 'process_name': 'segv', 'single': False},
                      {'application_name': 'firefox', 'process_name': 'firefox', 'single': True},
                      {'application_name': 'sample_test_1', 'process_name': None},
                      {'application_name': 'sample_test_2', 'process_name': None}]
    sorted_excluded = sorted(excluded, key=lambda x: x['process_name'])
    assert sorted_excluded == [{'application_name': 'sample_test_2', 'process_name': 'sleep', 'single': False},
                               {'application_name': 'sample_test_1', 'process_name': 'xclock', 'single': False},
                               {'application_name': 'sample_test_1', 'process_name': 'xfontsel', 'single': False},
                               {'application_name': 'sample_test_1', 'process_name': 'xlogo', 'single': False},
                               {'application_name': 'sample_test_2', 'process_name': 'yeux_00', 'single': False},
                               {'application_name': 'sample_test_2', 'process_name': 'yeux_01', 'single': False}]


def test_get_application_summary(mocker, view):
    """ Test the ProcInstanceView.get_application_summary method. """
    mocked_sum = mocker.patch.object(view, 'sum_process_info')
    # patch the context
    view.view_ctx = Mock(local_identifier='10.0.0.1')
    view.sup_ctx.applications['dummy_appli'] = Mock(state=ApplicationStates.RUNNING,
                                                    **{'get_operational_status.return_value': 'good'})
    # prepare parameters
    proc_1, proc_2, proc_3, proc_4 = Mock(), Mock(), Mock(), Mock()
    # test with empty list of processes
    expected = {'application_name': 'dummy_appli', 'process_name': None, 'namespec': None,
                'disabled': False, 'startable': False,
                'identifier': '10.0.0.1', 'statename': 'RUNNING', 'statecode': 2, 'gravity': 'RUNNING',
                'has_crashed': False, 'description': 'good', 'nb_processes': 0,
                'expected_load': 0, 'nb_cores': 0, 'proc_stats': None}
    mocked_sum.return_value = 0, 0, None
    assert view.get_application_summary('dummy_appli', []) == expected
    # test with non-running processes
    expected.update({'nb_processes': 1})
    assert view.get_application_summary('dummy_appli', [proc_4]) == expected
    # test with a mix of running and non-running processes
    appli_stats = Mock()
    mocked_sum.return_value = 27, 8, appli_stats
    expected.update({'nb_processes': 4, 'expected_load': 27, 'nb_cores': 8, 'proc_stats': appli_stats})
    assert view.get_application_summary('dummy_appli', [proc_1, proc_2, proc_3, proc_4]) == expected


def test_sum_process_info():
    """ Test the ProcInstanceView.sum_process_info method. """
    # prepare parameters
    proc_1 = {'statecode': ProcessStates.RUNNING, 'expected_load': 5, 'nb_cores': 8,
              'proc_stats': Mock(cpu=[10], mem=[5])}
    proc_2 = {'statecode': ProcessStates.STARTING, 'expected_load': 15, 'nb_cores': 8,
              'proc_stats': Mock(cpu=[], mem=[])}
    proc_3 = {'statecode': ProcessStates.BACKOFF, 'expected_load': 7, 'nb_cores': 8,
              'proc_stats': Mock(cpu=[8], mem=[22])}
    proc_4 = {'statecode': ProcessStates.FATAL, 'expected_load': 25, 'nb_cores': 8,
              'proc_stats': None}
    # test with empty list of processes
    assert ProcInstanceView.sum_process_info([]) == (0, 0, None)
    # test with non-running processes
    assert ProcInstanceView.sum_process_info([proc_4]) == (0, 0, None)
    # test with a mix of running and non-running processes
    expected_load, nb_cores, appli_stats = ProcInstanceView.sum_process_info([proc_1, proc_2, proc_3, proc_4])
    assert expected_load == 27
    assert nb_cores == 8
    assert appli_stats.cpu == [18]
    assert appli_stats.mem == [27]


def test_write_process_table(mocker, view):
    """ Test the ProcInstanceView.write_process_table method. """
    mocked_shex = mocker.patch.object(view, 'write_global_shex')
    mocked_total = mocker.patch.object(view, 'write_total_status')
    mocked_appli = mocker.patch.object(view, 'write_application_status')
    mocked_common = mocker.patch.object(view, 'write_common_process_status')
    mocked_supervisord = mocker.patch.object(view, 'write_supervisord_status')
    # patch the meld elements
    tr_elt_0 = Mock(attrib={'class': ''}, **{'findmeld.return_value': Mock()})
    tr_elt_1 = Mock(attrib={'class': ''}, **{'findmeld.return_value': Mock()})
    tr_elt_2 = Mock(attrib={'class': ''}, **{'findmeld.return_value': Mock()})
    tr_elt_3 = Mock(attrib={'class': ''}, **{'findmeld.return_value': Mock()})
    tr_elt_4 = Mock(attrib={'class': ''}, **{'findmeld.return_value': Mock()})
    tr_elt_5 = Mock(attrib={'class': ''}, **{'findmeld.return_value': Mock()})
    tr_mid = Mock(**{'repeat.return_value': [(tr_elt_0, {'process_name': 'info_0', 'single': True}),
                                             (tr_elt_1, {'process_name': None}),
                                             (tr_elt_2, {'process_name': 'info_2', 'single': False}),
                                             (tr_elt_3, {'process_name': 'info_3', 'single': False}),
                                             (tr_elt_4, {'process_name': None}),
                                             (tr_elt_5, {'process_name': 'supervisord', 'single': True})]})
    table_mid = Mock(**{'findmeld.return_value': tr_mid})
    mocked_root = Mock(**{'findmeld.return_value': table_mid})
    # test call with no data
    sorted_data, excluded_data = Mock(), Mock()
    view.write_process_table(mocked_root, [], excluded_data)
    assert table_mid.replace.call_args_list == [call('No programs to manage')]
    assert not mocked_shex.called
    assert not mocked_common.called
    assert not mocked_total.called
    assert not mocked_appli.called
    assert not tr_elt_0.findmeld.return_value.replace.called
    assert not tr_elt_1.findmeld.return_value.replace.called
    assert not tr_elt_2.findmeld.return_value.replace.called
    assert not tr_elt_3.findmeld.return_value.replace.called
    assert not tr_elt_4.findmeld.return_value.replace.called
    assert not tr_elt_5.findmeld.return_value.replace.called
    assert tr_elt_0.attrib['class'] == ''
    assert tr_elt_1.attrib['class'] == ''
    assert tr_elt_2.attrib['class'] == ''
    assert tr_elt_3.attrib['class'] == ''
    assert tr_elt_4.attrib['class'] == ''
    assert tr_elt_5.attrib['class'] == ''
    table_mid.replace.reset_mock()
    # test call with data and line selected
    view.write_process_table(mocked_root, sorted_data, excluded_data)
    assert not table_mid.replace.called
    assert mocked_shex.call_args_list == [call(table_mid)]
    assert mocked_common.call_args_list == [call(tr_elt_0, {'process_name': 'info_0', 'single': True}),
                                            call(tr_elt_2, {'process_name': 'info_2', 'single': False}),
                                            call(tr_elt_3, {'process_name': 'info_3', 'single': False})]
    assert mocked_supervisord.call_args_list == [call(tr_elt_5, {'process_name': 'supervisord', 'single': True})]
    assert mocked_appli.call_args_list == [call(tr_elt_1, {'process_name': None}, True),
                                           call(tr_elt_4, {'process_name': None}, False)]
    assert not tr_elt_0.findmeld.return_value.replace.called
    assert not tr_elt_1.findmeld.return_value.replace.called
    assert tr_elt_2.findmeld.return_value.replace.call_args_list == [call('')]
    assert tr_elt_3.findmeld.return_value.replace.call_args_list == [call('')]
    assert not tr_elt_4.findmeld.return_value.replace.called
    assert not tr_elt_5.findmeld.return_value.replace.called
    assert tr_elt_0.attrib['class'] == 'brightened'
    assert tr_elt_1.attrib['class'] == 'shaded'
    assert tr_elt_2.attrib['class'] == 'brightened'
    assert tr_elt_3.attrib['class'] == 'shaded'
    assert tr_elt_4.attrib['class'] == 'brightened'
    assert tr_elt_5.attrib['class'] == 'shaded'
    assert mocked_total.call_args_list == [call(table_mid, sorted_data, excluded_data)]


def test_write_global_shex(view):
    """ Test the ProcInstanceView.write_global_shex method. """
    # add context
    expanded = bytearray.fromhex('ffff')
    shrank = bytearray.fromhex('0000')
    view.view_ctx = Mock(parameters={SHRINK_EXPAND: 'ffff'},
                         **{'get_default_shex.side_effect': lambda x: expanded if x else shrank,
                            'format_url.return_value': 'an url'})
    # build HTML structure
    expand_elt = Mock()
    shrink_elt = Mock()
    mid_map = {'expand_a_mid': expand_elt, 'shrink_a_mid': shrink_elt}
    table_elt = Mock(**{'findmeld.side_effect': lambda x: mid_map[x]})
    # test with fully expanded shex
    view.write_global_shex(table_elt)
    assert expand_elt.replace.call_args_list == [call('')]
    assert not expand_elt.content.called
    assert not expand_elt.attributes.called
    assert not shrink_elt.replace.called
    assert shrink_elt.content.call_args_list == [call(SHEX_SHRINK)]
    assert shrink_elt.attributes.call_args_list == [call(href='an url')]
    assert view.view_ctx.format_url.call_args_list == [call('', 'proc_instance.html', shex='0000')]
    expand_elt.replace.reset_mock()
    shrink_elt.content.reset_mock()
    shrink_elt.attributes.reset_mock()
    view.view_ctx.format_url.reset_mock()
    # test with fully shrank shex
    view.view_ctx.parameters[SHRINK_EXPAND] = '0000'
    view.write_global_shex(table_elt)
    assert not expand_elt.replace.called
    assert expand_elt.content.call_args_list == [call(SHEX_EXPAND)]
    assert expand_elt.attributes.call_args_list == [call(href='an url')]
    assert shrink_elt.replace.call_args_list == [call('')]
    assert not shrink_elt.content.called
    assert not shrink_elt.attributes.called
    assert view.view_ctx.format_url.call_args_list == [call('', 'proc_instance.html', shex='ffff')]
    expand_elt.content.reset_mock()
    expand_elt.attributes.reset_mock()
    shrink_elt.replace.reset_mock()
    view.view_ctx.format_url.reset_mock()
    # test with fully mixed shex
    view.view_ctx.parameters[SHRINK_EXPAND] = '1234'
    view.write_global_shex(table_elt)
    assert not expand_elt.replace.called
    assert expand_elt.content.call_args_list == [call(SHEX_EXPAND)]
    assert expand_elt.attributes.call_args_list == [call(href='an url')]
    assert not shrink_elt.replace.called
    assert shrink_elt.content.call_args_list == [call(SHEX_SHRINK)]
    assert shrink_elt.attributes.call_args_list == [call(href='an url')]
    assert view.view_ctx.format_url.call_args_list == [call('', 'proc_instance.html', shex='ffff'),
                                                       call('', 'proc_instance.html', shex='0000')]


def test_write_application_status(mocker, view):
    """ Test the ProcInstanceView.write_application_status method. """
    mocked_common = mocker.patch.object(view, 'write_common_statistics')
    mocker.patch.object(view, '_write_process_button')
    # patch the context
    view.view_ctx = Mock(**{'get_application_shex.side_effect': [(False, '010'), (True, '101')],
                            'format_url.return_value': 'an url'})
    # patch the meld elements
    shex_a_mid = create_element()
    shex_td_mid = create_element({'shex_a_mid': shex_a_mid})
    name_a_mid = create_element()
    name_td_mid = create_element({'name_a_mid': name_a_mid})
    state_td_mid = create_element()
    desc_td_mid = create_element()
    clear_td_mid = create_element()
    tailout_td_mid = create_element()
    tailerr_td_mid = create_element()
    mocked_root = create_element({'shex_td_mid': shex_td_mid, 'name_td_mid': name_td_mid,
                                  'state_td_mid': state_td_mid, 'desc_td_mid': desc_td_mid,
                                  'clear_td_mid': clear_td_mid,
                                  'tailout_td_mid': tailout_td_mid, 'tailerr_td_mid': tailerr_td_mid})
    # prepare parameters
    info = {'application_name': 'dummy_appli', 'nb_processes': 4}
    # test call with application processes hidden
    view.write_application_status(mocked_root, info, True)
    assert mocked_common.call_args_list == [call(mocked_root, info)]
    assert 'rowspan' not in shex_td_mid.attrib
    assert shex_td_mid.attrib['class'] == ''
    assert shex_a_mid.content.call_args_list == [call('[+]')]
    assert shex_a_mid.attributes.call_args_list == [call(href='an url')]
    assert view.view_ctx.format_url.call_args_list == [call('', 'proc_instance.html', shex='010'),
                                                       call('', 'application.html', appliname='dummy_appli')]
    assert name_a_mid.content.call_args_list == [call('dummy_appli')]
    assert name_a_mid.attributes.call_args_list == [call(href='an url')]
    assert clear_td_mid.attrib['colspan'] == '3'
    assert clear_td_mid.content.call_args_list == [call('')]
    for mid in [tailout_td_mid, tailerr_td_mid]:
        assert mid.replace.call_args_list == [call('')]
    # reset context
    mocker.resetall()
    mocked_root.reset_all()
    view.view_ctx.format_url.reset_mock()
    # test call with application processes displayed
    view.write_application_status(mocked_root, info, False)
    assert mocked_common.call_args_list == [call(mocked_root, info)]
    assert shex_td_mid.attrib['rowspan'] == '5'
    assert shex_td_mid.attrib['class'] == 'brightened'
    assert shex_a_mid.content.call_args_list == [call('[\u2013]')]
    assert shex_a_mid.attributes.call_args_list == [call(href='an url')]
    assert view.view_ctx.format_url.call_args_list == [call('', 'proc_instance.html', shex='101'),
                                                       call('', 'application.html', appliname='dummy_appli')]
    assert name_a_mid.content.call_args_list == [call('dummy_appli')]
    assert name_a_mid.attributes.call_args_list == [call(href='an url')]
    assert clear_td_mid.attrib['colspan'] == '3'
    assert clear_td_mid.content.call_args_list == [call('')]
    for mid in [tailout_td_mid, tailerr_td_mid]:
        assert mid.replace.call_args_list == [call('')]


def test_write_supervisord_status(mocker, view):
    """ Test the write_supervisord_status method. """
    mocked_button = mocker.patch.object(view, '_write_supervisord_button')
    mocked_off = mocker.patch.object(view, '_write_supervisord_off_button')
    mocked_state = mocker.patch.object(view, 'write_common_state')
    mocked_stats = mocker.patch.object(view, 'write_common_statistics')
    # patch the view context
    view.view_ctx = Mock(**{'format_url.return_value': 'an url'})
    # patch the meld elements
    shex_elt = create_element()
    name_elt = create_element()
    start_elt = create_element()
    tailerr_elt = create_element()
    tr_elt = create_element({'shex_td_mid': shex_elt, 'name_a_mid': name_elt, 'start_a_mid': start_elt,
                             'tailerr_a_mid': tailerr_elt})
    # test call while not Master
    assert not view.sup_ctx.is_master
    info = {'namespec': 'supervisord', 'process_name': 'supervisord'}
    view.write_supervisord_status(tr_elt, info)
    assert mocked_state.call_args_list == [call(tr_elt, info)]
    assert mocked_stats.call_args_list == [call(tr_elt, info)]
    assert tr_elt.findmeld.call_args_list == [call('name_a_mid')]
    assert not shex_elt.content.called
    assert name_elt.content.call_args_list == [call('supervisord')]
    assert view.view_ctx.format_url.call_args_list == [call('', 'maintail.html', processname='supervisord', limit=1024)]
    assert name_elt.attributes.call_args_list == [call(href='an url', target="_blank")]
    assert mocked_button.call_args_list == [call(tr_elt, 'stop_a_mid', 'proc_instance.html', action='shutdownsup'),
                                            call(tr_elt, 'restart_a_mid', 'proc_instance.html', action='restartsup'),
                                            call(tr_elt, 'clear_a_mid', 'proc_instance.html', action='mainclearlog'),
                                            call(tr_elt, 'tailout_a_mid', MAIN_STDOUT_PAGE)]
    assert mocked_off.call_args_list == [call(tr_elt, 'start_a_mid'), call(tr_elt, 'tailerr_a_mid')]
    mocker.resetall()
    tr_elt.reset_all()
    view.view_ctx.format_url.reset_mock()
    # test call while Master
    view.sup_ctx.master_identifier = view.sup_ctx.local_identifier
    assert view.sup_ctx.is_master
    info = {'namespec': 'supervisord', 'process_name': 'supervisord'}
    view.write_supervisord_status(tr_elt, info)
    assert mocked_state.call_args_list == [call(tr_elt, info)]
    assert mocked_stats.call_args_list == [call(tr_elt, info)]
    assert tr_elt.findmeld.call_args_list == [call('shex_td_mid'), call('name_a_mid')]
    assert shex_elt.content.call_args_list == [call(MASTER_SYMBOL)]
    assert name_elt.content.call_args_list == [call('supervisord')]
    assert view.view_ctx.format_url.call_args_list == [call('', 'maintail.html', processname='supervisord', limit=1024)]
    assert name_elt.attributes.call_args_list == [call(href='an url', target="_blank")]
    assert mocked_button.call_args_list == [call(tr_elt, 'stop_a_mid', 'proc_instance.html', action='shutdownsup'),
                                            call(tr_elt, 'restart_a_mid', 'proc_instance.html', action='restartsup'),
                                            call(tr_elt, 'clear_a_mid', 'proc_instance.html', action='mainclearlog'),
                                            call(tr_elt, 'tailout_a_mid', MAIN_STDOUT_PAGE)]
    assert mocked_off.call_args_list == [call(tr_elt, 'start_a_mid'), call(tr_elt, 'tailerr_a_mid')]


def test_write_supervisord_button(view):
    """ Test the ProcInstanceView._write_supervisord_button method. """
    # patch the view context
    view.view_ctx = Mock(**{'format_url.return_value': 'an url'})
    # patch the meld elements
    a_elt = Mock(attrib={'class': ''})
    tr_elt = Mock(attrib={}, **{'findmeld.return_value': a_elt})
    # test call with action parameters
    view._write_supervisord_button(tr_elt, 'any_a_mid', 'proc_instance.html', **{ACTION: 'any_action'})
    assert tr_elt.findmeld.call_args_list == [call('any_a_mid')]
    assert view.view_ctx.format_url.call_args_list == [call('', 'proc_instance.html', action='any_action')]
    assert a_elt.attrib == {'class': 'button on'}
    assert a_elt.attributes.call_args_list == [call(href='an url')]
    tr_elt.findmeld.reset_mock()
    view.view_ctx.format_url.reset_mock()
    a_elt.attributes.reset_mock()
    a_elt.attrib['class'] = 'active'
    # test call without action parameters
    view._write_supervisord_button(tr_elt, 'any_a_mid', 'proc_instance.html')
    assert tr_elt.findmeld.call_args_list == [call('any_a_mid')]
    assert view.view_ctx.format_url.call_args_list == [call('', 'proc_instance.html')]
    assert a_elt.attrib == {'class': 'active button on'}
    assert a_elt.attributes.call_args_list == [call(href='an url')]


def test_write_supervisord_off_button(view):
    """ Test the ProcInstanceView._write_supervisord_off_button method. """
    # patch the meld elements
    start_a_mid = create_element()
    tr_elt = create_element({'start_a_mid': start_a_mid})
    # test call
    view._write_supervisord_off_button(tr_elt, 'start_a_mid')
    assert tr_elt.findmeld.call_args_list == [call('start_a_mid')]
    assert start_a_mid.attrib == {'class': 'button off'}
    assert not start_a_mid.attributes.called


def test_write_total_status(mocker, view):
    """ Test the ProcInstanceView.write_total_status method. """
    mocked_sum = mocker.patch.object(view, 'sum_process_info', return_value=(50, 2, None))
    # patch the meld elements
    load_elt = Mock(attrib={'class': ''})
    mem_elt = Mock(attrib={'class': ''})
    cpu_elt = Mock(attrib={'class': ''})
    mid_map = {'load_total_th_mid': load_elt, 'mem_total_th_mid': mem_elt, 'cpu_total_th_mid': cpu_elt}
    tr_elt = Mock(attrib={}, **{'findmeld.side_effect': lambda x: mid_map[x]})
    root_elt = Mock(attrib={}, **{'findmeld.return_value': None})
    # test call with total element removed
    sorted_data = [1, 2]
    excluded_data = [3, 4]
    view.write_total_status(root_elt, sorted_data, excluded_data)
    assert root_elt.findmeld.call_args_list == [call('total_mid')]
    assert not tr_elt.findmeld.called
    assert not mocked_sum.called
    for elt in mid_map.values():
        assert not elt.content.called
    root_elt.findmeld.reset_mock()
    # test call with total element present
    root_elt.findmeld.return_value = tr_elt
    # test call with no process stats
    view.write_total_status(root_elt, sorted_data, excluded_data)
    assert mocked_sum.call_args_list == [call([1, 2, 3, 4])]
    assert root_elt.findmeld.call_args_list == [call('total_mid')]
    assert tr_elt.findmeld.call_args_list == [call('load_total_th_mid')]
    assert load_elt.content.call_args_list == [call('50%')]
    assert not mem_elt.content.called
    assert not cpu_elt.content.called
    mocked_sum.reset_mock()
    root_elt.findmeld.reset_mock()
    tr_elt.findmeld.reset_mock()
    load_elt.content.reset_mock()
    # test call with process stats and irix mode
    mocked_sum.return_value = 50, 2, Mock(cpu=[12], mem=[25])
    view.supvisors.options.stats_irix_mode = True
    view.write_total_status(root_elt, sorted_data, excluded_data)
    assert mocked_sum.call_args_list == [call([1, 2, 3, 4])]
    assert root_elt.findmeld.call_args_list == [call('total_mid')]
    assert tr_elt.findmeld.call_args_list == [call('load_total_th_mid'), call('mem_total_th_mid'),
                                              call('cpu_total_th_mid')]
    assert load_elt.content.call_args_list == [call('50%')]
    assert mem_elt.content.call_args_list == [call('25.00%')]
    assert cpu_elt.content.call_args_list == [call('12.00%')]
    mocked_sum.reset_mock()
    root_elt.findmeld.reset_mock()
    tr_elt.findmeld.reset_mock()
    load_elt.content.reset_mock()
    mem_elt.content.reset_mock()
    cpu_elt.content.reset_mock()
    # test call with process stats and solaris mode
    view.supvisors.options.stats_irix_mode = False
    view.write_total_status(root_elt, sorted_data, excluded_data)
    assert mocked_sum.call_args_list == [call([1, 2, 3, 4])]
    assert root_elt.findmeld.call_args_list == [call('total_mid')]
    assert tr_elt.findmeld.call_args_list == [call('load_total_th_mid'), call('mem_total_th_mid'),
                                              call('cpu_total_th_mid')]
    assert load_elt.content.call_args_list == [call('50%')]
    assert mem_elt.content.call_args_list == [call('25.00%')]
    assert cpu_elt.content.call_args_list == [call('6.00%')]


def test_make_callback(mocker, view):
    """ Test the ProcInstanceView.make_callback method. """
    mocker.patch('supvisors.web.webutils.ctime', return_value='19:10:20')
    mocked_start = mocker.patch.object(view, 'start_group_action', return_value='started')
    mocked_stop = mocker.patch.object(view, 'stop_group_action', return_value='stopped')
    mocked_restart = mocker.patch.object(view, 'restart_group_action', return_value='restarted')
    mocked_clear = mocker.patch.object(view, 'clear_log_action', return_value='cleared')
    mocked_parent = mocker.patch('supvisors.web.viewinstance.SupvisorsInstanceView.make_callback',
                                 return_value='default')
    # test startgroup
    assert view.make_callback('namespec', 'startgroup') == 'started'
    assert mocked_start.call_args_list == [call('namespec')]
    assert not mocked_stop.called
    assert not mocked_restart.called
    assert not mocked_clear.called
    assert not mocked_parent.called
    mocked_start.reset_mock()
    # test stopgroup
    assert view.make_callback('namespec', 'stopgroup') == 'stopped'
    assert not mocked_start.called
    assert mocked_stop.call_args_list == [call('namespec')]
    assert not mocked_restart.called
    assert not mocked_clear.called
    assert not mocked_parent.called
    mocked_stop.reset_mock()
    # test restartgroup
    assert view.make_callback('namespec', 'restartgroup') == 'restarted'
    assert not mocked_start.called
    assert not mocked_stop.called
    assert mocked_restart.call_args_list == [call('namespec')]
    assert not mocked_clear.called
    assert not mocked_parent.called
    mocked_restart.reset_mock()
    # test mainclearlog
    assert view.make_callback('namespec', 'mainclearlog') == 'cleared'
    assert not mocked_start.called
    assert not mocked_stop.called
    assert not mocked_restart.called
    assert mocked_clear.call_args_list == [call()]
    assert not mocked_parent.called
    mocked_clear.reset_mock()
    # test other commands
    assert view.make_callback('namespec', 'other') == 'default'
    assert mocked_parent.call_args_list == [call('namespec', 'other')]
    assert not mocked_clear.called
    mocked_parent.reset_mock()
    # test another command returning an error message different from DISABLED code
    mocked_parent.return_value = lambda: 'abnormal termination'
    result = view.make_callback('namespec', 'other')
    assert result() == 'abnormal termination'
    assert mocked_parent.call_args_list == [call('namespec', 'other')]
    assert not mocked_clear.called
    mocked_parent.reset_mock()
    # test another command returning an error message
    mocked_parent.return_value = lambda: 'unexpected rpc fault [103]'
    result = view.make_callback('namespec', 'other')
    assert result() == ('erro', 'Process namespec: disabled at 19:10:20')
    assert mocked_parent.call_args_list == [call('namespec', 'other')]
    assert not mocked_clear.called


def test_start_group_action(mocker, view):
    """ Test the start_group_action method. """
    mocked_action = mocker.patch.object(view, 'supervisor_rpc_action')
    # test without auto-refresh
    view.view_ctx = Mock(parameters={AUTO: False})
    view.start_group_action('dummy_proc:*')
    assert mocked_action.call_args_list == [call('startProcess', ('dummy_proc:*', True),
                                                 'Group dummy_proc:* started')]
    mocker.resetall()
    # test with auto-refresh
    view.view_ctx.parameters[AUTO] = True
    view.start_group_action('dummy_proc:*')
    assert mocked_action.call_args_list == [call('startProcess', ('dummy_proc:*', False),
                                                 'Group dummy_proc:* started')]


def test_stop_group_action(mocker, view):
    """ Test the stop_group_action method. """
    mocked_action = mocker.patch.object(view, 'supervisor_rpc_action')
    # test without auto-refresh
    view.view_ctx = Mock(parameters={AUTO: False})
    view.stop_group_action('dummy_proc:*')
    assert mocked_action.call_args_list == [call('stopProcess', ('dummy_proc:*', True),
                                                 'Group dummy_proc:* stopped')]
    mocker.resetall()
    # test with auto-refresh
    view.view_ctx.parameters[AUTO] = True
    view.stop_group_action('dummy_proc:*')
    assert mocked_action.call_args_list == [call('stopProcess', ('dummy_proc:*', False),
                                                 'Group dummy_proc:* stopped')]


def test_restart_group_action(mocker, view):
    """ Test the restart_group_action method. """
    mocked_action = mocker.patch.object(view, 'multicall_rpc_action')
    # test without auto-refresh
    view.view_ctx = Mock(parameters={AUTO: False})
    view.restart_group_action('dummy_proc:*')
    multicall = [{'methodName': 'supervisor.stopProcess', 'params': ['dummy_proc:*']},
                 {'methodName': 'supervisor.startProcess', 'params': ['dummy_proc:*', True]}]
    assert mocked_action.call_args_list == [call(multicall, 'Group dummy_proc:* restarted')]
    mocker.resetall()
    # test with auto-refresh
    view.view_ctx.parameters[AUTO] = True
    view.restart_group_action('dummy_proc:*')
    multicall[1]['params'][1] = False
    assert mocked_action.call_args_list == [call(multicall, 'Group dummy_proc:* restarted')]


def test_clear_log_action(mocker, view):
    """ Test the ProcInstanceView.clear_log_action method. """
    mocked_action = mocker.patch.object(view, 'supervisor_rpc_action')
    view.clear_log_action()
    assert mocked_action.call_args_list == [call('clearLog', (), 'Log for Supervisor cleared')]
