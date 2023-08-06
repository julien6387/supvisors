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

import json
import os
import socket
from typing import Any, Dict, List, Tuple

from supervisor.events import notify
from supervisor.http import supervisor_auth_handler, logtail_handler, mainlogtail_handler
from supervisor.loggers import Logger
from supervisor.medusa import default_handler, filesys
from supervisor.options import make_namespec, split_namespec, ProcessConfig
from supervisor.process import Subprocess
from supervisor.states import ProcessStates

from .options import SupvisorsServerOptions
from .ttypes import ProcessAddedEvent, ProcessRemovedEvent, ProcessEnabledEvent, ProcessDisabledEvent, NameList

SUPERVISOR_TAIL_DEFAULT = 1024


def spawn(self):
    """ Overridden Subprocess spawn to handle disabled processes.

    :return: the process id or None if the fork() call fails.
    """
    if not self.config.disabled:
        return self._spawn()


class LogtailHandler(logtail_handler):
    """ Specialization of Supervisor logtail_handler to enable tail size configuration. """

    def handle_request(self, request):
        # call parent
        super().handle_request(request)
        # get configured tail size
        new_head = self.supervisord.supvisors.options.tailf_limit
        # re-calculate sz
        sz = request.outgoing[-1].sz
        request.outgoing[-1].sz = min(sz, max(sz + SUPERVISOR_TAIL_DEFAULT - new_head, 0))


class MainLogtailHandler(mainlogtail_handler):
    """ Specialization of Supervisor mainlogtail_handler to enable tail size configuration. """

    def handle_request(self, request):
        # call parent
        super().handle_request(request)
        # get configured tail size
        new_head = self.supervisord.supvisors.options.tailf_limit
        # re-calculate sz
        sz = request.outgoing[-1].sz
        request.outgoing[-1].sz = min(sz, max(sz + SUPERVISOR_TAIL_DEFAULT - new_head, 0))


class SupervisorData(object):
    """ Supvisors is started in Supervisor so Supervisor internal data is available from the supervisord structure. """

    def __init__(self, supvisors, supervisord):
        """ Initialization of the attributes.

        :param supvisors: the Supvisors global structure
        :param supervisord: the Supervisor global structure
        """
        self.supvisors = supvisors
        self.supervisord = supervisord
        self.logger: Logger = supvisors.logger
        # check HTTP configuration
        for config in supervisord.options.server_configs:
            if config['family'] == socket.AF_INET:
                self.server_config = config
                break
        else:
            # there MUST be an inet HTTP server
            raise ValueError(f'Supervisor MUST be configured using inet_http_server: {supervisord.options.configfile}')
        # shortcuts (not available yet)
        self._system_rpc_interface = None
        self._supervisor_rpc_interface = None
        self._supvisors_rpc_interface = None
        # disabilities for local processes (Supervisor issue #591)
        self.disabilities = {}
        self.read_disabilities()

    @property
    def http_server(self):
        """ Get the internal Supervisor HTTP server structure.

        :return: the HTTP server structure
        """
        for config, hs in self.supervisord.options.httpservers:
            if config['family'] == socket.AF_INET:
                return hs

    @property
    def system_rpc_interface(self):
        """ Get the internal System Supervisor RPC handler.
        XML-RPC call in another XML-RPC call on the same server is blocking.

        :return: the System Supervisor RPC handler
        """
        if not self._system_rpc_interface:
            # the first handler is the XML-RPC interface for rapid access
            handler = self.http_server.handlers[0]
            # if authentication used, handler is wrapped
            if self.username:
                handler = handler.handler
            self._system_rpc_interface = handler.rpcinterface.system
        return self._system_rpc_interface

    @property
    def supervisor_rpc_interface(self):
        """ Get the internal Supervisor RPC handler.
        XML-RPC call in another XML-RPC call on the same server is blocking.

        :return: the Supervisor RPC handler
        """
        if not self._supervisor_rpc_interface:
            # the first handler is the XML-RPC interface for rapid access
            handler = self.http_server.handlers[0]
            # if authentication used, handler is wrapped
            if self.username:
                handler = handler.handler
            self._supervisor_rpc_interface = handler.rpcinterface.supervisor
        return self._supervisor_rpc_interface

    @property
    def supvisors_rpc_interface(self):
        """ Get the internal Supvisors RPC handler.
        XML-RPC call in another XML-RPC call on the same server is blocking.

        :return: the Supvisors RPC handler
        """
        if not self._supvisors_rpc_interface:
            # the first handler is the XML-RPC interface for rapid access
            handler = self.http_server.handlers[0]
            # if authentication is used, handler is wrapped
            if self.username:
                handler = handler.handler
            self._supvisors_rpc_interface = handler.rpcinterface.supvisors
        return self._supvisors_rpc_interface

    @property
    def identifier(self) -> str:
        """ Get the internal Supervisor identifier.

        :return: the Supervisor identifier
        """
        return self.supervisord.options.identifier

    @property
    def server_host(self):
        """ Return the host defined in the inet http server section. """
        return self.server_config['host'] or 'localhost'

    @property
    def server_port(self):
        """ Return the port defined in the inet http server section. """
        return self.server_config['port']

    @property
    def username(self) -> str:
        """ Return the user authentication defined in the inet http server section. """
        return self.server_config['username']

    @property
    def password(self) -> str:
        """ Return the password authentication defined in the inet http server section. """
        return self.server_config['password']

    @property
    def server_url(self) -> str:
        """ Return the server URL defined in the inet http server section. """
        # do NOT use Supervisor serverurl as priority is given to the unix server if defined
        return f'http://{self.server_host}:{self.server_port}'

    @property
    def supervisor_state(self):
        """ Return the supervisord internal state. """
        return self.supervisord.options.mood

    def get_env(self) -> Dict[str, str]:
        """ Return a simple environment that can be used for the configuration of the XML-RPC client. """
        return {'SUPERVISOR_SERVER_URL': self.server_url,
                'SUPERVISOR_USERNAME': self.username,
                'SUPERVISOR_PASSWORD': self.password}

    def update_supervisor(self) -> None:
        """ Update Supervisor internal data for Supvisors support.

        :return: None
        """
        # replace the tail handlers for web ui
        self.replace_tail_handlers()
        # replace the default handler for web ui
        self.replace_default_handler()
        # update Supervisor internal data for extra_args and disabilities
        # WARN: this is also triggered by adding groups in Supervisor, however the initial group added events
        # are sent before the Supvisors RPC interface is created
        self.update_internal_data()
    
    def update_internal_data(self, group_name: str = None) -> None:
        """ Add extra attributes to Supervisor internal data.

        :param group_name: the name of the group that has been added to the Supervisor internal data
        :return: None
        """
        # determine targets
        if group_name:
            groups = [self.supervisord.process_groups[group_name]]
        else:
            groups = self.supervisord.process_groups.values()
        # apply the new configuration
        for group in groups:
            for process in group.processes.values():
                # prepare process disability
                program = self.supvisors.server_options.processes_program[process.config.name]
                process.config.disabled = self.disabilities.setdefault(program, False)
                # prepare extra arguments
                process.config.command_ref = process.config.command
                process.config.extra_args = ''

    def replace_tail_handlers(self) -> None:
        """ This method replaces Supervisor web UI tail handlers. """
        tail_handler = LogtailHandler(self.supervisord)
        main_tail_handler = MainLogtailHandler(self.supervisord)
        # deal with authentication
        if self.username:
            # wrap the default handler in an authentication handler
            users = {self.username: self.password}
            tail_handler = supervisor_auth_handler(users, tail_handler)
            main_tail_handler = supervisor_auth_handler(users, main_tail_handler)
        else:
            self.logger.debug('SupervisorData.replace_tail_handlers: Server running without any HTTP'
                              ' authentication checking')
        # replace Supervisor handlers considering the order in supervisor.http.make_http_servers
        self.http_server.handlers[1] = tail_handler
        self.http_server.handlers[2] = main_tail_handler

    def replace_default_handler(self) -> None:
        """ This method replaces Supervisor web UI with Supvisors web UI. """
        # create default handler pointing on Supvisors ui directory
        here = os.path.abspath(os.path.dirname(__file__))
        template_dir = os.path.join(here, 'ui')
        filesystem = filesys.os_filesystem(template_dir)
        def_handler = default_handler.default_handler(filesystem)
        # deal with authentication
        if self.username:
            # wrap the default handler in an authentication handler
            users = {self.username: self.password}
            def_handler = supervisor_auth_handler(users, def_handler)
        else:
            self.logger.debug('SupervisorData.replace_default_handler: Server running without any HTTP'
                              ' authentication checking')
        # replace Supervisor default handler at the end of the list
        self.http_server.handlers[-1] = def_handler

    def close_httpservers(self) -> None:
        """ Call the close_httpservers of Supervisor.
        This is called when receiving the Supervisor stopping event in order to force the termination
        of any asynchronous job. """
        # Supervisor issue #1596:
        #     In the event of a reload, the HTTP socket will be re-opened very quickly.
        #     Despite the REUSEADDR is set, there may still be a handle somewhere on the socket that makes it
        #     NOT deallocated, although it has been closed.
        #     To avoid issues, it is better to shut the socket down before closing it.
        self.http_server.socket.shutdown(socket.SHUT_RDWR)
        self.supervisord.options.close_httpservers()
        self.supervisord.options.httpservers = ()

    # Access to Group / Process structures and configurations
    def get_group_processes(self, application_name: str) -> List[Subprocess]:
        """ This method returns the processes related to a group.

        :param application_name: the group name
        :return: a list of Supervisor processes
        """
        # WARN: the method may throw a KeyError exception
        return self.supervisord.process_groups[application_name].processes

    def _get_process(self, namespec: str):
        """ This method returns the process configuration related to a namespec. """
        # WARN: the method may throw a KeyError exception
        application_name, process_name = split_namespec(namespec)
        return self.get_group_processes(application_name)[process_name]

    def _get_process_config(self, namespec: str):
        """ This method returns the process configuration related to a namespec. """
        return self._get_process(namespec).config

    def autorestart(self, namespec: str) -> bool:
        """ This method checks if autorestart is configured on the program. """
        return self._get_process_config(namespec).autorestart is not False

    def disable_autorestart(self, namespec: str) -> None:
        """ This method forces the autorestart to False in Supervisor internal data. """
        self._get_process_config(namespec).autorestart = False

    def get_process_config_options(self, namespec: str, option_names: List[str]) -> Dict[str, Any]:
        """ Get the configured option values of the program.

        :param namespec: the program namespec
        :param option_names: the options to get
        :return: a dictionary of option values
        """
        process_config = self._get_process_config(namespec)
        return {option_name: getattr(process_config, option_name) for option_name in option_names}

    def has_logfile(self, namespec: str, channel: str) -> bool:
        """ Return True if the process has a logfile configuration on the channel.

        :param namespec: the program namespec
        :param channel: the logfile channel (stdout or stderr)
        :return: True if the process has a logfile configured on the channel
        """
        process_config = self._get_process_config(namespec)
        return getattr(process_config, '%s_logfile' % channel)

    # Supervisor issue #1023
    def update_extra_args(self, namespec: str, extra_args: str) -> None:
        """ This method is used to add extra arguments to the command line.
        Implementation of Supervisor issue #1023 - Pass arguments to program when starting a job.

        :param namespec: the process namespec
        :param extra_args: the arguments to be added to the program command line
        :return: None
        """
        """  """
        config = self._get_process_config(namespec)
        # reset command line
        config.command = config.command_ref
        config.extra_args = extra_args
        # apply args to command line
        if extra_args:
            config.command += ' ' + extra_args
        self.logger.trace(f'SupervisorData.update_extra_args: {namespec} extra_args={extra_args}')

    def force_process_fatal(self, namespec: str, reason: str) -> None:
        """ This method forces the FATAL process state into Supervisor internal data and dispatches process event
        to event listeners. """
        process = self._get_process(namespec)
        # need to force BACKOFF state to go through assertion
        process.state = ProcessStates.BACKOFF
        process.spawnerr = reason
        process.give_up()

    # Supervisor issue #177
    def update_numprocs(self, program_name: str, numprocs: int) -> Tuple[NameList, NameList]:
        """ This method is used to dynamically update the program numprocs.
        Implementation of Supervisor issue #177 - Dynamic numproc change

        :param program_name: the program name, as found in the sections of the Supervisor configuration files
        :param numprocs: the new numprocs value
        :return: the list of processes added and removed (and eventually stop before removal)
        """
        self.logger.trace(f'SupervisorData.update_numprocs: {program_name} - numprocs={numprocs}')
        # re-evaluate for all groups including the program
        server_options = self.supervisord.supvisors.server_options
        program_groups = server_options.program_processes[program_name]
        current_numprocs = len(next(iter(program_groups.values())))
        self.logger.debug(f'SupervisorData.update_numprocs: {program_name} - current_numprocs={current_numprocs}')
        if current_numprocs > numprocs:
            # return the processes to stop if numprocs decreases
            return [], self._get_obsolete_processes(program_name, numprocs, program_groups)
        if current_numprocs < numprocs:
            # add the new processes into Supervisor
            return self._add_processes(program_name, numprocs, current_numprocs, list(program_groups.keys())), []
        # else equal / no change
        return [], []

    def _add_processes(self, program_name: str, new_numprocs: int, current_numprocs: int, groups: NameList) -> NameList:
        """ Add new processes to all Supervisor groups already including it.

        :param program_name: the program which definition has to be updated
        :param new_numprocs: the new numprocs value
        :param current_numprocs: the former numprocs value
        :param groups: the groups that embed the processes issued from the existing program definition
        :return: None
        """
        new_process_namespecs = []
        # update ServerOptions parser with new numprocs for program
        server_options = self.supervisord.supvisors.server_options
        section = server_options.update_numprocs(program_name, new_numprocs)
        for group_name in groups:
            # rebuild the process configs from the new Supervisor configuration
            process_configs = server_options.reload_processes_from_section(section, group_name)
            # the new processes are those over the previous size
            new_namespecs = self._add_supervisor_processes(program_name, group_name, process_configs[current_numprocs:])
            new_process_namespecs.extend(new_namespecs)
        return new_process_namespecs

    def _add_supervisor_processes(self, program_name: str, group_name: str,
                                  new_configs: List[ProcessConfig]) -> NameList:
        """ Add new processes to the Supervisor group from the configuration built.

        :param program_name: the program which definition has to be updated
        :param group_name: the group that embed the program definition
        :param new_configs: the new process configurations to add to the group
        :return: the new process namespecs
        """
        new_process_namespecs = []
        # add new process configs to group in Supervisor
        group = self.supervisord.process_groups[group_name]
        group.config.process_configs.extend(new_configs)
        # create processes from new process configs
        for process_config in new_configs:
            self.logger.info(f'SupervisorData._add_supervisor_processes: add process={process_config.name}')
            new_process_namespecs.append(make_namespec(group_name, process_config.name))
            # WARN: replace process_config Supvisors server_options by Supervisor options
            #  this is causing "reaped unknown pid" at exit due to inadequate pidhistory
            process_config.options = self.supervisord.options
            # additional Supvisors attributes
            process_config.disabled = self.disabilities[program_name]
            process_config.command_ref = process_config.command
            process_config.extra_args = ''
            # prepare log files
            process_config.create_autochildlogs()
            # add the new process to the group
            group.processes[process_config.name] = process = process_config.make_process(group)
            # fire event to Supervisor listeners
            notify(ProcessAddedEvent(process))
        return new_process_namespecs

    def _get_obsolete_processes(self, program_name: str, numprocs: int,
                                program_configs: SupvisorsServerOptions.ProcessConfigInfo) -> NameList:
        """ Return the obsolete processes in accordance with the new numprocs.
        The program may be used in many groups.

        :param program_name: the program which definition has to be updated
        :param numprocs: the new numprocs value
        :param program_configs: the current program configurations per group
        :return: the obsolete process namespecs
        """
        # do not remove process configs yet as they may need to be stopped before
        obsolete_processes = [make_namespec(group_name, process_config.name)
                              for group_name, process_configs in program_configs.items()
                              for process_config in process_configs[numprocs:]]
        # update ServerOptions parser with new numprocs for program
        server_options = self.supervisord.supvisors.server_options
        section = server_options.update_numprocs(program_name, numprocs)
        # rebuild the process configs from the new Supervisor configuration
        for group_name in program_configs:
            server_options.reload_processes_from_section(section, group_name)
        return obsolete_processes

    def delete_processes(self, namespecs: NameList):
        """ Remove processes from the internal Supervisor structure.
        This is consecutive to update_numprocs in the event where the new numprocs is lower than the existing one.

        :param namespecs: the namespecs to delete
        :return: None
        """
        for namespec in namespecs:
            # get Supervisor process from namespec
            group_name, process_name = split_namespec(namespec)
            group = self.supervisord.process_groups[group_name]
            process = group.processes[process_name]
            # fire event to Supervisor listeners
            notify(ProcessRemovedEvent(process))
            # delete the process from the group
            del group.processes[process_name]

    # Supervisor issue #591
    def read_disabilities(self) -> None:
        """ Read disabilities file and apply data to Supervisor processes.

        :return: None
        """
        self.disabilities = {}
        disabilities_file = self.supvisors.options.disabilities_file
        self.logger.debug(f'SupervisorData.read_disabilities: disabilities_file={disabilities_file}')
        if disabilities_file:
            if os.path.isfile(disabilities_file):
                with open(disabilities_file) as in_file:
                    data = json.load(in_file)
                    if type(data) is dict:
                        self.disabilities = data
                        self.logger.debug(f'SupervisorData.read_disabilities: disabilities={self.disabilities}')
            else:
                self.logger.debug(f'SupervisorData.read_disabilities: disabilities_file={disabilities_file} not found')
        else:
            self.logger.warn('SupervisorData.read_disabilities: no persistence for program disabilities')

    def write_disabilities(self, force: bool = True) -> None:
        """ Write disabilities file from Supervisor processes.
        If forced (default), the file will be written with the current status.
        If not forced, the file will be written if it does not exist.

        :param force: if True, overwrite the existing file.
        :return: None
        """
        disabilities_file = self.supvisors.options.disabilities_file
        if disabilities_file:
            if force or not os.path.isfile(disabilities_file):
                # serialize to the file defined in options
                with open(disabilities_file, 'w+') as out_file:
                    out_file.write(json.dumps(self.disabilities))

    def get_subprocesses(self, program_name) -> NameList:
        """ Find all processes related to the program definition.

        :param program_name: the name of the program, as declared in the configuration files.
        :return: the Subprocess instances corresponding to the program.
        """
        program_groups = self.supvisors.server_options.program_processes[program_name]
        return [make_namespec(group_name, process_config.name)
                for group_name, process_config_list in program_groups.items()
                for process_config in process_config_list]

    def enable_program(self, program_name: str) -> None:
        """ Re-enable the processes to be started and trigger their autostart if configured to.

        :param program_name: the program to enable
        :return: None
        """
        # store the disability value
        self.disabilities[program_name] = False
        # mark the processes as enabled
        # WARN: do NOT use the ProcessConfig from SupvisorsServerOptions because they are unknown to Supervisor
        processes_program = self.supvisors.server_options.processes_program
        for group_name, group in self.supervisord.process_groups.items():
            for process in group.processes.values():
                if processes_program[process.config.name] == program_name:
                    process.config.disabled = False
                    # fire event to Supervisor listeners
                    notify(ProcessEnabledEvent(process))
                    # if autostart configured, process transition will do the job if laststart is reset
                    process.laststart = 0
                    process.transition()
        # persist disabilities file
        self.write_disabilities()

    def disable_program(self, program_name: str) -> None:
        """ Disable the processes so that they cannot be started.
        It is assumed here that they have been stopped properly before.

        :param program_name: the program to disable
        :return: None
        """
        # store the disability value
        self.disabilities[program_name] = True
        # mark the processes as disabled
        # WARN: do NOT use the ProcessConfig from SupvisorsServerOptions because they are unknown to Supervisor
        processes_program = self.supvisors.server_options.processes_program
        for group_name, group in self.supervisord.process_groups.items():
            for process in group.processes.values():
                if processes_program[process.config.name] == program_name:
                    process.config.disabled = True
                    # fire event to Supervisor listeners
                    notify(ProcessDisabledEvent(process))
        # persist disabilities file
        self.write_disabilities()
