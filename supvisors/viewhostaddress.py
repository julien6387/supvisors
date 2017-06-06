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

from supervisor.web import StatusView

from supvisors.utils import get_stats, simple_localtime, supvisors_short_cuts
from supvisors.viewhandler import ViewHandler
from supvisors.viewimage import address_cpu_image, address_mem_image, address_io_image
from supvisors.webutils import *


class HostAddressView(StatusView, ViewHandler):
    """ View renderer of the Host section of the Supvisors Address page. """

    # Name of the HTML page
    page_name = 'hostaddress.html'

    # static attributes for statistics selection
    cpu_id_stats = 0
    interface_stats = ''

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

    def handle_parameters(self):
        """ Retrieve the parameters selected on the web page
        These parameters are static to the current class, so they are shared between all browsers connected on this server. """
        # call parent
        ViewHandler.handle_parameters(self)
        # get owned parameters
        form = self.context.form
       # update CPU statistics selection
        cpuid = form.get('idx')
        if cpuid:
            try:
                cpuid = int(cpuid)
            except ValueError:
                self.message(error_message('Cpu id is not an integer: {}'.format(cpuid)))
            else:
                address_stats = self.get_address_stats()
                if cpuid < len(address_stats.cpu):
                    if HostAddressView.cpu_id_stats != cpuid:
                        self.logger.info('select cpu#{} statistics for address'.format(self.cpu_id_to_string(cpuid)))
                        HostAddressView.cpu_id_stats = cpuid
                else:
                    self.message(error_message('Incorrect stats cpu id: {}'.format(cpuid)))
        # update Network statistics selection
        interface = form.get('intf')
        if interface:
            # check if interface requested exists
            address_stats = self.get_address_stats()
            if interface in address_stats.io.keys():
                if HostAddressView.interface_stats != interface:
                    self.logger.info('select Interface graph for {}'.format(interface))
                    HostAddressView.interface_stats = interface
            else:
                self.message(error_message('Incorrect stats interface: {}'.format(interface)))

    def write_navigation(self, root):
        """ Rendering of the navigation menu with selection of the current address. """
        self.write_nav(root, address=self.address)

    def write_header(self, root):
        """ Rendering of the header part of the Supvisors Address page. """
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

    def get_address_stats(self):
        """ Get the statistics structure related to the local address and the period selected. """
        return self.supvisors.statistician.data[self.address][ViewHandler.period_stats]

    def write_contents(self, root):
        """ Rendering of tables and figures for address statistics. """
        # get data from statistics module iaw period selection
        stats_instance = self.get_address_stats()
        self.write_memory_statistics(root, stats_instance.mem)
        self.write_processor_statistics(root, stats_instance.cpu)
        self.write_network_statistics(root, stats_instance.io)
        # write CPU / Memory / Network plots
        try:
            from supvisors.plot import StatisticsPlot
            # build CPU image
            cpu_img = StatisticsPlot()
            cpu_img.add_plot('CPU #{}'.format(self.cpu_id_to_string(HostAddressView.cpu_id_stats)), '%',
                stats_instance.cpu[HostAddressView.cpu_id_stats])
            cpu_img.export_image(address_cpu_image)
            # build Memory image
            mem_img = StatisticsPlot()
            mem_img.add_plot('MEM', '%', stats_instance.mem)
            mem_img.export_image(address_mem_image)
            # build Network image
            if HostAddressView.interface_stats:
                io_img = StatisticsPlot()
                io_img.add_plot('{} recv'.format(HostAddressView.interface_stats), 'kbits/s',
                    stats_instance.io[HostAddressView.interface_stats][0])
                io_img.add_plot('{} sent'.format(HostAddressView.interface_stats), 'kbits/s',
                    stats_instance.io[HostAddressView.interface_stats][1])
                io_img.export_image(address_io_image)
        except ImportError:
            self.logger.warn("matplotlib module not found")

    def write_memory_statistics(self, root, mem_stats):
        """ Rendering of the memory statistics. """
        if len(mem_stats) > 0:
            # get additional statistics
            avg, rate, (a, b), dev = get_stats(mem_stats)
            # set last value
            elt = root.findmeld('memval_td_mid')
            if rate is not None:
                self.set_slope_class(elt, rate)
            elt.content('{:.2f}'.format(mem_stats[-1]))
            # set mean value
            elt = root.findmeld('memavg_td_mid')
            elt.content('{:.2f}'.format(avg))
            if a is not None:
            	# set slope of linear regression
            	elt = root.findmeld('memslope_td_mid')
            	elt.content('{:.2f}'.format(a))
            if dev is not None:
            	# set standard deviation
            	elt = root.findmeld('memdev_td_mid')
            	elt.content('{:.2f}'.format(dev))

    def write_processor_statistics(self, root, cpu_stats):
        """ Rendering of the processor statistics. """
        iterator = root.findmeld('cpu_tr_mid').repeat(cpu_stats)
        shaded_tr = False
        for idx, (tr_element, single_cpu_stats) in enumerate(iterator):
            selected_tr = False
            # set CPU id
            elt = tr_element.findmeld('cpunum_a_mid')
            if HostAddressView.cpu_id_stats == idx:
                selected_tr = True
                elt.attrib['class'] = 'button off active'
            else:
                elt.attributes(href='{}?idx={}'.format(HostAddressView.page_name, idx))
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

    def write_network_statistics(self, root, io_stats):
        """ Rendering of the network statistics. """
        if not HostAddressView.interface_stats:
            # choose first interface name by default
            address_stats = self.get_address_stats()
            io_stats = address_stats.io
            HostAddressView.interface_stats = next(iter(io_stats.keys()))
        # display io statistics
        flatten_io_stats = [(intf, lst) for intf, lsts in io_stats.items() for lst in lsts]
        iterator = root.findmeld('intf_tr_mid').repeat(flatten_io_stats)
        rowspan, shaded_tr = True, False
        for tr_element, (intf, single_io_stats) in iterator:
            selected_tr = False
            # set interface cell rowspan
            elt = tr_element.findmeld('intf_td_mid')
            if rowspan:
                elt.attrib['rowspan'] = "2"
                # set interface name
                elt = elt.findmeld('intf_a_mid')
                if HostAddressView.interface_stats == intf:
                    selected_tr = True
                    elt.attrib['class'] = 'button off active'
                else:
                    elt.attributes(href='{}?intf={}'.format(HostAddressView.page_name, intf))
                elt.content(intf)
            else:
                if HostAddressView.interface_stats == intf:
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

    def make_callback(self, namespec, action):
        """ Triggers the action requested. """
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
