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

class XmlRpcClient(object):
    def __init__(self, address):
        import xmlrpclib
        self.transport = self._getRpcTransport(address)
        self.proxy = xmlrpclib.ServerProxy('http://{0}'.format(address), self.transport) if self.transport else None

    def _getRpcTransport(self, address):
        from supervisors.infosource import infoSource
        if infoSource.source.getServerUrl():
            serverUrl = infoSource.source.getServerUrl().split(':')
            if len(serverUrl) == 3:
                serverUrl[1] = '//' + address
                serverUrl = ':'.join(serverUrl)
                from supervisor.xmlrpc import SupervisorTransport
                return SupervisorTransport(infoSource.source.getUserName(), infoSource.source.getPassword(), serverUrl)
        return None


# unit test expecting that a Supervisor Server is running at address below
if __name__ == "__main__":
    def createSupervisordInstance():
        from supervisor.options import ServerOptions
        from supervisor.supervisord import Supervisor
        supervisord = Supervisor(ServerOptions())
        supervisord.options.serverurl = 'http://localhost:60000'
        supervisord.options.server_configs = [{'username': None, 'section': 'inet_http_server', 'password': None, 'port': 60000}]
        return supervisord
    # create logger
    from supervisors.options import mainOptions as opt
    from supervisor.loggers import getLogger
    opt.logger = getLogger('/tmp/xmlrpcclient.log', 20, '%(asctime)s %(levelname)s %(message)s\n', False, 0, 0, True)
    # assign supervisord info source
    from supervisors.infosource import infoSource, SupervisordSource
    infoSource.source = SupervisordSource(createSupervisordInstance())
    # test xml-rpc
    client = XmlRpcClient('cliche01')
    system = client.proxy.system
    supervisor = client.proxy.supervisor
    supervisors = client.proxy.supervisors
    # calls
    print system.listMethods()
    print system.methodHelp('supervisor.getState')
    print supervisor.getState()
    print system.methodHelp('supervisor.getProcessInfo')
    print supervisor.getProcessInfo('crash:segv')
    print supervisor.getProcessInfo('Listener')
    print supervisor.getProcessInfo('sample_test_2:sleep')
    print system.methodHelp('supervisor.startProcess')
    # print supervisor.startProcess('SupervisorsWeb')
    print system.methodHelp('supervisor.restart')
    #print supervisor.restart()
    print system.methodHelp('supervisors.getAPIVersion')
    print supervisors.getAPIVersion()
    print system.methodHelp('supervisors.getSupervisorsState')
    print supervisors.getSupervisorsState()
    print system.methodHelp('supervisors.getMasterAddress')
    print supervisors.getMasterAddress()
    print system.methodHelp('supervisors.getAllRemoteInfo')
    print supervisors.getAllRemoteInfo()
    print system.methodHelp('supervisors.getRemoteInfo')
    print supervisors.getRemoteInfo('cliche01')
    print system.methodHelp('supervisors.getAllApplicationInfo')
    print supervisors.getAllApplicationInfo()
    print system.methodHelp('supervisors.getApplicationInfo')
    print supervisors.getApplicationInfo('sample_test_2')
    print system.methodHelp('supervisors.getProcessInfo')
    print supervisors.getProcessInfo('crash:segv')
    print supervisors.getProcessInfo('Listener')
    print supervisors.getProcessInfo('sample_test_1:*')
    print system.methodHelp('supervisors.getProcessRules')
    print supervisors.getProcessRules('sample_test_2:*')
    print system.methodHelp('supervisors.getConflicts')
    print supervisors.getConflicts()
    print system.methodHelp('supervisors.restartApplication')
    from supervisors.types import DeploymentStrategies
    print supervisors.restartApplication(DeploymentStrategies.CONFIG, 'sample_test_2')
    print system.methodHelp('supervisors.stopApplication')
    print supervisors.stopApplication('sample_test_2')
    print system.methodHelp('supervisors.startApplication')
    print supervisors.startApplication(DeploymentStrategies.CONFIG, 'sample_test_2')
    print system.methodHelp('supervisors.restartProcess')
    print supervisors.restartProcess(DeploymentStrategies.LESS_LOADED, 'sample_test_2:yeux_01')
    print system.methodHelp('supervisors.stopProcess')
    print supervisors.stopProcess('sample_test_2:yeux_01')
    print system.methodHelp('supervisors.startProcess')
    print supervisors.startProcess(DeploymentStrategies.LESS_LOADED, 'sample_test_2:yeux_01')
    # different use of start/stop/restart
    print 'supervisors.restartProcess - alt'
    print supervisors.restartProcess(DeploymentStrategies.MOST_LOADED, 'sample_test_2:*')
    print 'supervisors.stoprocess - alt'
    print supervisors.stopProcess('sample_test_2:*')
    print 'supervisors.startProcess - alt'
    print supervisors.startProcess(DeploymentStrategies.MOST_LOADED, 'sample_test_2:*')
    print system.methodHelp('supervisors.restart')
    #print supervisors.restart()
    print system.methodHelp('supervisors.shutdown')
    #print supervisors.shutdown()
