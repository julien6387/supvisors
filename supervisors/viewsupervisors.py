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
from supervisors.strategy import conciliator
from supervisors.types import SupervisorsStates, supervisorsStateToString, stringToConciliationStrategy, conciliationStrategiesStrings
from supervisors.utils import simpleTime
from supervisors.viewhandler import ViewHandler
from supervisors.webutils import *

from supervisor.http import NOT_DONE_YET
from supervisor.web import MeldView
from supervisor.xmlrpc import RPCError

import urllib


class SupervisorsView(MeldView, ViewHandler):
    """ Class ensuring the rendering of the Supervisors main page with:
    * a navigation menu towards addresses contents and applications
    * the state of Supervisors
    * actions on Supervisors
    * a synoptic of the processes running on the different addresses
    * in CONCILIATION state only, the synoptic is replaced by a table of conflicts with means to solve them """

    # Name of the HTML page
    pageName = 'index.html'

    def __init__(self, context):
        """ Constructor stores actions for easy access """
        MeldView.__init__(self, context)
        # global actions (no parameter)
        self.globalMethods = { 'refresh': self.refreshAction, 'sup_restart': self.supRestartAction, 'sup_shutdown': self.supShutdownAction }
        # process actions
        self.processMethods = { 'pstop': self.stopAction, 'pkeep': self.keepAction }

    def render(self):
        """ Method called by Supervisor to handle the rendering of the Supervisors Address page """
        return self.writePage()

    def writeNavigation(self, root):
        """ Rendering of the navigation menu """
        self.writeNav(root)

    def writeHeader(self, root):
        """ Rendering of the header part of the Supervisors main page """
        # set Supervisors state
        root.findmeld('state_mid').content(supervisorsStateToString(fsm.state))

    def writeContents(self, root):
        """ Rendering of the contents of the Supervisors main page
        This builds either a synoptic of the processes running on the addresses or the table of conflicts if any """
        if fsm.state == SupervisorsStates.CONCILIATION and context.getConflicts():
            # remove address boxes
            root.findmeld('boxes_div_mid').replace('')
            # write conflicts
            self.writeConciliationTable(root)
            # TODO: add global conciliation
        else:
            # remove conflicts table
            root.findmeld('conflicts_div_mid').replace('')
            # write address boxes
            self.writeAddressBoxes(root)

    def writeAddressBoxes(self, root):
        """ Rendering of the addresses boxes """
        addressIterator = root.findmeld('address_div_mid').repeat(addressMapper.expectedAddresses)
        for divElt, address in addressIterator:
            status = context.remotes[address]
            # set address
            elt = divElt.findmeld('address_tda_mid')
            elt.attrib['class'] = remoteStateToString(status.state)
            if status.state == RemoteStates.RUNNING:
                # go to web page located on address, so as to reuse Supervisor StatusView
                elt.attributes(href='http://{}:{}/address.html'.format(urllib.quote(address), self.getServerPort()))
                elt.attrib['class'] = 'on'
            else:
                elt.attrib['class'] = 'off'
            elt.content(address)
            # set state
            elt = divElt.findmeld('state_td_mid')
            elt.attrib['class'] = remoteStateToString(status.state) + ' state'
            elt.content(remoteStateToString(status.state))
            # set loading
            elt = divElt.findmeld('percent_td_mid')
            elt.content('{}%'.format(context.getLoading(address)))
            # fill with running processes
            data = context.getRunningProcesses(address)
            processIterator = divElt.findmeld('process_li_mid').repeat(data)
            for liElt, process in processIterator:
                liElt.content(process.getNamespec())

    def writeConciliationTable(self, root):
        """ Rendering of the conflicts table """
        divElt = root.findmeld('conflicts_div_mid')
        # get data
        data = [ { 'namespec': process.getNamespec(), 'rowspan': len(process.addresses) if idx == 0 else 0,
            'address': address, 'uptime': process.processes[address]['uptime'] }
            for process in context.getConflicts() for idx, address in enumerate(process.addresses) ]
        addressIterator = divElt.findmeld('tr_mid').repeat(data)
        for trElt, item in addressIterator:
            # set process name
            elt = trElt.findmeld('name_td_mid')
            rowspan = item['rowspan']
            if rowspan > 0:
                namespec = item['namespec']
                elt.attrib['rowspan'] = str(rowspan)
                elt.content(namespec)
            else:
                elt.replace('')
            # set address
            address = item['address']
            elt = trElt.findmeld('caddress_a_mid')
            elt.attributes(href='http://{}:{}/address.html'.format(address, self.getServerPort()))
            elt.content(address)
            # set uptime
            elt = trElt.findmeld('uptime_td_mid')
            elt.content(simpleTime(item['uptime']))
            # set detailed process action links
            for action in self.processMethods.keys():
                elt = trElt.findmeld(action + '_a_mid')
                elt.attributes(href='index.html?processname={}&amp;address={}&amp;action={}'.format(urllib.quote(namespec), address, action))
            # set process action links
            tdElt = trElt.findmeld('strategy_td_mid')
            if rowspan > 0:
                tdElt.attrib['rowspan'] = str(rowspan)
                for action in map(str.lower, conciliationStrategiesStrings()):
                    elt = tdElt.findmeld(action + '_a_mid')
                    if elt is not None: elt.attributes(href='index.html?processname={}&amp;action={}'.format(urllib.quote(namespec), action))
            else:
                tdElt.replace('')

    def make_callback(self, namespec, action):
        """ Triggers processing iaw action requested """
        # global actions (no parameter)
        if action in self.globalMethods.keys(): return self.globalMethods[action]()
        # strategy actions
        if action in map(str.lower, conciliationStrategiesStrings()): return self.conciliationAction(namespec, action.upper())
        # process actions
        address = self.context.form.get('address')
        if action in self.processMethods.keys(): return self.processMethods[action](namespec, address)

    def refreshAction(self):
        """ Refresh web page """
        return delayedInfo('Page refreshed')

    def supRestartAction(self):
        """ Restart all Supervisor instances """
        try:
            infoSource.getSupervisorsRpcInterface().restart()
        except RPCError, e:
            return delayedError('restart: {}'.format(e))
        return delayedInfo('Supervisors restarted')

    def supShutdownAction(self):
        """ Stop all Supervisor instances """
        try:
            infoSource.getSupervisorsRpcInterface().shutdown()
        except RPCError, e:
            return delayedError('shutdown: {}'.format(e))
        return delayedInfo('Supervisors shut down')

    def stopAction(self, namespec, address):
        """ Stop the conflicting process """
        # get running addresses of process
        runningAddresses = context.getProcessFromNamespec(namespec).addresses
        try:
            from supervisors.rpcrequests import stopProcess
            stopProcess(address, namespec, False)
        except RPCError, e:
            return delayedError('stopProcess: {}'.format(e.message))
        def onWait():
            if address in runningAddresses: return NOT_DONE_YET
            return infoMessage('process {} stopped on {}'.format(namespec, address))
        onWait.delay = 0.1
        return onWait

    def keepAction(self, namespec, address):
        """ Stop the conflicting processes excepted the one running on address """
        # get running addresses of process
        addresses = context.getProcessFromNamespec(namespec).addresses
        runningAddresses = addresses.copy()
        runningAddresses.remove(address)
        try:
            from supervisors.rpcrequests import stopProcess
            for address in runningAddresses:
            	stopProcess(address, namespec, False)
        except RPCError, e:
            return delayedError('stopProcess: {}'.format(e.message))
        def onWait():
            if len(addresses) > 1: return NOT_DONE_YET
            return infoMessage('processes {} stopped, keeping the one running on {}'.format(namespec, address))
        onWait.delay = 0.1
        return onWait

    def conciliationAction(self, namespec, action):
        """ Performs the automatic concicliation to solve the conflicts """
        conciliator.conciliate(stringToConciliationStrategy(action), [ context.getProcessFromNamespec(namespec) ])
        return delayedInfo('{} in progress for {}'.format(action, namespec))

