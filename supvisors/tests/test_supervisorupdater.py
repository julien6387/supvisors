# ======================================================================
# Copyright 2024 Julien LE CLEACH
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
from supervisor.options import ProcessConfig

from supvisors.supervisorupdater import *
from supvisors.ttypes import ProgramConfig, SupvisorsProcessConfig


@pytest.fixture
def updater(supervisor, supvisors):
    """ Return the instance to test. """
    return SupervisorUpdater(supvisors)


def test_creation(supvisors, updater):
    """ Test the SupervisorUpdater constructor. """
    assert updater.supvisors is supvisors
    assert updater.logger is supvisors.logger
    assert updater.server_options is supvisors.server_options
    assert updater.supervisor is supvisors.supervisor_data


def test_on_supervisor_start(mocker, supvisors, updater):
    """ Test the on_supervisor_start method. """
    mocked_replace_tail = mocker.patch.object(updater.supervisor, 'replace_tail_handlers')
    mocked_replace_default = mocker.patch.object(updater.supervisor, 'replace_default_handler')
    mocked_update = mocker.patch.object(updater.supervisor, 'complete_internal_data')
    mocked_write = mocker.patch.object(updater.server_options, 'write_disabilities')
    updater.on_supervisor_start()
    assert mocked_replace_tail.called
    assert mocked_replace_default.called
    assert mocked_update.called
    assert mocked_write.called


def test_on_group_added(mocker, supvisors, updater):
    """ Test the on_group_added method. """
    mocked_update = mocker.patch.object(updater.supervisor, 'complete_internal_data')
    mocked_write = mocker.patch.object(updater.server_options, 'write_disabilities')
    updater.on_group_added('dummy_application')
    assert mocked_update.call_args_list == [call({}, 'dummy_application')]
    assert mocked_write.called


def test_enable_program(mocker, supvisors, updater):
    """ Test the enable_program method. """
    mocked_replace_tail = mocker.patch.object(updater.supervisor, 'enable_program')
    mocked_enable = mocker.patch.object(updater.server_options, 'enable_program')
    updater.enable_program('dummy_program')
    assert mocked_replace_tail.call_args_list == [call('dummy_program')]
    assert mocked_enable.call_args_list == [call('dummy_program')]


def test_disable_program(mocker, supvisors, updater):
    """ Test the disable_program method. """
    mocked_replace_tail = mocker.patch.object(updater.supervisor, 'disable_program')
    mocked_disable = mocker.patch.object(updater.server_options, 'disable_program')
    updater.disable_program('dummy_program')
    assert mocked_replace_tail.call_args_list == [call('dummy_program')]
    assert mocked_disable.call_args_list == [call('dummy_program')]


def test_update_numprocs_increase(mocker, updater):
    """ Test the possibility to update numprocs. """
    # get patches
    new_group_configs = {'dummy_group': ['dummy_process_1', 'dummy_process_2']}
    mocked_update = mocker.patch.object(updater.server_options, 'update_numprocs', return_value=new_group_configs)
    mocked_add = mocker.patch.object(updater, '_add_processes', return_value=['dummy_program_2'])
    mocked_obsolete = mocker.patch.object(updater, '_get_obsolete_processes')
    # set context
    program_config = ProgramConfig('dummy_program', ProcessConfig)
    program_config.numprocs = 1
    updater.server_options.program_configs = {'dummy_program': program_config}
    # test numprocs increase
    assert updater.update_numprocs('dummy_program', 2) == (['dummy_program_2'], [])
    assert mocked_update.call_args_list == [call('dummy_program', 2)]
    assert mocked_add.call_args_list == [call(1, new_group_configs)]
    assert not mocked_obsolete.called


def test_update_numprocs_decrease(mocker, updater):
    """ Test the possibility to update numprocs. """
    # get patches
    mocked_obsolete = mocker.patch.object(updater, '_get_obsolete_processes', return_value=['dummy_program_2'])
    mocked_update = mocker.patch.object(updater.server_options, 'update_numprocs',
                                        return_value={'dummy_group': ['dummy_process_1', 'dummy_process_2']})
    mocked_add = mocker.patch.object(updater, '_add_processes')
    # set context
    program_config = ProgramConfig('dummy_program', ProcessConfig)
    program_config.numprocs = 2
    updater.server_options.program_configs = {'dummy_program': program_config}
    program_config.group_config_info = {'dummy_group': []}
    # test numprocs decrease
    assert updater.update_numprocs('dummy_program', 1) == ([], ['dummy_program_2'])
    assert mocked_obsolete.call_args_list == [call(1, program_config.group_config_info)]
    assert mocked_update.call_args_list == [call('dummy_program', 1)]
    assert not mocked_add.called


def test_update_numprocs_no_change(mocker, updater):
    """ Test the possibility to update numprocs. """
    # get patches
    mocked_obsolete = mocker.patch.object(updater, '_get_obsolete_processes')
    mocked_add = mocker.patch.object(updater, '_add_processes')
    mocked_update = mocker.patch.object(updater.server_options, 'update_numprocs',)
    # set context
    program_config = ProgramConfig('dummy_program', ProcessConfig)
    program_config.numprocs = 2
    updater.server_options.program_configs = {'dummy_program': program_config}
    # test numprocs identity
    assert updater.update_numprocs('dummy_program', 2) == ([], [])
    assert not mocked_obsolete.called
    assert not mocked_add.called
    assert not mocked_update.called


def test_get_obsolete_processes(mocker, updater):
    """ Test getting the obsolete processes before decreasing numprocs. """
    mocked_obsolete = mocker.patch.object(updater.supervisor, 'obsolete_processes',
                                          return_value=['dummy_group:dummy_process_2'])
    # set context
    process_1, process_2 = Mock(), Mock()
    process_1.name = 'dummy_process_1'
    process_2.name = 'dummy_process_2'
    group_configs = {'dummy_group': [process_1, process_2]}
    # test call
    assert updater._get_obsolete_processes(1, group_configs) == ['dummy_group:dummy_process_2']
    assert mocked_obsolete.call_args_list == [call({'dummy_group': ['dummy_process_2']})]


def test_add_processes(mocker, updater):
    """ Test the addition of new processes in Supervisor. """
    # get the patches
    mocked_add = mocker.patch.object(updater.supervisor, 'add_supervisor_process',
                                     return_value='dummy_group:dummy_process_2')
    # set context
    process_1, process_2 = Mock(), Mock()
    process_1.name = 'dummy_process_1'
    process_2.name = 'dummy_process_2'
    group_configs = {'dummy_group': [process_1, process_2]}
    program_config = ProgramConfig('dummy_program', ProcessConfig)
    alt_config_1 = SupvisorsProcessConfig(program_config, 0, 'ls')
    alt_config_2 = SupvisorsProcessConfig(program_config, 1, 'ls')
    updater.server_options.process_configs['dummy_process_1'] = alt_config_1
    updater.server_options.process_configs['dummy_process_2'] = alt_config_2
    # test call
    assert updater._add_processes(1, group_configs) == ['dummy_group:dummy_process_2']
    assert mocked_add.call_args_list == [call('dummy_group', process_2, alt_config_2)]
