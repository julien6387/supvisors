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
from supervisors.options import options
from supervisors.remote import remoteStateToString, RemoteStates
from supervisors.statemachine import fsm
from supervisors.types import SupervisorsStates, supervisorsStateToString

from supervisor.http import NOT_DONE_YET
from supervisor.options import make_namespec
from supervisor.states import RUNNING_STATES, STOPPED_STATES
from supervisor.web import *

import urllib

# -----------------------------------------
# common utils
def writeNav(root, serverPort, address=None, appli=None):
    # update navigation addresses
    iterator = root.findmeld('address_li_mid').repeat(addressMapper.expectedAddresses)
    for li_element, item in iterator:
        state = context.remotes[item].state
        # set element class
        li_element.attrib['class'] = remoteStateToString(state) + (' active' if address and item == address else '')
        # set hyperlink attributes
        elt = li_element.findmeld('address_a_mid')
        if state == RemoteStates.RUNNING:
            # go to web page located on address, so as to reuse Supervisor StatusView
            elt.attributes(href='http://{}:{}/address.html?address={}'.format(item, serverPort, urllib.quote(item)))
            elt.attrib['class'] = 'on'
        else:
            elt.attrib['class'] = 'off'
        elt.content(item)
    # update navigation applications
    iterator = root.findmeld('appli_li_mid').repeat(context.applications.keys())
    for li_element, item in iterator:
        state = context.applications[item].state
        # set element class
        li_element.attrib['class'] = applicationStateToString(state) + (' active' if appli and item == appli else '')
        # set hyperlink attributes
        elt = li_element.findmeld('appli_a_mid')
        # go to web page located on Supervisors Master, so as to simplify requests
        if fsm.state == SupervisorsStates.INITIALIZATION:
            elt.attrib['class'] = 'off'
        else:
            elt.attributes(href='http://{}:{}/application.html?appli={}'.format(context.masterAddress, serverPort, urllib.quote(item)))
            elt.attrib['class'] = 'on'
        elt.content(item)

def printMessage(root, gravity, message):
    # print message as a result of action
    if message is not None:
        messageField = root.findmeld('message_mid')
        messageField.attrib['class'] = gravity
        messageField.content(message)


# -----------------------------------------
# Supervisors main page
class SupervisorsView(MeldView):
    def render(self):
        form = self.context.form
        serverPort = form.get('SERVER_PORT')
        # clone the template and set navigation menu
        root = self.clone()
        writeNav(root, serverPort, None)
        #TODO: write synoptic
        return root.write_xhtmlstring()


# -----------------------------------------
# Supervisors address page
class AddressView(StatusView):
    # Rendering part
    def render(self):
        form = self.context.form
        # get parameters
        serverPort = form.get('SERVER_PORT')
        self.address = form.get('address')
        # clone the template and set navigation menu
        root = self.clone()
        writeNav(root, serverPort, address=self.address)
        self._writeHeader(root)
        if self.address is None:
            options.logger.error('no address')
            printMessage(root, 'warn', 'no address requested')
        elif self.address not in addressMapper.expectedAddresses:
            options.logger.error('unknown address %s' % self.address)
            printMessage(root, 'error', 'unknown address: %s' % self.address)
        else:
            # manage action
            message = self.handleAction()
            if message is NOT_DONE_YET: return NOT_DONE_YET
            # display result
            printMessage(root, 'info', self.context.form.get('message'))
            self._renderGlobalActions(root)
            self._renderProcesses(root)
        return root.write_xhtmlstring()

    def _writeHeader(self, root):
        # set address name
        elt = root.findmeld('address_mid')
        elt.content(self.address)
        # set address state
        remote = context.remotes[self.address]
        elt = root.findmeld('state_mid')
        elt.content(remoteStateToString(remote.state))
        # set last tick date: remoteTime and localTime should be identical since self is running on the 'remote' address
        remote = context.remotes[self.address]
        elt = root.findmeld('date_mid')
        elt.content(time.ctime(remote.remoteTime))

    def _renderGlobalActions(self, root):
        # set hyperlinks for global actions
        elt = root.findmeld('refresh_a_mid')
        elt.attributes(href='address.html?address={}&amp;action=refresh'.format(self.address))
        elt = root.findmeld('stopall_a_mid')
        elt.attributes(href='address.html?address={}&amp;action=stopall'.format(self.address))
        elt = root.findmeld('restartsup_a_mid')
        elt.attributes(href='address.html?address={}&amp;action=restartsup'.format(self.address))
        elt = root.findmeld('shutdownsup_a_mid')
        elt.attributes(href='address.html?address={}&amp;action=shutdownsup'.format(self.address))

    def _renderProcesses(self, root):
        # collect data on processes
        data = [ ]
        try:
            from supervisors.rpcrequests import getAllProcessInfo
            for processinfo in getAllProcessInfo(self.address):
                data.append((make_namespec(processinfo['group'], processinfo['name']), processinfo['statename'], processinfo['state'], processinfo['description'] ))
        except RPCError, e:
            options.logger.warn('failed to get all process info from {}: {}'.format(self.address, e))
        # print processes
        if data:
            iterator = root.findmeld('tr_mid').repeat(data)
            shaded_tr = False # used to invert background style
            for tr_element, item in iterator:
                # print process name
                elt = tr_element.findmeld('name_a_mid')
                elt.attributes(href='tail.html?address={}&amp;processname={}'.format(self.address, urllib.quote(item[0])))
                elt.content(item[0])
                # print state
                elt = tr_element.findmeld('state_td_mid')
                elt.attrib['class'] = item[1]
                elt.content(item[1])
                # print description
                elt = tr_element.findmeld('desc_td_mid')
                elt.content(item[3])
                # manage process actions iaw state
                # start button
                elt = tr_element.findmeld('start_a_mid')
                if item[2] in STOPPED_STATES:
                    elt.attrib['class'] = 'button on'
                    elt.attributes(href='address.html?address={}&amp;processname={}&amp;action=start'.format(self.address, urllib.quote(item[0])))
                else:
                   elt.attrib['class'] = 'button off'
                # stop button
                elt = tr_element.findmeld('stop_a_mid')
                if item[2] in RUNNING_STATES:
                    elt.attrib['class'] = 'button on'
                    elt.attributes(href='address.html?address={}&amp;processname={}&amp;action=stop'.format(self.address, urllib.quote(item[0])))
                else:
                   elt.attrib['class'] = 'button off'
                # restart button
                elt = tr_element.findmeld('restart_a_mid')
                if item[2] in RUNNING_STATES:
                    elt.attrib['class'] = 'button on'
                    elt.attributes(href='address.html?address={}&amp;processname={}&amp;action=restart'.format(self.address, urllib.quote(item[0])))
                else:
                   elt.attrib['class'] = 'button off'
                # manage process log actions
                elt = tr_element.findmeld('clear_a_mid')
                elt.attributes(href='address.html?address={}&amp;processname={}&amp;action=clearlog'.format(self.address, urllib.quote(item[0])))
                elt = tr_element.findmeld('tail_a_mid')
                elt.attributes(href='logtail.html?address={}&amp;processname={}&amp'.format(self.address, urllib.quote(item[0])), target='_blank')
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
                location = form['SERVER_URL'] + form['PATH_TRANSLATED'] + '?address={}&amp;message={}'.format(self.address, urllib.quote(message))
                self.context.response['headers']['Location'] = location

    def make_callback(self, namespec, action):
        if action == 'restartsup':
            return self.restartSupAction()
        if action == 'shutdownsup':
            return self.shutdownSupAction()
        return StatusView.make_callback(self, namespec, action)

    def restartSupAction(self):
        from supervisors.rpcrequests import restart
        restart(self.address)
        # cannot defer result if restart address is self address
        # message is sent but it will be likely not displayed
        if addressMapper.localAddress == self.address:
            return self.infoFunction('Supervisor restart requested')
        # deferred result should relies on Supervisors remote state
        def onWait():
            # first wait for remote Supervisor to stop
            if onWait.waitDown:
                if checkDown(True):
                    # remote Supervisor is down. wait back again
                    onWait.waitDown = False
                    return NOT_DONE_YET
            if checkDown(False):
                # remote Supervisor is back
                return self.infoMessage('Supervisor restarted')
            return NOT_DONE_YET
        onWait.delay = 0.5
        onWait.waitDown = True
        return onWait

    def shutdownSupAction(self):
        from supervisors.rpcrequests import shutdown
        shutdown(self.address)
        # cannot defer result if shutdown address is self address
        if addressMapper.localAddress == self.address:
            return self.infoFunction('Supervisor shutdown requested')
       # deferred result relies on Supervisor not reachable
        def onWait():
            # wait for remote Supervisor to stop
            if checkDown(True):
                # remote Supervisor is down
                return self.infoMessage('Supervisor shut down')
            return NOT_DONE_YET
        onWait.delay = 0.5
        return onWait

    def infoMessage(self, msg):
        return msg + ' at {} on {}'.format(time.ctime(), self.address)

    def infoFunction(self, msg):
        def msgFunction():
            return self.infoMessage(msg)
        msgFunction.delay = 0.05
        return msgFunction

    def checkDown(self, down):
        try:
            from supervisors.rpcrequests import getSupervisorsState
            getSupervisorsState(self.address)
            return not down
        except:
            return down


# -----------------------------------------
# Supervisors application page
class ApplicationView(MeldView):
    # Rendering part
    def render(self):
        form = self.context.form
        # get parameters
        self.applicationName = form.get('appli')
        serverPort = form.get('SERVER_PORT')
        # clone the template and set navigation menu
        root = self.clone()
        writeNav(root, serverPort, appli=self.applicationName)
        self._writeHeader(root)
        if self.applicationName is None:
            options.logger.error('no application')
            printMessage(root, 'warn', 'no application requested')
        elif self.applicationName not in context.applications.keys():
            options.logger.error('unknown application: %s' % self.applicationName)
            printMessage(root, 'error', 'unknown application: %s' % self.applicationName)
        else:
            # manage action
            message = self.handleAction()
            if message is NOT_DONE_YET: return NOT_DONE_YET
            # display result
            printMessage(root, 'info', self.context.form.get('message'))
            self._renderGlobalActions(root)
            self._renderProcesses(root)
        return root.write_xhtmlstring()

    def _writeHeader(self, root):
        # set address name
        elt = root.findmeld('application_mid')
        elt.content(self.applicationName)
        # set application state
        state = context.applications[self.applicationName].state
        elt = root.findmeld('state_mid')
        elt.content(applicationStateToString(state))
        # TODO: set LEDs iaw major/minor failures
        elt = root.findmeld('major_mid')
        elt = root.findmeld('minor_mid')


    def _renderGlobalActions(self, root):
        # set hyperlinks for global actions
        elt = root.findmeld('refresh_a_mid')
        elt.attributes(href='application.html?appli={}&amp;action=refresh'.format(self.applicationName))
        elt = root.findmeld('startapp_a_mid')
        elt.attributes(href='application.html?appli={}&amp;action=startapp'.format(self.applicationName))
        elt = root.findmeld('stopapp_a_mid')
        elt.attributes(href='application.html?appli={}&amp;action=stopapp'.format(self.applicationName))
        elt = root.findmeld('restartapp_a_mid')
        elt.attributes(href='application.html?appli={}&amp;action=restartapp'.format(self.applicationName))

    def _renderProcesses(self, root):
        # collect data on processes
        data = [ ]
        for process in context.applications[self.applicationName].processes.values():
            data.append((process.processName, process.stateAsString(), process.state, list(process.addresses)))
        # print processes
        if data:
            iterator = root.findmeld('tr_mid').repeat(data)
            shaded_tr = False # used to invert background style
            for tr_element, item in iterator:
                # print process name. link is for TODO stats
                elt = tr_element.findmeld('name_a_mid')
                elt.attributes(href='#')
                elt.content(item[0])
                # print state
                elt = tr_element.findmeld('state_td_mid')
                elt.attrib['class'] = item[1]
                elt.content(item[1])
                # print running addresses
                if item[3]:
                    addrIterator = tr_element.findmeld('running_li_mid').repeat(item[3])
                    for li_element, address in addrIterator:
                        elt = li_element.findmeld('running_a_mid')
                        elt.attributes(href='address.html?address={}'.format(address))
                        elt.content(address)
                else:
                    elt = tr_element.findmeld('running_ul_mid')
                    elt.replace('')
                # manage actions iaw state
                elt = tr_element.findmeld('start_a_mid')
                elt.attrib['class'] = 'button {}'.format('on' if item[2] in STOPPED_STATES else 'off') 
                elt.attributes(href='application.html?appli={}&amp;processname={}&amp;action=start'.format(self.applicationName, urllib.quote(item[0])))
                elt = tr_element.findmeld('stop_a_mid')
                elt.attrib['class'] = 'button {}'.format('on' if item[2] in RUNNING_STATES else 'off')
                elt.attributes(href='application.html?appli={}&amp;processname={}&amp;action=stop'.format(self.applicationName, urllib.quote(item[0])))
                elt = tr_element.findmeld('restart_a_mid')
                elt.attrib['class'] = 'button {}'.format('on' if item[2] in RUNNING_STATES else 'off')
                elt.attributes(href='application.html?appli={}&amp;processname={}&amp;action=restart'.format(self.applicationName, urllib.quote(item[0])))
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
            processname = form.get('processname')
            if not self.callback:
                self.callback = self.make_callback(processname, action)
                return NOT_DONE_YET
            # intermediate check
            message = self.callback()
            if message is NOT_DONE_YET: return NOT_DONE_YET
            # post to write message
            if message is not None:
                location = form['SERVER_URL'] + form['PATH_TRANSLATED'] + '?appli={}&amp;message={}'.format(self.applicationName, urllib.quote(message))
                self.context.response['headers']['Location'] = location

    def make_callback(self, namespec, action):
        if action == 'refresh':
        		return self.refreshAction()
        if action == 'startapp':
            return self.startApplicationAction()
        if action == 'stopapp':
            return self.stopApplicationAction()
        if action == 'restartapp':
            return self.restartApplicationAction()

    def refreshAction(self):
        return self.infoFunction('Page refreshed', 'TODO')

    def startApplicationAction(self):
        from supervisors.rpcrequests import restart
        startApplication(self.address)
        # cannot defer result if restart address is self address
        # message is sent but it will be likely not displayed
        if addressMapper.localAddress == self.address:
            return self.infoFunction('Supervisor restart requested')
        # deferred result should relies on Supervisors remote state
        def onWait():
            # first wait for remote Supervisor to stop
            if onWait.waitDown:
                if checkDown(True):
                    # remote Supervisor is down. wait back again
                    onWait.waitDown = False
                    return NOT_DONE_YET
            if checkDown(False):
                # remote Supervisor is back
                return self.infoMessage('Supervisor restarted')
            return NOT_DONE_YET
        onWait.delay = 0.5
        onWait.waitDown = True
        return onWait

 
    def infoMessage(self, msg, address):
        return msg + ' at {} on {}'.format(time.ctime(), address)

    def infoFunction(self, msg, address):
        def msgFunction():
            return self.infoMessage(msg, address)
        msgFunction.delay = 0.05
        return msgFunction


# -----------------------------------------
# Trick to replace Supervisor main page
def updateUiHandler():
    # replace Supervisor main entry
    here = os.path.abspath(os.path.dirname(__file__))
    VIEWS['index.html'] =  { 'template': os.path.join(here, 'ui/index.html'), 'view': SupervisorsView }
    VIEWS['address.html'] =  { 'template': os.path.join(here, 'ui/address.html'), 'view': AddressView }
    VIEWS['application.html'] =  { 'template': os.path.join(here, 'ui/application.html'), 'view': ApplicationView }
