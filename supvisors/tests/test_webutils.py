# ======================================================================
# Copyright 2016 Julien LE CLEACH
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

from unittest.mock import call

from supvisors.web.webutils import *
from .conftest import create_element


def test_process_row_types():
    """ Test the ProcessRowTypes enumeration. """
    expected = ['INSTANCE_PROCESS', 'SUPERVISOR_PROCESS', 'APPLICATION_PROCESS', 'APPLICATION']
    assert [x.name for x in ProcessRowTypes] == expected


def test_format_gravity_message():
    """ Test the formatting of web messages. """
    # test Supervisor information message
    msg = format_gravity_message('an information message')
    assert type(msg) is tuple
    assert msg == ('info', 'an information message')
    # test Supervisor error message
    msg = format_gravity_message('ERROR: an error message')
    assert type(msg) is tuple
    assert msg == ('erro', 'an error message')
    # test Supervisor warning message
    msg = format_gravity_message('unexpected rpc fault')
    assert type(msg) is tuple
    assert msg == ('warn', 'unexpected rpc fault')
    # test Supvisors information message
    msg = format_gravity_message(('info', 'an information message'))
    assert type(msg) is tuple
    assert msg == ('info', 'an information message')


def test_print_message(mocker):
    """ Test the meld formatting of a message. """
    mocker.patch('supvisors.web.webutils.ctime', return_value='a date')
    # create element structure
    time_mid = create_element()
    identifier_mid = create_element()
    message_mid = create_element()
    root = create_element({'time_mid': time_mid, 'message_mid': message_mid, 'identifier_mid': identifier_mid})
    # test with empty message
    print_message(root, 'gravity', None, 1234, '10.0.0.1')
    assert time_mid.content.call_args_list == [mocker.call('a date')]
    assert identifier_mid.content.call_args_list == [mocker.call('10.0.0.1')]
    assert message_mid.content.call_args_list == [mocker.call('')]
    assert message_mid.attrib['class'] == 'empty'
    root.reset_all()
    # test with filled message
    print_message(root, 'gravity', 'a simple message', 1234, '10.0.0.1')
    assert time_mid.content.call_args_list == [mocker.call('a date')]
    assert identifier_mid.content.call_args_list == [mocker.call('10.0.0.1')]
    assert message_mid.content.call_args_list == [mocker.call('a simple message')]
    assert message_mid.attrib['class'] == 'gravity'


def check_message(gravity: SupvisorsGravities):
    """ Test the formatting of any message. """
    # test without address
    msg = WebMessage('a simple message', gravity)
    assert msg.message == 'a simple message at now'
    assert msg.gravity_message == (gravity.value, 'a simple message at now')
    cb = msg.delayed_message
    assert cb() == (gravity.value, 'a simple message at now')
    # test with address
    msg = WebMessage('a simple message', gravity, identifier='10.0.0.1')
    assert msg.message == 'a simple message at now on 10.0.0.1'
    assert msg.gravity_message == (gravity.value, 'a simple message at now on 10.0.0.1')
    cb = msg.delayed_message
    assert cb() == (gravity.value, 'a simple message at now on 10.0.0.1')


def test_web_message(mocker):
    """ Test the formatting of an information message. """
    mocker.patch('supvisors.web.webutils.ctime', return_value='now')
    for gravity in SupvisorsGravities:
        check_message(gravity)


def test_generic_rpc(mocker, supvisors_instance):
    """ Test the generic_rpc. """
    mocker.patch('supvisors.web.webutils.ctime', return_value='now')
    rpc_intf = supvisors_instance.supervisor_data.supvisors_rpc_interface
    mocked_rpc = mocker.patch.object(rpc_intf, 'start_args')
    params = (0, 'dummy_proc', False)
    # test call with error on main RPC call
    mocked_rpc.side_effect = RPCError('failed RPC')
    cb = generic_rpc(rpc_intf, 'start_args', params, 'started')
    assert cb() == ('erro', 'start_args: UNKNOWN at now')
    assert mocked_rpc.call_args_list == [call(0, 'dummy_proc', False)]
    mocked_rpc.reset_mock()
    # test call with direct result
    mocked_rpc.side_effect = None
    mocked_rpc.return_value = True
    cb = generic_rpc(rpc_intf, 'start_args', params, 'started')
    assert cb() == ('info', 'started at now')
    assert mocked_rpc.call_args_list == [call(0, 'dummy_proc', False)]
    mocked_rpc.reset_mock()
    # test call with indirect result leading to internal RPC error
    mocked_rpc.return_value = lambda: (_ for _ in ()).throw(RPCError(''))
    result = generic_rpc(rpc_intf, 'start_args', params, 'started')
    assert result() == ('erro', 'start_args: UNKNOWN at now')
    assert mocked_rpc.call_args_list == [call(0, 'dummy_proc', False)]
    mocked_rpc.reset_mock()
    # test call with indirect result leading to unfinished job
    mocked_rpc.return_value = lambda: NOT_DONE_YET
    result = generic_rpc(rpc_intf, 'start_args', params, 'started')
    assert result() is NOT_DONE_YET
    assert mocked_rpc.call_args_list == [call(0, 'dummy_proc', False)]
    mocked_rpc.reset_mock()
    # test call with indirect result leading to failure
    mocked_rpc.return_value = lambda: True
    result = generic_rpc(rpc_intf, 'start_args', params, 'started')
    assert result() == ('info', 'started at now')


def test_update_attrib():
    """ Test the update of element attributes. """
    elt = create_element()
    assert elt.attrib['class'] == ''
    update_attrib(elt, 'class', 'button')
    assert elt.attrib['class'] == 'button'
    update_attrib(elt, 'class', 'on')
    assert elt.attrib['class'] == 'button on'
    update_attrib(elt, 'class', 'off active')
    assert elt.attrib['class'] == 'button on off active'


def test_apply_shade():
    """ Test the formatting of shaded / non-shaded elements. """
    elt = create_element()
    # test shaded
    apply_shade(elt, True)
    assert elt.attrib['class'] == 'shaded'
    # test again to check that same value is not doubled
    apply_shade(elt, True)
    assert elt.attrib['class'] == 'shaded'
    # test non-shaded
    apply_shade(elt, False)
    assert elt.attrib['class'] == 'shaded brightened'
    # test again to check that same value is not doubled
    apply_shade(elt, False)
    assert elt.attrib['class'] == 'shaded brightened'
