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
from supervisors.application import applicationStateToString
from supervisors.context import context
from supervisors.statemachine import fsm
from supervisors.infosource import infoSource
from supervisors.options import options
from supervisors.remote import remoteStateToString, RemoteStates
from supervisors.types import SupervisorsStates
from supervisors.utils import getStats
from supervisors.webutils import *

from supervisor.http import NOT_DONE_YET
from supervisor.states import SupervisorStates, RUNNING_STATES, STOPPED_STATES

import urllib


# Supervisors address page
class ViewHandler(object):
    # static attributes for statistics selection
    periodStats = next(iter(options.statsPeriods))
    addressStatsType = 'acpu'
    cpuIdStats = 0
    interfaceStats = ''
    processStatsType = ''
    namespecStats = ''

    def writePage(self):
        """ Method called by Supervisor to handle the rendering of the Supervisors pages """
        # clone the template and set navigation menu
        if infoSource.supervisorState == SupervisorStates.RUNNING:
            # manage action
            message = self.handleAction()
            if message is NOT_DONE_YET: return NOT_DONE_YET
            # display result
            root = self.clone()
            form = self.context.form
            printMessage(root, form.get('gravity'), form.get('message'))
            # manage parameters
            self.handleParameters()
            # write navigation menu and Address header
            self.writeNavigation(root)
            self.writeHeader(root)
            self.writeContents(root)
            return root.write_xhtmlstring()

    def writeNav(self, root, address=None, appli=None):
        serverPort = self.getServerPort()
        # update navigation addresses
        iterator = root.findmeld('address_li_mid').repeat(addressMapper.expectedAddresses)
        for li_element, item in iterator:
            state = context.remotes[item].state
            # set element class
            li_element.attrib['class'] = remoteStateToString(state) + (' active' if item == address else '')
            # set hyperlink attributes
            elt = li_element.findmeld('address_a_mid')
            if state == RemoteStates.RUNNING:
                # go to web page located on address, so as to reuse Supervisor StatusView
                elt.attributes(href='http://{}:{}/address.html'.format(item, serverPort))
                elt.attrib['class'] = 'on'
            else:
                elt.attrib['class'] = 'off'
            elt.content(item)
        # update navigation applications
        iterator = root.findmeld('appli_li_mid').repeat(context.applications.keys())
        for li_element, item in iterator:
            state = context.applications[item].state
            # set element class
            li_element.attrib['class'] = applicationStateToString(state) + (' active' if item == appli else '')
            # set hyperlink attributes
            elt = li_element.findmeld('appli_a_mid')
            # go to web page located on Supervisors Master, so as to simplify requests
            if fsm.state == SupervisorsStates.INITIALIZATION:
                elt.attrib['class'] = 'off'
            else:
                elt.attributes(href='http://{}:{}/application.html?appli={}'.format(context.masterAddress, serverPort, urllib.quote(item)))
                elt.attrib['class'] = 'on'
            elt.content(item)

    def writePeriods(self, root):
        """ Write configured periods for statistics """
        iterator = root.findmeld('period_li_mid').repeat(options.statsPeriods)
        for li_element, period in iterator:
            # TODO: set period button on only if there is a related statistics
            # print period button
            elt = li_element.findmeld('period_a_mid')
            if period == ViewHandler.periodStats:
                elt.attrib['class'] = "button off active"
            else:
                elt.attributes(href='{}?{}period={}'.format(self.pageName, self.getUrlContext(), period))
            elt.content('{}s'.format(period))

    def writeCommonProcessStatus(self, trElt, item):
        selected_tr = False
        namespec = item['namespec']
        # print state
        elt = trElt.findmeld('state_td_mid')
        elt.attrib['class'] = item['statename']
        elt.content(item['statename'])
        # print expected loading
        procStatus = self.getProcessStatus(namespec)
        if procStatus:
            elt = trElt.findmeld('load_td_mid')
            elt.content('{}%'.format(procStatus.rules.expected_loading))
        # get data from statistics module iaw period selection
        hideCpuLink = hideMemLink = True
        procStats = self.getProcessStats(namespec)
        if procStats:
            if len(procStats[0]) > 0:
                # print last CPU value of process
                elt = trElt.findmeld('pcpu_a_mid')
                elt.content('{:.2f}%'.format(procStats[0][-1]))
                if ViewHandler.processStatsType == 'pcpu' and ViewHandler.namespecStats == namespec:
                    selected_tr = True
                    elt.attributes(href='#')
                    elt.attrib['class'] = 'button off active'
                else:
                    elt.attributes(href='{}?{}stats=pcpu&amp;processname={}'.format(self.pageName, self.getUrlContext(), urllib.quote(namespec)))
                    elt.attrib['class'] = 'button on'
                hideCpuLink = False
            if len(procStats[1]) > 0:
                # print last MEM value of process
                elt = trElt.findmeld('pmem_a_mid')
                elt.content('{:.2f}%'.format(procStats[1][-1]))
                if ViewHandler.processStatsType == 'pmem' and ViewHandler.namespecStats == namespec:
                    selected_tr = True
                    elt.attributes(href='#')
                    elt.attrib['class'] = 'button off active'
                else:
                    elt.attributes(href='{}?{}stats=pmem&amp;processname={}'.format(self.pageName, self.getUrlContext(), urllib.quote(namespec)))
                    elt.attrib['class'] = 'button on'
                hideMemLink = False
        # when no data, no not write link
        if hideCpuLink:
            elt = trElt.findmeld('pcpu_a_mid')
            elt.replace('--')
        if hideMemLink:
            elt = trElt.findmeld('pmem_a_mid')
            elt.replace('--')
        # manage actions iaw state
        processState = item['state']
        # start button
        elt = trElt.findmeld('start_a_mid')
        if processState in STOPPED_STATES:
            elt.attrib['class'] = 'button on'
            elt.attributes(href='{}?{}processname={}&amp;action=start'.format(self.pageName, self.getUrlContext(), urllib.quote(namespec)))
        else:
           elt.attrib['class'] = 'button off'
        # stop button
        elt = trElt.findmeld('stop_a_mid')
        if processState in RUNNING_STATES:
            elt.attrib['class'] = 'button on'
            elt.attributes(href='{}?{}processname={}&amp;action=stop'.format(self.pageName, self.getUrlContext(), urllib.quote(namespec)))
        else:
           elt.attrib['class'] = 'button off'
        # restart button
        elt = trElt.findmeld('restart_a_mid')
        if processState in RUNNING_STATES:
            elt.attrib['class'] = 'button on'
            elt.attributes(href='{}?{}processname={}&amp;action=restart'.format(self.pageName, self.getUrlContext(), urllib.quote(namespec)))
        else:
           elt.attrib['class'] = 'button off'
        return selected_tr
 
    def writeProcessStatistics(self, root):
        """ Display detailed statistics about the selected process """
        statsElt = root.findmeld('pstats_div_mid')
        # get data from statistics module iaw period selection
        procStats = self.getProcessStats(ViewHandler.namespecStats) if ViewHandler.namespecStats else None
        if procStats:
            # set CPU statistics
            if len(procStats[0]) > 0:
                avg, rate, (a, b), dev = getStats(procStats[0])
                # print last CPU value of process
                elt = statsElt.findmeld('pcpuval_td_mid')
                if rate is not None: self.setSlopeClass(elt, rate)
                elt.content('{:.2f}%'.format(procStats[0][-1]))
                # set mean value
                elt = statsElt.findmeld('pcpuavg_td_mid')
                elt.content('{:.2f}'.format(avg))
                if a is not None:
                    # set slope value between last 2 values
                    elt = statsElt.findmeld('pcpuslope_td_mid')
                    elt.content('{:.2f}'.format(a))
                if dev is not None:
                    # set standard deviation
                    elt = statsElt.findmeld('pcpudev_td_mid')
                    elt.content('{:.2f}'.format(dev))
            # set MEM statistics
            if len(procStats[1]) > 0:
                avg, rate, (a, b), dev = getStats(procStats[1])
                # print last MEM value of process
                elt = statsElt.findmeld('pmemval_td_mid')
                if rate is not None: self.setSlopeClass(elt, rate)
                elt.content('{:.2f}%'.format(procStats[1][-1]))
                # set mean value
                elt = statsElt.findmeld('pmemavg_td_mid')
                elt.content('{:.2f}'.format(avg))
                if a is not None:
                    # set slope value between last 2 values
                    elt = statsElt.findmeld('pmemslope_td_mid')
                    elt.content('{:.2f}'.format(a))
                if dev is not None:
                    # set standard deviation
                    elt = statsElt.findmeld('pmemdev_td_mid')
                    elt.content('{:.2f}'.format(dev))
            # write CPU / Memory plot
            from supervisors.plot import StatisticsPlot
            img = StatisticsPlot()
            if ViewHandler.processStatsType == 'pcpu':
                img.addPlot('CPU', '%', procStats[0])
            elif ViewHandler.processStatsType == 'pmem':
                img.addPlot('MEM', '%', procStats[1])
            from supervisors.viewimage import processImageContents
            img.exportImage(processImageContents)
            # set title
            elt = statsElt.findmeld('process_fig_mid')
            elt.content(ViewHandler.namespecStats)
        else:
            if ViewHandler.namespecStats :
                options.logger.warn('unselect Process Statistics for {}'.format(ViewHandler.namespecStats))
                ViewHandler.namespecStats = ''
            # hide stats part
            statsElt.attrib['class'] = 'hidden'

    def handleParameters(self):
        """ Retrieve the parameters selected on the web page
        These parameters are static to the current class, so they are shared between all browsers connected on this server """
        form = self.context.form
        # update context period
        periodString = form.get('period')
        if periodString:
            period = int(periodString)
            if period in options.statsPeriods:
                if ViewHandler.periodStats != period:
                    options.logger.info('statistics period set to %d' % period)
                    ViewHandler.periodStats = period
            else:
                self.setMessage(errorMessage('Incorrect period: {}'.format(periodString)))
        # get statistics type
        statsType = form.get('stats')
        if statsType:
            if statsType == 'acpu':
                cpuid = form.get('idx')
                try:
                    cpuid = int(cpuid)
                except ValueError:
                    self.setMessage(errorMessage('Cpu id is not an integer: {}'.format(cpuid)))
                else:
                    # update Address statistics selection
                    if cpuid < len(self.getAddressStats().cpu):
                        if ViewHandler.addressStatsType != statsType or ViewHandler.cpuIdStats != cpuid:
                            options.logger.info('select cpu#{} statistics for address'.format(self._transformCpuIdToString(cpuid)))
                            ViewHandler.addressStatsType = statsType
                            ViewHandler.cpuIdStats = cpuid
                    else:
                        self.setMessage(errorMessage('Incorrect stats cpu id: {}'.format(cpuid)))
            if statsType == 'amem':
                # update Address statistics selection
                if ViewHandler.addressStatsType != statsType:
                    options.logger.info('select mem statistics for address')
                    ViewHandler.addressStatsType = statsType
            elif statsType == 'io':
                interface = form.get('intf')
                # update Network statistics selection
                ioStats = self.getAddressStats().io
                if interface in ioStats.keys():
                    if ViewHandler.addressStatsType != statsType or ViewHandler.interfaceStats != interface:
                        options.logger.info('select Interface graph for %s' % interface)
                        ViewHandler.addressStatsType = statsType
                        ViewHandler.interfaceStats = interface
                else:
                    self.setMessage(errorMessage('Incorrect stats interface: {}'.format(intf)))
            elif statsType in ['pcpu', 'pmem']:
                namespec = form.get('processname')
                procStats = self.getProcessStats(namespec)
                if procStats:
                    if ViewHandler.processStatsType != statsType or ViewHandler.namespecStats != namespec:
                        options.logger.info('select detailed Process statistics for %s' % namespec)
                        ViewHandler.processStatsType = statsType
                        ViewHandler.namespecStats = namespec
                else:
                    self.setMessage(errorMessage('Incorrect stats namespec: {}'.format(namespec)))

    def handleAction(self):
        """ Handling of the actions requested from the Supervisors Address web page """
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
                self.setMessage(formatGravityMessage(message))

    def setMessage(self, message):
        """ Set message in context response to be displayed at next refresh """
        form = self.context.form
        location = form['SERVER_URL'] + form['PATH_TRANSLATED'] + '?{}message={}&amp;gravity={}'.format(self.getUrlContext(), urllib.quote(message[1]), message[0])
        self.context.response['headers']['Location'] = location

    def setSlopeClass(self, elt, value):
        if (abs(value) < .005):
            elt.attrib['class'] = 'stable'
        elif (value > 0):
            elt.attrib['class'] = 'increase'
        else:
            elt.attrib['class'] = 'decrease'

    def getUrlContext(self):
        """ Get the extra parameters for the URL """
        return ''

    def getProcessStatus(self, namespec):
        """ Get the ProcessStatus instance related to the process named namespec """
        try:
            procStatus = context.getProcessFromNamespec(namespec)
        except KeyError:
            options.logger.debug('failed to get ProcessStatus from {}'.format(namespec))
        else:
            return procStatus

    def getServerPort(self):
        """ Get the port number of the web server """
        return self.context.form.get('SERVER_PORT')

    def _transformCpuIdToString(self, idx):
        """ Get a displayable form to cpu index """
        return idx- 1 if idx > 0 else 'all'

