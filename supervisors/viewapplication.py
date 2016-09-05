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

from supervisors.application import applicationStateToString
from supervisors.context import context
from supervisors.infosource import infoSource
from supervisors.options import options
from supervisors.types import DeploymentStrategies
from supervisors.viewhandler import ViewHandler
from supervisors.webutils import *

from supervisor.http import NOT_DONE_YET
from supervisor.web import MeldView

import urllib


# Supervisors application page
class ApplicationView(MeldView, ViewHandler):
    # Name of the HTML page
    pageName = 'application.html'

    def getUrlContext(self):
        return 'appli={}&amp;'.format(self.applicationName)

    def render(self):
        """ Method called by Supervisor to handle the rendering of the Supervisors Address page """
        self.applicationName = self.context.form.get('appli')
        if self.applicationName is None:
            options.logger.error('no application')
        elif self.applicationName not in context.applications.keys():
            options.logger.error('unknown application: %s' % self.applicationName)
        else:
            return self.writePage()

    def writeNavigation(self, root):
        """ Rendering of the navigation menu with selection of the current address """
        self.writeNav(root, appli=self.applicationName)

    def writeHeader(self, root):
        """ Rendering of the header part of the Supervisors Application page """
        # set address name
        elt = root.findmeld('application_mid')
        elt.content(self.applicationName)
        # set application state
        application = context.applications[self.applicationName]
        elt = root.findmeld('state_mid')
        elt.content(applicationStateToString(application.state))
        # set LED iaw major/minor failures
        elt = root.findmeld('state_led_mid')
        if application.isRunning():
            if application.majorFailure:
                elt.attrib['class'] = 'status_red'
            elif application.minorFailure:
                elt.attrib['class'] = 'status_yellow'
            else:
                elt.attrib['class'] = 'status_green'
        else:
            elt.attrib['class'] = 'status_empty'
        # write periods of statistics
        self.writeDeploymentStrategy(root)
        self.writePeriods(root)
        # write actions related to application
        self.writeApplicationActions(root)

    def writeDeploymentStrategy(self, root):
        """ Write applicable deployment strategies """
        # get the current strategy
        from supervisors.deployer import deployer
        strategy = deployer.strategy
        # set hyperlinks for strategy actions
        # CONFIG strategy
        elt = root.findmeld('config_a_mid')
        if strategy == DeploymentStrategies.CONFIG:
            elt.attrib['class'] = "button off active"
        else:
            elt.attributes(href='{}?{}&action=config'.format(self.pageName, self.getUrlContext()))
        # MOST_LOADED strategy
        elt = root.findmeld('most_a_mid')
        if strategy == DeploymentStrategies.MOST_LOADED:
            elt.attrib['class'] = "button off active"
        else:
            elt.attributes(href='{}?{}action=most'.format(self.pageName, self.getUrlContext()))
        # LESS_LOADED strategy
        elt = root.findmeld('less_a_mid')
        if strategy == DeploymentStrategies.LESS_LOADED:
            elt.attrib['class'] = "button off active"
        else:
            elt.attributes(href='{}?{}&action=less'.format(self.pageName, self.getUrlContext()))


    def writeApplicationActions(self, root):
        """ Write actions related to the application """
        # set hyperlinks for global actions
        elt = root.findmeld('refresh_a_mid')
        elt.attributes(href='{}?{}action=refresh'.format(self.pageName, self.getUrlContext()))
        elt = root.findmeld('startapp_a_mid')
        elt.attributes(href='{}?{}action=startapp'.format(self.pageName, self.getUrlContext()))
        elt = root.findmeld('stopapp_a_mid')
        elt.attributes(href='{}?{}action=stopapp'.format(self.pageName, self.getUrlContext()))
        elt = root.findmeld('restartapp_a_mid')
        elt.attributes(href='{}?{}action=restartapp'.format(self.pageName, self.getUrlContext()))

    def writeContents(self, root):
        """ Rendering of the contents part of the page """
        self.writeProcessTable(root)
        # check selected Process Statistics
        if ViewHandler.namespecStats:
            procStatus = self.getProcessStatus(ViewHandler.namespecStats)
            if procStatus is None or procStatus.applicationName != self.applicationName:
                options.logger.warn('unselect Process Statistics for {}'.format(ViewHandler.namespecStats))
                ViewHandler.namespecStats = ''
            else:
                # addtional information for title
                elt = root.findmeld('address_fig_mid')
                elt.content(next(iter(procStatus.addresses), ''))
        # write selected Process Statistics
        self.writeProcessStatistics(root)

    def getProcessStats(self, namespec):
        """ Get the statistics structure related to the period selected and the address where the process named namespec is running """
        procStatus = self.getProcessStatus(namespec)
        if procStatus:
            # get running address from procStatus
            address = next(iter(procStatus.processes), None)
            if address:
                from supervisors.statistics import statisticsCompiler
                stats = statisticsCompiler.data[address][ViewHandler.periodStats]
                if namespec in stats.proc.keys():
                    return stats.proc[namespec]

    def writeProcessTable(self, root):
        """ Rendering of the application processes managed through Supervisor """
        # collect data on processes
        data = [ ]
        for process in sorted(context.applications[self.applicationName].processes.values(), key=lambda x: x.processName):
            data.append({ 'processname': process.processName, 'namespec': process.getNamespec(),
                'statename': process.stateAsString(), 'state': process.state, 'runninglist': list(process.addresses) })
        # print processes
        if data:
            iterator = root.findmeld('tr_mid').repeat(data)
            shaded_tr = False # used to invert background style
            for trElt, item in iterator:
                # get first item in running list
                runningList = item['runninglist']
                address = next(iter(runningList), None)
                # write common status
                selected_tr = self.writeCommonProcessStatus(trElt, item)
                # print process name (tail NOT allowed if STOPPED)
                processName = item['processname']
                namespec = item['namespec']
                if address:
                    elt = trElt.findmeld('name_a_mid')
                    elt.attributes(href='http://{}:{}/tail.html?processname={}'.format(address, self.getServerPort(), urllib.quote(namespec)))
                    elt.content(processName)
                else:
                    elt = trElt.findmeld('name_a_mid')
                    elt.replace(processName)
                # print running addresses
                if runningList:
                    addrIterator = trElt.findmeld('running_li_mid').repeat(runningList)
                    for liElt, address in addrIterator:
                        elt = liElt.findmeld('running_a_mid')
                        elt.attributes(href='address.html?address={}'.format(address))
                        elt.content(address)
                else:
                    elt = trElt.findmeld('running_ul_mid')
                    elt.replace('')
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
            if self.getProcessStatus(namespec) is None:
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
