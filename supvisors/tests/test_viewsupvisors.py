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

from unittest.mock import call, patch, Mock

import pytest
from supervisor.web import MeldView

from supvisors.web.viewsupvisors import *
from supvisors.web.webutils import PROC_INSTANCE_PAGE, SUPVISORS_PAGE
from .base import DummyHttpContext
from .conftest import create_element, to_simple_url


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
    view.view_ctx = Mock(parameters={}, **{'format_url.side_effect': to_simple_url})
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
    mocked_nav = mocker.patch('supvisors.web.viewsupvisors.SupvisorsView.write_nav')
    mocked_root = Mock()
    view.write_navigation(mocked_root)
    assert mocked_nav.call_args_list == [call(mocked_root)]


def test_write_header(mocker, view):
    """ Test the write_header method. """
    # patch context
    mocker.patch.object(view.sup_ctx, 'get_state_modes',
                        return_value={'fsm_statename': SupvisorsStates.DEPLOYMENT.name,
                                      'starting_jobs': True, 'stopping_jobs': False})
    mocked_actions = mocker.patch.object(view, 'write_supvisors_actions')
    # build root structure
    state_mid = create_element()
    starting_mid = create_element()
    stopping_mid = create_element()
    mocked_root = create_element({'state_mid': state_mid, 'starting_mid': starting_mid, 'stopping_mid': stopping_mid})
    # test call with no auto-refresh
    view.write_header(mocked_root)
    assert mocked_root.findmeld.call_args_list == [call('state_mid'), call('starting_mid'), call('stopping_mid')]
    assert state_mid.content.call_args_list == [call('DEPLOYMENT')]
    assert starting_mid.attrib['class'] == 'blink'
    assert not starting_mid.replace.called
    assert stopping_mid.attrib['class'] == ''
    assert stopping_mid.replace.call_args_list == [call('')]
    assert mocked_actions.call_args_list == [call(mocked_root)]


def test_write_supvisors_actions(view):
    """ Test the SupvisorsView.write_supvisors_actions method. """
    # set context (meant to be set through render)
    view.view_ctx = Mock(**{'format_url.return_value': 'an url'})
    # build root structure
    start_mid = create_element()
    restart_mid = create_element()
    shutdown_mid = create_element()
    mocked_root = create_element({'start_a_mid': start_mid,
                                  'restart_a_mid': restart_mid,
                                  'shutdown_a_mid': shutdown_mid})
    # test call
    view.write_supvisors_actions(mocked_root)
    assert mocked_root.findmeld.call_args_list == [call('start_a_mid'), call('restart_a_mid'), call('shutdown_a_mid')]
    assert view.view_ctx.format_url.call_args_list == [call('', SUPVISORS_PAGE, **{ACTION: 'sup_sync'}),
                                                       call('', SUPVISORS_PAGE, **{ACTION: 'sup_restart'}),
                                                       call('', SUPVISORS_PAGE, **{ACTION: 'sup_shutdown'})]
    assert start_mid.attributes.call_args_list == [call(href='an url')]
    assert restart_mid.attributes.call_args_list == [call(href='an url')]
    assert shutdown_mid.attributes.call_args_list == [call(href='an url')]


def test_write_contents(mocker, view):
    """ Test the SupvisorsView.write_contents method. """
    mocked_boxes = mocker.patch('supvisors.web.viewsupvisors.SupvisorsView.write_instance_boxes')
    mocked_conflicts = mocker.patch('supvisors.web.viewsupvisors.SupvisorsView.write_conciliation_table')
    mocked_strategies = mocker.patch('supvisors.web.viewsupvisors.SupvisorsView.write_conciliation_strategies')
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
    mocker.patch('supvisors.web.viewsupvisors.simple_localtime', return_value='12:34:30')
    mocked_status = Mock(identifier='10.0.0.1', state=SupvisorsInstanceStates.RUNNING,
                         **{'has_active_state.return_value': True,
                            'get_load.return_value': 17,
                            'get_remote_time.return_value': 1234})
    # build root structure with one single element
    mocked_sync_a_mid = create_element()
    mocked_sync_th_mid = create_element({'user_sync_a_mid': mocked_sync_a_mid})
    mocked_identifier_mid = create_element()
    mocked_state_mid = create_element()
    mocked_time_mid = create_element()
    mocked_percent_mid = create_element()
    mid_map = {'user_sync_th_mid': mocked_sync_th_mid,
               'identifier_a_mid': mocked_identifier_mid, 'state_th_mid': mocked_state_mid,
               'time_th_mid': mocked_time_mid, 'percent_th_mid': mocked_percent_mid}
    mocked_root = create_element(mid_map)
    # test call in RUNNING state but not master and user_sync
    view._write_instance_box_title(mocked_root, mocked_status, True)
    # test USER sync element
    assert not mocked_sync_th_mid.replace.called
    assert mocked_sync_a_mid.attrib['class'] == 'on'
    expected_url = 'http:///index.html?ident=10.0.0.1&action=sup_master_sync'
    assert mocked_sync_a_mid.attributes.call_args_list == [call(href=expected_url)]
    assert mocked_sync_a_mid.content.call_args_list == [call('&#160;&#10026;&#160;')]
    # test Supvisors instance element
    assert mocked_identifier_mid.attrib['class'] == 'on'
    expected_url = 'http://10.0.0.1/proc_instance.html'
    assert mocked_identifier_mid.attributes.call_args_list == [call(href=expected_url)]
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
    # test call in RUNNING state and master and not user_sync
    view.sup_ctx.master_identifier = '10.0.0.1'
    view._write_instance_box_title(mocked_root, mocked_status, False)
    # test USER sync element
    assert mocked_sync_th_mid.replace.call_args_list == [call('')]
    assert mocked_sync_a_mid.attrib['class'] == ''
    assert not mocked_sync_a_mid.attributes.called
    assert not mocked_sync_a_mid.content.called
    # test Supvisors instance element
    assert mocked_identifier_mid.attrib['class'] == 'on'
    expected_url = 'http://10.0.0.1/proc_instance.html'
    assert mocked_identifier_mid.attributes.call_args_list == [call(href=expected_url)]
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
    # test call in SILENT state and user sync
    mocked_status = Mock(identifier='10.0.0.1', state=SupvisorsInstanceStates.SILENT,
                         **{'has_active_state.return_value': False,
                            'get_load.return_value': 0})
    view._write_instance_box_title(mocked_root, mocked_status, True)
    # test USER sync element
    assert not mocked_sync_th_mid.replace.called
    assert mocked_sync_a_mid.attrib['class'] == 'off'
    assert not mocked_sync_a_mid.attributes.called
    assert mocked_sync_a_mid.content.call_args_list == [call('&#160;&#10026;&#160;')]
    # test Supvisors instance element
    assert mocked_identifier_mid.attrib['class'] == 'off'
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
    view._write_instance_box_processes(mocked_root, mocked_status, True)
    # test elements
    assert not mocked_appli_tr_mid.repeat.called
    assert mocked_process_li_mid.replace.call_args_list == [call('')]
    # 2. patch context for multiple running process on node
    mocked_process_1 = Mock(application_name='dummy_appli', process_name='dummy_proc')
    mocked_process_2 = Mock(application_name='other_appli', process_name='other_proc')
    mocked_status = Mock(**{'running_processes.return_value': [mocked_process_1, mocked_process_2]})
    # build root structure
    mocked_name_mids = [create_element(), create_element()]
    mocked_process_a_mids = [create_element(), create_element()]
    mocked_process_li_mid = Mock(**{'findmeld.side_effect': mocked_process_a_mids * 2})
    mocked_process_template = Mock(**{'repeat.side_effect': [[(mocked_process_li_mid, mocked_process_1)],
                                                             [(mocked_process_li_mid, mocked_process_2)]] * 2})
    mocked_appli_tr_mids = [create_element({'app_name_td_mid': mocked_name_mids[0],
                                            'process_li_mid': mocked_process_template}),
                            create_element({'app_name_td_mid': mocked_name_mids[1],
                                            'process_li_mid': mocked_process_template})]
    mocked_appli_template = create_element()
    mocked_appli_template.repeat.return_value = [(mocked_appli_tr_mids[0], 'dummy_appli'),
                                                 (mocked_appli_tr_mids[1], 'other_appli')]
    mocked_root = create_element({'appli_tr_mid': mocked_appli_template})
    # 2.1 test call with 2 running processes and user_sync set
    view._write_instance_box_processes(mocked_root, mocked_status, True)
    # test elements
    assert not mocked_appli_template.findmeld.called
    # test shade in mocked_appli_tr_mids
    assert mocked_appli_tr_mids[0].attrib['class'] == 'brightened'
    assert mocked_appli_tr_mids[1].attrib['class'] == 'shaded'
    # test application names in mocked_name_mids
    assert mocked_name_mids[0].content.call_args_list == [call('dummy_appli')]
    assert mocked_name_mids[0].attrib['colspan'] == '2'
    assert mocked_name_mids[1].content.call_args_list == [call('other_appli')]
    assert mocked_name_mids[1].attrib['colspan'] == '2'
    # test process elements in mocked_process_a_mids
    assert mocked_process_a_mids[0].content.call_args_list == [call('dummy_proc')]
    assert mocked_process_a_mids[1].content.call_args_list == [call('other_proc')]
    # reset mocks
    for mid in mocked_name_mids + mocked_process_a_mids:
        mid.attrib = {}
        mid.content.reset_mock()
    # 2.2 test call with 2 running processes and user_sync set
    view._write_instance_box_processes(mocked_root, mocked_status, False)
    # test elements
    assert not mocked_appli_template.findmeld.called
    # test shade in mocked_appli_tr_mids
    assert mocked_appli_tr_mids[0].attrib['class'] == 'brightened'
    assert mocked_appli_tr_mids[1].attrib['class'] == 'shaded'
    # test application names in mocked_name_mids
    assert mocked_name_mids[0].content.call_args_list == [call('dummy_appli')]
    assert 'colspan' not in mocked_name_mids[0].attrib
    assert mocked_name_mids[1].content.call_args_list == [call('other_appli')]
    assert 'colspan' not in mocked_name_mids[1].attrib
    # test process elements in mocked_process_a_mids
    assert mocked_process_a_mids[0].content.call_args_list == [call('dummy_proc')]
    assert mocked_process_a_mids[1].content.call_args_list == [call('other_proc')]


def test_write_node_boxes(mocker, view):
    """ Test the write_instance_boxes method. """
    mocked_box_processes = mocker.patch('supvisors.web.viewsupvisors.SupvisorsView._write_instance_box_processes')
    mocked_box_title = mocker.patch('supvisors.web.viewsupvisors.SupvisorsView._write_instance_box_title')
    # patch context
    view.supvisors.options.multicast_group = '293.0.0.1:7777'
    local_identifier = view.sup_ctx.local_identifier
    ref_instances = view.sup_ctx.instances
    view.sup_ctx.instances = {local_identifier: ref_instances[local_identifier],
                              '10.0.0.1': ref_instances['10.0.0.1']}
    # build root structure with one single element
    mocked_box_mid_1 = Mock()
    mocked_box_mid_2 = Mock()
    mocked_address_template = Mock(**{'repeat.return_value': [(mocked_box_mid_1, local_identifier),
                                                              (mocked_box_mid_2, '10.0.0.1')]})
    mocked_root = Mock(**{'findmeld.return_value': mocked_address_template})
    # test call with user sync disabled
    view.write_instance_boxes(mocked_root)
    assert mocked_box_title.call_args_list == [call(mocked_box_mid_1, ref_instances[local_identifier], False),
                                               call(mocked_box_mid_2, ref_instances['10.0.0.1'], False)]
    assert mocked_box_processes.call_args_list == [call(mocked_box_mid_1, ref_instances[local_identifier], False),
                                                   call(mocked_box_mid_2, ref_instances['10.0.0.1'], False)]
    mocker.resetall()
    # test call with user sync enabled
    view.supvisors.options.synchro_options = [SynchronizationOptions.USER]
    view.supvisors.fsm.state = SupvisorsStates.INITIALIZATION
    view.write_instance_boxes(mocked_root)
    assert mocked_box_title.call_args_list == [call(mocked_box_mid_1, ref_instances[local_identifier], True),
                                               call(mocked_box_mid_2, ref_instances['10.0.0.1'], True)]
    assert mocked_box_processes.call_args_list == [call(mocked_box_mid_1, ref_instances[local_identifier], True),
                                                   call(mocked_box_mid_2, ref_instances['10.0.0.1'], True)]


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
    mocked_name = mocker.patch('supvisors.web.viewsupvisors.SupvisorsView._write_conflict_name')
    mocked_node = mocker.patch('supvisors.web.viewsupvisors.SupvisorsView._write_conflict_identifier')
    mocked_time = mocker.patch('supvisors.web.viewsupvisors.SupvisorsView._write_conflict_uptime')
    mocked_actions = mocker.patch('supvisors.web.viewsupvisors.SupvisorsView._write_conflict_process_actions')
    mocked_strategies = mocker.patch('supvisors.web.viewsupvisors.SupvisorsView._write_conflict_strategies')
    mocked_data = mocker.patch('supvisors.web.viewsupvisors.SupvisorsView.get_conciliation_data')
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
    mocked_methods = [mocker.patch('supvisors.web.viewsupvisors.delayed_error', return_value='delayed error'),
                      mocker.patch('supvisors.web.viewsupvisors.delayed_warn', return_value='delayed warning'),
                      mocker.patch('supvisors.web.viewsupvisors.error_message', return_value='error'),
                      mocker.patch('supvisors.web.viewsupvisors.warn_message', return_value='warning')]
    _check_sup_action(mocker, view, view.sup_restart_action, 'restart', *mocked_methods)


def test_sup_shutdown_action(mocker, view):
    """ Test the sup_shutdown_action method. """
    mocked_methods = [mocker.patch('supvisors.web.viewsupvisors.delayed_error', return_value='delayed error'),
                      mocker.patch('supvisors.web.viewsupvisors.delayed_warn', return_value='delayed warning'),
                      mocker.patch('supvisors.web.viewsupvisors.error_message', return_value='error'),
                      mocker.patch('supvisors.web.viewsupvisors.warn_message', return_value='warning')]
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


def test_stop_action(mocker, view):
    """ Test the stop_action method. """
    mocked_info = mocker.patch('supvisors.web.viewsupvisors.info_message', return_value='done')
    process = Mock(running_identifiers=['10.0.0.1', '10.0.0.2', '10.0.0.3'])
    mocked_get = mocker.patch.object(view.supvisors.context, 'get_process', return_value=process)
    # test call
    mocked_rpc = mocker.patch.object(view.supvisors.internal_com.pusher, 'send_stop_process')
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
    mocked_info = mocker.patch('supvisors.web.viewsupvisors.info_message', return_value='done')
    process = Mock(running_identifiers=['10.0.0.1', '10.0.0.2', '10.0.0.3'])
    mocked_get = mocker.patch.object(view.supvisors.context, 'get_process', return_value=process)
    # test call
    with patch.object(view.supvisors.internal_com.pusher, 'send_stop_process') as mocked_rpc:
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
    mocked_info = mocker.patch('supvisors.web.viewsupvisors.delayed_info', return_value='delayed info')
    mocked_conciliate = mocker.patch('supvisors.web.viewsupvisors.conciliate_conflicts')
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


def test_sup_sync_action(mocker, view):
    """ Test the conciliation_action method. """
    mocked_derror = mocker.patch('supvisors.web.viewsupvisors.delayed_error', return_value='delayed error')
    mocked_dwarn = mocker.patch('supvisors.web.viewsupvisors.delayed_warn', return_value='delayed warning')
    mocked_rpc = mocker.patch.object(view.supvisors.supervisor_data.supvisors_rpc_interface, 'end_sync',
                                     side_effect=RPCError('failed RPC'))
    # test error with no parameter
    assert view.sup_sync_action() == 'delayed error'
    assert mocked_rpc.call_args_list == [call('')]
    assert mocked_derror.called
    assert not mocked_dwarn.called
    mocked_rpc.reset_mock()
    mocked_derror.reset_mock()
    # test success with no parameter
    mocked_rpc.side_effect = None
    mocked_rpc.return_value = True
    assert view.sup_sync_action() == 'delayed warning'
    assert mocked_rpc.call_args_list == [call('')]
    assert not mocked_derror.called
    assert mocked_dwarn.called
    mocked_rpc.reset_mock()
    mocked_dwarn.reset_mock()
    # test success with parameter
    assert view.sup_sync_action('10.0.0.1') == 'delayed warning'
    assert mocked_rpc.call_args_list == [call('10.0.0.1')]
    assert not mocked_derror.called
    assert mocked_dwarn.called


def test_make_callback(mocker, view):
    """ Test the make_callback method. """
    mocked_conciliate = mocker.patch.object(view, 'conciliation_action', return_value='conciliation called')
    for action_name in list(view.global_methods.keys()):
        view.global_methods[action_name] = Mock(return_value='%s called' % action_name)
    for action_name in list(view.process_methods.keys()):
        view.process_methods[action_name] = Mock(return_value='%s called' % action_name)
    mocked_sync = mocker.patch.object(view, 'sup_sync_action', return_value='sup_master_sync called')
    # patch context
    view.view_ctx = Mock(**{'get_identifier.return_value': '10.0.0.2'})
    # test strategies but USER
    for strategy in view.strategies:
        assert view.make_callback('dummy_namespec', strategy) == 'conciliation called'
        assert mocked_conciliate.call_args_list == [call('dummy_namespec', strategy.upper())]
        mocked_conciliate.reset_mock()
    assert not any(mocked.called for mocked in view.global_methods.values())
    assert not any(mocked.called for mocked in view.process_methods.values())
    assert not mocked_sync.called
    # test USER strategy
    assert not view.make_callback('dummy_namespec', 'user')
    assert not any(mocked.called for mocked in view.global_methods.values())
    assert not any(mocked.called for mocked in view.process_methods.values())
    assert not mocked_sync.called
    # test global actions
    for action in ['sup_sync', 'sup_restart', 'sup_shutdown']:
        assert view.make_callback(None, action) == '%s called' % action
        assert view.global_methods[action].call_args_list == [call()]
        view.global_methods[action].reset_mock()
        assert not any(mocked.called for mocked in view.global_methods.values())
    assert not any(mocked.called for mocked in view.process_methods.values())
    assert not mocked_conciliate.called
    assert not mocked_sync.called
    # test process actions
    for action in ['pstop', 'pkeep']:
        assert view.make_callback('dummy_namespec', action) == '%s called' % action
        assert view.process_methods[action].call_args_list == [call('dummy_namespec', '10.0.0.2')]
        view.process_methods[action].reset_mock()
        assert not any(mocked.called for mocked in view.process_methods.values())
    assert not any(mocked.called for mocked in view.global_methods.values())
    assert not mocked_sync.called
    # test user sync action
    assert view.make_callback(None, 'sup_master_sync') == 'sup_master_sync called'
    assert mocked_sync.call_args_list == [call('10.0.0.2')]
    assert not any(mocked.called for mocked in view.global_methods.values())
    assert not any(mocked.called for mocked in view.process_methods.values())
    assert not mocked_conciliate.called
