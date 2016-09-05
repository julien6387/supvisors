#!/usr/bin/python
#-*- coding: utf-8 -*-

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

from supervisors.utils import mean
import psutil, time


# CPU statistics
def getInstantCpuStats():
    work = [ ]
    idle = [ ]
    # CPU details
    cpuStats = psutil.cpu_times(percpu=True)
    for cpuStat in cpuStats:
        work.append(cpuStat.user + cpuStat.nice + cpuStat.system + cpuStat.irq + cpuStat.softirq + cpuStat.steal + cpuStat.guest)
        idle.append(cpuStat.idle + cpuStat.iowait)
    # return adding CPU average in front of lists
    work.insert(0, mean(work))
    idle.insert(0, mean(idle))
    return zip(work, idle)

def getCpuStats(last, ref):
    cpu = [ ]
    for unit in zip(last, ref):
        work = unit[0][0] - unit[1][0]
        idle = unit[0][1] - unit[1][1]
        cpu.append(100.0 * work / (work + idle))
    return cpu

def getTotalWork(last, ref):
    # return total wok on average CPU
    work = last[0][0] - ref[0][0]
    idle = last[0][1] - ref[0][1]
    return work + idle


# Memory statistics
def getInstantMemStats():
    # return RAM used
    return psutil.virtual_memory().percent

def getMemStats(last, ref):
    # return last memory value
    return last


# Network statistics
def getInstantIOStats():
    result = { }
    # IO details
    ioStats = psutil.net_io_counters(pernic=True)
    for intf, ioStat in ioStats.items():
        result[intf] = ioStat.bytes_recv, ioStat.bytes_sent
    return result

def getIOStats(last, ref, duration):
    ioStats = { }
    for intf, lastIOStat in last.items():
        if intf in ref.keys():
            refIOStat = ref[intf]
            recv_bytes = lastIOStat[0] - refIOStat[0]
            sent_bytes = lastIOStat[1] - refIOStat[1]
            # result in kilo bits per second (bytes / 1024 * 8)
            ioStats[intf] = recv_bytes / duration / 128, sent_bytes / duration / 128
    return ioStats


# Process statistics
def getInstantProcessStats(pid):
    work = memory = 0
    proc = psutil.Process(pid)
    for p in [ proc ] + proc.children(recursive=True):
        work += sum(p.cpu_times())
        memory += p.memory_percent()
    return work, memory

def getCpuProcessStats(last, ref, totalWork):
    # process may have been started between ref and last
    if ref is None: ref = 0,
    return 100.0 * (last[0] - ref[0]) / totalWork


# Snapshot of all resources
def getInstantStats(pidList):
    procStats = { namedPid: getInstantProcessStats(namedPid[1]) for namedPid in pidList }
    return time.time(), getInstantCpuStats(), getInstantMemStats(), getInstantIOStats(), procStats


# Calculate resources taken between two snapshots
def getStats(last, ref):
    # for use in client display
    duration = last[0] - ref[0]
    cpu = getCpuStats(last[1], ref[1])
    mem = getMemStats(last[2], ref[2])
    io = getIOStats(last[3], ref[3], duration)
    # process statistics
    totalWork = getTotalWork(last[1], ref[1])
    proc = { }
    for namedPid, stats in last[4].items():
        # calculation is based on key name+pid, in case of process restart
        # storage result forget about the pid
        proc[namedPid[0]] = getCpuProcessStats(stats, ref[4].get(namedPid, None), totalWork), stats[1]
    return last[0], cpu, mem, io, proc


# Class for statistics storage
class StatisticsInstance(object):
    def __init__(self, period, depth):
        # as period is a multiple of 5 and a call to pushStatistics is expected every 5 seconds, use period as a simple counter
        self.period = period / 5
        self.depth = depth
        self.clear()

    def clear(self):
        self.counter = -1
        self.refStats = None
        # data structures
        self.cpu = [ ]
        self.mem = [ ]
        self.io = { }

    def pushStatistics(self, stats):
        # check if pid is identical
        self.counter += 1
        if self.counter % self.period == 0:
            if self.refStats:
                # rearrange data so that there is less processing when getting them
                integStats = getStats(stats, self.refStats)
                # add new CPU values to CPU lists
                for lst in self.cpu:
                	lst.append(integStats[1].pop(0))
                	self._truncDepth(lst)
                # add new Mem value to MEM list
                self.mem.append(integStats[2])
                self._truncDepth(self.mem)
                # add new IO values to IO list
                for intf, bytes in self.io.items():
                	newBytes = integStats[3].pop(intf)
                	bytes[0].append(newBytes[0])
                	bytes[1].append(newBytes[1])
                	self._truncDepth(bytes[0])
                	self._truncDepth(bytes[1])
                # add new Process CPU / Mem values to Process list
                # as process list is dynamic, there are special rules
                destroyList = [ ]
                for namedPid, values in self.proc.items():
                	newValues = integStats[4].pop(namedPid, None)
                	if newValues is None:
                		# element is obsolete
                		destroyList.append(namedPid)
                	else:
                		values[0].append(newValues[0])
                		values[1].append(newValues[1])
                		self._truncDepth(values[0])
                		self._truncDepth(values[1])
                # destroy obsolete elements
                for namedPid in destroyList:
                	del self.proc[namedPid]
                # add new elements
                for namedPid in integStats[4].keys():
                	self.proc[namedPid] = ( [ ], [ ] )
            else:
                # init data structures (mem unchanged)
                	self.cpu = [ [ ] for _ in stats[1] ]
                	self.io = { intf: ( [ ], [ ] ) for intf in stats[3].keys() }
                	self.proc = { namedPid: ( [ ], [ ] ) for namedPid in stats[4].keys() }
            self.refStats = stats

    # remove first data of all lists if size exceeds depth
    def _truncDepth(self, lst):
        while len(lst) > self.depth:
            lst.pop(0)


# Class used to compile statistics coming from all addresses
class StatisticsCompiler(object):
    def __init__(self):
        self.clearAll([ 10 ], 10)

    def clearAll(self, periods, histoSize):
        from supervisors.addressmapper import addressMapper
        self.data = { address: { period: StatisticsInstance(period, histoSize) for period in periods } for address in addressMapper.expectedAddresses }

    def clear(self, address):
        for period in self.data[address].values():
            period.clear()

    def pushStatistics(self, address, stats):
        for period in self.data[address].values():
            period.pushStatistics(stats)


statisticsCompiler = StatisticsCompiler()

