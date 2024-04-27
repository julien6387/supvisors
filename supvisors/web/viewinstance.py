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

from supvisors.instancestatus import SupvisorsInstanceStatus
from .viewcontext import *
from .viewhandler import ViewHandler
from .webutils import *


class SupvisorsInstanceView(ViewHandler, StatusView):
    """ Common methods for the view renderer of the Supvisors Instance page.

    Inheritance is made from supervisor.web.StatusView to benefit from the action methods.
    This might have been a diamond problem, but it does not really exit in Python.
    """

    def __init__(self, context, page_name):
        """ Call of the superclass constructors. """
        ViewHandler.__init__(self, context)
        StatusView.__init__(self, context)
        self.page_name = page_name
        # this class deals with local statistics so a local collector must be available
        self.has_host_statistics = self.supvisors.stats_collector and self.supvisors.options.host_stats_enabled
        self.has_process_statistics = self.supvisors.stats_collector and self.supvisors.options.process_stats_enabled

    def render(self):
        """ Catch render to force the use of ViewHandler's method instead of StatusView's method. """
        return ViewHandler.render(self)

    # LEFT SIDE / NAVIGATION part
    def write_navigation(self, root):
        """ Rendering of the navigation menu with selection of the current Supvisors instance. """
        self.write_nav(root, identifier=self.local_identifier)

    # RIGHT SIDE / HEADER part
    def write_status(self, header_elt):
        """ Rendering of the header part of the Supvisors Instance page. """
        # set Master symbol
        if self.sup_ctx.is_master:
            header_elt.findmeld('master_mid').content(MASTER_SYMBOL)
        # set Supvisors instance identifier
        header_elt.findmeld('instance_mid').content(self.local_nick_identifier)
        # set Supvisors instance state
        status: SupvisorsInstanceStatus = self.sup_ctx.local_status
        header_elt.findmeld('state_mid').content(status.state.name)
        # set Supvisors discovery mode
        if status.state_modes.discovery_mode:
            header_elt.findmeld('discovery_mid').content('discovery')
        # set Supvisors instance modes
        for mid, progress in [('starting_mid', status.state_modes.starting_jobs),
                              ('stopping_mid', status.state_modes.stopping_jobs)]:
            if progress:
                elt = header_elt.findmeld(mid)
                elt.content(mid.split('_')[0])
                update_attrib(elt, 'class', 'blink')

    def write_actions(self, header_elt):
        """ Write actions related to the Supvisors instance. """
        super().write_actions(header_elt)
        # configure stop all button
        elt = header_elt.findmeld('stopall_a_mid')
        url = self.view_ctx.format_url('', self.page_name, **{ACTION: 'stopall'})
        elt.attributes(href=url)
        # configure restart button
        elt = header_elt.findmeld('restartsup_a_mid')
        url = self.view_ctx.format_url('', self.page_name, **{ACTION: 'restartsup'})
        elt.attributes(href=url)
        # configure shutdown button
        elt = header_elt.findmeld('shutdownsup_a_mid')
        url = self.view_ctx.format_url('', self.page_name, **{ACTION: 'shutdownsup'})
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
        self.supvisors.rpc_handler.send_restart(self.local_identifier)
        return delayed_warn('Supervisor restart requested')

    def shutdown_sup_action(self):
        """ Shut down the local supervisor. """
        self.supvisors.rpc_handler.send_shutdown(self.local_identifier)
        return delayed_warn('Supervisor shutdown requested')
