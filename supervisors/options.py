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

from supervisors.types import *
from supervisor.datatypes import boolean, integer, existing_dirpath, byte_size, logging_level, list_of_strings

# Options of main section
class _SupervisorsOptions(object):
    # logger output
    loggerFormat = '%(asctime)s %(levelname)s %(message)s\n'

    def realize(self):
        # supervisor Options class used to initialize search paths
        from supervisor.options import Options, UnhosedConfigParser
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
        from collections import OrderedDict
        import socket
        self.addresslist = list(OrderedDict.fromkeys(filter(None, list_of_strings(parser.getdefault('addresslist', socket.gethostname())))))
        self.internalport = self._toPortNum(parser.getdefault('internalport', '65001'))
        self.eventport = self._toPortNum(parser.getdefault('eventport', '65002'))
        self.deployment_file = existing_dirpath(parser.getdefault('deployment_file', ''))
        self.auto_fence = boolean(parser.getdefault('auto_fence', 'false'))
        self.statsport = self._toPortNum(parser.getdefault('statsport', '65003'))
        self.synchro_timeout = self._toTimeout(parser.getdefault('synchro_timeout', '15'))
        self.conciliation_strategy = self._toConciliationStrategy(parser.getdefault('conciliation_strategy', 'USER'))
        self.deployment_strategy = self._toDeploymentStrategy(parser.getdefault('deployment_strategy', 'CONFIG'))
        # configure logger
        logfile = existing_dirpath(parser.getdefault('logfile', '{}.log'.format(parser.mysection)))
        logfile_maxbytes = byte_size(parser.getdefault('logfile_maxbytes', '50MB'))
        logfile_backups = integer(parser.getdefault('logfile_backups', 10))
        loglevel = logging_level(parser.getdefault('loglevel', 'info'))
        # WARN: restart problems with loggers. do NOT close previous logger if any (closing rolling file handler leads to IOError)
        from supervisors.infosource import infoSource
        from supervisor.loggers import getLogger
        stdout = infoSource.supervisord.options.nodaemon
        self.logger = getLogger(logfile, loglevel, self.loggerFormat, True, logfile_maxbytes, logfile_backups, stdout)

    # conversion utils (completion of supervisor.datatypes)
    def _toPortNum(self, value):
        value = integer(value)
        if 0 < value <= 65535: return value
        raise ValueError('invalid value for port: %d. expected in [1;65535]' % value)

    def _toTimeout(self, value):
        value = integer(value)
        if 0 < value <= 1000: return value
        raise ValueError('invalid value for synchro_timeout: %d. expected in [1;1000]' % value)

    def _toConciliationStrategy(self, value):
        strategy = stringToConciliationStrategy(value)
        if strategy is None:
            raise ValueError('invalid value for conciliation_strategy: {}. expected in {}'.format(value, conciliationStrategiesValues()))
        return strategy

    def _toDeploymentStrategy(self, value):
        strategy = stringToDeploymentStrategy(value)
        if strategy is None:
            raise ValueError('invalid value for deployment_strategy: {}. expected in {}'.format(value, deploymentStrategiesValues()))
        return strategy


options = _SupervisorsOptions()
