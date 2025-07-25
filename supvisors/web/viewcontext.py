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
from urllib.parse import ParseResult, quote, urlparse

from supervisor.web import ViewContext

from supvisors.process import ProcessStatus
from supvisors.ttypes import StartingStrategies, NameList
from supvisors.utils import get_bit, set_bit
from .sessionviews import SupvisorsSession
from .webutils import SupvisorsPages, SupvisorsGravities, WebMessage

# form parameters
SERVER_URL = 'SERVER_URL'
SERVER_PORT = 'SERVER_PORT'
PATH_TRANSLATED = 'PATH_TRANSLATED'

IDENTIFIER = 'ident'  # navigation
APPLI = 'appname'  # navigation

ACTION = 'action'
NAMESPEC = 'namespec'  # used for actions
PROCESS = 'processname'  # used to tail (but also to display statistics)

PERIOD = 'period'
STRATEGY = 'strategy'
CPU = 'cpuid'
NIC = 'nic'
DISK_STATS = 'diskstats'
PARTITION = 'partition'
DEVICE = 'device'
AUTO = 'auto'  # auto-refresh
LIMIT = 'limit'

MESSAGE = 'message'
GRAVITY = 'gravity'

APP_SHRINK_EXPAND = 'ashex'
PROC_SHRINK_EXPAND = 'pshex'

# response parameters
HEADERS = 'headers'
LOCATION = 'Location'


class SupvisorsViewContext:
    """ Class used to retrieve the parameters selected on the web page.
    It is also used to format href in html pages. """

    def __init__(self, context: ViewContext):
        """ Define attributes for statistics selection. """
        # store the HTML context
        self.http_context: ViewContext = context
        # cookies
        self.session: SupvisorsSession = self.supvisors.sessions.get_session(context)
        # initialize parameters
        self.parameters = {}
        self.store_message = None
        self.redirect = False
        # extract parameters from context
        self.extract_parameters()
        # find the netmask associated
        parsed_exitf_url: ParseResult = urlparse(context.form['SERVER_URL'])
        hostname = parsed_exitf_url.hostname
        self.network_address = self.supvisors.mapper.local_network.get_network_address(hostname)
        self.logger.debug(f'SupvisorsViewContext: network_address={self.network_address}')

    @property
    def supvisors(self):
        return self.http_context.supervisord.supvisors

    @property
    def logger(self):
        return self.supvisors.logger

    @property
    def local_identifier(self) -> str:
        return self.supvisors.mapper.local_identifier

    # information extracted
    @property
    def strategy(self) -> StartingStrategies:
        return StartingStrategies[self.parameters[STRATEGY]]

    @property
    def auto_refresh(self) -> bool:
        return self.parameters[AUTO]

    @property
    def identifier(self) -> str:
        return self.parameters[IDENTIFIER]

    @property
    def application_name(self) -> str:
        return self.parameters[APPLI]

    @property
    def process_name(self) -> str:
        return self.parameters[PROCESS]

    @process_name.setter
    def process_name(self, proc_name: str) -> None:
        self.parameters[PROCESS] = proc_name

    @property
    def namespec(self) -> str:
        return self.parameters[NAMESPEC]

    @property
    def application_shex(self) -> str:
        return self.parameters[APP_SHRINK_EXPAND]

    @property
    def process_shex(self) -> str:
        return self.parameters[PROC_SHRINK_EXPAND]

    @property
    def period(self) -> float:
        return self.parameters[PERIOD]

    @property
    def cpu_id(self) -> int:
        return self.parameters[CPU]

    @property
    def nic_name(self) -> str:
        return self.parameters[NIC]

    @property
    def device(self) -> str:
        return self.parameters[DEVICE]

    @property
    def partition(self) -> str:
        return self.parameters[PARTITION]

    @property
    def disk_stats(self) -> str:
        return self.parameters[DISK_STATS]

    # simple extraction from context form
    def extract_parameters(self):
        """ Extract all parameters from the URL. """
        self.update_strategy()
        self.update_auto_refresh()
        self.update_identifier()
        self.update_application_name()
        self.update_process_name()
        self.update_namespec()
        self.update_application_shrink_expand()
        self.update_process_shrink_expand()
        self.update_period()
        self.update_cpu_id()
        self.update_nic_name()
        self.update_disk_stats_choice()
        self.update_partition_name()
        self.update_device_name()

    @property
    def action(self) -> str:
        """ Extract action requested in context form. """
        return self.http_context.form.get(ACTION)

    @property
    def message(self) -> str:
        """ Extract message text from context form. """
        return self.http_context.form.get(MESSAGE)

    @property
    def gravity(self) -> str:
        """ Extract message gravity from context form. """
        return self.http_context.form.get(GRAVITY)

    def set_default_message(self, message: str, gravity: SupvisorsGravities):
        """ Set the message and gravity if there is no existing message. """
        if not self.message:
            self.http_context.form[GRAVITY] = gravity
            self.http_context.form[MESSAGE] = message

    # complex extraction from context form
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
                self.store_message = WebMessage(f'Incorrect {NAMESPEC}: {str_value}',
                                                SupvisorsGravities.ERROR).gravity_message
        # assign value found or default
        self.logger.trace(f'SupvisorsViewContext.update_namespec: {NAMESPEC} set to {value}')
        self.parameters[NAMESPEC] = value

    def update_cpu_id(self) -> None:
        """ Extract CPU id from context. """
        self._update_integer(CPU, list(range(self.get_nb_cores(self.local_identifier) + 1)))

    def update_nic_name(self) -> None:
        """ Extract network interface name from context.
        Only the HostInstanceView displays interface data, so it's local. """
        stats_instance = self.get_instance_stats()
        interfaces = stats_instance.net_io.keys() if stats_instance else []
        default_value = next(iter(interfaces), None)
        self._update_string(NIC, interfaces, default_value)

    def update_disk_stats_choice(self) -> None:
        """ Extract the disk stats choice. """
        self._update_string(DISK_STATS, ['usage', 'io'], 'io')

    def update_partition_name(self) -> None:
        """ Extract interface name from context.
        Only the HostInstanceView displays interface data, so it's local. """
        stats_instance = self.get_instance_stats()
        partitions = stats_instance.disk_usage.keys() if stats_instance else []
        default_value = next(iter(partitions), None)
        self._update_string(PARTITION, partitions, default_value)

    def update_device_name(self) -> None:
        """ Extract interface name from context.
        Only the HostInstanceView displays interface data, so it's local. """
        stats_instance = self.get_instance_stats()
        devices = stats_instance.disk_io.keys() if stats_instance else []
        default_value = next(iter(devices), None)
        self._update_string(DEVICE, devices, default_value)

    @staticmethod
    def _get_default_shex(nb_items: int, expanded: bool) -> bytearray:
        """ Get a default shex bytearray filled with 1 if expanded.

        :param nb_items: the number of items in the shex.
        :param expanded: a status telling if the bytearray should be filled with 0 or 1.
        :return: the application shex bytearray.
        """
        base_value = 0xff if expanded else 0
        return bytearray([base_value] * math.ceil(nb_items / 8))

    def get_default_application_shex(self, expanded: bool) -> bytearray:
        """ Get a default application shex bytearray filled with 1 if expanded.

        :param expanded: a status telling if the bytearray should be filled with 0 or 1.
        :return: the application shex bytearray.
        """
        nb_applications = len(self.supvisors.context.applications)
        return SupvisorsViewContext._get_default_shex(nb_applications, expanded)

    def get_default_process_shex(self, application_name: str, expanded: bool) -> bytearray:
        """ Get a default process shex bytearray filled with 1 if expanded, for the considered application.

        :param application_name: the application name to get the processes from.
        :param expanded: a status telling if the bytearray should be filled with 0 or 1.
        :return: the process shex bytearray.
        """
        nb_processes = len(self.supvisors.context.applications[application_name].processes)
        return SupvisorsViewContext._get_default_shex(nb_processes, expanded)

    def update_application_shrink_expand(self):
        """ Extract process display choices from context.
        By default, all are displayed. """
        ba = self.get_default_application_shex(True)
        self._update_shex(APP_SHRINK_EXPAND, ba)

    def update_process_shrink_expand(self):
        """ Extract instance process display choices from context.
        By default, all are hidden. """
        if self.application_name:
            ba = self.get_default_process_shex(self.application_name, False)
            self._update_shex(PROC_SHRINK_EXPAND, ba)

    def _update_shex(self, param: str, default_ba: bytearray) -> None:
        """ Extract shex from context. """
        # extract mask from context
        str_value = self.http_context.form.get(param)
        if str_value:
            # check that value has correct format (only hex and size twice the size of the bytearray)
            try:
                value = bytearray.fromhex(str_value)
            except ValueError:
                self.logger.error(f'SupvisorsViewContext._update_shex: non-hexadecimal {param}')
            else:
                if len(default_ba) != len(value):
                    self.logger.error(f'SupvisorsViewContext._update_shex: {param} does not fit'
                                      ' with the number of items')
                else:
                    default_ba = value
        self.logger.debug(f'SupvisorsViewContext._update_shex: {param} set to {default_ba.hex()}')
        self.parameters[param] = default_ba.hex()

    def _update_string(self, param: str, check_list: NameList, default_value: str = None):
        """ Extract information from context based on allowed values in check_list. """
        value = default_value
        str_value = self.http_context.form.get(param)
        if str_value:
            # check that value is known to Supvisors
            if str_value in check_list:
                value = str_value
            else:
                self.store_message = WebMessage(f'Incorrect {param}: {str_value}',
                                                SupvisorsGravities.ERROR).gravity_message
                self.logger.error(f'SupvisorsViewContext._update_string: incorrect {param}: {str_value}')
        # assign value found or default
        self.logger.trace(f'SupvisorsViewContext._update_string: {param} set to {value}')
        self.parameters[param] = value

    def _update_integer(self, param, check_list, default_value=0):
        """ Extract information from context and convert to integer based on allowed values in check_list. """
        value = default_value
        str_value = self.http_context.form.get(param)
        if str_value:
            try:
                int_value = int(str_value)
            except ValueError:
                self.store_message = WebMessage(f'{param} is not an integer: {str_value}',
                                                SupvisorsGravities.ERROR).gravity_message
            else:
                # check that int_value is defined in check list
                if int_value in check_list:
                    value = int_value
                else:
                    self.store_message = WebMessage(f'Incorrect {param}: {int_value}',
                                                    SupvisorsGravities.ERROR).gravity_message
        # assign value found or default
        self.logger.trace(f'SupvisorsViewContext._update_integer: {param} set to {value}')
        self.parameters[param] = value

    def _update_float(self, param, check_list, default_value=0.0):
        """ Extract information from context and convert to float based on allowed values in check_list. """
        value = default_value
        str_value = self.http_context.form.get(param)
        if str_value:
            try:
                float_value = float(str_value)
            except ValueError:
                self.store_message = WebMessage(f'{param} is not a float: {str_value}',
                                                SupvisorsGravities.ERROR).gravity_message
            else:
                # check that float_value is defined in check list
                if float_value in check_list:
                    value = float_value
                else:
                    self.store_message = WebMessage(f'Incorrect {param}: {float_value}',
                                                    SupvisorsGravities.ERROR).gravity_message
        # assign value found or default
        self.logger.trace(f'SupvisorsViewContext._update_float: {param} set to {value}')
        self.parameters[param] = value

    def _update_boolean(self, param, default_value=False):
        """ Extract information from context and convert to boolean based on allowed values in check_list. """
        value = default_value
        str_value = self.http_context.form.get(param)
        if str_value:
            try:
                value = strtobool(str_value)
            except ValueError:
                self.store_message = WebMessage(f'{param} is not a boolean-like: {str_value}',
                                                SupvisorsGravities.ERROR).gravity_message
        # assign value found or default
        self.logger.trace(f'SupvisorsViewContext._update_boolean: {param} set to {value}')
        self.parameters[param] = value

    # URL formatting
    def url_parameters(self, reset_shex, **kwargs):
        """ Return the list of parameters for a URL. """
        parameters = dict(self.parameters, **kwargs)
        if reset_shex:
            del parameters[APP_SHRINK_EXPAND]
        return '&'.join([f'{key}={quote(str(value))}'
                         for key, value in sorted(parameters.items()) if value])

    def format_url(self, identifier: str, page: str, **kwargs):
        """ Format URL from parameters. """
        # build network location if identifier is provided
        if identifier:
            sup_id = self.supvisors.mapper.instances[identifier]
        else:
            sup_id = self.supvisors.mapper.local_instance
        # use network_address to get the relevant host_id
        host_id = sup_id.get_network_ip(self.network_address)
        netloc = f'http://{quote(host_id)}:{sup_id.http_port}/'
        self.logger.trace(f'SupvisorsViewContext: netloc={netloc}')
        # shex must be reset if the Supvisors instance changes
        local_identifier = sup_id.identifier == self.local_identifier
        # build URL from netloc, page and attributes
        return f'{netloc}{page}?{self.url_parameters(not local_identifier, **kwargs)}'

    def fire_message(self) -> None:
        """ Set message in context response to be displayed at next refresh. """
        if self.store_message:
            args = {MESSAGE: self.store_message[1], GRAVITY: self.store_message[0]}
            form = self.http_context.form
            # if redirect requested, go back to main page
            path_translated = '/' + SupvisorsPages.SUPVISORS_PAGE if self.redirect else form[PATH_TRANSLATED]
            location = f'{form[SERVER_URL]}{path_translated}?{self.url_parameters(False, **args)}'
            self.http_context.response[HEADERS][LOCATION] = location

    # Statistics
    def get_nb_cores(self, identifier: str) -> int:
        """ Get the number of processors of the host where the Supvisors instance is running. """
        # 2 chances to get the value
        nb_cores = self.supvisors.host_compiler.get_nb_cores(identifier)
        if not nb_cores:
            nb_cores = self.supvisors.process_compiler.get_nb_cores(identifier)
        return nb_cores

    def get_node_characteristics(self):
        """ Get the node characteristics from the stats collector. """
        if self.supvisors.stats_collector:
            node_info = self.supvisors.stats_collector.node_info
            node_info.refresh()
            return node_info
        return None

    def get_instance_stats(self, identifier: str = None):
        """ Get the statistics structure related to the identifier and the period selected.
        If no identifier is specified, local identifier is used. """
        stats_identifier = identifier or self.local_identifier
        period = self.parameters.get(PERIOD)
        return self.supvisors.host_compiler.get_stats(stats_identifier, period)

    def get_process_stats(self, namespec: str, identifier: str):
        """ Get the statistics structure related to the process and the period selected.
        The process CPU is updated if SOLARIS mode is expected.
        """
        # return the process statistics for this process
        period = self.parameters.get(PERIOD)
        return self.supvisors.process_compiler.get_stats(namespec, identifier, period)

    def get_process_status(self, namespec: str = None) -> Optional[ProcessStatus]:
        """ Get the ProcessStatus instance related to the process named namespec.
        If none specified, the form namespec is used. """
        namespec = namespec or self.namespec
        if namespec:
            try:
                return self.supvisors.context.get_process(namespec)
            except KeyError:
                self.logger.debug('SupvisorsViewContext.get_process_status: failed to get ProcessStatus'
                                  f' from {namespec}')

    # shex access
    def get_application_shex(self, application_name: str) -> Tuple[bool, str]:
        """ Get the expand / shrink value of the application and the shex string to invert it.

        :param application_name: the application name.
        :return: the application shex and the inverted shex.
        """
        ba = bytearray.fromhex(self.application_shex)
        # get the index of the application in context
        idx = sorted(self.supvisors.context.applications).index(application_name)
        # get application shex value
        application_shex = bool(get_bit(ba, idx))
        # get new shex with inverted value for application
        set_bit(ba, idx, not application_shex)
        return application_shex, ba.hex()

    def get_process_shex(self, process_name: str) -> Tuple[bool, str]:
        """ Get the expand / shrink value of the process and the shex string to invert it.

        :param process_name: the process name.
        :return: the process shex and the inverted shex.
        """
        ba = bytearray.fromhex(self.process_shex)
        # get the index of the application in context
        idx = sorted(self.supvisors.context.applications[self.application_name].processes).index(process_name)
        # get application shex value
        process_shex = bool(get_bit(ba, idx))
        # get new shex with inverted value for application
        set_bit(ba, idx, not process_shex)
        return process_shex, ba.hex()

    @staticmethod
    def cpu_id_to_string(idx):
        """ Get a printable form of cpu index. """
        return f'{idx - 1}' if idx > 0 else 'all'
