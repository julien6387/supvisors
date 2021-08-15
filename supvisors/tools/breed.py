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

from configparser import ConfigParser
from pathlib import Path
from typing import Dict, Mapping, Sequence, Tuple

# annotation types
TemplateGroups = Mapping[str, int]
TemplatePrograms = Mapping[str, Sequence[str]]
SectionConfigMap = Dict[str, ConfigParser]
FileConfigMap = Dict[Path, ConfigParser]


def read_config_files(src_dir: str, file_pattern: str) -> Tuple[SectionConfigMap, FileConfigMap]:
    """ Get all config files and create a parser for each of them.

    :param src_dir: the source folder
    :param file_pattern: the filepath pattern to search for config files from the source folder
    :return: the parsers grouped by section names and by file names
    """
    parser_map, parser_files = {}, {}
    for filename in Path(src_dir).glob(file_pattern):
        config = ConfigParser(interpolation=None)
        config.read(filename)
        parser_files[os.path.abspath(filename)] = config
        for section in config.sections():
            parser_map[section] = config
    return parser_map, parser_files


def write_config_files(dst_folder: str, parser_files: FileConfigMap) -> None:
    """ Write the contents of the parsers in new config files.

    :param dst_folder: the destination folder
    :param parser_files: the parsers to write, identified by their original file name
    :return: None
    """
    # remove the common part of the filepaths to simplify the output in dst_folder
    common_path = os.path.commonpath(parser_files)
    for filename, config in parser_files.items():
        filepath = os.path.join(dst_folder, os.path.relpath(filename, common_path))
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
            parser = parsers[group]
            programs = parser[group]['programs'].split(',')
            # duplicate and update <cardinality> versions of the group
            for idx in range(1, cardinality + 1):
                new_section = group + '_%02d' % idx
                new_programs = [program + '_%02d' % idx for program in programs]
                parser[new_section] = {'programs': ','.join(new_programs)}
                for program in programs:
                    template_programs.setdefault('program:' + program, []).append(program + '_%02d' % idx)
            # remove template
            del parser[group]
    return template_programs


def breed_programs(parsers, template_programs: TemplatePrograms) -> None:
    """ Find template programs in config files and replace them by X versions of the program.

    :param parsers: all the config parsers found
    :param template_programs: the template programs
    :return: None
    """
    for program, new_programs in template_programs.items():
        if program in parsers:
            parser = parsers[program]
            # duplicate and update X versions of the program
            # at the end, remove template
            for new_program in new_programs:
                # copy template section to new_section
                new_section = 'program:' + new_program
                parser[new_section] = parser[program]
            # remove template
            del parser[program]


if __name__ == '__main__':
    """ Create X definitions of group and programs based on group/program template.
    This is typically useful when an application could be started X times.
    As there's no concept of homogeneous group in Supervisor, this script duplicates X times the definition of a group
    and its related programs and removes the original definition.
    The resulting configuration files are written to a separate folder SW_DST_DIR.
    """
    # the template groups
    breed = {'player': 4, 'web_movies': 16}
    # program parameters
    SW_TEMPLATE_DIR = '.'
    SW_DST_DIR = 'temp'
    SEARCH_PATTERN = '../test/etc/**/*ini'
    # get one parser per template file
    config_map, config_files = read_config_files(SW_TEMPLATE_DIR, SEARCH_PATTERN)
    # print(list(config_map.keys()))
    # update all groups configurations
    group_breed = {'group:' + key: value for key, value in breed.items()}
    program_breed = breed_groups(config_map, group_breed)
    # print(program_breed)
    # update program configurations found in groups
    breed_programs(config_map, program_breed)
    # write files
    write_config_files(SW_DST_DIR, config_files)
