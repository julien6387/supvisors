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
from supervisors.viewhandler import ViewHandler
from supervisors.webutils import *

from supervisor.web import MeldView

import urllib


# Supervisors main page
class SupervisorsView(MeldView, ViewHandler):
    # Name of the HTML page
    pageName = 'index.html'

    def render(self):
        """ Method called by Supervisor to handle the rendering of the Supervisors Address page """
        return self.writePage()

    def writeNavigation(self, root):
        """ Rendering of the navigation menu """
        self.writeNav(root)

    def writeHeader(self, root):
        """ Rendering of the header part of the Supervisors main page """
        # set Supervisors state
        elt = root.findmeld('state_mid')
        elt.content(supervisorsStateToString(fsm.state))
        # if conciliation, display link to solve
        elt = root.findmeld('solve_a_mid')
        if fsm.state == SupervisorsStates.CONCILIATION:
            elt.attrib['class'] = 'conciliationLink'
        else:
            elt.attrib['class'] = 'hidden'

    def writeContents(self, root):
        """ Rendering of the contents of the Supervisors main page
        This builds a synoptic of the processes running on the addresses """
        addressIterator = root.findmeld('address_div_mid').repeat(addressMapper.expectedAddresses)
        for div_element, address in addressIterator:
            status = context.remotes[address]
            # set address
            elt = div_element.findmeld('address_tda_mid')
            elt.attrib['class'] = remoteStateToString(status.state)
            if status.state == RemoteStates.RUNNING:
                # go to web page located on address, so as to reuse Supervisor StatusView
                elt.attributes(href='http://{addr}:{port}/address.html?address={addr}'.format(addr= urllib.quote(address), port=self.getServerPort()))
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
    def make_callback(self, dummy, action):
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
