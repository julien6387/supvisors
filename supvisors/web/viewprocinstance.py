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

import os

from supervisor.states import ProcessStates, RUNNING_STATES

from supvisors.application import ApplicationStatus
from supvisors.instancestatus import SupvisorsInstanceStatus
from supvisors.statscompiler import ProcStatisticsInstance
from supvisors.ttypes import SupvisorsFaults, Payload, PayloadList, ProcessCPUHistoryStats, ProcessMemHistoryStats
from .viewcontext import *
from .viewinstance import SupvisorsInstanceView
from .webutils import *


class ProcInstanceView(SupvisorsInstanceView):
    """ View renderer of the Process section of the Supvisors Instance page.
    Inheritance is made from supervisor.web.StatusView to benefit from the action methods.
    Note that StatusView inheritance has been patched dynamically in supvisors.plugin.make_supvisors_rpcinterface
    so that StatusView inherits from ViewHandler instead of MeldView.
    """

    ProcessStats = Tuple[int, int, Optional[Tuple[ProcessCPUHistoryStats, ProcessMemHistoryStats]]]

    def __init__(self, context):
        """ Call of the superclass constructors. """
        SupvisorsInstanceView.__init__(self, context, PROC_INSTANCE_PAGE)

    def write_periods(self, root):
        """ Write configured periods for statistics. """
        self.write_periods_availability(root, self.has_process_statistics)

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
            crashed = ProcessStatus.is_crashed_event(info)
            nb_cores, proc_stats = self.view_ctx.get_process_stats(namespec)
            payload = {'application_name': info['group'], 'process_name': info['name'], 'namespec': namespec,
                       'single': single, 'identifier': self.view_ctx.local_identifier,
                       'disabled': info['disabled'], 'startable': not info['disabled'],
                       'statename': info['statename'], 'statecode': info['state'],
                       'gravity': 'FATAL' if crashed else info['statename'], 'has_crashed': info['has_crashed'],
                       'description': info['description'], 'expected_load': expected_load,
                       'nb_cores': nb_cores, 'proc_stats': proc_stats}
            data.append(payload)
        # re-arrange data
        sorted_data, excluded_data = self.sort_data(data)
        # add supervisord payload at the end of sorted data
        sorted_data.append(self.get_supervisord_data(status))
        return sorted_data, excluded_data

    def get_supervisord_data(self, status: SupvisorsInstanceStatus) -> Payload:
        """ Collect sorted data on supervisord process.

        :param status: the local Supvisors instance
        :return: the supervisord data.
        """
        nb_cores, proc_stats = self.view_ctx.get_process_stats('supervisord')
        payload = {'application_name': 'supervisord', 'process_name': 'supervisord', 'namespec': 'supervisord',
                   'single': True, 'identifier': self.view_ctx.local_identifier, 'disabled': False, 'startable': False,
                   'statename': 'RUNNING', 'statecode': 20, 'gravity': 'RUNNING', 'has_crashed': False,
                   'expected_load': 0, 'nb_cores': nb_cores, 'proc_stats': proc_stats}
        # add description (pid / uptime) as done by Supervisor
        info = {'state': ProcessStates.RUNNING, 'start': status.start_time, 'now': status.local_time,
                'pid': os.getpid()}
        payload['description'] = ProcessStatus.update_description(info)
        return payload

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
        expected_load, nb_cores, appli_stats = self.sum_process_info(application_processes)
        # create application payload
        application = self.sup_ctx.applications[application_name]
        payload = {'application_name': application_name, 'process_name': None, 'namespec': None,
                   'identifier': self.view_ctx.local_identifier, 'disabled': False, 'startable': False,
                   'statename': application.state.name, 'statecode': application.state.value,
                   'gravity': application.state.name, 'has_crashed': False,
                   'description': application.get_operational_status(),
                   'nb_processes': len(application_processes), 'expected_load': expected_load,
                   'nb_cores': nb_cores, 'proc_stats': appli_stats}
        return payload

    @staticmethod
    def sum_process_info(data: PayloadList) -> ProcessStats:
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
                    if len(proc_stats.cpu) and len(proc_stats.mem):
                        reset = False
                        # the most recent value is at the end of the list
                        cpu += proc_stats.cpu[-1]
                        mem += proc_stats.mem[-1]
        # reset appli_stats if no process involved
        # keep output similar to process stats
        appli_stats = None
        if not reset:
            appli_stats = ProcStatisticsInstance()
            appli_stats.cpu = [cpu]
            appli_stats.mem = [mem]
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
        # print application name (covers state and description)
        elt = tr_elt.findmeld('name_td_mid')
        elt.attrib['colspan'] = '3'
        elt = elt.findmeld('name_a_mid')
        elt.content(application_name)
        url = self.view_ctx.format_url('', APPLICATION_PAGE, **{APPLI: application_name})
        elt.attributes(href=url)
        for mid in ['state_td_mid', 'desc_td_mid']:
            tr_elt.findmeld(mid).replace('')
        # print application statistics
        self.write_common_statistics(tr_elt, info)
        # start / stop / restart group actions
        self._write_process_button(tr_elt, 'start_a_mid', '', self.page_name, 'startgroup', f'{application_name}:')
        self._write_process_button(tr_elt, 'stop_a_mid', '', self.page_name, 'stopgroup', f'{application_name}:')
        self._write_process_button(tr_elt, 'restart_a_mid', '', self.page_name, 'restartgroup', f'{application_name}:')
        # remove log actions
        elt = tr_elt.findmeld('clear_td_mid')
        elt.attrib['colspan'] = '3'
        elt.content('')
        for mid in ['tailout_td_mid', 'tailerr_td_mid']:
            tr_elt.findmeld(mid).replace('')

    def write_supervisord_status(self, tr_elt, info: Payload) -> None:
        """ Write the supervisord status into a table. """
        # display Master symbol in shex column
        if self.sup_ctx.is_master:
            elt = tr_elt.findmeld('shex_td_mid')
            elt.content(MASTER_SYMBOL)
        # print process name
        elt = tr_elt.findmeld('name_a_mid')
        elt.content(info['process_name'])
        url = self.view_ctx.format_url('', MAIN_TAIL_PAGE, **{PROCESS: info['namespec'],
                                                              LIMIT: self.supvisors.options.tail_limit})
        elt.attributes(href=url, target="_blank")
        # print common status
        self.write_common_state(tr_elt, info)
        self.write_common_statistics(tr_elt, info)
        # manage actions
        self._write_supervisord_button(tr_elt, 'stop_a_mid', self.page_name, **{ACTION: 'shutdownsup'})
        self._write_supervisord_button(tr_elt, 'restart_a_mid', self.page_name, **{ACTION: 'restartsup'})
        # manage log actions
        self._write_supervisord_button(tr_elt, 'clear_a_mid', self.page_name, **{ACTION: 'mainclearlog'})
        self._write_supervisord_button(tr_elt, 'tailout_a_mid', MAIN_STDOUT_PAGE)
        # start and tail stderr are not applicable
        self._write_supervisord_off_button(tr_elt, 'start_a_mid')
        self._write_supervisord_off_button(tr_elt, 'tailerr_a_mid')

    def _write_supervisord_button(self, tr_elt, mid: str, page: str, **action) -> None:
        """ Write the configuration of the button of supervisord. """
        elt = tr_elt.findmeld(mid)
        update_attrib(elt, 'class', 'button on')
        url = self.view_ctx.format_url('', page, **action)
        elt.attributes(href=url)

    @staticmethod
    def _write_supervisord_off_button(tr_elt, mid: str) -> None:
        """ Write the configuration of the button of supervisord. """
        elt = tr_elt.findmeld(mid)
        update_attrib(elt, 'class', 'button off')

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
                elt.content(f'{appli_stats.mem[0]:.2f}%')
                # update CPU
                elt = tr_elt.findmeld('cpu_total_th_mid')
                cpu_value = appli_stats.cpu[0]
                if not self.supvisors.options.stats_irix_mode:
                    cpu_value /= nb_cores
                elt.content(f'{cpu_value:.2f}%')

    # ACTION part
    def make_callback(self, namespec, action):
        """ Triggers processing iaw action requested """
        if action == 'startgroup':
            return self.start_group_action(namespec)
        if action == 'stopgroup':
            return self.stop_group_action(namespec)
        if action == 'restartgroup':
            return self.restart_group_action(namespec)
        if action == 'mainclearlog':
            return self.clear_log_action()
        result = super().make_callback(namespec, action)
        # WARN: this ugly part is necessary to handle the DISABLED exception that can be raised from Supervisor
        #  startProcess. It is not possible to patch Supervisor make_callback without copying a huge piece of source
        #  code from Supervisor, so here is an inspection of the make_callback result to check for a callable declaring
        #  an 'unexpected rpc fault [103]'
        if callable(result):
            message = result()
            if type(message) is str and f'[{SupvisorsFaults.DISABLED.value}]' in message:
                return delayed_error(f'Process {namespec}: disabled')
        return result

    def start_group_action(self, namespec: str) -> Callable:
        """ Start all processes in the group.
        The RPC wait parameter is linked to the auto-refresh parameter of the page.

        :param namespec: the group processes that have to be started (expecting a form like 'group:*')
        :return: a callable for deferred result
        """
        self.logger.debug(f'ProcInstanceView.start_group_action: group_name={namespec}')
        wait = not self.view_ctx.parameters[AUTO]
        return self.supervisor_rpc_action('startProcess', (f'{namespec}', wait), f'Group {namespec} started')

    def stop_group_action(self, namespec: str) -> Callable:
        """ Stop all processes in the group.
        The RPC wait parameter is linked to the auto-refresh parameter of the page.

        :param namespec: the group processes that have to be stopped (expecting a form like 'group:*')
        :return: a callable for deferred result
        """
        self.logger.debug(f'ProcInstanceView.stop_group_action: group_name={namespec}')
        wait = not self.view_ctx.parameters[AUTO]
        return self.supervisor_rpc_action('stopProcess', (f'{namespec}', wait), f'Group {namespec} stopped')

    def restart_group_action(self, namespec: str) -> Callable:
        """ Start all processes in the group.
        The RPC wait parameter is linked to the auto-refresh parameter of the page and set only on the last call.

        :param namespec: the group processes that have to be restarted (expecting a form like 'group:*')
        :return: a callable for deferred result
        """
        self.logger.debug(f'ProcInstanceView.restart_group_action: group_name={namespec}')
        wait = not self.view_ctx.parameters[AUTO]
        multicall = [{'methodName': 'supervisor.stopProcess', 'params': [f'{namespec}']},
                     {'methodName': 'supervisor.startProcess', 'params': [f'{namespec}', wait]}]
        return self.multicall_rpc_action(multicall, f'Group {namespec} restarted')

    def clear_log_action(self) -> Callable:
        """ Clear the log of Supervisor.

        :return: a callable for deferred result
        """
        return self.supervisor_rpc_action('clearLog', (), 'Log for Supervisor cleared')
