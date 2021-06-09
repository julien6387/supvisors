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
import sys
import unittest

from unittest.mock import patch

from supvisors.tests.base import MockedSupvisors


class UtilsTest(unittest.TestCase):
    """ Test case for the utils module. """

    def setUp(self):
        """ Create a logger that stores log traces. """
        self.supvisors = MockedSupvisors()

    def test_localtime(self):
        """ Test the display of local time. """
        import time
        from supvisors.utils import simple_localtime
        # test with argument
        time_shift = time.timezone if time.gmtime().tm_isdst else time.altzone
        self.assertEqual('07:07:00', simple_localtime(1476947220.416198 + time_shift))
        # test without argument: just test output format
        self.assertRegex(simple_localtime(), r'\d\d:\d\d:\d\d')

    def test_gmtime(self):
        """ Test the display of gm time. """
        from supvisors.utils import simple_gmtime
        # test with argument
        self.assertEqual('07:07:00', simple_gmtime(1476947220.416198))
        # test without argument: just test output format
        self.assertRegex(simple_gmtime(), r'\d\d:\d\d:\d\d')

    def test_extract_process_info(self):
        """ Test the extraction of useful data from process info. """
        from supvisors.utils import extract_process_info
        # test with no spawn error
        dummy_info = {'name': 'proc', 'group': 'appli', 'state': 10, 'start': 5, 'stop': 0,
                      'now': 10, 'pid': 1234, 'spawnerr': '', 'useless_key': 'useless_data',
                      'description': 'process dead'}
        self.assertDictEqual({'name': 'proc', 'group': 'appli', 'state': 10, 'start': 5, 'stop': 0,
                              'now': 10, 'pid': 1234, 'expected': True, 'spawnerr': '',
                              'description': 'process dead'},
                             extract_process_info(dummy_info))
        # test with spawn error
        dummy_info['spawnerr'] = 'something'
        self.assertDictEqual({'name': 'proc', 'group': 'appli', 'state': 10, 'start': 5, 'stop': 0,
                              'now': 10, 'pid': 1234, 'expected': False, 'spawnerr': 'something',
                              'description': 'process dead'},
                             extract_process_info(dummy_info))

    def test_statistics_functions(self):
        """ Test the simple statistics. """
        from supvisors.utils import mean, srate, stddev
        # test mean lambda
        self.assertAlmostEqual(4, mean([2, 5, 5]))
        with self.assertRaises(ZeroDivisionError):
            self.assertAlmostEqual(0, mean([]))
        # test srate lambda
        self.assertAlmostEqual(-50, srate(2, 4))
        self.assertAlmostEqual(100, srate(4, 2))
        self.assertAlmostEqual(float('inf'), srate(4, 0))
        # test stddev lambda
        self.assertAlmostEqual(math.sqrt(2), stddev([2, 5, 4, 6, 3], 4))

    def test_linear_regression_numpy(self):
        """ Test the linear regression using numpy (if installed). """
        # test that numpy is installed
        try:
            import numpy
            numpy.__name__
        except ImportError:
            raise unittest.SkipTest('cannot test as optional numpy is not installed')
        # perform the test with numpy
        from supvisors.utils import get_linear_regression, get_simple_linear_regression
        xdata = [2, 4, 6, 8, 10, 12]
        ydata = [3, 4, 5, 6, 7, 8]
        # test linear regression
        a, b = get_linear_regression(xdata, ydata)
        self.assertAlmostEqual(0.5, a)
        self.assertAlmostEqual(2.0, b)
        # test simple linear regression
        a, b = get_simple_linear_regression(ydata)
        self.assertAlmostEqual(1.0, a)
        self.assertAlmostEqual(3.0, b)

    @patch.dict('sys.modules', {'numpy': None})
    def test_linear_regression(self, *args, **keywargs):
        """ Test the linear regression without using numpy. """
        from supvisors.utils import get_linear_regression, get_simple_linear_regression
        xdata = [2, 4, 6, 8, 10, 12]
        ydata = [3, 4, 5, 6, 7, 8]
        # test linear regression
        a, b = get_linear_regression(xdata, ydata)
        self.assertAlmostEqual(0.5, a)
        self.assertAlmostEqual(2.0, b)
        # test simple linear regression
        a, b = get_simple_linear_regression(ydata)
        self.assertAlmostEqual(1.0, a)
        self.assertAlmostEqual(3.0, b)

    def test_statistics(self):
        """ Test the statistics function. """
        from supvisors.utils import get_stats
        ydata = [2, 3, 4, 5, 6]
        avg, rate, (a, b), dev = get_stats(ydata)
        self.assertAlmostEqual(4, avg)
        self.assertAlmostEqual(20, rate)
        self.assertAlmostEqual(1, a)
        self.assertAlmostEqual(2, b)
        self.assertAlmostEqual(math.sqrt(2), dev)


def test_suite():
    return unittest.findTestCases(sys.modules[__name__])


if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
