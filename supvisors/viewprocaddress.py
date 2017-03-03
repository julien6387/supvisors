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

from supvisors.utils import simple_localtime, supvisors_short_cuts
from supvisors.viewhandler import ViewHandler
from supvisors.webutils import *


class ProcAddressView(StatusView, ViewHandler):
    """ View renderer of the Process section of the Supvisors Address page. """

    # Name of the HTML page
    page_name = 'procaddress.html'

    def __init__(self, context):
        """ Initialization of the attributes. """
        StatusView.__init__(self, context)
        self.supvisors = self.context.supervisord.supvisors
        supvisors_short_cuts(self, ['info_source', 'logger'])
        self.address = self.supvisors.address_mapper.local_address

    def render(self):
        """ Method called by Supervisor to handle the rendering of the Supvisors Address page. """
        # Force the call to the render method of ViewHandler
        return ViewHandler.render(self)

    def write_navigation(self, root):
        """ Rendering of the navigation menu with selection of the current address """
        self.write_nav(root, address=self.address)

    def write_header(self, root):
        """ Rendering of the header part of the Supvisors Address page """
        # set address name
        elt = root.findmeld('address_mid')
        if self.supvisors.context.master:
            elt.attrib['class'] = 'master'
        elt.content(self.address)
        # set address state
        status = self.supvisors.context.addresses[self.address]
        elt = root.findmeld('state_mid')
        elt.content(status.state_string())
        # set loading
        elt = root.findmeld('percent_mid')
        elt.content('{}%'.format(status.loading()))
        # set last tick date: remote_time and local_time should be identical since self is running on the 'remote' address
        elt = root.findmeld('date_mid')
        elt.content(simple_localtime(status.remote_time))
        # write periods of statistics
        self.write_periods(root)

    def write_contents(self, root):
        """ Rendering of the contents part of the page """
        self.write_process_table(root)
        self.write_process_statistics(root)

    def get_address_stats(self):
        """ Get the statistics structure related to the local address and the period selected """
        return (self.supvisors.statistician.nbcores[self.address],
            self.supvisors.statistician.data[self.address][ViewHandler.period_stats])

    def get_process_stats(self, namespec):
        """ Get the statistics structure related to the local address and the period selected """
        nbcores, address_stats = self.get_address_stats()
        return nbcores, address_stats.find_process_stats(namespec)

    def write_process_table(self, root):
        """ Rendering of the processes managed through Supervisor """
        # collect data on processes
        data = []
        try:
            for info in self.info_source.supervisor_rpc_interface.getAllProcessInfo():
                data.append({'application_name': info['group'], 'process_name': info['name'],
                        'namespec': make_namespec(info['group'], info['name']),
                        'statename': info['statename'], 'statecode': info['state'],
                        'desc': info['description']})
        except RPCError, e:
            self.logger.warn('failed to get all process info from {}: {}'.format(self.address, e.text))
        # print processes
        if data:
            # re-arrange data
            data = self.sort_processes_by_config(data)
            # loop on all processes
            iterator = root.findmeld('tr_mid').repeat(data)
            shaded_tr = False # used to invert background style
            for tr_elt, item in iterator:
                selected_tr = self.write_common_process_status(tr_elt, item)
                # print process name (tail allowed if STOPPED)
                namespec = item['namespec']
                process_name = item.get('processname', namespec)
                elt = tr_elt.findmeld('name_a_mid')
                elt.attributes(href='http://{}:{}/tail.html?processname={}'.format(self.address, self.server_port(), urllib.quote(namespec)))
                elt.content(process_name)
                # print description
                elt = tr_elt.findmeld('desc_td_mid')
                elt.content(item['desc'])
                # manage process log actions
                namespec = item['namespec']
                elt = tr_elt.findmeld('clear_a_mid')
                elt.attributes(href='{}?processname={}&amp;action=clearlog'.format(ProcAddressView.page_name, urllib.quote(namespec)))
                elt = tr_elt.findmeld('tail_a_mid')
                elt.attributes(href='logtail/{}'.format(urllib.quote(namespec)), target='_blank')
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

