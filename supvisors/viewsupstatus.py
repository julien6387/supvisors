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

from supervisor.web import StatusView

from .utils import simple_localtime
from .viewcontext import *
from .viewhandler import ViewHandler
from .webutils import *


class SupvisorsAddressView(StatusView):
    """ Common methods for the view renderer of the Supvisors Address page.
    Inheritance is made from supervisor.web.StatusView to benefit from the action methods.
    Note that the inheritance of StatusView has been patched dynamically
    in supvisors.plugin.make_supvisors_rpcinterface so that StatusView
    inherits from ViewHandler instead of MeldView.
    """

    def __init__(self, context, page_name):
        """ Call of the superclass constructors. """
        StatusView.__init__(self, context)
        self.page_name = page_name

    def render(self):
        """ Catch render to force the use of ViewHandler's method. """
        return ViewHandler.render(self)

    # LEFT SIDE / NAVIGATION part
    def write_navigation(self, root):
        """ Rendering of the navigation menu with selection of the current address. """
        self.write_nav(root, node_name=self.local_node_name)

    # RIGHT SIDE / HEADER part
    def write_header(self, root):
        """ Rendering of the header part of the Supvisors Address page. """
        # set address name
        elt = root.findmeld('address_mid')
        if self.sup_ctx.is_master:
            elt.attrib['class'] = 'master'
        elt.content(self.local_node_name)
        # set address state
        status = self.sup_ctx.nodes[self.local_node_name]
        elt = root.findmeld('state_mid')
        elt.content(status.state.name)
        # set node load
        elt = root.findmeld('percent_mid')
        elt.content('{}%'.format(status.get_loading()))
        # set last tick date: remote_time and local_time should be identical
        # since self is running on the 'remote' address
        elt = root.findmeld('date_mid')
        elt.content(simple_localtime(status.remote_time))
        # write periods of statistics
        self.write_periods(root)
        # write actions related to address
        self.write_address_actions(root)

    def write_address_actions(self, root):
        """ Write actions related to the address. """
        # configure host address button / switch page
        elt = root.findmeld('view_a_mid')
        target = PROC_NODE_PAGE if self.page_name == HOST_NODE_PAGE else HOST_NODE_PAGE
        url = self.view_ctx.format_url('', target)
        elt.attributes(href=url)
        # configure stop all button
        elt = root.findmeld('stopall_a_mid')
        url = self.view_ctx.format_url('', self.page_name, **{ACTION: 'stopall'})
        elt.attributes(href=url)

    # ACTION part
    def make_callback(self, namespec, action):
        """ Triggers processing iaw action requested """
        if action == 'restartsup':
            return self.restart_sup_action()
        if action == 'shutdownsup':
            return self.shutdown_sup_action()
        return StatusView.make_callback(self, namespec, action)

    def restart_sup_action(self):
        """ Restart the local supervisor. """
        self.supvisors.zmq.pusher.send_restart(self.local_node_name)
        # cannot defer result as restart address is self address
        # message is sent but it will be likely not displayed
        return delayed_warn('Supervisor restart requested')

    def shutdown_sup_action(self):
        """ Shut down the local supervisor. """
        self.supvisors.zmq.pusher.send_shutdown(self.local_node_name)
        # cannot defer result if shutdown address is self address
        return delayed_warn('Supervisor shutdown requested')
