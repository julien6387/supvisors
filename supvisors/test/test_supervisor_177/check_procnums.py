#!/usr/bin/python
# -*- coding: utf-8 -*-

# ======================================================================
# Copyright 2017 Julien LE CLEACH
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

import pytest

from collections import defaultdict
from supervisor.childutils import getRPCInterface
from supervisor.compat import xmlrpclib
from time import sleep


@pytest.fixture
def proxy():
    """ Return the supervisor proxy. """
    proxy = getRPCInterface({'SUPERVISOR_SERVER_URL': 'http://localhost:60000'})
    yield proxy
    proxy.supervisor.restart()


def check_status(proxy, expected):
    """ Check the Supervisor processes. """
    nb_processes = defaultdict(int)
    all_process_info = proxy.supervisor.getAllProcessInfo()
    for process_info in all_process_info:
        process_name = process_info['name']
        # test state
        if process_name.startswith('stopped'):
            assert process_info['statename'] == 'STOPPED'
        else:
            assert process_info['statename'] == 'RUNNING'
        # increment counter
        if '_' in process_name:
            process_name = '_'.join(process_name.split('_')[:-1])
        nb_processes[process_name] += 1
    assert nb_processes == expected


def test_issue_177(proxy):
    """ Test the behaviour of update_numprocs XML-RPC. """
    # wait for Supvisors operation state
    while proxy.supvisors.get_supvisors_state()['statename'] != 'OPERATION':
        sleep(1)
    print('Supvisors is in OPERATION state')
    # check initial status
    check_status(proxy, {'autostarted': 4, 'stopped': 2, 'control': 1, 'listener': 1, 'multiple_listener': 2})
    # Test numprocs update on a program that doesn't support it (process_num not used)
    with pytest.raises(xmlrpclib.Fault):
        proxy.supvisors.update_numprocs('control', 5)
    # Test autostarted programs
    # increase autostarted numprocs
    proxy.supvisors.update_numprocs('autostarted', 5)
    sleep(2)
    check_status(proxy, {'autostarted': 10, 'stopped': 2, 'control': 1, 'listener': 1, 'multiple_listener': 2})
    # decrease autostarted numprocs (back to initial value)
    proxy.supvisors.update_numprocs('autostarted', 2)
    sleep(2)
    check_status(proxy, {'autostarted': 4, 'stopped': 2, 'control': 1, 'listener': 1, 'multiple_listener': 2})
    # Test not autostarted programs
    # increase stopped numprocs
    proxy.supvisors.update_numprocs('stopped', 4)
    sleep(2)
    check_status(proxy, {'autostarted': 4, 'stopped': 4, 'control': 1, 'listener': 1, 'multiple_listener': 2})
    # decrease stopped numprocs (back to initial value)
    proxy.supvisors.update_numprocs('stopped', 2)
    sleep(2)
    check_status(proxy, {'autostarted': 4, 'stopped': 2, 'control': 1, 'listener': 1, 'multiple_listener': 2})
    # Test event listeners
    # Test numprocs update on an event listener that doesn't support it (process_num not used)
    with pytest.raises(xmlrpclib.Fault):
        proxy.supvisors.update_numprocs('listener', 5)
    # increase multiple_listener numprocs
    proxy.supvisors.update_numprocs('multiple_listener', 3)
    sleep(2)
    check_status(proxy, {'autostarted': 4, 'stopped': 2, 'control': 1, 'listener': 1, 'multiple_listener': 3})
    # decrease multiple_listener numprocs (back to initial value)
    proxy.supvisors.update_numprocs('multiple_listener', 1)
    sleep(2)
    check_status(proxy, {'autostarted': 4, 'stopped': 2, 'control': 1, 'listener': 1, 'multiple_listener': 1})
