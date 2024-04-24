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
from supervisor.web import MeldView

from supvisors.ttypes import SupvisorsInstanceStates
from supvisors.web.viewinstance import *
from supvisors.web.webutils import HOST_INSTANCE_PAGE, PROC_INSTANCE_PAGE
from .base import DummyHttpContext
from .conftest import create_element


@pytest.fixture
def http_context(supvisors):
    """ Fixture for a consistent mocked HTTP context provided by Supervisor. """
    http_context = DummyHttpContext('ui/host_instance.html')
    http_context.supervisord.supvisors = supvisors
    supvisors.supervisor_data.supervisord = http_context.supervisord
    return http_context


@pytest.fixture
def view(http_context):
    """ Return the instance to test. """
    # apply the forced inheritance done in supvisors.plugin
    StatusView.__bases__ = (ViewHandler,)
    # create the instance to be tested
    return SupvisorsInstanceView(http_context, HOST_INSTANCE_PAGE)


@pytest.fixture
def view_no_stats(http_context):
    """ Return the instance to test, in which statistics have been disabled. """
    # apply the forced inheritance done in supvisors.plugin
    StatusView.__bases__ = (ViewHandler,)
    # create the instance to be tested
    http_context.supervisord.supvisors.stats_collector = None
    return SupvisorsInstanceView(http_context, HOST_INSTANCE_PAGE)


def test_init(view):
    """ Test the values set at construction. """
    # test instance inheritance
    for klass in [StatusView, ViewHandler, MeldView]:
        assert isinstance(view, klass)
    # test parameter page name
    assert view.page_name == HOST_INSTANCE_PAGE
    assert view.has_host_statistics
    assert view.has_process_statistics


def test_init_no_stats(view_no_stats):
    """ Test the values set at construction. """
    # test instance inheritance
    for klass in [StatusView, ViewHandler, MeldView]:
        assert isinstance(view_no_stats, klass)
    # test parameter page name
    assert view_no_stats.page_name == HOST_INSTANCE_PAGE
    assert not view_no_stats.has_host_statistics
    assert not view_no_stats.has_process_statistics


def test_render(mocker, view):
    """ Test the render method. """
    mocked_render = mocker.patch('supvisors.web.viewhandler.ViewHandler.render', return_value='default')
    assert view.render() == 'default'
    assert mocked_render.call_args_list == [call(view)]


def test_write_navigation(mocker, view):
    """ Test the write_navigation method. """
    mocked_nav = mocker.patch.object(view, 'write_nav')
    mocked_root = Mock()
    view.write_navigation(mocked_root)
    local_identifier = view.supvisors.mapper.local_identifier
    assert mocked_nav.call_args_list == [call(mocked_root, identifier=local_identifier)]


def test_write_header(mocker, supvisors, view):
    """ Test the write_header method. """
    mocked_actions = mocker.patch.object(view, 'write_instance_actions')
    mocked_periods = mocker.patch.object(view, 'write_periods')
    # build root structure
    instance_mid = create_element()
    state_mid = create_element()
    starting_mid = create_element()
    stopping_mid = create_element()
    discovery_mid = create_element()
    master_mid = create_element()
    header_mid = create_element({'master_mid': master_mid, 'instance_mid': instance_mid, 'state_mid': state_mid,
                                 'discovery_mid': discovery_mid, 'starting_mid': starting_mid,
                                 'stopping_mid': stopping_mid})
    mocked_root = create_element({'header_mid': header_mid})
    # first call tests with local instance not master, stopping jobs in progress and no discovery mode
    status = supvisors.context.local_status
    status._state = SupvisorsInstanceStates.RUNNING
    status.times.remote_time = 3600
    status.state_modes.stopping_jobs = True
    mocker.patch.object(status, 'get_load', return_value=12)
    assert not view.sup_ctx.is_master
    assert not view.sup_ctx.local_status.state_modes.discovery_mode
    view.write_header(mocked_root)
    assert mocked_root.findmeld.call_args_list == [call('header_mid')]
    assert header_mid.findmeld.call_args_list == [call('instance_mid'), call('state_mid'), call('stopping_mid')]
    assert not master_mid.content.called
    assert not discovery_mid.content.called
    assert instance_mid.content.call_args_list == [call(status.supvisors_id.nick_identifier)]
    assert state_mid.content.call_args_list == [call('RUNNING')]
    assert starting_mid.attrib['class'] == ''
    assert stopping_mid.attrib['class'] == 'blink'
    assert mocked_periods.call_args_list == [call(header_mid)]
    assert mocked_actions.call_args_list == [call(header_mid, status)]
    # reset mocks
    mocker.resetall()
    mocked_root.reset_all()
    # second call tests with master, discovery mode enabled and both Starter and Stopper having jobs
    view.sup_ctx.local_status.state_modes.master_identifier = view.sup_ctx.local_identifier
    assert view.sup_ctx.is_master
    status.state_modes.starting_jobs = True
    view.sup_ctx.local_status.state_modes.discovery_mode = True
    view.write_header(mocked_root)
    assert mocked_root.findmeld.call_args_list == [call('header_mid')]
    assert header_mid.findmeld.call_args_list == [call('master_mid'), call('instance_mid'), call('state_mid'),
                                                  call('discovery_mid'), call('starting_mid'), call('stopping_mid')]
    assert master_mid.content.call_args_list == [call(MASTER_SYMBOL)]
    assert discovery_mid.content.call_args_list == [call('discovery')]
    assert instance_mid.content.call_args_list == [call(status.supvisors_id.nick_identifier)]
    assert state_mid.content.call_args_list == [call('RUNNING')]
    assert starting_mid.attrib['class'] == 'blink'
    assert stopping_mid.attrib['class'] == 'blink'
    assert mocked_periods.call_args_list == [call(header_mid)]
    assert mocked_actions.call_args_list == [call(header_mid, status)]


def test_write_instance_actions(mocker, view):
    """ Test the SupvisorsInstanceView.write_instance_actions method. """
    mocker.patch.object(view, 'write_view_switch')
    # set context (meant to be set through render)
    view.view_ctx = Mock(**{'format_url.return_value': 'an url'})
    # set instance context
    mocked_status = Mock(**{'supvisors_id.host_name': '10.0.0.1'})
    # build root structure
    mocked_stop_mid = create_element()
    mocked_restart_mid = create_element()
    mocked_shutdown_mid = create_element()
    mocked_root = create_element({'stopall_a_mid': mocked_stop_mid, 'restartsup_a_mid': mocked_restart_mid,
                                  'shutdownsup_a_mid': mocked_shutdown_mid})
    # test call when SupvisorsInstanceView is a host page
    view.page_name = HOST_INSTANCE_PAGE
    view.write_instance_actions(mocked_root, mocked_status)
    assert mocked_root.findmeld.call_args_list == [call('stopall_a_mid'), call('restartsup_a_mid'),
                                                   call('shutdownsup_a_mid')]
    assert view.view_ctx.format_url.call_args_list == [call('', HOST_INSTANCE_PAGE, **{ACTION: 'stopall'}),
                                                       call('', HOST_INSTANCE_PAGE, **{ACTION: 'restartsup'}),
                                                       call('', HOST_INSTANCE_PAGE, **{ACTION: 'shutdownsup'})]
    assert mocked_stop_mid.attributes.call_args_list == [call(href='an url')]
    assert mocked_restart_mid.attributes.call_args_list == [call(href='an url')]
    assert mocked_shutdown_mid.attributes.call_args_list == [call(href='an url')]


def test_write_view_switch(view):
    """ Test the SupvisorsInstanceView.write_view_switch method. """
    # set context (meant to be set through constructor and render)
    view.has_host_statistics = True
    view.view_ctx = Mock(**{'format_url.return_value': 'an url'})
    # set instance context
    mocked_status = Mock(**{'supvisors_id.host_id': '10.0.0.1'})
    # build root structure
    mocked_process_view_mid = create_element()
    mocked_host_view_mid = create_element()
    mocked_view_mid = create_element()
    mocked_root = create_element({'process_view_a_mid': mocked_process_view_mid,
                                  'host_view_a_mid': mocked_host_view_mid,
                                  'view_div_mid': mocked_view_mid})
    # test call when SupvisorsInstanceView is a host page
    view.page_name = HOST_INSTANCE_PAGE
    view.write_view_switch(mocked_root, mocked_status)
    assert mocked_root.findmeld.call_args_list == [call('process_view_a_mid'), call('host_view_a_mid'), ]
    assert view.view_ctx.format_url.call_args_list == [call('', PROC_INSTANCE_PAGE)]
    assert mocked_process_view_mid.attributes.call_args_list == [call(href='an url')]
    assert mocked_host_view_mid.content.call_args_list == [call('10.0.0.1')]
    assert not mocked_view_mid.replace.called
    mocked_root.reset_all()
    view.view_ctx.format_url.reset_mock()
    # test call when SupvisorsInstanceView is a process page and statistics are enabled
    view.page_name = PROC_INSTANCE_PAGE
    view.write_view_switch(mocked_root, mocked_status)
    assert mocked_root.findmeld.call_args_list == [call('host_view_a_mid')]
    assert view.view_ctx.format_url.call_args_list == [call('', HOST_INSTANCE_PAGE)]
    assert not mocked_process_view_mid.attributes.called
    assert mocked_host_view_mid.attributes.call_args_list == [call(href='an url')]
    assert mocked_host_view_mid.content.call_args_list == [call('10.0.0.1')]
    assert not mocked_view_mid.replace.called
    mocked_root.reset_all()
    view.view_ctx.format_url.reset_mock()
    # test call when statistics are disabled or collector is missing
    view.has_host_statistics = False
    for page in [PROC_INSTANCE_PAGE, HOST_INSTANCE_PAGE]:
        view.page_name = page
        view.write_view_switch(mocked_root, mocked_status)
        assert mocked_root.findmeld.call_args_list == [call('view_div_mid')]
        assert not mocked_host_view_mid.content.called
        assert mocked_host_view_mid.attrib == {'class': ''}
        assert not view.view_ctx.format_url.called
        assert not mocked_process_view_mid.attributes.called
        assert not mocked_host_view_mid.attributes.called
        assert mocked_view_mid.replace.call_args_list == [call('')]
        mocked_root.reset_all()


def test_make_callback(mocker, view):
    """ Test the make_callback method. """
    # test restart
    mocked_action = mocker.patch.object(view, 'restart_sup_action', return_value='restart')
    assert view.make_callback('namespec', 'restartsup') == 'restart'
    assert mocked_action.call_args_list == [call()]
    # test shutdown
    mocked_action = mocker.patch.object(view, 'shutdown_sup_action', return_value='shutdown')
    assert view.make_callback('namespec', 'shutdownsup') == 'shutdown'
    assert mocked_action.call_args_list == [call()]
    # test restart
    mocked_action = mocker.patch('supervisor.web.StatusView.make_callback', return_value='default')
    assert view.make_callback('namespec', 'other') == 'default'
    assert mocked_action.call_args_list == [call(view, 'namespec', 'other')]


def test_restart_sup_action(mocker, view):
    """ Test the restart_sup_action method. """
    mocker.patch('supvisors.web.viewinstance.delayed_warn', return_value='delayed warn')
    mocked_pusher = mocker.patch.object(view.supvisors.rpc_handler, 'send_restart')
    local_identifier = view.supvisors.mapper.local_identifier
    assert view.restart_sup_action() == 'delayed warn'
    assert mocked_pusher.call_args_list == [call(local_identifier)]


def test_shutdown_sup_action(mocker, view):
    """ Test the shutdown_sup_action method. """
    mocker.patch('supvisors.web.viewinstance.delayed_warn', return_value='delayed warn')
    mocked_pusher = mocker.patch.object(view.supvisors.rpc_handler, 'send_shutdown')
    local_identifier = view.supvisors.mapper.local_identifier
    assert view.shutdown_sup_action() == 'delayed warn'
    assert mocked_pusher.call_args_list == [call(local_identifier)]
