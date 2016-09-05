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

# strings used as headers in messages between Listener and MainLoop
TickHeader = u'tick'
ProcessHeader = u'process'
StatisticsHeader = u'statistics'

# strings used as headers in messages between EventPublisher and Supervisors' Client
SupervisorsStatusHeader = u'supervisors'
RemoteStatusHeader = u'remote'
ApplicationStatusHeader = u'application'
ProcessStatusHeader = u'process'


# used to convert enumeration-like value to string and vice-versa
def enumToString(dico,  idxEnum):
    return next((name for name, value in dico.items() if value == idxEnum),  None)

def stringToEnum(dico,  strEnum):
    return next((value for name, value in dico.items() if name == strEnum),  None)

def enumValues(dico):
    return [ y for (x, y) in dico.items() if not x.startswith('__') ]

def enumStrings(dico):
    return [ x for x in dico.keys() if not x.startswith('__') ]


# return time without date
def simpleTime(now=None):
    import time
    if now is None: now = time.time()
    return time.strftime("%H:%M:%S", time.localtime(now))


# simple lambda functions
mean = lambda x: sum(x) / float(len(x))
slope = lambda x, y: 100.0 * x / y - 100.0 if y else float('inf')
stddev = lambda lst, avg: (sum((x - avg)**2 for x in lst) / len(lst))**.5


# get statistics from data
def getStats(lst):
    slp = dev = None
    # calculate mean value
    avg = mean(lst)
    if len(lst) > 1:
        # calculate slope value between last 2 values
        slp = slope(lst[-1], lst[-2])
        # calculate standard deviation
        dev = stddev(lst, avg)
    return avg, slp, dev

