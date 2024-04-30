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

from typing import List

from supvisors.application import ApplicationStatus
from supvisors.instancestatus import SupvisorsInstanceStatus
from supvisors.strategy import conciliate_conflicts
from supvisors.ttypes import ConciliationStrategies, SupvisorsInstanceStates, SupvisorsStates, SynchronizationOptions
from supvisors.utils import simple_duration, simple_localtime
from .viewcontext import *
from .viewhandler import ViewHandler
from .webutils import *


class SupvisorsView(ViewHandler):
    """ Class ensuring the rendering of the Supvisors main page with:

        - a navigation menu towards Supvisors instances contents and applications,
        - the state of Supvisors,
        - actions on Supvisors,
        - a synoptic of the processes running on the different Supvisors instances,
        - in CONCILIATION state only, the synoptic is replaced by a table of conflicts with tools to solve them.
    """

    def __init__(self, context):
        """ Call of the superclass constructors. """
        ViewHandler.__init__(self, context)
        self.page_name: str = SUPVISORS_PAGE
        # get applicable conciliation strategies
        self.strategies: List[str] = [x.name.lower() for x in ConciliationStrategies]
        self.strategies.remove(ConciliationStrategies.USER.name.lower())
        # global actions (no parameter)
        self.global_methods = {'sup_sync': self.sup_sync_action,
                               'sup_restart': self.sup_restart_action,
                               'sup_shutdown': self.sup_shutdown_action}
        # process actions
        self.process_methods = {'pstop': self.stop_action,
                                'pkeep': self.keep_action}

    def write_navigation(self, root) -> None:
        """ Rendering of the navigation menu. """
        self.write_nav(root)

    def write_status(self, header_elt) -> None:
        """ Rendering of the header part of the Supvisors main page. """
        # set Supvisors state & modes
        state_modes = self.sup_ctx.get_state_modes()
        header_elt.findmeld('state_mid').content(state_modes['fsm_statename'])
        # set Supvisors modes
        for mid, attr in [('starting_mid', 'starting_jobs'), ('stopping_mid', 'stopping_jobs')]:
            elt = header_elt.findmeld(mid)
            if state_modes[attr]:
                update_attrib(elt, 'class', 'blink')
            else:
                elt.replace('')
        # write the Master nick identifier
        master_instance = self.sup_ctx.master_instance
        identifier = master_instance.supvisors_id.nick_identifier if master_instance else 'none'
        header_elt.findmeld('master_name_mid').content(identifier)

    def write_actions(self, header_elt) -> None:
        """ Write actions related to Supvisors. """
        super().write_actions(header_elt)
        # configure end of sync button
        elt = header_elt.findmeld('start_a_mid')
        url = self.view_ctx.format_url('', SUPVISORS_PAGE, **{ACTION: 'sup_sync'})
        elt.attributes(href=url)
        # configure restart button
        elt = header_elt.findmeld('restart_a_mid')
        url = self.view_ctx.format_url('', SUPVISORS_PAGE, **{ACTION: 'sup_restart'})
        elt.attributes(href=url)
        # configure shutdown button
        elt = header_elt.findmeld('shutdown_a_mid')
        url = self.view_ctx.format_url('', SUPVISORS_PAGE, **{ACTION: 'sup_shutdown'})
        elt.attributes(href=url)

    def write_contents(self, contents_elt) -> None:
        """ Rendering of the contents of the Supvisors main page.
        This builds either a synoptic of the processes running on the Supvisors instances or the table of conflicts. """
        if self.supvisors.fsm.state == SupvisorsStates.CONCILIATION and self.sup_ctx.conflicts():
            # remove Supvisors instances boxes
            contents_elt.findmeld('boxes_div_mid').replace('')
            # write conflicts
            self.write_conciliation_strategies(contents_elt)
            self.write_conciliation_table(contents_elt)
        else:
            # remove conflicts table
            contents_elt.findmeld('conflicts_div_mid').replace('')
            # write Supvisors instances boxes
            self.write_instance_boxes(contents_elt)

    # Standard part
    def _write_instance_box_title(self, instance_div_elt, status: SupvisorsInstanceStatus, user_sync: bool) -> None:
        """ Rendering of the Supvisors instance box title.

        :param instance_div_elt: the Supvisors instance box element.
        :param status: the Supvisors instance status.
        :param user_sync: True if the Supvisors is configured to let the user end the synchronization phase.
        :return: None
        """
        # remove the end_synchro button if appropriate
        th_elt = instance_div_elt.findmeld('user_sync_th_mid')
        elt = th_elt.findmeld('user_sync_a_mid')
        if user_sync:
            # fill the button with Supvisors star symbol
            elt.content('&#160;&#10026;&#160;')
            if status.state == SupvisorsInstanceStates.RUNNING:
                update_attrib(elt, 'class', 'on')
                url = self.view_ctx.format_url('', SUPVISORS_PAGE,
                                               **{IDENTIFIER: status.identifier, ACTION: 'sup_master_sync'})
                elt.attributes(href=url)
            else:
                update_attrib(elt, 'class', 'off')
        else:
            # remove the button cell and extend the next cell
            th_elt.replace('')
        # set Supvisors instance name
        elt = instance_div_elt.findmeld('identifier_a_mid')
        if status.has_active_state():
            # go to web page located hosted by the Supvisors instance
            url = self.view_ctx.format_url(status.identifier, PROC_INSTANCE_PAGE)
            elt.attributes(href=url)
            update_attrib(elt, 'class', 'on')
        else:
            update_attrib(elt, 'class', 'off')
        nick_identifier = status.supvisors_id.nick_identifier
        if status.identifier == self.sup_ctx.master_identifier:
            nick_identifier = f'{MASTER_SYMBOL} {nick_identifier}'
        elt.content(nick_identifier)
        # set Supvisors instance state
        elt = instance_div_elt.findmeld('state_th_mid')
        update_attrib(elt, 'class', status.state.name)
        elt.content(status.state.name)
        # set Supvisors instance current time
        elt = instance_div_elt.findmeld('time_th_mid')
        if status.has_active_state():
            remote_time = status.times.get_current_remote_time(self.current_mtime)
            elt.content(simple_localtime(remote_time))
        # set Supvisors instance current load
        elt = instance_div_elt.findmeld('percent_th_mid')
        elt.content(f'{status.get_load()}%')

    def _write_instance_box_applications(self, instance_div_elt, status: SupvisorsInstanceStatus, user_sync: bool):
        """ Rendering of the Supvisors instance box running processes. """
        appli_tr_mid = instance_div_elt.findmeld('appli_tr_mid')
        running_processes = status.running_processes()
        application_names = sorted({process.application_name for process in running_processes})
        if application_names:
            shaded_tr = False
            for appli_tr_elt, application_name in appli_tr_mid.repeat(application_names):
                # set row shading
                apply_shade(appli_tr_elt, shaded_tr)
                shaded_tr = not shaded_tr
                # write application element
                application = self.sup_ctx.applications[application_name]
                self._write_instance_box_application(appli_tr_elt, status.identifier, application, user_sync,
                                                     running_processes)
        else:
            # keep an empty line
            process_li_mid = appli_tr_mid.findmeld('process_li_mid')
            process_li_mid.replace('')

    def _write_instance_box_application(self, appli_tr_elt, identifier: str, application: ApplicationStatus,
                                        user_sync: bool, running_processes: List[ProcessStatus]):
        """ Rendering of the application in the Supvisors instance box running processes. """
        # set application name
        app_name_td_mid = appli_tr_elt.findmeld('app_name_td_mid')
        app_name_td_mid.content(application.application_name)
        if application.rules.managed:
            update_attrib(app_name_td_mid, 'class', 'on')
            parameters = {APPLI: application.application_name, IDENTIFIER: identifier,
                          STRATEGY: application.rules.starting_strategy.name}
            url = self.view_ctx.format_url(identifier, APPLICATION_PAGE, **parameters)
            app_name_td_mid.attributes(href=url)
        # group cells if the User sync button is displayed
        if user_sync:
            update_attrib(app_name_td_mid, 'colspan', '2')
        # set running process list
        process_li_mid = appli_tr_elt.findmeld('process_li_mid')
        processes = filter(lambda x: x.application_name == application.application_name,
                           running_processes)
        for li_elt, process in process_li_mid.repeat(processes):
            process_a_mid = li_elt.findmeld('process_a_mid')
            process_a_mid.content(process.process_name)
            # write link to process page with process statistics
            update_attrib(process_a_mid, 'class', 'on')
            parameters = {PROCESS: process.namespec, IDENTIFIER: identifier}
            url = self.view_ctx.format_url(identifier, PROC_INSTANCE_PAGE, **parameters)
            process_a_mid.attributes(href=url)

    def write_instance_boxes(self, root):
        """ Rendering of the Supvisors instance boxes. """
        instance_div_mid = root.findmeld('instance_div_mid')
        # check if user end of sync is allowed
        user_sync = (SynchronizationOptions.USER in self.supvisors.options.synchro_options
                     and self.supvisors.fsm.state == SupvisorsStates.INITIALIZATION
                     and not self.sup_ctx.master_identifier)
        # create a box for every Supvisors instances
        identifiers = list(self.supvisors.mapper.instances.keys())
        # in discovery mode, other Supvisors instances arrive randomly in every Supvisors instance
        # so let's sort them by name
        if self.supvisors.options.discovery_mode:
            identifiers = [status.identifier
                           for status in sorted(self.supvisors.mapper.instances.values(),
                                                key=lambda x: x.nick_identifier)]
        for instance_div_elt, identifier in instance_div_mid.repeat(identifiers):
            # get Supvisors instance status from Supvisors context
            status = self.sup_ctx.instances[identifier]
            # write box_title
            self._write_instance_box_title(instance_div_elt, status, user_sync)
            # fill with running processes
            self._write_instance_box_applications(instance_div_elt, status, user_sync)

    # Conciliation part
    def write_conciliation_strategies(self, root):
        """ Rendering of the global conciliation actions. """
        div_elt = root.findmeld('conflicts_div_mid')
        global_strategy_li_mid = div_elt.findmeld('global_strategy_li_mid')
        for li_elt, item in global_strategy_li_mid.repeat(self.strategies):
            elt = li_elt.findmeld('global_strategy_a_mid')
            # conciliation requests MUST be sent to MASTER and namespec MUST be reset
            master = self.sup_ctx.master_identifier
            parameters = {NAMESPEC: '', ACTION: item}
            url = self.view_ctx.format_url(master, SUPVISORS_PAGE, **parameters)
            elt.attributes(href=url)
            elt.content(item.title())

    def get_conciliation_data(self):
        """ Get information about all conflicting processes. """
        return [{'namespec': process.namespec,
                 'rowspan': len(process.running_identifiers) if idx == 0 else 0,
                 'identifier': identifier,
                 'uptime': process.info_map[identifier]['uptime']}
                for process in self.sup_ctx.conflicts()
                for idx, identifier in enumerate(sorted(process.running_identifiers))]

    def write_conciliation_table(self, root):
        """ Rendering of the conflicts table. """
        # get data for table
        data = self.get_conciliation_data()
        # get meld elements
        div_elt = root.findmeld('conflicts_div_mid')
        shaded_tr = True
        for tr_elt, item in div_elt.findmeld('tr_mid').repeat(data):
            # first get the rowspan and change shade when rowspan is 0 (first line of conflict)
            rowspan = item['rowspan']
            if rowspan:
                shaded_tr = not shaded_tr
            # set row background
            apply_shade(tr_elt, shaded_tr)
            # write information and actions
            self._write_conflict_name(tr_elt, item, shaded_tr)
            self._write_conflict_identifier(tr_elt, item)
            self._write_conflict_uptime(tr_elt, item)
            self._write_conflict_process_actions(tr_elt, item)
            self._write_conflict_strategies(tr_elt, item, shaded_tr)

    @staticmethod
    def _write_conflict_name(tr_elt, info, shaded_tr):
        """ In a conflicts table, write the process name in conflict. """
        elt = tr_elt.findmeld('name_td_mid')
        rowspan = info['rowspan']
        if rowspan > 0:
            namespec = info['namespec']
            elt.attrib['rowspan'] = str(rowspan)
            elt.content(namespec)
            # apply shade logic to td element too for background-image to work
            apply_shade(elt, shaded_tr)
        else:
            elt.replace('')

    def _write_conflict_identifier(self, tr_elt, info):
        """ In a conflicts table, write the Supvisors instance identifier where runs the process in conflict. """
        identifier = info['identifier']
        elt = tr_elt.findmeld('conflict_instance_a_mid')
        url = self.view_ctx.format_url(identifier, PROC_INSTANCE_PAGE)
        elt.attributes(href=url)
        elt.content(identifier)

    @staticmethod
    def _write_conflict_uptime(tr_elt, info):
        """ In a conflicts table, write the uptime of the process in conflict. """
        elt = tr_elt.findmeld('uptime_td_mid')
        elt.content(simple_duration(info['uptime']))

    def _write_conflict_process_actions(self, tr_elt, info):
        """ In a conflicts table, write the actions that can be requested on the process in conflict. """
        namespec = info['namespec']
        identifier = info['identifier']
        for action in self.process_methods.keys():
            elt = tr_elt.findmeld(action + '_a_mid')
            parameters = {NAMESPEC: namespec, IDENTIFIER: identifier, ACTION: action}
            url = self.view_ctx.format_url('', SUPVISORS_PAGE, **parameters)
            elt.attributes(href=url)

    def _write_conflict_strategies(self, tr_elt, info, shaded_tr):
        """ In a conflicts table, write the strategies that can be requested on the process in conflict. """
        # extract info
        namespec = info['namespec']
        rowspan = info['rowspan']
        # update element structure
        td_elt = tr_elt.findmeld('strategy_td_mid')
        if rowspan > 0:
            # apply shade logic to td element too for background-image to work
            apply_shade(td_elt, shaded_tr)
            # fill the strategies
            td_elt.attrib['rowspan'] = str(rowspan)
            strategy_iterator = td_elt.findmeld('local_strategy_li_mid').repeat(self.strategies)
            for li_elt, st_item in strategy_iterator:
                elt = li_elt.findmeld('local_strategy_a_mid')
                # conciliation requests MUST be sent to MASTER
                master = self.sup_ctx.master_identifier
                parameters = {NAMESPEC: namespec, ACTION: st_item}
                url = self.view_ctx.format_url(master, SUPVISORS_PAGE, **parameters)
                elt.attributes(href=url)
                elt.content(st_item.title())
        else:
            td_elt.replace('')

    def make_callback(self, namespec: str, action: str):
        """ Triggers processing iaw action requested. """
        # global actions (no parameter)
        if action in self.global_methods:
            return self.global_methods[action]()
        # strategy actions
        if action in self.strategies:
            return self.conciliation_action(namespec, action.upper())
        # process actions
        if action in self.process_methods:
            identifier = self.view_ctx.get_identifier()
            return self.process_methods[action](namespec, identifier)
        # user sync action
        if action == 'sup_master_sync':
            identifier = self.view_ctx.get_identifier()
            return self.sup_sync_action(identifier)

    def sup_sync_action(self, master_identifier: str = ''):
        """ Restart all Supervisor instances. """
        try:
            self.supvisors.supervisor_data.supvisors_rpc_interface.end_sync(master_identifier)
        except RPCError as e:
            return delayed_error(f'end_synchro: {e}')
        message = 'Supvisors end of sync requested'
        if master_identifier:
            message += f' with Master={master_identifier}'
        return delayed_warn(message)

    def sup_restart_action(self):
        """ Restart all Supervisor instances. """
        try:
            self.supvisors.supervisor_data.supvisors_rpc_interface.restart()
        except RPCError as e:
            return delayed_error(f'restart: {e}')
        return delayed_warn('Supvisors restart requested')

    def sup_shutdown_action(self):
        """ Stop all Supervisor instances. """
        try:
            self.supvisors.supervisor_data.supvisors_rpc_interface.shutdown()
        except RPCError as e:
            return delayed_error(f'shutdown: {e}')
        return delayed_warn('Supvisors shutdown requested')

    def stop_action(self, namespec: str, identifier: str) -> Callable:
        """ Stop the conflicting process. """
        # get running instances of process
        running_identifiers = self.sup_ctx.get_process(namespec).running_identifiers
        self.supvisors.rpc_handler.send_stop_process(identifier, namespec)

        def on_wait():
            if identifier in running_identifiers:
                return NOT_DONE_YET
            return info_message(f'process {namespec} stopped on {identifier}')

        on_wait.delay = 0.1
        return on_wait

    def keep_action(self, namespec: str, kept_identifier: str) -> Callable:
        """ Stop the conflicting processes excepted the one running on kept_identifier. """
        # get running instances of process
        running_identifiers = self.sup_ctx.get_process(namespec).running_identifiers
        # send stop requests based on copy but check on source
        identifiers = running_identifiers.copy()
        identifiers.remove(kept_identifier)
        for identifier in identifiers:
            self.supvisors.rpc_handler.send_stop_process(identifier, namespec)

        def on_wait():
            if len(running_identifiers) > 1:
                return NOT_DONE_YET
            return info_message(f'processes {namespec} stopped but on {kept_identifier}')

        on_wait.delay = 0.1
        return on_wait

    def conciliation_action(self, namespec, action):
        """ Performs the automatic conciliation to solve the conflicts. """
        if namespec:
            # conciliate only one process
            conciliate_conflicts(self.supvisors, ConciliationStrategies[action], [self.sup_ctx.get_process(namespec)])
            return delayed_info(f'{action} in progress for {namespec}')
        else:
            # conciliate all conflicts
            conciliate_conflicts(self.supvisors, ConciliationStrategies[action], self.sup_ctx.conflicts())
            return delayed_info(f'{action} in progress for all conflicts')
