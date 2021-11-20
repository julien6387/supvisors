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

from time import ctime
from typing import Any, Callable, Tuple

# HTML page names
SUPVISORS_PAGE = 'index.html'
HOST_NODE_PAGE = 'hostaddress.html'
PROC_NODE_PAGE = 'procaddress.html'
APPLICATION_PAGE = 'application.html'
TAIL_PAGE = 'tail.html'
STDOUT_PAGE = 'logtail/%s'
STDERR_PAGE = 'logtail/%s/stderr'

# gravity classes for messages
# use of 'erro' instead of 'error' in order to avoid HTTP error log traces
Info = 'info'
Warn = 'warn'
Error = 'erro'


def format_gravity_message(message):
    """ Add a gravity to a message if not present."""
    if not isinstance(message, tuple):
        # gravity is not set by Supervisor so let's deduce it
        if 'ERROR' in message:
            message = message.replace('ERROR: ', '')
            gravity = Error
        elif 'unexpected rpc fault' in message:
            gravity = Warn
        else:
            gravity = Info
        return gravity, message
    # in other cases, Supervisor message is suitable
    return message


def print_message(root: Any, gravity: str, message: str, current_time: float):
    """ Print message as a result of action. """
    # print time
    elt = root.findmeld('time_mid')
    elt.content(ctime(current_time))
    # print message
    elt = root.findmeld('message_mid')
    if message is None:
        # always set the refresh time by default
        elt.attrib['class'] = 'empty'
        elt.content('')
    else:
        elt.attrib['class'] = gravity
        elt.content(message)


def format_message(msg, node_name=None) -> Tuple[str, str]:
    """ Define a global message structure. """
    return msg + ' at {}'.format(ctime()) + (' on {}'.format(node_name) if node_name else '')


def info_message(msg, node_name=None) -> Tuple[str, str]:
    """ Define an information message. """
    return Info, format_message(msg, node_name)


def warn_message(msg, node_name=None) -> Tuple[str, str]:
    """ Define a warning message. """
    return Warn, format_message(msg, node_name)


def error_message(msg, node_name=None) -> Tuple[str, str]:
    """ Define an error message. """
    return Error, format_message(msg, node_name)


def delayed_message(fct: Callable, msg: str, node_name=None) -> Callable:
    """ Define a delayed message. """
    def on_wait():
        return fct(msg, node_name)

    on_wait.delay = 0.05
    return on_wait


def delayed_info(msg: str, node_name=None) -> Callable:
    """ Define a delayed information message. """
    return delayed_message(info_message, msg, node_name)


def delayed_warn(msg, node_name=None) -> Callable:
    """ Define a delayed warning message. """
    return delayed_message(warn_message, msg, node_name)


def delayed_error(msg, node_name=None) -> Callable:
    """ Define a delayed error message. """
    return delayed_message(error_message, msg, node_name)


def update_attrib(elt, attribute: str, value: str) -> None:
    """ Add a new item to the attribute of an element.

    :param elt: the element to update
    :param attribute: the element attribute to update
    :param value: the value to add
    :return: None
    """
    current_value = elt.attrib.get(attribute, '')
    if value not in current_value:
        elt.attrib[attribute] = '{} {}'.format(current_value, value).strip()


def apply_shade(elt, shaded: bool) -> None:
    """ Apply shade on element.

    :param elt: the element to shade
    :param shaded: the shade status
    :return: None
    """
    if shaded:
        update_attrib(elt, 'class', 'shaded')
    else:
        update_attrib(elt, 'class', 'brightened')
