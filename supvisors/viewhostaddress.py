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

from .utils import get_stats
from .viewcontext import *
from .viewimage import address_cpu_img, address_mem_img, address_io_img
from .viewsupstatus import SupvisorsAddressView
from .webutils import *


class HostAddressView(SupvisorsAddressView):
    """ View renderer of the Host section of the Supvisors Address page.
    Inheritance is made from supervisor.web.StatusView to benefit from the action methods.
    Note that the inheritance of StatusView has been patched dynamically in supvisors.plugin.make_supvisors_rpcinterface
    so that StatusView inherits from ViewHandler instead of MeldView.
    """

    def __init__(self, context):
        """ Call of the superclass constructors. """
        SupvisorsAddressView.__init__(self, context, HOST_NODE_PAGE)

    def write_contents(self, root):
        """ Rendering of tables and figures for address statistics. """
        # get data from statistics module iaw period selection
        stats_instance = self.view_ctx.get_node_stats()
        self.write_processor_statistics(root, stats_instance.cpu)
        self.write_memory_statistics(root, stats_instance.mem)
        self.write_network_statistics(root, stats_instance.io)
        # write CPU / Memory / Network plots
        try:
            self._write_cpu_image(stats_instance.cpu)
            self._write_mem_image(stats_instance.mem)
            self._write_io_image(stats_instance.io)
        except ImportError:
            # matplotlib not installed
            pass

    def _write_processor_single_title(self, tr_elt, selected_cpu_id, cpu_id):
        """ Rendering of the title of a single core. """
        elt = tr_elt.findmeld('cpunum_a_mid')
        if selected_cpu_id == cpu_id:
            elt.attrib['class'] = 'button off active'
        else:
            url = self.view_ctx.format_url('', self.page_name, **{CPU: cpu_id})
            elt.attributes(href=url)
        cpu_id_string = self.view_ctx.cpu_id_to_string(cpu_id)
        elt.content('cpu#%s' % cpu_id_string)

    def _write_processor_single_statistics(self, tr_elt, single_cpu_stats):
        """ Rendering of the processor statistics for a single core. """
        self._write_common_statistics(tr_elt, single_cpu_stats,
                                      'cpuval_td_mid', 'cpuavg_td_mid',
                                      'cpuslope_td_mid', 'cpudev_td_mid')

    def write_processor_statistics(self, root, cpu_stats):
        """ Rendering of the processor statistics. """
        selected_cpu_id = self.view_ctx.parameters[CPU]
        iterator = root.findmeld('cpu_tr_mid').repeat(cpu_stats)
        shaded_tr = False
        for cpu_id, (tr_elt, single_cpu_stats) in enumerate(iterator):
            self._write_processor_single_title(tr_elt, selected_cpu_id, cpu_id)
            self._write_processor_single_statistics(tr_elt, single_cpu_stats)
            # set row background and invert
            apply_shade(tr_elt, shaded_tr)
            shaded_tr = not shaded_tr

    def write_memory_statistics(self, root, mem_stats):
        """ Rendering of the memory statistics. """
        self._write_common_statistics(root, mem_stats,
                                      'memval_td_mid', 'memavg_td_mid',
                                      'memslope_td_mid', 'memdev_td_mid')

    def _write_network_single_title(self, tr_elt, selected_intf, intf, rowspan, shaded_tr):
        """ Rendering of the title column of the network statistics. """
        # set interface cell rowspan
        elt = tr_elt.findmeld('intf_td_mid')
        if rowspan:
            elt.attrib['rowspan'] = '2'
            # apply shade logic to td element too for background-image to work
            apply_shade(elt, shaded_tr)
            # set interface name on a/href elt
            elt = elt.findmeld('intf_a_mid')
            elt.content(intf)
            if selected_intf == intf:
                elt.attrib['class'] = 'button off active'
            else:
                url = self.view_ctx.format_url('', self.page_name, **{INTF: intf})
                elt.attributes(href=url)
        else:
            elt.replace('')

    def _write_network_single_statistics(self, tr_elt, single_io_stats, rowspan):
        """ Rendering of the statistics columns of the network statistics. """
        elt = tr_elt.findmeld('intfrxtx_td_mid')
        elt.content('Rx' if rowspan else 'Tx')
        # calculate and write statistics
        self._write_common_statistics(tr_elt, single_io_stats,
                                      'intfval_td_mid', 'intfavg_td_mid',
                                      'intfslope_td_mid', 'intfdev_td_mid')

    def write_network_statistics(self, root, io_stats):
        """ Rendering of the network statistics. """
        selected_intf = self.view_ctx.parameters[INTF]
        # display io statistics
        flatten_io_stats = [(intf, lst)
                            for intf, lsts in io_stats.items()
                            for lst in lsts]
        iterator = root.findmeld('intf_tr_mid').repeat(flatten_io_stats)
        rowspan, shaded_tr = True, False
        for tr_elt, (intf, single_io_stats) in iterator:
            # set row background
            apply_shade(tr_elt, shaded_tr)
            # set interface cell rowspan
            self._write_network_single_title(tr_elt, selected_intf, intf, rowspan, shaded_tr)
            # set interface direction
            self._write_network_single_statistics(tr_elt, single_io_stats, rowspan)
            if not rowspan:
                shaded_tr = not shaded_tr
            rowspan = not rowspan

    def _write_common_statistics(self, root, stats, val_mid, avg_mid, slope_mid, dev_mid):
        """ Rendering of the memory statistics. """
        if len(stats) > 0:
            # get additional statistics
            avg, rate, (a, b), dev = get_stats(stats)
            # set last value
            elt = root.findmeld(val_mid)
            if rate is not None:
                self.set_slope_class(elt, rate)
            elt.content('{:.2f}'.format(stats[-1]))
            # set mean value
            elt = root.findmeld(avg_mid)
            elt.content('{:.2f}'.format(avg))
            if a is not None:
                # set slope of linear regression
                elt = root.findmeld(slope_mid)
                elt.content('{:.2f}'.format(a))
            if dev is not None:
                # set standard deviation
                elt = root.findmeld(dev_mid)
                elt.content('{:.2f}'.format(dev))

    def _write_cpu_image(self, cpu_stats):
        """ Write CPU data into the dedicated buffer. """
        from supvisors.plot import StatisticsPlot
        # get CPU data
        cpu_id = self.view_ctx.parameters[CPU]
        cpu_id_string = self.view_ctx.cpu_id_to_string(cpu_id)
        cpu_data = cpu_stats[cpu_id]
        # build image from data
        plt = StatisticsPlot()
        plt.add_plot('CPU #{}'.format(cpu_id_string), '%', cpu_data)
        plt.export_image(address_cpu_img)

    @staticmethod
    def _write_mem_image(mem_stats):
        """ Write MEM data into the dedicated buffer. """
        # build image from data
        from supvisors.plot import StatisticsPlot
        plt = StatisticsPlot()
        plt.add_plot('MEM', '%', mem_stats)
        plt.export_image(address_mem_img)

    def _write_io_image(self, io_stats):
        """ Write MEM data into the dedicated buffer. """
        from supvisors.plot import StatisticsPlot
        # get IO data
        intf_name = self.view_ctx.parameters[INTF]
        if intf_name:
            recv_data = io_stats[intf_name][0]
            sent_data = io_stats[intf_name][1]
            # build image from data
            plt = StatisticsPlot()
            plt.add_plot('{} recv'.format(intf_name), 'kbits/s', recv_data)
            plt.add_plot('{} sent'.format(intf_name), 'kbits/s', sent_data)
            plt.export_image(address_io_img)
