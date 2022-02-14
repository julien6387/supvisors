#!/usr/bin/python
# -*- coding: utf-8 -*-

# ======================================================================
# Copyright 2022 Julien LE CLEACH
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
import sys

from argparse import ArgumentParser
from flask import Flask, g, jsonify
from flask_restx import Resource, Api
from supervisor.childutils import getRPCInterface
from supervisor.rpcinterface import SupervisorNamespaceRPCInterface
from supervisor.xmlrpc import SystemNamespaceRPCInterface
from supvisors.rpcinterface import RPCInterface
from supvisors.ttypes import ConciliationStrategies, StartingStrategies, enum_names
from urllib.parse import urlparse


# Utilities
StartingStrategiesParam = ', '.join(enum_names(StartingStrategies))
ConciliationStrategiesParam = ', '.join(enum_names(ConciliationStrategies))
LoggerLevelsParam = ', '.join(RPCInterface.get_logger_levels().values())


def get_docstring_description(func) -> str:
    """ Extract the first part of the docstring. """
    description = []
    for line in func.__doc__.split('\n'):
        stripped_line = line.strip()
        if stripped_line.startswith('@') or stripped_line.startswith(':'):
            break
        description.append(stripped_line)
    return ' '.join(description)


# Create the Flask application
app = Flask('supvisors')
api = Api(app, title='Supvisors Flask interface')


@app.before_request
def get_supervisor_proxy():
    # get the Supervisor proxy
    supervisor_url = app.config.get('url')
    g.proxy = getRPCInterface({'SUPERVISOR_SERVER_URL': supervisor_url})
    # provide version information
    api.version = g.proxy.supvisors.get_api_version()


# System part
system_ns = api.namespace('system', description='System operations')


@system_ns.route('/listMethods', methods=('GET',))
@system_ns.doc(description=get_docstring_description(SystemNamespaceRPCInterface.listMethods))
class SystemListMethods(Resource):
    def get(self):
        return jsonify(g.proxy.system.listMethods())


@system_ns.route('/methodHelp/<string:name>', methods=('GET',))
@system_ns.doc(description=get_docstring_description(SystemNamespaceRPCInterface.methodHelp))
class SystemMethodHelp(Resource):
    @api.doc(params={'name': 'the name of the method'})
    def get(self, name):
        return jsonify(g.proxy.system.methodHelp(name))


@system_ns.route('/methodSignature/<string:name>', methods=('GET',))
@system_ns.doc(description=get_docstring_description(SystemNamespaceRPCInterface.methodSignature))
class SystemMethodSignature(Resource):
    @api.doc(params={'name': 'the name of the method'})
    def get(self, name):
        return jsonify(g.proxy.system.methodSignature(name))


# Supervisor part
supervisor_ns = api.namespace('supervisor', description='Supervisor operations')


@supervisor_ns.route('/getAPIVersion', methods=('GET',))
@supervisor_ns.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.getAPIVersion))
class SupervisorApiVersion(Resource):
    def get(self):
        return g.proxy.supervisor.getAPIVersion()


@supervisor_ns.route('/getSupervisorVersion', methods=('GET',))
@supervisor_ns.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.getSupervisorVersion))
class SupervisorVersion(Resource):
    def get(self):
        return g.proxy.supervisor.getSupervisorVersion()


@supervisor_ns.route('/getIdentification', methods=('GET',))
@supervisor_ns.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.getIdentification))
class SupervisorIdentification(Resource):
    def get(self):
        return g.proxy.supervisor.getIdentification()


@supervisor_ns.route('/getState', methods=('GET',))
@supervisor_ns.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.getState))
class SupervisorState(Resource):
    def get(self):
        return g.proxy.supervisor.getState()


@supervisor_ns.route('/getPID', methods=('GET',))
@supervisor_ns.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.getPID))
class SupervisorPid(Resource):
    def get(self):
        return g.proxy.supervisor.getPID()


@supervisor_ns.route('/readLog/<int:offset>/<int:length>', methods=('GET',))
@supervisor_ns.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.readLog))
class SupervisorReadLog(Resource):
    @api.doc(params={'offset': 'the offset to start reading from',
                     'length': 'the number of bytes to read from the log'})
    def get(self, offset, length):
        return g.proxy.supervisor.readLog(offset, length)


@supervisor_ns.route('/clearLog', methods=('POST',))
@supervisor_ns.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.clearLog))
class SupervisorClearLog(Resource):
    def post(self):
        return g.proxy.supervisor.clearLog()


@supervisor_ns.route('/shutdown', methods=('POST',))
@supervisor_ns.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.shutdown))
class SupervisorShutdown(Resource):
    def post(self):
        return g.proxy.supervisor.shutdown()


@supervisor_ns.route('/restart', methods=('POST',))
@supervisor_ns.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.restart))
class SupervisorRestart(Resource):
    def post(self):
        return g.proxy.supervisor.restart()


@supervisor_ns.route('/reloadConfig', methods=('POST',))
@supervisor_ns.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.reloadConfig))
class SupervisorReloadConfig(Resource):
    def post(self):
        return g.proxy.supervisor.reloadConfig()


@supervisor_ns.route('/addProcessGroup/<string:name>', methods=('POST',))
@supervisor_ns.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.addProcessGroup))
class SupervisorAddProcessGroup(Resource):
    @api.doc(params={'name': 'the name of the process group to add'})
    def post(self, name):
        return g.proxy.supervisor.addProcessGroup(name)


@supervisor_ns.route('/removeProcessGroup/<string:name>', methods=('POST',))
@supervisor_ns.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.removeProcessGroup))
class SupervisorRemoveProcessGroup(Resource):
    @api.doc(params={'name': 'the name of the process group to remove'})
    def post(self, name):
        return g.proxy.supervisor.removeProcessGroup(name)


@supervisor_ns.route('/startProcess/<string:name>', methods=('POST',))
@supervisor_ns.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.startProcess))
class SupervisorStartProcess(Resource):
    @api.doc(params={'name': 'the process name (or group:name, or group:*)'})
    def post(self, name):
        return g.proxy.supervisor.startProcess(name)


@supervisor_ns.route('/startProcessGroup/<string:name>', methods=('POST',))
@supervisor_ns.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.startProcessGroup))
class SupervisorStartProcessGroup(Resource):
    @api.doc(params={'name': 'the group name'})
    def post(self, name):
        return g.proxy.supervisor.startProcessGroup(name)


@supervisor_ns.route('/startAllProcesses', methods=('POST',))
@supervisor_ns.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.startAllProcesses))
class SupervisorStartAllProcesses(Resource):
    def post(self):
        return g.proxy.supervisor.startAllProcesses()


@supervisor_ns.route('/stopProcess/<string:name>', methods=('POST',))
@supervisor_ns.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.stopProcess))
class SupervisorStopProcess(Resource):
    @api.doc(params={'name': 'the name of the process to stop (or group:name)'})
    def post(self, name):
        return g.proxy.supervisor.stopProcess(name)


@supervisor_ns.route('/stopProcessGroup/<string:name>', methods=('POST',))
@supervisor_ns.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.stopProcessGroup))
class SupervisorStopProcessGroup(Resource):
    @api.doc(params={'name': 'the group name'})
    def post(self, name):
        return g.proxy.supervisor.stopProcessGroup(name)


@supervisor_ns.route('/stopAllProcesses', methods=('POST',))
@supervisor_ns.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.stopAllProcesses))
class SupervisorStopAllProcesses(Resource):
    def post(self):
        return g.proxy.supervisor.stopAllProcesses()


@supervisor_ns.route('/signalProcess/<string:name>/<string:signal>', methods=('POST',))
@supervisor_ns.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.signalProcess))
class SupervisorSignalProcess(Resource):
    @api.doc(params={'name': 'the name of the process to signal (or group:name)',
                     'signal': "the signal to send, as name ('HUP') or number ('1')"})
    def post(self, name, signal):
        return g.proxy.supervisor.signalProcess(name, signal)


@supervisor_ns.route('/signalProcessGroup/<string:name>/<string:signal>', methods=('POST',))
@supervisor_ns.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.signalProcessGroup))
class SupervisorSignalProcessGroup(Resource):
    @api.doc(params={'name': 'the group name',
                     'signal': "the signal to send, as name ('HUP') or number ('1')"})
    def post(self, name, signal):
        return g.proxy.supervisor.signalProcessGroup(name, signal)


@supervisor_ns.route('/signalAllProcesses/<string:signal>', methods=('POST',))
@supervisor_ns.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.signalAllProcesses))
class SupervisorSignalAllProcesses(Resource):
    @api.doc(params={'signal': "the signal to send, as name ('HUP') or number ('1')"})
    def post(self, signal):
        return g.proxy.supervisor.signalAllProcesses(signal)


@supervisor_ns.route('/getAllConfigInfo', methods=('GET',))
@supervisor_ns.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.getAllConfigInfo))
class SupervisorAllConfigInfo(Resource):
    def get(self):
        return jsonify(g.proxy.supervisor.getAllConfigInfo())


@supervisor_ns.route('/getProcessInfo/<string:name>', methods=('GET',))
@supervisor_ns.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.getProcessInfo))
class SupervisorAllConfigInfo(Resource):
    @api.doc(params={'name': 'the name of the process (or group:name)'})
    def get(self, name):
        return g.proxy.supervisor.getProcessInfo(name)


@supervisor_ns.route('/getAllProcessInfo', methods=('GET',))
@supervisor_ns.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.getAllProcessInfo))
class SupervisorAllProcessInfo(Resource):
    def get(self):
        return jsonify(g.proxy.supervisor.getAllProcessInfo())


@supervisor_ns.route('/readProcessStdoutLog/<string:name>/<int:offset>/<int:length>', methods=('GET',))
@supervisor_ns.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.readProcessStdoutLog))
class SupervisorReadProcessStdoutLog(Resource):
    @api.doc(params={'name': 'the name of the process (or group:name)',
                     'offset': 'the offset to start reading from',
                     'length': 'the number of bytes to read from the log'})
    def get(self, name, offset, length):
        return g.proxy.supervisor.readProcessStdoutLog(name, offset, length)


@supervisor_ns.route('/readProcessStderrLog/<string:name>/<int:offset>/<int:length>', methods=('GET',))
@supervisor_ns.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.readProcessStderrLog))
class SupervisorReadProcessStderrLog(Resource):
    @api.doc(params={'name': 'the name of the process (or group:name)',
                     'offset': 'the offset to start reading from',
                     'length': 'the number of bytes to read from the log'})
    def get(self, name, offset, length):
        return g.proxy.supervisor.readProcessStderrLog(name, offset, length)


@supervisor_ns.route('/tailProcessStdoutLog/<string:name>/<int:offset>/<int:length>', methods=('GET',))
@supervisor_ns.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.tailProcessStdoutLog))
class SupervisorTailProcessStdoutLog(Resource):
    @api.doc(params={'name': 'the name of the process (or group:name)',
                     'offset': 'the offset to start reading from',
                     'length': 'the number of bytes to read from the log'})
    def get(self, name, offset, length):
        return g.proxy.supervisor.tailProcessStdoutLog(name, offset, length)


@supervisor_ns.route('/tailProcessStderrLog/<string:name>/<int:offset>/<int:length>', methods=('GET',))
@supervisor_ns.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.tailProcessStderrLog))
class SupervisorTailProcessStderrLog(Resource):
    @api.doc(params={'name': 'the name of the process (or group:name)',
                     'offset': 'the offset to start reading from',
                     'length': 'the number of bytes to read from the log'})
    def get(self, name, offset, length):
        return g.proxy.supervisor.tailProcessStderrLog(name, offset, length)


@supervisor_ns.route('/clearProcessLogs/<string:name>', methods=('POST',))
@supervisor_ns.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.clearProcessLogs))
class SupervisorClearProcessLogs(Resource):
    @api.doc(params={'name': 'the name of the process (or group:name)'})
    def post(self, name):
        return g.proxy.supervisor.clearProcessLogs(name)


@supervisor_ns.route('/clearAllProcessLogs', methods=('POST',))
@supervisor_ns.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.clearAllProcessLogs))
class SupervisorClearAllProcessLogs(Resource):
    def post(self):
        return g.proxy.supervisor.clearAllProcessLogs()


@supervisor_ns.route('/sendProcessStdin/<string:name>/<string:chars>', methods=('POST',))
@supervisor_ns.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.sendProcessStdin))
class SupervisorSendProcessStdin(Resource):
    @api.doc(params={'name': 'the process name to send chars to (or group:name)',
                     'chars': 'the character data to send to the process'})
    def post(self, name, chars):
        return g.proxy.supervisor.sendProcessStdin(name, chars)


@supervisor_ns.route('/sendRemoteCommEvent/<string:event_type>/<string:data>', methods=('POST',))
@supervisor_ns.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.sendRemoteCommEvent))
class SupervisorSendProcessStdin(Resource):
    @api.doc(params={'event_type': 'the string for the "type" key in the event header',
                     'data': 'the data for the event body'})
    def post(self, event_type, data):
        return g.proxy.supervisor.sendRemoteCommEvent(event_type, data)


# Supvisors part
supvisors_ns = api.namespace('supvisors', description='Supvisors operations')


@supvisors_ns.route('/api_version', methods=('GET',))
@supvisors_ns.doc(description=get_docstring_description(RPCInterface.get_api_version))
class SupvisorsApiVersion(Resource):
    def get(self):
        return g.proxy.supvisors.get_api_version()


@supvisors_ns.route('/supvisors_state', methods=('GET',))
@supvisors_ns.doc(description=get_docstring_description(RPCInterface.get_supvisors_state))
class SupvisorsState(Resource):
    def get(self):
        return g.proxy.supvisors.get_supvisors_state()


@supvisors_ns.route('/master_identifier', methods=('GET',))
@supvisors_ns.doc(description=get_docstring_description(RPCInterface.get_master_identifier))
class SupvisorsMasterIdentifier(Resource):
    def get(self):
        return g.proxy.supvisors.get_master_identifier()


@supvisors_ns.route('/strategies', methods=('GET',))
@supvisors_ns.doc(description=get_docstring_description(RPCInterface.get_strategies))
class SupvisorsStrategies(Resource):
    def get(self):
        return g.proxy.supvisors.get_strategies()


@supvisors_ns.route('/all_instances_info', methods=('GET',))
@supvisors_ns.doc(description=get_docstring_description(RPCInterface.get_all_instances_info))
class SupvisorsAllInstancesInfo(Resource):
    def get(self):
        return jsonify(g.proxy.supvisors.get_all_instances_info())


@supvisors_ns.route('/instance_info/<string:identifier>', methods=('GET',))
@supvisors_ns.doc(description=get_docstring_description(RPCInterface.get_instance_info))
class SupvisorsInstanceInfo(Resource):
    @api.doc(params={'identifier': 'the identifier of a Supvisors instance'})
    def get(self, identifier):
        return g.proxy.supvisors.get_instance_info(identifier)


@supvisors_ns.route('/all_applications_info', methods=('GET',))
@supvisors_ns.doc(description=get_docstring_description(RPCInterface.get_all_applications_info))
class SupvisorsAllApplicationsInfo(Resource):
    def get(self):
        return jsonify(g.proxy.supvisors.get_all_applications_info())


@supvisors_ns.route('/application_info/<string:application_name>', methods=('GET',))
@supvisors_ns.doc(description=get_docstring_description(RPCInterface.get_application_info))
class SupvisorsApplicationInfo(Resource):
    @api.doc(params={'application_name': 'the name of an application managed in Supvisors'})
    def get(self, application_name):
        return g.proxy.supvisors.get_application_info(application_name)


@supvisors_ns.route('/application_rules/<string:application_name>', methods=('GET',))
@supvisors_ns.doc(description=get_docstring_description(RPCInterface.get_application_rules))
class SupvisorsApplicationRules(Resource):
    @api.doc(params={'application_name': 'the name of an application managed in Supvisors'})
    def get(self, application_name):
        return g.proxy.supvisors.get_application_rules(application_name)


@supvisors_ns.route('/all_process_info', methods=('GET',))
@supvisors_ns.doc(description=get_docstring_description(RPCInterface.get_all_process_info))
class SupvisorsAllProcessInfo(Resource):
    def get(self):
        return jsonify(g.proxy.supvisors.get_all_process_info())


@supvisors_ns.route('/process_info/<string:namespec>', methods=('GET',))
@supvisors_ns.doc(description=get_docstring_description(RPCInterface.get_process_info))
class SupvisorsProcessInfo(Resource):
    @api.doc(params={'namespec': 'the process namespec (group_name:process_name)'})
    def get(self, namespec):
        return jsonify(g.proxy.supvisors.get_process_info(namespec))


@supvisors_ns.route('/all_local_process_info', methods=('GET',))
@supvisors_ns.doc(description=get_docstring_description(RPCInterface.get_all_local_process_info))
class SupvisorsAllLocalProcessInfo(Resource):
    def get(self):
        return jsonify(g.proxy.supvisors.get_all_local_process_info())


@supvisors_ns.route('/local_process_info/<string:namespec>', methods=('GET',))
@supvisors_ns.doc(description=get_docstring_description(RPCInterface.get_local_process_info))
class SupvisorsLocalProcessInfo(Resource):
    @api.doc(params={'namespec': 'the process namespec (group_name:process_name)'})
    def get(self, namespec):
        return g.proxy.supvisors.get_local_process_info(namespec)


@supvisors_ns.route('/process_rules/<string:namespec>', methods=('GET',))
@supvisors_ns.doc(description=get_docstring_description(RPCInterface.get_process_rules))
class SupvisorsProcessRules(Resource):
    @api.doc(params={'namespec': 'the process namespec (group_name:process_name)'})
    def get(self, namespec):
        return jsonify(g.proxy.supvisors.get_process_rules(namespec))


@supvisors_ns.route('/conflicts', methods=('GET',))
@supvisors_ns.doc(description=get_docstring_description(RPCInterface.get_conflicts))
class SupvisorsConflicts(Resource):
    def get(self):
        return jsonify(g.proxy.supvisors.get_conflicts())


@supvisors_ns.route(f'/start_application/<any({StartingStrategiesParam}):strategy>/<string:application_name>',
                    methods=('POST',))
@supvisors_ns.doc(description=get_docstring_description(RPCInterface.start_application))
class SupvisorsStartApplication(Resource):
    @api.doc(params={'strategy': f'the starting strategy in {{{StartingStrategiesParam}}}',
                     'application_name': 'the name of the application to start'})
    def post(self, strategy, application_name):
        return g.proxy.supvisors.start_application(strategy, application_name)


@supvisors_ns.route(f'/stop_application/<string:application_name>', methods=('POST',))
@supvisors_ns.doc(description=get_docstring_description(RPCInterface.stop_application))
class SupvisorsStopApplication(Resource):
    @api.doc(params={'application_name': 'the name of the application to stop'})
    def post(self, application_name):
        return g.proxy.supvisors.stop_application(application_name)


@supvisors_ns.route(f'/restart_application/<any({StartingStrategiesParam}):strategy>/<string:application_name>',
                    methods=('POST',))
@supvisors_ns.doc(description=get_docstring_description(RPCInterface.restart_application))
class SupvisorsRestartApplication(Resource):
    @api.doc(params={'strategy': f'the starting strategy in {{{StartingStrategiesParam}}}',
                     'application_name': 'the name of the application to restart'})
    def post(self, strategy, application_name):
        return g.proxy.supvisors.restart_application(strategy, application_name)


@supvisors_ns.route(f'/start_args/<string:namespec>/<string:extra_args>', methods=('POST',))
@supvisors_ns.doc(description=get_docstring_description(RPCInterface.start_args))
class SupvisorsStartArgs(Resource):
    @api.doc(params={'namespec': 'the namespec of the process to start',
                     'extra_args': 'the extra arguments to be passed to the command line of the program'})
    def post(self, namespec, extra_args):
        return g.proxy.supvisors.start_args(namespec, extra_args)


@supvisors_ns.route(f'/start_process/<any({StartingStrategiesParam}):strategy>/<string:namespec>/<string:extra_args>',
                    methods=('POST',))
@supvisors_ns.doc(description=get_docstring_description(RPCInterface.start_process))
class SupvisorsStartProcess(Resource):
    @api.doc(params={'strategy': f'the starting strategy in {{{StartingStrategiesParam}}}',
                     'namespec': 'the namespec of the process to start',
                     'extra_args': 'the extra arguments to be passed to the command line of the program'})
    def post(self, strategy, namespec, extra_args):
        return g.proxy.supvisors.start_process(strategy, namespec, extra_args)


@supvisors_ns.route(f'/stop_process/<string:namespec>', methods=('POST',))
@supvisors_ns.doc(description=get_docstring_description(RPCInterface.stop_process))
class SupvisorsStopProcess(Resource):
    @api.doc(params={'namespec': 'the namespec of the process to stop'})
    def post(self, namespec):
        return g.proxy.supvisors.stop_process(namespec)


@supvisors_ns.route(f'/restart_process/<any({StartingStrategiesParam}):strategy>/<string:namespec>/<string:extra_args>',
                    methods=('POST',))
@supvisors_ns.doc(description=get_docstring_description(RPCInterface.restart_process))
class SupvisorsRestartProcess(Resource):
    @api.doc(params={'strategy': f'the starting strategy in {{{StartingStrategiesParam}}}',
                     'namespec': 'the namespec of the process to restart',
                     'extra_args': 'the extra arguments to be passed to the command line of the program'})
    def post(self, strategy, namespec, extra_args):
        return g.proxy.supvisors.restart_process(strategy, namespec, extra_args)


@supvisors_ns.route(f'/update_numprocs/<string:program_name>/<int:numprocs>', methods=('POST',))
@supvisors_ns.doc(description=get_docstring_description(RPCInterface.update_numprocs))
class SupvisorsUpdateNumprocs(Resource):
    @api.doc(params={'program_name': 'the program name, as found in the section of the Supervisor configuration files',
                     'numprocs': 'the new numprocs value'})
    def post(self, program_name, numprocs):
        return g.proxy.supvisors.update_numprocs(program_name, numprocs)


@supvisors_ns.route(f'/conciliate/<any({ConciliationStrategiesParam}):strategy>', methods=('POST',))
@supvisors_ns.doc(description=get_docstring_description(RPCInterface.conciliate))
class SupvisorsConciliate(Resource):
    @api.doc(params={'strategy': f'the conciliation strategy in {{{ConciliationStrategiesParam}}}'})
    def post(self, strategy):
        return g.proxy.supvisors.conciliate(strategy)


@supvisors_ns.route(f'/restart_sequence', methods=('POST',))
@supvisors_ns.doc(description=get_docstring_description(RPCInterface.restart_sequence))
class SupvisorsRestartSequence(Resource):
    def post(self):
        return g.proxy.supvisors.restart_sequence()


@supvisors_ns.route(f'/restart', methods=('POST',))
@supvisors_ns.doc(description=get_docstring_description(RPCInterface.restart))
class SupvisorsRestart(Resource):
    def post(self):
        return g.proxy.supvisors.restart()


@supvisors_ns.route(f'/shutdown', methods=('POST',))
@supvisors_ns.doc(description=get_docstring_description(RPCInterface.shutdown))
class SupvisorsShutdown(Resource):
    def post(self):
        return g.proxy.supvisors.shutdown()


@supvisors_ns.route(f'/change_log_level/<any({LoggerLevelsParam}):log_level>', methods=('POST',))
@supvisors_ns.doc(description=get_docstring_description(RPCInterface.change_log_level))
class SupvisorsChangeLogLevel(Resource):
    @api.doc(params={'log_level': f'the new logger level in {{{LoggerLevelsParam}}}'})
    def post(self, log_level):
        return g.proxy.supvisors.change_log_level(log_level)


# Argument parsing
def is_url(arg_parser, arg):
    """ Test if the argument is a well-formatted URL.

    :param arg_parser: the argument parser
    :param arg: the argument to test
    :return: True if the argument is a folder
    """
    try:
        result = urlparse(arg)
    except ValueError:
        arg_parser.error(f'Could not parse the URL provided: {arg}')
    if all([result.scheme, result.netloc]):
        return arg
    arg_parser.error(f'The URL provided is invalid: {arg}')


def parse_args(args):
    """ Parse arguments got from the command line.

    :param args: the command line arguments
    :return: the parsed arguments
    """
    # check if this process has been spawned by Supervisor
    supervisor_url = os.environ.get('SUPERVISOR_SERVER_URL')
    # create argument parser
    parser = ArgumentParser(description='Start a Flask application to interact with Supvisors')
    parser.add_argument('-s', '--server', type=str, default='0.0.0.0', help='the Flask server IP address')
    parser.add_argument('-p', '--port', type=int, default='5000', help='the Flask server port number')
    parser.add_argument('-u', '--supervisor_url', type=lambda x: is_url(parser, x),
                        default=supervisor_url, required=not supervisor_url,
                        help='the Supervisor URL, required if supvisorsflask is not spawned by Supervisor')
    parser.add_argument('-d', '--debug', action='store_true', help='the Flask Debug mode')
    # parse arguments from command line
    args = parser.parse_args(args)
    # if URL is not provided, check if this process is started by Supervisor
    if not args.supervisor_url:
        raise parser.error('supervisor_url must be provided when not spawned by Supervisor')
    return args


def main():
    # read the arguments
    args = parse_args(sys.argv[1:])
    if args.debug:
        print(f'ArgumentParser: {args}')
    # start the Flask application
    app.config['url'] = args.supervisor_url
    app.run(debug=args.debug, host=args.server, port=args.port)
