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
from supervisor.web import MeldView
from supervisor.xmlrpc import RPCError

from supvisors.ttypes import StartingStrategies
from supvisors.utils import supvisors_short_cuts
from supvisors.viewhandler import ViewHandler
from supvisors.webutils import *


class ApplicationView(MeldView, ViewHandler):
    """ Supvisors Application page. """

    # Name of the HTML page
    page_name = 'application.html'

    def __init__(self, context):
        """ Initialization of the attributes. """
        MeldView.__init__(self, context)
        self.supvisors = self.context.supervisord.supvisors
        supvisors_short_cuts(self, ['logger'])

    def url_context(self):
        return 'appli={}&amp;'.format(self.application_name)

    def render(self):
        """ Method called by Supervisor to handle the rendering
        of the Supvisors Application page. """
        self.application_name = self.context.form.get('appli')
        if not self.application_name:
            self.logger.error('no application')
        elif self.application_name not in self.supvisors.context.applications.keys():
            self.logger.error('unknown application: {}'.format(self.application_name))
        else:
            # Force the call to the render method of ViewHandler
            return ViewHandler.render(self)

    def write_navigation(self, root):
        """ Rendering of the navigation menu with selection
        of the current application. """
        self.write_nav(root, appli=self.application_name)

    def write_header(self, root):
        """ Rendering of the header part of the Supvisors Application page. """
        # set address name
        elt = root.findmeld('application_mid')
        elt.content(self.application_name)
        # set application state
        application = self.supvisors.context.applications[self.application_name]
        elt = root.findmeld('state_mid')
        elt.content(application.state_string())
        # set LED iaw major/minor failures
        elt = root.findmeld('state_led_mid')
        if application.running():
            if application.major_failure:
                elt.attrib['class'] = 'status_red'
            elif application.minor_failure:
                elt.attrib['class'] = 'status_yellow'
            else:
                elt.attrib['class'] = 'status_green'
        else:
            elt.attrib['class'] = 'status_empty'
        # write periods of statistics
        self.write_starting_strategy(root)
        self.write_periods(root)
        # write actions related to application
        self.write_application_actions(root)

    def write_starting_strategy(self, root):
        """ Write applicable starting strategies. """
        # get the current strategy
        strategy = self.supvisors.starter.strategy
        # set hyperlinks for strategy actions
        # CONFIG strategy
        elt = root.findmeld('config_a_mid')
        if strategy == StartingStrategies.CONFIG:
            elt.attrib['class'] = "button off active"
        else:
            elt.attributes(href='{}?{}&action=config'
                           .format(self.page_name, self.url_context()))
        # MOST_LOADED strategy
        elt = root.findmeld('most_a_mid')
        if strategy == StartingStrategies.MOST_LOADED:
            elt.attrib['class'] = "button off active"
        else:
            elt.attributes(href='{}?{}action=most'
                           .format(self.page_name, self.url_context()))
        # LESS_LOADED strategy
        elt = root.findmeld('less_a_mid')
        if strategy == StartingStrategies.LESS_LOADED:
            elt.attrib['class'] = "button off active"
        else:
            elt.attributes(href='{}?{}&action=less'
                           .format(self.page_name, self.url_context()))


    def write_application_actions(self, root):
        """ Write actions related to the application. """
        # set hyperlinks for global actions
        elt = root.findmeld('refresh_a_mid')
        elt.attributes(href='{}?{}action=refresh'
                       .format(self.page_name, self.url_context()))
        elt = root.findmeld('startapp_a_mid')
        elt.attributes(href='{}?{}action=startapp'
                       .format(self.page_name, self.url_context()))
        elt = root.findmeld('stopapp_a_mid')
        elt.attributes(href='{}?{}action=stopapp'.
                       format(self.page_name, self.url_context()))
        elt = root.findmeld('restartapp_a_mid')
        elt.attributes(href='{}?{}action=restartapp'
                       .format(self.page_name, self.url_context()))

    def write_contents(self, root):
        """ Rendering of the contents part of the page. """
        self.write_process_table(root)
        # check selected Process Statistics
        if ViewHandler.namespec_stats:
            status = self.get_process_status(ViewHandler.namespec_stats)
            if not status or status.application_name != self.application_name:
                self.logger.warn('unselect Process Statistics for {}'
                                 .format(ViewHandler.namespec_stats))
                ViewHandler.namespec_stats = ''
            else:
                # addtional information for title
                elt = root.findmeld('address_fig_mid')
                elt.content(next(iter(status.addresses), ''))
        # write selected Process Statistics
        self.write_process_statistics(root)

    def get_process_stats(self, namespec):
        """ Get the statistics structure related to the period selected
        and the address where the process named namespec is running. """
        status = self.get_process_status(namespec)
        if status:
            # get running address from procStatus
            address = next(iter(status.addresses), None)
            if address:
                stats = self.supvisors.statistician.data[address][ViewHandler.period_stats]
                nbcores = self.supvisors.statistician.nbcores[address]
                return nbcores, stats.find_process_stats(namespec)
        return 0, None

    def write_process_table(self, root):
        """ Rendering of the application processes managed through Supervisor. """
        # collect data on processes
        data = []
        application = self.supvisors.context.applications[self.application_name]
        for process in application.processes.values():
            data.append({'application_name': process.application_name,
                         'process_name': process.process_name,
                         'namespec': process.namespec(),
                         'running_list': list(process.addresses),
                         'statename': process.state_string(),
                         'statecode': process.state})
        # print processes
        if data:
            # re-arrange data
            data = self.sort_processes_by_config(data)
            # loop on all processes
            iterator = root.findmeld('tr_mid').repeat(data)
            shaded_tr = False # used to invert background style
            for tr_elt, item in iterator:
                # get first item in running list
                running_list = item['running_list']
                address = next(iter(running_list), None)
                # write common status(shared between this application view and address view)
                selected_tr = self.write_common_process_status(tr_elt, item)
                # print process name (tail NOT allowed if STOPPED)
                process_name = item['process_name']
                namespec = item['namespec']
                if address:
                    elt = tr_elt.findmeld('name_a_mid')
                    elt.attributes(href='http://{}:{}/tail.html?processname={}'.format(address, self.server_port(), urllib.quote(namespec)))
                    elt.content(process_name)
                else:
                    elt = tr_elt.findmeld('name_a_mid')
                    elt.replace(process_name)
                # print running addresses
                if running_list:
                    addrIterator = tr_elt.findmeld('running_li_mid').repeat(running_list)
                    for li_elt, address in addrIterator:
                        elt = li_elt.findmeld('running_a_mid')
                        elt.attributes(href='procaddress.html?address={}'.format(address))
                        elt.content(address)
                else:
                    elt = tr_elt.findmeld('running_ul_mid')
                    elt.replace('')
                # set line background and invert
                if selected_tr:
                    tr_elt.attrib['class'] = 'selected'
                elif shaded_tr:
                    tr_elt.attrib['class'] = 'shaded'
                shaded_tr = not shaded_tr
        else:
            table = root.findmeld('table_mid')
            table.replace('No programs to manage')

    def make_callback(self, namespec, action):
        """ Triggers processing iaw action requested. """
        if action == 'refresh':
            return self.refresh_action()
        if action == 'config':
            return self.set_starting_strategy(StartingStrategies.CONFIG)
        if action == 'most':
            return self.set_starting_strategy(StartingStrategies.MOST_LOADED)
        if action == 'less':
            return self.set_starting_strategy(StartingStrategies.LESS_LOADED)
        # get current strategy
        strategy = self.supvisors.starter.strategy
        if action == 'startapp':
            return self.start_application_action(strategy)
        if action == 'stopapp':
            return self.stop_application_action()
        if action == 'restartapp':
            return self.restart_application_action(strategy)
        if namespec:
            if self.get_process_status(namespec) is None:
                return delayed_error('No such process named %s' % namespec)
            if action == 'start':
                return self.start_process_action(strategy, namespec)
            if action == 'stop':
                return self.stop_process_action(namespec)
            if action == 'restart':
                return self.restart_process_action(strategy, namespec)

    def refresh_action(self):
        """ Refresh web page. """
        return delayed_info('Page refreshed')

    def set_starting_strategy(self, strategy):
        """ Update starting strategy. """
        self.supvisors.starter.strategy = strategy
        return delayed_info('Starting strategy set to {}'.format(StartingStrategies._to_string(strategy)))

    # Application actions
    def start_application_action(self, strategy):
        """ Start the application iaw the strategy. """
        try:
            cb = self.supvisors.info_source.supvisors_rpc_interface.start_application(strategy, self.application_name)
        except RPCError, e:
            return delayed_error('start_application: {}'.format(e.text))
        if callable(cb):
            def onwait():
                try:
                    result = cb()
                except RPCError, e:
                    return error_message('start_application: {}'.format(e.text))
                if result is NOT_DONE_YET:
                    return NOT_DONE_YET
                if result:
                    return info_message('Application {} started'.format(self.application_name))
                return warn_message('Application {} NOT started'.format(self.application_name))
            onwait.delay = 0.1
            return onwait
        if cb:
            return delayed_info('Application {} started'.format(self.application_name))
        return delayed_warn('Application {} NOT started'.format(self.application_name))

    def stop_application_action(self):
        """ Stop the application. """
        try:
            cb = self.supvisors.info_source.supvisors_rpc_interface.stop_application(self.application_name)
        except RPCError, e:
            return delayed_error('stopApplication: {}'.format(e.text))
        if callable(cb):
            def onwait():
                try:
                    result = cb()
                except RPCError, e:
                    return error_message('stopApplication: {}'.format(e.text))
                if result is NOT_DONE_YET:
                    return NOT_DONE_YET
                return info_message('Application {} stopped'.format(self.application_name))
            onwait.delay = 0.1
            return onwait
        return delayed_info('Application {} stopped'.format(self.application_name))

    def restart_application_action(self, strategy):
        """ Restart the application iaw the strategy. """
        try:
            cb = self.supvisors.info_source.supvisors_rpc_interface.restart_application(strategy, self.application_name)
        except RPCError, e:
            return delayed_error('restartApplication: {}'.format(e.text))
        if callable(cb):
            def onwait():
                try:
                    result = cb()
                except RPCError, e:
                    return error_message('restartApplication: {}'.format(e.text))
                if result is NOT_DONE_YET:
                    return NOT_DONE_YET
                if result:
                    return info_message('Application {} restarted'.format(self.application_name))
                return warn_message('Application {} NOT restarted'.format(self.application_name))
            onwait.delay = 0.1
            return onwait
        if cb:
            return delayed_info('Application {} restarted'.format(self.application_name))
        return delayed_warn('Application {} NOT restarted'.format(self.application_name))

    # Process actions
    def start_process_action(self, strategy, namespec):
        """ Start the process named namespec iaw the strategy. """
        try:
            cb = self.supvisors.info_source.supvisors_rpc_interface.start_process(strategy, namespec)
        except RPCError, e:
            return delayed_error('startProcess: {}'.format(e.text))
        if callable(cb):
            def onwait():
                try:
                    result = cb()
                except RPCError, e:
                    return error_message('startProcess: {}'.format(e.text))
                if result is NOT_DONE_YET:
                    return NOT_DONE_YET
                if result:
                    return info_message('Process {} started'.format(namespec))
                return warn_message('Process {} NOT started'.format(namespec))
            onwait.delay = 0.1
            return onwait
        if cb:
            return delayed_info('Process {} started'.format(namespec))
        return delayed_warn('Process {} NOT started'.format(namespec))

    def stop_process_action(self, namespec):
        """ Stop the process named namespec. """
        try:
            cb = self.supvisors.info_source.supvisors_rpc_interface.stop_process(namespec)
        except RPCError, e:
            return delayed_error('stopProcess: {}'.format(e.text))
        if callable(cb):
            def onwait():
                try:
                    result = cb()
                except RPCError, e:
                    return error_message('stopProcess: {}'.format(e.text))
                if result is NOT_DONE_YET:
                    return NOT_DONE_YET
                return info_message('process {} stopped'.format(namespec))
            onwait.delay = 0.1
            return onwait
        return delayed_info('process {} stopped'.format(namespec))

    def restart_process_action(self, strategy, namespec):
        """ Restart the process named namespec iaw the strategy. """
        try:
            cb = self.supvisors.info_source.supvisors_rpc_interface.restart_process(strategy, namespec)
        except RPCError, e:
            return delayed_error('restartProcess: {}'.format(e.text))
        if callable(cb):
            def onwait():
                try:
                    result = cb()
                except RPCError, e:
                    return error_message('restartProcess: {}'.format(e.text))
                if result is NOT_DONE_YET:
                    return NOT_DONE_YET
                if result:
                    return info_message('Process {} restarted'.format(namespec))
                return warn_message('Process {} NOT restarted'.format(namespec))
            onwait.delay = 0.1
            return onwait
        if cb:
            return delayed_info('Process {} restarted'.format(namespec))
        return delayed_warn('Process {} NOT restarted'.format(namespec))
