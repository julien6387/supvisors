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

import time
from typing import Type

from supervisor.compat import as_bytes, as_string
from supervisor.states import RUNNING_STATES, STOPPED_STATES
from supervisor.web import MeldView

from supvisors import __version__
from supvisors.instancestatus import SupvisorsInstanceStatus
from supvisors.internal_com.mapper import SupvisorsInstanceId
from supvisors.statscompiler import ProcStatisticsInstance
from supvisors.ttypes import SupvisorsStates, Payload, PayloadList
from supvisors.utils import get_stats, get_small_value
from .viewcontext import *
from .viewimage import process_cpu_img, process_mem_img, SoftwareIconImage
from .webutils import *


class ViewHandler(MeldView):
    """ Helper class to share rendering and behavior between handlers inheriting from MeldView. """

    def __init__(self, context):
        """ Initialization of the attributes. """
        MeldView.__init__(self, context)
        self.page_name = None
        self.current_mtime = time.monotonic()
        self.current_time = time.time()
        # add Supvisors shortcuts
        self.supvisors = context.supervisord.supvisors
        self.logger = self.supvisors.logger
        # cannot store context as it is named, or it would crush the http context
        self.sup_ctx = self.supvisors.context
        # even if there is no local collector, statistics can be available from other Supvisors instances
        # where a collector is available
        self.has_host_statistics = True
        self.has_process_statistics = True
        # init view_ctx (only for tests)
        self.view_ctx: Optional[ViewContext] = None

    @property
    def local_identifier(self):
        """ Return the identifier of the local Supvisors instance. """
        return self.supvisors.mapper.local_identifier

    @property
    def local_nick_identifier(self):
        """ Return the nick identifier of the local Supvisors instance. """
        return self.supvisors.mapper.local_nick_identifier

    def __call__(self):
        """ Anticipation of Supervisor#1273.
        Return response body as bytes instead of as string to prevent UnicodeDecodeError in the event
        of using binary references (images) in HTML. """
        response = MeldView.__call__(self)
        if response is NOT_DONE_YET:
            return NOT_DONE_YET
        response['body'] = as_bytes(response['body'])
        return response

    def render(self):
        """ Handle the rendering of the Supvisors pages. """
        # manage parameters
        self.handle_parameters()
        # manage action
        message = self.handle_action()
        if message is NOT_DONE_YET:
            return NOT_DONE_YET
        # clone the template and set navigation menu
        root = self.clone()
        # write navigation menu, page header and contents
        self.write_style(root)
        self.write_common(root)
        self.write_navigation(root)
        # write the header section
        header_elt = root.findmeld('header_mid')
        self.write_header(header_elt)
        # write the body section
        contents_elt = root.findmeld('contents_mid')
        self.write_contents(contents_elt)
        # send message only at the end to get all URL parameters
        self.view_ctx.fire_message()
        return as_string(root.write_xhtmlstring())

    def handle_parameters(self):
        """ Retrieve the parameters selected on the web page. """
        self.view_ctx = ViewContext(self.context)
        self.logger.debug(f'ViewHandler.handle_parameters: new context {self.view_ctx.parameters}')

    def write_style(self, root):
        """ Entry point for additional style instructions. """

    def write_common(self, root):
        """ Common rendering of the Supvisors pages. """
        # set auto-refresh status on page
        auto_refresh = self.view_ctx.auto_refresh
        if not auto_refresh:
            root.findmeld('meta_mid').deparent()
        # blink main title in conciliation state
        if self.supvisors.fsm.state == SupvisorsStates.CONCILIATION:
            elt = root.findmeld('supvisors_mid')
            update_attrib(elt, 'class', 'failure')
        # set Supvisors version
        root.findmeld('version_mid').content(__version__)
        # set bottom message
        footer_elt = root.findmeld('footer_mid')
        print_message(footer_elt, self.view_ctx.gravity, self.view_ctx.message,
                      self.current_time, self.local_nick_identifier)

    def write_navigation(self, root):
        """ Write the navigation menu.
        Subclasses will define the write_nav parameters to be used. """
        raise NotImplementedError

    def write_nav(self, root, identifier=None, appli=None):
        """ Write the navigation menu. """
        self.write_nav_instances(root, identifier)
        self.write_nav_applications(root, appli)

    def write_nav_instances(self, root, identifier: str) -> None:
        """ Write the node part of the navigation menu. """
        mid_elt = root.findmeld('instance_li_mid')
        identifiers = list(self.supvisors.mapper.instances.keys())
        any_failure = False
        # in discovery mode, other Supvisors instances arrive randomly in every Supvisors instance
        # so let's sort them by name
        if self.supvisors.options.discovery_mode:
            identifiers = [status.identifier
                           for status in sorted(self.supvisors.mapper.instances.values(),
                                                key=lambda x: x.nick_identifier)]
        for li_elt, item in mid_elt.repeat(identifiers):
            try:
                status: SupvisorsInstanceStatus = self.sup_ctx.instances[item]
            except KeyError:
                self.logger.debug(f'ViewHandler.write_nav_instances: failed to get instance status from {item}')
            else:
                failure = status.has_error()
                any_failure |= failure
                # set element class
                update_attrib(li_elt, 'class', status.state.name)
                if item == identifier:
                    update_attrib(li_elt, 'class', 'active')
                if failure:
                    update_attrib(li_elt, 'class', 'failure')
                # set hyperlink attributes
                elt = li_elt.findmeld('instance_a_mid')
                if status.state_modes.starting_jobs or status.state_modes.stopping_jobs:
                    update_attrib(elt, 'class', 'blink')
                if status.has_active_state():
                    # go to web page located on the Supvisors instance to reuse Supervisor StatusView
                    url = self.view_ctx.format_url(item, PROC_INSTANCE_PAGE)
                    elt.attributes(href=url)
                    update_attrib(elt, 'class', 'on')
                else:
                    update_attrib(elt, 'class', 'off')
                # set content (master and failure symbols need a positional update against the text)
                instance_elt = elt.findmeld('instance_sp_mid')
                instance_elt.content(status.supvisors_id.nick_identifier)
                if item == self.sup_ctx.master_identifier:
                    master_elt = elt.findmeld('master_sp_mid')
                    master_elt.content(MASTER_SYMBOL)
                    update_attrib(li_elt, 'class', 'master')
        # warn at title level if any application has a failure
        if any_failure:
            elt = root.findmeld('instance_h_mid')
            update_attrib(elt, 'class', 'failure')

    def write_nav_applications(self, root, appli):
        """ Write the application part of the navigation menu. """
        any_failure = False
        # write applications
        mid_elt = root.findmeld('appli_li_mid')
        applications = self.sup_ctx.get_managed_applications().values()
        working_apps = (self.supvisors.starter.get_application_job_names()
                        | self.supvisors.stopper.get_application_job_names())
        # forced to list otherwise not easily testable
        for li_elt, item in mid_elt.repeat(sorted(applications, key=lambda x: x.application_name)):
            failure = item.major_failure or item.minor_failure
            any_failure |= failure
            # set element class
            update_attrib(li_elt, 'class', item.state.name)
            if item.application_name == appli:
                update_attrib(li_elt, 'class', 'active')
            if failure:
                update_attrib(li_elt, 'class', 'failure')
            # set hyperlink attributes
            elt = li_elt.findmeld('appli_a_mid')
            if item.application_name in working_apps:
                update_attrib(elt, 'class', 'blink')
            if self.supvisors.fsm.state in [SupvisorsStates.OFF, SupvisorsStates.INITIALIZATION]:
                update_attrib(elt, 'class', 'off')
            else:
                # force default application starting strategy
                url = self.view_ctx.format_url('', APPLICATION_PAGE, **{APPLI: item.application_name,
                                                                        STRATEGY: item.rules.starting_strategy.name})
                elt.attributes(href=url)
                update_attrib(elt, 'class', 'on')
            elt.content(item.application_name)
        # warn at title level if any application has a failure
        if any_failure:
            elt = root.findmeld('appli_h_mid')
            update_attrib(elt, 'class', 'failure')

    def write_header(self, header_elt):
        """ Write the header common part of the page.
        Subclasses will define what's to be done at their level. """
        self.write_software(header_elt)
        self.write_status(header_elt)
        self.write_options(header_elt)
        self.write_actions(header_elt)

    def write_software(self, header_elt):
        """ Write the user software elements. """
        card_elt = header_elt.findmeld('software_card_mid')
        if not (self.supvisors.options.software_name or self.supvisors.options.software_icon):
            # remove the user software card if nothing set
            card_elt.replace('')
        else:
            if self.supvisors.options.software_name:
                # write software name
                card_elt.findmeld('software_name_mid').content(self.supvisors.options.software_name)
            # write user icon
            if self.supvisors.options.software_icon:
                SoftwareIconImage.set_path(self.supvisors.options.software_icon)
            else:
                card_elt.findmeld('software_icon_mid').replace('')

    def write_status(self, header_elt):
        """ Write the page instance status. """
        raise NotImplementedError

    def write_options(self, header_elt):
        """ Write configured periods for statistics.
        Does nothing by default. To be specialized in subclasses where statistics are available. """

    def write_periods(self, header_elt) -> None:
        """ Write configured periods for statistics.
        The update is conditioned to statistics options set in subclasses. """
        # write the available periods
        mid_elt = header_elt.findmeld('period_li_mid')
        for li_elt, item in mid_elt.repeat(self.supvisors.options.stats_periods):
            # print period button
            elt = li_elt.findmeld('period_a_mid')
            if item == self.view_ctx.period:
                update_attrib(li_elt, 'class', 'off active')
            else:
                update_attrib(li_elt, 'class', 'on')
                url = self.view_ctx.format_url('', self.page_name, **{PERIOD: item})
                elt.attributes(href=url)
            elt.content(f'{item}s')

    def write_actions(self, header_elt):
        """ Write the common action elements. """
        # configure refresh button
        elt = header_elt.findmeld('refresh_a_mid')
        url = self.view_ctx.format_url('', self.page_name)
        elt.attributes(href=url)
        # configure auto-refresh button
        auto_refresh = self.view_ctx.auto_refresh
        elt = header_elt.findmeld('autorefresh_a_mid')
        url = self.view_ctx.format_url('', self.page_name, **{AUTO: not auto_refresh})
        elt.attributes(href=url)
        if auto_refresh:
            update_attrib(elt, 'class', 'active')

    def write_contents(self, root):
        """ Write the contents part of the page.
        Subclasses will define what's to be done. """
        raise NotImplementedError

    def write_global_shex(self, table_elt, param: str, shex: str,
                          expand_shex: bytearray, shrink_shex: bytearray) -> None:
        """ Write global shrink / expand buttons.

        :param table_elt: the table element.
        :param param: the URL attribute for shex action.
        :param shex: the current shex from context form.
        :param expand_shex: the shex key to expand all items.
        :param shrink_shex: the shex key to shrink all items.
        :return: None.
        """
        # write expand button
        elt = table_elt.findmeld('expand_a_mid')
        if shex == expand_shex.hex():
            elt.replace('')
        else:
            elt.content(SHEX_EXPAND)
            url = self.view_ctx.format_url('', self.page_name, **{param: expand_shex.hex()})
            elt.attributes(href=url)
        # write shrink button
        elt = table_elt.findmeld('shrink_a_mid')
        if shex == shrink_shex.hex():
            elt.replace('')
        else:
            elt.content(SHEX_SHRINK)
            url = self.view_ctx.format_url('', self.page_name, **{param: shrink_shex.hex()})
            elt.attributes(href=url)

    def write_common_process_cpu(self, tr_elt, info):
        """ Write the CPU part of the common process status.
        Statistics data comes from the node. """
        if self.has_process_statistics:
            proc_stats: ProcStatisticsInstance = info['proc_stats']
            elt = tr_elt.findmeld('pcpu_a_mid')
            if proc_stats and len(proc_stats.cpu) > 0:
                # print last CPU value of process
                cpuvalue = proc_stats.cpu[-1]
                if not self.supvisors.options.stats_irix_mode:
                    cpuvalue /= info['nb_cores']
                if info['namespec']:  # empty for an application info
                    update_attrib(elt, 'class', 'button on')
                    parameters = {PROCESS: info['namespec'], IDENTIFIER: info['identifier']}
                    if (self.view_ctx.process_name == info['namespec']
                            and self.view_ctx.identifier == info['identifier']):
                        update_attrib(elt, 'class', 'active')
                        parameters[PROCESS] = None
                    url = self.view_ctx.format_url('', self.page_name, **parameters)
                    elt.attributes(href=url)
                    elt.content(get_small_value(cpuvalue))
                else:
                    # print data with no link and button format
                    elt.replace(get_small_value(cpuvalue))
            else:
                # when no data, do not write link
                elt.replace('--')
        else:
            # remove cell
            tr_elt.findmeld('pcpu_td_mid').deparent()

    def write_common_process_mem(self, tr_elt, info: Payload) -> None:
        """ Write the MEM part of the common process status.
        Statistics data comes from node. """
        if self.has_process_statistics:
            proc_stats: ProcStatisticsInstance = info['proc_stats']
            elt = tr_elt.findmeld('pmem_a_mid')
            if proc_stats and len(proc_stats.mem) > 0:
                # print last MEM value of process
                memvalue = proc_stats.mem[-1]
                if info['namespec']:  # empty for an application info
                    update_attrib(elt, 'class', 'button on')
                    parameters = {PROCESS: info['namespec'], IDENTIFIER: info['identifier']}
                    if (self.view_ctx.process_name == info['namespec']
                            and self.view_ctx.identifier == info['identifier']):
                        update_attrib(elt, 'class', 'active')
                        parameters[PROCESS] = None
                    url = self.view_ctx.format_url('', self.page_name, **parameters)
                    elt.attributes(href=url)
                    elt.content(get_small_value(memvalue))
                else:
                    # print data with no link
                    elt.replace(get_small_value(memvalue))
            else:
                # when no data, no not write link
                elt.replace('--')
        else:
            # remove cell
            tr_elt.findmeld('pmem_td_mid').deparent()

    def write_process_start_button(self, tr_elt, info):
        """ Write the configuration of the start button of a process.
        The action will be handled by the local Supvisors instance. """
        self._write_process_button(tr_elt, 'start_a_mid', '', self.page_name,
                                   'start', info['namespec'],
                                   info['startable'] and info['statecode'] in STOPPED_STATES)

    def write_process_stop_button(self, tr_elt, info):
        """ Write the configuration of the stop button of a process.
        The action will be handled by the local supvisors. """
        self._write_process_button(tr_elt, 'stop_a_mid', '', self.page_name,
                                   'stop', info['namespec'],
                                   info['stoppable'] and info['statecode'] in RUNNING_STATES)

    def write_process_restart_button(self, tr_elt, info):
        """ Write the configuration of the restart button of a process.
        The action will be handled by the local supvisors. """
        self._write_process_button(tr_elt, 'restart_a_mid', '', self.page_name,
                                   'restart', info['namespec'],
                                   info['startable'] and info['statecode'] in RUNNING_STATES)

    def write_process_clear_button(self, tr_elt, info):
        """ Write the configuration of the clear logs button of a process.
        This action must be sent to the relevant node. """
        namespec = info['namespec']
        self._write_process_button(tr_elt, 'clear_a_mid', info['identifier'], self.page_name,
                                   'clearlog', namespec, info['has_stdout'] or info['has_stderr'])

    def write_process_stdout_button(self, tr_elt, info):
        """ Write the configuration of the tail stdout button of a process.
        This action must be sent to the relevant node. """
        namespec = info['namespec']
        # no action requested. page name is enough
        self._write_process_button(tr_elt, 'tailout_a_mid', info['identifier'],
                                   STDOUT_PAGE % quote(namespec or ''), '', namespec, info['has_stdout'])

    def write_process_stderr_button(self, tr_elt, info):
        """ Write the configuration of the tail stderr button of a process.
        This action must be sent to the relevant node. """
        namespec = info['namespec']
        # no action requested. page name is enough
        self._write_process_button(tr_elt, 'tailerr_a_mid', info['identifier'],
                                   STDERR_PAGE % quote(namespec or ''), '', namespec, info['has_stderr'])

    def _write_process_button(self, tr_elt, elt_name: str, identifier: str, page: str, action: str, namespec: str,
                              active: bool = True):
        """ Write the configuration of a process button. """
        elt = tr_elt.findmeld(elt_name)
        if active:
            update_attrib(elt, 'class', 'button on')
            url = self.view_ctx.format_url(identifier, page, **{ACTION: action, NAMESPEC: namespec})
            elt.attributes(href=url)
        else:
            update_attrib(elt, 'class', 'button off')

    def write_common_process_table(self, table_elt):
        """ Hide MEM+CPU head+foot cells if statistics disabled"""
        if not self.has_process_statistics:
            for mid in ['mem_head_th_mid', 'cpu_head_th_mid',
                        'mem_foot_th_mid', 'cpu_foot_th_mid',
                        'mem_total_th_mid', 'cpu_total_th_mid']:
                elt = table_elt.findmeld(mid)
                if elt is not None:
                    elt.deparent()

    @staticmethod
    def write_common_state(tr_elt, info: Payload) -> None:
        """ Write the common part of a process state into a table. """
        # print state in cell
        td_elt = tr_elt.findmeld('state_td_mid')
        span_elt = td_elt.findmeld('state_span_mid')
        update_attrib(td_elt, 'class', info['gravity'])
        if info['has_crashed']:
            update_attrib(td_elt, 'class', 'crashed')
        if info['disabled']:
            update_attrib(td_elt, 'class', 'disabled')
        if len(info.get('running_identifiers', [])) > 1:
            update_attrib(span_elt, 'class', 'blink')
        span_elt.content(info['statename'])
        # print description
        tr_elt.findmeld('desc_td_mid').content(info['description'])

    def write_common_statistics(self, tr_elt, info: Payload) -> None:
        """ Write the common part of a process or application statistics into a table. """
        # print expected load
        tr_elt.findmeld('load_td_mid').content(f"{info['expected_load']}")
        # get data from statistics module iaw period selection
        self.write_common_process_cpu(tr_elt, info)
        self.write_common_process_mem(tr_elt, info)

    def write_common_process_status(self, tr_elt, info: Payload) -> None:
        """ Write the common part of a process status into a table. """
        # print common status
        self.write_common_state(tr_elt, info)
        self.write_common_statistics(tr_elt, info)
        # print process name
        # add break character only to processes belonging to an application
        process_name = info['process_name']
        if info.get('nb_items', 0) == 0:
            process_name = f'{SUB_SYMBOL} {process_name}'
        name_elt = tr_elt.findmeld('name_td_mid')
        # tail hyperlink depends on logfile availability
        namespec = info['namespec']
        # for application page, cannot state if logfile is there
        if info['has_stdout']:
            elt = name_elt.findmeld('name_a_mid')
            elt.content(process_name)
            url = self.view_ctx.format_url(info['identifier'], TAIL_PAGE,
                                           **{PROCESS: namespec, LIMIT: self.supvisors.options.tail_limit})
            elt.attributes(href=url, target="_blank")
        else:
            # overwrite a href entry
            name_elt.content(process_name)
        # manage actions iaw state
        self.write_process_start_button(tr_elt, info)
        self.write_process_stop_button(tr_elt, info)
        self.write_process_restart_button(tr_elt, info)
        # manage log actions
        self.write_process_clear_button(tr_elt, info)
        self.write_process_stdout_button(tr_elt, info)
        self.write_process_stderr_button(tr_elt, info)

    def write_detailed_process_cpu(self, stats_elt, proc_stats: Optional[ProcStatisticsInstance],
                                   nb_cores: int) -> bool:
        """ Write the CPU part of the detailed process status.

        :param stats_elt: the element from which to search for.
        :param proc_stats: the process statistics.
        :param nb_cores: the number of processor cores.
        :return: True if process CPU statistics are valid.
        """
        if proc_stats:
            # if SOLARIS mode configured, update the CPU data
            # this will be applicable to the CPU plot
            if not self.supvisors.options.stats_irix_mode:
                proc_stats.cpu = [x / nb_cores for x in proc_stats.cpu]
            self._write_common_detailed_statistics(stats_elt, proc_stats.cpu, proc_stats.times,
                                                   'pcpuval_td_mid', 'pcpuavg_td_mid',
                                                   'pcpuslope_td_mid', 'pcpudev_td_mid')
            return True

    def write_detailed_process_mem(self, stats_elt, proc_stats: Optional[ProcStatisticsInstance]) -> bool:
        """ Write the MEM part of the detailed process status.

        :param stats_elt: the element from which to search for.
        :param proc_stats: the process statistics.
        :return: True if process Memory statistics are valid.
        """
        if proc_stats:
            self._write_common_detailed_statistics(stats_elt, proc_stats.mem, proc_stats.times,
                                                   'pmemval_td_mid', 'pmemavg_td_mid',
                                                   'pmemslope_td_mid', 'pmemdev_td_mid')
            return True

    def _write_common_detailed_statistics(self, ref_elt, stats, timeline, val_mid, avg_mid, slope_mid, dev_mid):
        """ Common rendering of statistics. """
        if len(stats) > 0:
            # get additional statistics
            avg, rate, (slope, _), dev = get_stats(timeline, stats)
            # set last value
            elt = ref_elt.findmeld(val_mid)
            if rate is not None and not math.isinf(rate):
                self.set_slope_class(elt, rate)
            elt.content(get_small_value(stats[-1]))
            # set mean value
            ref_elt.findmeld(avg_mid).content(get_small_value(avg))
            # adapt slope value iaw period selected
            if slope is not None:
                value = slope * self.view_ctx.period
                ref_elt.findmeld(slope_mid).content(get_small_value(value))
            # set standard deviation
            if dev is not None:
                ref_elt.findmeld(dev_mid).content(get_small_value(dev))

    def write_process_plots(self, proc_stats: ProcStatisticsInstance) -> bool:
        """ Write the CPU / Memory plots (only if matplotlib is installed) """
        try:
            from supvisors.plot import StatisticsPlot
            # build CPU image (if SOLARIS mode configured, CPU values have already been adjusted)
            cpu_img = StatisticsPlot(self.logger)
            cpu_img.add_timeline(proc_stats.times)
            cpu_img.add_plot('CPU', '%', proc_stats.cpu)
            cpu_img.export_image(process_cpu_img)
            # build Memory image
            mem_img = StatisticsPlot(self.logger)
            mem_img.add_timeline(proc_stats.times)
            mem_img.add_plot('MEM', '%', proc_stats.mem)
            mem_img.export_image(process_mem_img)
            return True
        except ImportError:
            # matplotlib not installed
            return False

    def write_process_statistics(self, root, info: Payload) -> None:
        """ Display detailed statistics about the selected process. """
        # update the statistics table
        stats_elt = root.findmeld('pstats_div_mid')
        # get data from statistics module iaw period selection
        namespec = info.get('namespec', None)
        if namespec:
            # set CPU/MEM statistics
            proc_stats: ProcStatisticsInstance = info['proc_stats']
            done_cpu = self.write_detailed_process_cpu(stats_elt, proc_stats, info['nb_cores'])
            done_mem = self.write_detailed_process_mem(stats_elt, proc_stats)
            if done_cpu or done_mem:
                # set proces name
                stats_elt.findmeld('process_td_mid').content(namespec)
                # set node name and address
                supvisors_id: SupvisorsInstanceId = self.supvisors.mapper.instances[info['identifier']]
                stats_elt.findmeld('node_td_mid').content(supvisors_id.host_id)
                stats_elt.findmeld('ipaddress_td_mid').content(supvisors_id.ip_address)
                # write CPU / Memory plots
                if not self.write_process_plots(proc_stats):
                    # matplolib not installed: remove figure elements
                    for mid in ['cpuimage_fig_mid', 'memimage_fig_mid']:
                        stats_elt.findmeld(mid).replace('')
        else:
            # remove stats part if empty
            stats_elt.replace('')

    def handle_action(self) -> Optional[Type[NOT_DONE_YET]]:
        """ Handling of the actions requested from the Supvisors web pages.

        :return: NOT_DONE_YET if action is deferred, None otherwise
        """
        # check if any action is requested
        action = self.view_ctx.action
        if action:
            # trigger deferred action and wait
            namespec = self.view_ctx.namespec
            if not self.callback:
                self.callback = self.make_callback(namespec, action)
            # immediate check
            message = self.callback()
            if message is NOT_DONE_YET:
                return NOT_DONE_YET
            # post to write message
            if message is not None:
                self.view_ctx.store_message = format_gravity_message(message)

    def make_callback(self, namespec: str, action: str) -> Callable:
        """ Triggers processing iaw action requested.
        Subclasses will define what's to be done.

        :param namespec: the optional process namespec to which the action applies
        :param action: the action to perform
        :return: a callable for deferred result
        """
        raise NotImplementedError

    def multicall_rpc_action(self, args: PayloadList, success_msg: str) -> Callable:
        """ Generic wrapper for a System Supervisor RPC.

        :param args: the multiple RPC parameters
        :param success_msg: the message in case of success
        :return: a callable for deferred result
        """
        rpc_intf = self.supvisors.supervisor_data.system_rpc_interface
        return generic_rpc(rpc_intf, 'multicall', (args,), success_msg)

    def supervisor_rpc_action(self, rpc_name: str, args: tuple, success_msg: str) -> Callable:
        """ Generic wrapper for a Supervisor RPC.

        :param rpc_name: the RPC name in the Supervisor XML-RPC API
        :param args: the arguments of the RPC
        :param success_msg: the message in case of success
        :return: a callable for deferred result
        """
        rpc_intf = self.supvisors.supervisor_data.supervisor_rpc_interface
        return generic_rpc(rpc_intf, rpc_name, args, success_msg)

    def supvisors_rpc_action(self, rpc_name: str, args: tuple, success_msg: str) -> Callable:
        """ Generic wrapper for a Supvisors RPC.

        :param rpc_name: the RPC name in the Supvisors XML-RPC API
        :param args: the arguments of the RPC
        :param success_msg: the message in case of success
        :return: a callable for deferred result
        """
        rpc_intf = self.supvisors.supervisor_data.supvisors_rpc_interface
        return generic_rpc(rpc_intf, rpc_name, args, success_msg)

    @staticmethod
    def set_slope_class(elt, value: float) -> None:
        """ Set attribute class iaw positive or negative slope. """
        if abs(value) < .005:
            update_attrib(elt, 'class', 'stable')
        elif value > 0:
            update_attrib(elt, 'class', 'increase')
        else:
            update_attrib(elt, 'class', 'decrease')
