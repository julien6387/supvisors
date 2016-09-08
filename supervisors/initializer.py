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

from supervisor.loggers import getLogger
from supervisor.xmlrpc import Faults, RPCError

from supervisors.addressmapper import AddressMapper
from supervisors.context import Context
from supervisors.infosource import SupervisordSource
from supervisors.listener import SupervisorListener
from supervisors.options import SupervisorsOptions
from supervisors.parser import Parser
from supervisors.publisher import EventPublisher
from supervisors.statemachine import FiniteStateMachine


class Supervisors(object):
    """ the Supervisors class  """

    # logger output
    LOGGER_FORMAT = '%(asctime)s %(levelname)s %(message)s\n'

    def __init__(self, supervisord):
        # configure supervisor info source
        self.infoSource = SupervisordSource(supervisord)
        # get options from config file
        self.options = SupervisorsOptions()
        # WARN: restart problems with loggers. do NOT close previous logger if any (closing rolling file handler leads to IOError)
        stdout = supervisord.options.nodaemon
        self.logger = getLogger(self.options.logfile, self.options.loglevel, Supervisors.LOGGER_FORMAT, True, self.options.logfile_maxbytes, self.options.logfile_backups, stdout)
        # set addresses and check local address
        self.addressMapper = AddressMapper(self.logger)
        self.addressMapper.addresses = self.options.addressList
        if not self.addressMapper.local_address:
            raise RPCError(Faults.SUPERVISORS_CONF_ERROR, 'local host unexpected in address list: {}'.format(self.options.addressList))
        # create context data
        self.context = Context(self)
        # create state machine
        self.fsm = FiniteStateMachine(self)
        self.fsm.restart()
        # check parsing
        try:
            self.parser = Parser(self.options.deploymentFile)
        except:
            raise RPCError(Faults.SUPERVISORS_CONF_ERROR, 'cannot parse deployment file: {}'.format(self.options.deploymentFile))
        # create  event publisher
        self.eventPublisher = EventPublisher(self)
        # create event subscriber
        self.listener = SupervisorListener()
