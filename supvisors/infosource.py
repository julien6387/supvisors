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

import os

from supervisor.http import supervisor_auth_handler
from supervisor.medusa import default_handler, filesys
from supervisor.options import split_namespec
from supervisor.states import ProcessStates


# Supvisors is started in Supervisor so information is available in supervisor instance
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
        self._supervisor_rpc_interface = None
        self._supvisors_rpc_interface = None

    @property
    def supervisor_rpc_interface(self):
        # need to get internal Supervisor RPC handler to call behaviour from Supvisors
        # XML-RPC call in an other XML-RPC call on the same server is blocking
        # so, not very proud of the following lines but could not access it any other way
        if not self._supervisor_rpc_interface:
            self._supervisor_rpc_interface = self.httpservers.handlers[0].rpcinterface.supervisor
        return self._supervisor_rpc_interface

    @property
    def supvisors_rpc_interface(self):
        if not self._supvisors_rpc_interface:
            self._supvisors_rpc_interface = self.httpservers.handlers[0].rpcinterface.supvisors
        return self._supvisors_rpc_interface

    @property
    def httpservers(self):
        # ugly but works...
        return self.supervisord.options.httpservers[0][1]

    @property
    def serverurl(self): return self.supervisord.options.serverurl
    @property
    def serverport(self): return self.serverConfig['port']
    @property
    def username(self): return self.serverConfig['username']
    @property
    def password(self): return self.serverConfig['password']
    @property
    def supervisor_state(self): return self.supervisord.options.mood

    def get_env(self):
        """ Return a simple environment that can be used for the configuration of the XML-RPC client. """
        return {'SUPERVISOR_SERVER_URL': self.serverurl,
            'SUPERVISOR_USERNAME': self.username,
            'SUPERVISOR_PASSWORD': self.password}

    def close_httpservers(self):
        """ Call the close_httpservers of Supervisor.
        This is called when receiving the Supervisor stopping event in order to force the termination
        of any asynchronous pob. """
        self.supervisord.options.close_httpservers()
        self.supervisord.options.httpservers = ()

    def get_group_config(self, application_name):
        """ This method returns the group configuration related to an application. """
        # WARN: the following line may throw a KeyError exception
        return self.supervisord.process_groups[application_name].config

    def autorestart(self, namespec):
        """ This method checks if autorestart is configured on the process. """
        application_name, process_name = split_namespec(namespec)
        # WARN: the following line may throw a KeyError exception
        process = self.supervisord.process_groups[application_name].processes[process_name]
        return process.config.autorestart is not False

    def update_extra_args(self, namespec, extra_args):
        """ This method is used to add extra arguments to the command line. """
        application_name, process_name = split_namespec(namespec)
        # WARN: the following line may throw a KeyError exception
        config = self.supervisord.process_groups[application_name].processes[process_name].config
        # on first time, save the original command line
        if not hasattr(config, 'config_ref'):
            setattr(config, 'config_ref', config.command)
        # reset command line
        config.command = config.config_ref
        # apply args to command line
        if extra_args:
            config.command += ' ' + extra_args

    def force_process_fatal(self, namespec, reason):
        """ This method is used to force a process state into supervisord and to dispatch process event to event listeners. """
        application_name, process_name = split_namespec(namespec)
        # WARN: the following line may throw a KeyError exception
        process = self.supervisord.process_groups[application_name].processes[process_name]
        # need to force BACKOFF state to go through assertion
        process.state = ProcessStates.BACKOFF
        process.spawnerr = reason
        process.give_up()

    def force_process_unknown(self, namespec, reason):
        """ This method is used to force a process state into supervisord and to dispatch process event to event listeners. """
        application_name, process_name = split_namespec(namespec)
        # WARN: the following line may throw a KeyError exception
        process = self.supervisord.process_groups[application_name].processes[process_name]
        process.spawnerr = reason
        process.change_state(ProcessStates.UNKNOWN)

    # this method is used to replace Supervisor web ui with Supvisors web ui
    def replace_default_handler(self):
        # create default handler pointing on Supvisors ui directory
        here = os.path.abspath(os.path.dirname(__file__))
        templatedir = os.path.join(here, 'ui')
        filesystem = filesys.os_filesystem(templatedir)
        defaulthandler = default_handler.default_handler(filesystem)
        # deal with authentication
        if self.username:
            # wrap the xmlrpc handler and tailhandler in an authentication handler
            users = {self.username: self.password}
            defaulthandler = supervisor_auth_handler(users, defaulthandler)
        else:
            self.supervisord.supvisors.logger.warn('Server running without any HTTP authentication checking')
        # replace Supervisor default handler at the end of the list
        self.httpservers.handlers.pop()
        self.httpservers.install_handler(defaulthandler, True)
