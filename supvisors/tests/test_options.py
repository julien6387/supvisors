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
import sys
from unittest.mock import call

import pytest
from supervisor.loggers import LevelsByName

from supvisors.options import *
from supvisors.ttypes import ConciliationStrategies, StartingStrategies
from .configurations import *


@pytest.fixture
def config():
    return {'software_name': 'Supvisors tests',
            'software_icon': 'my_icon.png',
            'supvisors_list': 'cliche01,cliche03,cliche02', 'stereotypes': 'test',
            'multicast_group': '239.0.0.1:7777', 'multicast_interface': '192.168.1.1', 'multicast_ttl': '5',
            'rules_files': 'my_movies.xml', 'auto_fence': 'true',
            'event_link': 'zmq', 'event_port': '60002',
            'synchro_options': 'LIST,USER', 'synchro_timeout': '20',
            'inactivity_ticks': '9',
            'core_identifiers': 'cliche01,cliche03',
            'disabilities_file': '/tmp/disabilities.json',
            'starting_strategy': 'MOST_LOADED', 'conciliation_strategy': 'SENICIDE',
            'stats_enabled': 'process', 'stats_collecting_period': '2',
            'stats_periods': '5,50,77.7', 'stats_histo': '100',
            'stats_irix_mode': 'true',
            'tail_limit': '1MB', 'tailf_limit': '512',
            'logfile': '/tmp/supvisors.log', 'logfile_maxbytes': '50KB',
            'logfile_backups': '5', 'loglevel': 'error'}


@pytest.fixture
def opt(supervisor, supvisors):
    """ Create a Supvisors-like structure filled with some instances. """
    return SupvisorsOptions(supervisor, supvisors.logger)


@pytest.fixture
def filled_opt(mocker, supervisor, supvisors, config):
    """ Test the values of options with defined Supvisors configuration. """
    mocker.patch('supvisors.options.SupvisorsOptions.to_existing_file', return_value='my_icon.png')
    mocker.patch('supvisors.options.SupvisorsOptions.to_filepaths', return_value=['my_movies.xml'])
    return SupvisorsOptions(supervisor, supvisors.logger, **config)


@pytest.fixture
def server_opt(supvisors):
    """ Create a Supvisors-like structure filled with some instances. """
    return SupvisorsServerOptions(supvisors)


def test_empty_logger_configuration():
    """ Test the logger configuration with empty config. """
    assert get_logger_configuration() == {'prefix': '',
                                          'logfile': Automatic,
                                          'logfile_backups': 10,
                                          'logfile_maxbytes': 50 * 1024 * 1024,
                                          'loglevel': LevelsByName.INFO}


def test_filled_logger_configuration(config):
    """ Test the logger configuration with empty config. """
    assert get_logger_configuration(**config) == {'prefix': 'Supvisors tests',
                                                  'logfile': '/tmp/supvisors.log',
                                                  'logfile_backups': 5,
                                                  'logfile_maxbytes': 50 * 1024,
                                                  'loglevel': LevelsByName.ERRO}


def test_options_creation(opt):
    """ Test the values set at construction with empty config. """
    assert opt.software_name == ''
    assert opt.software_icon is None
    assert opt.supvisors_list is None
    assert opt.multicast_group is None
    assert opt.multicast_interface is None
    assert opt.multicast_ttl == 1
    assert opt.rules_files is None
    assert opt.event_link == EventLinks.NONE
    assert opt.event_port == 0
    assert not opt.auto_fence
    assert opt.synchro_timeout == 15
    assert opt.inactivity_ticks == 2
    assert opt.core_identifiers == set()
    assert opt.disabilities_file is None
    assert opt.conciliation_strategy == ConciliationStrategies.USER
    assert opt.starting_strategy == StartingStrategies.CONFIG
    assert opt.host_stats_enabled
    assert opt.process_stats_enabled
    assert opt.collecting_period == 5
    assert opt.stats_periods == [10]
    assert opt.stats_histo == 200
    assert not opt.stats_irix_mode
    assert opt.tail_limit == 1024
    assert opt.tailf_limit == 1024


def test_filled_options_creation(filled_opt):
    """ Test the values set at construction with config provided by Supervisor. """
    assert filled_opt.software_name == 'Supvisors tests'
    assert filled_opt.software_icon == 'my_icon.png'
    assert filled_opt.supvisors_list == ['cliche01', 'cliche03', 'cliche02']
    assert filled_opt.multicast_group == ('239.0.0.1', 7777)
    assert filled_opt.multicast_interface == '192.168.1.1'
    assert filled_opt.multicast_ttl == 5
    assert filled_opt.rules_files == ['my_movies.xml']
    assert filled_opt.event_link == EventLinks.ZMQ
    assert filled_opt.event_port == 60002
    assert filled_opt.auto_fence
    assert filled_opt.synchro_timeout == 20
    assert filled_opt.inactivity_ticks == 9
    assert filled_opt.core_identifiers == {'cliche01', 'cliche03'}
    assert filled_opt.disabilities_file == '/tmp/disabilities.json'
    assert filled_opt.conciliation_strategy == ConciliationStrategies.SENICIDE
    assert filled_opt.starting_strategy == StartingStrategies.MOST_LOADED
    assert not filled_opt.host_stats_enabled
    assert filled_opt.process_stats_enabled
    assert filled_opt.collecting_period == 2.0
    assert filled_opt.stats_periods == [5, 50, 77.7]
    assert filled_opt.stats_histo == 100
    assert filled_opt.stats_irix_mode
    assert filled_opt.tail_limit == 1024 * 1024
    assert filled_opt.tailf_limit == 512


def test_str(opt):
    """ Test the string output. """
    assert str(opt) == ('software_name="" software_icon=None'
                        ' supvisors_list=None stereotypes=set()'
                        ' multicast_group=None multicast_interface=None multicast_ttl=1'
                        ' rules_files=None'
                        ' event_link=NONE event_port=0'
                        " auto_fence=False synchro_options=['TIMEOUT'] synchro_timeout=15"
                        ' inactivity_ticks=2 core_identifiers=set()'
                        ' disabilities_file=None conciliation_strategy=USER starting_strategy=CONFIG'
                        ' host_stats_enabled=True process_stats_enabled=True'
                        ' collecting_period=5 stats_periods=[10] stats_histo=200'
                        ' stats_irix_mode=False tail_limit=1024 tailf_limit=1024')


def test_filled_str(filled_opt):
    """ Test the string output. """
    variable_core_1 = "{'cliche01', 'cliche03'}"
    variable_core_2 = "{'cliche03', 'cliche01'}"
    result = str(filled_opt)
    assert any(result == ('software_name="Supvisors tests" software_icon=my_icon.png'
                          " supvisors_list=['cliche01', 'cliche03', 'cliche02']"
                          " stereotypes={'test'}"
                          ' multicast_group=239.0.0.1:7777 multicast_interface=192.168.1.1 multicast_ttl=5'
                          " rules_files=['my_movies.xml']"
                          ' event_link=ZMQ event_port=60002'
                          ' auto_fence=True'
                          " synchro_options=['LIST', 'USER'] synchro_timeout=20"
                          ' inactivity_ticks=9'
                          f' core_identifiers={var}'
                          ' disabilities_file=/tmp/disabilities.json'
                          ' conciliation_strategy=SENICIDE starting_strategy=MOST_LOADED'
                          ' host_stats_enabled=False process_stats_enabled=True'
                          ' collecting_period=2.0 stats_periods=[5.0, 50.0, 77.7] stats_histo=100'
                          ' stats_irix_mode=True tail_limit=1048576 tailf_limit=512')
               for var in [variable_core_1, variable_core_2])


def test_get_value(opt, config):
    """ Test the SupvisorsOptions.get_value method. """
    assert opt._get_value(config, 'dummy', 'anything') == 'anything'
    assert opt._get_value(config, 'event_port', 'anything') == '60002'
    assert opt._get_value(config, 'event_port', 'anything', int) == 60002
    assert opt._get_value(config, 'rules_files', 'anything', int) == 'anything'


def test_check_synchro_options(opt, config):
    """ Test the SupvisorsOptions.check_synchro_options method. """
    opt.synchro_options = [SynchronizationOptions.STRICT, SynchronizationOptions.CORE]
    assert not opt.supvisors_list
    assert not opt.core_identifiers
    # call to check_synchro_options will empty synchro_options
    with pytest.raises(ValueError):
        opt.check_synchro_options()
    # call check_synchro_options with USER and TIMEOUT
    for option in [SynchronizationOptions.USER, SynchronizationOptions.TIMEOUT]:
        opt.synchro_options = [option]
        opt.check_synchro_options()
        assert opt.synchro_options == [option]


def test_check_dirpath(opt):
    """ Minimal test of check_dirpath because mostly tested in Supervisor's existing_dirpath. """
    # existing folder
    assert opt.check_dirpath('/tmp/disabilities.json') == '/tmp/disabilities.json'
    # existing folder that can be created
    assert opt.check_dirpath('/tmp/dummy/disabilities.json') == '/tmp/dummy/disabilities.json'
    # existing folder that cannot be created
    with pytest.raises(ValueError):
        assert opt.check_dirpath('/usr/dummy/disabilities.json')


def test_to_existing_file(opt):
    """ Test the validation of file globs into an existing file. """
    # find a secure glob that would work with developer test and in Travis-CI
    base_glob = os.path.dirname(__file__)
    # test return a single value
    filepath = opt.to_existing_file(f'{base_glob}/test_options.p?')
    assert os.path.basename(filepath) == 'test_options.py'
    # test return a single value despite multiple found
    filepath = opt.to_existing_file(f'{base_glob}/*.py')
    assert os.path.basename(filepath) == '__init__.py'
    # test a glob that would not work anywhere
    filepath = opt.to_existing_file(f'*/dummy.dumb')
    assert filepath is None


def test_to_filepaths(opt):
    """ Test the validation of file globs into file paths. """
    # find a secure glob that would work with developer test and in Travis-CI
    base_glob = os.path.dirname(__file__)
    filepaths = opt.to_filepaths(f'*/*/tests/test_opt*py {base_glob}/test_options.p? %(here)s/*/test_options.py')
    assert len(filepaths) == 1
    assert os.path.basename(filepaths[0]) == 'test_options.py'
    # test a glob that would not work anywhere
    filepaths = opt.to_filepaths(f'*/dummy.dumb')
    assert len(filepaths) == 0


common_error_message = r'invalid value for {}'


def test_check_multicast_address():
    """ Test the checking of a multicast address. """
    error_message = common_error_message.format('multicast address')
    # test invalid values
    with pytest.raises(ValueError, match=error_message):
        SupvisorsOptions._check_multicast_address('')
    with pytest.raises(ValueError, match=error_message):
        SupvisorsOptions._check_multicast_address('127.0.0.1')
    with pytest.raises(ValueError, match=error_message):
        SupvisorsOptions._check_multicast_address('192.168.12.4')
    with pytest.raises(ValueError, match=error_message):
        SupvisorsOptions._check_multicast_address('10.0.0.4')
    with pytest.raises(ValueError, match=error_message):
        SupvisorsOptions._check_multicast_address('240.256.0.1')
    with pytest.raises(ValueError, match=error_message):
        SupvisorsOptions._check_multicast_address('240..0.1')
    with pytest.raises(ValueError, match=error_message):
        SupvisorsOptions._check_multicast_address('240.0.1')
    # test reserved addresses
    for addr in SupvisorsOptions.RESERVED_MULTICAST_ADDRESSES:
        with pytest.raises(ValueError, match='reserved multicast address'):
            SupvisorsOptions._check_multicast_address(addr)
    # test valid values
    SupvisorsOptions._check_multicast_address('224.0.0.1')
    SupvisorsOptions._check_multicast_address('239.255.255.255')
    SupvisorsOptions._check_multicast_address('239.0.0.1')


def test_ip_address():
    """ Test the validity of an IP address. """
    error_message = common_error_message.format('IP address')
    # test invalid values
    with pytest.raises(ValueError, match=error_message):
        SupvisorsOptions.to_ip_address('dummy')
    with pytest.raises(ValueError, match=error_message):
        SupvisorsOptions.to_ip_address('7777')
    with pytest.raises(ValueError, match=error_message):
        SupvisorsOptions.to_ip_address('240.256.0.1')
    with pytest.raises(ValueError, match=error_message):
        SupvisorsOptions.to_ip_address('240..0.1')
    with pytest.raises(ValueError, match=error_message):
        SupvisorsOptions.to_ip_address('240.0.1')
    # test valid values
    assert SupvisorsOptions.to_ip_address('ANY') is None
    assert SupvisorsOptions.to_ip_address('INADDR_ANY') is None
    assert SupvisorsOptions.to_ip_address('10.0.0.1') == '10.0.0.1'
    assert SupvisorsOptions.to_ip_address('192.168.10.5') == '192.168.10.5'


def test_multicast_group():
    """ Test the conversion into to a valid multicast group. """
    error_message = common_error_message.format('multicast_group')
    # test invalid values
    with pytest.raises(ValueError, match=error_message):
        SupvisorsOptions.to_multicast_group('239.0.0.1')
    with pytest.raises(ValueError, match=error_message):
        SupvisorsOptions.to_multicast_group('7777')
    # test valid values
    assert SupvisorsOptions.to_multicast_group('239.0.0.1:7777') == ('239.0.0.1', 7777)


def test_ttl():
    """ Test the conversion into to a TTL number. """
    error_message = common_error_message.format('multicast_ttl')
    # test invalid values
    with pytest.raises(ValueError, match=error_message):
        SupvisorsOptions.to_ttl('-1')
    with pytest.raises(ValueError, match=error_message):
        SupvisorsOptions.to_ttl('256')
    # test valid values
    assert SupvisorsOptions.to_ttl('0') == 0
    assert SupvisorsOptions.to_ttl('1') == 1
    assert SupvisorsOptions.to_ttl('255') == 255


def test_port_num():
    """ Test the conversion into to a port number. """
    error_message = common_error_message.format('port')
    # test invalid values
    with pytest.raises(ValueError, match=error_message):
        SupvisorsOptions.to_port_num('-1')
    with pytest.raises(ValueError, match=error_message):
        SupvisorsOptions.to_port_num('0')
    with pytest.raises(ValueError, match=error_message):
        SupvisorsOptions.to_port_num('65536')
    # test valid values
    assert SupvisorsOptions.to_port_num('1') == 1
    assert SupvisorsOptions.to_port_num('65535') == 65535


def test_to_synchro_options():
    """ Test the conversion of a string to a list of SynchronizationOptions. """
    error_message = common_error_message.format('synchro_options')
    # test invalid values
    with pytest.raises(ValueError, match=error_message):
        SupvisorsOptions.to_synchro_options('dummy')
    with pytest.raises(ValueError, match=error_message):
        SupvisorsOptions.to_synchro_options('time,TIMEOUT')
    with pytest.raises(ValueError, match=error_message):
        SupvisorsOptions.to_synchro_options('user-core')
    # test valid values
    assert SupvisorsOptions.to_synchro_options('strict,list,timeout,core,user') == [x for x in SynchronizationOptions]
    assert SupvisorsOptions.to_synchro_options('  user, , liST,  USER,') == [SynchronizationOptions.USER,
                                                                             SynchronizationOptions.LIST]
    assert SupvisorsOptions.to_synchro_options('CoRe') == [SynchronizationOptions.CORE]


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


def test_to_ticks():
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


def test_to_event_link():
    """ Test the conversion of a string to a number of ticks. """
    error_message = common_error_message.format('event_link')
    # test invalid values
    with pytest.raises(ValueError, match=error_message):
        SupvisorsOptions.to_event_link('http')
    # test valid values
    assert SupvisorsOptions.to_event_link('none') == EventLinks.NONE
    assert SupvisorsOptions.to_event_link('None') == EventLinks.NONE
    assert SupvisorsOptions.to_event_link('zmq') == EventLinks.ZMQ
    assert SupvisorsOptions.to_event_link('ZMQ') == EventLinks.ZMQ


def test_conciliation_strategy():
    """ Test the conversion of a string to a conciliation strategy. """
    error_message = common_error_message.format('conciliation_strategy')
    # test invalid values
    with pytest.raises(ValueError, match=error_message):
        SupvisorsOptions.to_conciliation_strategy('123456')
    with pytest.raises(ValueError, match=error_message):
        SupvisorsOptions.to_conciliation_strategy('dummy')
    with pytest.raises(ValueError, match=error_message):
        SupvisorsOptions.to_conciliation_strategy('users')
    # test valid values
    assert SupvisorsOptions.to_conciliation_strategy('SENICIDE') == ConciliationStrategies.SENICIDE
    assert SupvisorsOptions.to_conciliation_strategy('INFANTICIDE') == ConciliationStrategies.INFANTICIDE
    assert SupvisorsOptions.to_conciliation_strategy('USER') == ConciliationStrategies.USER
    assert SupvisorsOptions.to_conciliation_strategy('user') == ConciliationStrategies.USER
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
        SupvisorsOptions.to_starting_strategy('configs')
    # test valid values
    assert SupvisorsOptions.to_starting_strategy('config') == StartingStrategies.CONFIG
    assert SupvisorsOptions.to_starting_strategy('CONFIG') == StartingStrategies.CONFIG
    assert SupvisorsOptions.to_starting_strategy('LESS_LOADED') == StartingStrategies.LESS_LOADED
    assert SupvisorsOptions.to_starting_strategy('MOST_LOADED') == StartingStrategies.MOST_LOADED


def test_statistics_type():
    """ Test the conversion of a string to a pair of booleans for host and process statistics. """
    error_message = common_error_message.format('stats_enabled')
    # test invalid values
    with pytest.raises(ValueError, match=error_message):
        SupvisorsOptions.to_statistics_type('')
    with pytest.raises(ValueError, match=error_message):
        SupvisorsOptions.to_statistics_type('activated')
    with pytest.raises(ValueError, match=error_message):
        SupvisorsOptions.to_statistics_type('1,both')
    # test valid values
    assert SupvisorsOptions.to_statistics_type('OFF') == (False, False)
    assert SupvisorsOptions.to_statistics_type('HOST') == (True, False)
    assert SupvisorsOptions.to_statistics_type('PROCESS') == (False, True)
    assert SupvisorsOptions.to_statistics_type('ALL') == (True, True)
    assert SupvisorsOptions.to_statistics_type('HOST, PROCESS') == (True, True)
    assert SupvisorsOptions.to_statistics_type('true, PROCESS') == (True, True)
    assert SupvisorsOptions.to_statistics_type('OFF, host') == (True, False)
    assert SupvisorsOptions.to_statistics_type('False, process, 0') == (False, True)


def test_period():
    """ Test the conversion of a string to a collecting period. """
    error_message = common_error_message.format('stats_collecting_period')
    # test invalid values
    with pytest.raises(ValueError, match=error_message):
        SupvisorsOptions.to_period('')
    with pytest.raises(ValueError, match=error_message):
        SupvisorsOptions.to_period('0.9,3600')
    with pytest.raises(ValueError, match=error_message):
        SupvisorsOptions.to_period('dummy')
    with pytest.raises(ValueError, match=error_message):
        SupvisorsOptions.to_period('0')
    with pytest.raises(ValueError, match=error_message):
        SupvisorsOptions.to_period('3601')
    # test valid values
    assert SupvisorsOptions.to_period('5') == 5
    assert SupvisorsOptions.to_period('3.3') == 3.3
    assert SupvisorsOptions.to_period('99.99') == 99.99


def test_periods():
    """ Test the conversion of a string to a list of periods. """
    error_message = common_error_message.format('stats_periods')
    # test invalid values
    with pytest.raises(ValueError, match='unexpected number of stats_periods: 0. minimum is 1'):
        SupvisorsOptions.to_periods('')
    with pytest.raises(ValueError, match='unexpected number of stats_periods: 4. maximum is 3'):
        SupvisorsOptions.to_periods('1, 2, 3, 4')
    with pytest.raises(ValueError, match=error_message):
        SupvisorsOptions.to_periods('0.9,3600')
    with pytest.raises(ValueError, match=error_message):
        SupvisorsOptions.to_periods('1,3600.1')
    with pytest.raises(ValueError, match=error_message):
        SupvisorsOptions.to_periods('90, none')
    # test valid values
    assert SupvisorsOptions.to_periods('5') == [5]
    assert SupvisorsOptions.to_periods('3.3') == [3.3]
    assert SupvisorsOptions.to_periods('60,3600') == [60, 3600]
    assert SupvisorsOptions.to_periods('1.0, 3599') == [1.0, 3599]
    assert SupvisorsOptions.to_periods('720, 120,1234.56') == [120, 720, 1234.56]


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


def test_server_options_disabilities(mocker, supvisors, server_opt):
    """ Test the SupvisorsServerOptions disabilities management. """
    # patch open
    mocked_open = mocker.patch('builtins.open', mocker.mock_open())
    # read_disabilities has already been called once in the constructor based on a non-existing file
    assert server_opt.disabilities == {}
    # disable program
    server_opt.disable_program('program_1')
    mocked_open.assert_called_once_with(supvisors.options.disabilities_file, 'w+')
    handle = mocked_open()
    json_expected = '{"program_1": true}'
    assert handle.write.call_args_list == [call(json_expected)]
    handle.reset_mock()
    mocked_open.reset_mock()
    # enable program
    server_opt.enable_program('program_2')
    mocked_open.assert_called_once_with(supvisors.options.disabilities_file, 'w+')
    json_expected = '{"program_1": true, "program_2": false}'
    assert handle.write.call_args_list == [call(json_expected)]
    handle.reset_mock()
    mocked_open.reset_mock()
    # check when write is not forced and file does not exist
    mocked_isfile = mocker.patch('os.path.isfile', return_value=False)
    server_opt.write_disabilities()
    assert handle.write.call_args_list == [call(json_expected)]
    handle.reset_mock()
    # empty context and read
    mocked_open = mocker.patch('builtins.open', mocker.mock_open(read_data=json_expected))
    mocker.patch('os.path.isfile', return_value=True)
    server_opt.disabilities = {}
    server_opt.read_disabilities()
    assert server_opt.disabilities == {'program_1': True, 'program_2': False}
    mocked_open.assert_called_once_with(supvisors.options.disabilities_file)
    handle = mocked_open()
    assert handle.read.call_args_list == [call()]
    # test with disabilities files not set
    supvisors.options.disabilities_file = None
    server_opt.disabilities = {}
    server_opt.read_disabilities()
    assert server_opt.disabilities == {}


def check_program_config(program_config: ProgramConfig, result: Payload):
    """ Compare the ProgramConfig to a result payload. """
    assert result['name'] == program_config.name
    assert result['klass'] is program_config.klass
    assert result['numprocs'] == program_config.numprocs
    assert result['disabled'] == program_config.disabled
    # only one group in all results
    assert len(program_config.group_config_info) == 1
    group_name, process_config_list = next(iter(program_config.group_config_info.items()))
    assert result['group_config_info'] == {group_name: [x.name for x in process_config_list]}


def check_process_config(process_config: SupvisorsProcessConfig, result: Payload):
    """ Compare the SupvisorsProcessConfig to a result payload. """
    assert result['process_index'] == process_config.process_index
    assert result['command_ref'] == process_config.command_ref
    assert result['program_config'] is process_config.program_config


def test_server_options(mocker, server_opt):
    """ Test that the internal numbers of homogeneous programs are stored.
    WARN: All in one test because it doesn't work when create_server is called twice.
    """
    # test attributes
    assert server_opt.parser is None
    assert server_opt.program_configs == {}
    assert server_opt.process_configs == {}
    # call realize
    server = create_server(mocker, server_opt, ProgramConfiguration)
    # check program configurations
    assert sorted(server_opt.program_configs.keys()) == ['dumber', 'dummies', 'dummy', 'dummy_ears']
    expected = {'name': 'dumber', 'klass': FastCGIProcessConfig, 'numprocs': 2, 'disabled': False,
                'group_config_info': {'dumber': ['dumber_10', 'dumber_11']}}
    check_program_config(server_opt.program_configs['dumber'], expected)
    expected = {'name': 'dummies', 'klass': ProcessConfig, 'numprocs': 3, 'disabled': False,
                'group_config_info': {'dummy_group': ['dummy_0', 'dummy_1', 'dummy_2']}}
    check_program_config(server_opt.program_configs['dummies'], expected)
    expected = {'name': 'dummy', 'klass': ProcessConfig, 'numprocs': 1, 'disabled': False,
                'group_config_info': {'dummy_group': ['dummy']}}
    check_program_config(server_opt.program_configs['dummy'], expected)
    expected = {'name': 'dummy_ears', 'klass': EventListenerConfig, 'numprocs': 2, 'disabled': False,
                'group_config_info': {'dummy_ears': ['dummy_ears_20', 'dummy_ears_21']}}
    check_program_config(server_opt.program_configs['dummy_ears'], expected)
    # check process configurations
    assert sorted(server_opt.process_configs.keys()) == ['dumber_10', 'dumber_11', 'dummy',
                                                         'dummy_0', 'dummy_1', 'dummy_2',
                                                         'dummy_ears_20', 'dummy_ears_21']
    expected = {'process_index': 0, 'command_ref': 'ls',
                'program_config': server_opt.program_configs['dumber']}
    check_process_config(server_opt.process_configs['dumber_10'], expected)
    expected = {'process_index': 1, 'command_ref': 'ls',
                'program_config': server_opt.program_configs['dumber']}
    check_process_config(server_opt.process_configs['dumber_11'], expected)
    expected = {'process_index': 0, 'command_ref': 'ls',
                'program_config': server_opt.program_configs['dummy']}
    check_process_config(server_opt.process_configs['dummy'], expected)
    expected = {'process_index': 0, 'command_ref': 'ls',
                'program_config': server_opt.program_configs['dummies']}
    check_process_config(server_opt.process_configs['dummy_0'], expected)
    expected = {'process_index': 1, 'command_ref': 'ls',
                'program_config': server_opt.program_configs['dummies']}
    check_process_config(server_opt.process_configs['dummy_1'], expected)
    expected = {'process_index': 2, 'command_ref': 'ls',
                'program_config': server_opt.program_configs['dummies']}
    check_process_config(server_opt.process_configs['dummy_2'], expected)
    expected = {'process_index': 0, 'command_ref': 'ls',
                'program_config': server_opt.program_configs['dummy_ears']}
    check_process_config(server_opt.process_configs['dummy_ears_20'], expected)
    expected = {'process_index': 1, 'command_ref': 'ls',
                'program_config': server_opt.program_configs['dummy_ears']}
    check_process_config(server_opt.process_configs['dummy_ears_21'], expected)
    # check sub-processes
    assert server_opt.get_subprocesses('dumber') == ['dumber:dumber_10', 'dumber:dumber_11']
    assert server_opt.get_subprocesses('dummies') == ['dummy_group:dummy_0', 'dummy_group:dummy_1',
                                                      'dummy_group:dummy_2']
    assert server_opt.get_subprocesses('dummy') == ['dummy_group:dummy']
    assert server_opt.get_subprocesses('dummy_ears') == ['dummy_ears:dummy_ears_20', 'dummy_ears:dummy_ears_21']
    # udpate procnums of a program
    result = server.update_numprocs('dummies', 1)
    assert server.parser['program:dummies']['numprocs'] == '1'
    assert sorted(result.keys()) == ['dummy_group']
    assert len(result['dummy_group']) == 1
    assert result['dummy_group'][0].name == 'dummy_0'
    expected = {'name': 'dummies', 'klass': ProcessConfig, 'numprocs': 1, 'disabled': False,
                'group_config_info': {'dummy_group': ['dummy_0']}}
    check_program_config(server_opt.program_configs['dummies'], expected)
    assert result['dummy_group'] == server_opt.program_configs['dummies'].group_config_info['dummy_group']
    expected = {'process_index': 0, 'command_ref': 'ls',
                'program_config': server_opt.program_configs['dummies']}
    check_process_config(server_opt.process_configs['dummy_0'], expected)
    assert 'dummy_1' not in server_opt.process_configs
    assert 'dummy_2' not in server_opt.process_configs
    assert server_opt.get_subprocesses('dummies') == ['dummy_group:dummy_0']
    # udpate procnums of a FastCGI program
    result = server.update_numprocs('dumber', 1)
    assert server.parser['fcgi-program:dumber']['numprocs'] == '1'
    assert sorted(result.keys()) == ['dumber']
    assert len(result['dumber']) == 1
    assert result['dumber'][0].name == 'dumber_10'
    expected = {'name': 'dumber', 'klass': FastCGIProcessConfig, 'numprocs': 1, 'disabled': False,
                'group_config_info': {'dumber': ['dumber_10']}}
    check_program_config(server_opt.program_configs['dumber'], expected)
    assert result['dumber'] == server_opt.program_configs['dumber'].group_config_info['dumber']
    expected = {'process_index': 0, 'command_ref': 'ls',
                'program_config': server_opt.program_configs['dumber']}
    check_process_config(server_opt.process_configs['dumber_10'], expected)
    assert 'dumber_11' not in server_opt.process_configs
    assert server_opt.get_subprocesses('dumber') == ['dumber:dumber_10']
    # udpate procnums of an event listener
    result = server.update_numprocs('dummy_ears', 3)
    assert server.parser['eventlistener:dummy_ears']['numprocs'] == '3'
    assert sorted(result.keys()) == ['dummy_ears']
    assert len(result['dummy_ears']) == 3
    assert result['dummy_ears'][0].name == 'dummy_ears_20'
    assert result['dummy_ears'][1].name == 'dummy_ears_21'
    assert result['dummy_ears'][2].name == 'dummy_ears_22'
    expected = {'name': 'dummy_ears', 'klass': EventListenerConfig, 'numprocs': 3, 'disabled': False,
                'group_config_info': {'dummy_ears': ['dummy_ears_20', 'dummy_ears_21', 'dummy_ears_22']}}
    check_program_config(server_opt.program_configs['dummy_ears'], expected)
    assert result['dummy_ears'] == server_opt.program_configs['dummy_ears'].group_config_info['dummy_ears']
    expected = {'process_index': 0, 'command_ref': 'ls',
                'program_config': server_opt.program_configs['dummy_ears']}
    check_process_config(server_opt.process_configs['dummy_ears_20'], expected)
    expected = {'process_index': 1, 'command_ref': 'ls',
                'program_config': server_opt.program_configs['dummy_ears']}
    check_process_config(server_opt.process_configs['dummy_ears_21'], expected)
    expected = {'process_index': 2, 'command_ref': 'ls',
                'program_config': server_opt.program_configs['dummy_ears']}
    check_process_config(server_opt.process_configs['dummy_ears_22'], expected)
    assert server_opt.get_subprocesses('dummy_ears') == ['dummy_ears:dummy_ears_20', 'dummy_ears:dummy_ears_21',
                                                         'dummy_ears:dummy_ears_22']
