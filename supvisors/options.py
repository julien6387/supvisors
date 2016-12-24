#!/usr/bin/python
#-*- coding: utf-8 -*-

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

from supervisor.datatypes import boolean, integer, existing_dirpath, byte_size, logging_level, list_of_strings
from supervisor.options import ServerOptions

from supvisors.ttypes import ConciliationStrategies, DeploymentStrategies


# Options of main section
class SupvisorsOptions(ServerOptions):
    """ Class used to parse the options of the 'supvisors' section in the supervisor configuration file.
    
    Attributes are:
    - address_list: list of host names or IP addresses where supvisors will be running,
    - deployment_file: absolute or relative path to the XML deployment file,
    - internal_port: port number used to publish local events to remote Supvisors instances,
    - event_port: port number used to publish all Supvisors events,
    - auto_fence: when True, Supvisors won't try to reconnect to a Supvisors instance that has been inactive,
    - synchro_timeout: time in seconds that Supvisors waits for all expected Supvisors instances to publish,
    - conciliation_strategy: strategy used to solve conflicts when Supvisors has detected that multiple instances of the same program are running,
    - deployment_strategy: strategy used to start applications on addresses,
    - stats_periods: list of periods for which the statistics will be provided in the Supvisors web page,
    - stats_histo: depth of statistics history,
    - logfile: absolute or relative path of the Supvisors log file,
    - logfile_maxbytes: maximum size of the Supvisors log file,
    - logfile_backups: number of Supvisors backup log files,
    - loglevel: logging level,

    - procnumbers: a dictionary giving the number of the program in a homogeneous group,

    - _Section: constant for the name of the Supvisors section in the Supervisor configuration file.
    """

    _Section = 'supvisors'

    def __init__(self):
        """ Initialization of the attributes. 
        Default parameters fit, so realize is called directly. """
        ServerOptions.__init__(self)
        self.procnumbers = {}
        self.realize()

    def _processes_from_section(self, parser, section, group_name, klass=None):
        """ This method is overriden to store the program number of a homogeneous program.
        This is used in Supervisor to set the real program name from the format defined in the ini file.
        However, Supervisor does not keep this information in its internal structure. """
        # call super behaviour
        programs = ServerOptions._processes_from_section(self, parser, section, group_name, klass)
        # store the number of each program
        for idx, program in enumerate(programs):
            self.procnumbers[program.name] = idx
        # return original result
        return programs

    def server_configs_from_parser(self, parser):
        """ The following has nothing to deal with Supervisor's server configurations.
        It gets Supvisors configuration.
        Supervisor's ServerOptions has not been designed to be specialized.
        This method is overriden just to have an access point to the Supervisor parser. """
        configs = ServerOptions.server_configs_from_parser(self, parser)
        # set section
        if not parser.has_section(self._Section):
            raise ValueError('section [{}] not found in ini file {}'.format(self._Section))
        parser.mysection = self._Section
        # get values
        self.address_list = list(OrderedDict.fromkeys(filter(None, list_of_strings(parser.getdefault('address_list', gethostname())))))
        self.deployment_file = existing_dirpath(parser.getdefault('deployment_file', ''))
        self.internal_port = self.to_port_num(parser.getdefault('internal_port', '65001'))
        self.event_port = self.to_port_num(parser.getdefault('event_port', '65002'))
        self.auto_fence = boolean(parser.getdefault('auto_fence', 'false'))
        self.synchro_timeout = self.to_timeout(parser.getdefault('synchro_timeout', '15'))
        self.conciliation_strategy = self.to_conciliation_strategy(parser.getdefault('conciliation_strategy', 'USER'))
        self.deployment_strategy = self.to_deployment_strategy(parser.getdefault('deployment_strategy', 'CONFIG'))
        # configure statistics
        self.stats_periods = self.to_periods(list_of_strings(parser.getdefault('stats_periods', '10')))
        self.stats_histo = self.to_histo(parser.getdefault('stats_histo', 200))
        # configure logger
        self.logfile = existing_dirpath(parser.getdefault('logfile', '{}.log'.format(self._Section)))
        self.logfile_maxbytes = byte_size(parser.getdefault('logfile_maxbytes', '50MB'))
        self.logfile_backups = integer(parser.getdefault('logfile_backups', 10))
        self.loglevel = logging_level(parser.getdefault('loglevel', 'info'))
        # return original result
        return configs

    # conversion utils (completion of supervisor.datatypes)
    @staticmethod
    def to_port_num(value):
        """ Convert a string into a port number. """
        value = integer(value)
        if 0 < value <= 65535:
            return value
        raise ValueError('invalid value for port: %d. expected in [1;65535]' % value)

    @staticmethod
    def to_timeout(value):
        """ Convert a string into a timeout value. """
        value = integer(value)
        if 0 < value <= 1000:
            return value
        raise ValueError('invalid value for synchro_timeout: %d. expected in [1;1000] (seconds)' % value)

    @staticmethod
    def to_conciliation_strategy(value):
        """ Convert a string into a ConciliationStrategies enum. """
        strategy = ConciliationStrategies._from_string(value)
        if strategy is None:
            raise ValueError('invalid value for conciliation_strategy: {}. expected in {}'.format(value, ConciliationStrategies.values()))
        return strategy

    @staticmethod
    def to_deployment_strategy(value):
        """ Convert a string into a DeploymentStrategies enum. """
        strategy = DeploymentStrategies._from_string(value)
        if strategy is None:
            raise ValueError('invalid value for deployment_strategy: {}. expected in {}'.format(value, DeploymentStrategies.values()))
        return strategy

    @staticmethod
    def to_periods(value):
        """ Convert a string into a list of period values. """
        if len(value) > 3:
            raise ValueError('unexpected number of periods: {}. maximum is 3'.format(value))
        periods = [ ]
        for val in value:
            period = integer(val)
            if 5 > period or period > 3600:
                raise ValueError('invalid value for period: {}. expected in [5;3600] (seconds)'.format(val))
            if period % 5 != 0:
                raise ValueError('invalid value for period: %d. expected multiple of 5' % period)
            periods.append(period)
        return sorted(filter(None, periods))

    @staticmethod
    def to_histo(value):
        """ Convert a string into a value of historic depth. """
        histo = integer(value)
        if 10 <= histo <= 1500:
            return histo
        raise ValueError('invalid value for histo: {}. expected in [10;1500] (seconds)'.format(value))
