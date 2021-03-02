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

from distutils.util import strtobool
from urllib.parse import quote

from supvisors.ttypes import StartingStrategies
from supvisors.utils import supvisors_shortcuts
from supvisors.webutils import error_message

# form parameters
SERVER_URL = 'SERVER_URL'
SERVER_PORT = 'SERVER_PORT'
PATH_TRANSLATED = 'PATH_TRANSLATED'

ACTION = 'action'
ADDRESS = 'address'

PERIOD = 'period'
STRATEGY = 'strategy'
APPLI = 'appliname'
PROCESS = 'processname'
NAMESPEC = 'namespec'
CPU = 'cpuid'
INTF = 'intfname'
AUTO = 'auto'

MESSAGE = 'message'
GRAVITY = 'gravity'

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
        # keep references to Supvisors instance and attributes for readability
        self.supvisors = context.supervisord.supvisors
        supvisors_shortcuts(self, ['address_mapper', 'context', 'logger',
                                   'options', 'statistician'])
        # keep reference to the local address
        self.local_address = self.address_mapper.local_address
        # initialize parameters
        self.parameters = {}
        # extract parameters from context
        # WARN: period must be done before processname and cpuid as it requires to be set to access statistics
        self.update_period()
        self.update_strategy()
        self.update_auto_refresh()
        self.update_address()
        self.update_application_name()
        self.update_process_name()
        self.update_namespec()
        self.update_cpu_id()
        self.update_interface_name()

    def get_server_port(self):
        """ Get the port number of the web server. """
        return self.http_context.form.get(SERVER_PORT)

    def get_action(self):
        """ Extract action requested in context form. """
        return self.http_context.form.get(ACTION)

    def get_address(self):
        """ Extract address from context form. """
        return self.http_context.form.get(ADDRESS)

    def get_message(self):
        """ Extract message from context form. """
        return self.http_context.form.get(MESSAGE)

    def get_gravity(self):
        """ Extract message from context form. """
        return self.http_context.form.get(GRAVITY)

    def update_period(self):
        """ Extract period from context. """
        default_value = next(iter(self.options.stats_periods))
        self._update_integer(PERIOD, self.options.stats_periods, default_value)

    def update_strategy(self):
        """ Extract starting strategy from context. """
        self._update_string(STRATEGY, StartingStrategies.strings(),
                            StartingStrategies.to_string(self.options.starting_strategy))

    def update_auto_refresh(self):
        """ Extract auto refresh from context. """
        # assign value found or default
        self._update_boolean(AUTO, False)

    def update_address(self):
        """ Extract address name from context. """
        # assign value found or default
        self._update_string(ADDRESS, self.address_mapper.addresses, self.local_address)

    def update_application_name(self):
        """ Extract application name from context. """
        self._update_string(APPLI, list(self.context.applications.keys()))

    def update_process_name(self):
        """ Extract process name from context.
        ApplicationView may select of another address. """
        address_stats = self.get_address_stats(self.parameters[ADDRESS])
        named_pids = address_stats.proc.keys() if address_stats else []
        self._update_string(PROCESS, [x for x, _ in named_pids])

    def update_namespec(self):
        """ Extract namespec from context. """
        self._update_string(NAMESPEC, list(self.context.processes.keys()))

    def update_cpu_id(self):
        """ Extract CPU id from context. """
        self._update_integer(CPU, list(range(self.get_nbcores() + 1)))

    def update_interface_name(self):
        """ Extract interface name from context.
        Only the HostAddressView displays interface data, so it's local. """
        address_stats = self.get_address_stats()
        interfaces = address_stats.io.keys() if address_stats else []
        default_value = next(iter(interfaces), None)
        self._update_string(INTF, interfaces, default_value)

    def url_parameters(self, **kwargs):
        """ Return the list of parameters for an URL. """
        parameters = dict(self.parameters, **kwargs)
        return '&amp;'.join(['{}={}'.format(key, quote(str(value)))
                             for key, value in parameters.items()
                             if value])

    def format_url(self, address_name, page, **kwargs):
        """ Format URL from parameters. """
        url = 'http://{}:{}/'.format(quote(address_name), self.get_server_port()) if address_name else ''
        return '{}{}?{}'.format(url, page, self.url_parameters(**kwargs))

    def message(self, message):
        """ Set message in context response to be displayed at next refresh. """
        form = self.http_context.form
        args = {MESSAGE: message[1], GRAVITY: message[0]}
        location = '{}{}?{}'.format(form[SERVER_URL], form[PATH_TRANSLATED], self.url_parameters(**args))
        self.http_context.response[HEADERS][LOCATION] = location

    def get_nbcores(self, address=None):
        """ Get the number of processors of the local address. """
        stats_address = address or self.local_address
        return self.statistician.nbcores.get(stats_address, 0)

    def get_address_stats(self, address=None):
        """ Get the statistics structure related to the address and the period selected.
        If no address is specified, local address is used. """
        stats_address = address or self.local_address
        return self.statistician.data.get(stats_address, {}).get(self.parameters[PERIOD], None)

    def get_process_last_desc(self, namespec, running=False):
        """ Get the latest description received from the process across all addresses.
        A priority is given to the info coming from an address where the process is running.
        If running is set to True, the priority is exclusive. """
        address, info = None, None
        status = self.get_process_status(namespec)
        if status:
            # search for process info where process is running
            infos = dict(filter(lambda elem: elem[0] in status.addresses,
                                status.infos.items()))
            if not infos and not running:
                # nothing found and running not requested: consider all process infos
                infos = status.infos
            # sort infos them by date (local_time is local time of latest received event)
            sorted_infos = sorted(infos.items(),
                                  key=lambda x: x[1]['local_time'],
                                  reverse=True)
            address, info = next(iter(sorted_infos), (None, None))
        # return the address too
        return address, info['description'] if info else None

    def get_process_stats(self, namespec, address=None):
        """ Get the statistics structure related to the process and the period selected.
        Get also the number of cores available on this address (useful for process CPU IRIX mode). """
        # use local address if not provided
        if not address:
            address = self.local_address
        # return the process statistics for this process
        address_stats = self.get_address_stats(address)
        nb_cores = self.get_nbcores(address)
        if address_stats:
            return nb_cores, address_stats.find_process_stats(namespec)
        return nb_cores, None

    def get_process_status(self, namespec=None):
        """ Get the ProcessStatus instance related to the process named namespec.
        If none specified, the form namespec is used. """
        namespec = namespec or self.parameters[NAMESPEC]
        if namespec:
            try:
                return self.context.processes[namespec]
            except KeyError:
                self.logger.debug('failed to get ProcessStatus from {}'.format(namespec))

    def _update_string(self, param, check_list, default_value=None):
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
        self.logger.debug('{} set to {}'.format(param, value))
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
        self.logger.debug('{} set to {}'.format(param, value))
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
        self.logger.debug('{} set to {}'.format(param, value))
        self.parameters[param] = value


    @staticmethod
    def cpu_id_to_string(idx):
        """ Get a printable form of cpu index. """
        return '{}'.format(idx - 1) if idx > 0 else 'all'
