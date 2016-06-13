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
from supervisors.options import mainOptions as opt
from supervisors.process import Process
from supervisors.remote import *

import time

# Applications management
class ApplicationsHandler(object):
    # constants
    ListenerName = 'Listener'

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

    def getLostProcesses(self):
        return [ process for process in self._getAllProcesses() if process.isRunningLost() ]

    def getRemoteLoading(self, address):
        try:
            remoteProcesses = self.processes[address]
        except KeyError:
            # remote address has never been loaded
            return 0
        else:
            loading = sum(process.rules.expected_loading for process in remoteProcesses if process.isRunningOn(address))
            opt.logger.debug('address={} loading={}'.format(address, loading))
            return loading

    # methods
    def isAddressLoaded(self, address):
        return address in self.processes

    def loadProcesses(self, address, allProcessesInfo):
        from supervisors.application import ApplicationInfo
        from supervisors.parser import parser
        # keep a dictionary address / processes
        self.processes[address] = [ ]
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
                # Supervisors' Listener is allowed to have multiple instances
                process.multipleRunningAllowed = (process.applicationName == process.processName == self.ListenerName)
                self.applications[process.applicationName].addProcess(process)
            else:
                process.addInfo(address, processInfo)
            # fill the dictionary address / processes
            self.processes[address].append(process)

    def sequenceDeployment(self):
        for application in self.applications.values():
            application.sequenceDeployment()

    def updateProcess(self, address, processEvent):
        process = self.getProcessFromEvent(processEvent)
        process.updateInfo(address, processEvent)
        # refresh application status
        self.applications[process.applicationName].updateStatus()
        return process

    def updateRemoteTime(self, address, remoteTime, localTime):
        for application in self.applications.values():
            application.updateRemoteTime(address, remoteTime, localTime)

    def invalidateAddresses(self, addresses):
        # remove address from all process.addresses
        for process in self._getAllProcesses():
            process.invalidateAddresses(addresses)

    def hasDuplicates(self):
        for process in self._getAllProcesses():
            if process.runningConflict:
                return True

    def _getAllProcesses(self):
        return [ process for application in self.applications.values() for process in application.processes.values() ]

