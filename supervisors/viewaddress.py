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

from supervisors.addressmapper import addressMapper
from supervisors.context import context
from supervisors.infosource import infoSource
from supervisors.options import options
from supervisors.webutils import *

from supervisor.http import NOT_DONE_YET
from supervisor.options import make_namespec
from supervisor.states import SupervisorStates, RUNNING_STATES, STOPPED_STATES
from supervisor.web import StatusView

import urllib


# Supervisors address page
def getStats(lst):
    from supervisors.utils import mean, slope, stddev
    slp = dev = None
    # calculate mean value
    avg = mean(lst)
    if len(lst) > 1:
        # calculate slope value between last 2 values
        slp = slope(lst[-1], lst[-2])
        # calculate standard deviation
        dev = stddev(lst, avg)
    return avg, slp, dev


# Supervisors address page
class AddressView(StatusView):
    # static attributes
    statsPeriod = next(iter(options.statsPeriods))
    namespec = ''

    # Rendering part
    def render(self):
        # clone the template and set navigation menu
        root = self.clone()
        if infoSource.supervisorState == SupervisorStates.RUNNING:
            # get parameters
            form = self.context.form
            serverPort = form.get('SERVER_PORT')
            # manage parameters
            self.handleParameters()
            # write navigation menu and Address header
            writeNav(root, serverPort, address=addressMapper.localAddress)
            self._writeHeader(root)
            self._writePeriods(root)
            self._writeAddressStatistics(root)
            self._writeProcessStatistics(root)
            # manage action
            message = self.handleAction()
            if message is NOT_DONE_YET: return NOT_DONE_YET
            # display result
            printMessage(root, self.context.form.get('gravity'), self.context.form.get('message'))
            self._renderProcesses(root)
        return root.write_xhtmlstring()

    def _writeHeader(self, root):
        from supervisors.remote import remoteStateToString
        # set address name
        elt = root.findmeld('address_mid')
        elt.content(addressMapper.localAddress)
        # set address state
        remote = context.remotes[addressMapper.localAddress]
        elt = root.findmeld('state_mid')
        elt.content(remoteStateToString(remote.state))
        # set loading
        elt = root.findmeld('percent_mid')
        elt.content('{}%'.format(context.getLoading(addressMapper.localAddress)))
        # set last tick date: remoteTime and localTime should be identical since self is running on the 'remote' address
        elt = root.findmeld('date_mid')
        elt.content(time.ctime(remote.remoteTime))

    def _writeProcessStatistics(self, root):
        """" Display detailed statistics about process """
        statsElt = root.findmeld('pstats_div_mid')
        # get data from statistics module iaw period selection
        from supervisors.statistics import statisticsCompiler
        statsInstance = statisticsCompiler.data[addressMapper.localAddress][AddressView.statsPeriod]
        if AddressView.namespec in statsInstance.proc.keys():
            procStats = statsInstance.proc[AddressView.namespec]
            # set CPU statistics
            if len(procStats[0]) > 0:
                avg, slp, dev = getStats(procStats[0])
                # print last CPU value of process
                elt = statsElt.findmeld('pcpuval_td_mid')
                elt.content('{:.2f}%'.format(procStats[0][-1]))
                # set mean value
                elt = statsElt.findmeld('pcpuavg_td_mid')
                elt.content('{:.2f}'.format(avg))
                if slp:
                    # set slope value between last 2 values
                    # TODO add class gradient to reflect increase / decrease
                    elt = statsElt.findmeld('pcpuslope_td_mid')
                    elt.content('{:.2f}'.format(slp))
                if dev:
                    # set standard deviation
                    elt = statsElt.findmeld('pcpudev_td_mid')
                    elt.content('{:.2f}'.format(dev))
            # set MEM statistics
            if len(procStats[1]) > 0:
                avg, slp, dev = getStats(procStats[1])
                # print last MEM value of process
                elt = statsElt.findmeld('pmemval_td_mid')
                elt.content('{:.2f}%'.format(procStats[1][-1]))
                # set mean value
                elt = statsElt.findmeld('pmemavg_td_mid')
                elt.content('{:.2f}'.format(avg))
                if slp:
                    # set slope value between last 2 values
                    # TODO add class gradient to reflect increase / decrease
                    elt = statsElt.findmeld('pmemslope_td_mid')
                    elt.content('{:.2f}'.format(slp))
                if dev:
                    # set standard deviation
                    elt = statsElt.findmeld('pmemdev_td_mid')
                    elt.content('{:.2f}'.format(dev))
            # write CPU / Memory plot
            from supervisors.plot import createCpuMemPlot
            from supervisors.viewimage import processImageContents
            createCpuMemPlot(procStats[0], procStats[1], processImageContents)
            # set title
            elt = statsElt.findmeld('process_fig_mid')
            elt.content(AddressView.namespec)
        else:
            AddressView.namespec = ''
            # hide stats part
            statsElt.attrib['class'] = "hidden"

    def _writeAddressStatistics(self, root):
        """" Display tables and figures for address statistics """
        # position to stats element
        statsElt = root.findmeld('stats_div_mid')
        # get data from statistics module iaw period selection
        from supervisors.statistics import statisticsCompiler
        statsInstance = statisticsCompiler.data[addressMapper.localAddress][AddressView.statsPeriod]
        self._writeMemoryStatistics(statsElt, statsInstance.mem)
        self._writeProcessorStatistics(statsElt, statsInstance.cpu)
        self._writeNetworkStatistics(statsElt, statsInstance.io)
        # TODO: get selection
        # write CPU / Memory plot
        from supervisors.plot import createCpuMemPlot
        from supervisors.viewimage import addressImageContents
        createCpuMemPlot(statsInstance.cpu[0], statsInstance.mem, addressImageContents)
        # write I/O plot
        # from supervisors.plot import createIoPlot
        # createIoPlot(interface, statsInstance.io[interface])
        # set title
        elt = root.findmeld('address_fig_mid')
        elt.content(addressMapper.localAddress)

    def _writePeriods(self, root):
        """ Display configured periods for statistics """
        iterator = root.findmeld('period_li_mid').repeat(options.statsPeriods)
        for li_element, period in iterator:
            # TODO: set period button on only if there is a related statistics
            # print period button
            elt = li_element.findmeld('period_a_mid')
            if period == AddressView.statsPeriod:
            	elt.attrib['class'] = "button off active"
            else:
            	elt.attributes(href='address.html?period={}'.format(period))
            elt.content('{}s'.format(period))

    def _writeMemoryStatistics(self, statsElt, memStats):
        """ Display memory statistics """
        if len(memStats) > 0:
            avg, slp, dev = getStats(memStats)
            # set last value
            elt = statsElt.findmeld('memval_td_mid')
            elt.content('{:.2f}'.format(memStats[-1]))
            # set mean value
            elt = statsElt.findmeld('memavg_td_mid')
            elt.content('{:.2f}'.format(avg))
            if slp:
            	# set slope value between last 2 values
            	# TODO add class gradient to reflect increase / decrease
            	elt = statsElt.findmeld('memslope_td_mid')
            	elt.content('{:.2f}'.format(slp))
            if dev:
            	# set standard deviation
            	elt = statsElt.findmeld('memdev_td_mid')
            	elt.content('{:.2f}'.format(dev))

    def _writeProcessorStatistics(self, statsElt, cpuStats):
        """ Display processor statistics """
        iterator = statsElt.findmeld('cpu_tr_mid').repeat(cpuStats)
        for (tr_element, singleCpuStats), idx in zip(iterator, range(-1, len(cpuStats) - 1)):
            # set CPU id
            elt = tr_element.findmeld('cpunum_a_mid')
            elt.content('cpu#{}'.format(idx if idx >= 0 else 'all'))
            if len(singleCpuStats) > 0:
            	avg, slp, dev = getStats(singleCpuStats)
            	# set last value
            	elt = tr_element.findmeld('cpuval_td_mid')
            	elt.content('{:.2f}'.format(singleCpuStats[-1]))
            	# set mean value
            	elt = tr_element.findmeld('cpuavg_td_mid')
            	elt.content('{:.2f}'.format(avg))
            	if slp:
            	    # set slope value between last 2 values
            	    # TODO add class gradient to reflect increase / decrease
            	    elt = tr_element.findmeld('cpuslope_td_mid')
            	    elt.content('{:.2f}'.format(slp))
            	if dev:
            	    # set standard deviation
            	    elt = tr_element.findmeld('cpudev_td_mid')
            	    elt.content('{:.2f}'.format(dev))

    def _writeNetworkStatistics(self, statsElt, ioStats):
        """ Display network statistics """
        flattenIoStats = [ (intf, lst) for intf, lsts in ioStats.items() for lst in lsts ]
        iterator = statsElt.findmeld('intf_tr_mid').repeat(flattenIoStats)
        rowspan = True
        for tr_element, (intf, singleIoStats) in iterator:
            # set interface cell rowspan
            elt = tr_element.findmeld('intf_td_mid')
            if rowspan:
            	elt.attrib['rowspan'] = "2"
            	# set interface name
            	elt = elt.findmeld('intf_a_mid')
            	elt.content(intf)
            else:
            	elt.replace('')
            # set interface direction
            elt = tr_element.findmeld('intfrxtx_td_mid')
            elt.content('Rx' if rowspan else 'Tx')
            if len(singleIoStats) > 0:
            	avg, slp, dev = getStats(singleIoStats)
            	# set last value
            	elt = tr_element.findmeld('intfval_td_mid')
            	elt.content('{:.2f}'.format(singleIoStats[-1]))
            	# set mean value
            	elt = tr_element.findmeld('intfavg_td_mid')
            	elt.content('{:.2f}'.format(avg))
            	if slp:
            	    # set slope value between last 2 values
            	    # TODO add class gradient to reflect increase / decrease
            	    elt = tr_element.findmeld('intfslope_td_mid')
            	    elt.content('{:.2f}'.format(slp))
            	if dev:
            	    # set standard deviation
            	    elt = tr_element.findmeld('intfdev_td_mid')
            	    elt.content('{:.2f}'.format(dev))
            rowspan = not rowspan

    def _renderProcesses(self, root):
        # collect data on processes
        data = [ ]
        try:
            from supervisors.rpcrequests import getAllProcessInfo
            for processinfo in getAllProcessInfo(addressMapper.localAddress):
                data.append((make_namespec(processinfo['group'], processinfo['name']), processinfo['statename'], processinfo['state'], processinfo['description'] ))
        except RPCError, e:
            options.logger.warn('failed to get all process info from {}: {}'.format(addressMapper.localAddress, e.text))
        # print processes
        if data:
            from supervisors.statistics import statisticsCompiler
            iterator = root.findmeld('tr_mid').repeat(data)
            shaded_tr = False # used to invert background style
            for tr_element, item in iterator:
                # print process name
                elt = tr_element.findmeld('name_a_mid')
                elt.attributes(href='tail.html?processname={}'.format(urllib.quote(item[0])))
                elt.content(item[0])
                # print state
                elt = tr_element.findmeld('state_td_mid')
                elt.attrib['class'] = item[1]
                elt.content(item[1])
                # print expected loading
                procStatus = context.getProcessFromNamespec(item[0])
                elt = tr_element.findmeld('load_td_mid')
                elt.content('{}%'.format(procStatus.rules.expected_loading))
                # get data from statistics module iaw period selection
                hideCpuLink = hideMemLink = True
                statsInstance = statisticsCompiler.data[addressMapper.localAddress][AddressView.statsPeriod]
                if item[0] in statsInstance.proc.keys():
                    procStats = statsInstance.proc[item[0]]
                    if len(procStats[0]) > 0:
                        # print last CPU value of process
                        elt = tr_element.findmeld('pcpu_a_mid')
                        elt.attributes(href='address.html?pstats={}'.format(urllib.quote(item[0])))
                        elt.content('{:.2f}%'.format(procStats[0][-1]))
                        hideCpuLink = False
                    if len(procStats[1]) > 0:
                        # print last MEM value of process
                        elt = tr_element.findmeld('pmem_a_mid')
                        elt.attributes(href='address.html?pstats={}'.format(urllib.quote(item[0])))
                        elt.content('{:.2f}%'.format(procStats[1][-1]))
                        hideMemLink = False
                # when no data, no not write link
                if hideCpuLink:
                    elt = tr_element.findmeld('pcpu_a_mid')
                    elt.replace('--')
                if hideMemLink:
                    elt = tr_element.findmeld('pmem_a_mid')
                    elt.replace('--')
               # print description
                elt = tr_element.findmeld('desc_td_mid')
                elt.content(item[3])
                # manage process actions iaw state
                # start button
                elt = tr_element.findmeld('start_a_mid')
                if item[2] in STOPPED_STATES:
                    elt.attrib['class'] = 'button on'
                    elt.attributes(href='address.html?processname={}&amp;action=start'.format(urllib.quote(item[0])))
                else:
                   elt.attrib['class'] = 'button off'
                # stop button
                elt = tr_element.findmeld('stop_a_mid')
                if item[2] in RUNNING_STATES:
                    elt.attrib['class'] = 'button on'
                    elt.attributes(href='address.html?processname={}&amp;action=stop'.format(urllib.quote(item[0])))
                else:
                   elt.attrib['class'] = 'button off'
                # restart button
                elt = tr_element.findmeld('restart_a_mid')
                if item[2] in RUNNING_STATES:
                    elt.attrib['class'] = 'button on'
                    elt.attributes(href='address.html?processname={}&amp;action=restart'.format(urllib.quote(item[0])))
                else:
                   elt.attrib['class'] = 'button off'
                # manage process log actions
                elt = tr_element.findmeld('clear_a_mid')
                elt.attributes(href='address.html?processname={}&amp;action=clearlog'.format( urllib.quote(item[0])))
                elt = tr_element.findmeld('tail_a_mid')
                elt.attributes(href='logtail/{}'.format(urllib.quote(item[0])), target='_blank')
                # set line background and invert
                if shaded_tr:
                    tr_element.attrib['class'] = 'shade'
                shaded_tr = not shaded_tr
        else:
            table = root.findmeld('table_mid')
            table.replace('No programs to manage')

    # Parameters part
    def handleParameters(self):
        form = self.context.form
        # update context period
        periodString = form.get('period')
        if periodString:
            period = int(periodString)
            if period in options.statsPeriods:
                if AddressView.statsPeriod != period:
                    options.logger.info('statistics period set to %d' % period)
                    AddressView.statsPeriod = period
            else:
                message = errorMessage('incorrect period: {}'.format(periodString))
                location = form['SERVER_URL'] + form['PATH_TRANSLATED'] + '?message={}&amp;gravity={}'.format(urllib.quote(message[1]), message[0])
                self.context.response['headers']['Location'] = location
        # update Process statistics selection
        namespec = form.get('pstats')
        if namespec:
            from supervisors.statistics import statisticsCompiler
            statsInstance = statisticsCompiler.data[addressMapper.localAddress][AddressView.statsPeriod].proc
            if namespec in statsInstance.keys():
                if AddressView.namespec != namespec:
                    options.logger.info('select detailed Process statistics for %s' % namespec)
                    AddressView.namespec = namespec
            else:
                message = errorMessage('incorrect pstat namespec: {}'.format(namespec))
                location = form['SERVER_URL'] + form['PATH_TRANSLATED'] + '?message={}&amp;gravity={}'.format(urllib.quote(message[1]), message[0])
                self.context.response['headers']['Location'] = location

    # Action part
    def handleAction(self):
        form = self.context.form
        action = form.get('action')
        if action:
            # trigger deferred action and wait
            processName = form.get('processname')
            if not self.callback:
                self.callback = self.make_callback(processName, action)
                return NOT_DONE_YET
            # intermediate check
            message = self.callback()
            if message is NOT_DONE_YET: return NOT_DONE_YET
            # post to write message
            if message is not None:
                message = formatGravityMessage(message)
                location = form['SERVER_URL'] + form['PATH_TRANSLATED'] + '?message={}&amp;gravity={}'.format(urllib.quote(message[1]), message[0])
                self.context.response['headers']['Location'] = location

    def make_callback(self, namespec, action):
        if action == 'restartsup':
            return self.restartSupAction()
        if action == 'shutdownsup':
            return self.shutdownSupAction()
        return StatusView.make_callback(self, namespec, action)

    def restartSupAction(self):
        from supervisors.rpcrequests import restart
        restart(addressMapper.localAddress)
        # cannot defer result as restart address is self address
        # message is sent but it will be likely not displayed
        return delayedWarn('Supervisor restart requested')

    def shutdownSupAction(self):
        from supervisors.rpcrequests import shutdown
        shutdown(addressMapper.localAddress)
        # cannot defer result if shutdown address is self address
        return delayedWarn('Supervisor shutdown requested')
