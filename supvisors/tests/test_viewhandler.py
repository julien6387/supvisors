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

import time
from unittest.mock import call, Mock

import pytest
from supervisor.http import NOT_DONE_YET
from supervisor.states import SupervisorStates, ProcessStates

from supvisors.rpcinterface import API_VERSION
from supvisors.ttypes import ApplicationStates, StartingStrategies, SupvisorsStates, SupvisorsInstanceStates
from supvisors.web.viewcontext import AUTO, PERIOD, PROCESS, ViewContext
from supvisors.web.viewhandler import ViewHandler
from supvisors.web.viewimage import process_cpu_img, process_mem_img
from supvisors.web.webutils import MASTER_SYMBOL
from .base import DummyHttpContext
from .conftest import create_element, create_application


@pytest.fixture
def http_context(supvisors):
    """ Fixture for a consistent mocked HTTP context provided by Supervisor. """
    http_context = DummyHttpContext('ui/index.html')
    http_context.supervisord.supvisors = supvisors
    supvisors.supervisor_data.supervisord = http_context.supervisord
    return http_context


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
    assert handler.page_name is None
    current_time = time.time()
    assert current_time - 1 < handler.current_time < current_time
    assert handler.supvisors is http_context.supervisord.supvisors
    assert handler.sup_ctx is http_context.supervisord.supvisors.context
    assert handler.local_identifier == handler.supvisors.mapper.local_identifier
    assert handler.has_host_statistics
    assert handler.has_process_statistics
    assert handler.view_ctx is None


def test_call(mocker, handler):
    """ Test the call method. """
    mocker.patch('supvisors.web.viewhandler.MeldView.__call__', side_effect=(NOT_DONE_YET, {'body': u'html_body'}))
    # first call to MeldView returns NOT_DONE_YET
    assert handler.__call__() is NOT_DONE_YET
    # second call to MeldView returns an HTML struct
    assert handler.__call__() == {'body': b'html_body'}


def test_render_action_in_progress(mocker, handler):
    """ Test the render method when Supervisor is in RUNNING state and when an action is in progress. """
    mocked_style = mocker.patch('supvisors.web.viewhandler.ViewHandler.write_style')
    mocked_common = mocker.patch('supvisors.web.viewhandler.ViewHandler.write_common')
    mocked_contents = mocker.patch('supvisors.web.viewhandler.ViewHandler.write_contents')
    mocked_header = mocker.patch('supvisors.web.viewhandler.ViewHandler.write_header')
    mocked_nav = mocker.patch('supvisors.web.viewhandler.ViewHandler.write_navigation')
    mocked_clone = mocker.patch('supervisor.web.MeldView.clone')
    mocked_action = mocker.patch('supvisors.web.viewhandler.ViewHandler.handle_action')
    # build xml template
    mocked_root = Mock(**{'write_xhtmlstring.return_value': 'xhtml'})
    mocked_clone.return_value = mocked_root
    # patch context
    handler.supvisors.context.get_all_namespecs = Mock(return_value=[])
    # 1. test render call when Supervisor is not RUNNING
    handler.context.supervisord.options.mood = SupervisorStates.RESTARTING
    assert not handler.render()
    assert handler.view_ctx is None
    assert not mocked_action.call_count
    assert not handler.clone.call_count
    assert not mocked_style.called
    assert not mocked_common.called
    assert not mocked_nav.called
    assert not mocked_header.call_count
    assert not mocked_contents.call_count
    # 2. test render call when Supervisor is RUNNING and an action is in progress
    handler.context.supervisord.options.mood = SupervisorStates.RUNNING
    mocked_action.return_value = NOT_DONE_YET
    assert handler.render() is NOT_DONE_YET
    assert handler.view_ctx is not None
    assert mocked_action.call_args_list == [call()]
    assert not mocked_clone.call_count
    assert not mocked_style.called
    assert not mocked_common.called
    assert not mocked_nav.called
    assert not mocked_header.call_count
    assert not mocked_contents.call_count
    # 3. test render call when Supervisor is RUNNING and no action is in progress
    mocked_action.reset_mock()
    mocked_action.return_value = None
    assert handler.render() == 'xhtml'
    assert handler.view_ctx is not None
    assert mocked_action.call_args_list == [call()]
    assert mocked_clone.call_args_list == [call()]
    assert mocked_style.call_args_list == [call(mocked_root)]
    assert mocked_common.call_args_list == [call(mocked_root)]
    assert mocked_header.call_args_list == [call(mocked_root)]
    assert mocked_nav.call_args_list == [call(mocked_root)]
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
    mocked_msg = mocker.patch('supvisors.web.viewhandler.print_message')
    # patch context
    handler.page_name = 'dummy.html'
    handler.view_ctx = Mock(parameters={AUTO: True}, **{'format_url.return_value': 'an url',
                                                        'get_gravity.return_value': 'severe',
                                                        'get_message.return_value': 'a message'})
    # build xml template
    mocked_meta = create_element()
    mocked_supv = create_element()
    mocked_version = create_element()
    mocked_identifier = create_element()
    mocked_refresh = create_element()
    mocked_autorefresh = create_element()
    mocked_autorefresh.attrib['class'] = 'button'
    mocked_root = create_element({'meta_mid': mocked_meta, 'supvisors_mid': mocked_supv,
                                  'version_mid': mocked_version, 'identifier_mid': mocked_identifier,
                                  'refresh_a_mid': mocked_refresh, 'autorefresh_a_mid': mocked_autorefresh})
    # 1. test no conflict and auto-refresh
    handler.supvisors.fsm.state = SupvisorsStates.OPERATION
    handler.write_common(mocked_root)
    assert mocked_root.findmeld.call_args_list == [call('version_mid'), call('identifier_mid'),
                                                   call('refresh_a_mid'), call('autorefresh_a_mid')]
    assert not mocked_meta.deparent.called
    assert 'failure' not in mocked_supv.attrib['class']
    assert mocked_version.content.call_args_list == [call(API_VERSION)]
    assert mocked_identifier.content.call_args_list == [call(handler.local_identifier)]
    assert mocked_refresh.attributes.call_args_list == [call(href='an url')]
    assert mocked_autorefresh.attributes.call_args_list == [call(href='an url')]
    assert mocked_autorefresh.attrib['class'] == 'button active'
    assert handler.view_ctx.format_url.call_args_list == [call('', 'dummy.html'),
                                                          call('', 'dummy.html', auto=False)]
    assert mocked_msg.call_args_list == [call(mocked_root, 'severe', 'a message', handler.current_time)]
    # reset mocks
    mocked_root.reset_all()
    mocked_autorefresh.attrib['class'] = 'button'
    mocked_msg.reset_mock()
    handler.view_ctx.format_url.reset_mock()
    # 2. test conflicts and no auto-refresh
    mocked_root.findmeld.side_effect = [mocked_meta, mocked_supv, mocked_version, mocked_identifier, mocked_refresh,
                                        mocked_autorefresh]
    handler.supvisors.fsm.state = SupvisorsStates.CONCILIATION
    mocker.patch.object(handler.sup_ctx, 'conflicts', return_value=True)
    handler.view_ctx.parameters[AUTO] = False
    handler.write_common(mocked_root)
    assert mocked_root.findmeld.call_args_list == [call('meta_mid'), call('supvisors_mid'), call('version_mid'),
                                                   call('identifier_mid'), call('refresh_a_mid'),
                                                   call('autorefresh_a_mid')]
    assert mocked_meta.deparent.called
    assert mocked_supv.attrib == {'class': 'failure'}
    assert mocked_version.content.call_args_list == [call(API_VERSION)]
    assert mocked_identifier.content.call_args_list == [call(handler.local_identifier)]
    assert mocked_refresh.attributes.call_args_list == [call(href='an url')]
    assert mocked_autorefresh.attributes.call_args_list == [call(href='an url')]
    assert mocked_autorefresh.attrib['class'] == 'button'
    assert handler.view_ctx.format_url.call_args_list == [call('', 'dummy.html'),
                                                          call('', 'dummy.html', auto=True)]
    assert mocked_msg.call_args_list == [call(mocked_root, 'severe', 'a message', handler.current_time)]


def test_write_navigation(handler):
    """ Test the write_navigation method. """
    with pytest.raises(NotImplementedError):
        handler.write_navigation(Mock())


def test_write_nav(mocker, handler):
    """ Test the write_nav method. """
    mocked_appli = mocker.patch('supvisors.web.viewhandler.ViewHandler.write_nav_applications')
    mocked_instances = mocker.patch('supvisors.web.viewhandler.ViewHandler.write_nav_instances')
    handler.write_nav('root', 'identifier', 'appli')
    assert mocked_instances.call_args_list == [call('root', 'identifier')]
    assert mocked_appli.call_args_list == [call('root', 'appli')]


def test_write_nav_instances_identifier_error(handler):
    """ Test the write_nav_instances method with an identifier not existing in supvisors context.
    Use discovery mode to test Supvisors instances ordering in this case. """
    handler.supvisors.options.multicast_group = '293.0.0.1:7777'
    # patch the meld elements
    href_elt = Mock(attrib={})
    address_elt = Mock(attrib={}, **{'findmeld.return_value': href_elt})
    mocked_mid = Mock(**{'repeat.return_value': [(address_elt, '10.0.0.0')]})
    mocked_root = Mock(**{'findmeld.return_value': mocked_mid})
    # test call with no address status in context
    handler.write_nav_instances(mocked_root, '10.0.0.0')
    assert mocked_root.findmeld.call_args_list == [call('instance_li_mid')]
    assert mocked_mid.repeat.call_args_list == [call(sorted(handler.supvisors.mapper.instances.keys()))]
    assert address_elt.findmeld.call_args_list == []


def test_write_nav_instances_silent_instance(handler):
    """ Test the write_nav_instances method using a SILENT address. """
    # patch the meld elements
    href_elt = Mock(attrib={})
    address_elt = Mock(attrib={}, **{'findmeld.return_value': href_elt})
    mocked_mid = Mock(**{'repeat.return_value': [(address_elt, '10.0.0.1')]})
    mocked_root = Mock(**{'findmeld.return_value': mocked_mid})
    # test call with address status set in context, SILENT and different from parameter
    handler.sup_ctx.instances['10.0.0.1']._state = SupvisorsInstanceStates.SILENT
    handler.write_nav_instances(mocked_root, '10.0.0.2')
    assert mocked_root.findmeld.call_args_list == [call('instance_li_mid')]
    assert mocked_mid.repeat.call_args_list == [call(list(handler.supvisors.mapper.instances.keys()))]
    assert address_elt.attrib['class'] == 'SILENT'
    assert address_elt.findmeld.call_args_list == [call('instance_a_mid')]
    assert href_elt.attrib['class'] == 'off'
    assert href_elt.content.call_args_list == [call('10.0.0.1')]
    mocked_root.findmeld.reset_mock()
    mocked_mid.repeat.reset_mock()
    address_elt.findmeld.reset_mock()
    href_elt.content.reset_mock()
    # test call with address status set in context, SILENT and identical to parameter
    handler.write_nav_instances(mocked_root, '10.0.0.1')
    assert mocked_root.findmeld.call_args_list == [call('instance_li_mid')]
    assert mocked_mid.repeat.call_args_list == [call(list(handler.supvisors.mapper.instances.keys()))]
    assert address_elt.attrib['class'] == 'SILENT active'
    assert address_elt.findmeld.call_args_list == [call('instance_a_mid')]
    assert href_elt.attrib['class'] == 'off'
    assert href_elt.content.call_args_list == [call('10.0.0.1')]


def test_write_nav_instances_running_instance(handler):
    """ Test the write_nav_instances method using a RUNNING instance. """
    # patch the meld elements
    instance_a_mid = create_element()
    instance_elt = create_element({'instance_a_mid': instance_a_mid})
    instance_li_mid = create_element()
    instance_li_mid.repeat.return_value = [(instance_elt, '10.0.0.1')]
    mocked_root = create_element({'instance_li_mid': instance_li_mid})
    handler.view_ctx = Mock(**{'format_url.return_value': 'an url'})
    # loop on active states
    status = handler.sup_ctx.instances['10.0.0.1']
    all_identifiers = list(handler.supvisors.mapper.instances.keys())
    for state in [SupvisorsInstanceStates.CHECKING, SupvisorsInstanceStates.CHECKED, SupvisorsInstanceStates.RUNNING]:
        # set context
        status._state = state
        status.state_modes.starting_jobs = False
        handler.sup_ctx.master_identifier = ''
        # test call with address status set in context, RUNNING, different from parameter and not MASTER
        handler.write_nav_instances(mocked_root, '10.0.0.2')
        assert mocked_root.findmeld.call_args_list == [call('instance_li_mid')]
        assert instance_li_mid.repeat.call_args_list == [call(all_identifiers)]
        assert instance_elt.attrib['class'] == state.name
        assert instance_elt.findmeld.call_args_list == [call('instance_a_mid')]
        assert handler.view_ctx.format_url.call_args_list == [call('10.0.0.1', 'proc_instance.html')]
        assert instance_a_mid.attributes.call_args_list == [call(href='an url')]
        assert instance_a_mid.attrib['class'] == 'on'
        assert instance_a_mid.content.call_args_list == [call('10.0.0.1')]
        instance_elt.reset_all()
        mocked_root.reset_all()
        handler.view_ctx.format_url.reset_mock()
        # test call with address status set in context, RUNNING, identical to parameter and MASTER
        status.state_modes.starting_jobs = True
        handler.sup_ctx.master_identifier = '10.0.0.1'
        handler.write_nav_instances(mocked_root, '10.0.0.1')
        assert mocked_root.findmeld.call_args_list == [call('instance_li_mid')]
        assert instance_li_mid.repeat.call_args_list == [call(all_identifiers)]
        assert instance_elt.attrib['class'] == state.name + ' active'
        assert instance_elt.findmeld.call_args_list == [call('instance_a_mid')]
        assert handler.view_ctx.format_url.call_args_list == [call('10.0.0.1', 'proc_instance.html')]
        assert instance_a_mid.attributes.call_args_list == [call(href='an url')]
        assert instance_a_mid.attrib['class'] == 'blink on'
        assert instance_a_mid.content.call_args_list == [call(f'{MASTER_SYMBOL} 10.0.0.1')]
        instance_elt.reset_all()
        mocked_root.reset_all()
        handler.view_ctx.format_url.reset_mock()


def test_write_nav_applications_initialization(handler):
    """ Test the write_nav_applications method with Supvisors in its INITIALIZATION state. """
    handler.supvisors.fsm.state = SupvisorsStates.INITIALIZATION
    dummy_appli = create_application('dummy_appli', handler.supvisors)
    dummy_appli._state = ApplicationStates.RUNNING
    handler.supvisors.starter.get_application_job_names.return_value = set()
    handler.supvisors.stopper.get_application_job_names.return_value = set()
    # patch the meld elements
    appli_a_mid = create_element()
    appli_elt = create_element({'appli_a_mid': appli_a_mid})
    appli_li_mid = create_element()
    appli_li_mid.repeat.return_value = [(appli_elt, dummy_appli)]
    appli_h_mid = create_element()
    mocked_root = create_element({'appli_li_mid': appli_li_mid, 'appli_h_mid': appli_h_mid})
    # test call with application name different from parameter
    handler.view_ctx = Mock(**{'format_url.return_value': 'an url'})
    handler.write_nav_applications(mocked_root, 'dumb_appli')
    assert mocked_root.findmeld.call_args_list == [call('appli_li_mid')]
    assert appli_elt.attrib['class'] == 'RUNNING'
    assert appli_elt.findmeld.call_args_list == [call('appli_a_mid')]
    assert appli_a_mid.attrib['class'] == 'off'
    assert handler.view_ctx.format_url.call_args_list == []
    assert appli_a_mid.attributes.call_args_list == []
    assert appli_a_mid.content.call_args_list == [call('dummy_appli')]
    assert appli_h_mid.attrib['class'] == ''
    mocked_root.reset_all()
    appli_elt.reset_all()
    # test call with application name identical to parameter and add a failure
    handler.supvisors.starter.get_application_job_names.return_value = {'dummy_appli'}
    dummy_appli.minor_failure = True
    handler.write_nav_applications(mocked_root, 'dummy_appli')
    assert mocked_root.findmeld.call_args_list == [call('appli_li_mid'), call('appli_h_mid')]
    assert appli_elt.attrib['class'] == 'RUNNING active failure'
    assert appli_elt.findmeld.call_args_list == [call('appli_a_mid')]
    assert appli_a_mid.attrib['class'] == 'blink off'
    assert handler.view_ctx.format_url.call_args_list == []
    assert appli_a_mid.attributes.call_args_list == []
    assert appli_a_mid.content.call_args_list == [call('dummy_appli')]
    assert appli_h_mid.attrib['class'] == 'failure'


def test_write_nav_applications_operation(handler):
    """ Test the write_nav_applications method with Supvisors in its OPERATION state. """
    handler.supvisors.fsm.state = SupvisorsStates.OPERATION
    dummy_appli = create_application('dummy_appli', handler.supvisors)
    dummy_appli._state = ApplicationStates.RUNNING
    dummy_appli.rules.starting_strategy = StartingStrategies.LESS_LOADED
    handler.supvisors.starter.get_application_job_names.return_value = set()
    handler.supvisors.stopper.get_application_job_names.return_value = set()
    # patch the meld elements
    appli_a_mid = create_element()
    appli_elt = create_element({'appli_a_mid': appli_a_mid})
    appli_li_mid = create_element()
    appli_li_mid.repeat.return_value = [(appli_elt, dummy_appli)]
    appli_h_mid = create_element()
    mocked_root = create_element({'appli_li_mid': appli_li_mid, 'appli_h_mid': appli_h_mid})
    # test call with application name different from parameter and failure
    dummy_appli.major_failure = True
    handler.view_ctx = Mock(**{'format_url.return_value': 'an url'})
    handler.write_nav_applications(mocked_root, 'dumb_appli')
    assert mocked_root.findmeld.call_args_list == [call('appli_li_mid'), call('appli_h_mid')]
    assert appli_elt.attrib['class'] == 'RUNNING failure'
    assert appli_elt.findmeld.call_args_list == [call('appli_a_mid')]
    assert appli_a_mid.attrib['class'] == 'on'
    assert handler.view_ctx.format_url.call_args_list == [call('', 'application.html', appliname='dummy_appli',
                                                               strategy='LESS_LOADED')]
    assert appli_a_mid.attributes.call_args_list == [call(href='an url')]
    assert appli_a_mid.content.call_args_list == [call('dummy_appli')]
    assert appli_h_mid.attrib['class'] == 'failure'
    handler.view_ctx.format_url.reset_mock()
    mocked_root.reset_all()
    appli_elt.reset_all()
    # test call with application name identical to parameter
    handler.supvisors.stopper.get_application_job_names.return_value = {'dummy_appli'}
    dummy_appli.major_failure = False
    handler.write_nav_applications(mocked_root, 'dummy_appli')
    assert mocked_root.findmeld.call_args_list == [call('appli_li_mid')]
    assert appli_elt.attrib['class'] == 'RUNNING active'
    assert appli_elt.findmeld.call_args_list == [call('appli_a_mid')]
    assert appli_a_mid.attrib['class'] == 'blink on'
    assert handler.view_ctx.format_url.call_args_list == [call('', 'application.html', appliname='dummy_appli',
                                                               strategy='LESS_LOADED')]
    assert appli_a_mid.attributes.call_args_list == [call(href='an url')]
    assert appli_a_mid.content.call_args_list == [call('dummy_appli')]


def test_write_header(handler):
    """ Test the ViewHandler.write_header method. """
    with pytest.raises(NotImplementedError):
        handler.write_header(Mock())


def test_write_periods(mocker, handler):
    """ Test the ViewHandler.write_periods method. """
    mocked_period = mocker.patch.object(handler, 'write_periods_availability')
    mocked_root = Mock()
    handler.write_periods(mocked_root)
    assert mocked_period.call_args_list == [call(mocked_root, True)]


def test_write_periods_availability(handler):
    """ Test the ViewHandler.write_periods_availability method. """
    # 1. test call with period selection identical to parameter
    mocked_mid = Mock()
    mocked_root = Mock(**{'findmeld.return_value': mocked_mid})
    # test call when statistics are disabled
    handler.write_periods_availability(mocked_root, False)
    assert mocked_root.findmeld.call_args_list == [call('period_div_mid')]
    assert mocked_mid.replace.call_args_list == [call('')]
    # patch the meld elements
    href_elt = Mock(attrib={'class': ''})
    period_elt = Mock(attrib={}, **{'findmeld.return_value': href_elt})
    mocked_mid = Mock(**{'repeat.return_value': [(period_elt, 5)]})
    mocked_root = Mock(**{'findmeld.return_value': mocked_mid})
    # test call with period selection identical to parameter
    handler.view_ctx = Mock(parameters={PERIOD: 5}, **{'format_url.return_value': 'an url'})
    handler.write_periods_availability(mocked_root, True)
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
    # 2. test call with period selection different from parameter
    handler.view_ctx.parameters[PERIOD] = 10
    handler.write_periods_availability(mocked_root, True)
    assert mocked_root.findmeld.call_args_list == [call('period_li_mid')]
    assert mocked_mid.repeat.call_args_list == [call(handler.supvisors.options.stats_periods)]
    assert period_elt.findmeld.call_args_list == [call('period_a_mid')]
    assert href_elt.attrib['class'] == ''
    assert handler.view_ctx.format_url.call_args_list == [call('', None, period=5)]
    assert href_elt.attributes.call_args_list == [call(href='an url')]
    assert href_elt.content.call_args_list == [call('5s')]


def test_write_contents(handler):
    """ Test the write_contents method. """
    with pytest.raises(NotImplementedError):
        handler.write_contents(Mock())


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
    assert not cell_elt.deparent.called
    assert cell_elt.replace.call_args_list == [call('--')]
    assert not handler.view_ctx.format_url.called
    assert not cell_elt.content.called
    # reset context
    tr_elt.findmeld.reset_mock()
    cell_elt.replace.reset_mock()
    # test with empty stats
    info = {'proc_stats': Mock(cpu=[])}
    handler.write_common_process_cpu(tr_elt, info)
    assert tr_elt.findmeld.call_args_list == [call('pcpu_a_mid')]
    assert not cell_elt.deparent.called
    assert cell_elt.replace.call_args_list == [call('--')]
    assert not handler.view_ctx.format_url.called
    assert not cell_elt.content.called
    tr_elt.findmeld.reset_mock()
    cell_elt.replace.reset_mock()
    # test with filled stats on selected process, irix mode
    handler.supvisors.options.stats_irix_mode = True
    info = {'namespec': 'dummy_proc', 'identifier': '10.0.0.1', 'proc_stats': Mock(cpu=[10, 20]), 'nb_cores': 2}
    handler.write_common_process_cpu(tr_elt, info)
    assert tr_elt.findmeld.call_args_list == [call('pcpu_a_mid')]
    assert not cell_elt.deparent.called
    assert not cell_elt.replace.called
    assert handler.view_ctx.format_url.call_args_list == [call('', None, processname=None, ident='10.0.0.1')]
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
    info = {'namespec': 'dummy', 'identifier': '10.0.0.1', 'proc_stats': Mock(cpu=[10, 20, 30]), 'nb_cores': 2}
    handler.write_common_process_cpu(tr_elt, info)
    assert tr_elt.findmeld.call_args_list == [call('pcpu_a_mid')]
    assert not cell_elt.deparent.called
    assert not cell_elt.replace.called
    assert cell_elt.content.call_args_list == [call('15.00%')]
    assert handler.view_ctx.format_url.call_args_list == [call('', None, processname='dummy', ident='10.0.0.1')]
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
    info = {'namespec': None, 'ident': '10.0.0.1', 'proc_stats': Mock(cpu=[10, 20, 30]), 'nb_cores': 2}
    handler.write_common_process_cpu(tr_elt, info)
    assert tr_elt.findmeld.call_args_list == [call('pcpu_a_mid')]
    assert not cell_elt.deparent.called
    assert cell_elt.replace.call_args_list == [call('15.00%')]
    assert not cell_elt.content.called
    assert not handler.view_ctx.format_url.called
    assert not cell_elt.attributes.called
    assert 'class' not in cell_elt.attrib
    # reset context
    tr_elt.findmeld.reset_mock()
    cell_elt.replace.reset_mock()
    # test with statistics disabled
    handler.has_process_statistics = False
    handler.write_common_process_cpu(tr_elt, info)
    assert tr_elt.findmeld.call_args_list == [call('pcpu_td_mid')]
    assert cell_elt.deparent.call_args_list == [call()]
    assert not cell_elt.replace.called
    assert not cell_elt.content.called
    assert not handler.view_ctx.format_url.called
    assert not cell_elt.attributes.called


def test_write_common_process_mem(handler):
    """ Test the write_common_process_mem method. """
    # patch the view context
    handler.view_ctx = Mock(parameters={PROCESS: 'dummy_proc'}, **{'format_url.return_value': 'an url'})
    # patch the meld elements
    cell_elt = Mock(attrib={'class': ''})
    tr_elt = Mock(attrib={}, **{'findmeld.return_value': cell_elt})
    # test with no stats
    info = {'proc_stats': None}
    handler.write_common_process_mem(tr_elt, info)
    assert tr_elt.findmeld.call_args_list == [call('pmem_a_mid')]
    assert not cell_elt.deparent.called
    assert cell_elt.replace.call_args_list == [call('--')]
    assert not handler.view_ctx.format_url.called
    assert not cell_elt.content.called
    # reset context
    tr_elt.findmeld.reset_mock()
    cell_elt.replace.reset_mock()
    # test with empty stats
    info = {'proc_stats': Mock(mem=[])}
    handler.write_common_process_mem(tr_elt, info)
    assert tr_elt.findmeld.call_args_list == [call('pmem_a_mid')]
    assert not cell_elt.deparent.called
    assert cell_elt.replace.call_args_list == [call('--')]
    assert not handler.view_ctx.format_url.called
    assert not cell_elt.content.called
    # reset context
    tr_elt.findmeld.reset_mock()
    cell_elt.replace.reset_mock()
    # test with filled stats on selected process
    info = {'namespec': 'dummy_proc', 'identifier': '10.0.0.2', 'proc_stats': Mock(mem=[10, 20])}
    handler.write_common_process_mem(tr_elt, info)
    assert tr_elt.findmeld.call_args_list == [call('pmem_a_mid')]
    assert not cell_elt.deparent.called
    assert not cell_elt.replace.called
    assert cell_elt.content.call_args_list == [call('20.00%')]
    assert handler.view_ctx.format_url.call_args_list == [call('', None, processname=None, ident='10.0.0.2')]
    assert cell_elt.attrib['class'] == 'button on active'
    # reset context
    tr_elt.findmeld.reset_mock()
    cell_elt.content.reset_mock()
    handler.view_ctx.format_url.reset_mock()
    cell_elt.attributes.reset_mock()
    del cell_elt.attrib['class']
    # test with filled stats on not selected process
    info = {'namespec': 'dummy', 'identifier': '10.0.0.2', 'proc_stats': Mock(mem=[10, 20, 30])}
    handler.write_common_process_mem(tr_elt, info)
    assert tr_elt.findmeld.call_args_list == [call('pmem_a_mid')]
    assert not cell_elt.deparent.called
    assert not cell_elt.replace.called
    assert cell_elt.content.call_args_list == [call('30.00%')]
    assert handler.view_ctx.format_url.call_args_list == [call('', None, processname='dummy', ident='10.0.0.2')]
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
    info = {'namespec': None, 'identifier': '10.0.0.2', 'proc_stats': Mock(mem=[10, 20, 30])}
    handler.write_common_process_mem(tr_elt, info)
    assert tr_elt.findmeld.call_args_list == [call('pmem_a_mid')]
    assert not cell_elt.deparent.called
    assert cell_elt.replace.call_args_list == [call('30.00%')]
    assert not cell_elt.content.called
    assert not handler.view_ctx.format_url.called
    assert not cell_elt.attributes.called
    assert 'class' not in cell_elt.attrib
    # reset context
    tr_elt.findmeld.reset_mock()
    cell_elt.replace.reset_mock()
    # test with statistics disabled
    handler.has_process_statistics = False
    handler.write_common_process_mem(tr_elt, info)
    assert tr_elt.findmeld.call_args_list == [call('pmem_td_mid')]
    assert cell_elt.deparent.call_args_list == [call()]
    assert not cell_elt.replace.called
    assert not cell_elt.content.called
    assert not handler.view_ctx.format_url.called
    assert not cell_elt.attributes.called


def test_write_process_start_button(mocker, handler):
    """ Test the write_process_start_button method. """
    mocked_button = mocker.patch('supvisors.web.viewhandler.ViewHandler._write_process_button')
    handler.page_name = 'My Page'
    # test call redirection when program is disabled
    info = {'namespec': 'dummy_proc', 'statecode': ProcessStates.STOPPED, 'startable': False}
    handler.write_process_start_button('elt', info)
    assert mocked_button.call_args_list == [call('elt', 'start_a_mid', '', 'My Page', 'start', 'dummy_proc', False)]
    mocked_button.reset_mock()
    # test call redirection when program is enabled
    info['startable'] = True
    handler.write_process_start_button('elt', info)
    assert mocked_button.call_args_list == [call('elt', 'start_a_mid', '', 'My Page', 'start', 'dummy_proc', True)]


def test_write_process_stop_button(mocker, handler):
    """ Test the write_process_stop_button method. """
    mocked_button = mocker.patch('supvisors.web.viewhandler.ViewHandler._write_process_button')
    handler.page_name = 'My Page'
    # test call redirection
    info = {'namespec': 'dummy_proc', 'statecode': ProcessStates.STARTING}
    handler.write_process_stop_button('elt', info)
    assert mocked_button.call_args_list == [call('elt', 'stop_a_mid', '', 'My Page', 'stop', 'dummy_proc', True)]


def test_write_process_restart_button(mocker, handler):
    """ Test the write_process_restart_button method. """
    mocked_button = mocker.patch('supvisors.web.viewhandler.ViewHandler._write_process_button')
    handler.page_name = 'My Page'
    # test call redirection when program is disabled
    info = {'namespec': 'dummy_proc', 'statecode': ProcessStates.RUNNING, 'startable': False}
    handler.write_process_restart_button('elt', info)
    assert mocked_button.call_args_list == [call('elt', 'restart_a_mid', '', 'My Page', 'restart', 'dummy_proc', False)]
    mocked_button.reset_mock()
    # test call redirection when program is enabled
    info['startable'] = True
    handler.write_process_restart_button('elt', info)
    assert mocked_button.call_args_list == [call('elt', 'restart_a_mid', '', 'My Page', 'restart', 'dummy_proc', True)]


def test_write_process_clear_button(mocker, handler):
    """ Test the write_process_clear_button method. """
    mocked_button = mocker.patch('supvisors.web.viewhandler.ViewHandler._write_process_button')
    handler.page_name = 'My Page'
    # test call indirection with log check
    info = {'namespec': 'dummy_application:dummy_process_1', 'identifier': '10.0.0.1'}
    handler.write_process_clear_button('elt', info, True)
    assert mocked_button.call_args_list == [call('elt', 'clear_a_mid', '10.0.0.1', 'My Page', 'clearlog',
                                                 'dummy_application:dummy_process_1', True)]
    mocked_button.reset_mock()
    # test call indirection without log check
    handler.write_process_clear_button('elt', info, False)
    assert mocked_button.call_args_list == [call('elt', 'clear_a_mid', '10.0.0.1', 'My Page', 'clearlog',
                                                 'dummy_application:dummy_process_1', True)]


def test_write_process_stdout_button(mocker, handler):
    """ Test the write_process_stdout_button method. """
    mocked_button = mocker.patch('supvisors.web.viewhandler.ViewHandler._write_process_button')
    handler.page_name = 'My Page'
    # test call indirection with log check
    info = {'namespec': 'dummy_application:dummy_process_1', 'identifier': '10.0.0.1'}
    handler.write_process_stdout_button('elt', info, True)
    assert mocked_button.call_args_list == [call('elt', 'tailout_a_mid', '10.0.0.1',
                                                 'logtail/dummy_application%3Adummy_process_1',
                                                 '', 'dummy_application:dummy_process_1', True)]
    mocked_button.reset_mock()
    # test call indirection without log check
    handler.write_process_stdout_button('elt', info, False)
    assert mocked_button.call_args_list == [call('elt', 'tailout_a_mid', '10.0.0.1',
                                                 'logtail/dummy_application%3Adummy_process_1',
                                                 '', 'dummy_application:dummy_process_1', True)]


def test_write_process_stderr_button(mocker, handler):
    """ Test the write_process_stderr_button method. """
    mocked_button = mocker.patch('supvisors.web.viewhandler.ViewHandler._write_process_button')
    handler.page_name = 'My Page'
    # test call indirection
    info = {'namespec': 'dummy_application:dummy_process_1', 'identifier': '10.0.0.1'}
    handler.write_process_stderr_button('elt', info, True)
    assert mocked_button.call_args_list == [call('elt', 'tailerr_a_mid', '10.0.0.1',
                                                 'logtail/dummy_application%3Adummy_process_1/stderr',
                                                 '', 'dummy_application:dummy_process_1', False)]
    mocked_button.reset_mock()
    # test call indirection
    handler.write_process_stderr_button('elt', info, False)
    assert mocked_button.call_args_list == [call('elt', 'tailerr_a_mid', '10.0.0.1',
                                                 'logtail/dummy_application%3Adummy_process_1/stderr',
                                                 '', 'dummy_application:dummy_process_1', True)]


def test_write_process_button(handler):
    """ Test the _write_process_button method. """
    # patch the view context
    handler.view_ctx = Mock(**{'format_url.return_value': 'an url'})
    # patch the meld elements
    cell_elt = Mock(attrib={'class': ''})
    tr_elt = Mock(**{'findmeld.return_value': cell_elt})
    # test with process state not in expected list
    handler._write_process_button(tr_elt, 'meld_id', '10.0.0.1', 'index.html', 'action', 'dummy_proc', False)
    assert tr_elt.findmeld.call_args_list == [call('meld_id')]
    assert cell_elt.attrib['class'] == 'button off'
    assert not cell_elt.attributes.called
    assert not cell_elt.content.called
    tr_elt.findmeld.reset_mock()
    del cell_elt.attrib['class']
    # test with filled stats on selected process
    handler._write_process_button(tr_elt, 'meld_id', '10.0.0.1', 'index.html', 'action', 'dummy_proc', True)
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


def test_write_common_process_table(handler):
    """ Test the write_common_process_table method. """
    mem_head_elt = Mock()
    mem_foot_elt = Mock()
    cpu_head_elt = Mock()
    cpu_foot_elt = Mock()
    mid_map = {'mem_head_th_mid': mem_head_elt, 'cpu_head_th_mid': cpu_head_elt,
               'mem_foot_th_mid': mem_foot_elt, 'cpu_foot_th_mid': cpu_foot_elt, 'total_mid': None}
    root = Mock(attrib={}, **{'findmeld.side_effect': lambda x: mid_map[x]})
    # test with statistics enabled
    handler.has_process_statistics = True
    handler.write_common_process_table(root)
    assert not root.findmeld.called
    assert not mem_head_elt.deparent.called
    assert not mem_foot_elt.deparent.called
    assert not cpu_head_elt.deparent.called
    assert not cpu_foot_elt.deparent.called
    # test with statistics enabled
    handler.has_process_statistics = False
    handler.write_common_process_table(root)
    assert root.findmeld.call_args_list == [call('mem_head_th_mid'), call('cpu_head_th_mid'),
                                            call('mem_foot_th_mid'), call('cpu_foot_th_mid'), call('total_mid')]
    assert mem_head_elt.deparent.call_args_list == [call()]
    assert mem_foot_elt.deparent.call_args_list == [call()]
    assert cpu_head_elt.deparent.call_args_list == [call()]
    assert cpu_foot_elt.deparent.call_args_list == [call()]


def test_write_common_state(handler):
    """ Test the write_common_state method. """
    # patch the meld elements
    state_elt = create_element()
    desc_elt = create_element()
    tr_elt = create_element({'state_td_mid': state_elt, 'desc_td_mid': desc_elt})
    # test call on process that never crashed
    param = {'expected_load': 35, 'statename': 'exited', 'gravity': 'exited', 'disabled': True,
             'has_crashed': False, 'description': 'something'}
    handler.write_common_state(tr_elt, param)
    assert tr_elt.findmeld.call_args_list == [call('state_td_mid'), call('desc_td_mid')]
    assert state_elt.attrib['class'] == 'exited disabled'
    assert state_elt.content.call_args_list == [call('exited')]
    assert desc_elt.content.call_args_list == [call('something')]
    tr_elt.reset_all()
    # test call on process that ever crashed
    param.update({'gravity': 'fatal', 'has_crashed': True, 'disabled': False})
    handler.write_common_state(tr_elt, param)
    assert tr_elt.findmeld.call_args_list == [call('state_td_mid'), call('desc_td_mid')]
    assert state_elt.attrib['class'] == 'fatal crashed'
    assert state_elt.content.call_args_list == [call('exited')]
    assert desc_elt.content.call_args_list == [call('something')]


def test_write_common_statistics(mocker, handler):
    """ Test the write_common_process_status method. """
    mocked_mem = mocker.patch.object(handler, 'write_common_process_mem')
    mocked_cpu = mocker.patch.object(handler, 'write_common_process_cpu')
    # patch the meld elements
    load_elt = Mock(attrib={'class': ''})
    tr_elt = create_element({'load_td_mid': load_elt})
    # test call on process that never crashed
    param = {'expected_load': 35, 'statename': 'exited', 'gravity': 'exited', 'disabled': True,
             'has_crashed': False, 'description': 'something'}
    handler.write_common_statistics(tr_elt, param)
    assert tr_elt.findmeld.call_args_list == [call('load_td_mid')]
    assert load_elt.content.call_args_list == [call('35%')]
    assert mocked_cpu.call_args_list == [call(tr_elt, param)]
    assert mocked_mem.call_args_list == [call(tr_elt, param)]


def test_write_common_process_status(mocker, handler):
    """ Test the write_common_process_status method. """
    mocked_stderr = mocker.patch('supvisors.web.viewhandler.ViewHandler.write_process_stderr_button')
    mocked_stdout = mocker.patch('supvisors.web.viewhandler.ViewHandler.write_process_stdout_button')
    mocked_clear = mocker.patch('supvisors.web.viewhandler.ViewHandler.write_process_clear_button')
    mocked_restart = mocker.patch('supvisors.web.viewhandler.ViewHandler.write_process_restart_button')
    mocked_stop = mocker.patch('supvisors.web.viewhandler.ViewHandler.write_process_stop_button')
    mocked_start = mocker.patch('supvisors.web.viewhandler.ViewHandler.write_process_start_button')
    mocked_state = mocker.patch('supvisors.web.viewhandler.ViewHandler.write_common_state')
    mocked_stats = mocker.patch('supvisors.web.viewhandler.ViewHandler.write_common_statistics')
    # patch the view context
    handler.view_ctx = Mock(**{'format_url.return_value': 'an url'})
    # patch the meld elements
    name_a_elt = create_element()
    name_td_elt = create_element({'name_a_mid': name_a_elt})
    tr_elt = create_element({'name_td_mid': name_td_elt})
    # test call on selected process having a stdout_logfile
    param = {'namespec': 'dummy_application:dummy_process_1', 'identifier': '10.0.0.1',
             'process_name': 'dummy_process_1'}
    handler.write_common_process_status(tr_elt, param)
    assert mocked_state.call_args_list == [call(tr_elt, param)]
    assert mocked_stats.call_args_list == [call(tr_elt, param)]
    assert not name_td_elt.content.called
    assert name_a_elt.content.call_args_list == [call('\u21B3 dummy_process_1')]
    assert handler.view_ctx.format_url.call_args_list == [call('10.0.0.1', 'tail.html',
                                                               processname='dummy_application:dummy_process_1',
                                                               limit=1024)]
    assert name_a_elt.attributes.call_args_list == [call(href='an url', target="_blank")]
    assert mocked_start.call_args_list == [call(tr_elt, param)]
    assert mocked_stop.call_args_list == [call(tr_elt, param)]
    assert mocked_restart.call_args_list == [call(tr_elt, param)]
    assert mocked_clear.call_args_list == [call(tr_elt, param, True)]
    assert mocked_stdout.call_args_list == [call(tr_elt, param, True)]
    assert mocked_stderr.call_args_list == [call(tr_elt, param, True)]
    mocker.resetall()
    tr_elt.reset_all()
    handler.view_ctx.format_url.reset_mock()
    # test call on selected process NOT having a stdout_logfile
    param = {'namespec': 'dummy_application:dummy_process_2', 'identifier': '10.0.0.1',
             'process_name': 'dummy_process_1'}
    handler.write_common_process_status(tr_elt, param, True)
    assert mocked_state.call_args_list == [call(tr_elt, param)]
    assert mocked_stats.call_args_list == [call(tr_elt, param)]
    assert name_td_elt.content.call_args_list == [call('\u21B3 dummy_process_1')]
    assert not name_a_elt.content.called
    assert not handler.view_ctx.format_url.called
    assert not name_a_elt.attributes.called
    assert mocked_start.call_args_list == [call(tr_elt, param)]
    assert mocked_stop.call_args_list == [call(tr_elt, param)]
    assert mocked_restart.call_args_list == [call(tr_elt, param)]
    assert mocked_clear.call_args_list == [call(tr_elt, param, True)]
    assert mocked_stdout.call_args_list == [call(tr_elt, param, True)]
    assert mocked_stderr.call_args_list == [call(tr_elt, param, True)]
    mocker.resetall()
    tr_elt.reset_all()
    handler.view_ctx.format_url.reset_mock()
    # test call on selected process NOT having a stdout_logfile but without check required
    param = {'namespec': 'dummy_application:dummy_process_2', 'identifier': '10.0.0.1',
             'process_name': 'dummy_process_1'}
    handler.write_common_process_status(tr_elt, param, False)
    assert mocked_state.call_args_list == [call(tr_elt, param)]
    assert mocked_stats.call_args_list == [call(tr_elt, param)]
    assert not name_td_elt.content.called
    assert name_a_elt.content.call_args_list == [call('\u21B3 dummy_process_1')]
    assert handler.view_ctx.format_url.call_args_list == [call('10.0.0.1', 'tail.html',
                                                               processname='dummy_application:dummy_process_2',
                                                               limit=1024)]
    assert name_a_elt.attributes.call_args_list == [call(href='an url', target="_blank")]
    assert mocked_start.call_args_list == [call(tr_elt, param)]
    assert mocked_stop.call_args_list == [call(tr_elt, param)]
    assert mocked_restart.call_args_list == [call(tr_elt, param)]
    assert mocked_clear.call_args_list == [call(tr_elt, param, False)]
    assert mocked_stdout.call_args_list == [call(tr_elt, param, False)]
    assert mocked_stderr.call_args_list == [call(tr_elt, param, False)]


def test_write_detailed_process_cpu(handler):
    """ Test the write_detailed_process_cpu method. """
    # patch the meld elements
    val_elt = Mock(attrib={'class': ''})
    avg_elt, slope_elt, dev_elt = Mock(), Mock(), Mock()
    stats_elt = Mock(**{'findmeld.side_effect': [val_elt, avg_elt, slope_elt, dev_elt] * 2})
    # create fake stats
    proc_stats = Mock(times=[1, 2, 3], cpu=[10, 16, 13])
    # test call with empty stats
    assert not handler.write_detailed_process_cpu(stats_elt, None, 4)
    assert not handler.write_detailed_process_cpu(stats_elt, Mock(cpu=[]), 4)
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
    proc_stats = Mock(times=[1, 2, 3], cpu=[10, 16, 24])
    handler.supvisors.options.stats_irix_mode = False
    assert handler.write_detailed_process_cpu(stats_elt, proc_stats, 4)
    assert val_elt.attrib['class'] == 'increase'
    assert val_elt.content.call_args_list == [call('6.00%')]
    assert avg_elt.content.call_args_list == [call('4.17%')]
    assert slope_elt.content.call_args_list == [call('7.00')]
    assert dev_elt.content.call_args_list == [call('5.73')]


def test_write_detailed_process_mem(handler):
    """ Test the write_detailed_process_mem method. """
    # patch the meld elements
    val_elt = Mock(attrib={'class': ''})
    avg_elt, slope_elt, dev_elt = Mock(), Mock(), Mock()
    stats_elt = Mock(**{'findmeld.side_effect': [val_elt, avg_elt, slope_elt, dev_elt] * 2})
    # create fake stats
    proc_stats = Mock(times=[1, 2, 3], mem=[20, 32, 32])
    # test call with empty stats
    assert not handler.write_detailed_process_mem(stats_elt, None)
    assert not handler.write_detailed_process_mem(stats_elt, Mock(mem=[]))
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
    assert not handler.write_process_plots([], 0)
    # test that plot methods are not called
    assert not mocked_export.called


def test_write_process_plots(mocker, handler):
    """ Test the write_process_plots method. """
    # skip test if matplotlib is not installed
    pytest.importorskip('matplotlib', reason='cannot test as optional matplotlib is not installed')
    # get patches
    mocked_export = mocker.patch('supvisors.plot.StatisticsPlot.export_image')
    mocked_time = mocker.patch('supvisors.plot.StatisticsPlot.add_timeline')
    mocked_plot = mocker.patch('supvisors.plot.StatisticsPlot.add_plot')
    # test call with dummy stats and Solaris mode
    proc_stats = Mock(times=[1, 2, 3], cpu=[10, 16, 24], mem=[20, 32, 32])
    assert handler.write_process_plots(proc_stats, 2)
    assert mocked_time.call_args_list == [call([1, 2, 3]), call([1, 2, 3])]
    assert mocked_plot.call_args_list == [call('CPU', '%', [5, 8, 12]), call('MEM', '%', [20, 32, 32])]
    assert mocked_export.call_args_list == [call(process_cpu_img), call(process_mem_img)]
    mocker.resetall()
    # test call with dummy stats and IRIX mode
    handler.supvisors.options.stats_irix_mode = True
    assert handler.write_process_plots(proc_stats, 2)
    assert mocked_time.call_args_list == [call([1, 2, 3]), call([1, 2, 3])]
    assert mocked_plot.call_args_list == [call('CPU', '%', [10, 16, 24]), call('MEM', '%', [20, 32, 32])]
    assert mocked_export.call_args_list == [call(process_cpu_img), call(process_mem_img)]


def test_write_process_statistics(mocker, handler):
    """ Test the write_process_statistics method. """
    mocked_plots = mocker.patch('supvisors.web.viewhandler.ViewHandler.write_process_plots', return_value=True)
    mocked_mem = mocker.patch('supvisors.web.viewhandler.ViewHandler.write_detailed_process_mem', return_value=False)
    mocked_cpu = mocker.patch('supvisors.web.viewhandler.ViewHandler.write_detailed_process_cpu', return_value=False)
    # patch the view context
    handler.view_ctx = Mock(parameters={PROCESS: None})
    # patch the meld elements
    process_h_mid = create_element()
    instance_fig_mid = create_element()
    cpuimage_fig_mid = create_element()
    memimage_fig_mid = create_element()
    stats_elt = create_element({'process_h_mid': process_h_mid, 'instance_fig_mid': instance_fig_mid,
                                'cpuimage_fig_mid': cpuimage_fig_mid, 'memimage_fig_mid': memimage_fig_mid})
    root_elt = create_element({'pstats_div_mid': stats_elt})
    # test call with no namespec selection
    info = {}
    handler.write_process_statistics(root_elt, info)
    assert root_elt.findmeld.call_args_list == [call('pstats_div_mid')]
    assert stats_elt.replace.call_args_list == [call('')]
    assert not stats_elt.findmeld.called
    assert not mocked_cpu.called
    assert not mocked_mem.called
    assert not process_h_mid.content.called
    assert not instance_fig_mid.content.called
    assert not cpuimage_fig_mid.replace.called
    assert not memimage_fig_mid.replace.called
    assert not mocked_plots.called
    root_elt.reset_all()
    # test call with namespec selection and no stats found
    info = {'namespec': 'dummy_proc', 'identifier': '10.0.0.1', 'proc_stats': 'dummy_stats', 'nb_cores': 8}
    handler.write_process_statistics(root_elt, info)
    assert root_elt.findmeld.call_args_list == [call('pstats_div_mid')]
    assert not stats_elt.replace.called
    assert not stats_elt.findmeld.called
    assert mocked_cpu.call_args_list == [call(stats_elt, 'dummy_stats', 8)]
    assert mocked_mem.call_args_list == [call(stats_elt, 'dummy_stats')]
    assert not process_h_mid.content.called
    assert not instance_fig_mid.content.called
    assert not cpuimage_fig_mid.replace.called
    assert not memimage_fig_mid.replace.called
    assert not mocked_plots.called
    root_elt.reset_all()
    mocker.resetall()
    # test call with namespec selection and stats found
    mocked_cpu.return_value = True
    handler.write_process_statistics(root_elt, info)
    assert root_elt.findmeld.call_args_list == [call('pstats_div_mid')]
    assert stats_elt.findmeld.call_args_list == [call('process_h_mid'), call('instance_fig_mid')]
    assert not stats_elt.replace.called
    assert mocked_cpu.call_args_list == [call(stats_elt, 'dummy_stats', 8)]
    assert mocked_mem.call_args_list == [call(stats_elt, 'dummy_stats')]
    assert process_h_mid.content.call_args_list == [call('dummy_proc')]
    assert instance_fig_mid.content.call_args_list == [call('10.0.0.1')]
    assert not cpuimage_fig_mid.replace.called
    assert not memimage_fig_mid.replace.called
    assert mocked_plots.call_args_list == [call('dummy_stats', 8)]
    root_elt.reset_all()
    mocker.resetall()
    # test again with matplotlib import failure
    mocked_plots.return_value = False
    handler.write_process_statistics(root_elt, info)
    assert root_elt.findmeld.call_args_list == [call('pstats_div_mid')]
    assert stats_elt.findmeld.call_args_list == [call('process_h_mid'), call('instance_fig_mid'),
                                                 call('cpuimage_fig_mid'), call('memimage_fig_mid')]
    assert not stats_elt.replace.called
    assert mocked_cpu.call_args_list == [call(stats_elt, 'dummy_stats', 8)]
    assert mocked_mem.call_args_list == [call(stats_elt, 'dummy_stats')]
    assert process_h_mid.content.call_args_list == [call('dummy_proc')]
    assert instance_fig_mid.content.call_args_list == [call('10.0.0.1')]
    assert cpuimage_fig_mid.replace.call_args_list == [call('')]
    assert memimage_fig_mid.replace.call_args_list == [call('')]
    assert mocked_plots.call_args_list == [call('dummy_stats', 8)]


def test_handle_action(handler):
    """ Test the handle_action method. """
    handler.view_ctx = Mock(parameters={'namespec': 'dummy_proc'}, **{'get_action.return_value': None})
    handler.callback = None
    handler.make_callback = Mock(return_value=lambda: NOT_DONE_YET)
    # test no action requested
    assert not handler.handle_action()
    assert not handler.make_callback.called
    # test no action in progress
    handler.view_ctx.get_action.return_value = 'test'
    assert handler.handle_action() == NOT_DONE_YET
    assert handler.make_callback.call_args_list == [call('dummy_proc', 'test')]
    handler.make_callback.reset_mock()
    # test action in progress
    assert handler.handle_action() == NOT_DONE_YET
    assert not handler.make_callback.called
    # test action completed
    handler.callback = None
    handler.make_callback = Mock(return_value=lambda: 'a message')
    assert not handler.handle_action()
    assert handler.make_callback.call_args_list == [call('dummy_proc', 'test')]
    assert handler.view_ctx.store_message == ('info', 'a message')


def test_make_callback(handler):
    """ Test the make_callback method. """
    with pytest.raises(NotImplementedError):
        handler.make_callback('dummy_namespec', 'dummy_action')


def test_multicall_rpc_action(mocker, handler):
    """ Test the multicall_rpc_action method. """
    mocked_rpc = mocker.patch('supvisors.web.viewhandler.generic_rpc', return_value='a deferred result')
    multicall = [{'methodName': 'supervisor.stopProcessGroup', 'params': ['dummy_proc']},
                 {'methodName': 'supervisor.startProcessGroup', 'params': ['dummy_proc', False]}]
    assert handler.multicall_rpc_action(multicall, 'successful') == 'a deferred result'
    assert mocked_rpc.call_args_list == [call(handler.supvisors.supervisor_data.system_rpc_interface,
                                              'multicall', (multicall,), 'successful')]


def test_supervisor_rpc_action(mocker, handler):
    """ Test the supervisor_rpc_action method. """
    mocked_rpc = mocker.patch('supvisors.web.viewhandler.generic_rpc', return_value='a deferred result')
    assert handler.supervisor_rpc_action('startProcess', ('dummy_proc', True), 'successful') == 'a deferred result'
    assert mocked_rpc.call_args_list == [call(handler.supvisors.supervisor_data.supervisor_rpc_interface,
                                              'startProcess', ('dummy_proc', True), 'successful')]


def test_supvisors_rpc_action(mocker, handler):
    """ Test the supvisors_rpc_action method. """
    mocked_rpc = mocker.patch('supvisors.web.viewhandler.generic_rpc', return_value='a deferred result')
    assert handler.supvisors_rpc_action('start_process', (1, 'dummy_proc', True), 'successful') == 'a deferred result'
    assert mocked_rpc.call_args_list == [call(handler.supvisors.supervisor_data.supvisors_rpc_interface,
                                              'start_process', (1, 'dummy_proc', True), 'successful')]


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
