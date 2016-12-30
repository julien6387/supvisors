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

from supvisors.utils import get_stats, simple_localtime, supvisors_short_cuts
from supvisors.viewhandler import ViewHandler
from supvisors.viewimage import address_image_contents
from supvisors.webutils import *


# Supvisors address page
class AddressView(StatusView, ViewHandler):
    # Name of the HTML page
    page_name = 'address.html'

    def __init__(self, context):
        StatusView.__init__(self, context)
        self.supvisors = self.context.supervisord.supvisors
        supvisors_short_cuts(self, ['info_source', 'logger'])
        self.address = self.supvisors.address_mapper.local_address

    def render(self):
        """ Method called by Supervisor to handle the rendering of the Supvisors Address page """
        return self.write_page()

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
        self.write_statistics(root)

    def write_statistics(self, root):
        """ Rendering of the statistics part of the page """
        self.write_address_statistics(root)
        self.write_process_statistics(root)

    def get_address_stats(self):
        """ Get the statistics structure related to the local address and the period selected """
        return self.supvisors.statistician.data[self.address][ViewHandler.period_stats]

    def get_process_stats(self, namespec):
        """ Get the statistics structure related to the local address and the period selected """
        stats = self.get_address_stats()
        if namespec in stats.proc.keys():
            return stats.proc[namespec]

    def write_address_statistics(self, root):
        """ Rendering of tables and figures for address statistics """
        # position to stats element
        stats_elt = root.findmeld('stats_div_mid')
        # get data from statistics module iaw period selection
        stats_instance = self.get_address_stats()
        self.write_memory_statistics(stats_elt, stats_instance.mem)
        self.write_processor_statistics(stats_elt, stats_instance.cpu)
        self.write_network_statistics(stats_elt, stats_instance.io)
        # write CPU / Memory plot
        try:
            from supvisors.plot import StatisticsPlot
            img = StatisticsPlot()
            if AddressView.address_stats_type == 'acpu':
                img.addPlot('CPU #{}'.format(self.cpu_id_to_string(AddressView.cpu_id_stats)), '%', stats_instance.cpu[AddressView.cpu_id_stats])
            elif AddressView.address_stats_type == 'amem':
                img.addPlot('MEM', '%', stats_instance.mem)
            elif AddressView.address_stats_type == 'io':
                img.addPlot('{} recv'.format(AddressView.interface_stats), 'kbits/s', stats_instance.io[AddressView.interface_stats][0])
                img.addPlot('{} sent'.format(AddressView.interface_stats), 'kbits/s', stats_instance.io[AddressView.interface_stats][1])
            img.exportImage(address_image_contents)
        except ImportError:
            self.logger.warn("matplotlib module not found")
       # set title
        elt = root.findmeld('address_fig_mid')
        elt.content(self.address)

    def write_memory_statistics(self, stats_elt, mem_stats):
        """ Rendering of the memory statistics """
        if len(mem_stats) > 0:
            tr_elt = stats_elt.findmeld('mem_tr_mid')
            # inactive button if selected
            if AddressView.address_stats_type == 'amem':
                tr_elt.attrib['class'] = 'selected'
                elt = stats_elt.findmeld('mem_a_mid')
                elt.attributes(href='#')
                elt.attrib['class'] = 'button off active'
            # get additional statistics
            avg, rate, (a, b), dev = get_stats(mem_stats)
            # set last value
            elt = tr_elt.findmeld('memval_td_mid')
            if rate is not None:
                self.set_slope_class(elt, rate)
            elt.content('{:.2f}'.format(mem_stats[-1]))
            # set mean value
            elt = tr_elt.findmeld('memavg_td_mid')
            elt.content('{:.2f}'.format(avg))
            if a is not None:
            	# set slope of linear regression
            	elt = tr_elt.findmeld('memslope_td_mid')
            	elt.content('{:.2f}'.format(a))
            if dev is not None:
            	# set standard deviation
            	elt = tr_elt.findmeld('memdev_td_mid')
            	elt.content('{:.2f}'.format(dev))

    def write_processor_statistics(self, stats_elt, cpu_stats):
        """ Rendering of the processor statistics """
        iterator = stats_elt.findmeld('cpu_tr_mid').repeat(cpu_stats)
        shaded_tr = False
        for idx, (tr_element, single_cpu_stats) in enumerate(iterator):
            selected_tr = False
            # set CPU id
            elt = tr_element.findmeld('cpunum_a_mid')
            if AddressView.address_stats_type == 'acpu' and AddressView.cpu_id_stats == idx:
                selected_tr = True
                elt.attrib['class'] = 'button off active'
            else:
                elt.attributes(href='address.html?stats=acpu&amp;idx={}'.format(idx))
            elt.content('cpu#{}'.format(idx-1 if idx > 0 else 'all'))
            if len(single_cpu_stats) > 0:
                avg, rate, (a, b), dev = get_stats(single_cpu_stats)
                # set last value with instant slope
                elt = tr_element.findmeld('cpuval_td_mid')
                if rate is not None:
                    self.set_slope_class(elt, rate)
                elt.content('{:.2f}'.format(single_cpu_stats[-1]))
                # set mean value
                elt = tr_element.findmeld('cpuavg_td_mid')
                elt.content('{:.2f}'.format(avg))
                if a is not None:
                    # set slope of linear regression
                    elt = tr_element.findmeld('cpuslope_td_mid')
                    elt.content('{:.2f}'.format(a))
                if dev is not None:
                    # set standard deviation
                    elt = tr_element.findmeld('cpudev_td_mid')
                    elt.content('{:.2f}'.format(dev))
            if selected_tr:
                tr_element.attrib['class'] = 'selected'
            elif shaded_tr:
                tr_element.attrib['class'] = 'shaded'
            shaded_tr = not shaded_tr

    def write_network_statistics(self, stats_elt, io_stats):
        """ Rendering of the network statistics """
        flatten_io_stats = [(intf, lst) for intf, lsts in io_stats.items() for lst in lsts]
        iterator = stats_elt.findmeld('intf_tr_mid').repeat(flatten_io_stats)
        rowspan, shaded_tr = True, False
        for tr_element, (intf, single_io_stats) in iterator:
            selected_tr = False
            # set interface cell rowspan
            elt = tr_element.findmeld('intf_td_mid')
            if rowspan:
                elt.attrib['rowspan'] = "2"
                # set interface name
                elt = elt.findmeld('intf_a_mid')
                if AddressView.address_stats_type == 'io' and AddressView.interface_stats == intf:
                    selected_tr = True
                    elt.attrib['class'] = 'button off active'
                else:
                    elt.attributes(href='address.html?stats=io&amp;intf={}'.format(intf))
                elt.content(intf)
            else:
                if AddressView.address_stats_type == 'io' and AddressView.interface_stats == intf:
                    selected_tr = True
                elt.replace('')
            # set interface direction
            elt = tr_element.findmeld('intfrxtx_td_mid')
            elt.content('Rx' if rowspan else 'Tx')
            if len(single_io_stats) > 0:
                avg, rate, (a, b), dev = get_stats(single_io_stats)
                # set last value
                elt = tr_element.findmeld('intfval_td_mid')
                if rate is not None:
                    self.set_slope_class(elt, rate)
                elt.content('{:.2f}'.format(single_io_stats[-1]))
                # set mean value
                elt = tr_element.findmeld('intfavg_td_mid')
                elt.content('{:.2f}'.format(avg))
                if a is not None:
                    # set slope of linear regression
                    elt = tr_element.findmeld('intfslope_td_mid')
                    elt.content('{:.2f}'.format(a))
                if dev is not None:
                    # set standard deviation
                    elt = tr_element.findmeld('intfdev_td_mid')
                    elt.content('{:.2f}'.format(dev))
            if selected_tr:
                tr_element.attrib['class'] = 'selected'
            elif shaded_tr:
                tr_element.attrib['class'] = 'shaded'
            if not rowspan:
                shaded_tr = not shaded_tr
            rowspan = not rowspan

    def write_process_table(self, root):
        """ Rendering of the processes managed through Supervisor """
        # collect data on processes
        data = [ ]
        try:
            for info in self.info_source.supervisor_rpc_interface.getAllProcessInfo():
                data.append({'namespec': make_namespec(info['group'], info['name']), 'statename': info['statename'],
                    'state': info['state'], 'desc': info['description'] })
        except RPCError, e:
            self.logger.warn('failed to get all process info from {}: {}'.format(self.address, e.text))
        # print processes
        if data:
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
                elt.attributes(href='address.html?processname={}&amp;action=clearlog'.format(urllib.quote(namespec)))
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
        self.supvisors.pool.async_restart(self.address)
        # cannot defer result as restart address is self address
        # message is sent but it will be likely not displayed
        return delayed_warn('Supervisor restart requested')

    def shutdown_sup_action(self):
        """ Shut down the local supervisor. """
        self.supvisors.pool.async_shutdown(self.address)
        # cannot defer result if shutdown address is self address
        return delayed_warn('Supervisor shutdown requested')

