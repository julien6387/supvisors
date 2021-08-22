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

import pytest

from random import shuffle

from supervisor.web import MeldView, StatusView

from unittest.mock import call, Mock

from supvisors.ttypes import ApplicationStates
from supvisors.viewhandler import ViewHandler
from supvisors.viewprocaddress import *
from supvisors.viewsupstatus import SupvisorsAddressView
from supvisors.webutils import PROC_NODE_PAGE

from .base import DummyHttpContext, ProcessInfoDatabase, process_info_by_name


@pytest.fixture
def view(supvisors):
    """ Return the instance to test. """
    # apply the forced inheritance done in supvisors.plugin
    StatusView.__bases__ = (ViewHandler,)
    # create the instance to be tested
    return ProcAddressView(DummyHttpContext('ui/procaddress.html'))


def test_init(view):
    """ Test the values set at construction of ProcAddressView. """
    # test instance inheritance
    for klass in [SupvisorsAddressView, StatusView, ViewHandler, MeldView]:
        assert isinstance(view, klass)
    # test default page name
    assert view.page_name == PROC_NODE_PAGE


def test_write_contents(mocker, view):
    """ Test the ProcAddressView.write_contents method. """
    mocked_stats = mocker.patch('supvisors.viewhandler.ViewHandler.write_process_statistics')
    mocked_table = mocker.patch('supvisors.viewprocaddress.ProcAddressView.write_process_table')
    mocked_data = mocker.patch('supvisors.viewprocaddress.ProcAddressView.get_process_data',
                               side_effect=(([{'namespec': 'dummy'}], []),
                                            ([{'namespec': 'dummy'}], [{'namespec': 'dummy_proc'}]),
                                            ([{'namespec': 'dummy'}], [{'namespec': 'dummy_proc'}]),
                                            ([{'namespec': 'dummy_proc'}], [{'namespec': 'dummy'}])))
    # patch context
    view.view_ctx = Mock(parameters={PROCESS: None}, local_node_name='10.0.0.1',
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
    # process set in excluded_list but not passed to write_process_statistics because unselected due to missing status
    view.view_ctx.parameters[PROCESS] = 'dummy_proc'
    view.write_contents(mocked_root)
    assert mocked_data.call_args_list == [call()]
    assert mocked_table.call_args_list == [call(mocked_root, [{'namespec': 'dummy'}])]
    assert view.view_ctx.parameters[PROCESS] == ''
    assert mocked_stats.call_args_list == [call(mocked_root, {})]
    mocked_data.reset_mock()
    mocked_table.reset_mock()
    mocked_stats.reset_mock()
    # test call with process selected but not running on considered node
    # process set in excluded_list
    view.view_ctx.parameters[PROCESS] = 'dummy_proc'
    view.view_ctx.get_process_status.return_value = Mock(running_nodes={'10.0.0.2'})
    view.write_contents(mocked_root)
    assert mocked_data.call_args_list == [call()]
    assert mocked_table.call_args_list == [call(mocked_root, [{'namespec': 'dummy'}])]
    assert view.view_ctx.parameters[PROCESS] == ''
    assert mocked_stats.call_args_list == [call(mocked_root, {})]
    mocked_data.reset_mock()
    mocked_table.reset_mock()
    mocked_stats.reset_mock()
    # test call with process selected and running
    view.view_ctx.parameters[PROCESS] = 'dummy'
    view.view_ctx.get_process_status.return_value = Mock(running_nodes={'10.0.0.1'})
    view.write_contents(mocked_root)
    assert mocked_data.call_args_list == [call()]
    assert mocked_table.call_args_list == [call(mocked_root, [{'namespec': 'dummy_proc'}])]
    assert view.view_ctx.parameters[PROCESS] == 'dummy'
    assert mocked_stats.call_args_list == [call(mocked_root, {'namespec': 'dummy'})]


def test_get_process_data(mocker, view):
    """ Test the ProcAddressView.get_process_data method. """
    # patch context
    process_status_1 = Mock(rules=Mock(expected_load=8))
    process_status_2 = Mock(rules=Mock(expected_load=17))
    process_status_3 = Mock(rules=Mock(expected_load=26))
    mocker.patch.object(view.sup_ctx, 'get_process', side_effect=[process_status_1, process_status_2, process_status_3])
    view.view_ctx = Mock(local_node_name='10.0.0.1',
                         **{'get_process_stats.side_effect': [(2, 'stats #1'), (8, 'stats #2'), (4, 'stats #3')]})
    # test RPC Error
    mocked_process_info = mocker.patch.object(view.supvisors.info_source.supervisor_rpc_interface, 'getAllProcessInfo')
    mocked_process_info.side_effect = RPCError('failed RPC')
    assert view.get_process_data() == ([], [])
    # test normal behavior
    mocked_sort = mocker.patch.object(view, 'sort_data', return_value=['process_2', 'process_1', 'process_3'])
    mocked_process_info.side_effect = None
    mocked_process_info.return_value = [process_info_by_name('xfontsel'), process_info_by_name('segv'),
                                        process_info_by_name('firefox')]
    assert view.get_process_data() == ['process_2', 'process_1', 'process_3']
    # test intermediate list
    data1 = {'application_name': 'sample_test_1', 'process_name': 'xfontsel', 'namespec': 'sample_test_1:xfontsel',
             'single': False, 'node_name': '10.0.0.1',
             'statename': 'RUNNING', 'statecode': 20, 'gravity': 'RUNNING',
             'description': 'pid 80879, uptime 0:01:19',
             'expected_load': 8, 'nb_cores': 2, 'proc_stats': 'stats #1'}
    data2 = {'application_name': 'crash', 'process_name': 'segv', 'namespec': 'crash:segv',
             'single': False, 'node_name': '10.0.0.1',
             'statename': 'BACKOFF', 'statecode': 30, 'gravity': 'BACKOFF',
             'description': 'Exited too quickly (process log may have details)',
             'expected_load': 17, 'nb_cores': 8, 'proc_stats': 'stats #2'}
    data3 = {'application_name': 'firefox', 'process_name': 'firefox', 'namespec': 'firefox',
             'single': True, 'node_name': '10.0.0.1',
             'statename': 'EXITED', 'statecode': 100, 'gravity': 'EXITED',
             'description': 'Sep 14 05:18 PM',
             'expected_load': 26, 'nb_cores': 4, 'proc_stats': 'stats #3'}
    assert mocked_sort.call_count == 1
    assert len(mocked_sort.call_args_list[0]) == 2
    # access to internal call data
    call_data = mocked_sort.call_args_list[0][0][0]
    assert call_data[0] == data1
    assert call_data[1] == data2
    assert call_data[2] == data3


def test_sort_data(mocker, view):
    """ Test the ProcAddressView.sort_data method. """
    mocker.patch('supvisors.viewprocaddress.ProcAddressView.get_application_summary',
                 side_effect=[{'application_name': 'crash', 'process_name': None},
                              {'application_name': 'sample_test_1', 'process_name': None},
                              {'application_name': 'sample_test_2', 'process_name': None}] * 2)
    # test empty parameter
    assert view.sort_data([]) == ([], [])
    # build process list
    processes = [{'application_name': info['group'], 'process_name': info['name'],
                  'single': info['group'] == info['name']}
                 for info in ProcessInfoDatabase]
    shuffle(processes)
    # patch context
    view.view_ctx = Mock(**{'get_application_shex.side_effect': [(True, 0), (True, 0), (True, 0),
                                                                 (True, 0), (False, 0), (False, 0)]})
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


def test_get_application_summary(view):
    """ Test the ProcAddressView.get_application_summary method. """
    # patch the context
    view.view_ctx = Mock(local_node_name='10.0.0.1')
    view.sup_ctx.applications['dummy_appli'] = Mock(state=ApplicationStates.RUNNING,
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
    assert view.get_application_summary('dummy_appli', []) == expected
    # test with non-running processes
    expected.update({'nb_processes': 1})
    assert view.get_application_summary('dummy_appli', [proc_4]) == expected
    # test with a mix of running and non-running processes
    expected.update({'nb_processes': 4, 'expected_load': 27, 'nb_cores': 8, 'proc_stats': [[18], [27]]})
    assert view.get_application_summary('dummy_appli', [proc_1, proc_2, proc_3, proc_4]) == expected


def test_write_process_table(mocker, view):
    """ Test the ProcAddressView.write_process_table method. """
    mocked_appli = mocker.patch('supvisors.viewprocaddress.ProcAddressView.write_application_status')
    mocked_common = mocker.patch('supvisors.viewhandler.ViewHandler.write_common_process_status')
    # patch the meld elements
    table_mid = Mock()
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
                                             (tr_elt_5, {'process_name': 'info_5', 'single': False})]})
    mocked_root = Mock(**{'findmeld.side_effect': [table_mid, tr_mid]})
    # test call with no data
    view.write_process_table(mocked_root, {})
    assert table_mid.replace.call_args_list == [call('No programs to manage')]
    assert not mocked_common.called
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
    view.write_process_table(mocked_root, [{}])
    assert not table_mid.replace.called
    assert mocked_common.call_args_list == [call(tr_elt_0, {'process_name': 'info_0', 'single': True}),
                                            call(tr_elt_2, {'process_name': 'info_2', 'single': False}),
                                            call(tr_elt_3, {'process_name': 'info_3', 'single': False}),
                                            call(tr_elt_5, {'process_name': 'info_5', 'single': False})]
    assert mocked_appli.call_args_list == [call(tr_elt_1, {'process_name': None}, True),
                                           call(tr_elt_4, {'process_name': None}, False)]
    assert not tr_elt_0.findmeld.return_value.replace.called
    assert not tr_elt_1.findmeld.return_value.replace.called
    assert tr_elt_2.findmeld.return_value.replace.call_args_list == [call('')]
    assert tr_elt_3.findmeld.return_value.replace.call_args_list == [call('')]
    assert not tr_elt_4.findmeld.return_value.replace.called
    assert tr_elt_5.findmeld.return_value.replace.call_args_list == [call('')]
    assert tr_elt_0.attrib['class'] == 'brightened'
    assert tr_elt_1.attrib['class'] == 'shaded'
    assert tr_elt_2.attrib['class'] == 'brightened'
    assert tr_elt_3.attrib['class'] == 'shaded'
    assert tr_elt_4.attrib['class'] == 'brightened'
    assert tr_elt_5.attrib['class'] == 'shaded'


def test_write_application_status(mocker, view):
    """ Test the ProcAddressView.write_application_status method. """
    mocked_common = mocker.patch('supvisors.viewhandler.ViewHandler.write_common_status')
    # patch the context
    view.view_ctx = Mock(**{'get_application_shex.side_effect': [(False, '010'), (True, '101')],
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
    view.write_application_status(mocked_root, info, True)
    assert mocked_common.call_args_list == [call(mocked_root, info)]
    assert 'rowspan' not in shex_td_mid.attrib
    assert 'class' not in shex_td_mid.attrib
    assert shex_a_mid.content.call_args_list == [call('[+]')]
    assert shex_a_mid.attributes.call_args_list == [call(href='an url')]
    assert view.view_ctx.format_url.call_args_list == [call('', 'procaddress.html', shex='010'),
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
    view.view_ctx.format_url.reset_mock()
    # test call with application processes displayed
    view.write_application_status(mocked_root, info, False)
    assert mocked_common.call_args_list == [call(mocked_root, info)]
    assert shex_td_mid.attrib['rowspan'] == '5'
    assert shex_td_mid.attrib['class'] == 'brightened'
    assert shex_a_mid.content.call_args_list == [call('[\u2013]')]
    assert shex_a_mid.attributes.call_args_list == [call(href='an url')]
    assert view.view_ctx.format_url.call_args_list == [call('', 'procaddress.html', shex='101'),
                                                       call('', 'application.html', appliname='dummy_appli')]
    assert name_a_mid.content.call_args_list == [call('dummy_appli')]
    assert name_a_mid.attributes.call_args_list == [call(href='an url')]
    for mid in [start_td_mid, clear_td_mid]:
        assert mid.attrib['colspan'] == '3'
        assert mid.content.call_args_list == [call('')]
    for mid in [stop_td_mid, restart_td_mid, tailout_td_mid, tailerr_td_mid]:
        assert mid.replace.call_args_list == [call('')]
