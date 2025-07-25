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

import random
import socket
from socket import gethostname
from unittest.mock import Mock

from supervisor.loggers import getLogger, handle_stdout, Logger
from supervisor.rpcinterface import SupervisorNamespaceRPCInterface
from supervisor.states import STOPPED_STATES, SupervisorStates, ProcessStates

from supvisors.context import Context
from supvisors.initializer import LOGGER_FORMAT
from supvisors.internal_com.mapper import SupvisorsMapper
from supvisors.internal_com.rpchandler import RpcHandler
from supvisors.options import SupvisorsOptions, SupvisorsServerOptions
from supvisors.rpcinterface import RPCInterface
from supvisors.statemodes import SupvisorsStateModes
from supvisors.statscollector import StatisticsCollectorProcess
from supvisors.statscompiler import HostStatisticsCompiler, ProcStatisticsCompiler
from supvisors.supervisordata import SupervisorData
from supvisors.supervisorupdater import SupervisorUpdater
from supvisors.utils import extract_process_info
from supvisors.web.sessionviews import SessionViews


class MockedSupvisors:
    """ Simple supvisors with all dummies. """

    def __init__(self, supervisord, config):
        """ Use mocks when not possible to use real structures. """
        self.logger = Mock(spec=Logger, level=10, handlers=[Mock(level=10)])
        self.options = SupvisorsOptions(supervisord, self.logger, **config)
        self.options.rules_files = [config['rules_files']]
        # mock the supervisord source
        self.supervisor_data = SupervisorData(self, supervisord)
        supervisord.supvisors = self
        self.supervisor_updater = SupervisorUpdater(self)
        self.mapper = SupvisorsMapper(self)
        identifiers = ['10.0.0.1', '10.0.0.2', '10.0.0.3', '10.0.0.4', '10.0.0.5', '10.0.0.6']
        self.mapper.configure(identifiers, {'supvisors_test'}, [])
        self.server_options = SupvisorsServerOptions(self)
        # set real statistics collector and compilers
        self.stats_collector = StatisticsCollectorProcess(self)
        self.host_compiler = HostStatisticsCompiler(self)
        self.process_compiler = ProcStatisticsCompiler(self.options, self.logger)
        # create normal structures
        self.state_modes = SupvisorsStateModes(self)
        self.context = Context(self)
        self.rpc_handler = RpcHandler(self)
        self.sessions = SessionViews(self)
        # mock by spec
        from supvisors.commander import Starter, Stopper, StarterModel
        from supvisors.strategy import RunningFailureHandler
        from supvisors.statemachine import FiniteStateMachine
        from supvisors.listener import SupervisorListener
        from supvisors.sparser import Parser
        self.starter = Mock(spec=Starter)
        self.starter_model = Mock(spec=StarterModel)
        self.stopper = Mock(spec=Stopper)
        self.failure_handler = Mock(spec=RunningFailureHandler)
        self.fsm = Mock(spec=FiniteStateMachine, force_distribution=False)
        self.listener = Mock(spec=SupervisorListener)
        self.parser = Mock(spec=Parser)
        # should be set in listener
        self.discovery_handler = None
        self.external_publisher = None


class DummyRpcHandler:
    """ Simple supervisord RPC handler with dummy attributes. """

    def __init__(self):
        self.handler = Mock(rpcinterface=Mock(system=Mock(rpc_name='system_RPC'),
                                              supervisor=Mock(rpc_name='supervisor_RPC'),
                                              supvisors=Mock(rpc_name='supvisors_RPC')))


class DummyRpcInterface:
    """ Simple RPC mock. """

    def __init__(self, supvisors):
        # create rpc interfaces to have a skeleton
        self.supervisor = SupervisorNamespaceRPCInterface(DummySupervisor())
        self.supvisors = RPCInterface(supvisors)


class DummyHttpServer:
    """ Simple supervisord RPC handler with dummy attributes. """

    def __init__(self):
        self.socket = Mock()
        self.handlers = [DummyRpcHandler(),
                         Mock(handler_name='tail_handler'),
                         Mock(handler_name='main_tail_handler'),
                         Mock(handler_name='ui_handler'),
                         Mock(handler_name='default_handler')]


class DummyServerOptions:
    """ Simple supervisord server options with dummy attributes. """

    def __init__(self):
        # build a fake server config
        server_config = {'section': 'inet_http_server',
                         'family': socket.AF_INET,
                         'host': gethostname(),
                         'port': 25000,
                         'username': 'user',
                         'password': 'p@$$w0rd'}
        self.configfile = 'supervisord.conf'
        self.httpserver = DummyHttpServer()
        self.server_configs = [server_config]
        self.here = '.'
        self.environ_expansions = {}
        self.identifier = gethostname()
        self.serverurl = 'unix://tmp/supervisor.sock'
        self.mood = SupervisorStates.RUNNING
        self.nodaemon = True
        self.silent = False
        # add silent logger to test create_logger
        self.logfile = 'supervisor.log'
        self.logger = getLogger()
        handle_stdout(self.logger, LOGGER_FORMAT)
        self.logger.log = Mock()
        # build a fake http config
        self.httpservers = [(server_config, self.httpserver)]
        # prepare storage for close_httpservers test
        self.storage = None

    def close_httpservers(self):
        self.storage = self.httpservers


class DummyProcessConfig:
    """ Simple supervisor process config with simple attributes. """

    def __init__(self, name: str, command: str, autorestart: bool, stdout_logfile: bool, stderr_logfile: bool):
        self.name = name
        self.command = command
        self.autorestart = autorestart
        self.startsecs = 5
        self.stopwaitsecs = 10
        self.stdout_logfile = stdout_logfile
        self.stderr_logfile = stderr_logfile


class DummyProcess:
    """ Simple supervisor process with simple attributes. """

    def __init__(self, name: str, command: str, autorestart: bool, stdout_logfile: bool, stderr_logfile: bool):
        self.state = ProcessStates.STOPPED
        self.spawnerr = ''
        self.laststart = 1234
        self.config = DummyProcessConfig(name, command, autorestart, stdout_logfile, stderr_logfile)

    def give_up(self):
        self.state = ProcessStates.FATAL

    def transition(self):
        self.state = ProcessStates.STARTING


class DummySupervisor:
    """ Simple supervisor with simple attributes. """

    def __init__(self):
        self.options = DummyServerOptions()
        dummy_process_1 = DummyProcess('dummy_process_1', 'ls', True, True, False)
        dummy_process_2 = DummyProcess('dummy_process_2', 'cat', False, False, True)
        self.process_groups = {'dummy_application': Mock(config=Mock(name='dummy_application'),
                                                         processes={'dummy_process_1': dummy_process_1,
                                                                    'dummy_process_2': dummy_process_2})}


# note that all dates ('now') are different
ProcessInfoDatabase = [
    {'description': '', 'pid': 80886, 'stderr_logfile': '', 'stop': 1473888084,
     'logfile': './log/late_segv_cliche01.log', 'exitstatus': 0, 'spawnerr': '', 'now': 1473888091,
     'group': 'crash', 'name': 'late_segv', 'statename': 'STARTING', 'start': 1473888089, 'state': 10,
     'stdout_logfile': './log/late_segv_cliche01.log'},
    {'description': 'Exited too quickly (process log may have details)', 'pid': 0, 'stderr_logfile': '',
     'stop': 1473888156, 'logfile': './log/segv_cliche01.log', 'exitstatus': 0,
     'spawnerr': 'Exited too quickly (process log may have details)', 'now': 1473888156,
     'group': 'crash', 'name': 'segv', 'statename': 'BACKOFF', 'start': 1473888155, 'state': 30,
     'stdout_logfile': './log/segv_cliche01.log'},
    {'description': 'Sep 14 05:18 PM', 'pid': 0, 'stderr_logfile': '', 'stop': 1473888937,
     'logfile': './log/firefox_cliche01.log', 'exitstatus': 0, 'spawnerr': '', 'now': 1473888161,
     'group': 'firefox', 'name': 'firefox', 'statename': 'EXITED', 'start': 1473887932, 'state': 100,
     'stdout_logfile': './log/firefox_cliche01.log'},
    {'description': 'pid 80877, uptime 0:01:20', 'pid': 80877, 'stderr_logfile': '', 'stop': 0,
     'logfile': './log/xclock_cliche01.log', 'exitstatus': 0, 'spawnerr': '', 'now': 1473888166,
     'group': 'sample_test_1', 'name': 'xclock', 'statename': 'STOPPING', 'start': 1473888078, 'state': 40,
     'stdout_logfile': './log/xclock_cliche01.log'},
    {'description': 'pid 80879, uptime 0:01:19', 'pid': 80879, 'stderr_logfile': '', 'stop': 0,
     'logfile': './log/xfontsel_cliche01.log', 'exitstatus': 0, 'spawnerr': '', 'now': 1473888171,
     'group': 'sample_test_1', 'name': 'xfontsel', 'statename': 'RUNNING', 'start': 1473888079, 'state': 20,
     'stdout_logfile': './log/xfontsel_cliche01.log'},
    {'description': 'Sep 14 05:21 PM', 'pid': 0, 'stderr_logfile': '', 'stop': 1473888104,
     'logfile': './log/xlogo_cliche01.log', 'exitstatus': -1, 'spawnerr': '', 'now': 1473888176,
     'group': 'sample_test_1', 'name': 'xlogo', 'statename': 'STOPPED', 'start': 1473888085, 'state': 0,
     'stdout_logfile': './log/xlogo_cliche01.log'},
    {'description': 'No resource available', 'pid': 0, 'stderr_logfile': '', 'stop': 0,
     'logfile': './log/sleep_cliche01.log', 'exitstatus': 0, 'spawnerr': 'No resource available',
     'now': 1473888181, 'group': 'sample_test_2', 'name': 'sleep', 'statename': 'FATAL', 'start': 0, 'state': 200,
     'stdout_logfile': './log/sleep_cliche01.log'},
    {'description': 'Sep 14 05:22 PM', 'pid': 0, 'stderr_logfile': '', 'stop': 1473888130,
     'logfile': './log/xeyes_cliche01.log', 'exitstatus': 0, 'spawnerr': '', 'now': 1473888186,
     'group': 'sample_test_2', 'name': 'yeux_00', 'statename': 'EXITED', 'start': 1473888086, 'state': 100,
     'stdout_logfile': './log/xeyes_cliche01.log'},
    {'description': 'pid 80882, uptime 0:01:12', 'pid': 80882, 'stderr_logfile': '', 'stop': 0,
     'logfile': './log/xeyes_cliche01.log', 'exitstatus': 0, 'spawnerr': '', 'now': 1473888196,
     'group': 'sample_test_2', 'name': 'yeux_01', 'statename': 'RUNNING', 'start': 1473888086, 'state': 20,
     'stdout_logfile': './log/xeyes_cliche01.log'}]


def extract_and_complete(info):
    """ Provide payload as processed by Supvisors. """
    extracted_info = extract_process_info(info)
    extracted_info.update({'startsecs': 0, 'stopwaitsecs': 0, 'extra_args': '', 'disabled': False})
    extracted_info.update({'now_monotonic': info['now'] - 1e6,
                           'start_monotonic': info['start'] - 1e6,
                           'stop_monotonic': info['stop'] - 1e6})
    if info['name'].startswith('yeux'):
        program_name, process_index = info['name'].split('_')
        extracted_info.update({'program_name': program_name, 'process_index': int(process_index)})
    else:
        extracted_info.update({'program_name': info['name'], 'process_index': 0})
    return extracted_info


def database_copy():
    """ Return a copy of the whole database. """
    return [extract_and_complete(info) for info in ProcessInfoDatabase]


def any_process_info():
    """ Return a copy of any process in database. """
    info = random.choice(ProcessInfoDatabase)
    return extract_and_complete(info)


def any_stopped_process_info():
    """ Return a copy of any stopped process in database. """
    info = random.choice([info for info in ProcessInfoDatabase if info['state'] in STOPPED_STATES])
    return extract_and_complete(info)


def any_process_info_by_state(state):
    """ Return a copy of any process in state 'state' in database. """
    info = random.choice([info for info in ProcessInfoDatabase if info['state'] == state])
    return extract_and_complete(info)


def process_info_by_name(name):
    """ Return a copy of a process named 'name' in database. """
    return next((extract_and_complete(info) for info in ProcessInfoDatabase if info['name'] == name), None)
