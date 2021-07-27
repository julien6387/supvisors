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
import pytest

pytest.importorskip('matplotlib', reason='cannot test as optional matplotlib is not installed')

from supvisors.plot import *
from supvisors.viewimage import StatsImage


def test_plot():
    """ Test a simple plot.
    Complex to test anything. Just check that there is no exception. """
    plot = StatisticsPlot()
    assert plot.ydata == {}
    # add series of data
    plot.add_plot('dummy_title_1', 'unit_1', [1, 2, 3])
    plot.add_plot('dummy_title_2', 'unit_2', [10, 20, 30])
    assert plot.ydata == {('dummy_title_1', 'unit_1'): [1, 2, 3], ('dummy_title_2', 'unit_2'): [10, 20, 30]}
    # export image in buffer
    contents = StatsImage()
    plot.export_image(contents)
    # test that result is a PNG file
    assert imghdr.what('', h=contents.contents.getvalue()) == 'png'


def test_get_range():
    """ Test a simple plot.
    Complex to test anything. Just check that there is no exception. """
    # first test
    min_range, max_range = StatisticsPlot.get_range([10, 50, 30, 90])
    assert pytest.approx(min_range) == 2.0
    assert pytest.approx(max_range) == 118.0
    # second test
    min_range, max_range = StatisticsPlot.get_range([0, 100])
    assert pytest.approx(min_range) == 0.0
    assert pytest.approx(max_range) == 135.0