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

import os

from psutil import cpu_times, net_io_counters, virtual_memory, Process, NoSuchProcess
from time import time
from typing import List

from .ttypes import JiffiesList, InterfaceInstantStats, InstantStatistics, NamedPidList, ProcessStats
from .utils import mean


# CPU statistics
def instant_cpu_statistics() -> JiffiesList:
    """ Return the instant work+idle jiffies for all the processors.
    The average on all processors is inserted in front of the list. """
    work: List[float] = []
    idle: List[float] = []
    # CPU details
    cpu_stats = cpu_times(percpu=True)
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
    return virtual_memory().percent


# Network statistics
def instant_io_statistics() -> InterfaceInstantStats:
    """ Return the instant values of receive / sent bytes per network interface. """
    result: InterfaceInstantStats = {}
    # IO details
    io_stats = net_io_counters(pernic=True)
    for intf, io_stat in io_stats.items():
        result[intf] = io_stat.bytes_recv, io_stat.bytes_sent
    return result


# Process statistics
def instant_process_statistics(pid, children=True) -> ProcessStats:
    """ Return the instant jiffies and memory values for the process identified by pid. """
    work = memory = 0
    try:
        # get main process
        proc = Process(pid)
        # Note: using Process.oneshot has no value (2 accesses and memory_percent not included in cache for Linux)
        # include children CPU times but exclude iowait
        work = sum(proc.cpu_times()[:4])
        memory = proc.memory_percent()
        # consider children
        if children:
            for p in proc.children(recursive=True):
                # children CPU times are already considered in parent
                memory += p.memory_percent()
    except (NoSuchProcess, ValueError):
        # process may have disappeared in the interval
        pass
    # take into account the number of processes for the process work
    return work, memory


# Snapshot of all resources
def instant_statistics(named_pid_list: NamedPidList) -> InstantStatistics:
    """ Return a tuple of all measures taken on the CPU, Memory and IO resources. """
    proc_statistics = {process_name: (pid, instant_process_statistics(pid))
                       for process_name, pid in named_pid_list}
    # add supervisord statistics, without considering its children
    # supervisord is the father of all named_pids so that should give a grand total
    self_pid = os.getpid()
    proc_statistics['supervisord'] = self_pid, instant_process_statistics(self_pid, False)
    # return a Tuple with everything
    return (time(), instant_cpu_statistics(), instant_memory_statistics(),
            instant_io_statistics(), proc_statistics)
