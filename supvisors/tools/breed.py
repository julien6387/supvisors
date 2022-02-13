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
from typing import Dict, Mapping


def is_folder(arg_parser, arg):
    """ Test if the argument is a folder.

    :param arg_parser: the argument parser
    :param arg: the argument to test
    :return: True if the argument is a folder
    """
    if not os.path.isdir(arg):
        arg_parser.error('The folder "%s" does not exist' % arg)
    return arg


class KeyValue(Action):
    """ Simple action to manage key / value pairs. """

    def __call__(self, arg_parser, namespace, values, option_string=None) -> None:
        """ Check the format and store key/value pairs found from values.

        :param arg_parser: the argument parser
        :param namespace: the destination storage in argument parser
        :param values: the argument to process
        :param option_string: not used. kept for signature
        :return: None
        """
        setattr(namespace, self.dest, {})
        for value in values:
            if '=' not in value:
                arg_parser.error('breed format must be: key=value')
            key, value = value.split('=')
            if not value.isdigit():
                arg_parser.error('breed value must be an integer')
            int_value = int(value)
            if int_value < 1:
                arg_parser.error('breed value must be strictly positive')
            getattr(namespace, self.dest)[key] = int_value


class Breed(object):
    """ Create X group definitions based on group template.
    This is typically useful when an application could be started X times.
    As there's no concept of homogeneous group in Supervisor, this script duplicates X times the definition of a group
    and removes the original definition.
    The resulting configuration files are written to a separate folder.
    """

    # annotation types
    TemplateGroups = Mapping[str, int]
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
                if section.startswith('group:'):
                    self.config_map[section] = config
        if self.verbose:
            print('Configuration files found:\n\t{}'.format('\n\t'.join([str(file) for file in self.config_files])))
            print('Template group elements found:\n\t{}'.format('\n\t'.join(self.config_map.keys())))

    def write_config_files(self, dst_folder: str) -> None:
        """ Write the contents of the parsers in new config files.

        :param dst_folder: the destination folder
        :return: None
        """
        for filename, config in self.config_files.items():
            if config.sections():
                filepath = os.path.join(dst_folder, filename)
                if self.verbose:
                    print('Writing file: {}'.format(filepath))
                # create path if it doesn't exist
                folder_name = os.path.dirname(filepath)
                os.makedirs(folder_name, exist_ok=True)
                # write new config file from parser
                with open(filepath, 'w') as configfile:
                    config.write(configfile)
            else:
                if self.verbose:
                    print('Empty sections for file: {}'.format(filename))

    def breed_groups(self, template_groups: TemplateGroups, new_files: bool) -> None:
        """ Find template groups in config files and replace them by X versions of the group.

        :param template_groups: the template groups
        :param new_files: True if new configuration files required
        :return: None
        """
        for group, cardinality in template_groups.items():
            if group in self.config_map:
                ref_group_config = self.config_map[group]
                programs = ref_group_config[group]['programs']
                # duplicate and update <cardinality> versions of the group
                for idx in range(1, cardinality + 1):
                    new_section = group + '_%02d' % idx
                    # if new files are requested, add the new configuration in a new parser
                    if new_files:
                        group_config = self.create_new_parser(new_section, ref_group_config)
                    else:
                        group_config = ref_group_config
                    group_config[new_section] = {'programs': programs}
                    if self.verbose:
                        print('New [{}]'.format(new_section))
                # remove template
                del ref_group_config[group]

    def create_new_parser(self, section: str, ref_config: ConfigParser) -> ConfigParser:
        """ Create a new ConfigParser whose dirpath is similar to reference.
        The new instance is stored in internal maps.

        :param section: the config section to store in a new ConfigParser
        :param ref_config: the reference ConfigParser
        :return: the new ConfigParser
        """
        config = ConfigParser(interpolation=None)
        self.config_map[section] = config
        # add a new file reference
        ref_filename = next(filename for filename, config in self.config_files.items()
                            if config is ref_config)
        filename = Path(os.path.join(os.path.dirname(ref_filename), '_'.join(section.split(':')) + '.ini'))
        self.config_files[filename] = config
        if self.verbose:
            print('New File: {}'.format(filename))
        return config


def parse_args(args):
    """ Parse arguments got from the command line.

    :param args: the command line arguments
    :return: the parsed arguments
    """
    parser = ArgumentParser(description='Duplicate the application definitions')
    parser.add_argument('-t', '--template', type=lambda x: is_folder(parser, x), required=True,
                        help='the template folder')
    parser.add_argument('-p', '--pattern', type=str, default='**/*.ini',
                        help='the search pattern from the template folder')
    parser.add_argument('-d', '--destination', type=str, required=True, help='the destination folder')
    parser.add_argument('-b', '--breed', metavar='app=nb', action=KeyValue, nargs='+', required=True,
                        help='the applications to breed')
    parser.add_argument('-x', '--extra', action='store_true', help='create new files')
    parser.add_argument('-v', '--verbose', action='store_true', help='activate logs')
    return parser.parse_args(args)


def main():
    args = parse_args(sys.argv[1:])
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
    breed.breed_groups(group_breed, args.extra)
    # back to previous directory and write files
    os.chdir(ref_directory)
    breed.write_config_files(args.destination)
