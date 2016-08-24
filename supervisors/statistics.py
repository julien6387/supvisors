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

import psutil, time

average = lambda x: sum(x) / float(len(x))


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
    work.insert(0, average(work))
    idle.insert(0, average(idle))
    return (time.time(), zip(work, idle))

def getCpuStats(last, ref):
    cpu = [ ]
    for unit in zip(last[1], ref[1]):
        work = unit[0][0] - unit[1][0]
        idle = unit[0][1] - unit[1][1]
        cpu.append(100.0 * work / (work + idle))
    return (last[0] - ref[0], cpu)


# Memory statistics: get RAM used
def getMemoryPercent():
    return psutil.virtual_memory().percent


# Network statistics
def getInstantIOStats():
    result = { }
    # IO details without loopback interface
    ioStats = psutil.net_io_counters(pernic=True)
    del ioStats['lo']
    for intf, ioStat in ioStats.items():
        result[intf] = (ioStat.bytes_recv, ioStat.bytes_sent)
    return (time.time(), result)

def getIOStats(last, ref):
    duration = last[0] - ref[0]
    ioStats = { }
    for intf, lastIOStat in last[1].items():
        if intf in ref[1].keys():
            refIOStat = ref[1][intf]
            recv_bytes = lastIOStat[0] - refIOStat[0]
            sent_bytes = lastIOStat[1] - refIOStat[1]
            # result in kilo bits per second (bytes / 1024 * 8)
            ioStats[intf] = (recv_bytes / duration / 128, sent_bytes / duration / 128)
    return (duration, ioStats)


# Process statistics
# TODO

