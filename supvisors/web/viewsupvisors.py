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
from supvisors.ttypes import SupvisorsInstanceStates, SupvisorsStates, SynchronizationOptions
from supvisors.utils import simple_localtime
from .viewcontext import *
from .viewmain import MainView
from .webutils import *


class SupvisorsView(MainView):
    """ Class ensuring the rendering of the Supvisors main page with:

        - a navigation menu towards Supvisors instances contents and applications,
        - the state of Supvisors,
        - actions on Supvisors,
        - a synoptic of the processes running on the different Supvisors instances.
    """

    def __init__(self, context):
        """ Call of the superclass constructors. """
        MainView.__init__(self, context)
        self.page_name: str = SUPVISORS_PAGE
        # global actions (no parameter)
        self.global_methods['sup_sync'] = self.sup_sync_action

    def write_actions(self, header_elt) -> None:
        """ Write actions related to Supvisors. """
        super().write_actions(header_elt)
        # configure end of sync button
        elt = header_elt.findmeld('start_a_mid')
        url = self.view_ctx.format_url('', SUPVISORS_PAGE, **{ACTION: 'sup_sync'})
        elt.attributes(href=url)

    def write_contents(self, contents_elt) -> None:
        """ Rendering of the contents of the Supvisors main page.
        This builds a synoptic of the processes running on the Supvisors instances. """
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
            # remove the button cell
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
        app_name_a_mid = app_name_td_mid.findmeld('app_name_a_mid')
        app_name_a_mid.content(application.application_name)
        if application.rules.managed:
            update_attrib(app_name_a_mid, 'class', 'on')
            parameters = {APPLI: application.application_name, IDENTIFIER: identifier,
                          STRATEGY: application.rules.starting_strategy.name}
            url = self.view_ctx.format_url(identifier, APPLICATION_PAGE, **parameters)
            app_name_a_mid.attributes(href=url)
        # group cells if the User sync button is displayed or remove the first cell
        if user_sync:
            update_attrib(app_name_td_mid, 'colspan', '2')
        # set running process list
        process_li_mid = appli_tr_elt.findmeld('process_li_mid')
        processes = filter(lambda x: x.application_name == application.application_name,
                           running_processes)
        for li_elt, process in process_li_mid.repeat(processes):
            process_a_mid = li_elt.findmeld('process_a_mid')
            process_span_mid = process_a_mid.findmeld('process_span_mid')
            process_span_mid.content(process.process_name)
            # write link to process page with process statistics
            update_attrib(process_a_mid, 'class', 'on')
            parameters = {PROCESS: process.namespec, IDENTIFIER: identifier}
            url = self.view_ctx.format_url(identifier, PROC_INSTANCE_PAGE, **parameters)
            process_a_mid.attributes(href=url)
            if process.conflicting() and application.rules.managed:
                update_attrib(process_span_mid, 'class', 'blink')

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

    def make_callback(self, namespec: str, action: str):
        """ Triggers processing iaw action requested. """
        # user sync action
        if action == 'sup_master_sync':
            identifier = self.view_ctx.identifier
            return self.sup_sync_action(identifier)
        # parent actions
        return super().make_callback(namespec, action)

    def sup_sync_action(self, master_identifier: str = ''):
        """ Restart all Supervisor instances. """
        try:
            self.supvisors.supervisor_data.supvisors_rpc_interface.end_sync(master_identifier)
        except RPCError as e:
            return delayed_error(f'end_synchro: {e}')
        message = 'Supvisors end of sync requested'
        if master_identifier:
            nick_identifier = self.supvisors.mapper.get_nick_identifier(master_identifier)
            message += f' with Master={nick_identifier}'
        return delayed_warn(message)
