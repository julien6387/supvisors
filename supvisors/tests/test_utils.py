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
from time import timezone, altzone

import pytest
from supervisor.rpcinterface import SupervisorNamespaceRPCInterface
from supervisor.xmlrpc import gettags

from supvisors.rpcinterface import RPCInterface
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
    env = {'SUPERVISOR_SERVER_URL': 'http://localhost:60000', 'DUMMY': 'dummy'}
    srv_url = SupervisorServerUrl(env)
    assert srv_url.env == env
    assert srv_url.authentication == ''
    srv_url.update_url('10.0.0.1', 7777)
    assert srv_url.env == {'SUPERVISOR_SERVER_URL': 'http://10.0.0.1:7777', 'DUMMY': 'dummy'}
    # test with authentication
    env = {'SUPERVISOR_SERVER_URL': 'http://user:password@localhost:60000', 'DUMMY': 'dummy'}
    srv_url = SupervisorServerUrl(env)
    assert srv_url.env == env
    assert srv_url.authentication == 'user:password@'
    srv_url.update_url('10.0.0.1', 7777)
    assert srv_url.env == {'SUPERVISOR_SERVER_URL': 'http://user:password@10.0.0.1:7777', 'DUMMY': 'dummy'}


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
    for bit in range(3 * 8):
        assert get_bit(ba, bit) == 0
    for bit in range(3 * 4):
        set_bit(ba, 2 * bit, 1)
    assert ba.hex() == '555555'
    for bit in range(3 * 4):
        set_bit(ba, 2 * bit, 0)
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


def test_linear_regression(mocker):
    """ Test the linear regression without using numpy. """
    mocker.patch.dict('sys.modules', {'numpy': None})
    xdata = [2, 4, 6, 8, 10, 12]
    ydata = [3, 4, 5, 6, 7, 8]
    # test linear regression
    a, b = get_linear_regression(xdata, ydata)
    assert pytest.approx(a) == 0.5
    assert pytest.approx(b) == 2.0


def test_statistics():
    """ Test the statistics function. """
    xdata = [2, 4, 6, 8, 10]
    ydata = [2, 3, 4, 5, 6]
    avg, rate, (a, b), dev = get_stats(xdata, ydata)
    assert pytest.approx(avg) == 4
    assert pytest.approx(rate) == 20
    assert pytest.approx(a) == 0.5
    assert pytest.approx(b) == 1
    assert pytest.approx(dev) == math.sqrt(2)


def test_parse_docstring_supervisor():
    """ Test the parse_docstring function with a Supervisor docstring.
    Just test that the result is strictly identical to Supervisor gettags. """
    # test with all as expected
    result = parse_docstring(SupervisorNamespaceRPCInterface.tailProcessStderrLog.__doc__)
    assert result == gettags(SupervisorNamespaceRPCInterface.tailProcessStderrLog.__doc__)
    # test with return no desc
    result = parse_docstring(SupervisorNamespaceRPCInterface.getPID.__doc__)
    assert result == gettags(SupervisorNamespaceRPCInterface.getPID.__doc__)
    # test with return no name + no desc
    result = parse_docstring(SupervisorNamespaceRPCInterface.signalProcess.__doc__)
    assert result == gettags(SupervisorNamespaceRPCInterface.signalProcess.__doc__)
    # test with double quotes in description
    result = parse_docstring(SupervisorNamespaceRPCInterface.sendRemoteCommEvent.__doc__)
    assert result == gettags(SupervisorNamespaceRPCInterface.sendRemoteCommEvent.__doc__)


def test_parse_docstring_supvisors():
    """ Test the parse_docstring function with a Supvisors docstring. """
    # test standard description
    expected = [(0, None, None, None,
                 'Start the *Managed* application named ``application_name`` iaw the strategy and the rules file.\n'
                 "To start *Unmanaged* applications, use ``supervisor.start('group:*')``."),
                (3, 'param', 'StartingStrategies', 'strategy', 'the strategy used to choose a **Supvisors** instance,\n'
                                                               'as a string or as a value.'),
                (5, 'param', 'str', 'application_name', 'the name of the application.'),
                (6, 'param', 'bool', 'wait',
                 'if ``True``, wait for the application to be fully started before returning.'),
                (7, 'return', 'bool', None, 'always ``True`` unless error or nothing to start.')]
    result = parse_docstring(RPCInterface.start_application.__doc__)
    assert result == expected
    # test with types including brackets
    expected = [(0, None, None, None,
                 'Change the logger level for the local **Supvisors** instance.\n'
                 'If **Supvisors** logger is configured as ``AUTO``, this will impact the Supervisor logger too.'),
                (3, 'param', 'Union[str, int]', 'level_param', 'the new logger level, as a string or as a value.'),
                (4, 'return', 'bool', None, 'always ``True`` unless error.')]
    result = parse_docstring(RPCInterface.change_log_level.__doc__)
    assert result == expected
    # test with rtype before return
    comment = """ Return the version of the RPC API used by **Supvisors**.

        :rtype: str
        :return: the **Supvisors** version.
        """
    expected = [(0, None, None, None,
                 'Return the version of the RPC API used by **Supvisors**.'),
                (2, 'return', 'str', None, 'the **Supvisors** version.')]
    result = parse_docstring(comment)
    assert result == expected
