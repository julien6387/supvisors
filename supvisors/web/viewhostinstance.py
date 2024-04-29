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

from supvisors.internal_com.mapper import SupvisorsInstanceId
from supvisors.statscompiler import HostStatisticsInstance
from .viewcontext import *
from .viewimage import host_cpu_img, host_mem_img, host_io_img
from .viewinstance import SupvisorsInstanceView
from .webutils import *


class HostInstanceView(SupvisorsInstanceView):
    """ View renderer of the Host section of the Supvisors Instance page. """

    def __init__(self, context):
        """ Call of the superclass constructors. """
        SupvisorsInstanceView.__init__(self, context, HOST_INSTANCE_PAGE)

    def write_options(self, header_elt):
        """ Write configured periods for host statistics. """
        # in the current design, this page should not be accessed if the host statistics are not enabled
        # so no need to hide the period buttons in this case
        self.write_periods(header_elt)
        # always allow to go back to process view
        self.write_view_switch(header_elt)

    def write_view_switch(self, header_elt):
        """ Configure the statistics view buttons. """
        # update process button
        elt = header_elt.findmeld('process_view_a_mid')
        url = self.view_ctx.format_url('', PROC_INSTANCE_PAGE)
        elt.attributes(href=url)
        # update host button
        elt = header_elt.findmeld('host_view_a_mid')
        elt.content(f'{self.sup_ctx.local_status.supvisors_id.host_id}')

    def write_contents(self, contents_elt):
        """ Rendering of tables and figures for address statistics. """
        # get node characteristics
        info = self.view_ctx.get_node_characteristics()
        if info:
            self.write_node_characteristics(contents_elt, info)
        # get data from statistics module iaw period selection
        stats_instance: HostStatisticsInstance = self.view_ctx.get_instance_stats()
        if stats_instance:
            self.write_processor_statistics(contents_elt, stats_instance.cpu, stats_instance.times)
            self.write_memory_statistics(contents_elt, stats_instance.mem, stats_instance.times)
            self.write_network_statistics(contents_elt, stats_instance.io)
            # write CPU / Memory / Network plots
            try:
                self._write_cpu_image(stats_instance.cpu, stats_instance.times)
                self._write_mem_image(stats_instance.mem, stats_instance.times)
                self._write_io_image(stats_instance.io)
            except ImportError:
                # matplotlib not installed: remove figure elements
                for mid in ['cpuimage_fig_mid', 'memimage_fig_mid', 'ioimage_fig_mid']:
                    contents_elt.findmeld(mid).replace('')

    def write_node_characteristics(self, contents_elt, info):
        """ Rendering of the node characteristics. """
        # write Node section
        supvisors_id: SupvisorsInstanceId = self.sup_ctx.local_status.supvisors_id
        contents_elt.findmeld('node_td_mid').content(supvisors_id.host_id)
        contents_elt.findmeld('ipaddress_td_mid').content(supvisors_id.ip_address)
        # write Processor section
        contents_elt.findmeld('cpu_count_td_mid').content(f'{info.nb_core_physical} / {info.nb_core_logical}')
        contents_elt.findmeld('cpu_freq_td_mid').content(info.frequency)
        # write Memory section
        contents_elt.findmeld('physical_mem_td_mid').content(info.physical_memory)

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

    def _write_processor_single_statistics(self, tr_elt, single_cpu_stats, timeline):
        """ Rendering of the processor statistics for a single core. """
        self._write_common_detailed_statistics(tr_elt, single_cpu_stats, timeline,
                                               'cpuval_td_mid', 'cpuavg_td_mid',
                                               'cpuslope_td_mid', 'cpudev_td_mid')

    def write_processor_statistics(self, root, cpu_stats, timeline):
        """ Rendering of the processor statistics. """
        selected_cpu_id = self.view_ctx.parameters[CPU]
        iterator = root.findmeld('cpu_tr_mid').repeat(cpu_stats)
        shaded_tr = False
        for cpu_id, (tr_elt, single_cpu_stats) in enumerate(iterator):
            self._write_processor_single_title(tr_elt, selected_cpu_id, cpu_id)
            self._write_processor_single_statistics(tr_elt, single_cpu_stats, timeline)
            # set row background and invert
            apply_shade(tr_elt, shaded_tr)
            shaded_tr = not shaded_tr

    def write_memory_statistics(self, root, mem_stats, timeline):
        """ Rendering of the memory statistics. """
        self._write_common_detailed_statistics(root, mem_stats, timeline,
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

    def _write_network_single_statistics(self, tr_elt, single_io_stats, timeline, rowspan):
        """ Rendering of the statistics columns of the network statistics. """
        elt = tr_elt.findmeld('intfrxtx_td_mid')
        elt.content('Rx' if rowspan else 'Tx')
        # calculate and write statistics
        self._write_common_detailed_statistics(tr_elt, single_io_stats, timeline,
                                               'intfval_td_mid', 'intfavg_td_mid',
                                               'intfslope_td_mid', 'intfdev_td_mid')

    def write_network_statistics(self, root, io_stats):
        """ Rendering of the network statistics. """
        selected_intf = self.view_ctx.parameters[INTF]
        # display io statistics
        flatten_io_stats = []
        for intf, (uptimes, recv_stats, sent_stats) in io_stats.items():
            flatten_io_stats.append((intf, uptimes, recv_stats))
            flatten_io_stats.append((intf, uptimes, sent_stats))
        iterator = root.findmeld('intf_tr_mid').repeat(flatten_io_stats)
        rowspan, shaded_tr = True, False
        for tr_elt, (intf, uptimes, single_io_stats) in iterator:
            # set row background
            apply_shade(tr_elt, shaded_tr)
            # set interface cell rowspan
            self._write_network_single_title(tr_elt, selected_intf, intf, rowspan, shaded_tr)
            # set interface direction
            self._write_network_single_statistics(tr_elt, single_io_stats, uptimes, rowspan)
            if not rowspan:
                shaded_tr = not shaded_tr
            rowspan = not rowspan

    def _write_cpu_image(self, cpu_stats, timeline):
        """ Write CPU data into the dedicated buffer. """
        from supvisors.plot import StatisticsPlot
        # get CPU data
        cpu_id = self.view_ctx.parameters[CPU]
        cpu_id_string = self.view_ctx.cpu_id_to_string(cpu_id)
        cpu_data = cpu_stats[cpu_id]
        # build image from data
        plt = StatisticsPlot(self.logger)
        plt.add_timeline(timeline)
        plt.add_plot(f'CPU #{cpu_id_string}', '%', cpu_data)
        plt.export_image(host_cpu_img)

    def _write_mem_image(self, mem_stats, timeline):
        """ Write MEM data into the dedicated buffer. """
        # build image from data
        from supvisors.plot import StatisticsPlot
        plt = StatisticsPlot(self.logger)
        plt.add_timeline(timeline)
        plt.add_plot('MEM', '%', mem_stats)
        plt.export_image(host_mem_img)

    def _write_io_image(self, io_stats):
        """ Write MEM data into the dedicated buffer. """
        from supvisors.plot import StatisticsPlot
        # get IO data
        intf_name = self.view_ctx.parameters[INTF]
        if intf_name:
            timeline, recv_data, sent_data = io_stats[intf_name]
            # build image from data
            plt = StatisticsPlot(self.logger)
            plt.add_timeline(timeline)
            plt.add_plot(f'{intf_name} recv', 'kbits/s', recv_data)
            plt.add_plot(f'{intf_name} sent', 'kbits/s', sent_data)
            plt.export_image(host_io_img)
