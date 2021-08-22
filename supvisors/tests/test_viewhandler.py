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

from unittest.mock import call, Mock

from supervisor.http import NOT_DONE_YET
from supervisor.states import SupervisorStates, RUNNING_STATES, STOPPED_STATES

from supvisors.rpcinterface import API_VERSION
from supvisors.ttypes import ApplicationStates, StartingStrategies, SupvisorsStates
from supvisors.viewcontext import AUTO, PERIOD, PROCESS, ViewContext
from supvisors.viewhandler import ViewHandler
from supvisors.viewimage import process_cpu_img, process_mem_img
from supvisors.webutils import SUPVISORS_PAGE

from .base import DummyHttpContext


@pytest.fixture
def http_context():
    return DummyHttpContext('ui/index.html')


@pytest.fixture
def handler(http_context):
    """ Fixture for the instance to test. """
    return ViewHandler(http_context)


def test_init(http_context, handler):
    """ Test the values set at construction. """
    assert handler.root is not None
    assert handler.root.findmeld('version_mid') is not None
    assert handler.callback is None
    # test MeldView inheritance
    assert handler.context == http_context
    # test ViewHandler initialization
    assert handler.supvisors is http_context.supervisord.supvisors
    assert handler.sup_ctx is http_context.supervisord.supvisors.context
    assert handler.local_node_name == handler.supvisors.address_mapper.local_node_name
    assert handler.view_ctx is None


def test_call(mocker, handler):
    """ Test the call method. """
    mocker.patch('supvisors.viewhandler.MeldView.__call__', side_effect=(NOT_DONE_YET, {'body': u'html_body'}))
    # first call to MeldView returns NOT_DONE_YET
    assert handler.__call__() is NOT_DONE_YET
    # second call to MeldView returns an HTML struct
    assert handler.__call__() == {'body': b'html_body'}


def test_render_action_in_progress(mocker, handler):
    """ Test the render method when Supervisor is in RUNNING state and when an action is in progress. """
    mocked_contents = mocker.patch('supvisors.viewhandler.ViewHandler.write_contents')
    mocked_header = mocker.patch('supvisors.viewhandler.ViewHandler.write_header')
    mocked_nav = mocker.patch('supvisors.viewhandler.ViewHandler.write_navigation')
    mocked_common = mocker.patch('supvisors.viewhandler.ViewHandler.write_common')
    mocked_clone = mocker.patch('supervisor.web.MeldView.clone')
    mocked_action = mocker.patch('supvisors.viewhandler.ViewHandler.handle_action')
    # build xml template
    mocked_root = Mock(**{'write_xhtmlstring.return_value': 'xhtml'})
    mocked_clone.return_value = mocked_root
    # patch context
    handler.supvisors.context.get_all_namespecs = Mock(return_value=[])
    # 1. test render call when Supervisor is not RUNNING
    handler.supvisors.info_source.supervisor_state = SupervisorStates.RESTARTING
    assert not handler.render()
    assert handler.view_ctx is None
    assert not mocked_action.call_count
    assert not handler.clone.call_count
    assert not handler.write_navigation.call_count
    assert not handler.write_header.call_count
    assert not handler.write_contents.call_count
    # 2. test render call when Supervisor is RUNNING and an action is in progress
    handler.supvisors.info_source.supervisor_state = SupervisorStates.RUNNING
    mocked_action.return_value = NOT_DONE_YET
    assert handler.render() is NOT_DONE_YET
    assert handler.view_ctx is not None
    assert mocked_action.call_args_list == [call()]
    assert not mocked_clone.call_count
    assert not mocked_common.call_count
    assert not mocked_nav.call_count
    assert not mocked_header.call_count
    assert not mocked_contents.call_count
    # 3. test render call when Supervisor is RUNNING and no action is in progress
    mocked_action.reset_mock()
    mocked_action.return_value = None
    assert handler.render() == 'xhtml'
    assert handler.view_ctx is not None
    assert mocked_action.call_args_list == [call()]
    assert mocked_clone.call_args_list == [call()]
    assert mocked_common.call_args_list == [call(mocked_root)]
    assert mocked_nav.call_args_list == [call(mocked_root)]
    assert mocked_header.call_args_list == [call(mocked_root)]
    assert mocked_contents.call_args_list == [call(mocked_root)]


def test_handle_parameters(handler):
    """ Test the handle_parameters method. """
    handler.supvisors.context.get_all_namespecs = Mock(return_value=[])
    assert handler.view_ctx is None
    handler.handle_parameters()
    assert handler.view_ctx is not None
    assert isinstance(handler.view_ctx, ViewContext)


def test_write_common(mocker, handler):
    """ Test the write_common method. """
    mocked_msg = mocker.patch('supvisors.viewhandler.print_message')
    # patch context
    handler.page_name = 'dummy.html'
    handler.view_ctx = Mock(parameters={AUTO: True}, **{'format_url.return_value': 'an url',
                                                        'get_gravity.return_value': 'severe',
                                                        'get_message.return_value': 'a message'})
    # build xml template
    mocked_meta = Mock(attrib={})
    mocked_supv = Mock(attrib={})
    mocked_version = Mock()
    mocked_node = Mock()
    mocked_refresh = Mock()
    mocked_autorefresh = Mock(attrib={'class': 'button'})
    mocked_root = Mock(**{'findmeld.side_effect': [mocked_meta, mocked_supv, mocked_version, mocked_node,
                                                   mocked_refresh, mocked_autorefresh] * 2})
    # 1. test no conflict and auto-refresh
    handler.supvisors.fsm.state = SupvisorsStates.OPERATION
    handler.write_common(mocked_root)
    assert mocked_root.findmeld.call_args_list == [call('meta_mid'), call('supvisors_mid'), call('version_mid'),
                                                   call('node_mid'), call('refresh_a_mid'), call('autorefresh_a_mid')]
    assert not mocked_meta.deparent.called
    assert mocked_supv.attributes.call_args_list == [call(href='an url')]
    assert 'class' not in mocked_supv.attrib
    assert mocked_version.content.call_args_list == [call(API_VERSION)]
    assert mocked_node.content.call_args_list == [call(handler.local_node_name)]
    assert mocked_refresh.attributes.call_args_list == [call(href='an url')]
    assert mocked_autorefresh.attributes.call_args_list == [call(href='an url')]
    assert mocked_autorefresh.attrib['class'] == 'button active'
    assert handler.view_ctx.format_url.call_args_list == [call('', SUPVISORS_PAGE),
                                                          call('', 'dummy.html', action='refresh'),
                                                          call('', 'dummy.html', action='refresh', auto=False)]
    assert mocked_msg.call_args_list == [call(mocked_root, 'severe', 'a message')]
    # reset mocks
    mocked_root.findmeld.reset_mock()
    handler.view_ctx.format_url.reset_mock()
    mocked_supv.attributes.reset_mock()
    mocked_version.content.reset_mock()
    mocked_node.content.reset_mock()
    mocked_refresh.attributes.reset_mock()
    mocked_autorefresh.attributes.reset_mock()
    mocked_autorefresh.attrib['class'] = 'button'
    mocked_msg.reset_mock()
    # 2. test conflicts and no auto-refresh
    handler.supvisors.fsm.state = SupvisorsStates.CONCILIATION
    mocker.patch.object(handler.sup_ctx, 'conflicts', return_value=True)
    handler.view_ctx.parameters[AUTO] = False
    handler.write_common(mocked_root)
    assert mocked_root.findmeld.call_args_list == [call('meta_mid'), call('supvisors_mid'), call('version_mid'),
                                                   call('node_mid'), call('refresh_a_mid'), call('autorefresh_a_mid')]
    assert mocked_meta.deparent.called
    assert mocked_supv.attributes.call_args_list == [call(href='an url')]
    assert mocked_supv.attrib == {'class': 'blink'}
    assert mocked_version.content.call_args_list == [call(API_VERSION)]
    assert mocked_node.content.call_args_list == [call(handler.local_node_name)]
    assert mocked_refresh.attributes.call_args_list == [call(href='an url')]
    assert mocked_autorefresh.attributes.call_args_list == [call(href='an url')]
    assert mocked_autorefresh.attrib['class'] == 'button'
    assert handler.view_ctx.format_url.call_args_list == [call('', SUPVISORS_PAGE),
                                                          call('', 'dummy.html', action='refresh'),
                                                          call('', 'dummy.html', action='refresh', auto=True)]
    assert mocked_msg.call_args_list == [call(mocked_root, 'severe', 'a message')]


def test_write_nav(mocker, handler):
    """ Test the write_nav method. """
    mocked_appli = mocker.patch('supvisors.viewhandler.ViewHandler.write_nav_applications')
    mocked_nodes = mocker.patch('supvisors.viewhandler.ViewHandler.write_nav_nodes')
    handler.write_nav('root', 'address', 'appli')
    assert mocked_nodes.call_args_list == [call('root', 'address')]
    assert mocked_appli.call_args_list == [call('root', 'appli')]


def test_write_nav_nodes_address_error(handler):
    """ Test the write_nav_nodes method with an address not existing in supvisors context. """
    # patch the meld elements
    href_elt = Mock(attrib={})
    address_elt = Mock(attrib={}, **{'findmeld.return_value': href_elt})
    mocked_mid = Mock(**{'repeat.return_value': [(address_elt, '10.0.0.0')]})
    mocked_root = Mock(**{'findmeld.return_value': mocked_mid})
    # test call with no address status in context
    handler.write_nav_nodes(mocked_root, '10.0.0.0')
    assert mocked_root.findmeld.call_args_list == [call('address_li_mid')]
    assert mocked_mid.repeat.call_args_list == [call(handler.supvisors.address_mapper.node_names)]
    assert address_elt.findmeld.call_args_list == []


def test_write_nav_nodes_silent_address(handler):
    """ Test the write_nav_nodes method using a SILENT address. """
    from supvisors.ttypes import AddressStates
    # patch the meld elements
    href_elt = Mock(attrib={})
    address_elt = Mock(attrib={}, **{'findmeld.return_value': href_elt})
    mocked_mid = Mock(**{'repeat.return_value': [(address_elt, '10.0.0.1')]})
    mocked_root = Mock(**{'findmeld.return_value': mocked_mid})
    # test call with address status set in context, SILENT and different from parameter
    handler.sup_ctx.nodes['10.0.0.1']._state = AddressStates.SILENT
    handler.write_nav_nodes(mocked_root, '10.0.0.2')
    assert mocked_root.findmeld.call_args_list == [call('address_li_mid')]
    assert mocked_mid.repeat.call_args_list == [call(handler.supvisors.address_mapper.node_names)]
    assert address_elt.attrib['class'] == 'SILENT'
    assert address_elt.findmeld.call_args_list == [call('address_a_mid')]
    assert href_elt.attrib['class'] == 'off'
    assert href_elt.content.call_args_list == [call('10.0.0.1')]
    mocked_root.findmeld.reset_mock()
    mocked_mid.repeat.reset_mock()
    address_elt.findmeld.reset_mock()
    href_elt.content.reset_mock()
    # test call with address status set in context, SILENT and identical to parameter
    handler.write_nav_nodes(mocked_root, '10.0.0.1')
    assert mocked_root.findmeld.call_args_list == [call('address_li_mid')]
    assert mocked_mid.repeat.call_args_list == [call(handler.supvisors.address_mapper.node_names)]
    assert address_elt.attrib['class'] == 'SILENT active'
    assert address_elt.findmeld.call_args_list == [call('address_a_mid')]
    assert href_elt.attrib['class'] == 'off'
    assert href_elt.content.call_args_list == [call('10.0.0.1')]


def test_write_nav_nodes_running_address(handler):
    """ Test the write_nav_nodes method using a RUNNING address. """
    from supvisors.ttypes import AddressStates
    # patch the meld elements
    href_elt = Mock(attrib={})
    address_elt = Mock(attrib={}, **{'findmeld.return_value': href_elt})
    mocked_mid = Mock(**{'repeat.return_value': [(address_elt, '10.0.0.1')]})
    mocked_root = Mock(**{'findmeld.return_value': mocked_mid})
    # test call with address status set in context, RUNNING, different from parameter and not MASTER
    handler.view_ctx = Mock(**{'format_url.return_value': 'an url'})
    handler.sup_ctx.nodes['10.0.0.1'] = Mock(state=AddressStates.RUNNING,
                                             **{'state_string.return_value': 'running'})
    handler.write_nav_nodes(mocked_root, '10.0.0.2')
    assert mocked_root.findmeld.call_args_list == [call('address_li_mid')]
    assert mocked_mid.repeat.call_args_list == [call(handler.supvisors.address_mapper.node_names)]
    assert address_elt.attrib['class'] == 'RUNNING'
    assert address_elt.findmeld.call_args_list == [call('address_a_mid')]
    assert handler.view_ctx.format_url.call_args_list == [call('10.0.0.1', 'procaddress.html')]
    assert href_elt.attributes.call_args_list == [call(href='an url')]
    assert href_elt.attrib['class'] == 'on'
    assert href_elt.content.call_args_list == [call('10.0.0.1')]
    mocked_root.findmeld.reset_mock()
    mocked_mid.repeat.reset_mock()
    address_elt.findmeld.reset_mock()
    handler.view_ctx.format_url.reset_mock()
    href_elt.attributes.reset_mock()
    href_elt.content.reset_mock()
    # test call with address status set in context, RUNNING, identical to parameter and MASTER
    handler.sup_ctx.master_node_name = '10.0.0.1'
    handler.write_nav_nodes(mocked_root, '10.0.0.1')
    assert mocked_root.findmeld.call_args_list == [call('address_li_mid')]
    assert mocked_mid.repeat.call_args_list == [call(handler.supvisors.address_mapper.node_names)]
    assert address_elt.attrib['class'] == 'RUNNING active'
    assert address_elt.findmeld.call_args_list == [call('address_a_mid')]
    assert handler.view_ctx.format_url.call_args_list == [call('10.0.0.1', 'procaddress.html')]
    assert href_elt.attributes.call_args_list == [call(href='an url')]
    assert href_elt.attrib['class'] == 'on master'
    assert href_elt.content.call_args_list == [call('10.0.0.1')]


def test_write_nav_applications_initialization(handler):
    """ Test the write_nav_applications method with Supvisors in its INITIALIZATION state. """
    handler.supvisors.fsm.state = SupvisorsStates.INITIALIZATION
    # patch the meld elements
    href_elt = Mock(attrib={})
    appli_elt = Mock(attrib={}, **{'findmeld.return_value': href_elt})
    mocked_appli = Mock(application_name='dummy_appli', major_failure=False, minor_failure=False,
                        state=ApplicationStates.RUNNING)
    mocked_li_mid = Mock(**{'repeat.return_value': [(appli_elt, mocked_appli)]})
    mocked_h_mid = Mock(attrib={})
    mocked_root = Mock(**{'findmeld.side_effect': [mocked_li_mid, mocked_li_mid, mocked_h_mid]})
    # test call with application name different from parameter
    handler.view_ctx = Mock(**{'format_url.return_value': 'an url'})
    handler.write_nav_applications(mocked_root, 'dumb_appli')
    assert mocked_root.findmeld.call_args_list == [call('appli_li_mid')]
    assert mocked_li_mid.repeat.call_args_list == [call([])]
    assert appli_elt.attrib['class'] == 'RUNNING'
    assert appli_elt.findmeld.call_args_list == [call('appli_a_mid')]
    assert href_elt.attrib['class'] == 'off'
    assert handler.view_ctx.format_url.call_args_list == []
    assert href_elt.attributes.call_args_list == []
    assert href_elt.content.call_args_list == [call('dummy_appli')]
    assert mocked_h_mid.attrib == {}
    mocked_root.findmeld.reset_mock()
    mocked_li_mid.repeat.reset_mock()
    appli_elt.findmeld.reset_mock()
    href_elt.content.reset_mock()
    del appli_elt.attrib['class']
    del href_elt.attrib['class']
    # test call with application name identical to parameter and add a failure
    mocked_appli.minor_failure = True
    handler.write_nav_applications(mocked_root, 'dummy_appli')
    assert mocked_root.findmeld.call_args_list == [call('appli_li_mid'), call('appli_h_mid')]
    assert [call([])] == mocked_li_mid.repeat.call_args_list
    assert appli_elt.attrib['class'] == 'RUNNING active failure'
    assert appli_elt.findmeld.call_args_list == [call('appli_a_mid')]
    assert href_elt.attrib['class'] == 'off'
    assert handler.view_ctx.format_url.call_args_list == []
    assert href_elt.attributes.call_args_list == []
    assert href_elt.content.call_args_list == [call('dummy_appli')]
    assert mocked_h_mid.attrib['class'] == 'failure'


def test_write_nav_applications_operation(handler):
    """ Test the write_nav_applications method with Supvisors in its OPERATION state. """
    handler.supvisors.fsm.state = SupvisorsStates.OPERATION
    # patch the meld elements
    href_elt = Mock(attrib={})
    appli_elt = Mock(attrib={}, **{'findmeld.return_value': href_elt})
    mocked_appli = Mock(application_name='dummy_appli', major_failure=False, minor_failure=False,
                        state=ApplicationStates.RUNNING, rules=Mock(starting_strategy=StartingStrategies.LESS_LOADED))
    mocked_li_mid = Mock(**{'repeat.return_value': [(appli_elt, mocked_appli)]})
    mocked_h_mid = Mock(attrib={})
    mocked_root = Mock(**{'findmeld.side_effect': [mocked_li_mid, mocked_h_mid, mocked_li_mid]})
    # test call with application name different from parameter and failure
    mocked_appli.major_failure = True
    handler.view_ctx = Mock(**{'format_url.return_value': 'an url'})
    handler.write_nav_applications(mocked_root, 'dumb_appli')
    assert mocked_root.findmeld.call_args_list == [call('appli_li_mid'), call('appli_h_mid')]
    assert mocked_li_mid.repeat.call_args_list == [call([])]
    assert appli_elt.attrib['class'] == 'RUNNING failure'
    assert appli_elt.findmeld.call_args_list == [call('appli_a_mid')]
    assert href_elt.attrib['class'] == 'on'
    assert handler.view_ctx.format_url.call_args_list == [call('', 'application.html', appliname='dummy_appli',
                                                               strategy='LESS_LOADED')]
    assert href_elt.attributes.call_args_list == [call(href='an url')]
    assert href_elt.content.call_args_list == [call('dummy_appli')]
    assert mocked_h_mid.attrib['class'] == 'failure'
    mocked_root.findmeld.reset_mock()
    mocked_li_mid.repeat.reset_mock()
    appli_elt.findmeld.reset_mock()
    handler.view_ctx.format_url.reset_mock()
    href_elt.attributes.reset_mock()
    href_elt.content.reset_mock()
    del appli_elt.attrib['class']
    del href_elt.attrib['class']
    # test call with application name identical to parameter
    mocked_appli.major_failure = False
    handler.write_nav_applications(mocked_root, 'dummy_appli')
    assert mocked_root.findmeld.call_args_list == [call('appli_li_mid')]
    assert mocked_li_mid.repeat.call_args_list == [call([])]
    assert appli_elt.attrib['class'] == 'RUNNING active'
    assert appli_elt.findmeld.call_args_list == [call('appli_a_mid')]
    assert href_elt.attrib['class'] == 'on'
    assert handler.view_ctx.format_url.call_args_list == [call('', 'application.html', appliname='dummy_appli',
                                                               strategy='LESS_LOADED')]
    assert href_elt.attributes.call_args_list == [call(href='an url')]
    assert href_elt.content.call_args_list == [call('dummy_appli')]


def test_write_periods(handler):
    """ Test the write_periods method. """
    # patch the meld elements
    href_elt = Mock(attrib={'class': ''})
    period_elt = Mock(attrib={}, **{'findmeld.return_value': href_elt})
    mocked_mid = Mock(**{'repeat.return_value': [(period_elt, 5)]})
    mocked_root = Mock(**{'findmeld.return_value': mocked_mid})
    # test call with period selection identical to parameter
    handler.view_ctx = Mock(parameters={PERIOD: 5}, **{'format_url.return_value': 'an url'})
    handler.write_periods(mocked_root)
    assert mocked_root.findmeld.call_args_list == [call('period_li_mid')]
    assert mocked_mid.repeat.call_args_list == [call(handler.supvisors.options.stats_periods)]
    assert period_elt.findmeld.call_args_list == [call('period_a_mid')]
    assert href_elt.attrib['class'] == 'button off active'
    assert handler.view_ctx.format_url.call_args_list == []
    assert href_elt.attributes.call_args_list == []
    assert href_elt.content.call_args_list == [call('5s')]
    mocked_root.findmeld.reset_mock()
    mocked_mid.repeat.reset_mock()
    period_elt.findmeld.reset_mock()
    href_elt.content.reset_mock()
    href_elt.attrib['class'] = ''
    # test call with period selection different from parameter
    handler.view_ctx.parameters[PERIOD] = 10
    handler.write_periods(mocked_root)
    assert mocked_root.findmeld.call_args_list == [call('period_li_mid')]
    assert mocked_mid.repeat.call_args_list == [call(handler.supvisors.options.stats_periods)]
    assert period_elt.findmeld.call_args_list == [call('period_a_mid')]
    assert href_elt.attrib['class'] == ''
    assert handler.view_ctx.format_url.call_args_list == [call('', None, period=5)]
    assert href_elt.attributes.call_args_list == [call(href='an url')]
    assert href_elt.content.call_args_list == [call('5s')]


def test_write_common_process_cpu(handler):
    """ Test the write_common_process_cpu method. """
    # patch the view context
    handler.view_ctx = Mock(parameters={PROCESS: 'dummy_proc'}, **{'format_url.return_value': 'an url'})
    # patch the meld elements
    cell_elt = Mock(attrib={'class': ''})
    tr_elt = Mock(attrib={}, **{'findmeld.return_value': cell_elt})
    # test with no stats
    info = {'proc_stats': None}
    handler.write_common_process_cpu(tr_elt, info)
    assert tr_elt.findmeld.call_args_list == [call('pcpu_a_mid')]
    assert cell_elt.replace.call_args_list == [call('--')]
    assert not handler.view_ctx.format_url.called
    assert not cell_elt.content.called
    # reset context
    tr_elt.findmeld.reset_mock()
    cell_elt.replace.reset_mock()
    # test with empty stats
    info = {'proc_stats': [[]]}
    handler.write_common_process_cpu(tr_elt, info)
    assert tr_elt.findmeld.call_args_list == [call('pcpu_a_mid')]
    assert cell_elt.replace.call_args_list == [call('--')]
    assert not handler.view_ctx.format_url.called
    assert not cell_elt.content.called
    tr_elt.findmeld.reset_mock()
    cell_elt.replace.reset_mock()
    # test with filled stats on selected process, irix mode
    handler.supvisors.options.stats_irix_mode = True
    info = {'namespec': 'dummy_proc', 'node_name': '10.0.0.1', 'proc_stats': [[10, 20]], 'nb_cores': 2}
    handler.write_common_process_cpu(tr_elt, info)
    assert tr_elt.findmeld.call_args_list == [call('pcpu_a_mid')]
    assert not cell_elt.replace.called
    assert handler.view_ctx.format_url.call_args_list == [call('', None, processname=None, node='10.0.0.1')]
    assert cell_elt.attrib['class'] == 'button on active'
    assert cell_elt.content.call_args_list == [call('20.00%')]
    # reset context
    tr_elt.findmeld.reset_mock()
    cell_elt.content.reset_mock()
    handler.view_ctx.format_url.reset_mock()
    cell_elt.attributes.reset_mock()
    del cell_elt.attrib['class']
    # test with filled stats on not selected process, solaris mode
    handler.supvisors.options.stats_irix_mode = False
    info = {'namespec': 'dummy', 'node_name': '10.0.0.1', 'proc_stats': [[10, 20, 30]], 'nb_cores': 2}
    handler.write_common_process_cpu(tr_elt, info)
    assert tr_elt.findmeld.call_args_list == [call('pcpu_a_mid')]
    assert not cell_elt.replace.called
    assert cell_elt.content.call_args_list == [call('15.00%')]
    assert handler.view_ctx.format_url.call_args_list == [call('', None, processname='dummy', node='10.0.0.1')]
    assert cell_elt.attributes.call_args_list == [call(href='an url')]
    assert cell_elt.attrib['class'] == 'button on'
    # reset context
    tr_elt.findmeld.reset_mock()
    cell_elt.content.reset_mock()
    handler.view_ctx.format_url.reset_mock()
    cell_elt.attributes.reset_mock()
    del cell_elt.attrib['class']
    # test with filled stats on application (so non process), solaris mode
    handler.supvisors.options.stats_irix_mode = False
    info = {'namespec': None, 'node_name': '10.0.0.1', 'proc_stats': [[10, 20, 30]], 'nb_cores': 2}
    handler.write_common_process_cpu(tr_elt, info)
    assert tr_elt.findmeld.call_args_list == [call('pcpu_a_mid')]
    assert cell_elt.replace.call_args_list == [call('15.00%')]
    assert not cell_elt.content.called
    assert not handler.view_ctx.format_url.called
    assert not cell_elt.attributes.called
    assert 'class' not in cell_elt.attrib


def test_write_common_process_mem(handler):
    """ Test the write_common_process_mem method. """
    # patch the view context
    handler.view_ctx = Mock(parameters={PROCESS: 'dummy_proc'}, **{'format_url.return_value': 'an url'})
    # patch the meld elements
    cell_elt = Mock(attrib={'class': ''})
    tr_elt = Mock(attrib={}, **{'findmeld.return_value': cell_elt})
    # test with no stats
    info = {'proc_stats': []}
    handler.write_common_process_mem(tr_elt, info)
    assert tr_elt.findmeld.call_args_list == [call('pmem_a_mid')]
    assert cell_elt.replace.call_args_list == [call('--')]
    assert not handler.view_ctx.format_url.called
    assert not cell_elt.content.called
    # reset context
    tr_elt.findmeld.reset_mock()
    cell_elt.replace.reset_mock()
    # test with empty stats
    info = {'proc_stats': ([], [])}
    handler.write_common_process_mem(tr_elt, info)
    assert tr_elt.findmeld.call_args_list == [call('pmem_a_mid')]
    assert cell_elt.replace.call_args_list == [call('--')]
    assert not handler.view_ctx.format_url.called
    assert not cell_elt.content.called
    # reset context
    tr_elt.findmeld.reset_mock()
    cell_elt.replace.reset_mock()
    # test with filled stats on selected process
    info = {'namespec': 'dummy_proc', 'node_name': '10.0.0.2', 'proc_stats': ([], [10, 20])}
    handler.write_common_process_mem(tr_elt, info)
    assert tr_elt.findmeld.call_args_list == [call('pmem_a_mid')]
    assert not cell_elt.replace.called
    assert cell_elt.content.call_args_list == [call('20.00%')]
    assert handler.view_ctx.format_url.call_args_list == [call('', None, processname=None, node='10.0.0.2')]
    assert cell_elt.attrib['class'] == 'button on active'
    # reset context
    tr_elt.findmeld.reset_mock()
    cell_elt.content.reset_mock()
    handler.view_ctx.format_url.reset_mock()
    cell_elt.attributes.reset_mock()
    del cell_elt.attrib['class']
    # test with filled stats on not selected process
    info = {'namespec': 'dummy', 'node_name': '10.0.0.2', 'proc_stats': ([], [10, 20, 30])}
    handler.write_common_process_mem(tr_elt, info)
    assert tr_elt.findmeld.call_args_list == [call('pmem_a_mid')]
    assert not cell_elt.replace.called
    assert cell_elt.content.call_args_list == [call('30.00%')]
    assert handler.view_ctx.format_url.call_args_list == [call('', None, processname='dummy', node='10.0.0.2')]
    assert cell_elt.attributes.call_args_list == [call(href='an url')]
    assert cell_elt.attrib['class'] == 'button on'
    # reset context
    tr_elt.findmeld.reset_mock()
    cell_elt.content.reset_mock()
    handler.view_ctx.format_url.reset_mock()
    cell_elt.attributes.reset_mock()
    del cell_elt.attrib['class']
    # test with filled stats on application (so non process), solaris mode
    handler.supvisors.options.stats_irix_mode = False
    info = {'namespec': None, 'node_name': '10.0.0.2', 'proc_stats': ([], [10, 20, 30])}
    handler.write_common_process_mem(tr_elt, info)
    assert tr_elt.findmeld.call_args_list == [call('pmem_a_mid')]
    assert cell_elt.replace.call_args_list == [call('30.00%')]
    assert not cell_elt.content.called
    assert not handler.view_ctx.format_url.called
    assert not cell_elt.attributes.called
    assert 'class' not in cell_elt.attrib


def test_write_process_start_button(mocker, handler):
    """ Test the write_process_start_button method. """
    mocked_button = mocker.patch('supvisors.viewhandler.ViewHandler._write_process_button')
    handler.page_name = 'My Page'
    # test call indirection
    info = {'namespec': 'dummy_proc', 'statecode': 'stopped'}
    handler.write_process_start_button('elt', info)
    assert mocked_button.call_args_list == [call('elt', 'start_a_mid', '', 'My Page', 'start', 'dummy_proc',
                                                 'stopped', STOPPED_STATES)]


def test_write_process_stop_button(mocker, handler):
    """ Test the write_process_stop_button method. """
    mocked_button = mocker.patch('supvisors.viewhandler.ViewHandler._write_process_button')
    handler.page_name = 'My Page'
    # test call indirection
    info = {'namespec': 'dummy_proc', 'statecode': 'starting'}
    handler.write_process_stop_button('elt', info)
    assert mocked_button.call_args_list == [call('elt', 'stop_a_mid', '', 'My Page', 'stop', 'dummy_proc',
                                                 'starting', RUNNING_STATES)]


def test_write_process_restart_button(mocker, handler):
    """ Test the write_process_restart_button method. """
    mocked_button = mocker.patch('supvisors.viewhandler.ViewHandler._write_process_button')
    handler.page_name = 'My Page'
    # test call indirection
    info = {'namespec': 'dummy_proc', 'statecode': 'running'}
    handler.write_process_restart_button('elt', info)
    assert mocked_button.call_args_list == [call('elt', 'restart_a_mid', '', 'My Page',
                                                 'restart', 'dummy_proc', 'running', RUNNING_STATES)]


def test_write_process_clear_button(mocker, handler):
    """ Test the write_process_clear_button method. """
    mocked_button = mocker.patch('supvisors.viewhandler.ViewHandler._write_process_button')
    handler.page_name = 'My Page'
    # test call indirection
    info = {'namespec': 'dummy_proc', 'node_name': '10.0.0.1'}
    handler.write_process_clear_button('elt', info)
    assert mocked_button.call_args_list == [call('elt', 'clear_a_mid', '10.0.0.1', 'My Page',
                                                 'clearlog', 'dummy_proc', '', '')]


def test_write_process_stdout_button(mocker, handler):
    """ Test the write_process_stdout_button method. """
    mocked_button = mocker.patch('supvisors.viewhandler.ViewHandler._write_process_button')
    handler.page_name = 'My Page'
    # test call indirection
    info = {'namespec': 'dummy_proc', 'node_name': '10.0.0.1'}
    handler.write_process_stdout_button('elt', info)
    assert mocked_button.call_args_list == [call('elt', 'tailout_a_mid', '10.0.0.1', 'logtail/dummy_proc',
                                                 '', 'dummy_proc', '', '')]


def test_write_process_stderr_button(mocker, handler):
    """ Test the write_process_stderr_button method. """
    mocked_button = mocker.patch('supvisors.viewhandler.ViewHandler._write_process_button')
    handler.page_name = 'My Page'
    # test call indirection
    info = {'namespec': 'dummy_proc', 'node_name': '10.0.0.1'}
    handler.write_process_stderr_button('elt', info)
    assert mocked_button.call_args_list == [call('elt', 'tailerr_a_mid', '10.0.0.1', 'logtail/dummy_proc/stderr',
                                                 '', 'dummy_proc', '', '')]


def test_write_process_button(handler):
    """ Test the _write_process_button method. """
    # patch the view context
    handler.view_ctx = Mock(**{'format_url.return_value': 'an url'})
    # patch the meld elements
    cell_elt = Mock(attrib={'class': ''})
    tr_elt = Mock(**{'findmeld.return_value': cell_elt})
    # test with process state not in expected list
    handler._write_process_button(tr_elt, 'meld_id', '10.0.0.1', 'index.html', 'action', 'dummy_proc',
                                  'running', ['stopped', 'stopping'])
    assert tr_elt.findmeld.call_args_list == [call('meld_id')]
    assert cell_elt.attrib['class'] == 'button off'
    assert not cell_elt.attributes.called
    assert not cell_elt.content.called
    tr_elt.findmeld.reset_mock()
    del cell_elt.attrib['class']
    # test with filled stats on selected process
    handler._write_process_button(tr_elt, 'meld_id', '10.0.0.1', 'index.html', 'action', 'dummy_proc',
                                  'running', ['running', 'starting'])
    assert tr_elt.findmeld.call_args_list == [call('meld_id')]
    assert cell_elt.attrib['class'] == 'button on'
    assert handler.view_ctx.format_url.call_args_list == [call('10.0.0.1', 'index.html', action='action',
                                                               namespec='dummy_proc')]
    assert cell_elt.attributes.call_args_list == [call(href='an url')]
    assert not cell_elt.content.called
    tr_elt.findmeld.reset_mock()
    handler.view_ctx.format_url.reset_mock()
    cell_elt.attributes.reset_mock()
    del cell_elt.attrib['class']
    # test with unset namespec
    handler._write_process_button(tr_elt, 'meld_id', '10.0.0.1', 'index.html', 'action', '',
                                  'running', ['running', 'starting'])
    assert tr_elt.findmeld.call_args_list == [call('meld_id')]
    assert 'class' not in cell_elt.attrib
    assert not handler.view_ctx.format_url.called
    assert not cell_elt.attributes.called
    assert cell_elt.content.call_args_list == [call('')]


def test_write_common_status(mocker, handler):
    """ Test the write_common_process_status method. """
    mocked_mem = mocker.patch('supvisors.viewhandler.ViewHandler.write_common_process_mem')
    mocked_cpu = mocker.patch('supvisors.viewhandler.ViewHandler.write_common_process_cpu')
    # patch the meld elements
    state_elt = Mock(attrib={'class': ''})
    desc_elt = Mock(attrib={'class': ''})
    load_elt = Mock(attrib={'class': ''})
    tr_elt = Mock(attrib={}, **{'findmeld.side_effect': [state_elt, desc_elt, load_elt]})
    # test call on selected process
    param = {'expected_load': 35, 'statename': 'running', 'description': 'something'}
    handler.write_common_status(tr_elt, param)
    assert tr_elt.findmeld.call_args_list == [call('state_td_mid'), call('desc_td_mid'), call('load_td_mid')]
    assert state_elt.attrib['class'] == 'running'
    assert state_elt.content.call_args_list == [call('running')]
    assert desc_elt.content.call_args_list == [call('something')]
    assert load_elt.content.call_args_list == [call('35%')]
    assert mocked_cpu.call_args_list == [call(tr_elt, param)]
    assert mocked_mem.call_args_list == [call(tr_elt, param)]


def test_write_common_process_status(mocker, handler):
    """ Test the write_common_process_status method. """
    mocked_stderr = mocker.patch('supvisors.viewhandler.ViewHandler.write_process_stderr_button')
    mocked_stdout = mocker.patch('supvisors.viewhandler.ViewHandler.write_process_stdout_button')
    mocked_clear = mocker.patch('supvisors.viewhandler.ViewHandler.write_process_clear_button')
    mocked_restart = mocker.patch('supvisors.viewhandler.ViewHandler.write_process_restart_button')
    mocked_stop = mocker.patch('supvisors.viewhandler.ViewHandler.write_process_stop_button')
    mocked_start = mocker.patch('supvisors.viewhandler.ViewHandler.write_process_start_button')
    mocked_common = mocker.patch('supvisors.viewhandler.ViewHandler.write_common_status')
    # patch the view context
    handler.view_ctx = Mock(parameters={PROCESS: 'dummy_proc'},
                            **{'format_url.return_value': 'an url'})
    # patch the meld elements
    name_elt = Mock(attrib={'class': ''})
    tr_elt = Mock(attrib={}, **{'findmeld.return_value': name_elt})
    # test call on selected process
    param = {'namespec': 'dummy_proc', 'node_name': '10.0.0.1', 'process_name': 'proc'}
    handler.write_common_process_status(tr_elt, param)
    assert mocked_common.call_args_list == [call(tr_elt, param)]
    assert tr_elt.findmeld.call_args_list == [call('name_a_mid')]
    assert name_elt.content.call_args_list == [call('\u21B3 proc')]
    assert handler.view_ctx.format_url.call_args_list == [call('10.0.0.1', 'tail.html', processname='dummy_proc')]
    assert name_elt.attributes.call_args_list == [call(href='an url', target="_blank")]
    assert mocked_start.call_args_list == [call(tr_elt, param)]
    assert mocked_stop.call_args_list == [call(tr_elt, param)]
    assert mocked_restart.call_args_list == [call(tr_elt, param)]
    assert mocked_clear.call_args_list == [call(tr_elt, param)]
    assert mocked_stdout.call_args_list == [call(tr_elt, param)]
    assert mocked_stderr.call_args_list == [call(tr_elt, param)]


def test_write_detailed_process_cpu(handler):
    """ Test the write_detailed_process_cpu method. """
    # patch the meld elements
    val_elt = Mock(attrib={'class': ''})
    avg_elt, slope_elt, dev_elt = Mock(), Mock(), Mock()
    stats_elt = Mock(**{'findmeld.side_effect': [val_elt, avg_elt, slope_elt, dev_elt] * 2})
    # create fake stats
    proc_stats = ([10, 16, 13],)
    # test call with empty stats
    assert not handler.write_detailed_process_cpu(stats_elt, [], 4)
    assert not handler.write_detailed_process_cpu(stats_elt, ([], []), 4)
    # test call with irix mode
    handler.supvisors.options.stats_irix_mode = True
    assert handler.write_detailed_process_cpu(stats_elt, proc_stats, 4)
    assert val_elt.attrib['class'] == 'decrease'
    assert val_elt.content.call_args_list == [call('13.00%')]
    assert avg_elt.content.call_args_list == [call('13.00%')]
    assert slope_elt.content.call_args_list == [call('1.50')]
    assert dev_elt.content.call_args_list == [call('2.45')]
    val_elt.content.reset_mock()
    avg_elt.content.reset_mock()
    slope_elt.content.reset_mock()
    dev_elt.content.reset_mock()
    del val_elt.attrib['class']
    # test call with solaris mode
    proc_stats = ([10, 16, 24],)
    handler.supvisors.options.stats_irix_mode = False
    assert handler.write_detailed_process_cpu(stats_elt, proc_stats, 4)
    assert val_elt.attrib['class'] == 'increase'
    assert val_elt.content.call_args_list == [call('6.00%')]
    assert avg_elt.content.call_args_list == [call('16.67%')]
    assert slope_elt.content.call_args_list == [call('7.00')]
    assert dev_elt.content.call_args_list == [call('5.73')]


def test_write_detailed_process_mem(handler):
    """ Test the write_detailed_process_mem method. """
    # patch the meld elements
    val_elt = Mock(attrib={'class': ''})
    avg_elt, slope_elt, dev_elt = Mock(), Mock(), Mock()
    stats_elt = Mock(**{'findmeld.side_effect': [val_elt, avg_elt, slope_elt, dev_elt] * 2})
    # create fake stats
    proc_stats = ((), [20, 32, 32])
    # test call with empty stats
    assert not handler.write_detailed_process_mem(stats_elt, [], )
    assert not handler.write_detailed_process_mem(stats_elt, ([], []))
    # test call with irix mode
    handler.supvisors.options.stats_irix_mode = True
    assert handler.write_detailed_process_mem(stats_elt, proc_stats)
    assert val_elt.attrib['class'] == 'stable'
    assert val_elt.content.call_args_list == [call('32.00%')]
    assert avg_elt.content.call_args_list == [call('28.00%')]
    assert slope_elt.content.call_args_list == [call('6.00')]
    assert dev_elt.content.call_args_list == [call('5.66')]


def test_write_process_plots_no_plot(mocker, handler):
    """ Test the write_process_plots method in the event of matplotlib import error. """
    mocked_export = mocker.patch('supvisors.plot.StatisticsPlot.export_image')
    mocker.patch.dict('sys.modules', {'supvisors.plot': None})
    # test call
    handler.write_process_plots([])
    # test that plot methods are not called
    assert not mocked_export.called


def test_write_process_plots(mocker, handler):
    """ Test the write_process_plots method. """
    # skip test if matplotlib is not installed
    pytest.importorskip('matplotlib', reason='cannot test as optional matplotlib is not installed')
    # test call with dummy stats
    mocked_export = mocker.patch('supvisors.plot.StatisticsPlot.export_image')
    mocked_add = mocker.patch('supvisors.plot.StatisticsPlot.add_plot')
    proc_stats = ([10, 16, 24], [20, 32, 32])
    handler.write_process_plots(proc_stats)
    assert mocked_add.call_args_list == [call('CPU', '%', [10, 16, 24]), call('MEM', '%', [20, 32, 32])]
    assert mocked_export.call_args_list == [call(process_cpu_img), call(process_mem_img)]


def test_write_process_statistics(mocker, handler):
    """ Test the write_process_statistics method. """
    mocked_plots = mocker.patch('supvisors.viewhandler.ViewHandler.write_process_plots')
    mocked_mem = mocker.patch('supvisors.viewhandler.ViewHandler.write_detailed_process_mem', return_value=False)
    mocked_cpu = mocker.patch('supvisors.viewhandler.ViewHandler.write_detailed_process_cpu', return_value=False)
    # patch the view context
    handler.view_ctx = Mock(parameters={PROCESS: None})
    # patch the meld elements
    row_elt = Mock(attrib={})
    title_elt = Mock()
    stats_elt = Mock(attrib={}, **{'findmeld.side_effect': [title_elt, row_elt]})
    root_elt = Mock(attrib={}, **{'findmeld.return_value': stats_elt})
    # test call with no namespec selection
    info = {}
    handler.write_process_statistics(root_elt, info)
    assert root_elt.findmeld.call_args_list == [call('pstats_div_mid')]
    assert stats_elt.replace.call_args_list == [call('')]
    assert stats_elt.findmeld.call_args_list == []
    assert mocked_cpu.call_args_list == []
    assert mocked_mem.call_args_list == []
    assert title_elt.content.call_args_list == []
    assert 'class' not in row_elt.attrib
    assert mocked_plots.call_args_list == []
    root_elt.findmeld.reset_mock()
    stats_elt.replace.reset_mock()
    # test call with namespec selection and no stats found
    info = {'namespec': 'dummy_proc', 'node_name': '10.0.0.1', 'proc_stats': 'dummy_stats', 'nb_cores': 8}
    handler.write_process_statistics(root_elt, info)
    assert root_elt.findmeld.call_args_list == [call('pstats_div_mid')]
    assert stats_elt.replace.call_args_list == []
    assert stats_elt.findmeld.call_args_list == []
    assert mocked_cpu.call_args_list == [call(stats_elt, 'dummy_stats', 8)]
    assert mocked_mem.call_args_list == [call(stats_elt, 'dummy_stats')]
    assert title_elt.content.call_args_list == []
    assert 'class' not in row_elt.attrib
    assert mocked_plots.call_args_list == []
    root_elt.findmeld.reset_mock()
    mocked_cpu.reset_mock()
    mocked_mem.reset_mock()
    # test call with namespec selection and stats found
    mocked_cpu.return_value = True
    handler.write_process_statistics(root_elt, info)
    assert root_elt.findmeld.call_args_list == [call('pstats_div_mid')]
    assert stats_elt.findmeld.call_args_list == [call('process_h_mid'), call('address_fig_mid')]
    assert stats_elt.replace.call_args_list == []
    assert mocked_cpu.call_args_list == [call(stats_elt, 'dummy_stats', 8)]
    assert mocked_mem.call_args_list == [call(stats_elt, 'dummy_stats')]
    assert title_elt.content.call_args_list == [call('dummy_proc')]
    assert mocked_plots.call_args_list == [call('dummy_stats')]


def test_handle_action(handler):
    """ Test the handle_action method. """
    handler.view_ctx = Mock(parameters={'namespec': 'dummy_proc'}, **{'get_action.return_value': 'test'})
    handler.callback = None
    handler.make_callback = Mock(return_value=lambda: NOT_DONE_YET)
    # test no action in progress
    assert handler.handle_action() == NOT_DONE_YET
    assert handler.make_callback.call_args_list == [call('dummy_proc', 'test')]
    handler.make_callback.reset_mock()
    # test action in progress
    assert handler.handle_action() == NOT_DONE_YET
    assert handler.make_callback.call_args_list == []
    # test action completed
    handler.callback = None
    handler.make_callback = Mock(return_value=lambda: 'a message')
    assert handler.handle_action() == NOT_DONE_YET
    assert handler.make_callback.call_args_list == [call('dummy_proc', 'test')]
    handler.make_callback.reset_mock()
    assert not handler.handle_action()
    assert handler.make_callback.call_args_list == []
    assert handler.view_ctx.message.call_args_list == [call(('info', 'a message'))]


def test_set_slope_class():
    """ Test the set_slope_class method. """
    elt = Mock(attrib={})
    # test with values around 0
    ViewHandler.set_slope_class(elt, 0)
    assert elt.attrib['class'] == 'stable'
    del elt.attrib['class']
    ViewHandler.set_slope_class(elt, 0.0049)
    assert elt.attrib['class'] == 'stable'
    del elt.attrib['class']
    ViewHandler.set_slope_class(elt, -0.0049)
    assert elt.attrib['class'] == 'stable'
    del elt.attrib['class']
    # test with values around greater than 0 but not around 0
    ViewHandler.set_slope_class(elt, 0.005)
    assert elt.attrib['class'] == 'increase'
    del elt.attrib['class']
    ViewHandler.set_slope_class(elt, 10)
    assert elt.attrib['class'] == 'increase'
    del elt.attrib['class']
    # test with values around lower than 0 but not around 0
    ViewHandler.set_slope_class(elt, -0.005)
    assert elt.attrib['class'] == 'decrease'
    del elt.attrib['class']
    ViewHandler.set_slope_class(elt, -10)
    assert elt.attrib['class'] == 'decrease'
