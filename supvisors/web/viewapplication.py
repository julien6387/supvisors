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

from supervisor.states import ProcessStates

from supvisors.application import ApplicationStatus
from supvisors.ttypes import PayloadList
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

    def handle_parameters(self) -> None:
        """ Retrieve the parameters selected on the web page.

        :return: None
        """
        ViewHandler.handle_parameters(self)
        # check if application name is available
        self.application_name = self.view_ctx.parameters[APPLI]
        try:
            # store application
            self.application = self.sup_ctx.applications[self.application_name]
        except KeyError:
            # may happen when the user clicks from a page of the previous launch while the current Supvisors is still
            # in INITIALIZATION stats or if wrong application_name set in URL
            self.logger.error(f'ApplicationView.handle_parameters: unknown application_name={self.application_name}')
            # redirect page to main page to avoid infinite error loop
            self.view_ctx.store_message = error_message(f'Unknown application: {self.application_name}')
            self.view_ctx.redirect = True

    def write_navigation(self, root):
        """ Rendering of the navigation menu with selection of the current application. """
        self.write_nav(root, appli=self.application_name)

    # RIGHT SIDE / HEADER part
    def write_header(self, root):
        """ Rendering of the header part of the Supvisors Application page. """
        if self.application:
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

    def write_periods(self, root):
        """ Write configured periods for statistics. """
        self.write_periods_availability(root, self.has_process_statistics)

    def write_starting_strategy(self, root):
        """ Write applicable starting strategies. """
        # get the current strategy
        selected_strategy = self.view_ctx.parameters[STRATEGY]
        # set hyperlinks for strategy actions
        for strategy in StartingStrategies:
            elt = root.findmeld('%s_a_mid' % strategy.name.lower())
            if selected_strategy == strategy.name:
                elt.attrib['class'] = 'button off active'
            else:
                url = self.view_ctx.format_url('', self.page_name, **{STRATEGY: strategy.name})
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
    def write_contents(self, root) -> None:
        """ Rendering of the contents part of the page.

        :param root: the root element of the page
        :return: None
        """
        if self.application:
            data = self.get_process_data()
            self.write_process_table(root, data)
            # check selected Process Statistics
            namespec = self.view_ctx.parameters[PROCESS]
            if namespec:
                status = self.view_ctx.get_process_status(namespec)
                if not status or status.stopped() or status.application_name != self.application_name:
                    self.logger.warn(f'ApplicationView.write_contents: unselect Process Statistics for {namespec}')
                    # form parameter is not consistent. remove it
                    self.view_ctx.parameters[PROCESS] = ''
            # write selected Process Statistics
            namespec = self.view_ctx.parameters[PROCESS]
            info = next(filter(lambda x: x['namespec'] == namespec, data), {})
            self.write_process_statistics(root, info)

    def get_process_last_desc(self, namespec: str) -> Tuple[Optional[str], str]:
        """ Get the latest description received from the process across all instances.
        A priority is given to the info coming from a node where the process is running. """
        status = self.view_ctx.get_process_status(namespec)
        return status.get_last_description()

    def get_process_data(self) -> PayloadList:
        """ Collect sorted data on processes.

        :return: information about the application processes
        """
        data = []
        for process in self.application.processes.values():
            namespec = process.namespec
            node_name, description = self.get_process_last_desc(namespec)
            unexpected_exit = process.state == ProcessStates.EXITED and not process.expected_exit
            nb_cores, proc_stats = self.view_ctx.get_process_stats(namespec, node_name)
            data.append({'application_name': process.application_name, 'process_name': process.process_name,
                         'namespec': namespec, 'identifier': node_name,
                         'disabled': process.disabled(), 'startable': len(process.possible_identifiers()) > 0,
                         'statename': process.displayed_state_string(), 'statecode': process.displayed_state,
                         'gravity': 'FATAL' if unexpected_exit else process.state_string(),
                         'has_crashed': process.has_crashed(),
                         'running_identifiers': list(process.running_identifiers),
                         'description': description,
                         'expected_load': process.rules.expected_load, 'nb_cores': nb_cores, 'proc_stats': proc_stats})
        # re-arrange data using alphabetical order
        return sorted(data, key=lambda x: x['process_name'])

    def write_process_table(self, root, data):
        """ Rendering of the application processes managed through Supervisor. """
        if data:
            self.write_common_process_table(root)
            # loop on all processes
            iterator = root.findmeld('tr_mid').repeat(data)
            shaded_tr = False  # used to invert background style
            for tr_elt, info in iterator:
                # write common status (shared between this application view and node view)
                self.write_common_process_status(tr_elt, info, False)
                # print process name and running instances
                self.write_process(tr_elt, info)
                # set line background and invert
                apply_shade(tr_elt, shaded_tr)
                shaded_tr = not shaded_tr
        else:
            table = root.findmeld('table_mid')
            table.replace('No programs to manage')

    def write_process(self, tr_elt, info):
        """ Rendering of the cell corresponding to the process running instances. """
        running_nodes = info['running_identifiers']
        if running_nodes:
            running_li_mid = tr_elt.findmeld('running_li_mid')
            for li_elt, node_name in running_li_mid.repeat(running_nodes):
                elt = li_elt.findmeld('running_a_mid')
                elt.content(node_name)
                url = self.view_ctx.format_url(node_name, PROC_INSTANCE_PAGE)
                elt.attributes(href=url)
                if node_name == info['identifier']:
                    update_attrib(elt, 'class', 'active')
        else:
            elt = tr_elt.findmeld('running_ul_mid')
            elt.replace('')

    # ACTIONS
    def make_callback(self, namespec: str, action: str):
        """ Triggers processing iaw action requested. """
        if self.application:
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

    # Application actions
    def start_application_action(self, strategy: StartingStrategies) -> Callable:
        """ Start the application iaw the strategy.
        The RPC wait parameter is linked to the auto-refresh parameter of the page.

        :param strategy: the strategy to apply for starting the application
        :return: a callable for deferred result
        """
        wait = not self.view_ctx.parameters[AUTO]
        return self.supvisors_rpc_action('start_application', (strategy.value, self.application_name, wait),
                                         f'Application {self.application_name} started')

    def restart_application_action(self, strategy: StartingStrategies) -> Callable:
        """ Restart the application iaw the strategy.
        The RPC wait parameter is linked to the auto-refresh parameter of the page.

        :param strategy: the strategy to apply for restarting the application
        :return: a callable for deferred result
        """
        wait = not self.view_ctx.parameters[AUTO]
        return self.supvisors_rpc_action('restart_application', (strategy.value, self.application_name, wait),
                                         f'Application {self.application_name} restarted')

    def stop_application_action(self) -> Callable:
        """ Stop the application.
        The RPC wait parameter is linked to the auto-refresh parameter of the page.

        :return: a callable for deferred result
        """
        wait = not self.view_ctx.parameters[AUTO]
        return self.supvisors_rpc_action('stop_application', (self.application_name, wait),
                                         f'Application {self.application_name} stopped')

    # Process actions
    def start_process_action(self, strategy: StartingStrategies, namespec: str) -> Callable:
        """ Start the process named namespec iaw the strategy.
        The RPC wait parameter is linked to the auto-refresh parameter of the page.

        :param strategy: the strategy to apply for starting the process
        :param namespec: the process namespec
        :return: a callable for deferred result
        """
        wait = not self.view_ctx.parameters[AUTO]
        return self.supvisors_rpc_action('start_process', (strategy.value, namespec, '', wait),
                                         f'Process {namespec} started')

    def restart_process_action(self, strategy: StartingStrategies, namespec: str) -> Callable:
        """ Restart the process named namespec iaw the strategy.
        The RPC wait parameter is linked to the auto-refresh parameter of the page.

        :param strategy: the strategy to apply for restarting the process
        :param namespec: the process namespec
        :return: a callable for deferred result
        """
        wait = not self.view_ctx.parameters[AUTO]
        return self.supvisors_rpc_action('restart_process', (strategy.value, namespec, '', wait),
                                         f'Process {namespec} restarted')

    def stop_process_action(self, namespec: str) -> Callable:
        """ Stop the process named namespec.
        The RPC wait parameter is linked to the auto-refresh parameter of the page.

        :param namespec: the process namespec
        :return: a callable for deferred result
        """
        wait = not self.view_ctx.parameters[AUTO]
        return self.supvisors_rpc_action('stop_process', (namespec, wait), f'Process {namespec} stopped')

    def clearlog_process_action(self, namespec: str) -> Callable:
        """ Can't call supervisor StatusView source code from application view.
        Just do the same job.

        :param namespec: the process namespec
        :return: a callable for deferred result
        """
        return self.supervisor_rpc_action('clearProcessLogs', (namespec,), f'Log for {namespec} cleared')
