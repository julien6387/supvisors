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

from supervisor.http import NOT_DONE_YET
from supervisor.web import MeldView
from supervisor.xmlrpc import RPCError

from supervisors.remote import remoteStateToString, RemoteStates
from supervisors.strategy import conciliate
from supervisors.types import ConciliationStrategies, conciliationStrategyToString, conciliationStrategiesStrings, stringToConciliationStrategy, SupervisorsStates, supervisorsStateToString
from supervisors.utils import simpleGmTime
from supervisors.viewhandler import ViewHandler
from supervisors.webutils import *


class SupervisorsView(MeldView, ViewHandler):
    """ Class ensuring the rendering of the Supervisors main page with:
    * a navigation menu towards addresses contents and applications
    * the state of Supervisors
    * actions on Supervisors
    * a synoptic of the processes running on the different addresses
    * in CONCILIATION state only, the synoptic is replaced by a table of conflicts with tools to solve them """

    # Name of the HTML page
    pageName = 'index.html'

    def __init__(self, context):
        """ Constructor stores actions for easy access """
        MeldView.__init__(self, context)
        self.supervisors = self.context.supervisord.supervisors
        # get applicable conciliation strategies
        self.strategies = map(str.lower, conciliationStrategiesStrings())
        self.strategies.remove(conciliationStrategyToString(ConciliationStrategies.USER).lower())
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
        root.findmeld('state_mid').content(supervisorsStateToString(self.supervisors.fsm.state))

    def writeContents(self, root):
        """ Rendering of the contents of the Supervisors main page
        This builds either a synoptic of the processes running on the addresses or the table of conflicts if any """
        if self.supervisors.fsm.state == SupervisorsStates.CONCILIATION and self.supervisors.context.getConflicts():
            # remove address boxes
            root.findmeld('boxes_div_mid').replace('')
            # write conflicts
            self.writeConciliationStrategies(root)
            self.writeConciliationTable(root)
        else:
            # remove conflicts table
            root.findmeld('conflicts_div_mid').replace('')
            # write address boxes
            self.writeAddressBoxes(root)

    def writeAddressBoxes(self, root):
        """ Rendering of the addresses boxes """
        addressIterator = root.findmeld('address_div_mid').repeat(self.supervisors.address_mapper.addresses)
        for divElt, address in addressIterator:
            status = self.supervisors.context.remotes[address]
            # set address
            elt = divElt.findmeld('address_tda_mid')
            if status.state == RemoteStates.RUNNING:
                # go to web page located on address, so as to reuse Supervisor StatusView
                elt.attributes(href='http://{}:{}/address.html'.format(urllib.quote(address), self.getServerPort()))
                elt.attrib['class'] = 'on'
            elt.content(address)
            # set state
            elt = divElt.findmeld('state_td_mid')
            elt.attrib['class'] = remoteStateToString(status.state) + ' state'
            elt.content(remoteStateToString(status.state))
            # set loading
            elt = divElt.findmeld('percent_td_mid')
            elt.content('{}%'.format(self.supervisors.context.getLoading(address)))
            # fill with running processes
            data = self.supervisors.context.getRunningProcesses(address)
            processIterator = divElt.findmeld('process_li_mid').repeat(data)
            for liElt, process in processIterator:
                liElt.content(process.getNamespec())

    def writeConciliationStrategies(self, root):
        """ Rendering of the global conciliation actions """
        divElt = root.findmeld('conflicts_div_mid')
        strategyIterator = divElt.findmeld('global_strategy_li_mid').repeat(self.strategies)
        for liElt, item in strategyIterator:
           elt = liElt.findmeld('global_strategy_a_mid')
           # conciliation requests MUST be sent to MASTER
           elt.attributes(href='http://{}:{}/index.html?action={}'.format(self.supervisors.context.master_address, self.getServerPort(), item))
           elt.content(item.title())

    def writeConciliationTable(self, root):
        """ Rendering of the conflicts table """
        divElt = root.findmeld('conflicts_div_mid')
        # get data for table
        data = [ { 'namespec': process.getNamespec(), 'rowspan': len(process.addresses) if idx == 0 else 0,
            'address': address, 'uptime': process.processes[address]['uptime'] }
            for process in self.supervisors.context.getConflicts() for idx, address in enumerate(process.addresses) ]
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
            elt.content(simpleGmTime(item['uptime']))
            # set detailed process action links
            for action in self.processMethods.keys():
                elt = trElt.findmeld(action + '_a_mid')
                elt.attributes(href='index.html?processname={}&amp;address={}&amp;action={}'.format(urllib.quote(namespec), address, action))
            # set process action links
            tdElt = trElt.findmeld('strategy_td_mid')
            if rowspan > 0:
                tdElt.attrib['rowspan'] = str(rowspan)
                strategyIterator = tdElt.findmeld('local_strategy_li_mid').repeat(self.strategies)
                for liElt, item in strategyIterator:
                    elt = liElt.findmeld('local_strategy_a_mid')
                    # conciliation requests MUST be sent to MASTER
                    elt.attributes(href='http://{}:{}/index.html?processname={}&amp;action={}'.format(self.supervisors.context.master_address, self.getServerPort(),
                        urllib.quote(namespec), item))
                    elt.content(item.title())
            else:
                tdElt.replace('')

    def make_callback(self, namespec, action):
        """ Triggers processing iaw action requested """
        # global actions (no parameter)
        if action in self.globalMethods.keys():
            return self.globalMethods[action]()
        # strategy actions
        if action in self.strategies:
            return self.conciliationAction(namespec, action.upper())
        # process actions
        address = self.context.form.get('address')
        if action in self.processMethods.keys():
            return self.processMethods[action](namespec, address)

    def refreshAction(self):
        """ Refresh web page """
        return delayedInfo('Page refreshed')

    def supRestartAction(self):
        """ Restart all Supervisor instances """
        try:
            self.supervisors.infoSource.getSupervisorsRpcInterface().restart()
        except RPCError, e:
            return delayedError('restart: {}'.format(e))
        return delayedInfo('Supervisors restarted')

    def supShutdownAction(self):
        """ Stop all Supervisor instances """
        try:
            self.supervisors.infoSource.getSupervisorsRpcInterface().shutdown()
        except RPCError, e:
            return delayedError('shutdown: {}'.format(e))
        return delayedInfo('Supervisors shut down')

    def stopAction(self, namespec, address):
        """ Stop the conflicting process """
        # get running addresses of process
        runningAddresses = self.supervisors.context.getProcessFromNamespec(namespec).addresses
        try:
            self.supervisors.requester.stopProcess(address, namespec, False)
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
        addresses = self.supervisors.context.getProcessFromNamespec(namespec).addresses
        runningAddresses = addresses.copy()
        runningAddresses.remove(address)
        try:
            for address in runningAddresses:
            	self.supervisors.requester.stopProcess(address, namespec, False)
        except RPCError, e:
            return delayedError('stopProcess: {}'.format(e.message))
        def onWait():
            if len(addresses) > 1: return NOT_DONE_YET
            return infoMessage('processes {} stopped, keeping the one running on {}'.format(namespec, address))
        onWait.delay = 0.1
        return onWait

    def conciliationAction(self, namespec, action):
        """ Performs the automatic conciliation to solve the conflicts """
        if namespec:
            # conciliate only one process
            conciliate(self.supervisors, stringToConciliationStrategy(action), [self.supervisors.context.getProcessFromNamespec(namespec)])
            return delayedInfo('{} in progress for {}'.format(action, namespec))
        else:
            # conciliate all conflicts
            conciliate(self.supervisors, stringToConciliationStrategy(action), self.supervisors.context.getConflicts())
            return delayedInfo('{} in progress for all conflicts'.format(action))
