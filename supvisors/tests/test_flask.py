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

from typing import Union
from unittest.mock import call, patch

import pytest
from supervisor.rpcinterface import SupervisorNamespaceRPCInterface
from supervisor.xmlrpc import RPCError, Faults
from werkzeug.exceptions import MethodNotAllowed

from supvisors.rpcinterface import RPCInterface
from supvisors.tools.apis import *
from supvisors.tools.apis.utils import *
from supvisors.tools.supvisorsflask import *
from .conftest import mock_xml_rpc


@pytest.fixture
def xml_rpc():
    """ Provide basic answers to the Supervisor & Supvisors XML-RPCs. """
    rpc_patch = patch('supvisors.tools.supvisorsflask.getRPCInterface')
    mocked_rpc = rpc_patch.start()
    proxy = mocked_rpc.return_value
    # assign basic responses
    mock_xml_rpc(proxy)
    yield proxy
    rpc_patch.stop()


@pytest.fixture
def flask_app():
    """ Configure the Flask application in testing mode. """
    app.config.update({'TESTING': True, 'DEBUG': True, 'url': 'http://localhost:60000'})
    return app


@pytest.fixture
def client(flask_app):
    """ Create a test client for the Flask application. """
    return flask_app.test_client()


def check_success(rv, mocked_func, call_args_list, json):
    """ Test request success. """
    assert mocked_func.call_args_list == call_args_list
    assert rv.status == '200 OK'
    assert rv.headers['Content-Type'] == 'application/json'
    assert rv.json == json
    mocked_func.reset_mock()


def check_get_success(client, url, mocked_func, call_args_list, json):
    """ Test GET success. """
    rv = client.get(url)
    check_success(rv, mocked_func, call_args_list, json)


def check_post_success(client, url, mocked_func, call_args_list, json: Union[bool, str] = True):
    """ Test POST success. """
    rv = client.post(url)
    check_success(rv, mocked_func, call_args_list, json)


def check_error(rv, mocked_func):
    """ Test request error with missing or incorrect parameter. """
    assert not mocked_func.called
    assert rv.status == '404 NOT FOUND'
    assert rv.headers['Content-Type'] == 'text/html; charset=utf-8'
    assert rv.json is None


def check_get_error(client, url, mocked_func):
    """ Test GET error with missing or incorrect parameter. """
    rv = client.get(url)
    check_error(rv, mocked_func)


def check_post_error(client, url, mocked_func):
    """ Test POST error with missing or incorrect parameter. """
    rv = client.post(url)
    check_error(rv, mocked_func)


# test System REST API
def test_system_list_methods(xml_rpc, client):
    """ Check the listMethods REST API. """
    base_url = '/system/listMethods'
    mocked_func = xml_rpc.system.listMethods
    check_get_success(client, f'{base_url}', mocked_func, [call()],
                      [['supervisor.getAPIVersion', 'supvisors.get_api_version']])


def test_system_method_help(xml_rpc, client):
    """ Check the methodHelp REST API. """
    base_url = '/system/methodHelp'
    mocked_func = xml_rpc.system.methodHelp
    # test error with no parameter
    check_get_error(client, f'{base_url}', mocked_func)
    # test with parameters
    check_get_success(client, f'{base_url}/system.methodHelp', mocked_func,
                      [call('system.methodHelp')], 'it just works')


def test_system_method_signature(xml_rpc, client):
    """ Check the methodSignature REST API. """
    base_url = '/system/methodSignature'
    mocked_func = xml_rpc.system.methodSignature
    # test error with no parameter
    check_get_error(client, f'{base_url}', mocked_func)
    # test with parameters
    check_get_success(client, f'{base_url}/system.methodHelp', mocked_func, [call('system.methodHelp')],
                      ['string', 'string'])


# test Supervisor REST API
def test_supervisor_get_api_version(xml_rpc, client):
    """ Check the getAPIVersion REST API. """
    base_url = '/supervisor/getAPIVersion'
    mocked_func = xml_rpc.supervisor.getAPIVersion
    check_get_success(client, f'{base_url}', mocked_func, [call()], '3.0')


def test_supervisor_get_supervisor_version(xml_rpc, client):
    """ Check the getSupervisorVersion REST API. """
    base_url = '/supervisor/getSupervisorVersion'
    mocked_func = xml_rpc.supervisor.getSupervisorVersion
    check_get_success(client, f'{base_url}', mocked_func, [call()], '4.2.1')


def test_supervisor_get_identification(xml_rpc, client):
    """ Check the getIdentification REST API. """
    base_url = '/supervisor/getIdentification'
    mocked_func = xml_rpc.supervisor.getIdentification
    check_get_success(client, f'{base_url}', mocked_func, [call()], 'server_01')


def test_supervisor_get_state(xml_rpc, client):
    """ Check the getState REST API. """
    base_url = '/supervisor/getState'
    mocked_func = xml_rpc.supervisor.getState
    check_get_success(client, f'{base_url}', mocked_func, [call()], {'statecode': 1, 'statename': 'RUNNING'})


def test_supervisor_get_pid(xml_rpc, client):
    """ Check the getPID REST API. """
    base_url = '/supervisor/getPID'
    mocked_func = xml_rpc.supervisor.getPID
    check_get_success(client, f'{base_url}', mocked_func, [call()], 1234)


def test_supervisor_read_log(xml_rpc, client):
    """ Check the readLog REST API. """
    base_url = '/supervisor/readLog'
    mocked_func = xml_rpc.supervisor.readLog
    # test error with missing parameter
    check_get_error(client, f'{base_url}', mocked_func)
    check_get_error(client, f'{base_url}/-1', mocked_func)
    # test error with incorrect parameter (not an integer)
    check_get_error(client, f'{base_url}/1/forty-four', mocked_func)
    # test with parameters
    check_get_success(client, f'{base_url}/-1/44', mocked_func, [call(-1, 44)], 'WARN No file matches')


def test_supervisor_clear_log(xml_rpc, client):
    """ Check the clearLog REST API. """
    base_url = '/supervisor/clearLog'
    mocked_func = xml_rpc.supervisor.clearLog
    check_post_success(client, f'{base_url}', mocked_func, [call()])


def test_supervisor_shutdown(xml_rpc, client):
    """ Check the shutdown REST API. """
    base_url = '/supervisor/shutdown'
    mocked_func = xml_rpc.supervisor.shutdown
    check_post_success(client, f'{base_url}', mocked_func, [call()])


def test_supervisor_restart(xml_rpc, client):
    """ Check the restart REST API. """
    base_url = '/supervisor/restart'
    mocked_func = xml_rpc.supervisor.restart
    check_post_success(client, f'{base_url}', mocked_func, [call()], False)


def test_supervisor_reload_config(xml_rpc, client):
    """ Check the reloadConfig REST API. """
    base_url = '/supervisor/reloadConfig'
    mocked_func = xml_rpc.supervisor.reloadConfig
    check_post_success(client, f'{base_url}', mocked_func, [call()])


def test_supervisor_add_process_group(xml_rpc, client):
    """ Check the addProcessGroup REST API. """
    base_url = '/supervisor/addProcessGroup'
    mocked_func = xml_rpc.supervisor.addProcessGroup
    # test error with missing parameter
    check_post_error(client, f'{base_url}', mocked_func)
    # test with parameters
    with pytest.raises(RPCError):
        client.post(f'{base_url}/test')
    assert mocked_func.call_args_list == [call('test')]


def test_supervisor_remove_process_group(xml_rpc, client):
    """ Check the removeProcessGroup REST API. """
    base_url = '/supervisor/removeProcessGroup'
    mocked_func = xml_rpc.supervisor.removeProcessGroup
    # test error with missing parameter
    check_post_error(client, f'{base_url}', mocked_func)
    # test with parameters
    check_post_success(client, f'{base_url}/test', mocked_func, [call('test')])


def test_supervisor_start_process(xml_rpc, client):
    """ Check the startProcess REST API. """
    base_url = '/supervisor/startProcess'
    mocked_func = xml_rpc.supervisor.startProcess
    # test error with missing parameter
    check_post_error(client, f'{base_url}', mocked_func)
    # test with parameters
    check_post_success(client, f'{base_url}/my_movies:converter_05', mocked_func,
                       [call('my_movies:converter_05', True)])
    mocked_func.reset_mock()
    check_post_success(client, f'{base_url}/my_movies:converter_05?wait=false', mocked_func,
                       [call('my_movies:converter_05', False)])


def test_supervisor_start_process_group(xml_rpc, client):
    """ Check the startProcessGroup REST API. """
    base_url = '/supervisor/startProcessGroup'
    mocked_func = xml_rpc.supervisor.startProcessGroup
    # test error with missing parameter
    check_post_error(client, f'{base_url}', mocked_func)
    # test with parameters
    check_post_success(client, f'{base_url}/my_movies', mocked_func, [call('my_movies', True)])
    mocked_func.reset_mock()
    check_post_success(client, f'{base_url}/my_movies?wait=false', mocked_func, [call('my_movies', False)])


def test_supervisor_start_all_processes(xml_rpc, client):
    """ Check the startAllProcesses REST API. """
    base_url = '/supervisor/startAllProcesses'
    mocked_func = xml_rpc.supervisor.startAllProcesses
    check_post_success(client, f'{base_url}', mocked_func, [call(True)])
    mocked_func.reset_mock()
    check_post_success(client, f'{base_url}?wait=false', mocked_func, [call(False)])


def test_supervisor_stop_process(xml_rpc, client):
    """ Check the stopProcess REST API. """
    base_url = '/supervisor/stopProcess'
    mocked_func = xml_rpc.supervisor.stopProcess
    # test error with missing parameter
    check_post_error(client, f'{base_url}', mocked_func)
    # test with parameters
    check_post_success(client, f'{base_url}/my_movies:converter_05', mocked_func,
                       [call('my_movies:converter_05', True)])
    mocked_func.reset_mock()
    check_post_success(client, f'{base_url}/my_movies:converter_05?wait=false', mocked_func,
                       [call('my_movies:converter_05', False)])


def test_supervisor_stop_process_group(xml_rpc, client):
    """ Check the stopProcessGroup REST API. """
    base_url = '/supervisor/stopProcessGroup'
    mocked_func = xml_rpc.supervisor.stopProcessGroup
    # test error with missing parameter
    check_post_error(client, f'{base_url}', mocked_func)
    # test with parameters
    check_post_success(client, f'{base_url}/my_movies', mocked_func, [call('my_movies', True)])
    mocked_func.reset_mock()
    check_post_success(client, f'{base_url}/my_movies?wait=false', mocked_func, [call('my_movies', False)])


def test_supervisor_stop_all_processes(xml_rpc, client):
    """ Check the stopAllProcesses REST API. """
    base_url = '/supervisor/stopAllProcesses'
    mocked_func = xml_rpc.supervisor.stopAllProcesses
    check_post_success(client, f'{base_url}', mocked_func, [call(True)])
    mocked_func.reset_mock()
    check_post_success(client, f'{base_url}?wait=false', mocked_func, [call(False)])


def test_supervisor_signal_process(xml_rpc, client):
    """ Check the signalProcess REST API. """
    base_url = '/supervisor/signalProcess'
    mocked_func = xml_rpc.supervisor.signalProcess
    # test error with missing parameter
    check_post_error(client, f'{base_url}', mocked_func)
    check_post_error(client, f'{base_url}/database:movie_server_01', mocked_func)
    # test with parameters
    check_post_success(client, f'{base_url}/database:movie_server_01/SEGV', mocked_func,
                       [call('database:movie_server_01', 'SEGV')])


def test_supervisor_signal_process_group(xml_rpc, client):
    """ Check the signalProcessGroup REST API. """
    base_url = '/supervisor/signalProcessGroup'
    mocked_func = xml_rpc.supervisor.signalProcessGroup
    # test error with missing parameter
    check_post_error(client, f'{base_url}', mocked_func)
    check_post_error(client, f'{base_url}/database', mocked_func)
    # test with parameters
    check_post_success(client, f'{base_url}/database/TERM', mocked_func, [call('database', 'TERM')])


def test_supervisor_signal_all_processes(xml_rpc, client):
    """ Check the signalAllProcesses REST API. """
    base_url = '/supervisor/signalAllProcesses'
    mocked_func = xml_rpc.supervisor.signalAllProcesses
    # test error with missing parameter
    check_post_error(client, f'{base_url}', mocked_func)
    # test with parameters
    check_post_success(client, f'{base_url}/QUIT', mocked_func, [call('QUIT')])


def test_supervisor_get_all_config_info(xml_rpc, client):
    """ Check the startProcess REST API. """
    base_url = '/supervisor/getAllConfigInfo'
    mocked_func = xml_rpc.supervisor.getAllConfigInfo
    check_get_success(client, f'{base_url}', mocked_func, [call()],
                      [{'autostart': False, 'exitcodes': [0, 2], 'name': 'dummy_1'},
                       {'stdout_logfile': './log/dummy_2.log'}])


def test_supervisor_get_process_info(xml_rpc, client):
    """ Check the getProcessInfo REST API. """
    base_url = '/supervisor/getProcessInfo'
    mocked_func = xml_rpc.supervisor.getProcessInfo
    # test error with missing parameter
    check_get_error(client, f'{base_url}', mocked_func)
    # test with parameters
    check_get_success(client, f'{base_url}/database:movie_srv_01', mocked_func, [call('database:movie_srv_01')],
                      {'name': 'movie_srv_01', 'pid': 55636, 'statename': 'RUNNING'})


def test_supervisor_get_all_process_info(xml_rpc, client):
    """ Check the getAllProcessInfo REST API. """
    base_url = '/supervisor/getAllProcessInfo'
    mocked_func = xml_rpc.supervisor.getAllProcessInfo
    check_get_success(client, f'{base_url}', mocked_func, [call()],
                      [{'name': 'movie_srv_01', 'pid': 55636, 'statename': 'RUNNING'},
                       {'logfile': './log/register.log'}])


def test_supervisor_read_process_stdout_log(xml_rpc, client):
    """ Check the readProcessStdoutLog REST API. """
    base_url = '/supervisor/readProcessStdoutLog'
    mocked_func = xml_rpc.supervisor.readProcessStdoutLog
    # test error with missing parameter
    check_get_error(client, f'{base_url}', mocked_func)
    check_get_error(client, f'{base_url}/test:check_starting_sequence', mocked_func)
    check_get_error(client, f'{base_url}/test:check_starting_sequence/0', mocked_func)
    # test error with incorrect parameter (not an integer)
    check_get_error(client, f'{base_url}/test:check_starting_sequence/hello/40', mocked_func)
    check_get_error(client, f'{base_url}/test:check_starting_sequence/10/hello', mocked_func)
    # test with parameters
    check_get_success(client, f'{base_url}/test:check_starting_sequence/-1/40', mocked_func,
                      [call('test:check_starting_sequence', -1, 40)], 'INFO;entering main')


def test_supervisor_read_process_stderr_log(xml_rpc, client):
    """ Check the readProcessStderrLog REST API. """
    base_url = '/supervisor/readProcessStderrLog'
    mocked_func = xml_rpc.supervisor.readProcessStderrLog
    # test error with missing parameter
    check_get_error(client, f'{base_url}', mocked_func)
    check_get_error(client, f'{base_url}/test:check_starting_sequence', mocked_func)
    check_get_error(client, f'{base_url}/test:check_starting_sequence/0', mocked_func)
    # test error with incorrect parameter (not an integer)
    check_get_error(client, f'{base_url}/test:check_starting_sequence/hello/40', mocked_func)
    check_get_error(client, f'{base_url}/test:check_starting_sequence/100/hello', mocked_func)
    # test with parameters
    check_get_success(client, f'{base_url}/test:check_starting_sequence/0/40', mocked_func,
                      [call('test:check_starting_sequence', 0, 40)], 'INFO;entering main')


def test_supervisor_tail_process_stdout_log(xml_rpc, client):
    """ Check the readProcessStdoutLog REST API. """
    base_url = '/supervisor/tailProcessStdoutLog'
    mocked_func = xml_rpc.supervisor.tailProcessStdoutLog
    # test error with missing parameter
    check_get_error(client, f'{base_url}', mocked_func)
    check_get_error(client, f'{base_url}/test:check_starting_sequence', mocked_func)
    check_get_error(client, f'{base_url}/test:check_starting_sequence/0', mocked_func)
    # test error with incorrect parameter (not an integer)
    check_get_error(client, f'{base_url}/test:check_starting_sequence/hello/40', mocked_func)
    check_get_error(client, f'{base_url}/test:check_starting_sequence/100/hello', mocked_func)
    # test with parameters
    check_get_success(client, f'{base_url}/test:check_starting_sequence/0/40', mocked_func,
                      [call('test:check_starting_sequence', 0, 40)], 'INFO;entering main')


def test_supervisor_tail_process_stderr_log(xml_rpc, client):
    """ Check the tailProcessStderrLog REST API. """
    base_url = '/supervisor/tailProcessStderrLog'
    mocked_func = xml_rpc.supervisor.tailProcessStderrLog
    # test error with missing parameter
    check_get_error(client, f'{base_url}', mocked_func)
    check_get_error(client, f'{base_url}/test:check_starting_sequence', mocked_func)
    check_get_error(client, f'{base_url}/test:check_starting_sequence/0', mocked_func)
    # test error with incorrect parameter (not an integer)
    check_get_error(client, f'{base_url}/test:check_starting_sequence/hello/40', mocked_func)
    check_get_error(client, f'{base_url}/test:check_starting_sequence/100/hello', mocked_func)
    # test with parameters
    check_get_success(client, f'{base_url}/test:check_starting_sequence/0/40', mocked_func,
                      [call('test:check_starting_sequence', 0, 40)], 'INFO;entering main')


def test_supervisor_clear_process_logs(xml_rpc, client):
    """ Check the clearProcessLogs REST API. """
    base_url = '/supervisor/clearProcessLogs'
    mocked_func = xml_rpc.supervisor.clearProcessLogs
    # test error with missing parameter
    check_post_error(client, f'{base_url}', mocked_func)
    # test with parameters
    check_post_success(client, f'{base_url}/test:check_starting_sequence', mocked_func,
                       [call('test:check_starting_sequence')])


def test_supervisor_clear_all_process_logs(xml_rpc, client):
    """ Check the clearAllProcessLogs REST API. """
    base_url = '/supervisor/clearAllProcessLogs'
    mocked_func = xml_rpc.supervisor.clearAllProcessLogs
    check_post_success(client, f'{base_url}', mocked_func, [call()])


def test_supervisor_send_process_stdin(xml_rpc, client):
    """ Check the sendProcessStdin REST API. """
    base_url = '/supervisor/sendProcessStdin'
    mocked_func = xml_rpc.supervisor.sendProcessStdin
    # test error with missing parameter
    check_post_error(client, f'{base_url}', mocked_func)
    check_post_error(client, f'{base_url}/my_movies:converter_02', mocked_func)
    # test with parameters
    check_post_success(client, f'{base_url}/my_movies:converter_02/hello', mocked_func,
                       [call('my_movies:converter_02', 'hello')])


def test_supervisor_send_remote_comm_event(xml_rpc, client):
    """ Check the sendRemoteCommEvent REST API. """
    base_url = '/supervisor/sendRemoteCommEvent'
    mocked_func = xml_rpc.supervisor.sendRemoteCommEvent
    # test error with missing parameter
    check_post_error(client, f'{base_url}', mocked_func)
    check_post_error(client, f'{base_url}/info', mocked_func)
    # test with parameters
    check_post_success(client, f'{base_url}/info/crash', mocked_func, [call('info', 'crash')])


# test Supvisors REST API
def test_supvisors_api_version(xml_rpc, client):
    """ Check the api_version REST API. """
    base_url = '/supvisors/api_version'
    mocked_func = xml_rpc.supvisors.get_api_version
    # get_api_version called twice (once in before_request)
    check_get_success(client, f'{base_url}', mocked_func, [call(), call()], '1.0')


def test_supvisors_supvisors_state(xml_rpc, client):
    """ Check the supvisors_state REST API. """
    base_url = '/supvisors/supvisors_state'
    mocked_func = xml_rpc.supvisors.get_supvisors_state
    check_get_success(client, f'{base_url}', mocked_func, [call()],
                      {'fsm_statename': 'OPERATION', 'starting_jobs': []})


def test_supvisors_master_identifier(xml_rpc, client):
    """ Check the master_identifier REST API. """
    base_url = '/supvisors/master_identifier'
    mocked_func = xml_rpc.supvisors.get_master_identifier
    check_get_success(client, f'{base_url}', mocked_func, [call()], 'server_01')


def test_supvisors_strategies(xml_rpc, client):
    """ Check the strategies REST API. """
    base_url = '/supvisors/strategies'
    mocked_func = xml_rpc.supvisors.get_strategies
    check_get_success(client, f'{base_url}', mocked_func, [call()], {'auto-fencing': False, 'conciliation': 'USER'})


def test_supvisors_all_instances_info(xml_rpc, client):
    """ Check the all_instances_info REST API. """
    base_url = '/supvisors/all_instances_info'
    mocked_func = xml_rpc.supvisors.get_all_instances_info
    check_get_success(client, f'{base_url}', mocked_func, [call()],
                      [{'identifier': 'server_01', 'statename': 'RUNNING'},
                       {'identifier': 'server_02', 'stopping': False}])


def test_supvisors_instance_info(xml_rpc, client):
    """ Check the instance_info REST API. """
    base_url = '/supvisors/instance_info'
    mocked_func = xml_rpc.supvisors.get_instance_info
    # test error with missing parameter
    check_get_error(client, f'{base_url}', mocked_func)
    # test with parameters
    check_get_success(client, f'{base_url}/server_02', mocked_func, [call('server_02')],
                      {'identifier': 'server_02', 'stopping': False})


def test_supvisors_all_applications_info(xml_rpc, client):
    """ Check the all_applications_info REST API. """
    base_url = '/supvisors/all_applications_info'
    mocked_func = xml_rpc.supvisors.get_all_applications_info
    check_get_success(client, f'{base_url}', mocked_func, [call()],
                      [{'application_name': 'database', 'statename': 'STOPPING'},
                       {'application_name': 'test', 'major_failure': True}])


def test_supvisors_application_info(xml_rpc, client):
    """ Check the application_info REST API. """
    base_url = '/supvisors/application_info'
    mocked_func = xml_rpc.supvisors.get_application_info
    # test error with missing parameter
    check_get_error(client, f'{base_url}', mocked_func)
    # test with parameters
    check_get_success(client, f'{base_url}/database', mocked_func, [call('database')],
                      {'application_name': 'database', 'statename': 'STOPPING'})


def test_supvisors_application_rules(xml_rpc, client):
    """ Check the application_rules REST API. """
    base_url = '/supvisors/application_rules'
    mocked_func = xml_rpc.supvisors.get_application_rules
    # test error with missing parameter
    check_get_error(client, f'{base_url}', mocked_func)
    # test with parameters
    check_get_success(client, f'{base_url}/database', mocked_func, [call('database')],
                      {'application_name': 'database', 'start_sequence': 3})


def test_supvisors_all_process_info(xml_rpc, client):
    """ Check the all_process_info REST API. """
    base_url = '/supvisors/all_process_info'
    mocked_func = xml_rpc.supvisors.get_all_process_info
    check_get_success(client, f'{base_url}', mocked_func, [call()],
                      [{'process_name': 'import', 'statename': 'STOPPED'},
                       {'process_name': 'browser', 'pid': 4321}])


def test_supvisors_process_info(xml_rpc, client):
    """ Check the process_info REST API. """
    base_url = '/supvisors/process_info'
    mocked_func = xml_rpc.supvisors.get_process_info
    # test error with missing parameter
    check_get_error(client, f'{base_url}', mocked_func)
    # test with parameters
    check_get_success(client, f'{base_url}/browser', mocked_func, [call('browser')],
                      {'process_name': 'browser', 'pid': 4321})


def test_supvisors_all_local_process_info(xml_rpc, client):
    """ Check the all_local_process_info REST API. """
    base_url = '/supvisors/all_local_process_info'
    mocked_func = xml_rpc.supvisors.get_all_local_process_info
    check_get_success(client, f'{base_url}', mocked_func, [call()],
                      [{'process_name': 'import', 'statename': 'STOPPED'},
                       {'process_name': 'browser', 'pid': 4321}])


def test_supvisors_local_process_info(xml_rpc, client):
    """ Check the local_process_info REST API. """
    base_url = '/supvisors/local_process_info'
    mocked_func = xml_rpc.supvisors.get_local_process_info
    # test error with missing parameter
    check_get_error(client, f'{base_url}', mocked_func)
    # test with parameters
    check_get_success(client, f'{base_url}/browser', mocked_func, [call('browser')],
                      {'process_name': 'browser', 'pid': 4321})


def test_supvisors_process_rules(xml_rpc, client):
    """ Check the process_rules REST API. """
    base_url = '/supvisors/process_rules'
    mocked_func = xml_rpc.supvisors.get_process_rules
    # test error with missing parameter
    check_get_error(client, f'{base_url}', mocked_func)
    # test with parameters
    check_get_success(client, f'{base_url}/browser', mocked_func, [call('browser')],
                      {'process_name': 'browser', 'required': True})


def test_supvisors_conflicts(xml_rpc, client):
    """ Check the conflicts REST API. """
    base_url = '/supvisors/conflicts'
    mocked_func = xml_rpc.supvisors.get_conflicts
    check_get_success(client, f'{base_url}', mocked_func, [call()], [])


def test_supvisors_start_application(xml_rpc, client):
    """ Check the start_application REST API. """
    base_url = '/supvisors/start_application'
    mocked_func = xml_rpc.supvisors.start_application
    # test error with missing parameter
    check_post_error(client, f'{base_url}', mocked_func)
    check_post_error(client, f'{base_url}/CONFIG', mocked_func)
    # test error with incorrect parameter (unknown strategy)
    check_post_error(client, f'{base_url}/NAWAK/my_movies:converter_02', mocked_func)
    # test with parameters
    check_post_success(client, f'{base_url}/LESS_LOADED/database', mocked_func, [call('LESS_LOADED', 'database', True)])
    mocked_func.reset_mock()
    check_post_success(client, f'{base_url}/LESS_LOADED/database?wait=false', mocked_func,
                       [call('LESS_LOADED', 'database', False)])


def test_supvisors_stop_application(xml_rpc, client):
    """ Check the stop_application REST API. """
    base_url = '/supvisors/stop_application'
    mocked_func = xml_rpc.supvisors.stop_application
    # test error with missing parameter
    check_post_error(client, f'{base_url}', mocked_func)
    # test with parameters
    check_post_success(client, f'{base_url}/database', mocked_func, [call('database', True)])
    mocked_func.reset_mock()
    check_post_success(client, f'{base_url}/database?wait=false', mocked_func,
                       [call('database', False)])


def test_supvisors_restart_application(xml_rpc, client):
    """ Check the restart_application REST API. """
    base_url = '/supvisors/restart_application'
    mocked_func = xml_rpc.supvisors.restart_application
    # test error with missing parameter
    check_post_error(client, f'{base_url}', mocked_func)
    check_post_error(client, f'{base_url}/CONFIG', mocked_func)
    # test error with incorrect parameter (unknown strategy)
    check_post_error(client, f'{base_url}/NAWAK/my_movies:converter_02', mocked_func)
    # test with parameters
    check_post_success(client, f'{base_url}/LESS_LOADED/database', mocked_func, [call('LESS_LOADED', 'database', True)])
    mocked_func.reset_mock()
    check_post_success(client, f'{base_url}/LESS_LOADED/database?wait=false', mocked_func,
                       [call('LESS_LOADED', 'database', False)])


def test_supvisors_start_args(xml_rpc, client):
    """ Check the start_args REST API. """
    base_url = '/supvisors/start_args'
    mocked_func = xml_rpc.supvisors.start_args
    # test error with missing parameter
    check_post_error(client, f'{base_url}', mocked_func)
    # test with parameters
    check_post_success(client, f'{base_url}/my_movies:converter_02', mocked_func,
                       [call('my_movies:converter_02', '', True)])
    mocked_func.reset_mock()
    check_post_success(client, f'{base_url}/my_movies:converter_02?extra_args=-x 2', mocked_func,
                       [call('my_movies:converter_02', '-x 2', True)])
    mocked_func.reset_mock()
    check_post_success(client, f'{base_url}/my_movies:converter_02?extra_args=-x%202&wait=false', mocked_func,
                       [call('my_movies:converter_02', '-x 2', False)])
    mocked_func.reset_mock()
    # test with path parameters
    file_path = os.path.abspath(__file__)
    check_post_success(client, f'{base_url}/my_movies:converter_02?extra_args={file_path}&wait=false', mocked_func,
                       [call('my_movies:converter_02', file_path, False)])


def test_supvisors_start_process(xml_rpc, client):
    """ Check the start_process REST API. """
    base_url = '/supvisors/start_process'
    mocked_func = xml_rpc.supvisors.start_process
    # test error with missing parameter
    check_post_error(client, f'{base_url}', mocked_func)
    check_post_error(client, f'{base_url}/CONFIG', mocked_func)
    # test error with incorrect parameter (unknown strategy)
    check_post_error(client, f'{base_url}/NAWAK/my_movies:converter_02', mocked_func)
    # test with parameters
    check_post_success(client, f'{base_url}/MOST_LOADED/my_movies:converter_02', mocked_func,
                       [call('MOST_LOADED', 'my_movies:converter_02', '', True)])
    mocked_func.reset_mock()
    check_post_success(client, f'{base_url}/LOCAL/my_movies:converter_02?extra_args=-x 2', mocked_func,
                       [call('LOCAL', 'my_movies:converter_02', '-x 2', True)])
    mocked_func.reset_mock()
    check_post_success(client, f'{base_url}/LESS_LOADED_NODE/my_movies:converter_02?extra_args=-x%202&wait=false',
                       mocked_func, [call('LESS_LOADED_NODE', 'my_movies:converter_02', '-x 2', False)])


def test_supvisors_start_any_process(xml_rpc, client):
    """ Check the start_any_process REST API. """
    base_url = '/supvisors/start_any_process'
    mocked_func = xml_rpc.supvisors.start_any_process
    # test error with missing parameter
    check_post_error(client, f'{base_url}', mocked_func)
    check_post_error(client, f'{base_url}/CONFIG', mocked_func)
    # test error with incorrect parameter (unknown strategy)
    check_post_error(client, f'{base_url}/NAWAK/converter', mocked_func)
    # test with parameters
    check_post_success(client, f'{base_url}/MOST_LOADED/converter', mocked_func,
                       [call('MOST_LOADED', 'converter', '', True)], 'dummy_group:dummy_process')
    mocked_func.reset_mock()
    check_post_success(client, f'{base_url}/LOCAL/converter?extra_args=-x 2', mocked_func,
                       [call('LOCAL', 'converter', '-x 2', True)], 'dummy_group:dummy_process')
    mocked_func.reset_mock()
    check_post_success(client, f'{base_url}/LESS_LOADED_NODE/converter?extra_args=-x%202&wait=false',
                       mocked_func, [call('LESS_LOADED_NODE', 'converter', '-x 2', False)], 'dummy_group:dummy_process')


def test_supvisors_stop_process(xml_rpc, client):
    """ Check the stop_process REST API. """
    base_url = '/supvisors/stop_process'
    mocked_func = xml_rpc.supvisors.stop_process
    # test error with missing parameter
    check_post_error(client, f'{base_url}', mocked_func)
    # test with parameters
    check_post_success(client, f'{base_url}/my_movies:converter_02', mocked_func,
                       [call('my_movies:converter_02', True)])
    mocked_func.reset_mock()
    check_post_success(client, f'{base_url}/my_movies:converter_02?wait=false', mocked_func,
                       [call('my_movies:converter_02', False)])


def test_supvisors_restart_process(xml_rpc, client):
    """ Check the restart_process REST API. """
    base_url = '/supvisors/restart_process'
    mocked_func = xml_rpc.supvisors.restart_process
    # test error with missing parameter
    check_post_error(client, f'{base_url}', mocked_func)
    check_post_error(client, f'{base_url}/CONFIG', mocked_func)
    # test error with incorrect parameter (unknown strategy)
    check_post_error(client, f'{base_url}/NAWAK/my_movies:converter_02', mocked_func)
    # test with parameters
    check_post_success(client, f'{base_url}/MOST_LOADED/my_movies:converter_02', mocked_func,
                       [call('MOST_LOADED', 'my_movies:converter_02', '', True)])
    mocked_func.reset_mock()
    check_post_success(client, f'{base_url}/LOCAL/my_movies:converter_02?extra_args=-x 2', mocked_func,
                       [call('LOCAL', 'my_movies:converter_02', '-x 2', True)])
    mocked_func.reset_mock()
    check_post_success(client, f'{base_url}/LESS_LOADED_NODE/my_movies:converter_02?extra_args=-x%202&wait=false',
                       mocked_func, [call('LESS_LOADED_NODE', 'my_movies:converter_02', '-x 2', False)])


def test_supvisors_update_numprocs(xml_rpc, client):
    """ Check the update_numprocs REST API. """
    base_url = '/supvisors/update_numprocs'
    mocked_func = xml_rpc.supvisors.update_numprocs
    # test error with missing parameter
    check_post_error(client, f'{base_url}', mocked_func)
    check_post_error(client, f'{base_url}/converter', mocked_func)
    # test error with incorrect parameter (not an integer)
    check_post_error(client, f'{base_url}/converter/hello', mocked_func)
    # test with parameters
    check_post_success(client, f'{base_url}/converter/10', mocked_func, [call('converter', 10, True)])
    mocked_func.reset_mock()
    check_post_success(client, f'{base_url}/converter/10?wait=false', mocked_func, [call('converter', 10, False)])


def test_supvisors_enable(xml_rpc, client):
    """ Check the enable REST API. """
    base_url = '/supvisors/enable'
    mocked_func = xml_rpc.supvisors.enable
    # test error with missing parameter
    check_post_error(client, f'{base_url}', mocked_func)
    # test with parameters
    check_post_success(client, f'{base_url}/converter', mocked_func, [call('converter', True)])
    mocked_func.reset_mock()
    check_post_success(client, f'{base_url}/converter?wait=false', mocked_func, [call('converter', False)])


def test_supvisors_disable(xml_rpc, client):
    """ Check the disable REST API. """
    base_url = '/supvisors/disable'
    mocked_func = xml_rpc.supvisors.disable
    # test error with missing parameter
    check_post_error(client, f'{base_url}', mocked_func)
    # test with parameters
    check_post_success(client, f'{base_url}/converter', mocked_func, [call('converter', True)])
    mocked_func.reset_mock()
    check_post_success(client, f'{base_url}/converter?wait=false', mocked_func, [call('converter', False)])


def test_supvisors_conciliate(xml_rpc, client):
    """ Check the conciliate REST API. """
    base_url = '/supvisors/conciliate'
    mocked_func = xml_rpc.supvisors.conciliate
    # test error with missing parameter
    check_post_error(client, f'{base_url}', mocked_func)
    # test error with incorrect parameter (not a conciliation strategy)
    check_post_error(client, f'{base_url}/SLAUGHTER', mocked_func)
    # test with parameters
    check_post_success(client, f'{base_url}/INFANTICIDE', mocked_func, [call('INFANTICIDE')])


def test_supvisors_restart_sequence(xml_rpc, client):
    """ Check the restart_sequence REST API. """
    base_url = '/supvisors/restart_sequence'
    mocked_func = xml_rpc.supvisors.restart_sequence
    # test without parameter
    check_post_success(client, f'{base_url}', mocked_func, [call(True)])
    mocked_func.reset_mock()
    # test with wait parameter
    check_post_success(client, f'{base_url}?wait=false', mocked_func, [call(False)])


def test_supvisors_restart(xml_rpc, client):
    """ Check the restart REST API. """
    base_url = '/supvisors/restart'
    mocked_func = xml_rpc.supvisors.restart
    # test without parameter
    check_post_success(client, f'{base_url}', mocked_func, [call()])


def test_supvisors_shutdown(xml_rpc, client):
    """ Check the shutdown REST API. """
    base_url = '/supvisors/shutdown'
    mocked_func = xml_rpc.supvisors.shutdown
    # test without parameter
    check_post_success(client, f'{base_url}', mocked_func, [call()])


def test_supvisors_end_sync(xml_rpc, client):
    """ Check the end_sync REST API. """
    base_url = '/supvisors/end_sync'
    mocked_func = xml_rpc.supvisors.end_sync
    # test without parameters
    check_post_success(client, f'{base_url}', mocked_func, [call()])
    # test with parameters
    check_post_success(client, f'{base_url}/10.0.0.1', mocked_func, [call('10.0.0.1')])


def test_supvisors_change_log_level(xml_rpc, client):
    """ Check the change_log_level REST API. """
    base_url = '/supvisors/change_log_level'
    mocked_func = xml_rpc.supvisors.change_log_level
    # test error with missing parameter
    check_post_error(client, f'{base_url}', mocked_func)
    # test error with incorrect parameter (not a Logger level)
    check_post_error(client, f'{base_url}/chatty', mocked_func)
    # test with parameters
    check_post_success(client, f'{base_url}/debug', mocked_func, [call('debug')])


# test error handlers
# WARN: the 2 Api error handlers don't look active in the Flask test client
#  could not find any trick to test them smartly
def test_error_handlers():
    """ Check the custom error handling. """
    # test non-werkzeug exception
    expected = {'message': 'not implemented'}, 500
    assert default_error_handler(NotImplementedError('not implemented')) == expected
    # test werkzeug exception (BadRequest)
    expected = {'message': '405 Method Not Allowed: The method is not allowed for the requested URL.'}, 405
    assert default_error_handler(MethodNotAllowed()) == expected
    # test Supervisor exception (RPCError converted to xmlrpclib.Fault)
    expected = {'message': 'already started', 'code': 60}, 400
    assert supervisor_error_handler(xmlrpclib.Fault(Faults.ALREADY_STARTED, 'already started')) == expected


# test utilities
def test_supervisor_docstring_description():
    """ Check the extraction of the description from a Supervisor doctring. """
    expected = 'Read length bytes from the main log starting at offset'
    assert get_docstring_description(SupervisorNamespaceRPCInterface.readLog) == expected


def test_supvisors_docstring_description():
    """ Check the extraction of the description from a Supvisors doctring. """
    expected = ('Stop the *Managed* application named ``application_name``.\n'
                "To stop *Unmanaged* applications, use ``supervisor.stop('group:*')``.")
    assert get_docstring_description(RPCInterface.stop_application) == expected


def test_parse_args(mocker):
    """ Check the argument parser of supvisorsflask. """
    mocker.patch('sys.stderr')
    # 1. Supervisor URL is not in environment
    # check error if -u not provided and
    with pytest.raises(SystemExit):
        parse_args(''.split())
    # check error if -u provided but invalid
    with pytest.raises(SystemExit):
        parse_args('-u 60000'.split())
    with pytest.raises(SystemExit):
        parse_args('-u http://localhost:222222'.split())
    # check defaults if -u provided
    args = parse_args('-u http://localhost:60000'.split())
    assert args.supervisor_url == 'http://localhost:60000'
    assert args.host is None
    assert args.port is None
    assert not args.debug
    # check all info provided
    args = parse_args('-d -h server_02 -p 6000 -u http://localhost:60000'.split())
    assert args.supervisor_url == 'http://localhost:60000'
    assert args.host == 'server_02'
    assert args.port == 6000
    assert args.debug
    # same with long options
    args = parse_args('--debug --host server_02 --port 6000 --supervisor_url http://localhost:60000'.split())
    assert args.supervisor_url == 'http://localhost:60000'
    assert args.host == 'server_02'
    assert args.port == 6000
    assert args.debug
    # 2. Supervisor URL is in environment
    mocker.patch.dict(os.environ, {"SUPERVISOR_SERVER_URL": "http://localhost:60000"})
    # check all info provided but supervisor_url
    args = parse_args('--debug -p 6000'.split())
    assert args.supervisor_url == 'http://localhost:60000'
    assert args.host is None
    assert args.port == 6000
    assert args.debug
    # check Supervisor URL can be overridden
    args = parse_args('--host server_02 -u http://localhost:30000'.split())
    assert args.supervisor_url == 'http://localhost:30000'
    assert args.host == 'server_02'
    assert args.port is None
    assert not args.debug


# test Main
def test_main(mocker):
    """ Test the main function. """
    mocker.patch('builtins.print')
    mocked_run = mocker.patch.object(app, 'run')
    # test with few arguments
    test_args = 'supvisorsflask.py -u http://localhost:60000'.split()
    with patch.object(sys, 'argv', test_args):
        main()
    assert mocked_run.call_args_list == [call(debug=False)]
    mocked_run.reset_mock()
    # test with more arguments
    test_args = 'supvisorsflask.py -u http://localhost:60000 --debug -p 3000 -h server_01'.split()
    with patch.object(sys, 'argv', test_args):
        main()
    assert mocked_run.call_args_list == [call(debug=True, host='server_01', port=3000)]
