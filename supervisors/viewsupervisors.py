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
from supervisors.remote import remoteStateToString, RemoteStates
from supervisors.statemachine import fsm
from supervisors.types import SupervisorsStates, supervisorsStateToString
from supervisors.webutils import *

from supervisor.http import NOT_DONE_YET
from supervisor.states import SupervisorStates
from supervisor.web import MeldView

import urllib


# Supervisors main page
class SupervisorsView(MeldView):
    # Rendering part
    def render(self):
        # clone the template and set navigation menu
        root = self.clone()
        if infoSource.supervisorState == SupervisorStates.RUNNING:
            # get parameters
            form = self.context.form
            serverPort = form.get('SERVER_PORT')
            # write navigation menu and Supervisors header
            writeNav(root, serverPort)
            self._writeHeader(root)
            # manage action
            message = self.handleAction()
            if message is NOT_DONE_YET: return NOT_DONE_YET
            # display result
            printMessage(root, self.context.form.get('gravity'), self.context.form.get('message'))
            self._renderSynoptic(root, serverPort)
        return root.write_xhtmlstring()

    def _writeHeader(self, root):
        # set Supervisors state
        elt = root.findmeld('state_mid')
        elt.content(supervisorsStateToString(fsm.state))
        # if conciliation, display link to solve
        elt = root.findmeld('solve_a_mid')
        if fsm.state == SupervisorsStates.CONCILIATION:
            elt.attrib['class'] = 'conciliationLink'
        else:
            elt.attrib['class'] = 'hidden'

    def _renderSynoptic(self, root, serverPort):
        addressIterator = root.findmeld('address_div_mid').repeat(addressMapper.expectedAddresses)
        for div_element, address in addressIterator:
            status = context.remotes[address]
            # set address
            elt = div_element.findmeld('address_tda_mid')
            elt.attrib['class'] = remoteStateToString(status.state)
            if status.state == RemoteStates.RUNNING:
                # go to web page located on address, so as to reuse Supervisor StatusView
                elt.attributes(href='http://{addr}:{port}/address.html?address={addr}'.format(addr= urllib.quote(address), port=serverPort))
                elt.attrib['class'] = 'on'
            else:
                elt.attrib['class'] = 'off'
            elt.content(address)
            # set state
            elt = div_element.findmeld('state_td_mid')
            elt.attrib['class'] = remoteStateToString(status.state) + ' state'
            elt.content(remoteStateToString(status.state))
            # set loading
            elt = div_element.findmeld('percent_td_mid')
            elt.content('{}%'.format(context.getLoading(address)))
            # fill with running processes
            data = context.getRunningProcesses(address)
            processIterator = div_element.findmeld('process_li_mid').repeat(data)
            for li_element, process in processIterator:
                li_element.content(process.getNamespec())

    # Action part
    def handleAction(self):
        form = self.context.form
        action = form.get('action')
        if action:
            # trigger deferred action and wait
            if not self.callback:
                self.callback = self.make_callback(action)
                return NOT_DONE_YET
            # intermediate check
            message = self.callback()
            if message is NOT_DONE_YET: return NOT_DONE_YET
            # post to write message
            if message is not None:
                location = form['SERVER_URL'] + form['PATH_TRANSLATED'] + '?message={}&amp;gravity={}'.format(urllib.quote(message[1]), message[0])
                self.context.response['headers']['Location'] = location

    def make_callback(self, action):
        if action == 'refresh':
        		return self.refreshAction()
        if action == 'restart':
            return self.restartAction()
        if action == 'shutdown':
            return self.shutdownAction()

    def refreshAction(self):
        return delayedInfo('Page refreshed')

    def restartAction(self):
        try:
            infoSource.getSupervisorsRpcInterface().restart()
        except RPCError, e:
            return delayedError('restart: {}'.format(e))
        return delayedInfo('Supervisors restarted')

    def shutdownAction(self):
        try:
            infoSource.getSupervisorsRpcInterface().shutdown()
        except RPCError, e:
            return delayedError('shutdown: {}'.format(e))
        return delayedInfo('Supervisors shut down')
