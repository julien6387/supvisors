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

from enum import Enum
from math import sqrt
from time import gmtime, localtime, strftime, time


class InternalEventHeaders(Enum):
    """ Enumeration class for the headers in messages between Listener and MainLoop. """
    TICK, PROCESS, STATISTICS, STATE = range(4)


class RemoteCommEvents:
    """ Strings used for remote communication between the Supvisors main loop and the listener. """
    SUPVISORS_AUTH = u'auth'
    SUPVISORS_EVENT = u'event'
    SUPVISORS_INFO = u'info'


class EventHeaders:
    """ Strings used as headers in messages between EventPublisher and Supvisors' Client. """
    SUPVISORS = u'supvisors'
    ADDRESS = u'address'
    APPLICATION = u'application'
    PROCESS_EVENT = u'event'
    PROCESS_STATUS = u'process'


# for deferred XML-RPC requests
class DeferredRequestHeaders(Enum):
    """ Enumeration class for the headers of deferred XML-RPC messages sent to MainLoop."""
    CHECK_NODE, ISOLATE_NODES, START_PROCESS, STOP_PROCESS, RESTART, SHUTDOWN, RESTART_ALL, SHUTDOWN_ALL = range(8)


def simple_localtime(now=None):
    """ Returns the local time as a string, without the date. """
    if now is None:
        now = time()
    return strftime("%H:%M:%S", localtime(now))


def simple_gmtime(now=None):
    """ Returns the UTC time as a string, without the date. """
    if now is None:
        now = time()
    return strftime("%H:%M:%S", gmtime(now))


# Keys of information kept from Supervisor
__Payload_Keys = ('name', 'group', 'state', 'start', 'stop', 'now', 'pid', 'description', 'spawnerr')


def extract_process_info(info):
    """ Returns a subset of Supervisor process information. """
    payload = {key: info[key] for key in __Payload_Keys}
    # expand information with 'expected' (deduced from spawnerr)
    payload['expected'] = not info['spawnerr']
    return payload


# simple functions
def mean(x):
    return sum(x) / float(len(x))


def srate(x, y):
    return 100.0 * x / y - 100.0 if y else float('inf')


def stddev(lst, avg):
    return sqrt(sum((x - avg) ** 2 for x in lst) / len(lst))


# linear regression
def get_linear_regression(xdata, ydata):
    """ Calculate the coefficients of the linear equation corresponding
    to the linear regression of a series of points. """
    try:
        import numpy
        return tuple(numpy.polyfit(xdata, ydata, 1))
    except ImportError:
        # numpy not available
        # try something approximate and simple
        datasize = len(xdata)
        sum_x = float(sum(xdata))
        sum_y = float(sum(ydata))
        sum_xx = float(sum(map(lambda x: x * x, xdata)))
        sum_products = float(sum([xdata[i] * ydata[i]
                                  for i in range(datasize)]))
        a = (sum_products - sum_x * sum_y / datasize) / (sum_xx - (sum_x * sum_x) / datasize)
        b = (sum_y - a * sum_x) / datasize
        return a, b


def get_simple_linear_regression(lst):
    """ Calculate the coefficients of the linear equation corresponding
    to the linear regression of a series of values. """
    # in Supvisors, Y data is periodic
    datasize = len(lst)
    return get_linear_regression([i for i in range(datasize)], lst)


# get statistics from data
def get_stats(lst):
    """ Calculate the following statistics from a series of points:
    - the mean value,
    - the instant rate between the two last values,
    - the coefficients of the linear regression,
    - the standard deviation. """
    rate, a, b, dev = (None,) * 4
    # calculate mean value
    avg = mean(lst)
    if len(lst) > 1:
        # calculate instant rate value between last 2 values
        rate = srate(lst[-1], lst[-2])
        # calculate slope value from linear regression of values
        a, b = get_simple_linear_regression(lst)
        # calculate standard deviation
        dev = stddev(lst, avg)
    return avg, rate, (a, b), dev
