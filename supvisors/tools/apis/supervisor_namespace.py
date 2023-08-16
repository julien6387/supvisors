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
from flask_restx import Namespace, Resource, inputs
from supervisor.rpcinterface import SupervisorNamespaceRPCInterface

from .utils import get_docstring_description, get_docstring_parameters

# Supervisor Control and Status API
api = Namespace('supervisor', description='Supervisor operations')

# Request parsers
wait_parser = api.parser()
wait_parser.add_argument('wait', type=inputs.boolean, default=True,
                         help='if ``True``, wait until completion of the request')


@api.route('/getAPIVersion', methods=('GET',))
@api.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.getAPIVersion))
class SupervisorApiVersion(Resource):
    @staticmethod
    def get():
        return g.proxy.supervisor.getAPIVersion()


@api.route('/getSupervisorVersion', methods=('GET',))
@api.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.getSupervisorVersion))
class SupervisorVersion(Resource):
    @staticmethod
    def get():
        return g.proxy.supervisor.getSupervisorVersion()


@api.route('/getIdentification', methods=('GET',))
@api.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.getIdentification))
class SupervisorIdentification(Resource):
    @staticmethod
    def get():
        return g.proxy.supervisor.getIdentification()


@api.route('/getState', methods=('GET',))
@api.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.getState))
class SupervisorState(Resource):
    @staticmethod
    def get():
        return g.proxy.supervisor.getState()


@api.route('/getPID', methods=('GET',))
@api.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.getPID))
class SupervisorPid(Resource):
    @staticmethod
    def get():
        return g.proxy.supervisor.getPID()


@api.route('/readLog/<int(signed=True):offset>/<int:length>', methods=('GET',))
@api.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.readLog))
class SupervisorReadLog(Resource):
    @api.doc(params=get_docstring_parameters(SupervisorNamespaceRPCInterface.readLog))
    def get(self, offset, length):
        return g.proxy.supervisor.readLog(offset, length)


@api.route('/clearLog', methods=('POST',))
@api.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.clearLog))
class SupervisorClearLog(Resource):
    @staticmethod
    def post():
        return g.proxy.supervisor.clearLog()


@api.route('/shutdown', methods=('POST',))
@api.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.shutdown))
class SupervisorShutdown(Resource):
    @staticmethod
    def post():
        return g.proxy.supervisor.shutdown()


@api.route('/restart', methods=('POST',))
@api.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.restart))
class SupervisorRestart(Resource):
    @staticmethod
    def post():
        return g.proxy.supervisor.restart()


@api.route('/reloadConfig', methods=('POST',))
@api.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.reloadConfig))
class SupervisorReloadConfig(Resource):
    @staticmethod
    def post():
        return g.proxy.supervisor.reloadConfig()


@api.route('/addProcessGroup/<string:name>', methods=('POST',))
@api.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.addProcessGroup))
class SupervisorAddProcessGroup(Resource):
    @api.doc(params=get_docstring_parameters(SupervisorNamespaceRPCInterface.addProcessGroup))
    def post(self, name):
        return g.proxy.supervisor.addProcessGroup(name)


@api.route('/removeProcessGroup/<string:name>', methods=('POST',))
@api.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.removeProcessGroup))
class SupervisorRemoveProcessGroup(Resource):
    @api.doc(params=get_docstring_parameters(SupervisorNamespaceRPCInterface.removeProcessGroup))
    def post(self, name):
        return g.proxy.supervisor.removeProcessGroup(name)


@api.route('/startProcess/<string:name>', methods=('POST',))
@api.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.startProcess))
class SupervisorStartProcess(Resource):
    @api.doc(params=get_docstring_parameters(SupervisorNamespaceRPCInterface.startProcess))
    @api.expect(wait_parser)
    def post(self, name):
        args = wait_parser.parse_args()
        return g.proxy.supervisor.startProcess(name, args.wait)


@api.route('/startProcessGroup/<string:name>', methods=('POST',))
@api.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.startProcessGroup))
class SupervisorStartProcessGroup(Resource):
    @api.doc(params=get_docstring_parameters(SupervisorNamespaceRPCInterface.startProcessGroup))
    @api.expect(wait_parser)
    def post(self, name):
        args = wait_parser.parse_args()
        return g.proxy.supervisor.startProcessGroup(name, args.wait)


@api.route('/startAllProcesses', methods=('POST',))
@api.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.startAllProcesses))
class SupervisorStartAllProcesses(Resource):
    @api.doc(params=get_docstring_parameters(SupervisorNamespaceRPCInterface.startAllProcesses))
    @api.expect(wait_parser)
    def post(self):
        args = wait_parser.parse_args()
        return g.proxy.supervisor.startAllProcesses(args.wait)


@api.route('/stopProcess/<string:name>', methods=('POST',))
@api.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.stopProcess))
class SupervisorStopProcess(Resource):
    @api.doc(params=get_docstring_parameters(SupervisorNamespaceRPCInterface.stopProcess))
    @api.expect(wait_parser)
    def post(self, name):
        args = wait_parser.parse_args()
        return g.proxy.supervisor.stopProcess(name, args.wait)


@api.route('/stopProcessGroup/<string:name>', methods=('POST',))
@api.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.stopProcessGroup))
class SupervisorStopProcessGroup(Resource):
    @api.doc(params=get_docstring_parameters(SupervisorNamespaceRPCInterface.stopProcessGroup))
    @api.expect(wait_parser)
    def post(self, name):
        args = wait_parser.parse_args()
        return g.proxy.supervisor.stopProcessGroup(name, args.wait)


@api.route('/stopAllProcesses', methods=('POST',))
@api.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.stopAllProcesses))
class SupervisorStopAllProcesses(Resource):
    @api.doc(params=get_docstring_parameters(SupervisorNamespaceRPCInterface.stopAllProcesses))
    @api.expect(wait_parser)
    def post(self):
        args = wait_parser.parse_args()
        return g.proxy.supervisor.stopAllProcesses(args.wait)


@api.route('/signalProcess/<string:name>/<string:signal>', methods=('POST',))
@api.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.signalProcess))
class SupervisorSignalProcess(Resource):
    @api.doc(params=get_docstring_parameters(SupervisorNamespaceRPCInterface.signalProcess))
    def post(self, name, signal):
        return g.proxy.supervisor.signalProcess(name, signal)


@api.route('/signalProcessGroup/<string:name>/<string:signal>', methods=('POST',))
@api.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.signalProcessGroup))
class SupervisorSignalProcessGroup(Resource):
    @api.doc(params=get_docstring_parameters(SupervisorNamespaceRPCInterface.signalProcessGroup))
    def post(self, name, signal):
        return g.proxy.supervisor.signalProcessGroup(name, signal)


@api.route('/signalAllProcesses/<string:signal>', methods=('POST',))
@api.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.signalAllProcesses))
class SupervisorSignalAllProcesses(Resource):
    @api.doc(params=get_docstring_parameters(SupervisorNamespaceRPCInterface.signalAllProcesses))
    def post(self, signal):
        return g.proxy.supervisor.signalAllProcesses(signal)


@api.route('/getAllConfigInfo', methods=('GET',))
@api.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.getAllConfigInfo))
class SupervisorAllConfigInfo(Resource):
    @staticmethod
    def get():
        return jsonify(g.proxy.supervisor.getAllConfigInfo())


@api.route('/getProcessInfo/<string:name>', methods=('GET',))
@api.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.getProcessInfo))
class SupervisorAllConfigInfo(Resource):
    @api.doc(params=get_docstring_parameters(SupervisorNamespaceRPCInterface.getProcessInfo))
    def get(self, name):
        return g.proxy.supervisor.getProcessInfo(name)


@api.route('/getAllProcessInfo', methods=('GET',))
@api.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.getAllProcessInfo))
class SupervisorAllProcessInfo(Resource):
    @staticmethod
    def get():
        return jsonify(g.proxy.supervisor.getAllProcessInfo())


@api.route('/readProcessStdoutLog/<string:name>/<int(signed=True):offset>/<int:length>', methods=('GET',))
@api.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.readProcessStdoutLog))
class SupervisorReadProcessStdoutLog(Resource):
    @api.doc(params=get_docstring_parameters(SupervisorNamespaceRPCInterface.readProcessStdoutLog))
    def get(self, name, offset, length):
        return g.proxy.supervisor.readProcessStdoutLog(name, offset, length)


@api.route('/readProcessStderrLog/<string:name>/<int(signed=True):offset>/<int:length>', methods=('GET',))
@api.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.readProcessStderrLog))
class SupervisorReadProcessStderrLog(Resource):
    @api.doc(params=get_docstring_parameters(SupervisorNamespaceRPCInterface.readProcessStderrLog))
    def get(self, name, offset, length):
        return g.proxy.supervisor.readProcessStderrLog(name, offset, length)


@api.route('/tailProcessStdoutLog/<string:name>/<int:offset>/<int:length>', methods=('GET',))
@api.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.tailProcessStdoutLog))
class SupervisorTailProcessStdoutLog(Resource):
    @api.doc(params=get_docstring_parameters(SupervisorNamespaceRPCInterface.tailProcessStdoutLog))
    def get(self, name, offset, length):
        return g.proxy.supervisor.tailProcessStdoutLog(name, offset, length)


@api.route('/tailProcessStderrLog/<string:name>/<int:offset>/<int:length>', methods=('GET',))
@api.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.tailProcessStderrLog))
class SupervisorTailProcessStderrLog(Resource):
    @api.doc(params=get_docstring_parameters(SupervisorNamespaceRPCInterface.tailProcessStderrLog))
    def get(self, name, offset, length):
        return g.proxy.supervisor.tailProcessStderrLog(name, offset, length)


@api.route('/clearProcessLogs/<string:name>', methods=('POST',))
@api.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.clearProcessLogs))
class SupervisorClearProcessLogs(Resource):
    @api.doc(params=get_docstring_parameters(SupervisorNamespaceRPCInterface.clearProcessLogs))
    def post(self, name):
        return g.proxy.supervisor.clearProcessLogs(name)


@api.route('/clearAllProcessLogs', methods=('POST',))
@api.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.clearAllProcessLogs))
class SupervisorClearAllProcessLogs(Resource):
    @staticmethod
    def post():
        return g.proxy.supervisor.clearAllProcessLogs()


@api.route('/sendProcessStdin/<string:name>/<string:chars>', methods=('POST',))
@api.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.sendProcessStdin))
class SupervisorSendProcessStdin(Resource):
    @api.doc(params=get_docstring_parameters(SupervisorNamespaceRPCInterface.sendProcessStdin))
    def post(self, name, chars):
        return g.proxy.supervisor.sendProcessStdin(name, chars)


@api.route('/sendRemoteCommEvent/<string:type>/<string:data>', methods=('POST',))
@api.doc(description=get_docstring_description(SupervisorNamespaceRPCInterface.sendRemoteCommEvent))
class SupervisorSendProcessStdin(Resource):
    @api.doc(params=get_docstring_parameters(SupervisorNamespaceRPCInterface.sendRemoteCommEvent))
    def post(self, type, data):
        return g.proxy.supervisor.sendRemoteCommEvent(type, data)
