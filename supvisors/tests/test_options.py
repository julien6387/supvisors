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
import sys

from supvisors.options import *
from supvisors.ttypes import ConciliationStrategies, StartingStrategies

from .configurations import *


@pytest.fixture
def opt():
    """ Create a Supvisors-like structure filled with some nodes. """
    return SupvisorsOptions()


@pytest.fixture
def server_opt():
    """ Create a Supvisors-like structure filled with some nodes. """
    return SupvisorsServerOptions()


def test_options_creation(opt):
    """ Test the values set at construction. """
    # all attributes are None
    assert opt.address_list is None
    assert opt.rules_file is None
    assert opt.internal_port is None
    assert opt.event_port is None
    assert opt.auto_fence is None
    assert opt.synchro_timeout is None
    assert opt.force_synchro_if is None
    assert opt.conciliation_strategy is None
    assert opt.starting_strategy is None
    assert opt.stats_periods is None
    assert opt.stats_histo is None
    assert opt.stats_irix_mode is None
    assert opt.logfile is None
    assert opt.logfile_maxbytes is None
    assert opt.logfile_backups is None
    assert opt.loglevel is None


def test_str(opt):
    """ Test the string output. """
    assert str(opt) == 'address_list=None rules_file=None internal_port=None event_port=None auto_fence=None '\
                       'synchro_timeout=None force_synchro_if=None conciliation_strategy=None ' \
                       'starting_strategy=None stats_periods=None stats_histo=None ' \
                       'stats_irix_mode=None logfile=None logfile_maxbytes=None logfile_backups=None loglevel=None'


common_error_message = r'invalid value for {}'


def test_port_num():
    """ Test the conversion into to a port number. """
    error_message = common_error_message.format('port')
    # test invalid values
    with pytest.raises(ValueError, match=error_message):
        SupvisorsServerOptions.to_port_num('-1')
    with pytest.raises(ValueError, match=error_message):
        SupvisorsServerOptions.to_port_num('0')
    with pytest.raises(ValueError, match=error_message):
        SupvisorsServerOptions.to_port_num('65536')
    # test valid values
    assert SupvisorsServerOptions.to_port_num('1') == 1
    assert SupvisorsServerOptions.to_port_num('65535') == 65535


def test_timeout():
    """ Test the conversion of a string to a timeout value. """
    error_message = common_error_message.format('synchro_timeout')
    # test invalid values
    with pytest.raises(ValueError, match=error_message):
        SupvisorsServerOptions.to_timeout('-1')
    with pytest.raises(ValueError, match=error_message):
        SupvisorsServerOptions.to_timeout('0')
    with pytest.raises(ValueError, match=error_message):
        SupvisorsServerOptions.to_timeout('14')
    with pytest.raises(ValueError, match=error_message):
        SupvisorsServerOptions.to_timeout('1201')
    # test valid values
    assert SupvisorsServerOptions.to_timeout('15') == 15
    assert SupvisorsServerOptions.to_timeout('1200') == 1200


def test_conciliation_strategy():
    """ Test the conversion of a string to a conciliation strategy. """
    error_message = common_error_message.format('conciliation_strategy')
    # test invalid values
    with pytest.raises(ValueError, match=error_message):
        SupvisorsServerOptions.to_conciliation_strategy('123456')
    with pytest.raises(ValueError, match=error_message):
        SupvisorsServerOptions.to_conciliation_strategy('dummy')
    with pytest.raises(ValueError, match=error_message):
        SupvisorsServerOptions.to_conciliation_strategy('user')
    # test valid values
    assert SupvisorsServerOptions.to_conciliation_strategy('SENICIDE') == ConciliationStrategies.SENICIDE
    assert SupvisorsServerOptions.to_conciliation_strategy('INFANTICIDE') == ConciliationStrategies.INFANTICIDE
    assert SupvisorsServerOptions.to_conciliation_strategy('USER') == ConciliationStrategies.USER
    assert SupvisorsServerOptions.to_conciliation_strategy('STOP') == ConciliationStrategies.STOP
    assert SupvisorsServerOptions.to_conciliation_strategy('RESTART') == ConciliationStrategies.RESTART


def test_starting_strategy():
    """ Test the conversion of a string to a starting strategy. """
    error_message = common_error_message.format('starting_strategy')
    # test invalid values
    with pytest.raises(ValueError, match=error_message):
        SupvisorsServerOptions.to_starting_strategy('123456')
    with pytest.raises(ValueError, match=error_message):
        SupvisorsServerOptions.to_starting_strategy('dummy')
    with pytest.raises(ValueError, match=error_message):
        SupvisorsServerOptions.to_starting_strategy('config')
    # test valid values
    assert SupvisorsServerOptions.to_starting_strategy('CONFIG') == StartingStrategies.CONFIG
    assert SupvisorsServerOptions.to_starting_strategy('LESS_LOADED') == StartingStrategies.LESS_LOADED
    assert SupvisorsServerOptions.to_starting_strategy('MOST_LOADED') == StartingStrategies.MOST_LOADED


def test_periods():
    """ Test the conversion of a string to a list of periods. """
    error_message = common_error_message.format('stats_periods')
    # test invalid values
    with pytest.raises(ValueError, match='unexpected number of stats_periods'):
        SupvisorsServerOptions.to_periods([])
    with pytest.raises(ValueError, match='unexpected number of stats_periods'):
        SupvisorsServerOptions.to_periods(['1', '2', '3', '4'])
    with pytest.raises(ValueError, match=error_message):
        SupvisorsServerOptions.to_periods(['4', '3600'])
    with pytest.raises(ValueError, match=error_message):
        SupvisorsServerOptions.to_periods(['5', '3601'])
    with pytest.raises(ValueError, match=error_message):
        SupvisorsServerOptions.to_periods(['6', '3599'])
    # test valid values
    assert SupvisorsServerOptions.to_periods(['5']) == [5]
    assert SupvisorsServerOptions.to_periods(['60', '3600']) == [60, 3600]
    assert SupvisorsServerOptions.to_periods(['120', '720', '1800']) == [120, 720, 1800]


def test_histo():
    """ Test the conversion of a string to a history depth. """
    error_message = common_error_message.format('stats_histo')
    # test invalid values
    with pytest.raises(ValueError, match=error_message):
        SupvisorsServerOptions.to_histo('-1')
    with pytest.raises(ValueError, match=error_message):
        SupvisorsServerOptions.to_histo('9')
    with pytest.raises(ValueError, match=error_message):
        SupvisorsServerOptions.to_histo('1501')
    # test valid values
    assert SupvisorsServerOptions.to_histo('10') == 10
    assert SupvisorsServerOptions.to_histo('1500') == 1500


def test_incorrect_supvisors(mocker, server_opt):
    """ Test that exception is raised when the supvisors section is missing. """
    with pytest.raises(ValueError):
        create_server(mocker, server_opt, NoSupvisors)


def test_program_numbers(mocker, server_opt):
    """ Test that the internal numbers of homogeneous programs are stored. """
    server = create_server(mocker, server_opt, ProgramConfiguration)
    assert server.supvisors_options.procnumbers == {'dummy': 0, 'dummy_0': 0, 'dummy_1': 1, 'dummy_2': 2,
                                                    'dumber_10': 0, 'dumber_11': 1}


def test_default_options(mocker, server_opt):
    """ Test the default values of options with empty Supvisors configuration. """
    server = create_server(mocker, server_opt, DefaultOptionConfiguration)
    opt = server.supvisors_options
    assert opt.address_list == [gethostname()]
    assert opt.rules_file is None
    assert opt.internal_port == 65001
    assert opt.event_port == 65002
    assert not opt.auto_fence
    assert opt.synchro_timeout == 15
    assert opt.force_synchro_if == set()
    assert opt.conciliation_strategy == ConciliationStrategies.USER
    assert opt.starting_strategy == StartingStrategies.CONFIG
    assert opt.stats_periods == [10]
    assert opt.stats_histo == 200
    assert not opt.stats_irix_mode
    assert opt.logfile == Automatic
    assert opt.logfile_maxbytes == 50 * 1024 * 1024
    assert opt.logfile_backups == 10
    assert opt.loglevel == 20


def test_defined_options(mocker, server_opt):
    """ Test the values of options with defined Supvisors configuration. """
    server = create_server(mocker, server_opt, DefinedOptionConfiguration)
    opt = server.supvisors_options
    assert opt.address_list == ['cliche01', 'cliche03', 'cliche02']
    assert opt.rules_file == 'my_movies.xml'
    assert opt.internal_port == 60001
    assert opt.event_port == 60002
    assert opt.auto_fence
    assert opt.synchro_timeout == 20
    assert opt.force_synchro_if == {'cliche01', 'cliche03'}
    assert opt.conciliation_strategy == ConciliationStrategies.SENICIDE
    assert opt.starting_strategy == StartingStrategies.MOST_LOADED
    assert opt.stats_periods == [5, 60, 600]
    assert opt.stats_histo == 100
    assert opt.stats_irix_mode
    assert opt.logfile == '/tmp/supvisors.log'
    assert opt.logfile_maxbytes == 50 * 1024
    assert opt.logfile_backups == 5
    assert opt.loglevel == 40


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
