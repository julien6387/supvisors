#!/usr/bin/python

import configparser, os

from pathlib import Path


# program parameters
SW_TEMPLATE_DIR = '.'
SW_DEST_DIR = 'mmcm'
breed = {'usvms-hci': 4, 'usvms-server': 3, 'practis-hci': 27}

# work parameters
SEARCH_PATTERN = '**/supvisors/etc/*ini'


def breed_groups(parsers, group_breed):
    program_breed = {}
    for group, cardinality in group_breed.items():
        if group in parsers:
            parser = parsers[group]
            programs = parser[group]['programs'].split(',')
            # duplicate and update <cardinality> versions of the group
            for idx in range(1, cardinality + 1):
                new_section = group + '_%02d' % idx
                new_programs = [program + '_%02d' % idx for program in programs]
                parser[new_section] = {'programs': ','.join(new_programs)}
                for program in programs:
                    program_breed.setdefault('program:' + program, []).append(program + '_%02d' % idx)
            # remove template
            del parser[group]
    return program_breed


def breed_programs(parsers, program_breed):
    for program, new_programs in program_breed.items():
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


# get one parser per template file
parser_map = {}
parser_files = {}
for filename in Path(SW_TEMPLATE_DIR).glob('**/*.ini'):
    parser = configparser.ConfigParser(interpolation=None)
    parser.read(filename)
    parser_files[filename] = parser
    for section in parser.sections():
        parser_map[section] = parser
#print(list(parser_map.keys()))

# update all groups
group_breed = {'group:' + key: value for key, value in breed.items()}
program_breed = breed_groups(parser_map, group_breed)
#print(program_breed)

# update found in groups
breed_programs(parser_map, program_breed)

# write files
for filename, parser in parser_files.items():
    filepath = os.path.join(SW_DEST_DIR, filename)
    # create path
    dirname = os.path.dirname(filepath)
    os.makedirs(dirname, exist_ok=True)
    # write new ini file from parser
    with open(filepath, 'w') as configfile:
        parser.write(configfile)

