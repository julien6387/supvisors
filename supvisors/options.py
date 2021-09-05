#!/usr/bin/python
# -*- coding: utf-8 -*-

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

from collections import OrderedDict
from socket import gethostname
from typing import Dict, List, TypeVar

from supervisor.datatypes import (Automatic, logfile_name,
                                  boolean, integer, byte_size,
                                  logging_level,
                                  existing_dirpath,
                                  list_of_strings)
from supervisor.loggers import Logger
from supervisor.options import ServerOptions, ProcessConfig, FastCGIProcessConfig, EventListenerConfig

from .ttypes import ConciliationStrategies, StartingStrategies


class SupvisorsOptions(object):
    """ Holder of the Supvisors options.

    Attributes are:

        - address_list: list of node names or IP addresses where supvisors will be running,
        - rules_file: absolute or relative path to the XML rules file,
        - internal_port: port number used to publish local events to remote Supvisors instances,
        - event_port: port number used to publish all Supvisors events,
        - auto_fence: when True, Supvisors won't try to reconnect to a Supvisors instance that has been inactive,
        - synchro_timeout: time in seconds that Supvisors waits for all expected Supvisors instances to publish,
        - force_synchro_if: subset of address_list that will force the end of synchro when all RUNNING,
        - conciliation_strategy: strategy used to solve conflicts when Supvisors has detected multiple running
          instances of the same program,
        - starting_strategy: strategy used to start processes on addresses,
        - stats_periods: list of periods for which the statistics will be provided in the Supvisors web page,
        - stats_histo: depth of statistics history,
        - logfile: absolute or relative path of the Supvisors log file,
        - logfile_maxbytes: maximum size of the Supvisors log file,
        - logfile_backups: number of Supvisors backup log files,
        - loglevel: logging level.
    """

    SYNCHRO_TIMEOUT_MIN = 15
    SYNCHRO_TIMEOUT_MAX = 1200

    def __init__(self, **config):
        """ Initialization of the attributes.

        :param config: the configuration provided by Supervisor from the [rpcinterface:supvisors] section
        """
        # get values from config
        self.address_list = filter(None, list_of_strings(config.get('address_list', gethostname())))
        self.address_list = list(OrderedDict.fromkeys(self.address_list))
        self.rules_file = config.get('rules_file', None)
        if self.rules_file:
            self.rules_file = existing_dirpath(self.rules_file)
        self.internal_port = self.to_port_num(config.get('internal_port', '65001'))
        self.event_port = self.to_port_num(config.get('event_port', '65002'))
        self.auto_fence = boolean(config.get('auto_fence', 'false'))
        self.synchro_timeout = self.to_timeout(config.get('synchro_timeout', str(self.SYNCHRO_TIMEOUT_MIN)))
        self.force_synchro_if = filter(None, list_of_strings(config.get('force_synchro_if', None)))
        self.force_synchro_if = {node for node in self.force_synchro_if if node in self.address_list}
        self.conciliation_strategy = self.to_conciliation_strategy(config.get('conciliation_strategy', 'USER'))
        self.starting_strategy = self.to_starting_strategy(config.get('starting_strategy', 'CONFIG'))
        # configure statistics
        self.stats_periods = self.to_periods(list_of_strings(config.get('stats_periods', '10')))
        self.stats_histo = self.to_histo(config.get('stats_histo', 200))
        self.stats_irix_mode = boolean(config.get('stats_irix_mode', 'false'))
        # configure logger
        self.logfile = logfile_name(config.get('logfile', Automatic))
        self.logfile_maxbytes = byte_size(config.get('logfile_maxbytes', '50MB'))
        self.logfile_backups = integer(config.get('logfile_backups', 10))
        self.loglevel = logging_level(config.get('loglevel', 'info'))

    def __str__(self):
        """ Contents as string. """
        return "address_list={} rules_file={} internal_port={} event_port={} auto_fence={}"\
               " synchro_timeout={} force_synchro_if={} conciliation_strategy={}"\
               " starting_strategy={} stats_periods={} stats_histo={} stats_irix_mode={}"\
               " logfile={} logfile_maxbytes={} logfile_backups={} loglevel={}"\
               .format(self.address_list, self.rules_file, self.internal_port, self.event_port, self.auto_fence,
                       self.synchro_timeout, self.force_synchro_if,
                       self.conciliation_strategy.name, self.starting_strategy.name,
                       self.stats_periods, self.stats_histo, self.stats_irix_mode,
                       self.logfile, self.logfile_maxbytes, self.logfile_backups, self.loglevel)

    # conversion utils (completion of supervisor.datatypes)
    @staticmethod
    def to_port_num(value: str) -> int:
        """ Convert a string into a port number, in [1;65535].

        :param value: the port number as a string
        :return: the port number as an integer
        """
        value = integer(value)
        if 0 < value <= 65535:
            return value
        raise ValueError('invalid value for port: %d. expected in [1;65535]' % value)

    @staticmethod
    def to_timeout(value: str) -> int:
        """ Convert a string into a timeout value, in [15;1200].

        :param value: the timeout as a string
        :return: the timeout as an integer
        """
        value = integer(value)
        if SupvisorsOptions.SYNCHRO_TIMEOUT_MIN <= value <= SupvisorsOptions.SYNCHRO_TIMEOUT_MAX:
            return value
        raise ValueError('invalid value for synchro_timeout: {}. expected in [{};{}] (seconds)'
                         .format(value, SupvisorsOptions.SYNCHRO_TIMEOUT_MIN, SupvisorsOptions.SYNCHRO_TIMEOUT_MAX))

    @staticmethod
    def to_conciliation_strategy(value):
        """ Convert a string into a ConciliationStrategies enum. """
        try:
            strategy = ConciliationStrategies[value]
        except KeyError:
            raise ValueError('invalid value for conciliation_strategy: {}. expected in {}'
                             .format(value, ConciliationStrategies._member_names_))
        return strategy

    @staticmethod
    def to_starting_strategy(value):
        """ Convert a string into a StartingStrategies enum. """
        try:
            strategy = StartingStrategies[value]
        except KeyError:
            raise ValueError('invalid value for starting_strategy: {}. expected in {}'
                             .format(value, StartingStrategies._member_names_))
        return strategy

    @staticmethod
    def to_periods(value):
        """ Convert a string into a list of period values. """
        if len(value) == 0:
            raise ValueError('unexpected number of stats_periods: {}. minimum is 1'.format(value))
        if len(value) > 3:
            raise ValueError('unexpected number of stats_periods: {}. maximum is 3'.format(value))
        periods = []
        for val in value:
            period = integer(val)
            if 5 > period or period > 3600:
                raise ValueError('invalid value for stats_periods: {}. expected in [5;3600] (seconds)'.format(val))
            if period % 5 != 0:
                raise ValueError('invalid value for stats_periods: %d. expected multiple of 5' % period)
            periods.append(period)
        return sorted(filter(None, periods))

    @staticmethod
    def to_histo(value: str) -> int:
        """ Convert a string into a value of historic depth, in [10;1500].

        :param value: the historic size as a string
        :return: the historic size as an integer
        """
        histo = integer(value)
        if 10 <= histo <= 1500:
            return histo
        raise ValueError('invalid value for stats_histo: {}. expected in [10;1500] (seconds)'.format(value))


class SupvisorsServerOptions(ServerOptions):
    """ Class used to parse the options of the 'supvisors' section in the supervisor configuration file. """

    # annotation types
    ProcessConfigList = List[ProcessConfig]
    ProcessConfigInfo = Dict[str, ProcessConfigList]
    ProcessGroupInfo = Dict[str, ProcessConfigInfo]
    ProcessConfigType = TypeVar('ProcessConfigType', bound='Type[ProcessConfig]')
    ProcessClassInfo = Dict[str, ProcessConfigType]

    def __init__(self, logger: Logger):
        """ Initialization of the attributes. """
        ServerOptions.__init__(self)
        # keep a reference to the logger
        self.logger: Logger = logger
        # attributes
        self.parser = None
        self.program_class: SupvisorsServerOptions.ProcessClassInfo = {}
        self.process_groups: SupvisorsServerOptions.ProcessGroupInfo = {}
        self.procnumbers: Dict[str, int] = {}

    def _processes_from_section(self, parser, section, group_name, klass=None) -> List[ProcessConfig]:
        """ This method is overridden to: store the program number of a homogeneous program.

        This is originally used in Supervisor to set the real program name from the format defined in the ini file.
        However, Supervisor does not keep this information in its internal structure.

        :param parser: the config parser
        :param section: the program section
        :param group_name: the group that embeds the program definition
        :param klass: the ProcessConfig class (may be EventListenerConfig or FastCGIProcessConfig)
        :return: the list of ProcessConfig
        """
        # keep a reference to the parser, so that it is not garbage-collected
        # it will be needed to re-evaluate procnums
        self.parser = parser
        # call super behaviour
        process_configs = ServerOptions._processes_from_section(self, parser, section, group_name, klass)
        # store the number of each program
        for idx, program in enumerate(process_configs):
            self.procnumbers[program.name] = idx
        # store process configurations and groups
        program_name = section.split(':', 1)[1]
        process_group = self.process_groups.setdefault(program_name, {})
        process_group[group_name] = process_configs
        # store the program class type
        self.program_class[program_name] = klass
        # return original result
        return process_configs

    def get_section(self, program_name: str):
        klass = self.program_class[program_name]
        if klass is FastCGIProcessConfig:
            return 'fcgi-program:%s' % program_name
        if klass is EventListenerConfig:
            return 'eventlistener:%s' % program_name
        return 'program:%s' % program_name

    def update_numprocs(self, program_name: str, numprocs: int) -> str:
        """ This method updates the numprocs value directly in the configuration parser.

        :param program_name: the program name, as found in the sections of the Supervisor configuration files
        :param numprocs: the new numprocs value
        :return: The section updated
        """
        section = self.get_section(program_name)
        self.logger.debug('SupvisorsServerOptions.update_numprocs: update parser section: {}'.format(section))
        self.parser[section]['numprocs'] = '%d' % numprocs
        return section

    def reload_processes_from_section(self, section: str, group_name: str) -> List[ProcessConfig]:
        """ This method rebuilds the ProcessConfig instances for the program.

        :param section: the program section in the configuration files
        :param group_name: the group that embeds the program definition
        :return: the list of ProcessConfig
        """
        # reset corresponding store procnumbers
        program_name = section.split(':')[1]
        for process_list in self.process_groups[program_name].values():
            for process in process_list:
                self.procnumbers.pop(process.name, None)
        # call parser again
        klass = self.program_class[program_name]
        return self.processes_from_section(self.parser, section, group_name, klass)
