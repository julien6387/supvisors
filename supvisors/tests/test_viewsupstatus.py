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
from unittest.mock import call, Mock

from supvisors.ttypes import SupvisorsInstanceStates
from supvisors.viewsupstatus import *
from supvisors.webutils import HOST_INSTANCE_PAGE, PROC_INSTANCE_PAGE

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


def test_init(view):
    """ Test the values set at construction. """
    # test instance inheritance
    for klass in [StatusView, ViewHandler, MeldView]:
        assert isinstance(view, klass)
    # test parameter page name
    assert view.page_name == HOST_INSTANCE_PAGE


def test_render(mocker, view):
    """ Test the render method. """
    mocked_render = mocker.patch('supvisors.viewhandler.ViewHandler.render', return_value='default')
    assert view.render() == 'default'
    assert mocked_render.call_args_list == [call(view)]


def test_write_navigation(mocker, view):
    """ Test the write_navigation method. """
    mocked_nav = mocker.patch.object(view, 'write_nav')
    mocked_root = Mock()
    view.write_navigation(mocked_root)
    local_identifier = view.supvisors.supvisors_mapper.local_identifier
    assert mocked_nav.call_args_list == [call(mocked_root, identifier=local_identifier)]


def test_write_header(mocker, view):
    """ Test the write_header method. """
    mocked_actions = mocker.patch.object(view, 'write_instance_actions')
    mocked_periods = mocker.patch.object(view, 'write_periods')
    # build root structure
    instance_mid = create_element()
    state_mid = create_element()
    percent_mid = create_element()
    mocked_root = create_element({'instance_mid': instance_mid, 'state_mid': state_mid, 'percent_mid': percent_mid})
    # first call tests with not master
    mocked_status = Mock(remote_time=3600, state=SupvisorsInstanceStates.RUNNING, **{'get_load.return_value': 12})
    local_identifier = view.supvisors.supvisors_mapper.local_identifier
    view.sup_ctx._is_master = False
    view.sup_ctx.instances[local_identifier] = mocked_status
    view.write_header(mocked_root)
    assert mocked_root.findmeld.call_args_list == [call('instance_mid'), call('state_mid'), call('percent_mid')]
    assert instance_mid.content.call_args_list == [call(local_identifier)]
    assert state_mid.content.call_args_list == [call('RUNNING')]
    assert percent_mid.content.call_args_list == [call('12%')]
    assert mocked_periods.call_args_list == [call(mocked_root)]
    assert mocked_actions.call_args_list == [call(mocked_root, mocked_status)]
    # reset mocks
    mocker.resetall()
    mocked_root.reset_all()
    # second call tests with master
    view.sup_ctx._is_master = True
    view.write_header(mocked_root)
    assert mocked_root.findmeld.call_args_list == [call('instance_mid'), call('state_mid'), call('percent_mid')]
    assert instance_mid.content.call_args_list == [call(f'{MASTER_SYMBOL} {local_identifier}')]
    assert state_mid.content.call_args_list == [call('RUNNING')]
    assert percent_mid.content.call_args_list == [call('12%')]
    assert mocked_periods.call_args_list == [call(mocked_root)]
    assert mocked_actions.call_args_list == [call(mocked_root, mocked_status)]


def test_write_instance_actions(view):
    """ Test the write_instance_actions method. """
    # set context (meant to be set through render)
    view.view_ctx = Mock(**{'format_url.return_value': 'an url'})
    # set instance context
    mocked_status = Mock(**{'supvisors_id.host_name': '10.0.0.1'})
    # build root structure
    mocked_process_view_mid = Mock(attrib={'class': ''})
    mocked_host_view_mid = Mock(attrib={'class': ''})
    mocked_view_mid = Mock(attrib={'class': ''})
    mocked_stop_mid = Mock(attrib={'class': ''})
    mid_map = {'process_view_a_mid': mocked_process_view_mid, 'host_view_a_mid': mocked_host_view_mid,
               'view_div_mid': mocked_view_mid, 'stopall_a_mid': mocked_stop_mid}
    mocked_root = Mock(**{'findmeld.side_effect': lambda x: mid_map[x]})
    # statistics are first enabled
    view.supvisors.options.stats_enabled = True
    # test call when SupvisorsInstanceView is a host page
    view.page_name = HOST_INSTANCE_PAGE
    view.write_instance_actions(mocked_root, mocked_status)
    assert mocked_root.findmeld.call_args_list == [call('process_view_a_mid'), call('host_view_a_mid'),
                                                   call('stopall_a_mid')]
    assert view.view_ctx.format_url.call_args_list == [call('', PROC_INSTANCE_PAGE),
                                                       call('', HOST_INSTANCE_PAGE, **{ACTION: 'stopall'})]
    assert mocked_process_view_mid.attributes.call_args_list == [call(href='an url')]
    assert mocked_host_view_mid.content.call_args_list == [call('10.0.0.1')]
    assert not mocked_view_mid.replace.called
    assert mocked_stop_mid.attributes.call_args_list == [call(href='an url')]
    # reset mocks
    mocked_root.findmeld.reset_mock()
    view.view_ctx.format_url.reset_mock()
    mocked_process_view_mid.attributes.reset_mock()
    mocked_host_view_mid.content.reset_mock()
    mocked_stop_mid.attributes.reset_mock()
    # test call when SupvisorsInstanceView is a process page
    view.page_name = PROC_INSTANCE_PAGE
    view.write_instance_actions(mocked_root, mocked_status)
    assert mocked_root.findmeld.call_args_list == [call('host_view_a_mid'), call('stopall_a_mid')]
    assert view.view_ctx.format_url.call_args_list == [call('', HOST_INSTANCE_PAGE),
                                                       call('', PROC_INSTANCE_PAGE, **{ACTION: 'stopall'})]
    assert not mocked_process_view_mid.attributes.called
    assert mocked_host_view_mid.attributes.call_args_list == [call(href='an url')]
    assert mocked_host_view_mid.content.call_args_list == [call('10.0.0.1')]
    assert not mocked_view_mid.replace.called
    assert mocked_stop_mid.attributes.call_args_list == [call(href='an url')]
    # reset mocks
    mocked_root.findmeld.reset_mock()
    view.view_ctx.format_url.reset_mock()
    mocked_host_view_mid.attributes.reset_mock()
    mocked_host_view_mid.content.reset_mock()
    mocked_stop_mid.attributes.reset_mock()
    # test call with statistics disabled
    view.supvisors.options.stats_enabled = False
    view.write_instance_actions(mocked_root, mocked_status)
    assert mocked_root.findmeld.call_args_list == [call('view_div_mid'), call('stopall_a_mid')]
    assert view.view_ctx.format_url.call_args_list == [call('', PROC_INSTANCE_PAGE, **{ACTION: 'stopall'})]
    assert not mocked_process_view_mid.attributes.called
    assert not mocked_host_view_mid.attributes.called
    assert not mocked_host_view_mid.content.called
    assert mocked_view_mid.replace.call_args_list == [call('')]
    assert mocked_stop_mid.attributes.call_args_list == [call(href='an url')]


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
    mocker.patch('supvisors.viewsupstatus.delayed_warn', return_value='delayed warn')
    mocked_pusher = mocker.patch.object(view.supvisors.zmq.pusher, 'send_restart')
    local_identifier = view.supvisors.supvisors_mapper.local_identifier
    assert view.restart_sup_action() == 'delayed warn'
    assert mocked_pusher.call_args_list == [call(local_identifier)]


def test_shutdown_sup_action(mocker, view):
    """ Test the shutdown_sup_action method. """
    mocker.patch('supvisors.viewsupstatus.delayed_warn', return_value='delayed warn')
    mocked_pusher = mocker.patch.object(view.supvisors.zmq.pusher, 'send_shutdown')
    local_identifier = view.supvisors.supvisors_mapper.local_identifier
    assert view.shutdown_sup_action() == 'delayed warn'
    assert mocked_pusher.call_args_list == [call(local_identifier)]
