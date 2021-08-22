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

from supervisor.loggers import LOG_LEVELS_BY_NUM

from supvisors.plugin import expand_faults
from supvisors.rpcinterface import *
from supvisors.ttypes import ApplicationStates, ConciliationStrategies, SupvisorsStates

from .conftest import create_application


@pytest.fixture(autouse=True)
def faults():
    """ Add fault codes to Supervisor. """
    expand_faults()


@pytest.fixture
def rpc(supvisors):
    """ create the instance to be tested. """
    return RPCInterface(supvisors)


def test_creation(supvisors, rpc):
    """ Test the values set at construction. """
    assert rpc.supvisors is supvisors


def test_api_version(rpc):
    """ Test the get_api_version RPC. """
    assert rpc.get_api_version() == API_VERSION


def test_supvisors_state(rpc):
    """ Test the get_supvisors_state RPC. """
    # prepare context
    rpc.supvisors.fsm.serial.return_value = 'RUNNING'
    # test call
    assert rpc.get_supvisors_state() == 'RUNNING'


def test_master_address(rpc):
    """ Test the get_master_address RPC. """
    # prepare context
    rpc.supvisors.context.master_node_name = '10.0.0.1'
    # test call
    assert rpc.get_master_address() == '10.0.0.1'


def test_strategies(rpc):
    """ Test the get_strategies RPC. """
    # prepare context
    rpc.supvisors.options.auto_fence = True
    rpc.supvisors.options.conciliation_strategy = ConciliationStrategies.INFANTICIDE
    rpc.supvisors.options.starting_strategy = StartingStrategies.MOST_LOADED
    # test call
    assert rpc.get_strategies() == {'auto-fencing': True, 'starting': 'MOST_LOADED', 'conciliation': 'INFANTICIDE'}


def test_address_info(rpc):
    """ Test the get_address_info RPC. """
    # prepare context
    rpc.supvisors.context.nodes = {'10.0.0.1': Mock(**{'serial.return_value': 'address_info'})}
    # test with known address
    assert rpc.get_address_info('10.0.0.1') == 'address_info'
    # test with unknown address
    with pytest.raises(RPCError) as exc:
        rpc.get_address_info('10.0.0.0')
    assert exc.value.args == (Faults.BAD_ADDRESS, 'node 10.0.0.0 unknown to Supvisors')


def test_all_addresses_info(rpc):
    """ Test the get_all_addresses_info RPC. """
    # prepare context
    rpc.supvisors.context.nodes = {'10.0.0.1': Mock(**{'serial.return_value': 'address_info_1'}),
                                   '10.0.0.2': Mock(**{'serial.return_value': 'address_info_2'})}
    # test call
    assert rpc.get_all_addresses_info() == ['address_info_1', 'address_info_2']


def test_application_info(mocker, rpc):
    """ Test the get_application_info RPC. """
    application = create_application('TestApplication', rpc.supvisors)
    mocked_serial = mocker.patch('supvisors.rpcinterface.RPCInterface._get_application', return_value=application)
    mocked_check = mocker.patch('supvisors.rpcinterface.RPCInterface._check_from_deployment')
    # test RPC call
    assert rpc.get_application_info('dummy') == {'application_name': 'TestApplication',
                                                 'major_failure': False, 'minor_failure': False,
                                                 'statecode': 0, 'statename': 'STOPPED'}
    assert mocked_check.call_args_list == [call()]
    assert mocked_serial.call_args_list == [call('dummy')]


def test_all_applications_info(mocker, rpc):
    """ Test the get_all_applications_info RPC. """
    mocked_get = mocker.patch('supvisors.rpcinterface.RPCInterface.get_application_info',
                              side_effect=[{'name': 'appli_1'}, {'name': 'appli_2'}])
    mocked_check = mocker.patch('supvisors.rpcinterface.RPCInterface._check_from_deployment')
    # prepare context
    rpc.supvisors.context.applications = {'dummy_1': None, 'dummy_2': None}
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
    mocked_check = mocker.patch('supvisors.rpcinterface.RPCInterface._check_from_deployment')
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


def test_all_process_info(mocker, rpc):
    """ Test the get_all_process_info RPC. """
    mocked_check = mocker.patch('supvisors.rpcinterface.RPCInterface._check_from_deployment')
    # prepare context
    rpc.supvisors.context.applications = {
        'appli_1': Mock(processes={'proc_1_1': Mock(**{'serial.return_value': {'name': 'proc_1_1'}}),
                                   'proc_1_2': Mock(**{'serial.return_value': {'name': 'proc_1_2'}})}),
        'appli_2': Mock(processes={'proc_2': Mock(**{'serial.return_value': {'name': 'proc_2'}})})}
    # test RPC call
    assert rpc.get_all_process_info() == [{'name': 'proc_1_1'}, {'name': 'proc_1_2'}, {'name': 'proc_2'}]
    assert mocked_check.call_args_list == [call()]


def test_local_process_info(mocker, rpc):
    """ Test the get_local_process_info RPC. """
    mocked_get = mocker.patch('supvisors.rpcinterface.RPCInterface._get_local_info',
                              return_value={'group': 'group', 'name': 'name'})
    # prepare context
    info_source = rpc.supvisors.info_source
    mocked_rpc = info_source.supervisor_rpc_interface.getProcessInfo
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
    info_source = rpc.supvisors.info_source
    mocked_rpc = info_source.supervisor_rpc_interface.getAllProcessInfo
    mocked_rpc.return_value = [{'group': 'dummy_group', 'name': 'dummy_name'}]
    # test RPC call with process namespec
    assert rpc.get_all_local_process_info() == [{'group': 'group', 'name': 'name'}]
    assert mocked_rpc.call_args_list == [call()]
    assert mocked_get.call_args_list == [call({'group': 'dummy_group', 'name': 'dummy_name'})]


def test_application_rules(mocker, rpc):
    """ Test the get_application_rules RPC. """
    application = create_application('TestApplication', rpc.supvisors)
    mocked_check = mocker.patch('supvisors.rpcinterface.RPCInterface._check_from_deployment')
    mocked_get = mocker.patch('supvisors.rpcinterface.RPCInterface._get_application', return_value=application)
    # test RPC call with application name and unmanaged application
    expected = {'application_name': 'appli', 'managed': False}
    assert rpc.get_application_rules('appli') == expected
    assert mocked_check.call_args_list == [call()]
    assert mocked_get.call_args_list == [call('appli')]
    mocker.resetall()
    # test RPC call with application name and managed/distributed application
    application.rules.managed = True
    expected = {'application_name': 'appli', 'managed': True, 'distributed': True,
                'start_sequence': 0, 'stop_sequence': 0, 'starting_strategy': 'CONFIG',
                'starting_failure_strategy': 'ABORT', 'running_failure_strategy': 'CONTINUE'}
    assert rpc.get_application_rules('appli') == expected
    assert mocked_check.call_args_list == [call()]
    assert mocked_get.call_args_list == [call('appli')]
    mocker.resetall()
    # test RPC call with application name and managed/non-distributed application
    application.rules.distributed = False
    expected = {'application_name': 'appli', 'managed': True, 'distributed': False, 'addresses': ['*'],
                'start_sequence': 0, 'stop_sequence': 0, 'starting_strategy': 'CONFIG',
                'starting_failure_strategy': 'ABORT', 'running_failure_strategy': 'CONTINUE'}
    assert rpc.get_application_rules('appli') == expected
    assert mocked_check.call_args_list == [call()]
    assert mocked_get.call_args_list == [call('appli')]


def test_process_rules(mocker, rpc):
    """ Test the get_process_rules RPC. """
    mocked_check = mocker.patch('supvisors.rpcinterface.RPCInterface._check_from_deployment')
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
    mocked_check = mocker.patch('supvisors.rpcinterface.RPCInterface._check_from_deployment')
    # prepare context
    proc_1 = Mock(**{'serial.return_value': {'name': 'proc_1'}})
    proc_3 = Mock(**{'serial.return_value': {'name': 'proc_3'}})
    mocker.patch.object(rpc.supvisors.context, 'conflicts', return_value=[proc_1, proc_3])
    # test RPC call
    assert rpc.get_conflicts() == [{'name': 'proc_1'}, {'name': 'proc_3'}]
    assert mocked_check.call_args_list == [call()]


def test_start_application(mocker, rpc):
    """ Test the start_application RPC. """
    mocked_check = mocker.patch('supvisors.rpcinterface.RPCInterface._check_operating')
    # prepare context
    rpc.supvisors.context.applications = {'appli_1': Mock()}
    # get patches
    mocked_start = rpc.supvisors.starter.start_application
    mocked_progress = rpc.supvisors.starter.in_progress
    # test RPC call with unknown strategy
    with pytest.raises(RPCError) as exc:
        rpc.start_application('strategy', 'appli')
    assert exc.value.args == (Faults.BAD_STRATEGY, 'strategy')
    assert mocked_check.call_args_list == [call()]
    assert mocked_start.call_count == 0
    assert mocked_start.call_count == 0
    assert mocked_progress.call_count == 0
    mocked_check.reset_mock()
    # test RPC call with unknown application
    with pytest.raises(RPCError) as exc:
        rpc.start_application(0, 'appli')
    assert exc.value.args == (Faults.BAD_NAME, 'appli')
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
        assert mocked_start.call_count == 0
        assert mocked_progress.call_count == 0
        mocked_check.reset_mock()
    # test RPC call with stopped application
    # test no wait and not done
    application.state = ApplicationStates.STOPPED
    mocked_start.return_value = False
    result = rpc.start_application(0, 'appli_1', False)
    assert result
    assert mocked_check.call_args_list == [call()]
    assert mocked_start.call_args_list == [call(StartingStrategies.CONFIG, application)]
    assert mocked_progress.call_count == 0
    mocked_check.reset_mock()
    mocked_start.reset_mock()
    # test no wait and done
    application.state = ApplicationStates.STOPPED
    mocked_start.return_value = True
    result = rpc.start_application(0, 'appli_1', False)
    assert not result
    assert mocked_check.call_args_list == [call()]
    assert mocked_start.call_args_list == [call(StartingStrategies.CONFIG, application)]
    assert mocked_progress.call_count == 0
    mocked_check.reset_mock()
    mocked_start.reset_mock()
    # test wait and done
    mocked_start.return_value = True
    result = rpc.start_application(0, 'appli_1')
    assert not result
    assert mocked_check.call_args_list == [call()]
    assert mocked_start.call_args_list == [call(StartingStrategies.CONFIG, application)]
    assert mocked_progress.call_count == 0
    mocked_check.reset_mock()
    mocked_start.reset_mock()
    # test wait and not done
    mocked_start.return_value = False
    deferred = rpc.start_application(0, 'appli_1')
    # result is a function for deferred result
    assert callable(deferred)
    assert mocked_check.call_args_list == [call()]
    assert mocked_start.call_args_list == [call(StartingStrategies.CONFIG, application)]
    assert mocked_progress.call_count == 0
    # test returned function: return True when job in progress
    mocked_progress.return_value = True
    assert deferred() == NOT_DONE_YET
    assert mocked_progress.call_args_list == [call()]
    mocked_progress.reset_mock()
    # test returned function: raise exception if job not in progress anymore and application not running
    mocked_progress.return_value = False
    for _ in [ApplicationStates.STOPPING, ApplicationStates.STOPPED, ApplicationStates.STARTING]:
        with pytest.raises(RPCError) as exc:
            deferred()
        assert exc.value.args == (Faults.ABNORMAL_TERMINATION, 'appli_1')
        assert mocked_progress.call_args_list == [call()]
        mocked_progress.reset_mock()
    # test returned function: return True if job not in progress anymore and application running
    application.state = ApplicationStates.RUNNING
    assert deferred()
    assert mocked_progress.call_args_list == [call()]


def test_stop_application(mocker, rpc):
    """ Test the stop_application RPC. """
    mocked_check = mocker.patch('supvisors.rpcinterface.RPCInterface._check_operating_conciliation')
    # prepare context
    appli_1 = Mock(**{'has_running_processes.return_value': False})
    rpc.supvisors.context.applications = {'appli_1': appli_1}
    # get patches
    mocked_stop = rpc.supvisors.stopper.stop_application
    mocked_progress = rpc.supvisors.stopper.in_progress
    # test RPC call with unknown application
    with pytest.raises(RPCError) as exc:
        rpc.stop_application('appli')
    assert exc.value.args == (Faults.BAD_NAME, 'appli')
    assert mocked_check.call_args_list == [call()]
    assert mocked_stop.call_count == 0
    assert mocked_progress.call_count == 0
    mocked_check.reset_mock()
    # test RPC call with stopped application
    application = rpc.supvisors.context.applications['appli_1']
    with pytest.raises(RPCError) as exc:
        rpc.stop_application('appli_1')
    assert exc.value.args == (Faults.NOT_RUNNING, 'appli_1')
    assert mocked_check.call_args_list == [call()]
    assert mocked_stop.call_count == 0
    assert mocked_progress.call_count == 0
    mocked_check.reset_mock()
    # test RPC call with running application
    appli_1.has_running_processes.return_value = True
    # test no wait and done
    mocked_stop.return_value = True
    result = rpc.stop_application('appli_1', False)
    assert not result
    assert mocked_check.call_args_list == [call()]
    assert mocked_stop.call_args_list == [call(application)]
    assert mocked_progress.call_count == 0
    mocked_check.reset_mock()
    mocked_stop.reset_mock()
    # test wait and done
    mocked_stop.return_value = True
    result = rpc.stop_application('appli_1')
    assert not result
    assert mocked_check.call_args_list == [call()]
    assert mocked_stop.call_args_list == [call(application)]
    assert mocked_progress.call_count == 0
    mocked_check.reset_mock()
    mocked_stop.reset_mock()
    # test wait and not done
    mocked_stop.return_value = False
    result = rpc.stop_application('appli_1')
    # result is a function
    assert callable(result)
    assert mocked_check.call_args_list == [call()]
    assert mocked_stop.call_args_list == [call(application)]
    assert mocked_progress.call_count == 0
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
        assert exc.value.args == (Faults.ABNORMAL_TERMINATION, 'appli_1')
        assert mocked_progress.call_args_list == [call()]
        mocked_progress.reset_mock()
    # test returned function: return True if job not in progress anymore and application running
    application.state = ApplicationStates.STOPPED
    assert result()
    assert mocked_progress.call_args_list == [call()]
    # reset patches for next loop
    mocked_check.reset_mock()
    mocked_stop.reset_mock()
    mocked_progress.reset_mock()


def test_restart_application(mocker, rpc):
    """ Test the restart_application RPC. """
    mocked_check = mocker.patch('supvisors.rpcinterface.RPCInterface._check_operating')
    mocked_start = mocker.patch('supvisors.rpcinterface.RPCInterface.start_application')
    mocked_stop = mocker.patch('supvisors.rpcinterface.RPCInterface.stop_application')
    # test RPC call with sub-RPC calls return a direct result
    mocked_stop.return_value = True
    mocked_start.return_value = False
    deferred = rpc.restart_application(0, 'appli', 'wait')
    assert mocked_check.call_args_list == [call()]
    assert mocked_stop.call_args_list == [call('appli', True)]
    assert mocked_start.call_count == 0
    mocked_stop.reset_mock()
    mocked_check.reset_mock()
    # result is a function
    assert callable(deferred)
    assert deferred.waitstop
    # test this function
    assert not deferred()
    assert not deferred.waitstop
    assert mocked_stop.call_count == 0
    assert mocked_start.call_args_list == [call(0, 'appli', 'wait')]
    mocked_start.reset_mock()
    # test RPC call with sub_RPC calls returning jobs
    # test with mocking functions telling that the jobs are not completed
    mocked_stop_job = Mock(return_value=False)
    mocked_start_job = Mock(return_value=False)
    mocked_stop.return_value = mocked_stop_job
    mocked_start.return_value = mocked_start_job
    deferred = rpc.restart_application(0, 'appli', 'wait')
    assert mocked_check.call_args_list == [call()]
    assert mocked_stop.call_args_list == [call('appli', True)]
    assert mocked_start.call_count == 0
    mocked_stop.reset_mock()
    # result is a function for deferred result
    assert callable(deferred)
    assert deferred.waitstop
    # first call to this function tells that job is still in progress
    assert mocked_stop_job.call_count == 0
    assert mocked_start_job.call_count == 0
    assert deferred() == NOT_DONE_YET
    assert mocked_stop.call_count == 0
    assert mocked_start.call_count == 0
    assert mocked_stop_job.call_args_list == [call()]
    assert mocked_start_job.call_count == 0
    mocked_stop_job.reset_mock()
    # replace the stop job with a function telling that the job is completed
    mocked_stop_job.return_value = True
    assert deferred() == NOT_DONE_YET
    assert not deferred.waitstop
    assert mocked_stop.call_count == 0
    assert mocked_start.call_args_list == [call(0, 'appli', 'wait')]
    assert mocked_stop_job.call_args_list == [call()]
    assert mocked_start_job.call_count == 0
    mocked_stop_job.reset_mock()
    # call the deferred function again to check that the start is engaged
    assert not deferred()
    assert mocked_start_job.call_args_list == [call()]
    assert mocked_stop_job.call_count == 0


def test_start_args(mocker, rpc):
    """ Test the start_args RPC. """
    mocker.patch('supvisors.rpcinterface.RPCInterface._get_application_process',
                 return_value=(None, Mock(namespec='appli:proc')))
    # prepare context
    info_source = rpc.supvisors.info_source
    info_source.update_extra_args.side_effect = KeyError
    mocked_startProcess = info_source.supervisor_rpc_interface.startProcess
    mocked_startProcess.side_effect = [RPCError(Faults.NO_FILE, 'no file'),
                                       RPCError(Faults.NOT_EXECUTABLE),
                                       RPCError(Faults.ABNORMAL_TERMINATION),
                                       'done']
    # test RPC call with extra arguments but with a process that is unknown to Supervisor
    with pytest.raises(RPCError) as exc:
        rpc.start_args('appli:proc', 'dummy arguments')
    assert exc.value.args == (Faults.BAD_NAME, 'namespec appli:proc unknown to this Supervisor instance')
    assert info_source.update_extra_args.call_args_list == [call('appli:proc', 'dummy arguments')]
    assert mocked_startProcess.call_count == 0
    # update mocking
    info_source.update_extra_args.reset_mock()
    info_source.update_extra_args.side_effect = None
    # test RPC call with start exceptions
    # NO_FILE exception triggers an update of the process state
    with pytest.raises(RPCError) as exc:
        rpc.start_args('appli:proc')
    assert exc.value.args == (Faults.NO_FILE, 'no file')
    assert info_source.update_extra_args.call_args_list == [call('appli:proc', '')]
    assert mocked_startProcess.call_args_list == [call('appli:proc', True)]
    assert info_source.force_process_fatal.call_args_list == [call('appli:proc', 'NO_FILE: no file')]
    # reset patches
    info_source.update_extra_args.reset_mock()
    info_source.force_process_fatal.reset_mock()
    mocked_startProcess.reset_mock()
    # NOT_EXECUTABLE exception triggers an update of the process state
    with pytest.raises(RPCError) as exc:
        rpc.start_args('appli:proc', wait=False)
    assert exc.value.args == (Faults.NOT_EXECUTABLE, )
    assert info_source.update_extra_args.call_args_list == [call('appli:proc', '')]
    assert mocked_startProcess.call_args_list == [call('appli:proc', False)]
    assert info_source.force_process_fatal.call_args_list == [call('appli:proc', 'NOT_EXECUTABLE')]
    # reset patches
    info_source.update_extra_args.reset_mock()
    info_source.force_process_fatal.reset_mock()
    mocked_startProcess.reset_mock()
    # other exception doesn't trigger an update of the process state
    with pytest.raises(RPCError) as exc:
        rpc.start_args('appli:proc', wait=False)
    assert exc.value.args == (Faults.ABNORMAL_TERMINATION, )
    assert info_source.update_extra_args.call_args_list == [call('appli:proc', '')]
    assert mocked_startProcess.call_args_list == [call('appli:proc', False)]
    assert not info_source.force_process_fatal.called
    # reset patches
    info_source.update_extra_args.reset_mock()
    mocked_startProcess.reset_mock()
    # finally, normal behaviour
    assert rpc.start_args('appli:proc') == 'done'
    assert info_source.update_extra_args.call_args_list == [call('appli:proc', '')]
    assert mocked_startProcess.call_args_list == [call('appli:proc', True)]
    assert not info_source.force_process_fatal.called


def test_start_process(mocker, rpc):
    """ Test the start_process RPC. """
    mocked_check = mocker.patch('supvisors.rpcinterface.RPCInterface._check_operating')
    # get patches
    mocked_start = rpc.supvisors.starter.start_process
    mocked_progress = rpc.supvisors.starter.in_progress
    # patch the instance
    rpc._get_application_process = Mock()
    # test RPC call with unknown strategy
    with pytest.raises(RPCError) as exc:
        rpc.start_process('strategy', 'appli:proc')
    assert exc.value.args == (Faults.BAD_STRATEGY, 'strategy')
    assert mocked_check.call_args_list == [call()]
    assert mocked_start.call_count == 0
    assert mocked_progress.call_count == 0
    mocked_check.reset_mock()
    # test RPC call with running process
    rpc._get_application_process.return_value = (None, Mock(namespec='proc1', **{'running.return_value': True}))
    with pytest.raises(RPCError) as exc:
        rpc.start_process(0, 'appli_1')
    assert exc.value.args == (Faults.ALREADY_STARTED, 'proc1')
    assert mocked_check.call_args_list == [call()]
    assert mocked_start.call_count == 0
    assert mocked_progress.call_count == 0
    mocked_check.reset_mock()
    # test RPC call with running processes
    proc_1 = Mock(**{'running.return_value': False})
    proc_2 = Mock(namespec='proc2', **{'running.return_value': True})
    rpc._get_application_process.return_value = (Mock(**{'processes.values.return_value': [proc_1, proc_2]}), None)
    with pytest.raises(RPCError) as exc:
        rpc.start_process(0, 'appli_1')
    assert exc.value.args == (Faults.ALREADY_STARTED, 'proc2')
    assert mocked_check.call_args_list == [call()]
    assert mocked_start.call_count == 0
    assert mocked_progress.call_count == 0
    mocked_check.reset_mock()
    # test RPC call with stopped processes
    proc_1 = Mock(namespec='proc1', **{'running.return_value': False, 'stopped.return_value': True})
    proc_2 = Mock(namespec='proc2', **{'running.return_value': False, 'stopped.return_value': False})
    rpc._get_application_process.return_value = (Mock(**{'processes.values.return_value': [proc_1, proc_2]}), None)
    # test RPC call with no wait and not done
    mocked_start.return_value = False
    result = rpc.start_process(1, 'appli:*', 'argument list', False)
    assert result
    assert mocked_check.call_args_list == [call()]
    assert mocked_start.call_args_list == [call(StartingStrategies.LESS_LOADED, proc_1, 'argument list'),
                                           call(StartingStrategies.LESS_LOADED, proc_2, 'argument list')]
    assert not mocked_progress.called
    mocked_check.reset_mock()
    mocked_start.reset_mock()
    # test RPC call no wait and done
    mocked_start.return_value = True
    with pytest.raises(RPCError) as exc:
        rpc.start_process(1, 'appli:*', 'argument list', False)
    assert exc.value.args == (Faults.ABNORMAL_TERMINATION, 'appli:*')
    assert mocked_check.call_args_list == [call()]
    assert mocked_start.call_args_list == [call(StartingStrategies.LESS_LOADED, proc_1, 'argument list'),
                                           call(StartingStrategies.LESS_LOADED, proc_2, 'argument list')]
    assert not mocked_progress.called
    mocked_check.reset_mock()
    mocked_start.reset_mock()
    # test RPC call with wait and done
    with pytest.raises(RPCError) as exc:
        rpc.start_process(2, 'appli:*', wait=True)
    assert exc.value.args == (Faults.ABNORMAL_TERMINATION, 'appli:*')
    assert mocked_start.call_args_list == [call(StartingStrategies.MOST_LOADED, proc_1, ''),
                                           call(StartingStrategies.MOST_LOADED, proc_2, '')]
    assert not mocked_progress.called
    mocked_check.reset_mock()
    mocked_start.reset_mock()
    # test RPC call with wait and not done
    mocked_start.return_value = False
    deferred = rpc.start_process(2, 'appli:*', wait=True)
    # result is a function for deferred result
    assert callable(deferred)
    assert mocked_check.call_args_list == [call()]
    assert mocked_start.call_args_list == [call(StartingStrategies.MOST_LOADED, proc_1, ''),
                                           call(StartingStrategies.MOST_LOADED, proc_2, '')]
    assert not mocked_progress.called
    # test returned function: return True when job in progress
    mocked_progress.return_value = True
    assert deferred() == NOT_DONE_YET
    assert mocked_progress.call_args_list == [call()]
    mocked_progress.reset_mock()
    # test returned function: raise exception if job not in progress anymore and process still stopped
    mocked_progress.return_value = False
    with pytest.raises(RPCError) as exc:
        deferred()
    assert exc.value.args == (Faults.ABNORMAL_TERMINATION, 'proc1')
    assert mocked_progress.call_args_list == [call()]
    mocked_progress.reset_mock()
    # test returned function: return True if job not in progress anymore and process running
    proc_1.stopped.return_value = False
    assert deferred()
    assert mocked_progress.call_args_list == [call()]


def test_stop_process(mocker, rpc):
    """ Test the stop_process RPC. """
    mocked_check = mocker.patch('supvisors.rpcinterface.RPCInterface._check_operating_conciliation')
    # get patches
    mocked_stop = rpc.supvisors.stopper.stop_process
    mocked_progress = rpc.supvisors.stopper.in_progress
    # patch the instance
    rpc._get_application_process = Mock()
    # test RPC call with running process
    rpc._get_application_process.return_value = (None, Mock(namespec='proc1', **{'stopped.return_value': True}))
    with pytest.raises(RPCError) as exc:
        rpc.stop_process('appli_1')
    assert exc.value.args == (Faults.NOT_RUNNING, 'proc1')
    assert mocked_check.call_args_list == [call()]
    assert mocked_stop.call_count == 0
    assert mocked_progress.call_count == 0
    mocked_check.reset_mock()
    # test RPC call with running processes
    proc_1 = Mock(**{'stopped.return_value': False})
    proc_2 = Mock(namespec='proc2', **{'stopped.return_value': True})
    rpc._get_application_process.return_value = (Mock(**{'processes.values.return_value': [proc_1, proc_2]}), None)
    with pytest.raises(RPCError) as exc:
        rpc.stop_process('appli_1')
    assert exc.value.args == (Faults.NOT_RUNNING, 'proc2')
    assert mocked_check.call_args_list == [call()]
    assert mocked_stop.call_count == 0
    assert mocked_progress.call_count == 0
    mocked_check.reset_mock()
    # test RPC call with stopped processes
    proc_1 = Mock(namespec='proc1', **{'running.return_value': True, 'stopped.return_value': False})
    proc_2 = Mock(namespec='proc2', **{'running.return_value': False, 'stopped.return_value': False})
    rpc._get_application_process.return_value = (Mock(**{'processes.values.return_value': [proc_1, proc_2]}), None)
    # test RPC call with no wait and not done
    mocked_stop.return_value = False
    assert rpc.stop_process('appli:*', False)
    assert mocked_check.call_args_list == [call()]
    assert mocked_stop.call_args_list == [call(proc_1), call(proc_2)]
    assert mocked_progress.call_count == 0
    mocked_check.reset_mock()
    mocked_stop.reset_mock()
    # test RPC call no wait and done
    mocked_stop.return_value = True
    assert rpc.stop_process('appli:*', False)
    assert mocked_check.call_args_list == [call()]
    assert mocked_stop.call_args_list == [call(proc_1), call(proc_2)]
    assert mocked_progress.call_count == 0
    mocked_check.reset_mock()
    mocked_stop.reset_mock()
    # test RPC call with wait and done
    assert rpc.stop_process('appli:*', wait=True)
    assert mocked_stop.call_args_list == [call(proc_1), call(proc_2)]
    assert mocked_progress.call_count == 0
    mocked_check.reset_mock()
    mocked_stop.reset_mock()
    # test RPC call with wait and not done
    mocked_stop.return_value = False
    deferred = rpc.stop_process('appli:*', wait=True)
    # result is a function for deferred result
    assert callable(deferred)
    assert mocked_check.call_args_list == [call()]
    assert mocked_stop.call_args_list == [call(proc_1), call(proc_2)]
    assert mocked_progress.call_count == 0
    # test returned function: return True when job in progress
    mocked_progress.return_value = True
    assert deferred() == NOT_DONE_YET
    assert mocked_progress.call_args_list == [call()]
    mocked_progress.reset_mock()
    # test returned function: raise exception if job not in progress anymore and process still running
    mocked_progress.return_value = False
    with pytest.raises(RPCError) as exc:
        deferred()
    assert exc.value.args == (Faults.ABNORMAL_TERMINATION, 'proc1')
    assert mocked_progress.call_args_list == [call()]
    mocked_progress.reset_mock()
    # test returned function: return True if job not in progress anymore and process stopped
    proc_1.running.return_value = False
    assert deferred()
    assert mocked_progress.call_args_list == [call()]


def test_restart_process(mocker, rpc):
    """ Test the restart_process RPC. """
    mocked_check = mocker.patch('supvisors.rpcinterface.RPCInterface._check_operating')
    mocked_start = mocker.patch('supvisors.rpcinterface.RPCInterface.start_process')
    mocked_stop = mocker.patch('supvisors.rpcinterface.RPCInterface.stop_process')
    # test RPC call with sub-RPC calls return a direct result
    mocked_stop.return_value = True
    mocked_start.return_value = False
    deferred = rpc.restart_process(0, 'appli:*', 'arg list', 'wait')
    assert mocked_check.call_args_list == [call()]
    assert mocked_stop.call_args_list == [call('appli:*', True)]
    assert mocked_start.call_count == 0
    mocked_stop.reset_mock()
    mocked_check.reset_mock()
    # result is a function
    assert callable(deferred)
    assert deferred.waitstop
    # test this function
    assert not deferred()
    assert not deferred.waitstop
    assert mocked_stop.call_count == 0
    assert mocked_start.call_args_list == [call(0, 'appli:*', 'arg list', 'wait')]
    mocked_start.reset_mock()
    # test RPC call with sub_RPC calls returning jobs
    # test with mocking functions telling that the jobs are not completed
    mocked_stop_job = Mock(return_value=False)
    mocked_start_job = Mock(return_value=False)
    mocked_stop.return_value = mocked_stop_job
    mocked_start.return_value = mocked_start_job
    deferred = rpc.restart_process(0, 'appli:*', '', 'wait')
    assert mocked_check.call_args_list == [call()]
    assert mocked_stop.call_args_list == [call('appli:*', True)]
    assert mocked_start.call_count == 0
    mocked_stop.reset_mock()
    # result is a function for deferred result
    assert callable(deferred)
    assert deferred.waitstop
    # test this function
    assert mocked_stop_job.call_count == 0
    assert mocked_start_job.call_count == 0
    assert deferred() == NOT_DONE_YET
    assert mocked_stop.call_count == 0
    assert mocked_start.call_count == 0
    assert mocked_stop_job.call_args_list == [call()]
    assert mocked_start_job.call_count == 0
    mocked_stop_job.reset_mock()
    # replace the stop job with a function telling that the job is completed
    mocked_stop_job.return_value = True
    assert deferred() == NOT_DONE_YET
    assert not deferred.waitstop
    assert mocked_stop.call_count == 0
    assert mocked_start.call_args_list == [call(0, 'appli:*', '', 'wait')]
    assert mocked_stop_job.call_args_list == [call()]
    assert mocked_start_job.call_count == 0
    mocked_stop_job.reset_mock()
    # call the deferred function again to check that the start is engaged
    assert not deferred()
    assert mocked_start_job.call_args_list == [call()]
    assert mocked_stop_job.call_count == 0


def test_restart(mocker, rpc):
    """ Test the restart RPC. """
    mocked_check = mocker.patch('supvisors.rpcinterface.RPCInterface._check_from_deployment')
    # test RPC call
    assert rpc.restart()
    assert mocked_check.call_args_list == [call()]
    assert rpc.supvisors.fsm.on_restart.call_args_list == [call()]


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
    assert exc.value.args == (Faults.BAD_STRATEGY, 'a strategy')
    mocked_check.reset_mock()
    # test RPC call with USER strategy
    assert not rpc.conciliate(ConciliationStrategies.USER)
    assert mocked_check.call_args_list == [call()]
    assert not mocked_conciliate.called
    mocked_check.reset_mock()
    # test RPC call with another strategy
    assert rpc.conciliate(1)
    assert mocked_check.call_args_list == [call()]
    assert mocked_conciliate.call_args_list == [call(rpc.supvisors, ConciliationStrategies.INFANTICIDE, [1, 2, 4])]


def test_shutdown(mocker, rpc):
    """ Test the shutdown RPC. """
    mocked_check = mocker.patch('supvisors.rpcinterface.RPCInterface._check_from_deployment')
    # test RPC call
    assert rpc.shutdown()
    assert mocked_check.call_args_list == [call()]
    assert rpc.supvisors.fsm.on_shutdown.call_args_list == [call()]


def test_change_log_level(rpc):
    """ Test the change_log_level RPC. """
    ref_level = rpc.logger.level
    # test RPC call with unknown level
    with pytest.raises(RPCError) as exc:
        rpc.change_log_level(22)
    assert exc.value.args == (Faults.BAD_LEVEL, '22')
    assert rpc.logger.level == ref_level
    # test RPC call with known level by enum
    for new_level in LOG_LEVELS_BY_NUM:
        assert rpc.change_log_level(new_level)
        assert rpc.logger.level == new_level
        assert rpc.logger.handlers[0].level == new_level
    # test RPC call with known level by enum
    for new_level in RPCInterface._get_logger_levels().values():
        assert rpc.change_log_level(new_level)
        level = getLevelNumByDescription(new_level)
        assert rpc.logger.level == level
        assert rpc.logger.handlers[0].level == level


def test_check_state(rpc):
    """ Test the _check_state utility. """
    # prepare context
    rpc.supvisors.fsm.state = SupvisorsStates.DEPLOYMENT
    # test there is no exception when internal state is in list
    rpc._check_state([SupvisorsStates.INITIALIZATION, SupvisorsStates.DEPLOYMENT, SupvisorsStates.OPERATION])
    # test there is an exception when internal state is not in list
    with pytest.raises(RPCError) as exc:
        rpc._check_state([SupvisorsStates.INITIALIZATION, SupvisorsStates.OPERATION])
    assert exc.value.args == (Faults.BAD_SUPVISORS_STATE,
                              "Supvisors (state=DEPLOYMENT) not in state ['INITIALIZATION', 'OPERATION'] "
                              "to perform request")


def test_check_from_deployment(mocker, rpc):
    """ Test the _check_from_deployment utility. """
    mocked_check = mocker.patch('supvisors.rpcinterface.RPCInterface._check_state')
    # test the call to _check_state
    rpc._check_from_deployment()
    expected = [x for x in SupvisorsStates if 0 < x.value < 6]
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
    assert exc.value.args == (Faults.BAD_NAME, 'application app unknown to Supvisors')


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


def test_get_local_info(rpc):
    """ Test the _get_local_info utility. """
    # prepare context
    info = {'group': 'dummy_group', 'name': 'dummy_name',
            'key': 'value', 'state': 'undefined',
            'start': 1234, 'stop': 7777,
            'now': 4321, 'pid': 4567,
            'description': 'process dead',
            'spawnerr': ''}
    info_source = rpc.supvisors.info_source
    info_source.get_extra_args.return_value = '-x dummy_args'
    # test call
    assert rpc._get_local_info(info) == {'group': 'dummy_group', 'name': 'dummy_name',
                                         'extra_args': '-x dummy_args',
                                         'state': 'undefined',
                                         'start': 1234, 'stop': 7777, 'now': 4321, 'pid': 4567,
                                         'description': 'process dead', 'expected': True, 'spawnerr': ''}
    # test again if process unknown to the local Supervisor
    rpc.supvisors.info_source.get_extra_args.side_effect = KeyError
    assert rpc._get_local_info(info) == {'group': 'dummy_group', 'name': 'dummy_name',
                                         'state': 'undefined',
                                         'start': 1234, 'stop': 7777, 'now': 4321, 'pid': 4567,
                                         'description': 'process dead', 'expected': True, 'spawnerr': ''}
