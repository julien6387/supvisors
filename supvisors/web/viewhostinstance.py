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
from supvisors.statscompiler import HostStatisticsInstance, InterfaceHistoryStats
from .viewcontext import *
from .viewimage import host_cpu_img, host_mem_img, host_net_io_img, host_disk_io_img, host_disk_usage_img
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
        if stats_instance and stats_instance.times:
            self.write_processor_statistics(contents_elt, stats_instance.cpu, stats_instance.times)
            self.write_memory_statistics(contents_elt, stats_instance.mem, stats_instance.times)
            self.write_network_io_statistics(contents_elt, stats_instance.net_io)
            self.write_disk_statistics(contents_elt, stats_instance)
            # write CPU / Memory / Network plots
            try:
                self._write_cpu_image(stats_instance.cpu, stats_instance.times)
                self._write_mem_image(stats_instance.mem, stats_instance.times)
                # other statistics include their own timeline
                self._write_net_io_image(stats_instance.net_io)
                self._write_disk_image(stats_instance)
            except ImportError:
                # matplotlib not installed: remove figure elements
                for mid in ['cpu_image_fig_mid', 'mem_image_fig_mid', 'net_io_image_fig_mid',
                            'disk_io_image_fig_mid', 'disk_usage_image_fig_mid']:
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
        elt = tr_elt.findmeld('cpu_num_a_mid')
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
                                               'cpu_val_td_mid', 'cpu_avg_td_mid',
                                               'cpu_slope_td_mid', 'cpu_dev_td_mid')

    def write_processor_statistics(self, root, cpu_stats, timeline):
        """ Rendering of the processor statistics. """
        selected_cpu_id = self.view_ctx.cpu_id
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
                                               'mem_val_td_mid', 'mem_avg_td_mid',
                                               'mem_slope_td_mid', 'mem_dev_td_mid')

    def _write_network_io_single_title(self, tr_elt, selected_nic, nic, rowspan, shaded_tr):
        """ Rendering of the title column of the network statistics. """
        # set interface cell rowspan
        elt = tr_elt.findmeld('net_io_nic_td_mid')
        if rowspan:
            elt.attrib['rowspan'] = '2'
            # apply shade logic to td element too for background-image to work
            apply_shade(elt, shaded_tr)
            # set interface name on a/href elt
            elt = elt.findmeld('net_io_nic_a_mid')
            elt.content(nic)
            if selected_nic == nic:
                elt.attrib['class'] = 'button off active'
            else:
                url = self.view_ctx.format_url('', self.page_name, **{NIC: nic})
                elt.attributes(href=url)
        else:
            elt.replace('')

    def _write_network_io_single_statistics(self, tr_elt, single_io_stats, timeline, rowspan):
        """ Rendering of the statistics columns of the network statistics. """
        elt = tr_elt.findmeld('net_io_rxtx_td_mid')
        elt.content('Rx' if rowspan else 'Tx')
        # calculate and write statistics
        self._write_common_detailed_statistics(tr_elt, single_io_stats, timeline,
                                               'net_io_val_td_mid', 'net_io_avg_td_mid',
                                               'net_io_slope_td_mid', 'net_io_dev_td_mid')

    def write_network_io_statistics(self, root, io_stats):
        """ Rendering of the network IO statistics. """
        selected_nic = self.view_ctx.nic_name
        # display io statistics
        flatten_io_stats = []
        for nic, (uptimes, [recv_stats, sent_stats]) in io_stats.items():
            flatten_io_stats.append((nic, uptimes, recv_stats))
            flatten_io_stats.append((nic, uptimes, sent_stats))
        iterator = root.findmeld('net_io_tr_mid').repeat(flatten_io_stats)
        rowspan, shaded_tr = True, False
        for tr_elt, (nic, uptimes, single_io_stats) in iterator:
            # set row background
            apply_shade(tr_elt, shaded_tr)
            # set interface cell rowspan
            self._write_network_io_single_title(tr_elt, selected_nic, nic, rowspan, shaded_tr)
            # set interface direction
            self._write_network_io_single_statistics(tr_elt, single_io_stats, uptimes, rowspan)
            if not rowspan:
                shaded_tr = not shaded_tr
            rowspan = not rowspan

    def _write_disk_io_single_title(self, tr_elt, selected_device, device, rowspan, shaded_tr):
        """ Rendering of the title column of the disk IO statistics. """
        # set device cell rowspan
        elt = tr_elt.findmeld('disk_io_device_td_mid')
        if rowspan:
            elt.attrib['rowspan'] = '2'
            # apply shade logic to td element too for background-image to work
            apply_shade(elt, shaded_tr)
            # set device name on a/href elt
            elt = elt.findmeld('disk_io_device_a_mid')
            elt.content(device)
            if selected_device == device:
                elt.attrib['class'] = 'button off active'
            else:
                url = self.view_ctx.format_url('', self.page_name, **{DEVICE: device})
                elt.attributes(href=url)
        else:
            elt.replace('')

    def _write_disk_io_single_statistics(self, tr_elt, single_io_stats, timeline, rowspan):
        """ Rendering of the statistics columns of the disk IO statistics. """
        elt = tr_elt.findmeld('disk_io_rw_td_mid')
        elt.content('R' if rowspan else 'W')
        # calculate and write statistics
        self._write_common_detailed_statistics(tr_elt, single_io_stats, timeline,
                                               'disk_io_val_td_mid', 'disk_io_avg_td_mid',
                                               'disk_io_slope_td_mid', 'disk_io_dev_td_mid')

    def write_disk_io_statistics(self, contents_elt, io_stats):
        """ Rendering of the disk IO statistics. """
        selected_device = self.view_ctx.device
        # display io device statistics
        flatten_io_stats = []
        for device, (uptimes, [read_stats, write_stats]) in io_stats.items():
            flatten_io_stats.append((device, uptimes, read_stats))
            flatten_io_stats.append((device, uptimes, write_stats))
        iterator = contents_elt.findmeld('disk_io_tr_mid').repeat(flatten_io_stats)
        rowspan, shaded_tr = True, False
        for tr_elt, (device, uptimes, single_io_stats) in iterator:
            # set row background
            apply_shade(tr_elt, shaded_tr)
            # set device cell rowspan
            self._write_disk_io_single_title(tr_elt, selected_device, device, rowspan, shaded_tr)
            # set device direction
            self._write_disk_io_single_statistics(tr_elt, single_io_stats, uptimes, rowspan)
            if not rowspan:
                shaded_tr = not shaded_tr
            rowspan = not rowspan

    def _write_disk_usage_single_title(self, tr_elt, selected_partition, partition):
        """ Rendering of the title column of the network statistics. """
        # set partition name on a/href elt
        elt = tr_elt.findmeld('disk_usage_partition_a_mid')
        elt.content(partition)
        if selected_partition == partition:
            elt.attrib['class'] = 'button off active'
        else:
            url = self.view_ctx.format_url('', self.page_name, **{PARTITION: partition})
            elt.attributes(href=url)

    def _write_disk_usage_single_statistics(self, tr_elt, usage_stats, timeline):
        """ Rendering of the statistics columns of the disk usage statistics. """
        self._write_common_detailed_statistics(tr_elt, usage_stats, timeline,
                                               'disk_usage_val_td_mid', 'disk_usage_avg_td_mid',
                                               'disk_usage_slope_td_mid', 'disk_usage_dev_td_mid')

    def write_disk_usage_statistics(self, contents_elt, usage_stats: InterfaceHistoryStats):
        """ Rendering of the network statistics. """
        selected_partition = self.view_ctx.partition
        iterator = contents_elt.findmeld('disk_usage_tr_mid').repeat(usage_stats.items())
        shaded_tr = False
        for tr_elt, (partition, (uptimes, [single_usage_stats])) in iterator:
            self._write_disk_usage_single_title(tr_elt, selected_partition, partition)
            self._write_disk_usage_single_statistics(tr_elt, single_usage_stats, uptimes)
            # set row background and invert
            apply_shade(tr_elt, shaded_tr)
            shaded_tr = not shaded_tr

    def write_disk_statistics(self, contents_elt, stats_instance: HostStatisticsInstance):
        """ Rendering the relevant Disk statistics depending on the display choice. """
        if self.view_ctx.disk_stats == 'usage':
            # update Disk usage stats and hide Disk IO stats
            self.write_disk_usage_statistics(contents_elt, stats_instance.disk_usage)
            contents_elt.findmeld('disk_io_div_mid').replace('')
            # update the disk stats selector
            url = self.view_ctx.format_url('', self.page_name, **{DISK_STATS: 'io'})
            contents_elt.findmeld('disk_usage_view_mid').attributes(href=url)
        else:
            # update Disk IO stats and hide Disk usage stats
            self.write_disk_io_statistics(contents_elt, stats_instance.disk_io)
            contents_elt.findmeld('disk_usage_div_mid').replace('')
            # update the disk stats selector
            url = self.view_ctx.format_url('', self.page_name, **{DISK_STATS: 'usage'})
            contents_elt.findmeld('disk_io_view_mid').attributes(href=url)

    def _write_cpu_image(self, cpu_stats, timeline):
        """ Write CPU data into the dedicated buffer. """
        from supvisors.plot import StatisticsPlot
        # get CPU data
        cpu_id = self.view_ctx.cpu_id
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

    def _write_net_io_image(self, net_io_stats):
        """ Write Network IO data into the dedicated buffer. """
        from supvisors.plot import StatisticsPlot
        # get IO data
        nic_name = self.view_ctx.nic_name
        if nic_name:
            timeline, [recv_data, sent_data] = net_io_stats[nic_name]
            # build image from data
            plt = StatisticsPlot(self.logger)
            plt.add_timeline(timeline)
            plt.add_plot(f'{nic_name} received', 'kbits/s', recv_data)
            plt.add_plot(f'{nic_name} sent', 'kbits/s', sent_data)
            plt.export_image(host_net_io_img)

    def _write_disk_image(self, stats_instance: HostStatisticsInstance):
        """ Update the relevant Disk image depending on the display choice. """
        if self.view_ctx.disk_stats == 'usage':
            # update Disk usage image
            self._write_disk_usage_image(stats_instance.disk_usage)
        else:
            # update Disk IO image
            self._write_disk_io_image(stats_instance.disk_io)

    def _write_disk_io_image(self, disk_io_stats):
        """ Write Disk IO data into the dedicated buffer. """
        from supvisors.plot import StatisticsPlot
        # get IO data
        device_name = self.view_ctx.device
        if device_name:
            timeline, [read_data, write_data] = disk_io_stats[device_name]
            # build image from data
            plt = StatisticsPlot(self.logger)
            plt.add_timeline(timeline)
            plt.add_plot(f'{device_name} read', 'kbits/s', read_data)
            plt.add_plot(f'{device_name} written', 'kbits/s', write_data)
            plt.export_image(host_disk_io_img)

    def _write_disk_usage_image(self, usage_stats):
        """ Write Disk usage data into the dedicated buffer. """
        from supvisors.plot import StatisticsPlot
        # get usage data
        partition = self.view_ctx.partition
        if partition:
            timeline, [usage_stats] = usage_stats[partition]
            # build image from data
            plt = StatisticsPlot(self.logger)
            plt.add_timeline(timeline)
            plt.add_plot(f'{partition}', '%', usage_stats)
            plt.export_image(host_disk_usage_img)
