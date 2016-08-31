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
class AddressView(StatusView):
    # Rendering part
    def render(self):
        # clone the template and set navigation menu
        root = self.clone()
        if infoSource.supervisorState == SupervisorStates.RUNNING:
            # get parameters
            form = self.context.form
            serverPort = form.get('SERVER_PORT')
            # write navigation menu and Address header
            writeNav(root, serverPort, address=addressMapper.localAddress)
            self._writeHeader(root)
            self._writeResources(root)
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

    def _writeResources(self, root):
        # TODO: parameter this
        period = 10
        # get data from statistics module
        from supervisors.statistics import statisticsCompiler
        statsInstance = statisticsCompiler.data[addressMapper.localAddress][period]
        # write CPU / Memory plot
        from supervisors.plot import createCpuMemPlot, createIoPlot
        cpuData = [ data[1][0] for data in statsInstance.data ]
        memData = [ data[2] for data in statsInstance.data ]
        createCpuMemPlot(cpuData, memData, 'ui/tmp/cpu-mem.png')
        # write I/O plot
        ioData = [ data[3] for data in statsInstance.data ]
        # rearrange io data
        sortedIoData = { inf: ( [ ], [ ] ) for inf in next(data.keys() for data in ioData) }
        for data in ioData:
            for inf, infData in data.items():
                sortedIoData[inf][0].append(infData[0])
                sortedIoData[inf][1].append(infData[1])
        createIoPlot(ioData, 'ui/tmp/cpu-mem.png')
        # set title
        elt = root.findmeld('address_fig_mid')
        elt.content(addressMapper.localAddress)

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
                elt.attributes(href='logtail.html?processname={}&amp'.format(urllib.quote(item[0])), target='_blank')
                # set line background and invert
                if shaded_tr:
                    tr_element.attrib['class'] = 'shade'
                shaded_tr = not shaded_tr
        else:
            table = root.findmeld('table_mid')
            table.replace('No programs to manage')

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
