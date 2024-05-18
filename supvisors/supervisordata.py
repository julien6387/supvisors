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
import socket
import time
from typing import Any, Dict, List, Optional

from supervisor.datatypes import Syslog
from supervisor.events import notify
from supervisor.http import supervisor_auth_handler, logtail_handler, mainlogtail_handler
from supervisor.loggers import Logger
from supervisor.medusa import default_handler, filesys
from supervisor.options import make_namespec, split_namespec, ProcessConfig
from supervisor.process import ProcessGroupBase, Subprocess
from supervisor.states import ProcessStates, STOPPED_STATES

from .ttypes import (ProcessAddedEvent, ProcessRemovedEvent, ProcessEnabledEvent, ProcessDisabledEvent,
                     SupvisorsProcessConfig, GroupConfigInfo, NameList)

SUPERVISOR_TAIL_DEFAULT = 1024


def spawn(self):
    """ Overridden Subprocess spawn to handle disabled and obsolete processes.

    :return: the process id or None if the fork() call fails.
    """
    if not self.supvisors_config.program_config.disabled and not self.obsolete:
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


class SupervisorData:
    """ Supvisors is started in Supervisor so Supervisor internal data is available from the supervisord structure. """

    # shortcuts
    _system_rpc_interface = None
    _supervisor_rpc_interface = None
    _supvisors_rpc_interface = None

    def __init__(self, supvisors, supervisord):
        """ Initialization of the attributes.

        :param supvisors: the Supvisors global structure
        :param supervisord: the Supervisor global structure
        """
        self.supvisors = supvisors
        self.supervisord = supervisord
        # check HTTP configuration
        for config in supervisord.options.server_configs:
            if config['family'] == socket.AF_INET:
                self.server_config = config
                break
        else:
            # there MUST be an inet HTTP server
            raise ValueError(f'Supervisor MUST be configured using inet_http_server: {supervisord.options.configfile}')

    @property
    def logger(self) -> Logger:
        """ Get the Supvisors logger. """
        return self.supvisors.logger

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
    def complete_internal_data(self, process_configs: Dict[str, SupvisorsProcessConfig],
                               group_name: str = None) -> None:
        """ Add extra attributes to Supervisor internal data.

        This is triggered in two occasions:
        1) when Supervisor sends its RUNNING state ;
        2) when groups are added to Supervisor.

        Note that the initial group added events are sent before the Supvisors RPC interface is created.

        :param process_configs: the process configuration extension.
        :param group_name: the name of the group that has been added to the Supervisor internal data.
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
                alt_process_config = process_configs[process.config.name]
                self.complete_process(process, alt_process_config)

    def get_group_processes(self, application_name: str) -> List[Subprocess]:
        """ This method returns the processes related to a group.

        :param application_name: the group name
        :return: a list of Supervisor processes
        """
        # WARN: the method may throw a KeyError exception
        return self.supervisord.process_groups[application_name].processes

    def _get_process(self, namespec: str) -> Subprocess:
        """ This method returns the process configuration related to a namespec. """
        # WARN: the method may throw a KeyError exception
        application_name, process_name = split_namespec(namespec)
        return self.get_group_processes(application_name)[process_name]

    def _get_process_config(self, namespec: str) -> ProcessConfig:
        """ This method returns the process configuration related to a namespec. """
        return self._get_process(namespec).config

    def autorestart(self, namespec: str) -> bool:
        """ This method checks if autorestart is configured on the program. """
        return self._get_process_config(namespec).autorestart is not False

    def disable_autorestart(self, namespec: str) -> None:
        """ This method forces the autorestart to False in Supervisor internal data. """
        self._get_process_config(namespec).autorestart = False

    def get_process_info(self, namespec: str) -> Dict[str, Any]:
        """ Get the process monotonic values and extra arguments.

        :param namespec: the program namespec.
        :return: a dictionary of configuration values.
        """
        process = self._get_process(namespec)
        return {'start_monotonic': process.laststart_monotonic,
                'stop_monotonic': process.laststop_monotonic,
                'now_monotonic': time.monotonic(),
                'extra_args': process.extra_args,
                'startsecs': process.config.startsecs,
                'stopwaitsecs': process.config.stopwaitsecs,
                'process_index': process.supvisors_config.process_index,
                'program_name': process.supvisors_config.program_config.name,
                'disabled': process.supvisors_config.program_config.disabled,
                'has_stdout': process.config.stdout_logfile not in [None, Syslog],
                'has_stderr': process.config.stderr_logfile not in [None, Syslog]}

    def has_logfile(self, namespec: str, channel: str) -> bool:
        """ Return True if the process has a logfile configuration on the channel.

        :param namespec: the program namespec.
        :param channel: the logfile channel (stdout or stderr).
        :return: True if the process has a logfile configured on the channel.
        """
        process_config = self._get_process_config(namespec)
        return getattr(process_config, '%s_logfile' % channel)

    # Supervisor issue #1023
    def update_extra_args(self, namespec: str, extra_args: str) -> None:
        """ This method is used to add extra arguments to the command line.
        Implementation of Supervisor issue #1023 - Pass arguments to program when starting a job.

        :param namespec: the process namespec.
        :param extra_args: the arguments to be added to the program command line.
        :return: None.
        """
        process = self._get_process(namespec)
        # reset command line
        process.config.command = process.supvisors_config.command_ref
        process.extra_args = extra_args
        # apply args to command line
        if extra_args:
            process.config.command += ' ' + extra_args
        self.logger.trace(f'SupervisorData.update_extra_args: {namespec} extra_args={extra_args}')

    def update_start(self, namespec: str) -> None:
        """ Add the monotonic start time to the internal process.

        :param namespec: the process namespec.
        :return: None.
        """
        process = self._get_process(namespec)
        process.laststart_monotonic = time.monotonic()

    def update_stop(self, namespec: str) -> None:
        """ Add the monotonic stop time to the internal process.

        :param namespec: the process namespec.
        :return: None.
        """
        # get Supervisor process from namespec
        group_name, process_name = split_namespec(namespec)
        group = self.supervisord.process_groups[group_name]
        process = group.processes[process_name]
        if process.obsolete:
            # if process is marked as obsolete following a decrease of numprocs, delete it
            self.delete_process(group, process)
        else:
            # update monotonic stop time
            process.laststop_monotonic = time.monotonic()

    def force_process_fatal(self, namespec: str, reason: str) -> None:
        """ This method forces the FATAL process state into Supervisor internal data and dispatches process event
        to event listeners. """
        process = self._get_process(namespec)
        # need to force BACKOFF state to go through assertion
        process.state = ProcessStates.BACKOFF
        process.spawnerr = reason
        process.give_up()

    # Supervisor issue #591
    def enable_program(self, program_name: str) -> None:
        """ Re-enable the processes to be started and trigger their autostart if configured to.

        :param program_name: the program to enable
        :return: None
        """
        for group_name, group in self.supervisord.process_groups.items():
            for process in group.processes.values():
                if process.supvisors_config.program_config.name == program_name:
                    process.supvisors_config.program_config.disabled = False
                    # fire event to Supervisor listeners
                    notify(ProcessEnabledEvent(process))
                    # if autostart configured, process transition will do the job if laststart is reset
                    process.laststart = 0
                    process.laststart_monotonic = 0.0
                    process.transition()

    def disable_program(self, program_name: str) -> None:
        """ Disable the processes so that they cannot be started.
        It is assumed here that they have been stopped properly before.

        :param program_name: the program to disable
        :return: None
        """
        for group_name, group in self.supervisord.process_groups.items():
            for process in group.processes.values():
                if process.supvisors_config.program_config.name == program_name:
                    process.supvisors_config.program_config.disabled = True
                    # fire event to Supervisor listeners
                    notify(ProcessDisabledEvent(process))

    # Supervisor issue #177
    def add_supervisor_process(self, group_name: str, process_config: ProcessConfig,
                               supvisors_config: SupvisorsProcessConfig) -> Optional[str]:
        """ Add new processes to the Supervisor group from the configuration built.

        :param group_name: the group that embed the program definition.
        :param process_config: the new process configurations to add to the group.
        :param supvisors_config: set to True if the program is disabled.
        :return: the new process namespecs.
        """
        # add new process configs to group in Supervisor
        group = self.supervisord.process_groups[group_name]
        # check if there's a corresponding process in the group (obsolete expected)
        process = group.processes.get(process_config.name)
        if process:
            if not process.obsolete:
                self.logger.error('SupervisorData.add_supervisor_process: unexpected non-obsolete'
                                  f' process={process_config.name} in group={group_name}')
            process.obsolete = False
            return None
        # create processes from new process configs
        self.logger.info(f'SupervisorData.add_supervisor_process: add process={process_config.name}')
        # WARN: replace process_config Supvisors server_options by Supervisor options
        #       this is causing "reaped unknown pid" at exit due to inadequate pidhistory
        process_config.options = self.supervisord.options
        # create a new process from the config
        process = process_config.make_process(group)
        # additional Supvisors attributes
        self.complete_process(process, supvisors_config)
        # prepare log files
        process_config.create_autochildlogs()
        # add the new process to the group processes
        group.processes[process_config.name] = process
        # add the new process config to the group process configs (used by supervisor.getAllConfigInfo)
        group.config.process_configs.append(process_config)
        # fire event to Supervisor listeners
        notify(ProcessAddedEvent(process))
        return make_namespec(group_name, process_config.name)

    def obsolete_processes(self, group_processes: GroupConfigInfo) -> NameList:
        """ Mark the selected processes as obsolete. """
        obsolete_processes = []
        for group_name, candidates in group_processes.items():
            group = self.supervisord.process_groups[group_name]
            for process_name in candidates:
                process = group.processes[process_name]
                if process.state in STOPPED_STATES:
                    # deleted processes are not added to the list of obsolete processes
                    self.delete_process(group, process)
                else:
                    process.obsolete = True
                    # add the process namespec to the list pf obsolete processes
                    obsolete_processes.append(make_namespec(group_name, process_name))
        return obsolete_processes

    @staticmethod
    def complete_process(process: Subprocess, supvisors_config: SupvisorsProcessConfig):
        """ Add addition configuration to the process and to its config structure. """
        # prepare monotonic start/stop times
        process.laststart_monotonic = 0.0
        process.laststop_monotonic = 0.0
        # prepare the process obsolescence (in case of numprocs decrease)
        process.obsolete = False
        # prepare extra arguments
        process.extra_args = ''
        # store the extended process config
        process.supvisors_config = supvisors_config

    def delete_process(self, group: ProcessGroupBase, process: Subprocess):
        """ Delete a process from Supervisor internal data. """
        self.logger.warn(f'SupervisorData.delete_process: delete process={process.config.name}'
                         f' in group={group.config.name}')
        # fire event to Supervisor listeners
        notify(ProcessRemovedEvent(process))
        # delete the process from the group
        del group.processes[process.config.name]
        # delete the process config
        group.config.process_configs.remove(process.config)
