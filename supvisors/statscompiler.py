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

import time
from typing import Dict, List, Optional, Tuple

from .ttypes import (CPUHistoryStats, CPUInstantStats,
                     JiffiesList,
                     InterfaceHistoryStats, InterfaceInstantStats, InterfaceIntegratedStats,
                     MemHistoryStats, TimesHistoryStats,
                     ProcessCPUHistoryStats, ProcessMemHistoryStats,
                     Payload, PayloadList)

# additional annotation types
FloatList = List[float]
IntegratedProcessStats = Tuple[float, float, float]  # cpu, mem, seconds
IntegratedHostStatistics = Tuple[float, CPUInstantStats, float, InterfaceIntegratedStats,
                                 InterfaceIntegratedStats, InterfaceIntegratedStats]


# CPU statistics
def cpu_statistics(latest_values: JiffiesList, ref_values: JiffiesList) -> CPUInstantStats:
    """ Return the CPU loading for all the processors between last and ref measures.
    The average on all processors is inserted in front of the list. """
    cpu = []
    for (latest_work, latest_idle), (ref_work, ref_idle) in zip(latest_values, ref_values):
        work = latest_work - ref_work
        idle = latest_idle - ref_idle
        total = work + idle
        cpu.append(100.0 * work / total if total else 0)
    return cpu


# Network / Disk statistics
def io_statistics(last_values: InterfaceInstantStats, ref_values: InterfaceInstantStats,
                  duration: float) -> InterfaceIntegratedStats:
    """ Return the rate of 'in' (read/receive) bytes and 'out' (write/sent) bytes per second per interface
    (network or device). """
    io_stats = {}
    for intf, (last_in, last_out) in last_values.items():
        if intf in ref_values.keys():
            ref_in, ref_out = ref_values[intf]
            # WARN: taken from psutil documentation (https://pythonhosted.org/psutil/#network)
            #       On some systems such as Linux, on a very busy or long-lived system these numbers may wrap
            #       (restart from zero), see issues #802. Applications should be prepared to deal with that.
            #       Same logic applies to Disk IO counters.
            if ref_in <= last_in and ref_out <= last_out:
                in_bytes = last_in - ref_in
                out_bytes = last_out - ref_out
                # result in kilo bits per second (bytes / 1024 * 8)
                io_stats[intf] = [in_bytes / duration / 128, out_bytes / duration / 128]
    return io_stats


# remove first data of list if size exceeds depth
def trunc_depth(lst, depth):
    """ Ensure that the list does not exceed the maximum historic size. """
    while len(lst) > depth:
        lst.pop(0)


# Class for statistics storage
class HostStatisticsInstance:
    """ This class handles resources statistics for a given node and period. """

    def __init__(self, identifier: str, period: float, depth: float, logger):
        """ Initialization of the attributes. """
        # keep reference to the logger
        self.logger = logger
        # parameters
        self.identifier: str = identifier
        self.period: float = period
        self.depth: float = depth
        self.ref_stats: Payload = {}
        self.ref_start_time: float = 0.0
        # data structures
        self.times: TimesHistoryStats = []
        self.cpu: CPUHistoryStats = []
        self.mem: MemHistoryStats = []
        self.net_io: InterfaceHistoryStats = {}  # {interface: ([uptimes], [[recv_bytes], [sent_bytes]])}
        self.disk_io: InterfaceHistoryStats = {}  # {interface: ([uptimes], [[read_bytes], [write_bytes]])}
        self.disk_usage: InterfaceHistoryStats = {}  # {interface: ([uptimes], [[percent]])}

    def _push_times_stats(self, time_value: float) -> None:
        """ Add new Times statistics. """
        self.times.append(time_value)
        trunc_depth(self.times, self.depth)

    def _push_cpu_stats(self, cpu_stats: FloatList) -> None:
        """ Add new CPU statistics. """
        for lst in self.cpu:
            lst.append(cpu_stats.pop(0))
            trunc_depth(lst, self.depth)

    def _push_mem_stats(self, mem_value: float) -> None:
        """ Add new MEM statistics. """
        self.mem.append(mem_value)
        trunc_depth(self.mem, self.depth)

    def _push_net_io_stats(self, net_io_stats: InterfaceIntegratedStats, uptime: float) -> None:
        """ Add new network IO statistics. """
        self._push_timed_stats(self.net_io, net_io_stats, 'nic', uptime)

    def _push_disk_io_stats(self, disk_io_stats: InterfaceIntegratedStats, uptime: float) -> None:
        """ Add new disk IO statistics. """
        self._push_timed_stats(self.disk_io, disk_io_stats, 'device', uptime)

    def _push_disk_usage_stats(self, disk_usage_stats: InterfaceIntegratedStats, uptime: float) -> None:
        """ Add new disk IO statistics. """
        self._push_timed_stats(self.disk_usage, disk_usage_stats, 'partition', uptime)

    def _push_timed_stats(self, ref_stats: InterfaceHistoryStats, io_stats: InterfaceIntegratedStats,
                          name: str, uptime: float) -> None:
        """ Add statistics variable in time (network IO, disk IO or disk usage).

        Unlike CPU and Mem, Network and Disk data may be variable in time, depending on the actions
        on the operating system, so the time_value must be associated with the values. """
        destroy_list = []
        for intf, (uptimes, ref_bytes) in ref_stats.items():
            new_bytes_list = io_stats.pop(intf, None)
            if new_bytes_list is None:
                # element is obsolete
                destroy_list.append(intf)
            else:
                # add new uptime value and clean
                uptimes.append(uptime)
                trunc_depth(uptimes, self.depth)
                # add new bytes rate values and clean
                for new_data_bytes, ref_bytes_list in zip(new_bytes_list, ref_bytes):
                    ref_bytes_list.append(new_data_bytes)
                    trunc_depth(ref_bytes_list, self.depth)
        # destroy obsolete elements
        for intf in destroy_list:
            self.logger.warn(f'StatisticsInstance._push_timed_stats: obsolete {name}={intf} on {self.identifier}'
                             f' (period={self.period})')
            del ref_stats[intf]
        # add new elements
        for intf, new_bytes_list in io_stats.items():
            self.logger.warn(f'StatisticsInstance._push_timed_stats: new {name}={intf} on {self.identifier}'
                             f' (period={self.period})')
            ref_stats[intf] = [uptime], [[new_data_bytes] for new_data_bytes in new_bytes_list]

    def integrate(self, last: Payload) -> IntegratedHostStatistics:
        """ Return resources' statistics from two series of measures. """
        # for use in client display
        duration: float = last['now'] - self.ref_stats['now']
        cpu: CPUInstantStats = cpu_statistics(last['cpu'], self.ref_stats['cpu'])
        mem: float = last['mem']
        net_io: InterfaceIntegratedStats = io_statistics(last['net_io'], self.ref_stats['net_io'], duration)
        disk_io: InterfaceIntegratedStats = io_statistics(last['disk_io'], self.ref_stats['disk_io'], duration)
        disk_usage: InterfaceIntegratedStats = {k: [v] for k, v in last['disk_usage'].items()}
        return last['now'] - self.ref_start_time, cpu, mem, net_io, disk_io, disk_usage

    def push_statistics(self, stats: Payload) -> Payload:
        """ Calculate new statistics given a new series of measures.
        Return True upon any change on network interfaces. """
        result = {}
        if self.ref_stats:
            if stats['now'] - self.ref_stats['now'] >= self.period:
                # rearrange data so that there is less processing afterward
                uptime, cpu, mem, net_io, disk_io, disk_usage = self.integrate(stats)
                # create the result structure (use a copy as the _push functions will pop the original data)
                result = {'identifier': self.identifier,
                          'now_monotonic': time.monotonic(),
                          'target_period': self.period,
                          'period': (self.ref_stats['now'] - self.ref_start_time,
                                     stats['now'] - self.ref_start_time),
                          'cpu': cpu.copy(),
                          'mem': mem,
                          'net_io': net_io.copy(),
                          'disk_io': disk_io.copy(),
                          'disk_usage': {k: v[0] for k, v in disk_usage.items()}}
                # add new values
                self._push_times_stats(uptime)
                self._push_cpu_stats(cpu)
                self._push_mem_stats(mem)
                self._push_net_io_stats(net_io, uptime)
                self._push_disk_io_stats(disk_io, uptime)
                self._push_disk_usage_stats(disk_usage, uptime)
                # new stats become the reference stats for next integration
                self.ref_stats = stats
        else:
            # new stats are the reference stats on first occurrence
            self.ref_stats = stats
            self.ref_start_time = stats['now']
            # init some data structures
            self.cpu = [[] for _ in stats['cpu']]
            self.net_io = {intf: ([], [[], []])
                           for intf in stats['net_io']}
            self.disk_io = {device: ([], [[], []])
                            for device in stats['disk_io']}
            self.disk_usage = {partition: ([], [[]])
                               for partition in stats['disk_usage']}
        return result


# Class used to compile statistics coming from all instances
class HostStatisticsCompiler:
    """ This class stores host statistics for all instances and periods.

    Attributes are:
        - instance_map: a dictionary containing a HostStatisticsInstance entry for each pair of node and period,
        - nb_cores: a dictionary giving the number of processor cores per node.
        """

    # additional annotation type for internal purpose
    HostStatisticsMap = Dict[str, Dict[float, HostStatisticsInstance]]

    def __init__(self, supvisors):
        """ Initialization of the attributes. """
        self.supvisors = supvisors
        # Instance structures
        self.instance_map: HostStatisticsCompiler.HostStatisticsMap = {}
        self.nb_cores: Dict[str, int] = {}

    def add_instance(self, identifier: str) -> None:
        """ Add a new Supvisors instance to the statistics structures."""
        self.instance_map[identifier] = {period: HostStatisticsInstance(identifier, period,
                                                                        self.supvisors.options.stats_histo,
                                                                        self.supvisors.logger)
                                         for period in self.supvisors.options.stats_periods}
        self.nb_cores[identifier] = 1

    def get_stats(self, identifier: str, period: float) -> Optional[HostStatisticsInstance]:
        """ Return the HostStatisticsInstance corresponding to a Supvisors instance and a period. """
        identifier_instance = self.instance_map.get(identifier)
        if identifier_instance:
            return identifier_instance.get(period)
        return None

    def get_nb_cores(self, identifier: str) -> int:
        """ Return the number of CPU cores linked to a Supvisors instance. """
        return self.nb_cores.get(identifier, 0)

    def push_statistics(self, identifier: str, stats: Payload) -> PayloadList:
        """ Insert a new statistics measure for identifier. """
        integrated_stats = []
        # create the statistics instance if it does not exist
        host_instance = self.instance_map.get(identifier)
        if not host_instance:
            self.add_instance(identifier)
        # consider new statistics on host
        host_instance = self.instance_map[identifier]
        for period, stats_instance in host_instance.items():
            result = stats_instance.push_statistics(stats)
            if result:
                integrated_stats.append(result)
        # set the number of processor cores
        # in the case of multiple cores, the first series of values are average values
        nb = len(stats['cpu'])
        self.nb_cores[identifier] = nb if nb == 1 else nb - 1
        return integrated_stats


# Process statistics
def cpu_process_statistics(latest: float, ref: float, host_work: float) -> float:
    """ Return the CPU loading of the process between latest and reference measures. """
    # process may have been started between ref and latest
    return 100.0 * (latest - ref) / host_work


class ProcStatisticsInstance:
    """ This class handles statistics for a process running on a Supervisor instance and for a given period. """

    def __init__(self, namespec: str = '', identifier: str = '', pid: int = 0, period: float = 0.0, depth: int = 0):
        """ Initialization of the attributes. """
        # parameters
        self.namespec: str = namespec
        self.identifier: str = identifier
        self.pid: int = pid
        self.period: float = period
        self.depth: int = depth
        self.ref_stats: Payload = {}
        self.ref_start_time: float = 0.0
        # data structures
        self.times: TimesHistoryStats = []
        self.cpu: ProcessCPUHistoryStats = []
        self.mem: ProcessMemHistoryStats = []

    def integrate(self, latest: Payload) -> IntegratedProcessStats:
        """ Return resources' statistics from two series of measures. """
        proc_cpu = (latest['proc_work'] - self.ref_stats['proc_work']) / (latest['now'] - self.ref_stats['now'])
        return 100.0 * proc_cpu, latest['proc_memory'], latest['now'] - self.ref_start_time

    def push_statistics(self, proc_stats: Payload) -> Payload:
        """ Calculate new statistics given a new series of measures. """
        result = {}
        if self.ref_stats:
            if proc_stats['now'] - self.ref_stats['now'] >= self.period:
                # rearrange data so that there is less processing afterward
                cpu_value, mem_value, time_value = self.integrate(proc_stats)
                # create the result structure (use a copy as the _push functions will pop)
                result = {'namespec': self.namespec,
                          'identifier': self.identifier,
                          'pid': self.pid,
                          'now_monotonic': time.monotonic(),
                          'target_period': self.period,
                          'period': (self.ref_stats['now'] - self.ref_start_time,
                                     proc_stats['now'] - self.ref_start_time),
                          'cpu': cpu_value,
                          'mem': mem_value}
                # add new Process CPU / Mem values to Process list
                self.cpu.append(cpu_value)
                self.mem.append(mem_value)
                self.times.append(time_value)
                # remove too old values when max depth is reached
                trunc_depth(self.cpu, self.depth)
                trunc_depth(self.mem, self.depth)
                trunc_depth(self.times, self.depth)
                # new stats become the reference stats for next integration
                self.ref_stats = proc_stats
        else:
            # new stats are the reference stats on first occurrence
            self.ref_stats = proc_stats
            self.ref_start_time = proc_stats['now']
        return result

    def copy(self, cpu_factor: int):
        """ Return a copy of the data in a new instance. """
        instance_copy = ProcStatisticsInstance()
        instance_copy.times = self.times.copy()
        instance_copy.mem = self.mem.copy()
        instance_copy.cpu = [x / cpu_factor for x in self.cpu]
        return instance_copy


class ProcStatisticsHolder:
    """ This class stores process statistics for a process that may be running on all Supervisor instances.

    Attributes are:

        - namespec: the process namespec ;
        - options: the Supvisors options ;
        - logger: the global Supvisors logger ;
        - instance_map: a dictionary of ProcStatisticsInstance for all Supvisors instances where the process is running
                        and for all periods.
    """

    IdentifierInstanceMap = Dict[str, Tuple[int, Dict[float, ProcStatisticsInstance]]]

    def __init__(self, namespec: str, options, logger):
        """ Initialization of the attributes. """
        self.namespec = namespec
        self.options = options
        self.logger = logger
        # {identifier: (pid, {period: ProcStatisticsInstance}}
        self.instance_map: ProcStatisticsHolder.IdentifierInstanceMap = {}

    def get_stats(self, identifier: str, period: float, cpu_factor: int) -> Optional[ProcStatisticsInstance]:
        """ Return the ProcStatisticsInstance corresponding to a Supvisors instance and a period. """
        _, identifier_instance = self.instance_map.get(identifier, (0, None))
        if identifier_instance:
            proc_stats = identifier_instance.get(period)
            if proc_stats:
                return proc_stats.copy(cpu_factor)
        return None

    def push_statistics(self, identifier: str, process_stats: Payload) -> PayloadList:
        """ Consider a new list of process statistics received from a Supvisors instance.
        Stopped processes (pid=0) are not considered if there is no existing holder. """
        integrated_stats = []
        pid = process_stats['pid']
        if pid == 0:
            # process has been stopped on Supervisord instance
            self.logger.debug(f'ProcStatisticsHolder.push_statistics: {self.namespec} stopped on {identifier}')
            self.instance_map.pop(identifier, None)
        else:
            ref_pid, identifier_instance = self.instance_map.get(identifier, (0, None))
            if not identifier_instance or pid != ref_pid:
                # process has been (re-)started on Supervisord instance
                self.logger.debug(f'ProcStatisticsHolder.push_statistics: {self.namespec} started on {identifier}')
                identifier_instance = {period: ProcStatisticsInstance(self.namespec, identifier, pid,
                                                                      period, self.options.stats_histo)
                                       for period in self.options.stats_periods}
                self.instance_map[identifier] = pid, identifier_instance
            # update process statistics for all periods
            for period_instance in identifier_instance.values():
                result = period_instance.push_statistics(process_stats)
                if result:
                    integrated_stats.append(result)
        return integrated_stats


class ProcStatisticsCompiler:
    """ This class stores process statistics for all processes running on all Supervisor instances.

    Attributes are:

        - options: the Supvisors options
        - logger: the global Supvisors logger
        - holder_map: a dictionary of ProcessesStatisticsHolder.
    """

    def __init__(self, options, logger):
        """ Initialization of the attributes. """
        self.options = options
        self.logger = logger
        self.holder_map: Dict[str, ProcStatisticsHolder] = {}
        # keep a CPU core map per identifier for Solaris mode
        self.nb_cores = {}

    def get_stats(self, namespec: str, identifier: str, period: float) -> Optional[ProcStatisticsInstance]:
        """ Return a copy of the current ProcStatisticsInstance corresponding to a namespec, a Supvisors instance
        and a period.
        CPU values are updated if SOLARIS mode is expected.
        """
        proc_holder = self.holder_map.get(namespec)
        if proc_holder:
            cpu_factor = 1 if self.options.stats_irix_mode else self.nb_cores.get(identifier, 1)
            return proc_holder.get_stats(identifier, period, cpu_factor)

    def get_nb_cores(self, identifier: str) -> int:
        """ Return the number of CPU cores linked to a Supvisors instance. """
        return self.nb_cores.get(identifier, 0)

    def push_statistics(self, identifier: str, process_stats: Payload) -> PayloadList:
        """ Consider a new list of process statistics received from a Supvisors instance.
        Stopped processes (pid=0) are not considered if there is no existing holder. """
        integrated_stats = []
        namespec = process_stats['namespec']
        pid = process_stats['pid']
        proc_holder = self.holder_map.get(namespec)
        if pid > 0 and not proc_holder:
            # new process spawned
            self.holder_map[namespec] = proc_holder = ProcStatisticsHolder(namespec, self.options, self.logger)
            self.logger.debug(f'ProcStatisticsCompiler.push_statistics: holder created for {namespec}')
        if proc_holder:
            # update the holder data
            integrated_stats = proc_holder.push_statistics(identifier, process_stats)
            # if no more data, delete the holder
            if not proc_holder.instance_map:
                self.logger.debug(f'ProcStatisticsCompiler.push_statistics: holder deleted for {namespec}')
                del self.holder_map[namespec]
        # set the number of processor cores on the identifier if provided (only in supervisord stats)
        if 'nb_cores' in process_stats:
            self.nb_cores[identifier] = process_stats['nb_cores']
        return integrated_stats
