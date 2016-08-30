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
from supervisors.infosource import infoSource
from supervisors.options import options
from supervisors.remote import remoteStateToString, RemoteStates
from supervisors.statemachine import fsm
from supervisors.types import DeploymentStrategies, SupervisorsStates, supervisorsStateToString

from supervisor.http import NOT_DONE_YET
from supervisor.options import make_namespec
from supervisor.states import SupervisorStates, RUNNING_STATES, STOPPED_STATES
from supervisor.web import *

import urllib

# TODO: list:
#   2) tail page
#   3) statistics
#   4) check if deployable for buttons (address / resource) ?
#   6) style for states
#   7) conciliation page

# -----------------------------------------
# common utils

# gravity classes for messages
# use of 'erro' instead of 'error' in order to avoid HTTP error log traces
Info='info'
Warn = 'warn'
Error = 'erro'

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

def formatGravityMessage(message):
    if not isinstance(message, tuple):
        # gravity is not set by Supervisor so let's deduce it
        if 'ERROR' in message:
            message = message.replace('ERROR: ', '')
            gravity = Error
        else:
            gravity = Info
        return (gravity, message)
    return message

def printMessage(root, gravity, message):
    # print message as a result of action
    if message is not None:
        elt = root.findmeld('message_mid')
        elt.attrib['class'] = gravity
        elt.content(message)

def infoMessage(msg, address=None):
    return (Info, msg + ' at {}'.format(time.ctime()) + (' on {}'.format(address) if address else ''))

def warnMessage(msg, address=None):
    return (Warn, msg + ' at {}'.format(time.ctime()) + (' on {}'.format(address) if address else ''))

def errorMessage(msg, address=None):
    return (Error, msg + ' at {}'.format(time.ctime()) + (' on {}'.format(address) if address else ''))

def delayedInfo(msg, address=None):
    def onWait():
        return infoMessage(msg, address)
    onWait.delay = 0.05
    return onWait

def delayedWarn(msg, address=None):
    def onWait():
        return warnMessage(msg, address)
    onWait.delay = 0.05
    return onWait

def delayedError(msg, address=None):
    def onWait():
        return errorMessage(msg, address)
    onWait.delay = 0.05
    return onWait


# -----------------------------------------
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
            # set cell color
            elt = div_element.findmeld('address_td_mid')
            elt.attrib['class'] = remoteStateToString(status.state)
            # set address
            elt = elt.findmeld('address_tda_mid')
            elt.attrib['class'] = remoteStateToString(status.state)
            if status.state == RemoteStates.RUNNING:
                # go to web page located on address, so as to reuse Supervisor StatusView
                elt.attributes(href='http://{addr}:{port}/address.html?address={addr}'.format(addr= urllib.quote(address), port=serverPort))
                elt.attrib['class'] = 'on'
            else:
                elt.attrib['class'] = 'off'
            elt.content(address)
            # set loading
            elt = div_element.findmeld('percent_td_mid')
            elt.content('{}%'.format(context.getRemoteLoading(address)))
            # fill with running processes
            data = context.getRemoteRunningProcesses(address)
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


# -----------------------------------------
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
        elt.content('{}%'.format(context.getRemoteLoading(addressMapper.localAddress)))
        # set last tick date: remoteTime and localTime should be identical since self is running on the 'remote' address
        elt = root.findmeld('date_mid')
        elt.content(time.ctime(remote.remoteTime))

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


# -----------------------------------------
# Supervisors application page
class ApplicationView(MeldView):
    # Rendering part
    def render(self):
        # clone the template and set navigation menu
        root = self.clone()
        if infoSource.supervisorState == SupervisorStates.RUNNING:
            # get parameters
            form = self.context.form
            self.applicationName = form.get('appli')
            serverPort = form.get('SERVER_PORT')
            # write navigation menu and Application header
            writeNav(root, serverPort, appli=self.applicationName)
            self._writeHeader(root)
            if self.applicationName is None:
                options.logger.error('no application')
                printMessage(root, Warning, 'no application requested')
            elif self.applicationName not in context.applications.keys():
                options.logger.error('unknown application: %s' % self.applicationName)
                printMessage(root, Error, 'unknown application: %s' % self.applicationName)
            else:
                # manage action
                message = self.handleAction()
                if message is NOT_DONE_YET: return NOT_DONE_YET
                # display result
                printMessage(root, self.context.form.get('gravity'), self.context.form.get('message'))
                self._renderGlobalActions(root)
                self._renderDeploymentStrategy(root)
                self._renderProcesses(root)
        return root.write_xhtmlstring()

    def _writeHeader(self, root):
        # set address name
        elt = root.findmeld('application_mid')
        elt.content(self.applicationName)
        # set application state
        application = context.applications[self.applicationName]
        elt = root.findmeld('state_mid')
        elt.content(applicationStateToString(application.state))
        # set LED iaw major/minor failures
        if application.isRunning():
            if application.majorFailure:
                elt.attrib['class'] = 'status_red'
            elif application.minorFailure:
                elt.attrib['class'] = 'status_yellow'
            else:
                elt.attrib['class'] = 'status_green'
        else:
            elt.attrib['class'] = 'status_empty'

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

    def _renderDeploymentStrategy(self, root):
        # get the current strategy
        from supervisors.deployer import deployer
        strategy = deployer.strategy
        # set hyperlinks for strategy actions
        elt = root.findmeld('config_a_mid')
        elt.attributes(href='application.html?appli={}&amp;action=config'.format(self.applicationName))
        if strategy == DeploymentStrategies.CONFIG: elt.attrib['class'] = "button on active"
        elt = root.findmeld('most_a_mid')
        elt.attributes(href='application.html?appli={}&amp;action=most'.format(self.applicationName))
        if strategy == DeploymentStrategies.MOST_LOADED: elt.attrib['class'] = "button on active"
        elt = root.findmeld('less_a_mid')
        elt.attributes(href='application.html?appli={}&amp;action=less'.format(self.applicationName))
        if strategy == DeploymentStrategies.LESS_LOADED: elt.attrib['class'] = "button on active"

    def _renderProcesses(self, root):
        # collect data on processes
        data = [ ]
        for process in sorted(context.applications[self.applicationName].processes.values(), key=lambda x: x.processName):
            data.append((process.processName, process.getNamespec(), process.stateAsString(), process.state, list(process.addresses)))
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
                elt.attrib['class'] = item[2]
                elt.content(item[2])
                # print running addresses
                if item[4]:
                    addrIterator = tr_element.findmeld('running_li_mid').repeat(item[4])
                    for li_element, address in addrIterator:
                        elt = li_element.findmeld('running_a_mid')
                        elt.attributes(href='address.html?address={}'.format(address))
                        elt.content(address)
                else:
                    elt = tr_element.findmeld('running_ul_mid')
                    elt.replace('')
                # manage actions iaw state
                elt = tr_element.findmeld('start_a_mid')
                elt.attrib['class'] = 'button {}'.format('on' if item[3] in STOPPED_STATES else 'off') 
                elt.attributes(href='application.html?appli={}&amp;processname={}&amp;action=start'.format(self.applicationName, urllib.quote(item[1])))
                elt = tr_element.findmeld('stop_a_mid')
                elt.attrib['class'] = 'button {}'.format('on' if item[3] in RUNNING_STATES else 'off')
                elt.attributes(href='application.html?appli={}&amp;processname={}&amp;action=stop'.format(self.applicationName, urllib.quote(item[1])))
                elt = tr_element.findmeld('restart_a_mid')
                elt.attrib['class'] = 'button {}'.format('on' if item[3] in RUNNING_STATES else 'off')
                elt.attributes(href='application.html?appli={}&amp;processname={}&amp;action=restart'.format(self.applicationName, urllib.quote(item[1])))
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
                location = form['SERVER_URL'] + form['PATH_TRANSLATED'] + '?appli={}&amp;message={}&amp;gravity={}'.format(self.applicationName, urllib.quote(message[1]), message[0])
                self.context.response['headers']['Location'] = location

    def make_callback(self, namespec, action):
        if action == 'refresh':
            return self.refreshAction()
        if action == 'config':
            return self.setDeploymentStrategy(DeploymentStrategies.CONFIG)
        if action == 'most':
            return self.setDeploymentStrategy(DeploymentStrategies.MOST_LOADED)
        if action == 'less':
            return self.setDeploymentStrategy(DeploymentStrategies.LESS_LOADED)
        # get current strategy
        from supervisors.deployer import deployer
        strategy = deployer.strategy
        if action == 'startapp':
            return self.startApplicationAction(strategy)
        if action == 'stopapp':
            return self.stopApplicationAction()
        if action == 'restartapp':
            return self.restartApplicationAction(strategy)
        if namespec:
            try:
                context.getProcessFromNamespec(namespec)
            except:
                return delayedError('No such process named %s' % namespec)
            if action == 'start':
                return self.startProcessAction(strategy, namespec)
            if action == 'stop':
                return self.stopProcessAction(namespec)
            if action == 'restart':
                return self.restartProcessAction(strategy, namespec)

    def refreshAction(self):
        return delayedInfo('Page refreshed')

    def setDeploymentStrategy(self, strategy):
        from supervisors.deployer import deployer
        from supervisors.types import deploymentStrategyToString
        deployer.useStrategy(strategy)
        return delayedInfo('Deployment strategy set to {}'.format(deploymentStrategyToString(strategy)))

    # Application actions
    def startApplicationAction(self, strategy):
        try:
            cb = infoSource.getSupervisorsRpcInterface().startApplication(strategy, self.applicationName)
        except RPCError, e:
            return delayedError('startApplication: {}'.format(e.text))
        if callable(cb):
            def onWait():
                try:
                    result = cb()
                except RPCError, e:
                    return errorMessage('startApplication: {}'.format(e.text))
                if result is NOT_DONE_YET: return NOT_DONE_YET
                if result: return infoMessage('Application {} started'.format(self.applicationName))
                return warnMessage('Application {} NOT started'.format(self.applicationName))
            onWait.delay = 0.1
            return onWait
        if cb: return delayedInfo('Application {} started'.format(self.applicationName))
        return delayedWarn('Application {} NOT started'.format(self.applicationName))
 
    def stopApplicationAction(self):
        try:
            cb = infoSource.getSupervisorsRpcInterface().stopApplication(self.applicationName)
        except RPCError, e:
            return delayedError('stopApplication: {}'.format(e.text))
        if callable(cb):
            def onWait():
                try:
                    result = cb()
                except RPCError, e:
                    return errorMessage('stopApplication: {}'.format(e.text))
                if result is NOT_DONE_YET: return NOT_DONE_YET
                return infoMessage('Application {} stopped'.format(self.applicationName))
            onWait.delay = 0.1
            return onWait
        return delayedInfo('Application {} stopped'.format(self.applicationName))
 
    def restartApplicationAction(self, strategy):
        try:
            cb = infoSource.getSupervisorsRpcInterface().restartApplication(strategy, self.applicationName)
        except RPCError, e:
            return delayedError('restartApplication: {}'.format(e.text))
        if callable(cb):
            def onWait():
                try:
                    result = cb()
                except RPCError, e:
                    return errorMessage('restartApplication: {}'.format(e.text))
                if result is NOT_DONE_YET: return NOT_DONE_YET
                if result: return infoMessage('Application {} restarted'.format(self.applicationName))
                return warnMessage('Application {} NOT restarted'.format(self.applicationName))
            onWait.delay = 0.1
            return onWait
        if cb: return delayedInfo('Application {} restarted'.format(self.applicationName))
        return delayedWarn('Application {} NOT restarted'.format(self.applicationName))

    # Process actions
    def startProcessAction(self, strategy, namespec):
        try:
            cb = infoSource.getSupervisorsRpcInterface().startProcess(strategy, namespec)
        except RPCError, e:
            return delayedError('startProcess: {}'.format(e.text))
        if callable(cb):
            def onWait():
                try:
                    result = cb()
                except RPCError, e:
                    return errorMessage('startProcess: {}'.format(e.text))
                if result is NOT_DONE_YET: return NOT_DONE_YET
                if result: return infoMessage('Process {} started'.format(namespec))
                return warnMessage('Process {} NOT started'.format(namespec))
            onWait.delay = 0.1
            return onWait
        if cb: return delayedInfo('Process {} started'.format(namespec))
        return delayedWarn('Process {} NOT started'.format(namespec))

    def stopProcessAction(self, namespec):
        try:
            cb = infoSource.getSupervisorsRpcInterface().stopProcess(namespec)
        except RPCError, e:
            return delayedError('stopProcess: {}'.format(e.text))
        if callable(cb):
            def onWait():
                try:
                    result = cb()
                except RPCError, e:
                    return errorMessage('stopProcess: {}'.format(e.text))
                if result is NOT_DONE_YET: return NOT_DONE_YET
                return infoMessage('process {} stopped'.format(namespec))
            onWait.delay = 0.1
            return onWait
        return delayedInfo('process {} stopped'.format(namespec))
 
    def restartProcessAction(self, strategy, namespec):
        try:
            cb = infoSource.getSupervisorsRpcInterface().restartProcess(strategy, namespec)
        except RPCError, e:
            return delayedError('restartProcess: {}'.format(e.text))
        if callable(cb):
            def onWait():
                try:
                    result = cb()
                except RPCError, e:
                    return errorMessage('restartProcess: {}'.format(e.text))
                if result is NOT_DONE_YET: return NOT_DONE_YET
                if result: return infoMessage('Process {} restarted'.format(namespec))
                return warnMessage('Process {} NOT restarted'.format(namespec))
            onWait.delay = 0.1
            return onWait
        if cb: return delayedInfo('Process {} restarted'.format(namespec))
        return delayedWarn('Process {} NOT restarted'.format(namespec))


# -----------------------------------------
# Trick to replace Supervisor main page
def updateUiHandler():
    # replace Supervisor main entry
    here = os.path.abspath(os.path.dirname(__file__))
    VIEWS['index.html'] =  { 'template': os.path.join(here, 'ui/index.html'), 'view': SupervisorsView }
    VIEWS['address.html'] =  { 'template': os.path.join(here, 'ui/address.html'), 'view': AddressView }
    VIEWS['application.html'] =  { 'template': os.path.join(here, 'ui/application.html'), 'view': ApplicationView }

