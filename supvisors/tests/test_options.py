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

import os.path

import pytest
import sys

from supervisor.loggers import LevelsByName

from supvisors.options import *
from supvisors.ttypes import ConciliationStrategies, StartingStrategies

from .configurations import *


@pytest.fixture
def opt(supervisor):
    """ Create a Supvisors-like structure filled with some instances. """
    return SupvisorsOptions(supervisor)


@pytest.fixture
def filled_opt(mocker, supervisor):
    """ Test the values of options with defined Supvisors configuration. """
    DefinedOptionConfiguration = {'supvisors_list': 'cliche01,cliche03,cliche02',
                                  'rules_files': 'my_movies.xml', 'auto_fence': 'true',
                                  'internal_port': '60001', 'event_port': '60002',
                                  'synchro_timeout': '20', 'inactivity_ticks': '9',
                                  'core_identifiers': 'cliche01,cliche03',
                                  'starting_strategy': 'MOST_LOADED', 'conciliation_strategy': 'SENICIDE',
                                  'stats_enabled': 'false', 'stats_periods': '5,60,600', 'stats_histo': '100',
                                  'stats_irix_mode': 'true',
                                  'logfile': '/tmp/supvisors.log', 'logfile_maxbytes': '50KB',
                                  'logfile_backups': '5', 'loglevel': 'error'}
    mocker.patch('supvisors.options.SupvisorsOptions.to_filepaths', return_value=['my_movies.xml'])
    return SupvisorsOptions(supervisor, **DefinedOptionConfiguration)


@pytest.fixture
def server_opt(supvisors):
    """ Create a Supvisors-like structure filled with some instances. """
    return SupvisorsServerOptions(supvisors.logger)


def test_options_creation(opt):
    """ Test the values set at construction with empty config. """
    # all attributes are None
    assert opt.supvisors_list == [gethostname()]
    assert opt.rules_files is None
    assert opt.internal_port == 0
    assert opt.event_port == 0
    assert not opt.auto_fence
    assert opt.synchro_timeout == 15
    assert opt.inactivity_ticks == 2
    assert opt.core_identifiers == set()
    assert opt.conciliation_strategy == ConciliationStrategies.USER
    assert opt.starting_strategy == StartingStrategies.CONFIG
    assert opt.stats_enabled
    assert opt.stats_periods == [10]
    assert opt.stats_histo == 200
    assert not opt.stats_irix_mode
    assert opt.logfile is Automatic
    assert opt.logfile_maxbytes == 50 * 1024 * 1024
    assert opt.logfile_backups == 10
    assert opt.loglevel == LevelsByName.INFO


def test_filled_options_creation(filled_opt):
    """ Test the values set at construction with config provided by Supervisor. """
    assert filled_opt.supvisors_list == ['cliche01', 'cliche03', 'cliche02']
    assert filled_opt.rules_files == ['my_movies.xml']
    assert filled_opt.internal_port == 60001
    assert filled_opt.event_port == 60002
    assert filled_opt.auto_fence
    assert filled_opt.synchro_timeout == 20
    assert filled_opt.inactivity_ticks == 9
    assert filled_opt.core_identifiers == {'cliche01', 'cliche03'}
    assert filled_opt.conciliation_strategy == ConciliationStrategies.SENICIDE
    assert filled_opt.starting_strategy == StartingStrategies.MOST_LOADED
    assert not filled_opt.stats_enabled
    assert filled_opt.stats_periods == [5, 60, 600]
    assert filled_opt.stats_histo == 100
    assert filled_opt.stats_irix_mode
    assert filled_opt.logfile == '/tmp/supvisors.log'
    assert filled_opt.logfile_maxbytes == 50 * 1024
    assert filled_opt.logfile_backups == 5
    assert filled_opt.loglevel == 40


def test_str(opt):
    """ Test the string output. """
    assert str(opt) == (f'supvisors_list=[\'{gethostname()}\'] rules_files=None internal_port=0 event_port=0'
                        ' auto_fence=False synchro_timeout=15 inactivity_ticks=2 core_identifiers=set()'
                        ' conciliation_strategy=USER starting_strategy=CONFIG'
                        ' stats_enabled=True stats_periods=[10] stats_histo=200'
                        f' stats_irix_mode=False logfile={Automatic} logfile_maxbytes={50 * 1024 * 1024}'
                        ' logfile_backups=10 loglevel=20')


def test_to_filepaths(opt):
    """ Test the validation of file globs into file paths. """
    # find a secure glob that would work with developer test and in Travis-CI
    base_glob = os.path.dirname(__file__)
    filepaths = opt.to_filepaths('*/*/tests/test_opt*py {}/test_options.p? %(here)s/*/test_options.py'
                                 .format(base_glob))
    assert len(filepaths) == 1
    assert os.path.basename(filepaths[0]) == 'test_options.py'


common_error_message = r'invalid value for {}'


def test_port_num():
    """ Test the conversion into to a port number. """
    error_message = common_error_message.format('port')
    # test invalid values
    with pytest.raises(ValueError, match=error_message):
        SupvisorsOptions.to_port_num('-1')
    with pytest.raises(ValueError, match=error_message):
        SupvisorsOptions.to_port_num('65536')
    # test valid values
    assert SupvisorsOptions.to_port_num('0') == 0
    assert SupvisorsOptions.to_port_num('1') == 1
    assert SupvisorsOptions.to_port_num('65535') == 65535


def test_timeout():
    """ Test the conversion of a string to a timeout value. """
    error_message = common_error_message.format('synchro_timeout')
    # test invalid values
    with pytest.raises(ValueError, match=error_message):
        SupvisorsOptions.to_timeout('-1')
    with pytest.raises(ValueError, match=error_message):
        SupvisorsOptions.to_timeout('0')
    with pytest.raises(ValueError, match=error_message):
        SupvisorsOptions.to_timeout('14')
    with pytest.raises(ValueError, match=error_message):
        SupvisorsOptions.to_timeout('1201')
    # test valid values
    assert SupvisorsOptions.to_timeout('15') == 15
    assert SupvisorsOptions.to_timeout('1200') == 1200


def test_ticks():
    """ Test the conversion of a string to a number of ticks. """
    error_message = common_error_message.format('inactivity_ticks')
    # test invalid values
    with pytest.raises(ValueError, match=error_message):
        SupvisorsOptions.to_ticks('-1')
    with pytest.raises(ValueError, match=error_message):
        SupvisorsOptions.to_ticks('0')
    with pytest.raises(ValueError, match=error_message):
        SupvisorsOptions.to_ticks('1')
    with pytest.raises(ValueError, match=error_message):
        SupvisorsOptions.to_ticks('721')
    # test valid values
    assert SupvisorsOptions.to_ticks('2') == 2
    assert SupvisorsOptions.to_ticks('720') == 720


def test_conciliation_strategy():
    """ Test the conversion of a string to a conciliation strategy. """
    error_message = common_error_message.format('conciliation_strategy')
    # test invalid values
    with pytest.raises(ValueError, match=error_message):
        SupvisorsOptions.to_conciliation_strategy('123456')
    with pytest.raises(ValueError, match=error_message):
        SupvisorsOptions.to_conciliation_strategy('dummy')
    with pytest.raises(ValueError, match=error_message):
        SupvisorsOptions.to_conciliation_strategy('user')
    # test valid values
    assert SupvisorsOptions.to_conciliation_strategy('SENICIDE') == ConciliationStrategies.SENICIDE
    assert SupvisorsOptions.to_conciliation_strategy('INFANTICIDE') == ConciliationStrategies.INFANTICIDE
    assert SupvisorsOptions.to_conciliation_strategy('USER') == ConciliationStrategies.USER
    assert SupvisorsOptions.to_conciliation_strategy('STOP') == ConciliationStrategies.STOP
    assert SupvisorsOptions.to_conciliation_strategy('RESTART') == ConciliationStrategies.RESTART


def test_starting_strategy():
    """ Test the conversion of a string to a starting strategy. """
    error_message = common_error_message.format('starting_strategy')
    # test invalid values
    with pytest.raises(ValueError, match=error_message):
        SupvisorsOptions.to_starting_strategy('123456')
    with pytest.raises(ValueError, match=error_message):
        SupvisorsOptions.to_starting_strategy('dummy')
    with pytest.raises(ValueError, match=error_message):
        SupvisorsOptions.to_starting_strategy('config')
    # test valid values
    assert SupvisorsOptions.to_starting_strategy('CONFIG') == StartingStrategies.CONFIG
    assert SupvisorsOptions.to_starting_strategy('LESS_LOADED') == StartingStrategies.LESS_LOADED
    assert SupvisorsOptions.to_starting_strategy('MOST_LOADED') == StartingStrategies.MOST_LOADED


def test_periods():
    """ Test the conversion of a string to a list of periods. """
    error_message = common_error_message.format('stats_periods')
    # test invalid values
    with pytest.raises(ValueError, match='unexpected number of stats_periods: 0. minimum is 1'):
        SupvisorsOptions.to_periods([])
    with pytest.raises(ValueError, match='unexpected number of stats_periods: 4. maximum is 3'):
        SupvisorsOptions.to_periods(['1', '2', '3', '4'])
    with pytest.raises(ValueError, match=error_message):
        SupvisorsOptions.to_periods(['4', '3600'])
    with pytest.raises(ValueError, match=error_message):
        SupvisorsOptions.to_periods(['5', '3601'])
    with pytest.raises(ValueError, match=error_message):
        SupvisorsOptions.to_periods(['6', '3599'])
    with pytest.raises(ValueError, match=error_message):
        SupvisorsOptions.to_periods(['90', 'none'])
    # test valid values
    assert SupvisorsOptions.to_periods(['5']) == [5]
    assert SupvisorsOptions.to_periods(['60', '3600']) == [60, 3600]
    assert SupvisorsOptions.to_periods(['720', '120', '1800']) == [120, 720, 1800]


def test_histo():
    """ Test the conversion of a string to a history depth. """
    error_message = common_error_message.format('stats_histo')
    # test invalid values
    with pytest.raises(ValueError, match=error_message):
        SupvisorsOptions.to_histo('-1')
    with pytest.raises(ValueError, match=error_message):
        SupvisorsOptions.to_histo('9')
    with pytest.raises(ValueError, match=error_message):
        SupvisorsOptions.to_histo('1501')
    # test valid values
    assert SupvisorsOptions.to_histo('10') == 10
    assert SupvisorsOptions.to_histo('1500') == 1500


def create_server(mocker, server_opt, config):
    """ Create a SupvisorsServerOptions instance using patches on Supervisor source code.
    This is required because the unit test does not include existing files. """
    mocker.patch.object(ServerOptions, 'default_configfile', return_value='supervisord.conf')
    mocker.patch.object(ServerOptions, 'exists', return_value=True)
    mocker.patch.object(ServerOptions, 'usage', side_effect=ValueError)
    # this flag is required for supervisor to cope with unittest arguments
    server_opt.positional_args_allowed = 1
    # remove pytest cov options
    mocker.patch.object(sys, 'argv', [sys.argv[0]])
    mocker.patch.object(ServerOptions, 'open', return_value=config)
    server_opt.realize()
    return server_opt


def test_server_options(mocker, server_opt):
    """ Test that the internal numbers of homogeneous programs are stored.
    WARN: All in one test because it doesn't work when create_server is called twice.
    """
    # test attributes
    assert server_opt.parser is None
    assert server_opt.program_class == {}
    assert server_opt.process_groups == {}
    assert server_opt.procnumbers == {}
    # call realize
    server = create_server(mocker, server_opt, ProgramConfiguration)
    assert server.procnumbers == {'dummy': 0, 'dummy_0': 0, 'dummy_1': 1, 'dummy_2': 2, 'dumber_10': 0, 'dumber_11': 1,
                                  'dummy_ears_20': 0, 'dummy_ears_21': 1}
    expected_printable = {program_name: {group_name: [process.name for process in processes]}
                          for program_name, program_configs in server.process_groups.items()
                          for group_name, processes in program_configs.items()}
    assert expected_printable == {'dumber': {'dumber': ['dumber_10', 'dumber_11']},
                                  'dummies': {'dummy_group': ['dummy_0', 'dummy_1', 'dummy_2']},
                                  'dummy': {'dummy_group': ['dummy']},
                                  'dummy_ears': {'dummy_ears': ['dummy_ears_20', 'dummy_ears_21']}}
    assert server.program_class['dummy'] is ProcessConfig
    assert server.program_class['dummies'] is ProcessConfig
    assert server.program_class['dumber'] is FastCGIProcessConfig
    assert server.program_class['dummy_ears'] is EventListenerConfig
    # udpate procnums of a program
    assert server.update_numprocs('dummies', 1) == 'program:dummies'
    assert server.parser['program:dummies']['numprocs'] == '1'
    # reload programs
    result = server.reload_processes_from_section('program:dummies', 'dummy_group')
    expected_printable = [process.name for process in result]
    assert expected_printable == ['dummy_0']
    assert server.procnumbers == {'dummy': 0, 'dummy_0': 0, 'dumber_10': 0, 'dumber_11': 1,
                                  'dummy_ears_20': 0, 'dummy_ears_21': 1}
    # udpate procnums of a FastCGI program
    assert server.update_numprocs('dumber', 1) == 'fcgi-program:dumber'
    assert server.parser['fcgi-program:dumber']['numprocs'] == '1'
    # reload programs
    result = server.reload_processes_from_section('fcgi-program:dumber', 'dumber')
    expected_printable = [process.name for process in result]
    assert expected_printable == ['dumber_10']
    assert server.procnumbers == {'dummy': 0, 'dummy_0': 0, 'dumber_10': 0, 'dummy_ears_20': 0, 'dummy_ears_21': 1}
    # udpate procnums of an event listener
    assert server.update_numprocs('dummy_ears', 3) == 'eventlistener:dummy_ears'
    assert server.parser['eventlistener:dummy_ears']['numprocs'] == '3'
    # reload programs
    result = server.reload_processes_from_section('eventlistener:dummy_ears', 'dummy_ears')
    expected_printable = [process.name for process in result]
    assert expected_printable == ['dummy_ears_20', 'dummy_ears_21', 'dummy_ears_22']
    assert server.procnumbers == {'dummy': 0, 'dummy_0': 0, 'dumber_10': 0,
                                  'dummy_ears_20': 0, 'dummy_ears_21': 1, 'dummy_ears_22': 2}
