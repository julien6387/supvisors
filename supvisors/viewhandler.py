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

from supervisor.http import NOT_DONE_YET
from supervisor.states import SupervisorStates, RUNNING_STATES, STOPPED_STATES

from supvisors.rpcinterface import API_VERSION
from supvisors.ttypes import AddressStates, SupvisorsStates
from supvisors.utils import get_stats, supvisors_shortcuts
from supvisors.viewcontext import *
from supvisors.viewimage import process_cpu_image, process_mem_image
from supvisors.webutils import *


class ViewHandler(object):
    """ Helper class to communalize rendering and behavior between handlers
    inheriting from MeldView.

    The use of some 'self' attributes may appear quite strange as they actually
    belong to MeldView inheritance.
    However it works because python interprets the attributes in the context
    of the instance inheriting from both MeldView and this class.
    """

    def __init__(self, context, page_name):
        """ Initialization of the attributes. """
        # store the page name
        self.page_name = page_name
        # add Supvisors shortcuts
        # WARN: not for Supvisors context as it is already used by MeldView
        self.supvisors = context.supervisord.supvisors
        supvisors_shortcuts(self, ['address_mapper', 'fsm', 'info_source',
                                   'logger', 'options', 'statistician'])
        # cannot store context as it is or it would crush the http context
        self.sup_ctx = self.supvisors.context
        # keep reference to the local address
        self.address = self.address_mapper.local_address
        # init view_ctx (only for tests)
        self.view_ctx = None

    def render(self):
        """ Method called by Supervisor to handle the rendering
        of the Supvisors pages. """
        # clone the template and set navigation menu
        if self.info_source.supervisor_state == SupervisorStates.RUNNING:
            # manage parameters
            self.handle_parameters()
            # manage action
            message = self.handle_action()
            if message is NOT_DONE_YET:
                return NOT_DONE_YET
            # display result
            root = self.clone()
            form = self.context.form
            print_message(root,
                          self.view_ctx.get_gravity(),
                          self.view_ctx.get_message())
            # blink main title in conciliation state
            if self.fsm.state == SupvisorsStates.CONCILIATION and \
                self.sup_ctx.conflicts():
                root.findmeld('supvisors_mid').attrib['class'] = 'blink'
            # set Supvisors version
            root.findmeld('version_mid').content(API_VERSION)
            # write navigation menu, page header and contents
            self.write_navigation(root)
            self.write_header(root)
            self.write_contents(root)
            return root.write_xhtmlstring()

    def handle_parameters(self):
        """ Retrieve the parameters selected on the web page. """
        self.view_ctx = ViewContext(self.context)

    def write_nav(self, root, address=None, appli=None):
        """ Write the navigation menu. """
        self.write_nav_addresses(root, address)
        self.write_nav_applications(root, appli)

    def write_nav_addresses(self, root, address):
        """ Write the address part of the navigation menu. """
        mid_elt = root.findmeld('address_li_mid')
        address_names = self.address_mapper.addresses
        for li_elt, item in mid_elt.repeat(address_names):
            try:
                status = self.sup_ctx.addresses[item]
            except KeyError:
                self.logger.debug('failed to get AddressStatus from {}'
                                  .format(item))
            else:
                # set element class
                li_elt.attrib['class'] = status.state_string() \
                    + (' active' if item == address else '')
                # set hyperlink attributes
                elt = li_elt.findmeld('address_a_mid')
                if status.state == AddressStates.RUNNING:
                    # go to web page located on address,
                    # so as to reuse Supervisor StatusView
                    url = self.view_ctx.format_url(item, PROC_ADDRESS_PAGE)
                    elt.attributes(href=url)
                    elt.attrib['class'] = 'on' \
                        + (' master'
                           if item == self.sup_ctx.master_address
                           else '')
                else:
                    elt.attrib['class'] = 'off'
                elt.content(item)

    def write_nav_applications(self, root, appli):
        """ Write the application part of the navigation menu. """
        mid_elt = root.findmeld('appli_li_mid')
        applications = self.sup_ctx.applications.values()
        for li_elt, item in mid_elt.repeat(applications):
            # set element class
            li_elt.attrib['class'] = item.state_string() \
                + (' active' if item.application_name == appli else '')
            # set hyperlink attributes
            elt = li_elt.findmeld('appli_a_mid')
            if self.fsm.state == SupvisorsStates.INITIALIZATION:
                elt.attrib['class'] = 'off'
            else:
                parameters = {APPLI: item.application_name}
                url = self.view_ctx.format_url('', APPLICATION_PAGE,
                                               **parameters)
                elt.attributes(href=url)
                elt.attrib['class'] = 'on'
            elt.content(item.application_name)

    def write_periods(self, root):
        """ Write configured periods for statistics. """
        mid_elt = root.findmeld('period_li_mid')
        periods = self.options.stats_periods
        for li_elt, item in mid_elt.repeat(periods):
            # print period button
            elt = li_elt.findmeld('period_a_mid')
            if item == self.view_ctx.parameters[PERIOD]:
                elt.attrib['class'] = "button off active"
            else:
                parameters = {PERIOD: item}
                url = self.view_ctx.format_url('', self.page_name,
                                               **parameters)
                elt.attributes(href=url)
            elt.content('{}s'.format(item))

    def write_common_process_status(self, tr_elt, item):
        """ Write the common part of a process status into a table. """
        selected_tr = False
        namespec = item['namespec']
        # print state
        elt = tr_elt.findmeld('state_td_mid')
        elt.attrib['class'] = item['statename']
        elt.content(item['statename'])
        # print expected loading
        status = self.view_ctx.get_process_status(namespec)
        if status:
            elt = tr_elt.findmeld('load_td_mid')
            elt.content('{}%'.format(status.rules.expected_loading))
        # get data from statistics module iaw period selection
        hide_cpu_link, hide_mem_link = (True, )*2
        proc_stats, nbcores = self.get_process_stats(namespec)
        if proc_stats:
            if len(proc_stats[0]) > 0:
                # print last CPU value of process
                elt = tr_elt.findmeld('pcpu_a_mid')
                cpuvalue = proc_stats[0][-1]
                if not self.supvisors.options.stats_irix_mode:
                    cpuvalue /= nbcores
                elt.content('{:.2f}%'.format(cpuvalue))
                if self.view_ctx.parameters[PROCESS] == namespec:
                    selected_tr = True
                    elt.attributes(href='#')
                    elt.attrib['class'] = 'button off active'
                else:
                    parameters = {PROCESS: namespec}
                    url = self.view_ctx.format_url('', self.page_name,
                                                   **parameters)
                    elt.attributes(href=url)
                    elt.attrib['class'] = 'button on'
                hide_cpu_link = False
            if len(proc_stats[1]) > 0:
                # print last MEM value of process
                elt = tr_elt.findmeld('pmem_a_mid')
                elt.content('{:.2f}%'.format(proc_stats[1][-1]))
                if self.view_ctx.parameters[PROCESS] == namespec:
                    selected_tr = True
                    elt.attributes(href='#')
                    elt.attrib['class'] = 'button off active'
                else:
                    parameters = {PROCESS: namespec}
                    url = self.view_ctx.format_url('', self.page_name,
                                                   **parameters)
                    elt.attributes(href=url)
                    elt.attrib['class'] = 'button on'
                hide_mem_link = False
        # when no data, no not write link
        if hide_cpu_link:
            elt = tr_elt.findmeld('pcpu_a_mid')
            elt.replace('--')
        if hide_mem_link:
            elt = tr_elt.findmeld('pmem_a_mid')
            elt.replace('--')
        # manage actions iaw state
        process_state = item['statecode']
        # start button
        elt = tr_elt.findmeld('start_a_mid')
        if process_state in STOPPED_STATES:
            elt.attrib['class'] = 'button on'
            parameters = {ACTION: 'start', NAMESPEC: namespec}
            url = self.view_ctx.format_url('', self.page_name,
                                           **parameters)
            elt.attributes(href=url)
        else:
           elt.attrib['class'] = 'button off'
        # stop button
        elt = tr_elt.findmeld('stop_a_mid')
        if process_state in RUNNING_STATES:
            elt.attrib['class'] = 'button on'
            parameters = {ACTION: 'stop', NAMESPEC: namespec}
            url = self.view_ctx.format_url('', self.page_name,
                                           **parameters)
            elt.attributes(href=url)
        else:
           elt.attrib['class'] = 'button off'
        # restart button
        elt = tr_elt.findmeld('restart_a_mid')
        if process_state in RUNNING_STATES:
            elt.attrib['class'] = 'button on'
            parameters = {ACTION: 'restart', NAMESPEC: namespec}
            url = self.view_ctx.format_url('', self.page_name,
                                           **parameters)
            elt.attributes(href=url)
        else:
           elt.attrib['class'] = 'button off'
        return selected_tr

    def write_process_statistics(self, root):
        """ Display detailed statistics about the selected process. """
        stats_elt = root.findmeld('pstats_div_mid')
        # get data from statistics module iaw period selection
        namespec = self.view_ctx.parameters[PROCESS]
        if namespec:
            proc_stats, nbcores = self.get_process_stats(namespec)
            if proc_stats and (len(proc_stats[0]) > 0 or
                               len(proc_stats[1]) > 0):
                # set titles
                elt = stats_elt.findmeld('process_h_mid')
                elt.content(namespec)
                 # set CPU statistics
                if len(proc_stats[0]) > 0:
                    avg, rate, (a, b), dev = get_stats(proc_stats[0])
                    # print last CPU value of process
                    elt = stats_elt.findmeld('pcpuval_td_mid')
                    if rate is not None:
                        self.set_slope_class(elt, rate)
                    cpuvalue = proc_stats[0][-1]
                    if not self.options.stats_irix_mode:
                        cpuvalue /= nbcores
                    elt.content('{:.2f}%'.format(cpuvalue))
                    # set mean value
                    elt = stats_elt.findmeld('pcpuavg_td_mid')
                    elt.content('{:.2f}'.format(avg))
                    if a is not None:
                        # set slope value between last 2 values
                        elt = stats_elt.findmeld('pcpuslope_td_mid')
                        elt.content('{:.2f}'.format(a))
                    if dev is not None:
                        # set standard deviation
                        elt = stats_elt.findmeld('pcpudev_td_mid')
                        elt.content('{:.2f}'.format(dev))
                # set MEM statistics
                if len(proc_stats[1]) > 0:
                    avg, rate, (a, b), dev = get_stats(proc_stats[1])
                    # print last MEM value of process
                    elt = stats_elt.findmeld('pmemval_td_mid')
                    if rate is not None:
                        self.set_slope_class(elt, rate)
                    elt.content('{:.2f}%'.format(proc_stats[1][-1]))
                    # set mean value
                    elt = stats_elt.findmeld('pmemavg_td_mid')
                    elt.content('{:.2f}'.format(avg))
                    if a is not None:
                        # set slope value between last 2 values
                        elt = stats_elt.findmeld('pmemslope_td_mid')
                        elt.content('{:.2f}'.format(a))
                    if dev is not None:
                        # set standard deviation
                        elt = stats_elt.findmeld('pmemdev_td_mid')
                        elt.content('{:.2f}'.format(dev))
                # write CPU / Memory plots
                try:
                    from supvisors.plot import StatisticsPlot
                    # build CPU image
                    cpu_img = StatisticsPlot()
                    cpu_img.add_plot('CPU', '%', proc_stats[0])
                    cpu_img.export_image(process_cpu_image)
                    # build Memory image
                    mem_img = StatisticsPlot()
                    mem_img.add_plot('MEM', '%', proc_stats[1])
                    mem_img.export_image(process_mem_image)
                except ImportError:
                    self.logger.warn('matplotlib module not found')
            elif namespec:
                self.logger.warn('unselect Process Statistics for {}'
                                 .format(namespec))
                self.view_ctx.parameters[PROCESS] = ''
        # remove stats part if empty
        if not namespec:
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

    def get_process_stats(self, namespec):
        """ Get process statistics of process located on local address. """
        return self.view_ctx.get_process_stats(namespec)

    @staticmethod
    def set_slope_class(elt, value):
        """ Set attribute class iaw positive or negative slope. """
        if (abs(value) < .005):
            elt.attrib['class'] = 'stable'
        elif (value > 0):
            elt.attrib['class'] = 'increase'
        else:
            elt.attrib['class'] = 'decrease'

    def sort_processes_by_config(self, processes):
        """ This method sorts a process list using the internal configuration
        of supervisor.
        The aim is to present processes sorted the same way as they are
        in group configuration file. """
        sorted_processes = []
        if processes:
            # get the list of applications, sorted alphabetically
            application_list = sorted({process['application_name']
                                       for process in processes})
            for application_name in application_list:
                # get supervisor configuration for application
                group_config = self.info_source.get_group_config(application_name)
                # get process name ordering in this configuration
                ordering = [proc.name for proc in group_config.process_configs]
                # add processes known to supervisor, using the same ordering
                known_list = sorted([proc for proc in processes
                                     if proc['application_name'] == application_name and \
                                     proc['process_name'] in ordering],
                                    key=lambda x: ordering.index(x['process_name']))
                sorted_processes.extend(known_list)
                # add processes unknown to supervisor, using the alphabetical
                # ordering
                unknown_list = sorted([proc for proc in processes
                                       if proc['application_name'] == application_name and \
                                       proc['process_name'] not in ordering],
                                      key=lambda x: x['process_name'])
                sorted_processes.extend(unknown_list)
        return sorted_processes
