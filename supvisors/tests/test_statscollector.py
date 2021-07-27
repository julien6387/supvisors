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

import pytest
pytest.importorskip('psutil', reason='cannot test as optional psutil is not installed')

import multiprocessing
import os
import time

from supvisors.statscollector import *


def test_instant_cpu_statistics():
    """ Test the instant CPU statistics. """
    stats = list(instant_cpu_statistics())
    # test number of results (number of cores + average)
    assert len(stats) == multiprocessing.cpu_count() + 1
    # test average value
    total_work = total_idle = 0
    for cpu in stats[1:]:
        assert len(cpu) == 2
        work, idle = cpu
        total_work += work
        total_idle += idle
    assert pytest.approx(total_work / multiprocessing.cpu_count()) == stats[0][0]
    assert pytest.approx(total_idle / multiprocessing.cpu_count()) == stats[0][1]


def test_instant_memory_statistics():
    """ Test the instant memory statistics. """
    stats = instant_memory_statistics()
    # test bounds (percent)
    assert type(stats) is float
    assert stats >= 0
    assert stats <= 100


def test_instant_io_statistics():
    """ Test the instant I/O statistics. """
    stats = instant_io_statistics()
    # test interface names
    with open('/proc/net/dev') as netfile:
        # two first lines are title
        contents = netfile.readlines()[2:]
    interfaces = [intf.strip().split(':')[0] for intf in contents]
    assert list(stats.keys()) == interfaces
    assert 'lo' in stats.keys()
    # test that values are pairs
    for intf, io_bytes in stats.items():
        assert len(io_bytes) == 2
        for value in io_bytes:
            assert type(value) is int
    # for loopback address, recv bytes equals sent bytes
    assert stats['lo'][0] == stats['lo'][1]


def test_instant_process_statistics():
    """ Test the instant process statistics. """
    # check with existing PID
    work, memory = instant_process_statistics(os.getpid())
    # test that a pair is returned with values in [0;100]
    # test cpu value
    assert type(work) is float
    assert work >= 0
    assert work <= 100
    # test mem value
    assert type(memory) is float
    assert memory >= 0
    assert memory <= 100
    # check handling of non-existing PID
    work, memory = instant_process_statistics(-1)
    assert work == 0
    assert memory == 0


def test_instant_statistics():
    """ Test the instant global statistics. """
    stats = instant_statistics([('myself', os.getpid())])
    # check result
    assert len(stats) == 5
    date, cpu_stats, mem_stats, io_stats, proc_stats = stats
    #  check time (current is greater)
    assert time() > date
    # check cpu jiffies
    assert len(list(cpu_stats)) == multiprocessing.cpu_count() + 1
    for cpu in cpu_stats:
        assert len(cpu) == 2
        for value in cpu:
            assert type(value) is float
    # check memory
    assert type(mem_stats) is float
    assert mem_stats >= 0
    assert mem_stats < 100
    # check io
    for intf, io_bytes in io_stats.items():
        assert type(intf) is str
        assert len(io_bytes) == 2
        for value in io_bytes:
            assert type(value) is int
    # check process stats
    assert list(proc_stats.keys()) == ['myself']
    values = proc_stats['myself']
    assert len(values) == 2
    assert values[0] == os.getpid()
    assert len(values[1]) == 2
    for value in values[1]:
        assert type(value) is float
        assert value >= 0
        assert value <= 100
