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

from unittest.mock import call, Mock

import pytest

from supvisors.web.viewmain import *
from .conftest import create_element, to_simple_url


@pytest.fixture
def view(http_context) -> MainView:
    """ Fixture for the instance to test. """
    view = MainView(http_context)
    view.view_ctx = Mock(parameters={}, **{'format_url.side_effect': to_simple_url})
    return view


def test_init(view):
    """ Test the values set at construction. """
    # test action methods storage
    assert sorted(view.global_methods.keys()) == ['sup_restart', 'sup_shutdown']
    assert all(callable(cb) for cb in view.global_methods.values())


def test_write_navigation(mocker, view):
    """ Test the MainView.write_navigation method. """
    mocked_nav = mocker.patch.object(view, 'write_nav')
    mocked_root = create_element()
    view.write_navigation(mocked_root)
    assert mocked_nav.call_args_list == [call(mocked_root, source=view.local_identifier)]


def test_write_status(mocker, supvisors_instance, view):
    """ Test the MainView.write_status method. """
    # patch context
    sm = {'fsm_statecode': SupvisorsStates.DISTRIBUTION.value,
          'fsm_statename': SupvisorsStates.DISTRIBUTION.name,
          'degraded_mode': False, 'discovery_mode': True,
          'master_identifier': '10.0.0.1',
          'starting_jobs': True, 'stopping_jobs': False,
          'instance_states': {}}
    supvisors_instance.state_modes.local_state_modes.update(sm)
    mocker.patch.object(view.sup_ctx, 'conflicting', return_value=False)
    # build root structure
    state_a_mid = create_element()
    starting_mid = create_element()
    stopping_mid = create_element()
    master_mid = create_element()
    mocked_header = create_element({'state_a_mid': state_a_mid, 'master_name_mid': master_mid,
                                    'starting_mid': starting_mid, 'stopping_mid': stopping_mid})
    # test call with no master, starting jobs and not in CONCILIATION
    view.write_status(mocked_header)
    assert mocked_header.findmeld.call_args_list == [call('state_a_mid'), call('starting_mid'), call('stopping_mid'),
                                                     call('master_name_mid')]
    assert state_a_mid.replace.call_args_list == [call('DISTRIBUTION')]
    assert not state_a_mid.attributes.called
    assert not state_a_mid.content.called
    assert state_a_mid.attrib['class'] == ''
    assert starting_mid.attrib['class'] == 'blink'
    assert not starting_mid.replace.called
    assert stopping_mid.attrib['class'] == ''
    assert stopping_mid.replace.call_args_list == [call('')]
    assert master_mid.content.call_args_list == [call('none')]
    mocked_header.reset_all()
    mocker.resetall()
    # test call with master, in CONCILIATION, but without conflicts (expected solved)
    sm.update({'fsm_statecode': SupvisorsStates.CONCILIATION.value,
               'fsm_statename': SupvisorsStates.CONCILIATION.name,
               'starting_jobs': False, 'stopping_jobs': True})
    supvisors_instance.state_modes.local_state_modes.update(sm)
    supvisors_instance.state_modes.master_identifier = '10.0.0.1:25000'
    view.write_status(mocked_header)
    assert mocked_header.findmeld.call_args_list == [call('state_a_mid'), call('starting_mid'), call('stopping_mid'),
                                                     call('master_name_mid')]
    assert state_a_mid.content.call_args_list == [call('CONCILIATION')]
    assert state_a_mid.attributes.call_args_list == [call(href=SupvisorsPages.CONCILIATION_PAGE)]
    assert not state_a_mid.replace.called
    assert state_a_mid.attrib['class'] == ''
    assert starting_mid.attrib['class'] == ''
    assert starting_mid.replace.call_args_list == [call('')]
    assert stopping_mid.attrib['class'] == 'blink'
    assert not stopping_mid.replace.called
    assert master_mid.content.call_args_list == [call('10.0.0.1')]
    mocked_header.reset_all()
    mocker.resetall()
    # test call with master, in CONCILIATION, and with conflicts
    view.sup_ctx.conflicting.return_value = True
    view.write_status(mocked_header)
    assert mocked_header.findmeld.call_args_list == [call('state_a_mid'), call('starting_mid'), call('stopping_mid'),
                                                     call('master_name_mid')]
    assert state_a_mid.content.call_args_list == [call('CONCILIATION >>')]
    assert state_a_mid.attributes.call_args_list == [call(href=SupvisorsPages.CONCILIATION_PAGE)]
    assert not state_a_mid.replace.called
    assert state_a_mid.attrib['class'] == 'on blink'
    assert starting_mid.attrib['class'] == ''
    assert starting_mid.replace.call_args_list == [call('')]
    assert stopping_mid.attrib['class'] == 'blink'
    assert not stopping_mid.replace.called
    assert master_mid.content.call_args_list == [call('10.0.0.1')]


def test_write_actions(mocker, view):
    """ Test the MainView.write_actions method. """
    mocked_super = mocker.patch('supvisors.web.viewhandler.ViewHandler.write_actions')
    # set context (meant to be set through render)
    view.view_ctx = Mock(**{'format_url.return_value': 'an url'})
    # build root structure
    restart_mid = create_element()
    shutdown_mid = create_element()
    mocked_header = create_element({'restart_a_mid': restart_mid,
                                    'shutdown_a_mid': shutdown_mid})
    # test call
    view.write_actions(mocked_header)
    assert mocked_super.call_args_list == [call(mocked_header)]
    assert mocked_header.findmeld.call_args_list == [call('restart_a_mid'), call('shutdown_a_mid')]
    expected = [call('', SupvisorsPages.SUPVISORS_PAGE, **{ACTION: 'sup_restart'}),
                call('', SupvisorsPages.SUPVISORS_PAGE, **{ACTION: 'sup_shutdown'})]
    assert view.view_ctx.format_url.call_args_list == expected
    assert restart_mid.attributes.call_args_list == [call(href='an url')]
    assert shutdown_mid.attributes.call_args_list == [call(href='an url')]


def test_make_callback(view):
    """ Test the MainView.make_callback method. """
    for action_name in list(view.global_methods.keys()):
        view.global_methods[action_name] = Mock(return_value='%s called' % action_name)
    # patch context
    view.view_ctx = Mock(identifier='10.0.0.2')
    # test unknown action
    assert view.make_callback(None, 'dummy') is None
    # test global actions
    for action in ['sup_restart', 'sup_shutdown']:
        assert view.make_callback('', action) == '%s called' % action
        assert view.global_methods[action].call_args_list == [call()]
        view.global_methods[action].reset_mock()


def test_sup_restart_action(mocker, view):
    """ Test the MainView.sup_shutdown_action method. """
    mocker.patch('supvisors.web.webutils.ctime', return_value='now')
    # test RPC error
    mocker.patch.object(view.supvisors.supervisor_data.supvisors_rpc_interface, 'restart',
                        side_effect=RPCError('failed RPC'))
    cb = view.sup_restart_action()
    assert cb() == ('erro', "restart: code='failed RPC', text='UNKNOWN' at now")
    # test direct result
    mocker.patch.object(view.supvisors.supervisor_data.supvisors_rpc_interface, 'restart',
                        return_value='not callable object')
    cb = view.sup_restart_action()
    assert cb() == ('warn', 'Supvisors restart requested at now')


def test_sup_shutdown_action(mocker, view):
    """ Test the MainView.sup_shutdown_action method. """
    mocker.patch('supvisors.web.webutils.ctime', return_value='now')
    # test RPC error
    mocker.patch.object(view.supvisors.supervisor_data.supvisors_rpc_interface, 'shutdown',
                        side_effect=RPCError('failed RPC'))
    cb = view.sup_shutdown_action()
    assert cb() == ('erro', "shutdown: code='failed RPC', text='UNKNOWN' at now")
    # test direct result
    mocker.patch.object(view.supvisors.supervisor_data.supvisors_rpc_interface, 'shutdown',
                        return_value='not callable object')
    cb = view.sup_shutdown_action()
    assert cb() == ('warn', 'Supvisors shutdown requested at now')
