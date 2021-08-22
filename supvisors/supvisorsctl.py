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

import errno
import socket

from supervisor import xmlrpc
from supervisor.compat import xmlrpclib
from supervisor.loggers import getLevelNumByDescription, LOG_LEVELS_BY_NUM
from supervisor.options import split_namespec
from supervisor.states import getProcessStateDescription
from supervisor.supervisorctl import ControllerPluginBase

from .rpcinterface import API_VERSION, RPCInterface
from .ttypes import ConciliationStrategies, StartingStrategies, PayloadList
from .utils import simple_localtime


class ControllerPlugin(ControllerPluginBase):
    """ The ControllerPlugin is the implementation of the Supvisors plugin
    that is embodied in the supervisorctl command. """

    def supvisors(self) -> RPCInterface:
        """ Get a proxy to the Supvisors RPC interface. """
        return self.ctl.get_server_proxy('supvisors')

    def do_sversion(self, _):
        """ Command to get the Supvisors API version. """
        if self._upcheck():
            try:
                version = self.supvisors().get_api_version()
            except xmlrpclib.Fault as e:
                self.ctl.output('ERROR ({})'.format(e.faultString))
            else:
                self.ctl.output(version)

    def help_sversion(self):
        """ Print the help of the sversion command."""
        self.ctl.output("sversion\t\t\t\tGet the API version of Supvisors.")

    def do_sstate(self, _):
        """ Command to get the Supvisors state. """
        if self._upcheck():
            try:
                state = self.supvisors().get_supvisors_state()
            except xmlrpclib.Fault as e:
                self.ctl.output('ERROR ({})'.format(e.faultString))
            else:
                template = '%(code)-3s%(state)-12s'
                line = template % {'code': state['statecode'], 'state': state['statename']}
                self.ctl.output(line)

    def help_sstate(self):
        """ Print the help of the sstate command."""
        self.ctl.output("sstate\t\t\t\t\tGet the Supvisors state.")

    def do_master(self, _):
        """ Command to get the Supvisors master address. """
        if self._upcheck():
            try:
                address = self.supvisors().get_master_address()
            except xmlrpclib.Fault as e:
                self.ctl.output('ERROR ({})'.format(e.faultString))
            else:
                self.ctl.output(address)

    def help_master(self):
        """ Print the help of the master command."""
        self.ctl.output("master\t\t\t\t\tGet the Supvisors master address.")

    def do_strategies(self, _):
        """ Command to get the Supvisors strategies. """
        if self._upcheck():
            try:
                strategies = self.supvisors().get_strategies()
            except xmlrpclib.Fault as e:
                self.ctl.output('ERROR ({})'.format(e.faultString))
            else:
                line = 'Auto-fencing: {}'.format(strategies['auto-fencing'])
                self.ctl.output(line)
                line = 'Conciliation: {}'.format(strategies['conciliation'])
                self.ctl.output(line)
                line = 'Starting:     {}'.format(strategies['starting'])
                self.ctl.output(line)

    def help_strategies(self):
        """ Print the help of the strategies command."""
        self.ctl.output("strategies\t\t\t\t\tGet the Supvisors strategies.")

    def do_address_status(self, arg):
        """ Command to get the status of addresses known to Supvisors. """
        if self._upcheck():
            try:
                # get everything at once instead of doing multiple requests
                info_list = self.supvisors().get_all_addresses_info()
            except xmlrpclib.Fault as e:
                self.ctl.output('ERROR ({})'.format(e.faultString))
            else:
                # create template. node name has variable length
                max_nodes = ControllerPlugin.max_template(info_list, 'address_name', 'Node')
                template = '%(addr)-{}s%(state)-11s%(load)-6s%(ltime)-10s%(counter)-9s'.format(max_nodes)
                # print title
                payload = {'addr': 'Node', 'state': 'State', 'load': 'Load',
                           'ltime': 'Time', 'counter': 'Counter'}
                self._output_info(template, payload)
                # check request args
                node_requests = arg.split()
                output_all = not node_requests or "all" in node_requests
                # print filtered payloads
                for info in info_list:
                    if output_all or info['address_name'] in node_requests:
                        payload = {'addr': info['address_name'], 'state': info['statename'],
                                   'load': '{}%'.format(info['loading']),
                                   'counter': info['sequence_counter'],
                                   'ltime': simple_localtime(info['local_time'])}
                        self._output_info(template, payload)

    def help_address_status(self):
        """ Print the help of the address_status command."""
        self.ctl.output("address_status <addr>\t\t\t"
                        "Get the status of remote supervisord managed in Supvisors and running on addr.")
        self.ctl.output("address_status <addr> <addr>\t\t"
                        "Get the status for multiple addresses")
        self.ctl.output("address_status\t\t\t\t"
                        "Get the status of all remote supervisord managed in Supvisors.")

    @staticmethod
    def max_template(payloads: PayloadList, item: str, title: str):
        """ Return the length of the item column taking into account the title and all its elements.

        :param payloads: the list of elements
        :param item: the item to display
        :param title: the title of the column
        :return: the length of the column
        """
        max_appli = max(len(info[item]) for info in payloads)
        return max(max_appli, len(title)) + 2

    def do_application_info(self, arg):
        """ Command to get information about applications known to Supvisors. """
        if self._upcheck():
            try:
                # get everything at once instead of doing multiple requests
                info_list = self.supvisors().get_all_applications_info()
            except xmlrpclib.Fault as e:
                self.ctl.output('ERROR ({})'.format(e.faultString))
            else:
                # create template. node name has variable length
                max_appli = ControllerPlugin.max_template(info_list, 'application_name', 'Application')
                template = '%(name)-{}s%(state)-10s%(major_failure)-7s%(minor_failure)-7s'.format(max_appli)
                # print title
                payload = {'name': 'Application', 'state': 'State', 'major_failure': 'Major', 'minor_failure': 'Minor'}
                self._output_info(template, payload)
                # check request args
                applications = arg.split()
                output_all = not applications or "all" in applications
                # print filtered payloads
                for info in info_list:
                    if output_all or info['application_name'] in applications:
                        payload = {'name': info['application_name'], 'state': info['statename'],
                                   'major_failure': info['major_failure'], 'minor_failure': info['minor_failure']}
                        self._output_info(template, payload)

    def help_application_info(self):
        """ Print the help of the application_info command."""
        self.ctl.output("application_info <appli>\t\t"
                        "Get the status of application named appli.")
        self.ctl.output("application_info <appli> <appli>\t"
                        "Get the status for multiple named application")
        self.ctl.output("application_info\t\t\t"
                        "Get the status of all applications.")

    def do_application_rules(self, arg):
        """ Command to get the application rules handled by Supvisors. """
        if self._upcheck():
            applications = arg.split()
            if not applications or "all" in applications:
                try:
                    applications = [application_info['application_name']
                                    for application_info in self.supvisors().get_all_applications_info()]
                except xmlrpclib.Fault as e:
                    self.ctl.output('ERROR ({})'.format(e.faultString))
                    applications = []
            rules_list = []
            for application in applications:
                try:
                    rules = self.supvisors().get_application_rules(application)
                except xmlrpclib.Fault as e:
                    self.ctl.output('{}: ERROR ({})'.format(application, e.faultString))
                else:
                    rules_list.append(rules)
            # print results
            if rules_list:
                # get longer from application names and title
                max_appli = max(len(rules['application_name']) for rules in rules_list)
                max_appli = max(max_appli, len('Application')) + 2
                # get longer from distribution nodes and title
                max_nodes = max(len(rules.get('addresses', '')) for rules in rules_list)
                max_nodes = max(max_nodes, len('Nodes')) + 2
                # print title
                template_managed = '%(appli)-{}s%(managed)-9s%(distributed)-13s%(nodes)-{}s' \
                                   '%(start_seq)-7s%(stop_seq)-7s' \
                                   '%(starting_strategy)-13s%(starting_failure_strategy)-18s' \
                                   '%(running_failure_strategy)s' \
                    .format(max_appli, max_nodes)
                title = {'appli': 'Application', 'managed': 'Managed', 'distributed': 'Distributed',
                         'nodes': 'Nodes', 'start_seq': 'Start', 'stop_seq': 'Stop', 'starting_strategy': 'Starting',
                         'starting_failure_strategy': 'Starting_Failure', 'running_failure_strategy': 'Running_Failure'}
                self.ctl.output(template_managed % title)
                for rules in rules_list:
                    if rules['managed']:
                        payload = {'appli': rules['application_name'], 'managed': True,
                                   'distributed': rules['distributed'], 'nodes': rules.get('addresses', ''),
                                   'start_seq': rules['start_sequence'], 'stop_seq': rules['stop_sequence'],
                                   'starting_strategy': rules['starting_strategy'],
                                   'starting_failure_strategy': rules['starting_failure_strategy'],
                                   'running_failure_strategy': rules['running_failure_strategy']}
                        line = template_managed % payload
                    else:
                        template_unmanaged = '%(appli)-{}sFalse'.format(max_appli)
                        line = template_unmanaged % {'appli': rules['application_name']}
                    self.ctl.output(line)

    def help_application_rules(self):
        """ Print the help of the application_rules command."""
        self.ctl.output("application_rules <appli>\t\t\t\t"
                        "Get the rules of the application named appli.")
        self.ctl.output("application_rules <appli> <appli>\t\t\t"
                        "Get the rules for multiple named applications")
        self.ctl.output("application_rules\t\t\t\t\t"
                        "Get the rules of all applications.")

    def do_sstatus(self, arg):
        """ Command to get information about processes known to Supvisors. """
        if self._upcheck():
            processes = arg.split()
            if not processes or "all" in processes:
                try:
                    info_list = self.supvisors().get_all_process_info()
                except xmlrpclib.Fault as e:
                    self.ctl.output('ERROR ({})'.format(e.faultString))
                    info_list = []
            else:
                info_list = []
                for process in processes:
                    try:
                        info = self.supvisors().get_process_info(process)
                    except xmlrpclib.Fault as e:
                        self.ctl.output('{}: ERROR ({})'.format(process, e.faultString))
                    else:
                        info_list.extend(info)
            # print results
            if info_list:
                max_appli = max(len(info['application_name']) for info in info_list) + 4
                max_proc = max(len(info['process_name']) for info in info_list) + 4
                template = '%(appli)-{}s%(proc)-{}s%(state)-12s%(addresses)s'.format(max_appli, max_proc)
                for info in info_list:
                    line = template % {'appli': info['application_name'],
                                       'proc': info['process_name'],
                                       'state': info['statename'],
                                       'addresses': info['addresses']}
                    self.ctl.output(line)

    def help_sstatus(self):
        """ Print the help of the sstatus command."""
        self.ctl.output("sstatus <proc>\t\t\t\t"
                        "Get the status of the process named proc.")
        self.ctl.output("sstatus <appli>:*\t\t\t"
                        "Get the process status of application named appli.")
        self.ctl.output("sstatus <proc> <proc>\t\t\t"
                        "Get the status for multiple named processes")
        self.ctl.output("sstatus\t\t\t\t\t"
                        "Get the status of all processes.")

    def do_local_status(self, arg):
        """ Command to get a subset of information about processes,
        using Supervisor's getProcessInfo, complemented by extra arguments.
        This is the minimal information required by Supvisors. """
        if self._upcheck():
            # get all information
            try:
                info_list = self.supvisors().get_all_local_process_info()
            except xmlrpclib.Fault as e:
                self.ctl.output('ERROR ({})'.format(e.faultString))
                info_list = []
            # filter information iaw arguments
            processes = arg.split()
            if not processes or 'all' in processes:
                match_list = info_list
            else:
                match_list = []
                for process in processes:
                    group_name, process_name = split_namespec(process)
                    for info in info_list:
                        matches = info['group'] == group_name
                        if process_name:
                            matches &= info['name'] == process_name
                        if matches:
                            match_list.append(info)
            # print results
            if match_list:
                max_appli = max(len(info['group']) for info in match_list) + 4
                max_proc = max(len(info['name']) for info in match_list) + 4
                template = '%(appli)-{}s%(proc)-{}s%(state)-12s%(start)-12s' \
                           '%(now)-12s%(pid)-8sargs="%(args)s"'. \
                    format(max_appli, max_proc)
                for info in match_list:
                    start_time = simple_localtime(info['start']) \
                        if info['start'] else 0
                    now_time = simple_localtime(info['now']) \
                        if info['now'] else 0
                    line = template % {
                        'appli': info['group'],
                        'proc': info['name'],
                        'state': getProcessStateDescription(info['state']),
                        'start': start_time,
                        'now': now_time,
                        'pid': info['pid'],
                        'args': info['extra_args']}
                    self.ctl.output(line)

    def help_local_status(self):
        """ Print the help of the local_status command."""
        self.ctl.output("local_status <proc>\t\t\t\t"
                        "Get the local status of the process named proc.")
        self.ctl.output("local_status <appli>:*\t\t\t"
                        "Get the local status of all processes in the application named appli.")
        self.ctl.output("local_status <proc> <proc>\t\t\t"
                        "Get the local status for multiple named processes")
        self.ctl.output("local_status\t\t\t\t\t"
                        "Get the local status of all processes.")

    def do_process_rules(self, arg):
        """ Command to get the process rules handled by Supvisors. """
        if self._upcheck():
            processes = arg.split()
            if not processes or "all" in processes:
                try:
                    processes = ['{}:*'.format(application_info['application_name'])
                                 for application_info in self.supvisors().get_all_applications_info()]
                except xmlrpclib.Fault as e:
                    self.ctl.output('ERROR ({})'.format(e.faultString))
                    processes = []
            rules_list = []
            for process in processes:
                try:
                    rules = self.supvisors().get_process_rules(process)
                except xmlrpclib.Fault as e:
                    self.ctl.output('{}: ERROR ({})'.format(process, e.faultString))
                else:
                    rules_list.extend(rules)
            # print results
            if rules_list:
                max_appli = max(len(rules['application_name'])
                                for rules in rules_list) + 4
                max_proc = max(len(rules['process_name'])
                               for rules in rules_list) + 4
                template = '%(appli)-{}s%(proc)-{}s%(start_seq)-5s%(stop_seq)-5s' \
                           '%(req)-12s%(exit)-12s%(load)-12s%(strategy)-22s%(addr)s'.format(max_appli, max_proc)
                for rules in rules_list:
                    required = rules['required']
                    wait_exit = rules['wait_exit']
                    line = template % {'appli': rules['application_name'],
                                       'proc': rules['process_name'],
                                       'addr': rules['addresses'],
                                       'start_seq': rules['start_sequence'],
                                       'stop_seq': rules['stop_sequence'],
                                       'req': 'required' if required else 'optional',
                                       'exit': 'exit' if wait_exit else '',
                                       'load': '{}%'.format(rules['expected_loading']),
                                       'strategy': rules['running_failure_strategy']}
                    self.ctl.output(line)

    def help_process_rules(self):
        """ Print the help of the process rules command."""
        self.ctl.output("process_rules <proc>\t\t\t\t"
                        "Get the rules of the process named proc.")
        self.ctl.output("process_rules <appli>:*\t\t\t\t"
                        "Get the rules of all processes in the application named appli.")
        self.ctl.output("process_rules <proc> <proc>\t\t\t"
                        "Get the rules for multiple named processes")
        self.ctl.output("process_rules\t\t\t\t\t"
                        "Get the rules of all processes.")

    def do_conflicts(self, _):
        """ Command to get the conflicts detected by Supvisors. """
        if self._upcheck():
            try:
                conflicts = self.supvisors().get_conflicts()
            except xmlrpclib.Fault as e:
                self.ctl.output('ERROR ({})'.format(e.faultString))
            else:
                if conflicts:
                    max_appli = max(len(conflict['application_name'])
                                    for conflict in conflicts) + 4
                    max_proc = max(len(conflict['process_name'])
                                   for conflict in conflicts) + 4
                    template = '%(appli)-{}s%(proc)-{}s%(state)-12s%(addresses)s'.format(max_appli, max_proc)
                    for conflict in conflicts:
                        line = template % {'appli': conflict['application_name'],
                                           'proc': conflict['process_name'],
                                           'state': conflict['statename'],
                                           'addresses': conflict['addresses']}
                        self.ctl.output(line)

    def help_conflicts(self):
        """ Print the help of the conflicts command."""
        self.ctl.output("conflicts\t\t\t\tGet the Supvisors conflicts.")

    def do_start_application(self, arg):
        """ Command to start Supvisors applications using a strategy and rules. """
        if self._upcheck():
            args = arg.split()
            if len(args) < 1:
                self.ctl.output('ERROR: start_application requires at least a strategy')
                self.help_start_application()
                return
            try:
                strategy = StartingStrategies[args[0]]
            except KeyError:
                self.ctl.output('ERROR: unknown strategy for start_application. use one of {}'
                                .format(StartingStrategies._member_names_))
                self.help_start_application()
                return
            applications = args[1:]
            if not applications or "all" in applications:
                try:
                    applications = [application_info['application_name']
                                    for application_info in self.supvisors().get_all_applications_info()]
                except xmlrpclib.Fault as e:
                    self.ctl.output('ERROR ({})'.format(e.faultString))
                    applications = []
            for application in applications:
                try:
                    result = self.supvisors().start_application(strategy.value, application)
                except xmlrpclib.Fault as e:
                    self.ctl.output('{}: ERROR ({})'.format(application, e.faultString))
                else:
                    self.ctl.output('{} started: {}'.format(application, result))

    def help_start_application(self):
        """ Print the help of the start_application command."""
        self.ctl.output("start_application <strategy> <appli>\t\t"
                        "Start the application named appli with strategy.")
        self.ctl.output("start_application <strategy> <appli> <appli>\t"
                        "Start multiple named applications with strategy")
        self.ctl.output("start_application <strategy>\t\t\t"
                        "Start all applications with strategy.")

    # stop an application
    def do_stop_application(self, arg):
        """ Command to stop Supvisors applications using rules. """
        if self._upcheck():
            applications = arg.split()
            if not applications or "all" in applications:
                try:
                    applications = [application_info['application_name']
                                    for application_info in self.supvisors().get_all_applications_info()]
                except xmlrpclib.Fault as e:
                    self.ctl.output('ERROR ({})'.format(e.faultString))
                    applications = []
            for application in applications:
                try:
                    self.supvisors().stop_application(application)
                except xmlrpclib.Fault as e:
                    self.ctl.output('{}: ERROR ({})'.format(application, e.faultString))
                else:
                    self.ctl.output('{} stopped'.format(application))

    def help_stop_application(self):
        """ Print the help of the stop_application command."""
        self.ctl.output("stop_application <appli>\t\t\t"
                        "Stop the application named appli.")
        self.ctl.output("stop_application <appli> <appli>\t\t"
                        "Stop multiple named applications.")
        self.ctl.output("stop_application\t\t\t\t"
                        "Stop all named applications.")

    def do_restart_application(self, arg):
        """ Command to restart Supvisors applications using a strategy and rules. """
        if self._upcheck():
            args = arg.split()
            if len(args) < 1:
                self.ctl.output('ERROR: restart_application requires at least a strategy')
                self.help_restart_application()
                return
            try:
                strategy = StartingStrategies[args[0]]
            except KeyError:
                self.ctl.output('ERROR: unknown strategy for restart_application. use one of {}'
                                .format(StartingStrategies._member_names_))
                self.help_restart_application()
                return
            applications = args[1:]
            if not applications or "all" in applications:
                try:
                    applications = [application_info['application_name']
                                    for application_info in self.supvisors().get_all_applications_info()]
                except xmlrpclib.Fault as e:
                    self.ctl.output('ERROR ({})'.format(e.faultString))
                    applications = []
            for application in applications:
                try:
                    self.supvisors().restart_application(strategy.value, application)
                except xmlrpclib.Fault as e:
                    self.ctl.output('{}: ERROR ({})'.format(application, e.faultString))
                else:
                    self.ctl.output('{} restarted'.format(application))

    def help_restart_application(self):
        """ Print the help of the restart_application command."""
        self.ctl.output("restart_application <strategy> <appli>\t\t"
                        "Restart the application named appli with strategy.")
        self.ctl.output("restart_application <strategy> <appli> <appli>\t"
                        "Restart multiple named applications with strategy")
        self.ctl.output("restart_application <strategy> \t\t\t"
                        "Restart all applications with strategy.")

    def do_start_args(self, arg):
        """ Command to start a local process with additional arguments. """
        if self._upcheck():
            args = arg.split()
            if len(args) < 2:
                self.ctl.output('ERROR: start_args requires a program name and extra arguments')
                self.help_start_args()
                return
            namespec = args[0]
            try:
                result = self.supvisors().start_args(namespec, ' '.join(args[1:]))
            except xmlrpclib.Fault as e:
                self.ctl.output('{}: ERROR ({})'.format(namespec, e.faultString))
            else:
                self.ctl.output('{} started: {}'.format(namespec, result))

    def help_start_args(self):
        """ Print the help of the start_args command."""
        self.ctl.output("Start a local process with additional arguments.")
        self.ctl.output("start_process <proc> <arg_list>\t\t\t"
                        "Start the local process named proc with additional arguments arg_list.")

    def do_start_process(self, arg):
        """ Command to start processes with a strategy and rules. """
        if self._upcheck():
            args = arg.split()
            if len(args) < 1:
                self.ctl.output('ERROR: start_process requires at least a strategy')
                self.help_start_process()
                return
            try:
                strategy = StartingStrategies[args[0]]
            except KeyError:
                self.ctl.output('ERROR: unknown strategy for start_process. use one of {}'
                                .format(StartingStrategies._member_names_))
                self.help_start_process()
                return
            processes = args[1:]
            if not processes or "all" in processes:
                try:
                    processes = ['{}:*'.format(application_info['application_name'])
                                 for application_info in self.supvisors().get_all_applications_info()]
                except xmlrpclib.Fault as e:
                    self.ctl.output('ERROR ({})'.format(e.faultString))
                    processes = []
            for process in processes:
                try:
                    result = self.supvisors().start_process(strategy.value, process)
                except xmlrpclib.Fault as e:
                    self.ctl.output('{}: ERROR ({})'.format(process, e.faultString))
                else:
                    self.ctl.output('{} started: {}'.format(process, result))

    def help_start_process(self):
        """ Print the help of the start_process command."""
        self.ctl.output("Start a process with strategy.")
        self.ctl.output("start_process <strategy> <proc>\t\t\t"
                        "Start the process named proc with strategy.")
        self.ctl.output("start_process <strategy> <proc> <proc>\t\t"
                        "Start multiple named processes with strategy.")
        self.ctl.output("start_process <strategy>\t\t\t"
                        "Start all processes with strategy.")

    # start a process using strategy and rules
    def do_start_process_args(self, arg):
        """ Command to start a process with a strategy, rules
        and additional arguments. """
        if self._upcheck():
            args = arg.split()
            if len(args) < 3:
                self.ctl.output('ERROR: start_process_args requires a strategy, '
                                'a program name and extra arguments')
                self.help_start_process_args()
                return
            try:
                strategy = StartingStrategies[args[0]]
            except KeyError:
                self.ctl.output('ERROR: unknown strategy for start_process_args. use one of {}'
                                .format(StartingStrategies._member_names_))
                self.help_start_process_args()
                return
            namespec = args[1]
            try:
                result = self.supvisors().start_process(strategy.value, namespec, ' '.join(args[2:]))
            except xmlrpclib.Fault as e:
                self.ctl.output('{}: ERROR ({})'.format(namespec, e.faultString))
            else:
                self.ctl.output('{} started: {}'.format(namespec, result))

    def help_start_process_args(self):
        """ Print the help of the start_process_args command."""
        self.ctl.output("Start a process with strategy and additional arguments.")
        self.ctl.output("start_process <strategy> <proc> <arg_list>\t"
                        "Start the process named proc with additional arguments arg_list.")

    def do_stop_process(self, arg):
        """ Command to stop processes with rules. """
        if self._upcheck():
            processes = arg.split()
            if not processes or "all" in processes:
                try:
                    processes = ['{}:*'.format(application_info['application_name'])
                                 for application_info in self.supvisors().get_all_applications_info()]
                except xmlrpclib.Fault as e:
                    self.ctl.output('ERROR ({})'.format(e.faultString))
                    processes = []
            for process in processes:
                try:
                    self.supvisors().stop_process(process)
                except xmlrpclib.Fault as e:
                    self.ctl.output('{}: ERROR ({})'.format(process, e.faultString))
                else:
                    self.ctl.output('{} stopped'.format(process))

    def help_stop_process(self):
        """ Print the help of the stop_process command."""
        self.ctl.output("Stop a process where it is running.")
        self.ctl.output("stop_process <strategy> <proc>\t\t\t"
                        "Stop the process named proc.")
        self.ctl.output("stop_process <strategy> <proc> <proc>\t\t"
                        "Stop multiple named processes.")
        self.ctl.output("stop_process <strategy> \t\t\t"
                        "Stop all named processes.")

    def do_restart_process(self, arg):
        """ Command to restart processes with a strategy and rules. """
        if self._upcheck():
            args = arg.split()
            if len(args) < 1:
                self.ctl.output('ERROR: restart_process requires a strategy and a program name')
                self.help_restart_process()
                return
            try:
                strategy = StartingStrategies[args[0]]
            except KeyError:
                self.ctl.output('ERROR: unknown strategy for restart_process. use one of {}'
                                .format(StartingStrategies._member_names_))
                self.help_restart_process()
                return
            processes = args[1:]
            if not processes or "all" in processes:
                try:
                    processes = ['{}:*'.format(application_info['application_name'])
                                 for application_info in self.supvisors().get_all_applications_info()]
                except xmlrpclib.Fault as e:
                    self.ctl.output('ERROR ({})'.format(e.faultString))
                    processes = []
            for process in processes:
                try:
                    result = self.supvisors().restart_process(strategy.value, process)
                except xmlrpclib.Fault as e:
                    self.ctl.output('{}: ERROR ({})'.format(process, e.faultString))
                else:
                    self.ctl.output('{} restarted: {}'.format(process, result))

    def help_restart_process(self):
        """ Print the help of the restart_process command."""
        self.ctl.output("Restart a process with strategy and rules.")
        self.ctl.output("restart_process <strategy> <proc>\t\t"
                        "Restart the process named proc using strategy.")
        self.ctl.output("restart_process <strategy> <proc> <proc>\t"
                        "Restart multiple named processes using strategy.")
        self.ctl.output("restart_process <strategy> \t\t\t"
                        "Restart all processes using strategy.")

    def do_conciliate(self, arg):
        """ Command to conciliate conflicts (applicable with default USER strategy). """
        if self._upcheck():
            args = arg.split()
            if len(args) < 1:
                self.ctl.output('ERROR: conciliate requires a strategy')
                self.help_conciliate()
                return
            try:
                strategy = ConciliationStrategies[args[0]]
            except KeyError:
                self.ctl.output('ERROR: unknown strategy for conciliate. use one of {}'
                                .format(ConciliationStrategies._member_names_))
                self.help_conciliate()
                return
            try:
                result = self.supvisors().conciliate(strategy.value)
            except xmlrpclib.Fault as e:
                self.ctl.output('ERROR ({})'.format(e.faultString))
            else:
                self.ctl.output('Conciliated: {}'.format(result))

    def help_conciliate(self):
        """ Print the help of the conciliate command. """
        self.ctl.output("Conciliate Supvisors conflicts.")
        self.ctl.output("conciliate strategy\t\t\t\t\tConciliate process conflicts using strategy")

    def do_sreload(self, _):
        """ Command to restart Supvisors on all addresses. """
        if self._upcheck():
            try:
                result = self.supvisors().restart()
            except xmlrpclib.Fault as e:
                self.ctl.output('ERROR ({})'.format(e.faultString))
            else:
                self.ctl.output('Restarted: {}'.format(result))

    def help_sreload(self):
        """ Print the help of the sreload command."""
        self.ctl.output("Restart Supvisors.")
        self.ctl.output("sreload\t\t\t\t\tRestart all remote supervisord")

    def do_sshutdown(self, _):
        """ Command to shutdown Supvisors on all addresses. """
        if self._upcheck():
            try:
                result = self.supvisors().shutdown()
            except xmlrpclib.Fault as e:
                self.ctl.output('ERROR ({})'.format(e.faultString))
            else:
                self.ctl.output('Shut down: {}'.format(result))

    def help_sshutdown(self):
        """ Print the help of the sshutdown command."""
        self.ctl.output("Shutdown Supvisors.")
        self.ctl.output("sshutdown\t\t\t\tShut all remote supervisord down")

    def do_loglevel(self, arg):
        """ Command to change the level of the local Supvisors. """
        if self._upcheck():
            args = arg.split()
            if len(args) < 1:
                self.ctl.output('ERROR: loglevel requires a level')
                self.help_loglevel()
                return
            level = getLevelNumByDescription(args[0])
            if level is None:
                self.ctl.output('ERROR: unknown level for Logger.')
                self.help_loglevel()
                return
            try:
                result = self.supvisors().change_log_level(level)
            except xmlrpclib.Fault as e:
                self.ctl.output('ERROR ({})'.format(e.faultString))
            else:
                self.ctl.output('Logger level changed: {}'.format(result))

    def help_loglevel(self):
        """ Print the help of the loglevel command."""
        self.ctl.output('Change the level of local Supvisors\' logger.')
        self.ctl.output('loglevel lvl\t\t\t\tChange the level of local Supvisors\' logger to lvl.')
        self.ctl.output('\t\t\t\t\t\t\tApplicable values are: {}.'.format(LOG_LEVELS_BY_NUM.values()))

    def _upcheck(self):
        """ Check of the API versions. """
        try:
            api = self.supvisors().get_api_version()
            if api != API_VERSION:
                self.ctl.output('ERROR: this version of supvisorsctl expects to talk to a server '
                                'with API version %s, but the remote version is %s.' % (API_VERSION, api))
                return False
        except xmlrpclib.Fault as e:
            if e.faultCode == xmlrpc.Faults.UNKNOWN_METHOD:
                self.ctl.output('ERROR: supervisord responded but did not recognize '
                                'the supvisors namespace commands that supvisorsctl uses to control it. '
                                'Please check that the [rpcinterface:supervisor] section is enabled '
                                'in the configuration file (see sample.conf).')
                return False
            raise
        except socket.error as why:
            if why.args[0] == errno.ECONNREFUSED:
                self.ctl.output('ERROR: %s refused connection' % self.ctl.options.serverurl)
                return False
            elif why.args[0] == errno.ENOENT:
                self.ctl.output('ERROR: %s no such file' % self.ctl.options.serverurl)
                return False
            raise
        return True

    def _output_info(self, template, payload):
        """ Write the information template. """
        self.ctl.output(template % payload)


def make_supvisors_controller_plugin(controller):
    """ Create a plugin for the Supvisors commands. """
    return ControllerPlugin(controller)
