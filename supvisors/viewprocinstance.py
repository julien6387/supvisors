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

from supervisor.states import RUNNING_STATES
from supervisor.xmlrpc import RPCError

from .application import ApplicationStatus
from .instancestatus import SupvisorsInstanceStatus
from .ttypes import Payload, PayloadList, ProcessHistoryStats
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
        self.write_process_table(root, sorted_data, excluded_data)
        # check selected Process Statistics
        namespec = self.view_ctx.parameters[PROCESS]
        if namespec and namespec != 'supervisord':
            # unselect if not running in this Supvisors instance
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
        # extract what is useful to display
        status: SupvisorsInstanceStatus = self.sup_ctx.instances[self.view_ctx.local_identifier]
        data = []
        for namespec, process in status.processes.items():
            expected_load = process.rules.expected_load
            application: ApplicationStatus = self.sup_ctx.applications[process.application_name]
            # a 'single' process has the same name as its application and the application contains only one process
            single = process.process_name == process.application_name and len(application.processes) == 1
            info = process.info_map[self.view_ctx.local_identifier]
            crashed = ProcessStatus.is_crashed_event(info['state'], info['expected'])
            nb_cores, proc_stats = self.view_ctx.get_process_stats(namespec)
            payload = {'application_name': info['group'], 'process_name': info['name'], 'namespec': namespec,
                       'single': single, 'identifier': self.view_ctx.local_identifier,
                       'statename': info['statename'], 'statecode': info['state'],
                       'gravity': 'FATAL' if crashed else info['statename'], 'has_crashed': info['has_crashed'],
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
        # add supervisord payload at the end
        nb_cores, proc_stats = self.view_ctx.get_process_stats('supervisord')
        payload = {'application_name': 'supervisord', 'process_name': 'supervisord', 'namespec': 'supervisord',
                   'single': True, 'identifier': self.view_ctx.local_identifier,
                   'statename': 'RUNNING', 'statecode': 20, 'gravity': 'RUNNING', 'has_crashed': False,
                   'description': f'Supervisor {self.view_ctx.local_identifier}', 'expected_load': 0,
                   'nb_cores': nb_cores, 'proc_stats': proc_stats}
        sorted_data.append(payload)
        return sorted_data, excluded_data

    def get_application_summary(self, application_name: str, application_processes: PayloadList) -> Payload:
        """ Get a summary of the application based on a subset of its processes.

        :param application_name: the name of the application
        :param application_processes: the subset of the application processes running on the same node
        :return: the application payload to be displayed
        """
        expected_load, nb_cores, appli_stats = self.sum_process_info(application_processes)
        # create application payload
        application = self.sup_ctx.applications[application_name]
        payload = {'application_name': application_name, 'process_name': None, 'namespec': None,
                   'identifier': self.view_ctx.local_identifier,
                   'statename': application.state.name, 'statecode': application.state.value,
                   'gravity': application.state.name, 'has_crashed': False,
                   'description': application.get_operational_status(),
                   'nb_processes': len(application_processes), 'expected_load': expected_load,
                   'nb_cores': nb_cores, 'proc_stats': appli_stats}
        return payload

    @staticmethod
    def sum_process_info(data: PayloadList) -> Tuple[int, int, Optional[ProcessHistoryStats]]:
        """ Get the total resources taken by the processes.

        :param data: the list of process payloads
        :return: the total expected load, number of processor cores, memory and CPU
        """
        expected_load, nb_cores, cpu, mem = 0, 0, 0, 0
        reset = True
        for info in data:
            if info['statecode'] in RUNNING_STATES:
                expected_load += info['expected_load']
                nb_cores = info['nb_cores']
                # sum CPU / Mem stats
                proc_stats = info['proc_stats']
                if proc_stats:
                    if len(proc_stats[0]) and len(proc_stats[1]):
                        reset = False
                        # the most recent value is at the end of the list
                        cpu += proc_stats[0][-1]
                        mem += proc_stats[1][-1]
        # reset appli_stats if no process involved
        # keep output similar to process stats
        appli_stats = None if reset else [[cpu], [mem]]
        return expected_load, nb_cores, appli_stats

    def write_process_table(self, root, sorted_data: PayloadList, excluded_data: PayloadList) -> None:
        """ Rendering of the processes managed in Supervisor.

        :param root: the root element of the page
        :param sorted_data: the process data displayed
        :param excluded_data: the process data not displayed
        :return: None
        """
        table_elt = root.findmeld('table_mid')
        if sorted_data:
            self.write_global_shex(table_elt)
            # remove stats columns if statistics are disabled
            self.write_common_process_table(table_elt)
            # loop on all processes
            iterator = table_elt.findmeld('tr_mid').repeat(sorted_data)
            shaded_appli_tr, shaded_proc_tr = False, False  # used to invert background style
            for tr_elt, info in iterator:
                if info['process_name']:
                    # this is a process row
                    if info['single']:
                        # single line background follows the same logic as applications
                        apply_shade(tr_elt, shaded_appli_tr)
                        shaded_appli_tr = not shaded_appli_tr
                    else:
                        # remove shex td
                        tr_elt.findmeld('shex_td_mid').replace('')
                        # set line background and invert
                        apply_shade(tr_elt, shaded_proc_tr)
                        shaded_proc_tr = not shaded_proc_tr
                    # supervisord line is a bit different
                    if info['process_name'] == 'supervisord':
                        self.write_supervisord_status(tr_elt, info)
                    else:
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
            # writes the total statistics line
            self.write_total_status(table_elt, sorted_data, excluded_data)
        else:
            table_elt.replace('No programs to manage')

    def write_global_shex(self, table_elt) -> None:
        """ Write global shrink / expand buttons.

        :param table_elt: the table element
        :return: None
        """
        shex = self.view_ctx.parameters[SHRINK_EXPAND]
        expand_shex = self.view_ctx.get_default_shex(True)
        shrink_shex = self.view_ctx.get_default_shex(False)
        # write expand button
        elt = table_elt.findmeld('expand_a_mid')
        if shex == expand_shex.hex():
            elt.replace('')
        else:
            elt.content(f'{SHEX_EXPAND}')
            url = self.view_ctx.format_url('', self.page_name, **{SHRINK_EXPAND: expand_shex.hex()})
            elt.attributes(href=url)
        # write shrink button
        elt = table_elt.findmeld('shrink_a_mid')
        if shex == shrink_shex.hex():
            elt.replace('')
        else:
            elt.content(f'{SHEX_SHRINK}')
            url = self.view_ctx.format_url('', self.page_name, **{SHRINK_EXPAND: shrink_shex.hex()})
            elt.attributes(href=url)

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
        elt.content(f'{SHEX_SHRINK if application_shex else SHEX_EXPAND}')
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

    def write_supervisord_status(self, tr_elt, info: Payload) -> None:
        """ Write the supervisord status into a table. """
        # display Master symbol in shex column
        if self.sup_ctx.is_master:
            elt = tr_elt.findmeld('shex_td_mid')
            elt.content(MASTER_SYMBOL)
        # print common status
        self.write_common_status(tr_elt, info)
        # print process name
        elt = tr_elt.findmeld('name_a_mid')
        elt.content(info['process_name'])
        url = self.view_ctx.format_url('', MAIN_TAIL_PAGE, **{PROCESS: info['namespec']})
        elt.attributes(href=url, target="_blank")
        # manage actions
        self.write_supervisord_button(tr_elt, 'stop_a_mid', self.page_name, **{ACTION: 'shutdownsup'})
        self.write_supervisord_button(tr_elt, 'restart_a_mid', self.page_name, **{ACTION: 'restartsup'})
        # manage log actions
        self.write_supervisord_button(tr_elt, 'clear_a_mid', self.page_name, **{ACTION: 'mainclearlog'})
        self.write_supervisord_button(tr_elt, 'tailout_a_mid', MAIN_STDOUT_PAGE)
        # start and tail stderr are not applicable
        tr_elt.findmeld('start_a_mid').content('')
        tr_elt.findmeld('tailerr_a_mid').content('')

    def write_supervisord_button(self, tr_elt, mid: str, page: str, **action) -> None:
        """ Write the configuration of the button of supervisord. """
        elt = tr_elt.findmeld(mid)
        update_attrib(elt, 'class', 'button on')
        url = self.view_ctx.format_url('', page, **action)
        elt.attributes(href=url)

    def write_total_status(self, table_elt, sorted_data: PayloadList, excluded_data: PayloadList):
        """ Write the total statistics for this Supvisors instance.

        :param table_elt: the table element
        :param sorted_data: the process data displayed
        :param excluded_data: the process data not displayed
        :return: None
        """
        tr_elt = table_elt.findmeld('total_mid')
        if tr_elt is not None:
            # element may have been removed due to stats option disabled
            # sum MEM and CPU stats of all processes
            expected_load, nb_cores, appli_stats = self.sum_process_info(sorted_data + excluded_data)
            # update Load
            elt = tr_elt.findmeld('load_total_th_mid')
            elt.content(f'{expected_load}%')
            if appli_stats:
                # update MEM
                elt = tr_elt.findmeld('mem_total_th_mid')
                elt.content(f'{appli_stats[1][0]:.2f}%')
                # update CPU
                elt = tr_elt.findmeld('cpu_total_th_mid')
                cpuvalue = appli_stats[0][0]
                if not self.supvisors.options.stats_irix_mode:
                    cpuvalue /= nb_cores
                elt.content(f'{cpuvalue:.2f}%')

    # ACTION part
    def make_callback(self, namespec, action):
        """ Triggers processing iaw action requested """
        if action == 'mainclearlog':
            return self.clear_log_action()
        return super().make_callback(namespec, action)

    def clear_log_action(self):
        """ Clear the log of Supervisor. """
        rpc_intf = self.supvisors.supervisor_data.supervisor_rpc_interface
        try:
            rpc_intf.clearLog()
        except RPCError as e:
            return delayed_error(f'clearLog: {e.text}')
        return delayed_info('Log for Supervisor cleared')
