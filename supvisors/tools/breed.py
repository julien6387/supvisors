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

import os
import sys

from argparse import Action, ArgumentParser
from configparser import ConfigParser
from pathlib import Path
from typing import Dict, Mapping, Sequence, Tuple

# annotation types
TemplateGroups = Mapping[str, int]
TemplatePrograms = Mapping[str, Sequence[str]]
SectionConfigMap = Dict[str, ConfigParser]
FileConfigMap = Dict[Path, ConfigParser]

# verbosity global variable
VERBOSE = False


def read_config_files(file_pattern: str) -> Tuple[SectionConfigMap, FileConfigMap]:
    """ Get all configuration files and create a parser for each of them.

    :param file_pattern: the filepath pattern to search for config files from the current working directory
    :return: the parsers grouped by section names and by file names
    """
    parser_map, parser_files = {}, {}
    for filename in Path('.').glob(file_pattern):
        config = ConfigParser(interpolation=None)
        config.read(filename)
        parser_files[filename] = config
        for section in config.sections():
            parser_map[section] = config
    return parser_map, parser_files


def write_config_files(dst_folder: str, parser_files: FileConfigMap) -> None:
    """ Write the contents of the parsers in new config files.

    :param dst_folder: the destination folder
    :param parser_files: the parsers to write, identified by their original file name
    :return: None
    """
    for filename, config in parser_files.items():
        filepath = os.path.join(dst_folder, filename)
        if VERBOSE:
            print('Writing file: {}'.format(filepath))
        # create path if it doesn't exist
        folder_name = os.path.dirname(filepath)
        os.makedirs(folder_name, exist_ok=True)
        # write new config file from parser
        with open(filepath, 'w') as configfile:
            config.write(configfile)


def breed_groups(parsers, template_groups: TemplateGroups) -> TemplatePrograms:
    """ Find template groups in config files and replace them by X versions of the group.
    Return the template programs that have to be multiplied.

    :param parsers: all the config parsers found
    :param template_groups: the template groups
    :return: the template programs
    """
    template_programs = {}
    for group, cardinality in template_groups.items():
        if group in parsers:
            config = parsers[group]
            programs = config[group]['programs'].split(',')
            # duplicate and update <cardinality> versions of the group
            for idx in range(1, cardinality + 1):
                new_section = group + '_%02d' % idx
                new_programs = [program + '_%02d' % idx for program in programs]
                config[new_section] = {'programs': ','.join(new_programs)}
                if VERBOSE:
                    print('New [{}]'.format(new_section))
                    print('\tprograms={}'.format(','.join(new_programs)))
                for program in programs:
                    template_programs.setdefault('program:' + program, []).append(program + '_%02d' % idx)
            # remove template
            del config[group]
    return template_programs


def breed_programs(parsers, template_programs: TemplatePrograms) -> None:
    """ Find template programs in config files and replace them by X versions of the program.

    :param parsers: all the config parsers found
    :param template_programs: the template programs
    :return: None
    """
    for program, new_programs in template_programs.items():
        if program in parsers:
            config = parsers[program]
            # duplicate and update X versions of the program
            # at the end, remove template
            for new_program in new_programs:
                # copy template section to new_section
                new_section = 'program:' + new_program
                config[new_section] = config[program]
            # remove template
            del config[program]


class KeyValue(Action):

    def __call__(self, arg_parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, {})
        for value in values:
            if '=' not in value:
                arg_parser.error('breed format must be: key=value')
            key, value = value.split('=')
            if not value.isdigit():
                arg_parser.error('breed value must be an integer')
            getattr(namespace, self.dest)[key] = int(value)


def is_folder(arg_parser, arg):
    if not os.path.isdir(arg):
        arg_parser.error('The folder "%s" does not exist' % arg)
    return arg


if __name__ == '__main__':
    """ Create X definitions of group and programs based on group/program template.
    This is typically useful when an application could be started X times.
    As there's no concept of homogeneous group in Supervisor, this script duplicates X times the definition of a group
    and its related programs and removes the original definition.
    The resulting configuration files are written to a separate folder.
    """
    # get arguments
    parser = ArgumentParser(description='Duplicate the application definitions')
    parser.add_argument('-t', '--template', type=lambda x: is_folder(parser, x), required=True,
                        help='the template folder')
    parser.add_argument('-p', '--pattern', type=str, default='**/*.ini',
                        help='the search pattern from the template folder')
    parser.add_argument('-d', '--destination', type=str, required=True, help='the destination folder')
    parser.add_argument('-b', '--breed', metavar='app=nb', action=KeyValue, nargs='+',
                        help='the applications to breed')
    parser.add_argument('-v', '--verbose', action='store_true', help='activate logs')
    args = parser.parse_args()
    # set verbosity global variable
    VERBOSE = args.verbose
    if VERBOSE:
        print('ArgumentParser: {}'.format(args))
    # change working directory
    ref_directory = os.getcwd()
    os.chdir(args.template)
    # get one parser per template file
    config_map, config_files = read_config_files(args.pattern)
    if VERBOSE:
        print('Configuration files found:\n\t{}'
              .format('\n\t'.join([str(file) for file in config_files])))
        print('Template elements found:\n\t{}'
              .format('\n\t'.join(config_map.keys())))
    if not len(config_files):
        print('No configuration files found')
        sys.exit(0)
    # update all groups configurations
    group_breed = {'group:' + key: value for key, value in args.breed.items()}
    program_breed = breed_groups(config_map, group_breed)
    # update program configurations found in groups
    breed_programs(config_map, program_breed)
    # back to previous directory and write files
    os.chdir(ref_directory)
    write_config_files(args.destination, config_files)
