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

from supervisor import supervisord
from supervisor.loggers import Logger, getLogger, handle_file, handle_stdout
from supervisor.supervisord import Supervisor

from supvisors.internal_com.mapper import SupvisorsMapper
from .commander import Starter, Stopper, StarterModel
from .context import Context
from .listener import SupervisorListener
from .options import SupvisorsOptions, SupvisorsServerOptions, Automatic, get_logger_configuration
from .sparser import Parser
from .statemachine import FiniteStateMachine
from .statscompiler import HostStatisticsCompiler, ProcStatisticsCompiler
from .strategy import RunningFailureHandler
from .supervisordata import SupervisorData
from .supervisorupdater import SupervisorUpdater
from .ttypes import Payload

# use ';' in logger output as separator because easier to cut
LOGGER_FORMAT = '%(asctime)s;%(levelname)s;%(message)s\n'


def create_logger(supervisor: Supervisor, logger_config: Payload) -> Logger:
    """ Create the logger that will be used in Supvisors.

    If logfile is not set or set to AUTO, Supvisors will use the Supervisor logger.
    Else Supvisors will log in the file defined in option.
    """
    # prefix all log traces with the software name if set
    prefix = logger_config['prefix']
    logger_format = f'{prefix};{LOGGER_FORMAT}' if prefix else LOGGER_FORMAT
    # configure the Supervisor logger
    logfile = logger_config['logfile']
    if logfile is Automatic:
        # use Supervisord logger but patch format anyway
        logger = supervisor.options.logger
        for handler in logger.handlers:
            handler.setFormat(logger_format)
        return logger
    # else create own Logger using Supervisor functions
    nodaemon = supervisor.options.nodaemon
    silent = supervisor.options.silent
    logger = getLogger(logger_config['loglevel'])
    # tag the logger so that it is properly closed when exiting
    # when not tagged, Supervisor closes it
    logger.SUPVISORS = True
    if nodaemon and not silent:
        handle_stdout(logger, logger_format)
    handle_file(logger, logfile, logger_format,
                rotating=not not logger_config['logfile_maxbytes'],
                maxbytes=logger_config['logfile_maxbytes'],
                backups=logger_config['logfile_backups'])
    return logger


class Supvisors:
    """ The Supvisors class used as a global structure passed to most Supvisors objects. """

    def __init__(self, supervisor: Supervisor, **config) -> None:
        """ Instantiation of all the Supvisors objects.

        :param supervisor: the Supervisor global structure
        """
        # WARN: The Supvisors communication objects cannot be created at this level.
        #       Before running, Supervisor forks when daemonized and the sockets would be lost.
        self.rpc_handler = None
        self.discovery_handler = None
        self.external_publisher = None
        # create logger using option from config
        logger_config = get_logger_configuration(**config)
        self.logger = create_logger(supervisor, logger_config)
        # get options from config
        self.options = SupvisorsOptions(supervisor, self.logger, **config)
        # re-realize configuration to get process configuration not stored within Supervisor options
        self.server_options = SupvisorsServerOptions(self)
        self.server_options.realize(sys.argv[1:], doc=supervisord.__doc__)
        # configure supervisor data wrapper
        self.supervisor_data = SupervisorData(self, supervisor)
        self.supervisor_updater = SupervisorUpdater(self)
        # get declared Supvisors instances and check local identifier
        self.mapper = SupvisorsMapper(self)
        try:
            self.mapper.configure(self.options.supvisors_list,
                                  self.options.stereotypes,
                                  self.options.core_identifiers)
        except ValueError:
            self.logger.critical('Supvisors: Wrong Supvisors configuration (supvisors_list)')
            raise
        # create statistics handler
        self.stats_collector = None
        try:
            from .statscollector import StatisticsCollectorProcess
            self.stats_collector = StatisticsCollectorProcess(self)
        except (ImportError, ModuleNotFoundError):
            self.logger.info('Supvisors: psutil not installed')
            self.logger.warn('Supvisors: this Supvisors instance cannot not collect statistics')
        self.host_compiler = HostStatisticsCompiler(self)
        self.process_compiler = ProcStatisticsCompiler(self.options, self.logger)
        # create context data
        self.context = Context(self)
        # create application starter and stopper
        self.starter = Starter(self)
        self.stopper = Stopper(self)
        # create application starter model
        self.starter_model = StarterModel(self)
        # create the failure handler of crashing processes
        # WARN: must be created before the state machine
        self.failure_handler = RunningFailureHandler(self)
        # check rules files
        try:
            self.parser = Parser(self)
        except Exception as exc:
            self.logger.warn(f'Supvisors: cannot parse rules files: {self.options.rules_files} - {exc}')
            self.parser = None
        # create Supervisor event subscriber
        self.listener = SupervisorListener(self)
        # create state machine
        self.fsm = FiniteStateMachine(self)
