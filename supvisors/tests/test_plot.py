#!/usr/bin/python
# -*- coding: utf-8 -*-

# ======================================================================
# Copyright 2017 Julien LE CLEACH
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

import imghdr
import sys
import unittest


class StatisticsPlotTest(unittest.TestCase):
    """ Test case for the plot module. """

    def setUp(self):
        """ Skip the test if matplotlib is not installed. """
        try:
            import matplotlib
            matplotlib.__name__
        except ImportError:
            raise unittest.SkipTest('cannot test as optional matplotlib is not installed')

    def test_plot(self):
        """ Test a simple plot.
        Complex to test anything. Just check that there is no exception. """
        from supvisors.plot import StatisticsPlot
        from supvisors.viewimage import StatsImage
        plot = StatisticsPlot()
        self.assertEqual({}, plot.ydata)
        # add series of data
        plot.add_plot('dummy_title_1', 'unit_1', [1, 2, 3])
        plot.add_plot('dummy_title_2', 'unit_2', [10, 20, 30])
        self.assertDictEqual({('dummy_title_1', 'unit_1'): [1, 2, 3], ('dummy_title_2', 'unit_2'): [10, 20, 30]},
                             plot.ydata)
        # export image in buffer
        contents = StatsImage()
        plot.export_image(contents)
        # test that result is a PNG file
        self.assertEqual('png', imghdr.what('', h=contents.contents.getvalue()))

    def test_get_range(self):
        """ Test a simple plot.
        Complex to test anything. Just check that there is no exception. """
        from supvisors.plot import StatisticsPlot
        # first test
        min_range, max_range = StatisticsPlot.get_range([10, 50, 30, 90])
        self.assertAlmostEqual(2.0, min_range)
        self.assertAlmostEqual(118.0, max_range)
        # second test
        min_range, max_range = StatisticsPlot.get_range([0, 100])
        self.assertAlmostEqual(0.0, min_range)
        self.assertAlmostEqual(135.0, max_range)


def test_suite():
    return unittest.findTestCases(sys.modules[__name__])


if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
