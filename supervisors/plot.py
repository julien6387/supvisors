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

def createCpuMemPlot(cpuData, memData, imageContents):
    nbData = len(cpuData)
    if nbData > 0:
        # create X axis
        plt.figure(figsize=(6, 3))
        xData = [ x for x in range(len(cpuData)) ]
        # calculate max range
        maxY = getMaxRange(cpuData + memData)
        # create plot for CPU / RAM
        cpuLine, meanCpuLine = plotData(xData, cpuData, maxY,'CPU', '%')
        memLine, meanMemLine = plotData(xData, memData, maxY,'MEM', '%')
        # create the CPU legend
        cpuLegend = plt.legend(handles=[cpuLine, meanCpuLine], loc=2, fontsize='small', fancybox=True, shadow=True)
        # add the legend to the current axes
        plt.gca().add_artist(cpuLegend)
        # create the MEM legend
        plt.legend(handles=[memLine, meanMemLine], loc=1, fontsize='small', fancybox=True, shadow=True)
        # export image
        saveFile(imageContents)
        plt.close()

def createIoPlot(interface, ioData, imageContents):
    nbData = len(ioData[0])
    if nbData > 0:
        # create X axis
        plt.figure(figsize=(6, 3))
        xData = [ x for x in range(nbData) ]
        # calculate max range
        maxY = getMaxRange(ioData[0] + ioData[1])
        # create plots for IO
        recvLine, meanRecvLine = plotData(xData, ioData[0], maxY, interface + ' recv', 'kbit/s')
        sentLine, meanSentLine = plotData(xData, ioData[1], maxY, interface + ' sent', 'kbit/s')
        # create the CPU legend
        recvLegend = plt.legend(handles=[recvLine, meanRecvLine], loc=2, fontsize='small', fancybox=True, shadow=True)
        # add the legend to the current axes
        plt.gca().add_artist(recvLegend)
        # create the MEM legend
        plt.legend(handles=[sentLine, meanSentLine], loc=1, fontsize='small', fancybox=True, shadow=True)
        # export image
        saveFile(imageContents)
        plt.close()

def saveFile(imageContents):
    # save image to internal memory buffer
    plt.savefig(imageContents.getNewImage(), dpi=80, bbox_inches='tight', format='png')

def getMaxRange(lst):
    import math
    # legend need additional space
    return math.ceil(max(lst) * 1.35)

def plotData(xData, data, maxY, title, unit):
    # calculate average of data
    avg = mean(data)
    avgData = [ avg for _ in data ]
    plt.ylim([ 0, maxY ])
    # plot the data
    dataLine, = plt.plot(xData, data, label=title)
    # plot the mean line
    meanLine, = plt.plot(xData, avgData, label='Mean: {:.2f}{}'.format(avg, unit), linestyle='--', color=dataLine.get_color())
    return dataLine, meanLine


# unit test
if __name__ == "__main__":
    # from supervisors.plot import *
    cpuData = [ 28.2,  31.4,  29.7 ]
    memData = [ 85.2,  85.9,  86.5 ]
    createCpuMemPlot(cpuData, memData, 'cliche01')
