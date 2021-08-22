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

from supervisor.datatypes import (Automatic, logfile_name,
                                  boolean, integer, byte_size,
                                  logging_level,
                                  existing_dirpath,
                                  list_of_strings)
from supervisor.options import ServerOptions

from .ttypes import ConciliationStrategies, StartingStrategies


# Options of main section
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
        - loglevel: logging level,
        - procnumbers: a dictionary giving the number of the program in a homogeneous group.
    """

    SYNCHRO_TIMEOUT_MIN = 15

    _Options = ['address_list', 'rules_file', 'internal_port', 'event_port', 'auto_fence',
                'synchro_timeout', 'force_synchro_if',
                'conciliation_strategy', 'starting_strategy',
                'stats_periods', 'stats_histo', 'stats_irix_mode',
                'logfile', 'logfile_maxbytes', 'logfile_backups', 'loglevel']

    def __init__(self):
        """ Initialization of the attributes. """
        # option list
        for option in SupvisorsOptions._Options:
            setattr(self, option, None)
        # second parse
        self.procnumbers = {}

    def __str__(self):
        """ Contents as string. """
        return ('address_list={} rules_file={} internal_port={} event_port={} auto_fence={} '
                'synchro_timeout={} force_synchro_if={} conciliation_strategy={} '
                'starting_strategy={} stats_periods={} stats_histo={} '
                'stats_irix_mode={} logfile={} logfile_maxbytes={} '
                'logfile_backups={} loglevel={}'.format(self.address_list, self.rules_file,
                                                        self.internal_port, self.event_port, self.auto_fence,
                                                        self.synchro_timeout, self.force_synchro_if,
                                                        self.conciliation_strategy, self.starting_strategy,
                                                        self.stats_periods, self.stats_histo, self.stats_irix_mode,
                                                        self.logfile, self.logfile_maxbytes, self.logfile_backups,
                                                        self.loglevel))


class SupvisorsServerOptions(ServerOptions):
    """ Class used to parse the options of the 'supvisors' section in the
    supervisor configuration file.

    Attributes are:
        - supvisors_options: the instance holding all Supvisors options,
        - _Section: constant for the name of the Supvisors section in the Supervisor configuration file.
    """

    # Name of the Supvisors section in the Supervisor configuration file
    _Section = 'supvisors'

    def __init__(self):
        """ Initialization of the attributes. """
        ServerOptions.__init__(self)
        self.supvisors_options = SupvisorsOptions()

    def _processes_from_section(self, parser, section, group_name, klass=None):
        """ This method is overridden to: store the program number of a homogeneous program.

        This is originally used in Supervisor to set the real program name from the format defined in the ini file.
        However, Supervisor does not keep this information in its internal structure.
        """
        # call super behaviour
        programs = ServerOptions._processes_from_section(self, parser, section, group_name, klass)
        # store the number of each program
        for idx, program in enumerate(programs):
            self.supvisors_options.procnumbers[program.name] = idx
        # return original result
        return programs

    def server_configs_from_parser(self, parser):
        """ The following has nothing to deal with Supervisor's server configurations.
        It gets Supvisors configuration.
        Supervisor's ServerOptions has not been designed to be specialized.
        This method is overridden just to have an access point to the Supervisor parser.
        """
        configs = ServerOptions.server_configs_from_parser(self, parser)
        # set section
        if not parser.has_section(SupvisorsServerOptions._Section):
            raise ValueError('.ini file ({}) does not include a [{}] section'
                             .format(self.configfile, SupvisorsServerOptions._Section))
        temp, parser.mysection = parser.mysection, SupvisorsServerOptions._Section
        # get values
        opt = self.supvisors_options
        opt.address_list = filter(None, list_of_strings(parser.getdefault('address_list', gethostname())))
        opt.address_list = list(OrderedDict.fromkeys(opt.address_list))
        opt.rules_file = parser.getdefault('rules_file', None)
        if opt.rules_file:
            opt.rules_file = existing_dirpath(opt.rules_file)
        opt.internal_port = self.to_port_num(parser.getdefault('internal_port', '65001'))
        opt.event_port = self.to_port_num(parser.getdefault('event_port', '65002'))
        opt.auto_fence = boolean(parser.getdefault('auto_fence', 'false'))
        opt.synchro_timeout = self.to_timeout(parser.getdefault('synchro_timeout', str(opt.SYNCHRO_TIMEOUT_MIN)))
        opt.force_synchro_if = filter(None, list_of_strings(parser.getdefault('force_synchro_if', None)))
        opt.force_synchro_if = {node for node in opt.force_synchro_if if node in opt.address_list}
        opt.conciliation_strategy = self.to_conciliation_strategy(parser.getdefault('conciliation_strategy', 'USER'))
        opt.starting_strategy = self.to_starting_strategy(parser.getdefault('starting_strategy', 'CONFIG'))
        # configure statistics
        opt.stats_periods = self.to_periods(list_of_strings(parser.getdefault('stats_periods', '10')))
        opt.stats_histo = self.to_histo(parser.getdefault('stats_histo', 200))
        opt.stats_irix_mode = boolean(parser.getdefault('stats_irix_mode', 'false'))
        # configure logger
        opt.logfile = logfile_name(parser.getdefault('logfile', Automatic))
        opt.logfile_maxbytes = byte_size(parser.getdefault('logfile_maxbytes', '50MB'))
        opt.logfile_backups = integer(parser.getdefault('logfile_backups', 10))
        opt.loglevel = logging_level(parser.getdefault('loglevel', 'info'))
        # reset mysection and return original result
        parser.mysection = temp
        return configs

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
        if 15 <= value <= 1200:
            return value
        raise ValueError('invalid value for synchro_timeout: %d. expected in [15;1200] (seconds)' % value)

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
