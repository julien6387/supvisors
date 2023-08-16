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
from flask_restx import Namespace, Resource, fields, inputs

from supvisors.rpcinterface import RPCInterface
from supvisors.ttypes import ConciliationStrategies, StartingStrategies
from .utils import get_docstring_description, get_docstring_parameters

# Utilities
StartingStrategiesParam = ', '.join([x.name for x in StartingStrategies])
ConciliationStrategiesParam = ', '.join([x.name for x in ConciliationStrategies])
LoggerLevelsParam = ', '.join(RPCInterface.get_logger_levels().values())

# Supvisors part
api = Namespace('supvisors', description='Supvisors operations')


# Request parsers
wait_parser = api.parser()
wait_parser.add_argument('wait', type=inputs.boolean, default=True,
                         help='if ``True``, wait until completion of the request')

start_process_parser = api.parser()
start_process_parser.add_argument('extra_args', type=str, default='',
                                  help='the extra arguments to be passed to the command line of the program')
start_process_parser.add_argument('wait', type=inputs.boolean, default=True,
                                  help='if ``True``, wait until completion of the request')

# Models
wait_model = api.model('Wait', {'wait': fields.Boolean})
start_process_model = api.clone('Start process', wait_model, {'extra_args': fields.String})


# Routes
@api.route('/api_version', methods=('GET',))
@api.doc(description=get_docstring_description(RPCInterface.get_api_version))
class SupvisorsApiVersion(Resource):
    @staticmethod
    def get():
        return g.proxy.supvisors.get_api_version()


@api.route('/supvisors_state', methods=('GET',))
@api.doc(description=get_docstring_description(RPCInterface.get_supvisors_state))
class SupvisorsState(Resource):
    @staticmethod
    def get():
        return g.proxy.supvisors.get_supvisors_state()


@api.route('/master_identifier', methods=('GET',))
@api.doc(description=get_docstring_description(RPCInterface.get_master_identifier))
class SupvisorsMasterIdentifier(Resource):
    @staticmethod
    def get():
        return g.proxy.supvisors.get_master_identifier()


@api.route('/strategies', methods=('GET',))
@api.doc(description=get_docstring_description(RPCInterface.get_strategies))
class SupvisorsStrategies(Resource):
    @staticmethod
    def get():
        return g.proxy.supvisors.get_strategies()


@api.route('/all_instances_info', methods=('GET',))
@api.doc(description=get_docstring_description(RPCInterface.get_all_instances_info))
class SupvisorsAllInstancesInfo(Resource):
    @staticmethod
    def get():
        return jsonify(g.proxy.supvisors.get_all_instances_info())


@api.route('/instance_info/<string:identifier>', methods=('GET',))
@api.doc(description=get_docstring_description(RPCInterface.get_instance_info))
class SupvisorsInstanceInfo(Resource):
    @api.doc(params=get_docstring_parameters(RPCInterface.get_instance_info))
    def get(self, identifier):
        return g.proxy.supvisors.get_instance_info(identifier)


@api.route('/all_applications_info', methods=('GET',))
@api.doc(description=get_docstring_description(RPCInterface.get_all_applications_info))
class SupvisorsAllApplicationsInfo(Resource):
    @staticmethod
    def get():
        return jsonify(g.proxy.supvisors.get_all_applications_info())


@api.route('/application_info/<string:application_name>', methods=('GET',))
@api.doc(description=get_docstring_description(RPCInterface.get_application_info))
class SupvisorsApplicationInfo(Resource):
    @api.doc(params=get_docstring_parameters(RPCInterface.get_application_info))
    def get(self, application_name):
        return g.proxy.supvisors.get_application_info(application_name)


@api.route('/application_rules/<string:application_name>', methods=('GET',))
@api.doc(description=get_docstring_description(RPCInterface.get_application_rules))
class SupvisorsApplicationRules(Resource):
    @api.doc(params=get_docstring_parameters(RPCInterface.get_application_rules))
    def get(self, application_name):
        return g.proxy.supvisors.get_application_rules(application_name)


@api.route('/all_process_info', methods=('GET',))
@api.doc(description=get_docstring_description(RPCInterface.get_all_process_info))
class SupvisorsAllProcessInfo(Resource):
    @staticmethod
    def get():
        return jsonify(g.proxy.supvisors.get_all_process_info())


@api.route('/process_info/<string:namespec>', methods=('GET',))
@api.doc(description=get_docstring_description(RPCInterface.get_process_info))
class SupvisorsProcessInfo(Resource):
    @api.doc(params=get_docstring_parameters(RPCInterface.get_process_info))
    def get(self, namespec):
        return jsonify(g.proxy.supvisors.get_process_info(namespec))


@api.route('/all_local_process_info', methods=('GET',))
@api.doc(description=get_docstring_description(RPCInterface.get_all_local_process_info))
class SupvisorsAllLocalProcessInfo(Resource):
    @staticmethod
    def get():
        return jsonify(g.proxy.supvisors.get_all_local_process_info())


@api.route('/local_process_info/<string:namespec>', methods=('GET',))
@api.doc(description=get_docstring_description(RPCInterface.get_local_process_info))
class SupvisorsLocalProcessInfo(Resource):
    @api.doc(params=get_docstring_parameters(RPCInterface.get_local_process_info))
    def get(self, namespec):
        return g.proxy.supvisors.get_local_process_info(namespec)


@api.route('/process_rules/<string:namespec>', methods=('GET',))
@api.doc(description=get_docstring_description(RPCInterface.get_process_rules))
class SupvisorsProcessRules(Resource):
    @api.doc(params=get_docstring_parameters(RPCInterface.get_process_rules))
    def get(self, namespec):
        return jsonify(g.proxy.supvisors.get_process_rules(namespec))


@api.route('/conflicts', methods=('GET',))
@api.doc(description=get_docstring_description(RPCInterface.get_conflicts))
class SupvisorsConflicts(Resource):
    @staticmethod
    def get():
        return jsonify(g.proxy.supvisors.get_conflicts())


@api.route(f'/start_application/<any({StartingStrategiesParam}):strategy>/<string:application_name>', methods=('POST',))
@api.doc(description=get_docstring_description(RPCInterface.start_application))
class SupvisorsStartApplication(Resource):
    # keep this instead of using get_docstring_parameters as it is useful to display the enumeration literals
    @api.doc(params={'strategy': f'the starting strategy in {{{StartingStrategiesParam}}}',
                     'application_name': 'the name of the application'})
    @api.expect(wait_parser)
    def post(self, strategy, application_name):
        args = wait_parser.parse_args()
        return g.proxy.supvisors.start_application(strategy, application_name, args.wait)


@api.route(f'/stop_application/<string:application_name>', methods=('POST',))
@api.doc(description=get_docstring_description(RPCInterface.stop_application))
class SupvisorsStopApplication(Resource):
    @api.doc(params=get_docstring_parameters(RPCInterface.stop_application))
    @api.expect(wait_parser)
    def post(self, application_name):
        args = wait_parser.parse_args()
        return g.proxy.supvisors.stop_application(application_name, args.wait)


@api.route(f'/restart_application/<any({StartingStrategiesParam}):strategy>/<string:application_name>',
           methods=('POST',))
@api.doc(description=get_docstring_description(RPCInterface.restart_application))
class SupvisorsRestartApplication(Resource):
    # keep this instead of using get_docstring_parameters as it is useful to display the enumeration literals
    @api.doc(params={'strategy': f'the starting strategy in {{{StartingStrategiesParam}}}',
                     'application_name': 'the name of the application'})
    @api.expect(wait_parser)
    def post(self, strategy, application_name):
        args = wait_parser.parse_args()
        return g.proxy.supvisors.restart_application(strategy, application_name, args.wait)


@api.route(f'/start_args/<string:namespec>', methods=('POST',))
@api.doc(description=get_docstring_description(RPCInterface.start_args))
class SupvisorsStartArgs(Resource):
    @api.doc(params=get_docstring_parameters(RPCInterface.start_args))
    @api.expect(start_process_parser)
    def post(self, namespec):
        args = start_process_parser.parse_args()
        return g.proxy.supvisors.start_args(namespec, args.extra_args, args.wait)


@api.route(f'/start_process/<any({StartingStrategiesParam}):strategy>/<string:namespec>', methods=('POST',))
@api.doc(description=get_docstring_description(RPCInterface.start_process))
class SupvisorsStartProcess(Resource):
    # keep this instead of using get_docstring_parameters as it is useful to display the enumeration literals
    @api.doc(params={'strategy': f'the starting strategy in {{{StartingStrategiesParam}}}',
                     'namespec': 'the namespec of the process to start'})
    @api.expect(start_process_parser)
    def post(self, strategy, namespec):
        args = start_process_parser.parse_args()
        return g.proxy.supvisors.start_process(strategy, namespec, args.extra_args, args.wait)


@api.route(f'/start_any_process/<any({StartingStrategiesParam}):strategy>/<string:regex>', methods=('POST',))
@api.doc(description=get_docstring_description(RPCInterface.start_any_process))
class SupvisorsStartAnyProcess(Resource):
    # keep this instead of using get_docstring_parameters as it is useful to display the enumeration literals
    @api.doc(params={'strategy': f'the starting strategy in {{{StartingStrategiesParam}}}',
                     'regex': 'the regular expression used to find a process to start'})
    @api.expect(start_process_parser)
    def post(self, strategy, regex):
        args = start_process_parser.parse_args()
        return g.proxy.supvisors.start_any_process(strategy, regex, args.extra_args, args.wait)


@api.route(f'/stop_process/<string:namespec>', methods=('POST',))
@api.doc(description=get_docstring_description(RPCInterface.stop_process))
class SupvisorsStopProcess(Resource):
    @api.doc(params=get_docstring_parameters(RPCInterface.stop_process))
    @api.expect(wait_parser)
    def post(self, namespec):
        args = wait_parser.parse_args()
        return g.proxy.supvisors.stop_process(namespec, args.wait)


@api.route(f'/restart_process/<any({StartingStrategiesParam}):strategy>/<string:namespec>', methods=('POST',))
@api.doc(description=get_docstring_description(RPCInterface.restart_process))
class SupvisorsRestartProcess(Resource):
    # keep this instead of using get_docstring_parameters as it is useful to display the enumeration literals
    @api.doc(params={'strategy': f'the starting strategy in {{{StartingStrategiesParam}}}',
                     'namespec': 'the namespec of the process to restart'})
    @api.expect(start_process_parser)
    def post(self, strategy, namespec):
        args = start_process_parser.parse_args()
        return g.proxy.supvisors.restart_process(strategy, namespec, args.extra_args, args.wait)


@api.route(f'/update_numprocs/<string:program_name>/<int:numprocs>', methods=('POST',))
@api.doc(description=get_docstring_description(RPCInterface.update_numprocs))
class SupvisorsUpdateNumprocs(Resource):
    @api.doc(params=get_docstring_parameters(RPCInterface.update_numprocs))
    @api.expect(wait_parser)
    def post(self, program_name, numprocs):
        args = wait_parser.parse_args()
        return g.proxy.supvisors.update_numprocs(program_name, numprocs, args.wait)


@api.route(f'/enable/<string:program_name>', methods=('POST',))
@api.doc(description=get_docstring_description(RPCInterface.enable))
class SupvisorsEnable(Resource):
    @api.doc(params=get_docstring_parameters(RPCInterface.enable))
    @api.expect(wait_parser)
    def post(self, program_name):
        args = wait_parser.parse_args()
        return g.proxy.supvisors.enable(program_name, args.wait)


@api.route(f'/disable/<string:program_name>', methods=('POST',))
@api.doc(description=get_docstring_description(RPCInterface.disable))
class SupvisorsDisable(Resource):
    @api.doc(params=get_docstring_parameters(RPCInterface.disable))
    @api.expect(wait_parser)
    def post(self, program_name):
        args = wait_parser.parse_args()
        return g.proxy.supvisors.disable(program_name, args.wait)


@api.route(f'/conciliate/<any({ConciliationStrategiesParam}):strategy>', methods=('POST',))
@api.doc(description=get_docstring_description(RPCInterface.conciliate))
class SupvisorsConciliate(Resource):
    # keep this instead of using get_docstring_parameters as it is useful to display the enumeration literals
    @api.doc(params={'strategy': f'the conciliation strategy in {{{ConciliationStrategiesParam}}}'})
    def post(self, strategy):
        return g.proxy.supvisors.conciliate(strategy)


@api.route(f'/restart_sequence', methods=('POST',))
@api.doc(description=get_docstring_description(RPCInterface.restart_sequence))
class SupvisorsRestartSequence(Resource):
    @api.expect(wait_parser)
    def post(self):
        args = wait_parser.parse_args()
        return g.proxy.supvisors.restart_sequence(args.wait)


@api.route(f'/restart', methods=('POST',))
@api.doc(description=get_docstring_description(RPCInterface.restart))
class SupvisorsRestart(Resource):
    @staticmethod
    def post():
        return g.proxy.supvisors.restart()


@api.route(f'/shutdown', methods=('POST',))
@api.doc(description=get_docstring_description(RPCInterface.shutdown))
class SupvisorsShutdown(Resource):
    @staticmethod
    def post():
        return g.proxy.supvisors.shutdown()


@api.route(f'/end_sync', methods=('POST',))
@api.doc(description=get_docstring_description(RPCInterface.end_sync))
class SupvisorsEndSync(Resource):
    @staticmethod
    def post():
        return g.proxy.supvisors.end_sync()


@api.route(f'/end_sync/<string:identifier>', methods=('POST',))
@api.doc(description=get_docstring_description(RPCInterface.end_sync))
class SupvisorsEndSyncMaster(Resource):
    @staticmethod
    def post(identifier: str):
        return g.proxy.supvisors.end_sync(identifier)


@api.route(f'/change_log_level/<any({LoggerLevelsParam}):log_level>', methods=('POST',))
@api.doc(description=get_docstring_description(RPCInterface.change_log_level))
class SupvisorsChangeLogLevel(Resource):
    # keep this instead of using get_docstring_parameters as it is useful to display the enumeration literals
    @api.doc(params={'log_level': f'the new logger level in {{{LoggerLevelsParam}}}'})
    def post(self, log_level):
        return g.proxy.supvisors.change_log_level(log_level)
