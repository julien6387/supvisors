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

from socket import gethostname
from supervisor.process import Subprocess
from supervisor.states import SupervisorStates
from unittest.mock import call, patch, Mock

from supvisors.supervisordata import *


@pytest.fixture
def source(supervisor, supvisors):
    """ Return the instance to test. """
    supervisor.supvisors = supvisors
    return SupervisorData(supvisors, supervisor)


def test_unix_server(mocker, supervisor, supvisors):
    """ Test that using UNIX HTTP server is not compliant with the use of Supvisors. """
    mocker.patch.dict(supervisor.options.server_configs[0], {'section': 'unix_http_server'})
    with pytest.raises(ValueError):
        SupervisorData(supvisors, supervisor)


def test_creation(supervisor, source):
    """ Test the values set at construction. """
    assert source.supervisord is supervisor
    assert source.server_config is source.supervisord.options.server_configs[0]
    assert source._supervisor_rpc_interface is None
    assert source._supvisors_rpc_interface is None
    assert source.disabilities == {}


def test_accessors(source):
    """ Test the accessors. """
    # test consistence with DummySupervisor configuration
    assert source.httpserver is source.supervisord.options.httpserver
    assert source.supervisor_rpc_interface.rpc_name == 'supervisor_RPC'
    assert source.supvisors_rpc_interface.rpc_name == 'supvisors_RPC'
    assert source.serverurl == f'http://{gethostname()}:65000'
    assert source.serverport == 65000
    assert source.username == 'user'
    assert source.password == 'p@$$w0rd'
    assert source.supervisor_state == SupervisorStates.RUNNING


def test_env(source):
    """ Test the environment build. """
    assert source.get_env() == {'SUPERVISOR_SERVER_URL': f'http://{gethostname()}:65000',
                                'SUPERVISOR_USERNAME': 'user', 'SUPERVISOR_PASSWORD': 'p@$$w0rd'}


def test_update_supervisor(mocker, source):
    """ Test the update_supervisor method. """
    mocked_replace = mocker.patch.object(source, 'replace_default_handler')
    mocked_update = mocker.patch.object(source, 'update_internal_data')
    source.update_supervisor()
    assert mocked_replace.called
    assert mocked_update.called


def test_close_server(source):
    """ Test the closing of supervisord HTTP servers. """
    # keep reference to http servers
    http_servers = source.supervisord.options.httpservers
    assert source.supervisord.options.storage is None
    # call the method
    source.close_httpservers()
    # test the result
    assert source.supervisord.options.storage is not None
    assert source.supervisord.options.storage is http_servers
    assert source.supervisord.options.httpservers == ()


def test_process(source):
    """ Test the access of a supervisord process. """
    # test unknown application and process
    with pytest.raises(KeyError):
        source._get_process('unknown_application:unknown_process')
    with pytest.raises(KeyError):
        source._get_process('dummy_application:unknown_process')
    # test normal behaviour
    app_config = source.supervisord.process_groups['dummy_application']
    assert source._get_process('dummy_application:dummy_process_1') is app_config.processes['dummy_process_1']
    assert source._get_process('dummy_application:dummy_process_2') is app_config.processes['dummy_process_2']


def test_process_config(source):
    """ Test the access of a group configuration. """
    # test unknown application and process
    with pytest.raises(KeyError):
        source._get_process_config('unknown_application:unknown_process')
    with pytest.raises(KeyError):
        source._get_process_config('dummy_application:unknown_process')
    # test normal behaviour
    config = source._get_process_config('dummy_application:dummy_process_1')
    assert config.autorestart
    assert config.command == 'ls'
    config = source._get_process_config('dummy_application:dummy_process_2')
    assert not config.autorestart
    assert config.command == 'cat'


def test_autorestart(source):
    """ Test the autostart value of a process configuration. """
    # test unknown application and process
    with pytest.raises(KeyError):
        source.autorestart('unknown_application:unknown_process')
    with pytest.raises(KeyError):
        source.autorestart('dummy_application:unknown_process')
    # test normal behaviour
    assert source.autorestart('dummy_application:dummy_process_1')
    assert not source.autorestart('dummy_application:dummy_process_2')


def test_disable_autorestart(source):
    """ Test the disable of the autostart of a process configuration. """
    # test unknown application and process
    with pytest.raises(KeyError):
        source.disable_autorestart('unknown_application:unknown_process')
    with pytest.raises(KeyError):
        source.disable_autorestart('dummy_application:unknown_process')
    # test normal behaviour
    assert source.autorestart('dummy_application:dummy_process_1')
    source.disable_autorestart('dummy_application:dummy_process_1')
    assert not source.autorestart('dummy_application:dummy_process_1')


def test_extra_args(source):
    """ Test the extra arguments functionality. """
    # test initial status
    assert not any(hasattr(process.config, 'command_ref') or hasattr(process.config, 'extra_args')
                   for appli in source.supervisord.process_groups.values()
                   for process in appli.processes.values())
    # add context to one group of the internal data
    source.supvisors.server_options.processes_program = {'dummy_process_1': 'dummy_process',
                                                         'dummy_process_2': 'dummy_process'}
    source.update_internal_data('dummy_application')
    # test internal data: 'dummy_application' processes should have additional attributes
    assert all(hasattr(process.config, 'command_ref') and hasattr(process.config, 'extra_args')
               for process in source.supervisord.process_groups['dummy_application'].processes.values())
    # add context to internal data
    source.update_internal_data()
    # test internal data: all should have additional attributes
    assert all(hasattr(process.config, 'command_ref') and hasattr(process.config, 'extra_args')
               for appli in source.supervisord.process_groups.values()
               for process in appli.processes.values())
    # test unknown application and process
    with pytest.raises(KeyError):
        source.update_extra_args('unknown_application:unknown_process', '-la')
    with pytest.raises(KeyError):
        source.update_extra_args('dummy_application:unknown_process', '-la')
    # test normal behaviour
    namespec = 'dummy_application:dummy_process_1'
    config = source._get_process_config(namespec)
    # add extra arguments
    source.update_extra_args(namespec, '-la')
    # test access
    assert source.get_process_config_options(namespec, ['extra_args']) == {'extra_args': '-la'}
    # test internal data
    assert config.command == 'ls -la'
    assert config.command_ref == 'ls'
    assert config.extra_args == '-la'
    # remove them
    source.update_extra_args(namespec, '')
    # test access
    assert source.get_process_config_options(namespec, ['extra_args']) == {'extra_args': ''}
    # test internal data
    assert config.command == 'ls'
    assert config.command_ref == 'ls'
    assert config.extra_args == ''


def test_update_numprocs(mocker, source):
    """ Test the possibility to update numprocs. """
    # get patches
    mocked_obsolete = mocker.patch.object(source, '_get_obsolete_processes', return_value=['dummy_program_2'])
    mocked_add = mocker.patch.object(source, '_add_processes', return_value=['dummy_program_3'])
    # set context
    source.supervisord.supvisors.server_options.program_processes = program_processes = {}
    program_processes['dummy_program'] = {'dummy_group': ['dummy_program_1', 'dummy_program_2']}
    # test numprocs increase
    assert source.update_numprocs('dummy_program', 3) == (['dummy_program_3'], [])
    assert not mocked_obsolete.called
    assert mocked_add.call_args_list == [call('dummy_program', 3, 2, ['dummy_group'])]
    mocker.resetall()
    # test numprocs decrease
    assert source.update_numprocs('dummy_program', 1) == ([], ['dummy_program_2'])
    assert mocked_obsolete.call_args_list == [call('dummy_program', 1,
                                                   {'dummy_group': ['dummy_program_1', 'dummy_program_2']})]
    assert not mocked_add.called
    mocker.resetall()
    # test numprocs identity
    source.update_numprocs('dummy_program', 2)
    assert not mocked_obsolete.called
    assert not mocked_add.called


def test_add_processes(mocker, source):
    """ Test the possibility to increase numprocs. """
    # get the patches
    mocked_update = source.supervisord.supvisors.server_options.update_numprocs
    mocked_update.return_value = 'program:dummy_program'
    mocked_reload = source.supervisord.supvisors.server_options.reload_processes_from_section
    process_1, process_2 = Mock(), Mock()
    mocked_reload.return_value = [process_1, process_2]
    expected = ['dummy_group:dummy_program_01', 'dummy_group:dummy_program_02']
    mocked_add = mocker.patch.object(source, '_add_supervisor_processes', return_value=expected)
    # test call
    assert source._add_processes('dummy_program', 2, 1, ['dummy_group']) == expected
    assert mocked_update.call_args_list == [call('dummy_program', 2)]
    assert mocked_reload.call_args_list == [call('program:dummy_program', 'dummy_group')]
    assert mocked_add.call_args_list == [call('dummy_program', 'dummy_group', [process_2])]


def test_add_supervisor_processes(mocker, source):
    """ Test the possibility to increase numprocs. """
    # get the patches
    mocked_notify = mocker.patch('supvisors.supervisordata.notify')
    # set context
    process_1, process_2 = Mock(), Mock()
    program_2 = Mock(command='bin/program_2', **{'make_process.return_value': process_2})
    program_2.name = 'dummy_program_02'
    source.supervisord.process_groups = {'dummy_group': Mock(processes={'dummy_program_01': process_1},
                                                             config=Mock(process_configs=[process_1]))}
    source.disabilities['dummy_program'] = True
    # test call
    expected = ['dummy_group:dummy_program_02']
    assert source._add_supervisor_processes('dummy_program', 'dummy_group', [program_2]) == expected
    assert program_2.options == source.supervisord.options
    assert program_2.command_ref == 'bin/program_2'
    assert program_2.extra_args == ''
    assert program_2.disabled
    assert program_2.create_autochildlogs.call_args_list == [call()]
    assert source.supervisord.process_groups['dummy_group'].processes == {'dummy_program_01': process_1,
                                                                          'dummy_program_02': process_2}
    notify_call = mocked_notify.call_args_list[0][0][0]
    assert isinstance(notify_call, ProcessAddedEvent)
    assert notify_call.process is process_2


def test_get_obsolete_processes(source):
    """ Test getting the obsolete processes before decreasing numprocs. """
    mocked_update = source.supervisord.supvisors.server_options.update_numprocs
    mocked_update.return_value = 'program:dummy_program'
    mocked_reload = source.supervisord.supvisors.server_options.reload_processes_from_section
    # set context
    process_1, process_2 = Mock(), Mock()
    process_1.name = 'dummy_process_1'
    process_2.name = 'dummy_process_2'
    program_configs = {'dummy_group': [process_1, process_2]}
    # test call
    assert source._get_obsolete_processes('dummy_program', 1, program_configs) == ['dummy_group:dummy_process_2']
    assert mocked_update.call_args_list == [call('dummy_program', 1)]
    assert mocked_reload.call_args_list == [call('program:dummy_program', 'dummy_group')]


def test_delete_processes(mocker, source):
    """ Test the possibility to decrease numprocs. """
    # get the patches
    mocked_notify = mocker.patch('supvisors.supervisordata.notify')
    # set context
    process_1, process_2, process_3 = Mock(), Mock(), Mock()
    source.supervisord.process_groups = {'dummy_group': Mock(processes={'dummy_program_01': process_1,
                                                                        'dummy_program_02': process_2,
                                                                        'dummy_program_03': process_3})}
    # test call
    source.delete_processes(['dummy_group:dummy_program_02', 'dummy_group:dummy_program_03'])
    notify_call_1 = mocked_notify.call_args_list[0][0][0]
    assert isinstance(notify_call_1, ProcessRemovedEvent)
    assert notify_call_1. process is process_2
    notify_call_2 = mocked_notify.call_args_list[1][0][0]
    assert isinstance(notify_call_2, ProcessRemovedEvent)
    assert notify_call_2. process is process_3
    assert source.supervisord.process_groups['dummy_group'].processes == {'dummy_program_01': process_1}


def test_force_fatal(source):
    """ Test the way to force a process in FATAL state. """
    # test unknown application and process
    with pytest.raises(KeyError):
        source.force_process_fatal('unknown_application:unknown_process', 'crash')
    with pytest.raises(KeyError):
        source.force_process_fatal('dummy_application:unknown_process', 'crash')
    # test normal behaviour
    process_1 = source._get_process('dummy_application:dummy_process_1')
    assert process_1.state == 'STOPPED'
    assert process_1.spawnerr == ''
    source.force_process_fatal('dummy_application:dummy_process_1', 'crash')
    assert process_1.state == 'FATAL'
    assert process_1.spawnerr == 'crash'
    # restore configuration
    process_1.state = 'STOPPED'
    process_1.spawnerr = ''


def test_replace_handler(source):
    """ Test the autostart value of a process configuration. """
    # keep reference to handler
    assert isinstance(source.supervisord.options.httpserver.handlers[1], Mock)
    # check method behaviour with authentication server
    source.replace_default_handler()
    # keep reference to handler
    assert isinstance(source.supervisord.options.httpserver.handlers[1], supervisor_auth_handler)
    # check method behaviour with authentication server
    with patch.dict(source.server_config, {'username': None}):
        source.replace_default_handler()
    # keep reference to handler
    assert isinstance(source.supervisord.options.httpserver.handlers[1], default_handler.default_handler)


def test_get_subprocesses(source):
    """ Test the get_subprocesses method. """
    # set context
    dummy_program_1, dummy_program_2 = Mock(), Mock()
    dummy_program_1.name = 'dummy_program_1'
    dummy_program_2.name = 'dummy_program_2'
    source.supervisord.supvisors.server_options.program_processes = program_processes = {}
    program_processes['dummy_program'] = {'dummy_group': [dummy_program_1, dummy_program_2]}
    assert source.get_subprocesses('dummy_program') == ['dummy_group:dummy_program_1', 'dummy_group:dummy_program_2']


def test_enable_disable(mocker, source):
    """ Test the disabling / enabling of a program. """
    mocked_notify = mocker.patch('supvisors.supervisordata.notify')
    mocked_write = mocker.patch.object(source, 'write_disabilities')
    # test initial status
    assert not any(hasattr(process.config, 'disabled')
                   for appli in source.supervisord.process_groups.values()
                   for process in appli.processes.values())
    # add context to one group of the internal data
    source.supvisors.server_options.processes_program = {'dummy_process_1': 'dummy_process',
                                                         'dummy_process_2': 'dummy_process'}
    source.update_internal_data('dummy_application')
    # test internal data: 'dummy_application' processes should have additional attributes
    assert all(not process.config.disabled
               for process in source.supervisord.process_groups['dummy_application'].processes.values())
    # add context to internal data
    source.update_internal_data()
    # test internal data: all should have additional attributes
    assert all(not process.config.disabled
               for appli in source.supervisord.process_groups.values()
               for process in appli.processes.values())
    # test unknown program
    source.enable_program('unknown_program')
    assert not mocked_notify.called
    assert mocked_write.called
    mocker.resetall()
    assert source.disabilities == {'dummy_process': False, 'unknown_program': False}
    assert all(not process.config.disabled
               for appli in source.supervisord.process_groups.values()
               for process in appli.processes.values())
    source.disable_program('unknown_program')
    assert not mocked_notify.called
    assert mocked_write.called
    mocker.resetall()
    assert source.disabilities == {'dummy_process': False, 'unknown_program': True}
    assert all(not process.config.disabled
               for appli in source.supervisord.process_groups.values()
               for process in appli.processes.values())
    # test known program
    source.disable_program('dummy_process')
    expected = list(source.supvisors.server_options.processes_program.keys())
    notify_call_1 = mocked_notify.call_args_list[0][0][0]
    assert isinstance(notify_call_1, ProcessDisabledEvent)
    assert notify_call_1.process.config.name in expected
    expected.remove(notify_call_1.process.config.name)
    notify_call_2 = mocked_notify.call_args_list[1][0][0]
    assert isinstance(notify_call_2, ProcessDisabledEvent)
    assert notify_call_2.process.config.name in expected
    assert mocked_write.called
    mocker.resetall()
    assert source.disabilities == {'dummy_process': True, 'unknown_program': True}
    assert all(process.config.disabled
               for process in source.supervisord.process_groups['dummy_application'].processes.values())
    source.enable_program('dummy_process')
    expected = list(source.supvisors.server_options.processes_program.keys())
    notify_call_1 = mocked_notify.call_args_list[0][0][0]
    assert isinstance(notify_call_1, ProcessEnabledEvent)
    assert notify_call_1.process.config.name in expected
    expected.remove(notify_call_1.process.config.name)
    notify_call_2 = mocked_notify.call_args_list[1][0][0]
    assert isinstance(notify_call_2, ProcessEnabledEvent)
    assert notify_call_2.process.config.name in expected
    assert mocked_write.called
    mocker.resetall()
    assert source.disabilities == {'dummy_process': False, 'unknown_program': True}
    assert all(not process.config.disabled and process.laststart == 0 and process.state == 'STARTING'
               for process in source.supervisord.process_groups['dummy_application'].processes.values())


def test_disabilities_serialization(mocker, source):
    """ Test the serialization of the disabilities. """
    # patch open
    mocked_open = mocker.patch('builtins.open', mocker.mock_open())
    # read_disabilities has already been called once in the constructor based on a non-existing file
    assert source.disabilities == {}
    # fill context and write
    source.disabilities['program_1'] = True
    source.disabilities['program_2'] = False
    source.write_disabilities()
    mocked_open.assert_called_once_with(source.supvisors.options.disabilities_file, 'w+')
    handle = mocked_open()
    json_expected = '{"program_1": true, "program_2": false}'
    assert handle.write.call_args_list == [call(json_expected)]
    # empty context and read
    mocked_open = mocker.patch('builtins.open', mocker.mock_open(read_data=json_expected))
    mocker.patch('os.path.isfile', return_value=True)
    source.disabilities = {}
    source.read_disabilities()
    assert source.disabilities == {'program_1': True, 'program_2': False}
    mocked_open.assert_called_once_with(source.supvisors.options.disabilities_file)
    handle = mocked_open()
    assert handle.read.call_args_list == [call()]
    # test with disabilities files not set
    source.supvisors.options.disabilities_file = None
    source.disabilities = {}
    source.read_disabilities()
    assert source.disabilities == {}


def test_spawn(mocker):
    """ Test the spawn method.
    This method is designed to be added to Supervisor by monkeypatch. """
    Subprocess._spawn, Subprocess.spawn = Subprocess.spawn, spawn
    # create a disabled process
    process = Subprocess(Mock(disabled=True))
    # patch the legacy Subprocess
    mocked_spawn = mocker.patch.object(process, '_spawn', return_value='spawned')
    # check that spawn does not work
    assert process.spawn() is None
    assert not mocked_spawn.called
    # enable the process
    process.config.disabled = False
    # check that spawn does work
    assert process.spawn() == 'spawned'
    assert mocked_spawn.called
