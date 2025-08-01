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

import re
import time
from datetime import timedelta
from math import sqrt
from typing import Dict, List
from urllib.parse import urlparse

from .ttypes import Payload

# Constants
# TICK period in seconds for internal Supvisors heartbeat
TICK_PERIOD = 5

# special characters used in rules
WILDCARD = '*'
HASHTAG = '#'
ATSIGN = '@'


def simple_localtime(now=None):
    """ Returns the local time as a string, without the date. """
    if now is None:
        now = time.time()
    return time.strftime("%H:%M:%S", time.localtime(now))


def simple_duration(duration: float):
    """ Returns the duration as days / hours / minutes / seconds. """
    return str(timedelta(seconds=int(duration)))


# Keys of information kept from Supervisor
__Payload_Keys = ('name', 'group', 'state', 'statename', 'start', 'stop', 'now', 'pid', 'description', 'spawnerr')


def extract_process_info(info: Payload) -> Payload:
    """ Returns a subset of Supervisor process information. """
    payload = {key: info[key] for key in __Payload_Keys if key in info}
    # expand information with 'expected' (deduced from spawnerr)
    payload['expected'] = not info['spawnerr']
    return payload


# parse the Server URL of Supervisor
class SupervisorServerUrl:
    """ Store and update the environment for RPC interfaces. """

    def __init__(self, env: Dict):
        """ Parse the Supervisor server URL for later modification. """
        self.env: Dict = env.copy()
        # get the possible authentication part
        parsed_url = urlparse(env['SUPERVISOR_SERVER_URL'])
        self.authentication = ''
        if parsed_url.username:
            self.authentication = parsed_url.username
            if parsed_url.password:
                self.authentication += f':{parsed_url.password}'
            self.authentication += '@'

    def update_url(self, hostname: str, port: int):
        """ Update the URL by changing the hostname and the port. """
        self.env['SUPERVISOR_SERVER_URL'] = f'http://{self.authentication}{hostname}:{port}'


# simple functions
def mean(x) -> float:
    """ Calculate the mean value of a list of values. """
    return sum(x) / float(len(x))


def srate(x, y) -> float:
    """ Calculate the instant rate between two values. """
    return 100.0 * x / y - 100.0 if y else float('inf')


def stddev(lst, avg) -> float:
    """ Calculate the standard deviation of a list of values (Bessel correction excluded). """
    return sqrt(sum((x - avg) ** 2 for x in lst) / len(lst))


# bit manipulation
def get_bit(data, num):
    """ Get the value of a bit in a byte. """
    base, shift = int(num // 8), int(num % 8)
    return (data[base] >> shift) & 0x1


def set_bit(data, num, value):
    """ Set the value of a bit in a byte. """
    base, shift = int(num // 8), int(num % 8)
    if value:
        data[base] |= 0x1 << shift
    else:
        data[base] &= ~(0x1 << shift)


# to display small float values
def get_small_value(value) -> str:
    """ Segregate small values from 0.
    For small negative values, the display is already suitable. """
    if 0 < value < 0.005:
        return f'+0.00'
    return f'{value:.2f}'


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


# get statistics from data
def get_stats(xdata, ydata):
    """ Calculate the following statistics from a series of points:
    - the mean value,
    - the instant rate between the two last values,
    - the coefficients of the linear regression,
    - the standard deviation. """
    rate, a, b, dev = (None,) * 4
    # calculate mean value
    avg = mean(ydata)
    if len(ydata) > 1:
        # calculate instant rate value between last 2 values
        rate = srate(ydata[-1], ydata[-2])
        # calculate slope value from linear regression of values
        a, b = get_linear_regression(xdata, ydata)
        # calculate standard deviation
        dev = stddev(ydata, avg)
    return avg, rate, (a, b), dev


# docstring parsing
SUPERVISOR_PARAM_FORMAT = re.compile(r'^@param\s+(?P<type>[a-z]+)\s+(?P<name>\w+)\s+(?P<desc>.*)$')
SUPERVISOR_RETURN_FORMAT = re.compile(r'^@return\s+(?P<type>[a-z]+)(\s+(?P<name>\w+)(\s+(?P<desc>.*))?)?$')

TYPE_FORMAT = r'(?P<type>[\w\[\], ]+)'
SUPVISORS_PARAM_FORMAT = re.compile(rf'^:param\s+{TYPE_FORMAT}\s+(?P<name>\w+):\s+(?P<desc>.*)$')
SUPVISORS_RETURN_FORMAT = re.compile(r'^:return:\s+(?P<desc>.*)$')
SUPVISORS_RTYPE_FORMAT = re.compile(rf'^:rtype:\s+{TYPE_FORMAT}$')
SUPVISORS_RAISE_FORMAT = re.compile(r'^:raises\s+(?P<exc>\w+):\s+(?P<desc>.*)$')


def parse_docstring(comment: str) -> List:
    """ Extract information from the docstring.
    Return the same structure as supervisor.xmlrpc.gettags. """
    description = [0, None, None, None, []]
    parameters = {}
    returns = None
    raises = {}
    # deal with description first
    current_struct = description
    current_desc = description[4]
    # reading fields
    for idx, line in enumerate(comment.split('\n')):
        stripped_line = line.strip()
        if not stripped_line:
            continue
        match = False
        # deal with parameters
        for fmt in [SUPERVISOR_PARAM_FORMAT, SUPVISORS_PARAM_FORMAT]:
            result = fmt.match(stripped_line)
            if result:
                match = True
                param_name = result.group('name')
                current_struct = parameters[param_name] = [idx, 'param', result.group('type'), param_name,
                                                           [result.group('desc')]]
        # deal with Supervisor return
        result = SUPERVISOR_RETURN_FORMAT.match(stripped_line)
        if result:
            match = True
            # Supervisor does not always provide a return name (e.g. signalProcess)
            name = result.group('name') or ''
            # Supervisor does not always provide a return description (e.g. getPID)
            desc = result.group('desc')
            returns = [idx, 'return', result.group('type'), name, [desc] if desc else []]
            current_struct = returns
        # deal with Supvisors return
        result = SUPVISORS_RETURN_FORMAT.match(stripped_line)
        if result:
            match = True
            if returns:
                returns[4] = [result.group('desc')]
            else:
                returns = [idx, 'return', None, None, [result.group('desc')]]
            current_struct = returns
        result = SUPVISORS_RTYPE_FORMAT.match(stripped_line)
        if result:
            match = True
            if returns:
                returns[2] = result.group('type')
            else:
                returns = [idx, 'return', result.group('type'), None, []]
            current_struct = returns
        # deal with Supvisors raises
        result = SUPVISORS_RAISE_FORMAT.match(stripped_line)
        if result:
            match = True
            exc = result.group('exc')
            current_struct = raises[exc] = [idx, 'raises', exc, None, [result.group('desc')]]
        # deal with description
        if match:
            current_desc = current_struct[4]
        else:
            current_desc.append(stripped_line)
    # return as gettags (exceptions not used)
    description[4] = '\n'.join(description[4])
    returns[4] = '\n'.join(returns[4])
    for param in parameters.values():
        param[4] = '\n'.join(param[4])
    return [tuple(description)] + [tuple(param) for param in parameters.values()] + [tuple(returns)]
