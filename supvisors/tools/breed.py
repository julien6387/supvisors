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


def is_folder(arg_parser, arg):
    """

    :param arg_parser:
    :param arg:
    :return:
    """
    if not os.path.isdir(arg):
        arg_parser.error('The folder "%s" does not exist' % arg)
    return arg


class KeyValue(Action):
    """ Simple action to manage key / value pairs. """

    def __call__(self, arg_parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, {})
        for value in values:
            if '=' not in value:
                arg_parser.error('breed format must be: key=value')
            key, value = value.split('=')
            if not value.isdigit():
                arg_parser.error('breed value must be an integer')
            getattr(namespace, self.dest)[key] = int(value)


class Breed(object):
    """ Create X definitions of group and programs based on group/program template.
    This is typically useful when an application could be started X times.
    As there's no concept of homogeneous group in Supervisor, this script duplicates X times the definition of a group
    and its related programs and removes the original definition.
    The resulting configuration files are written to a separate folder.
    """

    # annotation types
    TemplateGroups = Mapping[str, int]
    TemplatePrograms = Mapping[str, Sequence[str]]
    SectionConfigMap = Dict[str, ConfigParser]
    FileConfigMap = Dict[Path, ConfigParser]

    # verbosity global variable
    VERBOSE = False

    def __init__(self, verbose: bool = False):
        """ Initialization of the attributes. """
        self.verbose = verbose
        self.config_map: Breed.SectionConfigMap = {}
        self.config_files: Breed.FileConfigMap = {}

    def read_config_files(self, file_pattern: str):
        """ Get all configuration files and create a parser for each of them.

        :param file_pattern: the filepath pattern to search for config files from the current working directory
        :return: None
        """
        for filename in Path('.').glob(file_pattern):
            config = ConfigParser(interpolation=None)
            config.read(filename)
            self.config_files[filename] = config
            for section in config.sections():
                self.config_map[section] = config
        if self.verbose:
            print('Configuration files found:\n\t{}'.format('\n\t'.join([str(file) for file in self.config_files])))
            print('Template elements found:\n\t{}'.format('\n\t'.join(self.config_map.keys())))

    def write_config_files(self, dst_folder: str) -> None:
        """ Write the contents of the parsers in new config files.

        :param dst_folder: the destination folder
        :return: None
        """
        for filename, config in self.config_files.items():
            filepath = os.path.join(dst_folder, filename)
            if self.verbose:
                print('Writing file: {}'.format(filepath))
            # create path if it doesn't exist
            folder_name = os.path.dirname(filepath)
            os.makedirs(folder_name, exist_ok=True)
            # write new config file from parser
            with open(filepath, 'w') as configfile:
                config.write(configfile)

    def breed_groups(self, parsers, template_groups: TemplateGroups) -> TemplatePrograms:
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
                    if self.verbose:
                        print('New [{}]'.format(new_section))
                        print('\tprograms={}'.format(','.join(new_programs)))
                    for program in programs:
                        template_programs.setdefault('program:' + program, []).append(program + '_%02d' % idx)
                # remove template
                del config[group]
        return template_programs

    def breed_programs(self, template_programs: TemplatePrograms) -> None:
        """ Find template programs in config files and replace them by X versions of the program.

        :param template_programs: the template programs
        :return: None
        """
        for program, new_programs in template_programs.items():
            if program in self.config_map:
                config = self.config_map[program]
                # duplicate and update X versions of the program
                # at the end, remove template
                for new_program in new_programs:
                    # copy template section to new_section
                    new_section = 'program:' + new_program
                    config[new_section] = config[program]
                # remove template
                del config[program]


def main():
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
    if args.verbose:
        print('ArgumentParser: {}'.format(args))
    # change working directory
    ref_directory = os.getcwd()
    os.chdir(args.template)
    # create the Breed instance
    breed = Breed(args.verbose)
    # get one parser per template file
    breed.read_config_files(args.pattern)
    if not len(breed.config_files):
        print('No configuration files found')
        sys.exit(0)
    # update all groups configurations
    group_breed = {'group:' + key: value for key, value in args.breed.items()}
    program_breed = breed.breed_groups(group_breed)
    # update program configurations found in groups
    breed.breed_programs(program_breed)
    # back to previous directory and write files
    os.chdir(ref_directory)
    breed.write_config_files(args.destination)


if __name__ == '__main__':
    main()
