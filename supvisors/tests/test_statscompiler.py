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

import multiprocessing
import pytest

from unittest.mock import call

from supvisors.statscompiler import *


def test_cpu_statistics():
    """ Test the CPU statistics between 2 dates. """
    # take 2 spaced instant cpu statistics
    ref_stats = [(83.31, 305.4)] * (multiprocessing.cpu_count() + 1)
    last_stats = [(83.32, 306.4)] * (multiprocessing.cpu_count() + 1)
    stats = cpu_statistics(last_stats, ref_stats)
    # test number of results (number of cores + average)
    assert len(stats) == multiprocessing.cpu_count() + 1
    # test bounds (percent)
    for cpu in stats:
        assert type(cpu) is float
        assert cpu >= 0
        assert cpu <= 100


def test_cpu_total_work():
    """ Test the CPU total work between 2 dates. """
    # take 2 instant cpu statistics
    ref_stats = [(83.31, 305.4)] * 2
    last_stats = [(83.41, 306.3)] * 2
    total_work = cpu_total_work(last_stats, ref_stats)
    # total work is the sum of jiffies spent on cpu all
    assert pytest.approx(total_work) == 1


def test_io_statistics():
    """ Test the I/O statistics between 2 dates. """
    # take 2 instant cpu statistics
    ref_stats = {'eth0': (2000, 200), 'lo': (5000, 5000)}
    last_stats = {'eth0': (2896, 328), 'lo': (6024, 6024)}
    stats = io_statistics(last_stats, ref_stats, 1)
    # test keys
    assert stats.keys() == ref_stats.keys()
    assert stats.keys() == last_stats.keys()
    # test that values
    assert stats == {'lo': (8, 8), 'eth0': (7, 1)}


def test_cpu_process_statistics():
    """ Test the CPU of the process between 2 dates. """
    stats = cpu_process_statistics(50, 20, 100)
    assert type(stats) is float
    assert pytest.approx(stats) == 30


def test_statistics():
    """ Test the global statistics between 2 dates. """
    ref_stats = (1000, [(25, 400), (25, 125), (15, 150)], 65, {'eth0': (2000, 200), 'lo': (5000, 5000)},
                 {'myself': (26088, (0.15, 1.85))})
    last_stats = (1002, [(45, 700), (50, 225), (40, 250)], 67.7, {'eth0': (2768, 456), 'lo': (6024, 6024)},
                  {'myself': (26088, (1.75, 1.9))})
    stats = statistics(last_stats, ref_stats)
    # check result
    assert len(stats) == 5
    date, cpu_stats, mem_stats, io_stats, proc_stats = stats
    # check date
    assert date == 1002
    # check cpu
    assert cpu_stats == [6.25, 20.0, 20.0]
    # check memory
    assert pytest.approx(mem_stats) == 67.7
    # check io
    assert io_stats == {'lo': (4, 4), 'eth0': (3, 1)}
    # check process stats
    assert proc_stats == {('myself', 26088): (0.5, 1.9)}


@pytest.fixture
def statistics_instance(supvisors):
    # testing with period 12 and history depth 2
    return StatisticsInstance(12, 2, supvisors.logger)


def test_stats_create(statistics_instance):
    """ Test the initialization of an instance. """
    # check attributes
    assert statistics_instance.period == 2
    assert statistics_instance.depth == 2
    assert statistics_instance.counter == -1
    assert statistics_instance.ref_stats is None
    assert type(statistics_instance.cpu) is list
    assert not statistics_instance.cpu
    assert type(statistics_instance.mem) is list
    assert not statistics_instance.mem
    assert type(statistics_instance.io) is dict
    assert not statistics_instance.io
    assert type(statistics_instance.proc) is dict
    assert not statistics_instance.proc


def test_clear(statistics_instance):
    """ Test the clearance of an instance. """
    # change values
    statistics_instance.counter = 28
    statistics_instance.ref_stats = ('dummy', 0)
    statistics_instance.cpu = [13.2, 14.8]
    statistics_instance.mem = [56.4, 71.3, 68.9]
    statistics_instance.io = {'eth0': (123465, 654321), 'lo': (321, 321)}
    statistics_instance.proc = {('myself', 5888): (25.0, 12.5)}
    # check clearance
    statistics_instance.clear()
    assert statistics_instance.period == 2
    assert statistics_instance.depth == 2
    assert statistics_instance.counter == -1
    assert statistics_instance.ref_stats is None
    assert type(statistics_instance.cpu) is list
    assert not statistics_instance.cpu
    assert type(statistics_instance.mem) is list
    assert not statistics_instance.mem
    assert type(statistics_instance.io) is dict
    assert not statistics_instance.io
    assert type(statistics_instance.proc) is dict
    assert not statistics_instance.proc


def test_find_process_stats(statistics_instance):
    """ Test the search method for process statistics. """
    # change values
    statistics_instance.proc = {('the_other', 1234): (1.5, 2.4), ('myself', 5888): (25.0, 12.5)}
    # test find method with wrong argument
    assert statistics_instance.find_process_stats('someone') is None
    # test find method with correct argument
    stats = statistics_instance.find_process_stats('myself')
    assert stats == (25.0, 12.5)


def test_trunc_depth(statistics_instance):
    """ Test the history depth. """
    # test that the trunc_depth method does nothing when less than 2 elements in list
    test_list = [1, 2]
    statistics_instance.trunc_depth(test_list)
    assert test_list == [1, 2]
    # test that the trunc_depth method keeps only the last 5 elements in list
    test_list = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    statistics_instance.trunc_depth(test_list)
    assert test_list == [9, 10]


def test_push_cpu_stats(statistics_instance):
    """ Test the storage of the CPU instant statistics. """
    cpu_stats = [12.1, 16.0]
    # test adding CPU stats on non-initialized structure
    # should not happen as protected by the upper call of push_statistics
    statistics_instance._push_cpu_stats(cpu_stats)
    assert not statistics_instance.cpu
    # init internal structure and retry
    statistics_instance.cpu = [[] for _ in cpu_stats]
    statistics_instance._push_cpu_stats(cpu_stats)
    assert statistics_instance.cpu == [[12.1], [16.0]]
    # again: list increases
    cpu_stats = [8.7, 14.6]
    statistics_instance._push_cpu_stats(cpu_stats)
    assert statistics_instance.cpu == [[12.1, 8.7], [16.0, 14.6]]
    # again: list rotates due to history depth at 2
    cpu_stats = [11.9, 5.5]
    statistics_instance._push_cpu_stats(cpu_stats)
    assert statistics_instance.cpu == [[8.7, 11.9], [14.6, 5.5]]


def test_push_mem_stats(statistics_instance):
    """ Test the storage of the MEM instant statistics. """
    # MEM stats internal structure is initialized (simple list)
    statistics_instance._push_mem_stats(12.1)
    assert statistics_instance.mem == [12.1]
    # again: list increases
    statistics_instance._push_mem_stats(8.7)
    assert statistics_instance.mem == [12.1, 8.7]
    # again: list rotates due to history depth at 2
    statistics_instance._push_mem_stats(11.9)
    assert statistics_instance.mem == [8.7, 11.9]


def test_push_io_stats(statistics_instance):
    """ Test the storage of the IO instant statistics. """
    io_stats = {'eth0': (1024, 2000), 'lo': (500, 500)}
    # first time: structures are created
    statistics_instance._push_io_stats(io_stats)
    assert statistics_instance.io == {'eth0': ([1024], [2000]), 'lo': ([500], [500])}
    # again: list increases
    io_stats = {'eth0': (1250, 2200), 'lo': (620, 620)}
    statistics_instance._push_io_stats(io_stats)
    assert statistics_instance.io == {'eth0': ([1024, 1250], [2000, 2200]), 'lo': ([500, 620], [500, 620])}
    # again: list rotates due to history depth at 2
    io_stats = {'eth0': (2048, 2512), 'lo': (756, 756)}
    statistics_instance._push_io_stats(io_stats)
    assert statistics_instance.io == {'eth0': ([1250, 2048], [2200, 2512]), 'lo': ([620, 756], [620, 756])}
    # test obsolete and new interface
    io_stats = {'eth1': (3072, 2768), 'lo': (1780, 1780)}
    statistics_instance._push_io_stats(io_stats)
    assert statistics_instance.io == {'eth1': ([3072], [2768]), 'lo': ([756, 1780], [756, 1780])}


def test_push_process_stats(statistics_instance):
    """ Test the storage of the process instant statistics. """
    proc_stats = {('myself', 118612): (0.15, 1.85), ('other', 7754): (15.4, 12.2)}
    statistics_instance._push_process_stats(proc_stats)
    assert statistics_instance.proc == {('myself', 118612): ([0.15], [1.85]), ('other', 7754): ([15.4], [12.2])}
    # again: list increases
    proc_stats = {('myself', 118612): (1.9, 1.93), ('other', 7754): (14.9, 12.8)}
    statistics_instance._push_process_stats(proc_stats)
    assert statistics_instance.proc == {('myself', 118612): ([0.15, 1.9], [1.85, 1.93]),
                                        ('other', 7754): ([15.4, 14.9], [12.2, 12.8])}
    # again: list rotates due to history depth at 2
    proc_stats = {('myself', 118612): (2.47, 2.04), ('other', 7754): (6.5, 13.0)}
    statistics_instance._push_process_stats(proc_stats)
    assert statistics_instance.proc == {('myself', 118612): ([1.9, 2.47], [1.93, 2.04]),
                                        ('other', 7754): ([14.9, 6.5], [12.8, 13.0])}
    # test obsolete and new processes (here other is just restarted - new pid)
    proc_stats = {('myself', 118612): (0.15, 1.85), ('other', 826): (1.89, 2.67)}
    statistics_instance._push_process_stats(proc_stats)
    assert statistics_instance.proc == {('myself', 118612): ([2.47, 0.15], [2.04, 1.85]),
                                        ('other', 826): ([1.89], [2.67])}


def test_push_statistics(mocker, statistics_instance):
    """ Test the storage of the instant statistics. """
    mocked_stats = mocker.patch('supvisors.statscompiler.statistics')
    mocked_cpu = mocker.patch.object(statistics_instance, '_push_cpu_stats')
    mocked_mem = mocker.patch.object(statistics_instance, '_push_mem_stats')
    mocked_io = mocker.patch.object(statistics_instance, '_push_io_stats')
    mocked_proc = mocker.patch.object(statistics_instance, '_push_process_stats')
    # push first set of measures
    stats1 = 'stats 1'
    mocked_stats.return_value = (8.5, 'cpu_stats 1', 76.1, 'io_stats 1', 'proc_stats 1')
    statistics_instance.push_statistics(stats1)
    # check evolution of instance
    assert statistics_instance.counter == 0
    assert statistics_instance.ref_stats is stats1
    assert not mocked_stats.called
    assert not mocked_cpu.called
    assert not mocked_mem.called
    assert not mocked_io.called
    assert not mocked_proc.called
    # push second set of measures
    stats2 = 'stats 2'
    mocked_stats.return_value = (18.52, 'cpu_stats 2', 76.2, 'io_stats 2', 'proc_stats 2')
    statistics_instance.push_statistics(stats2)
    # counter is based a theoretical period of 5 seconds so this update is not taken into account
    # check evolution of instance
    assert statistics_instance.counter == 1
    assert statistics_instance.ref_stats is stats1
    assert not mocked_stats.called
    assert not mocked_cpu.called
    assert not mocked_mem.called
    assert not mocked_io.called
    assert not mocked_proc.called
    # push third set of measures
    stats3 = 'stats 3'
    mocked_stats.return_value = (28.5, 'cpu_stats 3', 76.1, 'io_stats 3', 'proc_stats 3')
    statistics_instance.push_statistics(stats3)
    # this update is taken into account
    # check evolution of instance
    assert statistics_instance.counter == 2
    assert statistics_instance.ref_stats is stats3
    assert mocked_stats.call_args_list == [call(stats3, stats1)]
    assert mocked_cpu.call_args_list == [call('cpu_stats 3')]
    assert mocked_mem.call_args_list == [call(76.1)]
    assert mocked_io.call_args_list == [call('io_stats 3')]
    assert mocked_proc.call_args_list == [call('proc_stats 3')]
    mocker.resetall()
    # push fourth set of measures (reuse stats2)
    statistics_instance.push_statistics(stats2)
    # again,this update is not taken into account
    assert statistics_instance.counter == 3
    assert statistics_instance.ref_stats is stats3
    assert not mocked_stats.called
    assert not mocked_cpu.called
    assert not mocked_mem.called
    assert not mocked_io.called
    assert not mocked_proc.called
    # push fifth set of measures
    stats5 = 'stats 5'
    mocked_stats.return_value = (38.5, 'cpu_stats 5', 75.9, 'io_stats 5', 'proc_stats 5')
    statistics_instance.push_statistics(stats5)
    # this update is taken into account
    # check evolution of instance
    assert statistics_instance.counter == 4
    assert statistics_instance.ref_stats is stats5
    assert mocked_stats.call_args_list == [call(stats5, stats3)]
    assert mocked_cpu.call_args_list == [call('cpu_stats 5')]
    assert mocked_mem.call_args_list == [call(75.9)]
    assert mocked_io.call_args_list == [call('io_stats 5')]
    assert mocked_proc.call_args_list == [call('proc_stats 5')]


@pytest.fixture
def compiler(supvisors):
    return StatisticsCompiler(supvisors)


def test_compiler_create(supvisors, compiler):
    """ Test the initialization for statistics of all addresses. """
    # check compiler contents at initialisation
    assert list(compiler.data.keys()) == list(supvisors.supvisors_mapper.instances.keys())
    for period_instance in compiler.data.values():
        assert tuple(period_instance.keys()) == supvisors.options.stats_periods
        for period, instance in period_instance.items():
            assert type(instance) is StatisticsInstance
            assert instance.period == period / 5
            assert instance.depth == supvisors.options.stats_histo


def test_compiler_clear(compiler):
    """ Test the clearance for statistics of all addresses. """
    # set data to a given address
    for address, period_instance in compiler.data.items():
        for period, instance in period_instance.items():
            instance.counter = 28
            instance.ref_stats = ('dummy', 0)
            instance.cpu = [13.2, 14.8]
            instance.mem = [56.4, 71.3, 68.9]
            instance.io = {'eth0': (123465, 654321), 'lo': (321, 321)}
            instance.proc = {('myself', 5888): (25.0, 12.5)}
    # check clearance of instance
    compiler.clear('10.0.0.2')
    for address, period_instance in compiler.data.items():
        if address == '10.0.0.2':
            for period, instance in period_instance.items():
                assert instance.period == period / 5
                assert instance.depth == 10
                assert instance.counter == -1
                assert instance.ref_stats is None
                assert type(instance.cpu) is list
                assert not instance.cpu
                assert type(instance.mem) is list
                assert not instance.mem
                assert type(instance.io) is dict
                assert not instance.io
                assert type(instance.proc) is dict
                assert not instance.proc
        else:
            for period, instance in period_instance.items():
                assert instance.period == period / 5
                assert instance.depth == 10
                assert instance.counter == 28
                assert instance.ref_stats == ('dummy', 0)
                assert instance.cpu == [13.2, 14.8]
                assert instance.mem == [56.4, 71.3, 68.9]
                assert instance.io == {'eth0': (123465, 654321), 'lo': (321, 321)}
                assert instance.proc == {('myself', 5888): (25.0, 12.5)}


def test_compiler_push_statistics(compiler):
    """ Test the storage of the instant statistics of an address. """
    # push statistics to a given address
    stats1 = (8.5, [(25, 400), (25, 125), (15, 150), (40, 400), (20, 200)],
              76.1, {'eth0': (1024, 2000), 'lo': (500, 500)}, {'myself': (118612, (0.15, 1.85))})
    compiler.push_statistics('10.0.0.2', stats1)
    # check compiler contents
    for address, period_instance in compiler.data.items():
        if address == '10.0.0.2':
            for period, instance in period_instance.items():
                assert instance.counter == 0
                assert instance.ref_stats is stats1
        else:
            for period, instance in period_instance.items():
                assert instance.counter == -1
                assert instance.ref_stats is None
    # push statistics to a given address
    stats2 = (28.5, [(45, 700), (50, 225), (40, 250), (42, 598), (20, 400)],
              76.1, {'eth0': (2048, 2512), 'lo': (756, 756)}, {'myself': (118612, (1.75, 1.9))})
    compiler.push_statistics('10.0.0.2', stats2)
    # check compiler contents
    for address, period_instance in compiler.data.items():
        if address == '10.0.0.2':
            for period, instance in period_instance.items():
                assert instance.counter == 1
                if period == 5:
                    assert instance.ref_stats is stats2
                else:
                    assert instance.ref_stats is stats1
        else:
            for period, instance in period_instance.items():
                assert instance.counter == -1
                assert instance.ref_stats is None
    # push statistics to a given address
    stats3 = (38.5, [(80, 985), (89, 386), (48, 292), (42, 635), (32, 468)],
              75.9, {'eth0': (3072, 2768), 'lo': (1780, 1780)}, {'myself': (118612, (11.75, 1.87))})
    compiler.push_statistics('10.0.0.2', stats3)
    # check compiler contents
    for address, period_instance in compiler.data.items():
        if address == '10.0.0.2':
            for period, instance in period_instance.items():
                assert instance.counter == 2
                if period == 5:
                    assert instance.ref_stats is stats3
                else:
                    assert instance.ref_stats is stats1
        else:
            for period, instance in period_instance.items():
                assert instance.counter == -1
                assert instance.ref_stats is None
    # push statistics to a given address
    stats4 = (48.5, [(84, 1061), (92, 413), (48, 480), (45, 832), (40, 1100)],
              74.7, {'eth0': (3584, 3792), 'lo': (1812, 1812)}, {'myself': (118612, (40.75, 2.34))})
    compiler.push_statistics('10.0.0.2', stats4)
    # check compiler contents
    for address, period_instance in compiler.data.items():
        if address == '10.0.0.2':
            for period, instance in period_instance.items():
                assert instance.counter == 3
                if period in [5, 15]:
                    assert instance.ref_stats is stats4
                else:
                    assert instance.ref_stats is stats1
        else:
            for period, instance in period_instance.items():
                assert instance.counter == -1
                assert instance.ref_stats is None
