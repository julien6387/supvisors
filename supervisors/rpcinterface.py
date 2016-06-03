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
from supervisors.datahandlers import applicationsHandler, remotesHandler
from supervisors.deployer import deployer
from supervisors.infosource import infoSource
from supervisors.options import mainOptions as opt, listenerOptions
from supervisors.remote import RemoteStates, remoteStateToString
from supervisors.rpcrequests import startProcess, stopProcess
from supervisors.types import deploymentStrategiesValues, SupervisorsStates

from supervisor.http import NOT_DONE_YET
from supervisor.xmlrpc import capped_int, Faults, RPCError

API_VERSION  = '1.0'

# Supervisors related faults
class SupervisorsFaults:
    SUPERVISORS_CONF_ERROR, BAD_SUPERVISORS_STATE, BAD_ADDRESS, BAD_STRATEGY = range(4)

_FAULTS_OFFSET = 100

class _RPCInterface(object):

    def __init__(self):
        # start Supervisors main loop
        from supervisors.mainloop import SupervisorsMainLoop
        self._mainLoop = SupervisorsMainLoop()

    # RPC for Supervisors internal use
    def internalStart(self):
        """ Start Supervisors within supervisord
        This is usually called by the Supervisors Listener instance once supervisord is RUNNING
        @return boolean result\t(always True)
        """
        # the thread MUST be started here and not in constructor otherwise, it would end after supervisord daemonizes
        self._mainLoop.start()
        return True

    def internalStartProcess(self, namespec, wait):
        """ Start a process upon request of the Deployer of Supervisors.
        The behaviour is different from 'supervisor.startProcess' as it sets the process state to FATAL instead of throwing an exception to the RPC client.
        @param string name\tThe process name
        @param boolean wait\tWait for process to be fully started
        @return boolean result\tAlways true unless error
        """
        try:
            opt.logger.info('RPC startProcess {}'.format(namespec))
            result = startProcess(addressMapper.expectedAddress, namespec, wait)
        except RPCError, why:
            opt.logger.error('startProcess {} failed: {}'.format(namespec, why))
            if why.code in [ Faults.NO_FILE, Faults.NOT_EXECUTABLE ]:
                opt.logger.warn('force supervisord internal state of {} to FATAL'.format(namespec))
                # force FATAL status in supervisord and trigger event notification in order to warn all remote Supervisors
                from supervisors.utils import getApplicationAndProcessNames
                applicationName, processName = getApplicationAndProcessNames(namespec)
                try:
                    subProcess = infoSource.source.supervisord.process_groups[applicationName].processes[processName]
                    # need to force BACKOFF state to go through assertion
                    from supervisor.states import ProcessStates
                    subProcess.state = ProcessStates.BACKOFF
                    subProcess.spawnerr = why.text
                    subProcess.give_up()
                    result = True
                except KeyError:
                    opt.logger.error('could not find {} in supervisord processes'.format(namespec))
                    result = False
            else:
                # process is already started. should not happen because Supervisors checks state before sending the request
                result = False
        return result

    # RPC Status methods
    def getAPIVersion(self):
        """ Return the version of the RPC API used by Supervisors
        @return string result\tThe version id
        """
        return API_VERSION

    def getSupervisorsState(self):
        """ Return the state of Supervisors
        @return string result\tThe state of Supervisors
        """
        from supervisors.types import supervisorsStateToString
        return supervisorsStateToString(context.state)

    def getMasterAddress(self):
        """ Get the address of the Supervisors Master used to send requests
        @return string result\tThe IPv4 address or host name
        """
        self._checkOperatingOrConciliation()
        return context.masterAddress

    def getAllRemoteInfo(self):
        """ Get info about all remote supervisord managed in Supervisors
        @return list result\tA list of structures containing data about all remote supervisord
        """
        return [ self.getRemoteInfo(address) for address in remotesHandler.remotes.keys() ]

    def getRemoteInfo(self, address):
        """ Get info about a remote supervisord managed in Supervisors and running on address
        @param string address\tThe address of the supervisord
        @return struct result\t\tA structure containing data about the remote supervisord
        """
        try:
            remote = remotesHandler.getRemoteInfo(address)
            loading = applicationsHandler.getRemoteLoading(address)
        except KeyError:
            raise RPCError(Faults.BAD_ADDRESS, 'address {} unknown in Supervisors'.format(address))
        from supervisors.remote import remoteStateToString
        return { 'address': remote.address, 'state': remoteStateToString(remote.state), 'checked': remote.checked,
            'remoteTime': capped_int(remote.remoteTime), 'localTime': capped_int(remote.localTime), 'loading': loading }

    def getAllApplicationInfo(self):
        """ Get info about all applications managed in Supervisors
        @return list result\tA list of structures containing data about all applications
        """
        self._checkOperatingOrConciliation()
        return [ self.getApplicationInfo(applicationName) for applicationName in applicationsHandler.applications.keys() ]

    def getApplicationInfo(self, applicationName):
        """ Get info about an application named applicationName
        @param string applicationName\tThe name of the application
        @return struct result\tA structure containing data about the application
        """
        self._checkOperatingOrConciliation()
        application = self._getApplication(applicationName)
        from supervisors.application import applicationStateToString
        return { 'applicationName': application.applicationName, 'state': applicationStateToString(application.state), 'degraded': application.degraded }

    def getProcessInfo(self, namespec):
        """ Get info about a process named namespec
        It just complements supervisor ProcessInfo by telling where the process is running
        @param string namespec\tThe process name (or ``group:name``, or ``group:*``)
        @return list result\tA list of structures containing data about the processes
        """
        self._checkOperatingOrConciliation()
        application, process = self._getApplicationAndProcess(namespec)
        if process: return [ self._getProcessInfo(process) ]
        return [ self._getProcessInfo(proc) for proc in application.processes.values() ]

    def getProcessRules(self, namespec):
        """ Get the rules used to deploy the process named namespec
        @param string namespec\tThe process name (or ``group:name``, or ``group:*``)
        @return list result\tA list of structures containing data about the deployment rules
        """
        self._checkFromDeployment()
        application, process = self._getApplicationAndProcess(namespec)
        if process: return [ self._getProcessRules(process) ]
        return [ self._getProcessRules(proc) for proc in application.processes.values() ]

    def getConflicts(self):
        """ Get the conflicting processes
        @return list result\t\t\tA list of structures containing data about the conflicting processes
        """
        self._checkOperatingOrConciliation()
        return [ self._getProcessInfo(process) for application in applicationsHandler.applications.values()
            for process in application.processes.values() if process.runningConflict ]

    # RPC Command methods
    def startApplication(self, strategy, applicationName, wait=True):
        """ Start the application named applicationName iaw the strategy and the rules defined in the deployment file.
        @param DeploymentStrategies strategy\tThe strategy to use for choosing addresses
        @param string applicationName\tThe name of the application
        @param boolean wait\tWait for application to be fully started
        @return boolean result\tAlways True unless error or nothing to start
        """
        self._checkOperating()
        # check strategy
        if strategy not in deploymentStrategiesValues():
            raise RPCError(Faults.BAD_STRATEGY, '{}'.format(strategy))
        # check application is known
        if applicationName not in applicationsHandler.applications.keys():
            raise RPCError(Faults.BAD_NAME, applicationName)
        # check application is not already RUNNING
        from supervisors.application import ApplicationStates
        application = applicationsHandler.applications[applicationName]
        if application.state == ApplicationStates.RUNNING:
            raise RPCError(Faults.ALREADY_STARTED, applicationName)
        # TODO: develop a predictive model to check if deployment can be achieved
        # if impossible due to a lack of resources, second try without optionals
        # return false if still impossible
        deployer.strategy = strategy
        done = deployer.deployApplication(applicationName)
        opt.logger.debug('startApplication {} done={}'.format(applicationName, done))
        # wait until application fully RUNNING or (failed)
        if wait and not done:
            def onwait():
                # check deployer
                if deployer.isDeploymentInProgress(): return NOT_DONE_YET
                if application.state != ApplicationStates.RUNNING:
                    raise RPCError(Faults.ABNORMAL_TERMINATION, applicationName)
                return True
            onwait.delay = 0.5
            return onwait # deferred
        # if done is True, nothing to do (no deployment or impossible to deploy)
        return not done

    def stopApplication(self, applicationName, wait=True):
        """ Stop the application named applicationName.
        @param string applicationName\tThe name of the application
        @param boolean wait\tWait for application to be fully stopped
        @return boolean result\tAlways True unless error
        """
        self._checkOperatingOrConciliation()
        # check application is known
        if applicationName not in applicationsHandler.applications.keys():
            raise RPCError(Faults.BAD_NAME, applicationName)
        # do NOT check application state as there may be processes RUNNING although the application is declared STOPPED
        application = applicationsHandler.applications[applicationName]
        for process in application.processes.values():
            if process.isRunning():
                for address in process.addresses:
                    opt.logger.info('stopping process {} on {}'.format(process.getNamespec(), address))
                    stopProcess(address, process.getNamespec(), False)
        # wait until all processes in STOPPED_STATES
        if wait:
            def onwait():
                for process in application.processes.values():
                    if not process.isStopped(): return NOT_DONE_YET
                return True
            onwait.delay = 0.5
            return onwait # deferred
        return True

    def restartApplication(self, strategy, applicationName, wait=True):
        """ Retart the application named applicationName iaw the strategy and the rules defined in the deployment file.
        @param DeploymentStrategies strategy\tThe strategy to use for choosing addresses
        @param string applicationName\tThe name of the application
        @param boolean wait\tWait for application to be fully stopped
        @return boolean result\tAlways True unless error
        """
        self._checkOperating()
        def onwait():
            # first wait for application to be stopped
            if onwait.waitstop:
                value = onwait.job()
                if value is True:
                    # done. request start application
                    onwait.waitstop = False
                    value = self.startApplication(strategy, applicationName, wait)
                    if type(value) is bool: return value
                    # deferred job to wait for application to be started
                    onwait.job = value
                return NOT_DONE_YET
            return onwait.job()
        onwait.delay = 0.5
        onwait.waitstop = True
        # request stop application. job is for deferred result
        onwait.job = self.stopApplication(applicationName, True)
        return onwait # deferred

    def startProcess(self, strategy, namespec, wait=True):
        """ Start a process named namespec iaw the strategy and some of the rules defined in the deployment file
        WARN; only the rules 'addresses' and 'expected_loading' are considered here
        @param DeploymentStrategies strategy\tThe strategy to use for choosing addresses
        @param string namespec\tThe process name (or ``group:name``, or ``group:*``)
        @param boolean wait\tWait for process to be fully started
        @return boolean result\tAlways true unless error
        """
        self._checkOperating()
        # check strategy
        if strategy not in deploymentStrategiesValues():
            raise RPCError(Faults.BAD_STRATEGY, '{}'.format(strategy))
        # check names
        application, process = self._getApplicationAndProcess(namespec)
        processes = [ process ] if process else application.processes.values()
        # check processes are not already RUNNING
        for process in processes:
            if process.isRunning():
                raise RPCError(Faults.ALREADY_STARTED, process.getNamespec())
        # TODO: use predictive model
        # start all processes
        deployer.strategy = strategy
        done = True
        for process in processes:
            done &= deployer.deployProcess(process)
        opt.logger.debug('startProcess {} done={}'.format(process.getNamespec(), done))
        # wait until application fully RUNNING or (failed)
        if wait and not done:
            def onwait():
                # check deployer
                if deployer.isDeploymentInProgress(): return NOT_DONE_YET
                for process in processes:
                    if process.isStopped():
                        raise RPCError(Faults.ABNORMAL_TERMINATION, process.getNamespec())
                return True
            onwait.delay = 0.5
            return onwait # deferred
        # if done is True, nothing to do (no deployment or impossible to deploy)
        return not done

    def stopProcess(self, namespec, wait=True):
        """ Stop the process named namespec where it is running.
        @param string namespec\tThe process name (or ``group:name``, or ``group:*``)
        @param boolean wait\tWait for process to be fully stopped
        @return boolean result\tAlways True unless error
        """
        self._checkOperatingOrConciliation()
        # check names
        application, process = self._getApplicationAndProcess(namespec)
        processes = [ process ] if process else application.processes.values()
        # stop all processes
        for process in processes:
            if process.isRunning():
                for address in process.addresses:
                    opt.logger.info('stopping process {} on {}'.format(process.getNamespec(), address))
                    stopProcess(address, process.getNamespec(), False)
            else:
                opt.logger.info('process {} already stopped'.format(process.getNamespec()))
        # wait until processes are in STOPPED_STATES
        if wait:
            def onwait():
                for process in processes:
                    if not process.isStopped(): return NOT_DONE_YET
                return True
            onwait.delay = 0.5
            return onwait # deferred
        return True

    def restartProcess(self, strategy, namespec, wait=True):
        """ Restart a process named namespec iaw the strategy and some of the rules defined in the deployment file
        WARN; only the rules 'addresses' and 'expected_loading' are considered here
        @param DeploymentStrategies strategy\tThe strategy to use for choosing addresses
        @param string namespec\tThe process name (or ``group:name``, or ``group:*``)
        @param boolean wait\tWait for process to be fully stopped
        @return boolean result\tAlways True unless error
        """
        self._checkOperating()
        def onwait():
            # first wait for process to be stopped
            if onwait.waitstop:
                value = onwait.job()
                if value is True:
                    # done. request start process
                    onwait.waitstop = False
                    value = self.startProcess(strategy, namespec, wait)
                    if type(value) is bool: return value
                    # deferred job to wait for process to be started
                    onwait.job = value
                return NOT_DONE_YET
            return onwait.job()
        onwait.delay = 0.5
        onwait.waitstop = True
        # request stop process. job is for deferred result
        onwait.job = self.stopProcess(namespec, True)
        return onwait # deferred

    def restart(self):
        """ Restart Supervisors through all remote supervisord
        @return boolean result\tAlways True unless error
        """
        self._checkOperatingOrConciliation()
        from supervisors.rpcrequests import restart
        return self._sendAddressesFunc(restart)

    def shutdown(self):
        """ Shut down Supervisors through all remote supervisord
        @return boolean result\tAlways True unless error
        """
        self._checkFromDeployment()
        from supervisors.rpcrequests import shutdown
        return self._sendAddressesFunc(shutdown)

    # TODO: RPC Statistics

    # utilities
    def _checkFromDeployment(self):
        self._checkState([ SupervisorsStates.DEPLOYMENT, SupervisorsStates.OPERATION, SupervisorsStates.CONCILIATION ])

    def _checkOperatingOrConciliation(self):
        self._checkState([ SupervisorsStates.OPERATION, SupervisorsStates.CONCILIATION ])

    def _checkOperating(self):
        self._checkState([ SupervisorsStates.OPERATION ])

    def _checkConciliation(self):
        self._checkState([ SupervisorsStates.CONCILIATION ])

    def _checkState(self, stateList):
        if context.state not in stateList:
            from supervisors.types import supervisorsStateToString
            raise RPCError(Faults.BAD_SUPERVISORS_STATE, 'Supervisors (state={}) not in state {} to perform request'.
                format(supervisorsStateToString(context.state), [ supervisorsStateToString(state) for state in stateList ]))

    # almost equivalent to the method in supervisor.rpcinterface
    def _getApplicationAndProcess(self, namespec):
        # get process to start from name
        from supervisor.options import split_namespec
        applicationName, processName = split_namespec(namespec)
        return self._getApplication(applicationName), self._getProcess(namespec) if processName else None

    def _getApplication(self, applicationName):
        try:
            application = applicationsHandler.applications[applicationName]
        except KeyError:
            raise RPCError(Faults.BAD_NAME, 'application {} unknown in Supervisors'.format(applicationName))
        return application

    def _getProcess(self, namespec):
        try:
            process = applicationsHandler.getProcessFromNamespec(namespec)
        except KeyError:
            raise RPCError(Faults.BAD_NAME, 'process {} unknown in Supervisors'.format(namespec))
        return process

    def _getProcessInfo(self, process):
        return { 'processName': process.getNamespec(), 'state': process.stateAsString(), 'address': list(process.addresses), 'conflict': process.runningConflict }

    def _getProcessRules(self, process):
        rules = process.rules
        return { 'processName': process.getNamespec(), 'addresses': rules.addresses, 'sequence': rules.sequence,
            'required': rules.required, 'wait_exit': rules.wait_exit, 'expected_loading': rules.expected_loading }

    def _sendAddressesFunc(self, func):
        # send func request to all locals (but self address)
        for remote in remotesHandler.remotes.values():
            if remote.state in [ RemoteStates.RUNNING, RemoteStates.SILENT ] and remote.address != addressMapper.expectedAddress:
                try:
                    func(remote.address)
                    opt.logger.warn('supervisord {} on {}'.format(func.__name__, remote.address))
                except:
                    opt.logger.error('failed to {} supervisord on {}'.format(func.__name__, remote.address))
            else:
                opt.logger.info('cannot {} supervisord on {}: Remote state is {}'.format(func.__name__, remote.address, remoteStateToString(remote.state)))
        # send request to self supervisord
        return func(addressMapper.expectedAddress)


# Supervisor entry point
def make_supervisors_rpcinterface(supervisord, **config):
    # expand supervisord Fault definition (no matter if done several times)
    for (x, y) in SupervisorsFaults.__dict__.items():
        if not x.startswith('__'):
            setattr(Faults, x, y + _FAULTS_OFFSET)
    # configure supervisor info source
    from supervisors.infosource import SupervisordSource
    infoSource.source = SupervisordSource(supervisord)
    # get options from config file
    listenerOptions.realize()
    opt.realize(True)
    # set addresses and check local address
    addressMapper.setAddresses(opt.addresslist)
    if not addressMapper.expectedAddress:
        raise RPCError(Faults.SUPERVISORS_CONF_ERROR, 'local host unexpected in address list: {}'.format(opt.addresslist))
    context.cleanup()
    # check parsing
    from supervisors.parser import parser
    try: parser.setFilename(opt.deployment_file)
    except:
        raise RPCError(Faults.SUPERVISORS_CONF_ERROR, 'cannot parse deployment file: {}'.format(opt.deployment_file))
    # update http web pages
    from supervisors.web import updateUiHandler
    updateUiHandler()
    # create and return handler
    return _RPCInterface()
