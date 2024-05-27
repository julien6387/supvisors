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

import multiprocessing as mp
import multiprocessing.connection
import os
import time
from enum import Enum
from typing import Dict, List, Optional, Tuple, Union

import psutil
from supervisor.loggers import Logger

from .ttypes import DiskUsage, JiffiesList, InterfaceInstantStats, ProcessStats, PayloadList
from .utils import mean

# Default sleep time when nothing to do
SLEEP_TIME = 0.2

# a heartbeat is expected every 5 seconds from the main process
# after 15 seconds without heartbeat received, it is considered that the main process has been killed
HEARTBEAT_TIMEOUT = 15

# Number of logical processors
NB_PROCESSORS = psutil.cpu_count()


class StatsMsgType(Enum):
    """ Message types used for PID queue. """
    ALIVE, PID, STOP, ENABLE_HOST, ENABLE_PROCESS, PERIOD = range(6)


# CPU statistics
def instant_all_cpu_statistics() -> JiffiesList:
    """ Return the instant work+idle jiffies for all the processors.
    The average on all processors is inserted in front of the list.
    Guest times are included in user and nice on Linux. """
    stats: JiffiesList = []
    # CPU details
    cpu_stats = psutil.cpu_times(percpu=True)
    for cpu_stat in cpu_stats:
        work = (cpu_stat.user + cpu_stat.nice + cpu_stat.system
                + cpu_stat.irq + cpu_stat.softirq + cpu_stat.steal)
        idle = cpu_stat.idle + cpu_stat.iowait
        stats.append((work, idle))
    # overall CPU average at the front of the list
    avg_work = mean([x[0] for x in stats])
    avg_idle = mean([x[1] for x in stats])
    stats.insert(0, (avg_work, avg_idle))
    return stats


# Memory statistics
def instant_memory_statistics() -> float:
    """ Return the instant value of the memory reserved.
    This is different from the memory used as it does not include the percent of memory that is available
    (in cache or swap). """
    return psutil.virtual_memory().percent


# Network statistics
def instant_net_io_statistics() -> InterfaceInstantStats:
    """ Return the instant values of receive / sent bytes per network interface. """
    # get active interfaces
    active_nics = [key for key, value in psutil.net_if_stats().items()
                   if value.isup]
    # IO details (only if active)
    return {nic: (io_stat.bytes_recv, io_stat.bytes_sent)
            for nic, io_stat in psutil.net_io_counters(pernic=True).items()
            if nic in active_nics}


# Disk statistics
def instant_disk_usage_statistics() -> DiskUsage:
    """ Return the instant value of the disk occupation per physical partition. """
    result = {}
    for partition in psutil.disk_partitions():
        try:
            result[partition.mountpoint] = psutil.disk_usage(partition.mountpoint).percent
        except PermissionError:
            # can happen when the disk is not ready
            pass
    return result


def instant_disk_io_statistics() -> InterfaceInstantStats:
    """ Return the instant values of read / write bytes per device. """
    return {disk: (disk_stat.read_bytes, disk_stat.write_bytes)
            for disk, disk_stat in psutil.disk_io_counters(perdisk=True).items()}


# Common
class LocalNodeInfo:
    """ Store node information to be displayed in the Supvisors Web UI. """

    def __init__(self):
        """ Get all values from psutil for once.
        Store as strings because their only purpose is to be displayed in the Web UI. """
        self.nb_core_physical: int = psutil.cpu_count(logical=False)
        self.nb_core_logical: int = psutil.cpu_count()
        # get processor frequency
        frequency: float = psutil.cpu_freq().current  # MHz
        self.frequency: str = f'{int(frequency)} MHz'
        # get physical memory
        physical_memory: int = psutil.virtual_memory().total  # bytes
        for unit in ['KiB', 'MiB', 'GiB']:
            physical_memory /= 1024
            if physical_memory < 1024:
                break
        self.physical_memory: str = f'{physical_memory:.2f} {unit}'


class StatisticsCollector:
    """ Base class for statistics collection. """

    def __init__(self, stats_conn: mp.connection.Connection, period: float, enabled: bool):
        """ Initialization of the attributes. """
        self.stats_conn: mp.connection.Connection = stats_conn
        self.period: float = period
        self.enabled: bool = enabled

    def _post(self, stats: Dict) -> None:
        """ Post the statistics collected into the pipe.
        A timeout is set to prevent an infinite blocking. """
        self.stats_conn.send(stats)


# Host statistics
class HostStatisticsCollector(StatisticsCollector):
    """ Class holding the psutil structures for all the processes to collect statistics from. """

    def __init__(self, stats_conn: mp.connection.Connection, period: float, enabled: bool):
        """ Initialization of the attributes. """
        super().__init__(stats_conn, period, enabled)
        self.last_stats_time: float = 0.0

    def collect_host_statistics(self) -> None:
        """ Get a snapshot of some host resources. """
        if self.enabled:
            current_time = time.monotonic()
            if current_time - self.last_stats_time >= self.period:
                try:
                    stats = {'now': current_time,
                             'cpu': instant_all_cpu_statistics(),
                             'mem': instant_memory_statistics(),
                             'net_io': instant_net_io_statistics(),
                             'disk_usage': instant_disk_usage_statistics(),
                             'disk_io': instant_disk_io_statistics()}
                except OSError:
                    # possibly Too many open files: '/proc/stat'
                    # still unclear why it happens
                    pass
                else:
                    # publish the information that it has been stopped
                    self._post(stats)
                # update reference time
                self.last_stats_time = current_time


# Process statistics
process_attributes = ['cpu_times', 'memory_percent']


def instant_process_statistics(proc: psutil.Process, get_children=True) -> Optional[Union[Tuple, ProcessStats]]:
    """ Return the instant jiffies and memory values for the process identified by pid. """
    try:
        # get main process statistics
        proc_stats = proc.as_dict(attrs=process_attributes)
        # WARN: children CPU times are not considered fully recursively, so exclude children CPU times and iowait
        work = sum(proc_stats['cpu_times'][:2])
        memory = proc_stats['memory_percent']
        # consider all children recursively
        if get_children:
            for p in proc.children(recursive=True):
                try:
                    p_stats = p.as_dict(attrs=process_attributes)
                    work += sum(p_stats['cpu_times'][:2])
                    memory += p_stats['memory_percent']
                except (psutil.NoSuchProcess, psutil.AccessDenied, ValueError):
                    # child process may have disappeared in the interval
                    pass
        # take into account the number of processes for the process work
        return work, memory
    except (psutil.NoSuchProcess, psutil.AccessDenied, ValueError):
        # process may have disappeared in the interval
        return None
    except OSError:
        # possibly Too many open files: '/proc/stat'
        # still unclear why it happens
        return ()


class ProcessStatisticsCollector(StatisticsCollector):
    """ Class holding the psutil structures for all the processes to collect statistics from. """

    def __init__(self, stats_conn: mp.connection.Connection,
                 period: float, enabled: bool, supervisor_pid: int):
        """ Initialization of the attributes. """
        super().__init__(stats_conn, period, enabled)
        self.processes: List[Dict] = []
        # define the supervisor process and this collector process
        self.supervisor_process: Dict = {'last': 0,
                                         'supervisor': psutil.Process(supervisor_pid),
                                         'collector': psutil.Process()}

    def update_process_list(self, namespec: str, pid: int):
        """ Update the list of processes to be collected, considering that events may have been missed. """
        # check if namespec is already being collected
        found = next(((idx, proc_stats) for idx, proc_stats in enumerate(self.processes)
                      if proc_stats['namespec'] == namespec), None)
        if found:
            # process already in list
            idx, proc_stats = found
            if proc_stats['process'].pid != pid:
                # process has been stopped in the gap. remove the entry
                self.processes.pop(idx)
                # publish the information that it has been stopped
                stats = {'namespec': namespec, 'pid': 0, 'now': time.monotonic()}
                self._post(stats)
                if pid > 0:
                    # new process running. mark as not found so that it is re-inserted
                    found = False
        if not found:
            # add new entry in list so that it is processed in priority
            try:
                process = psutil.Process(pid)
                self.processes.append({'namespec': namespec, 'last': 0, 'process': process})
            except psutil.NoSuchProcess:
                # process has been stopped in the gap
                # no need to post the termination as the process died before anything has been sent
                pass
            except OSError:
                # possibly Too many open files: '/proc/stat'
                # still unclear why it happens
                pass

    def collect_supervisor(self):
        """ Collect supervisor and collector statistics, without considering any other supervisor children. """
        current_time = time.monotonic()
        elapsed = current_time - self.supervisor_process['last']
        if elapsed >= self.period:
            supervisor = self.supervisor_process['supervisor']
            sup_stats = instant_process_statistics(supervisor, False)
            collector = self.supervisor_process['collector']
            col_stats = instant_process_statistics(collector, False)
            if sup_stats and col_stats:
                # push the results into the stats_conn
                stats = {'namespec': 'supervisord',
                         'pid': supervisor.pid,
                         'now': current_time,
                         'nb_cores': NB_PROCESSORS,  # needed for Solaris mode
                         'proc_work': sup_stats[0] + col_stats[0],
                         'proc_memory': sup_stats[1] + col_stats[1]}
                self._post(stats)
                # re-insert the process in front of the list
                self.supervisor_process['last'] = current_time
            else:
                # failure probably due to Too many open files: '/proc/stat'
                # re-insert the process in front of the list to avoid 100% CPU
                self.supervisor_process['last'] = current_time

    def collect_recent_process(self) -> bool:
        """ Collect the next process statistics. """
        if len(self.processes):
            current_time = time.monotonic()
            elapsed = current_time - self.processes[-1]['last']
            if elapsed >= self.period:
                # period has passed. get statistics on the process
                proc_data = self.processes.pop()
                proc = proc_data['process']
                proc_stats = instant_process_statistics(proc)
                if proc_stats is None:
                    # warn the subscribers that the process has been stopped
                    stats = {'namespec': proc_data['namespec'],
                             'pid': 0,
                             'now': current_time}
                    self._post(stats)
                    # not to be re-inserted in the list
                else:
                    if proc_stats:  # proc_stats is an empty tuple in case of OSError
                        # push the results into the stats_conn
                        stats = {'namespec': proc_data['namespec'],
                                 'pid': proc.pid,
                                 'now': current_time,
                                 'proc_work': proc_stats[0],
                                 'proc_memory': proc_stats[1]}
                        self._post(stats)
                    # whatever it has succeeded or not, update date and re-insert the process in front of the list
                    proc_data['last'] = current_time
                    self.processes.insert(0, proc_data)
                # no need to wait. ready to process another process
                return True
        # most ready process is not ready enough. wait
        return False

    def collect_processes_statistics(self) -> bool:
        """ Collect process statistics that have passed the collecting period.
        Return True if statistics from one process have been collected. """
        if self.enabled:
            # collect supervisord statistics
            self.collect_supervisor()
            # collect one sample of process statistics
            return self.collect_recent_process()
        return False


def statistics_collector_task(cmd_conn: mp.connection.Connection,
                              host_stats_conn: mp.connection.Connection,
                              proc_stats_conn: mp.connection.Connection,
                              period: float, host_stats_enabled: bool, process_stats_enabled: bool,
                              supervisor_pid: int):
    """ Statistics Collector main loop. """
    # create the collector instances
    host_collector = HostStatisticsCollector(host_stats_conn, period, host_stats_enabled)
    proc_collector = ProcessStatisticsCollector(proc_stats_conn, period, process_stats_enabled, supervisor_pid)
    # loop until a stop request is received or heartbeat fails
    last_heartbeat_received = time.monotonic()
    stopped = False
    while not stopped:
        # command reception loop
        while cmd_conn.poll(timeout=SLEEP_TIME):
            msg_type, msg_body = cmd_conn.recv()
            if msg_type == StatsMsgType.STOP:
                stopped = True
            elif msg_type == StatsMsgType.ALIVE:
                last_heartbeat_received = time.monotonic()
            elif msg_type == StatsMsgType.PID:
                proc_collector.update_process_list(*msg_body)
            elif msg_type == StatsMsgType.ENABLE_HOST:
                host_collector.enabled = msg_body
            elif msg_type == StatsMsgType.ENABLE_PROCESS:
                proc_collector.enabled = msg_body
            elif msg_type == StatsMsgType.PERIOD:
                host_collector.period = period
                proc_collector.period = period
        # test heartbeat
        if not stopped:
            if time.monotonic() - last_heartbeat_received > HEARTBEAT_TIMEOUT:
                stopped = True
        # collect process statistics
        if not stopped:
            # collect host statistics if enabled
            host_collector.collect_host_statistics()
            # collect process statistics if enabled
            ready = proc_collector.collect_processes_statistics()
            # if no process is ready to be collected, go to sleep
            if not ready:
                time.sleep(SLEEP_TIME)


class StatisticsCollectorProcess:
    """ Wrapper of the Statistics Collector task. """

    STOP_TIMEOUT = 2.0

    def __init__(self, supvisors):
        """ Initialization of the attributes. """
        # store the attributes
        self.supvisors = supvisors
        self.logger: Logger = supvisors.logger
        # get the node characteristics
        self.node_info: LocalNodeInfo = LocalNodeInfo()
        # create communication pipes
        self.cmd_recv, self.cmd_send = mp.Pipe(False)  # used to /receive commands, pids and program names
        self.host_stats_recv, self.host_stats_send = mp.Pipe(False)  # used to send/receive host statistics
        self.proc_stats_recv, self.proc_stats_send = mp.Pipe(False)  # used to send/receive process statistics
        # the process attribute
        self.process: Optional[mp.Process] = None

    def start(self):
        """ Create and start the statistics collector task.
        The process must be started by the process that has created it, hence not created in the constructor
        because Supervisor may fork depending on the options selected. """
        self.process = mp.Process(target=statistics_collector_task,
                                  args=(self.cmd_recv, self.host_stats_send, self.proc_stats_send,
                                        self.supvisors.options.collecting_period,
                                        self.supvisors.options.host_stats_enabled,
                                        self.supvisors.options.process_stats_enabled,
                                        os.getpid()),
                                  daemon=True)
        self.process.start()

    def alive(self):
        """ Send a heartbeat to the collector process.
        This is needed so that the thread ends itself if the main process gets killed. """
        self.cmd_send.send((StatsMsgType.ALIVE, None))

    def enable_host_statistics(self, enabled: bool):
        """ Enable / disable the host statistics collection. """
        self.cmd_send.send((StatsMsgType.ENABLE_HOST, enabled))

    def enable_process_statistics(self, enabled: bool):
        """ Enable / disable the process statistics collection. """
        self.cmd_send.send((StatsMsgType.ENABLE_PROCESS, enabled))

    def update_collecting_period(self, period: float):
        """ Update the period for host and process statistics collection. """
        self.cmd_send.send((StatsMsgType.PERIOD, period))

    def send_pid(self, namespec: str, pid: int):
        """ Send a process name and PID to the collector process. """
        self.cmd_send.send((StatsMsgType.PID, (namespec, pid)))

    @staticmethod
    def _get_stats(stats_conn: mp.connection.Connection) -> PayloadList:
        """ Get all statistics available from a given pipe connector. """
        stats = []
        while stats_conn.poll():
            stats.append(stats_conn.recv())
        return stats

    def get_host_stats(self) -> PayloadList:
        """ Get all host statistics available. """
        return self._get_stats(self.host_stats_recv)

    def get_process_stats(self) -> PayloadList:
        """ Get all process statistics available. """
        return self._get_stats(self.proc_stats_recv)

    def stop(self):
        """ Stop the collector process. """
        # send a stop message
        self.cmd_send.send((StatsMsgType.STOP, None))
        self.process.join(timeout=self.STOP_TIMEOUT)
        if self.process.exitcode != 0:
            # WARN: the process did not end by itself
            #       using Process.terminate won't change a thing and kill has been introduced from Python 3.7
            self.logger.critical('StatisticsCollectorProcess.stop: stop failed'
                                 f' exitcode={self.process.exitcode}')
