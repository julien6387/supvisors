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
    dummy_info = {'name': 'proc', 'group': 'appli', 'state': 10, 'start': 5, 'stop': 0,
                  'now': 10, 'pid': 1234, 'spawnerr': '', 'useless_key': 'useless_data',
                  'description': 'process dead'}
    assert extract_process_info(dummy_info) == {'name': 'proc', 'group': 'appli', 'state': 10, 'start': 5, 'stop': 0,
                                                'now': 10, 'pid': 1234, 'expected': True, 'spawnerr': '',
                                                'description': 'process dead'}
    # test with spawn error
    dummy_info['spawnerr'] = 'something'
    assert extract_process_info(dummy_info) == {'name': 'proc', 'group': 'appli', 'state': 10, 'start': 5, 'stop': 0,
                                                'now': 10, 'pid': 1234, 'expected': False, 'spawnerr': 'something',
                                                'description': 'process dead'}


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
