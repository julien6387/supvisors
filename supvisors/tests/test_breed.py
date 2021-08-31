#!/usr/bin/python
# -*- coding: utf-8 -*-

# ======================================================================
# Copyright 2016 Julien LE CLEACH
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

from argparse import Namespace
from unittest.mock import call, mock_open, Mock

from supvisors.tools.breed import *


def test_is_folder():
    """ Test the is_folder function. """
    arg_parser = Mock()
    # test with filename
    assert is_folder(arg_parser, __file__) == __file__
    assert arg_parser.error.call_args_list == [call('The folder "%s" does not exist' % __file__)]
    arg_parser.error.reset_mock()
    # test with wrong folder
    assert is_folder(arg_parser, '/dummy_folder') == '/dummy_folder'
    assert arg_parser.error.call_args_list == [call('The folder "/dummy_folder" does not exist')]
    arg_parser.error.reset_mock()
    # test with correct folder
    assert is_folder(arg_parser, '.') == '.'
    assert not arg_parser.error.called


def test_key_value():
    """ Test the KeyValue class. """
    arg_parser, namespace = Mock(), Mock()
    # test with wrong format
    action = KeyValue('', 'destination')
    with pytest.raises(ValueError):
        action(arg_parser, namespace, ['dummy'])
    assert arg_parser.error.call_args_list == [call('breed format must be: key=value')]
    assert namespace.destination == {}
    arg_parser.error.reset_mock()
    # test with wrong value
    with pytest.raises(ValueError):
        action(arg_parser, namespace, ['dummy=action'])
    assert arg_parser.error.call_args_list == [call('breed value must be an integer')]
    assert namespace.destination == {}
    arg_parser.error.reset_mock()
    # test with correct format and too low value
    action(arg_parser, namespace, ['dummy=0'])
    assert arg_parser.error.call_args_list == [call('breed value must be strictly positive')]
    assert namespace.destination == {'dummy': 0}
    arg_parser.error.reset_mock()
    # test with correct format and value
    action(arg_parser, namespace, ['dummy=2'])
    assert not arg_parser.error.called
    assert namespace.destination == {'dummy': 2}


def test_breed_creation():
    """ Test the Breed.__init__ method. """
    # test with default value
    breed = Breed()
    assert not breed.verbose
    assert breed.config_map == {}
    assert breed.config_files == {}
    # test with verbose
    breed = Breed(True)
    assert breed.verbose
    assert breed.config_map == {}
    assert breed.config_files == {}


def test_read_config_files(mocker):
    """ Test the Breed.read_config_files method. """
    mocked_path = Mock(**{'glob.return_value': ['file_1', 'file_2']})
    mocked_config = Mock(**{'sections.side_effect': [('group:file_1_A', 'file_1_B'), ('group:file_2_A', )]})
    mocker.patch('supvisors.tools.breed.Path', return_value=mocked_path)
    mocker.patch('supvisors.tools.breed.ConfigParser', return_value=mocked_config)
    mocker.patch('builtins.print')
    # test call
    breed = Breed(True)
    breed.read_config_files('/dummy_folder')
    assert list(breed.config_files.keys()) == ['file_1', 'file_2']
    assert all(config is mocked_config for config in breed.config_files.values())
    assert list(breed.config_map.keys()) == ['group:file_1_A', 'group:file_2_A']
    assert all(config is mocked_config for config in breed.config_map.values())
    # don't test print outputs


def test_write_config_files(mocker):
    """ Test the Breed.write_config_files method. """
    mocked_config = Mock(**{'sections.side_effect': [['file_1_A', 'file_1_B'], []]})
    mocked_dirs = mocker.patch('os.makedirs')
    mocked_file = mock_open()
    mocker.patch('builtins.open', mocked_file)
    mocker.patch('builtins.print')
    # test call
    breed = Breed(True)
    breed.config_files = {'etc/file_1': mocked_config, 'etc/dummy/file_2': mocked_config}
    breed.write_config_files('/dummy_folder')
    assert mocked_dirs.call_args_list == [call('/dummy_folder/etc', exist_ok=True)]
    assert mocked_config.write.call_args_list == [call(mocked_file())]


def test_breed_groups(mocker):
    """ Test the Breed.breed_groups method. """
    ref_config = {'group:dummy_appli': {'programs': 'program_1,program_2'}}
    new_config = {}
    mocked_create = mocker.patch('supvisors.tools.breed.Breed.create_new_parser', return_value=new_config)
    mocker.patch('builtins.print')
    # test call with unknown group
    template_groups = {'group:dummy': 2}
    breed = Breed(True)
    breed.config_map = {'group:dummy_appli': ref_config}
    breed.breed_groups(template_groups, False)
    assert not mocked_create.called
    # test call with same files
    template_groups = {'group:dummy_appli': 2}
    breed = Breed(True)
    breed.config_map = {'group:dummy_appli': ref_config}
    breed.breed_groups(template_groups, False)
    assert not mocked_create.called
    assert ref_config == {'group:dummy_appli_01': {'programs': 'program_1,program_2'},
                          'group:dummy_appli_02': {'programs': 'program_1,program_2'}}
    assert new_config == {}
    assert breed.config_map == {'group:dummy_appli': ref_config}
    # test call with new files
    ref_config = {'group:dummy_appli': {'programs': 'program_1,program_2'}}
    template_groups = {'group:dummy_appli': 2}
    breed = Breed(True)
    breed.config_map = {'group:dummy_appli': ref_config}
    breed.breed_groups(template_groups, True)
    assert mocked_create.call_args_list == [call('group:dummy_appli_01', ref_config),
                                            call('group:dummy_appli_02', ref_config)]
    assert ref_config == {}
    assert new_config == {'group:dummy_appli_01': {'programs': 'program_1,program_2'},
                          'group:dummy_appli_02': {'programs': 'program_1,program_2'}}
    assert breed.config_map == {'group:dummy_appli': {}}


def test_create_new_parser(mocker):
    """ Test the Breed.create_new_parser method. """
    mocked_ref1_config, mocked_ref2_config = Mock(), Mock()
    mocked_config = Mock()
    mocker.patch('supvisors.tools.breed.ConfigParser', return_value=mocked_config)
    mocker.patch('builtins.print')
    # test call
    breed = Breed(True)
    breed.config_files = {'etc/file_1': mocked_ref1_config, 'etc/dummy/file_2': mocked_ref2_config}
    assert breed.create_new_parser('program:file_2_A', mocked_ref2_config) == mocked_config
    assert breed.config_map == {'program:file_2_A': mocked_config}
    assert breed.config_files == {'etc/file_1': mocked_ref1_config, 'etc/dummy/file_2': mocked_ref2_config,
                                  Path('etc/dummy/program_file_2_A.ini'): mocked_config}


def test_parse_args(mocker):
    """ Test the parse_args function. """
    mocker.patch('sys.stderr')
    # test errors
    mocked_folder = mocker.patch('supvisors.tools.breed.is_folder', return_value=False)
    # test missing parameters
    with pytest.raises(SystemExit):
        parse_args(['-v'])
    # test missing template parameters
    with pytest.raises(SystemExit):
        parse_args(['-t', '-d', 'etc', '-b', 'key=value'])
    # test non-folder template parameters
    with pytest.raises(SystemExit):
        parse_args(['-t', 'template_etc', '-d', 'etc', '-b', 'key=value'])
    # test missing destination parameters
    mocked_folder.return_value = 'template_etc'
    with pytest.raises(SystemExit):
        parse_args(['-t', 'template_etc', '-d', '-b', 'key=value'])
    # test missing breed parameters
    with pytest.raises(SystemExit):
        parse_args(['-t', 'template_etc', '-d', 'etc', '-b'])
    # test incorrect breed parameters (no value)
    with pytest.raises(SystemExit):
        parse_args(['-t', 'template_etc', '-d', 'etc', '-b', 'dummy'])
    # test incorrect breed parameters (wrong value)
    with pytest.raises(SystemExit):
        parse_args(['-t', 'template_etc', '-d', 'etc', '-b', 'dummy=appli'])
    # test incorrect breed parameters (too low value)
    with pytest.raises(SystemExit):
        parse_args(['-t', 'template_etc', '-d', 'etc', '-b', 'dummy=0'])
    # test correct command line with defaults
    expected = Namespace(template='template_etc', pattern='**/*.ini', destination='etc', breed={'dummy': 1},
                         extra=False, verbose=False)
    assert parse_args(['-t', 'template_etc', '-d', 'etc', '-b', 'dummy=1']) == expected
    # test correct command line with all arguments set
    expected = Namespace(template='template_etc', pattern='etc/*', destination='etc', breed={'dummy': 1, 'appli': 2},
                         extra=True, verbose=True)
    assert parse_args(['-t', 'template_etc', '-p', 'etc/*', '-d', 'etc', '-b', 'dummy=1', 'appli=2',
                       '-x', '-v']) == expected


def test_main(mocker):
    """ Test the main function. """
    mocker.patch('builtins.print')
    mocked_chdir = mocker.patch('os.chdir')
    namespace = Namespace(template='template_etc', pattern='etc/*', destination='etc', breed={'dummy': 1, 'appli': 2},
                          extra=True, verbose=True)
    mocker.patch('supvisors.tools.breed.parse_args', return_value=namespace)
    mocked_breed = Mock(config_files={}, spec=Breed)
    mocked_breed.breed_groups.return_value = ['program_1', 'program_2']
    mocker.patch('supvisors.tools.breed.Breed', return_value=mocked_breed)
    # test call with no files found
    with pytest.raises(SystemExit):
        main()
    assert mocked_chdir.call_args_list == [call('template_etc')]
    assert mocked_breed.read_config_files.call_args_list == [call('etc/*')]
    assert not mocked_breed.breed_groups.called
    assert not mocked_breed.write_config_files.called
    mocked_chdir.reset_mock()
    mocked_breed.read_config_files.reset_mock()
    # test call with no files found
    mocked_breed.config_files = {'some file': 'some config'}
    main()
    assert mocked_chdir.call_args_list == [call('template_etc'), call(os.getcwd())]
    assert mocked_breed.read_config_files.call_args_list == [call('etc/*')]
    assert mocked_breed.breed_groups.call_args_list == [call({'group:dummy': 1, 'group:appli': 2}, True)]
    assert mocked_breed.write_config_files.call_args_list == [call('etc')]
