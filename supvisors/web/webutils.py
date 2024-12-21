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

from enum import Enum
from time import ctime
from typing import Any, Callable, Tuple

from supervisor.http import NOT_DONE_YET
from supervisor.xmlrpc import RPCError


# HTML page names
class SupvisorsPages:
    """ Supvisors HTML page names. """
    SUPVISORS_PAGE = 'index.html'
    CONCILIATION_PAGE = 'conciliation.html'
    HOST_INSTANCE_PAGE = 'host_instance.html'
    PROC_INSTANCE_PAGE = 'proc_instance.html'
    APPLICATION_PAGE = 'application.html'
    TAIL_PAGE = 'tail.html'
    MAIN_TAIL_PAGE = 'maintail.html'
    STDOUT_PAGE = 'logtail/%s'
    STDERR_PAGE = 'logtail/%s/stderr'
    MAIN_STDOUT_PAGE = 'mainlogtail'


class SupvisorsGravities(Enum):
    """ Gravity classes for messages.
    'erro' is used instead of 'error' in order to avoid HTTP error log traces.
    """
    INFO = 'info'
    WARNING = 'warn'
    ERROR = 'erro'


class SupvisorsSymbols:
    """ Supvisors Web UI symbols. """
    MASTER_SYMBOL = '\u272A'
    SUB_SYMBOL = '\u21B3'
    SHEX_SHRINK = '[\u2013]'
    SHEX_EXPAND = '[+]'


# entry types in a Process table
class ProcessRowTypes(Enum):
    """ Used to sort entries in a process table. """
    INSTANCE_PROCESS, SUPERVISOR_PROCESS, APPLICATION_PROCESS, APPLICATION = range(4)


def format_gravity_message(message):
    """ Add a gravity to a message if not present."""
    if not isinstance(message, tuple):
        # gravity is not set by Supervisor so let's deduce it
        if 'ERROR' in message:
            message = message.replace('ERROR: ', '')
            gravity = SupvisorsGravities.ERROR
        elif 'unexpected rpc fault' in message:
            gravity = SupvisorsGravities.WARNING
        else:
            gravity = SupvisorsGravities.INFO
        return gravity.value, message
    # in other cases, Supervisor message is suitable
    return message


def print_message(root: Any, gravity: str, message: str,
                  current_time: float, identifier: str):
    """ Print message as a result of action. """
    # print time and source
    root.findmeld('time_mid').content(ctime(current_time))
    root.findmeld('identifier_mid').content(identifier)
    # print message
    elt = root.findmeld('message_mid')
    if message is None:
        # always set the refresh time by default
        elt.attrib['class'] = 'empty'
        elt.content('')
    else:
        elt.attrib['class'] = gravity
        elt.content(message)


class WebMessage:
    """ Class defining a message to be displayed in the web page. """

    def __init__(self, message: str, gravity: SupvisorsGravities, identifier: str = ''):
        """ Initialization of the attributes. """
        self._message: str = message
        self.gravity: SupvisorsGravities = gravity
        self.identifier: str = identifier

    @property
    def message(self) -> str:
        """ Define a global message structure. """
        location = f' on {self.identifier}' if self.identifier else ''
        return f'{self._message} at {ctime()}{location}'

    @property
    def gravity_message(self) -> Tuple[str, str]:
        """ Define a global message structure. """
        return self.gravity.value, self.message

    @property
    def delayed_message(self) -> Callable:
        """ Return a callable that returns the message."""
        def on_wait():
            return self.gravity_message
        on_wait.delay = 0.05
        return on_wait


def generic_rpc(rpc_intf, rpc_name: str, args: tuple, success_msg: str) -> Callable:
    """ Generic wrapper for an XML-RPC in Supervisor.

    :param rpc_intf: the RPC interface
    :param rpc_name: the RPC name
    :param args: the arguments of the RPC
    :param success_msg: the message in case of success
    :return: a callable for deferred result
    """
    try:
        cb = getattr(rpc_intf, rpc_name)(*args)
    except RPCError as e:
        return WebMessage(f'{rpc_name}: {e.text}', SupvisorsGravities.ERROR).delayed_message
    # process the result if callable
    if callable(cb):
        def onwait():
            try:
                result = cb()
            except RPCError as exc:
                return WebMessage(f'{rpc_name}: {exc.text}', SupvisorsGravities.ERROR).gravity_message
            if result is NOT_DONE_YET:
                return NOT_DONE_YET
            return WebMessage(success_msg, SupvisorsGravities.INFO).gravity_message

        onwait.delay = 0.1
        return onwait
    # process the result if directly available
    return WebMessage(success_msg, SupvisorsGravities.INFO).delayed_message


def update_attrib(elt, attribute: str, value: str) -> None:
    """ Add a new item to the attribute of an element.

    :param elt: the element to update.
    :param attribute: the element attribute to update.
    :param value: the value to add.
    :return: None.
    """
    current_value = elt.attrib.get(attribute, '')
    # NOTE: test on the split string because 'on' is in 'button'
    if value not in current_value.split():
        elt.attrib[attribute] = f'{current_value} {value}'.strip()


def apply_shade(elt, shaded: bool) -> None:
    """ Apply shade on element.

    :param elt: the element to shade.
    :param shaded: the shade status.
    :return: None.
    """
    if shaded:
        update_attrib(elt, 'class', 'shaded')
    else:
        update_attrib(elt, 'class', 'brightened')
