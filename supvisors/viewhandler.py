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

from supervisor.http import NOT_DONE_YET
from supervisor.states import SupervisorStates, RUNNING_STATES, STOPPED_STATES

from supvisors.rpcinterface import API_VERSION
from supvisors.ttypes import AddressStates, SupvisorsStates
from supvisors.utils import get_stats
from supvisors.viewimage import process_cpu_image, process_mem_image
from supvisors.webutils import *


class ViewHandler(object):
    """ Helper class to commonize rendering and behaviour between handlers
    inheriting from MeldView.

    The use of some 'self' attributes may appear quite strange as they actually
    belong to MeldView inheritance.
    However it works because python interprets the attributes in the context
    of the instance inheriting from both MeldView and this class.

    The choice of the statistics is made through class attributes
    for the moment because it would take too much place on the URL.
    An change may be done later to use a short code that would be
    discriminating. """

    # static attributes for statistics selection
    period_stats = None
    namespec_stats = ''

    def render(self):
        """ Method called by Supervisor to handle the rendering
        of the Supvisors pages. """
        # clone the template and set navigation menu
        if self.supvisors.info_source.supervisor_state == SupervisorStates.RUNNING:
            # manage action
            message = self.handle_action()
            if message is NOT_DONE_YET:
                return NOT_DONE_YET
            # display result
            root = self.clone()
            form = self.context.form
            print_message(root, form.get('gravity'), form.get('message'))
            # manage parameters
            self.handle_parameters()
            # blink main title in conciliation state
            if self.supvisors.fsm.state == SupvisorsStates.CONCILIATION and \
                self.supvisors.context.conflicts():
                root.findmeld('supvisors_mid').attrib['class'] = 'blink'
            # set Supvisors version
            root.findmeld('version_mid').content(API_VERSION)
            # write navigation menu and Address header
            self.write_navigation(root)
            self.write_header(root)
            self.write_contents(root)
            return root.write_xhtmlstring()

    def write_nav(self, root, address=None, appli=None):
        """ Write the navigation menu. """
        server_port = self.server_port()
        # update navigation addresses
        iterator = root.findmeld('address_li_mid').repeat(
            self.supvisors.address_mapper.addresses)
        for li_elt, item in iterator:
            status = self.supvisors.context.addresses[item]
            # set element class
            li_elt.attrib['class'] = status.state_string() + (
                ' active' if item == address else '')
            # set hyperlink attributes
            elt = li_elt.findmeld('address_a_mid')
            if status.state == AddressStates.RUNNING:
                # go to web page located on address, so as to reuse Supervisor
                # StatusView
                elt.attributes(href='http://{}:{}/procaddress.html'.format(
                    item, server_port))
                elt.attrib['class'] = 'on' + \
                (' master' if item == self.supvisors.context.master_address
                 else '')
            else:
                elt.attrib['class'] = 'off'
            elt.content(item)
        # update navigation applications
        iterator = root.findmeld('appli_li_mid').repeat(
            self.supvisors.context.applications.keys())
        for li_elt, item in iterator:
            application = self.supvisors.context.applications[item]
            # set element class
            li_elt.attrib['class'] = application.state_string() + (
                ' active' if item == appli else '')
            # set hyperlink attributes
            elt = li_elt.findmeld('appli_a_mid')
            if self.supvisors.fsm.state == SupvisorsStates.INITIALIZATION:
                elt.attrib['class'] = 'off'
            else:
                elt.attributes(href='application.html?appli={}'.format(
                    urllib.quote(item)))
                elt.attrib['class'] = 'on'
            elt.content(item)

    def write_periods(self, root):
        """ Write configured periods for statistics. """
        # init period if necessary
        if ViewHandler.period_stats is None:
            ViewHandler.period_stats = next(iter(
                self.supvisors.options.stats_periods))
        # render periods
        iterator = root.findmeld('period_li_mid').repeat(
            self.supvisors.options.stats_periods)
        for li_elt, period in iterator:
            # print period button
            elt = li_elt.findmeld('period_a_mid')
            if period == ViewHandler.period_stats:
                elt.attrib['class'] = "button off active"
            else:
                elt.attributes(href='{}?{}period={}'
                               .format(self.page_name,
                                       self.url_context(),
                                       period))
            elt.content('{}s'.format(period))

    def write_common_process_status(self, tr_elt, item):
        """ Write the common part of a process status into a table. """
        selected_tr = False
        namespec = item['namespec']
        # print state
        elt = tr_elt.findmeld('state_td_mid')
        elt.attrib['class'] = item['statename']
        elt.content(item['statename'])
        # print expected loading
        status = self.get_process_status(namespec)
        if status:
            elt = tr_elt.findmeld('load_td_mid')
            elt.content('{}%'.format(status.rules.expected_loading))
        # get data from statistics module iaw period selection
        hide_cpu_link, hide_mem_link = (True, )*2
        nbcores, proc_stats = self.get_process_stats(namespec)
        if proc_stats:
            if len(proc_stats[0]) > 0:
                # print last CPU value of process
                elt = tr_elt.findmeld('pcpu_a_mid')
                cpuvalue = proc_stats[0][-1]
                if not self.supvisors.options.stats_irix_mode:
                    cpuvalue /= nbcores
                elt.content('{:.2f}%'.format(cpuvalue))
                if ViewHandler.namespec_stats == namespec:
                    selected_tr = True
                    elt.attributes(href='#')
                    elt.attrib['class'] = 'button off active'
                else:
                    elt.attributes(href='{}?{}processname={}'
                                   .format(self.page_name, self.url_context(),
                                           urllib.quote(namespec)))
                    elt.attrib['class'] = 'button on'
                hide_cpu_link = False
            if len(proc_stats[1]) > 0:
                # print last MEM value of process
                elt = tr_elt.findmeld('pmem_a_mid')
                elt.content('{:.2f}%'.format(proc_stats[1][-1]))
                if ViewHandler.namespec_stats == namespec:
                    selected_tr = True
                    elt.attributes(href='#')
                    elt.attrib['class'] = 'button off active'
                else:
                    elt.attributes(href='{}?{}processname={}'
                                   .format(self.page_name, self.url_context(),
                                           urllib.quote(namespec)))
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
            elt.attributes(href='{}?{}namespec={}&amp;action=start'
                           .format(self.page_name, self.url_context(),
                                   urllib.quote(namespec)))
        else:
           elt.attrib['class'] = 'button off'
        # stop button
        elt = tr_elt.findmeld('stop_a_mid')
        if process_state in RUNNING_STATES:
            elt.attrib['class'] = 'button on'
            elt.attributes(href='{}?{}namespec={}&amp;action=stop'
                           .format(self.page_name, self.url_context(),
                                   urllib.quote(namespec)))
        else:
           elt.attrib['class'] = 'button off'
        # restart button
        elt = tr_elt.findmeld('restart_a_mid')
        if process_state in RUNNING_STATES:
            elt.attrib['class'] = 'button on'
            elt.attributes(href='{}?{}namespec={}&amp;action=restart'
                           .format(self.page_name, self.url_context(),
                                   urllib.quote(namespec)))
        else:
           elt.attrib['class'] = 'button off'
        return selected_tr

    def write_process_statistics(self, root):
        """ Display detailed statistics about the selected process. """
        stats_elt = root.findmeld('pstats_div_mid')
        # get data from statistics module iaw period selection
        if ViewHandler.namespec_stats:
            nbcores, proc_stats = self.get_process_stats(
                ViewHandler.namespec_stats)
            if proc_stats and (len(proc_stats[0]) > 0 or \
                               len(proc_stats[1]) > 0):
                # set titles
                elt = stats_elt.findmeld('process_h_mid')
                elt.content(ViewHandler.namespec_stats)
                 # set CPU statistics
                if len(proc_stats[0]) > 0:
                    avg, rate, (a, b), dev = get_stats(proc_stats[0])
                    # print last CPU value of process
                    elt = stats_elt.findmeld('pcpuval_td_mid')
                    if rate is not None:
                        self.set_slope_class(elt, rate)
                    cpuvalue = proc_stats[0][-1]
                    if not self.supvisors.options.stats_irix_mode:
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
                    self.logger.warn("matplotlib module not found")
            else:
                if ViewHandler.namespec_stats:
                    self.logger.warn('unselect Process Statistics for {}'
                                     .format(ViewHandler.namespec_stats))
                    ViewHandler.namespec_stats = ''
        # remove stats part if empty
        if not ViewHandler.namespec_stats:
            stats_elt.replace('')

    def handle_parameters(self):
        """ Retrieve the parameters selected on the web page.
        These parameters are static to the current class, so they are shared
        between all browsers connected on this server. """
        form = self.context.form
        # update context period
        period_string = form.get('period')
        if period_string:
            period = int(period_string)
            if period in self.supvisors.options.stats_periods:
                if ViewHandler.period_stats != period:
                    self.logger.info('statistics period set to %d' % period)
                    ViewHandler.period_stats = period
            else:
                self.message(error_message('Incorrect period: {}'.format(
                    period_string)))
        # update process statistics selection
        process_name = form.get('processname')
        if process_name:
            _, proc_stats = self.get_process_stats(process_name)
            if proc_stats:
                if ViewHandler.namespec_stats != process_name:
                    self.logger.info('select detailed Process statistics '\
                                     'for %s' % process_name)
                    ViewHandler.namespec_stats = process_name
            else:
                self.message(error_message('Incorrect stats processname: {}'
                                           .format(process_name)))

    def handle_action(self):
        """ Handling of the actions requested from the Supvisors Address web
        page. """
        form = self.context.form
        action = form.get('action')
        if action:
            # trigger deferred action and wait
            namespec = form.get('namespec')
            if not self.callback:
                self.callback = self.make_callback(namespec, action)
                return NOT_DONE_YET
            # intermediate check
            message = self.callback()
            if message is NOT_DONE_YET:
                return NOT_DONE_YET
            # post to write message
            if message is not None:
                self.message(format_gravity_message(message))

    def message(self, message):
        """ Set message in context response to be displayed at next refresh. """
        form = self.context.form
        location = form['SERVER_URL'] + form['PATH_TRANSLATED'] + \
            '?{}message={}&amp;gravity={}'.format(
                self.url_context(), urllib.quote(message[1]), message[0])
        self.context.response['headers']['Location'] = location

    @staticmethod
    def set_slope_class(elt, value):
        """ Set attribute class iaw positive or negative slope. """
        if (abs(value) < .005):
            elt.attrib['class'] = 'stable'
        elif (value > 0):
            elt.attrib['class'] = 'increase'
        else:
            elt.attrib['class'] = 'decrease'

    def url_context(self):
        """ Get the extra parameters for the URL. """
        return ''

    def get_process_status(self, namespec):
        """ Get the ProcessStatus instance related to the process named
        namespec. """
        try:
            return self.supvisors.context.processes[namespec]
        except KeyError:
            self.logger.debug('failed to get ProcessStatus from {}'.format(
                namespec))

    def server_port(self):
        """ Get the port number of the web server. """
        return self.context.form.get('SERVER_PORT')

    @staticmethod
    def cpu_id_to_string(idx):
        """ Get a displayable form to cpu index. """
        return idx - 1 if idx > 0 else 'all'

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
                group_config = self.supvisors.info_source.get_group_config(
                    application_name)
                # get process name ordering in this configuration
                ordering = [proc.name for proc in group_config.process_configs]
                # add processes known to supervisor, using the same ordering
                sorted_processes.extend(sorted([proc for proc in processes
                    if proc['application_name'] == application_name and \
                        proc['process_name'] in ordering],
                    key=lambda x: ordering.index(x['process_name'])))
                # add processes unknown to supervisor, using the alphabetical
                # ordering
                sorted_processes.extend(sorted([proc for proc in processes
                    if proc['application_name'] == application_name and \
                        proc['process_name'] not in ordering],
                    key=lambda x: x['process_name']))
        return sorted_processes
