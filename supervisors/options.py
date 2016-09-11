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
from supervisor.options import Options, UnhosedConfigParser

from supervisors.types import ConciliationStrategies, DeploymentStrategies


# Options of main section
class SupervisorsOptions(object):
    """ Class used to parse the options of the 'supervisors' section in the supervisor configuration file. """

    def __init__(self):
        # supervisor Options class used to initialize search paths
        options = Options(True)
        # get supervisord.conf file from search paths
        configfile = options.default_configfile()
        # parse file
        parser = UnhosedConfigParser()
        parser.read(configfile)
        # set section
        parser.mysection = 'supervisors'
        if not parser.has_section(parser.mysection):
            raise ValueError('section [{}] not found in config file {}'.format(parser.mysection, configfile))
        # get values
        self.address_list = list(OrderedDict.fromkeys(filter(None, list_of_strings(parser.getdefault('address_list', gethostname())))))
        self.deployment_file = existing_dirpath(parser.getdefault('deployment_file', ''))
        self.internal_port = self.to_port_num(parser.getdefault('internal_port', '65001'))
        self.event_port = self.to_port_num(parser.getdefault('eventp_ort', '65002'))
        self.auto_fence = boolean(parser.getdefault('auto_fence', 'false'))
        self.synchro_timeout = self.to_timeout(parser.getdefault('synchro_timeout', '15'))
        self.conciliation_strategy = self.to_conciliation_strategy(parser.getdefault('conciliation_strategy', 'USER'))
        self.deployment_strategy = self.to_deployment_strategy(parser.getdefault('deployment_strategy', 'CONFIG'))
        # configure statistics
        self.stats_periods = self.to_periods(list_of_strings(parser.getdefault('stats_periods', '10')))
        self.stats_histo = self.to_histo(parser.getdefault('stats_histo', 200))
        # configure logger
        self.logfile = existing_dirpath(parser.getdefault('logfile', '{}.log'.format(parser.mysection)))
        self.logfile_maxbytes = byte_size(parser.getdefault('logfile_maxbytes', '50MB'))
        self.logfile_backups = integer(parser.getdefault('logfile_backups', 10))
        self.loglevel = logging_level(parser.getdefault('loglevel', 'info'))

    # conversion utils (completion of supervisor.datatypes)
    def to_port_num(self, value):
        value = integer(value)
        if 0 < value <= 65535: return value
        raise ValueError('invalid value for port: %d. expected in [1;65535]' % value)

    def to_timeout(self, value):
        value = integer(value)
        if 0 < value <= 1000: return value
        raise ValueError('invalid value for synchro_timeout: %d. expected in [1;1000] (seconds)' % value)

    def to_conciliation_strategy(self, value):
        strategy = ConciliationStrategies._from_string(value)
        if strategy is None:
            raise ValueError('invalid value for conciliation_strategy: {}. expected in {}'.format(value, ConciliationStrategies.values()))
        return strategy

    def to_deployment_strategy(self, value):
        strategy = DeploymentStrategies._from_string(value)
        if strategy is None:
            raise ValueError('invalid value for deployment_strategy: {}. expected in {}'.format(value, DeploymentStrategies.values()))
        return strategy

    def to_periods(self, value):
        if len(value) > 3: raise ValueError('unexpected number of periods: {}. maximum is 3'.format(value))
        periods = [ ]
        for val in value:
            period = integer(val)
            if 5 > period or period > 3600: raise ValueError('invalid value for period: {}. expected in [5;3600] (seconds)'.format(val))
            if period % 5 != 0: raise ValueError('invalid value for period: %d. expected multiple of 5' % period)
            periods.append(period)
        return sorted(filter(None, periods))

    def to_histo(self, value):
        histo = integer(value)
        if 10 <= histo <= 1500: return histo
        raise ValueError('invalid value for histo: {}. expected in [10;1500] (seconds)'.format(value))
