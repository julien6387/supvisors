#!/usr/bin/python
# -*- coding: utf-8 -*-

# ======================================================================
# Copyright 2018 Julien LE CLEACH
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

import math
from distutils.util import strtobool
from typing import Optional, Tuple
from urllib.parse import quote

from supvisors.process import ProcessStatus
from supvisors.ttypes import StartingStrategies, NameList
from supvisors.utils import get_bit, set_bit
from .webutils import SUPVISORS_PAGE, error_message

# form parameters
SERVER_URL = 'SERVER_URL'
SERVER_PORT = 'SERVER_PORT'
PATH_TRANSLATED = 'PATH_TRANSLATED'

IDENTIFIER = 'ident'  # navigation
APPLI = 'appliname'  # navigation

ACTION = 'action'
NAMESPEC = 'namespec'   # used for actions
PROCESS = 'processname'  # used to tail (but also to display statistics)

PERIOD = 'period'
STRATEGY = 'strategy'
CPU = 'cpuid'
INTF = 'intfname'
AUTO = 'auto'  # auto-refresh
LIMIT = 'limit'

MESSAGE = 'message'
GRAVITY = 'gravity'

SHRINK_EXPAND = 'shex'

# response parameters
HEADERS = 'headers'
LOCATION = 'Location'


class ViewContext:
    """ Class used to retrieve the parameters selected on the web page.
    It is also used to format href in html pages. """

    def __init__(self, context):
        """ Define attributes for statistics selection. """
        # store the HTML context
        self.http_context = context
        # keep references to Supvisors instance
        self.supvisors = context.supervisord.supvisors
        self.logger = self.supvisors.logger
        # keep reference to the local identifier
        self.local_identifier = self.supvisors.mapper.local_identifier
        # initialize parameters
        self.parameters = {}
        self.store_message = None
        self.redirect = False
        # extract parameters from context
        self.update_strategy()
        self.update_auto_refresh()
        self.update_identifier()
        self.update_application_name()
        self.update_process_name()
        self.update_namespec()
        self.update_shrink_expand()
        self.update_period()
        self.update_cpu_id()
        self.update_interface_name()

    def get_action(self):
        """ Extract action requested in context form. """
        return self.http_context.form.get(ACTION)

    def get_identifier(self):
        """ Extract identifier from context form. """
        return self.http_context.form.get(IDENTIFIER)

    def get_message(self):
        """ Extract message from context form. """
        return self.http_context.form.get(MESSAGE)

    def get_gravity(self):
        """ Extract message from context form. """
        return self.http_context.form.get(GRAVITY)

    def update_period(self) -> None:
        """ Extract period from context. """
        default_value = next(iter(self.supvisors.options.stats_periods))
        self._update_float(PERIOD, self.supvisors.options.stats_periods, default_value)

    def update_strategy(self) -> None:
        """ Extract starting strategy from context. """
        self._update_string(STRATEGY, [x.name for x in StartingStrategies],
                            self.supvisors.options.starting_strategy.name)

    def update_auto_refresh(self) -> None:
        """ Extract auto refresh from context. """
        # assign value found or default
        self._update_boolean(AUTO, False)

    def update_identifier(self) -> None:
        """ Extract identifier from context. """
        # assign value found or default
        self._update_string(IDENTIFIER, self.supvisors.mapper.instances, self.local_identifier)

    def update_application_name(self) -> None:
        """ Extract application name from context. """
        self._update_string(APPLI, list(self.supvisors.context.applications.keys()))

    def update_process_name(self) -> None:
        """ Extract process name from context.
        ApplicationView may select a process unknown to this Supvisors instance. """
        status = self.supvisors.context.instances[self.parameters[IDENTIFIER]]
        # consider processes running on this Supvisors instance + supervisord
        running_processes = [x.namespec for x in status.running_processes()]
        running_processes.append('supervisord')
        self._update_string(PROCESS, running_processes)

    def update_namespec(self) -> None:
        """ Extract namespec from context. """
        value = None
        str_value = self.http_context.form.get(NAMESPEC)
        if str_value:
            # check that value is known to Supvisors
            if self.supvisors.context.is_namespec(str_value):
                value = str_value
            else:
                self.store_message = error_message(f'Incorrect {NAMESPEC}: {str_value}')
        # assign value found or default
        self.logger.trace(f'ViewContext.update_namespec: {NAMESPEC} set to {value}')
        self.parameters[NAMESPEC] = value

    def update_cpu_id(self) -> None:
        """ Extract CPU id from context. """
        self._update_integer(CPU, list(range(self.get_nb_cores() + 1)))

    def update_interface_name(self) -> None:
        """ Extract interface name from context.
        Only the HostInstanceView displays interface data, so it's local. """
        stats_instance = self.get_instance_stats()
        interfaces = stats_instance.io.keys() if stats_instance else []
        default_value = next(iter(interfaces), None)
        self._update_string(INTF, interfaces, default_value)

    def get_default_shex(self, expanded: bool) -> bytearray:
        """ Get a default shex bytearray filled with 1 if expanded.

        :param expanded: a status telling if the bytearray should be filled with 0 or 1
        :return: the shex bytearray
        """
        nb_applications = len(self.supvisors.context.applications)
        base_value = 0xff if expanded else 0
        return bytearray([base_value] * math.ceil(nb_applications / 8))

    def update_shrink_expand(self):
        """ Extract process display choices from context. """
        # default is expanded
        ba = self.get_default_shex(True)
        # extract mask from context
        str_value = self.http_context.form.get(SHRINK_EXPAND)
        if str_value:
            # check that value has correct format (only hex and size twice the size of the bytearray)
            try:
                value = bytearray.fromhex(str_value)
            except ValueError as exc:
                self.logger.error(f'ViewContext.update_shrink_expand: non-hexadecimal SHRINK_EXPAND={exc}')
            else:
                if len(ba) != len(value):
                    self.logger.error('ViewContext.update_shrink_expand: SHRINK_EXPAND does not fit with the number'
                                      ' of applications')
                else:
                    ba = value
        self.logger.debug(f'ViewContext.update_shrink_expand: SHRINK_EXPAND set to {ba.hex()}')
        self.parameters[SHRINK_EXPAND] = ba.hex()

    def url_parameters(self, reset_shex, **kwargs):
        """ Return the list of parameters for a URL. """
        parameters = dict(self.parameters, **kwargs)
        if reset_shex:
            del parameters[SHRINK_EXPAND]
        return '&'.join([f'{key}={quote(str(value))}'
                         for key, value in sorted(parameters.items()) if value])

    def format_url(self, identifier: str, page: str, **kwargs):
        """ Format URL from parameters. """
        netloc = ''
        # build network location if identifier is provided
        if identifier:
            instance = self.supvisors.mapper.instances[identifier]
            netloc = f'http://{quote(instance.host_id)}:{instance.http_port}/'
        # shex must be reset if the Supvisors instance changes
        local_identifier = not identifier or identifier == self.local_identifier
        # build URL from netloc, page and attributes
        return f'{netloc}{page}?{self.url_parameters(not local_identifier, **kwargs)}'

    def fire_message(self) -> None:
        """ Set message in context response to be displayed at next refresh. """
        if self.store_message:
            args = {MESSAGE: self.store_message[1], GRAVITY: self.store_message[0]}
            form = self.http_context.form
            # if redirect requested, go back to main page
            path_translated = '/' + SUPVISORS_PAGE if self.redirect else form[PATH_TRANSLATED]
            location = f'{form[SERVER_URL]}{path_translated}?{self.url_parameters(False, **args)}'
            self.http_context.response[HEADERS][LOCATION] = location

    def get_nb_cores(self, identifier: str = None) -> int:
        """ Get the number of processors of the host where the Supvisors instance is running. """
        stats_identifier = identifier or self.local_identifier
        # 2 chances to get the value
        nb_cores = self.supvisors.host_compiler.get_nb_cores(stats_identifier)
        if not nb_cores:
            nb_cores = self.supvisors.process_compiler.get_nb_cores(stats_identifier)
        return nb_cores

    def get_instance_stats(self, identifier: str = None):
        """ Get the statistics structure related to the identifier and the period selected.
        If no identifier is specified, local identifier is used. """
        stats_identifier = identifier or self.local_identifier
        period = self.parameters.get(PERIOD)
        return self.supvisors.host_compiler.get_stats(stats_identifier, period)

    def get_process_stats(self, namespec: str, identifier: str = None):
        """ Get the statistics structure related to the process and the period selected.
        Get also the number of cores available where this Supvisors instance runs (useful for process CPU IRIX mode).
        """
        # use local identifier if not provided
        if not identifier:
            identifier = self.local_identifier
        # get the number of cores for Solaris mode
        nb_cores = self.get_nb_cores(identifier)
        # return the process statistics for this process
        period = self.parameters.get(PERIOD)
        stats_instance = self.supvisors.process_compiler.get_stats(namespec, identifier, period)
        return nb_cores, stats_instance

    def get_process_status(self, namespec: str = None) -> Optional[ProcessStatus]:
        """ Get the ProcessStatus instance related to the process named namespec.
        If none specified, the form namespec is used. """
        namespec = namespec or self.parameters[NAMESPEC]
        if namespec:
            try:
                return self.supvisors.context.get_process(namespec)
            except KeyError:
                self.logger.debug(f'ViewContext.get_process_status: failed to get ProcessStatus from {namespec}')

    def get_application_shex(self, application_name: str) -> Tuple[bool, str]:
        """ Get the expand / shrink value of the application and the shex string to invert it.

        :param application_name: the application name
        :return: the application shex and the inverted shex
        """
        shex = self.parameters[SHRINK_EXPAND]
        ba = bytearray.fromhex(shex)
        # get the index of the application in context
        idx = list(self.supvisors.context.applications).index(application_name)
        # get application shex value
        application_shex = bool(get_bit(ba, idx))
        # get new shex with inverted value for application
        set_bit(ba, idx, not application_shex)
        return application_shex, ba.hex()

    def _update_string(self, param: str, check_list: NameList, default_value: str = None):
        """ Extract information from context based on allowed values in check_list. """
        value = default_value
        str_value = self.http_context.form.get(param)
        if str_value:
            # check that value is known to Supvisors
            if str_value in check_list:
                value = str_value
            else:
                self.store_message = error_message(f'Incorrect {param}: {str_value}')
        # assign value found or default
        self.logger.trace(f'ViewContext._update_string: {param} set to {value}')
        self.parameters[param] = value

    def _update_integer(self, param, check_list, default_value=0):
        """ Extract information from context and convert to integer based on allowed values in check_list. """
        value = default_value
        str_value = self.http_context.form.get(param)
        if str_value:
            try:
                int_value = int(str_value)
            except ValueError:
                self.store_message = error_message(f'{param} is not an integer: {str_value}')
            else:
                # check that int_value is defined in check list
                if int_value in check_list:
                    value = int_value
                else:
                    self.store_message = error_message(f'Incorrect {param}: {int_value}')
        # assign value found or default
        self.logger.trace(f'ViewContext._update_integer: {param} set to {value}')
        self.parameters[param] = value

    def _update_float(self, param, check_list, default_value=0.0):
        """ Extract information from context and convert to float based on allowed values in check_list. """
        value = default_value
        str_value = self.http_context.form.get(param)
        if str_value:
            try:
                float_value = float(str_value)
            except ValueError:
                self.store_message = error_message(f'{param} is not a float: {str_value}')
            else:
                # check that float_value is defined in check list
                if float_value in check_list:
                    value = float_value
                else:
                    self.store_message = error_message(f'Incorrect {param}: {float_value}')
        # assign value found or default
        self.logger.trace(f'ViewContext._update_float: {param} set to {value}')
        self.parameters[param] = value

    def _update_boolean(self, param, default_value=False):
        """ Extract information from context and convert to boolean based on allowed values in check_list. """
        value = default_value
        str_value = self.http_context.form.get(param)
        if str_value:
            try:
                value = strtobool(str_value)
            except ValueError:
                self.store_message = error_message(f'{param} is not a boolean-like: {str_value}')
        # assign value found or default
        self.logger.trace(f'ViewContext._update_boolean: {param} set to {value}')
        self.parameters[param] = value

    @staticmethod
    def cpu_id_to_string(idx):
        """ Get a printable form of cpu index. """
        return '{}'.format(idx - 1) if idx > 0 else 'all'
