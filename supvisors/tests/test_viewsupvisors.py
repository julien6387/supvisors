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

from unittest.mock import call, Mock

import pytest

from supvisors.web.viewsupvisors import *
from .conftest import create_application, create_element, to_simple_url


@pytest.fixture
def view(http_context):
    """ Fixture for the instance to test. """
    view = SupvisorsView(http_context)
    view.view_ctx = Mock(parameters={}, **{'format_url.side_effect': to_simple_url})
    return view


def test_init(view):
    """ Test the values set at construction. """
    # test parameter page name
    assert view.page_name == SUPVISORS_PAGE
    # test action methods storage
    assert sorted(view.global_methods.keys()) == ['sup_restart', 'sup_shutdown', 'sup_sync']
    assert all(callable(cb) for cb in view.global_methods.values())


def test_write_actions(mocker, view):
    """ Test the SupvisorsView.write_supvisors_actions method. """
    mocked_super = mocker.patch('supvisors.web.viewmain.MainView.write_actions')
    # set context (meant to be set through render)
    view.view_ctx = Mock(**{'format_url.return_value': 'an url'})
    # build root structure
    start_mid = create_element()
    mocked_header = create_element({'start_a_mid': start_mid})
    # test call
    view.write_actions(mocked_header)
    assert mocked_super.call_args_list == [call(mocked_header)]
    assert mocked_header.findmeld.call_args_list == [call('start_a_mid')]
    assert view.view_ctx.format_url.call_args_list == [call('', SUPVISORS_PAGE, **{ACTION: 'sup_sync'})]
    assert start_mid.attributes.call_args_list == [call(href='an url')]


def test_write_contents(mocker, view):
    """ Test the SupvisorsView.write_contents method. """
    mocked_boxes = mocker.patch('supvisors.web.viewsupvisors.SupvisorsView.write_instance_boxes')
    # build xhtml structure
    header_elt = create_element()
    # test call
    view.write_contents(header_elt)
    assert mocked_boxes.call_args_list == [call(header_elt)]


def test_write_instance_box_title(mocker, supvisors, view):
    """ Test the write_instance_box_title method. """
    view.current_mtime = 234.56
    # patch context
    mocked_time = mocker.patch('supvisors.web.viewsupvisors.simple_localtime', return_value='12:34:30')
    status = supvisors.context.instances['10.0.0.1:25000']
    status._state = SupvisorsInstanceStates.RUNNING
    mocker.patch.object(status, 'get_load', return_value=17)
    mocker.patch.object(status.times, 'get_current_remote_time', side_effect=lambda x: x + 1)
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
    view._write_instance_box_title(mocked_root, status, True)
    # test USER sync element
    assert not mocked_sync_th_mid.replace.called
    assert mocked_sync_a_mid.attrib['class'] == 'on'
    expected_url = 'http:///index.html?ident=10.0.0.1:25000&action=sup_master_sync'
    assert mocked_sync_a_mid.attributes.call_args_list == [call(href=expected_url)]
    assert mocked_sync_a_mid.content.call_args_list == [call('&#160;&#10026;&#160;')]
    # test Supvisors instance element
    assert mocked_identifier_mid.attrib['class'] == 'on'
    expected_url = 'http://10.0.0.1:25000/proc_instance.html'
    assert mocked_identifier_mid.attributes.call_args_list == [call(href=expected_url)]
    assert mocked_identifier_mid.content.call_args_list == [call('10.0.0.1')]
    # test state element
    assert mocked_state_mid.attrib['class'] == 'RUNNING'
    assert mocked_state_mid.content.call_args_list == [call('RUNNING')]
    # test time element
    assert mocked_time_mid.content.call_args_list == [call('12:34:30')]
    assert mocked_time.call_args_list == [call(235.56)]
    # test loading element
    assert mocked_percent_mid.content.call_args_list == [call('17%')]
    # reset mocks and attributes
    mocker.resetall()
    mocked_root.reset_all()
    # test call in RUNNING state and master and not user_sync
    view.sup_ctx.master_identifier = '10.0.0.1:25000'
    view._write_instance_box_title(mocked_root, status, False)
    # test USER sync element
    assert mocked_sync_th_mid.replace.call_args_list == [call('')]
    assert mocked_sync_a_mid.attrib['class'] == ''
    assert not mocked_sync_a_mid.attributes.called
    assert not mocked_sync_a_mid.content.called
    # test Supvisors instance element
    assert mocked_identifier_mid.attrib['class'] == 'on'
    expected_url = 'http://10.0.0.1:25000/proc_instance.html'
    assert mocked_identifier_mid.attributes.call_args_list == [call(href=expected_url)]
    assert mocked_identifier_mid.content.call_args_list == [call(f'{MASTER_SYMBOL} 10.0.0.1')]
    # test state element
    assert mocked_state_mid.attrib['class'] == 'RUNNING'
    assert mocked_state_mid.content.call_args_list == [call('RUNNING')]
    # test time element
    assert mocked_time_mid.content.call_args_list == [call('12:34:30')]
    assert mocked_time.call_args_list == [call(235.56)]
    # test loading element
    assert mocked_percent_mid.content.call_args_list == [call('17%')]
    # reset mocks and attributes
    mocker.resetall()
    mocked_root.reset_all()
    # test call in SILENT state and user sync
    status._state = SupvisorsInstanceStates.SILENT
    mocker.patch.object(status, 'get_load', return_value=0)
    view._write_instance_box_title(mocked_root, status, True)
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
    assert mocked_state_mid.attrib['class'] == 'SILENT'
    assert mocked_state_mid.content.call_args_list == [call('SILENT')]
    # test time element
    assert not mocked_time_mid.content.called
    assert not mocked_time.called
    # test loading element
    assert mocked_percent_mid.content.call_args_list == [call('0%')]


def test_write_instance_box_applications(mocker, supvisors, view):
    """ Test the _write_instance_box_applications method. """
    mocked_write = mocker.patch.object(view, '_write_instance_box_application')
    # 1. patch context for no running process on node
    mocked_process_1 = Mock(application_name='dummy_appli', process_name='dummy_proc')
    mocked_process_2 = Mock(application_name='other_appli', process_name='other_proc')
    mocked_status = Mock(identifier='10.0.0.1', **{'running_processes.return_value': {}})
    application_1 = create_application('dummy_appli', supvisors)
    application_2 = create_application('other_appli', supvisors)
    supvisors.context.applications['dummy_appli'] = application_1
    supvisors.context.applications['other_appli'] = application_2
    # build root structure with one single element
    process_li_mid = create_element()
    appli_tr_mid = create_element({'process_li_mid': process_li_mid})
    mocked_box = create_element({'appli_tr_mid': appli_tr_mid})
    # test call with no running process
    view._write_instance_box_applications(mocked_box, mocked_status, True)
    # test elements
    assert appli_tr_mid.findmeld.call_args_list == [call('process_li_mid')]
    assert not appli_tr_mid.repeat.called
    assert not mocked_write.called
    assert process_li_mid.replace.call_args_list == [call('')]
    appli_tr_mid.reset_all()
    # 2. patch context for multiple running process on node
    mocked_status.running_processes.return_value = [mocked_process_1, mocked_process_2]
    # build xhtml structure
    appli_tr_elt_1 = create_element()
    appli_tr_elt_2 = create_element()
    appli_tr_mid.repeat.return_value = [(appli_tr_elt_1, 'dummy_appli'),
                                        (appli_tr_elt_2, 'other_appli')]
    # 2.1 test call with 2 running processes and user_sync set
    view._write_instance_box_applications(mocked_box, mocked_status, True)
    # test elements
    assert mocked_write.call_args_list == [call(appli_tr_elt_1, '10.0.0.1', application_1, True,
                                                [mocked_process_1, mocked_process_2]),
                                           call(appli_tr_elt_2, '10.0.0.1', application_2, True,
                                                [mocked_process_1, mocked_process_2])]
    assert not appli_tr_mid.findmeld.called
    assert not process_li_mid.replace.called
    # test shade in mocked_appli_tr_mids
    assert appli_tr_elt_1.attrib['class'] == 'brightened'
    assert appli_tr_elt_2.attrib['class'] == 'shaded'
    # reset mocks
    mocker.resetall()
    mocked_box.reset_all()
    appli_tr_elt_1.reset_all()
    appli_tr_elt_2.reset_all()
    mocked_status.running_processes.reset_mock()
    # 2.2 test call with 2 running processes and user_sync NOT set
    view._write_instance_box_applications(mocked_box, mocked_status, False)
    # test elements
    assert mocked_write.call_args_list == [call(appli_tr_elt_1, '10.0.0.1', application_1, False,
                                                [mocked_process_1, mocked_process_2]),
                                           call(appli_tr_elt_2, '10.0.0.1', application_2, False,
                                                [mocked_process_1, mocked_process_2])]
    assert not appli_tr_mid.findmeld.called
    assert not process_li_mid.replace.called
    # test shade in mocked_appli_tr_mids
    assert appli_tr_elt_1.attrib['class'] == 'brightened'
    assert appli_tr_elt_2.attrib['class'] == 'shaded'


def test_write_instance_box_application(supvisors, view):
    """ Test the _write_instance_box_application method. """
    mocked_process_1 = Mock(namespec='dummy_appli:dummy_proc', process_name='dummy_proc',
                            **{'conflicting.return_value': False})
    mocked_process_2 = Mock(namespec='other_appli:other_proc', process_name='other_proc',
                            **{'conflicting.return_value': False})
    view.view_ctx = Mock(**{'format_url.return_value': 'an url'})
    application = create_application('dummy_appli', supvisors)
    running_processes = [mocked_process_1, mocked_process_2]
    # build xhtml structure
    app_name_a_mid = create_element()
    app_name_td_mid = create_element({'app_name_a_mid': app_name_a_mid})
    process_span_mid_1 = create_element()
    process_span_mid_2 = create_element()
    process_a_mid_1 = create_element({'process_span_mid': process_span_mid_1})
    process_a_mid_2 = create_element({'process_span_mid': process_span_mid_2})
    process_li_elt_1 = create_element({'process_a_mid': process_a_mid_1})
    process_li_elt_2 = create_element({'process_a_mid': process_a_mid_2})
    process_li_mid = create_element()
    process_li_mid.repeat.return_value = []
    appli_tr_elt = create_element({'app_name_td_mid': app_name_td_mid, 'process_li_mid': process_li_mid})
    # 1. test call with managed application, no running process and user sync
    application.rules.managed = True
    view._write_instance_box_application(appli_tr_elt, '10.0.0.1', application, True, [])
    # test elements
    assert appli_tr_elt.findmeld.call_args_list == [call('app_name_td_mid'), call('process_li_mid')]
    assert view.view_ctx.format_url.call_args_list == [call('10.0.0.1', APPLICATION_PAGE, appname='dummy_appli',
                                                            ident='10.0.0.1', strategy='CONFIG')]
    assert app_name_a_mid.content.call_args_list == [call('dummy_appli')]
    assert app_name_a_mid.attributes.call_args_list == [call(href='an url')]
    assert app_name_a_mid.attrib == {'class': 'on'}
    assert app_name_td_mid.attrib == {'class': '', 'colspan': '2'}
    assert not process_li_mid.repeat.call_args_list == [call([])]
    assert not process_li_elt_1.findmeld.called
    assert not process_span_mid_1.content.called
    assert not process_a_mid_1.attributes.called
    assert process_a_mid_1.attrib['class'] == ''
    assert process_span_mid_1.attrib['class'] == ''
    assert not process_li_elt_2.findmeld.called
    assert not process_span_mid_2.content.called
    assert not process_a_mid_2.attributes.called
    assert process_a_mid_2.attrib['class'] == ''
    assert process_span_mid_2.attrib['class'] == ''
    view.view_ctx.format_url.reset_mock()
    appli_tr_elt.reset_all()
    # 2. test call with unmanaged application, multiple running process on node and no user sync
    process_li_mid.repeat.return_value = [(process_li_elt_1, mocked_process_1),
                                          (process_li_elt_2, mocked_process_2)]
    application.rules.managed = False
    mocked_process_2.conflicting.return_value = True
    view._write_instance_box_application(appli_tr_elt, '10.0.0.1', application, False, running_processes)
    # test elements
    assert appli_tr_elt.findmeld.call_args_list == [call('app_name_td_mid'), call('process_li_mid')]
    assert app_name_a_mid.content.call_args_list == [call('dummy_appli')]
    assert app_name_a_mid.attrib == {'class': ''}
    assert view.view_ctx.format_url.call_args_list == [call('10.0.0.1', PROC_INSTANCE_PAGE,
                                                            processname='dummy_appli:dummy_proc', ident='10.0.0.1'),
                                                       call('10.0.0.1', PROC_INSTANCE_PAGE,
                                                            processname='other_appli:other_proc', ident='10.0.0.1')]
    assert not process_li_mid.repeat.call_args_list == [call(running_processes)]
    assert process_li_elt_1.findmeld.call_args_list == [call('process_a_mid')]
    assert process_span_mid_1.content.call_args_list == [call('dummy_proc')]
    assert process_a_mid_1.attributes.call_args_list == [call(href='an url')]
    assert process_a_mid_1.attrib['class'] == 'on'
    assert process_span_mid_1.attrib['class'] == ''
    assert process_li_elt_2.findmeld.call_args_list == [call('process_a_mid')]
    assert process_span_mid_2.content.call_args_list == [call('other_proc')]
    assert process_a_mid_2.attributes.call_args_list == [call(href='an url')]
    assert process_a_mid_2.attrib['class'] == 'on'
    assert process_span_mid_2.attrib['class'] == ''
    view.view_ctx.format_url.reset_mock()
    appli_tr_elt.reset_all()
    process_li_elt_1.reset_all()
    process_li_elt_2.reset_all()
    # 3. test call with managed application, multiple running process on node and no user sync
    application.rules.managed = True
    view._write_instance_box_application(appli_tr_elt, '10.0.0.1', application, False, running_processes)
    # test elements
    assert appli_tr_elt.findmeld.call_args_list == [call('app_name_td_mid'), call('process_li_mid')]
    assert app_name_a_mid.content.call_args_list == [call('dummy_appli')]
    assert app_name_a_mid.attrib == {'class': 'on'}
    assert view.view_ctx.format_url.call_args_list == [call('10.0.0.1', APPLICATION_PAGE, appname='dummy_appli',
                                                            ident='10.0.0.1', strategy='CONFIG'),
                                                       call('10.0.0.1', PROC_INSTANCE_PAGE,
                                                            processname='dummy_appli:dummy_proc', ident='10.0.0.1'),
                                                       call('10.0.0.1', PROC_INSTANCE_PAGE,
                                                            processname='other_appli:other_proc', ident='10.0.0.1')]
    assert not process_li_mid.repeat.call_args_list == [call(running_processes)]
    assert process_li_elt_1.findmeld.call_args_list == [call('process_a_mid')]
    assert process_span_mid_1.content.call_args_list == [call('dummy_proc')]
    assert process_a_mid_1.attributes.call_args_list == [call(href='an url')]
    assert process_a_mid_1.attrib['class'] == 'on'
    assert process_span_mid_1.attrib['class'] == ''
    assert process_li_elt_2.findmeld.call_args_list == [call('process_a_mid')]
    assert process_span_mid_2.content.call_args_list == [call('other_proc')]
    assert process_a_mid_2.attributes.call_args_list == [call(href='an url')]
    assert process_a_mid_2.attrib['class'] == 'on'
    assert process_span_mid_2.attrib['class'] == 'blink'


def test_write_node_boxes(mocker, supvisors, view):
    """ Test the write_instance_boxes method. """
    mocked_box_processes = mocker.patch('supvisors.web.viewsupvisors.SupvisorsView._write_instance_box_applications')
    mocked_box_title = mocker.patch('supvisors.web.viewsupvisors.SupvisorsView._write_instance_box_title')
    # patch context
    supvisors.options.multicast_group = '293.0.0.1:7777'
    local_identifier = view.sup_ctx.local_identifier
    ref_instances = view.sup_ctx.instances
    view.sup_ctx.instances = {local_identifier: ref_instances[local_identifier],
                              '10.0.0.1:25000': ref_instances['10.0.0.1:25000']}
    # build root structure with one single element
    mocked_box_mid_1 = Mock()
    mocked_box_mid_2 = Mock()
    mocked_address_template = Mock(**{'repeat.return_value': [(mocked_box_mid_1, local_identifier),
                                                              (mocked_box_mid_2, '10.0.0.1:25000')]})
    mocked_root = Mock(**{'findmeld.return_value': mocked_address_template})
    # test call with user sync disabled
    view.write_instance_boxes(mocked_root)
    assert mocked_box_title.call_args_list == [call(mocked_box_mid_1, ref_instances[local_identifier], False),
                                               call(mocked_box_mid_2, ref_instances['10.0.0.1:25000'], False)]
    assert mocked_box_processes.call_args_list == [call(mocked_box_mid_1, ref_instances[local_identifier], False),
                                                   call(mocked_box_mid_2, ref_instances['10.0.0.1:25000'], False)]
    mocker.resetall()
    # test call with user sync enabled
    supvisors.options.synchro_options = [SynchronizationOptions.USER]
    supvisors.fsm.state = SupvisorsStates.INITIALIZATION
    view.write_instance_boxes(mocked_root)
    assert mocked_box_title.call_args_list == [call(mocked_box_mid_1, ref_instances[local_identifier], True),
                                               call(mocked_box_mid_2, ref_instances['10.0.0.1:25000'], True)]
    assert mocked_box_processes.call_args_list == [call(mocked_box_mid_1, ref_instances[local_identifier], True),
                                                   call(mocked_box_mid_2, ref_instances['10.0.0.1:25000'], True)]


def test_make_callback(mocker, view):
    """ Test the make_callback method. """
    mocked_super = mocker.patch('supvisors.web.viewmain.MainView.make_callback', return_value='other called')
    mocked_sync = mocker.patch.object(view, 'sup_sync_action', return_value='sup_master_sync called')
    # patch context
    view.view_ctx = Mock(identifier='10.0.0.2')
    # test user sync action
    assert view.make_callback('namespec', 'sup_master_sync') == 'sup_master_sync called'
    assert mocked_sync.call_args_list == [call('10.0.0.2')]
    assert not mocked_super.called
    mocker.resetall()
    # test other action
    assert view.make_callback('namespec', 'dummy') == 'other called'
    assert not mocked_sync.called
    assert mocked_super.call_args_list == [call('namespec', 'dummy')]


def test_sup_sync_action(mocker, supvisors, view):
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
    assert view.sup_sync_action('10.0.0.1:25000') == 'delayed warning'
    assert mocked_rpc.call_args_list == [call('10.0.0.1:25000')]
    assert not mocked_derror.called
    assert mocked_dwarn.called
