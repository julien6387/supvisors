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
        self.server_config = supervisord.options.server_configs[0]
        # server MUST be http, not unix
        serverSection = self.server_config['section'] 
        if serverSection != 'inet_http_server':
            raise ValueError('inet_http_server expected in config file: {}'.format(supervisord.configfile))
        # shortcuts (not available yet)
        self._supervisor_rpc_interface = None
        self._supvisors_rpc_interface = None

    @property
    def supervisor_rpc_interface(self):
        # need to get internal Supervisor RPC handler to call behaviour from Supvisors
        # XML-RPC call in an other XML-RPC call on the same server is blocking
        # so, not very proud of the following lines but could not access it any other way
        if not self._supervisor_rpc_interface:
            self._supervisor_rpc_interface = self.httpserver.handlers[0].rpcinterface.supervisor
        return self._supervisor_rpc_interface

    @property
    def supvisors_rpc_interface(self):
        if not self._supvisors_rpc_interface:
            self._supvisors_rpc_interface = self.httpserver.handlers[0].rpcinterface.supvisors
        return self._supvisors_rpc_interface

    @property
    def httpserver(self):
        # ugly but works...
        return self.supervisord.options.httpservers[0][1]

    @property
    def serverurl(self): return self.supervisord.options.serverurl
    @property
    def serverport(self): return self.server_config['port']
    @property
    def username(self): return self.server_config['username']
    @property
    def password(self): return self.server_config['password']
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

    def get_process(self, namespec):
        """ This method returns the process configuration related to a namespec. """
        # WARN: the following line may throw a KeyError exception
        application_name, process_name = split_namespec(namespec)
        return self.supervisord.process_groups[application_name].processes[process_name]

    def get_process_config(self, namespec):
        """ This method returns the process configuration related to a namespec. """
        return self.get_process(namespec).config

    def autorestart(self, namespec):
        """ This method checks if autorestart is configured on the process. """
        return self.get_process_config(namespec).autorestart is not False

    def disable_autorestart(self, namespec):
        """ This method forces the autorestart to False in Supervisor internal data. """
        self.get_process_config(namespec).autorestart = False

    def update_extra_args(self, namespec, extra_args):
        """ This method is used to add extra arguments to the command line. """
        config = self.get_process_config(namespec)
        # on first time, save the original command line
        if not hasattr(config, 'config_ref'):
            setattr(config, 'config_ref', config.command)
        # reset command line
        config.command = config.config_ref
        # apply args to command line
        if extra_args:
            config.command += ' ' + extra_args

    def force_process_fatal(self, namespec, reason):
        """ This method forces the FATAL process state into Supervisor internal data
        and dispatches process event to event listeners. """
        process = self.get_process(namespec)
        # need to force BACKOFF state to go through assertion
        process.state = ProcessStates.BACKOFF
        process.spawnerr = reason
        process.give_up()

    def force_process_unknown(self, namespec, reason):
        """ This method forces the UNKNOWN process state into Supervisor internal data
        and dispatches process event to event listeners. """
        process = self.get_process(namespec)
        process.spawnerr = reason
        process.change_state(ProcessStates.UNKNOWN)

    def replace_default_handler(self):
        """ This method replaces Supervisor web ui with Supvisors web ui. """
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
        self.httpserver.handlers.pop()
        self.httpserver.install_handler(defaulthandler, True)
