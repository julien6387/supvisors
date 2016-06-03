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

from supervisors.types import ConciliationStrategies, stringToConciliationStrategy, conciliationStrategiesValues

from supervisor.datatypes import integer, existing_dirpath, byte_size, logging_level, list_of_strings
from supervisor.options import Options

# conversion utils (completion of supervisor.datatypes)
def _toPortNum(value):
    if value is None: return None
    value = int(value)
    if 0 < value <= 65535: return value
    raise ValueError('invalid value for port: %d. expected in [1;65535]' % value)

def _toTimeout(value):
    if value is None: return 10
    value = int(value)
    if 0 < value <= 1000: return value
    raise ValueError('invalid value for deployment_timeout: %d. expected in [1;1000]' % value)

def _toConciliationStrategy(value):
    if value is None: return ConciliationStrategies.APPLICATIVE
    conciliation = stringToConciliationStrategy(value)
    if conciliation is None:
        raise ValueError('invalid value for conciliation: {}. expected in {}'.format(value,  conciliationStrategiesValues()))
    return conciliation


# inheritance not fully compliant but used to get some useful stuff
class _OptionsParser(Options):
    # Logger definition
    loggerFormat =  '%(asctime)s %(levelname)s %(message)s\n'

    def __init__(self):
        # used to initialize search paths
        Options.__init__(self, True)
        # get supervisord.conf file from search paths
        self._configfile = self.default_configfile()
        # parse file
        from supervisor.options import UnhosedConfigParser
        self._parser = UnhosedConfigParser()
        self._parser.read(self._configfile)

    def getOptions(self, section, optionsObject, logging):
        self._parser.mysection = section
        # get values
        if not self._parser.has_section(section):
            raise ValueError('section [{}] not found in config file {}'.format(section, self._configfile))
        # required
        for x in optionsObject.required_options:
            setattr(optionsObject, x, self._parser.getdefault(x, None))
            if not hasattr(optionsObject, x):
                raise ValueError('required value {} not found in section [{}] of config file {}'.format(x, section, self._configfile))
        # optional
        for x in optionsObject.optional_options:
            setattr(optionsObject, x, self._parser.getdefault(x, None))
        # logger
        if logging: 
            logfile = existing_dirpath(self._parser.getdefault('logfile', '{}.log'.format(section)))
            logfile_maxbytes = byte_size(self._parser.getdefault('logfile_maxbytes', '50MB'))
            logfile_backups = integer(self._parser.getdefault('logfile_backups', 10))
            loglevel = logging_level(self._parser.getdefault('loglevel', 'info'))
            # configure logger
            from supervisors.infosource import infoSource
            try: stdout = (section == 'supervisors') and not infoSource.source.daemon
            except AttributeError: stdout = False
            # WARN: restart problems with loggers. do NOT close previous logger if any (closing rolling file handler leads to IOError)
            from supervisor.loggers import getLogger
            optionsObject.logger = getLogger(logfile, loglevel, self.loggerFormat, True, logfile_maxbytes, logfile_backups, stdout)


# Options of listener section
class _ListenerOptions(object):
    required_options = ('eventport', )
    optional_options = ()

    def realize(self, logging=None):
        # get options from file
        optionParser = _OptionsParser()
        optionParser.getOptions('listener', self, logging)
        # reformat
        self.eventport = _toPortNum(self.eventport)


# Options of main section
class _MainOptions(object):
    required_options = ('addresslist', 'deployment_file', 'masterport')
    optional_options = ('authport', 'statsport', 'rpcport', 'synchro_timeout', 'conciliation')
    
    def realize(self, logging=None):
        # get options from file
        optionParser = _OptionsParser()
        optionParser.getOptions('supervisors', self, logging)
        # reformat
        from collections import OrderedDict
        self.addresslist = list(OrderedDict.fromkeys(filter(None, list_of_strings(self.addresslist))))
        self.masterport = _toPortNum(self.masterport)
        self.authport = _toPortNum(self.authport)
        self.statsport = _toPortNum(self.statsport)
        self.rpcport = _toPortNum(self.rpcport)
        self.synchro_timeout = _toTimeout(self.synchro_timeout)
        self.conciliation = _toConciliationStrategy(self.conciliation)


#################################
### exportable part
mainOptions = _MainOptions()
listenerOptions = _ListenerOptions()
#################################


# unit test
if __name__ == "__main__":
    print 'found main options: {}'.format(mainOptions.__dict__)
    print 'found listener options: {}'.format(listenerOptions.__dict__)
