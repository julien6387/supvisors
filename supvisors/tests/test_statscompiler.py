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
import os
from unittest.mock import call, Mock

import pytest

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
    assert stats == {'lo': [8, 8], 'eth0': [7, 1]}


def test_trunc_depth():
    """ Test the history depth. """
    # test that the trunc_depth method does nothing when less than 2 elements in list
    test_list = [1, 2]
    trunc_depth(test_list, 5)
    assert test_list == [1, 2]
    # test that the trunc_depth method keeps only the last 5 elements in list
    test_list = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    trunc_depth(test_list, 5)
    assert test_list == [6, 7, 8, 9, 10]


# Host Statistics part
@pytest.fixture
def host_statistics_instance(logger_instance):
    # testing with period 12 and history depth 2
    return HostStatisticsInstance('10.0.0.1', 12, 2, logger_instance)


def test_host_statistics_instance_creation(host_statistics_instance, supvisors_instance):
    """ Test the creation of HostStatisticsInstance. """
    assert host_statistics_instance.logger is supvisors_instance.logger
    assert host_statistics_instance.identifier == '10.0.0.1'
    assert host_statistics_instance.period == 12
    assert host_statistics_instance.depth == 2
    assert host_statistics_instance.ref_stats == {}
    assert host_statistics_instance.ref_start_time == 0.0
    assert host_statistics_instance.times == []
    assert host_statistics_instance.cpu == []
    assert host_statistics_instance.mem == []
    assert host_statistics_instance.net_io == {}
    assert host_statistics_instance.disk_io == {}
    assert host_statistics_instance.disk_usage == {}


def test_host_statistics_instance_push_times(host_statistics_instance):
    """ Test the HostStatisticsInstance._push_times_stats method. """
    host_statistics_instance._push_times_stats(1.0)
    assert host_statistics_instance.times == [1.0]
    host_statistics_instance._push_times_stats(2.5)
    assert host_statistics_instance.times == [1.0, 2.5]
    host_statistics_instance._push_times_stats(3.8)
    assert host_statistics_instance.times == [2.5, 3.8]
    host_statistics_instance._push_times_stats(5.7)
    assert host_statistics_instance.times == [3.8, 5.7]


def test_host_statistics_instance_push_cpu(host_statistics_instance):
    """ Test the HostStatisticsInstance._push_cpu_stats method. """
    cpu_stats = [12.1, 16.0]
    # test adding CPU stats on non-initialized structure
    # should not happen as protected by the upper call of push_statistics
    host_statistics_instance._push_cpu_stats(cpu_stats)
    assert not host_statistics_instance.cpu
    # init internal structure and retry
    host_statistics_instance.cpu = [[] for _ in cpu_stats]
    host_statistics_instance._push_cpu_stats(cpu_stats)
    assert host_statistics_instance.cpu == [[12.1], [16.0]]
    # again: list increases
    cpu_stats = [8.7, 14.6]
    host_statistics_instance._push_cpu_stats(cpu_stats)
    assert host_statistics_instance.cpu == [[12.1, 8.7], [16.0, 14.6]]
    # again: list rotates due to history depth at 2
    cpu_stats = [11.9, 5.5]
    host_statistics_instance._push_cpu_stats(cpu_stats)
    assert host_statistics_instance.cpu == [[8.7, 11.9], [14.6, 5.5]]


def test_host_statistics_instance_push_mem(host_statistics_instance):
    """ Test the HostStatisticsInstance._push_mem_stats method. """
    # MEM stats internal structure is initialized (simple list)
    host_statistics_instance._push_mem_stats(12.1)
    assert host_statistics_instance.mem == [12.1]
    # again: list increases
    host_statistics_instance._push_mem_stats(8.7)
    assert host_statistics_instance.mem == [12.1, 8.7]
    # again: list rotates due to history depth at 2
    host_statistics_instance._push_mem_stats(11.9)
    assert host_statistics_instance.mem == [8.7, 11.9]


def test_host_statistics_instance_push_io(host_statistics_instance):
    """ Test the storage of the IO instant statistics. """
    ref_stats = {}
    # first time: structures are created
    io_stats = {'eth0': [1024, 2000], 'lo': [500, 500]}
    host_statistics_instance._push_timed_stats(ref_stats, io_stats, 'nic', 5)
    assert ref_stats == {'eth0': ([5], [[1024], [2000]]),
                         'lo': ([5], [[500], [500]])}
    # again: list increases
    io_stats = {'eth0': [1250, 2200], 'lo': [620, 620]}
    host_statistics_instance._push_timed_stats(ref_stats, io_stats, 'nic', 10)
    assert ref_stats == {'eth0': ([5, 10], [[1024, 1250], [2000, 2200]]),
                         'lo': ([5, 10], [[500, 620], [500, 620]])}
    # again: list rotates due to history depth at 2
    io_stats = {'eth0': [2048, 2512], 'lo': [756, 756]}
    host_statistics_instance._push_timed_stats(ref_stats, io_stats, 'nic', 15)
    assert ref_stats == {'eth0': ([10, 15], [[1250, 2048], [2200, 2512]]),
                         'lo': ([10, 15], [[620, 756], [620, 756]])}
    # test obsolete and new interface
    io_stats = {'eth1': [3072, 2768], 'lo': [1780, 1780]}
    host_statistics_instance._push_timed_stats(ref_stats, io_stats, 'nic', 20)
    assert ref_stats == {'eth1': ([20], [[3072], [2768]]),
                         'lo': ([15, 20], [[756, 1780], [756, 1780]])}


def test_host_statistics_instance_push_net_io(mocker, host_statistics_instance):
    """ Test the storage of the network IO instant statistics. """
    mocked_push = mocker.patch.object(host_statistics_instance, '_push_timed_stats')
    io_stats = {'eth0': [2048, 2512], 'lo': [756, 756]}
    host_statistics_instance._push_net_io_stats(io_stats, 10)
    assert mocked_push.call_args_list == [call(host_statistics_instance.net_io, io_stats, 'nic', 10)]


def test_host_statistics_instance_push_disk_io(mocker, host_statistics_instance):
    """ Test the storage of the disk IO instant statistics. """
    mocked_push = mocker.patch.object(host_statistics_instance, '_push_timed_stats')
    io_stats = {'sda': [1024, 10000], 'sda1': [0, 29582848]}
    host_statistics_instance._push_disk_io_stats(io_stats, 5)
    assert mocked_push.call_args_list == [call(host_statistics_instance.disk_io, io_stats, 'device', 5)]


def test_host_statistics_instance_push_disk_usage(mocker, host_statistics_instance):
    """ Test the storage of the disk usage instant statistics. """
    mocked_push = mocker.patch.object(host_statistics_instance, '_push_timed_stats')
    io_stats = {'/': [60.4], '/boot': [42.6]}
    host_statistics_instance._push_disk_usage_stats(io_stats, 20)
    assert mocked_push.call_args_list == [call(host_statistics_instance.disk_usage, io_stats, 'partition', 20)]


def test_host_statistics_instance_integrate(host_statistics_instance):
    """ Test the host statistics integration between 2 instants. """
    host_statistics_instance.ref_start_time = 500
    host_statistics_instance.ref_stats = {'now': 1000,
                                          'cpu': [(25, 400), (25, 125), (15, 150)],
                                          'mem': 65,
                                          'net_io': {'eth0': (2000, 200), 'lo': (5000, 5000)},
                                          'disk_io': {'sda': (1000, 10000), 'sda1': (0, 100)},
                                          'disk_usage': {'/': 60.4, '/boot': 42.6}}
    last_stats = {'now': 1002,
                  'cpu': [(45, 700), (50, 225), (40, 250)],
                  'mem': 67.7,
                  'net_io': {'eth0': (2768, 456), 'lo': (6024, 6024)},
                  'disk_io': {'sda': (1512, 11024), 'sda1': (64, 100)},
                  'disk_usage': {'/': 60.5, '/boot': 42.5}}
    stats = host_statistics_instance.integrate(last_stats)
    # check result
    uptime, cpu_stats, mem_stats, net_io_stats, disk_io_stats, disk_usage_stats = stats
    # check date
    assert uptime == 502
    # check stats
    assert cpu_stats == [6.25, 20.0, 20.0]
    assert pytest.approx(mem_stats) == 67.7
    assert net_io_stats == {'lo': [4, 4], 'eth0': [3, 1]}
    assert disk_io_stats == {'sda': [2.0, 4.0], 'sda1': [0.25, 0.0]}
    assert disk_usage_stats == {'/': [60.5], '/boot': [42.5]}


def test_host_statistics_instance_push_statistics(mocker, host_statistics_instance):
    """ Test the reception of new host statistics. """
    mocker.patch('time.monotonic', return_value=1234.56)
    mocked_stats = mocker.patch.object(host_statistics_instance, 'integrate')
    mocked_times = mocker.patch.object(host_statistics_instance, '_push_times_stats')
    mocked_cpu = mocker.patch.object(host_statistics_instance, '_push_cpu_stats')
    mocked_mem = mocker.patch.object(host_statistics_instance, '_push_mem_stats')
    mocked_net_io = mocker.patch.object(host_statistics_instance, '_push_net_io_stats')
    mocked_disk_io = mocker.patch.object(host_statistics_instance, '_push_disk_io_stats')
    mocked_disk_usage = mocker.patch.object(host_statistics_instance, '_push_disk_usage_stats')
    # push first set of measures to become the first reference statistics
    stats1 = {'now': 1.0, 'cpu': [[], [], []],
              'net_io': {'lo': [], 'eth0': []},
              'disk_io': {'sda': [], 'sda1': []},
              'disk_usage': {'/': [], '/boot': []}}
    mocked_stats.return_value = (1.0, ['cpu_stats 1'], 76.1, {'net_io_stats 1': []},
                                 {'disk_io_stats 1': []}, {'disk_usage_stats 1': []})
    result = host_statistics_instance.push_statistics(stats1)
    assert result == {}
    # check evolution of instance
    assert host_statistics_instance.ref_start_time == 1.0
    assert host_statistics_instance.ref_stats is stats1
    assert not mocked_stats.called
    assert not mocked_times.called
    assert not mocked_cpu.called
    assert not mocked_mem.called
    assert not mocked_net_io.called
    assert not mocked_disk_io.called
    assert not mocked_disk_usage.called
    # push second set of measures
    stats2 = {'now': 5.1, 'cpu': [[], [], []],
              'net_io': {'lo': [], 'eth0': []},
              'disk_io': {'sda': [], 'sda1': []},
              'disk_usage': {'/': [], '/boot': []}}
    mocked_stats.return_value = (5.1, ['cpu_stats 2'], 76.2, {'net_io_stats 2': []},
                                 {'disk_io_stats 2': []}, {'disk_usage_stats 2': []})
    result = host_statistics_instance.push_statistics(stats2)
    # counter is based a theoretical period of 5 seconds so this update is not taken into account
    assert result == {}
    # check evolution of instance
    assert host_statistics_instance.ref_start_time == 1.0
    assert host_statistics_instance.ref_stats is stats1
    assert not mocked_stats.called
    assert not mocked_times.called
    assert not mocked_cpu.called
    assert not mocked_mem.called
    assert not mocked_net_io.called
    assert not mocked_disk_io.called
    assert not mocked_disk_usage.called
    # push third set of measures
    stats3 = {'now': 13.2, 'cpu': [[], [], []],
              'net_io': {'lo': [], 'eth0': []},
              'disk_io': {'sda': [], 'sda1': []},
              'disk_usage': {'/': [], '/boot': []}}
    mocked_stats.return_value = (12.2, ['cpu_stats 3'], 76.1, {'net_io_stats 3': []},
                                 {'disk_io_stats 3': []}, {'disk_usage_stats 3': [75]})
    result = host_statistics_instance.push_statistics(stats3)
    # this update is taken into account
    assert result == {'identifier': '10.0.0.1',
                      'now_monotonic': 1234.56,
                      'target_period': 12,
                      'period': (0.0, 12.2),
                      'cpu': ['cpu_stats 3'],
                      'mem': 76.1,
                      'net_io': {'net_io_stats 3': []},
                      'disk_io': {'disk_io_stats 3': []},
                      'disk_usage': {'disk_usage_stats 3': 75}}
    # check evolution of instance
    assert host_statistics_instance.ref_start_time == 1.0
    assert host_statistics_instance.ref_stats is stats3
    assert mocked_stats.call_args_list == [call(stats3)]
    assert mocked_times.call_args_list == [call(12.2)]
    assert mocked_cpu.call_args_list == [call(['cpu_stats 3'])]
    assert mocked_mem.call_args_list == [call(76.1)]
    assert mocked_net_io.call_args_list == [call({'net_io_stats 3': []}, 12.2)]
    assert mocked_disk_io.call_args_list == [call({'disk_io_stats 3': []}, 12.2)]
    assert mocked_disk_usage.call_args_list == [call({'disk_usage_stats 3': [75]}, 12.2)]
    mocker.resetall()
    # push fourth set of measures (reuse stats2)
    result = host_statistics_instance.push_statistics(stats2)
    # again, this update is not taken into account
    assert result == {}
    assert host_statistics_instance.ref_start_time == 1.0
    assert host_statistics_instance.ref_stats is stats3
    assert not mocked_stats.called
    assert not mocked_times.called
    assert not mocked_cpu.called
    assert not mocked_mem.called
    assert not mocked_net_io.called
    assert not mocked_disk_io.called
    assert not mocked_disk_usage.called
    # push fifth set of measures
    stats5 = {'now': 27.4, 'cpu': [[], [], []],
              'net_io': {'lo': [], 'eth0': []},
              'disk_io': {'sda': [], 'sda1': []},
              'disk_usage': {'/': [], '/boot': []}}
    mocked_stats.return_value = (38.5, ['cpu_stats 5'], 75.9, {'net_io_stats 5': []},
                                 {'disk_io_stats 5': []}, {'disk_usage_stats 5': [68]})
    result = host_statistics_instance.push_statistics(stats5)
    # this update is taken into account
    assert result == {'identifier': '10.0.0.1',
                      'now_monotonic': 1234.56,
                      'target_period': 12,
                      'period': (12.2, 26.4),
                      'cpu': ['cpu_stats 5'],
                      'mem': 75.9,
                      'net_io': {'net_io_stats 5': []},
                      'disk_io': {'disk_io_stats 5': []},
                      'disk_usage': {'disk_usage_stats 5': 68}}
    # check evolution of instance
    assert host_statistics_instance.ref_start_time == 1.0
    assert host_statistics_instance.ref_stats is stats5
    assert mocked_stats.call_args_list == [call(stats5)]
    assert mocked_times.call_args_list == [call(38.5)]
    assert mocked_cpu.call_args_list == [call(['cpu_stats 5'])]
    assert mocked_mem.call_args_list == [call(75.9)]
    assert mocked_net_io.call_args_list == [call({'net_io_stats 5': []}, 38.5)]
    assert mocked_disk_io.call_args_list == [call({'disk_io_stats 5': []}, 38.5)]
    assert mocked_disk_usage.call_args_list == [call({'disk_usage_stats 5': [68]}, 38.5)]


@pytest.fixture
def host_statistics_compiler(supvisors_instance):
    return HostStatisticsCompiler(supvisors_instance)


def test_host_statistics_compiler_creation(supvisors_instance, host_statistics_compiler):
    """ Test the creation of HostStatisticsCompiler. """
    assert host_statistics_compiler.supvisors is supvisors_instance
    assert host_statistics_compiler.instance_map == {}
    assert host_statistics_compiler.nb_cores == {}


def test_host_statistics_compiler_add_instance(supvisors_instance, host_statistics_compiler):
    """ Test the HostStatisticsCompiler.add_instance method """
    # add a first instance
    host_statistics_compiler.add_instance('10.0.0.1:25000')
    assert sorted(host_statistics_compiler.instance_map.keys()) == ['10.0.0.1:25000']
    for period_map in host_statistics_compiler.instance_map.values():
        assert sorted(period_map.keys()) == [5.0, 15.0, 60.0]
        for period, period_instances in period_map.items():
            assert isinstance(period_instances, HostStatisticsInstance)
            assert period_instances.period == period
            assert period_instances.depth == supvisors_instance.options.stats_histo
            assert period_instances.logger is supvisors_instance.logger
    # add a second instance
    host_statistics_compiler.add_instance('10.0.0.2:25000')
    assert sorted(host_statistics_compiler.instance_map.keys()) == ['10.0.0.1:25000', '10.0.0.2:25000']
    for period_map in host_statistics_compiler.instance_map.values():
        assert sorted(period_map.keys()) == [5.0, 15.0, 60.0]
        for period, period_instances in period_map.items():
            assert isinstance(period_instances, HostStatisticsInstance)
            assert period_instances.period == period
            assert period_instances.depth == supvisors_instance.options.stats_histo
            assert period_instances.logger is supvisors_instance.logger


@pytest.fixture
def filled_host_statistics_compiler(supvisors_instance, host_statistics_compiler):
    """ Add all declared Supvisors instances to the compiler. """
    for identifier in supvisors_instance.mapper.instances:
        host_statistics_compiler.add_instance(identifier)
    return host_statistics_compiler


def test_host_statistics_compiler_get_stats(filled_host_statistics_compiler):
    """ Test the HostStatisticsCompiler.get_stats method """
    # test with unknown identifier
    assert filled_host_statistics_compiler.get_stats('10.0.0.0:25000', 5.0) is None
    # test with correct identifier but unknown period
    assert filled_host_statistics_compiler.get_stats('10.0.0.1:25000', 1.0) is None
    # test with correct identifier and period
    instance = filled_host_statistics_compiler.get_stats('10.0.0.1:25000', 15.0)
    assert instance and instance.period == 15.0


def test_host_statistics_compiler_get_nb_cores(host_statistics_compiler):
    """ Test the HostStatisticsCompiler.get_nb_cores method """
    # fill some internal structures
    host_statistics_compiler.nb_cores = {'10.0.0.1:25000': 4}
    # test with unknown identifier
    assert host_statistics_compiler.get_nb_cores('10.0.0.0:25000') == 0
    # test with known identifier but data not received yet
    assert host_statistics_compiler.get_nb_cores('10.0.0.2:25000') == 0
    # test with known identifier and data available
    assert host_statistics_compiler.get_nb_cores('10.0.0.1:25000') == 4


def test_host_statistics_compiler_push_statistics(mocker, filled_host_statistics_compiler):
    """ Test the HostStatisticsCompiler.push_statistics method """
    mocker.patch('supvisors.statscompiler.HostStatisticsInstance.push_statistics',
                 return_value={'cpu': [1.0]})
    # test with unknown identifier: a new instance will be created
    host_stats = {'cpu': [1, 2, 3, 4, 5]}
    expected = [{'cpu': [1.0]}] * 3  # one per period
    assert filled_host_statistics_compiler.push_statistics('10.0.0.0:25000', host_stats) == expected
    assert filled_host_statistics_compiler.nb_cores == {'10.0.0.0:25000': 4,
                                                        '10.0.0.1:25000': 1, '10.0.0.2:25000': 1, '10.0.0.3:25000': 1,
                                                        '10.0.0.4:25000': 1, '10.0.0.5:25000': 1, '10.0.0.6:25000': 1}
    # test with known identifier
    filled_host_statistics_compiler.push_statistics('10.0.0.1:25000', host_stats)
    assert filled_host_statistics_compiler.nb_cores == {'10.0.0.0:25000': 4,
                                                        '10.0.0.1:25000': 4, '10.0.0.2:25000': 1, '10.0.0.3:25000': 1,
                                                        '10.0.0.4:25000': 1, '10.0.0.5:25000': 1, '10.0.0.6:25000': 1}


# Process Statistics part
def test_cpu_process_statistics():
    """ Test the CPU of the process between 2 dates. """
    stats = cpu_process_statistics(50, 20, 100)
    assert type(stats) is float
    assert pytest.approx(stats) == 30


@pytest.fixture
def proc_statistics_instance():
    # testing with period 12 and history depth 2
    return ProcStatisticsInstance(namespec='dummy_proc', identifier='10.0.0.1', pid=1234, period=12, depth=2)


def test_proc_statistics_instance_creation(proc_statistics_instance):
    """ Test the creation of ProcStatisticsInstance. """
    assert proc_statistics_instance.namespec == 'dummy_proc'
    assert proc_statistics_instance.identifier == '10.0.0.1'
    assert proc_statistics_instance.pid == 1234
    assert proc_statistics_instance.period == 12
    assert proc_statistics_instance.depth == 2
    assert proc_statistics_instance.ref_stats == {}
    assert proc_statistics_instance.ref_start_time == 0.0
    assert proc_statistics_instance.times == []
    assert proc_statistics_instance.cpu == []
    assert proc_statistics_instance.mem == []


def test_proc_statistics_instance_integrate(proc_statistics_instance):
    """ Test the ProcStatisticsInstance.integrate method. """
    proc_statistics_instance.ref_start_time = 800
    proc_statistics_instance.ref_stats = {'now': 1000,
                                          'proc_work': 0.15,
                                          'proc_memory': 1.85}
    last_stats = {'now': 1002,
                  'proc_work': 1.75,
                  'proc_memory': 1.9}
    proc_cpu, proc_mem, duration = proc_statistics_instance.integrate(last_stats)
    # check process stats
    assert proc_cpu == 80
    assert proc_mem == 1.9
    assert duration == 202


def test_proc_statistics_instance_push_statistics(mocker, proc_statistics_instance):
    """ Test the ProcStatisticsInstance.push_statistics method. """
    mocker.patch('time.monotonic', return_value=1234.56)
    mocked_integ = mocker.patch.object(proc_statistics_instance, 'integrate')
    # push first set of measures to become the first reference statistics
    stats1 = {'now': 1.0}
    mocked_integ.return_value = (5.2, 26.1, 1.0)
    # first push used as reference only
    result = proc_statistics_instance.push_statistics(stats1)
    assert result == {}
    assert not mocked_integ.called
    assert proc_statistics_instance.cpu == []
    assert proc_statistics_instance.mem == []
    assert proc_statistics_instance.times == []
    assert proc_statistics_instance.ref_stats == stats1
    assert proc_statistics_instance.ref_start_time == 1.0
    # from second push, integration is performed when period has passed
    # test when it didn't pass
    stats2 = {'now': 7.0}
    result = proc_statistics_instance.push_statistics(stats2)
    assert result == {}
    assert not mocked_integ.called
    assert proc_statistics_instance.cpu == []
    assert proc_statistics_instance.mem == []
    assert proc_statistics_instance.times == []
    assert proc_statistics_instance.ref_stats == stats1
    assert proc_statistics_instance.ref_start_time == 1.0
    # test when it has passed
    stats3 = {'now': 15.0}
    result = proc_statistics_instance.push_statistics(stats3)
    assert result == {'namespec': 'dummy_proc',
                      'identifier': '10.0.0.1',
                      'pid': 1234,
                      'now_monotonic': 1234.56,
                      'target_period': 12,
                      'period': (0.0, 14.0),
                      'cpu': 5.2,
                      'mem': 26.1}
    assert mocked_integ.call_args_list == [call(stats3)]
    assert proc_statistics_instance.cpu == [5.2]
    assert proc_statistics_instance.mem == [26.1]
    assert proc_statistics_instance.times == [1.0]
    assert proc_statistics_instance.ref_stats == stats3
    assert proc_statistics_instance.ref_start_time == 1.0
    mocked_integ.reset_mock()
    # test second push
    stats4 = {'now': 30.0}
    mocked_integ.return_value = (6.9, 13.7, 15.0)
    result = proc_statistics_instance.push_statistics(stats4)
    assert result == {'namespec': 'dummy_proc',
                      'identifier': '10.0.0.1',
                      'pid': 1234,
                      'now_monotonic': 1234.56,
                      'target_period': 12,
                      'period': (14.0, 29.0),
                      'cpu': 6.9,
                      'mem': 13.7}
    assert mocked_integ.call_args_list == [call(stats4)]
    assert proc_statistics_instance.cpu == [5.2, 6.9]
    assert proc_statistics_instance.mem == [26.1, 13.7]
    assert proc_statistics_instance.times == [1.0, 15.0]
    assert proc_statistics_instance.ref_stats == stats4
    assert proc_statistics_instance.ref_start_time == 1.0
    mocked_integ.reset_mock()
    # test third push for history rotation
    stats5 = {'now': 45.0}
    mocked_integ.return_value = (4.4, 8.9, 15.0)
    result = proc_statistics_instance.push_statistics(stats5)
    assert result == {'namespec': 'dummy_proc',
                      'identifier': '10.0.0.1',
                      'pid': 1234,
                      'now_monotonic': 1234.56,
                      'target_period': 12,
                      'period': (29.0, 44.0),
                      'cpu': 4.4,
                      'mem': 8.9}
    assert mocked_integ.call_args_list == [call(stats5)]
    assert proc_statistics_instance.cpu == [6.9, 4.4]
    assert proc_statistics_instance.mem == [13.7, 8.9]
    assert proc_statistics_instance.times == [15.0, 15.0]
    assert proc_statistics_instance.ref_stats == stats5
    assert proc_statistics_instance.ref_start_time == 1.0


@pytest.fixture
def proc_statistics_holder(supvisors_instance):
    return ProcStatisticsHolder('dummy_proc', supvisors_instance.options, supvisors_instance.logger)


def test_proc_statistics_holder_creation(supvisors_instance, proc_statistics_holder):
    """ Test the creation of ProcStatisticsHolder. """
    assert proc_statistics_holder.namespec == 'dummy_proc'
    assert proc_statistics_holder.options is supvisors_instance.options
    assert proc_statistics_holder.logger is supvisors_instance.logger
    assert proc_statistics_holder.instance_map == {}


def test_proc_statistics_holder_get_stats(proc_statistics_holder):
    """ Test the search method for process statistics. """
    # change values
    dummy_stats = ProcStatisticsInstance(identifier='10.0.0.1', period=5)
    dummy_stats.cpu = [2, 4, 8]
    proc_statistics_holder.instance_map = {'10.0.0.1': (os.getpid(), {5: dummy_stats})}
    # test find method with wrong identifier
    assert proc_statistics_holder.get_stats('10.0.0.2', 5, 1) is None
    # test find method with correct identifier and wrong period
    assert proc_statistics_holder.get_stats('10.0.0.1', 10, 1) is None
    # test find method with correct identifier and period and irix factor
    stats = proc_statistics_holder.get_stats('10.0.0.1', 5, 1)
    assert stats is not None
    assert stats is not dummy_stats
    assert stats.identifier == ''
    assert stats.period == 0
    assert stats.cpu == [2, 4, 8]
    # test find method with correct identifier and period and solaris factor
    stats = proc_statistics_holder.get_stats('10.0.0.1', 5, 4)
    assert stats is not None
    assert stats is not dummy_stats
    assert stats.identifier == ''
    assert stats.period == 0
    assert stats.cpu == [0.5, 1, 2]


def test_proc_statistics_holder_push_statistics(mocker, proc_statistics_holder):
    """ Test the storage of the process instant statistics. """
    mocked_instance = mocker.patch('supvisors.statscompiler.ProcStatisticsInstance',
                                   side_effect=lambda a, b, c, d, e: Mock(time_label=time.time(),
                                                                          namespec=a, identifier=b, pid=c,
                                                                          period=d, depth=e,
                                                                          **{'push_statistics.return_value': None}))
    # 1. test with running process not referenced yet
    proc_stats = {'pid': 118612}
    result = proc_statistics_holder.push_statistics('10.0.0.1', proc_stats)
    assert result == []
    assert list(proc_statistics_holder.instance_map.keys()) == ['10.0.0.1']
    # check host stats created
    pid, identifier_instances = proc_statistics_holder.instance_map['10.0.0.1']
    assert pid == 118612
    assert sorted(identifier_instances.keys()) == [5.0, 15.0, 60.0]
    for period, instance in identifier_instances.items():
        assert instance.namespec == 'dummy_proc'
        assert instance.identifier == '10.0.0.1'
        assert instance.pid == 118612
        assert instance.period == period
        assert instance.depth == 10
        assert instance.push_statistics.call_args_list == [call(proc_stats)]
        instance.push_statistics.reset_mock()
    # 2. test with running process not referenced yet on another host
    proc_stats = {'pid': 612}
    result = proc_statistics_holder.push_statistics('10.0.0.2', proc_stats)
    assert result == []
    assert sorted(proc_statistics_holder.instance_map.keys()) == ['10.0.0.1', '10.0.0.2']
    # check no change on first host stats
    pid, identifier_instances = proc_statistics_holder.instance_map['10.0.0.1']
    assert pid == 118612
    assert sorted(identifier_instances.keys()) == [5.0, 15.0, 60.0]
    for period, instance in identifier_instances.items():
        assert instance.namespec == 'dummy_proc'
        assert instance.identifier == '10.0.0.1'
        assert instance.pid == 118612
        assert instance.period == period
        assert instance.depth == 10
        assert not instance.push_statistics.called
    # check second host stats created
    pid, identifier_instances = proc_statistics_holder.instance_map['10.0.0.2']
    assert pid == 612
    assert sorted(identifier_instances.keys()) == [5.0, 15.0, 60.0]
    for period, instance in identifier_instances.items():
        assert instance.namespec == 'dummy_proc'
        assert instance.identifier == '10.0.0.2'
        assert instance.pid == 612
        assert instance.period == period
        assert instance.depth == 10
        assert instance.push_statistics.call_args_list == [call(proc_stats)]
        instance.push_statistics.reset_mock()
    # 3. test with running process with a different pid on existing host
    mocked_instance.side_effect = lambda a, b, c, d, e: Mock(time_label=time.time(),
                                                             namespec=a, identifier=b, pid=c, period=d, depth=e,
                                                             **{'push_statistics.return_value': f'{b}_{d}'})
    proc_stats = {'pid': 18612}
    result = proc_statistics_holder.push_statistics('10.0.0.1', proc_stats)
    assert result == ['10.0.0.1_5.0', '10.0.0.1_15.0', '10.0.0.1_60.0']
    assert sorted(proc_statistics_holder.instance_map.keys()) == ['10.0.0.1', '10.0.0.2']
    # check host instances are replaced
    pid, identifier_instances = proc_statistics_holder.instance_map['10.0.0.1']
    assert pid == 18612
    assert sorted(identifier_instances.keys()) == [5.0, 15.0, 60.0]
    for period, instance in identifier_instances.items():
        assert instance.namespec == 'dummy_proc'
        assert instance.identifier == '10.0.0.1'
        assert instance.pid == 18612
        assert instance.period == period
        assert instance.depth == 10
        assert instance.push_statistics.call_args_list == [call(proc_stats)]
        instance.push_statistics.reset_mock()
    # test no change on second host stats
    pid, identifier_instances = proc_statistics_holder.instance_map['10.0.0.2']
    assert pid == 612
    assert sorted(identifier_instances.keys()) == [5.0, 15.0, 60.0]
    for period, instance in identifier_instances.items():
        assert instance.namespec == 'dummy_proc'
        assert instance.identifier == '10.0.0.2'
        assert instance.pid == 612
        assert instance.period == period
        assert instance.depth == 10
        assert not instance.push_statistics.called
    # 4. test with stopped process. instances are deleted
    proc_stats = {'pid': 0}
    result = proc_statistics_holder.push_statistics('10.0.0.1', proc_stats)
    assert result == []
    assert list(proc_statistics_holder.instance_map.keys()) == ['10.0.0.2']
    # test no change on second host stats
    pid, identifier_instances = proc_statistics_holder.instance_map['10.0.0.2']
    assert pid == 612
    assert sorted(identifier_instances.keys()) == [5.0, 15.0, 60.0]
    for period, instance in identifier_instances.items():
        assert instance.namespec == 'dummy_proc'
        assert instance.identifier == '10.0.0.2'
        assert instance.pid == 612
        assert instance.period == period
        assert instance.depth == 10
        assert not instance.push_statistics.called


@pytest.fixture
def proc_statistics_compiler(supvisors_instance):
    return ProcStatisticsCompiler(supvisors_instance.options, supvisors_instance.logger)


def test_proc_statistics_compiler_creation(supvisors_instance, proc_statistics_compiler):
    """ Test the creation of ProcStatisticsCompiler. """
    assert proc_statistics_compiler.options is supvisors_instance.options
    assert proc_statistics_compiler.logger is supvisors_instance.logger
    assert proc_statistics_compiler.holder_map == {}
    assert proc_statistics_compiler.nb_cores == {}


def test_proc_statistics_compiler_get_stats(mocker, supvisors_instance, proc_statistics_compiler):
    """ Test the ProcStatisticsCompiler.get_stats method """
    mocked_stats = mocker.patch('supvisors.statscompiler.ProcStatisticsHolder.get_stats')
    # test on unknown namespec
    assert proc_statistics_compiler.get_stats('dummy_proc', '10.0.0.1', 12.5) is None
    assert not mocked_stats.called
    # fill some data
    mocked_holder = Mock(**{'get_stats.return_value': 'some stats'})
    proc_statistics_compiler.holder_map['dummy_proc'] = mocked_holder
    # test on known namespec and irix mode
    assert proc_statistics_compiler.get_stats('dummy_proc', '10.0.0.1', 12.5) == 'some stats'
    assert mocked_holder.get_stats.call_args_list == [call('10.0.0.1', 12.5, 1)]
    mocked_holder.get_stats.reset_mock()
    # test on known namespec and solaris mode (nb_cores not set)
    supvisors_instance.options.stats_irix_mode = False
    assert proc_statistics_compiler.get_stats('dummy_proc', '10.0.0.1', 12.5) == 'some stats'
    assert mocked_holder.get_stats.call_args_list == [call('10.0.0.1', 12.5, 1)]
    mocked_holder.get_stats.reset_mock()
    # test on known namespec and solaris mode (nb_cores set)
    proc_statistics_compiler.nb_cores['10.0.0.1'] = 4
    assert proc_statistics_compiler.get_stats('dummy_proc', '10.0.0.1', 12.5) == 'some stats'
    assert mocked_holder.get_stats.call_args_list == [call('10.0.0.1', 12.5, 4)]


def test_proc_statistics_compiler_get_nb_cores(proc_statistics_compiler):
    """ Test the ProcStatisticsCompiler.get_nb_cores method """
    # test on unknown identifier
    assert proc_statistics_compiler.get_nb_cores('10.0.0.1') == 0
    # fill some data
    proc_statistics_compiler.nb_cores['10.0.0.1'] = 4
    # test on known namespec
    assert proc_statistics_compiler.get_nb_cores('10.0.0.1') == 4


def test_proc_statistics_compiler_push_statistics(mocker, proc_statistics_compiler):
    """ Test the ProcStatisticsCompiler.push_statistics method """
    mocked_holder = Mock(instance_map=True, **{'push_statistics.return_value': ['dummy_proc stats']})
    mocked_holder_constr = mocker.patch('supvisors.statscompiler.ProcStatisticsHolder', return_value=mocked_holder)
    process_stats = {'namespec': 'dummy_proc', 'pid': 0}
    # 1. test with non-existing holder and 0 pid
    result = proc_statistics_compiler.push_statistics('10.0.0.1', process_stats)
    assert result == []
    assert proc_statistics_compiler.nb_cores == {}
    assert proc_statistics_compiler.holder_map == {}
    assert not mocked_holder_constr.called
    assert not mocked_holder.push_statistics.called
    # 2. test with non-existing holder and pid > 0
    process_stats['pid'] = 1234
    result = proc_statistics_compiler.push_statistics('10.0.0.1', process_stats)
    assert result == ['dummy_proc stats']
    assert proc_statistics_compiler.nb_cores == {}
    assert list(proc_statistics_compiler.holder_map.keys()) == ['dummy_proc']
    assert mocked_holder_constr.call_args_list == [call('dummy_proc', proc_statistics_compiler.options,
                                                        proc_statistics_compiler.logger)]
    assert mocked_holder.push_statistics.call_args_list == [call('10.0.0.1', process_stats)]
    mocked_holder_constr.reset_mock()
    mocked_holder.push_statistics.reset_mock()
    # 3. test with existing holder and pid > 0
    process_stats['nb_cores'] = 4
    result = proc_statistics_compiler.push_statistics('10.0.0.1', process_stats)
    assert result == ['dummy_proc stats']
    assert proc_statistics_compiler.nb_cores == {'10.0.0.1': 4}
    assert list(proc_statistics_compiler.holder_map.keys()) == ['dummy_proc']
    assert not mocked_holder_constr.called
    assert mocked_holder.push_statistics.call_args_list == [call('10.0.0.1', process_stats)]
    mocked_holder.push_statistics.reset_mock()
    # 4. test with existing holder and 0 pid
    process_stats['pid'] = 0
    process_stats['nb_cores'] = 6
    result = proc_statistics_compiler.push_statistics('10.0.0.1', process_stats)
    assert result == ['dummy_proc stats']
    assert proc_statistics_compiler.nb_cores == {'10.0.0.1': 6}
    assert list(proc_statistics_compiler.holder_map.keys()) == ['dummy_proc']
    assert not mocked_holder_constr.called
    assert mocked_holder.push_statistics.call_args_list == [call('10.0.0.1', process_stats)]
    mocked_holder.push_statistics.reset_mock()
    # test case when instance_map has been removed
    mocked_holder.instance_map = {}
    result = proc_statistics_compiler.push_statistics('10.0.0.1', process_stats)
    assert result == ['dummy_proc stats']
    assert proc_statistics_compiler.nb_cores == {'10.0.0.1': 6}
    assert proc_statistics_compiler.holder_map == {}
    assert not mocked_holder_constr.called
    assert mocked_holder.push_statistics.call_args_list == [call('10.0.0.1', process_stats)]
