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

from supervisor.http import NOT_DONE_YET
from supervisor.states import ProcessStates
from supervisor.xmlrpc import RPCError

from .application import ApplicationStatus
from .ttypes import PayloadList
from .viewcontext import *
from .viewhandler import ViewHandler
from .webutils import *


class ApplicationView(ViewHandler):
    """ Supvisors Application page. """

    def __init__(self, context):
        """ Call of the superclass constructors. """
        ViewHandler.__init__(self, context)
        self.page_name = APPLICATION_PAGE
        # init parameters
        self.application_name: str = ''
        self.application: Optional[ApplicationStatus] = None

    def handle_parameters(self):
        """ Retrieve the parameters selected on the web page. """
        ViewHandler.handle_parameters(self)
        # check if application name is available
        self.application_name = self.view_ctx.parameters[APPLI]
        if self.application_name:
            # store application
            self.application = self.sup_ctx.applications[self.application_name]
        else:
            self.view_ctx.message(error_message('No application'))

    def write_navigation(self, root):
        """ Rendering of the navigation menu with selection
        of the current application. """
        self.write_nav(root, appli=self.application_name)

    # RIGHT SIDE / HEADER part
    def write_header(self, root):
        """ Rendering of the header part of the Supvisors Application page. """
        # set application name
        elt = root.findmeld('application_mid')
        elt.content(self.application_name)
        # set application state
        elt = root.findmeld('state_mid')
        elt.content(self.application.state.name)
        # set LED iaw major/minor failures
        elt = root.findmeld('state_led_mid')
        if self.application.major_failure:
            elt.attrib['class'] = 'status_red'
        elif self.application.minor_failure:
            elt.attrib['class'] = 'status_yellow'
        elif self.application.running():
            elt.attrib['class'] = 'status_green'
        else:
            elt.attrib['class'] = 'status_empty'
        # write options
        self.write_starting_strategy(root)
        self.write_periods(root)
        # write actions related to application
        self.write_application_actions(root)

    def write_starting_strategy(self, root):
        """ Write applicable starting strategies. """
        # get the current strategy
        strategy = self.view_ctx.parameters[STRATEGY]
        # set hyperlinks for strategy actions
        for str_strategy in StartingStrategies._member_names_:
            elt = root.findmeld('%s_a_mid' % str_strategy.lower())
            if strategy == str_strategy:
                elt.attrib['class'] = 'button off active'
            else:
                url = self.view_ctx.format_url('', self.page_name, **{STRATEGY: str_strategy})
                elt.attributes(href=url)

    def write_application_actions(self, root):
        """ Write actions related to the application. """
        # configure start application button
        elt = root.findmeld('startapp_a_mid')
        url = self.view_ctx.format_url('', self.page_name, **{ACTION: 'startapp'})
        elt.attributes(href=url)
        # configure stop application button
        elt = root.findmeld('stopapp_a_mid')
        url = self.view_ctx.format_url('', self.page_name, **{ACTION: 'stopapp'})
        elt.attributes(href=url)
        # configure restart application button
        elt = root.findmeld('restartapp_a_mid')
        url = self.view_ctx.format_url('', self.page_name, **{ACTION: 'restartapp'})
        elt.attributes(href=url)

    # RIGHT SIDE / BODY part
    def write_contents(self, root):
        """ Rendering of the contents part of the page. """
        data = self.get_process_data()
        self.write_process_table(root, data)
        # check selected Process Statistics
        namespec = self.view_ctx.parameters[PROCESS]
        if namespec:
            status = self.view_ctx.get_process_status(namespec)
            if not status or status.stopped() or status.application_name != self.application_name:
                self.logger.warn('unselect Process Statistics for {}'.format(namespec))
                # form parameter is not consistent. remove it
                self.view_ctx.parameters[PROCESS] = ''
        # write selected Process Statistics
        namespec = self.view_ctx.parameters[PROCESS]
        info = next(filter(lambda x: x['namespec'] == namespec, data), {})
        self.write_process_statistics(root, info)

    def get_process_last_desc(self, namespec: str) -> Tuple[Optional[str], str]:
        """ Get the latest description received from the process across all nodes.
        A priority is given to the info coming from a node where the process is running. """
        status = self.view_ctx.get_process_status(namespec)
        return status.get_last_description()

    def get_process_data(self) -> PayloadList:
        """ Collect sorted data on processes. """
        data = []
        for process in self.application.processes.values():
            namespec = process.namespec
            node_name, description = self.get_process_last_desc(namespec)
            unexpected_exit = process.state == ProcessStates.EXITED and not process.expected_exit
            nb_cores, proc_stats = self.view_ctx.get_process_stats(namespec, node_name)
            data.append({'application_name': process.application_name, 'process_name': process.process_name,
                         'namespec': namespec, 'node_name': node_name,
                         'statename': process.state_string(), 'statecode': process.state,
                         'gravity': 'FATAL' if unexpected_exit else process.state_string(),
                         'running_nodes': list(process.running_nodes),
                         'description': description,
                         'expected_load': process.rules.expected_load, 'nb_cores': nb_cores, 'proc_stats': proc_stats})
        # re-arrange data using alphabetical order
        return sorted(data, key=lambda x: x['process_name'])

    def write_process_table(self, root, data):
        """ Rendering of the application processes managed through Supervisor. """
        if data:
            # loop on all processes
            iterator = root.findmeld('tr_mid').repeat(data)
            shaded_tr = False  # used to invert background style
            for tr_elt, info in iterator:
                # write common status (shared between this application view and node view)
                self.write_common_process_status(tr_elt, info)
                # print process name and running nodes
                self.write_process(tr_elt, info)
                # set line background and invert
                apply_shade(tr_elt, shaded_tr)
                shaded_tr = not shaded_tr
        else:
            table = root.findmeld('table_mid')
            table.replace('No programs to manage')

    def write_process(self, tr_elt, info):
        """ Rendering of the cell corresponding to the process running nodes. """
        running_nodes = info['running_nodes']
        if running_nodes:
            running_li_mid = tr_elt.findmeld('running_li_mid')
            for li_elt, node_name in running_li_mid.repeat(running_nodes):
                elt = li_elt.findmeld('running_a_mid')
                elt.content(node_name)
                url = self.view_ctx.format_url(node_name, PROC_NODE_PAGE)
                elt.attributes(href=url)
                if node_name == info['node_name']:
                    update_attrib(elt, 'class', 'active')
        else:
            elt = tr_elt.findmeld('running_ul_mid')
            elt.replace('')

    # ACTIONS
    def make_callback(self, namespec, action):
        """ Triggers processing iaw action requested. """
        if action == 'refresh':
            return self.refresh_action()
        # get current strategy
        strategy = StartingStrategies[self.view_ctx.parameters[STRATEGY]]
        if action == 'startapp':
            return self.start_application_action(strategy)
        if action == 'stopapp':
            return self.stop_application_action()
        if action == 'restartapp':
            return self.restart_application_action(strategy)
        if namespec:
            if self.view_ctx.get_process_status(namespec) is None:
                return delayed_error('No such process named %s' % namespec)
            if action == 'start':
                return self.start_process_action(strategy, namespec)
            if action == 'stop':
                return self.stop_process_action(namespec)
            if action == 'restart':
                return self.restart_process_action(strategy, namespec)
            if action == 'clearlog':
                return self.clearlog_process_action(namespec)

    @staticmethod
    def refresh_action():
        """ Refresh web page. """
        return delayed_info('Page refreshed')

    # Common processing for starting and stopping actions
    def start_action(self, strategy, rpc_name, arg_name, arg_type):
        """ Start/Restart an application or a process iaw the strategy. """
        try:
            rpc_intf = self.supvisors.info_source.supvisors_rpc_interface
            cb = getattr(rpc_intf, rpc_name)(strategy, arg_name)
        except RPCError as e:
            return delayed_error('{}: {}'.format(rpc_name, e.text))
        if callable(cb):
            def onwait():
                try:
                    result = cb()
                except RPCError as exc:
                    return error_message('{}: {}'.format(rpc_name, exc.text))
                if result is NOT_DONE_YET:
                    return NOT_DONE_YET
                if result:
                    return info_message('{} {} started'.format(arg_type, arg_name))
                return warn_message('{} {} NOT started'.format(arg_type, arg_name))

            onwait.delay = 0.1
            return onwait
        if cb:
            return delayed_info('{} {} started'.format(arg_type, arg_name))
        return delayed_warn('{} {} NOT started'.format(arg_type, arg_name))

    def stop_action(self, rpc_name, arg_name, arg_type):
        """ Stop an application or a process. """
        try:
            rpc_intf = self.supvisors.info_source.supvisors_rpc_interface
            cb = getattr(rpc_intf, rpc_name)(arg_name)
        except RPCError as e:
            return delayed_error('{}: {}'.format(rpc_name, e.text))
        if callable(cb):
            def onwait():
                try:
                    result = cb()
                except RPCError as exc:
                    return error_message('{}: {}'.format(rpc_name, exc.text))
                if result is NOT_DONE_YET:
                    return NOT_DONE_YET
                return info_message('{} {} stopped'.format(arg_type, arg_name))

            onwait.delay = 0.1
            return onwait
        if cb:
            return delayed_info('{} {} stopped'.format(arg_type, arg_name))
        return delayed_warn('{} {} NOT stopped'.format(arg_type, arg_name))

    # Application actions
    def start_application_action(self, strategy):
        """ Start the application iaw the strategy. """
        return self.start_action(strategy, 'start_application', self.application_name, 'Application')

    def restart_application_action(self, strategy):
        """ Restart the application iaw the strategy. """
        return self.start_action(strategy, 'restart_application', self.application_name, 'Application')

    def stop_application_action(self):
        """ Stop the application. """
        return self.stop_action('stop_application', self.application_name, 'Application')

    # Process actions
    def start_process_action(self, strategy, namespec):
        """ Start the process named namespec iaw the strategy. """
        return self.start_action(strategy, 'start_process', namespec, 'Process')

    def restart_process_action(self, strategy, namespec):
        """ Restart the process named namespec iaw the strategy. """
        return self.start_action(strategy, 'restart_process', namespec, 'Process')

    def stop_process_action(self, namespec):
        """ Stop the process named namespec. """
        return self.stop_action('stop_process', namespec, 'Process')

    def clearlog_process_action(self, namespec):
        """ Can't call supervisor StatusView source code from application view.
        Just do the same job. """
        try:
            rpc_intf = self.supvisors.info_source.supervisor_rpc_interface
            rpc_intf.clearProcessLogs(namespec)
        except RPCError as e:
            return delayed_error('unexpected rpc fault [%d] %s' % (e.code, e.text))
        return delayed_info('Log for %s cleared' % namespec)
