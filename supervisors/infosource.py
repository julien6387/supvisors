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

# Supervisors is started in Supervisor so information is available in supervisor instance
class SupervisordSource(object):
    def __init__(self, supervisord):
        self.supervisord = supervisord
        if len(supervisord.options.server_configs) == 0:
            raise Exception('no server configuration in config file: {}'.format(supervisord.configfile))
        self.serverConfig = supervisord.options.server_configs[0]
        # server MUST be http, not unix
        serverSection = self.serverConfig['section'] 
        if serverSection != 'inet_http_server':
            raise Exception('inet_http_server expected in config file: {}'.format(supervisord.configfile))
        # shortcuts (not available yet)
        self.supervisorRpcInterface = None
        self.supervisorsRpcInterface = None

    def getSupervisorRpcInterface(self):
        # need to get internal Supervisor RPC handler to call behaviour from Supervisors
        # XML-RPC call in an other XML-RPC call on the same server is blocking
        # so, not very proud of the following lines but could not access it any other way
        if not self.supervisorRpcInterface:
            self.supervisorRpcInterface = self.supervisord.options.httpservers[0][1].handlers[0].rpcinterface.supervisor
        return self.supervisorRpcInterface

    def getSupervisorsRpcInterface(self):
        if not self.supervisorsRpcInterface:
            self.supervisorsRpcInterface = self.supervisord.options.httpservers[0][1].handlers[0].rpcinterface.supervisors
        return self.supervisorsRpcInterface

    @property
    def serverUrl(self): return self.supervisord.options.serverurl
    @property
    def serverPort(self): return self.serverConfig['port']
    @property
    def userName(self): return self.serverConfig['username']
    @property
    def password(self): return self.serverConfig['password']

    # this method is used to force a process state into supervisord and to dispatch process event to event listeners
    def forceProcessFatalState(self, namespec, reason):
        from supervisors.utils import getApplicationAndProcessNames
        applicationName, processName = getApplicationAndProcessNames(namespec)
        # WARN: may throw KeyError
        subProcess = self.supervisord.process_groups[applicationName].processes[processName]
        # need to force BACKOFF state to go through assertion
        from supervisor.states import ProcessStates
        subProcess.state = ProcessStates.BACKOFF
        subProcess.spawnerr = reason
        subProcess.give_up()

# wrapper class
class _InfoSource(object):
    def __init__(self):
        self.source = None

infoSource = _InfoSource()
