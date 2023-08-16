#!/usr/bin/python
# -*- coding: utf-8 -*-

# ======================================================================
# Copyright 2022 Julien LE CLEACH
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
from argparse import ArgumentParser
from typing import Dict
from urllib.parse import urlparse

from supvisors.utils import parse_docstring


def get_docstring_description(func) -> str:
    """ Extract the first part of the docstring. """
    docstring = parse_docstring(func.__doc__)
    return docstring[0][4]


def get_docstring_parameters(func) -> Dict:
    """ Extract the parameters from the docstring.
    Supervisor and Supvisors have different formats. """
    docstring = parse_docstring(func.__doc__)
    return {entry[3]: entry[4] for entry in docstring if entry[1] == 'param'}


# Argument parsing
def is_url(arg_parser, arg):
    """ Test if the argument is a well-formatted URL.

    :param arg_parser: the argument parser
    :param arg: the argument to test
    :return: True if the argument is a folder
    """
    try:
        result = urlparse(arg)
        if all([result.scheme, result.netloc, result.port]):
            return arg
    except ValueError as exc:
        arg_parser.error(f'Could not parse the URL provided: {arg} ({exc})')
    arg_parser.error(f'The URL provided is invalid: {arg}')


def parse_args(args):
    """ Parse arguments got from the command line.

    :param args: the command line arguments
    :return: the parsed arguments
    """
    # check if this process has been spawned by Supervisor
    supervisor_url = os.environ.get('SUPERVISOR_SERVER_URL')
    # create argument parser
    parser = ArgumentParser(description='Start a Flask application to interact with Supvisors', add_help=False)
    parser.add_argument('--help', action='help', help='show this help message and exit')
    parser.add_argument('-u', '--supervisor_url', type=lambda x: is_url(parser, x),
                        default=supervisor_url, required=not supervisor_url,
                        help='the Supervisor URL, required if supvisorsflask is not spawned by Supervisor')
    parser.add_argument('-h', '--host', type=str, help='the Flask server IP address')
    parser.add_argument('-p', '--port', type=int, help='the Flask server port number')
    parser.add_argument('-d', '--debug', action='store_true', help='the Flask Debug mode')
    # parse arguments from command line
    args = parser.parse_args(args)
    return args
