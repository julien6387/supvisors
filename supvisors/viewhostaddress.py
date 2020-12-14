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

from supervisor.web import StatusView

from supvisors.utils import (get_stats,
                             simple_localtime,
                             supvisors_shortcuts)
from supvisors.viewcontext import *
from supvisors.viewhandler import HAS_PLOT, ViewHandler
from supvisors.viewimage import (address_cpu_img,
                                 address_mem_img,
                                 address_io_img)
from supvisors.webutils import *


class HostAddressView(StatusView):
    """ View renderer of the Host section of the Supvisors Address page.
    Inheritance is made from supervisor.web.StatusView to benefit from
    the action methods.
    Note that the inheritance of StatusView has been patched dynamically
    in supvisors.plugin.make_supvisors_rpcinterface so that StatusView
    inherits from ViewHandler instead of MeldView.
    """

    def __init__(self, context):
        """ Call of the superclass constructors. """
        StatusView.__init__(self, context)
        self.page_name = HOST_ADDRESS_PAGE

    def render(self):
        """ Catch render to force the use of ViewHandler's method. """
        return ViewHandler.render(self)

    def write_navigation(self, root):
        """ Rendering of the navigation menu with selection of the current
        address. """
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
        elt = root.findmeld('proc_a_mid')
        url = self.view_ctx.format_url('', PROC_ADDRESS_PAGE)
        elt.attributes(href=url)
        # configure refresh button
        elt = root.findmeld('refresh_a_mid')
        url = self.view_ctx.format_url('', self.page_name, **{ACTION: 'refresh'})
        elt.attributes(href=url)
        # configure stop all button
        elt = root.findmeld('stopall_a_mid')
        url = self.view_ctx.format_url('', self.page_name, **{ACTION: 'stopall'})
        elt.attributes(href=url)

    def write_contents(self, root):
        """ Rendering of tables and figures for address statistics. """
        # get data from statistics module iaw period selection
        stats_instance = self.view_ctx.get_address_stats()
        self.write_processor_statistics(root, stats_instance.cpu)
        self.write_memory_statistics(root, stats_instance.mem)
        self.write_network_statistics(root, stats_instance.io)
        # write CPU / Memory / Network plots
        if HAS_PLOT:
            self._write_cpu_image(stats_instance.cpu)
            self._write_mem_image(stats_instance.mem)
            self._write_io_image(stats_instance.io)

    def write_processor_statistics(self, root, cpu_stats):
        """ Rendering of the processor statistics. """
        selected_cpu_id = self.view_ctx.parameters[CPU]
        iterator = root.findmeld('cpu_tr_mid').repeat(cpu_stats)
        shaded_tr = False
        for cpu_id, (tr_elt, single_cpu_stats) in enumerate(iterator):
            # set CPU id
            elt = tr_elt.findmeld('cpunum_a_mid')
            if selected_cpu_id == cpu_id:
                elt.attrib['class'] = 'button off active'
            else:
                url = self.view_ctx.format_url('', self.page_name, **{CPU: cpu_id})
                elt.attributes(href=url)
            cpu_id_string = self.view_ctx.cpu_id_to_string(cpu_id)
            elt.content('cpu#%s' % cpu_id_string)
            # set statistics
            if len(single_cpu_stats) > 0:
                avg, rate, (a, b), dev = get_stats(single_cpu_stats)
                # set last value with instant slope
                elt = tr_elt.findmeld('cpuval_td_mid')
                if rate is not None:
                    self.set_slope_class(elt, rate)
                elt.content('{:.2f}'.format(single_cpu_stats[-1]))
                # set mean value
                elt = tr_elt.findmeld('cpuavg_td_mid')
                elt.content('{:.2f}'.format(avg))
                if a is not None:
                    # set slope of linear regression
                    elt = tr_elt.findmeld('cpuslope_td_mid')
                    elt.content('{:.2f}'.format(a))
                if dev is not None:
                    # set standard deviation
                    elt = tr_elt.findmeld('cpudev_td_mid')
                    elt.content('{:.2f}'.format(dev))
            # set row background
            if shaded_tr:
                tr_elt.attrib['class'] = 'shaded'
            else:
                tr_elt.attrib['class'] = 'brightened'
            shaded_tr = not shaded_tr

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

    def write_network_statistics(self, root, io_stats):
        """ Rendering of the network statistics. """
        intf_name = self.view_ctx.parameters[INTF]
        # display io statistics
        flatten_io_stats = [(intf, lst)
                            for intf, lsts in io_stats.items()
                            for lst in lsts]
        iterator = root.findmeld('intf_tr_mid').repeat(flatten_io_stats)
        rowspan, shaded_tr = True, False
        for tr_elt, (intf, single_io_stats) in iterator:
            # set row background
            if shaded_tr:
                tr_elt.attrib['class'] = 'shaded'
            else:
                tr_elt.attrib['class'] = 'brightened'
            # set interface cell rowspan
            elt = tr_elt.findmeld('intf_td_mid')
            if rowspan:
                elt.attrib['rowspan'] = "2"
                # apply shaded / brightened to td element too for background-image to work
                if shaded_tr:
                    elt.attrib['class'] = 'shaded'
                else:
                    elt.attrib['class'] = 'brightened'
                # set interface name on a/href elt
                elt = elt.findmeld('intf_a_mid')
                elt.content(intf)
                if intf_name == intf:
                    elt.attrib['class'] = 'button off active'
                else:
                    url = self.view_ctx.format_url('', self.page_name, **{INTF: intf})
                    elt.attributes(href=url)
            else:
                elt.replace('')
            # set interface direction
            elt = tr_elt.findmeld('intfrxtx_td_mid')
            elt.content('Rx' if rowspan else 'Tx')
            if len(single_io_stats) > 0:
                avg, rate, (a, b), dev = get_stats(single_io_stats)
                # set last value
                elt = tr_elt.findmeld('intfval_td_mid')
                if rate is not None:
                    self.set_slope_class(elt, rate)
                elt.content('{:.2f}'.format(single_io_stats[-1]))
                # set mean value
                elt = tr_elt.findmeld('intfavg_td_mid')
                elt.content('{:.2f}'.format(avg))
                if a is not None:
                    # set slope of linear regression
                    elt = tr_elt.findmeld('intfslope_td_mid')
                    elt.content('{:.2f}'.format(a))
                if dev is not None:
                    # set standard deviation
                    elt = tr_elt.findmeld('intfdev_td_mid')
                    elt.content('{:.2f}'.format(dev))
            if not rowspan:
                shaded_tr = not shaded_tr
            rowspan = not rowspan

    def _write_cpu_image(self, cpu_stats):
        """ Write CPU data into the dedicated buffer. """
        # get CPU data
        cpu_id = self.view_ctx.parameters[CPU]
        cpu_id_string = self.view_ctx.cpu_id_to_string(cpu_id)
        cpu_data = cpu_stats[cpu_id]
        # build image from data
        from supvisors.plot import StatisticsPlot
        plt = StatisticsPlot()
        plt.add_plot('CPU #{}'.format(cpu_id_string), '%', cpu_data)
        plt.export_image(address_cpu_img)

    def _write_mem_image(self, mem_stats):
        """ Write MEM data into the dedicated buffer. """
        # build image from data
        from supvisors.plot import StatisticsPlot
        plt = StatisticsPlot()
        plt.add_plot('MEM', '%', mem_stats)
        plt.export_image(address_mem_img)

    def _write_io_image(self, io_stats):
        """ Write MEM data into the dedicated buffer. """
        # get IO data
        intf_name = self.view_ctx.parameters[INTF]
        if intf_name:
            recv_data = io_stats[intf_name][0]
            sent_data = io_stats[intf_name][1]
            # build image from data
            from supvisors.plot import StatisticsPlot
            plt = StatisticsPlot()
            plt.add_plot('{} recv'.format(intf_name), 'kbits/s', recv_data)
            plt.add_plot('{} sent'.format(intf_name), 'kbits/s', sent_data)
            plt.export_image(address_io_img)

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
