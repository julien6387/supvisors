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

import time

from supervisor.compat import as_bytes, as_string
from supervisor.http import NOT_DONE_YET
from supervisor.states import SupervisorStates, RUNNING_STATES, STOPPED_STATES
from supervisor.web import MeldView

from .rpcinterface import API_VERSION
from .ttypes import SupvisorsInstanceStates, SupvisorsStates, Payload, ProcessHistoryStats
from .utils import get_stats
from .viewcontext import *
from .viewimage import process_cpu_img, process_mem_img
from .webutils import *


class ViewHandler(MeldView):
    """ Helper class to share rendering and behavior between handlers inheriting from MeldView. """

    def __init__(self, context):
        """ Initialization of the attributes. """
        MeldView.__init__(self, context)
        self.page_name = None
        self.current_time = time.time()
        # add Supvisors shortcuts
        self.supvisors = context.supervisord.supvisors
        self.logger = self.supvisors.logger
        # cannot store context as it is named, or it would crush the http context
        self.sup_ctx = self.supvisors.context
        # keep reference to the local node name
        self.local_identifier = self.supvisors.supvisors_mapper.local_identifier
        # init view_ctx (only for tests)
        self.view_ctx = None

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
        # clone the template and set navigation menu
        if self.supvisors.supervisor_data.supervisor_state == SupervisorStates.RUNNING:
            # manage parameters
            self.handle_parameters()
            # manage action
            message = self.handle_action()
            if message is NOT_DONE_YET:
                return NOT_DONE_YET
            # display result
            root = self.clone()
            # write navigation menu, page header and contents
            self.write_style(root)
            self.write_common(root)
            self.write_navigation(root)
            self.write_header(root)
            self.write_contents(root)
            # send message only at the end to get all URL parameters
            self.view_ctx.fire_message()
            return as_string(root.write_xhtmlstring())

    def handle_parameters(self):
        """ Retrieve the parameters selected on the web page. """
        self.view_ctx = ViewContext(self.context)
        self.logger.debug('New context: {}'. format(self.view_ctx.parameters))

    def write_style(self, root):
        """ Entry point for additional style instructions. """

    def write_common(self, root):
        """ Common rendering of the Supvisors pages. """
        # set auto-refresh status on page
        auto_refresh = self.view_ctx.parameters[AUTO]
        if not auto_refresh:
            root.findmeld('meta_mid').deparent()
        # configure Supvisors hyperlink
        elt = root.findmeld('supvisors_mid')
        url = self.view_ctx.format_url('', SUPVISORS_PAGE)
        elt.attributes(href=url)
        # blink main title in conciliation state
        if self.supvisors.fsm.state == SupvisorsStates.CONCILIATION and self.sup_ctx.conflicts():
            update_attrib(elt, 'class', 'blink')
        # set Supvisors version
        root.findmeld('version_mid').content(API_VERSION)
        # set current Supvisors instance identifier
        root.findmeld('identifier_mid').content(self.local_identifier)
        # configure refresh button
        elt = root.findmeld('refresh_a_mid')
        url = self.view_ctx.format_url('', self.page_name)
        elt.attributes(href=url)
        # configure auto-refresh button
        elt = root.findmeld('autorefresh_a_mid')
        url = self.view_ctx.format_url('', self.page_name, **{AUTO: not auto_refresh})
        elt.attributes(href=url)
        if auto_refresh:
            update_attrib(elt, 'class', 'active')
        # set bottom message
        print_message(root, self.view_ctx.get_gravity(), self.view_ctx.get_message(), self.current_time)

    def write_navigation(self, root):
        """ Write the navigation menu.
        Subclasses will define the write_nav parameters to be used. """
        raise NotImplementedError

    def write_nav(self, root, identifier=None, appli=None):
        """ Write the navigation menu. """
        self.write_nav_instances(root, identifier)
        self.write_nav_applications(root, appli)

    def write_nav_instances(self, root, identifier):
        """ Write the node part of the navigation menu. """
        mid_elt = root.findmeld('instance_li_mid')
        identifiers = list(self.supvisors.supvisors_mapper.instances.keys())
        for li_elt, item in mid_elt.repeat(identifiers):
            try:
                status = self.sup_ctx.instances[item]
            except KeyError:
                self.logger.debug(f'ViewHandler.write_nav_instances: failed to get instance status from {item}')
            else:
                # set element class
                update_attrib(li_elt, 'class', status.state.name)
                if item == identifier:
                    update_attrib(li_elt, 'class', 'active')
                # set hyperlink attributes
                elt = li_elt.findmeld('instance_a_mid')
                if status.state_modes.starting_jobs or status.state_modes.stopping_jobs:
                    update_attrib(elt, 'class', 'blink')
                if status.state == SupvisorsInstanceStates.RUNNING:
                    # go to web page located on the Supvisors instance so as to reuse Supervisor StatusView
                    url = self.view_ctx.format_url(item, PROC_INSTANCE_PAGE)
                    elt.attributes(href=url)
                    update_attrib(elt, 'class', 'on')
                else:
                    update_attrib(elt, 'class', 'off')
                # set content
                identifier = item
                if item == self.sup_ctx.master_identifier:
                    identifier = f'{MASTER_SYMBOL} {item}'
                elt.content(identifier)

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
            update_attrib(root.findmeld('appli_h_mid'), 'class', 'failure')

    def write_header(self, root):
        """ Write the header part of the page.
        Subclasses will define what's to be done. """
        raise NotImplementedError

    def write_periods(self, root):
        """ Write configured periods for statistics. """
        if self.supvisors.options.stats_enabled:
            # write the available periods
            mid_elt = root.findmeld('period_li_mid')
            for li_elt, item in mid_elt.repeat(self.supvisors.options.stats_periods):
                # print period button
                elt = li_elt.findmeld('period_a_mid')
                if item == self.view_ctx.parameters[PERIOD]:
                    update_attrib(elt, 'class', 'button off active')
                else:
                    url = self.view_ctx.format_url('', self.page_name, **{PERIOD: item})
                    elt.attributes(href=url)
                elt.content('{}s'.format(item))
        else:
            # hide the Statistics periods box
            root.findmeld('period_div_mid').replace('')

    def write_contents(self, root):
        """ Write the contents part of the page.
        Subclasses will define what's to be done. """
        raise NotImplementedError

    def write_common_process_cpu(self, tr_elt, info):
        """ Write the CPU part of the common process status.
        Statistics data comes from node. """
        if self.supvisors.options.stats_enabled:
            proc_stats = info['proc_stats']
            elt = tr_elt.findmeld('pcpu_a_mid')
            if proc_stats and len(proc_stats[0]) > 0:
                # print last CPU value of process
                cpuvalue = proc_stats[0][-1]
                if not self.supvisors.options.stats_irix_mode:
                    cpuvalue /= info['nb_cores']
                if info['namespec']:  # empty for an application info
                    update_attrib(elt, 'class', 'button on')
                    parameters = {PROCESS: info['namespec'], IDENTIFIER: info['identifier']}
                    if self.view_ctx.parameters[PROCESS] == info['namespec']:
                        update_attrib(elt, 'class', 'active')
                        parameters[PROCESS] = None
                    url = self.view_ctx.format_url('', self.page_name, **parameters)
                    elt.attributes(href=url)
                    elt.content(f'{cpuvalue:.2f}%')
                else:
                    # print data with no link and button format
                    elt.replace(f'{cpuvalue:.2f}%')
            else:
                # when no data, do not write link
                elt.replace('--')
        else:
            # remove cell
            tr_elt.findmeld('pcpu_td_mid').deparent()

    def write_common_process_mem(self, tr_elt, info: Payload) -> None:
        """ Write the MEM part of the common process status.
        Statistics data comes from node. """
        if self.supvisors.options.stats_enabled:
            proc_stats = info['proc_stats']
            elt = tr_elt.findmeld('pmem_a_mid')
            if proc_stats and len(proc_stats[1]) > 0:
                # print last MEM value of process
                memvalue = proc_stats[1][-1]
                if info['namespec']:  # empty for an application info
                    update_attrib(elt, 'class', 'button on')
                    parameters = {PROCESS: info['namespec'], IDENTIFIER: info['identifier']}
                    if self.view_ctx.parameters[PROCESS] == info['namespec']:
                        update_attrib(elt, 'class', 'active')
                        parameters[PROCESS] = None
                    url = self.view_ctx.format_url('', self.page_name, **parameters)
                    elt.attributes(href=url)
                    elt.content(f'{memvalue:.2f}%')
                else:
                    # print data with no link
                    elt.replace(f'{memvalue:.2f}%')
            else:
                # when no data, no not write link
                elt.replace('--')
        else:
            # remove cell
            tr_elt.findmeld('pmem_td_mid').deparent()

    def write_process_start_button(self, tr_elt, info):
        """ Write the configuration of the start button of a process.
        The action will be handled by the local supvisors. """
        self._write_process_button(tr_elt, 'start_a_mid', '', self.page_name, 'start', info['namespec'],
                                   info['statecode'], [] if info['disabled'] else STOPPED_STATES)

    def write_process_stop_button(self, tr_elt, info):
        """ Write the configuration of the stop button of a process.
        The action will be handled by the local supvisors. """
        self._write_process_button(tr_elt, 'stop_a_mid', '', self.page_name, 'stop', info['namespec'],
                                   info['statecode'], RUNNING_STATES)

    def write_process_restart_button(self, tr_elt, info):
        """ Write the configuration of the restart button of a process.
        The action will be handled by the local supvisors. """
        self._write_process_button(tr_elt, 'restart_a_mid', '', self.page_name, 'restart', info['namespec'],
                                   info['statecode'], [] if info['disabled'] else RUNNING_STATES)

    def write_process_clear_button(self, tr_elt, info):
        """ Write the configuration of the clear logs button of a process.
        This action must be sent to the relevant node. """
        self._write_process_button(tr_elt, 'clear_a_mid', info['identifier'], self.page_name,
                                   'clearlog', info['namespec'], '', '')

    def write_process_stdout_button(self, tr_elt, info):
        """ Write the configuration of the tail stdout button of a process.
        This action must be sent to the relevant node. """
        # no action requested. page name is enough
        self._write_process_button(tr_elt, 'tailout_a_mid', info['identifier'],
                                   STDOUT_PAGE % quote(info['namespec'] or ''),
                                   '', info['namespec'], '', '')

    def write_process_stderr_button(self, tr_elt, info):
        """ Write the configuration of the tail stderr button of a process.
        This action must be sent to the relevant node. """
        # no action requested. page name is enough
        self._write_process_button(tr_elt, 'tailerr_a_mid', info['identifier'],
                                   STDERR_PAGE % quote(info['namespec'] or ''),
                                   '', info['namespec'], '', '')

    def _write_process_button(self, tr_elt, elt_name, identifier, page, action, namespec, state, state_list):
        """ Write the configuration of a process button. """
        elt = tr_elt.findmeld(elt_name)
        if namespec:
            if state in state_list:
                update_attrib(elt, 'class', 'button on')
                url = self.view_ctx.format_url(identifier, page, **{ACTION: action, NAMESPEC: namespec})
                elt.attributes(href=url)
            else:
                update_attrib(elt, 'class', 'button off')
        else:
            # this corresponds to an application row: no action available
            elt.content('')

    def write_common_process_table(self, table_elt):
        """ Hide MEM+CPU head+foot cells if statistics disabled"""
        if not self.supvisors.options.stats_enabled:
            for mid in ['mem_head_th_mid', 'cpu_head_th_mid', 'mem_foot_th_mid', 'cpu_foot_th_mid', 'total_mid']:
                elt = table_elt.findmeld(mid)
                if elt is not None:
                    elt.deparent()

    def write_common_status(self, tr_elt, info: Payload) -> None:
        """ Write the common part of a process or application status into a table. """
        # print state
        elt = tr_elt.findmeld('state_td_mid')
        update_attrib(elt, 'class', info['gravity'])
        if info['has_crashed']:
            update_attrib(elt, 'class', 'crashed')
        if info['disabled']:
            update_attrib(elt, 'class', 'disabled')
        elt.content(info['statename'])
        # print description
        elt = tr_elt.findmeld('desc_td_mid')
        elt.content(info['description'])
        # print expected load
        elt = tr_elt.findmeld('load_td_mid')
        elt.content(f"{info['expected_load']}%")
        # get data from statistics module iaw period selection
        self.write_common_process_cpu(tr_elt, info)
        self.write_common_process_mem(tr_elt, info)

    def write_common_process_status(self, tr_elt, info: Payload) -> None:
        """ Write the common part of a process status into a table. """
        # print common status
        self.write_common_status(tr_elt, info)
        # print process name
        # add break character only to processes belonging to an application
        process_name = info['process_name']
        if 'single' not in info or not info['single']:
            process_name = '\u21B3 ' + process_name
        elt = tr_elt.findmeld('name_a_mid')
        elt.content(process_name)
        url = self.view_ctx.format_url(info['identifier'], TAIL_PAGE, **{PROCESS: info['namespec']})
        elt.attributes(href=url, target="_blank")
        # manage actions iaw state
        self.write_process_start_button(tr_elt, info)
        self.write_process_stop_button(tr_elt, info)
        self.write_process_restart_button(tr_elt, info)
        # manage log actions
        self.write_process_clear_button(tr_elt, info)
        self.write_process_stdout_button(tr_elt, info)
        self.write_process_stderr_button(tr_elt, info)

    def write_detailed_process_cpu(self, stats_elt, proc_stats: ProcessHistoryStats, nb_cores: int) -> bool:
        """ Write the CPU part of the detailed process status.

        :param stats_elt: the element from which to search for
        :param proc_stats: the process statistics
        :param nb_cores: the number of processor cores
        :return: True if process CPU statistics are valid
        """
        if proc_stats and len(proc_stats[0]) > 0:
            # calculate stats
            avg, rate, (slope, intercept), dev = get_stats(proc_stats[0])
            # print last CPU value of process
            elt = stats_elt.findmeld('pcpuval_td_mid')
            if rate is not None:
                self.set_slope_class(elt, rate)
            cpuvalue = proc_stats[0][-1]
            if not self.supvisors.options.stats_irix_mode:
                cpuvalue /= nb_cores
            elt.content(f'{cpuvalue:.2f}%')
            # set mean value
            elt = stats_elt.findmeld('pcpuavg_td_mid')
            elt.content(f'{avg:.2f}%')
            if slope is not None:
                # set slope value between last 2 values
                elt = stats_elt.findmeld('pcpuslope_td_mid')
                elt.content(f'{slope:.2f}')
            if dev is not None:
                # set standard deviation
                elt = stats_elt.findmeld('pcpudev_td_mid')
                elt.content(f'{dev:.2f}')
            return True

    def write_detailed_process_mem(self, stats_elt, proc_stats: ProcessHistoryStats) -> bool:
        """ Write the MEM part of the detailed process status.

        :param stats_elt: the element from which to search for
        :param proc_stats: the process statistics
        :return: True if process Memory statistics are valid
        """
        if proc_stats and len(proc_stats[1]) > 0:
            avg, rate, (a, b), dev = get_stats(proc_stats[1])
            # print last MEM value of process
            elt = stats_elt.findmeld('pmemval_td_mid')
            if rate is not None:
                self.set_slope_class(elt, rate)
            elt.content('{:.2f}%'.format(proc_stats[1][-1]))
            # set mean value
            elt = stats_elt.findmeld('pmemavg_td_mid')
            elt.content('{:.2f}%'.format(avg))
            if a is not None:
                # set slope value between last 2 values
                elt = stats_elt.findmeld('pmemslope_td_mid')
                elt.content('{:.2f}'.format(a))
            if dev is not None:
                # set standard deviation
                elt = stats_elt.findmeld('pmemdev_td_mid')
                elt.content('{:.2f}'.format(dev))
            return True

    def write_process_plots(self, proc_stats: ProcessHistoryStats, nb_cores: int) -> None:
        """ Write the CPU / Memory plots (only if matplotlib is installed) """
        try:
            from supvisors.plot import StatisticsPlot
            # build CPU image
            cpu_img = StatisticsPlot()
            cpu_values = proc_stats[0]
            if not self.supvisors.options.stats_irix_mode:
                cpu_values = [x / nb_cores for x in cpu_values]
            cpu_img.add_plot('CPU', '%', cpu_values)
            cpu_img.export_image(process_cpu_img)
            # build Memory image
            mem_img = StatisticsPlot()
            mem_img.add_plot('MEM', '%', proc_stats[1])
            mem_img.export_image(process_mem_img)
        except ImportError:
            # matplotlib not installed
            pass

    def write_process_statistics(self, root, info: Payload) -> None:
        """ Display detailed statistics about the selected process. """
        # update the statistics table
        stats_elt = root.findmeld('pstats_div_mid')
        # get data from statistics module iaw period selection
        namespec = info.get('namespec', None)
        if namespec:
            # set CPU/MEM statistics
            proc_stats = info['proc_stats']
            done_cpu = self.write_detailed_process_cpu(stats_elt, proc_stats, info['nb_cores'])
            done_mem = self.write_detailed_process_mem(stats_elt, proc_stats)
            if done_cpu or done_mem:
                # set titles
                elt = stats_elt.findmeld('process_h_mid')
                elt.content(namespec)
                elt = stats_elt.findmeld('instance_fig_mid')
                if elt is not None:
                    elt.content(info['identifier'])
                # write CPU / Memory plots
                self.write_process_plots(proc_stats, info['nb_cores'])
        else:
            # remove stats part if empty
            stats_elt.replace('')

    def handle_action(self):
        """ Handling of the actions requested from the Supvisors web pages. """
        # check if any action is requested
        action = self.view_ctx.get_action()
        if action:
            # trigger deferred action and wait
            namespec = self.view_ctx.parameters[NAMESPEC]
            if not self.callback:
                self.callback = self.make_callback(namespec, action)
            # immediate check
            message = self.callback()
            if message is NOT_DONE_YET:
                return NOT_DONE_YET
            # post to write message
            if message is not None:
                self.view_ctx.store_message = format_gravity_message(message)

    def make_callback(self, namespec: str, action: str):
        """ Triggers processing iaw action requested.
        Subclasses will define what's to be done. """
        raise NotImplementedError

    @staticmethod
    def set_slope_class(elt, value):
        """ Set attribute class iaw positive or negative slope. """
        if abs(value) < .005:
            update_attrib(elt, 'class', 'stable')
        elif value > 0:
            update_attrib(elt, 'class', 'increase')
        else:
            update_attrib(elt, 'class', 'decrease')
