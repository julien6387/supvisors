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

from unittest.mock import patch, Mock

from supervisor.http import supervisor_auth_handler
from supervisor.medusa import default_handler

from supvisors.infosource import SupervisordSource


@pytest.fixture
def source(supervisor):
    """ Return the instance to test. """
    return SupervisordSource(supervisor, supervisor.supvisors.logger)


def test_unix_server(mocker, supervisor):
    """ Test that using UNIX HTTP server is not compliant with the use of Supvisors. """
    mocker.patch.dict(supervisor.options.server_configs[0], {'section': 'unix_http_server'})
    with pytest.raises(ValueError):
        SupervisordSource(supervisor, supervisor.supvisors.logger)


def test_creation(supervisor, source):
    """ Test the values set at construction. """
    assert source.supervisord is supervisor
    assert source.server_config is source.supervisord.options.server_configs[0]
    assert source._supervisor_rpc_interface is None
    assert source._supvisors_rpc_interface is None


def test_accessors(source):
    """ Test the accessors. """
    # test consistence with DummySupervisor configuration
    assert source.httpserver is source.supervisord.options.httpserver
    assert source.supervisor_rpc_interface == 'supervisor_RPC'
    assert source.supvisors_rpc_interface == 'supvisors_RPC'
    assert source.serverurl == 'url'
    assert source.serverport == 1234
    assert source.username == 'user'
    assert source.password == 'p@$$w0rd'
    assert source.supervisor_state == 'mood'


def test_env(source):
    """ Test the environment build. """
    assert source.get_env() == {'SUPERVISOR_SERVER_URL': 'url',
                                'SUPERVISOR_USERNAME': 'user', 'SUPERVISOR_PASSWORD': 'p@$$w0rd'}


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


def test_group_config(source):
    """ Test the access of a group configuration. """
    # test unknown application
    with pytest.raises(KeyError):
        source.get_group_config('unknown_application')
    # test normal behaviour
    assert source.get_group_config('dummy_application') == 'dummy_application_config'


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
    # add context to internal data
    source.prepare_extra_args()
    # test internal data: all should have additional attributes
    assert all(hasattr(process.config, 'command_ref') or hasattr(process.config, 'extra_args')
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
    assert source.get_extra_args(namespec) == '-la'
    # test internal data
    assert config.command == 'ls -la'
    assert config.command_ref == 'ls'
    assert config.extra_args == '-la'
    # remove them
    source.update_extra_args(namespec, '')
    # test access
    assert source.get_extra_args(namespec) == ''
    # test internal data
    assert config.command == 'ls'
    assert config.command_ref == 'ls'
    assert config.extra_args == ''


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
