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

import random

from supervisor.states import RUNNING_STATES, STOPPED_STATES


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
        'logfile': './log/firefox_cliche01.log', 'exitstatus': 0, 'spawnerr': '', 'now': 1473888158,
        'group': 'firefox', 'name': 'firefox', 'statename': 'EXITED', 'start': 1473887932, 'state': 100,
        'stdout_logfile': './log/firefox_cliche01.log'},
    {'description': 'pid 80877, uptime 0:01:20', 'pid': 80877, 'stderr_logfile': '', 'stop': 0,
        'logfile': './log/xclock_cliche01.log', 'exitstatus': 0, 'spawnerr': '', 'now': 1473888158,
        'group': 'sample_test_1', 'name': 'xclock', 'statename': 'STOPPING', 'start': 1473888078, 'state': 40,
        'stdout_logfile': './log/xclock_cliche01.log'},
    {'description': 'pid 80879, uptime 0:01:19', 'pid': 80879, 'stderr_logfile': '', 'stop': 0,
        'logfile': './log/xfontsel_cliche01.log', 'exitstatus': 0, 'spawnerr': '', 'now': 1473888158,
        'group': 'sample_test_1', 'name': 'xfontsel', 'statename': 'RUNNING', 'start': 1473888079, 'state': 20,
        'stdout_logfile': './log/xfontsel_cliche01.log'},
    {'description': 'Sep 14 05:21 PM', 'pid': 0, 'stderr_logfile': '', 'stop': 1473888104,
        'logfile': './log/xlogo_cliche01.log', 'exitstatus': -1, 'spawnerr': '', 'now': 1473888158,
        'group': 'sample_test_1', 'name': 'xlogo', 'statename': 'STOPPED', 'start': 1473888085, 'state': 0,
        'stdout_logfile': './log/xlogo_cliche01.log'},
    {'description': 'No resource available', 'pid': 0, 'stderr_logfile': '', 'stop': 0,
        'logfile': './log/sleep_cliche01.log', 'exitstatus': 0, 'spawnerr': 'No resource available',
        'now': 1473888158, 'group': 'sample_test_2', 'name': 'sleep', 'statename': 'FATAL', 'start': 0, 'state': 200,
        'stdout_logfile': './log/sleep_cliche01.log'},
    {'description': 'Sep 14 05:22 PM', 'pid': 0, 'stderr_logfile': '', 'stop': 1473888130,
        'logfile': './log/xeyes_cliche01.log', 'exitstatus': 0, 'spawnerr': '', 'now': 1473888158,
        'group': 'sample_test_2', 'name': 'yeux_00', 'statename': 'EXITED', 'start': 1473888086, 'state': 100,
        'stdout_logfile': './log/xeyes_cliche01.log'},
    {'description': 'pid 80882, uptime 0:01:12', 'pid': 80882, 'stderr_logfile': '', 'stop': 0,
        'logfile': './log/xeyes_cliche01.log', 'exitstatus': 0, 'spawnerr': '', 'now': 1473888158,
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

