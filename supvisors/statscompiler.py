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

from typing import Dict, List, Optional, Tuple

from .ttypes import (CPUHistoryStats, CPUInstantStats, InstantStatistics, InterfaceHistoryStats, InterfaceInstantStats,
                     InterfaceIntegratedStats, JiffiesList, MemHistoryStats, ProcessHistoryStatsMap)

# additional annotation types
FloatList = List[float]
ProcessIntegratedStatsMap = Dict[Tuple[str, int], Tuple[float, float]]  # {(namespec, pid): (cpu, mem)}
IntegratedStats = Tuple[float, CPUInstantStats, float, InterfaceIntegratedStats, ProcessIntegratedStatsMap]


# CPU statistics
def cpu_statistics(last: JiffiesList, ref: JiffiesList) -> CPUInstantStats:
    """ Return the CPU loading for all the processors between last and ref measures.
    The average on all processors is inserted in front of the list. """
    cpu = []
    for unit in zip(last, ref):
        work = unit[0][0] - unit[1][0]
        idle = unit[0][1] - unit[1][1]
        total = work + idle
        cpu.append(100.0 * work / total if total else 0)
    return cpu


def cpu_total_work(last: JiffiesList, ref: JiffiesList) -> float:
    """ Return the total work on the average CPU between last and ref measures. """
    work = last[0][0] - ref[0][0]
    idle = last[0][1] - ref[0][1]
    return work + idle


# Network statistics
def io_statistics(last: InterfaceInstantStats, ref: InterfaceInstantStats, duration: float) -> InterfaceIntegratedStats:
    """ Return the rate of receive / sent bytes per second per network interface. """
    io_stats = {}
    for intf, (last_recv, last_sent) in last.items():
        if intf in ref.keys():
            ref_recv, ref_sent = ref[intf]
            # Warning taken from psutil documentation (https://pythonhosted.org/psutil/#network)
            # on some systems such as Linux, on a very busy or long-lived system these numbers may wrap
            # (restart from zero), see issues #802. Applications should be prepared to deal with that.
            if ref_recv <= last_recv and ref_sent <= last_sent:
                recv_bytes = last_recv - ref_recv
                sent_bytes = last_sent - ref_sent
                # result in kilo bits per second (bytes / 1024 * 8)
                io_stats[intf] = recv_bytes / duration / 128, sent_bytes / duration / 128
    return io_stats


# Process statistics
def cpu_process_statistics(last: float, ref: float, total_work: float) -> float:
    """ Return the CPU loading of the process between last and ref measures. """
    # process may have been started between ref and last
    return 100.0 * (last - ref) / total_work


# Calculate resources taken between two snapshots
def statistics(last: InstantStatistics, ref: InstantStatistics) -> IntegratedStats:
    """ Return resources' statistics from two series of measures. """
    # for use in client display
    duration = last[0] - ref[0]
    cpu = cpu_statistics(last[1], ref[1])
    mem = last[2]
    io = io_statistics(last[3], ref[3], duration)
    # process statistics
    work = cpu_total_work(last[1], ref[1])
    proc = {}
    # when tuples are deserialized through JSON, they become lists
    for process_name, last_pid_stats in last[4].items():
        # find same process in ref
        ref_pid_stats = ref[4].get(process_name, None)
        # calculate cpu if ref is found
        # pid must be identical (in case of process restart in the interval)
        if ref_pid_stats and last_pid_stats[0] == ref_pid_stats[0]:
            # need the work jiffies in the interval
            proc_cpu = cpu_process_statistics(last_pid_stats[1][0], ref_pid_stats[1][0], work)
            proc[process_name, last_pid_stats[0]] = proc_cpu, last_pid_stats[1][1]
    return last[0], cpu, mem, io, proc


# Class for statistics storage
class StatisticsInstance(object):
    """ This class handles resources statistics for a given node and period. """

    def __init__(self, period, depth, logger):
        """ Initialization of the attributes.
        As period is a multiple of 5 and a call to pushStatistics is expected every 5 seconds,
        period is used as a simple counter. """
        # keep reference to the logger
        self.logger = logger
        # parameters
        self.period: int = period // 5
        self.depth: int = depth
        self.counter: int = -1
        self.ref_stats: Optional[InstantStatistics] = None
        # data structures
        self.cpu: CPUHistoryStats = []
        self.mem: MemHistoryStats = []
        self.io: InterfaceHistoryStats = {}
        self.proc: ProcessHistoryStatsMap = {}

    def clear(self):
        """ Reset all attributes. """
        self.counter = -1
        self.ref_stats = None
        # data structures
        self.cpu = []
        self.mem = []
        self.io = {}
        self.proc = {}

    def find_process_stats(self, namespec):
        """ Return the process statistics related to the namespec. """
        return next((stats for (process_name, pid), stats in self.proc.items()
                     if process_name == namespec), None)

    def _push_cpu_stats(self, cpu_stats: FloatList):
        """ Add new CPU statistics. """
        for lst in self.cpu:
            lst.append(cpu_stats.pop(0))
            self.trunc_depth(lst)

    def _push_mem_stats(self, mem_stats: float):
        """ Add new MEM statistics. """
        self.mem.append(mem_stats)
        self.trunc_depth(self.mem)

    def _push_io_stats(self, io_stats: InterfaceIntegratedStats):
        """ Add new IO statistics. """
        # on certain node configurations, interface list may be dynamic
        # unlike processes, it is interesting to log when it happens
        destroy_list = []
        for intf, (recv_stats, sent_stats) in self.io.items():
            new_bytes = io_stats.pop(intf, None)
            if new_bytes is None:
                # element is obsolete
                destroy_list.append(intf)
            else:
                recv_bytes, sent_bytes = new_bytes
                recv_stats.append(recv_bytes)
                sent_stats.append(sent_bytes)
                # remove too old values when max depth is reached
                self.trunc_depth(recv_stats)
                self.trunc_depth(sent_stats)
        # destroy obsolete elements
        for intf in destroy_list:
            self.logger.warn(f'StatisticsInstance.push_io_stats: obsolete interface: {intf}')
            del self.io[intf]
        # add new elements
        for intf, (recv_bytes, sent_bytes) in io_stats.items():
            self.logger.warn(f'StatisticsInstance.push_io_stats: new interface: {intf}')
            self.io[intf] = [recv_bytes], [sent_bytes]

    def _push_process_stats(self, proc_stats):
        """ Add new process statistics. """
        # as process list is dynamic, there are special rules
        destroy_list = []
        for named_pid, (cpu_stats, mem_stats) in self.proc.items():
            new_values = proc_stats.pop(named_pid, None)
            if new_values is None:
                # element is obsolete
                destroy_list.append(named_pid)
            else:
                cpu_value, mem_value = new_values
                cpu_stats.append(cpu_value)
                mem_stats.append(mem_value)
                # remove too old values when max depth is reached
                self.trunc_depth(cpu_stats)
                self.trunc_depth(mem_stats)
        # destroy obsolete elements
        for named_pid in destroy_list:
            del self.proc[named_pid]
        # add new elements
        for named_pid, (cpu_value, mem_value) in proc_stats.items():
            self.proc[named_pid] = [cpu_value], [mem_value]

    def push_statistics(self, stats: InstantStatistics):
        """ Calculates new statistics given a new series of measures. """
        self.counter += 1
        if self.counter % self.period == 0:
            if self.ref_stats:
                # rearrange data so that there is less processing afterwards
                integ_stats = statistics(stats, self.ref_stats)
                # add new values
                self._push_cpu_stats(integ_stats[1])
                self._push_mem_stats(integ_stats[2])
                self._push_io_stats(integ_stats[3])
                # add new Process CPU / Mem values to Process list
                self._push_process_stats(integ_stats[4])
            else:
                # init some data structures
                self.cpu = [[] for _ in stats[1]]
                self.io = {intf: ([], []) for intf in stats[3]}
            self.ref_stats = stats

    # remove first data of all lists if size exceeds depth
    def trunc_depth(self, lst):
        """ Ensure that the list does not exceed the maximum historic size. """
        while len(lst) > self.depth:
            lst.pop(0)


# Class used to compile statistics coming from all instances
class StatisticsCompiler(object):
    """ This class handles stores statistics for all instances and periods.

    Attributes are:

        - data: a dictionary containing a StatisticsInstance entry for each pair of node and period,
        - nbcores: a dictionary giving the number of processor cores per node.
        """

    def __init__(self, supvisors):
        """ Initialization of the attributes. """
        self.data = {identifier: {period: StatisticsInstance(period, supvisors.options.stats_histo, supvisors.logger)
                                  for period in supvisors.options.stats_periods}
                     for identifier in supvisors.supvisors_mapper.instances}
        self.nbcores: Dict[str, int] = {identifier: 1 for identifier in supvisors.supvisors_mapper.instances}

    def clear(self, identifier: str):
        """ For a given node, clear the StatisticsInstance for all periods. """
        for period in self.data[identifier].values():
            period.clear()

    def push_statistics(self, identifier: str, stats: InstantStatistics):
        """ Insert a new statistics measure for identifier. """
        for stats_instance in self.data[identifier].values():
            stats_instance.push_statistics(stats)
        # set the number of processor cores
        nb = len(stats[1])
        self.nbcores[identifier] = nb if nb == 1 else nb - 1
