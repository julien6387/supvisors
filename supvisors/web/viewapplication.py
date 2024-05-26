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
from supvisors.ttypes import PayloadList, Payload
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
        self.application_name = self.view_ctx.application_name
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
    def write_status(self, header_elt):
        """ Rendering of the header part of the Supvisors Application page. """
        if self.application:
            # set application name
            header_elt.findmeld('application_mid').content(self.application_name)
            # set application state
            header_elt.findmeld('state_mid').content(self.application.state.name)
            # set LED iaw major/minor failures
            elt = header_elt.findmeld('state_led_mid')
            if self.application.major_failure:
                elt.attrib['class'] = 'status_red'
            elif self.application.minor_failure:
                elt.attrib['class'] = 'status_yellow'
            elif self.application.running():
                elt.attrib['class'] = 'status_green'
            else:
                elt.attrib['class'] = 'status_empty'

    def write_options(self, header_elt):
        """ Write application options. """
        self.write_starting_strategy(header_elt)
        if self.has_process_statistics:
            self.write_periods(header_elt)
        else:
            # hide the Statistics periods box
            header_elt.findmeld('period_div_mid').replace('')

    def write_starting_strategy(self, header_elt):
        """ Write applicable starting strategies. """
        # get the current strategy
        selected_strategy = self.view_ctx.strategy
        # set hyperlinks for strategy actions
        for strategy in StartingStrategies:
            button_elt = header_elt.findmeld('%s_div_mid' % strategy.name.lower())
            href_elt = button_elt.findmeld('%s_a_mid' % strategy.name.lower())
            if selected_strategy == strategy:
                update_attrib(button_elt, 'class', 'off active')
            else:
                update_attrib(button_elt, 'class', 'on')
                url = self.view_ctx.format_url('', self.page_name, **{STRATEGY: strategy.name})
                href_elt.attributes(href=url)

    def write_actions(self, header_elt):
        """ Write actions related to the application. """
        super().write_actions(header_elt)
        # configure start application button
        elt = header_elt.findmeld('startapp_a_mid')
        url = self.view_ctx.format_url('', self.page_name, **{ACTION: 'startapp'})
        elt.attributes(href=url)
        # configure stop application button
        elt = header_elt.findmeld('stopapp_a_mid')
        url = self.view_ctx.format_url('', self.page_name, **{ACTION: 'stopapp'})
        elt.attributes(href=url)
        # configure restart application button
        elt = header_elt.findmeld('restartapp_a_mid')
        url = self.view_ctx.format_url('', self.page_name, **{ACTION: 'restartapp'})
        elt.attributes(href=url)

    # RIGHT SIDE / BODY part
    def write_contents(self, contents_elt) -> None:
        """ Rendering of the contents part of the page.

        :param contents_elt: the root element of the page.
        :return: None.
        """
        if self.application:
            data = self.get_process_data()
            self.write_process_table(contents_elt, data)
            # check selected Process Statistics
            namespec = self.view_ctx.process_name
            identifier = self.view_ctx.identifier
            if namespec and identifier:
                status = self.view_ctx.get_process_status(namespec)
                if not status or status.stopped() or status.application_name != self.application_name:
                    self.logger.warn(f'ApplicationView.write_contents: unselect Process Statistics for {namespec}')
                    # form parameter is not consistent. remove it
                    self.view_ctx.process_name = ''
            # write selected Process Statistics
            namespec = self.view_ctx.process_name
            info = next(filter(lambda x: (x['namespec'] == namespec and x['identifier'] == identifier), data), {})
            self.write_process_statistics(contents_elt, info)

    def get_process_data(self) -> PayloadList:
        """ Collect sorted data on processes.

        :return: information about the application processes.
        """
        data = []
        for process in self.application.processes.values():
            namespec = process.namespec
            # add the process synthesis
            unexpected_exit = process.state == ProcessStates.EXITED and not process.expected_exit
            possible_identifiers = process.possible_identifiers()
            identifier, description, has_stdout, has_stderr = process.get_applicable_details()
            # get_applicable_details may return a list of identifiers
            nb_cores, proc_stats = 0, None
            if identifier:
                nb_cores, proc_stats = self.view_ctx.get_process_stats(namespec, identifier)
            data.append({'row_type': ProcessRowTypes.APPLICATION_PROCESS,
                         'application_name': process.application_name, 'process_name': process.process_name,
                         'namespec': namespec, 'identifier': identifier,
                         'disabled': process.disabled(), 'startable': len(possible_identifiers) > 0, 'stoppable': True,
                         'statename': process.displayed_state_string(), 'statecode': process.displayed_state,
                         'gravity': 'FATAL' if unexpected_exit else process.displayed_state_string(),
                         'has_crashed': process.has_crashed(),
                         'running_identifiers': list(process.running_identifiers),
                         'description': description,
                         'main': True, 'nb_items': len(process.info_map),
                         'expected_load': process.rules.expected_load,
                         'nb_cores': nb_cores, 'proc_stats': proc_stats,
                         'has_stdout': has_stdout, 'has_stderr': has_stderr})
            # add data depending on the process shex
            process_shex, _ = self.view_ctx.get_process_shex(process.process_name)
            if process_shex:
                # add the process details (name is not needed)
                # NOTE: start / restart actions are not allowed
                for identifier, info in process.info_map.items():
                    crashed = ProcessStatus.is_crashed_event(info)
                    nb_cores, proc_stats = self.view_ctx.get_process_stats(namespec, identifier)
                    data.append({'row_type': ProcessRowTypes.INSTANCE_PROCESS, 'namespec': namespec,
                                 'application_name': info['group'], 'process_name': '',
                                 'identifier': identifier,
                                 'disabled': info['disabled'], 'startable': False, 'stoppable': False,
                                 'statename': info['statename'], 'statecode': info['state'],
                                 'gravity': 'FATAL' if crashed else info['statename'],
                                 'has_crashed': info['has_crashed'],
                                 'running_identifiers': [identifier],  # used for button but not necessarily running
                                 'description': info['description'],
                                 'main': False, 'nb_items': 0,
                                 'expected_load': process.rules.expected_load,
                                 'nb_cores': nb_cores, 'proc_stats': proc_stats,
                                 'has_stdout': process.has_stdout(identifier),
                                 'has_stderr': process.has_stderr(identifier)})
        # re-arrange data using alphabetical order
        return sorted(data, key=lambda x: (x['namespec'], -x['row_type'].value, x['identifier']))

    def write_process_table(self, contents_elt, data: PayloadList):
        """ Rendering of the application processes managed through Supervisor.

        :param contents_elt: the root element of the page.
        :param data: the process data to be displayed.
        :return: None.
        """
        table_elt = contents_elt.findmeld('table_mid')
        if data:
            self.write_process_global_shex(table_elt)
            # remove stats columns if statistics are disabled
            self.write_common_process_table(table_elt)
            # loop on all processes
            shaded_proc_tr, shaded_detail_tr = False, False  # used to invert background style
            for tr_elt, info in table_elt.findmeld('tr_mid').repeat(data):
                # write common status (shared between this application view and node view)
                self.write_common_process_status(tr_elt, info)
                # print process name and running instances
                self.write_process(tr_elt, info)
                # specific updates
                if info['row_type'] == ProcessRowTypes.INSTANCE_PROCESS:
                    # remove shex td
                    tr_elt.findmeld('shex_td_mid').replace('')
                    # set line background and invert
                    apply_shade(tr_elt, shaded_detail_tr)
                    shaded_detail_tr = not shaded_detail_tr
                elif info['row_type'] == ProcessRowTypes.APPLICATION_PROCESS:
                    # print process shex
                    self.write_process_shex(tr_elt, info, shaded_proc_tr)
                    # set line background and invert
                    apply_shade(tr_elt, shaded_proc_tr)
                    shaded_proc_tr = not shaded_proc_tr
                    shaded_detail_tr = shaded_proc_tr
        else:
            table_elt.replace('No programs to display')

    def write_process_global_shex(self, table_elt) -> None:
        """ Write global shrink / expand buttons.

        :param table_elt: the process table element.
        :return: None.
        """
        shex = self.view_ctx.process_shex
        expand_shex = self.view_ctx.get_default_process_shex(self.application_name, True)
        shrink_shex = self.view_ctx.get_default_process_shex(self.application_name, False)
        self.write_global_shex(table_elt, PROC_SHRINK_EXPAND, shex, expand_shex, shrink_shex)

    def write_process_shex(self, tr_elt, info: Payload, shaded_tr: bool):
        """ Write the application process section into a table. """
        elt = tr_elt.findmeld('shex_td_mid')
        process_name = info['process_name']
        process_shex, inverted_shex = self.view_ctx.get_process_shex(process_name)
        self.logger.trace(f'ApplicationView.write_process_shex: process_name={process_name}'
                          f' process_shex={process_shex} inverted_shex={inverted_shex}')
        if process_shex:
            elt.attrib['rowspan'] = str(info['nb_items'] + 1)
            apply_shade(elt, shaded_tr)
        elt = elt.findmeld('shex_a_mid')
        elt.content(f'{SHEX_SHRINK if process_shex else SHEX_EXPAND}')
        url = self.view_ctx.format_url('', self.page_name, **{PROC_SHRINK_EXPAND: inverted_shex})
        elt.attributes(href=url)

    def write_process(self, tr_elt, info):
        """ Rendering of the cell corresponding to the process running instances. """
        running_a_elt = tr_elt.findmeld('running_a_mid')
        running_identifiers = info['running_identifiers']
        if len(running_identifiers) == 0:
            # no running instance: empty cell
            running_a_elt.replace('')
        else:
            running_span_elt = running_a_elt.findmeld('running_span_mid')
            if len(running_identifiers) == 1:
                # one running instance: use button to navigate to the process page
                identifier = running_identifiers[0]
                nick_identifier = self.supvisors.mapper.get_nick_identifier(identifier)
                running_span_elt.content(nick_identifier)
                url = self.view_ctx.format_url(identifier, PROC_INSTANCE_PAGE)
                running_a_elt.attributes(href=url)
            else:
                # multiple running instances: conflict
                running_span_elt.content('Conciliate')
                update_attrib(running_span_elt, 'class', 'blink')
                url = self.view_ctx.format_url('', CONCILIATION_PAGE)
                running_a_elt.attributes(href=url)

    # ACTIONS
    def make_callback(self, namespec: str, action: str):
        """ Triggers processing iaw action requested. """
        if self.application:
            # get current strategy
            strategy = self.view_ctx.strategy
            if action == 'startapp':
                return self.start_application_action(strategy)
            if action == 'stopapp':
                return self.stop_application_action()
            if action == 'restartapp':
                return self.restart_application_action(strategy)
            if namespec:
                if self.view_ctx.get_process_status(namespec) is None:
                    return delayed_error(f'No such process named {namespec}')
                if action == 'start':
                    return self.start_process_action(strategy, namespec)
                if action == 'stop':
                    return self.stop_process_action(namespec)
                if action == 'restart':
                    return self.restart_process_action(strategy, namespec)
                if action == 'clearlog':
                    return self.clearlog_process_action(namespec)
        return delayed_error('No application selected')

    # Application actions
    def start_application_action(self, strategy: StartingStrategies) -> Callable:
        """ Start the application iaw the strategy.
        The RPC wait parameter is linked to the auto-refresh parameter of the page.

        :param strategy: the strategy to apply for starting the application.
        :return: a callable for deferred result.
        """
        wait = not self.view_ctx.auto_refresh
        return self.supvisors_rpc_action('start_application', (strategy.value, self.application_name, wait),
                                         f'Application {self.application_name} started')

    def restart_application_action(self, strategy: StartingStrategies) -> Callable:
        """ Restart the application iaw the strategy.
        The RPC wait parameter is linked to the auto-refresh parameter of the page.

        :param strategy: the strategy to apply for restarting the application.
        :return: a callable for deferred result.
        """
        wait = not self.view_ctx.auto_refresh
        return self.supvisors_rpc_action('restart_application', (strategy.value, self.application_name, wait),
                                         f'Application {self.application_name} restarted')

    def stop_application_action(self) -> Callable:
        """ Stop the application.
        The RPC wait parameter is linked to the auto-refresh parameter of the page.

        :return: a callable for deferred result.
        """
        wait = not self.view_ctx.auto_refresh
        return self.supvisors_rpc_action('stop_application', (self.application_name, wait),
                                         f'Application {self.application_name} stopped')

    # Process actions
    def start_process_action(self, strategy: StartingStrategies, namespec: str) -> Callable:
        """ Start the process named namespec iaw the strategy.
        The RPC wait parameter is linked to the auto-refresh parameter of the page.

        :param strategy: the strategy to apply for starting the process.
        :param namespec: the process namespec.
        :return: a callable for deferred result.
        """
        wait = not self.view_ctx.auto_refresh
        return self.supvisors_rpc_action('start_process', (strategy.value, namespec, '', wait),
                                         f'Process {namespec} started')

    def restart_process_action(self, strategy: StartingStrategies, namespec: str) -> Callable:
        """ Restart the process named namespec iaw the strategy.
        The RPC wait parameter is linked to the auto-refresh parameter of the page.

        :param strategy: the strategy to apply for restarting the process.
        :param namespec: the process namespec.
        :return: a callable for deferred result.
        """
        wait = not self.view_ctx.auto_refresh
        return self.supvisors_rpc_action('restart_process', (strategy.value, namespec, '', wait),
                                         f'Process {namespec} restarted')

    def stop_process_action(self, namespec: str) -> Callable:
        """ Stop the process named namespec.
        The RPC wait parameter is linked to the auto-refresh parameter of the page.

        :param namespec: the process namespec.
        :return: a callable for deferred result.
        """
        wait = not self.view_ctx.auto_refresh
        return self.supvisors_rpc_action('stop_process', (namespec, wait), f'Process {namespec} stopped')

    def clearlog_process_action(self, namespec: str) -> Callable:
        """ Can't call supervisor StatusView source code from application view.
        Just do the same job.

        :param namespec: the process namespec.
        :return: a callable for deferred result.
        """
        return self.supervisor_rpc_action('clearProcessLogs', (namespec,), f'Log for {namespec} cleared')
