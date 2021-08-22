#!/usr/bin/python
# -*- coding: utf-8 -*-

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

from typing import Dict

from supervisor.http import supervisor_auth_handler
from supervisor.loggers import Logger
from supervisor.medusa import default_handler, filesys
from supervisor.options import split_namespec
from supervisor.states import ProcessStates


class SupervisordSource(object):
    """ Supvisors is started in Supervisor so Supervisor internal data is available from the supervisord instance. """

    def __init__(self, supervisord, logger: Logger):
        """ Initialization of the attributes. """
        self.supervisord = supervisord
        self.logger: Logger = logger
        self.server_config = supervisord.options.server_configs[0]
        # server MUST be http, not unix
        server_section = self.server_config['section']
        if server_section != 'inet_http_server':
            raise ValueError('inet_http_server expected in config file: {}'
                             .format(supervisord.configfile))
        # shortcuts (not available yet)
        self._supervisor_rpc_interface = None
        self._supvisors_rpc_interface = None

    @property
    def supervisor_rpc_interface(self):
        # need to get internal Supervisor RPC handler to call behavior from Supvisors
        # XML-RPC call in an other XML-RPC call on the same server is blocking
        # so, not very proud of the following lines but could not access it any other way
        if not self._supervisor_rpc_interface:
            handler = self.httpserver.handlers[0]
            # if authentication used, handler is wrapped
            if self.username:
                handler = handler.handler
            self._supervisor_rpc_interface = handler.rpcinterface.supervisor
        return self._supervisor_rpc_interface

    @property
    def supvisors_rpc_interface(self):
        if not self._supvisors_rpc_interface:
            handler = self.httpserver.handlers[0]
            # if authentication is used, handler is wrapped
            if self.username:
                handler = handler.handler
            self._supvisors_rpc_interface = handler.rpcinterface.supvisors
        return self._supvisors_rpc_interface

    @property
    def httpserver(self):
        # ugly but works...
        return self.supervisord.options.httpservers[0][1]

    @property
    def serverurl(self) -> str:
        return self.supervisord.options.serverurl

    @property
    def serverport(self):
        return self.server_config['port']

    @property
    def username(self) -> str:
        return self.server_config['username']

    @property
    def password(self) -> str:
        return self.server_config['password']

    @property
    def supervisor_state(self):
        return self.supervisord.options.mood

    def get_env(self) -> Dict[str, str]:
        """ Return a simple environment that can be used for the configuration of the XML-RPC client. """
        return {'SUPERVISOR_SERVER_URL': self.serverurl,
                'SUPERVISOR_USERNAME': self.username,
                'SUPERVISOR_PASSWORD': self.password}

    def prepare_extra_args(self) -> None:
        """ Add extra_args attributes in Supervisor internal data. """
        for group in self.supervisord.process_groups.values():
            for process in group.processes.values():
                process.config.command_ref = process.config.command
                process.config.extra_args = ''

    def close_httpservers(self) -> None:
        """ Call the close_httpservers of Supervisor.
        This is called when receiving the Supervisor stopping event in order to force the termination
        of any asynchronous job. """
        self.supervisord.options.close_httpservers()
        self.supervisord.options.httpservers = ()

    def get_group_config(self, application_name: str):
        """ This method returns the group configuration related to an application. """
        # WARN: the method may throw a KeyError exception
        return self.supervisord.process_groups[application_name].config

    def _get_process(self, namespec: str):
        """ This method returns the process configuration related to a namespec. """
        # WARN: the method may throw a KeyError exception
        application_name, process_name = split_namespec(namespec)
        return self.supervisord.process_groups[application_name].processes[process_name]

    def _get_process_config(self, namespec: str):
        """ This method returns the process configuration related to a namespec. """
        return self._get_process(namespec).config

    def autorestart(self, namespec: str) -> bool:
        """ This method checks if autorestart is configured on the process. """
        return self._get_process_config(namespec).autorestart is not False

    def disable_autorestart(self, namespec: str) -> None:
        """ This method forces the autorestart to False in Supervisor internal data. """
        self._get_process_config(namespec).autorestart = False

    def update_extra_args(self, namespec: str, extra_args: str) -> None:
        """ This method is used to add extra arguments to the command line. """
        config = self._get_process_config(namespec)
        # reset command line
        config.command = config.command_ref
        config.extra_args = extra_args
        # apply args to command line
        if extra_args:
            config.command += ' ' + extra_args
        self.logger.trace('SupervisordSource.update_extra_args: {} extra_args={}'.format(namespec, extra_args))

    def get_extra_args(self, namespec: str) -> str:
        """ Return the extra arguments passed to the command line of the process named namespec. """
        return self._get_process_config(namespec).extra_args

    def force_process_fatal(self, namespec: str, reason: str) -> None:
        """ This method forces the FATAL process state into Supervisor internal data and dispatches
        process event to event listeners. """
        process = self._get_process(namespec)
        # need to force BACKOFF state to go through assertion
        process.state = ProcessStates.BACKOFF
        process.spawnerr = reason
        process.give_up()

    def replace_default_handler(self) -> None:
        """ This method replaces Supervisor web ui with Supvisors web ui. """
        # create default handler pointing on Supvisors ui directory
        here = os.path.abspath(os.path.dirname(__file__))
        templatedir = os.path.join(here, 'ui')
        filesystem = filesys.os_filesystem(templatedir)
        defaulthandler = default_handler.default_handler(filesystem)
        # deal with authentication
        if self.username:
            # wrap the default handler in an authentication handler
            users = {self.username: self.password}
            defaulthandler = supervisor_auth_handler(users, defaulthandler)
        else:
            self.logger.warn('Server running without any HTTP authentication checking')
        # replace Supervisor default handler at the end of the list
        self.httpserver.handlers.pop()
        self.httpserver.install_handler(defaulthandler, True)
