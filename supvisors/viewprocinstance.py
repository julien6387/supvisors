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

from supervisor.options import make_namespec
from supervisor.states import ProcessStates, RUNNING_STATES
from supervisor.xmlrpc import RPCError

from .ttypes import Payload, PayloadList
from .viewcontext import *
from .viewsupstatus import SupvisorsInstanceView
from .webutils import *


class ProcInstanceView(SupvisorsInstanceView):
    """ View renderer of the Process section of the Supvisors Instance page.
    Inheritance is made from supervisor.web.StatusView to benefit from the action methods.
    Note that StatusView inheritance has been patched dynamically in supvisors.plugin.make_supvisors_rpcinterface
    so that StatusView inherits from ViewHandler instead of MeldView.
    """

    def __init__(self, context):
        """ Call of the superclass constructors. """
        SupvisorsInstanceView.__init__(self, context, PROC_INSTANCE_PAGE)

    # RIGHT SIDE / BODY part
    def write_contents(self, root):
        """ Rendering of the contents part of the page. """
        sorted_data, excluded_data = self.get_process_data()
        self.write_process_table(root, sorted_data)
        # check selected Process Statistics
        namespec = self.view_ctx.parameters[PROCESS]
        if namespec:
            status = self.view_ctx.get_process_status(namespec)
            if not status or self.view_ctx.local_identifier not in status.running_identifiers:
                self.logger.warn(f'ProcInstanceView.write_contents: unselect Process Statistics for {namespec}')
                # form parameter is not consistent. remove it
                self.view_ctx.parameters[PROCESS] = ''
        # write selected Process Statistics
        namespec = self.view_ctx.parameters[PROCESS]
        info = next(filter(lambda x: x['namespec'] == namespec, sorted_data + excluded_data), {})
        self.write_process_statistics(root, info)

    def get_process_data(self) -> Tuple[PayloadList, PayloadList]:
        """ Collect sorted data on processes.
        The sorted data are meant to be displayed in the process table.
        The excluded data are not but may be used for process statistics selection.

        :return: the sorted data and the excluded data.
        """
        # use Supervisor to get local information on all processes
        rpc_intf = self.supvisors.supervisor_data.supervisor_rpc_interface
        try:
            all_info = rpc_intf.getAllProcessInfo()
        except RPCError as e:
            self.logger.warn(f'ProcInstanceView.get_process_data: failed to get all process info'
                             f' from {self.local_identifier}: {e.text}')
            return [], []
        # extract what is useful to display
        data = []
        for info in all_info:
            namespec = make_namespec(info['group'], info['name'])
            process = self.sup_ctx.get_process(namespec)
            unexpected_exit = info['state'] == ProcessStates.EXITED and 'Bad exit code' in info['spawnerr']
            expected_load = process.rules.expected_load
            nb_cores, proc_stats = self.view_ctx.get_process_stats(namespec)
            payload = {'application_name': info['group'], 'process_name': info['name'], 'namespec': namespec,
                       'single': info['group'] == info['name'], 'identifier': self.view_ctx.local_identifier,
                       'statename': info['statename'], 'statecode': info['state'],
                       'gravity': 'FATAL' if unexpected_exit else info['statename'],
                       'description': info['description'], 'expected_load': expected_load,
                       'nb_cores': nb_cores, 'proc_stats': proc_stats}
            data.append(payload)
        # re-arrange data
        return self.sort_data(data)

    def sort_data(self, data: PayloadList) -> Tuple[PayloadList, PayloadList]:
        """ This method sorts a process list by application and using the alphabetical order.
        Processes belonging to an application may be removed, depending on the shex user selection.

        :param data: a list of process payloads
        :return: the sorted list and the excluded list.
        """
        sorted_data, excluded_data = [], []
        # sort processes by application
        application_map = {}
        for info in data:
            application_map.setdefault(info['application_name'], []).append(info)
        # sort applications alphabetically
        for application_name, application_processes in sorted(application_map.items()):
            single = len(application_processes) == 1 and application_processes[0]['single']
            application_shex = True
            if not single:
                # add entry for application
                sorted_data.append(self.get_application_summary(application_name, application_processes))
                # filter data depending on their application shex
                application_shex, _ = self.view_ctx.get_application_shex(application_name)
            if application_shex:
                # add processes using the alphabetical ordering
                sorted_list = sorted([info for info in application_processes], key=lambda x: x['process_name'])
                sorted_data.extend(sorted_list)
            else:
                # push to excluded data
                excluded_data.extend(application_processes)
        return sorted_data, excluded_data

    def get_application_summary(self, application_name: str, application_processes: PayloadList) -> Payload:
        """ Get a summary of the application based on a subset of its processes.

        :param application_name: the name of the application
        :param application_processes: the subset of the application processes running on the same node
        :return: the application payload to be displayed
        """
        application = self.sup_ctx.applications[application_name]
        expected_load, nb_cores, appli_stats = 0, 0, [[0], [0]]
        reset = True
        for proc in application_processes:
            if proc['statecode'] in RUNNING_STATES:
                expected_load = expected_load + proc['expected_load']
                nb_cores = proc.get('nb_cores', 0)
                # sum CPU / Mem stats
                proc_stats = proc.get('proc_stats')
                if proc_stats:
                    if len(proc_stats[0]) > 0 and len(proc_stats[1]) > 0:
                        reset = False
                        appli_stats[0][0] = appli_stats[0][0] + proc_stats[0][-1]
                        appli_stats[1][0] = appli_stats[1][0] + proc_stats[1][-1]
        # reset appli_stats if no process involved
        if reset:
            appli_stats = None
        payload = {'application_name': application_name, 'process_name': None, 'namespec': None,
                   'identifier': self.view_ctx.local_identifier,
                   'statename': application.state.name, 'statecode': application.state.value,
                   'description': application.get_operational_status(),
                   'nb_processes': len(application_processes), 'expected_load': expected_load}
        payload.update({'nb_cores': nb_cores, 'proc_stats': appli_stats})
        return payload

    def write_process_table(self, root, data: PayloadList):
        """ Rendering of the processes managed through Supervisor. """
        if data:
            self.write_common_process_table(root)
            # loop on all processes
            iterator = root.findmeld('tr_mid').repeat(data)
            shaded_appli_tr, shaded_proc_tr = False, False  # used to invert background style
            for tr_elt, info in iterator:
                if info['process_name']:
                    # this is a process row
                    elt = tr_elt.findmeld('shex_td_mid')
                    if info['single']:
                        # single line background follows the same logic as applications
                        apply_shade(tr_elt, shaded_appli_tr)
                        shaded_appli_tr = not shaded_appli_tr
                    else:
                        # remove shex td
                        elt.replace('')
                        # set line background and invert
                        apply_shade(tr_elt, shaded_proc_tr)
                        shaded_proc_tr = not shaded_proc_tr
                    # write common status (shared between this process view and application view)
                    self.write_common_process_status(tr_elt, info)
                else:
                    # this is an application row
                    # force next proc shade
                    shaded_proc_tr = not shaded_appli_tr
                    # write application status
                    self.write_application_status(tr_elt, info, shaded_appli_tr)
                    # set line background and invert
                    apply_shade(tr_elt, shaded_appli_tr)
                    shaded_appli_tr = not shaded_appli_tr
        else:
            table = root.findmeld('table_mid')
            table.replace('No programs to manage')

    def write_application_status(self, tr_elt, info, shaded_tr):
        """ Write the application section into a table. """
        application_name = info['application_name']
        # print common status
        self.write_common_status(tr_elt, info)
        # print application shex
        elt = tr_elt.findmeld('shex_td_mid')
        application_shex, inverted_shex = self.view_ctx.get_application_shex(application_name)
        if application_shex:
            elt.attrib['rowspan'] = str(info['nb_processes'] + 1)
            apply_shade(elt, shaded_tr)
        elt = elt.findmeld('shex_a_mid')
        self.logger.trace(f'ProcInstanceView.write_application_status: application_name={application_name}'
                          f' application_shex={application_shex} inverted_shex={inverted_shex}')
        elt.content('{}'.format('[\u2013]' if application_shex else '[+]'))
        url = self.view_ctx.format_url('', self.page_name, **{SHRINK_EXPAND: inverted_shex})
        elt.attributes(href=url)
        # print application name
        elt = tr_elt.findmeld('name_a_mid')
        elt.content(application_name)
        url = self.view_ctx.format_url('', APPLICATION_PAGE, **{APPLI: application_name})
        elt.attributes(href=url)
        # remove all actions
        for mid in ['start_td_mid', 'clear_td_mid']:
            elt = tr_elt.findmeld(mid)
            elt.attrib['colspan'] = '3'
            elt.content('')
        for mid in ['stop_td_mid', 'restart_td_mid', 'tailout_td_mid', 'tailerr_td_mid']:
            tr_elt.findmeld(mid).replace('')
