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


def test_cpu_statistics():
    """ Test the CPU statistics between 2 dates. """
    from supvisors.statscompiler import cpu_statistics
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
    from supvisors.statscompiler import cpu_total_work
    # take 2 instant cpu statistics
    ref_stats = [(83.31, 305.4)] * 2
    last_stats = [(83.41, 306.3)] * 2
    total_work = cpu_total_work(last_stats, ref_stats)
    # total work is the sum of jiffies spent on cpu all
    assert pytest.approx(total_work) == 1


def test_io_statistics():
    """ Test the I/O statistics between 2 dates. """
    from supvisors.statscompiler import io_statistics
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
    from supvisors.statscompiler import cpu_process_statistics
    stats = cpu_process_statistics(50, 20, 100)
    assert type(stats) is float
    assert pytest.approx(stats) == 30


def test_statistics():
    """ Test the global statistics between 2 dates. """
    from supvisors.statscompiler import statistics
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


def test_stats_create():
    """ Test the initialization of an instance. """
    from supvisors.statscompiler import StatisticsInstance
    instance = StatisticsInstance(17, 10)
    # check attributes
    assert instance.period == 3
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


def test_clear():
    """ Test the clearance of an instance. """
    from supvisors.statscompiler import StatisticsInstance
    instance = StatisticsInstance(17, 10)
    # change values
    instance.counter = 28
    instance.ref_stats = ('dummy', 0)
    instance.cpu = [13.2, 14.8]
    instance.mem = [56.4, 71.3, 68.9]
    instance.io = {'eth0': (123465, 654321), 'lo': (321, 321)}
    instance.proc = {('myself', 5888): (25.0, 12.5)}
    # check clearance
    instance.clear()
    assert instance.period == 3
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


def test_find_process_stats():
    """ Test the search method for process statistics. """
    from supvisors.statscompiler import StatisticsInstance
    instance = StatisticsInstance(17, 10)
    # change values
    instance.proc = {('the_other', 1234): (1.5, 2.4), ('myself', 5888): (25.0, 12.5)}
    # test find method with wrong argument
    assert instance.find_process_stats('someone') is None
    # test find method with correct argument
    stats = instance.find_process_stats('myself')
    assert stats == (25.0, 12.5)


def test_trunc_depth():
    """ Test the history depth. """
    from supvisors.statscompiler import StatisticsInstance
    instance = StatisticsInstance(12, 5)
    # test that the truc_depth method does nothing when less than 5 elements in list
    test_list = [1, 2, 3, 4]
    instance.trunc_depth(test_list)
    assert test_list == [1, 2, 3, 4]
    # test that the truc_depth method keeps only the last 5 elements in list
    test_list = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    instance.trunc_depth(test_list)
    assert test_list == [6, 7, 8, 9, 10]


def test_push_statistics():
    """ Test the storage of the instant statistics. """
    from supvisors.statscompiler import StatisticsInstance
    # testing with period 12 and history depth 2
    instance = StatisticsInstance(12, 2)
    # push first set of measures
    stats1 = (8.5, [(25, 400), (25, 125), (15, 150), (40, 400), (20, 200)],
              76.1, {'eth0': (1024, 2000), 'lo': (500, 500)},
              {'myself': (118612, (0.15, 1.85)), 'other1': (7754, (0.15, 1.85)), 'other2': (826, (0.15, 1.85))})
    instance.push_statistics(stats1)
    # check evolution of instance
    assert instance.counter == 0
    assert len(instance.cpu) == 5
    for cpu in instance.cpu:
        assert not cpu
    assert not instance.mem
    assert list(instance.io.keys()) == ['eth0', 'lo']
    for recv, sent in instance.io.values():
        assert recv == []
        assert sent == []
    assert list(instance.proc.keys()) == [('myself', 118612), ('other1', 7754), ('other2', 826)]
    for cpu_list, mem_list in instance.proc.values():
        assert cpu_list == []
        assert mem_list == []
    assert instance.ref_stats is stats1
    # push second set of measures
    stats2 = (18.52, [(30, 600), (40, 150), (30, 200), (41, 550), (20, 300)],
              76.2, {'eth0': (1250, 2200), 'lo': (620, 620)},
              {'myself': (118612, (0.16, 1.84)), 'other2': (826, (0.16, 1.84))})
    instance.push_statistics(stats2)
    # counter is based a theoretical period of 5 seconds
    # this update is not taken into account
    # check evolution of instance
    assert instance.counter == 1
    assert len(instance.cpu) == 5
    for cpu in instance.cpu:
        assert not cpu
    assert not instance.mem
    assert list(instance.io.keys()) == ['eth0', 'lo']
    for recv, sent in instance.io.values():
        assert recv == []
        assert sent == []
    assert list(instance.proc.keys()) == [('myself', 118612), ('other1', 7754), ('other2', 826)]
    for cpu_list, mem_list in instance.proc.values():
        assert cpu_list == []
        assert mem_list == []
    assert instance.ref_stats is stats1
    # push third set of measures
    stats3 = (28.5, [(45, 700), (50, 225), (40, 250), (42, 598), (20, 400)],
              76.1, {'eth0': (2048, 2512), 'lo': (756, 756)},
              {'myself': (118612, (1.75, 1.9)), 'other1': (8865, (1.75, 1.9))})
    instance.push_statistics(stats3)
    # this update is taken into account
    # check evolution of instance
    assert instance.counter == 2
    assert instance.cpu == [[6.25], [20.0], [20.0], [1.0], [0.0]]
    assert instance.mem == [76.1]
    assert instance.io == {'eth0': ([0.4], [0.2]), 'lo': ([0.1], [0.1])}
    assert instance.proc == {('myself', 118612): ([0.5], [1.9])}
    assert instance.ref_stats is stats3
    # push fourth set of measures (reuse stats2)
    instance.push_statistics(stats2)
    # again,this update is not taken into account
    assert instance.counter == 3
    assert instance.ref_stats is stats3
    # push fifth set of measures
    stats5 = (38.5, [(80, 985), (89, 386), (48, 292), (42, 635), (32, 468)],
              75.9, {'eth0': (3072, 2768), 'lo': (1780, 1780)},
              {'myself': (118612, (11.75, 1.87)), 'other1': (8865, (11.75, 1.87))})
    instance.push_statistics(stats5)
    # this update is taken into account
    # check evolution of instance
    assert instance.counter == 4
    assert instance.cpu == [[6.25, 10.9375], [20.0, 19.5], [20.0, 16.0], [1.0, 0.0], [0.0, 15.0]]
    assert instance.mem == [76.1, 75.9]
    assert instance.io == {'eth0': ([0.4, 0.8], [0.2, 0.2]), 'lo': ([0.1, 0.8], [0.1, 0.8])}
    assert instance.proc == {('myself', 118612): ([0.5, 3.125], [1.9, 1.87]), ('other1', 8865): ([3.125], [1.87])}
    assert instance.ref_stats is stats5
    # push sixth set of measures (reuse stats2)
    instance.push_statistics(stats2)
    # this update is not taken into account
    # check evolution of instance
    assert instance.counter == 5
    assert instance.ref_stats is stats5
    # push seventh set of measures
    stats7 = (48.5, [(84, 1061), (92, 413), (48, 480), (45, 832), (40, 1100)],
              74.7, {'eth0': (3584, 3792), 'lo': (1812, 1812)},
              {'myself': (118612, (40.75, 2.34)), 'other1': (8865, (40.75, 2.34))})
    instance.push_statistics(stats7)
    # this update is taken into account
    # check evolution of instance. max depth is reached so lists roll
    assert instance.counter == 6
    assert instance.cpu == [[10.9375, 5.0], [19.5, 10.0], [16.0, 0.0], [0.0, 1.5], [15.0, 1.25]]
    assert instance.mem == [75.9, 74.7]
    assert instance.io == {'eth0': ([0.8, 0.4], [0.2, 0.8]), 'lo': ([0.8, 0.025], [0.8, 0.025])}
    assert instance.proc == {('myself', 118612): ([3.125, 36.25], [1.87, 2.34]),
                             ('other1', 8865): ([3.125, 36.25], [1.87, 2.34])}
    assert instance.ref_stats is stats7


@pytest.fixture
def compiler(supvisors):
    from supvisors.statscompiler import StatisticsCompiler
    return StatisticsCompiler(supvisors)


def test_compiler_create(supvisors, compiler):
    """ Test the initialization for statistics of all addresses. """
    from supvisors.statscompiler import StatisticsInstance
    # check compiler contents at initialisation
    assert list(compiler.data.keys()) == supvisors.address_mapper.node_names
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
