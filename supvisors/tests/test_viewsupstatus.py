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

from supvisors.viewsupstatus import *
from supvisors.webutils import HOST_NODE_PAGE, PROC_NODE_PAGE

from .base import DummyHttpContext


@pytest.fixture
def view(supvisors):
    """ Return the instance to test. """
    # apply the forced inheritance done in supvisors.plugin
    StatusView.__bases__ = (ViewHandler,)
    # create the instance to be tested
    return SupvisorsAddressView(DummyHttpContext('ui/hostaddress.html'), HOST_NODE_PAGE)


def test_init(view):
    """ Test the values set at construction. """
    # test instance inheritance
    for klass in [StatusView, ViewHandler, MeldView]:
        assert isinstance(view, klass)
    # test parameter page name
    assert view.page_name == HOST_NODE_PAGE


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
    assert mocked_nav.call_args_list == [call(mocked_root, node_name='127.0.0.1')]


def test_write_header(mocker, view):
    """ Test the write_header method. """
    mocker.patch('supvisors.viewsupstatus.simple_localtime', return_value='07:05:30')
    mocked_actions = mocker.patch('supvisors.viewsupstatus.SupvisorsAddressView.write_address_actions')
    mocked_periods = mocker.patch('supvisors.viewsupstatus.SupvisorsAddressView.write_periods')
    from supvisors.ttypes import AddressStates
    # build root structure
    mocked_mids = [Mock(attrib={}) for _ in range(4)]
    mocked_root = Mock(**{'findmeld.side_effect': mocked_mids * 2})
    # first call tests with not master
    mocked_status = Mock(remote_time=3600, state=AddressStates.RUNNING, **{'get_loading.return_value': 12})
    view.sup_ctx._is_master = False
    view.sup_ctx.nodes['127.0.0.1'] = mocked_status
    view.write_header(mocked_root)
    assert mocked_root.findmeld.call_args_list == [call('address_mid'), call('state_mid'), call('percent_mid'),
                                                   call('date_mid')]
    assert mocked_mids[0].attrib == {}
    assert mocked_mids[0].content.call_args_list == [call('127.0.0.1')]
    assert mocked_mids[1].content.call_args_list == [call('RUNNING')]
    assert mocked_mids[2].content.call_args_list == [call('12%')]
    assert mocked_mids[3].content.call_args_list == [call('07:05:30')]
    assert mocked_periods.call_args_list == [call(mocked_root)]
    assert mocked_actions.call_args_list == [call(mocked_root)]
    # reset mocks
    mocked_root.findmeld.reset_mock()
    mocked_periods.reset_mock()
    mocked_actions.reset_mock()
    for mocked_mid in mocked_mids:
        mocked_mid.content.reset_mock()
    # second call tests with master
    view.sup_ctx._is_master = True
    view.write_header(mocked_root)
    assert mocked_root.findmeld.call_args_list == [call('address_mid'), call('state_mid'), call('percent_mid'),
                                                   call('date_mid')]
    assert mocked_mids[0].attrib == {'class': 'master'}
    assert mocked_mids[0].content.call_args_list == [call('127.0.0.1')]
    assert mocked_mids[1].content.call_args_list == [call('RUNNING')]
    assert mocked_mids[2].content.call_args_list == [call('12%')]
    assert mocked_mids[3].content.call_args_list == [call('07:05:30')]
    assert mocked_periods.call_args_list == [call(mocked_root)]
    assert mocked_actions.call_args_list == [call(mocked_root)]


def test_write_address_actions(view):
    """ Test the write_address_actions method. """
    # set context (meant to be set through render)
    view.view_ctx = Mock(**{'format_url.return_value': 'an url'})
    # build root structure
    mocked_view_mid = Mock(attrib={'class': ''})
    mocked_stop_mid = Mock(attrib={'class': ''})
    mocked_root = Mock(**{'findmeld.side_effect': [mocked_view_mid, mocked_stop_mid] * 2})
    # test call
    view.write_address_actions(mocked_root)
    assert mocked_root.findmeld.call_args_list == [call('view_a_mid'), call('stopall_a_mid')]
    assert view.view_ctx.format_url.call_args_list == [call('', PROC_NODE_PAGE),
                                                       call('', HOST_NODE_PAGE, **{ACTION: 'stopall'})]
    assert mocked_view_mid.attributes.call_args_list == [call(href='an url')]
    assert mocked_stop_mid.attributes.call_args_list == [call(href='an url')]
    # reset mocks
    mocked_root.findmeld.reset_mock()
    view.view_ctx.format_url.reset_mock()
    mocked_view_mid.attributes.reset_mock()
    mocked_stop_mid.attributes.reset_mock()
    # test call with PROC_ADDRESS_PAGE as self.page_name
    view.page_name = PROC_NODE_PAGE
    view.write_address_actions(mocked_root)
    assert mocked_root.findmeld.call_args_list == [call('view_a_mid'), call('stopall_a_mid')]
    assert view.view_ctx.format_url.call_args_list == [call('', HOST_NODE_PAGE),
                                                       call('', PROC_NODE_PAGE, **{ACTION: 'stopall'})]
    assert mocked_view_mid.attributes.call_args_list == [call(href='an url')]
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
    assert view.restart_sup_action() == 'delayed warn'
    assert mocked_pusher.call_args_list == [call('127.0.0.1')]


def test_shutdown_sup_action(mocker, view):
    """ Test the shutdown_sup_action method. """
    mocker.patch('supvisors.viewsupstatus.delayed_warn', return_value='delayed warn')
    mocked_pusher = mocker.patch.object(view.supvisors.zmq.pusher, 'send_shutdown')
    assert view.shutdown_sup_action() == 'delayed warn'
    assert mocked_pusher.call_args_list == [call('127.0.0.1')]
