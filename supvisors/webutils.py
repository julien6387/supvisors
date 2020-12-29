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

# HTML page names
SUPVISORS_PAGE = 'index.html'
HOST_ADDRESS_PAGE = 'hostaddress.html'
PROC_ADDRESS_PAGE = 'procaddress.html'
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


def print_message(root, gravity, message):
    """ Print message as a result of action. """
    elt = root.findmeld('message_mid')
    if message is not None:
        elt.attrib['class'] = gravity
        elt.content(message)
    else:
        elt.attrib['class'] = 'empty'
        elt.content('')


def info_message(msg, address=None):
    """ Define an information message. """
    return Info, msg + ' at {}'.format(ctime()) + (' on {}'.format(address) if address else '')


def warn_message(msg, address=None):
    """ Define a warning message. """
    return Warn, msg + ' at {}'.format(ctime()) + (' on {}'.format(address) if address else '')


def error_message(msg, address=None):
    """ Define an error message. """
    return Error, msg + ' at {}'.format(ctime()) + (' on {}'.format(address) if address else '')


def delayed_info(msg, address=None):
    """ Define a delayed information message. """

    def on_wait():
        return info_message(msg, address)

    on_wait.delay = 0.05
    return on_wait


def delayed_warn(msg, address=None):
    """ Define a delayed warning message. """

    def on_wait():
        return warn_message(msg, address)

    on_wait.delay = 0.05
    return on_wait


def delayed_error(msg, address=None):
    """ Define a delayed error message. """

    def on_wait():
        return error_message(msg, address)

    on_wait.delay = 0.05
    return on_wait


# common shade attribute
def apply_shade(elt, shaded):
    if shaded:
        elt.attrib['class'] = 'shaded'
    else:
        elt.attrib['class'] = 'brightened'

