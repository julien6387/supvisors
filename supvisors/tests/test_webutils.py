#!/usr/bin/python
# -*- coding: utf-8 -*-

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

from types import FunctionType
from unittest.mock import Mock

from supvisors.webutils import *


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


def test_print_message(root):
    """ Test the meld formatting of a message. """
    # test with empty message
    print_message(root, 'gravity', None)
    assert list(root.elts['time_mid'].attrib.keys()) == ['content']
    assert root.elts['message_mid'].attrib['class'] == 'empty'
    assert root.elts['message_mid'].attrib['content'] == ''
    current_time_content = root.elts['time_mid'].attrib['content']
    assert current_time_content is root.elts['time_mid'].attrib['content']
    # test with filled message&
    print_message(root, 'gravity', 'a simple message')
    assert list(root.elts['time_mid'].attrib.keys()) == ['content']
    assert root.elts['message_mid'].attrib['class'] == 'gravity'
    assert root.elts['message_mid'].attrib['content'] == 'a simple message'
    assert current_time_content is not root.elts['time_mid'].attrib['content']


def check_message(func, gravity):
    """ Test the formatting of any message. """
    # test without address
    msg = func('a simple message')
    assert type(msg) is tuple
    assert len(msg) == 2
    assert msg[0] == gravity
    assert msg[1] == 'a simple message at ' + ctime()
    # test with address
    msg = func('another simple message', '10.0.0.1')
    assert type(msg) is tuple
    assert len(msg) == 2
    assert msg[0] == gravity
    assert msg[1] == 'another simple message at ' + ctime() + ' on 10.0.0.1'


def check_delayed_message(func, gravity):
    """ Test the callable returned for any delayed message. """
    # test without address
    msg_cb = func('a simple message')
    assert type(msg_cb) is FunctionType
    assert msg_cb.delay == 0.05
    msg = msg_cb()
    assert type(msg) is tuple
    assert len(msg) == 2
    assert msg[0] == gravity
    assert msg[1] == 'a simple message at ' + ctime()
    # test with address
    msg_cb = func('another simple message', '10.0.0.1')
    assert type(msg_cb) is FunctionType
    assert msg_cb.delay == 0.05
    msg = msg_cb()
    assert type(msg) is tuple
    assert len(msg) == 2
    assert msg[0] == gravity
    assert msg[1] == 'another simple message at ' + ctime() + ' on 10.0.0.1'


def test_info_message():
    """ Test the formatting of an information message. """
    check_message(info_message, 'info')


def test_warn_message():
    """ Test the formatting of a warning message. """
    check_message(warn_message, 'warn')


def test_error_message():
    """ Test the formatting of an error message. """
    check_message(error_message, 'erro')


def test_delayed_info():
    """ Test the callable returned for a delayed information message. """
    check_delayed_message(delayed_info, 'info')


def test_delayed_warn():
    """ Test the callable returned for a delayed warning message. """
    check_delayed_message(delayed_warn, 'warn')


def test_delayed_error():
    """ Test the callable returned for a delayed error message. """
    check_delayed_message(delayed_error, 'erro')


def test_apply_shade():
    """ Test the formatting of shaded / non-shaded elements. """
    elt = Mock(attrib={})
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
