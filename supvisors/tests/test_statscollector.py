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

from threading import Thread
from unittest.mock import call, Mock

import pytest

from supvisors.statscollector import *

pytest.importorskip('psutil', reason='cannot test as optional psutil is not installed')

PipeConnection = Tuple[mp.connection.Connection, mp.connection.Connection]


@pytest.fixture
def pipes() -> Tuple[PipeConnection, PipeConnection, PipeConnection]:
    cmd_pipe = mp.Pipe(False)
    host_stats_pipe = mp.Pipe(False)  # used to send/receive host statistics
    proc_stats_pipe = mp.Pipe(False)  # used to send/receive process statistics
    return cmd_pipe, host_stats_pipe, proc_stats_pipe


@pytest.fixture
def host_collector(pipes) -> HostStatisticsCollector:
    return HostStatisticsCollector(pipes[1][1], 10, False)


@pytest.fixture
def proc_collector(pipes) -> ProcessStatisticsCollector:
    return ProcessStatisticsCollector(pipes[2][1], 5, False, os.getpid())


def test_instant_all_cpu_statistics(mocker):
    """ Test the instant CPU statistics. """
    # psutil scputimes is platform-dependent, so Mock needed to pass GitHub actions
    # use only integers to avoid comparison on floating values
    cpu = [Mock(user=65919, nice=19, system=13700, idle=766409, iowait=157, irq=2131,
                softirq=873, steal=0, guest=0, guest_nice=0),
           Mock(user=67098, nice=32, system=14033, idle=764931, iowait=161, irq=1691,
                softirq=290, steal=0, guest=0, guest_nice=0),
           Mock(user=66759, nice=29, system=14034, idle=764897, iowait=206, irq=1990,
                softirq=288, steal=0, guest=0, guest_nice=0),
           Mock(user=66319, nice=31, system=13768, idle=766044, iowait=155, irq=1606,
                softirq=484, steal=0, guest=0, guest_nice=0)]
    mocker.patch('psutil.cpu_times', return_value=cpu)
    stats = instant_all_cpu_statistics()
    assert stats == [(82773.5, 765740.0),
                     (82642, 766566),
                     (83144, 765092),
                     (83100, 765103),
                     (82208, 766199)]


def test_instant_memory_statistics(mocker):
    """ Test the instant memory statistics. """
    # psutil svmem is platform-dependent, so Mock needed to pass GitHub actions
    mem = Mock(total=16481181696, available=9487249408, percent=42.4, used=6530781184, free=541007872,
               active=2982461440, inactive=11854032896, buffers=3313664, cached=9406078976, shared=117649408,
               slab=643690496)
    mocker.patch('psutil.virtual_memory', return_value=mem)
    stats = instant_memory_statistics()
    assert stats == 42.4


def test_instant_net_io_statistics(mocker):
    """ Test the instant network I/O statistics. """
    # psutil snicstats is platform-dependent, so Mock needed to pass GitHub actions
    if_stats = {'lo': Mock(isup=True, duplex=0, speed=0, mtu=65536),
                'ens33': Mock(isup=True, duplex=2, speed=1000, mtu=1500),
                'virbr0': Mock(isup=False, duplex=0, speed=65535, mtu=1500)}
    # psutil snetio is platform-dependent, so Mock needed to pass GitHub actions
    io_counters = {'lo': Mock(bytes_sent=5278203410, bytes_recv=5278203410,
                              packets_sent=10515881, packets_recv=10515881,
                              errin=0, errout=0, dropin=0, dropout=0),
                   'ens33': Mock(bytes_sent=2661175503, bytes_recv=3224236577,
                                 packets_sent=6483142, packets_recv=7750813,
                                 errin=0, errout=0, dropin=55057, dropout=0),
                   'virbr0': Mock(bytes_sent=0, bytes_recv=0,
                                  packets_sent=0, packets_recv=0,
                                  errin=0, errout=0, dropin=0, dropout=0)}
    mocker.patch('psutil.net_if_stats', return_value=if_stats)
    mocker.patch('psutil.net_io_counters', return_value=io_counters)
    stats = instant_net_io_statistics()
    assert stats == {'ens33': (3224236577, 2661175503), 'lo': (5278203410, 5278203410)}


def test_instant_disk_io_statistics(mocker):
    """ Test the instant disk I/O statistics. """
    # psutil sdiskio is platform-dependent, so Mock needed to pass GitHub actions
    io_counters = {'sda': Mock(read_count=124912, write_count=2988960, read_bytes=5147740160,
                               write_bytes=65686229504, read_time=2705493, write_time=7443910,
                               read_merged_count=558, write_merged_count=203120, busy_time=3683152),
                   'sda1': Mock(read_count=180, write_count=56, read_bytes=18583552, write_bytes=29582848,
                                read_time=51, write_time=11996, read_merged_count=0, write_merged_count=8,
                                busy_time=1097),
                   'sda2': Mock(read_count=124676, write_count=2988904, read_bytes=5127436288,
                                write_bytes=65656646656, read_time=2705435, write_time=7431913,
                                read_merged_count=558, write_merged_count=203112, busy_time=3682449)}
    mocker.patch('psutil.disk_io_counters', return_value=io_counters)
    stats = instant_disk_io_statistics()
    assert stats == {'sda': (5147740160, 65686229504),
                     'sda1': (18583552, 29582848),
                     'sda2': (5127436288, 65656646656)}


def test_instant_disk_usage_statistics(mocker):
    """ Test the instant disk usage statistics. """
    # psutil sdiskpart is platform-dependent, so Mock needed to pass GitHub actions
    partitions = [Mock(device='/dev/mapper/rl_rocky51-root', mountpoint='/', fstype='xfs',
                       opts='rw,seclabel,relatime,attr2,inode64,logbufs=8,logbsize=32k,noquota',
                       maxfile=255, maxpath=4096),
                  Mock(device='/dev/sda1', mountpoint='/boot', fstype='xfs',
                       opts='rw,seclabel,relatime,attr2,inode64,logbufs=8,logbsize=32k,noquota',
                       maxfile=255, maxpath=4096),
                  Mock(device='/dev/sdb', mountpoint='/mnt', fstype='xfs',
                       opts='rw,seclabel,relatime,attr2,inode64,logbufs=8,logbsize=32k,noquota',
                       maxfile=255, maxpath=4096)]
    mocker.patch('psutil.disk_partitions', return_value=partitions)
    # psutil sdiskusage is platform-dependent, so Mock needed to pass GitHub actions
    usage = {'/': Mock(total=37625499648, used=22722027520, free=14903472128, percent=60.4),
             '/boot': Mock(total=1063256064, used=453169152, free=610086912, percent=42.6)}

    def get_usage(x):
        if x in usage:
            return usage[x]
        raise PermissionError
    mocker.patch('psutil.disk_usage', side_effect=get_usage)
    stats = instant_disk_usage_statistics()
    assert stats == {'/': 60.4, '/boot': 42.6}


def test_local_node_info(mocker):
    """ Test the LocalNodeInfo class method. """
    # patch psutil functions
    mocker.patch('psutil.cpu_count', side_effect=lambda logical=True: 8 if logical else 4)
    mocker.patch('psutil.cpu_freq', return_value=Mock(current=3000.01))
    mocked_ram = mocker.patch('psutil.virtual_memory', return_value=Mock(total=16123456789))
    # test call
    info = LocalNodeInfo()
    assert info.nb_core_physical == 4
    assert info.nb_core_logical == 8
    assert info.frequency == '3000 MHz'
    assert info.physical_memory == '15.02 GiB'
    # test call with less RAM (even if it is very unlikely)
    mocked_ram.return_value = Mock(total=16123456)
    info = LocalNodeInfo()
    assert info.nb_core_physical == 4
    assert info.nb_core_logical == 8
    assert info.frequency == '3000 MHz'
    assert info.physical_memory == '15.38 MiB'
    # test again with less RAM (even if it is VERY unlikely)
    mocked_ram.return_value = Mock(total=16123)
    info = LocalNodeInfo()
    assert info.nb_core_physical == 4
    assert info.nb_core_logical == 8
    assert info.frequency == '3000 MHz'
    assert info.physical_memory == '15.75 KiB'


def test_statistics_collector():
    """ Test the StatisticsCollector base class. """
    cmd_recv, cmd_send = mp.Pipe(False)  # used to /receive commands, pids and program names
    collector = StatisticsCollector(cmd_send, 28, False)
    assert collector.stats_conn is cmd_send
    assert collector.period == 28
    assert not collector.enabled
    assert not cmd_recv.poll(timeout=0.5)
    # check queue
    collector._post('dummy')
    assert cmd_recv.poll()
    assert cmd_recv.recv() == 'dummy'


def test_host_statistics_collector_creation(pipes, host_collector):
    """ Test the creation of a HostStatisticsCollector instance. """
    assert isinstance(host_collector, StatisticsCollector)
    assert host_collector.stats_conn is pipes[1][1]
    assert host_collector.period == 10
    assert not host_collector.enabled
    assert host_collector.last_stats_time == 0.0


def test_host_statistics_collector_exception(mocker, pipes, host_collector):
    """ Test the host statistics collector when OSError has been raised by psutil. """
    mocker.patch('supvisors.statscollector.instant_all_cpu_statistics', side_effect=OSError)
    assert not pipes[1][0].poll(timeout=0.5)
    for enabled in [True, False]:
        host_collector.enabled = enabled
        host_collector.collect_host_statistics()
        assert not pipes[1][0].poll(timeout=0.5)


def test_host_statistics_collector_disabled(pipes, host_collector):
    """ Test the host statistics collector when collection is disabled. """
    assert not host_collector.enabled
    assert not pipes[1][0].poll(timeout=0.5)
    host_collector.collect_host_statistics()
    assert not pipes[1][0].poll(timeout=0.5)


def test_host_statistics_collector_enabled(mocker, pipes, host_collector):
    """ Test the instant host statistics. """
    cpu = [(82776.1, 765740.7), (82643.8, 766566.8), (83146.3, 765092.5), (83103.9, 765103.7), (82210.53, 766199.8)]
    mem = 42.4
    net_io = {'ens33': (3224236577, 2661175503), 'lo': (5278203410, 5278203410)}
    disk_io = {'sda': (5147740160, 65686229504), 'sda1': (18583552, 29582848), 'sda2': (5127436288, 65656646656)}
    disk_usage = {'/': 60.4, '/boot': 42.6}
    mocker.patch('supvisors.statscollector.instant_all_cpu_statistics', return_value=cpu)
    mocker.patch('supvisors.statscollector.instant_memory_statistics', return_value=mem)
    mocker.patch('supvisors.statscollector.instant_net_io_statistics', return_value=net_io)
    mocker.patch('supvisors.statscollector.instant_disk_io_statistics', return_value=disk_io)
    mocker.patch('supvisors.statscollector.instant_disk_usage_statistics', return_value=disk_usage)
    # test call
    ref_time = time.monotonic()
    assert not pipes[1][0].poll(timeout=0.5)
    host_collector.enabled = True
    host_collector.collect_host_statistics()
    assert pipes[1][0].poll(timeout=0.5)
    stats = pipes[1][0].recv()
    # check result
    assert sorted(stats.keys()) == ['cpu', 'disk_io', 'disk_usage', 'mem', 'net_io', 'now']
    assert ref_time <= stats['now'] <= time.monotonic()
    assert stats['cpu'] == cpu
    assert stats['mem'] == mem
    assert stats['net_io'] == net_io
    assert stats['disk_io'] == disk_io
    assert stats['disk_usage'] == disk_usage


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


def test_process_statistics_collector_creation(pipes, proc_collector):
    """ Test the ProcessStatisticsCollector creation. """
    assert proc_collector.stats_conn is pipes[2][1]
    assert proc_collector.period == 5
    assert not proc_collector.enabled
    assert proc_collector.processes == []
    assert NB_PROCESSORS == mp.cpu_count()
    assert sorted(proc_collector.supervisor_process.keys()) == ['collector', 'last', 'supervisor']
    assert proc_collector.supervisor_process['last'] == 0
    assert proc_collector.supervisor_process['supervisor'].pid == os.getpid()
    assert proc_collector.supervisor_process['collector'].pid == os.getpid()


def test_process_statistics_collector_update_process_list(mocker, pipes, proc_collector):
    """ Test the ProcessStatisticsCollector.update_process_list method. """
    # WARN: queue timeout uses time.monotonic so cannot use a time patch here
    mocked_process = mocker.patch.object(psutil, 'Process', side_effect=psutil.NoSuchProcess(1234))
    # 1. not found and process does not exist
    proc_collector.update_process_list('dummy_proc', 1234)
    assert mocked_process.call_args_list == [call(1234)]
    assert not pipes[2][0].poll(timeout=0.5)
    assert proc_collector.processes == []
    mocked_process.reset_mock()
    # 2. not found and psutil raises an OSError
    mocked_process.side_effect = OSError
    proc_collector.update_process_list('dummy_proc', 1234)
    assert mocked_process.call_args_list == [call(1234)]
    assert not pipes[2][0].poll(timeout=0.5)
    assert proc_collector.processes == []
    mocked_process.reset_mock()
    # 3. not found but process exists
    mocked_process.side_effect = lambda x: Mock(pid=x)
    proc_collector.update_process_list('dummy_proc', 1234)
    assert mocked_process.call_args_list == [call(1234)]
    assert not pipes[2][0].poll(timeout=0.5)
    assert len(proc_collector.processes) == 1
    process = proc_collector.processes[0]
    assert process['namespec'] == 'dummy_proc'
    assert process['last'] == 0
    assert process['process'].pid == 1234
    mocked_process.reset_mock()
    # 4. update with same pid
    proc_collector.update_process_list('dummy_proc', 1234)
    assert not mocked_process.called
    assert not pipes[2][0].poll(timeout=0.5)
    assert len(proc_collector.processes) == 1
    process = proc_collector.processes[0]
    assert process['namespec'] == 'dummy_proc'
    assert process['last'] == 0
    assert process['process'].pid == 1234
    mocked_process.reset_mock()
    # 5. update with a different positive pid
    time_ref = time.monotonic()
    proc_collector.update_process_list('dummy_proc', 4321)
    assert mocked_process.call_args_list == [call(4321)]
    assert pipes[2][0].poll(timeout=0.5)
    result = pipes[2][0].recv()
    assert sorted(result.keys()) == ['namespec', 'now', 'pid']
    assert result['namespec'] == 'dummy_proc'
    assert result['pid'] == 0
    assert time_ref + 1 > result['now'] > time_ref
    assert len(proc_collector.processes) == 1
    process = proc_collector.processes[0]
    assert process['namespec'] == 'dummy_proc'
    assert process['last'] == 0
    assert process['process'].pid == 4321
    mocked_process.reset_mock()
    # 6. update with a different zero pid
    time_ref = time.monotonic()
    proc_collector.update_process_list('dummy_proc', 0)
    assert not mocked_process.called
    assert pipes[2][0].poll(timeout=0.5)
    result = pipes[2][0].recv()
    assert sorted(result.keys()) == ['namespec', 'now', 'pid']
    assert result['namespec'] == 'dummy_proc'
    assert result['pid'] == 0
    assert time_ref + 1 > result['now'] > time_ref
    assert proc_collector.processes == []


def test_process_statistics_collector_collect_supervisor(mocker, pipes, proc_collector):
    """ Test the ProcessStatisticsCollector.collect_supervisor method. """
    # WARN: queue timeout uses time.monotonic so cannot use a time patch here
    # 1. with not enough time to trigger the collection
    time_ref = time.monotonic()
    proc_collector.supervisor_process['last'] = time_ref
    proc_collector.collect_supervisor()
    assert not pipes[2][0].poll(timeout=0.5)
    assert proc_collector.supervisor_process['last'] == time_ref
    # 2. with enough time to trigger the collection
    proc_collector.supervisor_process['last'] -= 5
    proc_collector.collect_supervisor()
    assert pipes[2][0].poll(timeout=0.5)
    supervisor_stats = pipes[2][0].recv()
    assert sorted(supervisor_stats.keys()) == ['namespec', 'nb_cores', 'now', 'pid', 'proc_memory', 'proc_work']
    assert supervisor_stats['namespec'] == 'supervisord'
    assert supervisor_stats['nb_cores'] == mp.cpu_count()
    assert time_ref + 1 > supervisor_stats['now'] > time_ref
    assert supervisor_stats['pid'] == os.getpid()
    assert 0 < supervisor_stats['proc_memory'] < 100
    assert supervisor_stats['proc_work'] > 0
    assert proc_collector.supervisor_process['last'] > time_ref
    # 3. with no stats provided (OSError)
    proc_collector.supervisor_process['last'] -= 5
    mocker.patch('supvisors.statscollector.instant_process_statistics', return_value=())
    proc_collector.collect_supervisor()
    assert not pipes[2][0].poll(timeout=0.5)
    assert proc_collector.supervisor_process['last'] > time_ref


def test_process_statistics_collector_collect_recent_process(mocker, pipes, proc_collector):
    """ Test the ProcessStatisticsCollector.collect_recent_process method. """
    # WARN: queue timeout uses time.monotonic so cannot use a time patch here
    time_ref = time.monotonic()
    # first try with no process to collect
    proc_collector.collect_recent_process()
    assert not pipes[2][0].poll(timeout=0.5)
    # second try with processes but not enough time to trigger the collection
    process = psutil.Process()
    proc_collector.processes = [{'namespec': 'dummy_1', 'last': time_ref - 1, 'process': process},
                                {'namespec': 'dummy_2', 'last': time_ref - 4, 'process': process}]
    proc_collector.collect_recent_process()
    assert not pipes[2][0].poll(timeout=0.5)
    assert proc_collector.processes == [{'namespec': 'dummy_1', 'last': time_ref - 1, 'process': process},
                                        {'namespec': 'dummy_2', 'last': time_ref - 4, 'process': process}]
    # third try with enough time to trigger the collection on the first element of the list
    for proc in proc_collector.processes:
        proc['last'] -= 2
    proc_collector.collect_recent_process()
    assert pipes[2][0].poll(timeout=0.5)
    supervisor_stats = pipes[2][0].recv()
    assert sorted(supervisor_stats.keys()) == ['namespec', 'now', 'pid', 'proc_memory', 'proc_work']
    assert supervisor_stats['namespec'] == 'dummy_2'
    assert supervisor_stats['now'] > time_ref
    assert supervisor_stats['pid'] == os.getpid()
    assert 0 < supervisor_stats['proc_memory'] < 100
    assert supervisor_stats['proc_work'] > 0
    # check that the list has rotated
    assert len(proc_collector.processes) == 2
    proc_1 = proc_collector.processes[0]
    assert proc_1['namespec'] == 'dummy_2'
    assert proc_1['process'] is process
    assert proc_1['last'] > time_ref - 2
    proc_2 = proc_collector.processes[1]
    assert proc_2['namespec'] == 'dummy_1'
    assert proc_2['process'] is process
    assert proc_2['last'] == time_ref - 3
    # fourth try with enough time to trigger the collection on the first element of the list
    # but with stopped process
    mocker.patch('supvisors.statscollector.instant_process_statistics', return_value=None)
    for proc in proc_collector.processes:
        proc['last'] -= 3
    proc_collector.collect_recent_process()
    assert pipes[2][0].poll(timeout=0.5)
    supervisor_stats = pipes[2][0].recv()
    assert sorted(supervisor_stats.keys()) == ['namespec', 'now', 'pid']
    assert supervisor_stats['namespec'] == 'dummy_1'
    assert supervisor_stats['now'] > time_ref + 1
    assert supervisor_stats['pid'] == 0
    # check that dummy_1 has been removed from the list
    assert len(proc_collector.processes) == 1
    proc_1 = proc_collector.processes[0]
    assert proc_1['namespec'] == 'dummy_2'
    assert proc_1['process'] is process
    assert proc_1['last'] > time_ref - 2


def test_process_statistics_collector_collect_processes_statistics(mocker, proc_collector):
    """ Test the ProcessStatisticsCollector.collect_processes_statistics method. """
    mocked_supervisor = mocker.patch.object(proc_collector, 'collect_supervisor')
    mocked_recent = mocker.patch.object(proc_collector, 'collect_recent_process', return_value=False)
    # first try with statistics collection disabled
    assert not proc_collector.enabled
    assert not proc_collector.collect_processes_statistics()
    assert not mocked_supervisor.called
    assert not mocked_recent.called
    # try with statistics collection enabled but no process collected
    proc_collector.enabled = True
    assert not proc_collector.collect_processes_statistics()
    assert mocked_supervisor.called
    assert mocked_recent.called
    mocker.resetall()
    # try with statistics collection enabled and one process collected
    mocked_recent.return_value = True
    assert proc_collector.collect_processes_statistics()
    assert mocked_supervisor.called
    assert mocked_recent.called


def test_statistics_collector_task(mocker, pipes):
    """ Test the statistics_collector_task main loop of the process collector. """
    # mock HostStatisticsCollector
    mocked_host_collector = Mock(spec=HostStatisticsCollector)
    mocked_host_collector.collect_host_statistics.return_value = False
    mocked_host_constructor = mocker.patch('supvisors.statscollector.HostStatisticsCollector',
                                           return_value=mocked_host_collector)
    # mock ProcessStatisticsCollector
    mocked_proc_collector = Mock(spec=ProcessStatisticsCollector)
    mocked_proc_collector.collect_processes_statistics.return_value = False
    mocked_proc_constructor = mocker.patch('supvisors.statscollector.ProcessStatisticsCollector',
                                           return_value=mocked_proc_collector)
    # pre-fill the sending queue
    pipes[0][1].send((StatsMsgType.ALIVE, None))
    pipes[0][1].send((StatsMsgType.ENABLE_PROCESS, False))
    pipes[0][1].send((StatsMsgType.ENABLE_HOST, False))
    pipes[0][1].send((StatsMsgType.PERIOD, 7.5))
    pipes[0][1].send((StatsMsgType.PID, ('dummy_1', 123)))
    pipes[0][1].send((StatsMsgType.PID, ('dummy_2', 456)))
    pipes[0][1].send((StatsMsgType.ALIVE, None))

    def terminate():
        time.sleep(1)
        pipes[0][1].send((StatsMsgType.STOP, None))
    Thread(target=terminate).start()
    # trigger the main loop
    statistics_collector_task(pipes[0][0], pipes[1][0], pipes[2][0], 5, True, True, 777)
    assert mocked_host_constructor.call_args_list == [call(pipes[1][0], 5, True)]
    assert mocked_host_constructor.enabled
    assert mocked_proc_constructor.call_args_list == [call(pipes[2][0], 5, True, 777)]
    assert mocked_proc_constructor.enabled
    assert mocked_proc_collector.update_process_list.call_args_list == [call('dummy_1', 123), call('dummy_2', 456)]
    # due to the multi-threading aspect, impossible to predict the exact number of calls
    assert mocked_host_collector.collect_host_statistics.call_count > 1
    assert mocked_proc_collector.collect_processes_statistics.call_count > 1


def test_statistics_collector_task_main_killed(mocker, pipes):
    """ Test the exit of the statistics_collector_task main loop of the statistics collector
    when no heartbeat is received. """
    # mock HostStatisticsCollector
    mocked_host_collector = Mock(spec=HostStatisticsCollector)
    mocked_host_collector.collect_host_statistics.return_value = False
    mocker.patch('supvisors.statscollector.HostStatisticsCollector', return_value=mocked_host_collector)
    # mock ProcessStatisticsCollector
    mocked_proc_collector = Mock(spec=ProcessStatisticsCollector)
    mocked_proc_collector.collect_processes_statistics.return_value = False
    mocker.patch('supvisors.statscollector.ProcessStatisticsCollector', return_value=mocked_proc_collector)
    # trigger the main loop and test that it exits by itself after 15 seconds without heartbeat
    start_time = time.monotonic()
    statistics_collector_task(pipes[0][0], pipes[1][0], pipes[2][0], 5, False, False, 777)
    assert time.monotonic() - start_time > HEARTBEAT_TIMEOUT


def test_statistics_collector_process(mocker, supvisors):
    """ Test the StatisticsCollectorProcess class. """
    mocked_process = Mock(spec=mp.Process, exitcode=None)
    mocked_creation = mocker.patch('multiprocessing.Process', return_value=mocked_process)
    # test creation
    collector = StatisticsCollectorProcess(supvisors)
    assert type(collector.cmd_recv) is mp.connection.Connection
    assert type(collector.cmd_send) is mp.connection.Connection
    assert type(collector.host_stats_recv) is mp.connection.Connection
    assert type(collector.host_stats_send) is mp.connection.Connection
    assert type(collector.proc_stats_recv) is mp.connection.Connection
    assert type(collector.proc_stats_send) is mp.connection.Connection
    assert collector.process is None
    # test thread starting
    collector.start()
    assert mocked_creation.call_args_list == [call(target=statistics_collector_task,
                                                   args=(collector.cmd_recv,
                                                         collector.host_stats_send, collector.proc_stats_send,
                                                         5, True, True, os.getpid()),
                                                   daemon=True)]
    assert mocked_process.start.call_args_list == [call()]
    # test alive
    collector.alive()
    assert collector.cmd_recv.poll(timeout=0.5)
    assert collector.cmd_recv.recv() == (StatsMsgType.ALIVE, None)
    # test send_pid
    collector.send_pid('dummy_process', 1234)
    assert collector.cmd_recv.poll(timeout=0.5)
    assert collector.cmd_recv.recv() == (StatsMsgType.PID, ('dummy_process', 1234))
    # test get_host_stats
    assert collector.get_host_stats() == []
    host_stats = {'cpu': 28, 'mem': 12}
    collector.host_stats_send.send(host_stats)
    assert collector.host_stats_recv.poll(timeout=0.5)
    assert collector.get_host_stats() == [host_stats]
    # test get_process_stats
    assert collector.get_process_stats() == []
    proc_stats = {'namespec': 'dummy_process',
                  'pid': 1234,
                  'now': 4321,
                  'cpu': 'cpu_stats',
                  'proc_work': 12,
                  'proc_memory': 5}
    collector.proc_stats_send.send(proc_stats)
    assert collector.proc_stats_recv.poll(timeout=0.5)
    assert collector.get_process_stats() == [proc_stats]
    # test statistics deactivation
    collector.enable_host_statistics(False)
    assert collector.cmd_recv.poll(timeout=0.5)
    assert collector.cmd_recv.recv() == (StatsMsgType.ENABLE_HOST, False)
    collector.enable_process_statistics(False)
    assert collector.cmd_recv.poll(timeout=0.5)
    assert collector.cmd_recv.recv() == (StatsMsgType.ENABLE_PROCESS, False)
    # test statistics period update
    collector.update_collecting_period(7.5)
    assert collector.cmd_recv.poll(timeout=0.5)
    assert collector.cmd_recv.recv() == (StatsMsgType.PERIOD, 7.5)
    # test thread stopping
    collector.stop()
    assert collector.cmd_recv.poll(timeout=0.5)
    assert collector.cmd_recv.recv() == (StatsMsgType.STOP, None)
