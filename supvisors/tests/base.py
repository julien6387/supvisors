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

import os
import random
import supvisors

from socket import gethostname
from unittest.mock import Mock

from supervisor.datatypes import Automatic
from supervisor.loggers import getLogger, handle_stdout, LevelsByName, Logger
from supervisor.rpcinterface import SupervisorNamespaceRPCInterface
from supervisor.states import STOPPED_STATES, SupervisorStates

from supvisors.supvisorsmapper import SupvisorsMapper
from supvisors.context import Context
from supvisors.initializer import Supvisors
from supvisors.supervisordata import SupervisorData
from supvisors.supvisorszmq import SupervisorZmq
from supvisors.ttypes import StartingStrategies
from supvisors.utils import extract_process_info


class DummyOptions:
    """ Simple options with dummy attributes. """

    SYNCHRO_TIMEOUT_MIN = 15

    def __init__(self):
        """ Configuration options. """
        self.supvisors_list = [gethostname()]
        self.internal_port = 65100
        self.event_port = 65200
        self.synchro_timeout = 10
        self.inactivity_ticks = 2
        self.force_synchro_if = []
        self.auto_fence = True
        self.rules_files = 'my_movies.xml'
        self.starting_strategy = StartingStrategies.CONFIG
        self.conciliation_strategy = 0
        self.stats_enabled = True
        self.stats_periods = 5, 15, 60
        self.stats_histo = 10
        self.stats_irix_mode = False
        # logger options
        self.logfile = Automatic
        self.logfile_maxbytes = 10000
        self.logfile_backups = 12
        self.loglevel = LevelsByName.BLAT


class MockedSupvisors:
    """ Simple supvisors with all dummies. """

    def __init__(self):
        """ Use mocks when not possible to use real structures. """
        self.options = DummyOptions()
        self.logger = Mock(spec=Logger, level=10, handlers=[Mock(level=10)])
        # mock the supervisord source
        self.supervisor_data = SupervisorData(DummySupervisor(), self.logger)
        self.supvisors_mapper = SupvisorsMapper(self)
        host_name = gethostname()
        identifiers = ['10.0.0.1', '10.0.0.2', '10.0.0.3', '10.0.0.4', '10.0.0.5',
                       f'<{host_name}>{host_name}:65000:', f'<test>{host_name}:55000:']
        self.supvisors_mapper.configure(identifiers, [])
        self.server_options = Mock(procnumbers={'xclock': 2})
        # build context from node mapper
        self.context = Context(self)
        # mock by spec
        from supvisors.commander import Starter, Stopper
        from supvisors.strategy import RunningFailureHandler
        from supvisors.statemachine import FiniteStateMachine
        from supvisors.listener import SupervisorListener
        from supvisors.sparser import Parser
        self.starter = Mock(spec=Starter)
        self.stopper = Mock(spec=Stopper)
        self.failure_handler = Mock(spec=RunningFailureHandler)
        self.fsm = Mock(spec=FiniteStateMachine)
        self.statistician = Mock(data={}, nbcores={})
        self.listener = Mock(spec=SupervisorListener)
        self.parser = Mock(spec=Parser)
        # should be set in listener
        self.zmq = Mock(spec=SupervisorZmq)
        self.zmq.__init__()


class DummyRpcHandler:
    """ Simple supervisord RPC handler with dummy attributes. """

    def __init__(self):
        self.handler = Mock(rpcinterface=Mock(supervisor=Mock(rpc_name='supervisor_RPC'),
                                              supvisors=Mock(rpc_name='supvisors_RPC')))


class DummyRpcInterface:
    """ Simple RPC mock. """

    def __init__(self):
        from supvisors.rpcinterface import RPCInterface
        # create rpc interfaces to have a skeleton
        self.supervisor = SupervisorNamespaceRPCInterface(DummySupervisor())
        self.supvisors = RPCInterface(MockedSupvisors())


class DummyHttpServer:
    """ Simple supervisord RPC handler with dummy attributes. """

    def __init__(self):
        self.handlers = [DummyRpcHandler(), Mock()]

    def install_handler(self, handler, _):
        self.handlers.append(handler)


class DummyServerOptions:
    """ Simple supervisord server options with dummy attributes. """

    def __init__(self):
        # build a fake server config
        self.server_configs = [{'section': 'inet_http_server',
                                'port': 65000,
                                'username': 'user',
                                'password': 'p@$$w0rd'}]
        self.here = '.'
        self.environ_expansions = {}
        self.identifier = gethostname()
        self.serverurl = f'http://{gethostname()}:65000'
        self.mood = SupervisorStates.RUNNING
        self.nodaemon = True
        self.silent = False
        # add silent logger to test create_logger
        self.logger = getLogger()
        handle_stdout(self.logger, Supvisors.LOGGER_FORMAT)
        self.logger.log = Mock()
        # build a fake http config
        self.httpservers = [[None, DummyHttpServer()]]
        self.httpserver = self.httpservers[0][1]
        # prepare storage for close_httpservers test
        self.storage = None

    def close_httpservers(self):
        self.storage = self.httpservers


class DummyProcessConfig:
    """ Simple supervisor process config with simple attributes. """

    def __init__(self, command, autorestart):
        self.command = command
        self.autorestart = autorestart


class DummyProcess:
    """ Simple supervisor process with simple attributes. """

    def __init__(self, command, autorestart):
        self.state = 'STOPPED'
        self.spawnerr = ''
        self.config = DummyProcessConfig(command, autorestart)

    def give_up(self):
        self.state = 'FATAL'


class DummySupervisor:
    """ Simple supervisor with simple attributes. """

    def __init__(self):
        self.configfile = 'supervisord.conf'
        self.options = DummyServerOptions()
        self.process_groups = {'dummy_application': Mock(config='dummy_application_config',
                                                         processes={'dummy_process_1': DummyProcess('ls', True),
                                                                    'dummy_process_2': DummyProcess('cat', False)})}


class DummyHttpContext:
    """ Simple HTTP context for web ui views. """

    def __init__(self, template=None):
        supvisors_path = next(iter(supvisors.__path__), '.')
        self.template = os.path.join(supvisors_path, template) if template else None
        self.supervisord = DummySupervisor()
        # create form and response
        self.form = {'SERVER_URL': 'http://10.0.0.1:7777',
                     'SERVER_PORT': 7777,
                     'PATH_TRANSLATED': '/index.html',
                     'action': 'test',
                     'ident': '10.0.0.4',
                     'message': 'hi chaps',
                     'gravity': 'none',
                     'namespec': 'dummy_proc',
                     'processname': 'dummy_proc',
                     'appliname': 'dummy_appli',
                     'intfname': 'eth0',
                     'auto': 'false'}
        self.response = {'headers': {'Location': None}}


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
    extracted_info.update({'startsecs': 0, 'stopwaitsecs': 0, 'extra_args': ''})
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
