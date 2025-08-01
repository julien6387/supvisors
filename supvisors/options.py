# ======================================================================
# Copyright 2016 Julien LE CLEACH
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

import glob
import json
import os
import platform
from collections import OrderedDict
from typing import Dict, List, Optional, Tuple

from supervisor.datatypes import Automatic, logfile_name, boolean, integer, byte_size, logging_level, list_of_strings
from supervisor.loggers import Logger
from supervisor.options import (expand, make_namespec, ServerOptions,
                                ProcessConfig, FastCGIProcessConfig, EventListenerConfig)

from .ttypes import (ConciliationStrategies, StartingStrategies, SupvisorsFailureStrategies,
                     EventLinks, SynchronizationOptions,
                     Ipv4Address, NameList, Payload, StatisticsTypes,
                     GroupConfigInfo, ProgramConfig, SupvisorsProcessConfig)


# Options of main section
def get_logger_configuration(**config) -> Payload:
    """ Extract the logger parameters from the config structure.

    Returns a dictionary with the following entries:
        - software_name: the optional software name, used as a prefix in log traces ;
        - logfile: absolute or relative path of the Supvisors log file ;
        - logfile_maxbytes: maximum size of the Supvisors log file ;
        - logfile_backups: number of Supvisors backup log files ;
        - loglevel: logging level.

    :param config: the configuration provided by Supervisor from the [rpcinterface:supvisors] section.
    :return: a dictionary containing the logger parameters.
    """
    return {'prefix': config.get('software_name', ''),
            'logfile': logfile_name(config.get('logfile', Automatic)),
            'logfile_maxbytes': byte_size(config.get('logfile_maxbytes', '50MB')),
            'logfile_backups': integer(config.get('logfile_backups', 10)),
            'loglevel': logging_level(config.get('loglevel', 'info'))}


class SupvisorsOptions:
    """ Holder of the Supvisors options.

    Attributes are:
        - software_name: a string to be displayed at the top of the Supvisors Web UI ;
        - software_icon: the path of an icon to be displayed at the top of the Supvisors Web UI ;
        - supvisors_list: list of Supvisors instance identifiers where Supvisors will be running ;
        - stereotype: the Supvisors instance stereotype, used as aliases in rules ;
        - multicast: UDP Multicast Group where Supvisors will exchange data ;
        - multicast_interface: UDP Multicast Group interface ;
        - multicast_ttl: UDP Multicast time-to-live ;
        - rules_files: list of absolute or relative paths to the XML rules files ;
        - css_files: list of css files used to override the Supvisors default CSS ;
        - event_link: type of the event link used to publish all Supvisors events ;
        - event_port: port number used to publish all Supvisors events ;
        - auto_fence: when True, Supvisors won't try to reconnect to a Supvisors instance that has been inactive ;
        - synchro_options: the conditions that will end the synchronization phase ;
        - synchro_timeout: time in seconds that Supvisors waits for all expected Supvisors instances to publish ;
        - inactivity_ticks: number of local ticks to wait before considering a remote Supvisors instance inactive ;
        - core_identifiers: subset of supvisors_list identifiers that will force the end of synchro when all RUNNING ;
        - disabilities_file: the file used to persist the process disabilities ;
        - conciliation_strategy: strategy used to solve conflicts when Supvisors has detected multiple running
          instances of the same program ;
        - starting_strategy: strategy used to start processes on Supvisors instances ;
        - supvisors_failure_strategy: strategy used to decide the way forward after a node loss ;
        - host_stats_enabled: if False, no host statistics will be collected from this Supvisors instance ;
        - proc_stats_enabled: if False, no process statistics will be collected from this Supvisors instance ;
        - collecting_period: period of the statistics collection ;
        - stats_periods: list of periods for which the statistics will be provided in the Supvisors Web UI ;
        - stats_histo: depth of statistics history ;
        - stats_irix_mode: choice of CPU value display between IRIX and Solaris ;
        - tail_limit: the number of bytes used to display the log tail of the file in the Web UI (refresh mode) ;
        - tailf_limit: the number of bytes used to display the log tail of the file in the Web UI (tail -f mode).
    """

    SYNCHRO_TIMEOUT_MIN = 15
    SYNCHRO_TIMEOUT_MAX = 1200

    # default SynchronizationOptions list that is equivalent to previous Supvisors versions
    SYNCHRO_DEFAULT_OPTIONS = [SynchronizationOptions.STRICT,
                               SynchronizationOptions.TIMEOUT,
                               SynchronizationOptions.CORE]

    INACTIVITY_TICKS_MIN = 2
    INACTIVITY_TICKS_MAX = 720

    RESERVED_MULTICAST_ADDRESSES = ['224.0.0.0', '232.0.0.0', '233.0.0.0', '239.0.0.0']

    def __init__(self, supervisord, logger: Logger, **config):
        """ Initialization of the attributes.

        :param supervisord: the global Supervisor structure
        :param logger: the Supvisors logger
        :param config: the configuration provided by Supervisor from the [rpcinterface:supvisors] section
        """
        self.supervisord_options = supervisord.options
        self.logger = logger
        # get the string to be displayed at the top of the Supvisors Web UI
        self.software_name = self._get_value(config, 'software_name', '')
        self.software_icon = self._get_value(config, 'software_icon', None, self.to_existing_file)
        # get expected Supvisors instances
        self.supvisors_list = self._get_value(config, 'supvisors_list', None,
                                              lambda x: list(OrderedDict.fromkeys(filter(None, list_of_strings(x)))))
        # Supvisors instance generic type
        self.stereotypes = self._get_value(config, 'stereotypes', set(),
                                           lambda x: set(filter(None, list_of_strings(x))))
        # get multicast parameters for discovery mode
        self.multicast_group = self._get_value(config, 'multicast_group', None, self.to_multicast_group)
        self.multicast_interface = self._get_value(config, 'multicast_interface', None, self.to_ip_address)
        self.multicast_ttl = self._get_value(config, 'multicast_ttl', 1, self.to_ttl)
        # get the rules and CSS files
        self.rules_files = self._get_value(config, 'rules_files', None, self.to_filepaths)
        self.css_files = self._get_value(config, 'css_files', None, self.to_filepaths)
        # if event_port is not defined, it will be set later based on Supervisor HTTP port
        self.event_link = self._get_value(config, 'event_link', EventLinks.NONE, self.to_event_link)
        self.event_port = self._get_value(config, 'event_port', 0, self.to_port_num)
        self.auto_fence = self._get_value(config, 'auto_fence', False, boolean)
        self.synchro_options = self._get_value(config, 'synchro_options', self.SYNCHRO_DEFAULT_OPTIONS,
                                               self.to_synchro_options)
        self.synchro_timeout = self._get_value(config, 'synchro_timeout', self.SYNCHRO_TIMEOUT_MIN, self.to_timeout)
        self.inactivity_ticks = self._get_value(config, 'inactivity_ticks', self.INACTIVITY_TICKS_MIN, self.to_ticks)
        # get the minimum list of identifiers to end the synchronization phase
        self.core_identifiers = self._get_value(config, 'core_identifiers', set(),
                                                lambda x: set(filter(None, list_of_strings(x))))
        # get disabilities file
        self.disabilities_file = self._get_value(config, 'disabilities_file', None, self.check_dirpath)
        # get strategies
        self.conciliation_strategy = self._get_value(config, 'conciliation_strategy', ConciliationStrategies.USER,
                                                     self.to_conciliation_strategy)
        self.starting_strategy = self._get_value(config, 'starting_strategy', StartingStrategies.CONFIG,
                                                 self.to_starting_strategy)
        self.supvisors_failure_strategy = self._get_value(config, 'supvisors_failure_strategy',
                                                          SupvisorsFailureStrategies.CONTINUE,
                                                          self.to_supvisors_failure_strategy)
        # configure statistics
        # stats_enabled is deprecated
        stats_enabled = self._get_value(config, 'stats_enabled', (True, True), self.to_statistics_type)
        self.host_stats_enabled = stats_enabled[0]
        self.process_stats_enabled = stats_enabled[1]
        self.collecting_period = self._get_value(config, 'stats_collecting_period', 5, self.to_period)
        self.stats_periods = self._get_value(config, 'stats_periods', [10], self.to_periods)
        self.stats_histo = self._get_value(config, 'stats_histo', 200, self.to_histo)
        self.stats_irix_mode = self._get_value(config, 'stats_irix_mode', False, boolean)
        # configure log tail limits
        self.tail_limit = self._get_value(config, 'tail_limit', 1024, byte_size)
        self.tailf_limit = self._get_value(config, 'tailf_limit', 1024, byte_size)
        # check options consistency
        self.check_options()

    def __str__(self):
        """ Contents as string. """
        mc_group = None
        if self.multicast_group:
            mc_group = f'{self.multicast_group[0]}:{self.multicast_group[1]}'
        return (f'software_name="{self.software_name}"'
                f' software_icon={self.software_icon}'
                f' supvisors_list={self.supvisors_list}'
                f' stereotypes={self.stereotypes}'
                f' multicast_group={mc_group}'
                f' multicast_interface={self.multicast_interface}'
                f' multicast_ttl={self.multicast_ttl}'
                f' rules_files={self.rules_files}'
                f' css_files={self.css_files}'
                f' event_link={self.event_link.name}'
                f' event_port={self.event_port}'
                f' auto_fence={self.auto_fence}'
                f' synchro_options={[x.name for x in self.synchro_options]}'
                f' synchro_timeout={self.synchro_timeout}'
                f' inactivity_ticks={self.inactivity_ticks}'
                f' core_identifiers={self.core_identifiers}'
                f' disabilities_file={self.disabilities_file}'
                f' conciliation_strategy={self.conciliation_strategy.name}'
                f' starting_strategy={self.starting_strategy.name}'
                f' supvisors_failure_strategy={self.supvisors_failure_strategy.name}'
                f' host_stats_enabled={self.host_stats_enabled}'
                f' process_stats_enabled={self.process_stats_enabled}'
                f' collecting_period={self.collecting_period}'
                f' stats_periods={self.stats_periods}'
                f' stats_histo={self.stats_histo}'
                f' stats_irix_mode={self.stats_irix_mode}'
                f' tail_limit={self.tail_limit}'
                f' tailf_limit={self.tailf_limit}')

    @property
    def discovery_mode(self) -> bool:
        """ Return True if Supvisors is in discovery mode.

        :return: True if the multicast group is set
        """
        return self.multicast_group is not None

    def check_options(self):
        """ Check the consistency of the options. """
        # when using CORE in synchro_options, core_identifiers cannot be empty
        if not self.core_identifiers and SynchronizationOptions.CORE in self.synchro_options:
            self.logger.warn('SupvisorsOptions:check_options: cancellation of synchro_options CORE'
                             ' with no core_identifiers')
            self.synchro_options.remove(SynchronizationOptions.CORE)
        # when using LIST in synchro_options, supvisors_list cannot be empty
        if not self.supvisors_list and SynchronizationOptions.STRICT in self.synchro_options:
            self.logger.warn('SupvisorsOptions:check_options: cancellation of synchro_options STRICT'
                             ' with no supvisors_list')
            self.synchro_options.remove(SynchronizationOptions.STRICT)
        # synchro_options must not be empty
        if not self.synchro_options:
            raise ValueError('synchro_options shall not be empty')
        # using TIMEOUT in synchro_options invalidates SupvisorsFailureStrategies
        # otherwise the SynchronizedState._check_failure_strategy may always trigger
        if (SynchronizationOptions.TIMEOUT in self.synchro_options
                and self.supvisors_failure_strategy != SupvisorsFailureStrategies.CONTINUE):
            self.logger.warn('SupvisorsOptions:check_options: force supvisors_failure_strategy=CONTINUE'
                             ' because it is incompatible with synchro_options=TIMEOUT')
            self.supvisors_failure_strategy = SupvisorsFailureStrategies.CONTINUE

    def check_dirpath(self, file_path: str) -> str:
        """ Check if the path provided exists and create the folder tree if necessary.
        update of Supervisor datatypes.existing_dirpath.

        :param file_path: the file path to check.
        :return: the file path.
        """
        expanded_file_path = os.path.expanduser(file_path)
        file_dir = os.path.dirname(expanded_file_path)
        if not file_dir:
            # relative pathname with no directory component
            return expanded_file_path
        if not os.path.isdir(file_dir):
            # if the folder path does not exist, try to create it
            try:
                self.logger.info(f'SupvisorsOptions.check_dirpath: creating folder={file_dir}')
                os.makedirs(file_dir)
            except PermissionError:
                # creation of the folder tree denied
                raise ValueError(f'The directory named as part of the path={file_path} cannot be created')
        return expanded_file_path

    def _get_value(self, config: Payload, attr: str, default_value, fct=None):
        """ Read and convert the option.

        :param config: the option dictionary.
        :param attr: the option considered.
        :param default_value: the default value to apply if not found in config or erroneous.
        :param fct: the optional conversion function to apply to the string value.
        :return: the option with the requested type.
        """
        if attr not in config:
            return default_value
        value = config[attr]
        if fct:
            try:
                return fct(value)
            except ValueError as exc:
                self.logger.error(f'SupvisorsOptions.get_value: {str(exc)}')
                return default_value
        return value

    # conversion utils (completion of supervisor.datatypes)
    def to_existing_file(self, value: str) -> Optional[str]:
        """ Expand the file globs and return the file found.
        One single result expected.

        :param value: a space-separated sequence of file globs.
        :return: the file found.
        """
        file_set = self.to_filepaths(value)
        candidates = [filepath for filepath in file_set
                      if os.path.isfile(filepath)]
        if len(candidates) > 1:
            self.logger.warn(f'SupvisorsOptions.to_existing_file: multiple candidates found matching {value}'
                             f' - {candidates}')
        return candidates[0] if candidates else None

    def to_filepaths(self, value: str) -> List[str]:
        """ Expand the file globs and return the files found.

        :param value: a space-separated sequence of file globs
        :return: the list of files found
        """
        # apply expansions to value
        expansions = {'here': self.supervisord_options.here,
                      'host_node_name': platform.node()}
        expansions.update(self.supervisord_options.environ_expansions)
        files = expand(value, expansions, 'rpcinterface.supvisors')
        # get all files
        file_set = set()
        for pattern in files.split():
            filepaths = glob.glob(pattern)
            for filepath in filepaths:
                file_set.add(os.path.abspath(filepath))
        # check that something came out
        if value and not file_set:
            self.logger.warn(f'SupvisorsOptions.to_filepaths: no file found matching {value}')
        return sorted(file_set)

    @staticmethod
    def to_multicast_group(value: str) -> Ipv4Address:
        """ Convert a string into a TTL number, in [0;255].

        :param value: the multicast address + port as a string
        :return: the verified multicast address + port
        """
        # parse the value to find address + port
        values = value.split(':', 1)
        if len(values) != 2:
            raise ValueError(f'invalid value for multicast_group: "{value}".'
                             f' "ip_address:port" expected')
        SupvisorsOptions._check_multicast_address(values[0])
        return values[0], SupvisorsOptions.to_port_num(values[1])

    @staticmethod
    def to_ip_address(value: str) -> Optional[str]:
        """ Check the formatting of the IP address.

        :param value: the IP address to check
        :return: None
        """
        # will set INADDR_ANY later
        if value in ['ANY', 'INADDR_ANY']:
            return None
        # parse the IP address
        try:
            values = value.split('.')
            if len(values) != 4:
                raise ValueError('wrong number of bytes')
            for idx in range(0, 4):
                SupvisorsOptions.to_integer(values[idx], f'IP byte {idx}', (0, 255))
        except ValueError:
            raise ValueError(f'invalid value for IP address: "{value}"')
        return value

    @staticmethod
    def _check_multicast_address(value: str):
        """ Check the formatting of the multicast address from 224.0.0.0 to 239.255.255.255.

        :param value: the multicast address to check
        :return: None
        """
        if value in SupvisorsOptions.RESERVED_MULTICAST_ADDRESSES:
            raise ValueError(f'reserved multicast address: "{value}".'
                             f' reserved addresses are {SupvisorsOptions.RESERVED_MULTICAST_ADDRESSES}')
        # parse the IP address
        try:
            values = value.split('.')
            if len(values) != 4:
                raise ValueError('wrong number of bytes')
            SupvisorsOptions.to_integer(values[0], 'multicast byte 1', (224, 239))
            for idx in range(1, 4):
                SupvisorsOptions.to_integer(values[idx], f'multicast byte {idx}', (0, 255))
        except ValueError:
            raise ValueError(f'invalid value for multicast address: "{value}".'
                             ' IP address expected from 224.0.0.0 to 239.255.255.255')

    @staticmethod
    def to_ttl(value: str) -> int:
        """ Convert a string into a TTL number, in [0;255].

        :param value: the TTL as a string
        :return: the TTL as an integer
        """
        return SupvisorsOptions.to_integer(value, 'multicast_ttl', (0, 255))

    @staticmethod
    def to_port_num(value: str) -> int:
        """ Convert a string into a port number, in [1;65535].

        :param value: the port number as a string
        :return: the port number as an integer
        """
        return SupvisorsOptions.to_integer(value, 'port', (1, 65535))

    @staticmethod
    def to_integer(value: str, type_name: str, limits: Tuple[int, int]) -> int:
        """ Convert a string into an integer within given limits.

        :param value: the integer as a string
        :param type_name: the integer nature for log in case of exception
        :param limits: the integer limits, given as a tuple(min, max) of inclusive bounds
        :return: the integer found
        """
        try:
            port = integer(value)
            if limits[0] > port or port > limits[1]:
                raise ValueError
            return port
        except ValueError:
            raise ValueError(f'invalid value for {type_name}: "{value}".'
                             f' integer expected in {limits}')

    @staticmethod
    def to_synchro_options(value: str) -> List[SynchronizationOptions]:
        """ Return the list of options selected to end the synchronization phase. """
        option_str_list = filter(None, list_of_strings(value))
        option_list = []
        for option_str in option_str_list:
            try:
                option = SynchronizationOptions[option_str.upper()]
            except KeyError:
                raise ValueError(f'invalid value for synchro_options: "{option_str}".'
                                 f' expected in {[x.name for x in SynchronizationOptions]})')
            if option not in option_list:
                option_list.append(option)
        return option_list

    @staticmethod
    def to_timeout(value: str) -> int:
        """ Convert a string into a timeout value, in [15;1200].

        :param value: the timeout as a string
        :return: the timeout as an integer
        """
        try:
            timeout = integer(value)
            if SupvisorsOptions.SYNCHRO_TIMEOUT_MIN > timeout or timeout > SupvisorsOptions.SYNCHRO_TIMEOUT_MAX:
                raise ValueError
            return timeout
        except ValueError:
            raise ValueError(f'invalid value for synchro_timeout: "{value}".'
                             f' integer expected in [{SupvisorsOptions.SYNCHRO_TIMEOUT_MIN};'
                             f'{SupvisorsOptions.SYNCHRO_TIMEOUT_MAX}] (seconds)')

    @staticmethod
    def to_ticks(value: str) -> int:
        """ Convert a string into a number of ticks, in [2;720].

        :param value: the number of ticks as a string
        :return: the number of ticks as an integer
        """
        try:
            ticks = integer(value)
            if SupvisorsOptions.INACTIVITY_TICKS_MIN > ticks or ticks > SupvisorsOptions.INACTIVITY_TICKS_MAX:
                raise ValueError
            return ticks
        except ValueError:
            raise ValueError(f'invalid value for inactivity_ticks: "{value}".'
                             f' integer expected in [{SupvisorsOptions.INACTIVITY_TICKS_MIN};'
                             f'{SupvisorsOptions.INACTIVITY_TICKS_MAX}]')

    @staticmethod
    def to_event_link(value: str) -> EventLinks:
        """ Convert a string into a EventLinks enum. """
        try:
            event_link = EventLinks[value.upper()]
        except KeyError:
            raise ValueError(f'invalid value for event_link: "{value}".'
                             f' expected in {[x.name for x in EventLinks]}')
        return event_link

    @staticmethod
    def to_conciliation_strategy(value: str) -> ConciliationStrategies:
        """ Convert a string into a ConciliationStrategies enum. """
        try:
            strategy = ConciliationStrategies[value.upper()]
        except KeyError:
            raise ValueError(f'invalid value for conciliation_strategy: "{value}".'
                             f' expected in {[x.name for x in ConciliationStrategies]}')
        return strategy

    @staticmethod
    def to_starting_strategy(value: str) -> StartingStrategies:
        """ Convert a string into a StartingStrategies enum. """
        try:
            strategy = StartingStrategies[value.upper()]
        except KeyError:
            raise ValueError(f'invalid value for starting_strategy: "{value}".'
                             f' expected in {[x.name for x in StartingStrategies]}')
        return strategy

    @staticmethod
    def to_supvisors_failure_strategy(value: str) -> SupvisorsFailureStrategies:
        """ Convert a string into a SupvisorsFailureStrategies enum. """
        try:
            strategy = SupvisorsFailureStrategies[value.upper()]
        except KeyError:
            raise ValueError(f'invalid value for supvisors_failure_strategy: "{value}".'
                             f' expected in {[x.name for x in SupvisorsFailureStrategies]}')
        return strategy

    @staticmethod
    def to_statistics_type(value: str) -> Tuple[bool, bool]:
        """ Convert a string into a pair of boolean values to allow host and/or process statistics. """
        str_stats_types = list_of_strings(value)
        if len(str_stats_types) == 0:
            raise ValueError('invalid value for stats_enabled: <empty>')
        stats_types = []
        for val in str_stats_types:
            # first try to use the enumeration values
            try:
                stats_types.append(StatisticsTypes[val.upper()])
            except KeyError:
                # try the boolean version
                try:
                    stats_types.append(StatisticsTypes.ALL if boolean(val) else StatisticsTypes.OFF)
                except ValueError:
                    raise ValueError(f'invalid value for stats_enabled: "{value}".'
                                     f' expected in {[x.name for x in StatisticsTypes]}')
        return (StatisticsTypes.ALL in stats_types or StatisticsTypes.HOST in stats_types,
                StatisticsTypes.ALL in stats_types or StatisticsTypes.PROCESS in stats_types)

    @staticmethod
    def to_period(value: str) -> float:
        """ Convert a string into a list of period values. """
        try:
            period = float(value)
            if 1.0 > period or period > 3600.0:
                raise ValueError
            return period
        except ValueError:
            raise ValueError(f'invalid value for stats_collecting_period: "{value}".'
                             f' float expected in [1.0;3600.0] (seconds)')

    @staticmethod
    def to_periods(value: str) -> List[float]:
        """ Convert a string into a list of period values. """
        str_periods = list_of_strings(value)
        if len(str_periods) == 0:
            raise ValueError(f'unexpected number of stats_periods: {len(str_periods)}.'
                             ' minimum is 1')
        if len(str_periods) > 3:
            raise ValueError(f'unexpected number of stats_periods: {len(str_periods)}.'
                             ' maximum is 3')
        periods = []
        for val in str_periods:
            try:
                period = float(val)
                if 1.0 > period or period > 3600.0:
                    raise ValueError
                periods.append(period)
            except ValueError:
                raise ValueError(f'invalid value for stats_periods: "{val}".'
                                 f' float expected in [1.0;3600.0] (seconds)')
        return sorted(periods)

    @staticmethod
    def to_histo(value: str) -> int:
        """ Convert a string into a value of historic depth, in [10;1500].

        :param value: the historic size as a string
        :return: the historic size as an integer
        """
        try:
            histo = integer(value)
            if 10 > histo or histo > 1500:
                raise ValueError
            return histo
        except ValueError:
            raise ValueError(f'invalid value for stats_histo: "{value}".'
                             f' integer expected in [10;1500] (seconds)')


class SupvisorsServerOptions(ServerOptions):
    """ Class used to parse the options of the 'supvisors' section in the supervisor configuration file.

    Attributes are:
        - parser: the config parser ;
        - program_configs: the program configuration not retained by Supervisor ;
        - process_configs: the process configuration not retained by Supervisor.
    """

    def __init__(self, supvisors):
        """ Initialization of the attributes. """
        ServerOptions.__init__(self)
        self.supvisors = supvisors
        # attributes
        self.parser = None
        self.program_configs: Dict[str, ProgramConfig] = {}  # {program_name: ProgramConfig}
        self.process_configs: Dict[str, SupvisorsProcessConfig] = {}  # {process_name: SupvisorsProcessConfig}
        # disabilities for local processes (Supervisor issue #591)
        self.disabilities: Dict[str, bool] = {}  # {program_name: disability}
        self.read_disabilities()

    @property
    def logger(self) -> Logger:
        """ Get the Supvisors logger. """
        return self.supvisors.logger

    @property
    def supvisors_options(self) -> SupvisorsOptions:
        """ Get the Supvisors options. """
        return self.supvisors.options

    # Supervisor issue #591
    def read_disabilities(self) -> None:
        """ Read disabilities file and apply data to Supervisor processes.

        :return: None
        """
        self.disabilities = {}
        disabilities_file = self.supvisors_options.disabilities_file
        if disabilities_file:
            self.logger.info(f'SupvisorsServerOptions.read_disabilities: file={disabilities_file}')
            if os.path.isfile(disabilities_file):
                with open(disabilities_file) as in_file:
                    data = json.load(in_file)
                    if type(data) is dict:
                        self.disabilities = data
                        self.logger.debug(f'SupvisorsServerOptions.read_disabilities: disabilities={self.disabilities}')
            else:
                self.logger.debug(f'SupvisorsServerOptions.read_disabilities: {disabilities_file} not found')
        else:
            self.logger.warn('SupvisorsServerOptions.read_disabilities: no persistence for program disabilities')

    def write_disabilities(self) -> None:
        """ Write disabilities file from Supervisor processes.

        :return: None.
        """
        disabilities_file = self.supvisors_options.disabilities_file
        if disabilities_file:
            # serialize to the file defined in options
            with open(disabilities_file, 'w+') as out_file:
                out_file.write(json.dumps(self.disabilities))

    def enable_program(self, program_name: str) -> None:
        """ Re-enable the processes to be started and trigger their autostart if configured to.

        :param program_name: the program to enable
        :return: None
        """
        self.disabilities[program_name] = False
        self.write_disabilities()

    def disable_program(self, program_name: str) -> None:
        """ Disable the program so that the corresponding processes cannot be started.

        :param program_name: the program to disable
        :return: None
        """
        self.disabilities[program_name] = True
        self.write_disabilities()

    # Get additional information not stored by Supervisor when parsing the configuration files
    def _processes_from_section(self, parser, section: str, group_name: str, klass=None) -> List[ProcessConfig]:
        """ This method is overridden to store the configuration information not kept by Supervisor.

        This is originally used in Supervisor to set the real program name from the format defined in the ini file.
        However, Supervisor does not keep this information in its internal structure.

        :param parser: the config parser
        :param section: the program section
        :param group_name: the group that embeds the program definition
        :param klass: the ProcessConfig class (or EventListenerConfig or FastCGIProcessConfig)
        :return: the list of ProcessConfig
        """
        # keep a reference to the parser, so that it is not garbage-collected
        # it will be needed to re-evaluate procnums
        self.parser = parser
        # call super behaviour
        process_configs = ServerOptions._processes_from_section(self, parser, section, group_name, klass)
        # store process configurations and groups
        program_name = section.split(':', 1)[1]
        if program_name in self.program_configs:
            # get the existing program configuration
            program_config = self.program_configs[program_name]
        else:
            # create the program configuration
            program_config = ProgramConfig(program_name, klass)
            program_config.numprocs = int(parser.saneget(section, 'numprocs', '1'))
            program_config.disabled = self.disabilities.setdefault(program_name, False)
            self.program_configs[program_name] = program_config
        # store a generic process_config extension (identical for all groups)
        for idx, process_config in enumerate(process_configs):
            # process_config.name is the process_name (without group name)
            alt_process_config = self.process_configs.get(process_config.name)
            if not alt_process_config:
                # create a process configuration to get the associated program configuration
                alt_process_config = SupvisorsProcessConfig(program_config, idx, process_config.command)
                self.process_configs[process_config.name] = alt_process_config
        # associate the group to the program
        program_config.group_config_info[group_name] = process_configs
        # return super result
        return process_configs

    def get_section(self, program_name: str):
        """ Get the Supervisor relevant section name depending on the program name.

        :param program_name: the name of the program configured
        :return: the Supervisor section name
        """
        klass = self.program_configs[program_name].klass
        if klass is FastCGIProcessConfig:
            return f'fcgi-program:{program_name}'
        if klass is EventListenerConfig:
            return f'eventlistener:{program_name}'
        return f'program:{program_name}'

    def get_subprocesses(self, program_name) -> NameList:
        """ Return all processes related to the program definition.

        :param program_name: the name of the program, as declared in the configuration files.
        :return: all namespecs corresponding to the program.
        """
        program_groups: GroupConfigInfo = self.program_configs[program_name].group_config_info
        return [make_namespec(group_name, process_config.name)
                for group_name, process_config_list in program_groups.items()
                for process_config in process_config_list]

    def update_numprocs(self, program_name: str, numprocs: int) -> GroupConfigInfo:
        """ This method updates the program configuration based on the new numprocs value.

        :param program_name: the program name, as found in the sections of the Supervisor configuration files.
        :param numprocs: the new numprocs value.
        :return: the new process configurations.
        """
        section = self.get_section(program_name)
        # update the parser value
        self.logger.debug(f'SupvisorsServerOptions.update_numprocs: update parser section={section}'
                          f' with numprocs={numprocs}')
        self.parser[section]['numprocs'] = str(numprocs)
        # get the existing program configuration
        program = self.program_configs[program_name]
        program.numprocs = numprocs
        # rebuild the process configs from the new Supervisor configuration
        group_configs = {}
        for group_name, process_list in program.group_config_info.items():
            # remove the former process configuration
            for process in process_list:
                self.process_configs.pop(process.name, None)
            # build the new configuration
            group_configs[group_name] = self.processes_from_section(self.parser, section, group_name, program.klass)
        return group_configs
