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

import pytest

from unittest.mock import call, Mock

from supervisor.supervisorctl import Controller
from supervisor.xmlrpc import Faults

from supvisors.supvisorsctl import *


@pytest.fixture
def controller():
    controller = Mock(spec=Controller)
    controller.get_server_proxy.return_value = Mock(spec=RPCInterface)
    controller.options = Mock(serverurl='dummy_url')
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
    controller.output.reset_mock()


def _check_call(controller, mocked_check, mocked_rpc, help_fct, do_fct, arg, rpc_result):
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
    _check_output_error(controller, False)
    # test request error
    mocked_rpc.side_effect = xmlrpclib.Fault('0', 'error')
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


def _check_start_command(controller, mocked_check, mocked_appli, mocked_rpc,
                         help_cmd, do_cmd, all_result, sel_args, sel_result):
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
    mocked_appli.return_value = [{'application_name': 'appli_1'}, {'application_name': 'appli_2'}]
    # first possibility: use no name
    _check_call(controller, mocked_check, mocked_rpc, help_cmd, do_cmd, 'LESS_LOADED',
                [call(1, all_result[0]), call(1, all_result[1])])
    assert mocked_appli.call_args_list == [call(), call()]
    mocked_appli.reset_mock()
    # second possiblity: use 'all'
    _check_call(controller, mocked_check, mocked_rpc, help_cmd, do_cmd, 'MOST_LOADED all',
                [call(2, all_result[0]), call(2, all_result[1])])
    assert mocked_appli.call_args_list == [call(), call()]
    mocked_appli.reset_mock()
    # test help and request for starting a selection
    _check_call(controller, mocked_check, mocked_rpc, help_cmd, do_cmd, 'CONFIG ' + sel_args,
                [call(0, sel_result[0]), call(0, sel_result[1])])
    # test help and request with get_all_applications_info error
    mocked_appli.reset_mock()
    mocked_appli.side_effect = xmlrpclib.Fault('0', 'error')
    do_cmd('LESS_LOADED')
    assert mocked_appli.call_args_list == [call()]
    assert mocked_rpc.call_count == 0
    _check_output_error(controller, True)


def _check_stop_command(controller, mocked_check, mocked_appli, mocked_rpc,
                        help_cmd, do_cmd, all_result, sel_args, sel_result):
    """ Common test of a stopping command. """
    # test request to stop all
    mocked_appli.return_value = [{'application_name': 'appli_1'}, {'application_name': 'appli_2'}]
    # first possibility: use no name
    _check_call(controller, mocked_check, mocked_rpc, help_cmd, do_cmd,
                '', [call(all_result[0]), call(all_result[1])])
    assert mocked_appli.call_args_list == [call(), call()]
    mocked_appli.reset_mock()
    # second possiblity: use 'all'
    _check_call(controller, mocked_check, mocked_rpc, help_cmd, do_cmd,
                'all', [call(all_result[0]), call(all_result[1])])
    assert mocked_appli.call_args_list == [call(), call()]
    mocked_appli.reset_mock()
    # test help and request for starting a selection of applications
    _check_call(controller, mocked_check, mocked_rpc, help_cmd, do_cmd,
                sel_args, [call(sel_result[0]), call(sel_result[1])])
    # test help and request with get_all_applications_info error
    mocked_appli.reset_mock()
    mocked_appli.side_effect = xmlrpclib.Fault('0', 'error')
    do_cmd('')
    assert mocked_appli.call_args_list == [call()]
    assert mocked_rpc.call_count == 0
    _check_output_error(controller, True)


def test_supvisors(controller, plugin):
    """ Test the access to Supvisors proxy. """
    # test the proxy
    assert RPCInterface == plugin.supvisors()._spec_class
    assert controller.get_server_proxy.call_args_list == [call('supvisors')]


def test_sversion(controller, plugin, mocked_check):
    """ Test the sversion request. """
    mocked_rpc = plugin.supvisors().get_api_version
    _check_call(controller, mocked_check, mocked_rpc, plugin.help_sversion, plugin.do_sversion, '', [call()])


def test_master(controller, plugin, mocked_check):
    """ Test the master request. """
    mocked_rpc = plugin.supvisors().get_master_address
    _check_call(controller, mocked_check, mocked_rpc, plugin.help_master, plugin.do_master, '', [call()])


def test_strategies(controller, plugin, mocked_check):
    """ Test the master request. """
    mocked_rpc = plugin.supvisors().get_strategies
    mocked_rpc.return_value = {'conciliation': 'hard', 'starting': 'easy', 'auto-fencing': True}
    _check_call(controller, mocked_check, mocked_rpc, plugin.help_strategies, plugin.do_strategies, '', [call()])


def test_sstate(controller, plugin, mocked_check):
    """ Test the sstate request. """
    mocked_rpc = plugin.supvisors().get_supvisors_state
    mocked_rpc.return_value = {'statecode': 10, 'statename': 'running'}
    _check_call(controller, mocked_check, mocked_rpc, plugin.help_sstate, plugin.do_sstate, '', [call()])


def test_address_status(controller, plugin, mocked_check):
    """ Test the address_status request. """
    mocked_rpc = plugin.supvisors().get_all_addresses_info
    mocked_rpc.return_value = [{'address_name': '10.0.0.1', 'statename': 'running',
                                'loading': 10, 'local_time': 1500, 'sequence_counter': 12},
                               {'address_name': '10.0.0.2', 'statename': 'stopped',
                                'loading': 0, 'local_time': 100, 'sequence_counter': 15}]
    _check_call(controller, mocked_check, mocked_rpc,
                plugin.help_address_status, plugin.do_address_status, '', [call()])
    _check_call(controller, mocked_check, mocked_rpc,
                plugin.help_address_status, plugin.do_address_status, 'all', [call()])
    # test help and request for address status from a selection of address names
    _check_call(controller, mocked_check, mocked_rpc, plugin.help_address_status, plugin.do_address_status,
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
                                'statename': 'running', 'addresses': ['10.0.1', '10.0.2']},
                               {'application_name': 'appli_2', 'process_name': 'proc_3',
                                'statename': 'stopped', 'addresses': []}]
    _check_call(controller, mocked_check, mocked_rpc, plugin.help_sstatus, plugin.do_sstatus, '', [call()])
    _check_call(controller, mocked_check, mocked_rpc, plugin.help_sstatus, plugin.do_sstatus, 'all', [call()])
    # test help and request for process info from a selection of namespecs
    mocked_rpc = plugin.supvisors().get_process_info
    mocked_rpc.side_effect = [[{'application_name': 'appli_1', 'process_name': 'proc_1',
                                'statename': 'running', 'addresses': ['10.0.1', '10.0.2']}],
                              [{'application_name': 'appli_2', 'process_name': 'proc_3',
                                'statename': 'stopped', 'addresses': []}]]
    _check_call(controller, mocked_check, mocked_rpc, plugin.help_sstatus, plugin.do_sstatus,
                'appli_2:proc_3 appli_1:proc_1', [call('appli_2:proc_3'), call('appli_1:proc_1')])


def test_local_status(controller, plugin, mocked_check):
    """ Test the local_status request. """
    mocked_rpc = plugin.supvisors().get_all_local_process_info
    mocked_rpc.return_value = [{'group': 'appli_1', 'name': 'proc_1',
                                'state': 20, 'start': 1234, 'now': 4321, 'pid': 14725,
                                'extra_args': '-x dummy'},
                               {'group': 'appli_2', 'name': 'proc_3',
                                'state': 0, 'start': 0, 'now': 0, 'pid': 0,
                                'extra_args': ''}]
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
    returned_rules = [{'application_name': 'appli_1', 'managed': True, 'distributed': True,
                       'start_sequence': 2, 'stop_sequence': 3, 'starting_strategy': 'CONFIG',
                       'starting_failure_strategy': 'ABORT', 'running_failure_strategy': 'CONTINUE'},
                      {'application_name': 'appli_2', 'managed': True,
                       'distributed': False, 'addresses': ['10.0.0.1', '10.0.0.2', '10.0.0.3'],
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
    mocked_appli.side_effect = xmlrpclib.Fault('0', 'error')
    plugin.do_application_rules('')
    assert mocked_appli.call_args_list == [call()]
    assert mocked_rpc.call_count == 0
    _check_output_error(controller, True)


def test_process_rules(controller, plugin, mocked_check):
    """ Test the process_rules request. """
    mocked_appli = plugin.supvisors().get_all_applications_info
    mocked_appli.return_value = [{'application_name': 'appli_1'}, {'application_name': 'appli_2'}]
    mocked_rpc = plugin.supvisors().get_process_rules
    returned_rules = [[{'application_name': 'appli_1', 'process_name': 'proc_1', 'addresses': ['10.0.0.1', '10.0.0.2'],
                        'start_sequence': 2, 'stop_sequence': 3, 'required': True, 'wait_exit': False,
                        'expected_loading': 50, 'running_failure_strategy': 1}],
                      [{'application_name': 'appli_2', 'process_name': 'proc_3', 'addresses': ['*'],
                        'start_sequence': 1, 'stop_sequence': 0, 'required': False, 'wait_exit': True,
                        'expected_loading': 15, 'running_failure_strategy': 2}]]
    # first possiblity: no argument
    mocked_rpc.side_effect = returned_rules
    _check_call(controller, mocked_check, mocked_rpc, plugin.help_process_rules, plugin.do_process_rules,
                '', [call('appli_1:*'), call('appli_2:*')])
    assert mocked_appli.call_args_list == [call(), call()]
    mocked_appli.reset_mock()
    # second possiblity: use 'all'
    mocked_rpc.side_effect = returned_rules
    _check_call(controller, mocked_check, mocked_rpc, plugin.help_process_rules, plugin.do_process_rules,
                'all', [call('appli_1:*'), call('appli_2:*')])
    assert mocked_appli.call_args_list == [call(), call()]
    mocked_appli.reset_mock()
    # test help and request for rules from a selection of namespecs
    mocked_rpc.side_effect = returned_rules
    _check_call(controller, mocked_check, mocked_rpc, plugin.help_process_rules, plugin.do_process_rules,
                'appli_2:proc_3 appli_1:proc_1', [call('appli_2:proc_3'), call('appli_1:proc_1')])
    assert mocked_appli.call_count == 0
    # test help and request with get_all_applications_info error
    mocked_appli.reset_mock()
    mocked_appli.side_effect = xmlrpclib.Fault('0', 'error')
    plugin.do_process_rules('')
    assert mocked_appli.call_args_list == [call()]
    assert mocked_rpc.call_count == 0
    _check_output_error(controller, True)


def test_conflicts(controller, plugin, mocked_check):
    """ Test the conflicts request. """
    mocked_rpc = plugin.supvisors().get_conflicts
    mocked_rpc.return_value = [{'application_name': 'appli_1', 'process_name': 'proc_1',
                                'statename': 'running', 'addresses': ['10.0.0.1', '10.0.0.2']},
                               {'application_name': 'appli_2', 'process_name': 'proc_3',
                                'statename': 'stopped', 'addresses': ['10.0.0.2', '10.0.0.3']}]
    _check_call(controller, mocked_check, mocked_rpc, plugin.help_conflicts, plugin.do_conflicts, '', [call()])


def test_start_application(controller, plugin, mocked_check):
    """ Test the start_application request. """
    mocked_appli = plugin.supvisors().get_all_applications_info
    mocked_rpc = plugin.supvisors().start_application
    _check_start_command(controller, mocked_check, mocked_appli, mocked_rpc,
                         plugin.help_start_application, plugin.do_start_application,
                         ('appli_1', 'appli_2'), 'appli_2 appli_1', ('appli_2', 'appli_1'))


def test_restart_application(controller, plugin, mocked_check):
    """ Test the restart_application request. """
    mocked_appli = plugin.supvisors().get_all_applications_info
    mocked_rpc = plugin.supvisors().restart_application
    _check_start_command(controller, mocked_check, mocked_appli, mocked_rpc,
                         plugin.help_restart_application, plugin.do_restart_application,
                         ('appli_1', 'appli_2'), 'appli_2 appli_1', ('appli_2', 'appli_1'))


def test_stop_application(controller, plugin, mocked_check):
    """ Test the stop_application request. """
    mocked_appli = plugin.supvisors().get_all_applications_info
    mocked_rpc = plugin.supvisors().stop_application
    _check_stop_command(controller, mocked_check, mocked_appli, mocked_rpc,
                        plugin.help_stop_application, plugin.do_stop_application,
                        ('appli_1', 'appli_2'), 'appli_2 appli_1', ('appli_2', 'appli_1'))


def test_start_args(controller, plugin, mocked_check):
    """ Test the start_args request. """
    plugin.do_start_args('')
    _check_output_error(controller, True)
    assert mocked_check.call_args_list == [call()]
    mocked_check.reset_mock()
    # test request to start process without extra arguments
    mocked_rpc = plugin.supvisors().start_args
    _check_call(controller, mocked_check, mocked_rpc, plugin.help_start_args, plugin.do_start_args,
                'proc MOST_LOADED all', [call('proc', 'MOST_LOADED all')])


def test_start_process(controller, plugin, mocked_check):
    """ Test the start_process request. """
    mocked_appli = plugin.supvisors().get_all_applications_info
    mocked_rpc = plugin.supvisors().start_process
    _check_start_command(controller, mocked_check, mocked_appli, mocked_rpc,
                         plugin.help_start_process, plugin.do_start_process,
                         ('appli_1:*', 'appli_2:*'), 'appli_2:proc_3 appli_1:proc_1',
                         ('appli_2:proc_3', 'appli_1:proc_1'))


def test_restart_process(controller, plugin, mocked_check):
    """ Test the restart_process request. """
    mocked_appli = plugin.supvisors().get_all_applications_info
    mocked_rpc = plugin.supvisors().restart_process
    _check_start_command(controller, mocked_check, mocked_appli, mocked_rpc,
                         plugin.help_restart_process, plugin.do_restart_process,
                         ('appli_1:*', 'appli_2:*'), 'appli_2:proc_3 appli_1:proc_1',
                         ('appli_2:proc_3', 'appli_1:proc_1'))


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
    _check_call(controller, mocked_check, mocked_rpc, plugin.help_start_process_args, plugin.do_start_process_args,
                'LESS_LOADED appli_2:proc_3 a list of arguments', [call(1, 'appli_2:proc_3', 'a list of arguments')])


def test_stop_process(controller, plugin, mocked_check):
    """ Test the stop_process request. """
    mocked_appli = plugin.supvisors().get_all_applications_info
    mocked_rpc = plugin.supvisors().stop_process
    _check_stop_command(controller, mocked_check, mocked_appli, mocked_rpc,
                        plugin.help_stop_process, plugin.do_stop_process,
                        ('appli_1:*', 'appli_2:*'), 'appli_2:proc_3 appli_1:proc_1',
                        ('appli_2:proc_3', 'appli_1:proc_1'))


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


def test_sreload(controller, plugin, mocked_check):
    """ Test the sreload request. """
    mocked_rpc = plugin.supvisors().restart
    _check_call(controller, mocked_check, mocked_rpc, plugin.help_sreload, plugin.do_sreload, '', [call()])


def test_sshutdown(controller, plugin, mocked_check):
    """ Test the sshutdown request. """
    mocked_rpc = plugin.supvisors().shutdown
    _check_call(controller, mocked_check, mocked_rpc, plugin.help_sshutdown, plugin.do_sshutdown, '', [call()])


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
    for code, level in RPCInterface._get_logger_levels().items():
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
    mocked_rpc.side_effect = xmlrpclib.Fault('0', 'error')
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
