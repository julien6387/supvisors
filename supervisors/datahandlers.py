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

from supervisors.options import mainOptions as opt
from supervisors.process import Process
from supervisors.remote import *
from supervisors.rpcrequests import getAllProcessInfo
from supervisors.authorizer import authRequester, autoFence

import time

# Applications management
class _ApplicationsHandler(object):
    # constants
    ListenerName = 'Listener'

    def cleanup(self):
        # (re-)initialize maps
        self._applications = {}
        self._processes = {}

    @property
    def applications(self): return self._applications

    # access methods
    def getProcessFromInfo(self, processInfo):
        return self.getProcess(processInfo['group'], processInfo['name'])

    def getProcessFromEvent(self, processEvent):
        return self.getProcess(processEvent['groupname'], processEvent['processname'])

    def getProcessFromNamespec(self, namespec):
        from supervisor.options import split_namespec
        applicationName, processName = split_namespec(namespec)
        return self.getProcess(applicationName, processName)

    def getProcess(self, applicationName, processName):
        return self.applications[applicationName].processes[processName]

    def getRemoteLoading(self, address):
        try:
            remoteProcesses = self._processes[address]
        except KeyError:
            # remote address has never been loaded
            return 0
        else:
            loading = sum(process.rules.expected_loading for process in remoteProcesses if process.isRunningOn(address))
            opt.logger.debug('address={} loading={}'.format(address, loading))
            return loading

    # methods
    def loadProcesses(self, address, allProcessesInfo):
        from supervisors.application import ApplicationInfo
        from supervisors.parser import parser
        # keep a dictionary address / processes
        self._processes[address] = [ ]
        # get all processes and sort them by group (application)
        # first store applications
        applicationList = { x['group'] for x  in allProcessesInfo }
        opt.logger.debug('applicationList={} from {}'.format(applicationList, address))
        # add unknown applications
        for applicationName in applicationList:
            if applicationName not in self.applications:
                application = ApplicationInfo(applicationName)
                parser.setApplicationRules(application)
                self.applications[applicationName] = application
        # store processes into their application entry
        for processInfo in allProcessesInfo:
            try:
                process = self.getProcessFromInfo(processInfo)
            except KeyError:
                # not found. add new instance
                process = Process(address, processInfo)
                parser.setProcessRules(process)
                process.setMultipleRunningAllowed((process.applicationName == self.ListenerName) and (process.processName == self.ListenerName))
                self.applications[process.applicationName].addProcess(process)
            else:
                process.addInfo(address, processInfo)
            # fill the dictionary address / processes
            self._processes[address].append(process)

    def sequenceDeployment(self):
        for application in self.applications.values():
            application.sequenceDeployment()

    def updateProcess(self, address, processEvent):
        process = self.getProcessFromEvent(processEvent)
        process.updateInfo(address, processEvent)
        self.updateApplicationStatus(process.applicationName)
        return process

    def updateApplicationStatus(self, applicationName):
        self.applications[applicationName].updateStatus()

    def updateRemoteTime(self, address, remoteTime, localTime):
        for application in self.applications.values():
            application.updateRemoteTime(address, remoteTime, localTime)

applicationsHandler = _ApplicationsHandler()


# Remotes management
class _RemotesHandler(object):
    def cleanup(self):
        # (re-)initialize map
        from supervisors.addressmapper import addressMapper
        self._remotes = { address: RemoteInfo(address) for address in addressMapper.expectedAddresses }

    @property
    def remotes(self): return self._remotes

    def getRemoteInfo(self, address):
        return self.remotes[address]

    def updateRemoteTime(self, address, remoteTime, localTime):
        status = self.getRemoteInfo(address)
        if status.state != RemoteStates.ISOLATED:
            status.updateRemoteTime(remoteTime, localTime)
            # got event from remote supervisord, should be operating
            if not status.checked and status.state != RemoteStates.CHECKING and autoFence():
                # auto fencing activated: get authorization from remote by port-knocking
                status.setState(RemoteStates.CHECKING)
                authRequester.sendRequest(address)
            elif status.state != RemoteStates.RUNNING:
                # no auto fencing, operational
                status.setState(RemoteStates.RUNNING)
                # get list of processes handled by Supervisor on that address
                applicationsHandler.loadProcesses(address, getAllProcessInfo(address))

    def authorize(self, address, permit):
        status = self.getRemoteInfo(address)
        if status.state == RemoteStates.CHECKING:
            status.setChecked(True)
            if permit:
                status.setState(RemoteStates.RUNNING)
                # get list of processes handled by Supervisor on that address
                applicationsHandler.loadProcesses(address, getAllProcessInfo(address))
            else:
                status.setState(RemoteStates.ISOLATED)
        else:
            opt.logger.error('unexpected authorization from {}'.format(address))

    def checkRemotes(self):
        # consider problem if no tick received in last 10s
        for status in self.remotes.values():
            if status.state in [ RemoteStates.CHECKING, RemoteStates.RUNNING ] and (time.time() - status.localTime) > 10:
                self.invalidRemote(status)

    def sortRemotesByState(self):
        sortedRemotes = { x: [ ] for x in remoteStatesValues() }
        for status in self.remotes.values():
            sortedRemotes[status.state].append(status.address)
        opt.logger.debug(sortedRemotes)
        return sortedRemotes

    def endSynchro(self):
        # consider problem if no tick received at the end of synchro time
        for status in self.remotes.values():
            if status.state == RemoteStates.UNKNOWN:
                self.invalidRemote(status)

    def invalidRemote(self, status):
        # declare SILENT or isolate according to option
        if autoFence():
            status.setState(RemoteStates.ISOLATED)
            # TODO: disconnect address from remote supervisor and authorizer
        else: status.setState(RemoteStates.SILENT)

remotesHandler = _RemotesHandler()
