#!/usr/bin/python
# -*- coding: utf-8 -*-

# ======================================================================
# Copyright 2017 Julien LE CLEACH
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

from unittest.mock import call, Mock

import pytest
from supervisor.rpcinterface import SupervisorNamespaceRPCInterface
from supervisor.supervisorctl import DefaultControllerPlugin
from supervisor.xmlrpc import Faults

from supvisors.supvisorsctl import *
from supvisors.ttypes import SupvisorsFaults


@pytest.fixture
def remote_proxy(mocker):
    """ Patch the remote proxy getter. """

    def mock_server_proxy(uri, transport):
        return Mock(uri=uri, transport=transport,
                    supervisor=Mock(spec=SupervisorNamespaceRPCInterface),
                    supvisors=Mock(spec=RPCInterface))

    return mocker.patch('supvisors.supvisorsctl.xmlrpclib.ServerProxy', side_effect=mock_server_proxy)


@pytest.fixture
def controller(remote_proxy):
    """ Patch the controller instance. """
    controller = Mock(spec=Controller, exitstatus=LSBInitExitStatuses.SUCCESS)
    controller.get_server_proxy.return_value = Mock(spec=RPCInterface)
    controller.options = Mock(username='cliche',
                              password='p@$$w0rd',
                              serverurl='dummy_url',
                              plugins=[DefaultControllerPlugin(controller)])
    return controller


@pytest.fixture
def plugin(controller):
    """ Create the instance to test. """
    return ControllerPlugin(controller)


@pytest.fixture
def mocked_check(mocker):
    """ Mock _upcheck. """
    return mocker.patch('supvisors.supvisorsctl.ControllerPlugin._upcheck', return_value=True)


def _check_output_error(controller, error):
    """ Test output error of controller. """
    assert controller.output.called
    assert any('ERROR' in str(ocall) for ocall in controller.output.call_args_list) == error
    assert not error or controller.exitstatus != LSBInitExitStatuses.SUCCESS
    controller.output.reset_mock()


def _check_call(controller, mocked_check, mocked_rpc, help_fct, do_fct, arg, rpc_result, has_error=False):
    """ Generic test of help and request. """
    # test that help uses output
    help_fct()
    assert controller.output.called
    controller.output.reset_mock()
    # test request
    do_fct(arg)
    # test upcheck call if any
    if mocked_check:
        assert mocked_check.call_args_list == [call()]
        mocked_check.reset_mock()
    # test RPC
    assert mocked_rpc.call_args_list == rpc_result
    mocked_rpc.reset_mock()
    # test output (with no error)
    _check_output_error(controller, has_error)
    # test request error
    mocked_rpc.side_effect = xmlrpclib.Fault(0, 'error')
    do_fct(arg)
    mocked_rpc.side_effect = None
    # test upcheck call if any
    if mocked_check:
        assert mocked_check.call_args_list == [call()]
        mocked_check.reset_mock()
    # test RPC
    assert mocked_rpc.call_args_list == rpc_result
    mocked_rpc.reset_mock()
    # test output (with error)
    _check_output_error(controller, True)


def _check_start_application_command(controller, mocked_check, mocked_appli, mocked_rpc,
                                     help_cmd, do_cmd, all_results, sel_args, sel_results):
    """ Common test of a starting command. """
    # test the request using few arguments
    do_cmd('')
    _check_output_error(controller, True)
    assert mocked_check.call_args_list == [call()]
    mocked_check.reset_mock()
    # test the request using unknown strategy
    do_cmd('strategy')
    _check_output_error(controller, True)
    assert mocked_check.call_args_list == [call()]
    mocked_check.reset_mock()
    # test request to start all
    mocked_appli.return_value = [{'application_name': 'appli_1', 'managed': True},
                                 {'application_name': 'appli_2', 'managed': True},
                                 {'application_name': 'appli_3', 'managed': False}]
    # first possibility: use no name
    rpc_result = [call(1, result) for result in all_results]
    _check_call(controller, mocked_check, mocked_rpc, help_cmd, do_cmd, 'LESS_LOADED', rpc_result)
    assert mocked_appli.call_args_list == [call(), call()]
    mocked_appli.reset_mock()
    # second possibility: use 'all'
    rpc_result = [call(2, result) for result in all_results]
    _check_call(controller, mocked_check, mocked_rpc, help_cmd, do_cmd, 'MOST_LOADED all', rpc_result)
    assert mocked_appli.call_args_list == [call(), call()]
    mocked_appli.reset_mock()
    # test help and request for starting a selection
    rpc_result = [call(0, result) for result in sel_results]
    _check_call(controller, mocked_check, mocked_rpc, help_cmd, do_cmd, 'CONFIG ' + sel_args, rpc_result, True)
    # test help and request with get_all_applications_info error
    mocked_appli.reset_mock()
    mocked_appli.side_effect = xmlrpclib.Fault(0, 'error')
    do_cmd('LESS_LOADED')
    assert mocked_appli.call_args_list == [call()]
    assert not mocked_rpc.called
    _check_output_error(controller, True)


def _check_start_process_command(controller, mocked_check, mocked_info, mocked_rpc,
                                 help_cmd, do_cmd, all_results, sel_args, sel_results):
    """ Common test of a starting command. """
    # test the request using few arguments
    do_cmd('')
    _check_output_error(controller, True)
    assert mocked_check.call_args_list == [call()]
    mocked_check.reset_mock()
    # test the request using unknown strategy
    do_cmd('strategy')
    _check_output_error(controller, True)
    assert mocked_check.call_args_list == [call()]
    mocked_check.reset_mock()
    # test request to start all
    mocked_info.return_value = [{'application_name': 'appli_1', 'process_name': 'proc_1'},
                                {'application_name': 'appli_2', 'process_name': 'proc_3'}]
    # first possibility: use no name
    rpc_result = [call(1, result) for result in all_results]
    _check_call(controller, mocked_check, mocked_rpc, help_cmd, do_cmd, 'LESS_LOADED', rpc_result)
    assert mocked_info.call_args_list == [call(), call()]
    mocked_info.reset_mock()
    # second possibility: use 'all'
    rpc_result = [call(2, result) for result in all_results]
    _check_call(controller, mocked_check, mocked_rpc, help_cmd, do_cmd, 'MOST_LOADED all', rpc_result)
    assert mocked_info.call_args_list == [call(), call()]
    mocked_info.reset_mock()
    # test help and request for starting a selection
    rpc_result = [call(0, result) for result in sel_results]
    _check_call(controller, mocked_check, mocked_rpc, help_cmd, do_cmd, 'CONFIG ' + sel_args, rpc_result)
    # test help and request with get_all_applications_info error
    mocked_info.reset_mock()
    mocked_info.side_effect = xmlrpclib.Fault(0, 'error')
    do_cmd('LESS_LOADED')
    assert mocked_info.call_args_list == [call()]
    assert not mocked_rpc.called
    _check_output_error(controller, True)


def _check_stop_application_command(controller, mocked_check, mocked_appli, mocked_rpc,
                                    help_cmd, do_cmd, all_results, sel_args, sel_results):
    """ Common test of a stopping command. """
    # test request to stop all
    mocked_appli.return_value = [{'application_name': 'appli_1', 'managed': True},
                                 {'application_name': 'appli_2', 'managed': True},
                                 {'application_name': 'appli_3', 'managed': False}]
    # first possibility: use no name
    rpc_result = [call(result) for result in all_results]
    _check_call(controller, mocked_check, mocked_rpc, help_cmd, do_cmd, '', rpc_result)
    assert mocked_appli.call_args_list == [call(), call()]
    mocked_appli.reset_mock()
    # second possibility: use 'all'
    _check_call(controller, mocked_check, mocked_rpc, help_cmd, do_cmd, 'all', rpc_result)
    assert mocked_appli.call_args_list == [call(), call()]
    mocked_appli.reset_mock()
    # test help and request for starting a selection of applications
    rpc_result = [call(result) for result in sel_results]
    _check_call(controller, mocked_check, mocked_rpc, help_cmd, do_cmd, sel_args, rpc_result, True)
    # test help and request with get_all_applications_info error
    mocked_appli.reset_mock()
    mocked_appli.side_effect = xmlrpclib.Fault(0, 'error')
    do_cmd('')
    assert mocked_appli.call_args_list == [call()]
    assert mocked_rpc.call_count == 0
    _check_output_error(controller, True)


def _check_stop_process_command(controller, mocked_check, mocked_info, mocked_rpc,
                                help_cmd, do_cmd, all_results, sel_args, sel_results):
    """ Common test of a stopping command. """
    # test request to stop all
    mocked_info.return_value = [{'application_name': 'appli_1', 'process_name': 'proc_1'},
                                {'application_name': 'appli_2', 'process_name': 'proc_3'}]
    # first possibility: use no name
    rpc_result = [call(result) for result in all_results]
    _check_call(controller, mocked_check, mocked_rpc, help_cmd, do_cmd, '', rpc_result)
    assert mocked_info.call_args_list == [call(), call()]
    mocked_info.reset_mock()
    # second possibility: use 'all'
    _check_call(controller, mocked_check, mocked_rpc, help_cmd, do_cmd, 'all', rpc_result)
    assert mocked_info.call_args_list == [call(), call()]
    mocked_info.reset_mock()
    # test help and request for starting a selection of applications
    rpc_result = [call(result) for result in sel_results]
    _check_call(controller, mocked_check, mocked_rpc, help_cmd, do_cmd, sel_args, rpc_result)
    # test help and request with get_all_applications_info error
    mocked_info.reset_mock()
    mocked_info.side_effect = xmlrpclib.Fault(0, 'error')
    do_cmd('')
    assert mocked_info.call_args_list == [call()]
    assert mocked_rpc.call_count == 0
    _check_output_error(controller, True)


def test_creation(controller, plugin):
    """ Test the creation of the Supvisors ControllerPlugin and the _startresult patch applied to the Supervisor
    DefaultControllerPlugin. """
    assert plugin.ctl is controller
    # check that the Supervisor Faults have been expanded
    assert Faults.DISABLED == SupvisorsFaults.DISABLED.value
    # check that the Supervisor plugin has been patched and test the patch
    supervisor_plugin = controller.options.plugins[0]
    result = {'group': 'dummy_group', 'name': 'dummy_process', 'status': Faults.DISABLED}
    assert supervisor_plugin._startresult(result) == 'dummy_group:dummy_process: ERROR disabled'
    result['status'] = Faults.SUCCESS
    assert supervisor_plugin._startresult(result) == 'dummy_group:dummy_process: started'


def test_get_server_proxy(remote_proxy, plugin):
    """ Test the access to any remote proxy. """
    # test the proxy
    assert SupervisorNamespaceRPCInterface == plugin.get_server_proxy('http://localhost:9000', 'supervisor')._spec_class
    assert RPCInterface == plugin.get_server_proxy('http://localhost:9000', 'supvisors')._spec_class
    assert remote_proxy.call_count == 2
    for called in remote_proxy.call_args_list:
        args, kwargs = called
        assert args[0] == 'http://127.0.0.1'
        assert isinstance(args[1], xmlrpc.SupervisorTransport)
        assert args[1].username == 'cliche'
        assert args[1].password == 'p@$$w0rd'
        assert args[1].serverurl == 'http://localhost:9000'


def test_supvisors(controller, plugin):
    """ Test the access to Supvisors proxy. """
    # test the proxy
    assert RPCInterface == plugin.supvisors()._spec_class
    assert controller.get_server_proxy.call_args_list == [call('supvisors')]


def test_get_running_instances(controller, plugin, mocked_check):
    """ Test the get_running_instances request. """
    mocked_rpc = plugin.supvisors().get_all_instances_info
    mocked_rpc.return_value = [{'identifier': 'third', 'node_name': '10.0.0.3', 'port': 30000, 'statecode': 3},
                               {'identifier': 'first', 'node_name': '10.0.0.1', 'port': 30000, 'statecode': 2},
                               {'identifier': 'second', 'node_name': '10.0.0.2', 'port': 60000, 'statecode': 0}]
    # test request
    assert plugin.get_running_instances() == {'first': 'http://10.0.0.1:30000', 'third': 'http://10.0.0.3:30000'}
    # test output (with no error)
    assert not controller.output.called
    # test request error
    mocked_rpc.side_effect = xmlrpclib.Fault(0, 'error')
    assert plugin.get_running_instances() == {}
    mocked_rpc.side_effect = None
    # test output (with error)
    _check_output_error(controller, True)


def test_sversion(controller, plugin, mocked_check):
    """ Test the sversion request. """
    mocked_rpc = plugin.supvisors().get_api_version
    _check_call(controller, mocked_check, mocked_rpc, plugin.help_sversion, plugin.do_sversion, '', [call()])


def test_master(controller, plugin, mocked_check):
    """ Test the master request. """
    mocked_rpc = plugin.supvisors().get_master_identifier
    _check_call(controller, mocked_check, mocked_rpc, plugin.help_master, plugin.do_master, '', [call()])


def test_strategies(controller, plugin, mocked_check):
    """ Test the master request. """
    mocked_rpc = plugin.supvisors().get_strategies
    mocked_rpc.return_value = {'conciliation': 'hard', 'starting': 'easy', 'auto-fencing': True}
    _check_call(controller, mocked_check, mocked_rpc, plugin.help_strategies, plugin.do_strategies, '', [call()])


def test_sstate(controller, plugin, mocked_check):
    """ Test the sstate request. """
    mocked_rpc = plugin.supvisors().get_supvisors_state
    mocked_rpc.return_value = {'fsm_statecode': 10, 'fsm_statename': 'running',
                               'discovery_mode': True, 'master_identifier': '10.0.0.1',
                               'starting_jobs': [], 'stopping_jobs': ['10.0.0.1', 'test']}
    _check_call(controller, mocked_check, mocked_rpc, plugin.help_sstate, plugin.do_sstate, '', [call()])


def test_instance_status(controller, plugin, mocked_check):
    """ Test the instance_status request. """
    mocked_rpc = plugin.supvisors().get_all_instances_info
    mocked_rpc.return_value = [{'identifier': '10.0.0.1', 'node_name': '10.0.0.1', 'port': 60000,
                                'statename': 'running', 'discovery_mode': True,
                                'loading': 10, 'local_time': 1500, 'sequence_counter': 12,
                                'process_failure': False,
                                'fsm_statename': 'OPERATION', 'discovery_mode': False, 'master_identifier': '10.0.0.1',
                                'starting_jobs': True, 'stopping_jobs': False},
                               {'identifier': '10.0.0.2', 'node_name': '10.0.0.2', 'port': 60000,
                                'statename': 'stopped', 'discovery_mode': False,
                                'loading': 0, 'local_time': 100, 'sequence_counter': 15,
                                'process_failure': True,
                                'fsm_statename': 'CONCILATION', 'discovery_mode': True, 'master_identifier': 'hostname',
                                'starting_jobs': False, 'stopping_jobs': True}]
    _check_call(controller, mocked_check, mocked_rpc,  plugin.help_instance_status, plugin.do_instance_status,
                '', [call()])
    _check_call(controller, mocked_check, mocked_rpc, plugin.help_instance_status, plugin.do_instance_status,
                'all', [call()])
    # test help and request for node status from a selection of address names
    _check_call(controller, mocked_check, mocked_rpc, plugin.help_instance_status, plugin.do_instance_status,
                '10.0.0.2 10.0.0.1', [call()])


def test_application_info(controller, plugin, mocked_check):
    """ Test the application_info request. """
    mocked_rpc = plugin.supvisors().get_all_applications_info
    mocked_rpc.return_value = [{'application_name': 'appli_1', 'statename': 'running',
                                'major_failure': True, 'minor_failure': False},
                               {'application_name': 'appli_2', 'statename': 'stopped',
                                'major_failure': False, 'minor_failure': True}]
    _check_call(controller, mocked_check, mocked_rpc, plugin.help_application_info, plugin.do_application_info,
                '', [call()])
    _check_call(controller, mocked_check, mocked_rpc, plugin.help_application_info, plugin.do_application_info,
                'all', [call()])
    _check_call(controller, mocked_check, mocked_rpc, plugin.help_application_info, plugin.do_application_info,
                'appli_2 appli_1', [call()])


def test_sstatus(controller, plugin, mocked_check):
    """ Test the sstatus request. """
    mocked_rpc = plugin.supvisors().get_all_process_info
    mocked_rpc.return_value = [{'application_name': 'appli_1', 'process_name': 'proc_1',
                                'statecode': 20, 'statename': 'running', 'expected_exit': True,
                                'identifiers': ['10.0.1', '10.0.2']},
                               {'application_name': 'appli_2', 'process_name': 'proc_3',
                                'statecode': 100, 'statename': 'exited', 'expected_exit': False,
                                'identifiers': []}]
    _check_call(controller, mocked_check, mocked_rpc, plugin.help_sstatus, plugin.do_sstatus, '', [call()])
    _check_call(controller, mocked_check, mocked_rpc, plugin.help_sstatus, plugin.do_sstatus, 'all', [call()])
    # test help and request for process info from a selection of namespecs
    mocked_rpc = plugin.supvisors().get_process_info
    mocked_rpc.side_effect = [[{'application_name': 'appli_1', 'process_name': 'proc_1',
                                'statecode': 20, 'statename': 'running', 'expected_exit': True,
                                'identifiers': ['10.0.1', '10.0.2']}],
                              [{'application_name': 'appli_2', 'process_name': 'proc_3',
                                'statecode': 100, 'statename': 'exited', 'expected_exit': False,
                                'identifiers': []}]]
    _check_call(controller, mocked_check, mocked_rpc, plugin.help_sstatus, plugin.do_sstatus,
                'appli_2:proc_3 appli_1:proc_1', [call('appli_2:proc_3'), call('appli_1:proc_1')])


def test_local_status(controller, plugin, mocked_check):
    """ Test the local_status request. """
    mocked_rpc = plugin.supvisors().get_all_local_process_info
    mocked_rpc.return_value = [{'group': 'appli_1', 'name': 'proc_1',
                                'state': 20, 'start': 1234, 'now': 4321, 'pid': 14725,
                                'extra_args': '-x dummy', 'disabled': False},
                               {'group': 'appli_2', 'name': 'proc_3',
                                'state': 0, 'start': 0, 'now': 0, 'pid': 0,
                                'extra_args': '', 'disabled': True}]
    _check_call(controller, mocked_check, mocked_rpc, plugin.help_local_status, plugin.do_local_status,
                '', [call()])
    _check_call(controller, mocked_check, mocked_rpc, plugin.help_local_status, plugin.do_local_status,
                'all', [call()])
    # test help and request for process info from a selection of namespecs
    _check_call(controller, mocked_check, mocked_rpc, plugin.help_local_status, plugin.do_local_status,
                'appli_2:proc_3 appli_1:proc_1', [call()])


def test_application_rules(controller, plugin, mocked_check):
    """ Test the application_rules request. """
    mocked_appli = plugin.supvisors().get_all_applications_info
    mocked_appli.return_value = [{'application_name': 'appli_1'}, {'application_name': 'appli_2'},
                                 {'application_name': 'appli_3'}]
    mocked_rpc = plugin.supvisors().get_application_rules
    returned_rules = [{'application_name': 'appli_1', 'managed': True, 'distribution': 'SINGLE_NODE',
                       'start_sequence': 2, 'stop_sequence': 3, 'starting_strategy': 'CONFIG',
                       'starting_failure_strategy': 'ABORT', 'running_failure_strategy': 'CONTINUE'},
                      {'application_name': 'appli_2', 'managed': True,
                       'distribution': 'ALL_INSTANCES', 'addresses': ['10.0.0.1', '10.0.0.2', '10.0.0.3'],
                       'start_sequence': 1, 'stop_sequence': 0, 'starting_strategy': 'LESS_LOADED',
                       'starting_failure_strategy': 'CONTINUE', 'running_failure_strategy': 'RESTART_APPLICATION'},
                      {'application_name': 'appli_3', 'managed': False}]
    # first possibility: no argument
    mocked_rpc.side_effect = returned_rules
    _check_call(controller, mocked_check, mocked_rpc, plugin.help_application_rules, plugin.do_application_rules,
                '', [call('appli_1'), call('appli_2'), call('appli_3')])
    assert mocked_appli.call_args_list == [call(), call()]
    mocked_appli.reset_mock()
    # second possibility: use 'all'
    mocked_rpc.side_effect = returned_rules
    _check_call(controller, mocked_check, mocked_rpc, plugin.help_application_rules, plugin.do_application_rules,
                'all', [call('appli_1'), call('appli_2'), call('appli_3')])
    assert mocked_appli.call_args_list == [call(), call()]
    mocked_appli.reset_mock()
    # test help and request for rules from a selection of application names
    mocked_rpc.side_effect = returned_rules
    _check_call(controller, mocked_check, mocked_rpc, plugin.help_application_rules, plugin.do_application_rules,
                'appli_3 appli_2 appli_1', [call('appli_3'), call('appli_2'), call('appli_1')])
    assert mocked_appli.call_count == 0
    # test help and request with get_all_applications_info error
    mocked_appli.reset_mock()
    mocked_appli.side_effect = xmlrpclib.Fault(0, 'error')
    plugin.do_application_rules('')
    assert mocked_appli.call_args_list == [call()]
    assert not mocked_rpc.called
    _check_output_error(controller, True)


def test_process_rules(controller, plugin, mocked_check):
    """ Test the process_rules request. """
    mocked_info = plugin.supvisors().get_all_process_info
    mocked_info.return_value = [{'application_name': 'appli_1', 'process_name': 'proc_1'},
                                {'application_name': 'appli_2', 'process_name': 'proc_3'}]
    mocked_rpc = plugin.supvisors().get_process_rules
    returned_rules = [[{'application_name': 'appli_1', 'process_name': 'proc_1',
                        'identifiers': ['10.0.0.1', '10.0.0.2'],
                        'start_sequence': 2, 'stop_sequence': 3, 'required': True, 'wait_exit': False,
                        'expected_loading': 50, 'running_failure_strategy': 1}],
                      [{'application_name': 'appli_2', 'process_name': 'proc_3', 'identifiers': ['*'],
                        'start_sequence': 1, 'stop_sequence': 0, 'required': False, 'wait_exit': True,
                        'expected_loading': 15, 'running_failure_strategy': 2}]]
    # first case: no argument
    mocked_rpc.side_effect = returned_rules
    _check_call(controller, mocked_check, mocked_rpc, plugin.help_process_rules, plugin.do_process_rules,
                '', [call('appli_1:proc_1'), call('appli_2:proc_3')])
    assert mocked_info.call_args_list == [call(), call()]
    mocked_info.reset_mock()
    # second case: use 'all'
    mocked_rpc.side_effect = returned_rules
    _check_call(controller, mocked_check, mocked_rpc, plugin.help_process_rules, plugin.do_process_rules,
                'all', [call('appli_1:proc_1'), call('appli_2:proc_3')])
    assert mocked_info.call_args_list == [call(), call()]
    mocked_info.reset_mock()
    # test help and request for rules from a selection of namespecs
    mocked_rpc.side_effect = returned_rules
    _check_call(controller, mocked_check, mocked_rpc, plugin.help_process_rules, plugin.do_process_rules,
                'appli_1:proc_1 appli_2:proc_3', [call('appli_1:proc_1'), call('appli_2:proc_3')])
    assert not mocked_info.called
    # test help and request with get_all_applications_info error
    mocked_info.reset_mock()
    mocked_info.side_effect = xmlrpclib.Fault(0, 'error')
    plugin.do_process_rules('')
    assert mocked_info.call_args_list == [call()]
    assert not mocked_rpc.called
    _check_output_error(controller, True)


def test_conflicts(controller, plugin, mocked_check):
    """ Test the conflicts request. """
    mocked_rpc = plugin.supvisors().get_conflicts
    mocked_rpc.return_value = [{'application_name': 'appli_1', 'process_name': 'proc_1', 'statename': 'running',
                                'identifiers': ['10.0.0.1', '10.0.0.2']},
                               {'application_name': 'appli_2', 'process_name': 'proc_3', 'statename': 'stopped',
                                'identifiers': ['10.0.0.2', '10.0.0.3']}]
    _check_call(controller, mocked_check, mocked_rpc, plugin.help_conflicts, plugin.do_conflicts, '', [call()])


def test_start_application(controller, plugin, mocked_check):
    """ Test the start_application request. """
    mocked_appli = plugin.supvisors().get_all_applications_info
    mocked_rpc = plugin.supvisors().start_application
    _check_start_application_command(controller, mocked_check, mocked_appli, mocked_rpc,
                                     plugin.help_start_application, plugin.do_start_application,
                                     ('appli_1', 'appli_2'), 'appli_2 appli_1 appli_3 dummy_appli',
                                     ('appli_2', 'appli_1'))


def test_restart_application(controller, plugin, mocked_check):
    """ Test the restart_application request. """
    mocked_appli = plugin.supvisors().get_all_applications_info
    mocked_rpc = plugin.supvisors().restart_application
    _check_start_application_command(controller, mocked_check, mocked_appli, mocked_rpc,
                                     plugin.help_restart_application, plugin.do_restart_application,
                                     ('appli_1', 'appli_2'), 'appli_2 appli_1 appli_3 dummy_appli',
                                     ('appli_2', 'appli_1'))


def test_stop_application(controller, plugin, mocked_check):
    """ Test the stop_application request. """
    mocked_appli = plugin.supvisors().get_all_applications_info
    mocked_rpc = plugin.supvisors().stop_application
    _check_stop_application_command(controller, mocked_check, mocked_appli, mocked_rpc,
                                    plugin.help_stop_application, plugin.do_stop_application,
                                    ('appli_1', 'appli_2'), 'appli_2 appli_1 dummy_appli', ('appli_2', 'appli_1'))


def test_start_args(controller, plugin, mocked_check):
    """ Test the start_args request. """
    # test request to start process without extra arguments
    plugin.do_start_args('')
    _check_output_error(controller, True)
    assert mocked_check.call_args_list == [call()]
    mocked_check.reset_mock()
    # test request to start process with extra arguments
    mocked_rpc = plugin.supvisors().start_args
    _check_call(controller, mocked_check, mocked_rpc, plugin.help_start_args, plugin.do_start_args,
                'proc -x 5', [call('proc', '-x 5')])


def test_all_start(mocker, controller, plugin, mocked_check):
    """ Test the all_start request. """
    mocked_get_instances = mocker.patch.object(plugin, 'get_running_instances')
    mocked_rpc = Mock(**{'startProcess.return_value': True})
    mocked_get_proxy = mocker.patch.object(plugin, 'get_server_proxy', return_value=mocked_rpc)
    # test request to start process without arguments
    plugin.do_all_start('')
    _check_output_error(controller, True)
    assert mocked_check.call_args_list == [call()]
    mocked_check.reset_mock()
    # test without running instances (doesn't really make sense)
    mocked_get_instances.return_value = {}
    plugin.do_all_start('appli_1:proc_1')
    _check_output_error(controller, True)
    assert mocked_check.call_args_list == [call()]
    mocked_check.reset_mock()
    assert not mocked_get_proxy.called
    assert not mocked_rpc.startProcess.called
    # test with running instances
    mocked_get_instances.return_value = {'node_1': 'http://10.0.0.1:30000', 'node_2': 'http://10.0.0.2:31000'}
    _check_call(controller, mocked_check, mocked_rpc.startProcess, plugin.help_all_start, plugin.do_all_start,
                'appli_1:proc_1', [call('appli_1:proc_1', False), call('appli_1:proc_1', False)])
    # get_server_proxy is called 2x2 times, without error and with error (which is set on startProcess)
    assert mocked_get_proxy.call_args_list == [call('http://10.0.0.1:30000', 'supervisor'),
                                               call('http://10.0.0.2:31000', 'supervisor'),
                                               call('http://10.0.0.1:30000', 'supervisor'),
                                               call('http://10.0.0.2:31000', 'supervisor')]


def test_all_start_args(mocker, controller, plugin, mocked_check):
    """ Test the all_start_args request. """
    mocked_get_instances = mocker.patch.object(plugin, 'get_running_instances')
    mocked_rpc = Mock(**{'start_args.return_value': True})
    mocked_get_proxy = mocker.patch.object(plugin, 'get_server_proxy', return_value=mocked_rpc)
    # test request to start process without arguments
    plugin.do_all_start_args('')
    _check_output_error(controller, True)
    assert mocked_check.call_args_list == [call()]
    mocked_check.reset_mock()
    # test request to start process without extra arguments
    plugin.do_all_start_args('appli_1:proc_1')
    _check_output_error(controller, True)
    assert mocked_check.call_args_list == [call()]
    mocked_check.reset_mock()
    # test without running instances (doesn't really make sense)
    mocked_get_instances.return_value = {}
    plugin.do_all_start_args('appli_1:proc_1 -x 5')
    _check_output_error(controller, True)
    assert mocked_check.call_args_list == [call()]
    mocked_check.reset_mock()
    assert not mocked_get_proxy.called
    assert not mocked_rpc.start_args.called
    # test with running instances
    mocked_get_instances.return_value = {'node_1': 'http://10.0.0.1:30000', 'node_2': 'http://10.0.0.2:31000'}
    _check_call(controller, mocked_check, mocked_rpc.start_args, plugin.help_all_start_args, plugin.do_all_start_args,
                'appli_1:proc_1 -x 5 ', [call('appli_1:proc_1', '-x 5', False), call('appli_1:proc_1', '-x 5', False)])
    # get_server_proxy is called 2x2 times, without error and with error (which is set on startProcess)
    assert mocked_get_proxy.call_args_list == [call('http://10.0.0.1:30000', 'supvisors'),
                                               call('http://10.0.0.2:31000', 'supvisors'),
                                               call('http://10.0.0.1:30000', 'supvisors'),
                                               call('http://10.0.0.2:31000', 'supvisors')]


def test_start_process(controller, plugin, mocked_check):
    """ Test the start_process request. """
    mocked_info = plugin.supvisors().get_all_process_info
    mocked_rpc = plugin.supvisors().start_process
    _check_start_process_command(controller, mocked_check, mocked_info, mocked_rpc,
                                 plugin.help_start_process, plugin.do_start_process,
                                 ('appli_1:proc_1', 'appli_2:proc_3'), 'appli_1:proc_1 appli_2:proc_3',
                                 ('appli_1:proc_1', 'appli_2:proc_3'))


def test_start_any_process(controller, plugin, mocked_check):
    """ Test the start_any_process request. """
    # test the request using few arguments
    plugin.do_start_any_process('')
    _check_output_error(controller, True)
    assert mocked_check.call_args_list == [call()]
    mocked_check.reset_mock()
    plugin.do_start_any_process('CONFIG')
    _check_output_error(controller, True)
    assert mocked_check.call_args_list == [call()]
    mocked_check.reset_mock()
    # test the request using unknown strategy
    plugin.do_start_any_process('strategy regex')
    _check_output_error(controller, True)
    assert mocked_check.call_args_list == [call()]
    mocked_check.reset_mock()
    # test request to start the process
    mocked_rpc = plugin.supvisors().start_any_process
    _check_call(controller, mocked_check, mocked_rpc,
                plugin.help_start_any_process, plugin.do_start_any_process,
                'LESS_LOADED :x [abc]', [call(1, ':x'), call(1, '[abc]')])


def test_start_any_process_args(controller, plugin, mocked_check):
    """ Test the start_any_process_args request. """
    # test the request using few arguments
    plugin.do_start_any_process_args('')
    _check_output_error(controller, True)
    assert mocked_check.call_args_list == [call()]
    mocked_check.reset_mock()
    plugin.do_start_any_process_args('CONFIG')
    _check_output_error(controller, True)
    assert mocked_check.call_args_list == [call()]
    mocked_check.reset_mock()
    plugin.do_start_any_process_args('CONFIG regex')
    _check_output_error(controller, True)
    assert mocked_check.call_args_list == [call()]
    mocked_check.reset_mock()
    # test the request using unknown strategy
    plugin.do_start_any_process_args('strategy regex a list of arguments')
    _check_output_error(controller, True)
    assert mocked_check.call_args_list == [call()]
    mocked_check.reset_mock()
    # test request to start the process
    mocked_rpc = plugin.supvisors().start_any_process
    _check_call(controller, mocked_check, mocked_rpc,
                plugin.help_start_any_process_args, plugin.do_start_any_process_args,
                'LESS_LOADED :x  a list of arguments', [call(1, ':x', 'a list of arguments')])


def test_restart_process(controller, plugin, mocked_check):
    """ Test the restart_process request. """
    mocked_info = plugin.supvisors().get_all_process_info
    mocked_rpc = plugin.supvisors().restart_process
    _check_start_process_command(controller, mocked_check, mocked_info, mocked_rpc,
                                 plugin.help_restart_process, plugin.do_restart_process,
                                 ('appli_1:proc_1', 'appli_2:proc_3'), 'appli_1:proc_1 appli_2:proc_3',
                                 ('appli_1:proc_1', 'appli_2:proc_3'))


def test_start_process_args(controller, plugin, mocked_check):
    """ Test the start_process_args request. """
    # test the request using few arguments
    plugin.do_start_process_args('')
    _check_output_error(controller, True)
    assert mocked_check.call_args_list == [call()]
    mocked_check.reset_mock()
    plugin.do_start_process_args('CONFIG')
    _check_output_error(controller, True)
    assert mocked_check.call_args_list == [call()]
    mocked_check.reset_mock()
    plugin.do_start_process_args('CONFIG proc')
    _check_output_error(controller, True)
    assert mocked_check.call_args_list == [call()]
    mocked_check.reset_mock()
    # test the request using unknown strategy
    plugin.do_start_process_args('strategy program list of arguments')
    _check_output_error(controller, True)
    assert mocked_check.call_args_list == [call()]
    mocked_check.reset_mock()
    # test request to start the process
    mocked_rpc = plugin.supvisors().start_process
    _check_call(controller, mocked_check, mocked_rpc,
                plugin.help_start_process_args, plugin.do_start_process_args,
                'LESS_LOADED appli_2:proc_3 a list of arguments',
                [call(1, 'appli_2:proc_3', 'a list of arguments')])


def test_stop_process(controller, plugin, mocked_check):
    """ Test the stop_process request. """
    mocked_info = plugin.supvisors().get_all_process_info
    mocked_rpc = plugin.supvisors().stop_process
    _check_stop_process_command(controller, mocked_check, mocked_info, mocked_rpc,
                                plugin.help_stop_process, plugin.do_stop_process,
                                ('appli_1:proc_1', 'appli_2:proc_3'), 'appli_1:proc_1 appli_2:proc_3',
                                ('appli_1:proc_1', 'appli_2:proc_3'))


def test_update_numprocs(controller, plugin, mocked_check):
    """ Test the update_numprocs request. """
    plugin.do_update_numprocs('')
    _check_output_error(controller, True)
    assert mocked_check.call_args_list == [call()]
    mocked_check.reset_mock()
    # test the request using incorrect numprocs
    plugin.do_update_numprocs('dummy_process deux')
    _check_output_error(controller, True)
    assert mocked_check.call_args_list == [call()]
    mocked_check.reset_mock()
    # test the request using incorrect numprocs
    plugin.do_update_numprocs('dummy_process 0')
    _check_output_error(controller, True)
    assert mocked_check.call_args_list == [call()]
    mocked_check.reset_mock()
    # test help and request
    mocked_rpc = plugin.supvisors().update_numprocs
    _check_call(controller, mocked_check, mocked_rpc, plugin.help_update_numprocs, plugin.do_update_numprocs,
                'dummy_process 2', [call('dummy_process', 2)])


def test_enable(controller, plugin, mocked_check):
    """ Test the enable request. """
    plugin.do_enable('')
    _check_output_error(controller, True)
    assert mocked_check.call_args_list == [call()]
    mocked_check.reset_mock()
    # test help and request
    mocked_rpc = plugin.supvisors().enable
    _check_call(controller, mocked_check, mocked_rpc, plugin.help_enable, plugin.do_enable,
                'dummy_process', [call('dummy_process')])


def test_disable(controller, plugin, mocked_check):
    """ Test the disable request. """
    plugin.do_disable('')
    _check_output_error(controller, True)
    assert mocked_check.call_args_list == [call()]
    mocked_check.reset_mock()
    # test help and request
    mocked_rpc = plugin.supvisors().disable
    _check_call(controller, mocked_check, mocked_rpc, plugin.help_disable, plugin.do_disable,
                'dummy_process', [call('dummy_process')])


def test_conciliate(controller, plugin, mocked_check):
    """ Test the conciliate request. """
    plugin.do_conciliate('')
    _check_output_error(controller, True)
    assert mocked_check.call_args_list == [call()]
    mocked_check.reset_mock()
    # test the request using unknown strategy
    plugin.do_conciliate('strategy')
    _check_output_error(controller, True)
    assert mocked_check.call_args_list == [call()]
    mocked_check.reset_mock()
    # test help and request
    mocked_rpc = plugin.supvisors().conciliate
    _check_call(controller, mocked_check, mocked_rpc, plugin.help_conciliate, plugin.do_conciliate,
                'SENICIDE', [call(0)])


def test_restart_sequence(controller, plugin, mocked_check):
    """ Test the restart_sequence request. """
    mocked_rpc = plugin.supvisors().restart_sequence
    _check_call(controller, mocked_check, mocked_rpc, plugin.help_restart_sequence, plugin.do_restart_sequence,
                '', [call()])


def test_sreload(controller, plugin, mocked_check):
    """ Test the sreload request. """
    mocked_rpc = plugin.supvisors().restart
    _check_call(controller, mocked_check, mocked_rpc, plugin.help_sreload, plugin.do_sreload, '', [call()])


def test_sshutdown(controller, plugin, mocked_check):
    """ Test the sshutdown request. """
    mocked_rpc = plugin.supvisors().shutdown
    _check_call(controller, mocked_check, mocked_rpc, plugin.help_sshutdown, plugin.do_sshutdown, '', [call()])


def test_end_sync(controller, plugin, mocked_check):
    """ Test the end_sync request. """
    mocked_rpc = plugin.supvisors().end_sync
    _check_call(controller, mocked_check, mocked_rpc, plugin.help_end_sync, plugin.do_end_sync,
                '', [call('')])
    _check_call(controller, mocked_check, mocked_rpc, plugin.help_end_sync, plugin.do_end_sync,
                '10.0.0.1', [call('10.0.0.1')])
    # test error
    plugin.do_end_sync('10.0.0.1 10.0.0.2')
    _check_output_error(controller, True)
    assert mocked_check.call_args_list == [call()]


def test_loglevel(controller, plugin, mocked_check):
    """ Test the loglevel request. """
    mocked_rpc = plugin.supvisors().change_log_level
    # test the request without parameter
    plugin.do_loglevel('')
    _check_output_error(controller, True)
    assert mocked_check.call_args_list == [call()]
    mocked_check.reset_mock()
    # test the request using unknown strategy
    plugin.do_loglevel('logger')
    _check_output_error(controller, True)
    assert mocked_check.call_args_list == [call()]
    mocked_check.reset_mock()
    # test help and request
    for code, level in RPCInterface.get_logger_levels().items():
        _check_call(controller, mocked_check, mocked_rpc, plugin.help_loglevel, plugin.do_loglevel,
                    level, [call(code)])


def test_upcheck(controller, plugin):
    """ Test the _upcheck method. """
    # test different API versions
    mocked_rpc = plugin.supvisors().get_api_version
    mocked_rpc.return_value = 'dummy_version'
    assert not plugin._upcheck()
    _check_output_error(controller, True)
    assert mocked_rpc.call_args_list == [call()]
    mocked_rpc.reset_mock()
    # test handled RPC error
    mocked_rpc.side_effect = xmlrpclib.Fault(Faults.UNKNOWN_METHOD, '')
    assert not plugin._upcheck()
    _check_output_error(controller, True)
    assert mocked_rpc.call_args_list == [call()]
    mocked_rpc.reset_mock()
    # test not handled RPC error
    mocked_rpc.side_effect = xmlrpclib.Fault(0, 'error')
    with pytest.raises(xmlrpclib.Fault):
        plugin._upcheck()
    assert mocked_rpc.call_args_list == [call()]
    mocked_rpc.reset_mock()
    # test handled socket errors
    mocked_rpc.side_effect = socket.error(errno.ECONNREFUSED)
    assert not plugin._upcheck()
    _check_output_error(controller, True)
    assert mocked_rpc.call_args_list == [call()]
    mocked_rpc.reset_mock()
    mocked_rpc.side_effect = socket.error(errno.ENOENT)
    assert not plugin._upcheck()
    _check_output_error(controller, True)
    assert mocked_rpc.call_args_list == [call()]
    mocked_rpc.reset_mock()
    # test not handled socket error
    mocked_rpc.side_effect = socket.error(errno.EWOULDBLOCK)
    with pytest.raises(socket.error):
        plugin._upcheck()
    assert mocked_rpc.call_args_list == [call()]
    mocked_rpc.reset_mock()
    # test normal behaviour
    mocked_rpc.side_effect = None
    mocked_rpc.return_value = API_VERSION
    assert plugin._upcheck()
    assert mocked_rpc.call_args_list == [call()]


def test_make_plugin(mocker, controller):
    """ Test the plugin factory. """
    mocked_plugin = mocker.patch('supvisors.supvisorsctl.ControllerPlugin')
    make_supvisors_controller_plugin(controller)
    assert mocked_plugin.call_args_list == [call(controller)]


def test_main(mocker):
    """ Test the plugin factory. """
    mocked_client_options = Mock(args=['start', 'program'], interactive=False, plugin_factories=[])
    mocked_controller = Mock(exitstatus=2)
    mocker.patch('supvisors.supvisorsctl.ClientOptions', return_value=mocked_client_options)
    mocker.patch('supvisors.supvisorsctl.Controller', return_value=mocked_controller)
    mocked_sys = mocker.patch('supvisors.supvisorsctl.sys')
    # test with arguments
    main(args='command args')
    assert mocked_client_options.realize.call_args_list == [call('command args', doc=supervisorctl.__doc__)]
    assert mocked_controller.onecmd.call_args_list == [call('start program')]
    assert not mocked_controller.exec_cmdloop.called
    assert mocked_sys.exit.call_args_list == [call(2)]
    mocker.resetall()
    # test without arguments
    mocked_client_options.args = None
    mocked_client_options.interactive = True
    main()
    assert mocked_client_options.realize.call_args_list == [call(None, doc=supervisorctl.__doc__)]
    assert not mocked_controller.onecmd.called
    assert mocked_controller.exec_cmdloop.call_args_list == [call(None, mocked_client_options)]
    assert mocked_sys.exit.call_args_list == [call(0)]
