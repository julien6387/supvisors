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

import re

from distutils.util import strtobool
from typing import Optional, Tuple
from urllib.parse import quote

from .process import ProcessStatus
from .ttypes import StartingStrategies, NameList
from .webutils import error_message


# form parameters
SERVER_URL = 'SERVER_URL'
SERVER_PORT = 'SERVER_PORT'
PATH_TRANSLATED = 'PATH_TRANSLATED'

NODE = 'node'  # nav
APPLI = 'appliname'  # nav

ACTION = 'action'
NAMESPEC = 'namespec'   # used for actions
PROCESS = 'processname'  # used to tail (but also to display stats)

PERIOD = 'period'
STRATEGY = 'strategy'
CPU = 'cpuid'
INTF = 'intfname'
AUTO = 'auto'  # auto-refresh

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
        # keep reference to the local node
        self.local_node_name = self.supvisors.address_mapper.local_node_name
        # initialize parameters
        self.parameters = {}
        # extract parameters from context
        # WARN: period must be done before processname and cpuid as it requires to be set to access statistics
        self.update_period()
        self.update_strategy()
        self.update_auto_refresh()
        self.update_node_name()
        self.update_application_name()
        self.update_process_name()
        self.update_namespec()
        self.update_cpu_id()
        self.update_interface_name()
        self.update_shrink_expand()

    def get_server_port(self):
        """ Get the port number of the web server. """
        return self.http_context.form.get(SERVER_PORT)

    def get_action(self):
        """ Extract action requested in context form. """
        return self.http_context.form.get(ACTION)

    def get_node_name(self):
        """ Extract node name from context form. """
        return self.http_context.form.get(NODE)

    def get_message(self):
        """ Extract message from context form. """
        return self.http_context.form.get(MESSAGE)

    def get_gravity(self):
        """ Extract message from context form. """
        return self.http_context.form.get(GRAVITY)

    def update_period(self):
        """ Extract period from context. """
        default_value = next(iter(self.supvisors.options.stats_periods))
        self._update_integer(PERIOD, self.supvisors.options.stats_periods, default_value)

    def update_strategy(self):
        """ Extract starting strategy from context. """
        self._update_string(STRATEGY, StartingStrategies._member_names_, self.supvisors.options.starting_strategy.name)

    def update_auto_refresh(self):
        """ Extract auto refresh from context. """
        # assign value found or default
        self._update_boolean(AUTO, False)

    def update_node_name(self):
        """ Extract node name from context. """
        # assign value found or default
        self._update_string(NODE, self.supvisors.address_mapper.node_names, self.local_node_name)

    def update_application_name(self):
        """ Extract application name from context. """
        self._update_string(APPLI, list(self.supvisors.context.applications.keys()))

    def update_process_name(self):
        """ Extract process name from context.
        ApplicationView may select instance from another node. """
        stats_node = self.get_node_stats(self.parameters[NODE])
        named_pids = stats_node.proc.keys() if stats_node else []
        self._update_string(PROCESS, [x for x, _ in named_pids])

    def update_namespec(self):
        """ Extract namespec from context. """
        self._update_string(NAMESPEC, self.supvisors.context.get_all_namespecs())

    def update_cpu_id(self):
        """ Extract CPU id from context. """
        self._update_integer(CPU, list(range(self.get_nbcores() + 1)))

    def update_interface_name(self):
        """ Extract interface name from context.
        Only the HostAddressView displays interface data, so it's local. """
        stats_node = self.get_node_stats()
        interfaces = stats_node.io.keys() if stats_node else []
        default_value = next(iter(interfaces), None)
        self._update_string(INTF, interfaces, default_value)

    def update_shrink_expand(self):
        """ Extract process display choices from context. """
        # default is all displayed
        value = ''.rjust(len(self.supvisors.context.applications.keys()), '1')
        # extract mask from context
        str_value = self.http_context.form.get(SHRINK_EXPAND)
        if str_value:
            # check that value has correct format (only 0-1 and size equal to number of applications)
            if re.match(r'^[0-1]{%d}$' % len(value), str_value):
                value = str_value
            else:
                self.message(error_message('Incorrect SHRINK_EXPAND: {}'.format(str_value)))
        self.logger.trace('ViewContext.update_shrink_expand: SHRINK_EXPAND set to {}'.format(value))
        self.parameters[SHRINK_EXPAND] = value

    def url_parameters(self, reset_shex, **kwargs):
        """ Return the list of parameters for an URL. """
        parameters = dict(self.parameters, **kwargs)
        if reset_shex:
            del parameters[SHRINK_EXPAND]
        return '&'.join(['{}={}'.format(key, quote(str(value))) for key, value in parameters.items() if value])

    def format_url(self, node_name, page, **kwargs):
        """ Format URL from parameters. """
        local_node_name = not node_name or node_name == self.local_node_name
        url = 'http://{}:{}/'.format(quote(node_name), self.get_server_port()) if node_name else ''
        return '{}{}?{}'.format(url, page, self.url_parameters(not local_node_name, **kwargs))

    def message(self, message):
        """ Set message in context response to be displayed at next refresh. """
        form = self.http_context.form
        args = {MESSAGE: message[1], GRAVITY: message[0]}
        location = '{}{}?{}'.format(form[SERVER_URL], form[PATH_TRANSLATED], self.url_parameters(False, **args))
        self.http_context.response[HEADERS][LOCATION] = location

    def get_nbcores(self, node_name=None):
        """ Get the number of processors of the local node. """
        stats_node = node_name or self.local_node_name
        return self.supvisors.statistician.nbcores.get(stats_node, 0)

    def get_node_stats(self, node_name: str = None):
        """ Get the statistics structure related to the node and the period selected.
        If no node name is specified, local node name is used. """
        stats_node = node_name or self.local_node_name
        return self.supvisors.statistician.data.get(stats_node, {}).get(self.parameters[PERIOD], None)

    def get_process_stats(self, namespec: str, node_name: str = None):
        """ Get the statistics structure related to the process and the period selected.
        Get also the number of cores available on this node (useful for process CPU IRIX mode). """
        # use local node name if not provided
        if not node_name:
            node_name = self.local_node_name
        # return the process statistics for this process
        node_stats = self.get_node_stats(node_name)
        nb_cores = self.get_nbcores(node_name)
        if node_stats:
            return nb_cores, node_stats.find_process_stats(namespec)
        return nb_cores, None

    def get_process_status(self, namespec: str = None) -> Optional[ProcessStatus]:
        """ Get the ProcessStatus instance related to the process named namespec.
        If none specified, the form namespec is used. """
        namespec = namespec or self.parameters[NAMESPEC]
        if namespec:
            try:
                return self.supvisors.context.get_process(namespec)
            except KeyError:
                self.logger.debug('ViewContext.get_process_status: failed to get ProcessStatus from {}'
                                  .format(namespec))

    def get_application_shex(self, application_name: str) -> Tuple[bool, str]:
        """ Get the expand / shrink value of the application and the shex string to invert it.

        :param application_name: the name of the application
        :return: the application shex and the inverted shex
        """
        shex = self.parameters[SHRINK_EXPAND]
        # get the index of the application in context
        idx = list(self.supvisors.context.applications.keys()).index(application_name)
        # get application shex value
        application_shex = bool(int(shex[idx]))
        # get new shex with inverted value for application
        inverted_shex = list(shex)
        inverted_shex[idx] = str(int(not application_shex))
        return application_shex, ''.join(inverted_shex)

    def _update_string(self, param: str, check_list: NameList, default_value: str = None):
        """ Extract information from context based on allowed values in check_list. """
        value = default_value
        str_value = self.http_context.form.get(param)
        if str_value:
            # check that value is known to Supvisors
            if str_value in check_list:
                value = str_value
            else:
                self.message(error_message('Incorrect {}: {}'.format(param, str_value)))
        # assign value found or default
        self.logger.trace('ViewContext._update_string: {} set to {}'.format(param, value))
        self.parameters[param] = value

    def _update_integer(self, param, check_list, default_value=0):
        """ Extract information from context and convert to integer based on allowed values in check_list. """
        value = default_value
        str_value = self.http_context.form.get(param)
        if str_value:
            try:
                int_value = int(str_value)
            except ValueError:
                self.message(error_message('{} is not an integer: {}'.format(param, str_value)))
            else:
                # check that int_value is defined in check list
                if int_value in check_list:
                    value = int_value
                else:
                    self.message(error_message('Incorrect {}: {}'.format(param, int_value)))
        # assign value found or default
        self.logger.trace('ViewContext._update_integer: {} set to {}'.format(param, value))
        self.parameters[param] = value

    def _update_boolean(self, param, default_value=False):
        """ Extract information from context and convert to boolean based on allowed values in check_list. """
        value = default_value
        str_value = self.http_context.form.get(param)
        if str_value:
            try:
                value = strtobool(str_value)
            except ValueError:
                self.message(error_message('{} is not a boolean-like: {}'.format(param, str_value)))
        # assign value found or default
        self.logger.trace('ViewContext._update_boolean: {} set to {}'.format(param, value))
        self.parameters[param] = value

    @staticmethod
    def cpu_id_to_string(idx):
        """ Get a printable form of cpu index. """
        return '{}'.format(idx - 1) if idx > 0 else 'all'
