# ======================================================================
# Copyright 2024 Julien LE CLEACH
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

from supvisors.web.viewconciliation import *
from .conftest import create_element, to_simple_url


@pytest.fixture
def view(http_context):
    """ Fixture for the instance to test. """
    view = ConciliationView(http_context)
    view.view_ctx = Mock(parameters={}, **{'format_url.side_effect': to_simple_url})
    return view


def test_init(view):
    """ Test the values set at construction. """
    # test parameter page name
    assert view.page_name == CONCILIATION_PAGE
    # test strategy names
    for strategy in view.strategies:
        assert strategy.upper() in ConciliationStrategies._member_names_
    assert 'user' not in view.strategies
    # test action methods storage
    assert sorted(view.process_methods.keys()) == ['pkeep', 'pstop']
    assert all(callable(cb) for cb in view.process_methods.values())


def test_write_contents(mocker, supvisors, view):
    """ Test the ConciliationView.write_contents method. """
    mocked_conflicts = mocker.patch.object(view, 'write_conciliation_table')
    mocked_strategies = mocker.patch.object(view, 'write_conciliation_strategies')
    # build xhtml structure
    contents_elt = create_element()
    # test call
    view.write_contents(contents_elt)
    assert mocked_strategies.call_args_list == [call(contents_elt)]
    assert mocked_conflicts.call_args_list == [call(contents_elt)]


def test_write_conciliation_strategies(view):
    """ Test the ConciliationView.write_conciliation_strategies method. """
    # patch context
    view.view_ctx = Mock(**{'format_url.side_effect': lambda x, y, namespec, action: f'{action} url'})
    # build root structure with one single element
    infanticide_strategy_a_mid = create_element()
    senicide_strategy_a_mid = create_element()
    stop_strategy_a_mid = create_element()
    restart_strategy_a_mid = create_element()
    running_failure_strategy_a_mid = create_element()
    contents_elt = create_element({'infanticide_strategy_a_mid': infanticide_strategy_a_mid,
                                   'senicide_strategy_a_mid': senicide_strategy_a_mid,
                                   'stop_strategy_a_mid': stop_strategy_a_mid,
                                   'restart_strategy_a_mid': restart_strategy_a_mid,
                                   'running_failure_strategy_a_mid': running_failure_strategy_a_mid})
    # test call
    view.write_conciliation_strategies(contents_elt)
    assert view.view_ctx.format_url.call_args_list == [call('', CONCILIATION_PAGE, namespec='', action='senicide'),
                                                       call('', CONCILIATION_PAGE, namespec='', action='infanticide'),
                                                       call('', CONCILIATION_PAGE, namespec='', action='stop'),
                                                       call('', CONCILIATION_PAGE, namespec='', action='restart'),
                                                       call('', CONCILIATION_PAGE, namespec='',
                                                            action='running_failure')]
    assert infanticide_strategy_a_mid.attributes.call_args_list == [call(href='infanticide url')]
    assert senicide_strategy_a_mid.attributes.call_args_list == [call(href='senicide url')]
    assert stop_strategy_a_mid.attributes.call_args_list == [call(href='stop url')]
    assert restart_strategy_a_mid.attributes.call_args_list == [call(href='restart url')]
    assert running_failure_strategy_a_mid.attributes.call_args_list == [call(href='running_failure url')]


def test_get_conciliation_data(mocker, view):
    """ Test the get_conciliation_data method. """
    # patch context
    process_1 = Mock(namespec='proc_1', running_identifiers={'10.0.0.1', '10.0.0.2'},
                     info_map={'10.0.0.1': {'uptime': 12}, '10.0.0.2': {'uptime': 11}})
    process_2 = Mock(namespec='proc_2', running_identifiers={'10.0.0.3', '10.0.0.2'},
                     info_map={'10.0.0.3': {'uptime': 10}, '10.0.0.2': {'uptime': 11}})
    mocker.patch.object(view.sup_ctx, 'conflicts', return_value=[process_1, process_2])
    # test call
    expected = [{'row_type': ProcessRowTypes.APPLICATION_PROCESS, 'namespec': 'proc_1', 'nb_items': 2},
                {'row_type': ProcessRowTypes.INSTANCE_PROCESS, 'namespec': 'proc_1',
                 'identifier': '10.0.0.1', 'uptime': 12},
                {'row_type': ProcessRowTypes.INSTANCE_PROCESS, 'namespec': 'proc_1',
                 'identifier': '10.0.0.2', 'uptime': 11},
                {'row_type': ProcessRowTypes.APPLICATION_PROCESS, 'namespec': 'proc_2', 'nb_items': 2},
                {'row_type': ProcessRowTypes.INSTANCE_PROCESS, 'namespec': 'proc_2',
                 'identifier': '10.0.0.2', 'uptime': 11},
                {'row_type': ProcessRowTypes.INSTANCE_PROCESS, 'namespec': 'proc_2',
                 'identifier': '10.0.0.3', 'uptime': 10}]
    actual = view.get_conciliation_data()
    print(actual)
    # no direct method in pytest to compare 2 lists of dicts
    for actual_single in actual:
        assert any(actual_single == expected_single for expected_single in expected)


def test_write_conciliation_table(mocker, supvisors, view):
    """ Test the write_conciliation_table method. """
    mocked_process = mocker.patch.object(view, '_write_conflict_process')
    mocked_detail = mocker.patch.object(view, '_write_conflict_detail')
    mocked_data = mocker.patch.object(view, 'get_conciliation_data')
    # patch context
    view.supvisors.fsm.state = SupvisorsStates.OPERATION
    mocker.patch.object(view.sup_ctx, 'conflicts', return_value=True)
    # sample data
    data = [{'row_type': ProcessRowTypes.APPLICATION_PROCESS, 'namespec': 'proc_1', 'nb_items': 2},
            {'row_type': ProcessRowTypes.INSTANCE_PROCESS, 'namespec': 'proc_1',
             'identifier': '10.0.0.1', 'uptime': 12},
            {'row_type': ProcessRowTypes.INSTANCE_PROCESS, 'namespec': 'proc_1',
             'identifier': '10.0.0.2', 'uptime': 11},
            {'row_type': ProcessRowTypes.APPLICATION_PROCESS, 'namespec': 'proc_2', 'nb_items': 2},
            {'row_type': ProcessRowTypes.INSTANCE_PROCESS, 'namespec': 'proc_2',
             'identifier': '10.0.0.2', 'uptime': 11},
            {'row_type': ProcessRowTypes.INSTANCE_PROCESS, 'namespec': 'proc_2',
             'identifier': '10.0.0.3', 'uptime': 10}]
    # build simple root structure
    mocked_tr_elt = [create_element() for _ in data]
    conflict_tr_mid = create_element()
    conflict_tr_mid.repeat.return_value = zip(mocked_tr_elt, data)
    conflicts_div_mid = create_element({'conflict_tr_mid': conflict_tr_mid})
    contents_elt = create_element({'conflicts_div_mid': conflicts_div_mid})
    # test call when not in CONCILIATION state
    view.write_conciliation_table(contents_elt)
    assert not mocked_data.called
    assert conflicts_div_mid.replace.call_args_list == [call('No conflict')]
    assert all(tr_elt.attrib['class'] == '' for tr_elt in mocked_tr_elt)
    assert not mocked_process.called
    assert not mocked_detail.called
    conflicts_div_mid.reset_mock()
    # test call in CONCILIATION state with conflicts
    view.supvisors.fsm.state = SupvisorsStates.CONCILIATION
    view.write_conciliation_table(contents_elt)
    assert mocked_data.call_args_list == [call()]
    # check elements background
    assert mocked_tr_elt[0].attrib['class'] == 'brightened'
    assert mocked_tr_elt[1].attrib['class'] == 'shaded'
    assert mocked_tr_elt[2].attrib['class'] == 'brightened'
    assert mocked_tr_elt[3].attrib['class'] == 'shaded'
    assert mocked_tr_elt[4].attrib['class'] == 'brightened'
    assert mocked_tr_elt[5].attrib['class'] == 'shaded'
    assert mocked_process.call_args_list == [call(mocked_tr_elt[0],
                                                  {'row_type': ProcessRowTypes.APPLICATION_PROCESS,
                                                   'namespec': 'proc_1', 'nb_items': 2}, False),
                                             call(mocked_tr_elt[3],
                                                  {'row_type': ProcessRowTypes.APPLICATION_PROCESS,
                                                   'namespec': 'proc_2', 'nb_items': 2}, True)]
    assert mocked_detail.call_args_list == [call(mocked_tr_elt[1],
                                                 {'row_type': ProcessRowTypes.INSTANCE_PROCESS,
                                                  'namespec': 'proc_1', 'identifier': '10.0.0.1', 'uptime': 12}),
                                            call(mocked_tr_elt[2],
                                                 {'row_type': ProcessRowTypes.INSTANCE_PROCESS,
                                                  'namespec': 'proc_1', 'identifier': '10.0.0.2', 'uptime': 11}),
                                            call(mocked_tr_elt[4],
                                                 {'row_type': ProcessRowTypes.INSTANCE_PROCESS,
                                                  'namespec': 'proc_2', 'identifier': '10.0.0.2', 'uptime': 11}),
                                            call(mocked_tr_elt[5],
                                                 {'row_type': ProcessRowTypes.INSTANCE_PROCESS,
                                                  'namespec': 'proc_2', 'identifier': '10.0.0.3', 'uptime': 10})]


def test_write_conflict_process(mocker, view):
    """ Test the _write_conflict_process method. """
    mocked_node = mocker.patch.object(view, '_write_conflict_identifier')
    mocked_time = mocker.patch.object(view, '_write_conflict_uptime')
    mocked_actions = mocker.patch.object(view, '_write_conflict_process_actions')
    mocked_strategies = mocker.patch.object(view, '_write_conflict_strategies')
    # build xhtml structure
    section_td_mid = create_element()
    process_td_mid = create_element()
    conflict_instance_td_mid = create_element()
    pstop_td_mid = create_element()
    pkeep_td_mid = create_element()
    strategy_td_mid = create_element()
    tr_elt = create_element({'section_td_mid': section_td_mid, 'process_td_mid': process_td_mid,
                             'conflict_instance_td_mid': conflict_instance_td_mid,
                             'pstop_td_mid': pstop_td_mid, 'pkeep_td_mid': pkeep_td_mid,
                             'strategy_td_mid': strategy_td_mid})
    # test call
    info = {'row_type': ProcessRowTypes.APPLICATION_PROCESS, 'namespec': 'proc_1', 'nb_items': 2}
    view._write_conflict_process(tr_elt, info, True)
    assert section_td_mid.attrib == {'class': 'shaded', 'rowspan': '3'}
    assert process_td_mid.content.call_args_list == [call('proc_1')]
    assert not mocked_node.called
    assert not mocked_time.called
    assert not mocked_actions.called
    assert mocked_strategies.call_args_list == [call(tr_elt, info, True)]
    assert conflict_instance_td_mid.content.call_args_list == [call('')]
    assert pstop_td_mid.content.call_args_list == [call('')]
    assert pkeep_td_mid.content.call_args_list == [call('')]


def test_write_conflict_detail(mocker, view):
    """ Test the _write_conflict_detail method. """
    mocked_node = mocker.patch.object(view, '_write_conflict_identifier')
    mocked_time = mocker.patch.object(view, '_write_conflict_uptime')
    mocked_actions = mocker.patch.object(view, '_write_conflict_process_actions')
    mocked_strategies = mocker.patch.object(view, '_write_conflict_strategies')
    # build xhtml structure
    section_td_mid = create_element()
    process_td_mid = create_element()
    conflict_instance_td_mid = create_element()
    pstop_td_mid = create_element()
    pkeep_td_mid = create_element()
    strategy_td_mid = create_element()
    tr_elt = create_element({'section_td_mid': section_td_mid, 'process_td_mid': process_td_mid,
                             'conflict_instance_td_mid': conflict_instance_td_mid,
                             'pstop_td_mid': pstop_td_mid, 'pkeep_td_mid': pkeep_td_mid,
                             'strategy_td_mid': strategy_td_mid})
    # test call
    info = {'row_type': ProcessRowTypes.INSTANCE_PROCESS, 'namespec': 'proc_1', 'identifier': '10.0.0.2', 'uptime': 11}
    view._write_conflict_detail(tr_elt, info)
    assert section_td_mid.replace.call_args_list == [call('')]
    assert process_td_mid.content.call_args_list == [call(SUB_SYMBOL)]
    assert mocked_node.call_args_list == [call(tr_elt, info)]
    assert mocked_time.call_args_list == [call(tr_elt, info)]
    assert mocked_actions.call_args_list == [call(tr_elt, info)]
    assert not mocked_strategies.called
    assert strategy_td_mid.replace.call_args_list == [call('')]


def test_write_conflict_identifier(view):
    """ Test the _write_conflict_identifier method. """
    # patch context
    view.view_ctx = Mock(**{'format_url.return_value': 'an url'})
    # build root structure with one single element
    mocked_addr_mid = Mock()
    mocked_root = Mock(**{'findmeld.return_value': mocked_addr_mid})
    # test call
    view._write_conflict_identifier(mocked_root, {'identifier': '10.0.0.1:25000'})
    assert mocked_root.findmeld.call_args_list == [call('conflict_instance_a_mid')]
    assert mocked_addr_mid.attributes.call_args_list == [call(href='an url')]
    assert mocked_addr_mid.content.call_args_list == [call('10.0.0.1')]
    assert view.view_ctx.format_url.call_args_list == [call('10.0.0.1:25000', PROC_INSTANCE_PAGE)]


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
    assert mocked_uptime_mid.content.call_args_list == [call('0:20:34')]


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
    assert view.view_ctx.format_url.call_args_list == [call('', CONCILIATION_PAGE, action='pstop',
                                                            ident='10.0.0.1', namespec='dummy_proc'),
                                                       call('', CONCILIATION_PAGE, action='pkeep',
                                                            ident='10.0.0.1', namespec='dummy_proc')]


def test_write_conflict_strategies(view):
    """ Test the _write_conflict_strategies method. """
    # patch context
    view.sup_ctx.master_identifier = '10.0.0.1'
    view.view_ctx = Mock(**{'format_url.side_effect': lambda x, y, namespec, action: f'{action} url'})
    # build root structure with one single element
    infanticide_strategy_a_mid = create_element()
    senicide_strategy_a_mid = create_element()
    stop_strategy_a_mid = create_element()
    restart_strategy_a_mid = create_element()
    running_failure_strategy_a_mid = create_element()
    strategy_td_mid = create_element({'infanticide_local_strategy_a_mid': infanticide_strategy_a_mid,
                                      'senicide_local_strategy_a_mid': senicide_strategy_a_mid,
                                      'stop_local_strategy_a_mid': stop_strategy_a_mid,
                                      'restart_local_strategy_a_mid': restart_strategy_a_mid,
                                      'running_failure_local_strategy_a_mid': running_failure_strategy_a_mid})
    tr_elt = create_element({'strategy_td_mid': strategy_td_mid})
    # test call
    info = {'row_type': ProcessRowTypes.APPLICATION_PROCESS, 'namespec': 'proc_1', 'nb_items': 2}
    view._write_conflict_strategies(tr_elt, info, False)
    assert strategy_td_mid.attrib == {'class': 'brightened', 'rowspan': '3'}
    assert view.view_ctx.format_url.call_args_list == [call('10.0.0.1', CONCILIATION_PAGE, namespec='proc_1',
                                                            action='senicide'),
                                                       call('10.0.0.1', CONCILIATION_PAGE, namespec='proc_1',
                                                            action='infanticide'),
                                                       call('10.0.0.1', CONCILIATION_PAGE, namespec='proc_1',
                                                            action='stop'),
                                                       call('10.0.0.1', CONCILIATION_PAGE, namespec='proc_1',
                                                            action='restart'),
                                                       call('10.0.0.1', CONCILIATION_PAGE, namespec='proc_1',
                                                            action='running_failure')]
    assert infanticide_strategy_a_mid.attributes.call_args_list == [call(href='infanticide url')]
    assert senicide_strategy_a_mid.attributes.call_args_list == [call(href='senicide url')]
    assert stop_strategy_a_mid.attributes.call_args_list == [call(href='stop url')]
    assert restart_strategy_a_mid.attributes.call_args_list == [call(href='restart url')]
    assert running_failure_strategy_a_mid.attributes.call_args_list == [call(href='running_failure url')]


def test_stop_action(mocker, supvisors, view):
    """ Test the stop_action method. """
    mocked_info = mocker.patch('supvisors.web.viewconciliation.info_message', return_value='done')
    process = Mock(running_identifiers=['10.0.0.1', '10.0.0.2', '10.0.0.3'])
    mocked_get = mocker.patch.object(supvisors.context, 'get_process', return_value=process)
    # test call
    mocked_rpc = mocker.patch.object(supvisors.rpc_handler, 'send_stop_process')
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


def test_keep_action(mocker, supvisors, view):
    """ Test the keep_action method. """
    mocked_info = mocker.patch('supvisors.web.viewconciliation.info_message', return_value='done')
    process = Mock(running_identifiers=['10.0.0.1', '10.0.0.2', '10.0.0.3'])
    mocked_get = mocker.patch.object(supvisors.context, 'get_process', return_value=process)
    # test call
    with patch.object(supvisors.rpc_handler, 'send_stop_process') as mocked_rpc:
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


def test_conciliation_action(mocker, supvisors, view):
    """ Test the conciliation_action method. """
    mocked_info = mocker.patch('supvisors.web.viewconciliation.delayed_info', return_value='delayed info')
    mocked_conciliate = mocker.patch('supvisors.web.viewconciliation.conciliate_conflicts')
    # patch context
    mocker.patch.object(view.sup_ctx, 'get_process', return_value='a process status')
    mocker.patch.object(view.sup_ctx, 'conflicts', return_value='all conflicting process status')
    # test with no namespec
    assert view.conciliation_action(None, 'INFANTICIDE') == 'delayed info'
    assert mocked_conciliate.call_args_list == [call(supvisors, ConciliationStrategies.INFANTICIDE,
                                                     'all conflicting process status')]
    assert mocked_info.call_args_list == [call('INFANTICIDE in progress for all conflicts')]
    # reset mocks
    mocked_conciliate.reset_mock()
    mocked_info.reset_mock()
    # test with namespec
    assert view.conciliation_action('proc_conflict', 'STOP') == 'delayed info'
    assert mocked_conciliate.call_args_list == [call(supvisors, ConciliationStrategies.STOP, ['a process status'])]
    assert mocked_info.call_args_list == [call('STOP in progress for proc_conflict')]


def test_make_callback(mocker, view):
    """ Test the make_callback method. """
    mocked_super = mocker.patch('supvisors.web.viewmain.MainView.make_callback', return_value='other called')
    mocked_conciliate = mocker.patch.object(view, 'conciliation_action', return_value='conciliation called')
    for action_name in list(view.process_methods.keys()):
        view.process_methods[action_name] = Mock(return_value='%s called' % action_name)
    # patch context
    view.view_ctx = Mock(identifier='10.0.0.2')
    # test strategies but USER
    for strategy in view.strategies:
        assert view.make_callback('dummy_namespec', strategy) == 'conciliation called'
        assert mocked_conciliate.call_args_list == [call('dummy_namespec', strategy.upper())]
        mocked_conciliate.reset_mock()
    assert not any(mocked.called for mocked in view.process_methods.values())
    assert not mocked_super.called
    # test USER strategy
    assert view.make_callback('dummy_namespec', 'user') == 'other called'
    assert not any(mocked.called for mocked in view.process_methods.values())
    assert not mocked_conciliate.called
    assert mocked_super.call_args_list == [call('dummy_namespec', 'user')]
    mocked_super.reset_mock()
    # test process actions
    for action in ['pstop', 'pkeep']:
        assert view.make_callback('dummy_namespec', action) == '%s called' % action
        assert view.process_methods[action].call_args_list == [call('dummy_namespec', '10.0.0.2')]
        view.process_methods[action].reset_mock()
        assert not any(mocked.called for mocked in view.process_methods.values())
    assert not mocked_super.called
    # test other action
    assert view.make_callback('dummy_namespec', 'sup_master_sync') == 'other called'
    assert mocked_super.call_args_list == [call('dummy_namespec', 'sup_master_sync')]
    assert not any(mocked.called for mocked in view.process_methods.values())
    assert not mocked_conciliate.called
