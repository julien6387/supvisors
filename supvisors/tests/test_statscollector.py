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

import queue
from threading import Thread
from unittest.mock import call, Mock

import pytest

from supvisors.statscollector import *

pytest.importorskip('psutil', reason='cannot test as optional psutil is not installed')


@pytest.fixture
def queues():
    pid_queue = mp.Queue()
    stats_queue = mp.Queue()
    return pid_queue, stats_queue


@pytest.fixture
def collected_processes(queues):
    return CollectedProcesses(queues[1], 5, os.getpid())


def test_instant_cpu_statistics():
    """ Test the instant CPU statistics. """
    # measurement at t0
    work1, idle1 = instant_cpu_statistics()
    # do some work
    sleep(1)
    # measurement at t0+1
    work2, idle2 = instant_cpu_statistics()
    # jiffies should be increasing
    assert work2 >= work1
    assert idle2 >= idle1


def test_instant_all_cpu_statistics():
    """ Test the instant CPU statistics. """
    stats = instant_all_cpu_statistics()
    # test number of results (number of cores + average)
    assert len(stats) == mp.cpu_count() + 1
    # test average value
    total_work = total_idle = 0
    for cpu in stats[1:]:
        assert len(cpu) == 2
        work, idle = cpu
        total_work += work
        total_idle += idle
    assert pytest.approx(total_work / mp.cpu_count()) == stats[0][0]
    assert pytest.approx(total_idle / mp.cpu_count()) == stats[0][1]


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
    # test that Supvisors works on a subset
    interfaces = {intf.strip().split(':')[0] for intf in contents}
    assert set(stats.keys()).issubset(interfaces)
    assert 'lo' in stats.keys()
    # test that values are pairs
    for intf, io_bytes in stats.items():
        assert len(io_bytes) == 2
        for value in io_bytes:
            assert type(value) is int
    # for loopback address, recv bytes equals sent bytes
    assert stats['lo'][0] == stats['lo'][1]


def test_instant_host_statistics_exception(mocker):
    """ Test the instant host statistics when OSError has been raised by psutil. """
    mocker.patch('supvisors.statscollector.instant_all_cpu_statistics', side_effect=OSError)
    assert instant_host_statistics() == {}


def test_instant_host_statistics():
    """ Test the instant host statistics. """
    stats = instant_host_statistics()
    # check result
    assert len(stats) == 4
    #  check time (current is greater)
    assert time() > stats['now']
    # check cpu jiffies
    cpu_stats = stats['cpu']
    assert len(cpu_stats) == mp.cpu_count() + 1
    for cpu in cpu_stats:
        assert len(cpu) == 2
        for value in cpu:
            assert type(value) is float
    # check memory
    mem_stats = stats['mem']
    assert type(mem_stats) is float
    assert mem_stats >= 0
    assert mem_stats < 100
    # check io
    io_stats = stats['io']
    for intf, io_bytes in io_stats.items():
        assert type(intf) is str
        assert len(io_bytes) == 2
        for value in io_bytes:
            assert type(value) is int


def test_instant_process_statistics(mocker):
    """ Test the instant process statistics without children. """
    this_process = psutil.Process(os.getpid())
    # check with existing PID and no children requested
    work, memory = instant_process_statistics(this_process, False)
    # test that a pair is returned with values in [0;100]
    # test cpu value
    assert type(work) is float
    assert work >= 0
    assert work <= 100
    # test mem value
    assert type(memory) is float
    assert memory >= 0
    assert memory <= 100
    # check with exception PID
    mocker.patch.object(this_process, 'as_dict', side_effect=psutil.NoSuchProcess(os.getpid()))
    assert instant_process_statistics(this_process, False) is None
    # check with exception OSError
    mocker.patch.object(this_process, 'as_dict', side_effect=OSError)
    assert instant_process_statistics(this_process, False) == ()


def test_instant_process_statistics_children(mocker):
    """ Test the instant process statistics with children requested. """
    this_process = psutil.Process()
    this_process_as_child = psutil.Process()
    mocked_process = mocker.patch('psutil.Process.children', return_value=[this_process_as_child])
    # check with existing PID and children requested
    work, memory = instant_process_statistics(this_process)
    assert mocked_process.called
    # test that a pair is returned with values in [0;100]
    # test cpu value
    assert type(work) is float
    assert work >= 0
    assert work <= 100
    # test mem value
    assert type(memory) is float
    assert memory >= 0
    assert memory <= 100
    # check with existing PID, children requested but children dead
    mocker.patch.object(this_process_as_child, 'as_dict', side_effect=psutil.NoSuchProcess(os.getpid()))
    work, memory = instant_process_statistics(this_process)
    assert mocked_process.called
    # test that a pair is returned with values in [0;100]
    # test cpu value
    assert type(work) is float
    assert work >= 0
    assert work <= 100
    # test mem value
    assert type(memory) is float
    assert memory >= 0
    assert memory <= 100


def test_collected_processes_creation(queues, collected_processes):
    """ Test the CollectedProcesses creation. """
    assert collected_processes.stats_queue is queues[1]
    assert collected_processes.period == 5
    assert collected_processes.processes == []
    assert collected_processes.nb_cores == mp.cpu_count()
    assert sorted(collected_processes.supervisor_process.keys()) == ['collector', 'last', 'supervisor']
    assert collected_processes.supervisor_process['last'] == 0
    assert collected_processes.supervisor_process['supervisor'].pid == os.getpid()
    assert collected_processes.supervisor_process['collector'].pid == os.getpid()


def test_collected_processes_update_process_list(mocker, queues, collected_processes):
    """ Test the CollectedProcesses.update_process_list method. """
    mocker.patch('supvisors.statscollector.time', return_value=7777)
    mocked_process = mocker.patch.object(psutil, 'Process', side_effect=psutil.NoSuchProcess(1234))
    # 1. not found and process does not exist
    collected_processes.update_process_list('dummy_proc', 1234)
    assert mocked_process.call_args_list == [call(1234)]
    with pytest.raises(queue.Empty):
        assert queues[1].get(timeout=0.5)
    assert collected_processes.processes == []
    mocked_process.reset_mock()
    # 2. not found and psutil raises an OSError
    mocked_process.side_effect = OSError
    collected_processes.update_process_list('dummy_proc', 1234)
    assert mocked_process.call_args_list == [call(1234)]
    with pytest.raises(queue.Empty):
        assert queues[1].get(timeout=0.5)
    assert collected_processes.processes == []
    mocked_process.reset_mock()
    # 3. not found but process exists
    mocked_process.side_effect = lambda x: Mock(pid=x)
    collected_processes.update_process_list('dummy_proc', 1234)
    assert mocked_process.call_args_list == [call(1234)]
    with pytest.raises(queue.Empty):
        assert queues[1].get(timeout=0.5)
    assert len(collected_processes.processes) == 1
    process = collected_processes.processes[0]
    assert process['namespec'] == 'dummy_proc'
    assert process['last'] == 0
    assert process['process'].pid == 1234
    mocked_process.reset_mock()
    # 4. update with same pid
    collected_processes.update_process_list('dummy_proc', 1234)
    assert not mocked_process.called
    with pytest.raises(queue.Empty):
        assert queues[1].get(timeout=0.5)
    assert len(collected_processes.processes) == 1
    process = collected_processes.processes[0]
    assert process['namespec'] == 'dummy_proc'
    assert process['last'] == 0
    assert process['process'].pid == 1234
    mocked_process.reset_mock()
    # 5. update with a different positive pid
    collected_processes.update_process_list('dummy_proc', 4321)
    assert mocked_process.call_args_list == [call(4321)]
    assert queues[1].get(timeout=0.5) == {'namespec': 'dummy_proc', 'pid': 0, 'now': 7777}
    assert len(collected_processes.processes) == 1
    process = collected_processes.processes[0]
    assert process['namespec'] == 'dummy_proc'
    assert process['last'] == 0
    assert process['process'].pid == 4321
    mocked_process.reset_mock()
    # 6. update with a different zero pid
    collected_processes.update_process_list('dummy_proc', 0)
    assert not mocked_process.called
    assert queues[1].get(timeout=0.5) == {'namespec': 'dummy_proc', 'pid': 0, 'now': 7777}
    assert collected_processes.processes == []


def test_collected_processes_collect_supervisor(mocker, queues, collected_processes):
    """ Test the CollectedProcesses.collect_supervisor method. """
    mocked_time = mocker.patch('supvisors.statscollector.time', return_value=4)
    # 1. with not enough time to trigger the collection
    collected_processes.collect_supervisor()
    with pytest.raises(queue.Empty):
        assert queues[1].get(timeout=0.5)
    assert collected_processes.supervisor_process['last'] == 0
    # 2. with enough time to trigger the collection
    mocked_time.return_value = 5
    collected_processes.collect_supervisor()
    supervisor_stats = queues[1].get(timeout=0.5)
    assert sorted(supervisor_stats.keys()) == ['cpu', 'namespec', 'nb_cores', 'now', 'pid', 'proc_memory', 'proc_work']
    assert supervisor_stats['namespec'] == 'supervisord'
    assert supervisor_stats['nb_cores'] == mp.cpu_count()
    assert supervisor_stats['now'] == 5
    assert supervisor_stats['pid'] == os.getpid()
    assert 0 < supervisor_stats['proc_memory'] < 100
    assert supervisor_stats['proc_work'] > 0
    assert len(supervisor_stats['cpu']) == 2
    assert collected_processes.supervisor_process['last'] == 5
    # 3. with no stats provided (OSError)
    mocked_time.return_value = 10
    mocker.patch('supvisors.statscollector.instant_process_statistics', return_value=())
    collected_processes.collect_supervisor()
    with pytest.raises(queue.Empty):
        assert queues[1].get(timeout=0.5)
    assert collected_processes.supervisor_process['last'] == 10


def test_collected_processes_collect_recent_process(mocker, queues, collected_processes):
    """ Test the CollectedProcesses.collect_recent_process method. """
    mocked_time = mocker.patch('supvisors.statscollector.time', return_value=22)
    # first try with no process to collect
    collected_processes.collect_recent_process()
    with pytest.raises(queue.Empty):
        assert queues[1].get(timeout=0.5)
    # second try with processes but not enough time to trigger the collection
    process = psutil.Process()
    collected_processes.processes = [{'namespec': 'dummy_1', 'last': 21, 'process': process},
                                     {'namespec': 'dummy_2', 'last': 18, 'process': process}]
    collected_processes.collect_recent_process()
    with pytest.raises(queue.Empty):
        assert queues[1].get(timeout=0.5)
    assert collected_processes.processes == [{'namespec': 'dummy_1', 'last': 21, 'process': process},
                                             {'namespec': 'dummy_2', 'last': 18, 'process': process}]
    # third try with enough time to trigger the collection on the first element of the list
    mocked_time.return_value = 24
    collected_processes.collect_recent_process()
    supervisor_stats = queues[1].get(timeout=0.5)
    assert sorted(supervisor_stats.keys()) == ['cpu', 'namespec', 'now', 'pid', 'proc_memory', 'proc_work']
    assert supervisor_stats['namespec'] == 'dummy_2'
    assert supervisor_stats['now'] == 24
    assert supervisor_stats['pid'] == os.getpid()
    assert 0 < supervisor_stats['proc_memory'] < 100
    assert supervisor_stats['proc_work'] > 0
    assert len(supervisor_stats['cpu']) == 2
    # check that the list has rotated
    assert collected_processes.processes == [{'namespec': 'dummy_2', 'last': 24, 'process': process},
                                             {'namespec': 'dummy_1', 'last': 21, 'process': process}]
    # fourth try with enough time to trigger the collection on the first element of the list
    # but with stopped process
    mocker.patch('supvisors.statscollector.instant_process_statistics', return_value=None)
    mocked_time.return_value = 27
    collected_processes.collect_recent_process()
    supervisor_stats = queues[1].get(timeout=0.5)
    assert sorted(supervisor_stats.keys()) == ['namespec', 'now', 'pid']
    assert supervisor_stats['namespec'] == 'dummy_1'
    assert supervisor_stats['now'] == 27
    assert supervisor_stats['pid'] == 0
    # check that dummy_1 has been removed from the list
    assert collected_processes.processes == [{'namespec': 'dummy_2', 'last': 24, 'process': process}]


def test_collect_process_statistics(mocker, queues):
    """ Test the collect_process_statistics main loop of the process collector. """
    mocked_processes = Mock(spec=CollectedProcesses)
    mocked_processes.collect_recent_process.return_value = False
    mocked_constructor = mocker.patch('supvisors.statscollector.CollectedProcesses', return_value=mocked_processes)
    # pre-fill the sending queue
    queues[0].put((StatsMsgType.ALIVE, None))
    queues[0].put((StatsMsgType.PID, ('dummy_1', 123)))
    queues[0].put((StatsMsgType.PID, ('dummy_2', 456)))
    queues[0].put((StatsMsgType.ALIVE, None))

    def terminate():
        sleep(1)
        queues[0].put((StatsMsgType.STOP, None))
    Thread(target=terminate).start()
    # trigger the main loop
    collect_process_statistics(queues[0], queues[1], 5, 777)
    assert mocked_constructor.call_args_list == [call(queues[1], 5, 777)]
    assert mocked_processes.update_process_list.call_args_list == [call('dummy_1', 123), call('dummy_2', 456)]
    # due to the multi-threading aspect, impossible to predict the exact number of calls
    assert mocked_processes.collect_supervisor.call_count > 1
    assert mocked_processes.collect_recent_process.call_count > 1


def test_collect_process_statistics_main_killed(mocker, queues):
    """ Test the exit of the collect_process_statistics main loop of the process collector
    when no heartbeat is received. """
    mocked_processes = Mock(spec=CollectedProcesses)
    mocked_processes.collect_recent_process.return_value = False
    mocker.patch('supvisors.statscollector.CollectedProcesses', return_value=mocked_processes)
    # trigger the main loop and test that it exits by itself after 15 seconds without heartbeat
    start_time = time()
    collect_process_statistics(queues[0], queues[1], 5, 777)
    assert time() - start_time > HEARTBEAT_TIMEOUT


def test_process_statistics_collector(mocker, supvisors):
    """ Test the ProcessStatisticsCollector class. """
    mocked_process = Mock(spec=mp.Process, exitcode=None)
    mocked_creation = mocker.patch('multiprocessing.Process', return_value=mocked_process)
    # test creation
    collector = ProcessStatisticsCollector(10, supvisors.logger)
    assert collector.period == 10
    assert type(collector.pid_queue) is mp.queues.Queue
    assert type(collector.stats_queue) is mp.queues.Queue
    assert collector.process is None
    # test thread starting
    collector.start()
    assert mocked_creation.call_args_list == [call(target=collect_process_statistics,
                                                   args=(collector.pid_queue, collector.stats_queue, 10, os.getpid()),
                                                   daemon=True)]
    assert mocked_process.start.call_args_list == [call()]
    # test alive
    collector.alive()
    assert collector.pid_queue.get(timeout=1.0) == (StatsMsgType.ALIVE, None)
    # test send_pid
    collector.send_pid('dummy_process', 1234)
    assert collector.pid_queue.get(timeout=1.0) == (StatsMsgType.PID, ('dummy_process', 1234))
    # test get_process_stats
    assert collector.get_process_stats() == []
    proc_stats = {'namespec': 'dummy_process',
                  'pid': 1234,
                  'now': 4321,
                  'cpu': 'cpu_stats',
                  'proc_work': 12,
                  'proc_memory': 5}
    collector.stats_queue.put(proc_stats)
    sleep(0.5)
    assert collector.get_process_stats() == [proc_stats]
    # test thread stopping
    collector.stop()
    assert collector.pid_queue.get(timeout=1.0) == (StatsMsgType.STOP, None)
    assert mocked_process.terminate.call_args_list == [call()]
