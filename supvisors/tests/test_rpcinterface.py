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

from supvisors import __version__
from supvisors.instancestatus import StateModes
from supvisors.rpcinterface import *
from supvisors.statscollector import StatsMsgType
from supvisors.ttypes import (ApplicationStates, ConciliationStrategies, DistributionRules, SupvisorsStates,
                              SupvisorsFaults)
from .base import DummyRpcInterface
from .conftest import create_application


@pytest.fixture
def rpc(supvisors) -> RPCInterface:
    """ create the instance to be tested. """
    return RPCInterface(supvisors)


def test_creation(supvisors, rpc):
    """ Test the values set at construction. """
    assert rpc.supvisors is supvisors
    assert rpc.logger is supvisors.logger


def test_api_version(rpc):
    """ Test the get_api_version RPC. """
    assert rpc.get_api_version() == __version__


def test_supvisors_state(rpc):
    """ Test the get_supvisors_state RPC. """
    assert rpc.get_supvisors_state() == {'fsm_statecode': 0, 'fsm_statename': 'OFF',
                                         'discovery_mode': False,
                                         'master_identifier': '',
                                         'starting_jobs': [], 'stopping_jobs': []}


def test_master_node(supvisors, rpc):
    """ Test the get_master_address RPC. """
    # prepare context
    supvisors.context.master_identifier = '10.0.0.1'
    # test call
    assert rpc.get_master_identifier() == '10.0.0.1'


def test_strategies(supvisors, rpc):
    """ Test the get_strategies RPC. """
    # prepare context
    supvisors.options.auto_fence = True
    supvisors.options.conciliation_strategy = ConciliationStrategies.INFANTICIDE
    supvisors.options.starting_strategy = StartingStrategies.MOST_LOADED
    # test call
    assert rpc.get_strategies() == {'auto-fencing': True, 'starting': 'MOST_LOADED', 'conciliation': 'INFANTICIDE'}


def test_statistics_status(supvisors, rpc):
    """ Test the get_statistics_status RPC. """
    # test call
    assert rpc.get_statistics_status() == {'host_stats': True, 'process_stats': True, 'collecting_period': 5}
    # update options
    supvisors.options.process_stats_enabled = False
    supvisors.options.collecting_period = 7.5
    assert rpc.get_statistics_status() == {'host_stats': True, 'process_stats': False, 'collecting_period': 7.5}
    # delete statistics collector
    supvisors.options.host_stats_enabled = False
    supvisors.options.process_stats_enabled = True
    supvisors.stats_collector = None
    assert rpc.get_statistics_status() == {'host_stats': False, 'process_stats': False, 'collecting_period': 7.5}


def test_instance_info(supvisors, rpc):
    """ Test the RPCInterface.get_instance_info XML-RPC. """
    instance = supvisors.context.instances['10.0.0.1:25000']
    instance.state_modes = StateModes(SupvisorsStates.CONCILIATION, True, '10.0.0.2', False, True)
    # test with known identifier
    expected = {'identifier': '10.0.0.1:25000', 'nick_identifier': '10.0.0.1',
                'node_name': '10.0.0.1', 'port': 25000, 'loading': 0,
                'local_mtime': 0.0, 'local_time': 0, 'local_sequence_counter': 0,
                'remote_mtime': 0.0, 'remote_time': 0, 'remote_sequence_counter': 0,
                'statecode': 0, 'statename': 'UNKNOWN', 'discovery_mode': True,
                'process_failure': False,
                'fsm_statecode': 4, 'fsm_statename': 'CONCILIATION',
                'master_identifier': '10.0.0.2',
                'starting_jobs': False, 'stopping_jobs': True}
    assert rpc.get_instance_info('10.0.0.1') == [expected]
    # test with unknown identifier
    with pytest.raises(RPCError) as exc:
        rpc.get_instance_info('10.0.0.0')
    assert exc.value.args == (Faults.BAD_NAME, 'identifier=10.0.0.0 is unknown to Supvisors')


def test_all_instances_info(supvisors, rpc):
    """ Test the get_all_instances_info RPC. """
    supvisors.starter.in_progress.return_value = False
    supvisors.stopper.in_progress.return_value = True
    # prepare context
    supvisors.mapper._instances = {'10.0.0.1:25000': Mock(),
                                   '10.0.0.2:25000': Mock()}
    supvisors.context.instances = {'10.0.0.1:25000': Mock(**{'serial.return_value': 'address_info_1'}),
                                   '10.0.0.2:25000': Mock(**{'serial.return_value': 'address_info_2'})}
    # test call
    assert rpc.get_all_instances_info() == ['address_info_1', 'address_info_2']


def test_application_info(mocker, supvisors, rpc):
    """ Test the get_application_info RPC. """
    application = create_application('TestApplication', supvisors)
    mocked_serial = mocker.patch('supvisors.rpcinterface.RPCInterface._get_application', return_value=application)
    mocked_check = mocker.patch('supvisors.rpcinterface.RPCInterface._check_from_distribution')
    # test RPC call
    assert rpc.get_application_info('dummy') == {'application_name': 'TestApplication', 'managed': False,
                                                 'major_failure': False, 'minor_failure': False,
                                                 'statecode': 0, 'statename': 'STOPPED'}
    assert mocked_check.call_args_list == [call()]
    assert mocked_serial.call_args_list == [call('dummy')]


def test_all_applications_info(mocker, supvisors, rpc):
    """ Test the get_all_applications_info RPC. """
    mocked_get = mocker.patch('supvisors.rpcinterface.RPCInterface.get_application_info',
                              side_effect=[{'name': 'appli_1'}, {'name': 'appli_2'}])
    mocked_check = mocker.patch('supvisors.rpcinterface.RPCInterface._check_from_distribution')
    # prepare context
    supvisors.context.applications = {'dummy_1': None, 'dummy_2': None}
    # test RPC call
    assert rpc.get_all_applications_info() == [{'name': 'appli_1'}, {'name': 'appli_2'}]
    assert mocked_check.call_args_list == [call()]
    assert mocked_get.call_args_list == [call('dummy_1'), call('dummy_2')]


def test_process_info(mocker, rpc):
    """ Test the get_process_info RPC. """
    mocked_get = mocker.patch('supvisors.rpcinterface.RPCInterface._get_application_process',
                              side_effect=[(None, Mock(**{'serial.return_value': {'name': 'proc'}})),
                                           (Mock(**{'processes.values.return_value': [
                                               Mock(**{'serial.return_value': {'name': 'proc_1'}}),
                                               Mock(**{'serial.return_value': {'name': 'proc_2'}})]}), None)])
    mocked_check = mocker.patch('supvisors.rpcinterface.RPCInterface._check_from_distribution')
    # test first RPC call with process namespec
    assert rpc.get_process_info('appli:proc') == [{'name': 'proc'}]
    assert mocked_check.call_args_list == [call()]
    assert mocked_get.call_args_list == [call('appli:proc')]
    # reset patches
    mocked_check.reset_mock()
    mocked_get.reset_mock()
    # test second RPC call with group namespec
    assert rpc.get_process_info('appli:*') == [{'name': 'proc_1'}, {'name': 'proc_2'}]
    assert mocked_check.call_args_list == [call()]
    assert mocked_get.call_args_list == [call('appli:*')]


def test_all_process_info(mocker, supvisors, rpc):
    """ Test the get_all_process_info RPC. """
    mocked_check = mocker.patch('supvisors.rpcinterface.RPCInterface._check_from_distribution')
    # prepare context
    supvisors.context.applications = {
        'appli_1': Mock(processes={'proc_1_1': Mock(**{'serial.return_value': {'name': 'proc_1_1'}}),
                                   'proc_1_2': Mock(**{'serial.return_value': {'name': 'proc_1_2'}})}),
        'appli_2': Mock(processes={'proc_2': Mock(**{'serial.return_value': {'name': 'proc_2'}})})}
    # test RPC call
    assert rpc.get_all_process_info() == [{'name': 'proc_1_1'}, {'name': 'proc_1_2'}, {'name': 'proc_2'}]
    assert mocked_check.call_args_list == [call()]


def test_local_process_info(mocker, supvisors, rpc):
    """ Test the get_local_process_info RPC. """
    mocked_get = mocker.patch('supvisors.rpcinterface.RPCInterface._get_local_info',
                              return_value={'group': 'group', 'name': 'name'})
    # prepare context
    supervisor_data = supvisors.supervisor_data
    mocked_rpc = supervisor_data.supervisor_rpc_interface.getProcessInfo
    mocked_rpc.return_value = {'group': 'dummy_group', 'name': 'dummy_name'}
    # test RPC call with process namespec
    assert rpc.get_local_process_info('appli:proc') == {'group': 'group', 'name': 'name'}
    assert mocked_rpc.call_args_list == [call('appli:proc')]
    assert mocked_get.call_args_list == [call({'group': 'dummy_group', 'name': 'dummy_name'})]


def test_all_local_process_info(mocker, rpc):
    """ Test the get_all_local_process_info RPC. """
    mocked_get = mocker.patch('supvisors.rpcinterface.RPCInterface._get_local_info',
                              return_value={'group': 'group', 'name': 'name'})
    # prepare context
    info_source = rpc.supvisors.supervisor_data
    mocked_rpc = info_source.supervisor_rpc_interface.getAllProcessInfo
    mocked_rpc.return_value = [{'group': 'dummy_group', 'name': 'dummy_name'}]
    # test RPC call with process namespec
    assert rpc.get_all_local_process_info() == [{'group': 'group', 'name': 'name'}]
    assert mocked_rpc.call_args_list == [call()]
    assert mocked_get.call_args_list == [call({'group': 'dummy_group', 'name': 'dummy_name'})]


def test_inner_process_info(supvisors, rpc):
    """ Test the get_inner_process_info RPC. """
    # prepare context
    proc_1 = Mock(application_name='group',
                  info_map={'10.0.0.1:25000': {'name': 'proc_1', 'state': 'RUNNING'},
                            '10.0.0.2:25000': {'name': 'proc_1', 'state': 'STOPPED'}})
    proc_2 = Mock(application_name='group',
                  info_map={'10.0.0.2:25000': {'name': 'proc_2', 'state': 'STARTING'}})
    supvisors.context.instances['10.0.0.1:25000'].processes = {'proc_1': proc_1}
    supvisors.context.instances['10.0.0.2:25000'].processes = {'proc_1': proc_1, 'proc_2': proc_2}
    application = create_application('group', supvisors)
    application.processes = {'proc_1': proc_1, 'proc_2': proc_2}
    supvisors.context.applications['group'] = application
    # test unknown identifier
    with pytest.raises(RPCError) as exc:
        rpc.get_inner_process_info('10.0.0.0', 'group:proc_1')
    assert exc.value.args == (Faults.BAD_NAME, 'identifier=10.0.0.0 is unknown to Supvisors')
    # test known identifier but without handshake
    with pytest.raises(RPCError) as exc:
        rpc.get_inner_process_info('10.0.0.3', 'group:proc_1')
    assert exc.value.args == (Faults.FAILED, 'group:proc_1 unknown on 10.0.0.3')
    # test unknown application
    with pytest.raises(RPCError) as exc:
        rpc.get_inner_process_info('10.0.0.1', 'dummy_group:proc_1')
    assert exc.value.args == (Faults.BAD_NAME, 'application=dummy_group unknown to Supvisors')
    # test unknown namespec
    with pytest.raises(RPCError) as exc:
        rpc.get_inner_process_info('10.0.0.1', 'group:proc')
    assert exc.value.args == (Faults.BAD_NAME, 'process=proc unknown in application=group')
    # test RPC call with nick identifier and process namespec
    assert rpc.get_inner_process_info('10.0.0.1', 'group:proc_1') == [{'name': 'proc_1', 'state': 'RUNNING'}]
    assert rpc.get_inner_process_info('10.0.0.2', 'group:proc_1') == [{'name': 'proc_1', 'state': 'STOPPED'}]
    assert rpc.get_inner_process_info('10.0.0.2', 'group:proc_2') == [{'name': 'proc_2', 'state': 'STARTING'}]
    with pytest.raises(RPCError) as exc:
        rpc.get_inner_process_info('10.0.0.1', 'group:proc_2')
    assert exc.value.args == (Faults.FAILED, 'group:proc_2 unknown on 10.0.0.1')
    # test RPC call with nick identifier and homogeneous group namespec
    assert rpc.get_inner_process_info('10.0.0.1', 'group:*') == [{'name': 'proc_1', 'state': 'RUNNING'}]
    assert rpc.get_inner_process_info('10.0.0.2', 'group:*') == [{'name': 'proc_1', 'state': 'STOPPED'},
                                                                 {'name': 'proc_2', 'state': 'STARTING'}]


def test_get_all_inner_process_info(supvisors, rpc):
    """ Test the get_all_inner_process_info RPC. """
    # prepare context
    proc_1 = Mock(application_name='group',
                  info_map={'10.0.0.1:25000': {'name': 'proc_1', 'state': 'RUNNING'},
                            '10.0.0.2:25000': {'name': 'proc_1', 'state': 'STOPPED'}})
    proc_2 = Mock(application_name='group',
                  info_map={'10.0.0.2:25000': {'name': 'proc_2', 'state': 'STARTING'}})
    supvisors.context.instances['10.0.0.1:25000'].processes = {'proc_1': proc_1}
    supvisors.context.instances['10.0.0.2:25000'].processes = {'proc_1': proc_1, 'proc_2': proc_2}
    application = create_application('group', supvisors)
    application.processes = {'proc_1': proc_1, 'proc_2': proc_2}
    supvisors.context.applications['group'] = application
    # test unknown identifier
    with pytest.raises(RPCError) as exc:
        rpc.get_all_inner_process_info('10.0.0.0')
    assert exc.value.args == (Faults.BAD_NAME, 'identifier=10.0.0.0 is unknown to Supvisors')
    # test known identifier but without handshake
    assert rpc.get_all_inner_process_info('10.0.0.3') == []
    # test RPC call with nick identifier for all processes
    assert rpc.get_all_inner_process_info('10.0.0.1') == [{'name': 'proc_1', 'state': 'RUNNING'}]
    assert rpc.get_all_inner_process_info('10.0.0.2') == [{'name': 'proc_1', 'state': 'STOPPED'},
                                                          {'name': 'proc_2', 'state': 'STARTING'}]


def test_application_rules(mocker, supvisors, rpc):
    """ Test the get_application_rules RPC. """
    application = create_application('TestApplication', supvisors)
    mocked_check = mocker.patch('supvisors.rpcinterface.RPCInterface._check_from_distribution')
    mocked_get = mocker.patch('supvisors.rpcinterface.RPCInterface._get_application', return_value=application)
    # test RPC call with application name and unmanaged application
    expected = {'application_name': 'appli', 'managed': False}
    assert rpc.get_application_rules('appli') == expected
    assert mocked_check.call_args_list == [call()]
    assert mocked_get.call_args_list == [call('appli')]
    mocker.resetall()
    # test RPC call with application name and managed/distributed application
    application.rules.managed = True
    expected = {'application_name': 'appli', 'managed': True, 'distribution': 'ALL_INSTANCES',
                'identifiers': ['*'],
                'start_sequence': 0, 'stop_sequence': -1, 'starting_strategy': 'CONFIG',
                'starting_failure_strategy': 'ABORT', 'running_failure_strategy': 'CONTINUE',
                'status_formula': ''}
    assert rpc.get_application_rules('appli') == expected
    assert mocked_check.call_args_list == [call()]
    assert mocked_get.call_args_list == [call('appli')]
    mocker.resetall()
    # test RPC call with application name and managed/non-distributed application
    application.rules.distribution = DistributionRules.SINGLE_INSTANCE
    application.rules.status_formula = "'dumb' or 'dumber'"
    expected = {'application_name': 'appli', 'managed': True, 'distribution': 'SINGLE_INSTANCE',
                'identifiers': ['*'], 'start_sequence': 0, 'stop_sequence': -1, 'starting_strategy': 'CONFIG',
                'starting_failure_strategy': 'ABORT', 'running_failure_strategy': 'CONTINUE',
                'status_formula': "'dumb' or 'dumber'"}
    assert rpc.get_application_rules('appli') == expected
    assert mocked_check.call_args_list == [call()]
    assert mocked_get.call_args_list == [call('appli')]


def test_process_rules(mocker, rpc):
    """ Test the get_process_rules RPC. """
    mocked_check = mocker.patch('supvisors.rpcinterface.RPCInterface._check_from_distribution')
    mocked_get = mocker.patch('supvisors.rpcinterface.RPCInterface._get_application_process',
                              side_effect=[(None, '1'), (Mock(**{'processes.values.return_value': ['1', '2']}), None)])
    mocked_rules = mocker.patch('supvisors.rpcinterface.RPCInterface._get_internal_process_rules',
                                side_effect=[{'start': 1}, {'stop': 2}, {'required': True}])
    # test first RPC call with process namespec
    assert rpc.get_process_rules('appli:proc') == [{'start': 1}]
    assert mocked_check.call_args_list == [call()]
    assert mocked_get.call_args_list == [call('appli:proc')]
    assert mocked_rules.call_args_list == [call('1')]
    # reset patches
    mocked_check.reset_mock()
    mocked_get.reset_mock()
    mocked_rules.reset_mock()
    # test second RPC call with group namespec
    assert rpc.get_process_rules('appli:*') == [{'stop': 2}, {'required': True}]
    assert mocked_check.call_args_list == [call()]
    assert mocked_get.call_args_list == [call('appli:*')]
    assert mocked_rules.call_args_list == [call('1'), call('2')]


def test_conflicts(mocker, rpc):
    """ Test the get_conflicts RPC. """
    mocked_check = mocker.patch('supvisors.rpcinterface.RPCInterface._check_from_distribution')
    # prepare context
    proc_1 = Mock(**{'serial.return_value': {'name': 'proc_1'}})
    proc_3 = Mock(**{'serial.return_value': {'name': 'proc_3'}})
    mocker.patch.object(rpc.supvisors.context, 'conflicts', return_value=[proc_1, proc_3])
    # test RPC call
    assert rpc.get_conflicts() == [{'name': 'proc_1'}, {'name': 'proc_3'}]
    assert mocked_check.call_args_list == [call()]


def test_start_application(mocker, supvisors, rpc):
    """ Test the start_application RPC. """
    mocked_check = mocker.patch('supvisors.rpcinterface.RPCInterface._check_operating')
    # prepare context
    supvisors.context.applications = {'appli_1': Mock(**{'rules.managed': True}),
                                      'appli_2': Mock(**{'rules.managed': False})}
    # get patches
    mocked_start = supvisors.starter.start_application
    mocked_progress = supvisors.starter.in_progress
    # test RPC call with unknown strategy
    with pytest.raises(RPCError) as exc:
        rpc.start_application('strategy', 'appli')
    assert exc.value.args[0] == Faults.INCORRECT_PARAMETERS
    assert mocked_check.call_args_list == [call()]
    assert mocked_start.call_count == 0
    assert mocked_start.call_count == 0
    assert mocked_progress.call_count == 0
    mocked_check.reset_mock()
    # test RPC call with unknown application
    with pytest.raises(RPCError) as exc:
        rpc.start_application(0, 'appli')
    assert exc.value.args == (Faults.BAD_NAME, 'application=appli unknown to Supvisors')
    assert mocked_check.call_args_list == [call()]
    assert mocked_start.call_count == 0
    assert mocked_progress.call_count == 0
    mocked_check.reset_mock()
    # test RPC call with unmanaged application
    with pytest.raises(RPCError) as exc:
        rpc.start_application(0, 'appli_2')
    assert exc.value.args == (SupvisorsFaults.NOT_MANAGED.value, 'appli_2')
    assert mocked_check.call_args_list == [call()]
    assert mocked_start.call_count == 0
    assert mocked_progress.call_count == 0
    mocked_check.reset_mock()
    # test RPC call with running application
    application = rpc.supvisors.context.applications['appli_1']
    for appli_state in [ApplicationStates.STOPPING, ApplicationStates.RUNNING, ApplicationStates.STARTING]:
        application.state = appli_state
        with pytest.raises(RPCError) as exc:
            rpc.start_application(0, 'appli_1')
        assert exc.value.args == (Faults.ALREADY_STARTED, 'appli_1')
        assert mocked_check.call_args_list == [call()]
        assert not mocked_start.called
        assert not mocked_progress.called
        mocked_check.reset_mock()
    # test RPC call with stopped application
    # test no wait and not done
    application.state = ApplicationStates.STOPPED
    mocked_progress.return_value = True
    result = rpc.start_application(0, 'appli_1', False)
    assert result
    assert mocked_check.call_args_list == [call()]
    assert mocked_start.call_args_list == [call(StartingStrategies.CONFIG, application)]
    assert mocked_progress.called
    mocked_check.reset_mock()
    mocked_start.reset_mock()
    mocked_progress.reset_mock()
    # test internal failure
    application.state = ApplicationStates.STOPPED
    mocked_progress.return_value = False
    with pytest.raises(RPCError) as exc:
        rpc.start_application(0, 'appli_1', False)
    assert exc.value.args == (Faults.ABNORMAL_TERMINATION, 'failed to start appli_1')
    assert mocked_check.call_args_list == [call()]
    assert mocked_start.call_args_list == [call(StartingStrategies.CONFIG, application)]
    assert mocked_progress.called
    mocked_check.reset_mock()
    mocked_start.reset_mock()
    mocked_progress.reset_mock()
    # test wait and not done
    mocked_progress.return_value = True
    deferred = rpc.start_application(0, 'appli_1')
    # result is a function for deferred result
    assert callable(deferred)
    assert mocked_check.call_args_list == [call()]
    assert mocked_start.call_args_list == [call(StartingStrategies.CONFIG, application)]
    assert mocked_progress.called
    mocked_progress.reset_mock()
    # test returned function: return True when job in progress
    assert deferred() == NOT_DONE_YET
    assert mocked_progress.call_args_list == [call()]
    mocked_progress.reset_mock()
    # test returned function: raise exception if job not in progress anymore and application not running
    mocked_progress.return_value = False
    for _ in [ApplicationStates.STOPPING, ApplicationStates.STOPPED, ApplicationStates.STARTING]:
        with pytest.raises(RPCError) as exc:
            deferred()
        assert exc.value.args == (Faults.NOT_RUNNING, 'appli_1')
        assert mocked_progress.call_args_list == [call()]
        mocked_progress.reset_mock()
    # test returned function: return True if job not in progress anymore and application running
    application.state = ApplicationStates.RUNNING
    assert deferred()
    assert mocked_progress.call_args_list == [call()]


def test_test_start_application(mocker, supvisors, rpc):
    """ Test the test_start_application RPC. """
    mocked_check = mocker.patch('supvisors.rpcinterface.RPCInterface._check_operating')
    # prepare context
    supvisors.context.applications = {'appli_1': Mock(**{'rules.managed': True}),
                                      'appli_2': Mock(**{'rules.managed': False})}
    # get patches
    mocked_start = supvisors.starter_model.test_start_application
    expected = [{'application_name': 'appli_1', 'process_name': 'proc_1',
                 'state': 'RUNNING', 'running_identifiers': ['10.0.0.1'], 'forced_reason': ''},
                {'application_name': 'appli_1', 'process_name': 'proc_2',
                 'state': 'EXITED', 'running_identifiers': [], 'forced_reason': ''},
                {'application_name': 'appli_1', 'process_name': 'proc_3',
                 'state': 'FATAL', 'running_identifiers': [], 'forced_reason': 'no resource'}]
    mocked_start.return_value = expected
    # test RPC call with unknown strategy
    with pytest.raises(RPCError) as exc:
        rpc.test_start_application('strategy', 'appli')
    assert exc.value.args[0] == Faults.INCORRECT_PARAMETERS
    assert mocked_check.call_args_list == [call()]
    assert not mocked_start.called
    mocked_check.reset_mock()
    # test RPC call with unknown application
    with pytest.raises(RPCError) as exc:
        rpc.test_start_application(0, 'appli')
    assert exc.value.args == (Faults.BAD_NAME, 'application=appli unknown to Supvisors')
    assert mocked_check.call_args_list == [call()]
    assert not mocked_start.called
    mocked_check.reset_mock()
    # test RPC call with unmanaged application
    with pytest.raises(RPCError) as exc:
        rpc.test_start_application(0, 'appli_2')
    assert exc.value.args == (SupvisorsFaults.NOT_MANAGED.value, 'appli_2')
    assert mocked_check.call_args_list == [call()]
    assert not mocked_start.called
    mocked_check.reset_mock()
    # test RPC call with running application
    application = rpc.supvisors.context.applications['appli_1']
    for appli_state in [ApplicationStates.STOPPING, ApplicationStates.RUNNING, ApplicationStates.STARTING]:
        application.state = appli_state
        with pytest.raises(RPCError) as exc:
            rpc.test_start_application(0, 'appli_1')
        assert exc.value.args == (Faults.ALREADY_STARTED, 'appli_1')
        assert mocked_check.call_args_list == [call()]
        assert not mocked_start.called
        mocked_check.reset_mock()
    # test RPC call with stopped application
    application.state = ApplicationStates.STOPPED
    assert rpc.test_start_application(0, 'appli_1') == expected
    assert mocked_check.call_args_list == [call()]
    assert mocked_start.call_args_list == [call(StartingStrategies.CONFIG, application)]


def test_stop_application(mocker, supvisors, rpc):
    """ Test the stop_application RPC. """
    mocked_check = mocker.patch('supvisors.rpcinterface.RPCInterface._check_operating_conciliation')
    # prepare context
    appli_1 = Mock(**{'rules.managed': True, 'has_running_processes.return_value': False})
    supvisors.context.applications = {'appli_1': appli_1, 'appli_2': Mock(**{'rules.managed': False})}
    # get patches
    mocked_stop = supvisors.stopper.stop_application
    mocked_progress = supvisors.stopper.in_progress
    # test RPC call with unknown application
    with pytest.raises(RPCError) as exc:
        rpc.stop_application('appli')
    assert exc.value.args == (Faults.BAD_NAME, 'application=appli unknown to Supvisors')
    assert mocked_check.call_args_list == [call()]
    assert not mocked_stop.called
    assert not mocked_progress.called
    mocked_check.reset_mock()
    # test RPC call with unmanaged application
    with pytest.raises(RPCError) as exc:
        rpc.stop_application('appli_2')
    assert exc.value.args == (SupvisorsFaults.NOT_MANAGED.value, 'appli_2')
    assert mocked_check.call_args_list == [call()]
    assert not mocked_stop.called
    assert not mocked_progress.called
    mocked_check.reset_mock()
    # test RPC call with stopped application
    application = supvisors.context.applications['appli_1']
    with pytest.raises(RPCError) as exc:
        rpc.stop_application('appli_1')
    assert exc.value.args == (Faults.NOT_RUNNING, 'failed to stop appli_1')
    assert mocked_check.call_args_list == [call()]
    assert not mocked_stop.called
    assert not mocked_progress.called
    mocked_check.reset_mock()
    # test RPC call with running application
    appli_1.has_running_processes.return_value = True
    # test no wait and done
    mocked_progress.return_value = False
    result = rpc.stop_application('appli_1', False)
    assert not result
    assert mocked_check.call_args_list == [call()]
    assert mocked_stop.call_args_list == [call(application)]
    assert mocked_progress.called
    mocked_check.reset_mock()
    mocked_stop.reset_mock()
    mocked_progress.reset_mock()
    # test wait and done
    result = rpc.stop_application('appli_1')
    assert not result
    assert mocked_check.call_args_list == [call()]
    assert mocked_stop.call_args_list == [call(application)]
    assert mocked_progress.called
    mocked_check.reset_mock()
    mocked_stop.reset_mock()
    mocked_progress.reset_mock()
    # test wait and not done
    mocked_progress.return_value = True
    result = rpc.stop_application('appli_1')
    # result is a function
    assert callable(result)
    assert mocked_check.call_args_list == [call()]
    assert mocked_stop.call_args_list == [call(application)]
    assert mocked_progress.called
    mocked_progress.reset_mock()
    # test returned function: return True when job in progress
    mocked_progress.return_value = True
    assert result() == NOT_DONE_YET
    assert mocked_progress.call_args_list == [call()]
    mocked_progress.reset_mock()
    # test returned function: raise exception if job not in progress anymore and application not running
    mocked_progress.return_value = False
    for _ in [ApplicationStates.STOPPING, ApplicationStates.RUNNING, ApplicationStates.STARTING]:
        with pytest.raises(RPCError) as exc:
            result()
        assert exc.value.args == (Faults.STILL_RUNNING, 'appli_1')
        assert mocked_progress.call_args_list == [call()]
        mocked_progress.reset_mock()
    # test returned function: return True if job not in progress anymore and application running
    application.state = ApplicationStates.STOPPED
    assert result()
    assert mocked_progress.call_args_list == [call()]


def test_restart_application_done(mocker, supvisors, rpc):
    """ Test the RPCInterface.restart_application RPC when no job has been queued. """
    mocked_check = mocker.patch('supvisors.rpcinterface.RPCInterface._check_operating')
    mocked_restart = mocker.patch.object(supvisors.stopper, 'restart_application')
    supvisors.starter.in_progress.return_value = False
    supvisors.stopper.in_progress.return_value = False
    application = Mock()
    mocker.patch.object(rpc, '_get_application', return_value=application)
    # wait parameter doesn't matter
    for wait in [True, False]:
        with pytest.raises(RPCError) as exc:
            rpc.restart_application(0, 'appli_1', wait)
        assert exc.value.args == (Faults.ABNORMAL_TERMINATION, 'failed to restart appli_1')
        assert mocked_check.call_args_list == [call()]
        assert mocked_restart.call_args_list == [call(StartingStrategies.CONFIG, application)]
        mocker.resetall()


def test_restart_application_no_wait(mocker, supvisors, rpc):
    """ Test the RPCInterface.restart_application RPC when jobs have been queued but result is not requested. """
    mocked_check = mocker.patch('supvisors.rpcinterface.RPCInterface._check_operating')
    mocked_restart = mocker.patch.object(supvisors.stopper, 'restart_application', return_value=False)
    application = Mock()
    mocker.patch.object(rpc, '_get_application', return_value=application)
    # test with application
    result = rpc.restart_application(0, 'appli_1', False)
    assert type(result) is bool
    assert result
    assert mocked_check.call_args_list == [call()]
    assert mocked_restart.call_args_list == [call(StartingStrategies.CONFIG, application)]


def test_restart_application_wait(mocker, supvisors, rpc):
    """ Test the RPCInterface.restart_application RPC when jobs have been queued and result is requested. """
    mocked_check = mocker.patch('supvisors.rpcinterface.RPCInterface._check_operating')
    mocked_restart = mocker.patch.object(supvisors.stopper, 'restart_application', return_value=False)
    application = Mock(**{'stopped.return_value': False})
    mocker.patch.object(rpc, '_get_application', return_value=application)
    # test with single process
    result = rpc.restart_application(0, 'appli_1', True)
    assert callable(result)
    assert mocked_check.call_args_list == [call()]
    assert mocked_restart.call_args_list == [call(StartingStrategies.CONFIG, application)]
    check_restart_deferred_function(mocker, rpc, application, result)


def test_start_args(mocker, supvisors, rpc):
    """ Test the start_args RPC. """
    mocker.patch.object(rpc, '_get_application_process', return_value=(None, Mock(namespec='appli:proc')))
    # prepare context
    supervisor_data = supvisors.supervisor_data
    mocked_extra = mocker.patch.object(supervisor_data, 'update_extra_args', side_effect=KeyError)
    mocked_force = mocker.patch.object(supervisor_data, 'force_process_fatal')
    mocked_start_process = supervisor_data.supervisor_rpc_interface.startProcess
    mocked_start_process.side_effect = [RPCError(Faults.NO_FILE, 'no file'),
                                        RPCError(Faults.NOT_EXECUTABLE),
                                        RPCError(Faults.ABNORMAL_TERMINATION),
                                        'done']
    # test RPC call with extra arguments but with a process that is unknown to Supervisor
    with pytest.raises(RPCError) as exc:
        rpc.start_args('appli:proc', 'dummy arguments')
    assert exc.value.args == (Faults.BAD_NAME, 'namespec=appli:proc unknown to Supervisor')
    assert supervisor_data.update_extra_args.call_args_list == [call('appli:proc', 'dummy arguments')]
    assert mocked_start_process.call_count == 0
    # update mocking
    mocked_extra.reset_mock()
    mocked_extra.side_effect = None
    # test RPC call with start exceptions
    # NO_FILE exception triggers an update of the process state
    with pytest.raises(RPCError) as exc:
        rpc.start_args('appli:proc', 'dummy arguments')
    assert exc.value.args == (Faults.NO_FILE, 'no file')
    assert mocked_extra.call_args_list == [call('appli:proc', 'dummy arguments')]
    assert mocked_start_process.call_args_list == [call('appli:proc', True)]
    assert mocked_force.call_args_list == [call('appli:proc', 'NO_FILE: no file')]
    # reset patches
    mocked_extra.reset_mock()
    mocked_force.reset_mock()
    mocked_start_process.reset_mock()
    # NOT_EXECUTABLE exception triggers an update of the process state
    with pytest.raises(RPCError) as exc:
        rpc.start_args('appli:proc', 'dummy arguments', wait=False)
    assert exc.value.args == (Faults.NOT_EXECUTABLE, )
    assert mocked_extra.call_args_list == [call('appli:proc', 'dummy arguments')]
    assert mocked_start_process.call_args_list == [call('appli:proc', False)]
    assert mocked_force.call_args_list == [call('appli:proc', 'NOT_EXECUTABLE')]
    # reset patches
    mocked_extra.reset_mock()
    mocked_force.reset_mock()
    mocked_start_process.reset_mock()
    # other exception doesn't trigger an update of the process state
    with pytest.raises(RPCError) as exc:
        rpc.start_args('appli:proc', 'dummy arguments', wait=False)
    assert exc.value.args == (Faults.ABNORMAL_TERMINATION, )
    assert mocked_extra.call_args_list == [call('appli:proc', 'dummy arguments')]
    assert mocked_start_process.call_args_list == [call('appli:proc', False)]
    assert not mocked_force.called
    # reset patches
    mocked_extra.reset_mock()
    mocked_start_process.reset_mock()
    # finally, normal behaviour
    assert rpc.start_args('appli:proc', 'dummy arguments') == 'done'
    assert mocked_extra.call_args_list == [call('appli:proc', 'dummy arguments')]
    assert mocked_start_process.call_args_list == [call('appli:proc', True)]
    assert not mocked_force.called


def test_start_process_unknown_strategy(mocker, supvisors, rpc):
    """ Test the start_process RPC using an unknown strategy. """
    mocked_check = mocker.patch('supvisors.rpcinterface.RPCInterface._check_operating')
    # get patches
    mocked_start = supvisors.starter.start_process
    mocked_progress = supvisors.starter.in_progress
    # patch the instance
    mocker.patch.object(rpc, '_get_application_process')
    # test RPC call with unknown strategy
    with pytest.raises(RPCError) as exc:
        rpc.start_process('strategy', 'appli:proc')
    assert exc.value.args[0] == Faults.INCORRECT_PARAMETERS
    assert mocked_check.call_args_list == [call()]
    assert not mocked_start.called
    assert not mocked_progress.called


def test_start_process_running_process(mocker, supvisors, rpc):
    """ Test the start_process RPC using a running process. """
    mocked_check = mocker.patch('supvisors.rpcinterface.RPCInterface._check_operating')
    # get patches
    mocked_start = supvisors.starter.start_process
    mocked_progress = supvisors.starter.in_progress
    # patch the instance
    mocked_get = mocker.patch.object(rpc, '_get_application_process')
    mocked_get.return_value = (None, Mock(namespec='proc1', **{'running.return_value': True}))
    # test RPC call with running process
    with pytest.raises(RPCError) as exc:
        rpc.start_process(0, 'appli_1')
    assert exc.value.args == (Faults.ALREADY_STARTED, 'proc1')
    assert mocked_check.call_args_list == [call()]
    assert not mocked_start.called
    assert not mocked_progress.called


def test_start_process_running_app_processes(mocker, supvisors, rpc):
    """ Test the start_process RPC using a group including at least one running process. """
    mocked_check = mocker.patch('supvisors.rpcinterface.RPCInterface._check_operating')
    # get patches
    mocked_start = supvisors.starter.start_process
    mocked_progress = supvisors.starter.in_progress
    # patch the instance
    proc_1 = Mock(namespec='proc1', **{'running.return_value': False})
    proc_2 = Mock(namespec='proc2', **{'running.return_value': True})
    mocked_get = mocker.patch.object(rpc, '_get_application_process')
    mocked_get.return_value = (Mock(**{'processes.values.return_value': [proc_1, proc_2]}), None)
    # test RPC call with running processes
    with pytest.raises(RPCError) as exc:
        rpc.start_process(0, 'appli_1:*')
    assert exc.value.args == (Faults.ALREADY_STARTED, 'proc2')
    assert mocked_check.call_args_list == [call()]
    assert not mocked_start.called
    assert not mocked_progress.called


def test_start_process_stopped_processes_progress_nowait(mocker, supvisors, rpc):
    """ Test the start_process RPC using stopped process / in progress and no wait. """
    mocked_check = mocker.patch('supvisors.rpcinterface.RPCInterface._check_operating')
    # get patches
    mocked_start = supvisors.starter.start_process
    mocked_progress = supvisors.starter.in_progress
    # patch the instance
    proc_1 = Mock(namespec='proc1', **{'running.return_value': False, 'stopped.return_value': True})
    proc_2 = Mock(namespec='proc2', **{'running.return_value': False, 'stopped.return_value': False})
    mocked_get = mocker.patch.object(rpc, '_get_application_process')
    mocked_get.return_value = (Mock(**{'processes.values.return_value': [proc_1, proc_2]}), None)
    # test RPC call with no wait and not done
    mocked_progress.return_value = True
    result = rpc.start_process(1, 'appli:*', 'argument list', False)
    assert result
    assert mocked_check.call_args_list == [call()]
    assert mocked_start.call_args_list == [call(StartingStrategies.LESS_LOADED, proc_1, 'argument list'),
                                           call(StartingStrategies.LESS_LOADED, proc_2, 'argument list')]
    assert mocked_progress.called


def test_start_process_stopped_processes_done_nowait(mocker, supvisors, rpc):
    """ Test the start_process RPC using stopped process / done and no wait. """
    mocked_check = mocker.patch('supvisors.rpcinterface.RPCInterface._check_operating')
    # get patches
    mocked_start = supvisors.starter.start_process
    mocked_progress = supvisors.starter.in_progress
    # patch the instance
    proc_1 = Mock(namespec='proc1', **{'running.return_value': False, 'stopped.return_value': True})
    proc_2 = Mock(namespec='proc2', **{'running.return_value': False, 'stopped.return_value': False})
    mocked_get = mocker.patch.object(rpc, '_get_application_process')
    mocked_get.return_value = (Mock(**{'processes.values.return_value': [proc_1, proc_2]}), None)
    # test RPC call no wait and done
    mocked_progress.return_value = False
    with pytest.raises(RPCError) as exc:
        rpc.start_process(1, 'appli:*', 'argument list', False)
    assert exc.value.args == (Faults.ABNORMAL_TERMINATION, 'failed to start appli:*')
    assert mocked_check.call_args_list == [call()]
    assert mocked_start.call_args_list == [call(StartingStrategies.LESS_LOADED, proc_1, 'argument list'),
                                           call(StartingStrategies.LESS_LOADED, proc_2, 'argument list')]
    assert mocked_progress.called


def test_start_process_stopped_processes_done_wait(mocker, supvisors, rpc):
    """ Test the start_process RPC using stopped process / done and wait. """
    mocked_check = mocker.patch('supvisors.rpcinterface.RPCInterface._check_operating')
    # get patches
    mocked_start = supvisors.starter.start_process
    mocked_progress = supvisors.starter.in_progress
    # patch the instance
    proc_1 = Mock(namespec='proc1', **{'running.return_value': False, 'stopped.return_value': True})
    proc_2 = Mock(namespec='proc2', **{'running.return_value': False, 'stopped.return_value': False})
    mocked_get = mocker.patch.object(rpc, '_get_application_process')
    mocked_get.return_value = (Mock(**{'processes.values.return_value': [proc_1, proc_2]}), None)
    # test RPC call with wait and done
    mocked_progress.return_value = False
    with pytest.raises(RPCError) as exc:
        rpc.start_process(2, 'appli:*', wait=True)
    assert exc.value.args == (Faults.ABNORMAL_TERMINATION, 'failed to start appli:*')
    assert mocked_check.call_args_list == [call()]
    assert mocked_start.call_args_list == [call(StartingStrategies.MOST_LOADED, proc_1, ''),
                                           call(StartingStrategies.MOST_LOADED, proc_2, '')]
    assert mocked_progress.called


def test_start_process_stopped_processes_progress_wait(mocker, supvisors, rpc):
    """ Test the start_process RPC using stopped process / done and wait. """
    mocked_check = mocker.patch('supvisors.rpcinterface.RPCInterface._check_operating')
    # get patches
    mocked_start = supvisors.starter.start_process
    mocked_progress = supvisors.starter.in_progress
    # patch the instance
    proc_1 = Mock(namespec='proc1', **{'running.return_value': False, 'stopped.return_value': True})
    proc_2 = Mock(namespec='proc2', **{'running.return_value': False, 'stopped.return_value': False})
    mocked_get = mocker.patch.object(rpc, '_get_application_process')
    mocked_get.return_value = (Mock(**{'processes.values.return_value': [proc_1, proc_2]}), None)
    # test RPC call with wait and not done
    mocked_progress.return_value = True
    deferred = rpc.start_process(2, 'appli:*', wait=True)
    # result is a function for deferred result
    assert callable(deferred)
    assert mocked_check.call_args_list == [call()]
    assert mocked_start.call_args_list == [call(StartingStrategies.MOST_LOADED, proc_1, ''),
                                           call(StartingStrategies.MOST_LOADED, proc_2, '')]
    assert mocked_progress.called
    mocked_progress.reset_mock()
    # test returned function: return True when job in progress
    mocked_progress.return_value = True
    assert deferred() == NOT_DONE_YET
    assert mocked_progress.call_args_list == [call()]
    mocked_progress.reset_mock()
    # test returned function: raise exception if job not in progress anymore and process still stopped
    mocked_progress.return_value = False
    with pytest.raises(RPCError) as exc:
        deferred()
    assert exc.value.args == (Faults.NOT_RUNNING, "processes=['proc1']")
    assert mocked_progress.call_args_list == [call()]
    mocked_progress.reset_mock()
    # test returned function: return True if job not in progress anymore and process running
    proc_1.stopped.return_value = False
    assert deferred()
    assert mocked_progress.call_args_list == [call()]


def test_test_start_process_unknown_strategy(mocker, supvisors, rpc):
    """ Test the test_start_process RPC using an unknown strategy. """
    mocked_check = mocker.patch('supvisors.rpcinterface.RPCInterface._check_operating')
    # get patches
    mocked_start = supvisors.starter_model.test_start_processes
    # patch the instance
    mocker.patch.object(rpc, '_get_application_process')
    # test RPC call with unknown strategy
    with pytest.raises(RPCError) as exc:
        rpc.test_start_process('strategy', 'appli:proc')
    assert exc.value.args[0] == Faults.INCORRECT_PARAMETERS
    assert mocked_check.call_args_list == [call()]
    assert not mocked_start.called


def test_test_start_process_running_process(mocker, supvisors, rpc):
    """ Test the test_start_process RPC using a running process. """
    mocked_check = mocker.patch('supvisors.rpcinterface.RPCInterface._check_operating')
    # get patches
    mocked_start = supvisors.starter_model.test_start_processes
    # patch the instance
    mocked_get = mocker.patch.object(rpc, '_get_application_process')
    mocked_get.return_value = (None, Mock(namespec='proc1', **{'running.return_value': True}))
    # test RPC call with running process
    with pytest.raises(RPCError) as exc:
        rpc.test_start_process(0, 'appli_1')
    assert exc.value.args == (Faults.ALREADY_STARTED, 'proc1')
    assert mocked_check.call_args_list == [call()]
    assert not mocked_start.called


def test_test_start_process_running_app_processes(mocker, supvisors, rpc):
    """ Test the start_process RPC using a group including at least one running process. """
    mocked_check = mocker.patch('supvisors.rpcinterface.RPCInterface._check_operating')
    # get patches
    mocked_start = supvisors.starter_model.test_start_processes
    # patch the instance
    proc_1 = Mock(namespec='proc1', **{'running.return_value': False})
    proc_2 = Mock(namespec='proc2', **{'running.return_value': True})
    mocked_get = mocker.patch.object(rpc, '_get_application_process')
    mocked_get.return_value = (Mock(**{'processes.values.return_value': [proc_1, proc_2]}), None)
    # test RPC call with running processes
    with pytest.raises(RPCError) as exc:
        rpc.test_start_process(0, 'appli_1:*')
    assert exc.value.args == (Faults.ALREADY_STARTED, 'proc2')
    assert mocked_check.call_args_list == [call()]
    assert not mocked_start.called


def test_test_start_process_stopped_app_processes(mocker, supvisors, rpc):
    """ Test the start_process RPC using stopped process / in progress and no wait. """
    mocked_check = mocker.patch('supvisors.rpcinterface.RPCInterface._check_operating')
    # get patches
    mocked_start = supvisors.starter_model.test_start_processes
    # patch the instance
    proc_1 = Mock(namespec='proc1', **{'running.return_value': False, 'stopped.return_value': True})
    proc_2 = Mock(namespec='proc2', **{'running.return_value': False, 'stopped.return_value': False})
    mocked_get = mocker.patch.object(rpc, '_get_application_process')
    mocked_get.return_value = (Mock(**{'processes.values.return_value': [proc_1, proc_2]}), None)
    # test RPC call with no wait and not done
    result = rpc.test_start_process(1, 'appli:*')
    assert result
    assert mocked_check.call_args_list == [call()]
    assert mocked_start.call_args_list == [call(StartingStrategies.LESS_LOADED, [proc_1, proc_2])]


def test_start_any_process_unknown_strategy(mocker, supvisors, rpc):
    """ Test the start_any_process RPC using an unknown strategy. """
    # get patches
    mocked_check = mocker.patch('supvisors.rpcinterface.RPCInterface._check_operating')
    mocked_find = mocker.patch.object(supvisors.context, 'find_runnable_processes')
    mocked_instance = mocker.patch('supvisors.rpcinterface.get_supvisors_instance')
    mocked_start = mocker.patch.object(rpc, 'start_process')
    # test RPC call with unknown strategy
    with pytest.raises(RPCError) as exc:
        rpc.start_any_process('strategy', ':x')
    assert exc.value.args[0] == Faults.INCORRECT_PARAMETERS
    assert mocked_check.call_args_list == [call()]
    assert not mocked_find.called
    assert not mocked_instance.called
    assert not mocked_start.called


def test_start_any_process_no_process(mocker, supvisors, rpc):
    """ Test the start_any_process RPC using a regex that doesn't match any process. """
    # get patches
    mocked_check = mocker.patch('supvisors.rpcinterface.RPCInterface._check_operating')
    mocked_find = mocker.patch.object(supvisors.context, 'find_runnable_processes', return_value=[])
    mocked_instance = mocker.patch('supvisors.rpcinterface.get_supvisors_instance')
    mocked_start = mocker.patch.object(rpc, 'start_process')
    # test RPC call with running process
    with pytest.raises(RPCError) as exc:
        rpc.start_any_process(0, ':x')
    assert exc.value.args == (Faults.FAILED, 'no candidate process matching ":x"')
    assert mocked_check.call_args_list == [call()]
    assert mocked_find.call_args_list == [call(':x')]
    assert not mocked_instance.called
    assert not mocked_start.called


def test_start_any_process_no_identifier(mocker, supvisors, rpc):
    """ Test the start_any_process RPC using a regex that matches processes but no rule. """
    # get patches
    mocked_check = mocker.patch('supvisors.rpcinterface.RPCInterface._check_operating')
    process_1 = Mock(**{'rules.expected_load': 10, 'possible_identifiers.return_value': ['10.0.0.1']})
    mocked_find = mocker.patch.object(supvisors.context, 'find_runnable_processes', return_value=[process_1])
    mocked_instance = mocker.patch('supvisors.rpcinterface.get_supvisors_instance', return_value=None)
    mocked_start = mocker.patch.object(rpc, 'start_process')
    supvisors.starter.get_load_requests.return_value = {}
    # test RPC call with running process
    with pytest.raises(RPCError) as exc:
        rpc.start_any_process(0, ':x')
    assert exc.value.args == (Faults.FAILED, 'no candidate process matching ":x"')
    assert mocked_check.call_args_list == [call()]
    assert mocked_find.call_args_list == [call(':x')]
    assert mocked_instance.call_args_list == [call(supvisors, StartingStrategies.CONFIG, ['10.0.0.1'], 10, {})]
    assert not mocked_start.called


def test_start_any_process_no_wait(mocker, supvisors, rpc):
    """ Test the start_any_process RPC using a regex that matches processes and rules / no wait. """
    # get patches
    mocked_check = mocker.patch('supvisors.rpcinterface.RPCInterface._check_operating')
    process_1 = Mock(namespec='process_1',
                     **{'rules.expected_load': 10, 'possible_identifiers.return_value': ['10.0.0.1']})
    mocked_find = mocker.patch.object(supvisors.context, 'find_runnable_processes', return_value=[process_1])
    mocked_instance = mocker.patch('supvisors.rpcinterface.get_supvisors_instance', return_value='10.0.0.1')
    mocked_start = mocker.patch.object(rpc, 'start_process', return_value=True)
    supvisors.starter.get_load_requests.return_value = {}
    # test RPC call with running process
    assert rpc.start_any_process(0, ':x', '-x 2', False) == 'process_1'
    assert mocked_check.call_args_list == [call()]
    assert mocked_find.call_args_list == [call(':x')]
    assert mocked_instance.call_args_list == [call(supvisors, StartingStrategies.CONFIG, ['10.0.0.1'], 10, {})]
    assert mocked_start.call_args_list == [call(0, 'process_1', '-x 2', False)]


def test_start_any_process_wait(mocker, supvisors, rpc):
    """ Test the start_any_process RPC using a regex that matches processes and rules / no wait. """
    # get patches
    mocked_check = mocker.patch('supvisors.rpcinterface.RPCInterface._check_operating')
    process_1 = Mock(namespec='process_1',
                     **{'rules.expected_load': 10, 'possible_identifiers.return_value': ['10.0.0.1']})
    mocked_find = mocker.patch.object(supvisors.context, 'find_runnable_processes', return_value=[process_1])
    mocked_instance = mocker.patch('supvisors.rpcinterface.get_supvisors_instance', return_value='10.0.0.1')
    start_job = Mock(**{'done.return_value': NOT_DONE_YET})
    mocked_start = mocker.patch.object(rpc, 'start_process', return_value=lambda: start_job.done())
    supvisors.starter.get_load_requests.return_value = {}
    # test RPC call with running process
    deferred = rpc.start_any_process(0, ':x', '-x 2', True)
    assert callable(deferred)
    assert mocked_check.call_args_list == [call()]
    assert mocked_find.call_args_list == [call(':x')]
    assert mocked_instance.call_args_list == [call(supvisors, StartingStrategies.CONFIG, ['10.0.0.1'], 10, {})]
    assert mocked_start.call_args_list == [call(0, 'process_1', '-x 2', True)]
    # test the deferred function
    assert deferred() is NOT_DONE_YET
    start_job.done.return_value = True
    assert deferred() == 'process_1'


def test_stop_process(mocker, rpc):
    """ Test the stop_process RPC. """
    mocked_check = mocker.patch('supvisors.rpcinterface.RPCInterface._check_operating_conciliation')
    # get patches
    mocked_stop = rpc.supvisors.stopper.stop_process
    mocked_next = rpc.supvisors.stopper.next
    mocked_progress = rpc.supvisors.stopper.in_progress
    # patch the instance
    rpc._get_application_process = Mock()
    # test RPC call with stopped processes
    proc_1 = Mock(namespec='proc1', **{'running.return_value': True, 'stopped.return_value': False})
    proc_2 = Mock(namespec='proc2', **{'running.return_value': False, 'stopped.return_value': False})
    rpc._get_application_process.return_value = (Mock(**{'processes.values.return_value': [proc_1, proc_2]}), None)
    # test RPC call with no wait and not done
    mocked_progress.return_value = True
    assert rpc.stop_process('appli:*', False)
    assert mocked_check.call_args_list == [call()]
    assert mocked_stop.call_args_list == [call(proc_1, trigger=False), call(proc_2, trigger=False)]
    assert mocked_next.called
    assert mocked_progress.called
    mocked_check.reset_mock()
    mocked_stop.reset_mock()
    mocked_next.reset_mock()
    mocked_progress.reset_mock()
    # test RPC call no wait and done
    mocked_progress.return_value = False
    with pytest.raises(RPCError) as exc:
        rpc.stop_process('appli:*')
    assert exc.value.args == (Faults.NOT_RUNNING, 'appli:* already stopped')
    assert mocked_check.call_args_list == [call()]
    assert mocked_stop.call_args_list == [call(proc_1, trigger=False), call(proc_2, trigger=False)]
    assert mocked_next.called
    assert mocked_progress.called
    mocked_check.reset_mock()
    mocked_stop.reset_mock()
    mocked_next.reset_mock()
    mocked_progress.reset_mock()
    # test RPC call with wait and done
    with pytest.raises(RPCError) as exc:
        rpc.stop_process('appli:*', wait=True)
    assert exc.value.args == (Faults.NOT_RUNNING, 'appli:* already stopped')
    assert mocked_check.call_args_list == [call()]
    assert mocked_stop.call_args_list == [call(proc_1, trigger=False), call(proc_2, trigger=False)]
    assert mocked_next.called
    assert mocked_progress.called
    mocked_check.reset_mock()
    mocked_stop.reset_mock()
    mocked_next.reset_mock()
    mocked_progress.reset_mock()
    # test RPC call with wait and not done
    mocked_progress.return_value = True
    deferred = rpc.stop_process('appli:*', wait=True)
    # result is a function for deferred result
    assert callable(deferred)
    assert mocked_check.call_args_list == [call()]
    assert mocked_stop.call_args_list == [call(proc_1, trigger=False), call(proc_2, trigger=False)]
    assert mocked_next.called
    assert mocked_progress.called
    mocked_progress.reset_mock()
    # test returned function: return True when job in progress
    assert deferred() == NOT_DONE_YET
    assert mocked_progress.call_args_list == [call()]
    mocked_progress.reset_mock()
    # test returned function: raise exception if job not in progress anymore and process still running
    mocked_progress.return_value = False
    with pytest.raises(RPCError) as exc:
        deferred()
    assert exc.value.args == (Faults.STILL_RUNNING, "processes=['proc1']")
    assert mocked_progress.call_args_list == [call()]
    mocked_progress.reset_mock()
    # test returned function: return True if job not in progress anymore and process stopped
    proc_1.running.return_value = False
    assert deferred()
    assert mocked_progress.call_args_list == [call()]


def test_restart_process_done(mocker, rpc):
    """ Test the restart_process RPC when no job has been queued. """
    mocked_check = mocker.patch('supvisors.rpcinterface.RPCInterface._check_operating')
    mocked_restart = mocker.patch.object(rpc.supvisors.stopper, 'restart_process')
    rpc.supvisors.starter.in_progress.return_value = False
    rpc.supvisors.stopper.in_progress.return_value = False
    mocked_get = mocker.patch.object(rpc, '_get_application_process')
    process_1 = Mock(namespec='proc1')
    process_2 = Mock(namespec='proc2')
    application = Mock(processes={'proc1': process_1, 'proc2': process_2})
    # wait parameter doesn't matter
    for wait in [True, False]:
        # test with single process
        mocked_get.return_value = (None, process_1)
        with pytest.raises(RPCError) as exc:
            rpc.restart_process(0, 'proc1', 'arg list', wait)
        assert exc.value.args == (Faults.ABNORMAL_TERMINATION, 'failed to restart proc1')
        assert mocked_restart.call_args_list == [call(StartingStrategies.CONFIG, process_1, 'arg list')]
        assert mocked_check.call_args_list == [call()]
        mocker.resetall()
        # test with application
        mocked_get.return_value = (application, None)
        with pytest.raises(RPCError) as exc:
            rpc.restart_process(0, 'proc1', 'arg list', wait)
        assert exc.value.args == (Faults.ABNORMAL_TERMINATION, 'failed to restart proc1')
        assert mocked_check.call_args_list == [call()]
        assert mocked_restart.call_args_list == [call(StartingStrategies.CONFIG, process_1, 'arg list'),
                                                 call(StartingStrategies.CONFIG, process_2, 'arg list')]
        mocker.resetall()


def test_restart_process_no_wait(mocker, rpc):
    """ Test the restart_process RPC when jobs have been queued but result is not requested. """
    mocked_check = mocker.patch('supvisors.rpcinterface.RPCInterface._check_operating')
    mocked_restart = mocker.patch.object(rpc.supvisors.stopper, 'restart_process', return_value=False)
    mocked_get = mocker.patch.object(rpc, '_get_application_process')
    process_1 = Mock(namespec='proc1')
    process_2 = Mock(namespec='proc2')
    application = Mock(processes={'proc1': process_1, 'proc2': process_2})
    # test with single process
    mocked_get.return_value = (None, process_1)
    result = rpc.restart_process(0, 'proc1', 'arg list', False)
    assert type(result) is bool
    assert result
    assert mocked_check.call_args_list == [call()]
    assert mocked_restart.call_args_list == [call(StartingStrategies.CONFIG, process_1, 'arg list')]
    mocker.resetall()
    # test with application
    mocked_get.return_value = (application, None)
    result = rpc.restart_process(0, 'proc1', 'arg list', False)
    assert type(result) is bool
    assert result
    assert mocked_check.call_args_list == [call()]
    assert mocked_restart.call_args_list == [call(StartingStrategies.CONFIG, process_1, 'arg list'),
                                             call(StartingStrategies.CONFIG, process_2, 'arg list')]


def check_restart_deferred_function(mocker, rpc, app_proc, deferred):
    """ Check the deferred function provided by the restart_process or the restart_application RPC. """
    mocked_start_progress = mocker.patch.object(rpc.supvisors.starter, 'in_progress')
    mocked_stop_progress = mocker.patch.object(rpc.supvisors.stopper, 'in_progress')
    # in normal case, Stopper is first working, then Starter
    mocked_start_progress.return_value = False
    mocked_stop_progress.return_value = True
    assert deferred.waitstop
    # 1st call: Stopper working
    assert deferred() is NOT_DONE_YET
    assert deferred.waitstop
    assert mocked_stop_progress.called
    assert not mocked_start_progress.called
    mocked_stop_progress.reset_mock()
    # 2nd call: Stopper completed / Starter working
    mocked_start_progress.return_value = True
    mocked_stop_progress.return_value = False
    assert deferred() is NOT_DONE_YET
    assert not deferred.waitstop
    assert mocked_stop_progress.called
    assert not mocked_start_progress.called
    mocked_stop_progress.reset_mock()
    # 3rd call: Starter still working
    assert deferred() is NOT_DONE_YET
    assert not deferred.waitstop
    assert not mocked_stop_progress.called
    assert mocked_start_progress.called
    mocked_start_progress.reset_mock()
    # 4th call: Starter completed. results are evaluated
    mocked_start_progress.return_value = False
    # normal case, application or all processes are running
    assert deferred()
    assert not deferred.waitstop
    assert not mocked_stop_progress.called
    assert mocked_start_progress.called
    mocked_start_progress.reset_mock()
    # error case, one process is still stopped
    # process in parameter is used in both test cases (single process and application)
    app_proc.stopped.return_value = True
    with pytest.raises(RPCError) as exc:
        assert deferred()
    assert exc.value.args[0] == Faults.NOT_RUNNING
    assert not deferred.waitstop
    assert not mocked_stop_progress.called
    assert mocked_start_progress.called
    # reset stopped for next test case
    app_proc.stopped.return_value = False


def test_restart_process_wait(mocker, rpc):
    """ Test the restart_process RPC when jobs have been queued and result is requested. """
    mocked_check = mocker.patch('supvisors.rpcinterface.RPCInterface._check_operating')
    mocked_restart = mocker.patch.object(rpc.supvisors.stopper, 'restart_process')
    rpc.supvisors.starter.in_progress.return_value = True
    rpc.supvisors.stopper.in_progress.return_value = False
    mocked_get = mocker.patch.object(rpc, '_get_application_process')
    process_1 = Mock(namespec='proc1', **{'stopped.return_value': False})
    process_2 = Mock(namespec='proc2', **{'stopped.return_value': False})
    application = Mock(processes={'proc1': process_1, 'proc2': process_2})
    # test with single process
    mocked_get.return_value = (None, process_1)
    result = rpc.restart_process(0, 'proc1', 'arg list', True)
    assert callable(result)
    assert mocked_check.call_args_list == [call()]
    assert mocked_restart.call_args_list == [call(StartingStrategies.CONFIG, process_1, 'arg list')]
    check_restart_deferred_function(mocker, rpc, process_1, result)
    mocker.resetall()
    # test with application
    rpc.supvisors.starter.in_progress.return_value = False
    rpc.supvisors.stopper.in_progress.return_value = True
    mocked_get.return_value = (application, None)
    result = rpc.restart_process(0, 'proc1', 'arg list', True)
    assert callable(result)
    assert mocked_check.call_args_list == [call()]
    assert mocked_restart.call_args_list == [call(StartingStrategies.CONFIG, process_1, 'arg list'),
                                             call(StartingStrategies.CONFIG, process_2, 'arg list')]
    check_restart_deferred_function(mocker, rpc, process_1, result)


def test_update_numprocs_unknown_program(mocker, rpc):
    """ Test the update_numprocs RPC with unknown program. """
    # get patches
    mocked_check = mocker.patch.object(rpc, '_check_operating')
    mocked_numprocs = mocker.patch.object(rpc.supvisors.supervisor_updater, 'update_numprocs')
    mocked_insert = mocker.patch.object(rpc, '_check_process_insertion')
    mocked_decrease = mocker.patch.object(rpc, '_decrease_numprocs')
    # test RPC call with unknown program
    rpc.supvisors.server_options.program_processes = {}
    with pytest.raises(RPCError) as exc:
        rpc.update_numprocs('dummy_program', 1)
    assert exc.value.args == (Faults.BAD_NAME, 'program=dummy_program unknown to Supvisors')
    assert mocked_check.call_args_list == [call()]
    assert not mocked_numprocs.called
    assert not mocked_insert.called
    assert not mocked_decrease.called


def test_update_numprocs_invalid_numprocs(mocker, rpc):
    """ Test the update_numprocs RPC with known program and invalid numprocs. """
    # get patches
    mocked_check = mocker.patch.object(rpc, '_check_operating')
    mocked_numprocs = mocker.patch.object(rpc.supvisors.supervisor_updater, 'update_numprocs')
    mocked_insert = mocker.patch.object(rpc, '_check_process_insertion')
    mocked_decrease = mocker.patch.object(rpc, '_decrease_numprocs')
    # test RPC call with known program and invalid numprocs value (not integer)
    rpc.supvisors.server_options.program_configs = {'dummy_program': {}}
    with pytest.raises(RPCError) as exc:
        rpc.update_numprocs('dummy_program', 'one', False, False)
    assert exc.value.args == (Faults.INCORRECT_PARAMETERS,
                              'program=dummy_program incorrect numprocs=one - integer > 0 expected')
    assert mocked_check.call_args_list == [call()]
    assert not mocked_numprocs.called
    assert not mocked_insert.called
    assert not mocked_decrease.called


def test_update_numprocs_incorrect_numprocs(mocker, rpc):
    """ Test the update_numprocs RPC with known program and incorrect numprocs. """
    # get patches
    mocked_check = mocker.patch.object(rpc, '_check_operating')
    mocked_numprocs = mocker.patch.object(rpc.supvisors.supervisor_updater, 'update_numprocs')
    mocked_insert = mocker.patch.object(rpc, '_check_process_insertion')
    mocked_decrease = mocker.patch.object(rpc, '_decrease_numprocs')
    # test RPC call with known program and invalid numprocs value (not integer)
    rpc.supvisors.server_options.program_configs = {'dummy_program': {}}
    with pytest.raises(RPCError) as exc:
        rpc.update_numprocs('dummy_program', 0, False, False)
    assert exc.value.args == (Faults.INCORRECT_PARAMETERS,
                              'program=dummy_program incorrect numprocs=0 - integer > 0 expected')
    assert mocked_check.call_args_list == [call()]
    assert not mocked_numprocs.called
    assert not mocked_insert.called
    assert not mocked_decrease.called


def test_update_numprocs_wrong_config(mocker, rpc):
    """ Test the update_numprocs RPC with known program and correct numprocs and wrong program configuration. """
    # get patches
    mocked_check = mocker.patch.object(rpc, '_check_operating')
    mocked_numprocs = mocker.patch.object(rpc.supvisors.supervisor_updater, 'update_numprocs')
    mocked_insert = mocker.patch.object(rpc, '_check_process_insertion')
    mocked_decrease = mocker.patch.object(rpc, '_decrease_numprocs')
    # test RPC call with known program, correct numprocs value and wrong program configuration
    rpc.supvisors.server_options.program_configs = {'dummy_program': {}}
    mocked_numprocs.side_effect = ValueError('program_num missing in process_name')
    with pytest.raises(RPCError) as exc:
        rpc.update_numprocs('dummy_program', 2, False, False)
    assert exc.value.args == (SupvisorsFaults.NOT_APPLICABLE.value,
                              'numprocs not applicable to program=dummy_program')
    assert mocked_check.call_args_list == [call()]
    assert mocked_numprocs.call_args_list == [call('dummy_program', 2)]
    assert not mocked_insert.called
    assert not mocked_decrease.called


def test_update_numprocs_unchanged(mocker, rpc):
    """ Test the update_numprocs RPC, with equal number of processes. """
    # get patches
    mocked_check = mocker.patch.object(rpc, '_check_operating')
    mocked_numprocs = mocker.patch.object(rpc.supvisors.supervisor_updater, 'update_numprocs')
    mocked_insert = mocker.patch.object(rpc, '_check_process_insertion')
    mocked_decrease = mocker.patch.object(rpc, '_decrease_numprocs')
    # test RPC call with known program, correct numprocs value and numprocs increase (nothing to stop)
    rpc.supvisors.server_options.program_configs = {'dummy_program': {}}
    mocked_numprocs.return_value = [], []
    assert rpc.update_numprocs('dummy_program', 2, False, False) is True
    assert mocked_check.call_args_list == [call()]
    assert mocked_numprocs.call_args_list == [call('dummy_program', 2)]
    assert not mocked_insert.called
    assert not mocked_decrease.called


def test_update_numprocs_increase(mocker, rpc):
    """ Test the update_numprocs RPC, increasing the number of processes. """
    # get patches
    mocked_check = mocker.patch.object(rpc, '_check_operating')
    mocked_numprocs = mocker.patch.object(rpc.supvisors.supervisor_updater, 'update_numprocs')
    increase_mock = Mock()
    mocked_insert = mocker.patch.object(rpc, '_check_process_insertion', return_value=increase_mock)
    mocked_decrease = mocker.patch.object(rpc, '_decrease_numprocs')
    # test RPC call with known program, correct numprocs value and numprocs increase (nothing to stop)
    rpc.supvisors.server_options.program_configs = {'dummy_program': {}}
    mocked_numprocs.return_value = ['dummy_program_01', 'dummy_program_02'], None
    assert rpc.update_numprocs('dummy_program', 2, False, False)
    assert mocked_check.call_args_list == [call()]
    assert mocked_numprocs.call_args_list == [call('dummy_program', 2)]
    assert mocked_insert.call_args_list == [call(['dummy_program_01', 'dummy_program_02'])]
    assert not mocked_decrease.called


def test_update_numprocs_decrease(mocker, rpc):
    """ Test the update_numprocs RPC, decreasing the number of processes. """
    # get patches
    mocked_check = mocker.patch.object(rpc, '_check_operating')
    mocked_numprocs = mocker.patch.object(rpc.supvisors.supervisor_updater, 'update_numprocs')
    decrease_mock = Mock()
    mocked_increase = mocker.patch.object(rpc, '_check_process_insertion')
    mocked_decrease = mocker.patch.object(rpc, '_decrease_numprocs', return_value=decrease_mock)
    # test RPC call with known program, correct numprocs value and numprocs decrease
    rpc.supvisors.server_options.program_configs = {'dummy_program': {}}
    mocked_numprocs.return_value = None, ['dummy_program_01', 'dummy_program_02']
    assert rpc.update_numprocs('dummy_program', 2, True, False) is decrease_mock
    assert mocked_check.call_args_list == [call()]
    assert mocked_numprocs.call_args_list == [call('dummy_program', 2)]
    assert not mocked_increase.called
    assert mocked_decrease.call_args_list == [call(['dummy_program_01', 'dummy_program_02'], True)]


def test_update_numprocs_decrease_lazy(mocker, rpc):
    """ Test the update_numprocs RPC, decreasing the number of processes. """
    # get patches
    mocked_check = mocker.patch.object(rpc, '_check_operating')
    mocked_numprocs = mocker.patch.object(rpc.supvisors.supervisor_updater, 'update_numprocs')
    mocked_increase = mocker.patch.object(rpc, '_check_process_insertion')
    mocked_decrease = mocker.patch.object(rpc, '_decrease_numprocs')
    # test RPC call with known program, correct numprocs value and numprocs decrease
    rpc.supvisors.server_options.program_configs = {'dummy_program': {}}
    mocked_numprocs.return_value = None, ['dummy_program_01', 'dummy_program_02']
    assert rpc.update_numprocs('dummy_program', 2, True, True)
    assert mocked_check.call_args_list == [call()]
    assert mocked_numprocs.call_args_list == [call('dummy_program', 2)]
    assert not mocked_increase.called
    assert not mocked_decrease.called


def test_decrease_numprocs_no_stop(mocker, supvisors, rpc):
    """ Test the RPCInterface._decrease_numprocs method.
    This test case deals with a context where the processes to remove are already stopped. """
    # get patches
    mocked_check = mocker.patch.object(rpc, '_check_process_deletion')
    mocked_stop = supvisors.stopper.stop_process
    mocked_next = supvisors.stopper.next
    mocked_progress = supvisors.stopper.in_progress
    local_identifier = supvisors.mapper.local_identifier
    process_1 = Mock(namespec='process_1', info_map={local_identifier: {}}, **{'running_on.return_value': False})
    process_2 = Mock(namespec='process_2', info_map={local_identifier: {}}, **{'running_on.return_value': False})
    process_3 = Mock(namespec='process_3', info_map={local_identifier: {}}, **{'running_on.return_value': False})
    get_map = {'process_1': process_1, 'process_2': process_2, 'process_3': process_3}
    mocker.patch.object(supvisors.context, 'get_process', side_effect=lambda x: get_map[x])
    mocked_progress.return_value = False
    # 1. test RPC call with known program, correct numprocs value and numprocs decrease (no process to stop) / no wait
    params = ['process_1', 'process_2', 'process_3']
    assert rpc._decrease_numprocs(params, False)
    assert mocked_check.call_args_list == [call(params)]
    assert not mocked_stop.called
    assert mocked_next.called
    assert not mocked_progress.called
    mocked_check.reset_mock()
    mocked_next.reset_mock()
    # 2. test RPC call with known program, correct numprocs value and numprocs decrease (no process to stop) / wait
    deferred = rpc._decrease_numprocs(params, True)
    assert callable(deferred)
    assert not mocked_check.called
    assert not mocked_stop.called
    assert mocked_next.called
    assert not mocked_progress.called
    # test deferred function: pending job if wait
    assert deferred()
    assert mocked_check.called


def test_decrease_numprocs_stop(mocker, supvisors, rpc):
    """ Test the RPCInterface._decrease_numprocs method.
    This test case deals with a context where the processes to remove have to be stopped. """
    # get patches
    mocked_check = mocker.patch.object(rpc, '_check_process_deletion')
    mocked_stop = supvisors.stopper.stop_process
    mocked_next = supvisors.stopper.next
    mocked_progress = supvisors.stopper.in_progress
    local_identifier = supvisors.mapper.local_identifier
    process_1 = Mock(namespec='process_1', info_map={local_identifier: {}}, **{'running_on.return_value': True})
    process_2 = Mock(namespec='process_2', info_map={local_identifier: {}}, **{'running_on.return_value': True})
    process_3 = Mock(namespec='process_3', info_map={local_identifier: {}}, **{'running_on.return_value': False})
    get_map = {'process_1': process_1, 'process_2': process_2, 'process_3': process_3}
    mocker.patch.object(supvisors.context, 'get_process', side_effect=lambda x: get_map[x])
    mocked_progress.return_value = True
    # test RPC call with known program, correct numprocs value and numprocs decrease (one process to stop) / wait
    params = ['process_1', 'process_2', 'process_3']
    deferred = rpc._decrease_numprocs(params, True)
    assert callable(deferred)
    assert not mocked_check.called
    assert mocked_stop.call_args_list == [call(process_1, [local_identifier], False),
                                          call(process_2, [local_identifier], False)]
    assert mocked_next.called
    # test deferred function: still in progress
    assert deferred() is NOT_DONE_YET
    assert not mocked_check.called
    # test deferred function: exception as one process running
    process_2.running.return_value = False
    mocked_progress.return_value = False
    with pytest.raises(RPCError) as exc:
        deferred()
    assert exc.value.args == (Faults.STILL_RUNNING, "processes=['process_1']")
    assert not mocked_check.called
    # test deferred function: end of job
    process_1.running.return_value = False
    process_2.running.return_value = False
    assert deferred() is True
    assert not mocked_check.call_args_list == [call(['process_2', 'process_3'])]


def test_check_process_insertion(mocker, supvisors, rpc):
    """ Test the RPCInterface._check_process_insertion method. """
    # get patches
    local_identifier = supvisors.mapper.local_identifier
    process_1 = Mock(namespec='process_1', info_map={})
    process_2 = Mock(namespec='process_2', info_map={})
    get_map = {'process_1': process_1, 'process_2': process_2}
    mocker.patch.object(supvisors.context, 'get_process', side_effect=lambda x: get_map[x])
    # test with processes not added yet
    params = ['process_1', 'process_2']
    with pytest.raises(RPCError) as exc:
        rpc._check_process_insertion(params)
    assert exc.value.args == (Faults.FAILED, "processes=['process_1', 'process_2']")
    # test partial addition
    process_1.info_map[local_identifier] = {}
    with pytest.raises(RPCError) as exc:
        rpc._check_process_insertion(params)
    assert exc.value.args == (Faults.FAILED, "processes=['process_2']")
    # test complete addition
    process_2.info_map[local_identifier] = {}
    rpc._check_process_insertion(params)


def test_check_process_deletion(mocker, supvisors, rpc):
    """ Test the RPCInterface._check_process_deletion method. """
    # get patches
    local_identifier = supvisors.mapper.local_identifier
    process_1 = Mock(namespec='process_1', info_map={local_identifier: {}})
    process_2 = Mock(namespec='process_2', info_map={local_identifier: {}})
    get_map = {'process_1': process_1, 'process_2': process_2}
    mocket_get = mocker.patch.object(supvisors.context, 'get_process', side_effect=lambda x: get_map[x])
    # test with processes not removed yet
    params = ['process_1', 'process_2']
    with pytest.raises(RPCError) as exc:
        rpc._check_process_deletion(params)
    assert exc.value.args == (Faults.FAILED, "processes=['process_1', 'process_2']")
    # test partial removal
    process_1.info_map = {}
    with pytest.raises(RPCError) as exc:
        rpc._check_process_deletion(params)
    assert exc.value.args == (Faults.FAILED, "processes=['process_2']")
    # test complete removal
    process_2.info_map = {}
    rpc._check_process_deletion(params)
    # test process deletion
    mocket_get.side_effect = KeyError
    rpc._check_process_deletion(params)


def test_enable_unknown_program(mocker, supvisors, rpc):
    """ Test the enable RPC with unknown program. """
    # get patches
    mocked_check = mocker.patch.object(rpc, '_check_operating')
    mocked_enable = mocker.patch.object(supvisors.supervisor_updater, 'enable_program')
    # test RPC call with unknown program
    supvisors.server_options.program_configs = {}
    with pytest.raises(RPCError) as exc:
        rpc.enable('dummy_program')
    assert exc.value.args == (Faults.BAD_NAME, 'program=dummy_program unknown to Supvisors')
    assert mocked_check.call_args_list == [call()]
    assert not mocked_enable.called


def test_enable_no_wait(mocker, supvisors, rpc):
    """ Test the enable RPC / no wait. """
    # get patches
    mocked_check = mocker.patch.object(rpc, '_check_operating')
    mocked_enable = mocker.patch.object(supvisors.supervisor_updater, 'enable_program')
    # test RPC call with unknown program
    supvisors.server_options.program_configs = {'dummy_program': {}}
    assert rpc.enable('dummy_program', False) is True
    assert mocked_check.call_args_list == [call()]
    assert mocked_enable.call_args_list == [call('dummy_program')]


def test_enable_wait(mocker, rpc):
    """ Test the enable RPC / wait for result. """
    # get patches
    mocked_check = mocker.patch.object(rpc, '_check_operating')
    mocked_get = mocker.patch.object(rpc, '_get_application_process')
    mocked_enable = mocker.patch.object(rpc.supvisors.supervisor_updater, 'enable_program')
    mocked_getsub = mocker.patch.object(rpc.supvisors.server_options, 'get_subprocesses',)
    # patch the context
    mocked_getsub.return_value = ['process_1', 'process_2', 'process_3']
    process_1 = Mock(namespec='process_1', **{'disabled_on.return_value': True})
    process_2 = Mock(namespec='process_2', **{'disabled_on.return_value': True})
    process_3 = Mock(namespec='process_3', **{'disabled_on.return_value': True})
    get_map = {'process_1': process_1, 'process_2': process_2, 'process_3': process_3}
    mocked_get.side_effect = lambda x: (None, get_map[x])
    # test RPC call with unknown program
    rpc.supvisors.server_options.program_configs = {'dummy_program': {}}
    deferred = rpc.enable('dummy_program')
    assert callable(deferred)
    assert mocked_check.call_args_list == [call()]
    assert mocked_enable.call_args_list == [call('dummy_program')]
    # test deferred function: still in progress
    assert deferred() is NOT_DONE_YET
    # test deferred function: wait for processes to be disabled
    process_1.disabled_on.return_value = False
    process_2.disabled_on.return_value = False
    process_3.disabled_on.return_value = False
    assert deferred() is True


def test_disable_unknown_program(mocker, rpc):
    """ Test the disable RPC with unknown program. """
    # get patches
    mocked_check = mocker.patch.object(rpc, '_check_operating')
    mocked_disable = mocker.patch.object(rpc.supvisors.supervisor_updater, 'disable_program')
    mocked_get = mocker.patch.object(rpc.supvisors.server_options, 'get_subprocesses')
    # test RPC call with unknown program
    rpc.supvisors.server_options.program_configs = {}
    with pytest.raises(RPCError) as exc:
        rpc.disable('dummy_program')
    assert exc.value.args == (Faults.BAD_NAME, 'program=dummy_program unknown to Supvisors')
    assert mocked_check.call_args_list == [call()]
    assert not mocked_disable.called
    assert not mocked_get.called


def test_disable_no_stop(mocker, rpc):
    """ Test the disable RPC.
    This test case deals with a context where the processes to disable are already stopped. """
    mocked_check = mocker.patch.object(rpc, '_check_operating')
    mocked_get = mocker.patch.object(rpc, '_get_application_process')
    mocked_disable = mocker.patch.object(rpc.supvisors.supervisor_updater, 'disable_program')
    mocked_getsub = mocker.patch.object(rpc.supvisors.server_options, 'get_subprocesses')
    mocked_stop = rpc.supvisors.stopper.stop_process
    mocked_next = rpc.supvisors.stopper.next
    mocked_progress = rpc.supvisors.stopper.in_progress
    # patch the context
    mocked_getsub.return_value = ['process_1', 'process_2', 'process_3']
    process_1 = Mock(namespec='process_1', **{'running_on.return_value': True})
    process_2 = Mock(namespec='process_2', **{'running_on.return_value': True})
    process_3 = Mock(namespec='process_3', **{'running_on.return_value': False})
    get_map = {'process_1': process_1, 'process_2': process_2, 'process_3': process_3}
    mocked_get.side_effect = lambda x: (None, get_map[x])
    mocked_progress.return_value = True
    # test RPC call with known program
    local_identifier = rpc.supvisors.mapper.local_identifier
    rpc.supvisors.server_options.program_configs = {'dummy_program': {}}
    assert rpc.disable('dummy_program')
    assert mocked_check.call_args_list == [call()]
    assert mocked_disable.call_args_list == [call('dummy_program')]
    assert mocked_getsub.call_args_list == [call('dummy_program')]
    assert mocked_get.call_args_list == [call('process_1'), call('process_2'), call('process_3')]
    assert mocked_stop.call_args_list == [call(process_1, [local_identifier], False),
                                          call(process_2, [local_identifier], False)]
    assert mocked_next.called
    assert not mocked_progress.called


def test_disable_stop_no_wait(mocker, rpc):
    """ Test the disable RPC.
    This test case deals with a context where the processes to disable have to be stopped. """
    mocked_check = mocker.patch.object(rpc, '_check_operating')
    mocked_get = mocker.patch.object(rpc, '_get_application_process')
    mocked_disable = mocker.patch.object(rpc.supvisors.supervisor_updater, 'disable_program')
    mocked_getsub = mocker.patch.object(rpc.supvisors.server_options, 'get_subprocesses')
    mocked_stop = rpc.supvisors.stopper.stop_process
    mocked_next = rpc.supvisors.stopper.next
    mocked_progress = rpc.supvisors.stopper.in_progress
    # patch the context
    mocked_getsub.return_value = ['process_1', 'process_2', 'process_3']
    process_1 = Mock(namespec='process_1', **{'running_on.return_value': True})
    process_2 = Mock(namespec='process_2', **{'running_on.return_value': True})
    process_3 = Mock(namespec='process_3', **{'running_on.return_value': False})
    get_map = {'process_1': process_1, 'process_2': process_2, 'process_3': process_3}
    mocked_get.side_effect = lambda x: (None, get_map[x])
    mocked_progress.return_value = True
    # test RPC call with known program
    local_identifier = rpc.supvisors.mapper.local_identifier
    rpc.supvisors.server_options.program_configs = {'dummy_program': {}}
    assert rpc.disable('dummy_program', False) is True
    assert mocked_check.call_args_list == [call()]
    assert mocked_disable.call_args_list == [call('dummy_program')]
    assert mocked_getsub.call_args_list == [call('dummy_program')]
    assert mocked_get.call_args_list == [call('process_1'), call('process_2'), call('process_3')]
    assert mocked_stop.call_args_list == [call(process_1, [local_identifier], False),
                                          call(process_2, [local_identifier], False)]
    assert mocked_next.called
    assert not mocked_progress.called


def test_disable_stop_wait(mocker, rpc):
    """ Test the disable RPC.
    This test case deals with a context where the processes to disable have to be stopped. """
    mocked_check = mocker.patch.object(rpc, '_check_operating')
    mocked_get = mocker.patch.object(rpc, '_get_application_process')
    mocked_disable = mocker.patch.object(rpc.supvisors.supervisor_updater, 'disable_program')
    mocked_getsub = mocker.patch.object(rpc.supvisors.server_options, 'get_subprocesses')
    mocked_stop = rpc.supvisors.stopper.stop_process
    mocked_next = rpc.supvisors.stopper.next
    mocked_progress = rpc.supvisors.stopper.in_progress
    # patch the context
    mocked_getsub.return_value = ['process_1', 'process_2', 'process_3']
    process_1 = Mock(namespec='process_1', **{'disabled_on.return_value': False, 'running_on.return_value': True})
    process_2 = Mock(namespec='process_2', **{'disabled_on.return_value': False, 'running_on.return_value': True})
    process_3 = Mock(namespec='process_3', **{'disabled_on.return_value': False, 'running_on.return_value': False})
    get_map = {'process_1': process_1, 'process_2': process_2, 'process_3': process_3}
    mocked_get.side_effect = lambda x: (None, get_map[x])
    mocked_progress.return_value = True
    # test RPC call with known program
    local_identifier = rpc.supvisors.mapper.local_identifier
    rpc.supvisors.server_options.program_configs = {'dummy_program': {}}
    deferred = rpc.disable('dummy_program', True)
    assert callable(deferred)
    assert mocked_check.call_args_list == [call()]
    assert mocked_disable.call_args_list == [call('dummy_program')]
    assert mocked_getsub.call_args_list == [call('dummy_program')]
    assert mocked_get.call_args_list == [call('process_1'), call('process_2'), call('process_3')]
    assert mocked_stop.call_args_list == [call(process_1, [local_identifier], False),
                                          call(process_2, [local_identifier], False)]
    assert mocked_next.called
    assert not mocked_progress.called
    # test deferred function: still in progress
    mocked_progress.return_value = True
    assert deferred() is NOT_DONE_YET
    # test deferred function: exception as process running
    mocked_progress.return_value = False
    with pytest.raises(RPCError) as exc:
        deferred()
    assert exc.value.args == (Faults.STILL_RUNNING, "processes=['process_1', 'process_2']")
    # test deferred function: end of job
    process_1.running.return_value = False
    process_2.running.return_value = False
    assert deferred() is NOT_DONE_YET
    # test deferred function: wait for processes to be disabled
    process_1.disabled_on.return_value = True
    process_2.disabled_on.return_value = True
    process_3.disabled_on.return_value = True
    assert deferred() is True


def test_conciliate(mocker, rpc):
    """ Test the conciliate RPC. """
    # set context and patches
    mocked_check = mocker.patch('supvisors.rpcinterface.RPCInterface._check_conciliation')
    mocker.patch.object(rpc.supvisors.context, 'conflicts', return_value=[1, 2, 4])
    rpc.supvisors.fsm.state = SupvisorsStates.CONCILIATION
    mocked_conciliate = mocker.patch('supvisors.rpcinterface.conciliate_conflicts')
    # test RPC call with wrong strategy
    with pytest.raises(RPCError) as exc:
        assert rpc.conciliate('a strategy')
    assert mocked_check.call_args_list == [call()]
    assert exc.value.args[0] == Faults.INCORRECT_PARAMETERS
    mocked_check.reset_mock()
    # test RPC call with USER strategy
    assert not rpc.conciliate(ConciliationStrategies.USER.value)
    assert mocked_check.call_args_list == [call()]
    assert not mocked_conciliate.called
    mocked_check.reset_mock()
    # test RPC call with another strategy
    assert rpc.conciliate(1)
    assert mocked_check.call_args_list == [call()]
    assert mocked_conciliate.call_args_list == [call(rpc.supvisors, ConciliationStrategies.INFANTICIDE, [1, 2, 4])]


def test_restart_sequence(mocker, rpc):
    """ Test the restart_sequence RPC. """
    mocked_check = mocker.patch('supvisors.rpcinterface.RPCInterface._check_operating')
    # test no wait
    assert rpc.restart_sequence(False)
    assert mocked_check.call_args_list == [call()]
    assert rpc.supvisors.fsm.on_restart_sequence.call_args_list == [call()]
    mocked_check.reset_mock()
    rpc.supvisors.fsm.on_restart_sequence.reset_mock()
    # test wait and done
    deferred = rpc.restart_sequence()
    # result is a function for deferred result
    assert callable(deferred)
    assert deferred.wait_state == SupvisorsStates.DISTRIBUTION
    assert mocked_check.call_args_list == [call()]
    assert rpc.supvisors.fsm.on_restart_sequence.call_args_list == [call()]
    # test returned function: first wait for DEPLOYMENT state to be reached
    rpc.supvisors.fsm.state = SupvisorsStates.OPERATION
    assert deferred() == NOT_DONE_YET
    assert deferred.wait_state == SupvisorsStates.DISTRIBUTION
    # test returned function: when DEPLOYMENT state reached, wait for OPERATION state to be reached
    rpc.supvisors.fsm.state = SupvisorsStates.DISTRIBUTION
    assert deferred() == NOT_DONE_YET
    assert deferred.wait_state == SupvisorsStates.OPERATION
    assert deferred() == NOT_DONE_YET
    assert deferred.wait_state == SupvisorsStates.OPERATION
    # test returned function: when DEPLOYMENT state reached, return true
    rpc.supvisors.fsm.state = SupvisorsStates.OPERATION
    assert deferred()


def test_restart(mocker, rpc):
    """ Test the restart RPC. """
    mocked_check = mocker.patch('supvisors.rpcinterface.RPCInterface._check_from_distribution')
    # test RPC call
    assert rpc.restart()
    assert mocked_check.call_args_list == [call()]
    assert rpc.supvisors.fsm.on_restart.call_args_list == [call()]


def test_shutdown(mocker, rpc):
    """ Test the shutdown RPC. """
    mocked_check = mocker.patch('supvisors.rpcinterface.RPCInterface._check_from_distribution')
    # test RPC call
    assert rpc.shutdown()
    assert mocked_check.call_args_list == [call()]
    assert rpc.supvisors.fsm.on_shutdown.call_args_list == [call()]


def test_end_sync(mocker, supvisors, rpc):
    """ Test the end_synchro RPC. """
    mocked_check = mocker.patch.object(rpc, '_check_state')
    mocked_fsm = mocker.patch.object(supvisors.fsm, 'on_end_sync')
    # test RPC call with Master already set
    supvisors.context.master_identifier = '10.0.0.1:25000'
    with pytest.raises(RPCError) as exc:
        rpc.end_sync()
    assert exc.value.args[0] == SupvisorsFaults.BAD_SUPVISORS_STATE.value
    assert mocked_check.call_args_list == [call([SupvisorsStates.INITIALIZATION])]
    assert not mocked_fsm.called
    mocker.resetall()
    # test RPC call with no Master, USER not in synchro_options
    supvisors.context.master_identifier = ''
    with pytest.raises(RPCError) as exc:
        rpc.end_sync()
    assert exc.value.args[0] == SupvisorsFaults.NOT_APPLICABLE.value
    assert mocked_check.call_args_list == [call([SupvisorsStates.INITIALIZATION])]
    assert not mocked_fsm.called
    mocker.resetall()
    # test RPC call with no Master, USER in synchro_options, no master parameter
    supvisors.options.synchro_options = [SynchronizationOptions.USER]
    assert rpc.end_sync()
    assert mocked_check.call_args_list == [call([SupvisorsStates.INITIALIZATION])]
    assert mocked_fsm.call_args_list == [call('')]
    mocker.resetall()
    # test RPC call with no Master, USER in synchro_options, master parameter unknown
    with pytest.raises(RPCError) as exc:
        rpc.end_sync('dummy')
    assert exc.value.args[0] == Faults.BAD_NAME
    assert mocked_check.call_args_list == [call([SupvisorsStates.INITIALIZATION])]
    assert not mocked_fsm.called
    mocker.resetall()
    # test RPC call with no Master, USER in synchro_options, master parameter resolves in multiple identifiers
    supvisors.mapper.assign_stereotypes('10.0.0.1:25000', {'test_stereotype'})
    supvisors.mapper.assign_stereotypes('10.0.0.2:25000', {'test_stereotype'})
    with pytest.raises(RPCError) as exc:
        rpc.end_sync('test_stereotype')
    assert exc.value.args[0] == Faults.INCORRECT_PARAMETERS
    assert mocked_check.call_args_list == [call([SupvisorsStates.INITIALIZATION])]
    assert not mocked_fsm.called
    mocker.resetall()
    # test RPC call with no Master, USER in synchro_options, master parameter known but not running
    with pytest.raises(RPCError) as exc:
        rpc.end_sync('10.0.0.1:25000')
    assert exc.value.args[0] == Faults.NOT_RUNNING
    assert mocked_check.call_args_list == [call([SupvisorsStates.INITIALIZATION])]
    assert not mocked_fsm.called
    mocker.resetall()
    # test RPC call with no Master, USER in synchro_options, master parameter known running
    supvisors.context.instances['10.0.0.1:25000']._state = SupvisorsInstanceStates.RUNNING
    assert rpc.end_sync('10.0.0.1:25000')
    assert mocked_check.call_args_list == [call([SupvisorsStates.INITIALIZATION])]
    assert mocked_fsm.call_args_list == [call('10.0.0.1:25000')]


def test_change_log_level(rpc):
    """ Test the change_log_level RPC. """
    ref_level = rpc.logger.level
    # test RPC call with unknown level
    with pytest.raises(RPCError) as exc:
        rpc.change_log_level(22)
    assert exc.value.args[0] == Faults.INCORRECT_PARAMETERS
    assert rpc.logger.level == ref_level
    # test RPC call with known level by enum
    for new_level in LOG_LEVELS_BY_NUM:
        assert rpc.change_log_level(new_level)
        assert rpc.logger.level == new_level
        assert rpc.logger.handlers[0].level == new_level
    # test RPC call with known level by enum
    for new_level in RPCInterface.get_logger_levels().values():
        assert rpc.change_log_level(new_level)
        level = getLevelNumByDescription(new_level)
        assert rpc.logger.level == level
        assert rpc.logger.handlers[0].level == level
    # test RPC call with known level by enum, as upper case
    for new_level in RPCInterface.get_logger_levels().values():
        assert rpc.change_log_level(new_level.upper())
        level = getLevelNumByDescription(new_level)
        assert rpc.logger.level == level
        assert rpc.logger.handlers[0].level == level


def test_enable_host_statistics(rpc):
    """ Test the enable_host_statistics RPC. """
    # check initial state
    assert rpc.supvisors.stats_collector
    assert rpc.supvisors.options.host_stats_enabled
    # disable the shost statistics collection
    rpc.enable_host_statistics(False)
    assert not rpc.supvisors.options.host_stats_enabled
    assert rpc.supvisors.stats_collector.cmd_recv.poll(timeout=0.5)
    assert rpc.supvisors.stats_collector.cmd_recv.recv() == (StatsMsgType.ENABLE_HOST, False)
    # enable the shost statistics collection
    rpc.enable_host_statistics(True)
    assert rpc.supvisors.options.host_stats_enabled
    assert rpc.supvisors.stats_collector.cmd_recv.poll(timeout=0.5)
    assert rpc.supvisors.stats_collector.cmd_recv.recv() == (StatsMsgType.ENABLE_HOST, True)
    # again with no statistics collector
    rpc.supvisors.stats_collector = None
    for enabled in [False, True]:
        with pytest.raises(RPCError) as exc:
            rpc.enable_host_statistics(enabled)
        assert exc.value.args[0] == SupvisorsFaults.NOT_INSTALLED.value
        assert rpc.supvisors.options.host_stats_enabled


def test_enable_process_statistics(rpc):
    """ Test the enable_process_statistics RPC. """
    # check initial state
    assert rpc.supvisors.stats_collector
    assert rpc.supvisors.options.process_stats_enabled
    # disable the host statistics collection
    rpc.enable_process_statistics(False)
    assert not rpc.supvisors.options.process_stats_enabled
    assert rpc.supvisors.stats_collector.cmd_recv.poll(timeout=0.5)
    assert rpc.supvisors.stats_collector.cmd_recv.recv() == (StatsMsgType.ENABLE_PROCESS, False)
    # enable the host statistics collection
    rpc.enable_process_statistics(True)
    assert rpc.supvisors.options.process_stats_enabled
    assert rpc.supvisors.stats_collector.cmd_recv.poll(timeout=0.5)
    assert rpc.supvisors.stats_collector.cmd_recv.recv() == (StatsMsgType.ENABLE_PROCESS, True)
    # again with no statistics collector
    rpc.supvisors.stats_collector = None
    for enabled in [False, True]:
        with pytest.raises(RPCError) as exc:
            rpc.enable_process_statistics(enabled)
        assert exc.value.args[0] == SupvisorsFaults.NOT_INSTALLED.value
        assert rpc.supvisors.options.process_stats_enabled


def test_update_collecting_period(rpc):
    """ Test the update_collecting_period RPC. """
    # check initial state
    assert rpc.supvisors.stats_collector
    assert rpc.supvisors.options.collecting_period == 5
    # disable the shost statistics collection
    rpc.update_collecting_period(7.5)
    assert rpc.supvisors.options.collecting_period == 7.5
    assert rpc.supvisors.stats_collector.cmd_recv.poll(timeout=0.5)
    assert rpc.supvisors.stats_collector.cmd_recv.recv() == (StatsMsgType.PERIOD, 7.5)
    # again with no statistics collector
    rpc.supvisors.stats_collector = None
    with pytest.raises(RPCError) as exc:
        rpc.update_collecting_period(10)
    assert exc.value.args[0] == SupvisorsFaults.NOT_INSTALLED.value
    assert rpc.supvisors.options.collecting_period == 7.5


def test_get_logger_levels():
    """ Test the RPCInterface._get_logger_levels function. """
    assert RPCInterface.get_logger_levels() == {LevelsByName.BLAT: 'blather', LevelsByName.TRAC: 'trace',
                                                LevelsByName.DEBG: 'debug', LevelsByName.INFO: 'info',
                                                LevelsByName.WARN: 'warn', LevelsByName.ERRO: 'error',
                                                LevelsByName.CRIT: 'critical'}


def test_get_logger_level(rpc):
    """ Test the RPCInterface._get_logger_level method. """
    # test call using all logger levels as string or integer
    for int_level, str_level in RPCInterface.get_logger_levels().items():
        assert rpc._get_logger_level(str_level) == int_level
        assert rpc._get_logger_level(int_level) == int_level
    # test with unexpected string
    with pytest.raises(RPCError) as exc:
        rpc._get_logger_level('serious')
    assert exc.value.args[0] == Faults.INCORRECT_PARAMETERS
    # test with unexpected integer
    with pytest.raises(RPCError) as exc:
        rpc._get_logger_level(0)
    assert exc.value.args[0] == Faults.INCORRECT_PARAMETERS
    # test with unexpected type
    with pytest.raises(RPCError) as exc:
        rpc._get_logger_level({'test'})
    assert exc.value.args[0] == Faults.INCORRECT_PARAMETERS


def test_get_starting_strategy(rpc):
    """ Test the RPCInterface._get_starting_strategy function. """
    # test call using all starting strategies as string or integer
    for strategy in StartingStrategies:
        assert rpc._get_starting_strategy(strategy.value) == strategy
        assert rpc._get_starting_strategy(strategy.name) == strategy
    # test with unexpected string
    with pytest.raises(RPCError) as exc:
        rpc._get_starting_strategy('serious')
    assert exc.value.args[0] == Faults.INCORRECT_PARAMETERS
    # test with unexpected integer
    with pytest.raises(RPCError) as exc:
        rpc._get_starting_strategy(100)
    assert exc.value.args[0] == Faults.INCORRECT_PARAMETERS
    # test with unexpected type
    with pytest.raises(RPCError) as exc:
        rpc._get_starting_strategy({'test'})
    assert exc.value.args[0] == Faults.INCORRECT_PARAMETERS


def test_get_conciliation_strategy(rpc):
    """ Test the RPCInterface._get_conciliation_strategy function. """
    # test call using all starting strategies as string or integer
    for strategy in ConciliationStrategies:
        assert rpc._get_conciliation_strategy(strategy.value) == strategy
        assert rpc._get_conciliation_strategy(strategy.name) == strategy
    # test with unexpected string
    with pytest.raises(RPCError) as exc:
        rpc._get_conciliation_strategy('serious')
    assert exc.value.args[0] == Faults.INCORRECT_PARAMETERS
    # test with unexpected integer
    with pytest.raises(RPCError) as exc:
        rpc._get_conciliation_strategy(100)
    assert exc.value.args[0] == Faults.INCORRECT_PARAMETERS
    # test with unexpected type
    with pytest.raises(RPCError) as exc:
        rpc._get_conciliation_strategy({'test'})
    assert exc.value.args[0] == Faults.INCORRECT_PARAMETERS


def test_check_state(rpc):
    """ Test the RPCInterface._check_state function. """
    # prepare context
    rpc.supvisors.fsm.state = SupvisorsStates.DISTRIBUTION
    # test there is no exception when internal state is in list
    rpc._check_state([SupvisorsStates.INITIALIZATION, SupvisorsStates.DISTRIBUTION, SupvisorsStates.OPERATION])
    # test there is an exception when internal state is not in list
    with pytest.raises(RPCError) as exc:
        rpc._check_state([SupvisorsStates.INITIALIZATION, SupvisorsStates.OPERATION])
    assert exc.value.args == (SupvisorsFaults.BAD_SUPVISORS_STATE.value,
                              'invalid Supvisors state=DISTRIBUTION - state expected'
                              " in ['INITIALIZATION', 'OPERATION']")


def test_check_from_distribution(mocker, rpc):
    """ Test the _check_from_deployment utility. """
    mocked_check = mocker.patch('supvisors.rpcinterface.RPCInterface._check_state')
    # test the call to _check_state
    rpc._check_from_distribution()
    excluded_states = [SupvisorsStates.OFF, SupvisorsStates.INITIALIZATION, SupvisorsStates.FINAL]
    expected = [x for x in SupvisorsStates if x not in excluded_states]
    assert mocked_check.call_args_list == [call(expected)]


def test_check_operating_conciliation(mocker, rpc):
    """ Test the _check_operating_conciliation utility. """
    mocked_check = mocker.patch('supvisors.rpcinterface.RPCInterface._check_state')
    # test the call to _check_state
    rpc._check_operating_conciliation()
    assert mocked_check.call_args_list == [call([SupvisorsStates.OPERATION, SupvisorsStates.CONCILIATION])]


def test_check_operating(mocker, rpc):
    """ Test the _check_operating utility. """
    mocked_check = mocker.patch('supvisors.rpcinterface.RPCInterface._check_state')
    # test the call to _check_state
    rpc._check_operating()
    assert mocked_check.call_args_list == [call([SupvisorsStates.OPERATION])]


def test_check_conciliation(mocker, rpc):
    """ Test the _check_conciliation utility. """
    mocked_check = mocker.patch('supvisors.rpcinterface.RPCInterface._check_state')
    # test the call to _check_state
    rpc._check_conciliation()
    assert mocked_check.call_args_list == [call([SupvisorsStates.CONCILIATION])]


def test_get_application(rpc):
    """ Test the _get_application utility. """
    # prepare context
    rpc.supvisors.context.applications = {'appli_1': 'first application'}
    # test with known application
    assert rpc._get_application('appli_1') == 'first application'
    # test with unknown application
    with pytest.raises(RPCError) as exc:
        rpc._get_application('app')
    assert exc.value.args == (Faults.BAD_NAME, 'application=app unknown to Supvisors')


def test_get_process(rpc):
    """ Test the _get_process utility. """
    # prepare context
    application = Mock(application_name='appli_1', processes={'proc_1': 'first process'})
    # test with known application
    assert rpc._get_process(application, 'proc_1') == 'first process'
    # test with unknown application
    with pytest.raises(RPCError) as exc:
        rpc._get_process(application, 'proc')
    assert exc.value.args == (Faults.BAD_NAME, 'process=proc unknown in application=appli_1')


def test_get_application_process(rpc):
    """ Test the _get_application_process utility. """
    # prepare context
    application = Mock(processes={'proc_1': 'first process'})
    rpc.supvisors.context.applications = {'appli_1': application}
    # test with full namespec
    assert rpc._get_application_process('appli_1:proc_1') == (application, 'first process')
    # test with applicative namespec
    assert rpc._get_application_process('appli_1:*') == (application, None)


def test_get_internal_process_rules(rpc):
    """ Test the _get_application_process utility. """
    # prepare context
    process = Mock(application_name='appli', process_name='proc',
                   **{'rules.serial.return_value': {'start': 0, 'stop': 1}})
    # test call
    assert rpc._get_internal_process_rules(process) == {'application_name': 'appli', 'process_name': 'proc',
                                                        'start': 0, 'stop': 1}


def test_get_local_info(mocker, rpc):
    """ Test the _get_local_info utility. """
    # prepare context
    info = {'group': 'dummy_group', 'name': 'dummy_name',
            'key': 'value', 'state': 0, 'statename': 'STOPPED',
            'start': 1234, 'stop': 7777,
            'now': 4321, 'pid': 4567,
            'description': 'process dead',
            'spawnerr': ''}
    mocker.patch.object(rpc.supvisors.supervisor_data, 'get_process_info',
                        return_value={'start_monotonic': 123, 'stop_monotonic': 0, 'now_monotonic': 45.67,
                                      'process_index': 0, 'program_name': 'dummy_name',
                                      'extra_args': '-x dummy_args', 'startsecs': 2, 'stopwaitsecs': 10})
    # test call
    assert rpc._get_local_info(info) == {'group': 'dummy_group', 'name': 'dummy_name',
                                         'extra_args': '-x dummy_args',
                                         'state': 0, 'statename': 'STOPPED',
                                         'start': 1234, 'stop': 7777,
                                         'now': 4321, 'now_monotonic': 45.67, 'pid': 4567,
                                         'description': 'process dead', 'expected': True, 'spawnerr': '',
                                         'startsecs': 2, 'stopwaitsecs': 10,
                                         'program_name': 'dummy_name', 'process_index': 0,
                                         'start_monotonic': 123, 'stop_monotonic': 0}


def test_start_process(mocker, supvisors):
    """ Test the startProcess RPC.
    This RPC is designed to be added to Supervisor by monkeypatch. """
    SupervisorNamespaceRPCInterface._startProcess = SupervisorNamespaceRPCInterface.startProcess
    SupervisorNamespaceRPCInterface.startProcess = startProcess
    # patch the legacy startProcess
    rpc = DummyRpcInterface(supvisors)
    mocked_start_process = mocker.patch.object(rpc.supervisor, '_startProcess')
    mocked_update = mocker.patch.object(rpc.supervisor, '_update')
    mocked_get = mocker.patch.object(rpc.supervisor, '_getGroupAndProcess', return_value=('dummy_group', None))
    # first call: no process found from parameter
    rpc.supervisor.startProcess('dummy_group:*', False)
    assert mocked_update.call_args_list == [call('startProcess')]
    assert mocked_start_process.call_args_list == [call('dummy_group:*', False)]
    mocker.resetall()
    # second call: process found and not disabled
    mocked_get.return_value = 'dummy_group', Mock(**{'supvisors_config.program_config.disabled': False})
    rpc.supervisor.startProcess('dummy_group:dummy_process', True)
    assert mocked_update.call_args_list == [call('startProcess')]
    assert mocked_start_process.call_args_list == [call('dummy_group:dummy_process', True)]
    mocker.resetall()
    # third call: process found and disabled
    mocked_get.return_value = 'dummy_group', Mock(**{'config.disabled': True})
    with pytest.raises(RPCError) as exc:
        rpc.supervisor.startProcess('dummy_group:dummy_process')
    assert exc.value.args == (SupvisorsFaults.DISABLED.value, 'dummy_group:dummy_process')
    assert mocked_update.call_args_list == [call('startProcess')]
    assert not mocked_start_process.called
