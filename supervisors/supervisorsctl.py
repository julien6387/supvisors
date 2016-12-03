#!/usr/bin/python
#-*- coding: utf-8 -*-

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
import xmlrpclib

from supervisor import xmlrpc
from supervisor.supervisorctl import ControllerPluginBase

from supervisors.rpcinterface import API_VERSION
from supervisors.ttypes import DeploymentStrategies
from supervisors.utils import simple_localtime


class ControllerPlugin(ControllerPluginBase):

    def supervisors(self):
        return self.ctl.get_server_proxy('supervisors')

    # get Supervisors API version
    def do_sversion(self, arg):
        if self._upcheck():
            version = self.supervisors().get_api_version()
            self.ctl.output(version)

    def help_sversion(self):
        self.ctl.output("sversion\t\t\t\tGet the API version of Supervisors.")

    # get Supervisors master address
    def do_master(self, arg):
        if self._upcheck():
            try:
                address = self.supervisors().get_master_address()
            except xmlrpclib.Fault, e:
                self.ctl.output('ERROR ({})'.format(e.faultString))
            else:
                self.ctl.output(address)

    def help_master(self):
        self.ctl.output("master\t\t\t\t\tGet the Supervisors master address.")

    # get Supervisors state
    def do_sstate(self, arg):
        if self._upcheck():
            state = self.supervisors().get_supervisors_state()
            self.ctl.output(state)

    def help_sstate(self):
        self.ctl.output("sstate\t\t\t\t\tGet the Supervisors state.")

    # get Supervisors list of addresses
    def do_address_status(self, arg):
        if self._upcheck():
            addresses = arg.split()
            if not addresses or "all" in addresses:
                infos = self.supervisors().get_all_addresses_info()
                for info in infos:
                    self.output_address_info(info)
            else:
                for address in addresses:
                    try:
                        info = self.supervisors().get_address_info(address)
                    except xmlrpclib.Fault, e:
                        self.ctl.output('{}: ERROR ({})'.format(address, e.faultString))
                    else:
                        self.output_address_info(info)

    def output_address_info(self, info):
        template = '%(addr)-20s%(state)-12s%(checked)-12s%(load)-8s%(ltime)-12s'
        checked = info['checked']
        line = template % {'addr': info['address'], 'state': info['state'], 'checked': 'checked' if checked else 'unchecked',
            'load': '{}%'.format(info['loading']), 'ltime': simple_localtime(info['local_time']) if checked else ''}
        self.ctl.output(line)

    def help_address_status(self):
        self.ctl.output("address_status <addr>\t\t\tGet the status of remote supervisord managed in Supervisors and running on addr.")
        self.ctl.output("address_status <addr> <addr>\t\tGet the status for multiple addresses")
        self.ctl.output("address_status\t\t\t\tGet the status of all remote supervisord managed in Supervisors.")

    # get Supervisors application info
    def do_application_info(self, arg):
        if self._upcheck():
            applications = arg.split()
            if not applications or "all" in applications:
                infos = self.supervisors().get_all_applications_info()
                for info in infos:
                    self.output_application_info(info)
            else:
                for application_name in applications:
                    try:
                        info = self.supervisors().get_application_info(application_name)
                    except xmlrpclib.Fault, e:
                        self.ctl.output('{}: ERROR ({})'.format(application_name, e.faultString))
                    else:
                        self.output_application_info(info)

    def output_application_info(self, info):
        template = '%(name)-20s%(state)-12s%(major_failure)-15s%(minor_failure)-15s'
        major_failure = info['major_failure']
        minor_failure = info['minor_failure']
        line = template % {'name': info['application_name'], 'state': info['state'],
            'major_failure': 'major_failure' if major_failure else '', 'minor_failure': 'minor_failure' if minor_failure else ''}
        self.ctl.output(line)

    def help_application_info(self):
        self.ctl.output("application_info <appli>\t\tGet the status of application named appli.")
        self.ctl.output("application_info <appli> <appli>\tGet the status for multiple named application")
        self.ctl.output("application_info\t\t\tGet the status of all applications.")

    # get Supervisors process list of an application
    def do_sstatus(self, arg):
        if self._upcheck():
            processes = arg.split()
            if not processes or "all" in processes:
                processes = ['{}:*'.format(application_info['application_name']) for application_info in self.supervisors().get_all_applications_info()]
            template = '%(name)-30s%(state)-12s%(conflict)-12s%(addresses)s'
            for process in processes:
                try:
                    infoList = self.supervisors().get_process_info(process)
                except xmlrpclib.Fault, e:
                    self.ctl.output('{}: ERROR ({})'.format(process, e.faultString))
                else:
                    for info in infoList:
                        conflict = info['conflict']
                        line = template % {'name': info['process_name'], 'state': info['state'], 'conflict': 'conflict' if conflict else '', 'addresses': info['address']}
                        self.ctl.output(line)

    def help_sstatus(self):
        self.ctl.output("sstatus <proc>\t\t\t\tGet the status of the process named proc.")
        self.ctl.output("sstatus <appli>:*\t\t\tGet the process status of application named appli.")
        self.ctl.output("sstatus <proc> <proc>\t\t\tGet the status for multiple named processes")
        self.ctl.output("sstatus\t\t\t\t\tGet the status of all processes.")

    # get Supervisors deployment rules for processes
    def do_rules(self, arg):
        if self._upcheck():
            processes = arg.split()
            if not processes or "all" in processes:
                processes = ['{}:*'.format(application_info['application_name']) for application_info in self.supervisors().get_all_applications_info()]
            template = '%(name)-30s%(start_seq)-12s%(stop_seq)-12s%(req)-12s%(exit)-12s%(load)-12s%(addr)s'
            for process in processes:
                try:
                    rulesList = self.supervisors().get_process_rules(process)
                except xmlrpclib.Fault, e:
                    self.ctl.output('{}: ERROR ({})'.format(process, e.faultString))
                else:
                    for rules in rulesList:
                        required = rules['required']
                        wait_exit = rules['wait_exit']
                        line = template % {'name': rules['namespec'], 'addr': rules['addresses'],
                            'start_seq': rules['start_sequence'], 'stop_seq': rules['stop_sequence'], 
                            'req': 'required' if required else 'optional', 'exit': 'exit' if wait_exit else '',
                            'load': '{}%'.format(rules['expected_loading'])}
                        self.ctl.output(line)

    def help_rules(self):
        self.ctl.output("rules <proc>\t\t\t\tGet the deployment rules of the process named proc.")
        self.ctl.output("rules <appli>:*\t\t\t\tGet the deployment rules of all processes in the application named appli.")
        self.ctl.output("rules <proc> <proc>\t\t\tGet the deployment rules for multiple named processes")
        self.ctl.output("rules\t\t\t\t\tGet the deployment rules of all processes.")

    # get conflicts
    def do_conflicts(self, arg):
        if self._upcheck():
            try:
                conflicts = self.supervisors().get_conflicts()
            except xmlrpclib.Fault, e:
                self.ctl.output('ERROR ({})'.format(e.faultString))
            else:
                template = '%(name)-30s%(state)-12s%(addresses)s'
                for conflict in conflicts:
                    line = template % {'name': conflict['process_name'], 'state': conflict['state'], 'addresses': conflict['address']}
                    self.ctl.output(line)

    def help_conflicts(self):
        self.ctl.output("conflicts\t\t\t\tGet the Supervisors conflicts.")

    # start an application using strategy and rules
    def do_start_application(self, arg):
        if self._upcheck():
            args = arg.split()
            if len(args) < 2:
                self.ctl.output('ERROR: start_application requires a strategy and an application name')
                self.help_start_application()
                return
            strategy = DeploymentStrategies._from_string(args[0])
            if strategy is None:
                self.ctl.output('ERROR: unknown strategy for start_application. use one of {}'.format(DeploymentStrategies._strings()))
                self.help_start_application()
                return
            applications = args[1:]
            if not applications or "all" in applications:
                applications = [application_info['application_name'] for application_info in self.supervisors().get_all_applications_info()]
            for application in applications:
                try:
                    result = self.supervisors().start_application(strategy, application)
                except xmlrpclib.Fault, e:
                    self.ctl.output('{}: ERROR ({})'.format(application, e.faultString))
                else:
                    self.ctl.output('{} started: {}'.format(application, result))

    def help_start_application(self):
        self.ctl.output("start_application <strategy> <appli>\t\tStart the application named appli with strategy.")
        self.ctl.output("start_application <strategy> <appli> <appli>\tStart multiple named applications with strategy")
        self.ctl.output("start_application <strategy> \t\t\tStart all named applications with strategy.")

    # stop an application
    def do_stop_application(self, arg):
        if self._upcheck():
            applications = arg.split()
            if not applications or "all" in applications:
                applications = [application_info['application_name'] for application_info in self.supervisors().get_all_applications_info()]
            for application in applications:
                try:
                    self.supervisors().stop_application(application)
                except xmlrpclib.Fault, e:
                    self.ctl.output('{}: ERROR ({})'.format(application, e.faultString))
                else:
                    self.ctl.output('{} stopped'.format(application))

    def help_stop_application(self):
        self.ctl.output("stop_application <appli>\t\t\tStop the application named appli with strategy.")
        self.ctl.output("stop_application <appli> <appli>\t\tStop multiple named applications with strategy")
        self.ctl.output("stop_application\t\t\t\tStop all named applications with strategy.")

    # restart an application using strategy and rules
    def do_restart_application(self, arg):
        if self._upcheck():
            args = arg.split()
            if len(args) < 2:
                self.ctl.output('ERROR: restart_application requires a strategy and an application name')
                self.help_restart_application()
                return
            strategy = DeploymentStrategies._from_string(args[0])
            if strategy is None:
                self.ctl.output('ERROR: unknown strategy for restart_application. use one of {}'.format(DeploymentStrategies._strings()))
                self.help_restart_application()
                return
            applications = args[1:]
            if not applications or "all" in applications:
                applications = [ application_info['application_name'] for application_info in self.supervisors().get_all_applications_info() ]
            for application in applications:
                try:
                    self.supervisors().restart_application(strategy, application)
                except xmlrpclib.Fault, e:
                    self.ctl.output('{}: ERROR ({})'.format(application, e.faultString))
                else:
                    self.ctl.output('{} restarted'.format(application))

    def help_restart_application(self):
        self.ctl.output("restart_application <strategy> <appli>\t\tStart the application named appli with strategy.")
        self.ctl.output("restart_application <strategy> <appli> <appli>\tStart multiple named applications with strategy")
        self.ctl.output("restart_application <strategy> \t\t\tStart all named applications with strategy.")

    # start a local process using strategy and rules
    def do_start_args(self, arg):
        if self._upcheck():
            args = arg.split()
            if len(args) < 2:
                self.ctl.output('ERROR: start_args requires a program name and extra arguments')
                self.help_start_args()
                return
            namespec = args[0]
            try:
                result = self.supervisors().start_args(namespec, ' '.join(args[1:]))
            except xmlrpclib.Fault, e:
                self.ctl.output('{}: ERROR ({})'.format(namespec, e.faultString))
            else:
                self.ctl.output('{} started: {}'.format(namespec, result))

    def help_start_args(self):
        self.ctl.output("Start a local process with additional arguments.")
        self.ctl.output("start_process <proc> <arg_list>\t\t\tStart the local process named proc with additional arguments arg_list.")

    # start a process using strategy and rules
    def do_start_process(self, arg):
        if self._upcheck():
            args = arg.split()
            if len(args) < 2:
                self.ctl.output('ERROR: start_process requires a strategy and a program name')
                self.help_start_process()
                return
            strategy = DeploymentStrategies._from_string(args[0])
            if strategy is None:
                self.ctl.output('ERROR: unknown strategy for start_process. use one of {}'.format(DeploymentStrategies._strings()))
                self.help_start_process()
                return
            processes = args[1:]
            if not processes or "all" in processes:
                processes = [ '{}:*'.format(application_info['application_name']) for application_info in self.supervisors().get_all_applications_info() ]
            for process in processes:
                try:
                    result = self.supervisors().start_process(strategy, process)
                except xmlrpclib.Fault, e:
                    self.ctl.output('{}: ERROR ({})'.format(process, e.faultString))
                else:
                    self.ctl.output('{} started: {}'.format(process, result))

    def help_start_process(self):
        self.ctl.output("Start a process with strategy.")
        self.ctl.output("start_process <strategy> <proc>\t\t\tStart the process named proc.")
        self.ctl.output("start_process <strategy> <proc> <proc>\t\tStart multiple named processes.")
        self.ctl.output("start_process <strategy> \t\t\tStart all named processes.")

    # start a process using strategy and rules
    def do_start_process_args(self, arg):
        if self._upcheck():
            args = arg.split()
            if len(args) < 3:
                self.ctl.output('ERROR: start_process_args requires a strategy, a program name and extra arguments')
                self.help_start_process_args()
                return
            strategy = DeploymentStrategies._from_string(args[0])
            if strategy is None:
                self.ctl.output('ERROR: unknown strategy for start_process_args. use one of {}'.format(DeploymentStrategies._strings()))
                self.help_start_process_args()
                return
            namespec = args[1]
            try:
                result = self.supervisors().start_process(strategy, namespec, ' '.join(args[2:]))
            except xmlrpclib.Fault, e:
                self.ctl.output('{}: ERROR ({})'.format(namespec, e.faultString))
            else:
                self.ctl.output('{} started: {}'.format(namespec, result))

    def help_start_process_args(self):
        self.ctl.output("Start a process with strategy and additional arguments.")
        self.ctl.output("start_process <strategy> <proc> <arg_list>\tStart the process named proc with additional arguments arg_list.")

    # stop a process
    def do_stop_process(self, arg):
        if self._upcheck():
            processes = arg.split()
            if not processes or "all" in processes:
                processes = [ '{}:*'.format(application_info['application_name']) for application_info in self.supervisors().get_all_applications_info() ]
            for process in processes:
                try:
                    self.supervisors().stop_process(process)
                except xmlrpclib.Fault, e:
                    self.ctl.output('{}: ERROR ({})'.format(process, e.faultString))
                else:
                    self.ctl.output('{} stopped'.format(process))

    def help_stop_process(self):
        self.ctl.output("Stop a process where it is running.")
        self.ctl.output("stop_process <strategy> <proc>\t\t\tStop the process named proc.")
        self.ctl.output("stop_process <strategy> <proc> <proc>\t\tStop multiple named processes.")
        self.ctl.output("stop_process <strategy> \t\t\tStop all named processes.")

    # restart a process using strategy and rules
    def do_restart_process(self, arg):
        if self._upcheck():
            args = arg.split()
            if len(args) < 2:
                self.ctl.output('ERROR: restart_process requires a strategy and a program name')
                self.help_restart_process()
                return
            strategy = DeploymentStrategies._from_string(args[0])
            if strategy is None:
                self.ctl.output('ERROR: unknown strategy for restart_process. use one of {}'.format(DeploymentStrategies._strings()))
                self.help_restart_process()
                return
            processes = args[1:]
            if not processes or "all" in processes:
                processes = [ '{}:*'.format(application_info['application_name']) for application_info in self.supervisors().get_all_applications_info() ]
            for process in processes:
                try:
                    result = self.supervisors().restart_process(strategy, process)
                except xmlrpclib.Fault, e:
                    self.ctl.output('{}: ERROR ({})'.format(process, e.faultString))
                else:
                    self.ctl.output('{} restarted: {}'.format(process, result))

    def help_restart_process(self):
        self.ctl.output("Restart a process with strategy and rules.")
        self.ctl.output("restart_process <strategy> <proc>\t\tRestart the process named proc.")
        self.ctl.output("restart_process <strategy> <proc> <proc>\tRestart multiple named processes.")
        self.ctl.output("restart_process <strategy> \t\t\tRestart all named processes.")

    # restart Supervisors
    def do_sreload(self, arg):
        if self._upcheck():
            self.supervisors().restart()

    def help_sreload(self):
        self.ctl.output("Restart Supervisors.")
        self.ctl.output("sreload\t\t\t\t\tRestart all remote supervisord")

    # shutdown Supervisors
    def do_sshutdown(self, arg):
        if self._upcheck():
            self.supervisors().shutdown()

    def help_sshutdown(self):
        self.ctl.output("Shutdown Supervisors.")
        self.ctl.output("sshutdown\t\t\t\tShut all remote supervisord down")

    # checking API versions
    def _upcheck(self):
        try:
            api = self.supervisors().get_api_version()
            if api != API_VERSION:
                self.ctl.output('Sorry, this version of supervisorsctl expects to talk to a server '
                    'with API version %s, but the remote version is %s.' % (API_VERSION, api))
                return False
        except xmlrpclib.Fault, e:
            if e.faultCode == xmlrpc.Faults.UNKNOWN_METHOD:
                self.ctl.output('Sorry, supervisord responded but did not recognize the supervisors namespace commands that supervisorsctl uses to control it. '
                    'Please check that the [rpcinterface:supervisor] section is enabled in the configuration file (see sample.conf).')
                return False
            raise
        except socket.error, why:
            if why.args[0] == errno.ECONNREFUSED:
                self.ctl.output('%s refused connection' % self.ctl.options.serverurl)
                return False
            elif why.args[0] == errno.ENOENT:
                self.ctl.output('%s no such file' % self.ctl.options.serverurl)
                return False
            raise
        return True


def make_supervisors_controller_plugin(supervisord, **config):
    return ControllerPlugin(supervisord)
    
