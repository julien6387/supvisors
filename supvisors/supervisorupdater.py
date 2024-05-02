# ======================================================================
# Copyright 2024 Julien LE CLEACH
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

from typing import Any, Tuple

from supervisor.loggers import Logger

from .options import SupvisorsServerOptions
from .supervisordata import SupervisorData
from .ttypes import GroupConfigInfo, NameList


class SupervisorUpdater:
    """ Handles the updates to the Supervisor internal data. """

    def __init__(self, supvisors: Any):
        """ Initialization of the attributes.

        :param supvisors: the Supvisors global structure
        """
        self.supvisors = supvisors

    @property
    def logger(self) -> Logger:
        """ Get the Supvisors logger. """
        return self.supvisors.logger

    @property
    def server_options(self) -> SupvisorsServerOptions:
        """ Get the Supvisors view of Supervisor options. """
        return self.supvisors.server_options

    @property
    def supervisor(self) -> SupervisorData:
        """ Get the Supervisor internal data wrapper. """
        return self.supvisors.supervisor_data

    def on_supervisor_start(self):
        """ Update Supervisor internal data for Supvisors support.

        :return: None
        """
        # replace the tail handlers for web ui
        self.supervisor.replace_tail_handlers()
        # replace the default handler for web ui
        self.supervisor.replace_default_handler()
        # complete Supervisor internal data with information extracted from the Supervisor configuration
        self.supervisor.complete_internal_data(self.server_options.process_configs)
        self.server_options.write_disabilities()

    def on_group_added(self, group_name: str):
        """ Update Supervisor internal data for Supvisors support (impact limited on the group).

        :param group_name: the group newly added.
        :return: None.
        """
        self.supervisor.complete_internal_data(self.server_options.process_configs, group_name)
        self.server_options.write_disabilities()

    # Supervisor issue #591
    def enable_program(self, program_name: str) -> None:
        """ Re-enable the processes to be started and trigger their autostart if configured to.

        :param program_name: the program to enable.
        :return: None.
        """
        # update Supervisor
        self.supervisor.enable_program(program_name)
        # persist disabilities file
        self.server_options.enable_program(program_name)

    def disable_program(self, program_name: str) -> None:
        """ Disable the processes so that they cannot be started.

        :param program_name: the program to disable
        :return: None
        """
        # update Supervisor
        self.supervisor.disable_program(program_name)
        # persist disabilities file
        self.server_options.disable_program(program_name)

    # Supervisor issue #177
    def update_numprocs(self, program_name: str, new_numprocs: int) -> Tuple[NameList, NameList]:
        """ This method is used to dynamically update the program numprocs.
        Implementation of Supervisor issue #177 - Dynamic numproc change

        :param program_name: the program name, as found in the sections of the Supervisor configuration files.
        :param new_numprocs: the new numprocs value.
        :return: the list of processes added and removed (and eventually to stop before removal).
        """
        program = self.server_options.program_configs[program_name]
        ref_numprocs = program.numprocs
        self.logger.debug(f'SupervisorUpdater.update_numprocs: {program_name} ref_numprocs={ref_numprocs}'
                          f' new_numprocs={new_numprocs}')
        # increase or decrease logic
        if ref_numprocs > new_numprocs:
            # return the processes to stop if numprocs decreases, based on the current config
            current_program_configs = self.server_options.program_configs[program_name]
            process_list = self._get_obsolete_processes(new_numprocs, current_program_configs.group_config_info)
            # update ServerOptions parser with the new numprocs value for the considered program
            self.server_options.update_numprocs(program_name, new_numprocs)
            return [], process_list
        if ref_numprocs < new_numprocs:
            # update ServerOptions parser with the new numprocs value for the considered program
            new_group_configs = self.server_options.update_numprocs(program_name, new_numprocs)
            # add the new processes into Supervisor, based on the new config
            process_list = self._add_processes(ref_numprocs, new_group_configs)
            return process_list, []
        # else equal / no change
        return [], []

    def _get_obsolete_processes(self, numprocs: int, new_group_configs: GroupConfigInfo) -> NameList:
        """ Return the obsolete processes in accordance with the new numprocs.

        The program may be used in many groups.
        NOTE: the process configs are NOT deleted yet as the processes may need to be stopped before.

        :param numprocs: the new numprocs value.
        :param new_group_configs: the new program configurations per group name.
        :return: the obsolete process namespecs.
        """
        # get the excess processes
        group_processes = {group_name: [process_config.name
                                        for process_config in process_configs[numprocs:]]
                           for group_name, process_configs in new_group_configs.items()}
        # mark them as obsolete in Supervisor
        return self.supervisor.obsolete_processes(group_processes)

    def _add_processes(self, ref_numprocs: int, new_group_configs: GroupConfigInfo) -> NameList:
        """ Add new processes to all Supervisor groups already including it.

        :param ref_numprocs: the former numprocs value.
        :param new_group_configs: the new program configurations per group name.
        :return: the namespecs of the newly created processes.
        """
        new_namespecs = []
        for group_name, process_configs in new_group_configs.items():
            # the new processes are those over the previous numprocs value
            for process_config in process_configs[ref_numprocs:]:
                alt_config = self.server_options.process_configs[process_config.name]
                new_namespec = self.supervisor.add_supervisor_process(group_name, process_config, alt_config)
                if new_namespec:
                    new_namespecs.append(new_namespec)
        self.logger.info(f'SupervisorUpdater._add_processes: new_namespecs={new_namespecs}')
        return new_namespecs
