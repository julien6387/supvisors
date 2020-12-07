#!/usr/bin/python
#-*- coding: utf-8 -*-

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

import urllib

from supervisor.options import make_namespec
from supervisor.web import StatusView
from supervisor.xmlrpc import RPCError

from supvisors.utils import simple_localtime, supvisors_shortcuts
from supvisors.viewcontext import *
from supvisors.viewhandler import ViewHandler
from supvisors.webutils import *


class ProcAddressView(StatusView):
    """ View renderer of the Process section of the Supvisors Address page.
    Inheritance is made from supervisor.web.StatusView to benefit from
    the action methods.
    Note that the inheritance of StatusView has been patched dynamically
    in supvisors.plugin.make_supvisors_rpcinterface so that StatusView
    inherits from ViewHandler instead of MeldView.
    """

    def __init__(self, context):
        """ Call of the superclass constructors. """
        StatusView.__init__(self, context)
        self.page_name = PROC_ADDRESS_PAGE

    def render(self):
        """ Catch render to force the use of ViewHandler's method. """
        return ViewHandler.render(self)

    def write_navigation(self, root):
        """ Rendering of the navigation menu with selection of the current
        address """
        self.write_nav(root, address=self.address)

    def write_header(self, root):
        """ Rendering of the header part of the Supvisors Address page """
        # set address name
        elt = root.findmeld('address_mid')
        if self.sup_ctx.master:
            elt.attrib['class'] = 'master'
        elt.content(self.address)
        # set address state
        status = self.sup_ctx.addresses[self.address]
        elt = root.findmeld('state_mid')
        elt.content(status.state_string())
        # set loading
        elt = root.findmeld('percent_mid')
        elt.content('{}%'.format(status.loading()))
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
        # configure host address button
        elt = root.findmeld('host_a_mid')
        url = self.view_ctx.format_url('', HOST_ADDRESS_PAGE)
        elt.attributes(href=url)
        # configure refresh button
        elt = root.findmeld('refresh_a_mid')
        url = self.view_ctx.format_url('', self.page_name,
                                       **{ACTION: 'refresh'})
        elt.attributes(href=url)
        # configure stop all button
        elt = root.findmeld('stopall_a_mid')
        url = self.view_ctx.format_url('', self.page_name,
                                       **{ACTION: 'stopall'})
        elt.attributes(href=url)

    def write_contents(self, root):
        """ Rendering of the contents part of the page. """
        self.write_process_table(root)
        self.write_process_statistics(root)

    def get_process_data(self):
        """ Collect sorted data on processes. """
        # use Supervisor to get local information on all processes
        rpc_intf = self.info_source.supervisor_rpc_interface
        try:
            all_info = rpc_intf.getAllProcessInfo()
        except RPCError, e:
            self.logger.warn('failed to get all process info from {}: {}'
                             .format(self.address, e.text))
        else:
            # extract what is useful to display
            data = []
            for info in all_info:
                namespec = make_namespec(info['group'], info['name'])
                status = self.view_ctx.get_process_status(namespec)
                loading = status.rules.expected_loading if status else '?'
                data.append({'application_name': info['group'],
                             'process_name': info['name'],
                             'namespec': namespec,
                             'statename': info['statename'],
                             'statecode': info['state'],
                             'desc': info['description'],
                             'loading': loading})
            # re-arrange data
            return self.sort_processes_by_config(data)

    def write_process_table(self, root):
        """ Rendering of the processes managed through Supervisor """
        data = self.get_process_data()
        if data:
            # loop on all processes
            iterator = root.findmeld('tr_mid').repeat(data)
            shaded_tr = False # used to invert background style
            for tr_elt, item in iterator:
                selected_tr = self.write_common_process_status(tr_elt, item)
                # print process name (tail allowed if STOPPED)
                namespec = item['namespec']
                process_name = item.get('processname', namespec)
                elt = tr_elt.findmeld('name_a_mid')
                url = self.view_ctx.format_url(self.address, TAIL_PAGE,
                                               **{PROCESS: namespec})
                elt.attributes(href=url)
                elt.content(process_name)
                # print description
                elt = tr_elt.findmeld('desc_td_mid')
                elt.content(item['desc'])
                # manage process log actions
                namespec = item['namespec']
                elt = tr_elt.findmeld('clear_a_mid')
                parameters = {ACTION: 'clearlog', PROCESS: namespec}
                url = self.view_ctx.format_url('', self.page_name,
                                               **parameters)
                elt.attributes(href=url)
                elt = tr_elt.findmeld('tail_a_mid')
                elt.attributes(href='logtail/%s' % urllib.quote(namespec),
                               target='_blank')
                # set line background and invert
                if selected_tr:
                    tr_elt.attrib['class'] = 'selected'
                elif shaded_tr:
                    tr_elt.attrib['class'] = 'shaded'
                shaded_tr = not shaded_tr
        else:
            table = root.findmeld('table_mid')
            table.replace('No programs to manage')

    def make_callback(self, namespec, action):
        """ Triggers processing iaw action requested """
        if action == 'restartsup':
            return self.restart_sup_action()
        if action == 'shutdownsup':
            return self.shutdown_sup_action()
        # TODO: context is lost
        return StatusView.make_callback(self, namespec, action)

    def restart_sup_action(self):
        """ Restart the local supervisor. """
        self.supvisors.zmq.pusher.send_restart(self.address)
        # cannot defer result as restart address is self address
        # message is sent but it will be likely not displayed
        return delayed_warn('Supervisor restart requested')

    def shutdown_sup_action(self):
        """ Shut down the local supervisor. """
        self.supvisors.zmq.pusher.send_shutdown(self.address)
        # cannot defer result if shutdown address is self address
        return delayed_warn('Supervisor shutdown requested')

