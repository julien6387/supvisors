#!/usr/bin/python
# -*- coding: utf-8 -*-

# ======================================================================
# Copyright 2021 Julien LE CLEACH
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

import time
from unittest.mock import Mock

import pytest
from supervisor.xmlrpc import Faults, RPCError

from supvisors.application import ApplicationRules, ApplicationStatus
from supvisors.process import ProcessRules, ProcessStatus
from .base import DummySupervisor, MockedSupvisors, any_process_info


# Easy Application / Process creation
def create_process(info, supvisors):
    """ Create a ProcessStatus from a payload. """
    return ProcessStatus(info['group'], info['name'], ProcessRules(supvisors), supvisors)


def create_any_process(supvisors):
    return create_process(any_process_info(), supvisors)


def create_application(application_name, supvisors):
    """ Create an ApplicationStatus. """
    return ApplicationStatus(application_name, ApplicationRules(supvisors), supvisors)


# Common function for URLs
def to_simple_url(host: str, page: str, **actions):
    """ Create a simple url based on the ViewContext.format_url parameters. """
    url = f"http://{host}/{page}"
    attributes = '&'.join([f'{key}={value}' for key, value in dict(actions).items()])
    if attributes:
        url += f'?{attributes}'
    return url


# fixture for common global structures
@pytest.fixture
def options():
    return {'internal_port': '65100',
            'event_link': 'none',
            'event_port': '65200',
            'synchro_timeout': '20',
            'inactivity_ticks': '2',
            'core_identifiers': '',
            'disabilities_file': 'disabilities.json',
            'auto_fence': 'on',
            'rules_files': 'my_movies.xml',
            'starting_strategy': 'CONFIG',
            'conciliation_strategy': 'USER',
            'stats_enabled': 'true',
            'stats_periods': '5,15,60',
            'stats_histo': '10',
            'stats_irix_mode': 'False',
            'logfile': 'AUTO',
            'logfile_maxbytes': '10000',
            'logfile_backups': '12',
            'loglevel': 'blather'}


@pytest.fixture
def supervisor():
    return DummySupervisor()


@pytest.fixture
def supvisors(mocker, supervisor, options):
    mocker.patch('supvisors.internal_com.mapper.get_addresses', side_effect=lambda x, y: (x, [x], [x]))
    return MockedSupvisors(supervisor, options)


# Easy XHTML element creation
def create_element(mid_map=None):
    mock = Mock(attrib={'class': ''}, **{'findmeld.side_effect': lambda x: mid_map[x] if mid_map else None,
                                         'repeat.return_value': None})

    def reset_all():
        mock.attrib = {'class': ''}
        mock.reset_mock()
        if mid_map:
            for mid in mid_map.values():
                mid.reset_all()
    mock.reset_all = reset_all
    return mock


# Full RPCInterface mock
def mock_xml_rpc(proxy):
    """ Provide basic answers to the Supervisor & Supvisors XML-RPCs. """
    # set defaults for system XML-RPCs
    proxy.system.listMethods.return_value = ['supervisor.getAPIVersion', 'supvisors.get_api_version'],
    proxy.system.methodHelp.return_value = 'it just works',
    proxy.system.methodSignature.return_value = ['string', 'string']
    # set defaults for Supervisor XML-RPCs
    proxy.supervisor.getAPIVersion.return_value = '3.0'
    proxy.supervisor.getSupervisorVersion.return_value = '4.2.1'
    proxy.supervisor.getIdentification.return_value = 'server_01'
    proxy.supervisor.getState.return_value = {'statecode': 1, 'statename': 'RUNNING'}
    proxy.supervisor.getPID.return_value = 1234
    proxy.supervisor.readLog.return_value = 'WARN No file matches'
    proxy.supervisor.clearLog.return_value = True
    proxy.supervisor.shutdown.return_value = True
    proxy.supervisor.restart.return_value = False
    proxy.supervisor.reloadConfig.return_value = True
    proxy.supervisor.addProcessGroup.side_effect = RPCError(Faults.BAD_NAME, 'unknown')
    proxy.supervisor.removeProcessGroup.return_value = True
    proxy.supervisor.startProcess.return_value = True
    proxy.supervisor.startProcessGroup.return_value = True
    proxy.supervisor.startAllProcesses.return_value = True
    proxy.supervisor.stopProcess.return_value = True
    proxy.supervisor.stopProcessGroup.return_value = True
    proxy.supervisor.stopAllProcesses.return_value = True
    proxy.supervisor.signalProcess.return_value = True
    proxy.supervisor.signalProcessGroup.return_value = True
    proxy.supervisor.signalAllProcesses.return_value = True
    proxy.supervisor.getAllConfigInfo.return_value = [{'autostart': False, 'exitcodes': [0, 2], 'name': 'dummy_1'},
                                                      {'stdout_logfile': './log/dummy_2.log'}]
    proxy.supervisor.getProcessInfo.return_value = {'name': 'movie_srv_01', 'pid': 55636, 'statename': 'RUNNING'}
    proxy.supervisor.getAllProcessInfo.return_value = [{'name': 'movie_srv_01', 'pid': 55636, 'statename': 'RUNNING'},
                                                       {'logfile': './log/register.log'}]
    proxy.supervisor.readProcessStdoutLog.return_value = 'INFO;entering main'
    proxy.supervisor.readProcessStderrLog.return_value = 'INFO;entering main'
    proxy.supervisor.tailProcessStdoutLog.return_value = 'INFO;entering main'
    proxy.supervisor.tailProcessStderrLog.return_value = 'INFO;entering main'
    proxy.supervisor.clearProcessLogs.return_value = True
    proxy.supervisor.clearAllProcessLogs.return_value = True
    proxy.supervisor.sendProcessStdin.return_value = True
    proxy.supervisor.sendRemoteCommEvent.return_value = True
    # set defaults for Supvisors XML-RPCs
    proxy.supvisors.get_api_version.return_value = '1.0'
    proxy.supvisors.get_supvisors_state.return_value = {'fsm_statename': 'OPERATION', 'starting_jobs': []}
    proxy.supvisors.get_master_identifier.return_value = 'server_01'
    proxy.supvisors.get_strategies.return_value = {'auto-fencing': False, 'conciliation': 'USER'}
    proxy.supvisors.get_all_instances_info.return_value = [{'identifier': 'server_01', 'statename': 'RUNNING'},
                                                           {'identifier': 'server_02', 'stopping': False}]
    proxy.supvisors.get_instance_info.return_value = {'identifier': 'server_02', 'stopping': False}
    proxy.supvisors.get_all_applications_info.return_value = [{'application_name': 'database', 'statename': 'STOPPING'},
                                                              {'application_name': 'test', 'major_failure': True}]
    proxy.supvisors.get_application_info.return_value = {'application_name': 'database', 'statename': 'STOPPING'}
    proxy.supvisors.get_application_rules.return_value = {'application_name': 'database', 'start_sequence': 3}
    proxy.supvisors.get_all_process_info.return_value = [{'process_name': 'import', 'statename': 'STOPPED'},
                                                         {'process_name': 'browser', 'pid': 4321}]
    proxy.supvisors.get_process_info.return_value = {'process_name': 'browser', 'pid': 4321}
    proxy.supvisors.get_all_local_process_info.return_value = [{'process_name': 'import', 'statename': 'STOPPED'},
                                                               {'process_name': 'browser', 'pid': 4321}]
    proxy.supvisors.get_local_process_info.return_value = {'process_name': 'browser', 'pid': 4321}
    proxy.supvisors.get_process_rules.return_value = {'process_name': 'browser', 'required': True}
    proxy.supvisors.get_conflicts.return_value = []
    proxy.supvisors.start_application.return_value = True
    proxy.supvisors.stop_application.return_value = True
    proxy.supvisors.restart_application.return_value = True
    proxy.supvisors.start_args.return_value = True
    proxy.supvisors.start_process.return_value = True
    proxy.supvisors.start_any_process.return_value = 'dummy_group:dummy_process'
    proxy.supvisors.stop_process.return_value = True
    proxy.supvisors.restart_process.return_value = True
    proxy.supvisors.update_numprocs.return_value = True
    proxy.supvisors.enable.return_value = True
    proxy.supvisors.disable.return_value = True
    proxy.supvisors.conciliate.return_value = True
    proxy.supvisors.restart_sequence.return_value = True
    proxy.supvisors.restart.return_value = True
    proxy.supvisors.shutdown.return_value = True
    proxy.supvisors.end_sync.return_value = True
    proxy.supvisors.change_log_level.return_value = True


# Wait / sync functions
def wait_internal_publisher(publisher, max_time: int = 10) -> bool:
    """ Wait for the InternalPublisher to be alive. """
    nb_tries = max_time
    while nb_tries > 0 and publisher.stop_event is None:
        time.sleep(1.0)
        nb_tries -= 1
    return publisher.stop_event is not None
