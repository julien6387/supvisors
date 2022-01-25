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

from .instancestatus import SupvisorsInstanceStatus
from .viewcontext import *
from .viewhandler import ViewHandler
from .webutils import *


class SupvisorsInstanceView(StatusView):
    """ Common methods for the view renderer of the Supvisors Instance page.
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
        """ Catch render to force the use of ViewHandler's method instead of StatusView's method. """
        return ViewHandler.render(self)

    # LEFT SIDE / NAVIGATION part
    def write_navigation(self, root):
        """ Rendering of the navigation menu with selection of the current Supvisors instance. """
        self.write_nav(root, identifier=self.local_identifier)

    # RIGHT SIDE / HEADER part
    def write_header(self, root):
        """ Rendering of the header part of the Supvisors Instance page. """
        # set Supvisors instance identifier
        elt = root.findmeld('instance_mid')
        identifier = self.local_identifier
        if self.sup_ctx.is_master:
            identifier = f'{MASTER_SYMBOL} {identifier}'
        elt.content(identifier)
        # set Supvisors instance state
        status = self.sup_ctx.instances[self.local_identifier]
        elt = root.findmeld('state_mid')
        elt.content(status.state.name)
        # set Supvisors instance load
        elt = root.findmeld('percent_mid')
        elt.content(f'{status.get_load()}%')
        # write statistics parameters
        self.write_periods(root)
        # write actions related to the Supvisors instance
        self.write_instance_actions(root, status)

    def write_instance_actions(self, root, status: SupvisorsInstanceStatus):
        """ Write actions related to the Supvisors instance. """
        # configure switch page
        if self.supvisors.options.stats_enabled:
            # update process button
            if self.page_name == HOST_INSTANCE_PAGE:
                elt = root.findmeld('process_view_a_mid')
                url = self.view_ctx.format_url('', PROC_INSTANCE_PAGE)
                elt.attributes(href=url)
            # update host button
            elt = root.findmeld('host_view_a_mid')
            elt.content(f'{status.supvisors_id.host_name}')
            if self.page_name == PROC_INSTANCE_PAGE:
                url = self.view_ctx.format_url('', HOST_INSTANCE_PAGE)
                elt.attributes(href=url)
        else:
            # remove whole box if statistics disabled. Host node page is useless in this case
            root.findmeld('view_div_mid').replace('')
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
        self.supvisors.zmq.pusher.send_restart(self.local_identifier)
        return delayed_warn('Supervisor restart requested')

    def shutdown_sup_action(self):
        """ Shut down the local supervisor. """
        self.supvisors.zmq.pusher.send_shutdown(self.local_identifier)
        return delayed_warn('Supervisor shutdown requested')
