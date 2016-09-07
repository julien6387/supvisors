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
from supervisors.deployer import deployer
from supervisors.options import options
from supervisors.process import *
from supervisors.publisher import eventPublisher
from supervisors.remote import *
from supervisors.rpcrequests import getAllProcessInfo, getRemoteInfo

import time

# Context management
class _Context(object):
    def restart(self):
        """ Reinitialize attributes """
        self.remotes = { address: RemoteStatus(address) for address in addressMapper.expectedAddresses }
        self.applications = {} # { applicationName: ApplicationStatus }
        self.master = False
        self.masterAddress = ''

    # methods on remotes
    def unknownRemotes(self): return self._remotesByStates([ RemoteStates.UNKNOWN ])
    def runningRemotes(self): return self._remotesByStates([ RemoteStates.RUNNING ])
    def isolatingRemotes(self): return self._remotesByStates([ RemoteStates.ISOLATING ])

    def _remotesByStates(self, states):
        """ Return the RemoteStatus instances sorted by state """
        return [ status.address for status in self.remotes.values() if status.state in states ]

    def getRunningProcesses(self, address):
        """ Return the process running on the address
        here, running means that the process state is in Supervisor RUNNING_STATES """
        return [ process for process in self._getAllProcesses() if process.isRunningOn(address) ]

    def getPidProcesses(self, address):
        """ Return the process running on the address and having a pid
       different from getRunningProcesses because it excludes the states STARTING and BACKOFF """
        return [ process for process in self._getAllProcesses() if process.hasRunningPidOn(address) ]

    def getLoading(self, address):
        """ Return the loading of the address, by summing the declared loading of the processes running on that address """
        loading = sum(process.rules.expected_loading for process in self.getRunningProcesses(address))
        options.logger.debug('address={} loading={}'.format(address, loading))
        return loading

    def endSynchro(self):
        """ Declare as SILENT the RemotesStatus that are still not responsive at the end of the INITIALIZATION state of Supervisors """
        # consider problem if no tick received at the end of synchro time
        map(self._invalidRemote, filter(lambda x: x.state == RemoteStates.UNKNOWN, self.remotes.values()))

    def _invalidRemote(self, status):
        # declare SILENT or isolate according to option
        # never isolate local address. may be a problem with Listener. give it a chance to restart
        if options.autoFence and status.address != addressMapper.localAddress:
            status.state = RemoteStates.ISOLATING
        else:
            status.state = RemoteStates.SILENT
            status.checked = False
        # invalidate address in concerned processes
        for process in self.getRunningProcesses(status.address):
            process.invalidateAddress(status.address)
        # programs running on lost addresses may be declared running without an address, which is inconsistent

    # methods on applications / processes
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

    def getMarkedProcesses(self):
        return [ process for process in self._getAllProcesses() if process.markForRestart ]

    # load internal maps from processes info got from Supervisor on address
    def _loadProcesses(self, address, allProcessesInfo):
        from supervisors.application import ApplicationStatus
        from supervisors.parser import parser
        # get all processes and sort them by group (application)
        # first store applications
        applicationList = { x['group'] for x  in allProcessesInfo }
        options.logger.debug('applicationList={} from {}'.format(applicationList, address))
        # add unknown applications
        for applicationName in applicationList:
            if applicationName not in self.applications:
                application = ApplicationStatus(applicationName)
                parser.setApplicationRules(application)
                self.applications[applicationName] = application
        # store processes into their application entry
        for processInfo in allProcessesInfo:
            try:
                process = self.getProcessFromInfo(processInfo)
            except KeyError:
                # not found. add new instance
                process = ProcessStatus(address, processInfo)
                parser.setProcessRules(process)
                self.applications[process.applicationName].addProcess(process)
            else:
                process.addInfo(address, processInfo)

    def hasConflict(self):
        # return True if any conflict detected
        return next((True for process in self._getAllProcesses() if process.runningConflict()), False)

    def getConflicts(self):
        return [ process for process in self._getAllProcesses() if process.runningConflict() ]

    def _getAllProcesses(self):
        return [ process for application in self.applications.values() for process in application.processes.values() ]

    def getAllProcessesOnAddress(self, address):
        return [ process for process in self._getAllProcesses() if address in process.processes.keys()]

    # methods on events
    def _updateRemoteTime(self, status, remoteTime, localTime):
        status.updateRemoteTime(remoteTime, localTime)
        # got event from remote supervisord, should be operating
        if not status.checked:
            status.checked = True
            # if auto fencing activated: get authorization from remote by port-knocking
            if options.autoFence and not self._isLocalAuthorized(status.address):
                options.logger.warn('local is not authorized to deal with {}'.format(status.address))
                self._invalidRemote(status)
            else:
                options.logger.info('local is authorized to deal with {}'.format(status.address))
                status.state = RemoteStates.RUNNING
                # refresh supervisor information
                info = self._getAllProcessInfo(status.address)
                if info: self._loadProcesses(status.address, info)
                else: self._invalidRemote(status)
        else:
            status.state = RemoteStates.RUNNING
        # refresh dates of processes running on that address
        for application in self.applications.values():
            application.updateRemoteTime(status.address, remoteTime, localTime)

    def onTickEvent(self, address, when):
        if addressMapper.isAddressValid(address):
            status = self.remotes[address]
            # ISOLATED remote is not updated anymore
            if not status.isInIsolation():
                options.logger.debug('got tick {} from location={}'.format(when, address))
                localTime = int(time.time())
                self._updateRemoteTime(status, when, localTime)
                # publish RemoteStatus event
                eventPublisher.sendRemoteStatus(status)
        else:
            options.logger.warn('got tick from unexpected location={}'.format(addresses))

    def onProcessEvent(self, address, processEvent):
        if addressMapper.isAddressValid(address):
            status = self.remotes[address]
            # ISOLATED remote is not updated anymore
            if not status.isInIsolation():
                options.logger.debug('got event {} from location={}'.format(processEvent, address))
                try:
                    # refresh process info from process event
                    process = self.getProcessFromEvent(processEvent)
                    process.updateInfo(address, processEvent)
                    # publish ProcessStatus event
                    eventPublisher.sendProcessStatus(process)
                    # refresh application status
                    application = self.applications[process.applicationName]
                    application.updateStatus()
                    # publish ApplicationStatus event
                    eventPublisher.sendApplicationStatus(application)
                except KeyError:
                    # process not found. normal when no tick yet received from this address
                    options.logger.debug('reject event {} from location={}'.format(processEvent, address))
                else:
                    # trigger deployment work if needed
                    if deployer.isDeploymentInProgress():
                        deployer.deployOnEvent(process)
        else:
            options.logger.error('got process event from unexpected location={}'.format(addresses))

    def onTimerEvent(self):
        # check that all remotes are still publishing. consider problem if no tick received in last 10s
        for status in self.remotes.values():
            if status.state == RemoteStates.RUNNING and (time.time() - status.localTime) > 10:
                self._invalidRemote(status)
                # publish RemoteStatus event
                eventPublisher.sendRemoteStatus(status)

    def handleIsolation(self):
        # master can fix inconsistencies if any
        if context.master: deployer.deployMarkedProcesses(self.getMarkedProcesses())
        # move ISOLATING remotes to ISOLATED
        addresses = self.isolatingRemotes()
        for address in addresses:
            status = self.remotes[address]
            status.state = RemoteStates.ISOLATED
            # publish RemoteStatus event
            eventPublisher.sendRemoteStatus(status)
        return addresses

    # XML-RPC requets
    def _isLocalAuthorized(self, address):
        # XML-RPC request to remote to check that local is not ISOLATED
        try:
            status = getRemoteInfo(address, addressMapper.localAddress)
        except RPCError:
            options.logger.critical('[BUG] could not get remote info from running remote supervisor {}'.format(address))
            raise
        return stringToRemoteState(status['state']) not in [ RemoteStates.ISOLATING, RemoteStates.ISOLATED ]

    def _getAllProcessInfo(self, address):
        # XML-RPC request to get information about all processes managed by Supervisor on address
        try:
            info = getAllProcessInfo(address)
        except RPCError:
            options.logger.critical('[BUG] could not get all process info from running remote supervisor {}'.format(address))
            raise
        return info

context = _Context()
