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

from supervisor.web import MeldView

from unittest.mock import call, patch, Mock

from supvisors.viewsupvisors import *
from supvisors.webutils import PROC_INSTANCE_PAGE, SUPVISORS_PAGE

from .base import DummyHttpContext
from .conftest import create_element


@pytest.fixture
def http_context(supvisors):
    """ Fixture for a consistent mocked HTTP context provided by Supervisor. """
    http_context = DummyHttpContext('ui/index.html')
    http_context.supervisord.supvisors = supvisors
    supvisors.supervisor_data.supervisord = http_context.supervisord
    return http_context


@pytest.fixture
def view(http_context):
    """ Fixture for the instance to test. """
    view = SupvisorsView(http_context)
    view.view_ctx = Mock(parameters={}, **{'format_url.return_value': 'an url'})
    return view

def test_init(view):
    """ Test the values set at construction. """
    # test instance inheritance
    for klass in [ViewHandler, MeldView]:
        assert isinstance(view, klass)
    # test parameter page name
    assert view.page_name == SUPVISORS_PAGE
    # test strategy names
    for strategy in view.strategies:
        assert strategy.upper() in ConciliationStrategies._member_names_
    assert 'user' not in view.strategies
    # test action methods storage
    assert all(callable(cb) for cb in view.global_methods.values())
    assert all(callable(cb) for cb in view.process_methods.values())


def test_write_navigation(mocker, view):
    """ Test the write_navigation method. """
    mocked_nav = mocker.patch('supvisors.viewsupvisors.SupvisorsView.write_nav')
    mocked_root = Mock()
    view.write_navigation(mocked_root)
    assert mocked_nav.call_args_list == [call(mocked_root)]


def test_write_header(view):
    """ Test the write_header method. """
    # patch context
    view.supvisors.fsm.state = SupvisorsStates.OPERATION
    # build root structure
    mocked_state_mid = Mock()
    mocked_root = Mock(**{'findmeld.return_value': mocked_state_mid})
    # test call with no auto-refresh
    view.write_header(mocked_root)
    assert mocked_state_mid.content.call_args_list == [call('OPERATION')]


def test_write_contents(mocker, view):
    """ Test the write_contents method. """
    mocked_boxes = mocker.patch('supvisors.viewsupvisors.SupvisorsView.write_instance_boxes')
    mocked_conflicts = mocker.patch('supvisors.viewsupvisors.SupvisorsView.write_conciliation_table')
    mocked_strategies = mocker.patch('supvisors.viewsupvisors.SupvisorsView.write_conciliation_strategies')
    # patch context
    view.supvisors.fsm.state = SupvisorsStates.OPERATION
    mocker.patch.object(view.sup_ctx, 'conflicts', return_value=True)
    # build root structure
    mocked_box_mid = Mock()
    mocked_conflict_mid = Mock()
    mocked_root = Mock(**{'findmeld.side_effect': [mocked_conflict_mid, mocked_box_mid]})
    # test call in normal state (no conciliation)
    view.write_contents(mocked_root)
    assert mocked_boxes.call_args_list == [call(mocked_root)]
    assert not mocked_strategies.called
    assert not mocked_conflicts.called
    assert mocked_conflict_mid.replace.call_args_list == [call('')]
    assert not mocked_box_mid.replace.called
    # reset mocks
    mocked_boxes.reset_mock()
    mocked_conflict_mid.replace.reset_mock()
    # test call in conciliation state
    view.supvisors.fsm.state = SupvisorsStates.CONCILIATION
    view.write_contents(mocked_root)
    assert mocked_strategies.call_args_list == [call(mocked_root)]
    assert mocked_conflicts.call_args_list == [call(mocked_root)]
    assert not mocked_boxes.called
    assert mocked_box_mid.replace.call_args_list == [call('')]
    assert not mocked_conflict_mid.replace.called


def test_write_instance_box_title(mocker, view):
    """ Test the _write_instance_box_title method. """
    # patch context
    mocker.patch('supvisors.viewsupvisors.simple_localtime', return_value='12:34:30')
    mocked_status = Mock(identifier='10.0.0.1', state=SupvisorsInstanceStates.RUNNING,
                         **{'get_load.return_value': 17, 'get_remote_time.return_value': 1234})
    # build root structure with one single element
    mocked_identifier_mid = create_element()
    mocked_state_mid = create_element()
    mocked_time_mid = create_element()
    mocked_percent_mid = create_element()
    mid_map = {'identifier_th_mid': mocked_identifier_mid, 'state_th_mid': mocked_state_mid,
               'time_th_mid': mocked_time_mid, 'percent_th_mid': mocked_percent_mid}
    mocked_root = create_element(mid_map)
    # test call in RUNNING state but not master
    view._write_instance_box_title(mocked_root, mocked_status)
    # test address element
    assert mocked_identifier_mid.attrib['class'] == 'on'
    assert mocked_identifier_mid.attributes.call_args_list == [call(href='an url')]
    assert mocked_identifier_mid.content.call_args_list == [call('10.0.0.1')]
    # test state element
    assert mocked_state_mid.attrib['class'] == 'RUNNING state'
    assert mocked_state_mid.content.call_args_list == [call('RUNNING')]
    # test time element
    assert mocked_time_mid.content.call_args_list == [call('12:34:30')]
    # test loading element
    assert mocked_percent_mid.content.call_args_list == [call('17%')]
    # reset mocks and attributes
    mocked_root.reset_all()
    # test call in RUNNING state and master
    view.sup_ctx.master_identifier = '10.0.0.1'
    view._write_instance_box_title(mocked_root, mocked_status)
    # test address element
    assert mocked_identifier_mid.attrib['class'] == 'on'
    assert mocked_identifier_mid.attributes.call_args_list == [call(href='an url')]
    assert mocked_identifier_mid.content.call_args_list == [call(f'{MASTER_SYMBOL} 10.0.0.1')]
    # test state element
    assert mocked_state_mid.attrib['class'] == 'RUNNING state'
    assert mocked_state_mid.content.call_args_list == [call('RUNNING')]
    # test time element
    assert mocked_time_mid.content.call_args_list == [call('12:34:30')]
    # test loading element
    assert mocked_percent_mid.content.call_args_list == [call('17%')]
    # reset mocks and attributes
    mocked_root.reset_all()
    # test call in SILENT state
    mocked_status = Mock(identifier='10.0.0.1', state=SupvisorsInstanceStates.SILENT, **{'get_load.return_value': 0})
    view._write_instance_box_title(mocked_root, mocked_status)
    # test node element
    assert mocked_identifier_mid.attrib['class'] == ''
    assert not mocked_identifier_mid.attributes.called
    assert mocked_identifier_mid.content.call_args_list == [call(f'{MASTER_SYMBOL} 10.0.0.1')]
    # test state element
    assert mocked_state_mid.attrib['class'] == 'SILENT state'
    assert mocked_state_mid.content.call_args_list == [call('SILENT')]
    # test time element
    assert not mocked_time_mid.content.called
    # test loading element
    assert mocked_percent_mid.content.call_args_list == [call('0%')]


def test_write_node_box_processes(view):
    """ Test the _write_instance_box_processes method. """
    # 1. patch context for no running process on node
    mocked_status = Mock(**{'running_processes.return_value': {}})
    # build root structure with one single element
    mocked_process_li_mid = create_element()
    mocked_appli_tr_mid = create_element({'process_li_mid': mocked_process_li_mid})
    mocked_root = create_element({'appli_tr_mid': mocked_appli_tr_mid})
    # test call with no running process
    view._write_instance_box_processes(mocked_root, mocked_status)
    # test elements
    assert not mocked_appli_tr_mid.repeat.called
    assert mocked_process_li_mid.replace.call_args_list == [call('')]
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
    mocked_appli_tr_mids = [create_element({'app_name_td_mid': mocked_name_mids[0],
                                            'process_li_mid': mocked_process_template}),
                            create_element({'app_name_td_mid': mocked_name_mids[1],
                                            'process_li_mid': mocked_process_template})]
    mocked_appli_template = create_element()
    mocked_appli_template.repeat.return_value = [(mocked_appli_tr_mids[0], 'dummy_appli'),
                                                 (mocked_appli_tr_mids[1], 'other_appli')]
    mocked_root = create_element({'appli_tr_mid': mocked_appli_template})
    # test call with 2 running processes
    view._write_instance_box_processes(mocked_root, mocked_status)
    # test elements
    assert not mocked_appli_template.findmeld.called
    # test shade in mocked_appli_tr_mids
    assert mocked_appli_tr_mids[0].attrib['class'] == 'brightened'
    assert mocked_appli_tr_mids[1].attrib['class'] == 'shaded'
    # test application names in mocked_name_mids
    assert mocked_name_mids[0].content.call_args_list == [call('dummy_appli')]
    assert mocked_name_mids[1].content.call_args_list == [call('other_appli')]
    # test process elements in mocked_process_a_mids
    assert mocked_process_a_mids[0].content.call_args_list == [call('dummy_proc')]
    assert mocked_process_a_mids[1].content.call_args_list == [call('other_proc')]


def test_write_node_boxes(mocker, view):
    """ Test the write_instance_boxes method. """
    mocked_box_processes = mocker.patch('supvisors.viewsupvisors.SupvisorsView._write_instance_box_processes')
    mocked_box_title = mocker.patch('supvisors.viewsupvisors.SupvisorsView._write_instance_box_title')
    # patch context
    mocked_node_1 = Mock(address_name='10.0.0.1')
    mocked_node_2 = Mock(address_name='10.0.0.2')
    view.sup_ctx.instances = {'10.0.0.1': mocked_node_1, '10.0.0.2': mocked_node_2}
    view.view_ctx = Mock(**{'format_url.return_value': 'an url'})
    # build root structure with one single element
    mocked_box_mid_1 = Mock()
    mocked_box_mid_2 = Mock()
    mocked_address_template = Mock(**{'repeat.return_value': [(mocked_box_mid_1, '10.0.0.1'),
                                                              (mocked_box_mid_2, '10.0.0.2')]})
    mocked_root = Mock(**{'findmeld.return_value': mocked_address_template})
    # test call
    view.write_instance_boxes(mocked_root)
    assert mocked_box_title.call_args_list == [call(mocked_box_mid_1, mocked_node_1),
                                               call(mocked_box_mid_2, mocked_node_2)]
    assert mocked_box_processes.call_args_list == [call(mocked_box_mid_1, mocked_node_1),
                                                   call(mocked_box_mid_2, mocked_node_2)]


def test_write_conciliation_strategies(view):
    """ Test the write_conciliation_strategies method. """
    # patch context
    view.sup_ctx.master_address = {'10.0.0.1'}
    view.view_ctx = Mock(**{'format_url.return_value': 'an url'})
    # build root structure with one single element
    mocked_strategy_mid = Mock()
    mocked_strategy_li = Mock(**{'findmeld.return_value': mocked_strategy_mid})
    mocked_strategy_template = Mock(**{'repeat.return_value': [(mocked_strategy_li, 'infanticide')]})
    mocked_conflicts_mid = Mock(**{'findmeld.return_value': mocked_strategy_template})
    mocked_root = Mock(**{'findmeld.return_value': mocked_conflicts_mid})
    # test call
    view.write_conciliation_strategies(mocked_root)
    assert mocked_strategy_mid.attributes.call_args_list == [call(href='an url')]
    assert mocked_strategy_mid.content.call_args_list == [call('Infanticide')]


def test_write_conciliation_table(mocker, view):
    """ Test the write_conciliation_table method. """
    mocked_name = mocker.patch('supvisors.viewsupvisors.SupvisorsView._write_conflict_name')
    mocked_node = mocker.patch('supvisors.viewsupvisors.SupvisorsView._write_conflict_identifier')
    mocked_time = mocker.patch('supvisors.viewsupvisors.SupvisorsView._write_conflict_uptime')
    mocked_actions = mocker.patch('supvisors.viewsupvisors.SupvisorsView._write_conflict_process_actions')
    mocked_strategies = mocker.patch('supvisors.viewsupvisors.SupvisorsView._write_conflict_strategies')
    mocked_data = mocker.patch('supvisors.viewsupvisors.SupvisorsView.get_conciliation_data')
    # sample data
    data = [{'namespec': 'proc_1', 'rowspan': 2}, {'namespec': 'proc_1', 'rowspan': 0},
            {'namespec': 'proc_2', 'rowspan': 2}, {'namespec': 'proc_2', 'rowspan': 0}]
    # build simple root structure
    mocked_tr_elt = [Mock(attrib={}) for _ in range(4)]
    mocked_tr_mid = Mock(**{'repeat.return_value': zip(mocked_tr_elt, data)})
    mocked_div_elt = Mock(**{'findmeld.return_value': mocked_tr_mid})
    mocked_root = Mock(**{'findmeld.return_value': mocked_div_elt})
    # test call
    view.write_conciliation_table(mocked_root)
    assert mocked_data.call_args_list == [call()]
    # check elements background
    assert mocked_tr_elt[0].attrib['class'] == 'brightened'
    assert mocked_tr_elt[1].attrib['class'] == 'brightened'
    assert mocked_tr_elt[2].attrib['class'] == 'shaded'
    assert mocked_tr_elt[3].attrib['class'] == 'shaded'
    assert mocked_name.call_args_list == [call(mocked_tr_elt[0], data[0], False),
                                          call(mocked_tr_elt[1], data[1], False),
                                          call(mocked_tr_elt[2], data[2], True), call(mocked_tr_elt[3], data[3], True)]
    assert mocked_node.call_args_list == [call(mocked_tr_elt[0], data[0]), call(mocked_tr_elt[1], data[1]),
                                          call(mocked_tr_elt[2], data[2]), call(mocked_tr_elt[3], data[3])]
    assert mocked_time.call_args_list == [call(mocked_tr_elt[0], data[0]), call(mocked_tr_elt[1], data[1]),
                                          call(mocked_tr_elt[2], data[2]), call(mocked_tr_elt[3], data[3])]
    assert mocked_actions.call_args_list == [call(mocked_tr_elt[0], data[0]), call(mocked_tr_elt[1], data[1]),
                                             call(mocked_tr_elt[2], data[2]), call(mocked_tr_elt[3], data[3])]
    assert mocked_strategies.call_args_list == [call(mocked_tr_elt[0], data[0], False),
                                                call(mocked_tr_elt[1], data[1], False),
                                                call(mocked_tr_elt[2], data[2], True),
                                                call(mocked_tr_elt[3], data[3], True)]


def test_write_conflict_name(view):
    """ Test the _write_conflict_name method. """
    # build root structure with one single element
    mocked_name_mid = Mock(attrib={})
    mocked_root = Mock(**{'findmeld.return_value': mocked_name_mid})
    # test call with different values of rowspan and shade
    # first line, shaded
    info = {'namespec': 'dummy_proc', 'rowspan': 2}
    view._write_conflict_name(mocked_root, info, True)
    assert mocked_root.findmeld.call_args_list == [call('name_td_mid')]
    assert mocked_name_mid.attrib['rowspan'] == '2'
    assert mocked_name_mid.attrib['class'] == 'shaded'
    assert mocked_name_mid.content.call_args_list == [call('dummy_proc')]
    # reset mocks
    mocked_root.findmeld.reset_mock()
    mocked_name_mid.content.reset_mock()
    mocked_name_mid.attrib = {}
    # first line, non shaded
    view._write_conflict_name(mocked_root, info, False)
    assert mocked_root.findmeld.call_args_list == [call('name_td_mid')]
    assert mocked_name_mid.attrib['rowspan'] == '2'
    assert mocked_name_mid.attrib['class'] == 'brightened'
    assert mocked_name_mid.content.call_args_list == [call('dummy_proc')]
    assert not mocked_name_mid.replace.called
    # reset mocks
    mocked_root.findmeld.reset_mock()
    mocked_name_mid.content.reset_mock()
    mocked_name_mid.attrib = {}
    # not first line, shaded
    info['rowspan'] = 0
    view._write_conflict_name(mocked_root, info, True)
    assert mocked_root.findmeld.call_args_list == [call('name_td_mid')]
    assert 'rowspan' not in mocked_name_mid.attrib
    assert 'class' not in mocked_name_mid.attrib
    assert not mocked_name_mid.content.called
    assert mocked_name_mid.replace.call_args_list == [call('')]
    # reset mocks
    mocked_root.findmeld.reset_mock()
    mocked_name_mid.replace.reset_mock()
    # not first line, non shaded
    view._write_conflict_name(mocked_root, info, False)
    assert mocked_root.findmeld.call_args_list == [call('name_td_mid')]
    assert 'rowspan' not in mocked_name_mid.attrib
    assert 'class' not in mocked_name_mid.attrib
    assert not mocked_name_mid.content.called
    assert mocked_name_mid.replace.call_args_list == [call('')]


def test_write_conflict_node(view):
    """ Test the _write_conflict_identifier method. """
    # patch context
    view.view_ctx = Mock(**{'format_url.return_value': 'an url'})
    # build root structure with one single element
    mocked_addr_mid = Mock()
    mocked_root = Mock(**{'findmeld.return_value': mocked_addr_mid})
    # test call
    view._write_conflict_identifier(mocked_root, {'identifier': '10.0.0.1'})
    assert mocked_root.findmeld.call_args_list == [call('conflict_instance_a_mid')]
    assert mocked_addr_mid.attributes.call_args_list == [call(href='an url')]
    assert mocked_addr_mid.content.call_args_list == [call('10.0.0.1')]
    assert view.view_ctx.format_url.call_args_list == [call('10.0.0.1', PROC_INSTANCE_PAGE)]


def test_write_conflict_uptime(view):
    """ Test the _write_conflict_uptime method. """
    # patch context
    view.view_ctx = Mock(**{'format_url.return_value': 'an url'})
    # build root structure with one single element
    mocked_uptime_mid = Mock()
    mocked_root = Mock(**{'findmeld.return_value': mocked_uptime_mid})
    # test call
    view._write_conflict_uptime(mocked_root, {'uptime': 1234})
    assert mocked_root.findmeld.call_args_list == [call('uptime_td_mid')]
    assert mocked_uptime_mid.content.call_args_list == [call('00:20:34')]


def test_write_conflict_process_actions(view):
    """ Test the _write_conflict_process_actions method. """
    # patch context
    view.view_ctx = Mock(**{'format_url.return_value': 'an url'})
    # build root structure with one single element
    mocked_stop_mid = Mock()
    mocked_keep_mid = Mock()
    mocked_root = Mock(**{'findmeld.side_effect': [mocked_stop_mid, mocked_keep_mid]})
    # test call
    info = {'namespec': 'dummy_proc', 'identifier': '10.0.0.1'}
    view._write_conflict_process_actions(mocked_root, info)
    assert mocked_root.findmeld.call_args_list == [call('pstop_a_mid'), call('pkeep_a_mid')]
    assert mocked_stop_mid.attributes.call_args_list == [call(href='an url')]
    assert mocked_keep_mid.attributes.call_args_list == [call(href='an url')]
    assert view.view_ctx.format_url.call_args_list == [call('', SUPVISORS_PAGE, action='pstop',
                                                            ident='10.0.0.1', namespec='dummy_proc'),
                                                       call('', SUPVISORS_PAGE, action='pkeep',
                                                            ident='10.0.0.1', namespec='dummy_proc')]


def test_write_conflict_strategies(view):
    """ Test the _write_conflict_strategies method. """
    # patch context
    view.sup_ctx.master_identifier = '10.0.0.1'
    view.view_ctx = Mock(**{'format_url.return_value': 'an url'})
    # build root structure with one single element
    mocked_a_mid = Mock()
    mocked_li_mid = Mock(**{'findmeld.return_value': mocked_a_mid})
    mocked_li_template = Mock(**{'repeat.return_value': [(mocked_li_mid, 'senicide')]})
    mocked_td_mid = Mock(attrib={}, **{'findmeld.return_value': mocked_li_template})
    mocked_root = Mock(**{'findmeld.return_value': mocked_td_mid})
    # test call with different values of rowspan and shade
    # first line, shaded
    info = {'namespec': 'dummy_proc', 'rowspan': 2}
    view._write_conflict_strategies(mocked_root, info, True)
    assert mocked_td_mid.attrib['rowspan'] == '2'
    assert mocked_td_mid.attrib['class'] == 'shaded'
    assert mocked_a_mid.attributes.call_args_list == [call(href='an url')]
    assert mocked_a_mid.content.call_args_list == [call('Senicide')]
    assert view.view_ctx.format_url.call_args_list == [call('10.0.0.1', SUPVISORS_PAGE,
                                                            action='senicide', namespec='dummy_proc')]
    # reset mocks
    view.view_ctx.format_url.reset_mock()
    mocked_a_mid.attributes.reset_mock()
    mocked_a_mid.content.reset_mock()
    mocked_td_mid.attrib = {}
    # first line, not shaded
    info = {'namespec': 'dummy_proc', 'rowspan': 2}
    view._write_conflict_strategies(mocked_root, info, False)
    assert mocked_td_mid.attrib['rowspan'] == '2'
    assert mocked_td_mid.attrib['class'] == 'brightened'
    assert mocked_a_mid.attributes.call_args_list == [call(href='an url')]
    assert mocked_a_mid.content.call_args_list == [call('Senicide')]
    assert view.view_ctx.format_url.call_args_list == [call('10.0.0.1', SUPVISORS_PAGE,
                                                            action='senicide', namespec='dummy_proc')]
    # reset mocks
    view.view_ctx.format_url.reset_mock()
    mocked_a_mid.attributes.reset_mock()
    mocked_a_mid.content.reset_mock()
    mocked_td_mid.attrib = {}
    # not first line, shaded
    info = {'namespec': 'dummy_proc', 'rowspan': 0}
    view._write_conflict_strategies(mocked_root, info, True)
    assert 'rowspan' not in mocked_td_mid.attrib
    assert not mocked_a_mid.attributes.called
    assert not mocked_a_mid.content.called
    assert not mocked_a_mid.content.called
    assert not view.view_ctx.format_url.called
    assert mocked_td_mid.replace.call_args_list == [call('')]
    # reset mocks
    mocked_td_mid.replace.reset_mock()
    # not first line, not shaded
    info = {'namespec': 'dummy_proc', 'rowspan': 0}
    view._write_conflict_strategies(mocked_root, info, False)
    assert 'rowspan' not in mocked_td_mid.attrib
    assert not mocked_a_mid.attributes.called
    assert not mocked_a_mid.content.called
    assert not mocked_a_mid.content.called
    assert not view.view_ctx.format_url.called
    assert mocked_td_mid.replace.call_args_list == [call('')]


def test_get_conciliation_data(mocker, view):
    """ Test the get_conciliation_data method. """
    # patch context
    process_1 = Mock(namespec='proc_1', running_identifiers={'10.0.0.1', '10.0.0.2'},
                     info_map={'10.0.0.1': {'uptime': 12}, '10.0.0.2': {'uptime': 11}})
    process_2 = Mock(namespec='proc_2', running_identifiers={'10.0.0.3', '10.0.0.2'},
                     info_map={'10.0.0.3': {'uptime': 10}, '10.0.0.2': {'uptime': 11}})
    mocker.patch.object(view.sup_ctx, 'conflicts', return_value=[process_1, process_2])
    # test call
    expected = [{'namespec': 'proc_1', 'rowspan': 2, 'identifier': '10.0.0.1', 'uptime': 12},
                {'namespec': 'proc_1', 'rowspan': 0, 'identifier': '10.0.0.2', 'uptime': 11},
                {'namespec': 'proc_2', 'rowspan': 2, 'identifier': '10.0.0.2', 'uptime': 11},
                {'namespec': 'proc_2', 'rowspan': 0, 'identifier': '10.0.0.3', 'uptime': 10}]
    actual = view.get_conciliation_data()
    # no direct method in pytest to compare 2 lists of dicts
    for actual_single in actual:
        assert any(actual_single == expected_single for expected_single in expected)


def test_sup_restart_action(mocker, view):
    """ Test the sup_shutdown_action method. """
    mocked_methods = [mocker.patch('supvisors.viewsupvisors.delayed_error', return_value='delayed error'),
                      mocker.patch('supvisors.viewsupvisors.delayed_warn', return_value='delayed warning'),
                      mocker.patch('supvisors.viewsupvisors.error_message', return_value='error'),
                      mocker.patch('supvisors.viewsupvisors.warn_message', return_value='warning')]
    _check_sup_action(mocker, view, view.sup_restart_action, 'restart', *mocked_methods)


def test_sup_shutdown_action(mocker, view):
    """ Test the sup_shutdown_action method. """
    mocked_methods = [mocker.patch('supvisors.viewsupvisors.delayed_error', return_value='delayed error'),
                      mocker.patch('supvisors.viewsupvisors.delayed_warn', return_value='delayed warning'),
                      mocker.patch('supvisors.viewsupvisors.error_message', return_value='error'),
                      mocker.patch('supvisors.viewsupvisors.warn_message', return_value='warning')]
    _check_sup_action(mocker, view, view.sup_shutdown_action, 'shutdown', *mocked_methods)


def _check_sup_action(mocker, view, method_cb, rpc_name, mocked_derror, mocked_dwarn, mocked_error, mocked_warn):
    """ Test the sup_restart_action & sup_shutdown_action methods. """
    # test RPC error
    mocker.patch.object(view.supvisors.supervisor_data.supvisors_rpc_interface, rpc_name,
                        side_effect=RPCError('failed RPC'))
    assert method_cb() == 'delayed error'
    assert mocked_derror.called
    assert not mocked_dwarn.called
    assert not mocked_error.called
    assert not mocked_warn.called
    # reset mocks
    mocked_derror.reset_mock()
    # test direct result
    mocker.patch.object(view.supvisors.supervisor_data.supvisors_rpc_interface, rpc_name,
                        return_value='not callable object')
    assert method_cb() == 'delayed warning'
    assert not mocked_derror.called
    assert mocked_dwarn.called
    assert not mocked_error.called
    assert not mocked_warn.called
    # reset mocks
    mocked_dwarn.reset_mock()
    # test delayed result with RPC error
    mocked_onwait = Mock(side_effect=RPCError('failed RPC'))
    mocker.patch.object(view.supvisors.supervisor_data.supvisors_rpc_interface, rpc_name, return_value=mocked_onwait)
    cb = method_cb()
    assert callable(cb)
    assert cb() == 'error'
    assert not mocked_derror.called
    assert not mocked_dwarn.called
    assert mocked_error.called
    assert not mocked_warn.called
    # reset mocks
    mocked_error.reset_mock()
    # test delayed / uncompleted result
    mocked_onwait = Mock(return_value=NOT_DONE_YET)
    mocker.patch.object(view.supvisors.supervisor_data.supvisors_rpc_interface, rpc_name, return_value=mocked_onwait)
    cb = method_cb()
    assert callable(cb)
    assert cb() is NOT_DONE_YET
    assert not mocked_derror.called
    assert not mocked_dwarn.called
    assert not mocked_error.called
    assert not mocked_warn.called
    # test delayed / completed result
    mocked_onwait = Mock(return_value='done')
    mocker.patch.object(view.supvisors.supervisor_data.supvisors_rpc_interface, rpc_name, return_value=mocked_onwait)
    cb = method_cb()
    assert callable(cb)
    assert cb() == 'warning'
    assert not mocked_derror.called
    assert not mocked_dwarn.called
    assert not mocked_error.called
    assert mocked_warn.called


def test_stop_action(mocker, view):
    """ Test the stop_action method. """
    mocked_info = mocker.patch('supvisors.viewsupvisors.info_message', return_value='done')
    process = Mock(running_identifiers=['10.0.0.1', '10.0.0.2', '10.0.0.3'])
    mocked_get = mocker.patch.object(view.supvisors.context, 'get_process', return_value=process)
    # test call
    mocked_rpc = mocker.patch.object(view.supvisors.zmq.pusher, 'send_stop_process')
    cb = view.stop_action('dummy_proc', '10.0.0.2')
    assert callable(cb)
    assert mocked_rpc.call_args_list == [call('10.0.0.2', 'dummy_proc')]
    assert mocked_get.call_args_list == [call('dummy_proc')]
    # at this stage, there should be still 3 elements in identifiers
    assert cb() is NOT_DONE_YET
    assert not mocked_info.called
    # remove one identifier from list
    process.running_identifiers.remove('10.0.0.2')
    assert cb() == 'done'
    assert mocked_info.call_args_list == [call('process dummy_proc stopped on 10.0.0.2')]


def test_keep_action(mocker, view):
    """ Test the keep_action method. """
    mocked_info = mocker.patch('supvisors.viewsupvisors.info_message', return_value='done')
    process = Mock(running_identifiers=['10.0.0.1', '10.0.0.2', '10.0.0.3'])
    mocked_get = mocker.patch.object(view.supvisors.context, 'get_process', return_value=process)
    # test call
    with patch.object(view.supvisors.zmq.pusher, 'send_stop_process') as mocked_rpc:
        cb = view.keep_action('dummy_proc', '10.0.0.2')
    assert callable(cb)
    assert mocked_rpc.call_args_list == [call('10.0.0.1', 'dummy_proc'), call('10.0.0.3', 'dummy_proc')]
    assert mocked_get.call_args_list == [call('dummy_proc')]
    # at this stage, there should be still 3 elements in identifiers
    assert cb() is NOT_DONE_YET
    assert not mocked_info.called
    # remove one identifier from list
    process.running_identifiers.remove('10.0.0.1')
    assert cb() is NOT_DONE_YET
    assert not mocked_info.called
    # remove one identifier from list
    process.running_identifiers.remove('10.0.0.3')
    assert cb() == 'done'
    assert mocked_info.call_args_list == [call('processes dummy_proc stopped but on 10.0.0.2')]


def test_conciliation_action(mocker, view):
    """ Test the conciliation_action method. """
    mocked_info = mocker.patch('supvisors.viewsupvisors.delayed_info', return_value='delayed info')
    mocked_conciliate = mocker.patch('supvisors.viewsupvisors.conciliate_conflicts')
    # patch context
    mocker.patch.object(view.sup_ctx, 'get_process', return_value='a process status')
    mocker.patch.object(view.sup_ctx, 'conflicts', return_value='all conflicting process status')
    # test with no namespec
    assert view.conciliation_action(None, 'INFANTICIDE') == 'delayed info'
    assert mocked_conciliate.call_args_list == [call(view.supvisors, ConciliationStrategies.INFANTICIDE,
                                                     'all conflicting process status')]
    assert mocked_info.call_args_list == [call('INFANTICIDE in progress for all conflicts')]
    # reset mocks
    mocked_conciliate.reset_mock()
    mocked_info.reset_mock()
    # test with namespec
    assert view.conciliation_action('proc_conflict', 'STOP') == 'delayed info'
    assert mocked_conciliate.call_args_list == [call(view.supvisors,
                                                     ConciliationStrategies.STOP, ['a process status'])]
    assert mocked_info.call_args_list == [call('STOP in progress for proc_conflict')]


def test_make_callback(mocker, view):
    """ Test the make_callback method. """
    mocked_conciliate = mocker.patch.object(view, 'conciliation_action', return_value='conciliation called')
    for action_name in list(view.global_methods.keys()):
        view.global_methods[action_name] = Mock(return_value='%s called' % action_name)
    for action_name in list(view.process_methods.keys()):
        view.process_methods[action_name] = Mock(return_value='%s called' % action_name)
    # patch context
    view.view_ctx = Mock(**{'get_identifier.return_value': '10.0.0.2'})
    # test strategies but USER
    for strategy in view.strategies:
        assert view.make_callback('dummy_namespec', strategy) == 'conciliation called'
        assert mocked_conciliate.call_args_list == [call('dummy_namespec', strategy.upper())]
        mocked_conciliate.reset_mock()
    assert not any(mocked.called for mocked in view.global_methods.values())
    assert not any(mocked.called for mocked in view.process_methods.values())
    # test USER strategy
    assert not view.make_callback('dummy_namespec', 'user')
    assert not any(mocked.called for mocked in view.global_methods.values())
    assert not any(mocked.called for mocked in view.process_methods.values())
    # test global actions
    for action in ['sup_restart', 'sup_shutdown']:
        assert view.make_callback(None, action) == '%s called' % action
        assert view.global_methods[action].call_args_list == [call()]
        view.global_methods[action].reset_mock()
        assert not any(mocked.called for mocked in view.global_methods.values())
    assert not any(mocked.called for mocked in view.process_methods.values())
    assert not mocked_conciliate.called
    # test process actions
    for action in ['pstop', 'pkeep']:
        assert view.make_callback('dummy_namespec', action) == '%s called' % action
        assert view.process_methods[action].call_args_list == [call('dummy_namespec', '10.0.0.2')]
        view.process_methods[action].reset_mock()
        assert not any(mocked.called for mocked in view.process_methods.values())
    assert not any(mocked.called for mocked in view.global_methods.values())
