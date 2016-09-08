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

import math
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from supervisors.utils import getStats


# class to create statistics graph using matplotlib 
class StatisticsPlot(object):
    def __init__(self):
        plt.figure(figsize=(6, 3))
        self.yData = { }

    def addPlot(self, title, unit, yData):
        if len(yData) > 0:
            self.yData[(title, unit)] = yData

    def exportImage(self, imageContents):
        if self.yData:
            # calculate and apply max range
            allYData = [ ]
            map(allYData.extend, [yData for yData in self.yData.values()])
            plt.ylim(self.getRange(allYData))
            # create plots for each series of data
            for i, ((title, unit), yData) in enumerate(self.yData.items()):
                # create X axis
                xData = [ x for x in range(len(yData)) ]
                # get additional statistics
                avg, rate, (a, b), dev = getStats(yData)
                # plot the data
                dataLine, = plt.plot(xData, yData, label=title)
                plotColor = dataLine.get_color()
                # plot the mean line
                avgData = [ avg for _ in yData ]
                meanLine, = plt.plot(xData, avgData, label='Mean: {:.2f}{}'.format(avg, unit), linestyle='--', color=plotColor)
                if a is not None:
                    # plot the linear regression
                    plt.plot( [ xData[0], xData[-1] ], [ a * xData[0] + b,  a * xData[-1] + b], linestyle=':', color=plotColor)
                if dev is not None:
                    # plot the standard deviation
                    plt.fill_between(xData, avg-dev, avg+dev, facecolor=plotColor, alpha=.3)
                # create the legend
                legend = plt.legend(handles=[dataLine, meanLine], loc=i+1, fontsize='small', fancybox=True, shadow=True)
                # add the legend to the current axes
                plt.gca().add_artist(legend)
            # save image to internal memory buffer
            plt.savefig(imageContents.getNewImage(), dpi=80, bbox_inches='tight', format='png')
            # reset yData
            self.yData = { }
        # close plot
        plt.close()

    def getRange(self, lst):
        # legend need additional space
        minRange = math.floor(min(lst))
        maxRange = math.ceil(max(lst))
        range = maxRange - minRange
        return max(0, minRange - range * 0.1), maxRange + range * .35
