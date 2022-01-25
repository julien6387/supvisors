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

import math
import pytest
import re

from time import timezone, altzone

from supvisors.utils import *


def test_localtime():
    """ Test the display of local time. """
    # test with argument
    time_shift = timezone if gmtime().tm_isdst else altzone
    assert simple_localtime(1476947220.416198 + time_shift) == '07:07:00'
    # test without argument: just test output format
    assert re.match(r'\d\d:\d\d:\d\d', simple_localtime())


def test_gmtime():
    """ Test the display of gm time. """
    # test with argument
    assert simple_gmtime(1476947220.416198) == '07:07:00'
    # test without argument: just test output format
    assert re.match(r'\d\d:\d\d:\d\d', simple_gmtime())


def test_extract_process_info():
    """ Test the extraction of useful data from process info. """
    # test with no spawn error
    dummy_info = {'name': 'proc', 'group': 'appli', 'state': 10, 'statename': 'STARTING', 'start': 5, 'stop': 0,
                  'now': 10, 'pid': 1234, 'spawnerr': '', 'useless_key': 'useless_data',
                  'description': 'process dead'}
    assert extract_process_info(dummy_info) == {'name': 'proc', 'group': 'appli', 'state': 10, 'statename': 'STARTING',
                                                'start': 5, 'stop': 0,
                                                'now': 10, 'pid': 1234, 'expected': True, 'spawnerr': '',
                                                'description': 'process dead'}
    # test with spawn error
    dummy_info['spawnerr'] = 'something'
    assert extract_process_info(dummy_info) == {'name': 'proc', 'group': 'appli', 'state': 10, 'statename': 'STARTING',
                                                'start': 5, 'stop': 0,
                                                'now': 10, 'pid': 1234, 'expected': False, 'spawnerr': 'something',
                                                'description': 'process dead'}


def test_server_url():
    """ Test the SupervisorServerUrl class. """
    # test without authentication
    env = {'SUPERVISOR_SERVER_URL': 'http://localhost:60000'}
    srv_url = SupervisorServerUrl(env)
    assert srv_url.env is env
    assert srv_url.parsed_url.geturl() == 'http://localhost:60000'
    assert srv_url.authentication == ''
    # without port
    srv_url.update_url('cliche81')
    assert env['SUPERVISOR_SERVER_URL'] == 'http://cliche81:60000'
    assert srv_url.parsed_url.geturl() == 'http://cliche81:60000'
    # with port
    srv_url.update_url('cliche82', 61000)
    assert env['SUPERVISOR_SERVER_URL'] == 'http://cliche82:61000'
    assert srv_url.parsed_url.geturl() == 'http://cliche82:61000'
    # test with authentication
    env = {'SUPERVISOR_SERVER_URL': 'http://user:password@localhost:60000'}
    srv_url = SupervisorServerUrl(env)
    assert srv_url.env is env
    assert srv_url.parsed_url.geturl() == 'http://user:password@localhost:60000'
    assert srv_url.authentication == 'user:password@'
    # without port
    srv_url.update_url('cliche81')
    assert env['SUPERVISOR_SERVER_URL'] == 'http://user:password@cliche81:60000'
    assert srv_url.parsed_url.geturl() == 'http://user:password@cliche81:60000'
    # with port
    srv_url.update_url('cliche82', 61000)
    assert env['SUPERVISOR_SERVER_URL'] == 'http://user:password@cliche82:61000'
    assert srv_url.parsed_url.geturl() == 'http://user:password@cliche82:61000'


def test_statistics_functions():
    """ Test the simple statistics. """
    # test mean lambda
    assert pytest.approx(mean([2, 5, 5])) == 4
    with pytest.raises(ZeroDivisionError):
        assert pytest.approx(mean([])) == 0
    # test srate lambda
    assert pytest.approx(srate(2, 4)) == -50
    assert pytest.approx(srate(4, 2)) == 100
    assert pytest.approx(srate(4, 0)) == float('inf')
    # test stddev lambda
    assert pytest.approx(stddev([2, 5, 4, 6, 3], 4)) == math.sqrt(2)


def test_bit_manipulation():
    """ Test the bit manipulation functions. """
    ba = bytearray(3)
    for bit in range(3*8):
        assert get_bit(ba, bit) == 0
    for bit in range(3*4):
        set_bit(ba, 2*bit, 1)
    assert ba.hex() == '555555'
    for bit in range(3*4):
        set_bit(ba, 2*bit, 0)
    assert ba.hex() == '000000'


def test_linear_regression_numpy():
    """ Test the linear regression using numpy (if installed). """
    pytest.importorskip('numpy')
    # perform the test with numpy
    xdata = [2, 4, 6, 8, 10, 12]
    ydata = [3, 4, 5, 6, 7, 8]
    # test linear regression
    a, b = get_linear_regression(xdata, ydata)
    assert pytest.approx(a) == 0.5
    assert pytest.approx(b) == 2.0
    # test simple linear regression
    a, b = get_simple_linear_regression(ydata)
    assert pytest.approx(a) == 1.0
    assert pytest.approx(b) == 3.0


def test_linear_regression(mocker):
    """ Test the linear regression without using numpy. """
    mocker.patch.dict('sys.modules', {'numpy': None})
    xdata = [2, 4, 6, 8, 10, 12]
    ydata = [3, 4, 5, 6, 7, 8]
    # test linear regression
    a, b = get_linear_regression(xdata, ydata)
    assert pytest.approx(a) == 0.5
    assert pytest.approx(b) == 2.0
    # test simple linear regression
    a, b = get_simple_linear_regression(ydata)
    assert pytest.approx(a) == 1.0
    assert pytest.approx(b) == 3.0


def test_statistics():
    """ Test the statistics function. """
    ydata = [2, 3, 4, 5, 6]
    avg, rate, (a, b), dev = get_stats(ydata)
    assert pytest.approx(avg) == 4
    assert pytest.approx(rate) == 20
    assert pytest.approx(a) == 1
    assert pytest.approx(b) == 2
    assert pytest.approx(dev) == math.sqrt(2)
