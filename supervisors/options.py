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

import ConfigParser
from collections import OrderedDict
from socket import gethostname

from supervisor.datatypes import boolean, integer, existing_dirpath, byte_size, logging_level, list_of_strings
from supervisor.options import Options

from supervisors.ttypes import ConciliationStrategies, DeploymentStrategies


# Options of main section
class SupervisorsOptions(object):
    """ Class used to parse the options of the 'supervisors' section in the supervisor configuration file. """

    _Section = 'supervisors'

    def __init__(self, fp=None):
        self.parser = ConfigParser.RawConfigParser()
        if fp:
            # contents provided, parse now
            self.parse_fp(fp)
        else:
            # supervisor Options class used (lazily) to initialize search paths
            options = Options(True)
            configfile = options.default_configfile()
            # parse the contents of the file
            with open(configfile) as fp:
                self.parse_fp(fp, configfile)

    def parse_fp(self, fp, filename=None):
        self.parser.readfp(fp, filename)
        # set section
        if not self.parser.has_section(self._Section):
            raise ValueError('section [{}] not found in config file {}'.format(self._Section, filename))
        # get values
        self.address_list = list(OrderedDict.fromkeys(filter(None, list_of_strings(self.get_default('address_list', gethostname())))))
        self.deployment_file = existing_dirpath(self.get_default('deployment_file', ''))
        self.internal_port = self.to_port_num(self.get_default('internal_port', '65001'))
        self.event_port = self.to_port_num(self.get_default('event_port', '65002'))
        self.auto_fence = boolean(self.get_default('auto_fence', 'false'))
        self.synchro_timeout = self.to_timeout(self.get_default('synchro_timeout', '15'))
        self.conciliation_strategy = self.to_conciliation_strategy(self.get_default('conciliation_strategy', 'USER'))
        self.deployment_strategy = self.to_deployment_strategy(self.get_default('deployment_strategy', 'CONFIG'))
        # configure statistics
        self.stats_periods = self.to_periods(list_of_strings(self.get_default('stats_periods', '10')))
        self.stats_histo = self.to_histo(self.get_default('stats_histo', 200))
        # configure logger
        self.logfile = existing_dirpath(self.get_default('logfile', '{}.log'.format(self._Section)))
        self.logfile_maxbytes = byte_size(self.get_default('logfile_maxbytes', '50MB'))
        self.logfile_backups = integer(self.get_default('logfile_backups', 10))
        self.loglevel = logging_level(self.get_default('loglevel', 'info'))

    def get_default(self, option, default_value):
        try:
            return self.parser.get(self._Section, option)
        except ConfigParser.NoOptionError:
            return default_value

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
