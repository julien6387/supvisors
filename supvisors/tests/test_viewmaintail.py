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

import os
from unittest.mock import call, Mock

import pytest
import supervisor

from supvisors.web.viewmaintail import *
from .base import DummyHttpContext


@pytest.fixture
def http_context(supvisors):
    """ Fixture for a consistent mocked HTTP context provided by Supervisor. """
    http_context = DummyHttpContext()
    # use a supervisor template for once
    supervisor_path = next(iter(supervisor.__path__), '.')
    http_context.template = os.path.join(supervisor_path, 'ui/tail.html')
    # assign supvisors in supervisord structure
    http_context.supervisord.supvisors = supvisors
    supvisors.supervisor_data.supervisord = http_context.supervisord
    return http_context


@pytest.fixture
def view(http_context):
    """ Return the instance to test. """
    # create the instance to be tested
    return MainTailView(http_context)


def test_init(view):
    """ Test the construction of MainTailView. """
    # test instance inheritance
    assert isinstance(view, MeldView)


def test_render(mocker, view):
    """ Test the MainTailView.render method. """
    rpc_intf = view.context.supervisord.supvisors.supervisor_data.supervisor_rpc_interface
    rpc = mocker.patch.object(rpc_intf, 'readLog', return_value='supervisor log tail')
    # build XML context
    title_elt = Mock()
    body_elt = Mock()
    anchor_elt = Mock()
    mid_map = {'title': title_elt, 'tailbody': body_elt, 'refresh_anchor': anchor_elt}
    mocked_root = Mock(**{'findmeld.side_effect': lambda x: mid_map[x],
                          'write_xhtmlstring.return_value': 'xhtml'})
    mocker.patch('supervisor.web.MeldView.clone', return_value=mocked_root)
    # test RPC error NO_FILE
    rpc.side_effect = RPCError(Faults.NO_FILE)
    assert view.render() == 'xhtml'
    assert title_elt.content.call_args_list == [call('Supervisor tail')]
    assert body_elt.content.call_args_list == [call('No file for Supervisor')]
    assert anchor_elt.attributes.call_args_list == [call(href='maintail.html?limit=1024')]
    for elt in mid_map.values():
        elt.reset_mock()
    # test RPC error BAD_ARGUMENTS
    rpc.side_effect = RPCError(Faults.BAD_ARGUMENTS, 'invalid limit')
    assert view.render() == 'xhtml'
    assert title_elt.content.call_args_list == [call('Supervisor tail')]
    assert body_elt.content.call_args_list == [call('ERROR: unexpected rpc fault [3] BAD_ARGUMENTS: invalid limit')]
    assert anchor_elt.attributes.call_args_list == [call(href='maintail.html?limit=1024')]
    for elt in mid_map.values():
        elt.reset_mock()
    # test normal case
    rpc.side_effect = None
    view.context.form['limit'] = '2048'
    assert view.render() == 'xhtml'
    assert title_elt.content.call_args_list == [call('Supervisor tail')]
    assert body_elt.content.call_args_list == [call('supervisor log tail')]
    assert anchor_elt.attributes.call_args_list == [call(href='maintail.html?limit=2048')]
