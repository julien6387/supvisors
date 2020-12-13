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
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from supvisors.utils import get_stats


# class to create statistics graph using matplotlib
class StatisticsPlot(object):
    """ Class used to export statistics data into a PNG graph. """

    def __init__(self):
        """ Initialization of the plot. """
        plt.figure(figsize=(6, 3), dpi=90)
        self.ydata = {}

    def add_plot(self, title, unit, ydata):
        """ Add a defined series of values to the plot. """
        if len(ydata) > 0:
            self.ydata[title, unit] = ydata

    def export_image(self, image_contents):
        """ Write curves into a PNG image. """
        if self.ydata:
            # calculate and apply max range on all sub-lists
            all_ydata = []
            for ydata in self.ydata.values():
                all_ydata.extend(ydata)
            plt.ylim(self.get_range(all_ydata))
            # create plots for each series of data
            for i, ((title, unit), ydata) in enumerate(self.ydata.items()):
                # create X axis
                xdata = [x for x in range(len(ydata))]
                # get additional statistics
                avg, rate, (a, b), dev = get_stats(ydata)
                # plot the data
                data_line, = plt.plot(xdata, ydata, label=title)
                plot_color = data_line.get_color()
                # plot the mean line
                avg_data = [avg, ] * len(ydata)
                mean_line, = plt.plot(xdata, avg_data,
                                      label='Mean: {:.2f}{}'.format(avg, unit),
                                      linestyle='--', color=plot_color)
                if a is not None:
                    # plot the linear regression
                    plt.plot([xdata[0], xdata[-1]],
                             [a * xdata[0] + b, a * xdata[-1] + b],
                             linestyle=':', color=plot_color)
                if dev is not None:
                    # plot the standard deviation
                    plt.fill_between(xdata, avg - dev, avg + dev,
                                     facecolor=plot_color, alpha=.3)
                # create the legend
                legend = plt.legend(handles=[data_line, mean_line], loc=i + 1,
                                    fontsize='small', fancybox=True, shadow=True)
                # add the legend to the current axes
                plt.gca().add_artist(legend)
            # save image to internal memory buffer
            # supported formats: eps, pdf, pgf, png, ps, raw, rgba, svg, svgz
            plt.savefig(image_contents.new_image(),
                        bbox_inches='tight', format='png')
            # reset yData
            self.ydata = {}
        # close plot
        plt.close()

    @staticmethod
    def get_range(lst):
        """ Return a custom range from a series of values.
        Min range is 0.
        Range is at least 1.
        Max range is increased to let additional space for legend. """
        min_range = math.floor(min(lst))
        max_range = math.ceil(max(lst))
        full_range = max(1, max_range - min_range)
        return max(0.0, min_range - full_range * 0.1), max_range + full_range * .35
