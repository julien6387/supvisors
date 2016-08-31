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

from supervisors.utils import mean

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def createCpuMemPlot(cpuData, memData, fileName):
    # create dummy X axis
    plt.figure(figsize=(6, 3))
    xData = [ x for x in range(len(cpuData)) ]
    # create plot for CPU / RAM
    # TODO: mix all CPU ?
    cpuLine, meanCpuLine = plotPercentData(xData, cpuData, 'CPU')
    memLine, meanMemLine = plotPercentData(xData, memData, 'MEM')
    # create the CPU legend
    cpuLegend = plt.legend(handles=[cpuLine, meanCpuLine], loc=2, fontsize='small', fancybox=True, shadow=True)
    # add the legend to the current axes
    plt.gca().add_artist(cpuLegend)
    # create the MEM legend
    plt.legend(handles=[memLine, meanMemLine], loc=1, fontsize='small', fancybox=True, shadow=True)
    # export image
    saveFile(fileName)
    plt.close()

def createIoPlot(ioData, fileName):
    # create plot for io
    lines =[ ]
    for intf, yData in ioData.items():
        # create dummy X axis
        xData = [ x for x in range(len(yData)) ]
        recvLine, = plotPercentData(xData, yData, intf)
        sentLine, = plotPercentData(xData, yData, intf)
        lines.expand([ recvLine,  sentLine ])
    # create the CPU legend
    plt.legend(loc='upper center', fancybox=True, shadow=True)
    # export image
    saveFile(fileName)
    plt.close()

def saveFile(fileName):
    # FIXME: find either a directory that is visible to HTTP server or a way to avoid an intermediate file
    from os import path
    here = path.abspath(path.dirname(__file__))
    filePath = path.join(here, fileName)
    plt.savefig(filePath, dpi=80, bbox_inches='tight')

def plotPercentData(xData, data, title):
    # calculate average of data
    avg = mean(data)
    avgData = [ avg for _ in data ]
    # calculate max range
    import math
    maxY = math.ceil(max(data) / 10 + 2.5) * 10
    plt.ylim([ 0, maxY ])
    # plot the data
    dataLine, = plt.plot(xData, data, label=title)
    # plot the mean line
    meanLine, = plt.plot(xData, avgData, label='Mean: {0:.2f}%'.format(avg), linestyle='--', color=dataLine.get_color())
    return dataLine, meanLine


# unit test
if __name__ == "__main__":
    # from supervisors.plot import createAddressPlot
    cpuData = [ 28.2,  31.4,  29.7 ]
    memData = [ 85.2,  85.9,  86.5 ]
    createAddressPlot(cpuData, memData, 'cliche01')
