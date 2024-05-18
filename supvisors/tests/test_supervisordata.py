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

import stat
from socket import gethostname
from unittest.mock import call, patch, Mock

import pytest
from supervisor.medusa.http_server import http_request
from supervisor.states import SupervisorStates

from supvisors.supervisordata import *
from supvisors.ttypes import ProgramConfig


@pytest.fixture
def source(supervisor, supvisors):
    """ Return the instance to test. """
    supervisor.supvisors = supvisors
    return SupervisorData(supvisors, supervisor)


@pytest.fixture
def medusa_request():
    str_request = 'GET /logtail/dummy_application%3A3Adummy_process_1 HTTP/1.1'
    uri = '/logtail/dummy_application:dummy_process_1'
    header = ['Host: rocky51:60000',
              'User-Agent: Mozilla/5.0 (X11; Linux x86_64; rv:91.0) Gecko/20100101 Firefox/91.0',
              'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
              'Accept-Language: en-US,en;q=0.5',
              'Accept-Encoding: gzip, deflate',
              'Connection: keep-alive',
              'Referer: http://rocky51:60000/proc_instance.html',
              'Upgrade-Insecure-Requests: 1']
    return http_request(Mock(), str_request, 'GET', uri, '1.1', header)


def test_spawn(mocker):
    """ Test the spawn method.
    This method is designed to be added to Supervisor by monkeypatch. """
    Subprocess._spawn, Subprocess.spawn = Subprocess.spawn, spawn
    # create a disabled non-obsolete process
    process = Subprocess(Mock())
    process.supvisors_config = SupvisorsProcessConfig(ProgramConfig('dummy_proc', ProcessConfig), 0, 'ls')
    process.supvisors_config.program_config.disabled = True
    process.obsolete = False
    # patch the legacy Subprocess
    mocked_spawn = mocker.patch.object(process, '_spawn', return_value='spawned')
    # check that spawn does NOT work
    assert process.spawn() is None
    assert not mocked_spawn.called
    # enable the process
    process.supvisors_config.program_config.disabled = False
    # check that spawn does work
    assert process.spawn() == 'spawned'
    assert mocked_spawn.called
    mocker.resetall()
    # obsolete the process
    process.obsolete = True
    # check that spawn does NOT work
    assert process.spawn() is None
    assert not mocked_spawn.called


def test_logtail_handler(mocker, source, medusa_request):
    """ Test the LogtailHandler class used to override the 1024 bytes in process log tail.
    Here, fsize lower than new tail size. """
    mocker.patch('os.path.exists', return_value=True)
    mocker.patch('os.stat', return_value=[0, ] * stat.ST_CTIME)
    mocked_producer = Mock(sz=1000)
    mocker.patch('supervisor.http.tail_f_producer', return_value=mocked_producer)
    source.supervisord.supvisors.options.tailf_limit = 2048
    # first test with fsize lower than new tail size
    handler = LogtailHandler(source.supervisord)
    handler.handle_request(medusa_request)
    assert medusa_request.outgoing[-1].sz == 0
    # second test with fsize greater than new tail size
    mocked_producer.sz = 2000
    # sz at 2000 means that 3024 bytes are available, given that Supervisor goes back 1024 bytes
    handler.handle_request(medusa_request)
    assert medusa_request.outgoing[-1].sz == 976


def test_mainlogtail_handler(mocker, source, medusa_request):
    """ Test the MainLogtailHandler class used to override the 1024 bytes in supervisor log tail. """
    mocker.patch('os.path.exists', return_value=True)
    mocker.patch('os.stat', return_value=[0, ] * stat.ST_CTIME)
    mocked_producer = Mock(sz=1000)
    mocker.patch('supervisor.http.tail_f_producer', return_value=mocked_producer)
    source.supervisord.supvisors.options.tailf_limit = 2048
    # first test with fsize lower than new tail size
    handler = MainLogtailHandler(source.supervisord)
    handler.handle_request(medusa_request)
    assert medusa_request.outgoing[-1].sz == 0
    # first test with fsize greater than tail size
    # sz at 2000 means that 3024 bytes are available, given that Supervisor goes back 1024 bytes
    mocked_producer.sz = 2000
    handler.handle_request(medusa_request)
    assert medusa_request.outgoing[-1].sz == 976


def test_unix_server(mocker, supervisor, supvisors):
    """ Test that using UNIX HTTP server is not compliant with the use of Supvisors. """
    mocker.patch.dict(supervisor.options.server_configs[0], {'family': socket.AF_UNIX})
    with pytest.raises(ValueError):
        SupervisorData(supvisors, supervisor)


def test_creation(supervisor, supvisors, source):
    """ Test the values set at construction. """
    assert source.supervisord is supervisor
    assert source.supvisors is supvisors
    assert source.server_config is source.supervisord.options.server_configs[0]
    assert source._system_rpc_interface is None
    assert source._supervisor_rpc_interface is None
    assert source._supvisors_rpc_interface is None


def test_accessors(source):
    """ Test the accessors. """
    # test consistence with DummySupervisor configuration
    assert source.http_server is source.supervisord.options.httpserver
    assert source.system_rpc_interface.rpc_name == 'system_RPC'
    assert source.supervisor_rpc_interface.rpc_name == 'supervisor_RPC'
    assert source.supvisors_rpc_interface.rpc_name == 'supvisors_RPC'
    assert source.identifier == gethostname()
    assert source.server_host == gethostname()
    assert source.server_port == 25000
    assert source.username == 'user'
    assert source.password == 'p@$$w0rd'
    assert source.server_url == f'http://{gethostname()}:25000'
    assert source.supervisor_state == SupervisorStates.RUNNING


def test_env(source):
    """ Test the environment build. """
    assert source.get_env() == {'SUPERVISOR_SERVER_URL': f'http://{gethostname()}:25000',
                                'SUPERVISOR_USERNAME': 'user', 'SUPERVISOR_PASSWORD': 'p@$$w0rd'}


def test_replace_tail_handlers(source, supervisor):
    """ Test the replacement of the default handler so that the Supvisors pages replace the Supervisor pages. """
    # check handlers type
    assert supervisor.options.httpserver.handlers[1].handler_name == 'tail_handler'
    assert supervisor.options.httpserver.handlers[2].handler_name == 'main_tail_handler'
    # check method behaviour with authentication server
    source.replace_tail_handlers()
    # check handlers type
    assert isinstance(supervisor.options.httpserver.handlers[1], supervisor_auth_handler)
    assert isinstance(supervisor.options.httpserver.handlers[1].handler, LogtailHandler)
    assert isinstance(supervisor.options.httpserver.handlers[2], supervisor_auth_handler)
    assert isinstance(supervisor.options.httpserver.handlers[2].handler, MainLogtailHandler)
    # check method behaviour without authentication server
    with patch.dict(source.server_config, {'username': None}):
        source.replace_tail_handlers()
    # check handlers type
    assert isinstance(supervisor.options.httpserver.handlers[1], LogtailHandler)
    assert isinstance(supervisor.options.httpserver.handlers[2], MainLogtailHandler)


def test_replace_default_handler(source, supervisor):
    """ Test the replacement of the default handler so that the Supvisors pages replace the Supervisor pages. """
    # check handler type
    assert isinstance(supervisor.options.httpserver.handlers[-1], Mock)
    assert supervisor.options.httpserver.handlers[-1].handler_name == 'default_handler'
    # check method behaviour with authentication server
    source.replace_default_handler()
    # check handler type
    assert not isinstance(supervisor.options.httpserver.handlers[-1], Mock)
    assert isinstance(supervisor.options.httpserver.handlers[-1], supervisor_auth_handler)
    assert isinstance(supervisor.options.httpserver.handlers[-1].handler, default_handler.default_handler)
    # check method behaviour without authentication server
    with patch.dict(source.server_config, {'username': None}):
        source.replace_default_handler()
    # check handler type
    assert isinstance(supervisor.options.httpserver.handlers[-1], default_handler.default_handler)


def test_close_httpservers(source, supervisor):
    """ Test the closing of supervisord HTTP servers. """
    # keep reference to http servers
    http_servers = supervisor.options.httpservers
    assert supervisor.options.storage is None
    # call the method
    source.close_httpservers()
    # test the result
    assert supervisor.options.storage is not None
    assert supervisor.options.storage is http_servers
    assert supervisor.options.httpservers == ()


def test_complete_internal_data(source, supervisor):
    """ Test the SupervisorData.complete_internal_data method with no group name set. """
    new_attributes = ['laststart_monotonic', 'laststop_monotonic', 'obsolete', 'extra_args', 'supvisors_config']
    # initial check
    assert 'dummy_application' in supervisor.process_groups
    dummy_application = supervisor.process_groups['dummy_application']
    assert sorted(dummy_application.processes.keys()) == ['dummy_process_1', 'dummy_process_2']
    assert not any(hasattr(process, x)
                   for appli in source.supervisord.process_groups.values()
                   for process in appli.processes.values()
                   for x in new_attributes)
    # add context to one group of the internal data
    program_config = ProgramConfig('dummy_program', ProcessConfig)
    process_configs = {'dummy_process_1': SupvisorsProcessConfig(program_config, 0, 'ls'),
                       'dummy_process_2': SupvisorsProcessConfig(program_config, 1, 'ls')}
    source.complete_internal_data(process_configs)
    # test internal data: 'dummy_application' processes should have additional attributes
    assert all(hasattr(process, x)
               for appli in source.supervisord.process_groups.values()
               for process in appli.processes.values()
               for x in new_attributes)


def test_complete_internal_data_group(source, supervisor):
    """ Test the SupervisorData.complete_internal_data method. """
    new_attributes = ['laststart_monotonic', 'laststop_monotonic', 'obsolete', 'extra_args', 'supvisors_config']
    # initial check
    assert 'dummy_application' in supervisor.process_groups
    dummy_application = supervisor.process_groups['dummy_application']
    assert sorted(dummy_application.processes.keys()) == ['dummy_process_1', 'dummy_process_2']
    assert not any(hasattr(process, x)
                   for appli in source.supervisord.process_groups.values()
                   for process in appli.processes.values()
                   for x in new_attributes)
    # add context to one group of the internal data
    program_config = ProgramConfig('dummy_program', ProcessConfig)
    process_configs = {'dummy_process_1': SupvisorsProcessConfig(program_config, 0, 'ls'),
                       'dummy_process_2': SupvisorsProcessConfig(program_config, 1, 'ls')}
    source.complete_internal_data(process_configs, 'dummy_application')
    # test internal data: 'dummy_application' processes should have additional attributes
    assert all(hasattr(process, x)
               for appli in source.supervisord.process_groups.values()
               for process in appli.processes.values()
               for x in new_attributes)


def test_get_group_processes(source):
    """ Test the access of a supervisord process. """
    # test unknown application
    with pytest.raises(KeyError):
        source.get_group_processes('unknown_application:unknown_process')
    # test normal behaviour
    app_config = source.supervisord.process_groups['dummy_application']
    assert source.get_group_processes('dummy_application') is app_config.processes


def test_get_process(source):
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
    """ Test the autorestart value of a process configuration. """
    # test unknown application and process
    with pytest.raises(KeyError):
        source.autorestart('unknown_application:unknown_process')
    with pytest.raises(KeyError):
        source.autorestart('dummy_application:unknown_process')
    # test normal behaviour
    assert source.autorestart('dummy_application:dummy_process_1')
    assert not source.autorestart('dummy_application:dummy_process_2')


def test_disable_autorestart(source):
    """ Test the disabling of the autorestart of a process configuration. """
    # test unknown application and process
    with pytest.raises(KeyError):
        source.disable_autorestart('unknown_application:unknown_process')
    with pytest.raises(KeyError):
        source.disable_autorestart('dummy_application:unknown_process')
    # test normal behaviour
    assert source.autorestart('dummy_application:dummy_process_1')
    source.disable_autorestart('dummy_application:dummy_process_1')
    assert not source.autorestart('dummy_application:dummy_process_1')


def test_get_process_info(mocker, source):
    """ Test the process information accessor. """
    mocker.patch('time.monotonic', return_value=45.6)
    # not working until Supvisors-related attributes have been set
    with pytest.raises(AttributeError):
        source.get_process_info('dummy_application:dummy_process_1')
    # update the supervisor structures
    program_config = ProgramConfig('dummy_program', ProcessConfig)
    process_configs = {'dummy_process_1': SupvisorsProcessConfig(program_config, 0, 'ls'),
                       'dummy_process_2': SupvisorsProcessConfig(program_config, 1, 'ls')}
    source.complete_internal_data(process_configs, 'dummy_application')
    # retry
    expected = {'disabled': False,
                'extra_args': '',
                'now_monotonic': 45.6,
                'process_index': 0,
                'program_name': 'dummy_program',
                'start_monotonic': 0.0, 'stop_monotonic': 0.0,
                'startsecs': 5, 'stopwaitsecs': 10,
                'has_stderr': True, 'has_stdout': True}
    assert source.get_process_info('dummy_application:dummy_process_1') == expected


def test_has_logfile(source):
    """ Test the logfile existence verification. """
    assert source.has_logfile('dummy_application:dummy_process_1', 'stdout')
    assert not source.has_logfile('dummy_application:dummy_process_1', 'stderr')
    assert not source.has_logfile('dummy_application:dummy_process_2', 'stdout')
    assert source.has_logfile('dummy_application:dummy_process_2', 'stderr')


def test_extra_args(source):
    """ Test the extra arguments functionality. """
    # not working until Supvisors-related attributes have been set
    with pytest.raises(AttributeError):
        source.get_process_info('dummy_application:dummy_process_1')
    # update the supervisor structures
    program_config = ProgramConfig('dummy_program', ProcessConfig)
    process_configs = {'dummy_process_1': SupvisorsProcessConfig(program_config, 0, 'ls'),
                       'dummy_process_2': SupvisorsProcessConfig(program_config, 1, 'ls')}
    source.complete_internal_data(process_configs, 'dummy_application')
    # test unknown application and process
    with pytest.raises(KeyError):
        source.update_extra_args('unknown_application:unknown_process', '-la')
    with pytest.raises(KeyError):
        source.update_extra_args('dummy_application:unknown_process', '-la')
    # test normal behaviour
    namespec = 'dummy_application:dummy_process_1'
    process = source._get_process(namespec)
    assert source.get_process_info(namespec)['extra_args'] == ''
    assert process.supvisors_config.command_ref == 'ls'
    # add extra arguments
    source.update_extra_args(namespec, '-la')
    # test access
    assert source.get_process_info(namespec)['extra_args'] == '-la'
    # test internal data
    assert process.config.command == 'ls -la'
    assert process.supvisors_config.command_ref == 'ls'
    assert process.extra_args == '-la'
    # remove them
    source.update_extra_args(namespec, '')
    # test access
    assert source.get_process_info(namespec)['extra_args'] == ''
    # test internal data
    assert process.config.command == 'ls'
    assert process.supvisors_config.command_ref == 'ls'
    assert process.extra_args == ''


def test_update_start_stop(mocker, source):
    """ Test the update of the supervisor process on process start / stop events. """
    mocker.patch('time.monotonic', return_value=45.6)
    namespec = 'dummy_application:dummy_process_1'
    process = source._get_process(namespec)
    # not working until Supvisors-related attributes have been set
    with pytest.raises(AttributeError):
        process.laststart_monotonic
    with pytest.raises(AttributeError):
        process.laststop_monotonic
    # update the supervisor structures
    program_config = ProgramConfig('dummy_program', ProcessConfig)
    process_configs = {'dummy_process_1': SupvisorsProcessConfig(program_config, 0, 'ls'),
                       'dummy_process_2': SupvisorsProcessConfig(program_config, 1, 'ls')}
    source.complete_internal_data(process_configs, 'dummy_application')
    # retry
    assert process.laststart_monotonic == 0.0
    assert process.laststop_monotonic == 0.0
    # test update_start
    source.update_start(namespec)
    process = source._get_process(namespec)
    assert process.laststart_monotonic == 45.6
    assert process.laststop_monotonic == 0.0
    # test update_stop
    assert not process.obsolete
    source.update_stop(namespec)
    process = source._get_process(namespec)
    assert process.laststart_monotonic == 45.6
    assert process.laststop_monotonic == 45.6
    # test update_stop on obsolete process
    process.obsolete = True
    source.update_stop(namespec)
    with pytest.raises(KeyError):
        source._get_process(namespec)


def test_force_fatal(source):
    """ Test the way to force a process in FATAL state. """
    # test unknown application and process
    with pytest.raises(KeyError):
        source.force_process_fatal('unknown_application:unknown_process', 'crash')
    with pytest.raises(KeyError):
        source.force_process_fatal('dummy_application:unknown_process', 'crash')
    # test normal behaviour
    process_1 = source._get_process('dummy_application:dummy_process_1')
    assert process_1.state == ProcessStates.STOPPED
    assert process_1.spawnerr == ''
    source.force_process_fatal('dummy_application:dummy_process_1', 'crash')
    assert process_1.state == ProcessStates.FATAL
    assert process_1.spawnerr == 'crash'
    # restore configuration
    process_1.state = ProcessStates.STOPPED
    process_1.spawnerr = ''


def test_enable_disable(mocker, supvisors, source):
    """ Test the disabling / enabling of a program. """
    mocked_notify = mocker.patch('supvisors.supervisordata.notify')
    # not working until Supvisors-related attributes have been set
    with pytest.raises(AttributeError):
        source.enable_program('dummy_program')
    with pytest.raises(AttributeError):
        source.disable_program('dummy_program')
    # update the supervisor structures
    program_config = ProgramConfig('dummy_program', ProcessConfig)
    assert not program_config.disabled
    process_configs = {'dummy_process_1': SupvisorsProcessConfig(program_config, 0, 'ls'),
                       'dummy_process_2': SupvisorsProcessConfig(program_config, 1, 'ls')}
    source.complete_internal_data(process_configs)
    # test unknown program
    source.enable_program('unknown_program')
    assert not mocked_notify.called
    mocker.resetall()
    source.disable_program('unknown_program')
    assert not mocked_notify.called
    mocker.resetall()
    assert not program_config.disabled
    assert all(not process.supvisors_config.program_config.disabled
               for appli in source.supervisord.process_groups.values()
               for process in appli.processes.values())
    # test known program
    source.disable_program('dummy_program')
    expected = ['dummy_process_1', 'dummy_process_2']
    notify_call_1 = mocked_notify.call_args_list[0][0][0]
    assert isinstance(notify_call_1, ProcessDisabledEvent)
    assert notify_call_1.process.config.name in expected
    expected.remove(notify_call_1.process.config.name)
    notify_call_2 = mocked_notify.call_args_list[1][0][0]
    assert isinstance(notify_call_2, ProcessDisabledEvent)
    assert notify_call_2.process.config.name in expected
    mocker.resetall()
    assert all(process.supvisors_config.program_config.disabled
               for appli in source.supervisord.process_groups.values()
               for process in appli.processes.values())
    source.enable_program('dummy_program')
    expected = ['dummy_process_1', 'dummy_process_2']
    notify_call_1 = mocked_notify.call_args_list[0][0][0]
    assert isinstance(notify_call_1, ProcessEnabledEvent)
    assert notify_call_1.process.config.name in expected
    expected.remove(notify_call_1.process.config.name)
    notify_call_2 = mocked_notify.call_args_list[1][0][0]
    assert isinstance(notify_call_2, ProcessEnabledEvent)
    assert notify_call_2.process.config.name in expected
    mocker.resetall()
    assert all((not process.supvisors_config.program_config.disabled
                and process.laststart == 0
                and process.laststart_monotonic == 0.0
                and process.state == ProcessStates.STARTING)
               for appli in source.supervisord.process_groups.values()
               for process in appli.processes.values())


def test_add_supervisor_process_obsolete(mocker, source):
    """ Test the addition of a new process in Supervisor, in the event where it has been obsoleted. """
    # get the patches
    mocked_notify = mocker.patch('supvisors.supervisordata.notify')
    # set context
    new_process = Mock()
    process_config = Mock(command='bin/program.exe',
                          **{'make_process.return_value': new_process})
    process_config.name = 'dummy_process_1'
    program_config = ProgramConfig('dummy_program', ProcessConfig)
    alt_config = SupvisorsProcessConfig(program_config, 0, 'ls')
    # test on unknown group
    with pytest.raises(KeyError):
        source.add_supervisor_process('unknown_application', process_config, alt_config)
    # test on non-obsolete process (should not happen though)
    ref_process = source.supervisord.process_groups['dummy_application'].processes['dummy_process_1']
    ref_process.obsolete = False
    assert source.add_supervisor_process('dummy_application', process_config, alt_config) is None
    assert not mocked_notify.called
    # test on obsolete process
    ref_process.obsolete = True
    assert source.add_supervisor_process('dummy_application', process_config, alt_config) is None
    assert not ref_process.obsolete
    assert not mocked_notify.called


def test_add_supervisor_process(mocker, source):
    """ Test the addition of a new process in Supervisor. """
    # get the patches
    mocked_notify = mocker.patch('supvisors.supervisordata.notify')
    # set context
    process_config = Mock(command='bin/program.exe')
    process_config.name = 'dummy_process_3'
    new_process = Mock(config=process_config)
    process_config.make_process.return_value = new_process
    program_config = ProgramConfig('dummy_program', ProcessConfig)
    alt_config = SupvisorsProcessConfig(program_config, 0, 'bin/program.exe')
    # test call
    expected_namespec = 'dummy_application:dummy_process_3'
    assert source.add_supervisor_process('dummy_application', process_config, alt_config) == expected_namespec
    assert source._get_process(expected_namespec) is new_process
    assert new_process.config.options is source.supervisord.options
    assert new_process.supvisors_config.command_ref == 'bin/program.exe'
    assert new_process.extra_args == ''
    assert not new_process.supvisors_config.program_config.disabled
    assert process_config.create_autochildlogs.call_args_list == [call()]
    notify_call = mocked_notify.call_args_list[0][0][0]
    assert isinstance(notify_call, ProcessAddedEvent)
    assert notify_call.process is new_process


def test_obsolete_processes(source):
    """ Test the obsolescence of the supervisor processes. """
    # test call on unknown group
    with pytest.raises(KeyError):
        source.obsolete_processes({'unknown_group': []})
    # test call on known group and empty candidates
    group_processes = {'dummy_application': []}
    assert source.obsolete_processes(group_processes) == []
    # test call on known group and running candidates
    group_processes = {'dummy_application': ['dummy_process_2']}
    process = source._get_process('dummy_application:dummy_process_2')
    process.transition()
    process.obsolete = False
    assert process.state == ProcessStates.STARTING
    assert source.obsolete_processes(group_processes) == ['dummy_application:dummy_process_2']
    process = source._get_process('dummy_application:dummy_process_2')
    assert process.obsolete
    # test call on known group and stopped candidates
    group_processes = {'dummy_application': ['dummy_process_1']}
    process = source._get_process('dummy_application:dummy_process_1')
    process.obsolete = False
    assert process.state == ProcessStates.STOPPED
    assert source.obsolete_processes(group_processes) == []
    with pytest.raises(KeyError):
        source._get_process('dummy_application:dummy_process_1')


def test_delete_process(mocker, source):
    """ Test the possibility to decrease numprocs. """
    # get the patches
    mocked_notify = mocker.patch('supvisors.supervisordata.notify')
    # set context
    group = source.supervisord.process_groups['dummy_application']
    process = group.processes['dummy_process_1']
    # test call
    source.delete_process(group, process)
    notify_call = mocked_notify.call_args_list[0][0][0]
    assert isinstance(notify_call, ProcessRemovedEvent)
    assert notify_call.process is process
    assert list(group.processes.keys()) == ['dummy_process_2']
