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
import sys
from types import MethodType

from supervisor import supervisorctl
from supervisor import xmlrpc
from supervisor.compat import as_string, xmlrpclib
from supervisor.loggers import getLevelNumByDescription
from supervisor.options import ClientOptions, make_namespec, split_namespec
from supervisor.states import ProcessStates, getProcessStateDescription
from supervisor.supervisorctl import Controller, ControllerPluginBase, LSBInitExitStatuses

from .plugin import expand_faults
from .rpcinterface import API_VERSION, RPCInterface
from .ttypes import ConciliationStrategies, StartingStrategies, SupvisorsInstanceStates, PayloadList
from .utils import simple_localtime


def _startresult(self, result):
    """ This method replaces the Supervisor method in DefaultControllerPlugin.

    :param result: the command result
    :return: the result to output
    """
    if result['status'] == xmlrpc.Faults.DISABLED:
        name = make_namespec(result['group'], result['name'])
        return f'{name}: ERROR disabled'
    return self._startresult_ref(result)


class ControllerPlugin(ControllerPluginBase):
    """ The ControllerPlugin is the implementation of the Supvisors plugin that is embodied in the supervisorctl
    command. """

    def __init__(self, controller):
        super().__init__(controller)
        # update Supervisor Fault definition
        expand_faults()
        # patch supervisor plugin to manage new Faults.DISABLED code in RPCError
        supervisor_plugin = controller.options.plugins[0]
        if not hasattr(supervisor_plugin, '_startresult_ref'):
            supervisor_plugin._startresult_ref = supervisor_plugin._startresult
            supervisor_plugin._startresult = MethodType(_startresult, supervisor_plugin)

    def get_server_proxy(self, server_url: str, namespace: str):
        """ Return a proxy on a remote supervisor instance. """
        proxy = xmlrpclib.ServerProxy('http://127.0.0.1',
                                      xmlrpc.SupervisorTransport(self.ctl.options.username,
                                                                 self.ctl.options.password,
                                                                 server_url))
        return getattr(proxy, namespace)

    def supvisors(self) -> RPCInterface:
        """ Get a proxy to the Supvisors RPC interface. """
        return self.ctl.get_server_proxy('supvisors')

    def get_running_instances(self):
        """ Return the URL of the Supvisors running instances. """
        try:
            # get everything at once instead of doing multiple requests
            info_list = self.supvisors().get_all_instances_info()
        except xmlrpclib.Fault as e:
            self.ctl.output(f'ERROR ({e.faultString})')
            self.ctl.exitstatus = LSBInitExitStatuses.GENERIC
            info_list = []
        return {info['identifier']: 'http://%s:%d' % (info['node_name'], info['port'])
                for info in info_list
                if info['statecode'] in [SupvisorsInstanceStates.CHECKED.value, SupvisorsInstanceStates.RUNNING.value]}

    def do_sversion(self, _):
        """ Command to get the Supvisors API version. """
        if self._upcheck():
            try:
                version = self.supvisors().get_api_version()
            except xmlrpclib.Fault as e:
                self.ctl.output(f'ERROR ({e.faultString})')
                self.ctl.exitstatus = LSBInitExitStatuses.GENERIC
            else:
                self.ctl.output(version)

    def help_sversion(self):
        """ Print the help of the sversion command. """
        self.ctl.output('sversion\t\t\t\tGet the API version of Supvisors.')

    def do_sstate(self, _):
        """ Command to get the Supvisors state. """
        if self._upcheck():
            try:
                state_modes = self.supvisors().get_supvisors_state()
            except xmlrpclib.Fault as e:
                self.ctl.output(f'ERROR ({e.faultString})')
                self.ctl.exitstatus = LSBInitExitStatuses.GENERIC
            else:
                max_master = ControllerPlugin.max_template([state_modes], 'master_identifier', 'Master')
                max_starting = ControllerPlugin.max_template([state_modes], 'starting_jobs', 'Starting')
                max_stopping = ControllerPlugin.max_template([state_modes], 'stopping_jobs', 'Stopping')
                template = (f'%(state)-16s%(discovery)-11s%(master)-{max_master}s%(starting)-{max_starting}s'
                            f'%(stopping)-{max_stopping}s')
                # print title
                payload = {'state': 'State', 'discovery': 'Discovery', 'master': 'Master',
                           'starting': 'Starting', 'stopping': 'Stopping'}
                self.ctl.output(template % payload)
                # print data
                line = template % {'state': state_modes['fsm_statename'],
                                   'discovery': state_modes['discovery_mode'],
                                   'master': state_modes['master_identifier'],
                                   'starting': state_modes['starting_jobs'],
                                   'stopping': state_modes['stopping_jobs']}
                self.ctl.output(line)

    def help_sstate(self):
        """ Print the help of the sstate command. """
        self.ctl.output('sstate\t\t\t\t\tGet the Supvisors state.')

    def do_master(self, _):
        """ Command to get the Master Supvisors instance. """
        if self._upcheck():
            try:
                identifier = self.supvisors().get_master_identifier()
            except xmlrpclib.Fault as e:
                self.ctl.output(f'ERROR ({e.faultString})')
                self.ctl.exitstatus = LSBInitExitStatuses.GENERIC
            else:
                self.ctl.output(identifier)

    def help_master(self):
        """ Print the help of the master command. """
        self.ctl.output('master\t\t\t\t\tGet the Master Supvisors instance.')

    def do_strategies(self, _):
        """ Command to get the Supvisors strategies. """
        if self._upcheck():
            try:
                strategies = self.supvisors().get_strategies()
            except xmlrpclib.Fault as e:
                self.ctl.output(f'ERROR ({e.faultString})')
                self.ctl.exitstatus = LSBInitExitStatuses.GENERIC
            else:
                self.ctl.output(f"Auto-fencing: {strategies['auto-fencing']}")
                self.ctl.output(f"Conciliation: {strategies['conciliation']}")
                self.ctl.output(f"Starting:     {strategies['starting']}")

    def help_strategies(self):
        """ Print the help of the strategies command."""
        self.ctl.output('strategies\t\t\t\t\tGet the Supvisors strategies.')

    def do_instance_status(self, arg):
        """ Command to get the status of instances known to Supvisors. """
        if self._upcheck():
            try:
                # get everything at once instead of doing multiple requests
                info_list = self.supvisors().get_all_instances_info()
            except xmlrpclib.Fault as e:
                self.ctl.output(f'ERROR ({e.faultString})')
                self.ctl.exitstatus = LSBInitExitStatuses.GENERIC
            else:
                # create template. identifier has variable length
                max_identifiers = ControllerPlugin.max_template(info_list, 'identifier', 'Supervisor')
                max_node_names = ControllerPlugin.max_template(info_list, 'node_name', 'Node')
                template = (f'%(identifier)-{max_identifiers}s%(node_name)-{max_node_names}s%(port)-7s'
                            '%(state)-11s%(discovery)-11s%(load)-6s%(ltime)-10s%(counter)-9s%(failure)-9s'
                            f'%(fsm_state)-16s%(discovery)-11s%(master)-{max_node_names}s'
                            '%(starting)-10s%(stopping)-10s')
                # print title
                payload = {'identifier': 'Supervisor', 'node_name': 'Node', 'port': 'Port',
                           'state': 'State', 'discovery': 'Discovery',
                           'load': 'Load', 'ltime': 'Time', 'counter': 'Counter', 'failure': 'Failure',
                           'fsm_state': 'FSM', 'master': 'Master', 'discovery': 'Discovery',
                           'starting': 'Starting', 'stopping': 'Stopping'}
                self.ctl.output(template % payload)
                # check request args
                identifiers = arg.split()
                output_all = not identifiers or 'all' in identifiers
                # print filtered payloads
                for info in info_list:
                    if output_all or info['identifier'] in identifiers:
                        payload = {'identifier': info['identifier'],
                                   'node_name': info['node_name'], 'port': info['port'],
                                   'state': info['statename'],
                                   'discovery': info['discovery_mode'],
                                   'load': f"{info['loading']}%",
                                   'ltime': simple_localtime(info['local_time']),
                                   'counter': info['sequence_counter'],
                                   'failure': info['process_failure'],
                                   'fsm_state': info['fsm_statename'],
                                   'discovery': info['discovery_mode'],
                                   'master': info['master_identifier'],
                                   'starting': info['starting_jobs'],
                                   'stopping': info['stopping_jobs']}
                        self.ctl.output(template % payload)

    def help_instance_status(self):
        """ Print the help of the instance_status command."""
        self.ctl.output('instance_status <identifier>\t\t\tGet the status of the Supvisors instance.')
        self.ctl.output('instance_status <identifier> <identifier>\t\tGet the status for multiple Supvisors instances')
        self.ctl.output('instance_status\t\t\t\tGet the status of all remote Supvisors instances.')

    @staticmethod
    def max_template(payloads: PayloadList, item: str, title: str):
        """ Return the length of the item column taking into account the title and all its elements.

        :param payloads: the list of elements
        :param item: the item to display
        :param title: the title of the column
        :return: the length of the column
        """
        max_item = len(title)
        # WARN: item value is not always a string
        values = [len(str(info[item])) for info in payloads if item in info]
        return max(max_item, max(values) if values else 0) + 2

    def do_application_info(self, arg):
        """ Command to get information about applications known to Supvisors. """
        if self._upcheck():
            try:
                # get everything at once instead of doing multiple requests
                info_list = self.supvisors().get_all_applications_info()
            except xmlrpclib.Fault as e:
                self.ctl.output(f'ERROR ({e.faultString})')
                self.ctl.exitstatus = LSBInitExitStatuses.GENERIC
            else:
                # create template. identifier has variable length
                max_appli = ControllerPlugin.max_template(info_list, 'application_name', 'Application')
                template = '%(name)-{}s%(state)-10s%(major_failure)-7s%(minor_failure)-7s'.format(max_appli)
                # print title
                payload = {'name': 'Application', 'state': 'State', 'major_failure': 'Major', 'minor_failure': 'Minor'}
                self.ctl.output(template % payload)
                # check request args
                applications = arg.split()
                output_all = not applications or "all" in applications
                # print filtered payloads
                for info in info_list:
                    if output_all or info['application_name'] in applications:
                        payload = {'name': info['application_name'], 'state': info['statename'],
                                   'major_failure': info['major_failure'], 'minor_failure': info['minor_failure']}
                        self.ctl.output(template % payload)

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
            if not applications or 'all' in applications:
                try:
                    applications = [application_info['application_name']
                                    for application_info in self.supvisors().get_all_applications_info()]
                except xmlrpclib.Fault as e:
                    self.ctl.output(f'ERROR ({e.faultString})')
                    self.ctl.exitstatus = LSBInitExitStatuses.GENERIC
                    applications = []
            rules_list = []
            for application in applications:
                try:
                    rules = self.supvisors().get_application_rules(application)
                except xmlrpclib.Fault as e:
                    self.ctl.output(f'{application}: ERROR ({e.faultString})')
                    self.ctl.exitstatus = LSBInitExitStatuses.GENERIC
                else:
                    rules_list.append(rules)
            # print results
            if rules_list:
                max_appli = ControllerPlugin.max_template(rules_list, 'application_name', 'Application')
                max_identifiers = ControllerPlugin.max_template(rules_list, 'identifiers', 'Supervisor')
                # print title
                template = (f'%(appli)-{max_appli}s%(managed)-9s%(distribution)-17s%(identifiers)-{max_identifiers}s'
                            '%(start_seq)-7s%(stop_seq)-7s%(starting_strategy)-18s%(starting_failure_strategy)-18s'
                            '%(running_failure_strategy)s')
                title = {'appli': 'Application', 'managed': 'Managed', 'distribution': 'Distribution',
                         'identifiers': 'Supervisor', 'start_seq': 'Start', 'stop_seq': 'Stop',
                         'starting_strategy': 'Starting', 'starting_failure_strategy': 'Starting_Failure',
                         'running_failure_strategy': 'Running_Failure'}
                self.ctl.output(template % title)
                # print rules
                for rules in rules_list:
                    if rules['managed']:
                        payload = {'appli': rules['application_name'], 'managed': True,
                                   'distribution': rules['distribution'],
                                   'identifiers': rules.get('identifiers', 'n/a'),
                                   'start_seq': rules['start_sequence'], 'stop_seq': rules['stop_sequence'],
                                   'starting_strategy': rules['starting_strategy'],
                                   'starting_failure_strategy': rules['starting_failure_strategy'],
                                   'running_failure_strategy': rules['running_failure_strategy']}
                    else:
                        payload = {'appli': rules['application_name'], 'managed': False,
                                   'distribution': 'n/a', 'identifiers': 'n/a',
                                   'start_seq': 'n/a', 'stop_seq': 'n/a',
                                   'starting_strategy': 'n/a',
                                   'starting_failure_strategy': 'n/a',
                                   'running_failure_strategy': 'n/a'}
                    self.ctl.output(template % payload)

    def help_application_rules(self):
        """ Print the help of the application_rules command."""
        self.ctl.output('application_rules <appli>\t\t\tGet the rules of the application named appli.')
        self.ctl.output('application_rules <appli> <appli>\t\tGet the rules for multiple named applications')
        self.ctl.output('application_rules\t\t\t\tGet the rules of all applications.')

    def do_sstatus(self, arg):
        """ Command to get information about processes known to Supvisors. """
        if self._upcheck():
            processes = arg.split()
            if not processes or 'all' in processes:
                try:
                    info_list = self.supvisors().get_all_process_info()
                except xmlrpclib.Fault as e:
                    self.ctl.output(f'ERROR ({e.faultString})')
                    self.ctl.exitstatus = LSBInitExitStatuses.GENERIC
                    info_list = []
            else:
                info_list = []
                for process in processes:
                    try:
                        info = self.supvisors().get_process_info(process)
                    except xmlrpclib.Fault as e:
                        self.ctl.output(f'{process}: ERROR ({e.faultString})')
                        self.ctl.exitstatus = LSBInitExitStatuses.GENERIC
                    else:
                        info_list.extend(info)
            # print results
            if info_list:
                max_appli = ControllerPlugin.max_template(info_list, 'application_name', 'Application')
                max_proc = ControllerPlugin.max_template(info_list, 'process_name', 'Process')
                # print title
                template = f'%(appli)-{max_appli}s%(proc)-{max_proc}s%(state)-12s%(expected)-10s%(identifiers)s'
                title = {'appli': 'Application', 'proc': 'Process', 'state': 'State',
                         'expected': 'Expected', 'identifiers': 'Supervisor'}
                self.ctl.output(template % title)
                # print process status
                for info in info_list:
                    expected = info['expected_exit'] if info['statecode'] == ProcessStates.EXITED else 'n/a'
                    payload = {'appli': info['application_name'],
                               'proc': info['process_name'],
                               'state': info['statename'],
                               'expected': expected,
                               'identifiers': info['identifiers']}
                    self.ctl.output(template % payload)

    def help_sstatus(self):
        """ Print the help of the sstatus command."""
        self.ctl.output('sstatus <proc>\t\t\t\tGet the status of the process named proc.')
        self.ctl.output('sstatus <appli>:*\t\t\tGet the process status of application named appli.')
        self.ctl.output('sstatus <proc> <proc>\t\t\tGet the status for multiple named processes')
        self.ctl.output('sstatus\t\t\t\t\tGet the status of all processes.')

    def do_local_status(self, arg):
        """ Command to get a subset of information about processes, using Supervisor's getProcessInfo,
        complemented by extra arguments.
        This is the minimal information required by Supvisors. """
        if self._upcheck():
            # get all information
            try:
                info_list = self.supvisors().get_all_local_process_info()
            except xmlrpclib.Fault as e:
                self.ctl.output(f'ERROR ({e.faultString})')
                self.ctl.exitstatus = LSBInitExitStatuses.GENERIC
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
                max_appli = ControllerPlugin.max_template(match_list, 'group', 'Application')
                max_proc = ControllerPlugin.max_template(match_list, 'name', 'Process')
                template = (f'%(appli)-{max_appli}s%(proc)-{max_proc}s%(disabled)-10s%(state)-12s%(start)-12s'
                            '%(now)-12s%(pid)-8s%(args)s')
                # print title
                payload = {'appli': 'Application', 'proc': 'Process', 'disabled': 'Disabled', 'state': 'State',
                           'start': 'Start', 'now': 'Now', 'pid': 'PID', 'args': 'Extra args'}
                self.ctl.output(template % payload)
                # print filtered payloads (some attributes serve only Supvisors internal purpose)
                for info in match_list:
                    start_time = simple_localtime(info['start']) if info['start'] else 0
                    now_time = simple_localtime(info['now']) if info['now'] else 0
                    payload = {'appli': info['group'], 'proc': info['name'], 'disabled': info['disabled'],
                               'state': getProcessStateDescription(info['state']),
                               'start': start_time, 'now': now_time, 'pid': info['pid'],
                               'args': info['extra_args']}
                    self.ctl.output(template % payload)

    def help_local_status(self):
        """ Print the help of the local_status command."""
        self.ctl.output('local_status <proc>\t\t\tGet the local status of the process named proc.')
        self.ctl.output('local_status <appli>:*\t\t\t'
                        'Get the local status of all processes in the application named appli.')
        self.ctl.output('local_status <proc> <proc>\t\tGet the local status for multiple named processes')
        self.ctl.output('local_status\t\t\t\tGet the local status of all processes.')

    def do_process_rules(self, arg):
        """ Command to get the process rules handled by Supvisors. """
        if self._upcheck():
            namespecs = arg.split()
            if not namespecs or 'all' in namespecs:
                try:
                    namespecs = [make_namespec(info['application_name'], info['process_name'])
                                 for info in self.supvisors().get_all_process_info()]
                except xmlrpclib.Fault as e:
                    self.ctl.output(f'ERROR ({e.faultString})')
                    self.ctl.exitstatus = LSBInitExitStatuses.GENERIC
                    namespecs = []
            rules_list = []
            for namespec in sorted(namespecs):
                try:
                    rules = self.supvisors().get_process_rules(namespec)
                except xmlrpclib.Fault as e:
                    self.ctl.output(f'{namespec}: ERROR ({e.faultString})')
                    self.ctl.exitstatus = LSBInitExitStatuses.GENERIC
                else:
                    rules_list.extend(rules)
            # print results
            if rules_list:
                max_appli = ControllerPlugin.max_template(rules_list, 'application_name', 'Application')
                max_proc = ControllerPlugin.max_template(rules_list, 'process_name', 'Process')
                template = (f'%(appli)-{max_appli}s%(proc)-{max_proc}s%(start_seq)-7s%(stop_seq)-7s'
                            '%(req)-12s%(exit)-12s%(load)-12s%(strategy)-22s%(identifiers)s')
                # print title
                payload = {'appli': 'Application', 'proc': 'Process', 'start_seq': 'Start', 'stop_seq': 'Stop',
                           'req': 'Required', 'exit': 'WaitExit', 'load': 'Loading', 'strategy': 'Strategy',
                           'identifiers': 'Supervisor'}
                self.ctl.output(template % payload)
                # print filtered payloads
                for rules in rules_list:
                    payload = {'appli': rules['application_name'],
                               'proc': rules['process_name'],
                               'identifiers': rules['identifiers'],
                               'start_seq': rules['start_sequence'],
                               'stop_seq': rules['stop_sequence'],
                               'req': rules['required'],
                               'exit': rules['wait_exit'],
                               'load': f"{rules['expected_loading']}%",
                               'strategy': rules['running_failure_strategy']}
                    self.ctl.output(template % payload)

    def help_process_rules(self):
        """ Print the help of the process rules command."""
        self.ctl.output('process_rules <proc>\t\t\tGet the rules of the process named proc.')
        self.ctl.output('process_rules <appli>:*\t\t\tGet the rules of all processes in the application named appli.')
        self.ctl.output('process_rules <proc> <proc>\t\tGet the rules for multiple named processes')
        self.ctl.output('process_rules\t\t\t\tGet the rules of all processes.')

    def do_conflicts(self, _):
        """ Command to get the conflicts detected by Supvisors. """
        if self._upcheck():
            try:
                conflicts = self.supvisors().get_conflicts()
            except xmlrpclib.Fault as e:
                self.ctl.output(f'ERROR ({e.faultString})')
                self.ctl.exitstatus = LSBInitExitStatuses.GENERIC
            else:
                if conflicts:
                    max_appli = ControllerPlugin.max_template(conflicts, 'application_name', 'Application')
                    max_proc = ControllerPlugin.max_template(conflicts, 'process_name', 'Process')
                    template = f'%(appli)-{max_appli}s%(proc)-{max_proc}s%(state)-12s%(identifiers)s'
                    # print title
                    payload = {'appli': 'Application', 'proc': 'Process', 'state': 'State', 'identifiers': 'Supervisor'}
                    self.ctl.output(template % payload)
                    # print filtered payloads
                    for conflict in conflicts:
                        payload = {'appli': conflict['application_name'],
                                   'proc': conflict['process_name'],
                                   'state': conflict['statename'],
                                   'identifiers': conflict['identifiers']}
                        self.ctl.output(template % payload)

    def help_conflicts(self):
        """ Print the help of the conflicts command."""
        self.ctl.output('conflicts\t\t\t\tGet the Supvisors conflicts.')

    def _get_matching_applications(self, parameters, all_info, alt_rpc):
        """ Get the matching information from the full list. """
        matching_info = []
        if not parameters or 'all' in parameters:
            # get all managed applications
            matching_info = sorted([application_name for application_name, managed in all_info.items() if managed])
        else:
            for application_name in parameters:
                if application_name in all_info:
                    if all_info[application_name]:
                        matching_info.append(application_name)
                    else:
                        self.ctl.output(f'{application_name}: IGNORED (unmanaged. use {alt_rpc} {application_name}:*)')
                else:
                    self.ctl.output(f'{application_name}: ERROR (no such application)')
                    self.ctl.exitstatus = LSBInitExitStatuses.INVALID_ARGS
        return matching_info

    def do_start_application(self, arg):
        """ Command to start Supvisors applications using a strategy and rules. """
        if self._upcheck():
            args = as_string(arg).split()
            # check number of arguments
            if len(args) < 1:
                self.ctl.output('ERROR: start_application requires at least a strategy')
                self.ctl.exitstatus = LSBInitExitStatuses.INVALID_ARGS
                self.help_start_application()
                return
            # check strategy format
            try:
                strategy = StartingStrategies[args[0]]
            except KeyError:
                self.ctl.output('ERROR: unknown strategy for start_application.'
                                f' use one of {[x.name for x in StartingStrategies]}')
                self.ctl.exitstatus = LSBInitExitStatuses.INVALID_ARGS
                self.help_start_application()
                return
            # get all application info
            try:
                all_info = {application_info['application_name']: application_info['managed']
                            for application_info in self.supvisors().get_all_applications_info()}
            except xmlrpclib.Fault as e:
                self.ctl.output(f'ERROR ({e.faultString})')
                self.ctl.exitstatus = LSBInitExitStatuses.GENERIC
                return
            # match with parameters
            matching_info = self._get_matching_applications(args[1:], all_info, 'start')
            # request start for matching applications
            for application_name in matching_info:
                try:
                    result = self.supvisors().start_application(strategy.value, application_name)
                except xmlrpclib.Fault as e:
                    self.ctl.output(f'{application_name}: ERROR ({e.faultString})')
                    self.ctl.exitstatus = LSBInitExitStatuses.GENERIC
                else:
                    self.ctl.output(f'{application_name} started: {result}')

    def help_start_application(self):
        """ Print the help of the start_application command."""
        self.ctl.output('start_application <strategy> <appli>\t\t'
                        'Start the managed application named appli with strategy.')
        self.ctl.output('start_application <strategy> <appli> <appli>\t'
                        'Start multiple managed named applications with strategy')
        self.ctl.output('start_application <strategy>\t\t\t'
                        'Start all managed applications with strategy.')

    def do_restart_application(self, arg):
        """ Command to restart Supvisors applications using a strategy and rules. """
        if self._upcheck():
            args = as_string(arg).split()
            # check number of arguments
            if len(args) < 1:
                self.ctl.output('ERROR: restart_application requires at least a strategy')
                self.ctl.exitstatus = LSBInitExitStatuses.INVALID_ARGS
                self.help_restart_application()
                return
            # check strategy format
            try:
                strategy = StartingStrategies[args[0]]
            except KeyError:
                self.ctl.output('ERROR: unknown strategy for restart_application.'
                                f' use one of {[x.name for x in StartingStrategies]}')
                self.ctl.exitstatus = LSBInitExitStatuses.INVALID_ARGS
                self.help_restart_application()
                return
            # get all application info
            try:
                all_info = {application_info['application_name']: application_info['managed']
                            for application_info in self.supvisors().get_all_applications_info()}
            except xmlrpclib.Fault as e:
                self.ctl.output(f'ERROR ({e.faultString})')
                self.ctl.exitstatus = LSBInitExitStatuses.GENERIC
                return
            # match with parameters
            matching_info = self._get_matching_applications(args[1:], all_info, 'restart')
            # request start for matching applications
            for application_name in matching_info:
                try:
                    result = self.supvisors().restart_application(strategy.value, application_name)
                except xmlrpclib.Fault as e:
                    self.ctl.output(f'{application_name}: ERROR ({e.faultString})')
                    self.ctl.exitstatus = LSBInitExitStatuses.GENERIC
                else:
                    self.ctl.output(f'{application_name} restarted: {result}')

    def help_restart_application(self):
        """ Print the help of the restart_application command."""
        self.ctl.output('restart_application <strategy> <appli>\t\t'
                        'Restart the managed application named appli with strategy.')
        self.ctl.output('restart_application <strategy> <appli> <appli>\t'
                        'Restart multiple managed named applications with strategy')
        self.ctl.output('restart_application <strategy> \t\t\t'
                        'Restart all managed applications with strategy.')

    def do_stop_application(self, arg):
        """ Command to stop Supvisors applications using rules. """
        if self._upcheck():
            # get all application info
            try:
                all_info = {application_info['application_name']: application_info['managed']
                            for application_info in self.supvisors().get_all_applications_info()}
            except xmlrpclib.Fault as e:
                self.ctl.output('ERROR ({})'.format(e.faultString))
                self.ctl.exitstatus = LSBInitExitStatuses.GENERIC
                return
            # match with parameters
            args = as_string(arg).split()
            matching_info = self._get_matching_applications(args, all_info, 'stop')
            # request start for matching applications
            for application_name in matching_info:
                try:
                    result = self.supvisors().stop_application(application_name)
                except xmlrpclib.Fault as e:
                    self.ctl.output('{}: ERROR ({})'.format(application_name, e.faultString))
                    self.ctl.exitstatus = LSBInitExitStatuses.GENERIC
                else:
                    self.ctl.output('{} stopped: {}'.format(application_name, result))

    def help_stop_application(self):
        """ Print the help of the stop_application command."""
        self.ctl.output('stop_application <appli>\t\t\tStop the managed application named appli.')
        self.ctl.output('stop_application <appli> <appli>\t\tStop multiple managed named applications.')
        self.ctl.output('stop_application\t\t\t\tStop all managed applications.')

    def do_all_start(self, arg):
        """ Invoke the same Supervisor start command over all running nodes. """
        if self._upcheck():
            args = arg.split()
            if len(args) < 1:
                self.ctl.output('ERROR: all_start requires a process name')
                self.ctl.exitstatus = LSBInitExitStatuses.INVALID_ARGS
                self.help_all_start()
                return
            namespec = args[0]
            # get running instances
            urls = self.get_running_instances()
            # send the start command to all instances
            if urls:
                for identifier, url in urls.items():
                    try:
                        # no wait
                        proxy = self.get_server_proxy(url, 'supervisor')
                        result = proxy.startProcess(namespec, False)
                    except xmlrpclib.Fault as e:
                        self.ctl.output(f'{namespec}: ERROR ({e.faultString})')
                        self.ctl.exitstatus = LSBInitExitStatuses.GENERIC
                    else:
                        self.ctl.output(f'{namespec} started on {identifier}: {result}')
            else:
                self.ctl.output(f'ERROR: no running Supvisors instance')

    def help_all_start(self):
        """ Print the help of the all_start command."""
        self.ctl.output('all_start <proc>\t\t\t'
                        'Start the process named proc on all RUNNING Supvisors instances.')

    def do_start_args(self, arg):
        """ Command to start a local process with additional arguments. """
        if self._upcheck():
            args = arg.split()
            if len(args) < 2:
                self.ctl.output('ERROR: start_args requires a process name and extra arguments')
                self.ctl.exitstatus = LSBInitExitStatuses.INVALID_ARGS
                self.help_start_args()
                return
            namespec = args[0]
            try:
                result = self.supvisors().start_args(namespec, ' '.join(args[1:]))
            except xmlrpclib.Fault as e:
                self.ctl.output(f'{namespec}: ERROR ({e.faultString})')
                self.ctl.exitstatus = LSBInitExitStatuses.GENERIC
            else:
                self.ctl.output(f'{namespec} started: {result}')

    def help_start_args(self):
        """ Print the help of the start_args command."""
        self.ctl.output('start_args <proc> <arg_list>\t\t\t'
                        'Start the local process named proc with additional arguments arg_list.')

    def do_all_start_args(self, arg):
        """ Invoke the same Supvisors start_args command over all running nodes. """
        if self._upcheck():
            args = arg.split()
            if len(args) < 2:
                self.ctl.output('ERROR: all_start_args requires a process name and extra arguments')
                self.ctl.exitstatus = LSBInitExitStatuses.INVALID_ARGS
                self.help_all_start_args()
                return
            namespec = args[0]
            # get running instances
            urls = self.get_running_instances()
            if urls:
                # send the start command to all instances
                for identifier, url in urls.items():
                    try:
                        # no wait
                        result = self.get_server_proxy(url, 'supvisors').start_args(namespec, ' '.join(args[1:]), False)
                    except xmlrpclib.Fault as e:
                        self.ctl.output(f'{namespec}: ERROR ({e.faultString})')
                        self.ctl.exitstatus = LSBInitExitStatuses.GENERIC
                    else:
                        self.ctl.output(f'{namespec} started on {identifier}: {result}')
            else:
                self.ctl.output(f'ERROR: no running Supvisors instance')

    def help_all_start_args(self):
        """ Print the help of the all_start_args command."""
        self.ctl.output('all_start_args <proc> <arg_list>\t\t\t'
                        'Start the process named proc on all RUNNING Supvisors instances'
                        ' with additional arguments arg_list.')

    def do_start_process(self, arg):
        """ Command to start processes with a strategy and rules. """
        if self._upcheck():
            args = arg.split()
            if len(args) < 1:
                self.ctl.output('ERROR: start_process requires at least a strategy')
                self.ctl.exitstatus = LSBInitExitStatuses.INVALID_ARGS
                self.help_start_process()
                return
            try:
                strategy = StartingStrategies[args[0]]
            except KeyError:
                self.ctl.output('ERROR: unknown strategy for start_process.'
                                f' use one of {[x.name for x in StartingStrategies]}')
                self.ctl.exitstatus = LSBInitExitStatuses.INVALID_ARGS
                self.help_start_process()
                return
            namespecs = args[1:]
            if not namespecs or 'all' in namespecs:
                try:
                    namespecs = [make_namespec(info['application_name'], info['process_name'])
                                 for info in self.supvisors().get_all_process_info()]
                except xmlrpclib.Fault as e:
                    self.ctl.output(f'ERROR ({e.faultString})')
                    self.ctl.exitstatus = LSBInitExitStatuses.GENERIC
                    namespecs = []
            for namespec in sorted(namespecs):
                try:
                    result = self.supvisors().start_process(strategy.value, namespec)
                except xmlrpclib.Fault as e:
                    self.ctl.output(f'{namespec}: ERROR ({e.faultString})')
                    self.ctl.exitstatus = LSBInitExitStatuses.GENERIC
                else:
                    self.ctl.output(f'{namespec} started: {result}')

    def help_start_process(self):
        """ Print the help of the start_process command."""
        self.ctl.output('start_process <strategy> <proc>\t\t\tStart the process named proc with strategy.')
        self.ctl.output('start_process <strategy> <proc> <proc>\t\tStart multiple named processes with strategy.')
        self.ctl.output('start_process <strategy>\t\t\tStart all processes with strategy.')

    def do_start_any_process(self, arg):
        """ Command to start processes using regular expressions, with a strategy and rules. """
        if self._upcheck():
            args = arg.split()
            if len(args) < 2:
                self.ctl.output('ERROR: start_any_process requires a strategy and at least a regular expression')
                self.ctl.exitstatus = LSBInitExitStatuses.INVALID_ARGS
                self.help_start_any_process()
                return
            try:
                strategy = StartingStrategies[args[0]]
            except KeyError:
                self.ctl.output('ERROR: unknown strategy for start_any_process.'
                                f' use one of {[x.name for x in StartingStrategies]}')
                self.ctl.exitstatus = LSBInitExitStatuses.INVALID_ARGS
                self.help_start_any_process()
                return
            regexes = args[1:]
            for regex in sorted(regexes):
                try:
                    result = self.supvisors().start_any_process(strategy.value, regex)
                except xmlrpclib.Fault as e:
                    self.ctl.output(f'"{regex}": ERROR ({e.faultString})')
                    self.ctl.exitstatus = LSBInitExitStatuses.GENERIC
                else:
                    self.ctl.output(f'{result} started')

    def help_start_any_process(self):
        """ Print the help of the start_any_process command."""
        self.ctl.output('start_any_process <strategy> <regex>\t\t\t'
                        'Start a process whose namespec matches the regular expression and with a starting strategy.')
        self.ctl.output('start_any_process <strategy> <regex> <regex>\t\t'
                        'Start multiple processes whose namespec matches the regular expressions'
                        ' and with a starting strategy.')

    # start a process using strategy, rules and additional arguments
    def do_start_process_args(self, arg):
        """ Command to start a process with a strategy, rules and additional arguments. """
        if self._upcheck():
            args = arg.split()
            if len(args) < 3:
                self.ctl.output('ERROR: start_process_args requires a strategy, '
                                'a program namespec and extra arguments')
                self.ctl.exitstatus = LSBInitExitStatuses.INVALID_ARGS
                self.help_start_process_args()
                return
            try:
                strategy = StartingStrategies[args[0]]
            except KeyError:
                self.ctl.output('ERROR: unknown strategy for start_process_args.'
                                f' use one of {[x.name for x in StartingStrategies]}')
                self.ctl.exitstatus = LSBInitExitStatuses.INVALID_ARGS
                self.help_start_process_args()
                return
            namespec = args[1]
            try:
                result = self.supvisors().start_process(strategy.value, namespec, ' '.join(args[2:]))
            except xmlrpclib.Fault as e:
                self.ctl.output(f'{namespec}: ERROR ({e.faultString})')
                self.ctl.exitstatus = LSBInitExitStatuses.GENERIC
            else:
                self.ctl.output(f'{namespec} started: {result}')

    def help_start_process_args(self):
        """ Print the help of the start_process_args command."""
        self.ctl.output('start_process <strategy> <proc> <arg_list>\t'
                        'Start the process named proc with additional arguments arg_list.')

    def do_start_any_process_args(self, arg):
        """ Command to start processes using regular expressions, with a strategy and rules. """
        if self._upcheck():
            args = arg.split()
            if len(args) < 3:
                self.ctl.output('ERROR: start_any_process_args requires a strategy, a regular expression'
                                ' and extra arguments')
                self.ctl.exitstatus = LSBInitExitStatuses.INVALID_ARGS
                self.help_start_any_process_args()
                return
            try:
                strategy = StartingStrategies[args[0]]
            except KeyError:
                self.ctl.output('ERROR: unknown strategy for start_any_process_args.'
                                f' use one of {[x.name for x in StartingStrategies]}')
                self.ctl.exitstatus = LSBInitExitStatuses.INVALID_ARGS
                self.help_start_any_process_args()
                return
            regex = args[1]
            try:
                result = self.supvisors().start_any_process(strategy.value, regex, ' '.join(args[2:]))
            except xmlrpclib.Fault as e:
                self.ctl.output(f'"{regex}": ERROR ({e.faultString})')
                self.ctl.exitstatus = LSBInitExitStatuses.GENERIC
            else:
                self.ctl.output(f'{result} started')

    def help_start_any_process_args(self):
        """ Print the help of the start_any_process_args command."""
        self.ctl.output('start_any_process_args <strategy> <regex> <arg_list>\t'
                        'Start a process whose namespec matches the regular expression, using a starting strategy and'
                        ' additional arguments arg_list.')

    def do_stop_process(self, arg):
        """ Command to stop processes with rules. """
        if self._upcheck():
            namespecs = arg.split()
            if not namespecs or 'all' in namespecs:
                try:
                    namespecs = [make_namespec(info['application_name'], info['process_name'])
                                 for info in self.supvisors().get_all_process_info()]
                except xmlrpclib.Fault as e:
                    self.ctl.output(f'ERROR ({e.faultString})')
                    self.ctl.exitstatus = LSBInitExitStatuses.GENERIC
                    namespecs = []
            for namespec in sorted(namespecs):
                try:
                    self.supvisors().stop_process(namespec)
                except xmlrpclib.Fault as e:
                    self.ctl.output(f'{namespec}: ERROR ({e.faultString})')
                    self.ctl.exitstatus = LSBInitExitStatuses.GENERIC
                else:
                    self.ctl.output(f'{namespec} stopped')

    def help_stop_process(self):
        """ Print the help of the stop_process command."""
        self.ctl.output('stop_process <proc>\t\tStop the process named proc.')
        self.ctl.output('stop_process <proc> <proc>\tStop multiple named processes.')
        self.ctl.output('stop_process\t\t\tStop all named processes.')

    def do_restart_process(self, arg):
        """ Command to restart processes with a strategy and rules. """
        if self._upcheck():
            args = arg.split()
            if len(args) < 1:
                self.ctl.output('ERROR: restart_process requires a strategy and a program name')
                self.ctl.exitstatus = LSBInitExitStatuses.INVALID_ARGS
                self.help_restart_process()
                return
            try:
                strategy = StartingStrategies[args[0]]
            except KeyError:
                self.ctl.output(f'ERROR: unknown strategy={args[0]}. use one of {[x.name for x in StartingStrategies]}')
                self.ctl.exitstatus = LSBInitExitStatuses.INVALID_ARGS
                self.help_restart_process()
                return
            processes = args[1:]
            if not processes or 'all' in processes:
                try:
                    processes = [make_namespec(info['application_name'], info['process_name'])
                                 for info in self.supvisors().get_all_process_info()]
                except xmlrpclib.Fault as e:
                    self.ctl.output('ERROR ({})'.format(e.faultString))
                    self.ctl.exitstatus = LSBInitExitStatuses.GENERIC
                    processes = []
            for process in sorted(processes):
                try:
                    result = self.supvisors().restart_process(strategy.value, process)
                except xmlrpclib.Fault as e:
                    self.ctl.output('{}: ERROR ({})'.format(process, e.faultString))
                    self.ctl.exitstatus = LSBInitExitStatuses.GENERIC
                else:
                    self.ctl.output('{} restarted: {}'.format(process, result))

    def help_restart_process(self):
        """ Print the help of the restart_process command."""
        self.ctl.output("restart_process <strategy> <proc>\t\t"
                        "Restart the process named proc using strategy.")
        self.ctl.output("restart_process <strategy> <proc> <proc>\t"
                        "Restart multiple named processes using strategy.")
        self.ctl.output("restart_process <strategy> \t\t\t"
                        "Restart all processes using strategy.")

    def do_update_numprocs(self, arg):
        """ Command to dynamically update the numprocs of the program.
        Implementation of Supervisor issue #177 - Dynamic numproc change.
        """
        if self._upcheck():
            args = arg.split()
            if len(args) < 2:
                self.ctl.output('ERROR: update_numprocs requires a program name and a numprocs values')
                self.ctl.exitstatus = LSBInitExitStatuses.INVALID_ARGS
                self.help_update_numprocs()
                return
            try:
                value = int(args[1])
                assert value > 0
            except (ValueError, AssertionError):
                self.ctl.output('ERROR: numprocs must be a strictly positive integer')
                self.ctl.exitstatus = LSBInitExitStatuses.INVALID_ARGS
                self.help_update_numprocs()
                return
            try:
                result = self.supvisors().update_numprocs(args[0], value)
            except xmlrpclib.Fault as e:
                self.ctl.output(f'ERROR ({e.faultString})')
                self.ctl.exitstatus = LSBInitExitStatuses.GENERIC
            else:
                self.ctl.output('{} numprocs updated: {}'.format(args[0], result))

    def help_update_numprocs(self):
        """ Print the help of the update_numprocs command. """
        self.ctl.output('update_numprocs program_name numprocs\t\t\t\tUpdate the program numprocs.')

    def do_enable(self, arg):
        """ Command to enable the processes corresponding to the program.
        Implementation of Supervisor issue #591 - New Feature: disable/enable.
        """
        if self._upcheck():
            args = arg.split()
            if len(args) < 1:
                self.ctl.output('ERROR: enable requires a program name')
                self.ctl.exitstatus = LSBInitExitStatuses.INVALID_ARGS
                self.help_enable()
                return
            try:
                result = self.supvisors().enable(args[0])
            except xmlrpclib.Fault as e:
                self.ctl.output(f'ERROR ({e.faultString})')
                self.ctl.exitstatus = LSBInitExitStatuses.GENERIC
            else:
                self.ctl.output(f'{args[0]} enabled: {result}')

    def help_enable(self):
        """ Print the help of the enable command. """
        self.ctl.output('enable program_name\t\t\t\tEnable the program.')

    def do_disable(self, arg):
        """ Command to disable the processes corresponding to the program.
        Implementation of Supervisor issue #591 - New Feature: disable/enable.
        """
        if self._upcheck():
            args = arg.split()
            if len(args) < 1:
                self.ctl.output('ERROR: disable requires a program name')
                self.ctl.exitstatus = LSBInitExitStatuses.INVALID_ARGS
                self.help_disable()
                return
            try:
                result = self.supvisors().disable(args[0])
            except xmlrpclib.Fault as e:
                self.ctl.output(f'ERROR ({e.faultString})')
                self.ctl.exitstatus = LSBInitExitStatuses.GENERIC
            else:
                self.ctl.output(f'{args[0]} disabled: {result}')

    def help_disable(self):
        """ Print the help of the disable command. """
        self.ctl.output('disable program_name\t\t\t\tDisable the program.')

    def do_conciliate(self, arg):
        """ Command to conciliate conflicts (applicable with default USER strategy). """
        if self._upcheck():
            args = arg.split()
            if len(args) < 1:
                self.ctl.output('ERROR: conciliate requires a strategy')
                self.ctl.exitstatus = LSBInitExitStatuses.INVALID_ARGS
                self.help_conciliate()
                return
            try:
                strategy = ConciliationStrategies[args[0]]
            except KeyError:
                self.ctl.output(f'ERROR: unknown strategy for conciliate.'
                                f' use one of {[x.name for x in ConciliationStrategies]}')
                self.ctl.exitstatus = LSBInitExitStatuses.INVALID_ARGS
                self.help_conciliate()
                return
            try:
                result = self.supvisors().conciliate(strategy.value)
            except xmlrpclib.Fault as e:
                self.ctl.output(f'ERROR ({e.faultString})')
                self.ctl.exitstatus = LSBInitExitStatuses.GENERIC
            else:
                self.ctl.output(f'Conciliated: {result}')

    def help_conciliate(self):
        """ Print the help of the conciliate command. """
        self.ctl.output('conciliate <strategy>\t\t\t\t\tConciliate process conflicts using strategy')

    def do_restart_sequence(self, _):
        """ Command to trigger the whole start sequence of Supvisors. """
        if self._upcheck():
            try:
                result = self.supvisors().restart_sequence()
            except xmlrpclib.Fault as e:
                self.ctl.output(f'ERROR ({e.faultString})')
                self.ctl.exitstatus = LSBInitExitStatuses.GENERIC
            else:
                self.ctl.output(f'Start sequence completed: {result}')

    def help_restart_sequence(self):
        """ Print the help of the restart_sequence command."""
        self.ctl.output('restart_sequence\t\t\t\t\tTrigger the whole start sequence')

    def do_sreload(self, _):
        """ Command to restart Supvisors on all instances. """
        if self._upcheck():
            try:
                result = self.supvisors().restart()
            except xmlrpclib.Fault as e:
                self.ctl.output(f'ERROR ({e.faultString})')
                self.ctl.exitstatus = LSBInitExitStatuses.GENERIC
            else:
                self.ctl.output(f'Restarted: {result}')

    def help_sreload(self):
        """ Print the help of the sreload command."""
        self.ctl.output('sreload\t\t\t\t\tRestart Supvisors on all instances')

    def do_sshutdown(self, _):
        """ Command to shutdown Supvisors on all instances. """
        if self._upcheck():
            try:
                result = self.supvisors().shutdown()
            except xmlrpclib.Fault as e:
                self.ctl.output(f'ERROR ({e.faultString})')
                self.ctl.exitstatus = LSBInitExitStatuses.GENERIC
            else:
                self.ctl.output(f'Shut down: {result}')

    def help_sshutdown(self):
        """ Print the help of the sshutdown command."""
        self.ctl.output('sshutdown\t\t\t\tShutdown Supvisors on all instances')

    def do_end_sync(self, arg):
        """ Command to end the Supvisors synchronization phase. """
        if self._upcheck():
            # check request args
            args = arg.split()
            if len(args) > 1:
                self.ctl.output('ERROR: end_sync optionally takes one single Supvisors identifier')
                self.ctl.exitstatus = LSBInitExitStatuses.INVALID_ARGS
                self.help_end_sync()
                return
            master = args[0] if args else ''
            try:
                result = self.supvisors().end_sync(master)
            except xmlrpclib.Fault as e:
                self.ctl.output(f'ERROR ({e.faultString})')
                self.ctl.exitstatus = LSBInitExitStatuses.GENERIC
            else:
                self.ctl.output(f'End of Synchronization phase requested: {result}')

    def help_end_sync(self):
        """ Print the help of the end_sync command."""
        self.ctl.output('end_sync\t\t\t\tEnd the Supvisors synchronization phase')
        self.ctl.output('end_sync master_identifier\t\tEnd the Supvisors synchronization phase'
                        ' and select this identifier as Supvisors Master instance ')

    def do_loglevel(self, arg):
        """ Command to change the level of the local Supvisors. """
        if self._upcheck():
            args = arg.split()
            if len(args) < 1:
                self.ctl.output('ERROR: loglevel requires a level')
                self.ctl.exitstatus = LSBInitExitStatuses.INVALID_ARGS
                self.help_loglevel()
                return
            level = getLevelNumByDescription(args[0])
            if level is None:
                self.ctl.output('ERROR: unknown level for Logger')
                self.ctl.exitstatus = LSBInitExitStatuses.INVALID_ARGS
                self.help_loglevel()
                return
            try:
                result = self.supvisors().change_log_level(level)
            except xmlrpclib.Fault as e:
                self.ctl.output(f'ERROR ({e.faultString})')
                self.ctl.exitstatus = LSBInitExitStatuses.GENERIC
            else:
                self.ctl.output(f'Logger level changed: {result}')

    def help_loglevel(self):
        """ Print the help of the loglevel command."""
        self.ctl.output('loglevel lvl\t\t\t\tChange the level of local Supvisors\' logger to lvl.')
        values = RPCInterface.get_logger_levels().values()
        self.ctl.output(f'\t\t\t\t\tApplicable values are: {values}.')

    def _upcheck(self):
        """ Check of the API versions. """
        try:
            api = self.supvisors().get_api_version()
            if api != API_VERSION:
                self.ctl.output('ERROR: this version of supvisorsctl expects to talk to a server '
                                'with API version %s, but the remote version is %s.' % (API_VERSION, api))
                self.ctl.exitstatus = LSBInitExitStatuses.NOT_INSTALLED
                return False
        except xmlrpclib.Fault as e:
            if e.faultCode == xmlrpc.Faults.UNKNOWN_METHOD:
                self.ctl.output('ERROR: supervisord responded but did not recognize '
                                'the supvisors namespace commands that supervisorstl uses to control it. '
                                'Please check that the [rpcinterface:supvisors] section is enabled '
                                'in the configuration file.')
                self.ctl.exitstatus = LSBInitExitStatuses.UNIMPLEMENTED_FEATURE
                return False
            self.exitstatus = LSBInitExitStatuses.GENERIC
            raise
        except socket.error as why:
            if why.args[0] == errno.ECONNREFUSED:
                self.ctl.output(f'ERROR: {self.ctl.options.serverurl} refused connection')
                self.ctl.exitstatus = LSBInitExitStatuses.INSUFFICIENT_PRIVILEGES
                return False
            elif why.args[0] == errno.ENOENT:
                self.ctl.output(f'ERROR: {self.ctl.options.serverurl} no such file')
                self.ctl.exitstatus = LSBInitExitStatuses.NOT_RUNNING
                return False
            self.exitstatus = LSBInitExitStatuses.GENERIC
            raise
        return True


def make_supvisors_controller_plugin(controller):
    """ Create a plugin for the Supvisors commands. """
    return ControllerPlugin(controller)


# Copied and adapted from supervisor.supervisorctl source code
def main(args=None, options=None):
    # read options
    if options is None:
        options = ClientOptions()
    options.realize(args, doc=supervisorctl.__doc__)
    # add supvisors plugin if not there
    if not any(factory[0] == 'supvisors' for factory in options.plugin_factories):
        options.plugin_factories.append(('supvisors', make_supvisors_controller_plugin, {}))
    # create controller
    c = Controller(options)
    # process single command
    if options.args:
        c.onecmd(' '.join(options.args))
        sys.exit(c.exitstatus)
    # enter the interactive mode
    if options.interactive:
        c.exec_cmdloop(args, options)
        sys.exit(0)  # exitstatus always 0 for interactive mode
