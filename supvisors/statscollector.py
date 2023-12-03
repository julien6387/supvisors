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

import multiprocessing as mp
import os
import signal
from enum import Enum
from time import sleep, time
from typing import Dict, List, Optional

import psutil
from supervisor.loggers import Logger

from .ttypes import Jiffies, JiffiesList, InterfaceInstantStats, ProcessStats, PayloadList
from .utils import mean

# Default sleep time when nothing to do
SLEEP_TIME = 0.2

# Maximum time to put data into the statistics queue
# Although daemonized, the collect_process_statistics does not end when supervisord is killed
# so if the put fails because the other end is terminated, the TimeoutException will end the process
QUEUE_TIMEOUT = 10

# a heartbeat is expected every 5 seconds from the main process
# after 15 seconds without heartbeat received, it is considered that the main process has been killed
HEARTBEAT_TIMEOUT = 15


class StatsMsgType(Enum):
    """ Message types used for PID queue. """
    ALIVE, PID, STOP = range(3)


# CPU statistics
def instant_cpu_statistics() -> Jiffies:
    """ Return the instant average work+idle jiffies. """
    cpu_stat = psutil.cpu_times()
    work = (cpu_stat.user + cpu_stat.nice + cpu_stat.system
            + cpu_stat.irq + cpu_stat.softirq
            + cpu_stat.steal + cpu_stat.guest)
    idle = (cpu_stat.idle + cpu_stat.iowait)
    return work, idle


def instant_all_cpu_statistics() -> JiffiesList:
    """ Return the instant work+idle jiffies for all the processors.
    The average on all processors is inserted in front of the list. """
    work: List[float] = []
    idle: List[float] = []
    # CPU details
    cpu_stats = psutil.cpu_times(percpu=True)
    for cpu_stat in cpu_stats:
        work.append(cpu_stat.user + cpu_stat.nice + cpu_stat.system
                    + cpu_stat.irq + cpu_stat.softirq
                    + cpu_stat.steal + cpu_stat.guest)
        idle.append(cpu_stat.idle + cpu_stat.iowait)
    # return adding CPU average in front of lists
    work.insert(0, mean(work))
    idle.insert(0, mean(idle))
    return list(zip(work, idle))


# Memory statistics
def instant_memory_statistics() -> float:
    """ Return the instant value of the memory reserved.
    This is different from the memory used as it does not include the percent of memory that is available
    (in cache or swap). """
    return psutil.virtual_memory().percent


# Network statistics
def instant_io_statistics() -> InterfaceInstantStats:
    """ Return the instant values of receive / sent bytes per network interface. """
    result: InterfaceInstantStats = {}
    # get active interfaces
    active_nics = [key for key, value in psutil.net_if_stats().items() if value.isup]
    # IO details (only if active)
    io_stats = psutil.net_io_counters(pernic=True)
    for nic, io_stat in io_stats.items():
        if nic in active_nics:
            result[nic] = io_stat.bytes_recv, io_stat.bytes_sent
    return result


# Host statistics
def instant_host_statistics() -> Dict:
    """ Get a snapshot of some host resources. """
    try:
        return {'now': time(),
                'cpu': instant_all_cpu_statistics(),
                'mem': instant_memory_statistics(),
                'io': instant_io_statistics()}
    except OSError:
        # possibly Too many open files: '/proc/stat'
        # still unclear why it happens
        return {}


# Process statistics
process_attributes = ['cpu_times', 'memory_percent']


def instant_process_statistics(proc: psutil.Process, get_children=True) -> Optional[ProcessStats]:
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


class CollectedProcesses:
    """ Class holding the psutil structures for all the processes to collect statistics from. """

    def __init__(self, stats_queue: mp.Queue, period: float, supervisor_pid: int):
        """ Initialization of the attributes. """
        self.stats_queue: mp.Queue = stats_queue
        self.period: float = period
        self.processes: List[Dict] = []
        # additional information obout the number of CPU cores, used for the Solaris mode
        self.nb_cores = mp.cpu_count()
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
                self.stats_queue.put({'namespec': namespec,
                                      'pid': 0,
                                      'now': time()},
                                     timeout=QUEUE_TIMEOUT)
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
        current_time = time()
        elapsed = current_time - self.supervisor_process['last']
        if elapsed >= self.period:
            supervisor = self.supervisor_process['supervisor']
            sup_stats = instant_process_statistics(supervisor, False)
            collector = self.supervisor_process['collector']
            col_stats = instant_process_statistics(collector, False)
            if sup_stats and col_stats:
                # push the results into the stats_queue
                self.stats_queue.put({'namespec': 'supervisord',
                                      'pid': supervisor.pid,
                                      'now': current_time,
                                      'cpu': instant_cpu_statistics(),  # CPU needed for process CPU calculation
                                      'nb_cores': self.nb_cores,  # needed for Solaris mode
                                      'proc_work': sup_stats[0] + col_stats[0],
                                      'proc_memory': sup_stats[1] + col_stats[1]},
                                     timeout=QUEUE_TIMEOUT)
                # re-insert the process in front of the list
                self.supervisor_process['last'] = current_time
            else:
                # failure probably due to Too many open files: '/proc/stat'
                # re-insert the process in front of the list to avoid 100% CPU
                self.supervisor_process['last'] = current_time

    def collect_recent_process(self) -> bool:
        """ Collect the next process statistics. """
        if len(self.processes):
            current_time = time()
            elapsed = current_time - self.processes[-1]['last']
            if elapsed >= self.period:
                # period has passed. get statistics on the process
                proc_data = self.processes.pop()
                proc = proc_data['process']
                proc_stats = instant_process_statistics(proc)
                if proc_stats is None:
                    # warn the subscribers that the process has been stopped
                    self.stats_queue.put({'namespec': proc_data['namespec'],
                                          'pid': 0,
                                          'now': current_time},
                                         timeout=QUEUE_TIMEOUT)
                    # not to be re-inserted in the list
                else:
                    if proc_stats:  # proc_stats is an empty tuple in case of OSError
                        # push the results into the stats_queue
                        self.stats_queue.put({'namespec': proc_data['namespec'],
                                              'pid': proc.pid,
                                              'now': current_time,
                                              'cpu': instant_cpu_statistics(),  # CPU needed for process CPU calculation
                                              'proc_work': proc_stats[0],
                                              'proc_memory': proc_stats[1]},
                                             timeout=QUEUE_TIMEOUT)
                    # whatever it has succeeded or not, update date and re-insert the process in front of the list
                    proc_data['last'] = current_time
                    self.processes.insert(0, proc_data)
                # no need to wait. ready to process another process
                return True
        # most ready process is not ready enough. wait
        return False


def collect_process_statistics(pid_queue: mp.Queue, stats_queue: mp.Queue, period: int, supervisor_pid: int):
    """ Collector main loop. """
    collector = CollectedProcesses(stats_queue, period, supervisor_pid)
    # loop until a stop request is received
    last_heartbeat_received = time()
    stopped = False
    while not stopped:
        # get new pids to collect statistics from
        while not pid_queue.empty():
            msg_type, msg_body = pid_queue.get()
            if msg_type == StatsMsgType.STOP:
                stopped = True
            elif msg_type == StatsMsgType.ALIVE:
                last_heartbeat_received = time()
            elif msg_type == StatsMsgType.PID:
                collector.update_process_list(*msg_body)
        # test heartbeat
        if not stopped:
            if time() - last_heartbeat_received > HEARTBEAT_TIMEOUT:
                stopped = True
        # collect process statistics
        if not stopped:
            # test if supervisord is ready to be collected
            collector.collect_supervisor()
            # test if the last element of the list is ready to be collected
            ready = collector.collect_recent_process()
            # if no process is ready to be collected, go to sleep
            if not ready:
                sleep(SLEEP_TIME)


class ProcessStatisticsCollector:
    """ Collector of instant process statistics.
    The psutil processes are cached to speed up. """

    STOP_TIMEOUT = 2.0

    def __init__(self, period: int, logger: Logger):
        # store the attributes
        self.period = period
        self.logger: Logger = logger
        # create communication queues
        self.pid_queue = mp.Queue()  # used to receive pids and program names
        self.stats_queue = mp.Queue()  # used to send process statistics
        # the process attribute
        self.process: Optional[mp.Process] = None

    def start(self):
        """ Create and start the collector process.
        The process must be started by the process that has created it, hence not created in the constructor
        because Supervisor may fork depending on the options selected."""
        self.process = mp.Process(target=collect_process_statistics,
                                  args=(self.pid_queue, self.stats_queue, self.period, os.getpid()),
                                  daemon=True)
        self.process.start()

    def alive(self):
        """ Send a heartbeat to the collector process.
        This is needed so that the thread ends itself if the main process gets killed. """
        self.pid_queue.put((StatsMsgType.ALIVE, None))

    def send_pid(self, namespec: str, pid: int):
        """ Send a process name and PID to the collector process. """
        self.pid_queue.put((StatsMsgType.PID, (namespec, pid)))

    def get_process_stats(self) -> PayloadList:
        """ Get all process statistics available. """
        proc_stats = []
        while not self.stats_queue.empty():
            proc_stats.append(self.stats_queue.get())
        return proc_stats

    def stop(self):
        """ Stop the collector process. """
        # send a stop message
        self.pid_queue.put((StatsMsgType.STOP, None))
        self.process.join(timeout=self.STOP_TIMEOUT)
        self.logger.debug(f'ProcessStatisticsCollector.stop: msg exitcode={self.process.exitcode}')
        if self.process.exitcode != 0:
            # the process did not end by itself, use hard termination
            self.logger.error('ProcessStatisticsCollector.stop: exit failed')
            # NOTE: kill introduced from Python 3.7
            self.process.terminate()
            self.process.join(timeout=self.STOP_TIMEOUT)
            self.logger.debug(f'ProcessStatisticsCollector.stop: terminate exitcode={self.process.exitcode}')
            if self.process.exitcode != signal.SIGTERM:
                self.logger.critical('ProcessStatisticsCollector.stop: terminate failed'
                                     f' exitcode={self.process.exitcode}')
