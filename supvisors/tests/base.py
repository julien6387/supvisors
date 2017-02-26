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

import os
import random

from supervisor.states import RUNNING_STATES, STOPPED_STATES


class DummyClass:
    """ Temporary empty class. """


class DummyLogger:
    """ Simple logger that stores log traces. """

    def __init__(self):
        self.messages = []

    def critical(self, message):
        self.messages.append(('critical', message))

    def error(self, message):
        self.messages.append(('error', message))

    def warn(self, message):
        self.messages.append(('warn', message))

    def info(self, message):
        self.messages.append(('info', message))

    def debug(self, message):
        self.messages.append(('debug', message))

    def trace(self, message):
        self.messages.append(('trace', message))

    def blather(self, message):
        self.messages.append(('blather', message))


class DummyAddressMapper:
    """ Simple address mapper with an empty addresses list. """

    def __init__(self):
        self.addresses = ['127.0.0.1', '10.0.0.1', '10.0.0.2', '10.0.0.3', '10.0.0.4', '10.0.0.5']
        self.local_address = '127.0.0.1'


class DummyAddressStatus:
    """ Simple address status with name, state and loading. """

    def __init__(self, name, state, load):
        self.name = name
        self.state = state
        self.load = load

    def state_string(self):
        return ""

    def loading(self):
        return self.load


class DummyApplicationStatus:
    """ Simple ApplicationStatus. """

    def sequence_deployment(self):
        pass

    def update_status(self):
        pass


class DummyContext:
    """ Simple context with an empty list of AddressStatus. """

    def __init__(self):
        self.addresses = {}
        self.applications = {}
        self.master_address = ''
        self.master = True

    # TODO: implement running_addresses, unknown_addresses, conflicting, conflicts, marked_processes,
    #                 on_timer_event, handle_isolation, on_tick_event, on_process_event

# TEMP
def read_string(self, s):
    from StringIO import StringIO
    s = StringIO(s)
    return self.readfp(s)


class DummyInfoSource:
    """ Simple info source with dummy methods. """

    def get_env(self):
        return {'SUPERVISOR_SERVER_URL': 'http://127.0.0.1:65000', 
            'SUPERVISOR_USERNAME': '',
            'SUPERVISOR_PASSWORD': ''}

    def autorestart(self, namespec):
        return namespec == 'test_autorestart'


class DummyOptions:
    """ Simple options with dummy attributes. """

    def __init__(self):
        self.internal_port = 65100
        self.event_port = 65200
        self.synchro_timeout = 10
        self.deployment_strategy = 0
        self.conciliation_strategy = 0
        self.stats_periods = 5, 15, 60
        self.stats_histo = 10


class DummyStarter:
    """ Simple starter. """
        # TODO: deploy_applications, check_deployment, in_progress, deploy_on_event, deploy_marked_processes


class DummyStopper:
    """ Simple stopper. """


class DummyZmq:
    """ Simple Supvisors ZeroMQ behaviour. """
 
    def __init__(self):
        self.internal_subscriber = None
        self.puller = None


class DummySupvisors:
    """ Simple supvisors with all dummies. """

    def __init__(self):
        self.address_mapper = DummyAddressMapper()
        self.context = DummyContext()
        self.deployer = DummyClass()
        self.fsm = DummyClass()
        self.info_source = DummyInfoSource()
        self.logger = DummyLogger()
        self.options = DummyOptions()
        self.pool = DummyClass()
        self.requester = DummyClass()
        self.statistician = DummyClass()
        self.starter = DummyStarter()
        self.stopper = DummyStopper()
        self.zmq = DummyZmq()


class DummySupervisor:
    """ Simple supervisor instance with simple attributes. """

    def __init__(self):
        self.supvisors = DummySupvisors()
        self.options = DummyClass()
        self.options.server_configs = [{'section': 'inet_http_server'}]


class DummyHttpContext:
    """ Simple HTTP context for web ui views. """

    def __init__(self, template):
        import supvisors
        module_path = os.path.dirname(supvisors.__file__)
        self.template = os.path.join(module_path, template)
    
    
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
    {'description': 'Sep 14 05:18 PM', 'pid': 0, 'stderr_logfile': '', 'stop': 1473887937,
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


def any_process_info():
    """ Return a copy of any process in database. """
    return random.choice(ProcessInfoDatabase).copy()

def any_stopped_process_info():
    """ Return a copy of any stopped process in database. """
    return random.choice([info for info in ProcessInfoDatabase if info['state'] in STOPPED_STATES]).copy()

def any_running_process_info():
    """ Return a copy of any running process in database. """
    return random.choice([info for info in ProcessInfoDatabase if info['state'] in RUNNING_STATES]).copy()

def any_process_info_by_state(state):
    """ Return a copy of any process in state 'state' in database. """
    return random.choice([info for info in ProcessInfoDatabase if info['state'] == state]).copy()

def process_info_by_name(name):
    """ Return a copy of a process named 'name' in database. """
    return next((info.copy() for info in ProcessInfoDatabase if info['name'] == name), None)

