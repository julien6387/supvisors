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

from flask import g, jsonify
from flask_restx import Namespace, Resource
from supervisor.rpcinterface import SupervisorNamespaceRPCInterface

from .utils import get_docstring_description

# Supervisor Control and Status API
api = Namespace('supervisor', description='Supervisor operations')


@api.route('/getAPIVersion', methods=('GET',))
@api.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.getAPIVersion))
class SupervisorApiVersion(Resource):
    def get(self):
        return g.proxy.supervisor.getAPIVersion()


@api.route('/getSupervisorVersion', methods=('GET',))
@api.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.getSupervisorVersion))
class SupervisorVersion(Resource):
    def get(self):
        return g.proxy.supervisor.getSupervisorVersion()


@api.route('/getIdentification', methods=('GET',))
@api.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.getIdentification))
class SupervisorIdentification(Resource):
    def get(self):
        return g.proxy.supervisor.getIdentification()


@api.route('/getState', methods=('GET',))
@api.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.getState))
class SupervisorState(Resource):
    def get(self):
        return g.proxy.supervisor.getState()


@api.route('/getPID', methods=('GET',))
@api.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.getPID))
class SupervisorPid(Resource):
    def get(self):
        return g.proxy.supervisor.getPID()


@api.route('/readLog/<int:offset>/<int:length>', methods=('GET',))
@api.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.readLog))
class SupervisorReadLog(Resource):
    @api.doc(params={'offset': 'the offset to start reading from',
                     'length': 'the number of bytes to read from the log'})
    def get(self, offset, length):
        return g.proxy.supervisor.readLog(offset, length)


@api.route('/clearLog', methods=('POST',))
@api.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.clearLog))
class SupervisorClearLog(Resource):
    def post(self):
        return g.proxy.supervisor.clearLog()


@api.route('/shutdown', methods=('POST',))
@api.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.shutdown))
class SupervisorShutdown(Resource):
    def post(self):
        return g.proxy.supervisor.shutdown()


@api.route('/restart', methods=('POST',))
@api.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.restart))
class SupervisorRestart(Resource):
    def post(self):
        return g.proxy.supervisor.restart()


@api.route('/reloadConfig', methods=('POST',))
@api.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.reloadConfig))
class SupervisorReloadConfig(Resource):
    def post(self):
        return g.proxy.supervisor.reloadConfig()


@api.route('/addProcessGroup/<string:name>', methods=('POST',))
@api.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.addProcessGroup))
class SupervisorAddProcessGroup(Resource):
    @api.doc(params={'name': 'the name of the process group to add'})
    def post(self, name):
        return g.proxy.supervisor.addProcessGroup(name)


@api.route('/removeProcessGroup/<string:name>', methods=('POST',))
@api.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.removeProcessGroup))
class SupervisorRemoveProcessGroup(Resource):
    @api.doc(params={'name': 'the name of the process group to remove'})
    def post(self, name):
        return g.proxy.supervisor.removeProcessGroup(name)


@api.route('/startProcess/<string:name>', methods=('POST',))
@api.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.startProcess))
class SupervisorStartProcess(Resource):
    @api.doc(params={'name': 'the process name (or group:name, or group:*)'})
    def post(self, name):
        return g.proxy.supervisor.startProcess(name)


@api.route('/startProcessGroup/<string:name>', methods=('POST',))
@api.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.startProcessGroup))
class SupervisorStartProcessGroup(Resource):
    @api.doc(params={'name': 'the group name'})
    def post(self, name):
        return g.proxy.supervisor.startProcessGroup(name)


@api.route('/startAllProcesses', methods=('POST',))
@api.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.startAllProcesses))
class SupervisorStartAllProcesses(Resource):
    def post(self):
        return g.proxy.supervisor.startAllProcesses()


@api.route('/stopProcess/<string:name>', methods=('POST',))
@api.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.stopProcess))
class SupervisorStopProcess(Resource):
    @api.doc(params={'name': 'the name of the process to stop (or group:name)'})
    def post(self, name):
        return g.proxy.supervisor.stopProcess(name)


@api.route('/stopProcessGroup/<string:name>', methods=('POST',))
@api.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.stopProcessGroup))
class SupervisorStopProcessGroup(Resource):
    @api.doc(params={'name': 'the group name'})
    def post(self, name):
        return g.proxy.supervisor.stopProcessGroup(name)


@api.route('/stopAllProcesses', methods=('POST',))
@api.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.stopAllProcesses))
class SupervisorStopAllProcesses(Resource):
    def post(self):
        return g.proxy.supervisor.stopAllProcesses()


@api.route('/signalProcess/<string:name>/<string:signal>', methods=('POST',))
@api.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.signalProcess))
class SupervisorSignalProcess(Resource):
    @api.doc(params={'name': 'the name of the process to signal (or group:name)',
                     'signal': "the signal to send, as name ('HUP') or number ('1')"})
    def post(self, name, signal):
        return g.proxy.supervisor.signalProcess(name, signal)


@api.route('/signalProcessGroup/<string:name>/<string:signal>', methods=('POST',))
@api.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.signalProcessGroup))
class SupervisorSignalProcessGroup(Resource):
    @api.doc(params={'name': 'the group name',
                     'signal': "the signal to send, as name ('HUP') or number ('1')"})
    def post(self, name, signal):
        return g.proxy.supervisor.signalProcessGroup(name, signal)


@api.route('/signalAllProcesses/<string:signal>', methods=('POST',))
@api.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.signalAllProcesses))
class SupervisorSignalAllProcesses(Resource):
    @api.doc(params={'signal': "the signal to send, as name ('HUP') or number ('1')"})
    def post(self, signal):
        return g.proxy.supervisor.signalAllProcesses(signal)


@api.route('/getAllConfigInfo', methods=('GET',))
@api.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.getAllConfigInfo))
class SupervisorAllConfigInfo(Resource):
    def get(self):
        return jsonify(g.proxy.supervisor.getAllConfigInfo())


@api.route('/getProcessInfo/<string:name>', methods=('GET',))
@api.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.getProcessInfo))
class SupervisorAllConfigInfo(Resource):
    @api.doc(params={'name': 'the name of the process (or group:name)'})
    def get(self, name):
        return g.proxy.supervisor.getProcessInfo(name)


@api.route('/getAllProcessInfo', methods=('GET',))
@api.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.getAllProcessInfo))
class SupervisorAllProcessInfo(Resource):
    def get(self):
        return jsonify(g.proxy.supervisor.getAllProcessInfo())


@api.route('/readProcessStdoutLog/<string:name>/<int:offset>/<int:length>', methods=('GET',))
@api.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.readProcessStdoutLog))
class SupervisorReadProcessStdoutLog(Resource):
    @api.doc(params={'name': 'the name of the process (or group:name)',
                     'offset': 'the offset to start reading from',
                     'length': 'the number of bytes to read from the log'})
    def get(self, name, offset, length):
        return g.proxy.supervisor.readProcessStdoutLog(name, offset, length)


@api.route('/readProcessStderrLog/<string:name>/<int:offset>/<int:length>', methods=('GET',))
@api.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.readProcessStderrLog))
class SupervisorReadProcessStderrLog(Resource):
    @api.doc(params={'name': 'the name of the process (or group:name)',
                     'offset': 'the offset to start reading from',
                     'length': 'the number of bytes to read from the log'})
    def get(self, name, offset, length):
        return g.proxy.supervisor.readProcessStderrLog(name, offset, length)


@api.route('/tailProcessStdoutLog/<string:name>/<int:offset>/<int:length>', methods=('GET',))
@api.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.tailProcessStdoutLog))
class SupervisorTailProcessStdoutLog(Resource):
    @api.doc(params={'name': 'the name of the process (or group:name)',
                     'offset': 'the offset to start reading from',
                     'length': 'the number of bytes to read from the log'})
    def get(self, name, offset, length):
        return g.proxy.supervisor.tailProcessStdoutLog(name, offset, length)


@api.route('/tailProcessStderrLog/<string:name>/<int:offset>/<int:length>', methods=('GET',))
@api.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.tailProcessStderrLog))
class SupervisorTailProcessStderrLog(Resource):
    @api.doc(params={'name': 'the name of the process (or group:name)',
                     'offset': 'the offset to start reading from',
                     'length': 'the number of bytes to read from the log'})
    def get(self, name, offset, length):
        return g.proxy.supervisor.tailProcessStderrLog(name, offset, length)


@api.route('/clearProcessLogs/<string:name>', methods=('POST',))
@api.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.clearProcessLogs))
class SupervisorClearProcessLogs(Resource):
    @api.doc(params={'name': 'the name of the process (or group:name)'})
    def post(self, name):
        return g.proxy.supervisor.clearProcessLogs(name)


@api.route('/clearAllProcessLogs', methods=('POST',))
@api.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.clearAllProcessLogs))
class SupervisorClearAllProcessLogs(Resource):
    def post(self):
        return g.proxy.supervisor.clearAllProcessLogs()


@api.route('/sendProcessStdin/<string:name>/<string:chars>', methods=('POST',))
@api.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.sendProcessStdin))
class SupervisorSendProcessStdin(Resource):
    @api.doc(params={'name': 'the process name to send chars to (or group:name)',
                     'chars': 'the character data to send to the process'})
    def post(self, name, chars):
        return g.proxy.supervisor.sendProcessStdin(name, chars)


@api.route('/sendRemoteCommEvent/<string:event_type>/<string:data>', methods=('POST',))
@api.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.sendRemoteCommEvent))
class SupervisorSendProcessStdin(Resource):
    @api.doc(params={'event_type': 'the string for the "type" key in the event header',
                     'data': 'the data for the event body'})
    def post(self, event_type, data):
        return g.proxy.supervisor.sendRemoteCommEvent(event_type, data)
