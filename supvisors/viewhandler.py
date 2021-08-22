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

from supervisor.compat import as_bytes, as_string
from supervisor.http import NOT_DONE_YET
from supervisor.states import SupervisorStates, RUNNING_STATES, STOPPED_STATES
from supervisor.web import MeldView

from .rpcinterface import API_VERSION
from .ttypes import AddressStates, SupvisorsStates, Payload
from .utils import get_stats
from .viewcontext import *
from .viewimage import process_cpu_img, process_mem_img
from .webutils import *


class ViewHandler(MeldView):
    """ Helper class to commonize rendering and behavior between handlers inheriting from MeldView. """

    def __init__(self, context):
        """ Initialization of the attributes. """
        MeldView.__init__(self, context)
        self.page_name = None
        # add Supvisors shortcuts
        # WARN: do not shortcut Supvisors context as it is already used by MeldView
        self.supvisors = context.supervisord.supvisors
        self.logger = self.supvisors.logger
        # cannot store context as it is named or it would crush the http context
        self.sup_ctx = self.supvisors.context
        # keep reference to the local node name
        self.local_node_name = self.supvisors.address_mapper.local_node_name
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
        if self.supvisors.info_source.supervisor_state == SupervisorStates.RUNNING:
            # manage parameters
            self.handle_parameters()
            # manage action
            message = self.handle_action()
            if message is NOT_DONE_YET:
                return NOT_DONE_YET
            # display result
            root = self.clone()
            # write navigation menu, page header and contents
            self.write_common(root)
            self.write_navigation(root)
            self.write_header(root)
            self.write_contents(root)
            return as_string(root.write_xhtmlstring())

    def handle_parameters(self):
        """ Retrieve the parameters selected on the web page. """
        self.view_ctx = ViewContext(self.context)
        self.logger.debug('New context: {}'. format(self.view_ctx.parameters))

    def write_common(self, root):
        """ Common rendering of the Supvisors pages. """
        # set auto-refresh status on page
        auto_refresh = self.view_ctx.parameters[AUTO]
        elt = root.findmeld('meta_mid')
        if auto_refresh:
            # consider to bind the statistics period to auto-refresh period
            pass
        else:
            elt.deparent()
        # configure Supvisors hyperlink
        elt = root.findmeld('supvisors_mid')
        url = self.view_ctx.format_url('', SUPVISORS_PAGE)
        elt.attributes(href=url)
        # blink main title in conciliation state
        if self.supvisors.fsm.state == SupvisorsStates.CONCILIATION and self.sup_ctx.conflicts():
            update_attrib(elt, 'class', 'blink')
        # set Supvisors version
        root.findmeld('version_mid').content(API_VERSION)
        # set hosting node name
        root.findmeld('node_mid').content(self.local_node_name)
        # configure refresh button
        elt = root.findmeld('refresh_a_mid')
        url = self.view_ctx.format_url('', self.page_name, **{ACTION: 'refresh'})
        elt.attributes(href=url)
        # configure auto-refresh button
        elt = root.findmeld('autorefresh_a_mid')
        url = self.view_ctx.format_url('', self.page_name, **{ACTION: 'refresh', AUTO: not auto_refresh})
        elt.attributes(href=url)
        if auto_refresh:
            update_attrib(elt, 'class', 'active')
        # set bottom message
        print_message(root, self.view_ctx.get_gravity(), self.view_ctx.get_message())

    def write_navigation(self, root):
        """ Write the navigation menu.
        Subclasses will define the write_nav parameters to be used. """

    def write_nav(self, root, node_name=None, appli=None):
        """ Write the navigation menu. """
        self.write_nav_nodes(root, node_name)
        self.write_nav_applications(root, appli)

    def write_nav_nodes(self, root, node_name):
        """ Write the node part of the navigation menu. """
        mid_elt = root.findmeld('address_li_mid')
        node_names = self.supvisors.address_mapper.node_names
        for li_elt, item in mid_elt.repeat(node_names):
            try:
                status = self.sup_ctx.nodes[item]
            except KeyError:
                self.logger.debug('failed to get AddressStatus from {}'.format(item))
            else:
                # set element class
                update_attrib(li_elt, 'class', status.state.name)
                if item == node_name:
                    update_attrib(li_elt, 'class', 'active')
                # set hyperlink attributes
                elt = li_elt.findmeld('address_a_mid')
                if status.state == AddressStates.RUNNING:
                    # go to web page located on node, so as to reuse Supervisor StatusView
                    url = self.view_ctx.format_url(item, PROC_NODE_PAGE)
                    elt.attributes(href=url)
                    update_attrib(elt, 'class', 'on')
                    if item == self.sup_ctx.master_node_name:
                        update_attrib(elt, 'class', 'master')
                else:
                    update_attrib(elt, 'class', 'off')
                elt.content(item)

    def write_nav_applications(self, root, appli):
        """ Write the application part of the navigation menu. """
        any_failure = False
        # write applications
        mid_elt = root.findmeld('appli_li_mid')
        applications = self.sup_ctx.get_managed_applications()
        # forced to list otherwise not easily testable
        for li_elt, item in mid_elt.repeat(list(applications)):
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
            if self.supvisors.fsm.state == SupvisorsStates.INITIALIZATION:
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

    def write_periods(self, root):
        """ Write configured periods for statistics. """
        mid_elt = root.findmeld('period_li_mid')
        periods = self.supvisors.options.stats_periods
        for li_elt, item in mid_elt.repeat(periods):
            # print period button
            elt = li_elt.findmeld('period_a_mid')
            if item == self.view_ctx.parameters[PERIOD]:
                update_attrib(elt, 'class', 'button off active')
            else:
                url = self.view_ctx.format_url('', self.page_name, **{PERIOD: item})
                elt.attributes(href=url)
            elt.content('{}s'.format(item))

    def write_contents(self, root):
        """ Write the contents part of the page.
        Subclasses will define what's to be done. """

    def write_common_process_cpu(self, tr_elt, info):
        """ Write the CPU part of the common process status.
        Statistics data comes from node. """
        proc_stats = info['proc_stats']
        elt = tr_elt.findmeld('pcpu_a_mid')
        if proc_stats and len(proc_stats[0]) > 0:
            # print last CPU value of process
            cpuvalue = proc_stats[0][-1]
            if not self.supvisors.options.stats_irix_mode:
                cpuvalue /= info['nb_cores']
            if info['namespec']:  # empty for an application info
                update_attrib(elt, 'class', 'button on')
                parameters = {PROCESS: info['namespec'], NODE: info['node_name']}
                if self.view_ctx.parameters[PROCESS] == info['namespec']:
                    update_attrib(elt, 'class', 'active')
                    parameters[PROCESS] = None
                url = self.view_ctx.format_url('', self.page_name, **parameters)
                elt.attributes(href=url)
                elt.content('{:.2f}%'.format(cpuvalue))
            else:
                # print data with no link
                elt.replace('{:.2f}%'.format(cpuvalue))
        else:
            # when no data, no not write link
            elt.replace('--')

    def write_common_process_mem(self, tr_elt, info):
        """ Write the MEM part of the common process status.
        Statistics data comes from node. """
        proc_stats = info['proc_stats']
        elt = tr_elt.findmeld('pmem_a_mid')
        if proc_stats and len(proc_stats[1]) > 0:
            # print last MEM value of process
            memvalue = proc_stats[1][-1]
            if info['namespec']:  # empty for an application info
                update_attrib(elt, 'class', 'button on')
                parameters = {PROCESS: info['namespec'], NODE: info['node_name']}
                if self.view_ctx.parameters[PROCESS] == info['namespec']:
                    update_attrib(elt, 'class', 'active')
                    parameters[PROCESS] = None
                url = self.view_ctx.format_url('', self.page_name, **parameters)
                elt.attributes(href=url)
                elt.content('{:.2f}%'.format(memvalue))
            else:
                # print data with no link
                elt.replace('{:.2f}%'.format(memvalue))
        else:
            # when no data, no not write link
            elt.replace('--')

    def write_process_start_button(self, tr_elt, info):
        """ Write the configuration of the start button of a process.
        The action will be handled by the local supvisors. """
        self._write_process_button(tr_elt, 'start_a_mid', '', self.page_name,
                                   'start', info['namespec'], info['statecode'], STOPPED_STATES)

    def write_process_stop_button(self, tr_elt, info):
        """ Write the configuration of the stop button of a process.
        The action will be handled by the local supvisors. """
        self._write_process_button(tr_elt, 'stop_a_mid', '', self.page_name,
                                   'stop', info['namespec'], info['statecode'], RUNNING_STATES)

    def write_process_restart_button(self, tr_elt, info):
        """ Write the configuration of the restart button of a process.
        The action will be handled by the local supvisors. """
        self._write_process_button(tr_elt, 'restart_a_mid', '', self.page_name,
                                   'restart', info['namespec'], info['statecode'], RUNNING_STATES)

    def write_process_clear_button(self, tr_elt, info):
        """ Write the configuration of the clear logs button of a process.
        This action must be sent to the relevant node. """
        self._write_process_button(tr_elt, 'clear_a_mid', info['node_name'], self.page_name,
                                   'clearlog', info['namespec'], '', '')

    def write_process_stdout_button(self, tr_elt, info):
        """ Write the configuration of the tail stdout button of a process.
        This action must be sent to the relevant node. """
        # no action requested. page name is enough
        self._write_process_button(tr_elt, 'tailout_a_mid', info['node_name'],
                                   STDOUT_PAGE % quote(info['namespec'] or ''),
                                   '', info['namespec'], '', '')

    def write_process_stderr_button(self, tr_elt, info):
        """ Write the configuration of the tail stderr button of a process.
        This action must be sent to the relevant node. """
        # no action requested. page name is enough
        self._write_process_button(tr_elt, 'tailerr_a_mid', info['node_name'],
                                   STDERR_PAGE % quote(info['namespec'] or ''),
                                   '', info['namespec'], '', '')

    def _write_process_button(self, tr_elt, elt_name, node_name, page, action, namespec, state, state_list):
        """ Write the configuration of a process button. """
        elt = tr_elt.findmeld(elt_name)
        if namespec:
            if state in state_list:
                update_attrib(elt, 'class', 'button on')
                url = self.view_ctx.format_url(node_name, page, **{ACTION: action, NAMESPEC: namespec})
                elt.attributes(href=url)
            else:
                update_attrib(elt, 'class', 'button off')
        else:
            # this corresponds to an application row: no action available
            elt.content('')

    def write_common_status(self, tr_elt, info: Payload) -> None:
        """ Write the common part of a process or application status into a table. """
        # print state
        elt = tr_elt.findmeld('state_td_mid')
        update_attrib(elt, 'class', info.get('gravity', info['statename']))
        elt.content(info['statename'])
        # print description
        elt = tr_elt.findmeld('desc_td_mid')
        elt.content(info['description'])
        # print expected load
        elt = tr_elt.findmeld('load_td_mid')
        elt.content('{}%'.format(info['expected_load']))
        # get data from statistics module iaw period selection
        self.write_common_process_cpu(tr_elt, info)
        self.write_common_process_mem(tr_elt, info)

    def write_common_process_status(self, tr_elt, info: Payload) -> None:
        """ Write the common part of a process status into a table. """
        # print common status
        self.write_common_status(tr_elt, info)
        # print process name
        elt = tr_elt.findmeld('name_a_mid')
        elt.content('\u21B3 {}'.format(info['process_name']))
        url = self.view_ctx.format_url(info['node_name'], TAIL_PAGE, **{PROCESS: info['namespec']})
        elt.attributes(href=url, target="_blank")
        # manage actions iaw state
        self.write_process_start_button(tr_elt, info)
        self.write_process_stop_button(tr_elt, info)
        self.write_process_restart_button(tr_elt, info)
        # manage log actions
        self.write_process_clear_button(tr_elt, info)
        self.write_process_stdout_button(tr_elt, info)
        self.write_process_stderr_button(tr_elt, info)

    def write_detailed_process_cpu(self, stats_elt, proc_stats, nb_cores):
        """ Write the CPU part of the detailed process status. """
        if proc_stats and len(proc_stats[0]) > 0:
            # calculate stats
            avg, rate, (a, b), dev = get_stats(proc_stats[0])
            # print last CPU value of process
            elt = stats_elt.findmeld('pcpuval_td_mid')
            if rate is not None:
                self.set_slope_class(elt, rate)
            cpuvalue = proc_stats[0][-1]
            if not self.supvisors.options.stats_irix_mode:
                cpuvalue /= nb_cores
            elt.content('{:.2f}%'.format(cpuvalue))
            # set mean value
            elt = stats_elt.findmeld('pcpuavg_td_mid')
            elt.content('{:.2f}%'.format(avg))
            if a is not None:
                # set slope value between last 2 values
                elt = stats_elt.findmeld('pcpuslope_td_mid')
                elt.content('{:.2f}'.format(a))
            if dev is not None:
                # set standard deviation
                elt = stats_elt.findmeld('pcpudev_td_mid')
                elt.content('{:.2f}'.format(dev))
            return True

    def write_detailed_process_mem(self, stats_elt, proc_stats):
        """ Write the MEM part of the detailed process status. """
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

    @staticmethod
    def write_process_plots(proc_stats):
        """ Write the CPU / Memory plots (only if matplotlib is installed) """
        try:
            from supvisors.plot import StatisticsPlot
            # build CPU image
            cpu_img = StatisticsPlot()
            cpu_img.add_plot('CPU', '%', proc_stats[0])
            cpu_img.export_image(process_cpu_img)
            # build Memory image
            mem_img = StatisticsPlot()
            mem_img.add_plot('MEM', '%', proc_stats[1])
            mem_img.export_image(process_mem_img)
        except ImportError:
            # matplotlib not installed
            pass

    def write_process_statistics(self, root, info):
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
                elt = stats_elt.findmeld('address_fig_mid')
                if elt is not None:
                    elt.content(info['node_name'])
                # write CPU / Memory plots
                self.write_process_plots(proc_stats)
        else:
            # remove stats part if empty
            stats_elt.replace('')

    def handle_action(self):
        """ Handling of the actions requested from the Supvisors web pages. """
        action = self.view_ctx.get_action()
        if action:
            # trigger deferred action and wait
            namespec = self.view_ctx.parameters[NAMESPEC]
            if not self.callback:
                self.callback = self.make_callback(namespec, action)
                return NOT_DONE_YET
            # intermediate check
            message = self.callback()
            if message is NOT_DONE_YET:
                return NOT_DONE_YET
            # post to write message
            if message is not None:
                self.view_ctx.message(format_gravity_message(message))

    def make_callback(self, namespec, action):
        """ Triggers processing iaw action requested.
        Subclasses will define what's to be done. """

    @staticmethod
    def set_slope_class(elt, value):
        """ Set attribute class iaw positive or negative slope. """
        if abs(value) < .005:
            update_attrib(elt, 'class', 'stable')
        elif value > 0:
            update_attrib(elt, 'class', 'increase')
        else:
            update_attrib(elt, 'class', 'decrease')
