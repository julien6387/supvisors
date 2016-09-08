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

import urllib

from supervisor.options import make_namespec
from supervisor.web import StatusView
from supervisor.xmlrpc import RPCError

from supervisors.plot import StatisticsPlot
from supervisors.remote import remoteStateToString
from supervisors.utils import getStats, simpleLocalTime, supervisors_short_cuts
from supervisors.viewhandler import ViewHandler
from supervisors.viewimage import addressImageContents
from supervisors.webutils import *


# Supervisors address page
class AddressView(StatusView, ViewHandler):
    # Name of the HTML page
    pageName = 'address.html'

    def __init__(self, context):
        StatusView.__init__(self, context)
        self.supervisors = self.context.supervisord.supervisors
        supervisors_short_cuts(self, ['logger'])
        self.address = self.supervisors.address_mapper.local_address

    def render(self):
        """ Method called by Supervisor to handle the rendering of the Supervisors Address page """
        return self.writePage()

    def writeNavigation(self, root):
        """ Rendering of the navigation menu with selection of the current address """
        self.writeNav(root, address=self.address)

    def writeHeader(self, root):
        """ Rendering of the header part of the Supervisors Address page """
        # set address name
        elt = root.findmeld('address_mid')
        if self.supervisors.context.is_master:
            elt.attrib['class'] = 'master'
        elt.content(self.address)
        # set address state
        remote = self.supervisors.context.remotes[self.address]
        elt = root.findmeld('state_mid')
        elt.content(remoteStateToString(remote.state))
        # set loading
        elt = root.findmeld('percent_mid')
        elt.content('{}%'.format(self.supervisors.context.getLoading(self.address)))
        # set last tick date: remoteTime and localTime should be identical since self is running on the 'remote' address
        elt = root.findmeld('date_mid')
        elt.content(simpleLocalTime(remote.remoteTime))
        # write periods of statistics
        self.writePeriods(root)

    def writeContents(self, root):
        """ Rendering of the contents part of the page """
        self.writeProcessTable(root)
        self.writeStatistics(root)

    def writeStatistics(self, root):
        """ Rendering of the statistics part of the page """
        self.writeAddressStatistics(root)
        self.writeProcessStatistics(root)

    def getAddressStats(self):
        """ Get the statistics structure related to the local address and the period selected """
        return self.supervisors.statistician.data[self.address][ViewHandler.periodStats]

    def getProcessStats(self, namespec):
        """ Get the statistics structure related to the local address and the period selected """
        stats = self.getAddressStats()
        if namespec in stats.proc.keys():
            return stats.proc[namespec]

    def writeAddressStatistics(self, root):
        """ Rendering of tables and figures for address statistics """
        # position to stats element
        statsElt = root.findmeld('stats_div_mid')
        # get data from statistics module iaw period selection
        statsInstance = self.getAddressStats()
        self.writeMemoryStatistics(statsElt, statsInstance.mem)
        self.writeProcessorStatistics(statsElt, statsInstance.cpu)
        self.writeNetworkStatistics(statsElt, statsInstance.io)
        # write CPU / Memory plot
        img = StatisticsPlot()
        if AddressView.addressStatsType == 'acpu':
            img.addPlot('CPU #{}'.format(self._transformCpuIdToString(AddressView.cpuIdStats)), '%', statsInstance.cpu[AddressView.cpuIdStats])
        elif AddressView.addressStatsType == 'amem':
            img.addPlot('MEM', '%', statsInstance.mem)
        elif AddressView.addressStatsType == 'io':
            img.addPlot('{} recv'.format(AddressView.interfaceStats), 'kbits/s', statsInstance.io[AddressView.interfaceStats][0])
            img.addPlot('{} sent'.format(AddressView.interfaceStats), 'kbits/s', statsInstance.io[AddressView.interfaceStats][1])
        img.exportImage(addressImageContents)
        # set title
        elt = root.findmeld('address_fig_mid')
        elt.content(self.address)

    def writeMemoryStatistics(self, statsElt, memStats):
        """ Rendering of the memory statistics """
        if len(memStats) > 0:
            tr_elt = statsElt.findmeld('mem_tr_mid')
            # inactive button if selected
            if AddressView.addressStatsType == 'amem':
                tr_elt.attrib['class'] = 'selected'
                elt = statsElt.findmeld('mem_a_mid')
                elt.attributes(href='#')
                elt.attrib['class'] = 'button off active'
            # get additional statistics
            avg, rate, (a, b), dev = getStats(memStats)
            # set last value
            elt = tr_elt.findmeld('memval_td_mid')
            if rate is not None: self.setSlopeClass(elt, rate)
            elt.content('{:.2f}'.format(memStats[-1]))
            # set mean value
            elt = tr_elt.findmeld('memavg_td_mid')
            elt.content('{:.2f}'.format(avg))
            if a is not None:
            	# set slope of linear regression
            	elt = tr_elt.findmeld('memslope_td_mid')
            	elt.content('{:.2f}'.format(a))
            if dev is not None:
            	# set standard deviation
            	elt = tr_elt.findmeld('memdev_td_mid')
            	elt.content('{:.2f}'.format(dev))

    def writeProcessorStatistics(self, statsElt, cpuStats):
        """ Rendering of the processor statistics """
        iterator = statsElt.findmeld('cpu_tr_mid').repeat(cpuStats)
        shaded_tr = False
        for idx, (tr_element, singleCpuStats) in enumerate(iterator):
            selected_tr = False
            # set CPU id
            elt = tr_element.findmeld('cpunum_a_mid')
            if AddressView.addressStatsType == 'acpu' and AddressView.cpuIdStats == idx:
                selected_tr = True
                elt.attrib['class'] = 'button off active'
            else:
                elt.attributes(href='address.html?stats=acpu&amp;idx={}'.format(idx))
            elt.content('cpu#{}'.format(idx-1 if idx > 0 else 'all'))
            if len(singleCpuStats) > 0:
            	avg, rate, (a, b), dev = getStats(singleCpuStats)
            	# set last value with instant slope
            	elt = tr_element.findmeld('cpuval_td_mid')
            	if rate is not None: self.setSlopeClass(elt, rate)
            	elt.content('{:.2f}'.format(singleCpuStats[-1]))
            	# set mean value
            	elt = tr_element.findmeld('cpuavg_td_mid')
            	elt.content('{:.2f}'.format(avg))
            	if a is not None:
            	    # set slope of linear regression
            	    elt = tr_element.findmeld('cpuslope_td_mid')
            	    elt.content('{:.2f}'.format(a))
            	if dev is not None:
            	    # set standard deviation
            	    elt = tr_element.findmeld('cpudev_td_mid')
            	    elt.content('{:.2f}'.format(dev))
            if selected_tr:
                tr_element.attrib['class'] = 'selected'
            elif shaded_tr:
                tr_element.attrib['class'] = 'shaded'
            shaded_tr = not shaded_tr

    def writeNetworkStatistics(self, statsElt, ioStats):
        """ Rendering of the network statistics """
        flattenIoStats = [ (intf, lst) for intf, lsts in ioStats.items() for lst in lsts ]
        iterator = statsElt.findmeld('intf_tr_mid').repeat(flattenIoStats)
        rowspan, shaded_tr = True, False
        for tr_element, (intf, singleIoStats) in iterator:
            selected_tr = False
            # set interface cell rowspan
            elt = tr_element.findmeld('intf_td_mid')
            if rowspan:
                elt.attrib['rowspan'] = "2"
                # set interface name
                elt = elt.findmeld('intf_a_mid')
                if AddressView.addressStatsType == 'io' and AddressView.interfaceStats == intf:
                    selected_tr = True
                    elt.attrib['class'] = 'button off active'
                else:
                    elt.attributes(href='address.html?stats=io&amp;intf={}'.format(intf))
                elt.content(intf)
            else:
                if AddressView.addressStatsType == 'io' and AddressView.interfaceStats == intf:
                    selected_tr = True
                elt.replace('')
            # set interface direction
            elt = tr_element.findmeld('intfrxtx_td_mid')
            elt.content('Rx' if rowspan else 'Tx')
            if len(singleIoStats) > 0:
            	avg, rate, (a, b), dev = getStats(singleIoStats)
            	# set last value
            	elt = tr_element.findmeld('intfval_td_mid')
            	if rate is not None: self.setSlopeClass(elt, rate)
            	elt.content('{:.2f}'.format(singleIoStats[-1]))
            	# set mean value
            	elt = tr_element.findmeld('intfavg_td_mid')
            	elt.content('{:.2f}'.format(avg))
            	if a is not None:
            	    # set slope of linear regression
            	    elt = tr_element.findmeld('intfslope_td_mid')
            	    elt.content('{:.2f}'.format(a))
            	if dev is not None:
            	    # set standard deviation
            	    elt = tr_element.findmeld('intfdev_td_mid')
            	    elt.content('{:.2f}'.format(dev))
            if selected_tr:
                tr_element.attrib['class'] = 'selected'
            elif shaded_tr:
                tr_element.attrib['class'] = 'shaded'
            if not rowspan:
                shaded_tr = not shaded_tr
            rowspan = not rowspan

    def writeProcessTable(self, root):
        """ Rendering of the processes managed through Supervisor """
        # collect data on processes
        data = [ ]
        try:
            for processinfo in self.supervisors.requester.getAllProcessInfo(self.address):
                data.append({'namespec': make_namespec(processinfo['group'], processinfo['name']), 'statename': processinfo['statename'],
                    'state': processinfo['state'], 'desc': processinfo['description'] })
        except RPCError, e:
            self.logger.warn('failed to get all process info from {}: {}'.format(self.address, e.text))
        # print processes
        if data:
            iterator = root.findmeld('tr_mid').repeat(data)
            shaded_tr = False # used to invert background style
            for trElt, item in iterator:
                selected_tr = self.writeCommonProcessStatus(trElt, item)
                # print process name (tail allowed if STOPPED)
                namespec = item['namespec']
                processName = item.get('processname', namespec)
                elt = trElt.findmeld('name_a_mid')
                elt.attributes(href='http://{}:{}/tail.html?processname={}'.format(self.address, self.getServerPort(), urllib.quote(namespec)))
                elt.content(processName)
                # print description
                elt = trElt.findmeld('desc_td_mid')
                elt.content(item['desc'])
                # manage process log actions
                namespec = item['namespec']
                elt = trElt.findmeld('clear_a_mid')
                elt.attributes(href='address.html?processname={}&amp;action=clearlog'.format(urllib.quote(namespec)))
                elt = trElt.findmeld('tail_a_mid')
                elt.attributes(href='logtail/{}'.format(urllib.quote(namespec)), target='_blank')
                # set line background and invert
                if selected_tr:
                    trElt.attrib['class'] = 'selected'
                elif shaded_tr:
                    trElt.attrib['class'] = 'shaded'
                shaded_tr = not shaded_tr
        else:
            table = root.findmeld('table_mid')
            table.replace('No programs to manage')

    def make_callback(self, namespec, action):
        """ Triggers processing iaw action requested """
        if action == 'restartsup':
            return self.restartSupAction()
        if action == 'shutdownsup':
            return self.shutdownSupAction()
        return StatusView.make_callback(self, namespec, action)

    def restartSupAction(self):
        """ Restart the local supervisor """
        restart(self.address)
        # cannot defer result as restart address is self address
        # message is sent but it will be likely not displayed
        return delayedWarn('Supervisor restart requested')

    def shutdownSupAction(self):
        """ Shutdown the local supervisor """
        shutdown(self.address)
        # cannot defer result if shutdown address is self address
        return delayedWarn('Supervisor shutdown requested')

