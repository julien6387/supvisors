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

from typing import Callable

from supervisor.xmlrpc import RPCError

from supvisors.ttypes import SupvisorsStates
from .viewcontext import *
from .viewhandler import ViewHandler
from .webutils import WebMessage, SupvisorsPages, SupvisorsGravities, update_attrib


class MainView(ViewHandler):
    """ Class ensuring the common rendering of the main pages (index and conciliation) with:

        - a navigation menu towards Supvisors instances contents and applications,
        - the state of Supvisors,
        - actions on Supvisors.
    """

    def __init__(self, context):
        """ Call of the superclass constructors. """
        ViewHandler.__init__(self, context)
        # global actions (no parameter)
        self.global_methods = {'sup_restart': self.sup_restart_action,
                               'sup_shutdown': self.sup_shutdown_action}

    def write_navigation(self, root) -> None:
        """ Rendering of the navigation menu. """
        self.write_nav(root, source=self.local_identifier)

    def write_status(self, header_elt) -> None:
        """ Rendering of the header part of the Supvisors main page. """
        # set Supvisors state & modes
        elt = header_elt.findmeld('state_a_mid')
        statename = self.state_modes.state.name
        if self.state_modes.state == SupvisorsStates.CONCILIATION:
            elt.attributes(href=SupvisorsPages.CONCILIATION_PAGE)
            # blinking state until full conciliation performed
            if self.sup_ctx.conflicting():
                statename += ' >>'
                update_attrib(elt, 'class', 'on blink')
            elt.content(statename)
        else:
            elt.replace(statename)
        # set Supvisors starting mode
        elt = header_elt.findmeld('starting_mid')
        if self.state_modes.starting_identifiers:
            update_attrib(elt, 'class', 'blink')
        else:
            elt.replace('')
        # set Supvisors starting mode
        elt = header_elt.findmeld('stopping_mid')
        if self.state_modes.stopping_identifiers:
            update_attrib(elt, 'class', 'blink')
        else:
            elt.replace('')
        # write the Master nick identifier
        master_instance = self.sup_ctx.master_instance
        identifier = master_instance.supvisors_id.nick_identifier if master_instance else 'none'
        header_elt.findmeld('master_name_mid').content(identifier)

    def write_actions(self, header_elt) -> None:
        """ Write actions related to Supvisors. """
        super().write_actions(header_elt)
        # configure restart button
        elt = header_elt.findmeld('restart_a_mid')
        url = self.view_ctx.format_url('', SupvisorsPages.SUPVISORS_PAGE, **{ACTION: 'sup_restart'})
        elt.attributes(href=url)
        # configure shutdown button
        elt = header_elt.findmeld('shutdown_a_mid')
        url = self.view_ctx.format_url('', SupvisorsPages.SUPVISORS_PAGE, **{ACTION: 'sup_shutdown'})
        elt.attributes(href=url)

    def make_callback(self, namespec: str, action: str):
        """ Triggers processing iaw action requested. """
        if action in self.global_methods:
            return self.global_methods[action]()

    def sup_restart_action(self) -> Callable:
        """ Restart all Supervisor instances. """
        try:
            self.supvisors.supervisor_data.supvisors_rpc_interface.restart()
        except RPCError as e:
            return WebMessage(f'restart: {e}', SupvisorsGravities.ERROR).delayed_message
        return WebMessage('Supvisors restart requested', SupvisorsGravities.WARNING).delayed_message

    def sup_shutdown_action(self) -> Callable:
        """ Stop all Supervisor instances. """
        try:
            self.supvisors.supervisor_data.supvisors_rpc_interface.shutdown()
        except RPCError as e:
            return WebMessage(f'shutdown: {e}', SupvisorsGravities.ERROR).delayed_message
        return WebMessage('Supvisors shutdown requested', SupvisorsGravities.WARNING).delayed_message
