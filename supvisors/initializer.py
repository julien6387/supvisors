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

import sys

from supervisor import loggers, supervisord
from supervisor.supervisord import Supervisor
from supervisor.xmlrpc import Faults, RPCError

from .addressmapper import AddressMapper
from .commander import Starter, Stopper
from .context import Context
from .infosource import SupervisordSource
from .listener import SupervisorListener
from .options import *
from .sparser import Parser
from .statemachine import FiniteStateMachine
from .statscompiler import StatisticsCompiler
from .strategy import RunningFailureHandler


class Supvisors(object):
    """ The Supvisors class used as a global structure passed to most Supvisors objects. """

    # logger output (use ';' as separator as easier to cut)
    LOGGER_FORMAT = '%(asctime)s;%(levelname)s;%(message)s\n'

    def __init__(self, supervisor: Supervisor, **config) -> None:
        """ Instantiation of all the Supvisors objects.

        :param supervisord: the Supervisor global structure
        """
        # declare zmq context (will be created in listener)
        self.zmq = None
        # get options from config file
        self.options = SupvisorsOptions(**config)
        # create logger
        self.logger = self.create_logger(supervisor)
        # re-evaluate the Supervisor configuration to get what hasn't been stored
        self.server_options = SupvisorsServerOptions(self.logger)
        self.server_options.realize(sys.argv[1:], doc=supervisord.__doc__)
        # configure supervisor info source
        self.info_source = SupervisordSource(supervisor, self.logger)
        # set addresses and check local address
        self.address_mapper = AddressMapper(self.logger)
        self.address_mapper.node_names = self.options.address_list
        if not self.address_mapper.local_node_name:
            raise RPCError(Faults.SUPVISORS_CONF_ERROR,
                           'local node is expected in node list: {}'.format(self.options.address_list))
        # create context data
        self.context = Context(self)
        # create application starter and stopper
        self.starter = Starter(self)
        self.stopper = Stopper(self)
        # create statistics handler
        self.statistician = StatisticsCompiler(self)
        # create the failure handler of crashing processes
        self.failure_handler = RunningFailureHandler(self)
        # create state machine
        self.fsm = FiniteStateMachine(self)
        # check parsing
        try:
            self.parser = Parser(self)
        except Exception as exc:
            self.logger.warn('Supvisors: cannot parse rules file: {} - {}'.format(self.options.rules_file, exc))
            self.parser = None
        # create event subscriber
        self.listener = SupervisorListener(self)

    def create_logger(self, supervisor):
        """ Create the logger that will be used in Supvisors.
        If logfile is not set or set to AUTO, Supvisors will use Supervisor logger.
        Else Supvisors will log in the file defined in option.
        """
        if self.options.logfile is Automatic:
            # use Supervisord logger but patch format anyway
            logger = supervisor.options.logger
            for handler in logger.handlers:
                handler.setFormat(Supvisors.LOGGER_FORMAT)
            return logger
        # else create own Logger using Supervisor functions
        nodaemon = supervisor.options.nodaemon
        silent = supervisor.options.silent
        logger = loggers.getLogger(self.options.loglevel)
        # tag the logger so that it is properly closed when exiting
        logger.SUPVISORS = True
        if nodaemon and not silent:
            loggers.handle_stdout(logger, Supvisors.LOGGER_FORMAT)
        loggers.handle_file(logger,
                            self.options.logfile,
                            Supvisors.LOGGER_FORMAT,
                            rotating=not not self.options.logfile_maxbytes,
                            maxbytes=self.options.logfile_maxbytes,
                            backups=self.options.logfile_backups)
        return logger
