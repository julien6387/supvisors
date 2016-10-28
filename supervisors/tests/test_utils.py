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

import sys
import unittest

from supervisors.tests.base import DummySupervisors


class UtilsTest(unittest.TestCase):
    """ Test case for the utils module. """

    def setUp(self):
        """ Create a logger that stores log traces. """
        self.supervisors = DummySupervisors()

    def test_enum(self):
        """ Test the values set at construction. """
        from supervisors.utils import enumeration_tools
        @enumeration_tools
        class DummyEnum:
            ENUM_1, ENUM_2, ENUM_3 = range(3)
        # test _to_string
        self.assertEqual('ENUM_1', DummyEnum._to_string(DummyEnum.ENUM_1))
        self.assertEqual('ENUM_2', DummyEnum._to_string(DummyEnum.ENUM_2))
        self.assertEqual('ENUM_3', DummyEnum._to_string(DummyEnum.ENUM_3))
        self.assertEqual('ENUM_1', DummyEnum._to_string(0))
        self.assertEqual('ENUM_2', DummyEnum._to_string(1))
        self.assertEqual('ENUM_3', DummyEnum._to_string(2))
        self.assertIsNone(DummyEnum._to_string(-1))
        # test _from_string
        self.assertEqual(DummyEnum.ENUM_1, DummyEnum._from_string('ENUM_1'))
        self.assertEqual(DummyEnum.ENUM_2, DummyEnum._from_string('ENUM_2'))
        self.assertEqual(DummyEnum.ENUM_3, DummyEnum._from_string('ENUM_3'))
        self.assertIsNone(DummyEnum._from_string('ENUM_0'))
        # test _values
        self.assertListEqual([DummyEnum.ENUM_1, DummyEnum.ENUM_2, DummyEnum.ENUM_3], sorted(DummyEnum._values()))
        # test _strings
        self.assertListEqual(['ENUM_1', 'ENUM_2', 'ENUM_3'], sorted(DummyEnum._strings()))

    def test_shortcut(self):
        """ Test the values set at construction. """
        from supervisors.utils import supervisors_short_cuts
        # test with existing attributes
        supervisors_short_cuts(self, ['address_mapper', 'deployer', 'fsm', 'logger', 'requester', 'statistician'])
        self.assertIs(self.address_mapper, self.supervisors.address_mapper)
        self.assertIs(self.fsm, self.supervisors.fsm)
        self.assertIs(self.statistician, self.supervisors.statistician)
        self.assertIs(self.requester, self.supervisors.requester)
        self.assertIs(self.deployer, self.supervisors.deployer)
        self.assertIs(self.logger, self.supervisors.logger)
        # test with unknown attributes
        with self.assertRaises(AttributeError):
            supervisors_short_cuts(self, ['addresser', 'logging'])

    def test_localtime(self):
        """ Test the values set at construction. """
        import time
        from supervisors.utils import simple_localtime
        time_shift = time.timezone if time.gmtime().tm_isdst else time.altzone
        self.assertEqual('07:07:00', simple_localtime(1476947220.416198 + time_shift))

    def test_gmtime(self):
        """ Test the values set at construction. """
        from supervisors.utils import simple_gmtime
        self.assertEqual('07:07:00', simple_gmtime(1476947220.416198))

    def test_statistics_functions(self):
        """ Test the values set at construction. """
        import math
        from supervisors.utils import mean, srate, stddev
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

    def test_linear_regression(self):
        """ Test the values set at construction. """
        from supervisors.utils import get_linear_regression, get_simple_linear_regression
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
        """ Test the values set at construction. """
        import math
        from supervisors.utils import get_stats
        ydata = [2, 3, 4, 5, 6]
        avg, rate, (a,  b), dev = get_stats(ydata)
        self.assertAlmostEqual(4, avg)
        self.assertAlmostEqual(20, rate)
        self.assertAlmostEqual(1, a)
        self.assertAlmostEqual(2, b)
        self.assertAlmostEqual(math.sqrt(2), dev)


def test_suite():
    return unittest.findTestCases(sys.modules[__name__])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')

